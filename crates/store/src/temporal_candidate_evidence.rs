//! Synthetic-only S5 binding from one sealed S4 projection to Track B handles.
//!
//! This source-level interface is not a transport. It consumes the original
//! S4 request and sealed projection together, requires their claim sets to be
//! identical, emits only request-scoped opaque handles, and drops all raw
//! projection material before returning a non-serializable result.

use crate::{
    temporal_truth_project_read_only_synthetic_v1, BoundTemporalTruthProjectionV1,
    SyntheticTemporalTruthProjectionPermitV1, TemporalTruthProjectionLimitsV1,
    TemporalTruthProjectionRequestV1, TemporalTruthStateV1, TemporalTruthTemporalStateV1,
    TemporalTruthTierV1, TEMPORAL_TRUTH_PROJECTION_V1_MAPPING, TEMPORAL_TRUTH_PROJECTION_V1_MODE,
    TEMPORAL_TRUTH_PROJECTION_V1_PROFILE, TEMPORAL_TRUTH_PROJECTION_V1_SCHEMA,
};
use ring::hmac;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::io::{self, Write};
use std::path::Path;

pub const TRACK_B_CANDIDATE_EVIDENCE_V1_SCHEMA: &str =
    "agent_bridge.biocortex_ab_track_b_candidate_evidence_envelope.v0";
pub const TRACK_B_CANDIDATE_EVIDENCE_V1_MODE: &str = "synthetic_source_interface_not_live_bound";
pub const TRACK_B_CANDIDATE_HANDLE_PROFILE_V1: &str = "request_scoped_hmac_sha256_trunc128_v1";
pub const TRACK_B_CANDIDATE_EVIDENCE_SCHEMA_SHA256: &str =
    "edba8da90abeeda83e33943d9b87f76c0deff9fad34cb314cd27c28b85ed1b77";
pub const TRACK_B_FOUNDATIONAL_PACK_MANIFEST_SHA256: &str =
    "fbfbf5738dd81e0afe8dbc45b1e91a35e92382a1913006a9b2e5ded67c077f36";
pub const TRACK_B_FOUNDATIONAL_ARTIFACT_CATALOG_SHA256: &str =
    "bdee820dba3f20bae415826382551bf74cc9b6f13e51d2f9b1c49d9f9394d684";
pub const TRACK_B_TRUTH_REFERENT_SCHEMA_ID: &str =
    "urn:agent-bridge:biocortex-ab:track-b:truth-referent:v0";
pub const TRACK_B_TRUTH_REFERENT_SCHEMA_SHA256: &str =
    "5da057e70675cbd259e0d1beb98039d2eee8589c73aa910f92f90cb0374545a8";

const TRACK_B_FOUNDATIONAL_PACK_BASELINE: &str = "a989cf6e09d60cb4d3d9b6d5f6a60e55ecd65259";
const S2_SCHEMA_SHA256: &str = "6d321d45aafe65ef06efb49c46ccf9f1931624aada9e8873d7e29765826e3aa0";
const S2_MIGRATION_SHA256: &str =
    "f0d9a3a2505d301a266bb41c09ce2fbaebd8572aa9340affd7e62b6d29faa8bb";
const CANDIDATE_ID: &str = "temporal_truth_projection_v1_synthetic_source_binding";
const HMAC_ALGORITHM: &str = "HMAC-SHA-256";
const AUTHENTICATION_DOMAIN: &str = "agent-bridge/track-b/candidate-evidence-envelope/v0";
const AUTHENTICATION_CANONICALIZATION: &str = "serde_json_compact_struct_field_order_utf8_v1";
const AUTHENTICATION_MESSAGE_PROFILE: &str =
    "u64be_len_domain_domain_u64be_len_key_id_key_id_exact_payload_json";
const HANDLE_DIGEST_BYTES: usize = 16;
const MAX_CLAIMS: usize = 1_024;
const MAX_VALUES_PER_CLAIM: usize = 1_024;
const MAX_EVIDENCE_PER_CLAIM: usize = 1_024;
const MAX_SOURCE_BINDINGS_PER_CLAIM: usize = 1_024;
const MAX_ENVELOPE_BYTES: usize = 4 * 1024 * 1024;
const MAX_TTL_SECONDS: i64 = 3_600;
const REQUEST_BINDING_DOMAIN: &[u8] = b"agent-bridge/track-b/candidate-evidence/request-binding/v1";
const HANDLE_SCOPE_DOMAIN: &[u8] = b"agent-bridge/track-b/candidate-evidence/handle-scope/v1";
const PROJECTION_HANDLE_DOMAIN: &[u8] =
    b"agent-bridge/track-b/candidate-evidence/projection-handle/v1";
const CLAIM_HANDLE_DOMAIN: &[u8] = b"agent-bridge/track-b/candidate-evidence/claim-handle/v1";
const REFERENT_HANDLE_DOMAIN: &[u8] = b"agent-bridge/track-b/candidate-evidence/referent-handle/v1";
const PREDICATE_HANDLE_DOMAIN: &[u8] =
    b"agent-bridge/track-b/candidate-evidence/predicate-handle/v1";
const VALUE_HANDLE_DOMAIN: &[u8] = b"agent-bridge/track-b/candidate-evidence/value-handle/v1";
const EVIDENCE_HANDLE_DOMAIN: &[u8] = b"agent-bridge/track-b/candidate-evidence/evidence-handle/v1";
const SOURCE_HANDLE_DOMAIN: &[u8] = b"agent-bridge/track-b/candidate-evidence/source-handle/v1";
const CLAIM_BINDING_DOMAIN: &[u8] = b"agent-bridge/track-b/candidate-evidence/claim-binding/v1";

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
#[error("{code}: {detail}")]
pub struct TrackBCandidateEvidenceV1Error {
    code: &'static str,
    detail: String,
}

impl TrackBCandidateEvidenceV1Error {
    pub fn code(&self) -> &str {
        self.code
    }

    pub fn detail(&self) -> &str {
        &self.detail
    }
}

type CandidateResult<T> = std::result::Result<T, TrackBCandidateEvidenceV1Error>;

