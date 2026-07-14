//! Synthetic-only, one-shot temporal truth projection v1.
//!
//! The complete v43 ledger never leaves `ab-store`: a fresh physical
//! read-only connection loads, maps, projects, and seals one result in the
//! same deferred transaction. The feature is off by default, and its public
//! permit has no safe non-test constructor, so merely compiling the feature
//! cannot expose an arbitrary database path.

use super::*;

use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::fmt;
use std::io::{self, Write};
use std::path::Path;
use std::time::Duration;
use tokio_rusqlite::Connection;

pub const TEMPORAL_TRUTH_PROJECTION_V1_SCHEMA: &str = "agent_bridge.temporal_truth_projection.v1";
pub const TEMPORAL_TRUTH_PROJECTION_V1_MODE: &str = "synthetic_shadow_only";
pub const TEMPORAL_TRUTH_PROJECTION_V1_MAPPING: &str = "sqlite_v43_full_ledger_source_time_v1";
pub const TEMPORAL_TRUTH_PROJECTION_V1_PROFILE: &str =
    "read_only_sqlite_v43_ledger_v0_synthetic_mechanism";

const PREPARED_SCHEMA: &str = "agent_bridge.prepared_temporal_evidence.v1";
const DIGEST_ENCODING: &str = "serde_struct_order_json_v0";
const MAX_PREPARED_DIGEST_BYTES: usize = 64 * 1024 * 1024;
const MAX_PROJECTION_DIGEST_BYTES: usize = 16 * 1024 * 1024;
const MAX_REQUIRED_CLAIMS: usize = 1_024;
const MAX_REQUIRED_CLAIM_BYTES: usize = 256 * 1024;
const SYNTHETIC_FIXTURE_ID: &str = "crate_unit_test_only_v0";

/// Capability for the default-off S4 synthetic projection mechanism.
///
/// Its field is private and it is consumed by the one-shot API. The sole safe
/// constructor is compiled only for store unit tests; production and Bridge
/// code can name the type but cannot construct it.
#[derive(Debug)]
pub struct SyntheticTemporalTruthProjectionPermitV1 {
    _private: (),
}

#[cfg(test)]
pub(super) fn synthetic_projection_permit_v1() -> SyntheticTemporalTruthProjectionPermitV1 {
    SyntheticTemporalTruthProjectionPermitV1 { _private: () }
}

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
#[error("{code}: {detail}")]
pub struct TemporalTruthProjectionV1Error {
    code: String,
    detail: String,
}

impl TemporalTruthProjectionV1Error {
    pub fn code(&self) -> &str {
        &self.code
    }

    pub fn detail(&self) -> &str {
        &self.detail
    }
}

type ProjectionResult<T> = std::result::Result<T, TemporalTruthProjectionV1Error>;

