//! v22 — agent-bridge memory substrate Layer 2.
//!
//! Phase 1 scaffold (commit per design board #6 post 57 Gate A pass):
//! wraps an inner [`EmbeddingBackend`] with an AiOT
//! [`seed_neuron::NeuronGrid`] that observes every embedding call as
//! perception. The outer `embed()` returns the inner backend's vector
//! unchanged — L3 retrieval contract (384-dim cosine search) is
//! preserved — while the substrate accumulates topology in parallel.
//!
//! ## Non-goals for phase 1
//! - No snapshot persistence (state lives in-process until process exit)
//! - No learned projection 384 → D (uses deterministic truncate, see
//!   Q-back-1 caveat in `research_v22_perception_dim_pca_scree_2026_05_13`)
//! - No `neighbors_of` query API (phase 3)
//! - No multi-grid / inter-grid signal exchange (phase 4+)
//!
//! Phase 1 only needs to show G1-G3 from v22 §1: events flow through →
//! `connection_logits` change → `stats()` reports `n_alive` & `step_count`.

use std::cmp::Ordering;
use std::collections::{HashSet, VecDeque};
use std::path::PathBuf;
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

use ab_store::embedding::{EmbeddingBackend, HashBackend, OnnxBackend};
use seed_neuron::NeuronGrid;
use serde::{Deserialize, Serialize};

pub mod projection;
pub mod snapshot;
pub use snapshot::{SnapshotRow, SnapshotTier};

/// Env var that opts the process into substrate. Set to `1` / `true` to
/// install [`SeedBackend`] as the default embedding backend at startup.
/// Default (unset): no substrate, agent-bridge runs as before (G5 ablation).
pub const SUBSTRATE_ENV_VAR: &str = "AB_SUBSTRATE";

/// Process-wide handle to the installed substrate, set by
/// [`install_default`]. `None` if substrate is disabled or never installed.
static INSTANCE: OnceLock<Arc<SeedBackend>> = OnceLock::new();

/// Returns the current substrate handle, if installed. CLI / MCP tools
/// use this to render `stats`.
pub fn current() -> Option<Arc<SeedBackend>> {
    INSTANCE.get().cloned()
}

/// Whether the env var opts this process into substrate. Pure read.
pub fn env_enabled() -> bool {
    match std::env::var(SUBSTRATE_ENV_VAR).ok().as_deref() {
        Some("1") | Some("true") | Some("TRUE") | Some("yes") => true,
        _ => false,
    }
}

/// Install [`SeedBackend`] as the process-wide default embedding backend.
///
/// Builds an inner backend by reading `AGENT_BRIDGE_EMBED_BACKEND` (same
/// precedence ab-store uses), wraps it with substrate, and registers
/// with `ab_store::embedding::set_default_backend`. Also stores the
/// wrapped backend in [`INSTANCE`] so `stats` callers can read its state.
///
/// Safe to call at most once per process. Subsequent calls are no-ops
/// returning `Err`. MUST be called before any `memory_save` /
/// `memory_search` activity — the `OnceLock` semantics in ab-store make
/// late install silently inert.
pub fn install_default() -> Result<(), &'static str> {
    let inner = build_inner_backend();
    // Phase 2.4 — opt into SVD warm-start projection iff env opts in AND
    // load succeeds. Any failure logs and falls back to bucket-pool so
    // mis-deployment never panics the daemon.
    let proj = resolve_install_projection();
    let backend = Arc::new(SeedBackend::wrap_with_projection(
        inner,
        SubstrateConfig::default(),
        proj,
    ));
    // Phase 2.2 — auto-wire snapshot persistence at install time. Tests
    // that don't want IO simply don't call `install_default`.
    backend.set_snapshot_path(snapshot::default_snapshot_path());
    INSTANCE
        .set(backend.clone())
        .map_err(|_| "seed-bridge already installed")?;
    ab_store::embedding::set_default_backend(backend)?;
    Ok(())
}

/// Decide which [`projection::Projection`] to install based on env vars.
/// Returns `BucketPool` when SVD is not opted into OR when the load
/// fails. Failure path is logged to `tracing::warn` so deployment
/// surfaces still tell the operator why bucket-pool is in effect.
fn resolve_install_projection() -> projection::Projection {
    if !projection::svd_env_enabled() {
        return projection::Projection::BucketPool;
    }
    let path = match projection::svd_path_from_env() {
        Some(p) => p,
        None => {
            tracing::warn!(
                env = projection::SVD_PATH_ENV,
                "AB_SUBSTRATE_PROJECTION=svd but {} unset — falling back to bucket-pool",
                projection::SVD_PATH_ENV
            );
            return projection::Projection::BucketPool;
        }
    };
    match projection::load_svd(&path) {
        Ok(svd) => {
            tracing::info!(
                path = %path.display(),
                sha256 = %svd.sha256,
                encoder_dim = svd.encoder_dim,
                perception_dim = svd.perception_dim,
                "substrate-projection: loaded SVD warm-start"
            );
            projection::Projection::Svd(svd)
        }
        Err(e) => {
            tracing::warn!(
                path = %path.display(),
                error = %e,
                "substrate-projection: SVD load failed — falling back to bucket-pool"
            );
            projection::Projection::BucketPool
        }
    }
}

/// Env var ab-store uses to pick the default backend. We mirror its
/// precedence so wrapping decisions stay in sync — substrate observes
/// the same kind of perception that retrieval would have produced.
const ABSTORE_BACKEND_ENV: &str = "AGENT_BRIDGE_EMBED_BACKEND";

/// Mirror of `ab_store::embedding::select_default` so SeedBackend wraps
/// whatever would have been the default. Selection precedence:
///   1. `AGENT_BRIDGE_EMBED_BACKEND` env (`onnx` | `hash`)
///   2. Compile-time default: ONNX (ab-store has `onnx-embed` feature on
///      by default).
///
/// `OnnxBackend` carries its own hash fallback if the model fails to
/// load, so picking onnx is always safe — at worst it degrades to hash
/// at first call. Phase 2.1 lifts wrap from hash-only (phase 1) to
/// real-semantic ONNX so substrate perception is in the same vector
/// space the L3 retrieval sees.
fn build_inner_backend() -> Arc<dyn EmbeddingBackend> {
    match select_inner_kind().as_str() {
        "hash" => Arc::new(HashBackend),
        // "onnx" or anything else → onnx (it falls back to hash on
        // model-load failure, so unknown values are safe-by-default).
        _ => Arc::new(OnnxBackend),
    }
}