fn candidate_error(
    code: &'static str,
    detail: impl Into<String>,
) -> TrackBCandidateEvidenceV1Error {
    TrackBCandidateEvidenceV1Error {
        code,
        detail: detail.into(),
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
struct SnapshotCountsWire {
    evidence_revisions: usize,
    lineages: usize,
    policy_revisions: usize,
    relationships: usize,
    tombstones: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
struct ProjectionLimitsWire {
    max_evidence_revisions: usize,
    max_lineages: usize,
    max_payload_bytes: usize,
    max_policy_revisions: usize,
    max_relationships: usize,
    max_tombstones: usize,
}

impl From<TemporalTruthProjectionLimitsV1> for ProjectionLimitsWire {
    fn from(value: TemporalTruthProjectionLimitsV1) -> Self {
        Self {
            max_evidence_revisions: value.max_evidence_revisions(),
            max_lineages: value.max_lineages(),
            max_payload_bytes: value.max_payload_bytes(),
            max_policy_revisions: value.max_policy_revisions(),
            max_relationships: value.max_relationships(),
            max_tombstones: value.max_tombstones(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
struct ProjectionBindingWire {
    as_of: i64,
    canonical_order: String,
    knowledge_cutoff: i64,
    ledger_format_version: u32,
    mapping_version: String,
    migration_sha256: String,
    prepared_input_sha256: String,
    producer_profile: String,
    projection_mode: String,
    projection_schema: String,
    projection_sha256: String,
    pruned_inbound_relationships: usize,
    query_only_attested: bool,
    read_only_attested: bool,
    schema_meta_version: String,
    schema_sha256: String,
    snapshot_counts: SnapshotCountsWire,
    snapshot_limits: ProjectionLimitsWire,
    snapshot_payload_bytes: usize,
    snapshot_payload_sha256: String,
    synthetic_fixture_id: String,
    zero_total_changes_attested: bool,
}

impl ProjectionBindingWire {
    fn from_projection(projection: &BoundTemporalTruthProjectionV1) -> Self {
        let counts = projection.snapshot_counts();
        Self {
            as_of: projection.as_of(),
            canonical_order: projection.canonical_order().to_string(),
            knowledge_cutoff: projection.knowledge_cutoff(),
            ledger_format_version: projection.ledger_format_version(),
            mapping_version: projection.mapping_version().to_string(),
            migration_sha256: projection.migration_sha256().to_string(),
            prepared_input_sha256: projection.prepared_input_sha256().to_string(),
            producer_profile: projection.producer_profile().to_string(),
            projection_mode: projection.mode().to_string(),
            projection_schema: projection.schema().to_string(),
            projection_sha256: projection.projection_sha256().to_string(),
            pruned_inbound_relationships: projection.pruned_inbound_relationships(),
            query_only_attested: projection.query_only_attested(),
            read_only_attested: projection.read_only_attested(),
            schema_meta_version: projection.schema_meta_version().to_string(),
            schema_sha256: projection.schema_sha256().to_string(),
            snapshot_counts: SnapshotCountsWire {
                evidence_revisions: counts.evidence_revisions(),
                lineages: counts.lineages(),
                policy_revisions: counts.policy_revisions(),
                relationships: counts.relationships(),
                tombstones: counts.tombstones(),
            },
            snapshot_limits: projection.snapshot_limits().into(),
            snapshot_payload_bytes: projection.snapshot_payload_bytes(),
            snapshot_payload_sha256: projection.snapshot_payload_sha256().to_string(),
            synthetic_fixture_id: projection.synthetic_fixture_id().to_string(),
            zero_total_changes_attested: projection.zero_total_changes_attested(),
        }
    }
}

#[derive(Serialize)]
struct RequiredClaimWire<'a> {
    predicate_id: &'a str,
    referent_id: &'a str,
}

#[derive(Serialize)]
struct RequestBindingWire<'a> {
    as_of: i64,
    knowledge_cutoff: i64,
    limits: ProjectionLimitsWire,
    required_claims: Vec<RequiredClaimWire<'a>>,
}

/// An inseparable S4 request/projection pair created by one projection call.
///
/// This transient object retains the raw S4 projection only until it is
/// consumed by S5. It is neither cloneable nor serializable, and its fields are
/// private so a projection cannot be paired with a later replacement request.
#[must_use]
pub struct SyntheticTrackBCandidateProjectionPairV1 {
    projection: BoundTemporalTruthProjectionV1,
    request: TemporalTruthProjectionRequestV1,
}

impl fmt::Debug for SyntheticTrackBCandidateProjectionPairV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("SyntheticTrackBCandidateProjectionPairV1")
            .field("projection_sha256", &self.projection.projection_sha256())
            .field("request", &"[REDACTED]")
            .finish_non_exhaustive()
    }
}

impl SyntheticTrackBCandidateProjectionPairV1 {
    pub fn projection(&self) -> &BoundTemporalTruthProjectionV1 {
        &self.projection
    }
}

/// Create the only safe request/projection pairing accepted by S5.
///
/// The S4 permit still has no safe non-test constructor, so this source-level
/// function cannot activate a production read path by enabling the feature.
pub async fn project_synthetic_track_b_candidate_source_v1(
    permit: SyntheticTemporalTruthProjectionPermitV1,
    path: &Path,
    request: TemporalTruthProjectionRequestV1,
) -> CandidateResult<SyntheticTrackBCandidateProjectionPairV1> {
    let projection = temporal_truth_project_read_only_synthetic_v1(permit, path, request.clone())
        .await
        .map_err(|error| {
            candidate_error(
                "track_b_candidate_v1_source_projection",
                format!("{}: {}", error.code(), error.detail()),
            )
        })?;
    Ok(SyntheticTrackBCandidateProjectionPairV1 {
        projection,
        request,
    })
}

/// One-shot synthetic capability carrying request-local key material and the
/// exact request/projection tuple it is allowed to bind.
///
/// There is no safe non-test constructor. Both keys and the nonce are
/// best-effort cleared on drop; no secret is copied into the result.
pub struct SyntheticTrackBCandidateEvidencePermitV1 {
    case_id: String,
    contract_sha256: String,
    expected_projection: ProjectionBindingWire,
    expected_request_binding_sha256: String,
    expires_at_utc: i64,
    handle_key: [u8; 32],
    handle_key_id: String,
    issued_at_utc: i64,
    request_id: String,
    request_nonce: [u8; 32],
    transport_key: [u8; 32],
    transport_key_id: String,
    trial_id: String,
}

impl fmt::Debug for SyntheticTrackBCandidateEvidencePermitV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("SyntheticTrackBCandidateEvidencePermitV1")
            .field("key_material", &"[REDACTED]")
            .field("scope_material", &"[REDACTED]")
            .finish_non_exhaustive()
    }
}

impl Drop for SyntheticTrackBCandidateEvidencePermitV1 {
    fn drop(&mut self) {
        self.handle_key.fill(0);
        self.request_nonce.fill(0);
        self.transport_key.fill(0);
    }
}

#[cfg(test)]
#[allow(clippy::too_many_arguments)]
pub(crate) fn synthetic_track_b_candidate_evidence_permit_v1(
    pair: &SyntheticTrackBCandidateProjectionPairV1,
    handle_key: [u8; 32],
    transport_key: [u8; 32],
    request_nonce: [u8; 32],
    trial_id: impl Into<String>,
    contract_sha256: impl Into<String>,
    case_id: impl Into<String>,
    request_id: impl Into<String>,
    handle_key_id: impl Into<String>,
    transport_key_id: impl Into<String>,
    issued_at_utc: i64,
    expires_at_utc: i64,
) -> CandidateResult<SyntheticTrackBCandidateEvidencePermitV1> {
    let projection = &pair.projection;
    let request = &pair.request;
    validate_source_projection(projection)?;
    validate_request_against_projection(request, projection)?;
    if request.required_claims().is_empty() {
        return Err(candidate_error(
            "track_b_candidate_v1_empty_required_claims",
            "candidate export requires a non-empty exact claim allowlist",
        ));
    }
    if handle_key.iter().all(|byte| *byte == 0)
        || transport_key.iter().all(|byte| *byte == 0)
        || handle_key == transport_key
    {
        return Err(candidate_error(
            "track_b_candidate_v1_invalid_key_material",
            "synthetic handle and transport keys must be non-zero and distinct",
        ));
    }
    if request_nonce.iter().all(|byte| *byte == 0) {
        return Err(candidate_error(
            "track_b_candidate_v1_invalid_request_nonce",
            "synthetic request nonce must not be all zero",
        ));
    }

    let trial_id = trial_id.into();
    let contract_sha256 = contract_sha256.into();
    let case_id = case_id.into();
    let request_id = request_id.into();
    let handle_key_id = handle_key_id.into();
    let transport_key_id = transport_key_id.into();
    for (field, value) in [
        ("trial_id", trial_id.as_str()),
        ("request_id", request_id.as_str()),
        ("handle_key_id", handle_key_id.as_str()),
        ("transport_key_id", transport_key_id.as_str()),
    ] {
        validate_label(field, value)?;
    }
    validate_case_id(&case_id)?;
    validate_sha256("contract_sha256", &contract_sha256)?;
    if handle_key_id == transport_key_id {
        return Err(candidate_error(
            "track_b_candidate_v1_key_id_collision",
            "handle and transport key ids must be distinct",
        ));
    }
    let ttl = expires_at_utc.checked_sub(issued_at_utc).ok_or_else(|| {
        candidate_error(
            "track_b_candidate_v1_invalid_time_window",
            "candidate time window overflow",
        )
    })?;
    if issued_at_utc < 0 || ttl <= 0 || ttl >= MAX_TTL_SECONDS {
        return Err(candidate_error(
            "track_b_candidate_v1_invalid_time_window",
            "candidate request must be currently valid and below the TTL sentinel",
        ));
    }

    Ok(SyntheticTrackBCandidateEvidencePermitV1 {
        case_id,
        contract_sha256,
        expected_projection: ProjectionBindingWire::from_projection(projection),
        expected_request_binding_sha256: request_binding_digest(request)?,
        expires_at_utc,
        handle_key,
        handle_key_id,
        issued_at_utc,
        request_id,
        request_nonce,
        transport_key,
        transport_key_id,
        trial_id,
    })
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct CandidateReferentModel {
    claim_handle: String,
    predicate_handle: String,
    referent_handle: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct CandidateClaimBindingModel {
    claim_binding_hmac_sha256: String,
    evidence_count: usize,
    evidence_handles: Vec<String>,
    noncurrent_evidence_count: usize,
    referent: CandidateReferentModel,
    shadowed_evidence_count: usize,
    source_binding_handles: Vec<String>,
    supporting_evidence_handles: Vec<String>,
    temporal_state: TemporalTruthTemporalStateV1,
    truth_state: TemporalTruthStateV1,
    truth_tier: Option<TemporalTruthTierV1>,
    value_handles: Vec<String>,
}

fn validate_candidate_claim_model(model: &CandidateClaimBindingModel) -> CandidateResult<()> {
    if model.evidence_count != model.evidence_handles.len() {
        return Err(candidate_error(
            "track_b_candidate_v1_evidence_cardinality",
            "evidence_count must equal the number of top evidence handles",
        ));
    }
    let state_is_valid = match model.truth_state {
        TemporalTruthStateV1::Supported => model.value_handles.len() == 1,
        TemporalTruthStateV1::Conflicted => model.value_handles.len() >= 2,
        TemporalTruthStateV1::Unknown => {
            model.truth_tier.is_none()
                && model.value_handles.is_empty()
                && model.evidence_handles.is_empty()
                && model.supporting_evidence_handles.is_empty()
                && model.source_binding_handles.is_empty()
                && model.evidence_count == 0
                && model.noncurrent_evidence_count == 0
                && model.shadowed_evidence_count == 0
        }
    };
    if !state_is_valid {
        return Err(candidate_error(
            "track_b_candidate_v1_truth_cardinality",
            "truth state, tier, handles, and evidence counts are inconsistent",
        ));
    }
    Ok(())
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct CandidateAuthenticationModel {
    hmac_sha256: String,
    key_id: String,
    payload_sha256: String,
}

/// Field-private, non-serializable, non-cloneable S5 candidate binding.
///
/// The S4 request and projection are consumed and dropped before this object
/// is returned. No raw truth material or key material remains reachable.
#[must_use]
pub struct BoundTrackBCandidateEvidenceV1 {
    authentication: CandidateAuthenticationModel,
    case_id: String,
    claims: Vec<CandidateClaimBindingModel>,
    contract_sha256: String,
    expires_at_utc: i64,
    handle_key_id: String,
    issued_at_utc: i64,
    projection_binding_handle: String,
    request_id: String,
    request_nonce: String,
    trial_id: String,
}

impl fmt::Debug for BoundTrackBCandidateEvidenceV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("BoundTrackBCandidateEvidenceV1")
            .field("schema", &TRACK_B_CANDIDATE_EVIDENCE_V1_SCHEMA)
            .field("mode", &TRACK_B_CANDIDATE_EVIDENCE_V1_MODE)
            .field("payload_sha256", &self.authentication.payload_sha256)
            .field("claim_count", &self.claims.len())
            .finish_non_exhaustive()
    }
}

impl BoundTrackBCandidateEvidenceV1 {
    pub fn schema(&self) -> &str {
        TRACK_B_CANDIDATE_EVIDENCE_V1_SCHEMA
    }

    pub fn mode(&self) -> &str {
        TRACK_B_CANDIDATE_EVIDENCE_V1_MODE
    }

    pub fn candidate_id(&self) -> &str {
        CANDIDATE_ID
    }

    pub fn trial_id(&self) -> &str {
        &self.trial_id
    }

    pub fn contract_sha256(&self) -> &str {
        &self.contract_sha256
    }

    pub fn case_id(&self) -> &str {
        &self.case_id
    }

    pub fn request_id(&self) -> &str {
        &self.request_id
    }

    pub fn request_nonce(&self) -> &str {
        &self.request_nonce
    }

    pub fn issued_at_utc(&self) -> i64 {
        self.issued_at_utc
    }

    pub fn expires_at_utc(&self) -> i64 {
        self.expires_at_utc
    }

    pub fn handle_profile(&self) -> &str {
        TRACK_B_CANDIDATE_HANDLE_PROFILE_V1
    }

    pub fn handle_key_id(&self) -> &str {
        &self.handle_key_id
    }

    pub fn projection_binding_handle(&self) -> &str {
        &self.projection_binding_handle
    }

    pub fn candidate_evidence_schema_sha256(&self) -> &str {
        TRACK_B_CANDIDATE_EVIDENCE_SCHEMA_SHA256
    }

    pub fn track_b_foundational_pack_baseline(&self) -> &str {
        TRACK_B_FOUNDATIONAL_PACK_BASELINE
    }

    pub fn track_b_foundational_pack_manifest_sha256(&self) -> &str {
        TRACK_B_FOUNDATIONAL_PACK_MANIFEST_SHA256
    }

    pub fn track_b_foundational_artifact_catalog_sha256(&self) -> &str {
        TRACK_B_FOUNDATIONAL_ARTIFACT_CATALOG_SHA256
    }

    pub fn track_b_truth_referent_schema_id(&self) -> &str {
        TRACK_B_TRUTH_REFERENT_SCHEMA_ID
    }

    pub fn track_b_truth_referent_schema_sha256(&self) -> &str {
        TRACK_B_TRUTH_REFERENT_SCHEMA_SHA256
    }

    pub fn authentication_algorithm(&self) -> &str {
        HMAC_ALGORITHM
    }

    pub fn authentication_domain(&self) -> &str {
        AUTHENTICATION_DOMAIN
    }

    pub fn authentication_key_id(&self) -> &str {
        &self.authentication.key_id
    }

    pub fn authentication_canonicalization(&self) -> &str {
        AUTHENTICATION_CANONICALIZATION
    }

    pub fn authentication_message_profile(&self) -> &str {
        AUTHENTICATION_MESSAGE_PROFILE
    }

    pub fn payload_sha256(&self) -> &str {
        &self.authentication.payload_sha256
    }

    pub fn hmac_sha256(&self) -> &str {
        &self.authentication.hmac_sha256
    }

    pub fn claims(&self) -> impl ExactSizeIterator<Item = TrackBCandidateEvidenceClaimViewV1<'_>> {
        self.claims
            .iter()
            .map(|model| TrackBCandidateEvidenceClaimViewV1 { model })
    }
}

#[derive(Clone, Copy)]
pub struct TrackBCandidateEvidenceClaimViewV1<'a> {
    model: &'a CandidateClaimBindingModel,
}