fn projection_error(code: &str, detail: impl Into<String>) -> TemporalTruthProjectionV1Error {
    TemporalTruthProjectionV1Error {
        code: code.to_string(),
        detail: detail.into(),
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TemporalTruthProjectionLimitsV1 {
    max_lineages: usize,
    max_policy_revisions: usize,
    max_evidence_revisions: usize,
    max_relationships: usize,
    max_tombstones: usize,
    max_payload_bytes: usize,
}

impl TemporalTruthProjectionLimitsV1 {
    #[allow(clippy::too_many_arguments)]
    pub fn try_new(
        max_lineages: usize,
        max_policy_revisions: usize,
        max_evidence_revisions: usize,
        max_relationships: usize,
        max_tombstones: usize,
        max_payload_bytes: usize,
    ) -> ProjectionResult<Self> {
        let limits = TemporalEvidenceSnapshotLimits {
            max_lineages,
            max_policy_revisions,
            max_evidence_revisions,
            max_relationships,
            max_tombstones,
            max_payload_bytes,
        };
        limits.validate().map_err(|error| {
            projection_error("truth_projection_v1_snapshot_limit", error.to_string())
        })?;
        Ok(Self {
            max_lineages,
            max_policy_revisions,
            max_evidence_revisions,
            max_relationships,
            max_tombstones,
            max_payload_bytes,
        })
    }

    pub fn max_lineages(&self) -> usize {
        self.max_lineages
    }

    pub fn max_policy_revisions(&self) -> usize {
        self.max_policy_revisions
    }

    pub fn max_evidence_revisions(&self) -> usize {
        self.max_evidence_revisions
    }

    pub fn max_relationships(&self) -> usize {
        self.max_relationships
    }

    pub fn max_tombstones(&self) -> usize {
        self.max_tombstones
    }

    pub fn max_payload_bytes(&self) -> usize {
        self.max_payload_bytes
    }

    fn substrate_limits(self) -> TemporalEvidenceSnapshotLimits {
        TemporalEvidenceSnapshotLimits {
            max_lineages: self.max_lineages,
            max_policy_revisions: self.max_policy_revisions,
            max_evidence_revisions: self.max_evidence_revisions,
            max_relationships: self.max_relationships,
            max_tombstones: self.max_tombstones,
            max_payload_bytes: self.max_payload_bytes,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct TemporalTruthRequiredClaimV1 {
    referent_id: String,
    predicate_id: String,
}

impl TemporalTruthRequiredClaimV1 {
    pub fn try_new(
        referent_id: impl Into<String>,
        predicate_id: impl Into<String>,
    ) -> ProjectionResult<Self> {
        let claim = Self {
            referent_id: referent_id.into(),
            predicate_id: predicate_id.into(),
        };
        validate_projection_label("required_claim.referent_id", &claim.referent_id)?;
        validate_projection_label("required_claim.predicate_id", &claim.predicate_id)?;
        Ok(claim)
    }

    pub fn referent_id(&self) -> &str {
        &self.referent_id
    }

    pub fn predicate_id(&self) -> &str {
        &self.predicate_id
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TemporalTruthProjectionRequestV1 {
    as_of: i64,
    knowledge_cutoff: i64,
    required_claims: Vec<TemporalTruthRequiredClaimV1>,
    limits: TemporalTruthProjectionLimitsV1,
}

impl TemporalTruthProjectionRequestV1 {
    pub fn try_new(
        as_of: i64,
        knowledge_cutoff: i64,
        required_claims: Vec<TemporalTruthRequiredClaimV1>,
        limits: TemporalTruthProjectionLimitsV1,
    ) -> ProjectionResult<Self> {
        if as_of < 0 || knowledge_cutoff < 0 {
            return Err(projection_error(
                "truth_projection_v1_invalid_time",
                format!("as_of={as_of}, knowledge_cutoff={knowledge_cutoff}"),
            ));
        }
        if as_of > knowledge_cutoff {
            return Err(projection_error(
                "truth_projection_v1_invalid_window",
                format!("as_of {as_of} exceeds knowledge_cutoff {knowledge_cutoff}"),
            ));
        }
        if required_claims.len() >= MAX_REQUIRED_CLAIMS {
            return Err(projection_error(
                "truth_projection_v1_required_claim_capacity",
                format!("required claim count reached sentinel {MAX_REQUIRED_CLAIMS}"),
            ));
        }
        let mut claim_bytes = 0usize;
        let mut unique = BTreeSet::new();
        for claim in &required_claims {
            claim_bytes = claim_bytes
                .checked_add(claim.referent_id.len())
                .and_then(|total| total.checked_add(claim.predicate_id.len()))
                .ok_or_else(|| {
                    projection_error(
                        "truth_projection_v1_required_claim_capacity",
                        "required claim byte count overflow",
                    )
                })?;
            if claim_bytes >= MAX_REQUIRED_CLAIM_BYTES {
                return Err(projection_error(
                    "truth_projection_v1_required_claim_capacity",
                    format!("required claim bytes reached sentinel {MAX_REQUIRED_CLAIM_BYTES}"),
                ));
            }
            if !unique.insert((claim.referent_id.as_str(), claim.predicate_id.as_str())) {
                return Err(projection_error(
                    "truth_projection_v1_duplicate_required_claim",
                    format!("{}/{}", claim.referent_id, claim.predicate_id),
                ));
            }
        }
        let mut required_claims = required_claims;
        required_claims.sort();
        Ok(Self {
            as_of,
            knowledge_cutoff,
            required_claims,
            limits,
        })
    }

    pub fn as_of(&self) -> i64 {
        self.as_of
    }

    pub fn knowledge_cutoff(&self) -> i64 {
        self.knowledge_cutoff
    }

    pub fn required_claims(&self) -> &[TemporalTruthRequiredClaimV1] {
        &self.required_claims
    }

    pub fn limits(&self) -> TemporalTruthProjectionLimitsV1 {
        self.limits
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TemporalTruthTierV1 {
    Inferred,
    Observed,
    Verified,
    Authoritative,
}

impl TemporalTruthTierV1 {
    fn from_substrate(value: TruthTier) -> Self {
        match value {
            TruthTier::Inferred => Self::Inferred,
            TruthTier::Observed => Self::Observed,
            TruthTier::Verified => Self::Verified,
            TruthTier::Authoritative => Self::Authoritative,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TemporalTruthStateV1 {
    Supported,
    Conflicted,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TemporalTruthTemporalStateV1 {
    Current,
    Historical,
    Future,
    Indeterminate,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TemporalTruthSuppressionKindV1 {
    Supersedes,
    Invalidates,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TemporalTruthDispositionReasonKindV1 {
    Active,
    NotYetValid,
    ValidityExpired,
    IndeterminateValidity,
    LifecycleSuperseded,
    LifecycleArchived,
    Suppressed,
}

impl TemporalTruthSuppressionKindV1 {
    fn from_substrate(value: RelationshipKind) -> Self {
        match value {
            RelationshipKind::Supersedes => Self::Supersedes,
            RelationshipKind::Invalidates => Self::Invalidates,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
enum DispositionReasonModel {
    Active,
    NotYetValid {
        valid_from: i64,
    },
    ValidityExpired {
        valid_until: i64,
    },
    IndeterminateValidity,
    LifecycleSuperseded {
        effective_from: i64,
    },
    LifecycleArchived {
        effective_from: i64,
    },
    SupersededBy {
        source_id: String,
        effective_from: i64,
    },
    InvalidatedBy {
        source_id: String,
        effective_from: i64,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
struct EvidenceDispositionModel {
    evidence_id: String,
    temporal_state: TemporalTruthTemporalStateV1,
    reasons: Vec<DispositionReasonModel>,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
struct SourceBindingModel {
    source_key: String,
    provenance_sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
struct ProjectedClaimModel {
    aliases: Vec<String>,
    evidence_dispositions: Vec<EvidenceDispositionModel>,
    evidence_ids: Vec<String>,
    noncurrent_evidence_ids: Vec<String>,
    predicate_id: String,
    referent_id: String,
    shadowed_evidence_ids: Vec<String>,
    source_bindings: Vec<SourceBindingModel>,
    supporting_evidence_ids: Vec<String>,
    temporal_state: TemporalTruthTemporalStateV1,
    truth_state: TemporalTruthStateV1,
    truth_tier: Option<TemporalTruthTierV1>,
    values: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
struct EvidenceProvenanceModel {
    evidence_id: String,
    source_bindings: Vec<SourceBindingModel>,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
struct AuthorityBasisModel {
    source_evidence_id: String,
    source_recorded_at: i64,
    target_evidence_id: String,
    target_lineage_id: String,
    target_recorded_at: i64,
    target_revision_seq: i64,
    target_truth_tier: TemporalTruthTierV1,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
struct ProjectionModel {
    as_of: i64,
    authority_bases: Vec<AuthorityBasisModel>,
    claims: Vec<ProjectedClaimModel>,
    evidence_provenance: Vec<EvidenceProvenanceModel>,
    knowledge_cutoff: i64,
    mode: &'static str,
    schema: &'static str,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TemporalTruthSnapshotCountsV1 {
    lineages: usize,
    policy_revisions: usize,
    evidence_revisions: usize,
    relationships: usize,
    tombstones: usize,
}

impl TemporalTruthSnapshotCountsV1 {
    pub fn lineages(&self) -> usize {
        self.lineages
    }
    pub fn policy_revisions(&self) -> usize {
        self.policy_revisions
    }
    pub fn evidence_revisions(&self) -> usize {
        self.evidence_revisions
    }
    pub fn relationships(&self) -> usize {
        self.relationships
    }
    pub fn tombstones(&self) -> usize {
        self.tombstones
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct BindingModel {
    as_of: i64,
    canonical_order: &'static str,
    knowledge_cutoff: i64,
    ledger_format_version: u32,
    mapping_version: &'static str,
    migration_sha256: String,
    prepared_input_sha256: String,
    producer_profile: &'static str,
    projection_sha256: String,
    pruned_inbound_relationships: usize,
    query_only_attested: bool,
    read_only_attested: bool,
    schema_meta_version: String,
    schema_sha256: String,
    snapshot_counts: TemporalTruthSnapshotCountsV1,
    snapshot_limits: TemporalTruthProjectionLimitsV1,
    snapshot_payload_bytes: usize,
    snapshot_payload_sha256: String,
    synthetic_fixture_id: &'static str,
    zero_total_changes_attested: bool,
}

/// Field-private, non-serializable result of one atomic read/map/project call.
#[must_use]
pub struct BoundTemporalTruthProjectionV1 {
    binding: BindingModel,
    projection: ProjectionModel,
}

impl fmt::Debug for BoundTemporalTruthProjectionV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("BoundTemporalTruthProjectionV1")
            .field("schema", &self.projection.schema)
            .field("mode", &self.projection.mode)
            .field(
                "snapshot_payload_sha256",
                &self.binding.snapshot_payload_sha256,
            )
            .field("prepared_input_sha256", &self.binding.prepared_input_sha256)
            .field("projection_sha256", &self.binding.projection_sha256)
            .field("claim_count", &self.projection.claims.len())
            .finish_non_exhaustive()
    }
}

impl BoundTemporalTruthProjectionV1 {
    pub fn schema(&self) -> &str {
        self.projection.schema
    }
    pub fn mode(&self) -> &str {
        self.projection.mode
    }
    pub fn producer_profile(&self) -> &str {
        self.binding.producer_profile
    }
    pub fn mapping_version(&self) -> &str {
        self.binding.mapping_version
    }
    pub fn schema_meta_version(&self) -> &str {
        &self.binding.schema_meta_version
    }
    pub fn schema_sha256(&self) -> &str {
        &self.binding.schema_sha256
    }
    pub fn migration_sha256(&self) -> &str {
        &self.binding.migration_sha256
    }
    pub fn ledger_format_version(&self) -> u32 {
        self.binding.ledger_format_version
    }
    pub fn canonical_order(&self) -> &str {
        self.binding.canonical_order
    }
    pub fn as_of(&self) -> i64 {
        self.binding.as_of
    }
    pub fn knowledge_cutoff(&self) -> i64 {
        self.binding.knowledge_cutoff
    }
    pub fn snapshot_counts(&self) -> TemporalTruthSnapshotCountsV1 {
        self.binding.snapshot_counts
    }
    pub fn snapshot_limits(&self) -> TemporalTruthProjectionLimitsV1 {
        self.binding.snapshot_limits
    }
    pub fn snapshot_payload_bytes(&self) -> usize {
        self.binding.snapshot_payload_bytes
    }
    pub fn snapshot_payload_sha256(&self) -> &str {
        &self.binding.snapshot_payload_sha256
    }
    pub fn prepared_input_sha256(&self) -> &str {
        &self.binding.prepared_input_sha256
    }
    pub fn projection_sha256(&self) -> &str {
        &self.binding.projection_sha256
    }
    pub fn synthetic_fixture_id(&self) -> &str {
        self.binding.synthetic_fixture_id
    }
    pub fn read_only_attested(&self) -> bool {
        self.binding.read_only_attested
    }
    pub fn query_only_attested(&self) -> bool {
        self.binding.query_only_attested
    }
    pub fn zero_total_changes_attested(&self) -> bool {
        self.binding.zero_total_changes_attested
    }
    pub fn pruned_inbound_relationships(&self) -> usize {
        self.binding.pruned_inbound_relationships
    }
    pub fn claims(&self) -> impl ExactSizeIterator<Item = TemporalTruthProjectedClaimViewV1<'_>> {
        self.projection
            .claims
            .iter()
            .map(|model| TemporalTruthProjectedClaimViewV1 { model })
    }
    pub fn evidence_provenance(
        &self,
    ) -> impl ExactSizeIterator<Item = TemporalTruthEvidenceProvenanceViewV1<'_>> {
        self.projection
            .evidence_provenance
            .iter()
            .map(|model| TemporalTruthEvidenceProvenanceViewV1 { model })
    }
    pub fn authority_bases(
        &self,
    ) -> impl ExactSizeIterator<Item = TemporalTruthAuthorityBasisViewV1<'_>> {
        self.projection
            .authority_bases
            .iter()
            .map(|model| TemporalTruthAuthorityBasisViewV1 { model })
    }
}

#[derive(Clone, Copy)]
pub struct TemporalTruthProjectedClaimViewV1<'a> {
    model: &'a ProjectedClaimModel,
}

impl<'a> TemporalTruthProjectedClaimViewV1<'a> {
    pub fn referent_id(&self) -> &'a str {
        &self.model.referent_id
    }
    pub fn predicate_id(&self) -> &'a str {
        &self.model.predicate_id
    }
    pub fn aliases(&self) -> &'a [String] {
        &self.model.aliases
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
    pub fn values(&self) -> &'a [String] {
        &self.model.values
    }
    pub fn evidence_ids(&self) -> &'a [String] {
        &self.model.evidence_ids
    }
    pub fn supporting_evidence_ids(&self) -> &'a [String] {
        &self.model.supporting_evidence_ids
    }
    pub fn shadowed_evidence_ids(&self) -> &'a [String] {
        &self.model.shadowed_evidence_ids
    }
    pub fn noncurrent_evidence_ids(&self) -> &'a [String] {
        &self.model.noncurrent_evidence_ids
    }
    pub fn source_bindings(
        &self,
    ) -> impl ExactSizeIterator<Item = TemporalTruthSourceBindingViewV1<'a>> + 'a {
        self.model
            .source_bindings
            .iter()
            .map(|model| TemporalTruthSourceBindingViewV1 { model })
    }
    pub fn evidence_dispositions(
        &self,
    ) -> impl ExactSizeIterator<Item = TemporalTruthEvidenceDispositionViewV1<'a>> + 'a {
        self.model
            .evidence_dispositions
            .iter()
            .map(|model| TemporalTruthEvidenceDispositionViewV1 { model })
    }
}

#[derive(Clone, Copy)]
pub struct TemporalTruthSourceBindingViewV1<'a> {
    model: &'a SourceBindingModel,
}

impl<'a> TemporalTruthSourceBindingViewV1<'a> {
    pub fn source_key(&self) -> &'a str {
        &self.model.source_key
    }
    pub fn provenance_sha256(&self) -> &'a str {
        &self.model.provenance_sha256
    }
}

#[derive(Clone, Copy)]
pub struct TemporalTruthEvidenceProvenanceViewV1<'a> {
    model: &'a EvidenceProvenanceModel,
}

impl<'a> TemporalTruthEvidenceProvenanceViewV1<'a> {
    pub fn evidence_id(&self) -> &'a str {
        &self.model.evidence_id
    }
    pub fn source_bindings(
        &self,
    ) -> impl ExactSizeIterator<Item = TemporalTruthSourceBindingViewV1<'a>> + 'a {
        self.model
            .source_bindings
            .iter()
            .map(|model| TemporalTruthSourceBindingViewV1 { model })
    }
}

#[derive(Clone, Copy)]
pub struct TemporalTruthAuthorityBasisViewV1<'a> {
    model: &'a AuthorityBasisModel,
}

impl<'a> TemporalTruthAuthorityBasisViewV1<'a> {
    pub fn source_evidence_id(&self) -> &'a str {
        &self.model.source_evidence_id
    }
    pub fn source_recorded_at(&self) -> i64 {
        self.model.source_recorded_at
    }
    pub fn target_lineage_id(&self) -> &'a str {
        &self.model.target_lineage_id
    }
    pub fn target_evidence_id(&self) -> &'a str {
        &self.model.target_evidence_id
    }
    pub fn target_revision_seq(&self) -> i64 {
        self.model.target_revision_seq
    }
    pub fn target_recorded_at(&self) -> i64 {
        self.model.target_recorded_at
    }
    pub fn target_truth_tier(&self) -> TemporalTruthTierV1 {
        self.model.target_truth_tier
    }
}

#[derive(Clone, Copy)]
pub struct TemporalTruthEvidenceDispositionViewV1<'a> {
    model: &'a EvidenceDispositionModel,
}

impl<'a> TemporalTruthEvidenceDispositionViewV1<'a> {
    pub fn evidence_id(&self) -> &'a str {
        &self.model.evidence_id
    }
    pub fn temporal_state(&self) -> TemporalTruthTemporalStateV1 {
        self.model.temporal_state
    }
    pub fn reason_count(&self) -> usize {
        self.model.reasons.len()
    }
    pub fn reasons(
        &self,
    ) -> impl ExactSizeIterator<Item = TemporalTruthDispositionReasonViewV1<'a>> + 'a {
        self.model
            .reasons
            .iter()
            .map(|model| TemporalTruthDispositionReasonViewV1 { model })
    }
}

#[derive(Clone, Copy)]
pub struct TemporalTruthDispositionReasonViewV1<'a> {
    model: &'a DispositionReasonModel,
}

impl<'a> TemporalTruthDispositionReasonViewV1<'a> {
    pub fn kind(&self) -> TemporalTruthDispositionReasonKindV1 {
        match self.model {
            DispositionReasonModel::Active => TemporalTruthDispositionReasonKindV1::Active,
            DispositionReasonModel::NotYetValid { .. } => {
                TemporalTruthDispositionReasonKindV1::NotYetValid
            }
            DispositionReasonModel::ValidityExpired { .. } => {
                TemporalTruthDispositionReasonKindV1::ValidityExpired
            }
            DispositionReasonModel::IndeterminateValidity => {
                TemporalTruthDispositionReasonKindV1::IndeterminateValidity
            }
            DispositionReasonModel::LifecycleSuperseded { .. } => {
                TemporalTruthDispositionReasonKindV1::LifecycleSuperseded
            }
            DispositionReasonModel::LifecycleArchived { .. } => {
                TemporalTruthDispositionReasonKindV1::LifecycleArchived
            }
            DispositionReasonModel::SupersededBy { .. }
            | DispositionReasonModel::InvalidatedBy { .. } => {
                TemporalTruthDispositionReasonKindV1::Suppressed
            }
        }
    }

    pub fn suppression_kind(&self) -> Option<TemporalTruthSuppressionKindV1> {
        match self.model {
            DispositionReasonModel::SupersededBy { .. } => {
                Some(TemporalTruthSuppressionKindV1::Supersedes)
            }
            DispositionReasonModel::InvalidatedBy { .. } => {
                Some(TemporalTruthSuppressionKindV1::Invalidates)
            }
            _ => None,
        }
    }

    pub fn source_evidence_id(&self) -> Option<&'a str> {
        match self.model {
            DispositionReasonModel::SupersededBy { source_id, .. }
            | DispositionReasonModel::InvalidatedBy { source_id, .. } => Some(source_id),
            _ => None,
        }
    }

    pub fn effective_from(&self) -> Option<i64> {
        match self.model {
            DispositionReasonModel::LifecycleSuperseded { effective_from }
            | DispositionReasonModel::LifecycleArchived { effective_from }
            | DispositionReasonModel::SupersededBy { effective_from, .. }
            | DispositionReasonModel::InvalidatedBy { effective_from, .. } => Some(*effective_from),
            _ => None,
        }
    }

    pub fn validity_boundary(&self) -> Option<i64> {
        match self.model {
            DispositionReasonModel::NotYetValid { valid_from } => Some(*valid_from),
            DispositionReasonModel::ValidityExpired { valid_until } => Some(*valid_until),
            _ => None,
        }
    }
}

#[derive(Debug)]
struct PreparedEvidenceV1<'a> {
    lineage: &'a TruthLineageRow,
    revision: &'a EvidenceRevisionRow,
    relationships: Vec<&'a EvidenceRelationshipRow>,
}