/// Pure helper for selection precedence. Extracted so the choice is
/// unit-testable without spinning up ONNX. Returns `"onnx"` or
/// `"hash"`; unknown env values fall through to `"onnx"` and the
/// `build_inner_backend` arm handles the fallback safely.
fn select_inner_kind() -> String {
    std::env::var(ABSTORE_BACKEND_ENV)
        .ok()
        .map(|s| s.to_lowercase())
        .filter(|s| s == "hash" || s == "onnx")
        .unwrap_or_else(|| "onnx".to_string())
}

/// v22 substrate config. Defaults from `DESIGN-v22-...md` §3.3 (Q-back-1
/// integrated): N=256, D=192. `state_noise` and `lr` are AiOT crate
/// defaults; safe values for memory-domain perception per multigrid
/// foundations §5.6 envelope.
#[derive(Debug, Clone)]
pub struct SubstrateConfig {
    /// Grid size. Phase 1: 256 starting point per Multi-Grid Foundations §5.6.
    pub n: usize,
    /// Substrate-internal perception dim. 192 per Q-back-1 PCA scree
    /// (≥80% cum_var on real 659×384 corpus). MUST be ≤ inner backend
    /// dim so truncate projection is well-defined.
    pub d: usize,
    /// Random-walk noise on non-carrier neuron states (AiOT crate default 0.01).
    pub state_noise: f32,
    /// Adam learning rate (AiOT crate default 0.01).
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

/// Snapshot of substrate health for the `agent-bridge substrate stats`
/// CLI. Phase 1 reports the bare minimum needed to confirm G1-G3:
/// the grid is running, receiving perception, learning topology.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubstrateStats {
    pub backend_name: String,
    pub n: usize,
    pub d: usize,
    /// Outer dim — the embedding the inner backend produces; we return
    /// this unchanged.
    pub outer_dim: usize,
    /// Total `step()` calls since process start.
    pub step_count: u64,
    /// Latest surprise array (mean & max over the grid). Drifts during
    /// learning; flatlined means substrate is dormant.
    pub last_surprise_mean: f32,
    pub last_surprise_max: f32,
    /// Mean absolute connection weight across all (i,j), i≠j. Phase 1
    /// proxy for "topology has structure"; should drift from initial
    /// 1/(N-1) toward bimodal extremes as learning proceeds.
    pub connection_mean_abs: f32,
    /// Phase 2.4 — active outer→D projection ("bucket_pool" | "svd").
    /// `bucket_pool` is Phase 1 default; `svd` confirms a successful
    /// SVD warm-start load via env opt-in. Surfaced so the operator
    /// knows at a glance which path is in effect.
    #[serde(default = "default_projection_tag")]
    pub projection: String,
}

fn default_projection_tag() -> String {
    "bucket_pool".to_string()
}

/// v22 substrate backend.
///
/// Implements [`EmbeddingBackend`] by **delegating** to an inner backend
/// for the public contract (text → 384-dim vector). After the inner call
/// returns, the same vector is projected to D and fed into the substrate
/// grid as one perception step. Steps run synchronously on the calling
/// thread; each is ~1 ms at N=256.
pub struct SeedBackend {
    inner: Arc<dyn EmbeddingBackend>,
    config: SubstrateConfig,
    grid: Mutex<NeuronGrid>,
    last_surprise: Mutex<(f32, f32)>, // (mean, max)
    // Phase 2.2 — trailing surprise rings + last_perceived per neuron + snapshot path.
    surprise_short: Mutex<VecDeque<f32>>,
    surprise_long: Mutex<VecDeque<f32>>,
    last_perceived: Mutex<Vec<(String, i64)>>,
    last_long_snapshot_ts: Mutex<i64>,
    /// Phase 2.2 snapshot file path. `None` disables snapshot writes
    /// (used by tests and ablation). Defaults to
    /// [`snapshot::default_snapshot_path`] when [`install_default`] runs.
    snapshot_path: Mutex<Option<PathBuf>>,
    /// Phase 2.4 — outer→D projection. Installed once at construct time
    /// so the hot-path `project()` is a borrow + dispatch with no lock.
    /// Defaults to [`projection::Projection::BucketPool`] (Phase 1
    /// behaviour); SVD warm-start activated by `install_default` when
    /// env opts in and the artifact loads cleanly.
    projection: projection::Projection,
}

impl SeedBackend {
    /// Wrap an inner backend with default substrate config.
    pub fn wrap(inner: Arc<dyn EmbeddingBackend>) -> Self {
        Self::wrap_with(inner, SubstrateConfig::default())
    }

    /// Wrap with explicit config. Panics if `config.d > inner.dim()` —
    /// the truncate projection requires the substrate dim be ≤ outer dim.
    pub fn wrap_with(inner: Arc<dyn EmbeddingBackend>, config: SubstrateConfig) -> Self {
        Self::wrap_with_projection(inner, config, projection::Projection::default())
    }

