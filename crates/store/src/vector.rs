//! Text embedding for semantic search.
//!
//! Two backends, selected at runtime:
//!
//! 1. **ONNX** (`onnx-embed` feature, default): `all-MiniLM-L6-v2` via `fastembed`.
//!    384-dimensional sentence embeddings. Model downloaded once to
//!    `~/.cache/fastembed/` on first use (~22 MB).
//!
//! 2. **Hash fallback**: FNV-1a feature hashing (unigrams + bigrams).
//!    384-dimensional, no external dependencies, deterministic.
//!    Used when the ONNX model is unavailable or the feature is disabled.
//!
//! `VECTOR_DIM = 384` is the canonical dimension for both paths.

pub const VECTOR_DIM: usize = 384;

// ── ONNX backend (optional) ───────────────────────────────────────────────

#[cfg(feature = "onnx-embed")]
mod onnx {
    use fastembed::{EmbeddingModel, InitOptions, TextEmbedding};
    use std::sync::{Mutex, OnceLock};
    use tracing::{info, warn};

    // TextEmbedding::embed() requires &mut self, so we wrap in Mutex.
    static EMBEDDER: OnceLock<Option<Mutex<TextEmbedding>>> = OnceLock::new();

    fn cell() -> &'static Option<Mutex<TextEmbedding>> {
        EMBEDDER.get_or_init(|| {
            let opts = InitOptions::new(EmbeddingModel::AllMiniLML6V2);
            match TextEmbedding::try_new(opts) {
                Ok(e) => {
                    info!("fastembed: all-MiniLM-L6-v2 ready (384-dim)");
                    Some(Mutex::new(e))
                }
                Err(e) => {
                    warn!("fastembed init failed, falling back to hash embedding: {e}");
                    None
                }
            }
        })
    }

    /// Embed a single text string; returns `None` when ONNX is unavailable.
    pub fn embed(text: &str) -> Option<Vec<f32>> {
        let mutex = cell().as_ref()?;
        let mut guard = mutex.lock().ok()?;
        match guard.embed(vec![text], None) {
            Ok(mut vecs) if !vecs.is_empty() => Some(vecs.remove(0)),
            Ok(_) => None,
            Err(e) => {
                warn!("fastembed embed error: {e}");
                None
            }
        }
    }
}

// ── Public API ─────────────────────────────────────────────────────────────

/// Compute a 384-dim f32 embedding for `text`.
///
/// Uses `all-MiniLM-L6-v2` (ONNX) when available; otherwise falls back to
/// FNV-1a feature hashing. Both paths produce 384-dim unit vectors, so
/// cosine similarity works consistently regardless of which path ran.
pub fn embed_text(text: &str) -> Vec<f32> {
    #[cfg(feature = "onnx-embed")]
    if let Some(v) = onnx::embed(text) {
        return v;
    }
    embed_text_hash(text)
}

/// Cosine similarity between two equal-length vectors.
/// Returns 0.0 for zero vectors or mismatched lengths.
///
/// Adapted from project-resonance/crates/resonance-field/src/field.rs.
pub fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() || a.is_empty() {
        return 0.0;
    }
    let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm_a == 0.0 || norm_b == 0.0 {
        0.0
    } else {
        (dot / (norm_a * norm_b)).clamp(-1.0, 1.0)
    }
}

/// Serialize a Vec<f32> to bytes (little-endian f32 array).
pub fn encode_embedding(v: &[f32]) -> Vec<u8> {
    let mut out = Vec::with_capacity(v.len() * 4);
    for &x in v {
        out.extend_from_slice(&x.to_le_bytes());
    }
    out
}

/// Deserialize bytes to Vec<f32>. Returns empty vec on length mismatch.
pub fn decode_embedding(bytes: &[u8]) -> Vec<f32> {
    if bytes.len() % 4 != 0 {
        return Vec::new();
    }
    bytes
        .chunks_exact(4)
        .map(|b| f32::from_le_bytes([b[0], b[1], b[2], b[3]]))
        .collect()
}

// ── Hash fallback ─────────────────────────────────────────────────────────

