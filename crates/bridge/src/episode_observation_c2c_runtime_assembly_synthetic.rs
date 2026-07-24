//! Default-off structural assembly gate for synthetic C2C tests.
//!
//! It owns neither a provider nor runtime configuration. Normal startup never
//! calls this module; a future C2C-B packet must separately authorize that.

use crate::episode_observation_curation_batch::CurationBatchObservationCapability;
use std::sync::Arc;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum EpisodeObservationRuntimeAuthorization {
    Disabled,
    ExplicitSyntheticLab,
}

/// Returns an opaque C1 capability only for the explicit synthetic lab gate.
///
/// The capability is assembled elsewhere and passed through unchanged. This
/// function performs no I/O and cannot construct a custody provider.
pub(crate) fn assemble_curation_batch_observer(
    authorization: EpisodeObservationRuntimeAuthorization,
    capability: Option<Arc<dyn CurationBatchObservationCapability>>,
) -> Option<Arc<dyn CurationBatchObservationCapability>> {
    match (authorization, capability) {
        (EpisodeObservationRuntimeAuthorization::ExplicitSyntheticLab, Some(capability)) => {
            Some(capability)
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::episode_observation_curation_batch::{
        CurationBatchObservationAttempt, CurationBatchObservationCompletion,
        CurationBatchObservationError, CurationBatchObservationRun,
    };
    use crate::episode_observation_curation_batch_c2_synthetic::synthetic_store_observer;
    use ab_store::episode_observation_c2_synthetic::CurationBatchObservationHandle;
    use ab_store::SqliteStore;
    use async_trait::async_trait;
    use std::sync::{Arc, Mutex};

    #[derive(Default)]
    struct FakeState {
        calls: Vec<&'static str>,
        fail_begin: bool,
        fail_item: bool,
        fail_close: bool,
    }

    struct FakeCapability(Arc<Mutex<FakeState>>);
    struct FakeAttempt(Arc<Mutex<FakeState>>);

    #[async_trait]
    impl CurationBatchObservationCapability for FakeCapability {
        async fn begin(
            &self,
        ) -> Result<Box<dyn CurationBatchObservationAttempt>, CurationBatchObservationError>
        {
            let mut state = self.0.lock().expect("fake state");
            if state.fail_begin {
                return Err(CurationBatchObservationError::Begin);
            }
            state.calls.push("open");
            Ok(Box::new(FakeAttempt(self.0.clone())))
        }
    }

    #[async_trait]
    impl CurationBatchObservationAttempt for FakeAttempt {
        async fn observe_saved(
            &mut self,
            _memory_key: &str,
            _saved_ordinal: u32,
        ) -> Result<(), CurationBatchObservationError> {
            let mut state = self.0.lock().expect("fake state");
            if state.fail_item {
                return Err(CurationBatchObservationError::Item);
            }
            state.calls.push("item");
            Ok(())
        }

        async fn finish(
            self: Box<Self>,
            _item_count: u32,
        ) -> Result<(), CurationBatchObservationError> {
            let mut state = self.0.lock().expect("fake state");
            if state.fail_close {
                return Err(CurationBatchObservationError::Close);
            }
            state.calls.push("close");
            Ok(())
        }
    }

    fn fake(state: Arc<Mutex<FakeState>>) -> Arc<dyn CurationBatchObservationCapability> {
        Arc::new(FakeCapability(state))
    }

    #[test]
    fn all_incomplete_conjunctions_assemble_nothing() {
        let state = Arc::new(Mutex::new(FakeState::default()));
        let capability = fake(state);
        assert!(assemble_curation_batch_observer(
            EpisodeObservationRuntimeAuthorization::Disabled,
            Some(capability.clone())
        )
        .is_none());
        assert!(assemble_curation_batch_observer(
            EpisodeObservationRuntimeAuthorization::ExplicitSyntheticLab,
            None
        )
        .is_none());
        assert!(assemble_curation_batch_observer(
            EpisodeObservationRuntimeAuthorization::Disabled,
            None
        )
        .is_none());
    }

    #[tokio::test]
    async fn explicit_synthetic_assembly_finalizes_one_bounded_episode() {
        let dir = tempfile::tempdir().expect("tempdir");
        let store = Arc::new(
            SqliteStore::open(&dir.path().join("state.db"))
                .await
                .expect("disposable store"),
        );
        let handle = Arc::new(CurationBatchObservationHandle::synthetic_test_only(store));
        let capability = assemble_curation_batch_observer(
            EpisodeObservationRuntimeAuthorization::ExplicitSyntheticLab,
            Some(synthetic_store_observer(handle)),
        );
        let mut run = CurationBatchObservationRun::begin(capability, true).await;
        run.observe_memory_saved("memory-a").await;
        assert_eq!(
            run.finish().await,
            CurationBatchObservationCompletion::Finalized
        );
    }

    #[tokio::test]
    async fn disabled_or_missing_operands_emit_no_episode() {
        let state = Arc::new(Mutex::new(FakeState::default()));
        for capability in [
            assemble_curation_batch_observer(
                EpisodeObservationRuntimeAuthorization::Disabled,
                Some(fake(state.clone())),
            ),
            assemble_curation_batch_observer(
                EpisodeObservationRuntimeAuthorization::ExplicitSyntheticLab,
                None,
            ),
        ] {
            let run = CurationBatchObservationRun::begin(capability, true).await;
            assert_eq!(
                run.finish().await,
                CurationBatchObservationCompletion::NoEpisode
            );
        }
        assert!(state.lock().expect("fake state").calls.is_empty());
    }

    #[tokio::test]
    async fn sidecar_failures_remain_fail_closed_without_propagating() {
        for (state, expected) in [
            (
                Arc::new(Mutex::new(FakeState {
                    fail_begin: true,
                    ..FakeState::default()
                })),
                CurationBatchObservationCompletion::NoEpisode,
            ),
            (
                Arc::new(Mutex::new(FakeState {
                    fail_item: true,
                    ..FakeState::default()
                })),
                CurationBatchObservationCompletion::Incomplete,
            ),
            (
                Arc::new(Mutex::new(FakeState {
                    fail_close: true,
                    ..FakeState::default()
                })),
                CurationBatchObservationCompletion::Incomplete,
            ),
        ] {
            let capability = assemble_curation_batch_observer(
                EpisodeObservationRuntimeAuthorization::ExplicitSyntheticLab,
                Some(fake(state.clone())),
            );
            let mut run = CurationBatchObservationRun::begin(capability, true).await;
            run.observe_memory_saved("memory-a").await;
            assert_eq!(run.finish().await, expected);
        }
    }
}
