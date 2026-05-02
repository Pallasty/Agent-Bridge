//! Lightweight local text embedding via feature hashing (hash trick).
//!
//! Converts any text to a fixed-size f32 vector without external models or APIs.
//! Uses 512-dimensional hash space with word unigrams + bigrams; good for a
//! corpus of a few hundred memories where BM25 keyword misses near-synonyms.
//!
//! Cosine similarity function adapted from project-resonance (same author).

pub const VECTOR_DIM: usize = 512;

/// Compute a 512-dim f32 embedding for `text` using the hash trick.
///
/// Steps:
///  1. Lowercase + tokenize on non-alphanumeric boundaries
///  2. Remove stopwords
///  3. Hash unigrams + bigrams to [0, VECTOR_DIM) → accumulate counts
///  4. L2-normalize to unit length
///
/// Deterministic: same text always produces the same vector.
pub fn embed_text(text: &str) -> Vec<f32> {
    let tokens = tokenize(text);
    let mut vec = vec![0.0f32; VECTOR_DIM];

    // Unigrams
    for tok in &tokens {
        let idx = fnv1a(tok.as_bytes()) % VECTOR_DIM;
        vec[idx] += 1.0;
    }
    // Bigrams
    for pair in tokens.windows(2) {
        let bigram = format!("{}\x00{}", pair[0], pair[1]);
        let idx = fnv1a(bigram.as_bytes()) % VECTOR_DIM;
        vec[idx] += 0.5; // bigrams down-weighted
    }

    l2_normalize(&mut vec);
    vec
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

// ── internals ────────────────────────────────────────────────────────────────

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

/// FNV-1a 32-bit hash, mapped to usize index.
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
        "the" | "a" | "an" | "is" | "are" | "was" | "were" | "be" | "been" | "being"
        | "have" | "has" | "had" | "do" | "does" | "did" | "will" | "would" | "could"
        | "should" | "may" | "might" | "shall" | "can" | "to" | "of" | "in" | "for"
        | "on" | "with" | "at" | "by" | "from" | "it" | "its" | "this" | "that"
        | "and" | "or" | "but" | "not" | "no" | "if" | "as" | "so" | "than"
        | "then" | "when" | "where" | "which" | "who" | "what" | "how"
        | "we" | "i" | "you" | "he" | "she" | "they" | "them" | "their"
        | "our" | "my" | "your" | "his" | "her"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_text_same_vector() {
        let a = embed_text("Warp IPC socket");
        let b = embed_text("Warp IPC socket");
        assert_eq!(a, b);
    }

    #[test]
    fn similar_texts_high_similarity() {
        let a = embed_text("terminal send keys IPC socket warp");
        let b = embed_text("IPC socket warp terminal");
        let sim = cosine_similarity(&a, &b);
        assert!(sim > 0.5, "expected high similarity, got {sim}");
    }

    #[test]
    fn unrelated_texts_low_similarity() {
        let a = embed_text("cargo build rust terminal");
        let b = embed_text("user profile markdown photo camera");
        let sim = cosine_similarity(&a, &b);
        assert!(sim < 0.5, "expected low similarity, got {sim}");
    }

    #[test]
    fn roundtrip_encode_decode() {
        let v = embed_text("hello world test");
        let bytes = encode_embedding(&v);
        let decoded = decode_embedding(&bytes);
        assert_eq!(v.len(), decoded.len());
        for (a, b) in v.iter().zip(decoded.iter()) {
            assert!((a - b).abs() < 1e-6);
        }
    }
}