/// FNV-1a feature-hash embedding: 384-dim, no external dependencies.
/// Used when the ONNX backend is unavailable.
pub fn embed_text_hash(text: &str) -> Vec<f32> {
    let tokens = tokenize(text);
    let mut vec = vec![0.0f32; VECTOR_DIM];

    for tok in &tokens {
        let idx = fnv1a(tok.as_bytes()) % VECTOR_DIM;
        vec[idx] += 1.0;
    }
    for pair in tokens.windows(2) {
        let bigram = format!("{}\x00{}", pair[0], pair[1]);
        let idx = fnv1a(bigram.as_bytes()) % VECTOR_DIM;
        vec[idx] += 0.5;
    }

    l2_normalize(&mut vec);
    vec
}

// ── Internals ─────────────────────────────────────────────────────────────

fn tokenize(text: &str) -> Vec<String> {
    let lower = text.to_lowercase();
    lower
        .split(|c: char| !c.is_alphanumeric())
        .filter(|s| s.len() >= 2 && !is_stopword(s))
        .map(str::to_string)
        .collect()
}

fn l2_normalize(v: &mut [f32]) {
    let norm: f32 = v.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm > 1e-9 {
        for x in v.iter_mut() {
            *x /= norm;
        }
    }
}

fn fnv1a(bytes: &[u8]) -> usize {
    let mut h: u32 = 2_166_136_261;
    for &b in bytes {
        h ^= b as u32;
        h = h.wrapping_mul(16_777_619);
    }
    h as usize
}

fn is_stopword(w: &str) -> bool {
    matches!(
        w,
        "the"
            | "a"
            | "an"
            | "is"
            | "are"
            | "was"
            | "were"
            | "be"
            | "been"
            | "being"
            | "have"
            | "has"
            | "had"
            | "do"
            | "does"
            | "did"
            | "will"
            | "would"
            | "could"
            | "should"
            | "may"
            | "might"
            | "shall"
            | "can"
            | "to"
            | "of"
            | "in"
            | "for"
            | "on"
            | "with"
            | "at"
            | "by"
            | "from"
            | "it"
            | "its"
            | "this"
            | "that"
            | "and"
            | "or"
            | "but"
            | "not"
            | "no"
            | "if"
            | "as"
            | "so"
            | "than"
            | "then"
            | "when"
            | "where"
            | "which"
            | "who"
            | "what"
            | "how"
            | "we"
            | "i"
            | "you"
            | "he"
            | "she"
            | "they"
            | "them"
            | "their"
            | "our"
            | "my"
            | "your"
            | "his"
            | "her"
    )
}

// ── Tests ─────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_text_same_vector() {
        let a = embed_text_hash("Warp IPC socket");
        let b = embed_text_hash("Warp IPC socket");
        assert_eq!(a, b);
    }

    #[test]
    fn hash_dim_is_384() {
        let v = embed_text_hash("hello world");
        assert_eq!(v.len(), VECTOR_DIM);
        assert_eq!(VECTOR_DIM, 384);
    }

    #[test]
    fn similar_texts_high_similarity() {
        let a = embed_text_hash("terminal send keys IPC socket warp");
        let b = embed_text_hash("IPC socket warp terminal");
        let sim = cosine_similarity(&a, &b);
        assert!(sim > 0.5, "expected high similarity, got {sim}");
    }

    #[test]
    fn unrelated_texts_low_similarity() {
        let a = embed_text_hash("cargo build rust terminal");
        let b = embed_text_hash("user profile markdown photo camera");
        let sim = cosine_similarity(&a, &b);
        assert!(sim < 0.5, "expected low similarity, got {sim}");
    }

    #[test]
    fn roundtrip_encode_decode() {
        let v = embed_text_hash("hello world test");
        let bytes = encode_embedding(&v);
        let decoded = decode_embedding(&bytes);
        assert_eq!(v.len(), decoded.len());
        for (a, b) in v.iter().zip(decoded.iter()) {
            assert!((a - b).abs() < 1e-6);
        }
    }
}
