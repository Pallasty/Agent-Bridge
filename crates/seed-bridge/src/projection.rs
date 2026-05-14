//! v22 Phase 2.4 — projection layer for substrate perception.
//!
//! Two variants:
//!
//! 1. [`Projection::BucketPool`] — Phase 1 deterministic bucket-average. No
//!    artifact, no opt-in needed. Survives tests and unit fixtures.
//!
//! 2. [`Projection::Svd`] — Phase 2.4 SVD warm-start, loaded from the
//!    artifact AiOT ships as part of Direction α-α (recall@10 = 0.964 on
//!    real corpus, +0.194 over bucket-pool baseline). Opt-in via env
//!    `AB_SUBSTRATE_PROJECTION=svd` + `AB_SUBSTRATE_SVD_PATH=/path/to.bin`.
//!    On any load failure (missing file, sha mismatch, shape mismatch) the
//!    substrate falls back to bucket-pool with a warning — never panics.
//!
//! The artifact contract (binary + JSON sidecar) is documented in
//! `docs/memos/ALPHA_ALPHA_SVD_PROJECTION_RESULT_2026_05_14.md` §3
//! (AiOT side). Loader-side responsibilities mirrored here:
//!
//! - read `weights.bin` as raw little-endian f32, length = encoder_dim *
//!   perception_dim
//! - read `weights.json` for shape + sha256 + mean_vector_b64
//! - verify sha256 of bytes == metadata `sha256_bin`
//! - decode mean vector (base64 → little-endian f32)
//! - project: `out[j] = Σ_i (encoded[i] - mean[i]) * weights[i*D + j]`,
//!   then L2-normalize

use base64::Engine;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

/// Env: `svd` activates Phase 2.4 loader; anything else (or unset) keeps
/// Phase 1 bucket-pool. Read once at `install_default` time.
pub const PROJECTION_KIND_ENV: &str = "AB_SUBSTRATE_PROJECTION";

/// Env: absolute path to the `*.bin` artifact. Sidecar `*.json` resolved
/// from `bin_path.with_extension("json")`. Required when
/// `AB_SUBSTRATE_PROJECTION=svd`.
pub const SVD_PATH_ENV: &str = "AB_SUBSTRATE_SVD_PATH";

/// Active projection backing the substrate's outer→D mapping.
#[derive(Debug, Clone)]
pub enum Projection {
    /// Phase 1 baseline. Stateless, always available.
    BucketPool,
    /// Phase 2.4 SVD warm-start. Carries the loaded weights + mean +
    /// shape so `project()` is a hot-path function without disk I/O.
    Svd(SvdProjection),
}

impl Projection {
    /// Stable kind tag for logs / `substrate stats` output.
    pub fn kind(&self) -> &'static str {
        match self {
            Self::BucketPool => "bucket_pool",
            Self::Svd(_) => "svd",
        }
    }

    /// Project an outer encoding to substrate dim. Caller guarantees
    /// `out_dim` matches the substrate config; SVD path additionally
    /// requires `encoded.len() == svd.encoder_dim`.
    pub fn project(&self, encoded: &[f32], out_dim: usize) -> Vec<f32> {
        match self {
            Self::BucketPool => project_bucket_pool(encoded, out_dim),
            Self::Svd(svd) => svd.project(encoded),
        }
    }
}

impl Default for Projection {
    fn default() -> Self {
        Self::BucketPool
    }
}

/// Loaded SVD projection: weights row-major `[encoder_dim, perception_dim]`
/// (length `encoder_dim * perception_dim`), mean vector `[encoder_dim]`,
/// plus the verified sha256 for diagnostics.
#[derive(Debug, Clone)]
pub struct SvdProjection {
    pub weights: Vec<f32>,
    pub mean: Vec<f32>,
    pub encoder_dim: usize,
    pub perception_dim: usize,
    pub sha256: String,
}

impl SvdProjection {
    /// Apply `out[j] = Σ_i (encoded[i] - mean[i]) * weights[i*D + j]`,
    /// then L2-normalize to unit length so the downstream NeuronGrid
    /// sees a sphere-aligned vector (same contract as bucket-pool).
    pub fn project(&self, encoded: &[f32]) -> Vec<f32> {
        let d = self.perception_dim;
        if encoded.len() != self.encoder_dim || d == 0 {
            // Defensive fallback — shouldn't happen post-load.
            return vec![0.0f32; d];
        }
        let mut out = vec![0.0f32; d];
        for i in 0..self.encoder_dim {
            let centered = encoded[i] - self.mean[i];
            if centered == 0.0 {
                continue;
            }
            let row_off = i * d;
            for j in 0..d {
                out[j] += centered * self.weights[row_off + j];
            }
        }
        let norm: f32 = out.iter().map(|x| x * x).sum::<f32>().sqrt();
        if norm > 1e-9 {
            for x in out.iter_mut() {
                *x /= norm;
            }
        }
        out
    }
}

