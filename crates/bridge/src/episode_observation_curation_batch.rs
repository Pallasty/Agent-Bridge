//! Default-off orchestration for one `session_curate:curation_batch` attempt.
//!
//! This module deliberately owns no store adapter, key provider, runtime
//! configuration, event serializer, or production capability implementation.

use async_trait::async_trait;
use std::sync::Arc;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
// C1 deliberately ships no production capability implementation; variants are
// constructed only by synthetic test capabilities until C2 is separately open.
#[allow(dead_code)]
pub(crate) enum CurationBatchObservationError {
    Begin,
    Item,
    Close,
}

#[async_trait]
pub(crate) trait CurationBatchObservationAttempt: Send {
    /// Observe a memory key only after its core memory save committed.
    /// Implementations must derive a pseudonymous item reference immediately
    /// and must not retain or log the raw key.
    async fn observe_saved(
        &mut self,
        memory_key: &str,
        saved_ordinal: u32,
    ) -> Result<(), CurationBatchObservationError>;

    async fn finish(self: Box<Self>, item_count: u32) -> Result<(), CurationBatchObservationError>;
}

#[async_trait]
pub(crate) trait CurationBatchObservationCapability: Send + Sync {
    /// Begin one non-empty curation batch. A successful return means the open
    /// event was accepted and the returned attempt exclusively owns its IDs,
    /// pseudonym derivation, payload hashing, key provider, and sink.
    async fn begin(
        &self,
    ) -> Result<Box<dyn CurationBatchObservationAttempt>, CurationBatchObservationError>;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum CurationBatchObservationCompletion {
    NoEpisode,
    Incomplete,
    Finalized,
}

/// Fail-open for core curation and fail-closed for the observation sidecar.
/// The first observation error drops the attempt and suppresses every later
/// item/close call. The caller intentionally receives no error detail that
/// could be confused with a memory-save failure.
pub(crate) struct CurationBatchObservationRun {
    attempt: Option<Box<dyn CurationBatchObservationAttempt>>,
    opened: bool,
    compromised: bool,
    saved_count: u32,
}

impl CurationBatchObservationRun {
    pub(crate) async fn begin(
        capability: Option<Arc<dyn CurationBatchObservationCapability>>,
        has_candidates: bool,
    ) -> Self {
        if !has_candidates {
            return Self::disabled();
        }
        let Some(capability) = capability else {
            return Self::disabled();
        };
        match capability.begin().await {
            Ok(attempt) => Self {
                attempt: Some(attempt),
                opened: true,
                compromised: false,
                saved_count: 0,
            },
            Err(error) => {
                tracing::debug!(?error, "curation-batch observation begin failed");
                Self::disabled()
            }
        }
    }

    fn disabled() -> Self {
        Self {
            attempt: None,
            opened: false,
            compromised: false,
            saved_count: 0,
        }
    }

    pub(crate) async fn observe_memory_saved(&mut self, memory_key: &str) {
        let saved_ordinal = self.saved_count;
        self.saved_count = self
            .saved_count
            .checked_add(1)
            .expect("session_curate limits candidates to at most 50");
        let Some(attempt) = self.attempt.as_mut() else {
            return;
        };
        if let Err(error) = attempt.observe_saved(memory_key, saved_ordinal).await {
            tracing::debug!(?error, "curation-batch observation item failed");
            self.compromised = true;
            self.attempt = None;
        }
    }

