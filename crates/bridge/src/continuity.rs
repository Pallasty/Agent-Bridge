//! Goal C — standing continuity `U` surface (store-side, read-only).
//!
//! The continuity honest ledger flagged memory-continuity as "missing a standing
//! continuity dashboard". This module mechanizes the store-derivable half of the
//! report-first `U` surface into one call: the embedding-space health that
//! decides whether semantic retrieval can serve continuity at all — backend mix,
//! stale-vector fraction, and host-correct anisotropy — each surfaced with its
//! external anchor, falsifier, and owner.
//!
//! It does NOT re-run the held-out recall corpus: R@k is owned by the
//! `recall_eval` harness (the board-agreed external falsifier anchor). The board
//! converged that FTS is the headline continuity signal and semantic/whitening
//! is a SECONDARY lever, so this report frames embedding-space health as a
//! diagnostic, not the continuity verdict.
//!
//! Read-only: SELECTs active embeddings, computes statistics. No write, no
//! ranking change, no MCP tool. Exposed via the `agent-bridge continuity-report`
//! CLI subcommand and reused by `examples/continuity_report.rs`.

use ab_store::vector::{VECTOR_DIM, decode_embedding};
use anyhow::Result;
use std::collections::BTreeMap;
use std::path::Path;
use tokio_rusqlite::Connection;

const HASH_BACKEND_NAME: &str = "fnv1a-hash-384";
const NULL_BACKEND_LABEL: &str = "<null pre-v26>";

/// One embedding backend's share of the active embedded corpus.
pub struct BackendStat {
    pub backend: String,
    pub n: usize,
}

/// Store-side continuity health snapshot.
pub struct ContinuityReport {
    pub db_path: String,
    pub active_total: i64,
    pub embedded: usize,
    pub dominant_backend: String,
    pub dominant_count: usize,
    pub anisotropy_ratio: f32,
    pub stale_vectors: usize,
    pub stale_frac: f64,
    pub backends: Vec<BackendStat>,
}

/// ‖μ‖ / mean‖v‖ over a backend's vectors; →1.0 means severe anisotropy (all
/// vectors share one dominant direction, so cosine ranking is near-random).
fn anisotropy_ratio(vecs: &[Vec<f32>]) -> f32 {
    if vecs.is_empty() {
        return 0.0;
    }
    let mut mu = vec![0f32; VECTOR_DIM];
    for v in vecs {
        for (m, x) in mu.iter_mut().zip(v) {
            *m += x;
        }
    }
    for m in mu.iter_mut() {
        *m /= vecs.len() as f32;
    }
    let mu_norm: f32 = mu.iter().map(|x| x * x).sum::<f32>().sqrt();
    let mean_vnorm: f32 = vecs
        .iter()
        .map(|v| v.iter().map(|x| x * x).sum::<f32>().sqrt())
        .sum::<f32>()
        / vecs.len() as f32;
    if mean_vnorm < 1e-6 {
        0.0
    } else {
        mu_norm / mean_vnorm
    }
}

/// Build the store-side continuity report. Read-only; opens a short connection,
/// groups active embeddings by backend, and measures anisotropy on the dominant
/// (host-correct) backend.
pub async fn build_report(db_path: &Path) -> Result<ContinuityReport> {
    let conn = Connection::open(db_path).await?;
    let raw: Vec<(Option<String>, Vec<u8>)> = conn
        .call(|c| {
            let mut stmt = c.prepare(
                "SELECT embedding_backend, embedding FROM memories \
                 WHERE status='active' AND embedding IS NOT NULL",
            )?;
            let out = stmt
                .query_map([], |row| {
                    Ok((row.get::<_, Option<String>>(0)?, row.get::<_, Vec<u8>>(1)?))
                })?
                .collect::<Result<Vec<_>, _>>()?;
            Ok::<_, tokio_rusqlite::rusqlite::Error>(out)
        })
        .await?;
    let active_total: i64 = conn
        .call(|c| {
            let v = c.query_row(
                "SELECT COUNT(*) FROM memories WHERE status='active'",
                [],
                |r| r.get::<_, i64>(0),
            )?;
            Ok::<_, tokio_rusqlite::rusqlite::Error>(v)
        })
        .await?;

    let mut by_backend: BTreeMap<String, Vec<Vec<f32>>> = BTreeMap::new();
    for (be, bytes) in raw {
        let name = be.unwrap_or_else(|| NULL_BACKEND_LABEL.to_string());
        let v = decode_embedding(&bytes);
        if v.len() != VECTOR_DIM {
            continue;
        }
        by_backend.entry(name).or_default().push(v);
    }

    let embedded: usize = by_backend.values().map(|v| v.len()).sum();
    // dominant tagged backend = the model the store is "indexed with" (host-correct).
    let dominant = by_backend
        .iter()
        .filter(|(k, _)| k.as_str() != NULL_BACKEND_LABEL && k.as_str() != HASH_BACKEND_NAME)
        .max_by_key(|(_, v)| v.len());
    let dominant_backend = dominant.map(|(k, _)| k.clone()).unwrap_or_default();
    let dominant_count = dominant.map(|(_, v)| v.len()).unwrap_or(0);
    let anisotropy_ratio = dominant.map(|(_, v)| anisotropy_ratio(v)).unwrap_or(0.0);
    let stale_vectors = embedded.saturating_sub(dominant_count);
    let stale_frac = if embedded > 0 {
        stale_vectors as f64 / embedded as f64
    } else {
        0.0
    };

    let mut backends: Vec<BackendStat> = by_backend
        .into_iter()
        .map(|(backend, v)| BackendStat {
            backend,
            n: v.len(),
        })
        .collect();
    backends.sort_by(|a, b| b.n.cmp(&a.n));

    Ok(ContinuityReport {
        db_path: db_path.display().to_string(),
        active_total,
        embedded,
        dominant_backend,
        dominant_count,
        anisotropy_ratio,
        stale_vectors,
        stale_frac,
        backends,
    })
}