/// JSON sidecar shape per α-α loader contract.
#[derive(Debug, Deserialize)]
pub struct SvdMeta {
    #[serde(default = "one")]
    pub version: u32,
    pub encoder_dim: usize,
    pub perception_dim: usize,
    /// "little-endian" expected; rejected otherwise to keep portability
    /// guarantees explicit.
    pub byte_order: String,
    pub sha256_bin: String,
    /// Optional: when omitted, mean is treated as zero (no-center artifact).
    /// AiOT default ships zero-mean for unit-norm encoders.
    #[serde(default)]
    pub mean_vector_b64: Option<String>,
}

fn one() -> u32 {
    1
}

/// Errors surfaced by [`load_svd`]. All paths are non-panicking; callers
/// log + fall back to bucket-pool when this returns `Err`.
#[derive(Debug, thiserror::Error)]
pub enum ProjectionLoadError {
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    #[error("json parse: {0}")]
    Json(#[from] serde_json::Error),
    #[error("base64: {0}")]
    Base64(String),
    #[error(
        "weights byte length {actual} != encoder_dim*perception_dim*4 = {expected} (encoder_dim={encoder_dim}, perception_dim={perception_dim})"
    )]
    ShapeMismatch {
        actual: usize,
        expected: usize,
        encoder_dim: usize,
        perception_dim: usize,
    },
    #[error("sha256 mismatch: meta says {expected}, file is {actual}")]
    Sha256Mismatch { expected: String, actual: String },
    #[error("byte_order='{0}' not supported (only 'little-endian')")]
    UnsupportedByteOrder(String),
    #[error(
        "mean_vector length {actual} != encoder_dim {expected} after base64 decode"
    )]
    MeanShapeMismatch { actual: usize, expected: usize },
}

/// Load + verify an SVD artifact. `bin_path` points at the raw f32 bytes;
/// the JSON sidecar is resolved by swapping the extension.
pub fn load_svd(bin_path: &Path) -> Result<SvdProjection, ProjectionLoadError> {
    let json_path = bin_path.with_extension("json");
    let bytes = std::fs::read(bin_path)?;
    let meta_text = std::fs::read_to_string(&json_path)?;
    let meta: SvdMeta = serde_json::from_str(&meta_text)?;

    if meta.byte_order != "little-endian" {
        return Err(ProjectionLoadError::UnsupportedByteOrder(meta.byte_order));
    }

    // sha256 verify before trusting the header.
    let mut hasher = Sha256::new();
    hasher.update(&bytes);
    let actual_sha = hex_lower(&hasher.finalize());
    if actual_sha != meta.sha256_bin.to_lowercase() {
        return Err(ProjectionLoadError::Sha256Mismatch {
            expected: meta.sha256_bin,
            actual: actual_sha,
        });
    }

    let expected_bytes = meta.encoder_dim * meta.perception_dim * 4;
    if bytes.len() != expected_bytes {
        return Err(ProjectionLoadError::ShapeMismatch {
            actual: bytes.len(),
            expected: expected_bytes,
            encoder_dim: meta.encoder_dim,
            perception_dim: meta.perception_dim,
        });
    }

    let weights = bytes_to_f32_le(&bytes);

    let mean = match &meta.mean_vector_b64 {
        Some(b64) => decode_mean(b64, meta.encoder_dim)?,
        None => vec![0.0f32; meta.encoder_dim],
    };

    Ok(SvdProjection {
        weights,
        mean,
        encoder_dim: meta.encoder_dim,
        perception_dim: meta.perception_dim,
        sha256: actual_sha,
    })
}

/// Resolve `AB_SUBSTRATE_SVD_PATH` if set + non-empty.
pub fn svd_path_from_env() -> Option<PathBuf> {
    std::env::var(SVD_PATH_ENV)
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
}

/// True when env opts the process into SVD projection. Loader still has
/// to succeed — returning `true` here only means "try SVD first."
pub fn svd_env_enabled() -> bool {
    matches!(
        std::env::var(PROJECTION_KIND_ENV)
            .ok()
            .as_deref()
            .map(str::to_ascii_lowercase)
            .as_deref(),
        Some("svd")
    )
}

