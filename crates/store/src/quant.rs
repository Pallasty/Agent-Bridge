//! Read-only INT8 quantization codec for stored embeddings (ArrowQuant V2 — T2 borrow).
//!
//! **STATUS: landed + tested (wired via `pub mod quant;`).** Shadow / measurement only —
//! there is still no INT8 column in the store; this measures whether one would be safe.
//! Two read-only surfaces: [`measure_drift`] (per-row round-trip cosine fidelity) and
//! [`recall_regression_gate`] (does INT8 preserve the top-K neighbor *ranking* that actually
//! drives retrieval — the recall-regression gate the plan requires *before* any INT8 column
//! is proposed).
//!
//! Borrowed pattern: per-row **symmetric absmax INT8** (vLLM `tpu_int8.py::_quantize_weight`),
//! reimplemented in dependency-free Rust. **SHADOW / MEASUREMENT ONLY** — nothing here is
//! wired into the live store write path; [`crate::vector::encode_embedding`] /
//! [`crate::vector::decode_embedding`] (raw little-endian `f32`) remain the source of truth.
//!
//! A stored row of `f32[D]` (D*4 bytes; 3072 B for gte-768) projects to `i8[D]` + one `f32`
//! scale (D + 4 bytes; 772 B for gte-768 ≈ **3.98×** smaller) for footprint estimation and
//! recall-drift checks before any real INT8 column is ever proposed (gated separately).
//!
//! The `eps` max-floor is **load-bearing**: AB stores all-zero hash-fallback rows
//! (`embedding_result_is_hash_fallback`), and without the floor the per-row scale would
//! divide by zero. gte rows are L2-normalized, so per-row symmetric INT8 keeps cosine error
//! sub-1% (this module is exactly what measures that empirically).

const I8_MIN_F: f32 = -128.0;
const I8_MAX_F: f32 = 127.0;

/// Minimum absmax used as the quantization denominator. Guards all-zero / degenerate rows.
pub const QUANT_EPS: f32 = 1e-5;

/// One row quantized: `codes[i] = round(x[i] / scale)`, `scale = max(absmax, eps) / 127`.
#[derive(Debug, Clone, PartialEq)]
pub struct QuantizedRow {
    pub codes: Vec<i8>,
    pub scale: f32,
}

impl QuantizedRow {
    /// Bytes this row occupies in the quantized representation: `i8` codes + one `f32` scale.
    pub fn encoded_len(&self) -> usize {
        self.codes.len() + std::mem::size_of::<f32>()
    }
}

/// Per-row symmetric absmax INT8 quantizer. Pure, deterministic, dependency-free.
///
/// Mirrors the vLLM recipe: `scale = max(|x|).max(eps) / 127`, then
/// `round(x / scale)` clamped into `[-128, 127]`. The `eps` floor is what makes an
/// all-zero row safe (scale stays finite and positive).
pub fn quantize_row_i8(row: &[f32]) -> QuantizedRow {
    let absmax = row.iter().fold(0.0_f32, |m, &x| m.max(x.abs()));
    let scale = absmax.max(QUANT_EPS) / I8_MAX_F;
    let codes = row
        .iter()
        .map(|&x| (x / scale).round().clamp(I8_MIN_F, I8_MAX_F) as i8)
        .collect();
    QuantizedRow { codes, scale }
}

/// Dequantize back to `f32`: `x[i] ≈ codes[i] * scale`.
pub fn dequantize_row_i8(q: &QuantizedRow) -> Vec<f32> {
    q.codes.iter().map(|&c| c as f32 * q.scale).collect()
}

/// Cosine similarity between a row and its INT8 quantize→dequantize round-trip.
/// `1.0` = lossless. A pair of all-zero vectors counts as lossless (no information lost).
pub fn roundtrip_cosine(row: &[f32]) -> f32 {
    let deq = dequantize_row_i8(&quantize_row_i8(row));
    cosine(row, &deq)
}

/// Byte length of the raw little-endian `f32` encoding (matches `encode_embedding`).
pub fn f32_encoded_len(dim: usize) -> usize {
    dim * std::mem::size_of::<f32>()
}

fn cosine(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() {
        return 0.0;
    }
    let dot: f32 = a.iter().zip(b).map(|(x, y)| x * y).sum();
    let na: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let nb: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if na == 0.0 || nb == 0.0 {
        // Both-zero round-trips here (zero quantizes to zero); treat as lossless.
        1.0
    } else {
        (dot / (na * nb)).clamp(-1.0, 1.0)
    }
}