impl<'a> TrackBCandidateEvidenceClaimViewV1<'a> {
    pub fn claim_handle(&self) -> &'a str {
        &self.model.referent.claim_handle
    }

    pub fn referent_handle(&self) -> &'a str {
        &self.model.referent.referent_handle
    }

    pub fn predicate_handle(&self) -> &'a str {
        &self.model.referent.predicate_handle
    }

    pub fn claim_binding_hmac_sha256(&self) -> &'a str {
        &self.model.claim_binding_hmac_sha256
    }

    pub fn truth_state(&self) -> TemporalTruthStateV1 {
        self.model.truth_state
    }

    pub fn temporal_state(&self) -> TemporalTruthTemporalStateV1 {
        self.model.temporal_state
    }

    pub fn truth_tier(&self) -> Option<TemporalTruthTierV1> {
        self.model.truth_tier
    }

    pub fn evidence_count(&self) -> usize {
        self.model.evidence_count
    }

    pub fn evidence_handles(&self) -> &'a [String] {
        &self.model.evidence_handles
    }

    pub fn shadowed_evidence_count(&self) -> usize {
        self.model.shadowed_evidence_count
    }

    pub fn noncurrent_evidence_count(&self) -> usize {
        self.model.noncurrent_evidence_count
    }

    pub fn value_handles(&self) -> &'a [String] {
        &self.model.value_handles
    }

    pub fn supporting_evidence_handles(&self) -> &'a [String] {
        &self.model.supporting_evidence_handles
    }

    pub fn source_binding_handles(&self) -> &'a [String] {
        &self.model.source_binding_handles
    }
}