/// Phase 1 bucket-pool: each outer index `i` maps to bucket
/// `i*D/outer`, summed and L2-normalized. Pure function — moved out of
/// `SeedBackend` so [`Projection`] dispatches cleanly.
pub fn project_bucket_pool(v: &[f32], d: usize) -> Vec<f32> {
    let outer = v.len();
    let mut out = vec![0.0f32; d];
    if outer == 0 || d == 0 {
        return out;
    }
    for (i, &x) in v.iter().enumerate() {
        let bucket = (i * d / outer).min(d - 1);
        out[bucket] += x;
    }
    let norm: f32 = out.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm > 1e-9 {
        for x in out.iter_mut() {
            *x /= norm;
        }
    }
    out
}

fn bytes_to_f32_le(bytes: &[u8]) -> Vec<f32> {
    let n = bytes.len() / 4;
    let mut out = Vec::with_capacity(n);
    for chunk in bytes.chunks_exact(4) {
        out.push(f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]));
    }
    out
}

fn decode_mean(b64: &str, expected_dim: usize) -> Result<Vec<f32>, ProjectionLoadError> {
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(b64.trim())
        .map_err(|e| ProjectionLoadError::Base64(e.to_string()))?;
    if bytes.len() != expected_dim * 4 {
        return Err(ProjectionLoadError::MeanShapeMismatch {
            actual: bytes.len() / 4,
            expected: expected_dim,
        });
    }
    Ok(bytes_to_f32_le(&bytes))
}

