//! Startup embedding **dim-guard** — make silent embedding-model drift loud.
//!
//! A process can serve/write semantic embeddings at a *different* vector
//! dimension than the store was written in, with NO error and NO bad return
//! code — `cosine_similarity` just returns `0.0` on a length mismatch, so
//! semantic search silently degrades to recency-only ranking. We hit this in
//! production three ways (2026-06-25 audit, forum #4282):
//!   1. **config vs store** — a stale launchd plist pinned
//!      `AGENT_BRIDGE_ONNX_MODEL=e5-small` (384d) while the store had been
//!      re-embedded to `gte-multilingual-base` (768d); the daemon served
//!      e5-384 queries against a gte-768 store → all-zero cosines.
//!   2. **silent fallback** — a wrong `AGENT_BRIDGE_ONNX_MODEL_DIR` made the
//!      gte ONNX load fail and the backend fell back to e5-small (384d) while
//!      still *claiming* gte (768d configured).
//!   3. **mislabel** — a peer (aio2) wrote rows tagged `gte` but 384d.
//!
//! None of these were caught by anything at runtime — only a manual `ps`+`sqlite`
//! audit found them. This guard runs at daemon/daemon-http/mcp startup, compares
//! the active embedder against the store's dominant embedding profile, and logs
//! a LOUD `WARN` per inconsistency. **v1 is warn-only**: it never changes
//! behavior, it just makes the drift impossible to miss in the logs / `doctor`.

use std::sync::Arc;
use std::time::Duration;

use ab_store::{EmbeddingProfile, StateStore};
use tracing::{info, warn};

/// Max seconds to wait for the embedding model to settle before giving up on
/// the actual-output-dim probe. gte's ORT session can cold-load ~90s.
const SETTLE_TIMEOUT_SECS: u64 = 180;

/// Result of comparing the active embedder against the store's dominant
/// embedding profile. `warnings` is empty exactly when everything is consistent.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct DimGuardReport {
    pub warnings: Vec<String>,
}

impl DimGuardReport {
    pub fn ok(&self) -> bool {
        self.warnings.is_empty()
    }
}

/// Pure comparison — no I/O, no model load — so the mismatch logic is unit
/// tested without spinning up an embedder.
///
/// - `configured`: `vector_dim()` for the active model (what config *claims*).
/// - `actual`: real `embed_text(probe).len()` once the model settled, if known
///   (`None` during the early, pre-load synchronous check).
/// - `store`: dominant `(backend, dim)` the store was actually written in.
pub fn evaluate_embedding_dims(
    model_name: &str,
    configured: usize,
    actual: Option<usize>,
    store: &EmbeddingProfile,
) -> DimGuardReport {
    let mut warnings = Vec::new();
    let store_backend = store.backend.as_deref().unwrap_or("unknown");

    // (1) config vs store — a process configured for a different model than the
    //     store was written in (stale launchd plist / wrong env). Detectable
    //     immediately, before the model even loads.
    if let Some(sd) = store.dim {
        if sd != configured {
            warnings.push(format!(
                "EMBEDDING DIM MISMATCH (config vs store): process configured for model \
                 '{model_name}' ({configured}d) but the store was written at {sd}d \
                 ({store_backend}, {} rows). Semantic search returns dim-mismatched 0.0 cosines. \
                 Likely a stale AGENT_BRIDGE_ONNX_MODEL / launchd plist; set the process model to \
                 match the store and restart.",
                store.rows
            ));
        }
    }

    if let Some(act) = actual {
        // (2) actual vs config — SILENT FALLBACK: the configured model failed to
        //     load and the backend swapped to a different model/dim while still
        //     claiming the configured one (e.g. gte dir missing → e5-small 384d).
        if act != configured {
            warnings.push(format!(
                "EMBEDDING DIM MISMATCH (silent fallback): model '{model_name}' is configured for \
                 {configured}d but the loaded embedder emits {act}d — the ONNX model likely failed \
                 to load and fell back to another model. Check AGENT_BRIDGE_ONNX_MODEL_DIR / the \
                 model files."
            ));
        }
        // (3) actual vs store — the effective truth: what this process produces
        //     at query time vs what the store holds.
        if let Some(sd) = store.dim {
            if act != sd {
                warnings.push(format!(
                    "EMBEDDING DIM MISMATCH (effective): process embeds queries at {act}d but the \
                     store holds {sd}d ({store_backend}) — semantic cosines are 0.0 for {} rows.",
                    store.rows
                ));
            }
        }
    }

    DimGuardReport { warnings }
}

/// Spawn the startup dim-guard as a detached background task. Call once per
/// long-lived store-backed service (daemon / daemon-http / mcp). Cheap: one
/// SQL `GROUP BY` + (after the model warms) one throwaway embed.
pub fn spawn(store: Arc<dyn StateStore>) {
    tokio::spawn(async move {
        run(store).await;
    });
}

