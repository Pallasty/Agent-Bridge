//! Default-off explicit-runtime C2C store handle. No startup code calls this.

use crate::episode_observation_c2_keychain_macos::derive_active_item_ref_from_keychain;
use crate::episode_observation_slice_a::{
    EpisodeObservationEvent, EpisodeObservationKind, EpisodeObservationSourceKind,
};
use crate::sqlite::SqliteStore;
use sha2::{Digest, Sha256};
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Arc,
};

static NEXT_ID: AtomicU64 = AtomicU64::new(1);
const READINESS_MEMORY_KEY: &str = "c2c-keychain-readiness-v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CurationBatchObservationError {
    Begin,
    Item,
    Close,
    Unavailable,
}

trait ItemRefDeriver: Send + Sync {
    fn derive(&self, memory_key: &str) -> Result<String, ()>;
}
struct MacOsDeriver;
impl ItemRefDeriver for MacOsDeriver {
    fn derive(&self, key: &str) -> Result<String, ()> {
        derive_active_item_ref_from_keychain(key).map_err(|_| ())
    }
}

pub struct ExplicitKeychainMacosHandle {
    store: Arc<SqliteStore>,
    deriver: Arc<dyn ItemRefDeriver>,
}
pub struct ExplicitKeychainMacosAttempt {
    store: Arc<SqliteStore>,
    deriver: Arc<dyn ItemRefDeriver>,
    episode_id: String,
    run_id: String,
    next_event: u64,
    compromised: bool,
}

fn digest(parts: &[&str]) -> String {
    let mut h = Sha256::new();
    for p in parts {
        h.update((p.len() as u64).to_be_bytes());
        h.update(p.as_bytes());
    }
    format!("{:x}", h.finalize())
}

impl ExplicitKeychainMacosHandle {
    pub fn try_new(store: Arc<SqliteStore>) -> Result<Self, CurationBatchObservationError> {
        Self::from_deriver(store, Arc::new(MacOsDeriver))
    }
    fn from_deriver(
        store: Arc<SqliteStore>,
        deriver: Arc<dyn ItemRefDeriver>,
    ) -> Result<Self, CurationBatchObservationError> {
        deriver
            .derive(READINESS_MEMORY_KEY)
            .map_err(|_| CurationBatchObservationError::Unavailable)?;
        Ok(Self { store, deriver })
    }
    pub async fn begin(
        &self,
    ) -> Result<ExplicitKeychainMacosAttempt, CurationBatchObservationError> {
        let id = NEXT_ID.fetch_add(1, Ordering::Relaxed);
        let episode_id = format!("c2c-keychain-episode-{id}");
        let run_id = format!("c2c-keychain-run-{id}");
        let event_id = format!("{run_id}-0");
        let event = EpisodeObservationEvent {
            event_id: &event_id,
            episode_id: &episode_id,
            producer_run_id: &run_id,
            source_kind: EpisodeObservationSourceKind::CurationBatch,
            kind: EpisodeObservationKind::Open,
        };
        self.store
            .append_c2_keychain_macos_runtime_event(
                &event,
                &digest(&[&event_id, &episode_id, &run_id, "open"]),
                crate::now_secs(),
            )
            .await
            .map_err(|_| CurationBatchObservationError::Begin)?;
        Ok(ExplicitKeychainMacosAttempt {
            store: self.store.clone(),
            deriver: self.deriver.clone(),
            episode_id,
            run_id,
            next_event: 1,
            compromised: false,
        })
    }
}
impl ExplicitKeychainMacosAttempt {
    pub async fn observe_saved(
        &mut self,
        memory_key: &str,
        ordinal: u32,
    ) -> Result<(), CurationBatchObservationError> {
        let item_ref = self.deriver.derive(memory_key).map_err(|_| {
            self.compromised = true;
            CurationBatchObservationError::Item
        })?;
        let event_id = format!("{}-{}", self.run_id, self.next_event);
        self.next_event += 1;
        let event = EpisodeObservationEvent {
            event_id: &event_id,
            episode_id: &self.episode_id,
            producer_run_id: &self.run_id,
            source_kind: EpisodeObservationSourceKind::CurationBatch,
            kind: EpisodeObservationKind::Item {
                item_ref: &item_ref,
                episode_position: ordinal,
            },
        };
        self.store
            .append_c2_keychain_macos_runtime_event(
                &event,
                &digest(&[&event_id, &self.episode_id, &self.run_id, &item_ref]),
                crate::now_secs(),
            )
            .await
            .map_err(|_| {
                self.compromised = true;
                CurationBatchObservationError::Item
            })
    }
    pub async fn finish(self, count: u32) -> Result<(), CurationBatchObservationError> {
        if self.compromised {
            return Err(CurationBatchObservationError::Close);
        };
        let event_id = format!("{}-{}", self.run_id, self.next_event);
        let event = EpisodeObservationEvent {
            event_id: &event_id,
            episode_id: &self.episode_id,
            producer_run_id: &self.run_id,
            source_kind: EpisodeObservationSourceKind::CurationBatch,
            kind: EpisodeObservationKind::Close { item_count: count },
        };
        self.store
            .append_c2_keychain_macos_runtime_event(
                &event,
                &digest(&[&event_id, &self.episode_id, &self.run_id, "close"]),
                crate::now_secs(),
            )
            .await
            .map_err(|_| CurationBatchObservationError::Close)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    struct Failing;
    impl ItemRefDeriver for Failing {
        fn derive(&self, _: &str) -> Result<String, ()> {
            Err(())
        }
    }
    struct Fixed;
    impl ItemRefDeriver for Fixed {
        fn derive(&self, _: &str) -> Result<String, ()> {
            Ok("epr_v1_test_x".into())
        }
    }

    #[tokio::test]
    async fn readiness_failure_prevents_any_open_attempt() {
        let dir = tempfile::tempdir().expect("tempdir");
        let store = Arc::new(
            SqliteStore::open(&dir.path().join("state.db"))
                .await
                .expect("store"),
        );
        assert!(matches!(
            ExplicitKeychainMacosHandle::from_deriver(store, Arc::new(Failing)),
            Err(CurationBatchObservationError::Unavailable)
        ));
    }
    #[tokio::test]
    async fn fake_ready_handle_can_begin_item_and_close_without_keychain() {
        let dir = tempfile::tempdir().expect("tempdir");
        let store = Arc::new(
            SqliteStore::open(&dir.path().join("state.db"))
                .await
                .expect("store"),
        );
        let handle =
            ExplicitKeychainMacosHandle::from_deriver(store, Arc::new(Fixed)).expect("ready");
        let mut attempt = handle.begin().await.expect("open");
        attempt.observe_saved("memory-a", 0).await.expect("item");
        attempt.finish(1).await.expect("close");
    }
}