fn hex_lower(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        use std::fmt::Write;
        let _ = write!(s, "{:02x}", b);
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;
    use base64::Engine;
    use std::io::Write;

    fn write_artifact(
        encoder_dim: usize,
        perception_dim: usize,
        weights: &[f32],
        mean: Option<&[f32]>,
        sha_override: Option<&str>,
        len_override: Option<usize>,
    ) -> (tempfile::TempDir, PathBuf) {
        let dir = tempfile::tempdir().unwrap();
        let bin_path = dir.path().join("svd.bin");
        let json_path = dir.path().join("svd.json");

        let mut bytes = Vec::with_capacity(weights.len() * 4);
        for w in weights {
            bytes.extend_from_slice(&w.to_le_bytes());
        }
        if let Some(n) = len_override {
            bytes.truncate(n.min(bytes.len()));
            while bytes.len() < n {
                bytes.push(0u8);
            }
        }
        std::fs::write(&bin_path, &bytes).unwrap();

        let mut hasher = Sha256::new();
        hasher.update(&bytes);
        let true_sha = hex_lower(&hasher.finalize());
        let sha = sha_override.unwrap_or(&true_sha).to_string();

        let mean_b64 = mean.map(|m| {
            let mut mb = Vec::with_capacity(m.len() * 4);
            for x in m {
                mb.extend_from_slice(&x.to_le_bytes());
            }
            base64::engine::general_purpose::STANDARD.encode(&mb)
        });

        let meta = serde_json::json!({
            "version": 1,
            "encoder_dim": encoder_dim,
            "perception_dim": perception_dim,
            "byte_order": "little-endian",
            "sha256_bin": sha,
            "mean_vector_b64": mean_b64,
        });
        let mut f = std::fs::File::create(&json_path).unwrap();
        f.write_all(serde_json::to_string(&meta).unwrap().as_bytes())
            .unwrap();
        (dir, bin_path)
    }

    #[test]
    fn load_svd_happy_path_no_center() {
        // 4x2 identity-like projection: takes first 2 of 4 inputs.
        #[rustfmt::skip]
        let weights = vec![
            1.0f32, 0.0,
            0.0,    1.0,
            0.0,    0.0,
            0.0,    0.0,
        ];
        let (_dir, bin) = write_artifact(4, 2, &weights, None, None, None);
        let svd = load_svd(&bin).unwrap();
        assert_eq!(svd.encoder_dim, 4);
        assert_eq!(svd.perception_dim, 2);
        assert_eq!(svd.weights.len(), 8);
        // No-center: mean defaults to zero vector of encoder_dim.
        assert_eq!(svd.mean, vec![0.0; 4]);
        // Project [3, 4, 0, 0] → [3, 4] → unit-norm = [0.6, 0.8].
        let out = svd.project(&[3.0, 4.0, 0.0, 0.0]);
        assert!((out[0] - 0.6).abs() < 1e-5);
        assert!((out[1] - 0.8).abs() < 1e-5);
    }

    #[test]
    fn load_svd_with_centered_mean_subtracts_correctly() {
        let weights = vec![1.0f32, 0.0, 0.0, 1.0]; // 2x2 identity
        let mean = vec![2.0f32, 3.0];
        let (_dir, bin) = write_artifact(2, 2, &weights, Some(&mean), None, None);
        let svd = load_svd(&bin).unwrap();
        // (5,7) - (2,3) = (3,4) → unit-norm [0.6, 0.8].
        let out = svd.project(&[5.0, 7.0]);
        assert!((out[0] - 0.6).abs() < 1e-5);
        assert!((out[1] - 0.8).abs() < 1e-5);
    }

    #[test]
    fn load_svd_rejects_sha_mismatch() {
        let weights = vec![1.0f32; 4];
        let (_dir, bin) = write_artifact(2, 2, &weights, None, Some("00deadbeef"), None);
        let err = load_svd(&bin).unwrap_err();
        assert!(matches!(err, ProjectionLoadError::Sha256Mismatch { .. }));
    }

    #[test]
    fn load_svd_rejects_shape_mismatch() {
        let weights = vec![1.0f32; 4]; // 16 bytes
        // Claim encoder_dim=4, perception_dim=2 (=> need 32 bytes) but file
        // only carries 16. Length override forces the underlying file to
        // mismatch the meta-declared shape.
        let (_dir, bin) = write_artifact(4, 2, &weights, None, None, Some(16));
        let err = load_svd(&bin).unwrap_err();
        assert!(matches!(err, ProjectionLoadError::ShapeMismatch { .. }));
    }

    #[test]
    fn load_svd_missing_file_returns_io_error() {
        let dir = tempfile::tempdir().unwrap();
        let bin = dir.path().join("nope.bin");
        let err = load_svd(&bin).unwrap_err();
        assert!(matches!(err, ProjectionLoadError::Io(_)));
    }

    #[test]
    fn projection_dispatch_kind_tag() {
        assert_eq!(Projection::BucketPool.kind(), "bucket_pool");
        let svd = SvdProjection {
            weights: vec![1.0, 0.0, 0.0, 1.0],
            mean: vec![0.0, 0.0],
            encoder_dim: 2,
            perception_dim: 2,
            sha256: "x".to_string(),
        };
        assert_eq!(Projection::Svd(svd).kind(), "svd");
    }

    #[test]
    fn projection_svd_output_is_unit_norm() {
        let weights = vec![1.0f32, 1.0, 1.0, 1.0]; // 2x2 all-ones
        let svd = SvdProjection {
            weights,
            mean: vec![0.0, 0.0],
            encoder_dim: 2,
            perception_dim: 2,
            sha256: "x".to_string(),
        };
        let out = svd.project(&[3.0, 4.0]);
        let norm: f32 = out.iter().map(|x| x * x).sum::<f32>().sqrt();
        assert!((norm - 1.0).abs() < 1e-5, "expected unit norm, got {norm}");
    }

    #[test]
    fn projection_svd_diverges_from_bucket_pool_for_real_input() {
        // Same 4-d input projected through identity-like SVD vs bucket-pool
        // produces structurally different outputs — confirms the dispatch
        // actually swaps semantics, not just labels.
        let weights = vec![1.0f32, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]; // 4x2 takes first 2
        let svd = SvdProjection {
            weights,
            mean: vec![0.0; 4],
            encoder_dim: 4,
            perception_dim: 2,
            sha256: "x".to_string(),
        };
        let input = vec![3.0f32, 4.0, 5.0, 6.0];
        let svd_out = svd.project(&input);
        let bp_out = project_bucket_pool(&input, 2);
        // SVD picks first two coords (3,4) → unit-norm.
        // Bucket-pool: bucket_0 ← idx 0,1 → 7; bucket_1 ← idx 2,3 → 11
        //   → (7, 11) → unit-norm ≈ (0.537, 0.844).
        assert!((svd_out[0] - 0.6).abs() < 1e-5);
        assert!((bp_out[0] - 7.0 / (49.0f32 + 121.0).sqrt()).abs() < 1e-5);
        assert!(
            (svd_out[0] - bp_out[0]).abs() > 0.01,
            "expected divergence; svd={:?} bp={:?}",
            svd_out,
            bp_out
        );
    }

    #[test]
    fn svd_env_enabled_respects_case_and_unset() {
        // Snapshot + restore (other tests may set this).
        let prev = std::env::var(PROJECTION_KIND_ENV).ok();
        std::env::set_var(PROJECTION_KIND_ENV, "svd");
        assert!(svd_env_enabled());
        std::env::set_var(PROJECTION_KIND_ENV, "SVD");
        assert!(svd_env_enabled());
        std::env::set_var(PROJECTION_KIND_ENV, "bucket_pool");
        assert!(!svd_env_enabled());
        std::env::remove_var(PROJECTION_KIND_ENV);
        assert!(!svd_env_enabled());
        if let Some(v) = prev {
            std::env::set_var(PROJECTION_KIND_ENV, v);
        }
    }
}
