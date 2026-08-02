//! Dormant S630 durable replay composition for the synthetic Story chain.
//!
//! S625 acquires the host lock before this adapter reserves a sequence through
//! the S628 continuity seam. A successful synthetic response is committed;
//! every returned admission failure is aborted. Dropped or failed finalization
//! remains reserved and therefore fails closed. This module has no runtime
//! caller, storage implementation, authority, model, audio, memory, or MCP
//! surface.

#![deny(clippy::all)]

use crate::story_render_fixed_synthetic_provider::{
    StoryRenderFixedSyntheticGrant, StoryRenderFixedSyntheticProvider,
};
use crate::story_render_replay_continuity_synthetic::{
    StoryRenderReplayContinuityError, StoryRenderReplayContinuityStore,
};
use crate::story_render_supervisor::StoryRenderSupervisorConfig;
use crate::story_render_synthetic_admission::{
    StoryRenderSyntheticAdmissionError, StoryRenderSyntheticAdmissionProvider,
    run_s625_synthetic_admission,
};
use crate::story_render_synthetic_composition::StoryRenderSyntheticResult;

#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum StoryRenderDurableSyntheticCompositionError {
    #[error("continuity_{0:?}")]
    Continuity(StoryRenderReplayContinuityError),
    #[error("admission_{0}")]
    Admission(StoryRenderSyntheticAdmissionError),
}

struct StoryRenderDurableSyntheticProvider<'a, S>
where
    S: StoryRenderReplayContinuityStore,
{
    inner: StoryRenderFixedSyntheticProvider,
    store: &'a S,
    sequence: u64,
    reservation: Option<S::Reservation>,
    continuity_error: Option<StoryRenderReplayContinuityError>,
}

impl<'a, S> StoryRenderDurableSyntheticProvider<'a, S>
where
    S: StoryRenderReplayContinuityStore,
{
    fn new(sequence: u64, store: &'a S) -> Self {
        Self {
            inner: StoryRenderFixedSyntheticProvider::new_with_external_replay_gate(sequence),
            store,
            sequence,
            reservation: None,
            continuity_error: None,
        }
    }

    fn take_reservation(&mut self) -> Option<S::Reservation> {
        self.reservation.take()
    }

    fn take_continuity_error(&mut self) -> Option<StoryRenderReplayContinuityError> {
        self.continuity_error.take()
    }
}

impl<S> StoryRenderSyntheticAdmissionProvider for StoryRenderDurableSyntheticProvider<'_, S>
where
    S: StoryRenderReplayContinuityStore,
{
    type Grant = StoryRenderFixedSyntheticGrant;

    fn generate_request_id(&mut self) -> Option<String> {
        self.inner.generate_request_id()
    }

    fn issue_grant(&mut self, request_id: &str) -> Option<Self::Grant> {
        if self.reservation.is_some() || self.continuity_error.is_some() {
            return None;
        }
        let expected_request_id = self.inner.generate_request_id()?;
        if request_id != expected_request_id {
            return None;
        }
        let reservation = match self.store.reserve(self.sequence) {
            Ok(reservation) => reservation,
            Err(error) => {
                self.continuity_error = Some(error);
                return None;
            }
        };

        match self.inner.issue_grant(request_id) {
            Some(grant) => {
                self.reservation = Some(reservation);
                Some(grant)
            }
            None => {
                if let Err(error) = self.store.abort(reservation) {
                    self.continuity_error = Some(error);
                }
                None
            }
        }
    }

    fn build_request(&mut self, request_id: &str, grant: Self::Grant) -> Option<Vec<u8>> {
        self.inner.build_request(request_id, grant)
    }
}

pub async fn run_s630_durable_synthetic_composition<S>(
    config: StoryRenderSupervisorConfig,
    sequence: u64,
    store: &S,
) -> Result<StoryRenderSyntheticResult, StoryRenderDurableSyntheticCompositionError>
where
    S: StoryRenderReplayContinuityStore,
{
    let mut provider = StoryRenderDurableSyntheticProvider::new(sequence, store);
    match run_s625_synthetic_admission(config, &mut provider).await {
        Ok(result) => {
            let reservation = provider.take_reservation().ok_or(
                StoryRenderDurableSyntheticCompositionError::Continuity(
                    StoryRenderReplayContinuityError::InvalidTransition,
                ),
            )?;
            store
                .commit(reservation)
                .map_err(StoryRenderDurableSyntheticCompositionError::Continuity)?;
            Ok(result)
        }
        Err(admission_error) => {
            if let Some(error) = provider.take_continuity_error() {
                return Err(StoryRenderDurableSyntheticCompositionError::Continuity(
                    error,
                ));
            }
            if let Some(reservation) = provider.take_reservation() {
                store
                    .abort(reservation)
                    .map_err(StoryRenderDurableSyntheticCompositionError::Continuity)?;
            }
            Err(StoryRenderDurableSyntheticCompositionError::Admission(
                admission_error,
            ))
        }
    }
}