#[derive(Debug)]
struct PreparedTemporalEvidenceV1<'a> {
    snapshot: &'a TemporalEvidenceSnapshot,
    evidence: Vec<PreparedEvidenceV1<'a>>,
    tombstones: Vec<&'a LineageTombstoneRow>,
    authority_bases: Vec<AuthorityBasisModel>,
    pruned_inbound_relationships: usize,
}

#[derive(Serialize)]
struct RequiredClaimWire<'a> {
    predicate_id: &'a str,
    referent_id: &'a str,
}

#[derive(Serialize)]
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
            max_evidence_revisions: value.max_evidence_revisions,
            max_lineages: value.max_lineages,
            max_payload_bytes: value.max_payload_bytes,
            max_policy_revisions: value.max_policy_revisions,
            max_relationships: value.max_relationships,
            max_tombstones: value.max_tombstones,
        }
    }
}

#[derive(Serialize)]
struct ProjectionRequestWire<'a> {
    as_of: i64,
    knowledge_cutoff: i64,
    limits: ProjectionLimitsWire,
    required_claims: Vec<RequiredClaimWire<'a>>,
}

#[derive(Serialize)]
struct PreparedEvidenceWire<'a> {
    lineage: &'a TruthLineageRow,
    relationships: &'a Vec<&'a EvidenceRelationshipRow>,
    revision: &'a EvidenceRevisionRow,
}

