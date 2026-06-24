//! Text embedding for semantic search — low-level primitives.
//!
//! This module provides the two **built-in** embedding implementations:
//!
//! 1. **ONNX** (`onnx-embed` feature, default): `all-MiniLM-L6-v2` via `fastembed`.
//!    384-dim sentence embeddings; model auto-downloads to `~/.cache/fastembed/`.
//! 2. **Hash fallback**: FNV-1a feature hashing (unigrams + bigrams). 384-dim,
//!    no external deps, deterministic.
//!
//! Both paths produce unit vectors so cosine similarity is consistent
//! regardless of which path ran. The canonical dimension is **model-aware**:
//! 384 for e5/MiniLM/para-ml, 768 for gte-multilingual-base — resolved at
//! runtime by [`vector_dim`] from the active model name.
//!
//! Pluggable backend selection (e.g. swapping in AIoT Rust Seed) lives in
//! [`crate::embedding`]. The free function [`embed_text`] is a compatibility
//! shim that delegates to `embedding::default_backend()`.

/// Dimension for a stable embedding backend label.
pub(crate) fn vector_dim_for_model_name(model_name: &str) -> usize {
    match model_name {
        "gte-multilingual-base" => 768,
        _ => 384,
    }
}

/// Canonical embedding dimension for the active model (model-aware, runtime).
///
/// 768 for `gte-multilingual-base`, else 384 (e5 / MiniLM / para-ml). The
/// active model name is memoised via [`active_model_name`], so repeated calls
/// are cheap. e5/MiniLM stores stay byte-for-byte 384-dim — this only widens
/// to 768 when gte is the active model.
pub fn vector_dim() -> usize {
    #[cfg(feature = "onnx-embed")]
    {
        vector_dim_for_model_name(onnx::active_model_name())
    }
    #[cfg(not(feature = "onnx-embed"))]
    {
        384
    }
}

// ── ONNX backend (optional) ───────────────────────────────────────────────

#[cfg(feature = "onnx-embed")]
pub(crate) mod onnx {
    use fastembed::{
        EmbeddingModel, InitOptions, InitOptionsUserDefined, Pooling, QuantizationMode,
        TextEmbedding, TokenizerFiles, UserDefinedEmbeddingModel,
    };
    use std::sync::atomic::{AtomicU8, Ordering};
    use std::sync::{Mutex, OnceLock};
    use tracing::{info, warn};

    // Init state machine for the fastembed model.
    //
    // The naïve previous impl called `TextEmbedding::try_new` inside
    // `OnceLock::get_or_init` — which blocked the *caller's* thread for
    // however long the first-time model download took. On hosts with no
    // model cached (e.g. fresh machines onboarded to cross-device sync),
    // memory_import → memory_save → embed would silently hang the entire
    // MCP request until the MCP timeout killed the process. No log line,
    // no fall-through. See `feedback_onnx_backend_hangs_without_model`.
    //
    // New impl: init runs on a one-shot background thread kicked off
    // lazily. Callers see `embed → None` until init completes (which
    // makes the outer `OnnxBackend::embed` fall through to HashBackend),
    // then once the model is ready they pick up the higher-quality
    // path on the next call. Process exit kills the bg thread naturally.
    //
    // INIT_STATE: 0=not started, 1=in progress, 2=done (success xor failure).
    static EMBEDDER: OnceLock<Option<Mutex<TextEmbedding>>> = OnceLock::new();
    static INIT_STARTED: OnceLock<()> = OnceLock::new();
    static INIT_STATE: AtomicU8 = AtomicU8::new(0);

    /// Opt-in embedding-model selection via `AGENT_BRIDGE_ONNX_MODEL`.
    /// Default is unchanged (`all-MiniLM-L6-v2`) so existing stores and sibling
    /// lanes are not forced onto a new backend. `AGENT_BRIDGE_ONNX_MODEL=e5-small`
    /// switches to the bilingual `multilingual-e5-small` (also 384-dim, so
    /// `VECTOR_DIM` is unchanged) — the #1447 retrieval-quality win for the
    /// Chinese-dominant memory corpus. Returns (model, stable-name, needs-e5-prefix).
    fn select_model() -> (EmbeddingModel, &'static str, bool) {
        match std::env::var("AGENT_BRIDGE_ONNX_MODEL").ok().as_deref() {
            Some("e5-small") | Some("multilingual-e5-small") => (
                EmbeddingModel::MultilingualE5Small,
                "multilingual-e5-small",
                true,
            ),
            // LEVER 3: paraphrase-multilingual-MiniLM-L12-v2 — 384-dim multilingual,
            // a TRUE drop-in (no VECTOR_DIM migration). Unlike e5 it does NOT collapse
            // Chinese query↔doc cosines into a narrow ~0.86 band — it keeps a wide
            // 0.2–0.7 spread, so ranking margins survive corpus-scale dilution AND the
            // absolute-cosine consumers (e.g. introspect novelty) stay meaningful. No
            // task prefix. The #1485/LEVER-3 retrieval-quality model for the
            // Chinese-dominant corpus.
            Some("para-ml")
            | Some("paraphrase-ml-l12")
            | Some("paraphrase-multilingual-MiniLM-L12-v2") => (
                EmbeddingModel::ParaphraseMLMiniLML12V2,
                "paraphrase-multilingual-MiniLM-L12-v2",
                false,
            ),
            // gte-multilingual-base — 768-dim multilingual (model-aware VECTOR_DIM
            // widens to 768 via `vector_dim()`). The EmbeddingModel here is a
            // placeholder enum: gte always loads via `try_load_local` from a local
            // ONNX dir (the enum is only consulted by the broken hf-hub download
            // fallback, which can't fetch gte anyway). No task prefix.
            Some("gte") | Some("gte-ml") | Some("gte-multilingual-base") => (
                EmbeddingModel::MultilingualE5Small,
                "gte-multilingual-base",
                false,
            ),
            _ => (EmbeddingModel::AllMiniLML6V2, "all-MiniLM-L6-v2", false),
        }
    }