#[derive(Serialize)]
struct ReferentWire<'a> {
    claim_handle: &'a str,
    predicate_handle: &'a str,
    referent_handle: &'a str,
}

#[derive(Serialize)]
struct ClaimWire<'a> {
    claim_binding_hmac_sha256: &'a str,
    evidence_count: usize,
    evidence_handles: &'a [String],
    noncurrent_evidence_count: usize,
    referent: ReferentWire<'a>,
    shadowed_evidence_count: usize,
    source_binding_handles: &'a [String],
    supporting_evidence_handles: &'a [String],
    temporal_state: &'static str,
    truth_state: &'static str,
    truth_tier: &'static str,
    value_handles: &'a [String],
}

impl<'a> ClaimWire<'a> {
    fn from_model(model: &'a CandidateClaimBindingModel) -> Self {
        Self {
            claim_binding_hmac_sha256: &model.claim_binding_hmac_sha256,
            evidence_count: model.evidence_count,
            evidence_handles: &model.evidence_handles,
            noncurrent_evidence_count: model.noncurrent_evidence_count,
            referent: ReferentWire {
                claim_handle: &model.referent.claim_handle,
                predicate_handle: &model.referent.predicate_handle,
                referent_handle: &model.referent.referent_handle,
            },
            shadowed_evidence_count: model.shadowed_evidence_count,
            source_binding_handles: &model.source_binding_handles,
            supporting_evidence_handles: &model.supporting_evidence_handles,
            temporal_state: temporal_state_label(model.temporal_state),
            truth_state: truth_state_label(model.truth_state),
            truth_tier: truth_tier_label(model.truth_tier),
            value_handles: &model.value_handles,
        }
    }
}

#[derive(Serialize)]
struct ClaimBindingWire<'a> {
    evidence_count: usize,
    evidence_handles: &'a [String],
    noncurrent_evidence_count: usize,
    referent: ReferentWire<'a>,
    shadowed_evidence_count: usize,
    source_binding_handles: &'a [String],
    supporting_evidence_handles: &'a [String],
    temporal_state: &'static str,
    truth_state: &'static str,
    truth_tier: &'static str,
    value_handles: &'a [String],
}

impl<'a> ClaimBindingWire<'a> {
    fn from_model(model: &'a CandidateClaimBindingModel) -> Self {
        Self {
            evidence_count: model.evidence_count,
            evidence_handles: &model.evidence_handles,
            noncurrent_evidence_count: model.noncurrent_evidence_count,
            referent: ReferentWire {
                claim_handle: &model.referent.claim_handle,
                predicate_handle: &model.referent.predicate_handle,
                referent_handle: &model.referent.referent_handle,
            },
            shadowed_evidence_count: model.shadowed_evidence_count,
            source_binding_handles: &model.source_binding_handles,
            supporting_evidence_handles: &model.supporting_evidence_handles,
            temporal_state: temporal_state_label(model.temporal_state),
            truth_state: truth_state_label(model.truth_state),
            truth_tier: truth_tier_label(model.truth_tier),
            value_handles: &model.value_handles,
        }
    }
}