    pub(crate) async fn finish(mut self) -> CurationBatchObservationCompletion {
        if !self.opened {
            return CurationBatchObservationCompletion::NoEpisode;
        }
        if self.compromised || self.saved_count == 0 {
            return CurationBatchObservationCompletion::Incomplete;
        }
        let Some(attempt) = self.attempt.take() else {
            return CurationBatchObservationCompletion::Incomplete;
        };
        match attempt.finish(self.saved_count).await {
            Ok(()) => CurationBatchObservationCompletion::Finalized,
            Err(error) => {
                tracing::debug!(?error, "curation-batch observation close failed");
                CurationBatchObservationCompletion::Incomplete
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    #[derive(Default)]
    struct FakeState {
        calls: Vec<String>,
        fail_begin: bool,
        fail_item: Option<u32>,
        fail_close: bool,
    }

    struct FakeCapability {
        state: Arc<Mutex<FakeState>>,
    }

    struct FakeAttempt {
        state: Arc<Mutex<FakeState>>,
    }

    #[async_trait]
    impl CurationBatchObservationCapability for FakeCapability {
        async fn begin(
            &self,
        ) -> Result<Box<dyn CurationBatchObservationAttempt>, CurationBatchObservationError>
        {
            let mut state = self.state.lock().expect("fake state");
            if state.fail_begin {
                return Err(CurationBatchObservationError::Begin);
            }
            state.calls.push("open".to_string());
            drop(state);
            Ok(Box::new(FakeAttempt {
                state: self.state.clone(),
            }))
        }
    }

    #[async_trait]
    impl CurationBatchObservationAttempt for FakeAttempt {
        async fn observe_saved(
            &mut self,
            _memory_key: &str,
            saved_ordinal: u32,
        ) -> Result<(), CurationBatchObservationError> {
            let mut state = self.state.lock().expect("fake state");
            if state.fail_item == Some(saved_ordinal) {
                return Err(CurationBatchObservationError::Item);
            }
            state.calls.push(format!("item:{saved_ordinal}"));
            Ok(())
        }

        async fn finish(
            self: Box<Self>,
            item_count: u32,
        ) -> Result<(), CurationBatchObservationError> {
            let mut state = self.state.lock().expect("fake state");
            if state.fail_close {
                return Err(CurationBatchObservationError::Close);
            }
            state.calls.push(format!("close:{item_count}"));
            Ok(())
        }
    }

    fn fake(state: Arc<Mutex<FakeState>>) -> Arc<dyn CurationBatchObservationCapability> {
        Arc::new(FakeCapability { state })
    }

    fn calls(state: &Arc<Mutex<FakeState>>) -> Vec<String> {
        state.lock().expect("fake state").calls.clone()
    }

    fn strings(values: &[&str]) -> Vec<String> {
        values.iter().map(|value| (*value).to_string()).collect()
    }

    #[tokio::test]
    async fn absent_capability_and_empty_batch_emit_nothing() {
        let no_capability = CurationBatchObservationRun::begin(None, true).await;
        assert_eq!(
            no_capability.finish().await,
            CurationBatchObservationCompletion::NoEpisode
        );

        let state = Arc::new(Mutex::new(FakeState::default()));
        let empty = CurationBatchObservationRun::begin(Some(fake(state.clone())), false).await;
        assert_eq!(
            empty.finish().await,
            CurationBatchObservationCompletion::NoEpisode
        );
        assert!(calls(&state).is_empty());
    }

    #[tokio::test]
    async fn saved_ordinals_are_contiguous_and_close_matches() {
        let state = Arc::new(Mutex::new(FakeState::default()));
        let mut run = CurationBatchObservationRun::begin(Some(fake(state.clone())), true).await;
        run.observe_memory_saved("memory-a").await;
        run.observe_memory_saved("memory-b").await;
        assert_eq!(
            run.finish().await,
            CurationBatchObservationCompletion::Finalized
        );
        assert_eq!(
            calls(&state),
            strings(&["open", "item:0", "item:1", "close:2"])
        );
    }

    #[tokio::test]
    async fn first_item_failure_latches_and_suppresses_close() {
        let state = Arc::new(Mutex::new(FakeState {
            fail_item: Some(0),
            ..FakeState::default()
        }));
        let mut run = CurationBatchObservationRun::begin(Some(fake(state.clone())), true).await;
        run.observe_memory_saved("memory-a").await;
        run.observe_memory_saved("memory-b").await;
        assert_eq!(
            run.finish().await,
            CurationBatchObservationCompletion::Incomplete
        );
        assert_eq!(calls(&state), strings(&["open"]));
    }

    #[tokio::test]
    async fn begin_close_and_zero_save_fail_closed_without_core_error() {
        let begin_state = Arc::new(Mutex::new(FakeState {
            fail_begin: true,
            ..FakeState::default()
        }));
        let begin = CurationBatchObservationRun::begin(Some(fake(begin_state.clone())), true).await;
        assert_eq!(
            begin.finish().await,
            CurationBatchObservationCompletion::NoEpisode
        );
        assert!(calls(&begin_state).is_empty());

        let zero_state = Arc::new(Mutex::new(FakeState::default()));
        let zero = CurationBatchObservationRun::begin(Some(fake(zero_state.clone())), true).await;
        assert_eq!(
            zero.finish().await,
            CurationBatchObservationCompletion::Incomplete
        );
        assert_eq!(calls(&zero_state), strings(&["open"]));

        let close_state = Arc::new(Mutex::new(FakeState {
            fail_close: true,
            ..FakeState::default()
        }));
        let mut close =
            CurationBatchObservationRun::begin(Some(fake(close_state.clone())), true).await;
        close.observe_memory_saved("memory-a").await;
        assert_eq!(
            close.finish().await,
            CurationBatchObservationCompletion::Incomplete
        );
        assert_eq!(calls(&close_state), strings(&["open", "item:0"]));
    }
}