async fn run(store: Arc<dyn StateStore>) {
    let profile = match store.dominant_embedding_profile().await {
        Ok(p) => p,
        Err(e) => {
            warn!(error = %e, "embedding dim-guard: could not read store profile; skipping");
            return;
        }
    };
    // Empty store: nothing written yet, nothing to compare against.
    if profile.dim.is_none() || profile.rows == 0 {
        return;
    }

    let model_name = ab_store::vector::active_model_name();
    let configured = ab_store::vector::vector_dim();

    // Phase 1 — synchronous config-vs-store check; fires instantly at startup,
    // before paying any model-load latency.
    let early = evaluate_embedding_dims(model_name, configured, None, &profile);
    for w in &early.warnings {
        warn!(target: "embedding_dim_guard", "{w}");
    }

    // Phase 2 — wait for the embedder to settle, then probe its REAL output dim
    // (during the load window embed_text returns the vector_dim()-wide hash
    // fallback, which would mask a real model loading at a different dim).
    ab_store::vector::warmup();
    let mut settled = false;
    for _ in 0..SETTLE_TIMEOUT_SECS {
        if ab_store::vector::model_init_done() {
            settled = true;
            break;
        }
        tokio::time::sleep(Duration::from_secs(1)).await;
    }
    if !settled {
        warn!(
            target: "embedding_dim_guard",
            "embedding model did not settle within {SETTLE_TIMEOUT_SECS}s; skipping actual-dim \
             probe (config={model_name}/{configured}d, store={}d)",
            profile.dim.unwrap_or(0)
        );
        return;
    }

    let actual = ab_store::vector::embed_text("embedding dim-guard probe").len();
    let report = evaluate_embedding_dims(model_name, configured, Some(actual), &profile);
    if report.ok() {
        info!(
            target: "embedding_dim_guard",
            "embedding dim-guard OK: process and store agree at {actual}d (model={model_name}, \
             store_backend={}, rows={})",
            profile.backend.as_deref().unwrap_or("unknown"),
            profile.rows
        );
    } else {
        // Phase 1 already logged the config-vs-store line; only emit lines that
        // newly appear once `actual` is known, to avoid duplicate WARNs.
        for w in &report.warnings {
            if !early.warnings.contains(w) {
                warn!(target: "embedding_dim_guard", "{w}");
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn profile(backend: &str, dim: usize, rows: u64) -> EmbeddingProfile {
        EmbeddingProfile {
            backend: Some(backend.to_string()),
            dim: Some(dim),
            rows,
        }
    }

    #[test]
    fn consistent_process_and_store_is_silent() {
        let p = profile("gte-multilingual-base", 768, 3000);
        let r = evaluate_embedding_dims("gte-multilingual-base", 768, Some(768), &p);
        assert!(r.ok(), "no warnings expected, got {:?}", r.warnings);
    }

    #[test]
    fn stale_plist_e5_process_against_gte_store_warns() {
        // The real 2026-06-25 launchd bug: process e5-384, store gte-768.
        let p = profile("gte-multilingual-base", 768, 3098);
        let r = evaluate_embedding_dims("multilingual-e5-small", 384, Some(384), &p);
        assert!(!r.ok());
        // config-vs-store fires; effective fires; silent-fallback does NOT
        // (actual == configured here).
        assert!(r.warnings.iter().any(|w| w.contains("config vs store")));
        assert!(r.warnings.iter().any(|w| w.contains("effective")));
        assert!(!r.warnings.iter().any(|w| w.contains("silent fallback")));
        assert_eq!(r.warnings.len(), 2);
    }

    #[test]
    fn silent_fallback_gte_configured_but_e5_loaded_warns() {
        // gte configured (768) but the ONNX load fell back to e5 (384).
        let p = profile("gte-multilingual-base", 768, 3098);
        let r = evaluate_embedding_dims("gte-multilingual-base", 768, Some(384), &p);
        assert!(!r.ok());
        assert!(r.warnings.iter().any(|w| w.contains("silent fallback")));
        assert!(r.warnings.iter().any(|w| w.contains("effective")));
        // config matches store (both 768), so config-vs-store stays silent.
        assert!(!r.warnings.iter().any(|w| w.contains("config vs store")));
    }

    #[test]
    fn early_phase_without_actual_still_catches_config_vs_store() {
        let p = profile("gte-multilingual-base", 768, 3098);
        let r = evaluate_embedding_dims("multilingual-e5-small", 384, None, &p);
        assert_eq!(r.warnings.len(), 1);
        assert!(r.warnings[0].contains("config vs store"));
    }

    #[test]
    fn empty_store_invents_no_store_comparison_warnings() {
        let empty = EmbeddingProfile::default();
        // Empty store + a model that loaded fine: nothing to compare, silent.
        let healthy = evaluate_embedding_dims("gte-multilingual-base", 768, Some(768), &empty);
        assert!(healthy.ok(), "empty store + healthy model: {:?}", healthy.warnings);
        // A genuine silent fallback (loaded dim != configured) is store-
        // independent, so it is still flagged — but no `config vs store` /
        // `effective` warning is invented from a store with no embeddings.
        let fallback = evaluate_embedding_dims("gte-multilingual-base", 768, Some(384), &empty);
        assert!(fallback.warnings.iter().any(|w| w.contains("silent fallback")));
        assert!(!fallback.warnings.iter().any(|w| w.contains("config vs store")));
        assert!(!fallback.warnings.iter().any(|w| w.contains("effective")));
    }
}
