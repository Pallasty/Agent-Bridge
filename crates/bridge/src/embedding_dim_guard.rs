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
//! the active embedder against the store's dominant embedding profile AND flags
//! any minority of in-store rows that hold a different dimension (case 3), and
//! logs a LOUD `WARN` per inconsistency. **v1 is warn-only**: it never changes
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
/// - `model_name` / `configured`: the active backend's `name()` / `dim()` — what
///   THIS process's embedder claims (routed through `default_backend()`, so it
///   stays correct under a custom substrate backend, not just raw ONNX).
/// - `actual`: real `embed_text(probe).len()` once the model settled, if known
///   (`None` during the early, pre-load synchronous check).
/// - `dominant`: the largest `(backend, dim)` bucket — the space the store was
///   actually written in.
/// - `minority_mismatch_rows`: active rows whose dim differs from the dominant
///   dim (mislabeled/stale rows the dominant bucket alone would hide).
pub fn evaluate_embedding_dims(
    model_name: &str,
    configured: usize,
    actual: Option<usize>,
    dominant: &EmbeddingProfile,
    minority_mismatch_rows: u64,
) -> DimGuardReport {
    let mut warnings = Vec::new();
    let store_backend = dominant.backend.as_deref().unwrap_or("unknown");

    // (1) config vs store — a process configured for a different model than the
    //     store was written in (stale launchd plist / wrong env). Detectable
    //     immediately, before the model even loads.
    if let Some(sd) = dominant.dim {
        if sd != configured {
            warnings.push(format!(
                "EMBEDDING DIM MISMATCH (config vs store): process configured for model \
                 '{model_name}' ({configured}d) but the store was written at {sd}d \
                 ({store_backend}, {} rows). Semantic search returns dim-mismatched 0.0 cosines. \
                 Likely a stale AGENT_BRIDGE_ONNX_MODEL / launchd plist; set the process model to \
                 match the store and restart.",
                dominant.rows
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
        if let Some(sd) = dominant.dim {
            if act != sd {
                warnings.push(format!(
                    "EMBEDDING DIM MISMATCH (effective): process embeds queries at {act}d but the \
                     store holds {sd}d ({store_backend}) — semantic cosines are 0.0 for {} rows.",
                    dominant.rows
                ));
            }
        }
    }

    // (4) in-store minority dim anomaly — a slice of active rows hold a dim
    //     OTHER than the dominant one (e.g. peer-synced rows tagged `gte` but
    //     384d among a healthy gte-768 store). These individual rows are
    //     dim-mismatched and invisible to semantic search even when THIS process
    //     is perfectly aligned with the dominant space. Caught from the full
    //     bucket distribution, which the dominant bucket alone hides.
    if let Some(dom) = dominant.dim {
        if minority_mismatch_rows > 0 {
            warnings.push(format!(
                "EMBEDDING DIM ANOMALY (in-store): {minority_mismatch_rows} active row(s) hold a \
                 dimension other than the dominant {dom}d — these mislabeled/stale embeddings are \
                 dim-mismatched and invisible to semantic search. Run memory_reindex(only_stale=true) \
                 or re-embed them from their source node."
            ));
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
    let buckets = match store.embedding_profile_buckets().await {
        Ok(b) => b,
        Err(e) => {
            warn!(error = %e, "embedding dim-guard: could not read store profile; skipping");
            return;
        }
    };
    let dominant = buckets.first().cloned().unwrap_or_default();
    // Empty store: nothing written yet, nothing to compare against.
    if dominant.dim.is_none() || dominant.rows == 0 {
        return;
    }
    // Active rows whose dim differs from the dominant dim — mislabeled/stale
    // embeddings the dominant bucket alone would hide (cross-machine sync, an
    // aborted re-embed, etc.).
    let minority_mismatch: u64 = buckets
        .iter()
        .filter(|b| b.dim != dominant.dim)
        .map(|b| b.rows)
        .sum();

    // Identity routed through the ACTIVE backend (not raw `vector::*`) so it
    // stays correct if a custom substrate backend is ever linked. Today this is
    // a LATENT path: the in-tree seed-substrate shim is build-disabled
    // (`ab_seed_bridge::install_default()` always Errs), so under the default
    // build `default_backend()` resolves to `OnnxBackend` and name()/dim() are
    // identical to the old raw `vector::*` values — behavior-preserving now,
    // forward-compatible if the standalone seed-bridge is ever linked via the
    // `seed-substrate` feature. NB: the Phase-2 actual-dim probe still keys off
    // the raw-ONNX settle signal (`model_init_done`); for a non-ONNX backend it
    // is best-effort and the Phase-1 config/anomaly checks (no probe) carry it.
    let backend = ab_store::embedding::default_backend();
    let model_name = backend.name().to_string();
    let configured = backend.dim();

    // Phase 1 — synchronous checks (config-vs-store + in-store anomaly); fire
    // instantly at startup, before paying any model-load latency.
    let early =
        evaluate_embedding_dims(&model_name, configured, None, &dominant, minority_mismatch);
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
            dominant.dim.unwrap_or(0)
        );
        return;
    }

    let actual = ab_store::vector::embed_text("embedding dim-guard probe").len();
    let report =
        evaluate_embedding_dims(&model_name, configured, Some(actual), &dominant, minority_mismatch);
    if report.ok() {
        info!(
            target: "embedding_dim_guard",
            "embedding dim-guard OK: process and store agree at {actual}d (model={model_name}, \
             store_backend={}, rows={})",
            dominant.backend.as_deref().unwrap_or("unknown"),
            dominant.rows
        );
    } else {
        // Phase 1 already logged the config-vs-store / anomaly lines; only emit
        // lines that newly appear once `actual` is known, to avoid duplicates.
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
        let r = evaluate_embedding_dims("gte-multilingual-base", 768, Some(768), &p, 0);
        assert!(r.ok(), "no warnings expected, got {:?}", r.warnings);
    }

    #[test]
    fn stale_plist_e5_process_against_gte_store_warns() {
        // The real 2026-06-25 launchd bug: process e5-384, store gte-768.
        let p = profile("gte-multilingual-base", 768, 3098);
        let r = evaluate_embedding_dims("multilingual-e5-small", 384, Some(384), &p, 0);
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
        let r = evaluate_embedding_dims("gte-multilingual-base", 768, Some(384), &p, 0);
        assert!(!r.ok());
        assert!(r.warnings.iter().any(|w| w.contains("silent fallback")));
        assert!(r.warnings.iter().any(|w| w.contains("effective")));
        // config matches store (both 768), so config-vs-store stays silent.
        assert!(!r.warnings.iter().any(|w| w.contains("config vs store")));
    }

    #[test]
    fn early_phase_without_actual_still_catches_config_vs_store() {
        let p = profile("gte-multilingual-base", 768, 3098);
        let r = evaluate_embedding_dims("multilingual-e5-small", 384, None, &p, 0);
        assert_eq!(r.warnings.len(), 1);
        assert!(r.warnings[0].contains("config vs store"));
    }

    #[test]
    fn in_store_minority_dim_anomaly_warns_even_when_process_is_aligned() {
        // The aio2 case: process AND dominant store both healthy gte-768, but a
        // handful of active rows hold 384d (tagged gte but mislabeled/stale).
        let p = profile("gte-multilingual-base", 768, 3241);
        // Process is perfectly aligned (actual == configured == dominant 768) …
        let r = evaluate_embedding_dims("gte-multilingual-base", 768, Some(768), &p, 5);
        // … yet the 5 minority rows are flagged.
        assert!(!r.ok());
        assert_eq!(r.warnings.len(), 1);
        assert!(r.warnings[0].contains("in-store"));
        assert!(r.warnings[0].contains('5'));
        // And zero minority rows on an otherwise identical store stays silent.
        let clean = evaluate_embedding_dims("gte-multilingual-base", 768, Some(768), &p, 0);
        assert!(clean.ok(), "no anomaly expected, got {:?}", clean.warnings);
    }

    #[test]
    fn empty_store_invents_no_store_comparison_warnings() {
        let empty = EmbeddingProfile::default();
        // Empty store + a model that loaded fine: nothing to compare, silent.
        let healthy = evaluate_embedding_dims("gte-multilingual-base", 768, Some(768), &empty, 0);
        assert!(healthy.ok(), "empty store + healthy model: {:?}", healthy.warnings);
        // A genuine silent fallback (loaded dim != configured) is store-
        // independent, so it is still flagged — but no `config vs store` /
        // `effective` / `in-store` warning is invented from an empty store.
        let fallback = evaluate_embedding_dims("gte-multilingual-base", 768, Some(384), &empty, 0);
        assert!(fallback.warnings.iter().any(|w| w.contains("silent fallback")));
        assert!(!fallback.warnings.iter().any(|w| w.contains("config vs store")));
        assert!(!fallback.warnings.iter().any(|w| w.contains("effective")));
        assert!(!fallback.warnings.iter().any(|w| w.contains("in-store")));
    }
}
