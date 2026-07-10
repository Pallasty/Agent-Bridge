//! Pluggable embedding backend.
//!
//! Lets agent-bridge swap the inference kernel without touching call sites.
//! The current built-ins are:
//!
//! - [`OnnxBackend`] — model-aware `fastembed` + `ort`; the compiled default
//!   is 768-dimensional `gte-multilingual-base` when `onnx-embed` is enabled.
//! - [`HashBackend`] — FNV-1a feature hashing (no external deps; default
//!   fallback).
//!
//! External crates (e.g. AIoT's Rust Seed neural network) implement
//! [`EmbeddingBackend`] and register themselves at startup via
//! [`set_default_backend`]:
//!
//! ```ignore
//! use ab_store::embedding::{set_default_backend, EmbeddingBackend};
//! use std::sync::Arc;
//!
//! struct SeedBackend { /* … */ }
//! impl EmbeddingBackend for SeedBackend { /* … */ }
//!
//! ab_store::embedding::set_default_backend(Arc::new(SeedBackend::new()))
//!     .expect("default backend already initialized");
//! ```
//!
//! Selection precedence:
//! 1. Explicit override via [`set_default_backend`] (must be called before
//!    the first embedding lookup).
//! 2. Env var `AGENT_BRIDGE_EMBED_BACKEND` — values: `onnx`, `hash`.
//! 3. Compile-time default: ONNX when `onnx-embed` is on, otherwise hash.

use std::sync::{Arc, OnceLock};

use crate::vector::{embed_text_hash, vector_dim};

/// Common trait for any text → fixed-dim vector encoder.
///
/// Backends MUST produce vectors of `dim()` length. Cosine similarity
/// across rows assumes a single backend across the table — mixing backends
/// silently produces meaningless scores. After switching backends in
/// production, call `memory_reindex` to repopulate.
pub trait EmbeddingBackend: Send + Sync {
    /// Stable identifier (e.g. `"all-MiniLM-L6-v2"`, `"fnv1a-hash-384"`,
    /// `"aiot-seed-v1"`). Used for diagnostics and capability reporting.
    fn name(&self) -> &str;

    /// Vector dimension produced by this backend. Must be constant.
    fn dim(&self) -> usize;

    /// Encode a single text string. Implementations should return a vector
    /// of length `dim()`; if the underlying model fails, falling back to a
    /// deterministic hash vector (see [`HashBackend`]) is acceptable to keep
    /// the call infallible.
    fn embed(&self, text: &str) -> Vec<f32>;

    /// Batch encode. Default impl is a per-row loop; backends with
    /// vectorized inference (ONNX, batched GPU, etc.) should override.
    fn embed_batch(&self, texts: &[&str]) -> Vec<Vec<f32>> {
        texts.iter().map(|t| self.embed(t)).collect()
    }

    /// **P-γ perception** — embed `text_to_embed` for semantic signal but
    /// record `key_to_perceive` as the identifier under which substrate
    /// (if any) indexes this perception event. Decouples *what is embedded*
    /// (long semantic content) from *what queries return* (short opaque
    /// memory key).
    ///
    /// Default impl forwards to [`Self::embed`], discarding the key, so
    /// `HashBackend`/`OnnxBackend` semantics are unchanged. Substrate-
    /// aware backends (`SeedBackend`) override this to call
    /// `step(primary, key_to_perceive)` instead of
    /// `step(primary, text_to_embed)`, so `substrate.neighbors_of(key)`
    /// can find perceived neurons by their memory key.
    fn perceive(&self, text_to_embed: &str, _key_to_perceive: &str) -> Vec<f32> {
        self.embed(text_to_embed)
    }

    /// Batch counterpart to [`Self::perceive`]. `texts` and `keys` must
    /// have the same length; for substrate-aware backends, item `i`
    /// records `keys[i]` as the perception identifier after embedding
    /// `texts[i]`. Default impl forwards to [`Self::embed_batch`],
    /// discarding `keys`.
    fn perceive_batch(&self, texts: &[&str], _keys: &[&str]) -> Vec<Vec<f32>> {
        self.embed_batch(texts)
    }
}

// ── Built-in: hash ────────────────────────────────────────────────────────

/// FNV-1a feature-hash backend. No external dependencies, deterministic,
/// fast (~10 μs / call). Its stable name is retained for store compatibility;
/// [`Self::dim`] and the emitted vector follow the active model-aware dimension.
pub struct HashBackend;

impl EmbeddingBackend for HashBackend {
    fn name(&self) -> &str {
        "fnv1a-hash-384"
    }
    fn dim(&self) -> usize {
        vector_dim()
    }
    fn embed(&self, text: &str) -> Vec<f32> {
        embed_text_hash(text)
    }
}

// ── Built-in: ONNX ────────────────────────────────────────────────────────

/// Model-aware local ONNX sentence embeddings via `fastembed`. The compiled
/// default is `gte-multilingual-base` at 768 dimensions; 384-dimensional
/// e5/MiniLM/para-ml variants are selectable by environment. Falls back to
/// [`HashBackend`] if the model fails to load.
pub struct OnnxBackend;

