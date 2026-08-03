//! Private S624 composition of the S622 wire contract and S623 Supervisor.
//!
//! The caller supplies an already closed synthetic request. A repository-owned
//! fixture Worker performs the S622 request decode; this layer binds the
//! expected request identity, installs an exact Rust response validator, and
//! delegates all process ownership to the S623 Supervisor. There is no runtime
//! caller, authority verification, model access, playback, memory write, or MCP
//! registration in this module.

#![deny(clippy::all)]

use std::sync::Arc;

use serde::Deserialize;

use crate::story_render_supervisor::{
    start_story_render_supervisor, ResponseValidator, StoryRenderSupervisorConfig,
    StoryRenderSupervisorError,
};

const S622_PROTOCOL: &str = "agent_bridge.story-render-worker.v1";

#[derive(Debug, Clone, PartialEq)]
pub struct StoryRenderSyntheticAssembly {
    pub sha256: String,
    pub sample_rate_hz: u64,
    pub channels: u64,
    pub frames: u64,
    pub duration_seconds: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct StoryRenderSyntheticSuccess {
    pub request_id: String,
    pub render_id: String,
    pub segment_count: u64,
    pub assembly: StoryRenderSyntheticAssembly,
    pub playback_authorized: bool,
    pub memory_authorized: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StoryRenderSyntheticWorkerError {
    pub request_id: String,
    pub code: String,
    pub retryable: bool,
}

#[derive(Debug, Clone, PartialEq)]
pub enum StoryRenderSyntheticResponse {
    Success(StoryRenderSyntheticSuccess),
    Error(StoryRenderSyntheticWorkerError),
}

#[derive(Debug, Clone, PartialEq)]
pub struct StoryRenderSyntheticResult {
    pub status_code: Option<i32>,
    pub response: StoryRenderSyntheticResponse,
    pub stderr: Vec<u8>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum StoryRenderSyntheticCompositionError {
    #[error("invalid_request_id")]
    InvalidRequestId,
    #[error("supervisor_{0}")]
    Supervisor(StoryRenderSupervisorError),
    #[error("response_decode_failed")]
    ResponseDecodeFailed,
}

#[derive(Deserialize)]
struct StatusWire {
    status: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SuccessWire {
    protocol: String,
    request_id: String,
    status: String,
    render_id: String,
    segment_count: u64,
    assembly: AssemblyWire,
    playback_authorized: bool,
    memory_authorized: bool,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct AssemblyWire {
    sha256: String,
    sample_rate_hz: u64,
    channels: u64,
    frames: u64,
    duration_seconds: f64,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ErrorWire {
    protocol: String,
    request_id: String,
    status: String,
    code: String,
    retryable: bool,
}

pub async fn run_s622_synthetic_composition(
    mut config: StoryRenderSupervisorConfig,
    request_id: String,
    request: Vec<u8>,
) -> Result<StoryRenderSyntheticResult, StoryRenderSyntheticCompositionError> {
    if !is_s622_request_id(&request_id) {
        return Err(StoryRenderSyntheticCompositionError::InvalidRequestId);
    }

    config.response_validator = s622_response_validator(request_id.clone());
    let output = start_story_render_supervisor(config, request)
        .await
        .map_err(StoryRenderSyntheticCompositionError::Supervisor)?
        .await
        .map_err(StoryRenderSyntheticCompositionError::Supervisor)?;
    let response = decode_s622_response(&output.stdout, &request_id)
        .ok_or(StoryRenderSyntheticCompositionError::ResponseDecodeFailed)?;
    Ok(StoryRenderSyntheticResult {
        status_code: output.status_code,
        response,
        stderr: output.stderr,
    })
}

pub(crate) fn s622_response_validator(request_id: String) -> ResponseValidator {
    Arc::new(move |raw| decode_s622_response(raw, &request_id).is_some())
}

pub(crate) fn decode_s622_response(
    raw: &[u8],
    expected_request_id: &str,
) -> Option<StoryRenderSyntheticResponse> {
    let status: StatusWire = serde_json::from_slice(raw).ok()?;
    match status.status.as_str() {
        "success" => {
            decode_success(raw, expected_request_id).map(StoryRenderSyntheticResponse::Success)
        }
        "error" => decode_error(raw, expected_request_id).map(StoryRenderSyntheticResponse::Error),
        _ => None,
    }
}

fn decode_success(raw: &[u8], expected_request_id: &str) -> Option<StoryRenderSyntheticSuccess> {
    let wire: SuccessWire = serde_json::from_slice(raw).ok()?;
    if wire.protocol != S622_PROTOCOL
        || wire.status != "success"
        || wire.request_id != expected_request_id
        || wire.render_id != expected_request_id
        || wire.segment_count == 0
        || !is_lower_hex(&wire.assembly.sha256, 64)
        || wire.assembly.sample_rate_hz == 0
        || wire.assembly.channels == 0
        || wire.assembly.frames == 0
        || !wire.assembly.duration_seconds.is_finite()
        || wire.assembly.duration_seconds <= 0.0
        || wire.playback_authorized
        || wire.memory_authorized
    {
        return None;
    }
    Some(StoryRenderSyntheticSuccess {
        request_id: wire.request_id,
        render_id: wire.render_id,
        segment_count: wire.segment_count,
        assembly: StoryRenderSyntheticAssembly {
            sha256: wire.assembly.sha256,
            sample_rate_hz: wire.assembly.sample_rate_hz,
            channels: wire.assembly.channels,
            frames: wire.assembly.frames,
            duration_seconds: wire.assembly.duration_seconds,
        },
        playback_authorized: wire.playback_authorized,
        memory_authorized: wire.memory_authorized,
    })
}

fn decode_error(raw: &[u8], expected_request_id: &str) -> Option<StoryRenderSyntheticWorkerError> {
    let wire: ErrorWire = serde_json::from_slice(raw).ok()?;
    if wire.protocol != S622_PROTOCOL
        || wire.status != "error"
        || wire.request_id != expected_request_id
        || !matches!(
            wire.code.as_str(),
            "invalid_request"
                | "authority_rejected"
                | "nonce_reused"
                | "custody_rejected"
                | "model_rejected"
                | "render_failed"
                | "internal_failure"
        )
    {
        return None;
    }
    Some(StoryRenderSyntheticWorkerError {
        request_id: wire.request_id,
        code: wire.code,
        retryable: wire.retryable,
    })
}

fn is_lower_hex(value: &str, length: usize) -> bool {
    value.len() == length
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

pub(crate) fn is_s622_request_id(value: &str) -> bool {
    is_lower_hex(value, 32)
}