#[derive(Serialize)]
struct BoundaryWire {
    authority_custody_resolved: bool,
    biocortex_runtime_influence: bool,
    capture_provenance_attested: bool,
    contains_raw_evidence_ids: bool,
    contains_raw_predicate_ids: bool,
    contains_raw_provenance: bool,
    contains_raw_referent_ids: bool,
    contains_raw_source_bindings: bool,
    contains_raw_values: bool,
    cross_repository_transport_authorized: bool,
    live_binding_satisfied: bool,
    physical_privacy_deletion_resolved: bool,
    production_profile_active: bool,
    side_effects_unlocked: &'static str,
}

#[derive(Serialize)]
struct CandidateLimitsWire {
    max_claims: usize,
    max_envelope_bytes: usize,
    max_evidence_per_claim: usize,
    max_source_bindings_per_claim: usize,
    max_ttl_seconds: i64,
    max_values_per_claim: usize,
}

#[derive(Serialize)]
struct CandidateEnvelopePayloadWire<'a> {
    boundary: BoundaryWire,
    candidate_evidence_schema_sha256: &'static str,
    candidate_id: &'static str,
    case_id: &'a str,
    claims: Vec<ClaimWire<'a>>,
    contract_sha256: &'a str,
    expires_at_utc: i64,
    foundational_schema_pack_manifest_sha256: &'static str,
    handle_key_id: &'a str,
    handle_profile_id: &'static str,
    issued_at_utc: i64,
    limits: CandidateLimitsWire,
    projection_binding_handle: &'a str,
    request_id: &'a str,
    request_nonce: &'a str,
    schema: &'static str,
    trial_id: &'a str,
    truth_referent_schema_sha256: &'static str,
}

fn temporal_state_label(value: TemporalTruthTemporalStateV1) -> &'static str {
    match value {
        TemporalTruthTemporalStateV1::Current => "current",
        TemporalTruthTemporalStateV1::Historical => "historical",
        TemporalTruthTemporalStateV1::Future => "future",
        TemporalTruthTemporalStateV1::Indeterminate => "indeterminate",
    }
}

fn truth_state_label(value: TemporalTruthStateV1) -> &'static str {
    match value {
        TemporalTruthStateV1::Supported => "supported",
        TemporalTruthStateV1::Conflicted => "conflicted",
        TemporalTruthStateV1::Unknown => "unknown",
    }
}

fn truth_tier_label(value: Option<TemporalTruthTierV1>) -> &'static str {
    match value {
        Some(TemporalTruthTierV1::Inferred) => "inferred",
        Some(TemporalTruthTierV1::Observed) => "observed",
        Some(TemporalTruthTierV1::Verified) => "verified",
        Some(TemporalTruthTierV1::Authoritative) => "authoritative",
        None => "none",
    }
}

#[cfg(test)]
fn validate_label(field: &str, value: &str) -> CandidateResult<()> {
    if value.is_empty()
        || value.len() > 128
        || !value.is_ascii()
        || !value
            .bytes()
            .next()
            .is_some_and(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit())
        || !value.bytes().all(|byte| {
            byte.is_ascii_lowercase()
                || byte.is_ascii_digit()
                || matches!(byte, b'.' | b'_' | b':' | b'-')
        })
    {
        return Err(candidate_error(
            "track_b_candidate_v1_invalid_label",
            format!("{field} is not a bounded Track B label"),
        ));
    }
    Ok(())
}

#[cfg(test)]
fn validate_case_id(value: &str) -> CandidateResult<()> {
    if value.len() != 37
        || !value.starts_with("case_")
        || !value[5..]
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(candidate_error(
            "track_b_candidate_v1_invalid_case_id",
            "case_id must match the foundational Track B case_[0-9a-f]{32} identity",
        ));
    }
    Ok(())
}

fn validate_sha256(field: &str, value: &str) -> CandidateResult<()> {
    if value.len() != 64
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(candidate_error(
            "track_b_candidate_v1_invalid_sha256",
            format!("{field} must be 64 lowercase hexadecimal characters"),
        ));
    }
    Ok(())
}

fn validate_source_projection(projection: &BoundTemporalTruthProjectionV1) -> CandidateResult<()> {
    if projection.schema() != TEMPORAL_TRUTH_PROJECTION_V1_SCHEMA
        || projection.mode() != TEMPORAL_TRUTH_PROJECTION_V1_MODE
        || projection.producer_profile() != TEMPORAL_TRUTH_PROJECTION_V1_PROFILE
        || projection.mapping_version() != TEMPORAL_TRUTH_PROJECTION_V1_MAPPING
        || projection.synthetic_fixture_id() != "crate_unit_test_only_v0"
        || projection.schema_meta_version() != "43"
        || projection.schema_sha256() != S2_SCHEMA_SHA256
        || projection.migration_sha256() != S2_MIGRATION_SHA256
        || projection.ledger_format_version() != 0
        || projection.canonical_order() != "binary_utf8_v0"
        || !projection.read_only_attested()
        || !projection.query_only_attested()
        || !projection.zero_total_changes_attested()
    {
        return Err(candidate_error(
            "track_b_candidate_v1_source_projection_boundary",
            "source projection did not retain the exact S4 synthetic sealed boundary",
        ));
    }
    for (field, value) in [
        ("schema_sha256", projection.schema_sha256()),
        ("migration_sha256", projection.migration_sha256()),
        (
            "snapshot_payload_sha256",
            projection.snapshot_payload_sha256(),
        ),
        ("prepared_input_sha256", projection.prepared_input_sha256()),
        ("projection_sha256", projection.projection_sha256()),
    ] {
        validate_sha256(field, value)?;
    }
    Ok(())
}

fn validate_request_against_projection(
    request: &TemporalTruthProjectionRequestV1,
    projection: &BoundTemporalTruthProjectionV1,
) -> CandidateResult<()> {
    if request.as_of() != projection.as_of()
        || request.knowledge_cutoff() != projection.knowledge_cutoff()
        || request.limits() != projection.snapshot_limits()
    {
        return Err(candidate_error(
            "track_b_candidate_v1_request_projection_mismatch",
            "request time or limits differ from the sealed S4 projection",
        ));
    }
    Ok(())
}

struct BoundedDigestWriter {
    bytes: usize,
    hasher: Sha256,
    max_bytes: usize,
}

impl BoundedDigestWriter {
    fn new(max_bytes: usize) -> Self {
        Self {
            bytes: 0,
            hasher: Sha256::new(),
            max_bytes,
        }
    }

    fn finish(self) -> String {
        format!("{:x}", self.hasher.finalize())
    }
}