    /// Stable name of the active ONNX model (memoised; reflects the env choice).
    /// Feeds the `embedding_backend` column so e5 vectors are never mixed with
    /// MiniLM vectors at query time.
    pub fn active_model_name() -> &'static str {
        static N: OnceLock<&'static str> = OnceLock::new();
        N.get_or_init(|| select_model().1)
    }

    fn e5_prefix() -> bool {
        static E: OnceLock<bool> = OnceLock::new();
        *E.get_or_init(|| select_model().2)
    }

    /// E5 models expect a `query: ` / `passage: ` task prefix; for symmetric
    /// memory↔memory similarity we use `query: ` uniformly (matches the #1447
    /// study). MiniLM takes the raw text.
    fn prep(text: &str) -> String {
        if e5_prefix() {
            format!("query: {text}")
        } else {
            text.to_string()
        }
    }

    /// Load the active model from a local directory via fastembed's
    /// user-defined path, bypassing fastembed's hf-hub download.
    ///
    /// Dir: `$AGENT_BRIDGE_ONNX_MODEL_DIR/<model-name>/` (default
    /// `~/.cache/agent-bridge/onnx-models/<model-name>/`) holding model.onnx +
    /// tokenizer.json + config.json + special_tokens_map.json +
    /// tokenizer_config.json. Used because fastembed's bundled hf-hub client
    /// cannot follow HF's Xet CDN redirect on this environment (every model
    /// download fails → permanent hash fallback); the files are fetched from
    /// ModelScope instead and placed here. Returns None if the dir is absent or
    /// incomplete, so the caller falls back to the normal download path.
    fn try_load_local() -> Option<TextEmbedding> {
        let base = std::env::var("AGENT_BRIDGE_ONNX_MODEL_DIR").unwrap_or_else(|_| {
            let home = std::env::var("HOME").unwrap_or_default();
            format!("{home}/.cache/agent-bridge/onnx-models")
        });
        let dir = std::path::Path::new(&base).join(active_model_name());
        if !dir.join("model.onnx").exists() {
            return None;
        }
        let rd = |f: &str| std::fs::read(dir.join(f));
        let build = || -> std::io::Result<UserDefinedEmbeddingModel> {
            Ok(UserDefinedEmbeddingModel {
                onnx_file: rd("model.onnx")?,
                external_initializers: Vec::new(),
                tokenizer_files: TokenizerFiles {
                    tokenizer_file: rd("tokenizer.json")?,
                    config_file: rd("config.json")?,
                    special_tokens_map_file: rd("special_tokens_map.json")?,
                    tokenizer_config_file: rd("tokenizer_config.json")?,
                },
                pooling: Some(Pooling::Mean), // e5 / MiniLM are mean-pooled
                quantization: QuantizationMode::None,
                output_key: None,
            })
        };
        let model = match build() {
            Ok(m) => m,
            Err(e) => {
                warn!(
                    "fastembed local model dir {} incomplete: {e}",
                    dir.display()
                );
                return None;
            }
        };
        let mut opts = InitOptionsUserDefined::new();
        opts.max_length = 512;
        match TextEmbedding::try_new_from_user_defined(model, opts) {
            Ok(e) => {
                info!(
                    "fastembed: {} loaded from {} (user-defined, no hf-hub)",
                    active_model_name(),
                    dir.display()
                );
                Some(e)
            }
            Err(e) => {
                warn!(
                    "fastembed user-defined load failed for {}: {e}",
                    dir.display()
                );
                None
            }
        }
    }

    fn kickoff_init() {
        INIT_STARTED.get_or_init(|| {
            INIT_STATE.store(1, Ordering::Release);
            std::thread::Builder::new()
                .name("fastembed-init".into())
                .spawn(|| {
                    let started = std::time::Instant::now();
                    // Prefer a local model dir (ModelScope-fetched, no hf-hub);
                    // fall back to fastembed's own download if absent.
                    let result = match try_load_local() {
                        Some(e) => Ok(e),
                        None => TextEmbedding::try_new(InitOptions::new(select_model().0)),
                    };
                    let elapsed = started.elapsed();
                    let payload = match result {
                        Ok(e) => {
                            let model_name = active_model_name();
                            info!(
                                "fastembed: {} ready ({}-dim) — init {:.1}s",
                                model_name,
                                super::vector_dim_for_model_name(model_name),
                                elapsed.as_secs_f32()
                            );
                            Some(Mutex::new(e))
                        }
                        Err(e) => {
                            warn!(
                                "fastembed init failed after {:.1}s, falling back to hash embedding permanently: {e}",
                                elapsed.as_secs_f32()
                            );
                            None
                        }
                    };
                    // EMBEDDER is OnceLock; ignore re-set error (can't happen
                    // because INIT_STARTED gates this thread to one runner).
                    let _ = EMBEDDER.set(payload);
                    INIT_STATE.store(2, Ordering::Release);
                })
                .expect("fastembed init thread spawn");
        });
    }

    /// Return the live ONNX embedder *if* init has completed successfully.
    /// During the init window (state=1) returns `None`; callers must fall
    /// back to hash. Once state=2, returns the cached embedder (or `None`
    /// if init permanently failed). Never blocks the caller.
    fn try_cell() -> Option<&'static Mutex<TextEmbedding>> {
        kickoff_init();
        if INIT_STATE.load(Ordering::Acquire) != 2 {
            return None;
        }
        EMBEDDER.get()?.as_ref()
    }

    /// Embed a single text string; returns `None` when ONNX is unavailable
    /// (model not cached, init still in progress, or permanent failure).
    pub fn embed(text: &str) -> Option<Vec<f32>> {
        let mutex = try_cell()?;
        let mut guard = mutex.lock().ok()?;
        let prepped = prep(text);
        match guard.embed(vec![prepped.as_str()], None) {
            Ok(mut vecs) if !vecs.is_empty() => Some(vecs.remove(0)),
            Ok(_) => None,
            Err(e) => {
                warn!("fastembed embed error: {e}");
                None
            }
        }
    }

    /// Batch-embed multiple texts in one forward pass. Amortises the
    /// attention compute across `texts.len()` items — significantly faster
    /// than per-row [`embed`] when N > a few. Returns `None` when ONNX is
    /// unavailable; on individual failure, returns `None` for the whole
    /// batch (caller should fall back to hash per-row).
    pub fn embed_batch(texts: Vec<String>) -> Option<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Some(Vec::new());
        }
        let mutex = try_cell()?;
        let mut guard = mutex.lock().ok()?;
        let prepped: Vec<String> = texts.iter().map(|s| prep(s)).collect();
        let refs: Vec<&str> = prepped.iter().map(|s| s.as_str()).collect();
        match guard.embed(refs, None) {
            Ok(vecs) => Some(vecs),
            Err(e) => {
                warn!("fastembed embed_batch error: {e}");
                None
            }
        }
    }
}