#[derive(Serialize)]
struct PreparedInputWire<'a> {
    authority_bases: &'a [AuthorityBasisModel],
    authority_policies: &'a [AuthorityPolicyRevisionRow],
    canonical_order: &'static str,
    digest_encoding: &'static str,
    evidence: Vec<PreparedEvidenceWire<'a>>,
    fixture_id: &'static str,
    ledger_format_version: u32,
    mapping_version: &'static str,
    prepared_schema: &'static str,
    producer_identity: &'a TemporalEvidenceProducerIdentity,
    pruned_inbound_relationships: usize,
    request: ProjectionRequestWire<'a>,
    snapshot_counts: TemporalEvidenceSnapshotCounts,
    snapshot_limits: TemporalEvidenceSnapshotLimits,
    snapshot_payload_bytes: usize,
    snapshot_payload_sha256: &'a str,
    tombstones: &'a Vec<&'a LineageTombstoneRow>,
}

struct BoundedProjectionDigestWriter {
    hasher: Sha256,
    bytes: usize,
    max_bytes: usize,
}

impl BoundedProjectionDigestWriter {
    fn new(max_bytes: usize) -> Self {
        Self {
            hasher: Sha256::new(),
            bytes: 0,
            max_bytes,
        }
    }

    fn finish(self) -> (usize, String) {
        (self.bytes, format!("{:x}", self.hasher.finalize()))
    }
}