impl Write for BoundedDigestWriter {
    fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
        let next = self
            .bytes
            .checked_add(buffer.len())
            .ok_or_else(|| io::Error::other("digest byte count overflow"))?;
        if next >= self.max_bytes {
            return Err(io::Error::other(format!(
                "digest reached byte sentinel {}",
                self.max_bytes
            )));
        }
        self.hasher.update(buffer);
        self.bytes = next;
        Ok(buffer.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

fn digest_json(value: &impl Serialize, domain: &[u8]) -> CandidateResult<String> {
    let mut writer = BoundedDigestWriter::new(MAX_ENVELOPE_BYTES);
    writer
        .write_all(&(domain.len() as u64).to_be_bytes())
        .and_then(|_| writer.write_all(domain))
        .map_err(|error| candidate_error("track_b_candidate_v1_digest", error.to_string()))?;
    serde_json::to_writer(&mut writer, value)
        .map_err(|error| candidate_error("track_b_candidate_v1_digest", error.to_string()))?;
    Ok(writer.finish())
}

fn request_binding_digest(request: &TemporalTruthProjectionRequestV1) -> CandidateResult<String> {
    let wire = RequestBindingWire {
        as_of: request.as_of(),
        knowledge_cutoff: request.knowledge_cutoff(),
        limits: request.limits().into(),
        required_claims: request
            .required_claims()
            .iter()
            .map(|claim| RequiredClaimWire {
                predicate_id: claim.predicate_id(),
                referent_id: claim.referent_id(),
            })
            .collect(),
    };
    digest_json(&wire, REQUEST_BINDING_DOMAIN)
}

fn update_framed(context: &mut hmac::Context, bytes: &[u8]) {
    context.update(&(bytes.len() as u64).to_be_bytes());
    context.update(bytes);
}

fn hmac_sha256_parts(key_bytes: &[u8], domain: &[u8], parts: &[&[u8]]) -> [u8; 32] {
    let key = hmac::Key::new(hmac::HMAC_SHA256, key_bytes);
    let mut context = hmac::Context::with_key(&key);
    update_framed(&mut context, domain);
    for part in parts {
        update_framed(&mut context, part);
    }
    let tag = context.sign();
    let mut output = [0u8; 32];
    output.copy_from_slice(tag.as_ref());
    output
}

fn bytes_to_hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        use std::fmt::Write as _;
        write!(&mut output, "{byte:02x}").expect("write to String cannot fail");
    }
    output
}

fn derive_handle(prefix: &str, key: &[u8], domain: &[u8], parts: &[&[u8]]) -> String {
    let digest = hmac_sha256_parts(key, domain, parts);
    format!("{prefix}{}", bytes_to_hex(&digest[..HANDLE_DIGEST_BYTES]))
}

fn projection_binding_handle(
    key: &[u8],
    projection: &ProjectionBindingWire,
    request_binding_sha256: &str,
    permit: &SyntheticTrackBCandidateEvidencePermitV1,
) -> CandidateResult<String> {
    let projection_json = serde_json::to_vec(projection).map_err(|error| {
        candidate_error("track_b_candidate_v1_projection_binding", error.to_string())
    })?;
    if projection_json.len() >= MAX_ENVELOPE_BYTES {
        return Err(candidate_error(
            "track_b_candidate_v1_projection_binding_capacity",
            "projection binding reached byte sentinel",
        ));
    }
    Ok(derive_handle(
        "prj_",
        key,
        PROJECTION_HANDLE_DOMAIN,
        &[
            permit.trial_id.as_bytes(),
            permit.contract_sha256.as_bytes(),
            permit.case_id.as_bytes(),
            permit.request_id.as_bytes(),
            &permit.request_nonce,
            request_binding_sha256.as_bytes(),
            &projection_json,
        ],
    ))
}

fn raw_fingerprint(domain: &[u8], parts: &[&[u8]]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update((domain.len() as u64).to_be_bytes());
    hasher.update(domain);
    for part in parts {
        hasher.update((part.len() as u64).to_be_bytes());
        hasher.update(part);
    }
    hasher.finalize().into()
}

fn insert_collision_checked(
    table: &mut BTreeMap<String, [u8; 32]>,
    handle: &str,
    fingerprint: [u8; 32],
) -> CandidateResult<bool> {
    if let Some(previous) = table.get(handle) {
        if previous != &fingerprint {
            return Err(candidate_error(
                "track_b_candidate_v1_handle_collision",
                "different local inputs produced the same request-scoped handle",
            ));
        }
        return Ok(false);
    }
    table.insert(handle.to_string(), fingerprint);
    Ok(true)
}

fn ensure_below_sentinel(field: &str, value: usize, sentinel: usize) -> CandidateResult<()> {
    if value >= sentinel {
        return Err(candidate_error(
            "track_b_candidate_v1_capacity",
            format!("{field} reached sentinel {sentinel}"),
        ));
    }
    Ok(())
}

struct AuthenticatedPayloadWriter {
    bytes: usize,
    hmac: hmac::Context,
    sha256: Sha256,
}

impl AuthenticatedPayloadWriter {
    fn new(key_bytes: &[u8], domain: &[u8], key_id: &[u8]) -> Self {
        let key = hmac::Key::new(hmac::HMAC_SHA256, key_bytes);
        let mut writer = Self {
            bytes: 0,
            hmac: hmac::Context::with_key(&key),
            sha256: Sha256::new(),
        };
        update_framed(&mut writer.hmac, domain);
        update_framed(&mut writer.hmac, key_id);
        writer
    }

    fn finish(self) -> (String, String) {
        let payload_sha256 = format!("{:x}", self.sha256.finalize());
        let hmac_sha256 = bytes_to_hex(self.hmac.sign().as_ref());
        (payload_sha256, hmac_sha256)
    }
}