    /// Wrap with explicit config + caller-supplied projection. Used by
    /// [`install_default`] to swap in Phase 2.4 SVD warm-start. Panics
    /// if `config.d > inner.dim()` (same invariant as [`wrap_with`]).
    /// SVD projections additionally require `svd.encoder_dim ==
    /// inner.dim()` — caller is responsible for matching the artifact
    /// to the running encoder; mismatched SVD is degraded to bucket-pool
    /// with a warning rather than panicking the daemon.
    pub fn wrap_with_projection(
        inner: Arc<dyn EmbeddingBackend>,
        config: SubstrateConfig,
        projection: projection::Projection,
    ) -> Self {
        assert!(
            config.d <= inner.dim(),
            "substrate D={} must not exceed inner backend dim {}",
            config.d,
            inner.dim()
        );
        let projection = match &projection {
            projection::Projection::Svd(svd) if svd.encoder_dim != inner.dim() => {
                tracing::warn!(
                    svd_encoder_dim = svd.encoder_dim,
                    inner_dim = inner.dim(),
                    "substrate-projection: SVD encoder_dim != inner.dim — falling back to bucket-pool"
                );
                projection::Projection::BucketPool
            }
            projection::Projection::Svd(svd) if svd.perception_dim != config.d => {
                tracing::warn!(
                    svd_perception_dim = svd.perception_dim,
                    substrate_d = config.d,
                    "substrate-projection: SVD perception_dim != config.d — falling back to bucket-pool"
                );
                projection::Projection::BucketPool
            }
            _ => projection,
        };
        let grid = NeuronGrid::new(
            config.n,
            config.d,
            /*primary_carrier=*/ 0,
            /*secondary_carrier=*/ 1,
            config.state_noise,
        );
        let last_perceived = vec![(String::new(), 0i64); config.n];
        Self {
            inner,
            config,
            grid: Mutex::new(grid),
            last_surprise: Mutex::new((0.0, 0.0)),
            surprise_short: Mutex::new(VecDeque::with_capacity(snapshot::SHORT_WINDOW + 1)),
            surprise_long: Mutex::new(VecDeque::with_capacity(snapshot::LONG_WINDOW + 1)),
            last_perceived: Mutex::new(last_perceived),
            last_long_snapshot_ts: Mutex::new(0),
            snapshot_path: Mutex::new(None),
            projection,
        }
    }