impl Write for BoundedProjectionDigestWriter {
    fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
        let next = self
            .bytes
            .checked_add(buffer.len())
            .ok_or_else(|| io::Error::other("projection digest byte count overflow"))?;
        if next >= self.max_bytes {
            return Err(io::Error::other(format!(
                "projection digest reached byte sentinel {}",
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

fn bounded_projection_digest<T: Serialize>(
    value: &T,
    max_bytes: usize,
    code: &str,
) -> ProjectionResult<(usize, String)> {
    let mut writer = BoundedProjectionDigestWriter::new(max_bytes);
    serde_json::to_writer(&mut writer, value)
        .map_err(|error| projection_error(code, error.to_string()))?;
    Ok(writer.finish())
}

fn validate_projection_label(field: &str, value: &str) -> ProjectionResult<()> {
    if value.is_empty()
        || value.len() > MAX_LABEL_BYTES
        || value.trim() != value
        || !value.is_ascii()
        || value.bytes().any(|byte| byte < 32 || byte == 127)
    {
        return Err(projection_error(
            "truth_projection_v1_invalid_label",
            format!("{field} is not a bounded printable ASCII label"),
        ));
    }
    Ok(())
}

fn prepare_snapshot_v1(
    snapshot: &TemporalEvidenceSnapshot,
) -> ProjectionResult<PreparedTemporalEvidenceV1<'_>> {
    if let Some(tombstone) = snapshot
        .tombstones
        .iter()
        .find(|tombstone| tombstone.had_outgoing_governance)
    {
        return Err(projection_error(
            "truth_projection_v1_governed_tombstone_source",
            format!(
                "tombstoned lineage {} carried outgoing governance",
                tombstone.lineage_id
            ),
        ));
    }

    let tombstoned: HashSet<&str> = snapshot
        .tombstones
        .iter()
        .map(|tombstone| tombstone.lineage_id.as_str())
        .collect();
    let lineage_by_id: HashMap<&str, &TruthLineageRow> = snapshot
        .lineages
        .iter()
        .map(|lineage| (lineage.lineage_id.as_str(), lineage))
        .collect();
    let mut revisions_by_lineage: BTreeMap<&str, Vec<&EvidenceRevisionRow>> = BTreeMap::new();
    for revision in &snapshot.revisions {
        revisions_by_lineage
            .entry(revision.lineage_id.as_str())
            .or_default()
            .push(revision);
    }
    let mut relationships_by_evidence: HashMap<&str, Vec<&EvidenceRelationshipRow>> =
        HashMap::new();
    for relationship in &snapshot.relationships {
        relationships_by_evidence
            .entry(relationship.declared_evidence_id.as_str())
            .or_default()
            .push(relationship);
    }

    let mut evidence = Vec::with_capacity(snapshot.revisions.len());
    let mut authority_bases = Vec::with_capacity(snapshot.relationships.len());
    let mut pruned_inbound_relationships = 0usize;
    for revision in &snapshot.revisions {
        if tombstoned.contains(revision.lineage_id.as_str()) {
            continue;
        }
        let lineage = lineage_by_id
            .get(revision.lineage_id.as_str())
            .copied()
            .ok_or_else(|| {
                projection_error(
                    "truth_projection_v1_missing_lineage",
                    revision.lineage_id.clone(),
                )
            })?;
        let mut retained_relationships = Vec::new();
        for relationship in relationships_by_evidence
            .get(revision.evidence_id.as_str())
            .into_iter()
            .flatten()
            .copied()
        {
            if tombstoned.contains(relationship.target_lineage_id.as_str()) {
                pruned_inbound_relationships =
                    pruned_inbound_relationships.checked_add(1).ok_or_else(|| {
                        projection_error(
                            "truth_projection_v1_relationship_capacity",
                            "pruned relationship count overflow",
                        )
                    })?;
                continue;
            }
            let target_revisions = revisions_by_lineage
                .get(relationship.target_lineage_id.as_str())
                .ok_or_else(|| {
                    projection_error(
                        "truth_projection_v1_missing_relationship_target",
                        relationship.target_lineage_id.clone(),
                    )
                })?;
            if target_revisions
                .iter()
                .any(|target| target.recorded_at == revision.recorded_at)
            {
                return Err(projection_error(
                    "truth_projection_v1_same_second_target_ambiguity",
                    relationship.target_lineage_id.clone(),
                ));
            }
            let target = target_revisions
                .iter()
                .rev()
                .find(|target| target.recorded_at < revision.recorded_at)
                .copied()
                .ok_or_else(|| {
                    projection_error(
                        "truth_projection_v1_missing_source_time_basis",
                        format!(
                            "{} -> {}",
                            revision.evidence_id, relationship.target_lineage_id
                        ),
                    )
                })?;
            if revision.resolved_truth_tier.rank() < target.resolved_truth_tier.rank() {
                return Err(projection_error(
                    "truth_projection_v1_insufficient_source_time_authority",
                    format!(
                        "{} -> {}",
                        revision.evidence_id, relationship.target_lineage_id
                    ),
                ));
            }
            authority_bases.push(AuthorityBasisModel {
                source_evidence_id: revision.evidence_id.clone(),
                source_recorded_at: revision.recorded_at,
                target_evidence_id: target.evidence_id.clone(),
                target_lineage_id: target.lineage_id.clone(),
                target_recorded_at: target.recorded_at,
                target_revision_seq: target.revision_seq,
                target_truth_tier: TemporalTruthTierV1::from_substrate(target.resolved_truth_tier),
            });
            retained_relationships.push(relationship);
        }
        evidence.push(PreparedEvidenceV1 {
            lineage,
            revision,
            relationships: retained_relationships,
        });
    }
    authority_bases.sort();
    authority_bases.dedup();

    Ok(PreparedTemporalEvidenceV1 {
        snapshot,
        evidence,
        tombstones: snapshot.tombstones.iter().collect(),
        authority_bases,
        pruned_inbound_relationships,
    })
}

fn prepared_input_digest_v1(
    prepared: &PreparedTemporalEvidenceV1<'_>,
    request: &TemporalTruthProjectionRequestV1,
    fixture_id: &'static str,
) -> ProjectionResult<String> {
    let evidence = prepared
        .evidence
        .iter()
        .map(|item| PreparedEvidenceWire {
            lineage: item.lineage,
            relationships: &item.relationships,
            revision: item.revision,
        })
        .collect();
    let request_wire = ProjectionRequestWire {
        as_of: request.as_of,
        knowledge_cutoff: request.knowledge_cutoff,
        limits: request.limits.into(),
        required_claims: request
            .required_claims
            .iter()
            .map(|claim| RequiredClaimWire {
                predicate_id: &claim.predicate_id,
                referent_id: &claim.referent_id,
            })
            .collect(),
    };
    let snapshot = prepared.snapshot;
    let wire = PreparedInputWire {
        authority_bases: &prepared.authority_bases,
        authority_policies: &snapshot.authority_policies,
        canonical_order: snapshot.canonical_order,
        digest_encoding: DIGEST_ENCODING,
        evidence,
        fixture_id,
        ledger_format_version: snapshot.ledger_format_version,
        mapping_version: TEMPORAL_TRUTH_PROJECTION_V1_MAPPING,
        prepared_schema: PREPARED_SCHEMA,
        producer_identity: &snapshot.producer_identity,
        pruned_inbound_relationships: prepared.pruned_inbound_relationships,
        request: request_wire,
        snapshot_counts: snapshot.counts,
        snapshot_limits: snapshot.limits,
        snapshot_payload_bytes: snapshot.payload_bytes,
        snapshot_payload_sha256: &snapshot.payload_sha256,
        tombstones: &prepared.tombstones,
    };
    bounded_projection_digest(
        &wire,
        MAX_PREPARED_DIGEST_BYTES,
        "truth_projection_v1_prepared_digest",
    )
    .map(|(_, digest)| digest)
}

fn select_visible_revisions_v1<'a, 'snapshot>(
    prepared: &'a PreparedTemporalEvidenceV1<'snapshot>,
    knowledge_cutoff: i64,
) -> BTreeMap<String, &'a PreparedEvidenceV1<'snapshot>> {
    let mut visible = BTreeMap::new();
    for item in &prepared.evidence {
        if item.revision.recorded_at > knowledge_cutoff {
            continue;
        }
        match visible.entry(item.revision.lineage_id.clone()) {
            std::collections::btree_map::Entry::Vacant(entry) => {
                entry.insert(item);
            }
            std::collections::btree_map::Entry::Occupied(mut entry) => {
                let previous: &&PreparedEvidenceV1<'_> = entry.get();
                if (
                    previous.revision.recorded_at,
                    previous.revision.revision_seq,
                ) < (item.revision.recorded_at, item.revision.revision_seq)
                {
                    entry.insert(item);
                }
            }
        }
    }
    visible
}

fn validate_visible_aliases_v1(
    visible: &BTreeMap<String, &PreparedEvidenceV1<'_>>,
    required: &[TemporalTruthRequiredClaimV1],
) -> ProjectionResult<()> {
    let mut owners: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for claim in required {
        owners
            .entry(claim.referent_id.to_ascii_lowercase())
            .or_default()
            .insert(claim.referent_id.clone());
    }
    for item in visible.values() {
        owners
            .entry(item.lineage.referent_id.to_ascii_lowercase())
            .or_default()
            .insert(item.lineage.referent_id.clone());
        for alias in &item.revision.aliases {
            owners
                .entry(alias.to_ascii_lowercase())
                .or_default()
                .insert(item.lineage.referent_id.clone());
        }
    }
    if let Some((alias, referents)) = owners.into_iter().find(|(_, owners)| owners.len() > 1) {
        return Err(projection_error(
            "truth_projection_v1_alias_collision",
            format!("{alias:?} maps to {referents:?}"),
        ));
    }
    Ok(())
}

fn authority_basis_index_v1<'a>(
    prepared: &'a PreparedTemporalEvidenceV1<'_>,
) -> HashMap<(&'a str, &'a str), &'a AuthorityBasisModel> {
    prepared
        .authority_bases
        .iter()
        .map(|basis| {
            (
                (
                    basis.source_evidence_id.as_str(),
                    basis.target_lineage_id.as_str(),
                ),
                basis,
            )
        })
        .collect()
}

fn derive_suppression_v1(
    visible: &BTreeMap<String, &PreparedEvidenceV1<'_>>,
    authority_bases: &HashMap<(&str, &str), &AuthorityBasisModel>,
    as_of: i64,
) -> ProjectionResult<BTreeMap<String, Vec<DispositionReasonModel>>> {
    let mut edges: BTreeMap<String, BTreeMap<String, (RelationshipKind, i64)>> = visible
        .keys()
        .map(|lineage_id| (lineage_id.clone(), BTreeMap::new()))
        .collect();
    let mut indegree: BTreeMap<String, usize> = visible
        .keys()
        .map(|lineage_id| (lineage_id.clone(), 0usize))
        .collect();

    for (source_lineage_id, source) in visible {
        for relationship in &source.relationships {
            let target_lineage_id = relationship.target_lineage_id.as_str();
            if target_lineage_id == source_lineage_id {
                return Err(projection_error(
                    "truth_projection_v1_self_relationship",
                    source.revision.evidence_id.clone(),
                ));
            }
            let target = visible.get(target_lineage_id).ok_or_else(|| {
                projection_error(
                    "truth_projection_v1_dangling_visible_relationship",
                    format!("{} -> {target_lineage_id}", source.revision.evidence_id),
                )
            })?;
            if source.lineage.referent_id != target.lineage.referent_id
                || source.lineage.predicate_id != target.lineage.predicate_id
            {
                return Err(projection_error(
                    "truth_projection_v1_cross_claim_relationship",
                    format!("{} -> {target_lineage_id}", source.revision.evidence_id),
                ));
            }

            // Deliberately do not compare against the cutoff-visible target
            // tier. Authority is bound to the target revision strictly before
            // the source's recorded_at in the complete validated snapshot.
            let basis = authority_bases
                .get(&(source.revision.evidence_id.as_str(), target_lineage_id))
                .copied()
                .ok_or_else(|| {
                    projection_error(
                        "truth_projection_v1_unbound_relationship_authority",
                        format!("{} -> {target_lineage_id}", source.revision.evidence_id),
                    )
                })?;
            if basis.source_recorded_at != source.revision.recorded_at
                || basis.target_recorded_at >= basis.source_recorded_at
            {
                return Err(projection_error(
                    "truth_projection_v1_invalid_relationship_authority_basis",
                    format!("{} -> {target_lineage_id}", source.revision.evidence_id),
                ));
            }

            let source_edges = edges
                .get_mut(source_lineage_id)
                .expect("visible source has an edge row");
            if let Some((previous_kind, previous_time)) = source_edges.insert(
                target_lineage_id.to_string(),
                (relationship.relationship_kind, relationship.effective_from),
            ) {
                if previous_kind != relationship.relationship_kind
                    || previous_time != relationship.effective_from
                {
                    return Err(projection_error(
                        "truth_projection_v1_conflicting_relationship",
                        format!("{} -> {target_lineage_id}", source.revision.evidence_id),
                    ));
                }
            } else {
                *indegree
                    .get_mut(target_lineage_id)
                    .expect("visible relationship target has indegree row") += 1;
            }
        }
    }

    let mut ready: BTreeSet<String> = indegree
        .iter()
        .filter_map(|(lineage_id, degree)| (*degree == 0).then_some(lineage_id.clone()))
        .collect();
    let mut topological_order = Vec::with_capacity(visible.len());
    while let Some(lineage_id) = ready.pop_first() {
        topological_order.push(lineage_id.clone());
        for target in edges
            .get(&lineage_id)
            .into_iter()
            .flat_map(|targets| targets.keys())
        {
            let degree = indegree
                .get_mut(target)
                .expect("edge target has indegree row");
            *degree -= 1;
            if *degree == 0 {
                ready.insert(target.clone());
            }
        }
    }
    if topological_order.len() != visible.len() {
        return Err(projection_error(
            "truth_projection_v1_relationship_cycle",
            "visible relationship graph is cyclic",
        ));
    }

    let mut suppressed_at: BTreeMap<String, (i64, Vec<DispositionReasonModel>)> = BTreeMap::new();
    for source_lineage_id in topological_order {
        let source_suppressed_at = suppressed_at
            .get(&source_lineage_id)
            .map(|(timestamp, _)| *timestamp);
        let source_evidence_id = &visible[&source_lineage_id].revision.evidence_id;
        for (target_lineage_id, (kind, effective_from)) in &edges[&source_lineage_id] {
            if source_suppressed_at.is_none_or(|timestamp| *effective_from < timestamp) {
                let reason = match kind {
                    RelationshipKind::Supersedes => DispositionReasonModel::SupersededBy {
                        source_id: source_evidence_id.clone(),
                        effective_from: *effective_from,
                    },
                    RelationshipKind::Invalidates => DispositionReasonModel::InvalidatedBy {
                        source_id: source_evidence_id.clone(),
                        effective_from: *effective_from,
                    },
                };
                match suppressed_at.entry(target_lineage_id.clone()) {
                    std::collections::btree_map::Entry::Vacant(entry) => {
                        entry.insert((*effective_from, vec![reason]));
                    }
                    std::collections::btree_map::Entry::Occupied(mut entry) => {
                        let (earliest, reasons) = entry.get_mut();
                        if *effective_from < *earliest {
                            *earliest = *effective_from;
                            *reasons = vec![reason];
                        } else if *effective_from == *earliest && !reasons.contains(&reason) {
                            reasons.push(reason);
                            reasons.sort();
                        }
                    }
                }
            }
        }
    }

    Ok(suppressed_at
        .into_iter()
        .filter_map(|(lineage_id, (effective_from, reasons))| {
            (effective_from <= as_of)
                .then(|| (visible[&lineage_id].revision.evidence_id.clone(), reasons))
        })
        .collect())
}

fn intrinsic_temporal_state_v1(
    revision: &EvidenceRevisionRow,
    as_of: i64,
) -> TemporalTruthTemporalStateV1 {
    match revision.lifecycle.state {
        LifecycleState::Superseded | LifecycleState::Archived
            if revision
                .lifecycle
                .effective_from
                .is_some_and(|effective_from| as_of >= effective_from) =>
        {
            return TemporalTruthTemporalStateV1::Historical;
        }
        LifecycleState::Active | LifecycleState::Superseded | LifecycleState::Archived => {}
    }
    match revision.validity.kind {
        ValidityKind::Timeless => TemporalTruthTemporalStateV1::Current,
        ValidityKind::Indeterminate => TemporalTruthTemporalStateV1::Indeterminate,
        ValidityKind::Bounded => {
            if revision
                .validity
                .valid_from
                .is_some_and(|valid_from| as_of < valid_from)
            {
                TemporalTruthTemporalStateV1::Future
            } else if revision
                .validity
                .valid_until
                .is_some_and(|valid_until| as_of > valid_until)
            {
                TemporalTruthTemporalStateV1::Historical
            } else {
                TemporalTruthTemporalStateV1::Current
            }
        }
    }
}

fn temporal_state_v1(
    revision: &EvidenceRevisionRow,
    suppressed: &BTreeMap<String, Vec<DispositionReasonModel>>,
    as_of: i64,
) -> TemporalTruthTemporalStateV1 {
    if suppressed.contains_key(&revision.evidence_id) {
        TemporalTruthTemporalStateV1::Historical
    } else {
        intrinsic_temporal_state_v1(revision, as_of)
    }
}

fn intrinsic_disposition_reason_v1(
    revision: &EvidenceRevisionRow,
    as_of: i64,
) -> DispositionReasonModel {
    match revision.lifecycle.state {
        LifecycleState::Superseded
            if revision
                .lifecycle
                .effective_from
                .is_some_and(|effective_from| as_of >= effective_from) =>
        {
            return DispositionReasonModel::LifecycleSuperseded {
                effective_from: revision.lifecycle.effective_from.unwrap_or(0),
            };
        }
        LifecycleState::Archived
            if revision
                .lifecycle
                .effective_from
                .is_some_and(|effective_from| as_of >= effective_from) =>
        {
            return DispositionReasonModel::LifecycleArchived {
                effective_from: revision.lifecycle.effective_from.unwrap_or(0),
            };
        }
        LifecycleState::Active | LifecycleState::Superseded | LifecycleState::Archived => {}
    }
    match revision.validity.kind {
        ValidityKind::Timeless => DispositionReasonModel::Active,
        ValidityKind::Indeterminate => DispositionReasonModel::IndeterminateValidity,
        ValidityKind::Bounded => {
            if let Some(valid_from) = revision
                .validity
                .valid_from
                .filter(|valid_from| as_of < *valid_from)
            {
                DispositionReasonModel::NotYetValid { valid_from }
            } else if let Some(valid_until) = revision
                .validity
                .valid_until
                .filter(|valid_until| as_of > *valid_until)
            {
                DispositionReasonModel::ValidityExpired { valid_until }
            } else {
                DispositionReasonModel::Active
            }
        }
    }
}

fn evidence_disposition_v1(
    revision: &EvidenceRevisionRow,
    suppressed: &BTreeMap<String, Vec<DispositionReasonModel>>,
    as_of: i64,
) -> EvidenceDispositionModel {
    let intrinsic_state = intrinsic_temporal_state_v1(revision, as_of);
    let mut reasons = suppressed
        .get(&revision.evidence_id)
        .cloned()
        .unwrap_or_default();
    if reasons.is_empty() || intrinsic_state != TemporalTruthTemporalStateV1::Current {
        reasons.push(intrinsic_disposition_reason_v1(revision, as_of));
    }
    reasons.sort();
    reasons.dedup();
    EvidenceDispositionModel {
        evidence_id: revision.evidence_id.clone(),
        temporal_state: temporal_state_v1(revision, suppressed, as_of),
        reasons,
    }
}

fn sorted_evidence_ids_v1<'a>(
    evidence: impl Iterator<Item = &'a PreparedEvidenceV1<'a>>,
) -> Vec<String> {
    evidence
        .map(|item| item.revision.evidence_id.clone())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect()
}

fn project_claim_v1(
    referent_id: &str,
    predicate_id: &str,
    mut evidence: Vec<&PreparedEvidenceV1<'_>>,
    suppressed: &BTreeMap<String, Vec<DispositionReasonModel>>,
    as_of: i64,
) -> ProjectedClaimModel {
    evidence.sort_by(|left, right| left.revision.evidence_id.cmp(&right.revision.evidence_id));
    let aliases = evidence
        .iter()
        .flat_map(|item| item.revision.aliases.iter().cloned())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let classified: Vec<(&PreparedEvidenceV1<'_>, TemporalTruthTemporalStateV1)> = evidence
        .iter()
        .map(|item| (*item, temporal_state_v1(item.revision, suppressed, as_of)))
        .collect();
    let selected_state = [
        TemporalTruthTemporalStateV1::Current,
        TemporalTruthTemporalStateV1::Indeterminate,
        TemporalTruthTemporalStateV1::Future,
        TemporalTruthTemporalStateV1::Historical,
    ]
    .into_iter()
    .find(|state| classified.iter().any(|(_, candidate)| candidate == state));

    let Some(selected_state) = selected_state else {
        return ProjectedClaimModel {
            aliases,
            evidence_dispositions: Vec::new(),
            evidence_ids: Vec::new(),
            noncurrent_evidence_ids: Vec::new(),
            predicate_id: predicate_id.to_string(),
            referent_id: referent_id.to_string(),
            shadowed_evidence_ids: Vec::new(),
            source_bindings: Vec::new(),
            supporting_evidence_ids: Vec::new(),
            temporal_state: TemporalTruthTemporalStateV1::Indeterminate,
            truth_state: TemporalTruthStateV1::Unknown,
            truth_tier: None,
            values: Vec::new(),
        };
    };

    let selected: Vec<&PreparedEvidenceV1<'_>> = classified
        .iter()
        .filter_map(|(item, state)| (*state == selected_state).then_some(*item))
        .collect();
    let max_tier = selected
        .iter()
        .map(|item| TemporalTruthTierV1::from_substrate(item.revision.resolved_truth_tier))
        .max()
        .expect("selected temporal class is non-empty");
    let top: Vec<&PreparedEvidenceV1<'_>> = selected
        .iter()
        .copied()
        .filter(|item| {
            TemporalTruthTierV1::from_substrate(item.revision.resolved_truth_tier) == max_tier
        })
        .collect();
    let values: Vec<String> = top
        .iter()
        .map(|item| item.revision.value.clone())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let top_values: BTreeSet<&str> = values.iter().map(String::as_str).collect();
    let supporting: Vec<&PreparedEvidenceV1<'_>> = selected
        .iter()
        .copied()
        .filter(|item| {
            TemporalTruthTierV1::from_substrate(item.revision.resolved_truth_tier) < max_tier
                && top_values.contains(item.revision.value.as_str())
        })
        .collect();
    let shadowed: Vec<&PreparedEvidenceV1<'_>> = selected
        .iter()
        .copied()
        .filter(|item| {
            TemporalTruthTierV1::from_substrate(item.revision.resolved_truth_tier) < max_tier
                && !top_values.contains(item.revision.value.as_str())
        })
        .collect();

    let mut source_binding_pairs = BTreeSet::new();
    for item in top.iter().copied().chain(supporting.iter().copied()) {
        for binding in &item.revision.source_bindings {
            source_binding_pairs.insert((
                binding.source_key.clone(),
                binding.provenance_sha256.clone(),
            ));
        }
    }
    let source_bindings = source_binding_pairs
        .into_iter()
        .map(|(source_key, provenance_sha256)| SourceBindingModel {
            source_key,
            provenance_sha256,
        })
        .collect();
    let evidence_dispositions = evidence
        .iter()
        .map(|item| evidence_disposition_v1(item.revision, suppressed, as_of))
        .collect();
    let noncurrent_evidence_ids = classified
        .iter()
        .filter_map(|(item, state)| {
            (*state != selected_state).then_some(item.revision.evidence_id.clone())
        })
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();

    ProjectedClaimModel {
        aliases,
        evidence_dispositions,
        evidence_ids: top
            .iter()
            .map(|item| item.revision.evidence_id.clone())
            .collect::<BTreeSet<_>>()
            .into_iter()
            .collect(),
        noncurrent_evidence_ids,
        predicate_id: predicate_id.to_string(),
        referent_id: referent_id.to_string(),
        shadowed_evidence_ids: shadowed
            .iter()
            .map(|item| item.revision.evidence_id.clone())
            .collect::<BTreeSet<_>>()
            .into_iter()
            .collect(),
        source_bindings,
        supporting_evidence_ids: supporting
            .iter()
            .map(|item| item.revision.evidence_id.clone())
            .collect::<BTreeSet<_>>()
            .into_iter()
            .collect(),
        temporal_state: selected_state,
        truth_state: if values.len() == 1 {
            TemporalTruthStateV1::Supported
        } else {
            TemporalTruthStateV1::Conflicted
        },
        truth_tier: Some(max_tier),
        values,
    }
}

fn project_prepared_v1(
    prepared: &PreparedTemporalEvidenceV1<'_>,
    request: &TemporalTruthProjectionRequestV1,
) -> ProjectionResult<ProjectionModel> {
    let visible_by_lineage = select_visible_revisions_v1(prepared, request.knowledge_cutoff);
    validate_visible_aliases_v1(&visible_by_lineage, &request.required_claims)?;
    let authority_index = authority_basis_index_v1(prepared);
    let suppressed = derive_suppression_v1(&visible_by_lineage, &authority_index, request.as_of)?;

    let mut claim_ids: BTreeSet<(String, String)> = request
        .required_claims
        .iter()
        .map(|claim| (claim.referent_id.clone(), claim.predicate_id.clone()))
        .collect();
    for item in visible_by_lineage.values() {
        claim_ids.insert((
            item.lineage.referent_id.clone(),
            item.lineage.predicate_id.clone(),
        ));
    }
    let mut claims = Vec::with_capacity(claim_ids.len());
    for (referent_id, predicate_id) in claim_ids {
        let group = visible_by_lineage
            .values()
            .copied()
            .filter(|item| {
                item.lineage.referent_id == referent_id && item.lineage.predicate_id == predicate_id
            })
            .collect();
        claims.push(project_claim_v1(
            &referent_id,
            &predicate_id,
            group,
            &suppressed,
            request.as_of,
        ));
    }

    let mut visible_by_evidence_id: BTreeMap<String, &PreparedEvidenceV1<'_>> = BTreeMap::new();
    for item in visible_by_lineage.values().copied() {
        visible_by_evidence_id.insert(item.revision.evidence_id.clone(), item);
    }
    let evidence_provenance = visible_by_evidence_id
        .values()
        .map(|item| EvidenceProvenanceModel {
            evidence_id: item.revision.evidence_id.clone(),
            source_bindings: item
                .revision
                .source_bindings
                .iter()
                .map(|binding| SourceBindingModel {
                    source_key: binding.source_key.clone(),
                    provenance_sha256: binding.provenance_sha256.clone(),
                })
                .collect(),
        })
        .collect();

    let mut visible_authority_bases = BTreeSet::new();
    for item in visible_by_evidence_id.values() {
        for relationship in &item.relationships {
            let basis = authority_index
                .get(&(
                    item.revision.evidence_id.as_str(),
                    relationship.target_lineage_id.as_str(),
                ))
                .copied()
                .ok_or_else(|| {
                    projection_error(
                        "truth_projection_v1_unbound_relationship_authority",
                        format!(
                            "{} -> {}",
                            item.revision.evidence_id, relationship.target_lineage_id
                        ),
                    )
                })?;
            visible_authority_bases.insert(basis.clone());
        }
    }

    Ok(ProjectionModel {
        as_of: request.as_of,
        authority_bases: visible_authority_bases.into_iter().collect(),
        claims,
        evidence_provenance,
        knowledge_cutoff: request.knowledge_cutoff,
        mode: TEMPORAL_TRUTH_PROJECTION_V1_MODE,
        schema: TEMPORAL_TRUTH_PROJECTION_V1_SCHEMA,
    })
}

fn seal_projection_v1(
    prepared: &PreparedTemporalEvidenceV1<'_>,
    request: &TemporalTruthProjectionRequestV1,
    fixture_id: &'static str,
) -> ProjectionResult<BoundTemporalTruthProjectionV1> {
    let prepared_input_sha256 = prepared_input_digest_v1(prepared, request, fixture_id)?;
    let projection = project_prepared_v1(prepared, request)?;
    let (_, projection_sha256) = bounded_projection_digest(
        &projection,
        MAX_PROJECTION_DIGEST_BYTES,
        "truth_projection_v1_projection_digest",
    )?;
    let snapshot = prepared.snapshot;
    Ok(BoundTemporalTruthProjectionV1 {
        binding: BindingModel {
            as_of: request.as_of,
            canonical_order: snapshot.canonical_order,
            knowledge_cutoff: request.knowledge_cutoff,
            ledger_format_version: snapshot.ledger_format_version,
            mapping_version: TEMPORAL_TRUTH_PROJECTION_V1_MAPPING,
            migration_sha256: snapshot.producer_identity.migration_digest.clone(),
            prepared_input_sha256,
            producer_profile: TEMPORAL_TRUTH_PROJECTION_V1_PROFILE,
            projection_sha256,
            pruned_inbound_relationships: prepared.pruned_inbound_relationships,
            query_only_attested: true,
            read_only_attested: true,
            schema_meta_version: snapshot.producer_identity.schema_meta_version.clone(),
            schema_sha256: snapshot.producer_identity.schema_digest.clone(),
            snapshot_counts: TemporalTruthSnapshotCountsV1 {
                lineages: snapshot.counts.lineages,
                policy_revisions: snapshot.counts.policy_revisions,
                evidence_revisions: snapshot.counts.evidence_revisions,
                relationships: snapshot.counts.relationships,
                tombstones: snapshot.counts.tombstones,
            },
            snapshot_limits: request.limits,
            snapshot_payload_bytes: snapshot.payload_bytes,
            snapshot_payload_sha256: snapshot.payload_sha256.clone(),
            synthetic_fixture_id: fixture_id,
            zero_total_changes_attested: true,
        },
        projection,
    })
}

#[derive(Debug)]
enum ProjectionCallError {
    Sqlite(rusqlite::Error),
    Projection(TemporalTruthProjectionV1Error),
}

impl fmt::Display for ProjectionCallError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Sqlite(error) => write!(formatter, "{error}"),
            Self::Projection(error) => write!(formatter, "{error}"),
        }
    }
}

