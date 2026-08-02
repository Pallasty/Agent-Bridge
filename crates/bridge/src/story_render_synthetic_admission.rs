//! Private S625 synthetic admission seam for Story render work.
//!
//! The host lock is acquired before a provider may create an identity, issue a
//! synthetic grant, or close the request. The admission handle then transfers
//! lock ownership to the S623 Worker cleanup task. This module has no runtime
//! caller, durable custody, model access, playback, memory write, or MCP
//! registration.

#![deny(clippy::all)]

use crate::story_render_supervisor::{
    begin_story_render_admission, StoryRenderSupervisorConfig, StoryRenderSupervisorError,
};
use crate::story_render_synthetic_composition::{
    decode_s622_response, is_s622_request_id, s622_response_validator,
    StoryRenderSyntheticResponse, StoryRenderSyntheticResult,
};

pub trait StoryRenderSyntheticAdmissionProvider {
    type Grant;

    fn generate_request_id(&mut self) -> Option<String>;
    fn issue_grant(&mut self, request_id: &str) -> Option<Self::Grant>;
    fn build_request(&mut self, request_id: &str, grant: Self::Grant) -> Option<Vec<u8>>;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum StoryRenderSyntheticAdmissionError {
    #[error("identity_rejected")]
    IdentityRejected,
    #[error("invalid_request_id")]
    InvalidRequestId,
    #[error("grant_declined")]
    GrantDeclined,
    #[error("request_build_rejected")]
    RequestBuildRejected,
    #[error("supervisor_{0}")]
    Supervisor(StoryRenderSupervisorError),
    #[error("response_decode_failed")]
    ResponseDecodeFailed,
}

pub async fn run_s625_synthetic_admission<P>(
    config: StoryRenderSupervisorConfig,
    provider: &mut P,
) -> Result<StoryRenderSyntheticResult, StoryRenderSyntheticAdmissionError>
where
    P: StoryRenderSyntheticAdmissionProvider,
{
    let mut admission = begin_story_render_admission(config)
        .map_err(StoryRenderSyntheticAdmissionError::Supervisor)?;
    let request_id = provider
        .generate_request_id()
        .ok_or(StoryRenderSyntheticAdmissionError::IdentityRejected)?;
    if !is_s622_request_id(&request_id) {
        return Err(StoryRenderSyntheticAdmissionError::InvalidRequestId);
    }
    let grant = provider
        .issue_grant(&request_id)
        .ok_or(StoryRenderSyntheticAdmissionError::GrantDeclined)?;
    let request = provider
        .build_request(&request_id, grant)
        .ok_or(StoryRenderSyntheticAdmissionError::RequestBuildRejected)?;
    admission.bind_response_validator(s622_response_validator(request_id.clone()));
    let output = admission
        .start(request)
        .await
        .map_err(StoryRenderSyntheticAdmissionError::Supervisor)?
        .await
        .map_err(StoryRenderSyntheticAdmissionError::Supervisor)?;
    let response: StoryRenderSyntheticResponse = decode_s622_response(&output.stdout, &request_id)
        .ok_or(StoryRenderSyntheticAdmissionError::ResponseDecodeFailed)?;
    Ok(StoryRenderSyntheticResult {
        status_code: output.status_code,
        response,
        stderr: output.stderr,
    })
}
