//! Default-off synthetic-only bridge to the private Slice B store.
//!
//! This module owns deterministic test identity and HMAC derivation. It has no
//! environment/config reader and no production constructor.

use crate::episode_observation_slice_a::{
    derive_active_item_ref, EpisodeObservationEvent, EpisodeObservationKind,
    EpisodeObservationSourceKind, EpisodeRefKeyMaterial, EpisodeRefKeyProvider,
};
use crate::sqlite::SqliteStore;
use sha2::{Digest, Sha256};
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Arc,
};

static NEXT_ID: AtomicU64 = AtomicU64::new(1);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CurationBatchObservationError {
    Begin,
    Item,
    Close,
}

pub struct CurationBatchObservationHandle {
    store: Arc<SqliteStore>,
}
pub struct CurationBatchObservationAttempt {
    store: Arc<SqliteStore>,
    episode_id: String,
    run_id: String,
    next_event: u64,
    compromised: bool,
}

struct SyntheticProvider;
impl EpisodeRefKeyProvider for SyntheticProvider {
    fn active_key(&self) -> Option<EpisodeRefKeyMaterial<'_>> {
        Some(EpisodeRefKeyMaterial::new(
            "synthetic-0001",
            b"0123456789abcdef0123456789abcdef",
        ))
    }
    fn key_for_epoch(&self, epoch: &str) -> Option<EpisodeRefKeyMaterial<'_>> {
        (epoch == "synthetic-0001").then(|| {
            EpisodeRefKeyMaterial::new("synthetic-0001", b"0123456789abcdef0123456789abcdef")
        })
    }
}

fn digest(parts: &[&str]) -> String {
    let mut h = Sha256::new();
    for p in parts {
        h.update((p.len() as u64).to_be_bytes());
        h.update(p.as_bytes());
    }
    format!("{:x}", h.finalize())
}

impl CurationBatchObservationHandle {
    /// Available only with the explicit synthetic C2 feature; startup never calls it.
    pub fn synthetic_test_only(store: Arc<SqliteStore>) -> Self {
        Self { store }
    }
    pub async fn begin(
        &self,
    ) -> Result<CurationBatchObservationAttempt, CurationBatchObservationError> {
        let id = NEXT_ID.fetch_add(1, Ordering::Relaxed);
        let episode_id = format!("c2-synthetic-episode-{id}");
        let run_id = format!("c2-synthetic-run-{id}");
        let event_id = format!("c2-synthetic-event-{id}-0");
        let event = EpisodeObservationEvent {
            event_id: &event_id,
            episode_id: &episode_id,
            producer_run_id: &run_id,
            source_kind: EpisodeObservationSourceKind::CurationBatch,
            kind: EpisodeObservationKind::Open,
        };
        self.store
            .append_c2_synthetic_event(
                &event,
                &digest(&[&event_id, &episode_id, &run_id, "open"]),
                crate::now_secs(),
            )
            .await
            .map_err(|_| CurationBatchObservationError::Begin)?;
        Ok(CurationBatchObservationAttempt {
            store: self.store.clone(),
            episode_id,
            run_id,
            next_event: 1,
            compromised: false,
        })
    }
}

impl CurationBatchObservationAttempt {
    pub async fn observe_saved(
        &mut self,
        memory_key: &str,
        saved_ordinal: u32,
    ) -> Result<(), CurationBatchObservationError> {
        let item_ref = match derive_active_item_ref(Some(&SyntheticProvider), memory_key) {
            Ok(item_ref) => item_ref,
            Err(_) => {
                self.compromised = true;
                return Err(CurationBatchObservationError::Item);
            }
        };
        let event_id = format!("{}-{}", self.run_id, self.next_event);
        self.next_event += 1;
        let event = EpisodeObservationEvent {
            event_id: &event_id,
            episode_id: &self.episode_id,
            producer_run_id: &self.run_id,
            source_kind: EpisodeObservationSourceKind::CurationBatch,
            kind: EpisodeObservationKind::Item {
                item_ref: &item_ref,
                episode_position: saved_ordinal,
            },
        };
        self.store
            .append_c2_synthetic_event(
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
    pub async fn finish(self, item_count: u32) -> Result<(), CurationBatchObservationError> {
        if self.compromised {
            return Err(CurationBatchObservationError::Close);
        }
        let event_id = format!("{}-{}", self.run_id, self.next_event);
        let event = EpisodeObservationEvent {
            event_id: &event_id,
            episode_id: &self.episode_id,
            producer_run_id: &self.run_id,
            source_kind: EpisodeObservationSourceKind::CurationBatch,
            kind: EpisodeObservationKind::Close { item_count },
        };
        self.store
            .append_c2_synthetic_event(
                &event,
                &digest(&[&event_id, &self.episode_id, &self.run_id, "close"]),
                crate::now_secs(),
            )
            .await
            .map_err(|_| CurationBatchObservationError::Close)
    }

    #[cfg(test)]
    pub(crate) fn test_episode_id(&self) -> &str {
        &self.episode_id
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn synthetic_handle_two_items_finalize_on_disposable_database() {
        let dir = tempfile::tempdir().expect("tempdir");
        let store = Arc::new(
            SqliteStore::open(&dir.path().join("state.db"))
                .await
                .expect("store"),
        );
        let handle = CurationBatchObservationHandle::synthetic_test_only(store.clone());
        let mut attempt = handle.begin().await.expect("open");
        attempt
            .observe_saved("memory-a", 0)
            .await
            .expect("first item");
        attempt
            .observe_saved("memory-b", 1)
            .await
            .expect("second item");
        let episode_id = attempt.test_episode_id().to_owned();
        attempt.finish(2).await.expect("close");
        assert!(store
            .c2_synthetic_is_finalized_for_test(&episode_id)
            .await
            .expect("projection"));
    }

    #[tokio::test]
    async fn failed_item_latches_and_cannot_close_a_finalized_trace() {
        let dir = tempfile::tempdir().expect("tempdir");
        let store = Arc::new(
            SqliteStore::open(&dir.path().join("state.db"))
                .await
                .expect("store"),
        );
        let handle = CurationBatchObservationHandle::synthetic_test_only(store.clone());
        let mut attempt = handle.begin().await.expect("open");
        let episode_id = attempt.test_episode_id().to_owned();
        assert_eq!(
            attempt.observe_saved("", 0).await,
            Err(CurationBatchObservationError::Item)
        );
        assert_eq!(
            attempt.finish(0).await,
            Err(CurationBatchObservationError::Close)
        );
        assert!(!store
            .c2_synthetic_is_finalized_for_test(&episode_id)
            .await
            .expect("projection"));
        assert_eq!(
            store
                .c2_synthetic_event_count_for_test()
                .await
                .expect("event count"),
            1
        );
    }

    #[tokio::test]
    async fn duplicate_ordinal_cannot_form_a_finalized_trace() {
        let dir = tempfile::tempdir().expect("tempdir");
        let store = Arc::new(
            SqliteStore::open(&dir.path().join("state.db"))
                .await
                .expect("store"),
        );
        let handle = CurationBatchObservationHandle::synthetic_test_only(store.clone());
        let mut attempt = handle.begin().await.expect("open");
        let episode_id = attempt.test_episode_id().to_owned();
        attempt
            .observe_saved("memory-a", 0)
            .await
            .expect("first item");
        attempt
            .observe_saved("memory-b", 0)
            .await
            .expect("duplicate ordinal");
        attempt.finish(2).await.expect("close");
        assert!(!store
            .c2_synthetic_is_finalized_for_test(&episode_id)
            .await
            .expect("projection"));
    }
}