// ── Public API ─────────────────────────────────────────────────────────────

/// Compute a 384-dim f32 embedding for `text` using the active default backend.
///
/// The default backend is resolved once per process via
/// [`crate::embedding::default_backend`] (selected by the
/// `AGENT_BRIDGE_EMBED_BACKEND` env var, falling back to ONNX when the
/// `onnx-embed` feature is on, otherwise hash). Custom backends — e.g. the
/// AIoT Rust Seed inference kernel — can be installed at startup via
/// [`crate::embedding::set_default_backend`] and will be used here too.
pub fn embed_text(text: &str) -> Vec<f32> {
    crate::embedding::default_backend().embed(text)
}

/// Eagerly kick off embedding-model initialization (non-blocking). The ONNX
/// init runs on a background thread that takes seconds for large models
/// (~7.5s for para-ml's 470 MB L12). Calling this at process startup lets the
/// model load DURING startup so the first real query neither pays the cold
/// latency NOR falls back to the hash backend — which, against a real-model
/// store, returns near-orthogonal garbage cosines (the cold-first-query bug).
/// One throwaway embed triggers the lazy init; the result is discarded.
/// No-op cost for the hash backend.
pub fn warmup() {
    let _ = embed_text("warmup");
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
    let dim = vector_dim();
    let mut vec = vec![0.0f32; dim];

    for tok in &tokens {
        let idx = fnv1a(tok.as_bytes()) % dim;
        vec[idx] += 1.0;
    }
    for pair in tokens.windows(2) {
        let bigram = format!("{}\x00{}", pair[0], pair[1]);
        let idx = fnv1a(bigram.as_bytes()) % dim;
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
        // Tests run with the default model (no AGENT_BRIDGE_ONNX_MODEL set),
        // so the e5/MiniLM/default path must stay 384-dim.
        let v = embed_text_hash("hello world");
        assert_eq!(v.len(), vector_dim());
        assert_eq!(vector_dim(), 384);
    }

    #[test]
    fn model_name_dimension_gate_covers_gte_flagday() {
        assert_eq!(vector_dim_for_model_name("all-MiniLM-L6-v2"), 384);
        assert_eq!(vector_dim_for_model_name("multilingual-e5-small"), 384);
        assert_eq!(
            vector_dim_for_model_name("paraphrase-multilingual-MiniLM-L12-v2"),
            384
        );
        assert_eq!(vector_dim_for_model_name("gte-multilingual-base"), 768);
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