impl From<rusqlite::Error> for ProjectionCallError {
    fn from(value: rusqlite::Error) -> Self {
        Self::Sqlite(value)
    }
}

impl From<TemporalTruthProjectionV1Error> for ProjectionCallError {
    fn from(value: TemporalTruthProjectionV1Error) -> Self {
        Self::Projection(value)
    }
}

fn map_projection_call_error(
    error: tokio_rusqlite::Error<ProjectionCallError>,
) -> TemporalTruthProjectionV1Error {
    match error {
        tokio_rusqlite::Error::Error(ProjectionCallError::Projection(error)) => error,
        tokio_rusqlite::Error::Error(ProjectionCallError::Sqlite(error)) => {
            projection_error("truth_projection_v1_sqlite", error.to_string())
        }
        tokio_rusqlite::Error::ConnectionClosed => projection_error(
            "truth_projection_v1_connection_closed",
            "read-only SQLite worker closed before projection completed",
        ),
        tokio_rusqlite::Error::Close((_connection, error)) => {
            projection_error("truth_projection_v1_connection_close", error.to_string())
        }
        _ => projection_error(
            "truth_projection_v1_connection",
            "unknown read-only SQLite worker failure",
        ),
    }
}

/// Atomically load, map, project, and seal one v43 temporal-evidence snapshot.
///
/// The database is opened with SQLite's physical read-only flag, reinforced by
/// `query_only`, and checked before and after one deferred transaction. This
/// attests a complete transactional SQLite snapshot (including a live WAL when
/// present); it does not claim that an external writer was globally paused.
pub async fn temporal_truth_project_read_only_synthetic_v1(
    _permit: SyntheticTemporalTruthProjectionPermitV1,
    path: &Path,
    request: TemporalTruthProjectionRequestV1,
) -> ProjectionResult<BoundTemporalTruthProjectionV1> {
    let connection = Connection::open_with_flags(path, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY)
        .await
        .map_err(|error| {
            projection_error("truth_projection_v1_open_read_only", error.to_string())
        })?;
    connection
        .call(
            move |connection| -> std::result::Result<_, ProjectionCallError> {
                connection.busy_timeout(Duration::from_secs(5))?;
                connection.execute_batch("PRAGMA query_only=ON; PRAGMA foreign_keys=ON;")?;
                if !connection.is_readonly(rusqlite::MAIN_DB)? {
                    return Err(projection_error(
                        "truth_projection_v1_read_only_attestation",
                        "sqlite3_db_readonly(main) was false",
                    )
                    .into());
                }
                let query_only: i64 =
                    connection.query_row("PRAGMA query_only", [], |row| row.get(0))?;
                let foreign_keys: i64 =
                    connection.query_row("PRAGMA foreign_keys", [], |row| row.get(0))?;
                if query_only != 1 || foreign_keys != 1 {
                    return Err(projection_error(
                        "truth_projection_v1_read_only_attestation",
                        format!("query_only={query_only}, foreign_keys={foreign_keys}"),
                    )
                    .into());
                }
                if connection.total_changes() != 0 {
                    return Err(projection_error(
                        "truth_projection_v1_zero_changes_attestation",
                        "fresh read-only connection had non-zero total_changes",
                    )
                    .into());
                }

                let transaction = connection
                    .transaction_with_behavior(rusqlite::TransactionBehavior::Deferred)?;
                let transaction_query_only: i64 =
                    transaction.query_row("PRAGMA query_only", [], |row| row.get(0))?;
                if transaction_query_only != 1 {
                    return Err(projection_error(
                        "truth_projection_v1_read_only_attestation",
                        "query_only drifted inside the projection transaction",
                    )
                    .into());
                }
                let snapshot = load_snapshot(
                    &transaction,
                    request.limits.substrate_limits(),
                    request.knowledge_cutoff,
                )?;
                let prepared = prepare_snapshot_v1(&snapshot)?;
                let result = seal_projection_v1(&prepared, &request, SYNTHETIC_FIXTURE_ID)?;
                transaction.commit()?;

                if connection.total_changes() != 0
                    || !connection.is_readonly(rusqlite::MAIN_DB)?
                    || connection.query_row("PRAGMA query_only", [], |row| row.get::<_, i64>(0))?
                        != 1
                {
                    return Err(projection_error(
                        "truth_projection_v1_post_transaction_attestation",
                        "read-only or zero-change attestation drifted",
                    )
                    .into());
                }
                Ok(result)
            },
        )
        .await
        .map_err(map_projection_call_error)
}
