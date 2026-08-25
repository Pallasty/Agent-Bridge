//! Daemon-owned coactivation decay supervisor.

use ab_store::StateStore;
use std::future::Future;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const DEFAULT_TICK_SECS: u64 = 30;
const MIN_TICK_SECS: u64 = 5;
const MAX_TICK_SECS: u64 = 300;
const DEFAULT_TAU_SECS: i64 = 7 * 86_400;
const MIN_TAU_SECS: i64 = 3_600;
const MAX_TAU_SECS: i64 = 30 * 86_400;
const MAX_ITERATIONS: u32 = 10;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CoactivationTickConfig {
    pub enabled: bool,
    pub tick_secs: u64,
    pub tau_secs: i64,
}

impl CoactivationTickConfig {
    pub fn from_env() -> Self {
        Self::from_lookup(|key| std::env::var(key).ok())
    }

    fn from_lookup<F>(mut lookup: F) -> Self
    where
        F: FnMut(&str) -> Option<String>,
    {
        let disabled = lookup("AGENT_BRIDGE_DISABLE_SUBSTRATE_TICK")
            .map(|value| value == "1" || value.eq_ignore_ascii_case("true"))
            .unwrap_or(false);
        let tick_secs = lookup("AGENT_BRIDGE_TICK_SECS")
            .and_then(|value| value.parse().ok())
            .unwrap_or(DEFAULT_TICK_SECS)
            .clamp(MIN_TICK_SECS, MAX_TICK_SECS);
        let tau_secs = lookup("AGENT_BRIDGE_TAU_SECS")
            .and_then(|value| value.parse().ok())
            .unwrap_or(DEFAULT_TAU_SECS)
            .clamp(MIN_TAU_SECS, MAX_TAU_SECS);

        Self {
            enabled: !disabled,
            tick_secs,
            tau_secs,
        }
    }
}

pub fn spawn(
    store: Arc<dyn StateStore>,
    config: CoactivationTickConfig,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(run_loop(Duration::from_secs(config.tick_secs), move || {
        let store = Arc::clone(&store);
        async move {
            let now = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|duration| duration.as_secs() as i64)
                .unwrap_or(0);
            match store
                .decay_coactivation_once(config.tau_secs, now, MAX_ITERATIONS)
                .await
            {
                Ok(stats) if stats.iterations > 0 => {
                    tracing::debug!(
                        swept = stats.swept,
                        pruned = stats.pruned,
                        iters = stats.iterations,
                        "substrate-tick: ran"
                    );
                }
                Ok(_) => {}
                Err(error) => {
                    tracing::warn!(error = %error, "substrate-tick: decay error");
                }
            }
        }
    }))
}

async fn run_loop<F, Fut>(period: Duration, mut run_pass: F)
where
    F: FnMut() -> Fut,
    Fut: Future<Output = ()>,
{
    let mut interval = tokio::time::interval(period);
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
    // Tokio intervals fire once at t=0. Skipping that fire preserves the
    // daemon contract that decay never runs immediately after startup.
    interval.tick().await;
    loop {
        interval.tick().await;
        run_pass().await;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::sync::atomic::{AtomicUsize, Ordering};

    fn config(values: &[(&str, &str)]) -> CoactivationTickConfig {
        let values = values
            .iter()
            .map(|(key, value)| ((*key).to_string(), (*value).to_string()))
            .collect::<HashMap<_, _>>();
        CoactivationTickConfig::from_lookup(|key| values.get(key).cloned())
    }

    #[test]
    fn defaults_match_the_existing_daemon_contract() {
        assert_eq!(
            config(&[]),
            CoactivationTickConfig {
                enabled: true,
                tick_secs: 30,
                tau_secs: 7 * 86_400,
            }
        );
    }

    #[test]
    fn disable_values_preserve_exact_legacy_semantics() {
        assert!(!config(&[("AGENT_BRIDGE_DISABLE_SUBSTRATE_TICK", "1")]).enabled);
        assert!(!config(&[("AGENT_BRIDGE_DISABLE_SUBSTRATE_TICK", "TRUE")]).enabled);
        assert!(config(&[("AGENT_BRIDGE_DISABLE_SUBSTRATE_TICK", "yes")]).enabled);
        assert!(config(&[("AGENT_BRIDGE_DISABLE_SUBSTRATE_TICK", "0")]).enabled);
    }

    #[test]
    fn cadence_and_tau_are_clamped() {
        let low = config(&[
            ("AGENT_BRIDGE_TICK_SECS", "1"),
            ("AGENT_BRIDGE_TAU_SECS", "20"),
        ]);
        assert_eq!(low.tick_secs, 5);
        assert_eq!(low.tau_secs, 3_600);

        let high = config(&[
            ("AGENT_BRIDGE_TICK_SECS", "9999"),
            ("AGENT_BRIDGE_TAU_SECS", "99999999"),
        ]);
        assert_eq!(high.tick_secs, 300);
        assert_eq!(high.tau_secs, 30 * 86_400);
    }

    #[test]
    fn invalid_values_fall_back_to_defaults() {
        let value = config(&[
            ("AGENT_BRIDGE_TICK_SECS", "invalid"),
            ("AGENT_BRIDGE_TAU_SECS", "invalid"),
        ]);
        assert_eq!(value.tick_secs, 30);
        assert_eq!(value.tau_secs, 7 * 86_400);
    }

    #[tokio::test]
    async fn first_pass_waits_for_one_full_period() {
        let calls = Arc::new(AtomicUsize::new(0));
        let observed = Arc::clone(&calls);
        let task = tokio::spawn(run_loop(Duration::from_millis(80), move || {
            let observed = Arc::clone(&observed);
            async move {
                observed.fetch_add(1, Ordering::SeqCst);
            }
        }));

        tokio::time::sleep(Duration::from_millis(20)).await;
        assert_eq!(calls.load(Ordering::SeqCst), 0);

        tokio::time::timeout(Duration::from_millis(300), async {
            while calls.load(Ordering::SeqCst) == 0 {
                tokio::task::yield_now().await;
            }
        })
        .await
        .expect("first pass should run after one full period");
        assert_eq!(calls.load(Ordering::SeqCst), 1);
        task.abort();
    }
}
