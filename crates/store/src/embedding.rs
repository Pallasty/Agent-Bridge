//! Pluggable embedding backend.
//!
//! Lets agent-bridge swap the inference kernel without touching call sites.
//! The current built-ins are:
//!
//! - [`OnnxBackend`] — `all-MiniLM-L6-v2` via `fastembed` + `ort` (default
//!   when the `onnx-embed` feature is enabled).
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

use crate::vector::{embed_text_hash, VECTOR_DIM};

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
}

// ── Built-in: hash ────────────────────────────────────────────────────────

/// FNV-1a feature-hash backend. No external dependencies, deterministic,
/// fast (~10 μs / call). Used as fallback when ONNX is unavailable.
pub struct HashBackend;

impl EmbeddingBackend for HashBackend {
    fn name(&self) -> &str {
        "fnv1a-hash-384"
    }
    fn dim(&self) -> usize {
        VECTOR_DIM
    }
    fn embed(&self, text: &str) -> Vec<f32> {
        embed_text_hash(text)
    }
}

// ── Built-in: ONNX ────────────────────────────────────────────────────────

/// `all-MiniLM-L6-v2` via `fastembed`. 384-dim sentence embeddings; model
/// downloads on first use to `~/.cache/fastembed/`. Falls back to
/// [`HashBackend`] silently if the model fails to load (e.g. network down
/// on first call).
pub struct OnnxBackend;

impl EmbeddingBackend for OnnxBackend {
    fn name(&self) -> &str {
        "all-MiniLM-L6-v2"
    }
    fn dim(&self) -> usize {
        VECTOR_DIM
    }
    fn embed(&self, text: &str) -> Vec<f32> {
        #[cfg(feature = "onnx-embed")]
        if let Some(v) = crate::vector::onnx::embed(text) {
            return v;
        }
        // Fall through to hash if ONNX disabled or the model didn't load.
        HashBackend.embed(text)
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
        #[cfg(feature = "onnx-embed")]
        {
            "onnx"
        }
        #[cfg(not(feature = "onnx-embed"))]
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
            tracing::warn!("Unknown AGENT_BRIDGE_EMBED_BACKEND={other:?}; using compile-time default");
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
        assert_eq!(b.name(), "fnv1a-hash-384");
        assert_eq!(b.dim(), 384);
        let v1 = b.embed("Warp IPC socket");
        let v2 = b.embed("Warp IPC socket");
        assert_eq!(v1, v2);
        assert_eq!(v1.len(), 384);
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