    /// Stable kind tag for the active projection ("bucket_pool" | "svd").
    /// Surfaced in [`SubstrateStats`] + the `substrate stats` CLI so the
    /// operator can confirm Phase 2.4 wire-up at a glance.
    pub fn projection_kind(&self) -> &'static str {
        self.projection.kind()
    }

    /// Set or clear the snapshot file path. `install_default` calls this
    /// with [`snapshot::default_snapshot_path`]; tests pass a `tempdir`
    /// path; passing `None` disables snapshot writes entirely.
    pub fn set_snapshot_path(&self, path: Option<PathBuf>) {
        if let Ok(mut p) = self.snapshot_path.lock() {
            *p = path;
        }
    }

    /// Snapshot file path currently configured.
    pub fn snapshot_path(&self) -> Option<PathBuf> {
        self.snapshot_path.lock().ok().and_then(|g| g.clone())
    }

    /// Outer→D projection. Dispatches on the installed
    /// [`projection::Projection`]: Phase 1 bucket-pool by default; Phase
    /// 2.4 SVD warm-start when the operator opts in via
    /// `AB_SUBSTRATE_PROJECTION=svd` + `AB_SUBSTRATE_SVD_PATH`. Returns
    /// unit-norm in either case.
    fn project(&self, v: &[f32]) -> Vec<f32> {
        self.projection.project(v, self.config.d)
    }

    /// Perception step. Called once per outer `embed()`. `primary` is the
    /// projected vector; `secondary` is the zero vector in phase 1 (the
    /// rolling-mean second carrier is a phase 2 feature). `perceived_text`
    /// is the original input text — used to populate per-neuron
    /// `last_perceived_key` for the winning neuron (argmin surprise).
    fn step(&self, primary: &[f32], perceived_text: &str) {
        let secondary = vec![0.0f32; self.config.d];
        let (surprises, step_count) = {
            let mut grid = match self.grid.lock() {
                Ok(g) => g,
                Err(_) => return, // poisoned; degrade silently
            };
            let s = grid.step(primary, &secondary, self.config.lr);
            let sc = grid.step_count;
            (s, sc)
        };
        let (mean, max) = surprise_stats(&surprises);
        if let Ok(mut s) = self.last_surprise.lock() {
            *s = (mean, max);
        }

        // Phase 2.2 — trailing surprise rings.
        let now = unix_secs_now();
        if let Ok(mut short) = self.surprise_short.lock() {
            short.push_back(mean);
            while short.len() > snapshot::SHORT_WINDOW {
                short.pop_front();
            }
        }
        if let Ok(mut long_ring) = self.surprise_long.lock() {
            long_ring.push_back(mean);
            while long_ring.len() > snapshot::LONG_WINDOW {
                long_ring.pop_front();
            }
        }

        // Phase 2.2 — per-neuron last_perceived. Winner = argmin surprise
        // (the neuron whose Hebbian prediction was closest to the input).
        if !perceived_text.is_empty() {
            if let Some(winner) = argmin(&surprises) {
                if let Ok(mut lp) = self.last_perceived.lock() {
                    if winner < lp.len() {
                        lp[winner] = (perceived_text.to_string(), now);
                    }
                }
            }
        }

        // Phase 2.2 — cadence check + snapshot write.
        self.maybe_snapshot(step_count, now);
    }

    /// Trailing surprise mean over the last [`snapshot::SHORT_WINDOW`]
    /// events. Returns 0.0 when the ring is empty.
    fn trailing_short(&self) -> f32 {
        ring_mean(&self.surprise_short)
    }

    /// Trailing surprise mean over the last [`snapshot::LONG_WINDOW`]
    /// events. Returns 0.0 when the ring is empty.
    fn trailing_long(&self) -> f32 {
        ring_mean(&self.surprise_long)
    }

    /// Build a snapshot row from current substrate state. `tier` controls
    /// whether the expensive `connection_logits` is filled (Long) or left
    /// empty (Hot).
    pub fn build_row(&self, tier: SnapshotTier, now: i64) -> Option<SnapshotRow> {
        let (n, step_count, conn, in_strengths) = {
            let grid = self.grid.lock().ok()?;
            let matrix = grid.connection_matrix();
            // in_strengths proxy: sum of absolute connection weights INTO
            // each neuron (column-wise). Hebbian "how strongly does the
            // grid attend to me?" signal.
            let in_strengths = column_abs_sums(&matrix);
            let logits = if matches!(tier, SnapshotTier::Long) {
                flatten_off_diagonal(&matrix)
            } else {
                Vec::new()
            };
            (grid.n, grid.step_count, logits, in_strengths)
        };
        let (keys, ts) = {
            let lp = self.last_perceived.lock().ok()?;
            let keys: Vec<String> = lp.iter().map(|(s, _)| s.clone()).collect();
            let tss: Vec<i64> = lp.iter().map(|(_, t)| *t).collect();
            (keys, tss)
        };
        Some(SnapshotRow {
            step: step_count as i64,
            cycle_ts: now,
            tier,
            n_alive: n as i32,
            in_strengths,
            last_perceived_key: keys,
            last_perceived_ts: ts,
            trailing_surprise_mean_short: self.trailing_short(),
            trailing_surprise_mean_long: self.trailing_long(),
            connection_logits: conn,
        })
    }

    /// Cadence dispatcher: at most one snapshot write per step. Long tier
    /// takes precedence when both fire (it strictly subsumes Hot data).
    fn maybe_snapshot(&self, step_count: u64, now: i64) {
        let last_long_ts = self
            .last_long_snapshot_ts
            .lock()
            .map(|g| *g)
            .unwrap_or(0);
        let do_long = snapshot::should_write_long(step_count, last_long_ts, now);
        let do_hot = snapshot::should_write_hot(step_count);
        if !(do_long || do_hot) {
            return;
        }
        let tier = if do_long {
            SnapshotTier::Long
        } else {
            SnapshotTier::Hot
        };
        let path = match self.snapshot_path() {
            Some(p) => p,
            None => return, // snapshot disabled
        };
        let row = match self.build_row(tier, now) {
            Some(r) => r,
            None => return,
        };
        match snapshot::append_row(&path, row) {
            Ok(fp) => tracing::debug!(
                "substrate snapshot tier={} step={} fp={}",
                tier.as_str(),
                step_count,
                &fp[..16]
            ),
            Err(e) => tracing::warn!(
                "substrate snapshot write failed: {}",
                e
            ),
        }
        if do_long {
            if let Ok(mut ts) = self.last_long_snapshot_ts.lock() {
                *ts = now;
            }
        }
    }

    /// G3-ready snapshot. Cheap; no mutation; safe to call from any thread.
    pub fn stats(&self) -> SubstrateStats {
        let (n, d, step_count, conn_abs) = {
            let grid = self
                .grid
                .lock()
                .expect("substrate grid mutex poisoned in stats()");
            let mat = grid.connection_matrix();
            let mut sum = 0.0f64;
            let mut count = 0u64;
            for (i, row) in mat.iter().enumerate() {
                for (j, &w) in row.iter().enumerate() {
                    if i == j {
                        continue;
                    }
                    sum += w.abs() as f64;
                    count += 1;
                }
            }
            let mean = if count > 0 {
                (sum / count as f64) as f32
            } else {
                0.0
            };
            (grid.n, grid.dim, grid.step_count, mean)
        };
        let (mean, max) = self
            .last_surprise
            .lock()
            .map(|g| *g)
            .unwrap_or((0.0, 0.0));
        SubstrateStats {
            backend_name: self.inner.name().to_string(),
            projection: self.projection_kind().to_string(),
            n,
            d,
            outer_dim: self.inner.dim(),
            step_count,
            last_surprise_mean: mean,
            last_surprise_max: max,
            connection_mean_abs: conn_abs,
        }
    }

    /// v22 §3.5 substrate query API. Phase 3 (A).
    ///
    /// Find neurons whose most recent winning perception was `key`, then
    /// return up to `k` distinct *other* keys those neurons connect to
    /// most strongly, weighted by summed absolute `connection_logits`.
    ///
    /// Read-only — no mutation, no access bump (vision rule 5). Returns
    /// empty when:
    /// - `key` is empty or unknown to any neuron's `last_perceived`
    /// - `k == 0`
    /// - substrate has had zero perception steps
    ///
    /// Known lossiness: `last_perceived` keeps one slot per neuron, so a
    /// key whose winner-neuron later fires on a different text is lost
    /// from this query. v0 accepts this — matches snapshot persistence.
    /// Phase 3.1 candidate: explicit `recent_winners` reverse index.
    pub fn neighbors_of(&self, key: &str, k: usize) -> Vec<(String, f32)> {
        if k == 0 || key.is_empty() {
            return Vec::new();
        }
        // Post 89 Minor #3: clone last_perceived once instead of locking
        // twice. At N=256 this is ~256 short String clones — negligible
        // vs reacquiring the mutex.
        let lp_snapshot: Vec<(String, i64)> = match self.last_perceived.lock() {
            Ok(g) => g.clone(),
            Err(_) => return Vec::new(),
        };
        let winners: Vec<usize> = lp_snapshot
            .iter()
            .enumerate()
            .filter(|(_, (k_text, _))| k_text == key)
            .map(|(i, _)| i)
            .collect();
        if winners.is_empty() {
            return Vec::new();
        }
        let matrix = {
            let grid = match self.grid.lock() {
                Ok(g) => g,
                Err(_) => return Vec::new(),
            };
            grid.connection_matrix()
        };
        let n = matrix.len();
        if n == 0 {
            return Vec::new();
        }
        let mut scores = vec![0.0f32; n];
        for &w in &winners {
            if w >= n {
                continue;
            }
            for (j, &weight) in matrix[w].iter().enumerate() {
                if j == w || j >= scores.len() {
                    continue;
                }
                // Post 89 Minor #2: `connection_matrix()` returns softmax
                // values (≥0), so `.abs()` is a no-op here. Kept as
                // defensive guard for any future signed-weight variant
                // of the underlying matrix (e.g. raw logits or
                // covariance-style topology) without changing this call
                // site.
                scores[j] += weight.abs();
            }
        }
        let mut ranked: Vec<(usize, f32)> = scores.iter().copied().enumerate().collect();
        ranked.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(Ordering::Equal));
        let mut seen: HashSet<String> = HashSet::new();
        let mut out: Vec<(String, f32)> = Vec::with_capacity(k);
        for (i, score) in ranked {
            if score <= 0.0 {
                break;
            }
            let cand = match lp_snapshot.get(i) {
                Some((s, _)) => s,
                None => continue,
            };
            if cand.is_empty() || cand == key {
                continue;
            }
            if seen.insert(cand.clone()) {
                out.push((cand.clone(), score));
                if out.len() >= k {
                    break;
                }
            }
        }
        out
    }
}

