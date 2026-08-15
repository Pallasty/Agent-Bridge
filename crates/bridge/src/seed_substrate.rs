//! Compatibility boundary for the legacy AiOT Seed substrate.
//!
//! The AB runtime no longer links the legacy `ab-seed-bridge` crate. Keeping
//! this shim lets historical CLI/MCP surfaces report a clean disabled state
//! while BioCortex becomes the active substrate integration path.

#[allow(dead_code, unused_imports)]
mod disabled {
    use std::path::{Path, PathBuf};
    use std::sync::Arc;

    use ab_store::embedding::EmbeddingBackend;
    use serde::{Deserialize, Serialize};

    pub const SUBSTRATE_ENV_VAR: &str = "AB_SUBSTRATE";

    const DISABLED: &str =
        "legacy Seed substrate support is unavailable; seed-substrate is a reserved compatibility marker and does not enable runtime or snapshot I/O";

    pub fn current() -> Option<Arc<SeedBackend>> {
        None
    }

    pub fn env_enabled() -> bool {
        matches!(
            std::env::var(SUBSTRATE_ENV_VAR).ok().as_deref(),
            Some("1") | Some("true") | Some("TRUE") | Some("yes")
        )
    }

    pub fn install_default() -> Result<(), &'static str> {
        Err(DISABLED)
    }

    pub fn neighbors_from_snapshot(
        _row: &SnapshotRow,
        _key: &str,
        _k: usize,
    ) -> Vec<(String, f32)> {
        Vec::new()
    }

    #[derive(Debug, Clone)]
    pub struct SubstrateConfig {
        pub n: usize,
        pub d: usize,
        pub state_noise: f32,
        pub lr: f32,
    }

    impl Default for SubstrateConfig {
        fn default() -> Self {
            Self {
                n: 256,
                d: 192,
                state_noise: 0.01,
                lr: 0.01,
            }
        }
    }

    #[derive(Debug, Clone, Serialize, Deserialize)]
    pub struct SubstrateStats {
        pub backend_name: String,
        pub n: usize,
        pub d: usize,
        pub outer_dim: usize,
        pub step_count: u64,
        pub last_surprise_mean: f32,
        pub last_surprise_max: f32,
        pub connection_mean_abs: f32,
        pub projection: String,
    }

    pub struct SeedBackend {
        inner: Arc<dyn EmbeddingBackend>,
        config: SubstrateConfig,
        snapshot_path: Option<PathBuf>,
    }

    impl SeedBackend {
        pub fn wrap(inner: Arc<dyn EmbeddingBackend>) -> Self {
            Self::wrap_with(inner, SubstrateConfig::default())
        }

        pub fn wrap_with(inner: Arc<dyn EmbeddingBackend>, config: SubstrateConfig) -> Self {
            Self {
                inner,
                config,
                snapshot_path: None,
            }
        }

        pub fn set_snapshot_path(&self, _path: Option<PathBuf>) {}

        pub fn snapshot_path(&self) -> Option<PathBuf> {
            self.snapshot_path.clone()
        }

        pub fn stats(&self) -> SubstrateStats {
            SubstrateStats {
                backend_name: format!("{}+seed-substrate-disabled", self.inner.name()),
                n: self.config.n,
                d: self.config.d,
                outer_dim: self.inner.dim(),
                step_count: 0,
                last_surprise_mean: 0.0,
                last_surprise_max: 0.0,
                connection_mean_abs: 0.0,
                projection: "disabled".to_string(),
            }
        }

        pub fn build_row(&self, tier: SnapshotTier, now: i64) -> Option<SnapshotRow> {
            Some(SnapshotRow {
                step: 0,
                cycle_ts: now,
                tier,
                n_alive: self.config.n as i32,
                in_strengths: Vec::new(),
                last_perceived_key: Vec::new(),
                last_perceived_ts: Vec::new(),
                trailing_surprise_mean_short: 0.0,
                trailing_surprise_mean_long: 0.0,
                connection_logits: Vec::new(),
            })
        }

        pub fn neighbors_of(&self, _key: &str, _k: usize) -> Vec<(String, f32)> {
            Vec::new()
        }
    }

    impl EmbeddingBackend for SeedBackend {
        fn name(&self) -> &str {
            "seed-substrate-disabled"
        }

        fn dim(&self) -> usize {
            self.inner.dim()
        }

        fn embed(&self, text: &str) -> Vec<f32> {
            self.inner.embed(text)
        }

        fn embed_batch(&self, texts: &[&str]) -> Vec<Vec<f32>> {
            self.inner.embed_batch(texts)
        }

        fn perceive(&self, text_to_embed: &str, key_to_perceive: &str) -> Vec<f32> {
            self.inner.perceive(text_to_embed, key_to_perceive)
        }

        fn perceive_batch(&self, texts: &[&str], keys: &[&str]) -> Vec<Vec<f32>> {
            self.inner.perceive_batch(texts, keys)
        }
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
    pub enum SnapshotTier {
        Hot,
        Long,
    }

    impl SnapshotTier {
        pub fn as_str(self) -> &'static str {
            match self {
                Self::Hot => "hot",
                Self::Long => "long",
            }
        }

        pub fn from_str(s: &str) -> Option<Self> {
            match s {
                "hot" => Some(Self::Hot),
                "long" => Some(Self::Long),
                _ => None,
            }
        }
    }

    #[derive(Debug, Clone, PartialEq)]
    pub struct SnapshotRow {
        pub step: i64,
        pub cycle_ts: i64,
        pub tier: SnapshotTier,
        pub n_alive: i32,
        pub in_strengths: Vec<f32>,
        pub last_perceived_key: Vec<String>,
        pub last_perceived_ts: Vec<i64>,
        pub trailing_surprise_mean_short: f32,
        pub trailing_surprise_mean_long: f32,
        pub connection_logits: Vec<f32>,
    }

    pub mod snapshot {
        use super::*;

        pub use super::{SnapshotRow, SnapshotTier};

        #[derive(Debug, thiserror::Error)]
        pub enum SnapshotError {
            #[error("legacy Seed substrate support is unavailable; seed-substrate is a reserved compatibility marker and does not enable runtime or snapshot I/O")]
            Disabled,
        }

        pub fn require_write_capability() -> Result<(), SnapshotError> {
            Err(SnapshotError::Disabled)
        }

        pub fn default_snapshot_path() -> Option<PathBuf> {
            std::env::var("HOME")
                .ok()
                .map(|h| PathBuf::from(h).join(".local/share/agent-bridge/substrate.parquet"))
        }

        pub fn read_all(_path: &Path) -> Result<Vec<SnapshotRow>, SnapshotError> {
            Err(SnapshotError::Disabled)
        }

        pub fn append_row(_path: &Path, _row: SnapshotRow) -> Result<String, SnapshotError> {
            Err(SnapshotError::Disabled)
        }

        pub fn fingerprint(row: &SnapshotRow) -> String {
            format!(
                "seed-substrate-disabled-step-{}-ts-{}-tier-{}",
                row.step,
                row.cycle_ts,
                row.tier.as_str()
            )
        }
    }
}

pub use disabled::*;
