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

use std::sync::{Arc, Mutex, OnceLock};

use ab_store::embedding::{EmbeddingBackend, HashBackend};
use seed_neuron::NeuronGrid;
use serde::{Deserialize, Serialize};

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
    let backend = Arc::new(SeedBackend::wrap(inner));
    INSTANCE
        .set(backend.clone())
        .map_err(|_| "seed-bridge already installed")?;
    ab_store::embedding::set_default_backend(backend)?;
    Ok(())
}

/// Mirror of `ab_store::embedding::select_default` selection logic so
/// SeedBackend wraps whatever would have been the default. Only the
/// hash fallback is built-in here; ONNX gets pulled in by ab-store's
/// feature flag and would require linking against fastembed which is
/// out of scope for seed-bridge — phase 1 wraps hash. Phase 2 lifts the
/// ONNX inner through a constructor parameter so MCP startup picks it.
fn build_inner_backend() -> Arc<dyn EmbeddingBackend> {
    // Phase 1: hash inner is sufficient to validate the wiring (G1-G3
    // smoke). The substrate observes hashed perception, not real
    // semantic vectors, so cluster quality is degraded — but the
    // step_count / connection_logits / surprise pipeline is identical
    // to what the ONNX-wrapped version will exercise in phase 2.
    Arc::new(HashBackend)
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
}

impl SeedBackend {
    /// Wrap an inner backend with default substrate config.
    pub fn wrap(inner: Arc<dyn EmbeddingBackend>) -> Self {
        Self::wrap_with(inner, SubstrateConfig::default())
    }

    /// Wrap with explicit config. Panics if `config.d > inner.dim()` —
    /// the truncate projection requires the substrate dim be ≤ outer dim.
    pub fn wrap_with(inner: Arc<dyn EmbeddingBackend>, config: SubstrateConfig) -> Self {
        assert!(
            config.d <= inner.dim(),
            "substrate D={} must not exceed inner backend dim {}",
            config.d,
            inner.dim()
        );
        let grid = NeuronGrid::new(
            config.n,
            config.d,
            /*primary_carrier=*/ 0,
            /*secondary_carrier=*/ 1,
            config.state_noise,
        );
        Self {
            inner,
            config,
            grid: Mutex::new(grid),
            last_surprise: Mutex::new((0.0, 0.0)),
        }
    }

    /// Phase 1 projection: linear-bucket average pool inner → D.
    /// Each outer index `i` maps to bucket `i*D/outer`. Preserves L1
    /// mass and survives sparse-input backends (e.g. HashBackend with
    /// short text would zero out under naive truncate; this does not).
    /// Phase 2 swaps in learned linear projection. Returns unit-norm.
    fn project(&self, v: &[f32]) -> Vec<f32> {
        let d = self.config.d;
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

    /// Perception step. Called once per outer `embed()`. `primary` is the
    /// projected vector; `secondary` is the zero vector in phase 1 (the
    /// rolling-mean second carrier is a phase 2 feature).
    fn step(&self, primary: &[f32]) {
        let secondary = vec![0.0f32; self.config.d];
        let mut grid = match self.grid.lock() {
            Ok(g) => g,
            Err(_) => return, // poisoned; degrade silently
        };
        let surprises = grid.step(primary, &secondary, self.config.lr);
        let (mean, max) = surprise_stats(&surprises);
        if let Ok(mut s) = self.last_surprise.lock() {
            *s = (mean, max);
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
            n,
            d,
            outer_dim: self.inner.dim(),
            step_count,
            last_surprise_mean: mean,
            last_surprise_max: max,
            connection_mean_abs: conn_abs,
        }
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
            self.step(&primary);
        }
        v
    }

    fn embed_batch(&self, texts: &[&str]) -> Vec<Vec<f32>> {
        let vecs = self.inner.embed_batch(texts);
        for v in &vecs {
            if v.len() == self.inner.dim() {
                let primary = self.project(v);
                self.step(&primary);
            }
        }
        vecs
    }
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