impl EmbeddingBackend for OnnxBackend {
    fn name(&self) -> &str {
        #[cfg(feature = "onnx-embed")]
        {
            crate::vector::onnx::active_model_name()
        }
        #[cfg(not(feature = "onnx-embed"))]
        {
            "all-MiniLM-L6-v2"
        }
    }
    fn dim(&self) -> usize {
        vector_dim()
    }
    fn embed(&self, text: &str) -> Vec<f32> {
        #[cfg(feature = "onnx-embed")]
        if let Some(v) = crate::vector::onnx::embed(text) {
            return v;
        }
        // Fall through to hash if ONNX disabled or the model didn't load.
        HashBackend.embed(text)
    }

    /// Override to use `fastembed`'s native batch inference — runs a single
    /// forward pass across all texts, amortising attention compute. Real
    /// observation (2026-05-03 friction record): per-row pushed
    /// `memory_import` to ~16s for ~100 rows; batch should bring this to
    /// O(seconds) total. Falls back to per-row hash on failure.
    fn embed_batch(&self, texts: &[&str]) -> Vec<Vec<f32>> {
        if texts.is_empty() {
            return Vec::new();
        }
        #[cfg(feature = "onnx-embed")]
        {
            let owned: Vec<String> = texts.iter().map(|s| s.to_string()).collect();
            if let Some(vecs) = crate::vector::onnx::embed_batch(owned) {
                return vecs;
            }
        }
        // Fall back to per-row hash if ONNX path unavailable.
        texts.iter().map(|t| HashBackend.embed(t)).collect()
    }
}

// ── Default backend selection ─────────────────────────────────────────────

static DEFAULT: OnceLock<Arc<dyn EmbeddingBackend>> = OnceLock::new();

/// Return the active default backend, initializing on first call.
///
/// Selection (high → low priority):
/// 1. A backend previously installed via [`set_default_backend`].
/// 2. `AGENT_BRIDGE_EMBED_BACKEND` env var (`onnx` | `hash`).
/// 3. Compile-time default: ONNX when feature on, hash otherwise.
pub fn default_backend() -> Arc<dyn EmbeddingBackend> {
    DEFAULT.get_or_init(select_default).clone()
}

/// Install a custom backend as the process-wide default.
///
/// Returns `Err` if [`default_backend`] has already been called (the slot is
/// `OnceLock`-protected). Call this **early** during startup, before any
/// `memory_save` / `memory_search` activity.
pub fn set_default_backend(b: Arc<dyn EmbeddingBackend>) -> Result<(), &'static str> {
    DEFAULT
        .set(b)
        .map_err(|_| "default embedding backend already initialized")
}

fn select_default() -> Arc<dyn EmbeddingBackend> {
    let from_env = std::env::var("AGENT_BRIDGE_EMBED_BACKEND").ok();
    let pick = from_env.as_deref().unwrap_or({
        // Under `cfg(test)` the compile-time default is ALWAYS hash, regardless of
        // the `onnx-embed` feature. `cargo test --workspace` unifies features, so an
        // unrelated crate enabling `ab-store/onnx-embed` would otherwise make this
        // process-global `OnceLock` resolve to ONNX on whichever test touches
        // `default_backend()` first — making backend-sensitive tests (e.g. reindex)
        // flaky by scheduling order, which previously required a manual
        // `AGENT_BRIDGE_EMBED_BACKEND=hash` to suppress. Pinning hash here removes the
        // order dependence at the source; an explicit env var still overrides, so an
        // onnx-specific test can opt back in.
        #[cfg(test)]
        {
            "hash"
        }
        #[cfg(all(not(test), feature = "onnx-embed"))]
        {
            "onnx"
        }
        #[cfg(all(not(test), not(feature = "onnx-embed")))]
        {
            "hash"
        }
    });
    match pick {
        "onnx" => {
            #[cfg(feature = "onnx-embed")]
            {
                Arc::new(OnnxBackend)
            }
            #[cfg(not(feature = "onnx-embed"))]
            {
                tracing::warn!(
                    "AGENT_BRIDGE_EMBED_BACKEND=onnx but onnx-embed feature is off; using hash"
                );
                Arc::new(HashBackend)
            }
        }
        "hash" => Arc::new(HashBackend),
        other => {
            tracing::warn!(
                "Unknown AGENT_BRIDGE_EMBED_BACKEND={other:?}; using compile-time default"
            );
            #[cfg(feature = "onnx-embed")]
            {
                Arc::new(OnnxBackend)
            }
            #[cfg(not(feature = "onnx-embed"))]
            {
                Arc::new(HashBackend)
            }
        }
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash_backend_dim_and_determinism() {
        let b = HashBackend;
        // name() is a stable label, not a live dimension; dim()/embed() track
        // the active model via vector_dim() (768 since the gte default flip).
        assert_eq!(b.name(), "fnv1a-hash-384");
        assert_eq!(b.dim(), vector_dim());
        let v1 = b.embed("Warp IPC socket");
        let v2 = b.embed("Warp IPC socket");
        assert_eq!(v1, v2);
        assert_eq!(v1.len(), vector_dim());
    }

    #[test]
    fn batch_default_matches_per_row() {
        let b = HashBackend;
        let texts = ["alpha", "beta", "gamma"];
        let refs: Vec<&str> = texts.iter().copied().collect();
        let batched = b.embed_batch(&refs);
        for (i, t) in texts.iter().enumerate() {
            assert_eq!(batched[i], b.embed(t));
        }
    }
}