impl EmbeddingBackend for SeedBackend {
    fn name(&self) -> &str {
        // Identify ourselves so `embedding_backend` column distinguishes
        // substrate-mediated embeds from raw inner-backend embeds.
        "aiot-seed-v1"
    }

    fn dim(&self) -> usize {
        self.inner.dim()
    }

    fn embed(&self, text: &str) -> Vec<f32> {
        let v = self.inner.embed(text);
        // Defensive: if inner returns wrong-length vector, skip step
        // rather than panic.
        if v.len() == self.inner.dim() {
            let primary = self.project(&v);
            self.step(&primary, text);
        }
        v
    }

    fn embed_batch(&self, texts: &[&str]) -> Vec<Vec<f32>> {
        let vecs = self.inner.embed_batch(texts);
        for (v, &text) in vecs.iter().zip(texts.iter()) {
            if v.len() == self.inner.dim() {
                let primary = self.project(v);
                self.step(&primary, text);
            }
        }
        vecs
    }
}

/// Snapshot-based variant of [`SeedBackend::neighbors_of`]. Same **shape**
/// applied to a serialized [`SnapshotRow`] read from `substrate.parquet`,
/// so short-lived CLI / cross-process queries can answer without
/// installing a live substrate. Only `Long`-tier rows carry the
/// `connection_logits` field this needs; Hot rows always return `[]`.
///
/// **Semantic asymmetry vs live** (Phase 3 A review post 89 Minor #1):
/// the live `SeedBackend::neighbors_of` weights neighbors by
/// `grid.connection_matrix()` which is **softmax(logits)** per
/// `seed_neuron::dynamic`, while this function weights by **raw logits**
/// straight out of the SnapshotRow. The two are rank-preserving for the
/// typical low-variance distributions we expect at N=256, but **not
/// bit-exact** when logits are bimodal — softmax squashes the middle
/// tail and can re-order keys whose scores are close. Trend-tracking
/// (Day-7/14/28 P2 audit) is unaffected because both pipelines are
/// self-consistent; cross-pipeline diff is the failure mode to watch.
/// Phase 3.1 candidate: apply per-winner-row softmax here too for
/// strict equivalence.
pub fn neighbors_from_snapshot(
    row: &SnapshotRow,
    key: &str,
    k: usize,
) -> Vec<(String, f32)> {
    if k == 0 || key.is_empty() {
        return Vec::new();
    }
    if !matches!(row.tier, SnapshotTier::Long) {
        return Vec::new();
    }
    let lp = &row.last_perceived_key;
    let n = lp.len();
    if n == 0 {
        return Vec::new();
    }
    let logits = &row.connection_logits;
    let expected = n * n.saturating_sub(1);
    if logits.len() != expected {
        return Vec::new();
    }
    let winners: Vec<usize> = lp
        .iter()
        .enumerate()
        .filter(|(_, t)| t.as_str() == key)
        .map(|(i, _)| i)
        .collect();
    if winners.is_empty() {
        return Vec::new();
    }
    let mut scores = vec![0.0f32; n];
    for &w in &winners {
        if w >= n {
            continue;
        }
        let base = w * (n - 1);
        for off in 0..(n - 1) {
            // Off-diagonal layout: row w skips column w; off-index `off`
            // maps to column `off` when `off < w` else `off + 1`.
            let j = if off < w { off } else { off + 1 };
            if j == w || j >= scores.len() {
                continue;
            }
            scores[j] += logits[base + off].abs();
        }
    }
    let mut ranked: Vec<(usize, f32)> = scores.iter().copied().enumerate().collect();
    ranked.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(Ordering::Equal));
    let mut seen: HashSet<String> = HashSet::new();
    let mut out: Vec<(String, f32)> = Vec::with_capacity(k);
    for (i, score) in ranked {
        if score <= 0.0 {
            break;
        }
        let cand = match lp.get(i) {
            Some(s) => s.as_str(),
            None => continue,
        };
        if cand.is_empty() || cand == key {
            continue;
        }
        if seen.insert(cand.to_string()) {
            out.push((cand.to_string(), score));
            if out.len() >= k {
                break;
            }
        }
    }
    out
}

fn unix_secs_now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn argmin(s: &[f32]) -> Option<usize> {
    let mut best: Option<(usize, f32)> = None;
    for (i, &v) in s.iter().enumerate() {
        if !v.is_finite() {
            continue;
        }
        match best {
            None => best = Some((i, v)),
            Some((_, bv)) if v < bv => best = Some((i, v)),
            _ => {}
        }
    }
    best.map(|(i, _)| i)
}

fn ring_mean(m: &Mutex<VecDeque<f32>>) -> f32 {
    let g = match m.lock() {
        Ok(g) => g,
        Err(_) => return 0.0,
    };
    if g.is_empty() {
        return 0.0;
    }
    let sum: f64 = g.iter().map(|x| *x as f64).sum();
    (sum / g.len() as f64) as f32
}

/// Flatten an [n][n] connection matrix to a flat Vec of length N×(N-1),
/// skipping the diagonal (neurons have no self-logit, per memo §3.4).
fn flatten_off_diagonal(m: &[Vec<f32>]) -> Vec<f32> {
    let n = m.len();
    let mut out = Vec::with_capacity(n * n.saturating_sub(1));
    for (i, row) in m.iter().enumerate() {
        for (j, &v) in row.iter().enumerate() {
            if i == j {
                continue;
            }
            out.push(v);
        }
    }
    out
}

/// Sum of absolute column-j values in [n][n] matrix m — the in-strength
/// proxy "how strongly does the grid attend to neuron j?".
fn column_abs_sums(m: &[Vec<f32>]) -> Vec<f32> {
    let n = m.len();
    let mut out = vec![0.0f32; n];
    for row in m {
        for (j, &v) in row.iter().enumerate() {
            if j < out.len() {
                out[j] += v.abs();
            }
        }
    }
    out
}

