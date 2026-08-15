//! Fixed S626 provider for exercising the private Story render admission chain.
//!
//! All identities and wire fields are deterministic synthetic fixtures. The
//! contract-mandated output path is serialized but never accessed here. The
//! placeholder digest is deliberately unkeyed and grants no authority. This
//! module performs no I/O and has no runtime caller.

#![deny(clippy::all)]

use std::sync::atomic::{AtomicU64, Ordering};

use serde_json::json;
use sha2::{Digest, Sha256};

use crate::story_render_synthetic_admission::StoryRenderSyntheticAdmissionProvider;

const REQUEST_DOMAIN: &str = "agent-bridge.story-render-synthetic-request.v1";
const NONCE_DOMAIN: &str = "agent-bridge.story-render-synthetic-nonce.v1";
const PLACEHOLDER_DOMAIN: &str = "agent-bridge.story-render-synthetic-placeholder.v1";
const PROTOCOL: &str = "agent_bridge.story-render-worker.v1";
const CONTRACT_SHA256: &str = "be4bfc12d9adeda14b8d20048b91baaaf903f155a3fca5bd3413b2b649f7334d";
const PREFLIGHT_SHA256: &str = "6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb";
const EXECUTION_CONTRACT_SHA256: &str =
    "24edc82e885c7f8e5a934019e78530f0d70a482e15ec04c52824395fef1e0fe8";
const WIRE_OUTPUT_ROOT: &str = "/home/pallasting/.agent-bridge-secure/story-render/outputs";
const ISSUED_AT: &str = "2026-08-02T12:00:00Z";
const EXPIRES_AT: &str = "2026-08-02T12:05:00Z";
const SYNTHETIC_KEY_ID: &str = "story-render-synthetic-structure-only-no-key-v1";
pub const SYNTHETIC_REPLAY_LEDGER_CAPACITY: usize = 4_096;
const SYNTHETIC_REPLAY_LEDGER_WORDS: usize = SYNTHETIC_REPLAY_LEDGER_CAPACITY / u64::BITS as usize;
static SYNTHETIC_REPLAY_LEDGER: [AtomicU64; SYNTHETIC_REPLAY_LEDGER_WORDS] =
    [const { AtomicU64::new(0) }; SYNTHETIC_REPLAY_LEDGER_WORDS];

pub struct StoryRenderFixedSyntheticProvider {
    sequence: u64,
    request_id: String,
    nonce: Option<String>,
    placeholder_sha256: String,
    request_pending: bool,
    replay_mode: StoryRenderFixedSyntheticReplayMode,
}

pub struct StoryRenderFixedSyntheticGrant {
    request_id: String,
    nonce: String,
    placeholder_sha256: String,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum StoryRenderFixedSyntheticReplayMode {
    ProcessLocal,
    ExternalGate,
}

impl StoryRenderFixedSyntheticProvider {
    pub fn new(sequence: u64) -> Self {
        Self::with_replay_mode(sequence, StoryRenderFixedSyntheticReplayMode::ProcessLocal)
    }

    pub(crate) fn new_with_external_replay_gate(sequence: u64) -> Self {
        Self::with_replay_mode(sequence, StoryRenderFixedSyntheticReplayMode::ExternalGate)
    }

    fn with_replay_mode(sequence: u64, replay_mode: StoryRenderFixedSyntheticReplayMode) -> Self {
        let request_digest = domain_digest(REQUEST_DOMAIN, sequence);
        Self {
            sequence,
            request_id: request_digest[..32].to_owned(),
            nonce: Some(domain_digest(NONCE_DOMAIN, sequence)),
            placeholder_sha256: domain_digest(PLACEHOLDER_DOMAIN, sequence),
            request_pending: false,
            replay_mode,
        }
    }
}

impl StoryRenderSyntheticAdmissionProvider for StoryRenderFixedSyntheticProvider {
    type Grant = StoryRenderFixedSyntheticGrant;

    fn generate_request_id(&mut self) -> Option<String> {
        Some(self.request_id.clone())
    }

    fn issue_grant(&mut self, request_id: &str) -> Option<Self::Grant> {
        if request_id != self.request_id {
            return None;
        }
        let nonce = self.nonce.take()?;
        if self.replay_mode == StoryRenderFixedSyntheticReplayMode::ProcessLocal
            && !reserve_sequence(self.sequence)
        {
            return None;
        }
        self.request_pending = true;
        Some(StoryRenderFixedSyntheticGrant {
            request_id: self.request_id.clone(),
            nonce,
            placeholder_sha256: self.placeholder_sha256.clone(),
        })
    }

    fn build_request(&mut self, request_id: &str, grant: Self::Grant) -> Option<Vec<u8>> {
        if !self.request_pending {
            return None;
        }
        self.request_pending = false;
        if request_id != self.request_id || grant.request_id != self.request_id {
            return None;
        }
        serde_json::to_vec(&json!({
            "protocol": PROTOCOL,
            "request_id": request_id,
            "fixture": {
                "preflight": "fixed_s602_fixture_only",
                "chapter": 2,
                "preflight_sha256": PREFLIGHT_SHA256,
                "execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
            },
            "authorization": {
                "authorization_id": format!("story-render-synthetic-{request_id}"),
                "contract_sha256": CONTRACT_SHA256,
                "preflight_sha256": PREFLIGHT_SHA256,
                "output_directory": format!("{WIRE_OUTPUT_ROOT}/{request_id}"),
                "action": "render",
                "issued_at": ISSUED_AT,
                "expires_at": EXPIRES_AT,
                "single_use_nonce": grant.nonce,
                "issuer": "agent-bridge-synthetic-fixture",
                "subject": "story-bounded-render-executor",
                "key_id": SYNTHETIC_KEY_ID,
                "mac_sha256": grant.placeholder_sha256,
            },
        }))
        .ok()
    }
}

fn reserve_sequence(sequence: u64) -> bool {
    let Ok(index) = usize::try_from(sequence) else {
        return false;
    };
    if index >= SYNTHETIC_REPLAY_LEDGER_CAPACITY {
        return false;
    }
    let word = index / u64::BITS as usize;
    let mask = 1_u64 << (index % u64::BITS as usize);
    SYNTHETIC_REPLAY_LEDGER[word].fetch_or(mask, Ordering::Relaxed) & mask == 0
}

fn domain_digest(domain: &str, sequence: u64) -> String {
    let mut hasher = Sha256::new();
    hasher.update(domain.as_bytes());
    hasher.update(b"\0");
    hasher.update(sequence.to_be_bytes());
    format!("{:x}", hasher.finalize())
}
