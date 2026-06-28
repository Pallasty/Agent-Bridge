//! Read-only INT8 quantization codec for stored embeddings (ArrowQuant V2 — T2 borrow).
//!
//! **STATUS: UNVERIFIED DRAFT (authored 2026-06-28).** This module is NOT yet wired into
//! `lib.rs` (`mod quant;` is intentionally absent) and has NOT been compiled/tested — the
//! shell backend was unavailable when it was written. To verify: add `pub mod quant;` to
//! `lib.rs`, then `cargo test -p ab-store quant && cargo clippy -p ab-store --all-targets
//! -- -D warnings && cargo fmt -p ab-store -- --check`.
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

#[cfg(test)]
mod tests {
    use super::*;

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