/// Aggregate read-only footprint + recall-drift report over a set of embedding rows.
/// Pure measurement — mutates no store state.
#[derive(Debug, Clone)]
pub struct QuantDriftReport {
    pub rows: usize,
    pub f32_bytes: usize,
    pub int8_bytes: usize,
    pub min_cosine: f32,
    pub mean_cosine: f64,
    /// Rows whose round-trip cosine fell below 0.999 (recall-risk tail).
    pub rows_below_0_999: usize,
    /// All-zero rows (hash-fallback / degenerate) seen.
    pub zero_rows: usize,
}

impl Default for QuantDriftReport {
    fn default() -> Self {
        Self {
            rows: 0,
            f32_bytes: 0,
            int8_bytes: 0,
            min_cosine: 1.0,
            mean_cosine: 1.0,
            rows_below_0_999: 0,
            zero_rows: 0,
        }
    }
}

impl QuantDriftReport {
    /// `f32_bytes / int8_bytes` (≈ 3.98 for gte-768). `0.0` when nothing was measured.
    pub fn compression_ratio(&self) -> f64 {
        if self.int8_bytes == 0 {
            0.0
        } else {
            self.f32_bytes as f64 / self.int8_bytes as f64
        }
    }
}

/// Build a drift report by quantizing each row in memory (read-only). Empty rows are skipped.
pub fn measure_drift<'a, I>(rows: I) -> QuantDriftReport
where
    I: IntoIterator<Item = &'a [f32]>,
{
    let mut rep = QuantDriftReport::default();
    let mut cos_sum = 0.0_f64;
    for row in rows {
        if row.is_empty() {
            continue;
        }
        let q = quantize_row_i8(row);
        let deq = dequantize_row_i8(&q);
        let c = cosine(row, &deq);
        rep.rows += 1;
        rep.f32_bytes += f32_encoded_len(row.len());
        rep.int8_bytes += q.encoded_len();
        rep.min_cosine = rep.min_cosine.min(c);
        cos_sum += c as f64;
        if c < 0.999 {
            rep.rows_below_0_999 += 1;
        }
        if row.iter().all(|&x| x == 0.0) {
            rep.zero_rows += 1;
        }
    }
    rep.mean_cosine = if rep.rows == 0 {
        1.0
    } else {
        cos_sum / rep.rows as f64
    };
    rep
}

/// Recall-regression gate report — does storing embeddings as per-row INT8
/// preserve the top-`k` neighbor sets that drive retrieval?
#[derive(Debug, Clone)]
pub struct RecallGateReport {
    /// Usable corpus rows (non-empty, dim-consistent) considered.
    pub corpus: usize,
    /// Queries evaluated (a deterministic stride sample of the corpus).
    pub queries: usize,
    /// Neighbors compared per query (clamped to `corpus - 1`).
    pub k: usize,
    /// Mean recall@k over all queries (1.0 = INT8 reproduces every f32 neighbor).
    pub mean_recall_at_k: f64,
    /// Worst single-query recall@k.
    pub min_recall_at_k: f64,
    /// Queries whose recall@k fell below `threshold`.
    pub queries_below_threshold: usize,
    /// The pass floor the gate was run at.
    pub threshold: f64,
    /// `mean_recall_at_k >= threshold` — the gate verdict.
    pub passed: bool,
}