impl Write for AuthenticatedPayloadWriter {
    fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
        let next = self
            .bytes
            .checked_add(buffer.len())
            .ok_or_else(|| io::Error::other("candidate envelope byte count overflow"))?;
        if next >= MAX_ENVELOPE_BYTES {
            return Err(io::Error::other(format!(
                "candidate envelope reached byte sentinel {MAX_ENVELOPE_BYTES}"
            )));
        }
        self.sha256.update(buffer);
        self.hmac.update(buffer);
        self.bytes = next;
        Ok(buffer.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

/// Consume an exact S4 request/projection pair and bind it to the S5 Track B
/// source schema using request-scoped opaque handles.
///
/// The complete projected claim set must equal the non-empty request allowlist.
/// This intentionally rejects S4 projections containing additional visible
/// claims rather than silently exporting or filtering ambient truth material.
/// The result is not a serializer or transport and satisfies no live binding.
pub fn bind_synthetic_track_b_candidate_evidence_v1(
    permit: SyntheticTrackBCandidateEvidencePermitV1,
    pair: SyntheticTrackBCandidateProjectionPairV1,
    evaluated_at_utc: i64,
) -> CandidateResult<BoundTrackBCandidateEvidenceV1> {
    let SyntheticTrackBCandidateProjectionPairV1 {
        projection,
        request,
    } = pair;
    validate_source_projection(&projection)?;
    validate_request_against_projection(&request, &projection)?;
    let request_binding_sha256 = request_binding_digest(&request)?;
    if request_binding_sha256 != permit.expected_request_binding_sha256 {
        return Err(candidate_error(
            "track_b_candidate_v1_request_mix_and_match",
            "request does not match the permit-bound S4 request",
        ));
    }
    let current_projection = ProjectionBindingWire::from_projection(&projection);
    if current_projection != permit.expected_projection {
        return Err(candidate_error(
            "track_b_candidate_v1_projection_mix_and_match",
            "projection does not match the permit-bound complete S4 tuple",
        ));
    }
    if evaluated_at_utc < permit.issued_at_utc || evaluated_at_utc >= permit.expires_at_utc {
        return Err(candidate_error(
            "track_b_candidate_v1_expired",
            "candidate permit is outside its synthetic validity window",
        ));
    }

    let required_claims: BTreeSet<(&str, &str)> = request
        .required_claims()
        .iter()
        .map(|claim| (claim.referent_id(), claim.predicate_id()))
        .collect();
    if required_claims.is_empty() {
        return Err(candidate_error(
            "track_b_candidate_v1_empty_required_claims",
            "candidate export requires a non-empty exact claim allowlist",
        ));
    }
    ensure_below_sentinel("required_claims", required_claims.len(), MAX_CLAIMS)?;
    let projected_claim_count = projection.claims().len();
    let projected_claims: BTreeSet<(&str, &str)> = projection
        .claims()
        .map(|claim| (claim.referent_id(), claim.predicate_id()))
        .collect();
    if projected_claims != required_claims || projected_claims.len() != projected_claim_count {
        return Err(candidate_error(
            "track_b_candidate_v1_claim_set_mismatch",
            "sealed projection claim set must exactly equal the request allowlist",
        ));
    }

    let projection_binding_handle = projection_binding_handle(
        &permit.handle_key,
        &current_projection,
        &request_binding_sha256,
        &permit,
    )?;
    let request_nonce = bytes_to_hex(&permit.request_nonce);
    let scope_bytes = raw_fingerprint(
        HANDLE_SCOPE_DOMAIN,
        &[
            permit.trial_id.as_bytes(),
            permit.contract_sha256.as_bytes(),
            permit.case_id.as_bytes(),
            permit.request_id.as_bytes(),
            request_nonce.as_bytes(),
            projection_binding_handle.as_bytes(),
        ],
    );

    let mut collision_table = BTreeMap::new();
    let mut claims = Vec::with_capacity(required_claims.len());
    for claim in projection.claims() {
        let referent = claim.referent_id().as_bytes();
        let predicate = claim.predicate_id().as_bytes();
        let claim_handle = derive_handle(
            "clm_",
            &permit.handle_key,
            CLAIM_HANDLE_DOMAIN,
            &[&scope_bytes, referent, predicate],
        );
        let referent_handle = derive_handle(
            "ref_",
            &permit.handle_key,
            REFERENT_HANDLE_DOMAIN,
            &[&scope_bytes, referent],
        );
        let predicate_handle = derive_handle(
            "prd_",
            &permit.handle_key,
            PREDICATE_HANDLE_DOMAIN,
            &[&scope_bytes, predicate],
        );
        for (handle, domain, parts) in [
            (
                claim_handle.as_str(),
                CLAIM_HANDLE_DOMAIN,
                vec![referent, predicate],
            ),
            (
                referent_handle.as_str(),
                REFERENT_HANDLE_DOMAIN,
                vec![referent],
            ),
            (
                predicate_handle.as_str(),
                PREDICATE_HANDLE_DOMAIN,
                vec![predicate],
            ),
        ] {
            insert_collision_checked(
                &mut collision_table,
                handle,
                raw_fingerprint(domain, &parts),
            )?;
        }

        ensure_below_sentinel("values", claim.values().len(), MAX_VALUES_PER_CLAIM)?;
        ensure_below_sentinel(
            "evidence",
            claim.evidence_ids().len(),
            MAX_EVIDENCE_PER_CLAIM,
        )?;
        ensure_below_sentinel(
            "supporting_evidence",
            claim.supporting_evidence_ids().len(),
            MAX_EVIDENCE_PER_CLAIM,
        )?;
        ensure_below_sentinel(
            "shadowed_evidence",
            claim.shadowed_evidence_ids().len(),
            MAX_EVIDENCE_PER_CLAIM,
        )?;
        ensure_below_sentinel(
            "noncurrent_evidence",
            claim.noncurrent_evidence_ids().len(),
            MAX_EVIDENCE_PER_CLAIM,
        )?;
        ensure_below_sentinel(
            "source_bindings",
            claim.source_bindings().len(),
            MAX_SOURCE_BINDINGS_PER_CLAIM,
        )?;

        let mut value_handles = Vec::with_capacity(claim.values().len());
        for value in claim.values() {
            let handle = derive_handle(
                "val_",
                &permit.handle_key,
                VALUE_HANDLE_DOMAIN,
                &[&scope_bytes, claim_handle.as_bytes(), value.as_bytes()],
            );
            if insert_collision_checked(
                &mut collision_table,
                &handle,
                raw_fingerprint(
                    VALUE_HANDLE_DOMAIN,
                    &[claim_handle.as_bytes(), value.as_bytes()],
                ),
            )? {
                value_handles.push(handle);
            }
        }
        value_handles.sort();

        let mut evidence_handles = Vec::with_capacity(claim.evidence_ids().len());
        for evidence_id in claim.evidence_ids() {
            let handle = derive_handle(
                "evd_",
                &permit.handle_key,
                EVIDENCE_HANDLE_DOMAIN,
                &[
                    &scope_bytes,
                    claim_handle.as_bytes(),
                    evidence_id.as_bytes(),
                ],
            );
            if insert_collision_checked(
                &mut collision_table,
                &handle,
                raw_fingerprint(
                    EVIDENCE_HANDLE_DOMAIN,
                    &[claim_handle.as_bytes(), evidence_id.as_bytes()],
                ),
            )? {
                evidence_handles.push(handle);
            }
        }
        evidence_handles.sort();

        let mut supporting_evidence_handles =
            Vec::with_capacity(claim.supporting_evidence_ids().len());
        for evidence_id in claim.supporting_evidence_ids() {
            let handle = derive_handle(
                "evd_",
                &permit.handle_key,
                EVIDENCE_HANDLE_DOMAIN,
                &[
                    &scope_bytes,
                    claim_handle.as_bytes(),
                    evidence_id.as_bytes(),
                ],
            );
            if insert_collision_checked(
                &mut collision_table,
                &handle,
                raw_fingerprint(
                    EVIDENCE_HANDLE_DOMAIN,
                    &[claim_handle.as_bytes(), evidence_id.as_bytes()],
                ),
            )? {
                supporting_evidence_handles.push(handle);
            }
        }
        supporting_evidence_handles.sort();

        let mut source_binding_handles = Vec::with_capacity(claim.source_bindings().len());
        for source in claim.source_bindings() {
            let handle = derive_handle(
                "src_",
                &permit.handle_key,
                SOURCE_HANDLE_DOMAIN,
                &[
                    &scope_bytes,
                    claim_handle.as_bytes(),
                    source.source_key().as_bytes(),
                    source.provenance_sha256().as_bytes(),
                ],
            );
            if insert_collision_checked(
                &mut collision_table,
                &handle,
                raw_fingerprint(
                    SOURCE_HANDLE_DOMAIN,
                    &[
                        claim_handle.as_bytes(),
                        source.source_key().as_bytes(),
                        source.provenance_sha256().as_bytes(),
                    ],
                ),
            )? {
                source_binding_handles.push(handle);
            }
        }
        source_binding_handles.sort();

        let mut model = CandidateClaimBindingModel {
            claim_binding_hmac_sha256: String::new(),
            evidence_count: claim.evidence_ids().len(),
            evidence_handles,
            noncurrent_evidence_count: claim.noncurrent_evidence_ids().len(),
            referent: CandidateReferentModel {
                claim_handle,
                predicate_handle,
                referent_handle,
            },
            shadowed_evidence_count: claim.shadowed_evidence_ids().len(),
            source_binding_handles,
            supporting_evidence_handles,
            temporal_state: claim.temporal_state(),
            truth_state: claim.truth_state(),
            truth_tier: claim.truth_tier(),
            value_handles,
        };
        validate_candidate_claim_model(&model)?;
        let claim_wire = ClaimBindingWire::from_model(&model);
        let claim_json = serde_json::to_vec(&claim_wire).map_err(|error| {
            candidate_error("track_b_candidate_v1_claim_binding", error.to_string())
        })?;
        model.claim_binding_hmac_sha256 = bytes_to_hex(&hmac_sha256_parts(
            &permit.handle_key,
            CLAIM_BINDING_DOMAIN,
            &[&scope_bytes, &claim_json],
        ));
        claims.push(model);
    }
    claims.sort_by(|left, right| {
        (
            left.referent.referent_handle.as_str(),
            left.referent.predicate_handle.as_str(),
            left.referent.claim_handle.as_str(),
        )
            .cmp(&(
                right.referent.referent_handle.as_str(),
                right.referent.predicate_handle.as_str(),
                right.referent.claim_handle.as_str(),
            ))
    });

    let claim_wires = claims.iter().map(ClaimWire::from_model).collect();
    let payload = CandidateEnvelopePayloadWire {
        boundary: BoundaryWire {
            authority_custody_resolved: false,
            biocortex_runtime_influence: false,
            capture_provenance_attested: false,
            contains_raw_evidence_ids: false,
            contains_raw_predicate_ids: false,
            contains_raw_provenance: false,
            contains_raw_referent_ids: false,
            contains_raw_source_bindings: false,
            contains_raw_values: false,
            cross_repository_transport_authorized: false,
            live_binding_satisfied: false,
            physical_privacy_deletion_resolved: false,
            production_profile_active: false,
            side_effects_unlocked: "NONE",
        },
        candidate_evidence_schema_sha256: TRACK_B_CANDIDATE_EVIDENCE_SCHEMA_SHA256,
        candidate_id: CANDIDATE_ID,
        case_id: &permit.case_id,
        claims: claim_wires,
        contract_sha256: &permit.contract_sha256,
        expires_at_utc: permit.expires_at_utc,
        foundational_schema_pack_manifest_sha256: TRACK_B_FOUNDATIONAL_PACK_MANIFEST_SHA256,
        handle_key_id: &permit.handle_key_id,
        handle_profile_id: TRACK_B_CANDIDATE_HANDLE_PROFILE_V1,
        issued_at_utc: permit.issued_at_utc,
        limits: CandidateLimitsWire {
            max_claims: MAX_CLAIMS - 1,
            max_envelope_bytes: MAX_ENVELOPE_BYTES - 1,
            max_evidence_per_claim: MAX_EVIDENCE_PER_CLAIM - 1,
            max_source_bindings_per_claim: MAX_SOURCE_BINDINGS_PER_CLAIM - 1,
            max_ttl_seconds: MAX_TTL_SECONDS - 1,
            max_values_per_claim: MAX_VALUES_PER_CLAIM - 1,
        },
        projection_binding_handle: &projection_binding_handle,
        request_id: &permit.request_id,
        request_nonce: &request_nonce,
        schema: TRACK_B_CANDIDATE_EVIDENCE_V1_SCHEMA,
        trial_id: &permit.trial_id,
        truth_referent_schema_sha256: TRACK_B_TRUTH_REFERENT_SCHEMA_SHA256,
    };
    let mut writer = AuthenticatedPayloadWriter::new(
        &permit.transport_key,
        AUTHENTICATION_DOMAIN.as_bytes(),
        permit.transport_key_id.as_bytes(),
    );
    serde_json::to_writer(&mut writer, &payload).map_err(|error| {
        candidate_error(
            "track_b_candidate_v1_envelope_authentication",
            error.to_string(),
        )
    })?;
    let (payload_sha256, hmac_sha256) = writer.finish();

    Ok(BoundTrackBCandidateEvidenceV1 {
        authentication: CandidateAuthenticationModel {
            hmac_sha256,
            key_id: permit.transport_key_id.clone(),
            payload_sha256,
        },
        case_id: permit.case_id.clone(),
        claims,
        contract_sha256: permit.contract_sha256.clone(),
        expires_at_utc: permit.expires_at_utc,
        handle_key_id: permit.handle_key_id.clone(),
        issued_at_utc: permit.issued_at_utc,
        projection_binding_handle,
        request_id: permit.request_id.clone(),
        request_nonce,
        trial_id: permit.trial_id.clone(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn temporal_truth_candidate_binding_s5_hmac_domain_framing_known_answer() {
        assert_eq!(
            bytes_to_hex(&hmac_sha256_parts(
                &[0x0b; 20],
                b"domain",
                &[b"Hi There", b"v1"]
            )),
            "e679924005dfd5de88551d2f38ffde004f64a06d1665c27ddb084a1fdfc38f37"
        );
        let mut writer = AuthenticatedPayloadWriter::new(&[0x0b; 20], b"domain", b"key-1");
        writer.write_all(br#"{"a":1}"#).unwrap();
        let (payload_sha256, envelope_hmac_sha256) = writer.finish();
        assert_eq!(
            payload_sha256,
            "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"
        );
        assert_eq!(
            envelope_hmac_sha256,
            "aba5e2a84aead0906d267c48663c0b77d3db87e41216383eaf02565496bc4e65"
        );
        let mut substituted = AuthenticatedPayloadWriter::new(&[0x0b; 20], b"domain", b"key-2");
        substituted.write_all(br#"{"a":1}"#).unwrap();
        assert_ne!(substituted.finish().1, envelope_hmac_sha256);
        assert!(ensure_below_sentinel("evidence", 1_023, MAX_EVIDENCE_PER_CLAIM).is_ok());
        assert_eq!(
            ensure_below_sentinel("evidence", 1_024, MAX_EVIDENCE_PER_CLAIM)
                .expect_err("evidence sentinel must reject")
                .code(),
            "track_b_candidate_v1_capacity"
        );
    }
}