fn surprise_stats(s: &[f32]) -> (f32, f32) {
    if s.is_empty() {
        return (0.0, 0.0);
    }
    let mean = s.iter().sum::<f32>() / s.len() as f32;
    let max = s.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
    (mean, max)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(d: usize) -> SeedBackend {
        SeedBackend::wrap_with(
            Arc::new(HashBackend),
            SubstrateConfig {
                n: 32, // small grid for fast tests
                d,
                state_noise: 0.01,
                lr: 0.01,
            },
        )
    }

    #[test]
    fn outer_dim_matches_inner_and_passes_through() {
        // v22 §1 G5: ablation-safe contract — outer embed() must
        // return inner backend's vector verbatim. Substrate observes,
        // doesn't transform.
        let inner = Arc::new(HashBackend);
        let raw = inner.embed("hello world");
        let backend = SeedBackend::wrap_with(
            inner.clone(),
            SubstrateConfig {
                n: 16,
                d: 64,
                state_noise: 0.01,
                lr: 0.01,
            },
        );
        let out = backend.embed("hello world");
        assert_eq!(backend.dim(), 384);
        assert_eq!(out, raw, "outer embed must equal inner embed");
    }

    #[test]
    fn step_count_advances_on_each_call() {
        // v22 §1 G1: every memory event flows through substrate. After
        // 5 embed() calls, step_count must be exactly 5.
        let b = fixture(64);
        assert_eq!(b.stats().step_count, 0);
        for s in ["one", "two", "three", "four", "five"] {
            let _ = b.embed(s);
        }
        assert_eq!(b.stats().step_count, 5);
    }

    #[test]
    fn batch_advances_step_count_per_text() {
        // Phase 1 batch path also dispatches one step per text. If a
        // future optimization batches stepping, this test changes —
        // but for now: 1 text = 1 step.
        let b = fixture(64);
        let texts: Vec<&str> = vec!["a", "b", "c", "d"];
        let _ = b.embed_batch(&texts);
        assert_eq!(b.stats().step_count, 4);
    }

    #[test]
    fn surprise_is_recorded_after_step() {
        // v22 §1 G2: substrate is learning. Surprise from `step()` is
        // captured into `last_surprise_*` so `stats()` can report it.
        // We don't assert a particular value (it's substrate-internal)
        // — just that it's no longer 0 after a real step.
        let b = fixture(32);
        let stats0 = b.stats();
        assert_eq!(stats0.last_surprise_mean, 0.0);
        assert_eq!(stats0.last_surprise_max, 0.0);

        let _ = b.embed("substrate test phrase");
        let stats1 = b.stats();
        // Hash backend is deterministic but produces non-zero values for
        // non-empty input → projection is non-zero → step produces
        // non-zero surprise.
        assert!(
            stats1.last_surprise_max.is_finite(),
            "max must be finite, got {}",
            stats1.last_surprise_max
        );
        assert!(stats1.step_count == 1);
    }

    #[test]
    fn project_truncates_and_normalizes() {
        // Phase 1 projection contract: truncate to D, unit-normalize.
        // Exposed via embed path; we verify properties by reading the
        // grid's primary_carrier z_state after a step (it gets the
        // projected vector verbatim).
        let b = fixture(8); // D=8 small for inspection
        let inner_vec = b.inner.embed("test");
        assert_eq!(inner_vec.len(), 384);
        let _ = b.embed("test");
        let grid = b.grid.lock().unwrap();
        let z = &grid.z_states[grid.primary_carrier];
        assert_eq!(z.len(), 8);
        // Unit norm within float error.
        let norm: f32 = z.iter().map(|x| x * x).sum::<f32>().sqrt();
        assert!((norm - 1.0).abs() < 1e-4, "expected unit norm, got {}", norm);
    }

    #[test]
    fn select_inner_kind_default_is_onnx() {
        // Phase 2.1: with no env hint, prefer ONNX (matches ab-store
        // default + has built-in hash fallback so we can't actually
        // crash from this choice).
        // Snapshot + restore to avoid racing with parallel tests.
        let prev = std::env::var(ABSTORE_BACKEND_ENV).ok();
        std::env::remove_var(ABSTORE_BACKEND_ENV);
        let kind = select_inner_kind();
        if let Some(v) = prev {
            std::env::set_var(ABSTORE_BACKEND_ENV, v);
        }
        assert_eq!(kind, "onnx");
    }

    #[test]
    fn select_inner_kind_respects_hash_env() {
        // Explicit `hash` keeps the phase-1 cheap path available for
        // CI / dev loops where ONNX model download is undesirable.
        let prev = std::env::var(ABSTORE_BACKEND_ENV).ok();
        std::env::set_var(ABSTORE_BACKEND_ENV, "hash");
        let kind = select_inner_kind();
        std::env::remove_var(ABSTORE_BACKEND_ENV);
        if let Some(v) = prev {
            std::env::set_var(ABSTORE_BACKEND_ENV, v);
        }
        assert_eq!(kind, "hash");
    }

    #[test]
    fn select_inner_kind_unknown_falls_through_to_onnx() {
        // Unknown values are unsafe to honor literally; defer to ab-store
        // pattern which warns + uses compile-time default. Substrate
        // mirrors that: unknown → onnx (which itself falls back to hash
        // if model load fails, so this is doubly safe).
        let prev = std::env::var(ABSTORE_BACKEND_ENV).ok();
        std::env::set_var(ABSTORE_BACKEND_ENV, "fictional-model");
        let kind = select_inner_kind();
        std::env::remove_var(ABSTORE_BACKEND_ENV);
        if let Some(v) = prev {
            std::env::set_var(ABSTORE_BACKEND_ENV, v);
        }
        assert_eq!(kind, "onnx");
    }

    #[test]
    fn build_inner_returns_correct_kind_per_env() {
        // End-to-end check on `build_inner_backend()`. We don't actually
        // call .embed() on the ONNX path (would trigger model download
        // in CI), just verify the chosen backend's name() identifies it.
        let prev = std::env::var(ABSTORE_BACKEND_ENV).ok();

        std::env::set_var(ABSTORE_BACKEND_ENV, "hash");
        let hash_b = build_inner_backend();
        assert_eq!(hash_b.name(), "fnv1a-hash-384");

        std::env::set_var(ABSTORE_BACKEND_ENV, "onnx");
        let onnx_b = build_inner_backend();
        assert_eq!(onnx_b.name(), "all-MiniLM-L6-v2");

        std::env::remove_var(ABSTORE_BACKEND_ENV);
        if let Some(v) = prev {
            std::env::set_var(ABSTORE_BACKEND_ENV, v);
        }
    }

    #[test]
    fn no_snapshot_path_means_no_writes() {
        // Phase 2.2 ablation: with `snapshot_path == None`, even at the
        // 20-event cadence boundary, nothing should write to disk.
        let b = fixture(64);
        assert!(b.snapshot_path().is_none());
        for _ in 0..25 {
            let _ = b.embed("event");
        }
        // No panic, no error — just no-op writes. step_count advances.
        assert_eq!(b.stats().step_count, 25);
    }

    #[test]
    fn cadence_step20_writes_hot_tier() {
        // Phase 2.2 integration: 20 embed() calls trigger one Hot snapshot.
        // We use a tempdir to avoid writing to ~/.local/share.
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("substrate.parquet");
        let b = fixture(64);
        b.set_snapshot_path(Some(path.clone()));

        // Vary input so surprise is non-degenerate.
        for i in 0..20 {
            let _ = b.embed(&format!("event-{i}"));
        }
        let rows = snapshot::read_all(&path).unwrap();
        assert_eq!(rows.len(), 1, "exactly one snapshot at step=20");
        assert_eq!(rows[0].step, 20);
        assert_eq!(rows[0].tier, SnapshotTier::Hot);
        assert!(rows[0].connection_logits.is_empty(),
            "Hot tier should NOT carry connection_logits");
        // Per-neuron in_strengths populated.
        assert_eq!(rows[0].in_strengths.len(), 32);
        // At least one last_perceived_key should be set (winner has fired).
        let any_set = rows[0].last_perceived_key.iter().any(|s| !s.is_empty());
        assert!(any_set, "at least one neuron should have last_perceived after 20 events");
    }

    #[test]
    fn cadence_step100_writes_long_tier_with_logits() {
        // Phase 2.2 integration: 100 embed() calls → long-tier snapshot
        // carrying the full N×(N-1) connection_logits flat. Note that
        // step=20/40/60/80 all also fire as Hot, so we expect 5 rows total.
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("substrate.parquet");
        let b = fixture(64);
        b.set_snapshot_path(Some(path.clone()));

        for i in 0..100 {
            let _ = b.embed(&format!("e{i}"));
        }
        let rows = snapshot::read_all(&path).unwrap();
        // Hot fires at 20/40/60/80, Long at 100 (Long subsumes Hot at
        // step=100 — we picked it over Hot in the dispatcher).
        assert_eq!(rows.len(), 5);
        let last = &rows[rows.len() - 1];
        assert_eq!(last.step, 100);
        assert_eq!(last.tier, SnapshotTier::Long);
        // N=32 → N*(N-1) = 992 entries.
        assert_eq!(last.connection_logits.len(), 32 * 31);
        // Trailing means should be populated (we just ran 100 events).
        assert!(last.trailing_surprise_mean_short.is_finite());
        assert!(last.trailing_surprise_mean_long.is_finite());
    }

    // ---- Phase 3 (A): neighbors_of tests ----

    #[test]
    fn neighbors_of_empty_key_returns_empty() {
        // v22 §3.5: empty key is meaningless; never returns spurious matches.
        let b = fixture(64);
        let _ = b.embed("seeded text");
        let out = b.neighbors_of("", 5);
        assert!(out.is_empty());
    }

    #[test]
    fn neighbors_of_zero_k_returns_empty() {
        // k==0 short-circuits before any work.
        let b = fixture(64);
        let _ = b.embed("alpha");
        let out = b.neighbors_of("alpha", 0);
        assert!(out.is_empty());
    }

    #[test]
    fn neighbors_of_no_perception_returns_empty() {
        // step_count==0 → no neuron has last_perceived set → []
        let b = fixture(64);
        assert_eq!(b.stats().step_count, 0);
        let out = b.neighbors_of("anything", 5);
        assert!(out.is_empty());
    }

    #[test]
    fn neighbors_of_unknown_key_returns_empty() {
        // Key that no neuron ever won on → [], even if substrate has
        // perception history.
        let b = fixture(64);
        let _ = b.embed("alpha");
        let _ = b.embed("beta");
        let out = b.neighbors_of("gamma-never-perceived", 5);
        assert!(out.is_empty());
    }

    #[test]
    fn neighbors_of_self_excluded() {
        // Queried key MUST NOT appear in its own neighbors output.
        let b = fixture(64);
        for i in 0..30 {
            let _ = b.embed(&format!("event-{i}"));
        }
        let _ = b.embed("query-key");
        let _ = b.embed("partner-1");
        let _ = b.embed("query-key");
        let _ = b.embed("partner-2");
        let out = b.neighbors_of("query-key", 10);
        assert!(
            out.iter().all(|(k, _)| k != "query-key"),
            "self key leaked into neighbors: {:?}",
            out
        );
    }

    #[test]
    fn neighbors_of_respects_k_cap() {
        // Output length must be ≤ k regardless of substrate state.
        let b = fixture(64);
        for i in 0..40 {
            let _ = b.embed(&format!("text-{i}"));
        }
        let _ = b.embed("anchor");
        let out = b.neighbors_of("anchor", 2);
        assert!(out.len() <= 2);
    }

    #[test]
    fn neighbors_of_sorted_descending() {
        // Scores must be monotonically non-increasing — ranking contract.
        let b = fixture(64);
        for i in 0..40 {
            let _ = b.embed(&format!("seed-{i}"));
        }
        let _ = b.embed("hub");
        let out = b.neighbors_of("hub", 10);
        let scores: Vec<f32> = out.iter().map(|(_, s)| *s).collect();
        for w in scores.windows(2) {
            assert!(
                w[0] >= w[1],
                "neighbors not sorted descending: {:?}",
                scores
            );
        }
    }

    #[test]
    fn neighbors_of_dedupes_keys_across_neurons() {
        // If `target` happens to win on multiple neurons (e.g. because
        // it was perceived many times with varying grid state), the
        // SAME other-key may appear in multiple neurons' last_perceived.
        // We must dedupe so it surfaces at most once.
        let b = fixture(64);
        // Variety so many neurons get populated.
        for i in 0..60 {
            let _ = b.embed(&format!("filler-{i}"));
        }
        // Perceive the same anchor twice to widen its winner footprint.
        let _ = b.embed("repeat-anchor");
        let _ = b.embed("repeat-anchor");
        let out = b.neighbors_of("repeat-anchor", 50);
        let mut seen: HashSet<&str> = HashSet::new();
        for (k_text, _) in &out {
            assert!(
                seen.insert(k_text.as_str()),
                "duplicate key in neighbors output: {}",
                k_text
            );
        }
    }

    #[test]
    fn neighbors_of_returns_format_valid_after_two_perceptions() {
        // Format contract: each entry has non-empty key and finite score.
        // Doesn't assert specific keys (substrate state is grid-dependent),
        // just that we get a well-formed Vec.
        let b = fixture(64);
        let _ = b.embed("alpha");
        let _ = b.embed("beta");
        let out = b.neighbors_of("alpha", 5);
        for (k_text, score) in &out {
            assert!(!k_text.is_empty(), "empty key leaked: {:?}", out);
            assert!(score.is_finite(), "non-finite score: {}", score);
            assert!(*score > 0.0, "non-positive score leaked: {}", score);
        }
    }

    // ---- Phase 3 (A): neighbors_from_snapshot tests ----

    #[test]
    fn neighbors_from_snapshot_hot_tier_returns_empty() {
        // Hot tier rows ship without connection_logits — any query
        // against them must return [] rather than reading 0 weights.
        let row = SnapshotRow {
            step: 20,
            cycle_ts: 1_000_000,
            tier: SnapshotTier::Hot,
            n_alive: 4,
            in_strengths: vec![0.1, 0.2, 0.3, 0.4],
            last_perceived_key: vec![
                "k0".into(),
                "k1".into(),
                "k2".into(),
                "k3".into(),
            ],
            last_perceived_ts: vec![1, 2, 3, 4],
            trailing_surprise_mean_short: 0.5,
            trailing_surprise_mean_long: 0.5,
            connection_logits: Vec::new(),
        };
        assert!(neighbors_from_snapshot(&row, "k0", 5).is_empty());
    }

    #[test]
    fn neighbors_from_snapshot_long_with_winners_returns_others() {
        // Synthesize a 4×3 off-diagonal connection_logits block where
        // neuron 0 (the "k0" winner) has its strongest |weight| toward
        // neuron 2. With last_perceived_key[2] = "k2", the query
        // neighbors_from_snapshot(row, "k0", 5) should rank "k2" first.
        // Off-diag flat layout for N=4: row i has 3 slots (cols !=i),
        // ordered ascending.
        let logits = vec![
            // row 0 (cols 1,2,3): weights 0.1, 0.9, 0.2
            0.1, 0.9, 0.2,
            // row 1 (cols 0,2,3): weights 0.0, 0.0, 0.0
            0.0, 0.0, 0.0,
            // row 2 (cols 0,1,3): weights 0.0, 0.0, 0.0
            0.0, 0.0, 0.0,
            // row 3 (cols 0,1,2): weights 0.0, 0.0, 0.0
            0.0, 0.0, 0.0,
        ];
        let row = SnapshotRow {
            step: 100,
            cycle_ts: 1_000_000,
            tier: SnapshotTier::Long,
            n_alive: 4,
            in_strengths: vec![0.1, 0.2, 0.3, 0.4],
            last_perceived_key: vec![
                "k0".into(),
                "k1".into(),
                "k2".into(),
                "k3".into(),
            ],
            last_perceived_ts: vec![1, 2, 3, 4],
            trailing_surprise_mean_short: 0.5,
            trailing_surprise_mean_long: 0.5,
            connection_logits: logits,
        };
        let out = neighbors_from_snapshot(&row, "k0", 5);
        assert!(!out.is_empty(), "expected non-empty output, got {:?}", out);
        // Strongest from row 0 is col 2 (0.9) → first entry must be "k2".
        assert_eq!(out[0].0, "k2");
        assert!(out[0].1 >= 0.85, "k2 score should be ~0.9, got {}", out[0].1);
        // "k0" (self) MUST NOT appear.
        assert!(out.iter().all(|(k, _)| k != "k0"));
    }

    #[test]
    fn neighbors_from_snapshot_unknown_key_returns_empty() {
        let row = SnapshotRow {
            step: 100,
            cycle_ts: 1_000_000,
            tier: SnapshotTier::Long,
            n_alive: 2,
            in_strengths: vec![0.5, 0.5],
            last_perceived_key: vec!["alpha".into(), "beta".into()],
            last_perceived_ts: vec![1, 2],
            trailing_surprise_mean_short: 0.0,
            trailing_surprise_mean_long: 0.0,
            // N=2 → off-diag = 2 entries.
            connection_logits: vec![0.5, 0.5],
        };
        assert!(neighbors_from_snapshot(&row, "gamma", 5).is_empty());
    }

    #[test]
    fn neighbors_from_snapshot_malformed_logits_returns_empty() {
        // Defensive: if logits length doesn't match n*(n-1), we
        // return [] rather than panic on out-of-bounds indexing.
        let row = SnapshotRow {
            step: 100,
            cycle_ts: 1_000_000,
            tier: SnapshotTier::Long,
            n_alive: 4,
            in_strengths: vec![0.1, 0.2, 0.3, 0.4],
            last_perceived_key: vec![
                "k0".into(),
                "k1".into(),
                "k2".into(),
                "k3".into(),
            ],
            last_perceived_ts: vec![1, 2, 3, 4],
            trailing_surprise_mean_short: 0.0,
            trailing_surprise_mean_long: 0.0,
            connection_logits: vec![0.1, 0.2, 0.3], // 3 != 4*3=12
        };
        assert!(neighbors_from_snapshot(&row, "k0", 5).is_empty());
    }

    #[test]
    #[should_panic(expected = "must not exceed inner backend dim")]
    fn d_greater_than_outer_dim_panics() {
        // Truncate projection requires D <= outer dim. Phase 1 enforces
        // this at construction — phase 2 (learned projection) will
        // accept arbitrary D.
        let _ = SeedBackend::wrap_with(
            Arc::new(HashBackend),
            SubstrateConfig {
                n: 16,
                d: 999,
                state_noise: 0.01,
                lr: 0.01,
            },
        );
    }
}