/// **Recall-regression gate** — would switching the stored embedding column to
/// per-row INT8 change *which* memories retrieval returns? The f32 ranking is
/// the frozen baseline; for a deterministic stride sample of up to `max_queries`
/// rows, `recall@k = |int8_topk ∩ f32_topk| / k`, where `int8_topk` ranks the
/// **dequantized-INT8** corpus against the still-`f32` query (the realistic
/// "fresh f32 query against an INT8 store" retrieval path). The gate passes when
/// `mean_recall_at_k >= threshold`.
///
/// Pure / read-only: quantizes a copy, mutates nothing. Deterministic — cosine
/// ties break by ascending index, queries are a fixed stride. This is the gate
/// the plan requires green *before* any real INT8 column is proposed (which then
/// goes through the lswr admission ladder, not this surface).
pub fn recall_regression_gate(
    rows: &[&[f32]],
    k: usize,
    max_queries: usize,
    threshold: f64,
) -> RecallGateReport {
    // Keep only usable rows: non-empty and the same dim as the first non-empty
    // row (mixed-dim rows can't be compared by cosine).
    let dim = rows.iter().map(|r| r.len()).find(|&l| l > 0).unwrap_or(0);
    let corpus: Vec<&[f32]> = rows
        .iter()
        .copied()
        .filter(|r| dim > 0 && r.len() == dim)
        .collect();
    let n = corpus.len();
    let k_eff = k.min(n.saturating_sub(1));

    // A corpus too small to support a k-NN comparison is vacuously "no regression".
    if n < 2 || k_eff == 0 {
        return RecallGateReport {
            corpus: n,
            queries: 0,
            k: k_eff,
            mean_recall_at_k: 1.0,
            min_recall_at_k: 1.0,
            queries_below_threshold: 0,
            threshold,
            passed: true,
        };
    }

    // The "INT8 store": quantize → dequantize every corpus row once.
    let int8_owned: Vec<Vec<f32>> = corpus
        .iter()
        .map(|r| dequantize_row_i8(&quantize_row_i8(r)))
        .collect();
    let int8: Vec<&[f32]> = int8_owned.iter().map(|v| v.as_slice()).collect();

    // Deterministic stride sample of query rows.
    let q_count = max_queries.clamp(1, n);
    let stride = (n / q_count).max(1);

    let mut recall_sum = 0.0_f64;
    let mut min_recall = 1.0_f64;
    let mut below = 0usize;
    let mut queries = 0usize;
    let mut qi = 0usize;
    while qi < n {
        let query = corpus[qi];
        let f32_top = top_k_neighbors(query, &corpus, qi, k_eff);
        let int8_top = top_k_neighbors(query, &int8, qi, k_eff);
        let hits = f32_top.intersection(&int8_top).count();
        let recall = hits as f64 / k_eff as f64;
        recall_sum += recall;
        min_recall = min_recall.min(recall);
        if recall < threshold {
            below += 1;
        }
        queries += 1;
        qi += stride;
    }

    let mean = recall_sum / queries as f64;
    RecallGateReport {
        corpus: n,
        queries,
        k: k_eff,
        mean_recall_at_k: mean,
        min_recall_at_k: min_recall,
        queries_below_threshold: below,
        threshold,
        passed: mean >= threshold,
    }
}