impl ContinuityReport {
    fn aniso_state(&self) -> &'static str {
        if self.anisotropy_ratio >= 0.85 {
            "SEVERE (cosine near-random)"
        } else if self.anisotropy_ratio >= 0.5 {
            "elevated"
        } else {
            "healthy"
        }
    }

    /// Human-readable standing `U` report.
    pub fn render_markdown(&self) -> String {
        let mut s = String::new();
        s.push_str("# Continuity U — standing report (store-side embedding-space health)\n");
        s.push_str(&format!("db:               {}\n", self.db_path));
        s.push_str(&format!(
            "active memories:  {}  ({} embedded)\n",
            self.active_total, self.embedded
        ));
        s.push_str(&format!(
            "host backend:     {} (dominant tagged, {} vectors)\n\n",
            self.dominant_backend, self.dominant_count
        ));

        s.push_str("## Embedding backend mix (active, embedded)\n");
        s.push_str(&format!("  {:<32} {:>7} {:>7}\n", "backend", "n", "%"));
        for b in &self.backends {
            s.push_str(&format!(
                "  {:<32} {:>7} {:>6.1}%\n",
                b.backend,
                b.n,
                100.0 * b.n as f64 / self.embedded.max(1) as f64
            ));
        }
        s.push('\n');

        s.push_str("## Continuity signals (each: value · external anchor · falsifier · owner)\n");
        s.push_str(&format!(
            "  - anisotropy({})  ratio={:.3}  [{}]\n      anchor: ‖μ‖/mean‖v‖ over live store · falsifier: ratio<0.5 would mean cosine is usable · owner: memory-continuity lane\n",
            self.dominant_backend,
            self.anisotropy_ratio,
            self.aniso_state()
        ));
        s.push_str(&format!(
            "  - stale vectors          {}/{} ({:.0}%) not in {} space\n      anchor: embedding_backend tags · falsifier: reindex drops this to ~0 · owner: @mac hygiene (Goal B)\n",
            self.stale_vectors,
            self.embedded,
            100.0 * self.stale_frac,
            self.dominant_backend
        ));
        s.push_str(
            "  - recall R@k             SEE `recall_eval` (host-correct, Action A)\n      anchor: 18-case held-out paraphrase corpus, FTS R@10 = headline · falsifier: hard-tier R@k unchanged ⇒ a gate is decorative (#3774) · owner: memory-continuity lane\n",
        );
        s.push_str(
            "  - L6 hallucination gate  falsified_shelved (rule-3, 3/3)\n      anchor: docs/L6-OPTION-E-RESULT · falsifier: a NEW design beats P1≥60%/P2≤25% on held-out · owner: shelved\n",
        );
        s.push('\n');

        s.push_str("## Read\n");
        s.push_str(
            "  Board verdict (#3834/#3835/#3774): semantic/whitening is a SECONDARY lever —\n",
        );
        s.push_str(
            "  anisotropy is a sentence-transformer family disease (e5 0.906 / para-ml 0.773),\n",
        );
        s.push_str(
            "  and even whitened, semantic recall stays below FTS. So FTS R@10 is the headline\n",
        );
        s.push_str(
            "  continuity number; this embedding-space report is a DIAGNOSTIC for why semantic\n",
        );
        s.push_str(
            "  underperforms, not the continuity verdict. Stale-vector reindex is hygiene, not a\n",
        );
        s.push_str("  recall lever (#3834 falsified poisoning). Refresh R@k via `recall_eval`.\n");
        s
    }

    /// Machine-readable snapshot.
    pub fn to_json(&self) -> String {
        let backends: Vec<String> = self
            .backends
            .iter()
            .map(|b| format!("{{\"backend\":\"{}\",\"n\":{}}}", b.backend, b.n))
            .collect();
        format!(
            "{{\"db\":\"{}\",\"active_total\":{},\"embedded\":{},\"dominant_backend\":\"{}\",\"dominant_count\":{},\"anisotropy_ratio\":{:.3},\"stale_vectors\":{},\"stale_frac\":{:.3},\"backends\":[{}]}}",
            self.db_path,
            self.active_total,
            self.embedded,
            self.dominant_backend,
            self.dominant_count,
            self.anisotropy_ratio,
            self.stale_vectors,
            self.stale_frac,
            backends.join(",")
        )
    }
}