/// Indices of the `k` highest-cosine rows to `query` in `corpus`, skipping
/// `exclude`. Deterministic: ties break by ascending index. Returns a set (order
/// is irrelevant to recall overlap).
fn top_k_neighbors(
    query: &[f32],
    corpus: &[&[f32]],
    exclude: usize,
    k: usize,
) -> std::collections::BTreeSet<usize> {
    let mut scored: Vec<(f32, usize)> = corpus
        .iter()
        .enumerate()
        .filter(|(j, _)| *j != exclude)
        .map(|(j, row)| (cosine(query, row), j))
        .collect();
    // Highest cosine first; equal cosine → smaller index first.
    scored.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.cmp(&b.1)));
    scored.into_iter().take(k).map(|(_, j)| j).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 40 distinct gte-like L2-normalized rows (what the store actually holds).
    fn normalized_corpus() -> Vec<Vec<f32>> {
        (0..40)
            .map(|s| {
                let mut row: Vec<f32> = (0..768)
                    .map(|i| ((i as f32) * 0.013 + s as f32 * 0.5).sin())
                    .collect();
                let norm = row.iter().map(|x| x * x).sum::<f32>().sqrt();
                for x in &mut row {
                    *x /= norm;
                }
                row
            })
            .collect()
    }

    #[test]
    fn recall_gate_passes_on_normalized_rows() {
        // Per-row INT8 is near-lossless on L2-normalized rows, so retrieval
        // neighbors are preserved → the gate passes with near-perfect recall.
        let owned = normalized_corpus();
        let rows: Vec<&[f32]> = owned.iter().map(|v| v.as_slice()).collect();
        let rep = recall_regression_gate(&rows, 5, 40, 0.90);
        assert_eq!(rep.queries, 40);
        assert_eq!(rep.k, 5);
        assert!(
            rep.mean_recall_at_k >= 0.95,
            "mean recall@5 {} should be near-perfect",
            rep.mean_recall_at_k
        );
        assert!(rep.passed);
    }

    #[test]
    fn recall_gate_is_deterministic() {
        let owned = normalized_corpus();
        let rows: Vec<&[f32]> = owned.iter().map(|v| v.as_slice()).collect();
        let a = recall_regression_gate(&rows, 5, 40, 0.90);
        let b = recall_regression_gate(&rows, 5, 40, 0.90);
        assert_eq!(a.mean_recall_at_k, b.mean_recall_at_k);
        assert_eq!(a.min_recall_at_k, b.min_recall_at_k);
        assert_eq!(a.passed, b.passed);
        assert_eq!(a.queries, b.queries);
    }

    #[test]
    fn recall_gate_degenerate_corpus_is_vacuous_pass() {
        let one = vec![vec![1.0_f32, 0.0, 0.0]];
        let rows: Vec<&[f32]> = one.iter().map(|v| v.as_slice()).collect();
        let rep = recall_regression_gate(&rows, 5, 10, 0.99);
        assert_eq!(rep.queries, 0);
        assert_eq!(rep.k, 0);
        assert!(rep.passed, "a corpus too small for k-NN is a vacuous pass");
    }

    #[test]
    fn recall_gate_detects_neighbor_regression() {
        // Query q's f32 nearest is b, but a huge absmax dim forces a's and b's
        // discriminating dims to round to 0, collapsing both to [1000,0,0]; the
        // tie-break then flips the INT8 top-1 to a → recall@1 = 0, gate fails.
        let q = [0.0_f32, 1.0, 2.0];
        let a = [1000.0_f32, 2.0, 0.5];
        let b = [1000.0_f32, 0.5, 2.0];
        let rows: Vec<&[f32]> = vec![&q, &a, &b];
        let rep = recall_regression_gate(&rows, 1, 1, 0.90);
        assert_eq!(rep.queries, 1);
        assert!(
            rep.mean_recall_at_k < 0.5,
            "expected a detected regression, got recall {}",
            rep.mean_recall_at_k
        );
        assert!(
            !rep.passed,
            "gate must fail when INT8 changes the top-1 neighbor"
        );
    }

    #[test]
    fn unit_vector_roundtrip_is_near_lossless() {
        // gte-like 768-dim row, L2-normalized (as the store guarantees).
        let mut row: Vec<f32> = (0..768).map(|i| (i as f32 * 0.013).sin()).collect();
        let norm = row.iter().map(|x| x * x).sum::<f32>().sqrt();
        for x in &mut row {
            *x /= norm;
        }
        let c = roundtrip_cosine(&row);
        assert!(c > 0.999, "symmetric INT8 cosine {c} should exceed 0.999");
    }

    #[test]
    fn all_zero_row_does_not_divide_by_zero() {
        let row = vec![0.0_f32; 768];
        let q = quantize_row_i8(&row);
        assert!(q.scale.is_finite() && q.scale > 0.0, "scale {} ", q.scale);
        assert!(q.codes.iter().all(|&c| c == 0));
        assert_eq!(roundtrip_cosine(&row), 1.0);
    }

    #[test]
    fn codes_stay_in_i8_range_and_endpoints_map() {
        let row = vec![-1.0, 1.0, 0.5, -0.5, 0.0];
        let q = quantize_row_i8(&row);
        // absmax = 1.0 -> scale = 1/127 -> +1.0 maps to 127, -1.0 to -127.
        assert_eq!(q.codes[1], 127);
        assert_eq!(q.codes[0], -127);
        assert!(q.codes.iter().all(|&c| (-128..=127).contains(&(c as i32))));
    }

    #[test]
    fn compression_ratio_matches_gte768() {
        let rows: Vec<Vec<f32>> = (0..10)
            .map(|s| (0..768).map(|i| ((i + s) as f32).cos()).collect())
            .collect();
        let rep = measure_drift(rows.iter().map(|r| r.as_slice()));
        assert_eq!(rep.rows, 10);
        assert_eq!(rep.f32_bytes, 10 * 768 * 4);
        assert_eq!(rep.int8_bytes, 10 * (768 + 4));
        // 3072 / 772 = 3.9793...
        assert!(
            (rep.compression_ratio() - 3.9793).abs() < 0.01,
            "ratio {}",
            rep.compression_ratio()
        );
    }

    #[test]
    fn quantize_is_deterministic() {
        let row: Vec<f32> = (0..768).map(|i| i as f32 * 0.001 - 0.3).collect();
        assert_eq!(quantize_row_i8(&row), quantize_row_i8(&row));
    }
}
