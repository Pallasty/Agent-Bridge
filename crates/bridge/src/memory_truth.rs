//! Deterministic, read-only temporal truth projection.
//!
//! This module is intentionally DB-agnostic and side-effect free. Callers
//! provide normalized claim evidence; [`project`] validates the complete input
//! and derives a canonical projection for an explicit `(as_of,
//! knowledge_cutoff)` pair. It does not search, write, rank, cache, or update
//! access/retrieval telemetry.
//!
//! v0 is an internal Agent-Bridge contract. Its evidence ids, values, and
//! source keys must not be sent directly to BioCortex. A later cross-repository
//! transport must replace them with request-scoped opaque handles and bind the
//! projection to a sealed snapshot.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};
use thiserror::Error;

pub const TRUTH_PROJECTION_SCHEMA: &str = "agent_bridge.truth_projection.v0";
pub const TRUTH_PROJECTION_MODE: &str = "shadow_only";

const MAX_LABEL_BYTES: usize = 512;
const MAX_VALUE_BYTES: usize = 256 * 1024;

/// Canonical identity of one claim. A memory/evidence key is not a referent.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ClaimIdentity {
    pub referent_id: String,
    pub predicate_id: String,
}

/// Explicit temporal semantics for one evidence item.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum TemporalValidity {
    /// Caller explicitly asserts that the claim is not time-bounded.
    Timeless,
    /// Inclusive bounds, matching the frozen portfolio-continuity evaluator:
    /// `valid_from <= as_of <= valid_until`. Either bound may be absent.
    Bounded {
        #[serde(default, skip_serializing_if = "Option::is_none")]
        valid_from: Option<i64>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        valid_until: Option<i64>,
    },
    /// Temporal knowledge is missing. This must never default to current.
    Indeterminate,
}

/// Lifecycle copied from the evidence owner. Only `Active` can be current.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "state", rename_all = "snake_case", deny_unknown_fields)]
pub enum LifecycleState {
    Active,
    /// The evidence becomes superseded at this inclusive world-time boundary.
    Superseded {
        effective_from: i64,
    },
    /// The evidence becomes archived at this inclusive world-time boundary.
    Archived {
        effective_from: i64,
    },
    /// Privacy deletion: excluded from every projection, including historical.
    Tombstoned,
}

/// Explicit evidence authority. Declaration confidence is a separate concern.
/// Variant order is load-bearing: `Inferred < Observed < Verified < Authoritative`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TruthTier {
    Inferred,
    Observed,
    Verified,
    Authoritative,
}

/// One normalized evidence envelope supplied by an Agent-Bridge adapter.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TruthEvidence {
    pub evidence_id: String,
    /// Stable revision lineage. A tombstone redacts every revision sharing this
    /// id before knowledge-cutoff selection.
    pub lineage_id: String,
    pub claim: ClaimIdentity,
    #[serde(default)]
    pub aliases: Vec<String>,
    pub value: String,
    /// World time at which the source observation occurred.
    pub observed_at: i64,
    /// Knowledge time at which Agent-Bridge admitted this envelope. The
    /// knowledge cutoff is evaluated against this field, never `observed_at`.
    pub recorded_at: i64,
    pub validity: TemporalValidity,
    pub lifecycle: LifecycleState,
    pub truth_tier: TruthTier,
    /// Traceable Agent-Bridge source identities. v0 requires at least one.
    pub source_keys: Vec<String>,
    /// Evidence lineage replaced by this item. v0 relationships are same-claim only.
    #[serde(default)]
    pub supersedes: Vec<TruthRelationship>,
    /// Evidence lineage made invalid by this item. v0 relationships are same-claim only.
    #[serde(default)]
    pub invalidates: Vec<TruthRelationship>,
}

/// One explicit truth-governance relationship. `effective_from` is required so
/// a later correction cannot erase a target from historical projections that
/// predate the correction.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TruthRelationship {
    pub target_lineage_id: String,
    pub effective_from: i64,
}

/// Complete input to [`project`].
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TruthProjectionRequest {
    pub as_of: i64,
    pub knowledge_cutoff: i64,
    /// Required claim identities yield an explicit `unknown` result when no
    /// evidence is visible. Discovered visible claims are projected as well.
    #[serde(default)]
    pub required_claims: Vec<ClaimIdentity>,
    #[serde(default)]
    pub evidence: Vec<TruthEvidence>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TruthState {
    Supported,
    Conflicted,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TemporalState {
    Current,
    Historical,
    Future,
    Indeterminate,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SuppressionKind {
    Supersedes,
    Invalidates,
}

/// Why one visible evidence item has its derived temporal state.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum EvidenceDispositionReason {
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

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvidenceDisposition {
    pub evidence_id: String,
    pub temporal_state: TemporalState,
    pub reasons: Vec<EvidenceDispositionReason>,
}

/// Resolved view of one claim.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProjectedClaim {
    #[serde(flatten)]
    pub claim: ClaimIdentity,
    pub aliases: Vec<String>,
    pub truth_state: TruthState,
    pub temporal_state: TemporalState,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub truth_tier: Option<TruthTier>,
    /// Distinct top-tier values in canonical lexical order. More than one
    /// value means `truth_state=conflicted`.
    pub values: Vec<String>,
    /// Load-bearing top-tier evidence ids.
    pub evidence_ids: Vec<String>,
    /// Lower-tier evidence agreeing with one of the selected top-tier values.
    pub supporting_evidence_ids: Vec<String>,
    /// Lower-tier evidence disagreeing with all selected top-tier values.
    pub shadowed_evidence_ids: Vec<String>,
    /// Visible evidence in a non-selected temporal class, including explicit
    /// supersession/invalidation targets.
    pub noncurrent_evidence_ids: Vec<String>,
    /// Per-evidence temporal/lifecycle/relation reasons. This makes replacement,
    /// revocation, expiry, and lifecycle retirement auditable rather than
    /// collapsing all of them into one noncurrent bucket.
    pub evidence_dispositions: Vec<EvidenceDisposition>,
    /// Sources backing load-bearing or agreeing evidence only.
    pub source_keys: Vec<String>,
}

/// Canonical, serialization-stable truth projection.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TruthProjection {
    pub schema: String,
    pub mode: String,
    pub as_of: i64,
    pub knowledge_cutoff: i64,
    pub claims: Vec<ProjectedClaim>,
}

#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum TruthProjectionError {
    #[error("{field} must be a non-negative unix timestamp, got {value}")]
    InvalidTimestamp { field: String, value: i64 },
    #[error("as_of {as_of} must not be later than knowledge_cutoff {knowledge_cutoff}")]
    InvalidRequestWindow { as_of: i64, knowledge_cutoff: i64 },
    #[error("{field} is not a valid bounded label: {reason}")]
    InvalidLabel { field: String, reason: String },
    #[error("evidence {evidence_id} has an empty or oversized value")]
    InvalidValue { evidence_id: String },
    #[error("evidence {evidence_id} must cite at least one source key")]
    MissingSourceKeys { evidence_id: String },
    #[error("evidence {evidence_id} was observed at {observed_at} after it was recorded at {recorded_at}")]
    ObservationAfterRecording {
        evidence_id: String,
        observed_at: i64,
        recorded_at: i64,
    },
    #[error("duplicate required claim {referent_id}/{predicate_id}")]
    DuplicateRequiredClaim {
        referent_id: String,
        predicate_id: String,
    },
    #[error("duplicate evidence id {evidence_id}")]
    DuplicateEvidenceId { evidence_id: String },
    #[error(
        "lineage {lineage_id} has multiple revisions recorded at {recorded_at}: {evidence_ids:?}"
    )]
    AmbiguousLineageRevision {
        lineage_id: String,
        recorded_at: i64,
        evidence_ids: Vec<String>,
    },
    #[error("lineage {lineage_id} revision {evidence_id} drops durable relationships {missing:?}")]
    RelationshipHistoryDropped {
        lineage_id: String,
        evidence_id: String,
        missing: Vec<String>,
    },
    #[error("one evidence lineage changes claim identity across revisions")]
    LineageClaimDrift,
    #[error("a privacy-redacted lineage contains durable governance relationships")]
    TombstonedGovernanceSource,
    #[error("evidence {evidence_id} has valid_from {valid_from} after valid_until {valid_until}")]
    InvalidValidityInterval {
        evidence_id: String,
        valid_from: i64,
        valid_until: i64,
    },
    #[error("evidence {evidence_id} uses bounded validity without either bound")]
    EmptyBoundedValidity { evidence_id: String },
    #[error("evidence {evidence_id} has relationships but indeterminate validity")]
    IndeterminateRelationshipSource { evidence_id: String },
    #[error(
        "relationship {source_id}->{target_id} becomes effective at {effective_from} while its source is not active and temporally valid"
    )]
    RelationshipOutsideSourceActivity {
        source_id: String,
        target_id: String,
        effective_from: i64,
    },
    #[error(
        "evidence {source_id} relates to {target_id} with conflicting effective times {first_effective_from} and {second_effective_from}"
    )]
    ConflictingRelationshipEffectiveTime {
        source_id: String,
        target_id: String,
        first_effective_from: i64,
        second_effective_from: i64,
    },
    #[error(
        "evidence {source_id} declares both supersedes and invalidates for target {target_id}"
    )]
    ConflictingRelationshipKind {
        source_id: String,
        target_id: String,
    },
    #[error("referent alias {alias:?} is ambiguous across {referents:?}")]
    AliasCollision {
        alias: String,
        referents: Vec<String>,
    },
    #[error("evidence {source_id} references unavailable relationship target {target_id}")]
    DanglingRelationship {
        source_id: String,
        target_id: String,
    },
    #[error("evidence {evidence_id} has a self relationship")]
    SelfRelationship { evidence_id: String },
    #[error(
        "relationship {source_id}->{target_id} crosses claim identities ({source_claim} vs {target_claim})"
    )]
    CrossClaimRelationship {
        source_id: String,
        target_id: String,
        source_claim: String,
        target_claim: String,
    },
    #[error(
        "relationship {source_id}->{target_id} cannot suppress higher-tier evidence ({source_tier:?} < {target_tier:?})"
    )]
    InsufficientRelationshipAuthority {
        source_id: String,
        target_id: String,
        source_tier: TruthTier,
        target_tier: TruthTier,
    },
    #[error("relationship graph contains a cycle involving {evidence_ids:?}")]
    RelationshipCycle { evidence_ids: Vec<String> },
}

/// Resolve normalized evidence into a deterministic temporal truth projection.
///
/// Structural integrity failures in the permitted knowledge view reject the
/// complete request. Evidence recorded after `knowledge_cutoff` cannot create
/// a claim, alter success/failure, suppress another item, contribute aliases,
/// or affect serialized output. Tombstones are the deliberate exception: any
/// known tombstone retroactively removes its complete revision lineage because
/// privacy deletion outranks historical replay.
pub fn project(request: &TruthProjectionRequest) -> Result<TruthProjection, TruthProjectionError> {
    validate_request_window(request)?;

    let required = validate_required_claims(&request.required_claims)?;
    let mut redacted_lineages = BTreeSet::new();
    for (index, evidence) in request.evidence.iter().enumerate() {
        if matches!(evidence.lifecycle, LifecycleState::Tombstoned) {
            validate_label(
                &format!("evidence[{index}].tombstone.lineage_id"),
                &evidence.lineage_id,
            )?;
            redacted_lineages.insert(evidence.lineage_id.as_str());
        }
    }
    if request.evidence.iter().any(|evidence| {
        redacted_lineages.contains(evidence.lineage_id.as_str())
            && (!evidence.supersedes.is_empty() || !evidence.invalidates.is_empty())
    }) {
        return Err(TruthProjectionError::TombstonedGovernanceSource);
    }
    let visible_items = select_visible_revisions(request, &redacted_lineages)?;
    let visible_by_id = validate_evidence(visible_items)?;

    validate_aliases(&visible_by_id, &required)?;
    let suppressed = validate_relationships(&visible_by_id, &redacted_lineages, request.as_of)?;

    let mut claim_ids = required;
    for evidence in visible_by_id.values() {
        claim_ids.insert(evidence.claim.clone());
    }

    let mut claims = Vec::with_capacity(claim_ids.len());
    for claim in claim_ids {
        let mut group: Vec<&TruthEvidence> = visible_by_id
            .values()
            .copied()
            .filter(|evidence| evidence.claim == claim)
            .collect();
        group.sort_by(|a, b| a.evidence_id.cmp(&b.evidence_id));
        claims.push(project_claim(claim, &group, &suppressed, request.as_of));
    }

    Ok(TruthProjection {
        schema: TRUTH_PROJECTION_SCHEMA.to_string(),
        mode: TRUTH_PROJECTION_MODE.to_string(),
        as_of: request.as_of,
        knowledge_cutoff: request.knowledge_cutoff,
        claims,
    })
}

fn select_visible_revisions<'a>(
    request: &'a TruthProjectionRequest,
    redacted_lineages: &BTreeSet<&str>,
) -> Result<Vec<&'a TruthEvidence>, TruthProjectionError> {
    let mut visible_ids = BTreeSet::new();
    let mut revisions_by_lineage: BTreeMap<&str, Vec<&TruthEvidence>> = BTreeMap::new();
    for (index, evidence) in request.evidence.iter().enumerate() {
        if evidence.recorded_at > request.knowledge_cutoff
            || matches!(evidence.lifecycle, LifecycleState::Tombstoned)
            || redacted_lineages.contains(evidence.lineage_id.as_str())
        {
            continue;
        }
        validate_label(
            &format!("evidence[{index}].evidence_id"),
            &evidence.evidence_id,
        )?;
        validate_label(
            &format!("evidence[{index}].lineage_id"),
            &evidence.lineage_id,
        )?;
        validate_timestamp(
            &format!("evidence[{index}].recorded_at"),
            evidence.recorded_at,
        )?;
        if !visible_ids.insert(evidence.evidence_id.as_str()) {
            return Err(TruthProjectionError::DuplicateEvidenceId {
                evidence_id: evidence.evidence_id.clone(),
            });
        }
        revisions_by_lineage
            .entry(evidence.lineage_id.as_str())
            .or_default()
            .push(evidence);
    }

    let mut selected = Vec::with_capacity(revisions_by_lineage.len());
    for (lineage_id, mut revisions) in revisions_by_lineage {
        revisions.sort_by(|a, b| {
            a.recorded_at
                .cmp(&b.recorded_at)
                .then(a.evidence_id.cmp(&b.evidence_id))
        });
        for pair in revisions.windows(2) {
            if pair[0].recorded_at == pair[1].recorded_at {
                return Err(TruthProjectionError::AmbiguousLineageRevision {
                    lineage_id: lineage_id.to_string(),
                    recorded_at: pair[0].recorded_at,
                    evidence_ids: vec![pair[0].evidence_id.clone(), pair[1].evidence_id.clone()],
                });
            }
        }
        if revisions
            .iter()
            .skip(1)
            .any(|revision| revision.claim != revisions[0].claim)
        {
            return Err(TruthProjectionError::LineageClaimDrift);
        }

        // Every revision is a full snapshot. Once a relationship appears it
        // must be carried forward, unless its target lineage is privacy-redacted.
        let mut durable = BTreeSet::new();
        for revision in &revisions {
            let snapshot = relationship_snapshot(revision, redacted_lineages);
            let missing: Vec<String> = durable
                .difference(&snapshot)
                .map(format_relationship_key)
                .collect();
            if !missing.is_empty() {
                return Err(TruthProjectionError::RelationshipHistoryDropped {
                    lineage_id: lineage_id.to_string(),
                    evidence_id: revision.evidence_id.clone(),
                    missing,
                });
            }
            durable = snapshot;
        }
        selected.push(*revisions.last().expect("lineage has at least one revision"));
    }
    Ok(selected)
}

type RelationshipKey = (SuppressionKind, String, i64);

fn relationship_snapshot(
    evidence: &TruthEvidence,
    redacted_lineages: &BTreeSet<&str>,
) -> BTreeSet<RelationshipKey> {
    let mut out = BTreeSet::new();
    for (kind, relationships) in [
        (SuppressionKind::Supersedes, &evidence.supersedes),
        (SuppressionKind::Invalidates, &evidence.invalidates),
    ] {
        out.extend(
            relationships
                .iter()
                .filter(|relationship| {
                    !redacted_lineages.contains(relationship.target_lineage_id.as_str())
                })
                .map(|relationship| {
                    (
                        kind,
                        relationship.target_lineage_id.clone(),
                        relationship.effective_from,
                    )
                }),
        );
    }
    out
}

fn format_relationship_key(key: &RelationshipKey) -> String {
    format!("{:?}:{}@{}", key.0, key.1, key.2)
}

fn validate_request_window(request: &TruthProjectionRequest) -> Result<(), TruthProjectionError> {
    validate_timestamp("as_of", request.as_of)?;
    validate_timestamp("knowledge_cutoff", request.knowledge_cutoff)?;
    if request.as_of > request.knowledge_cutoff {
        return Err(TruthProjectionError::InvalidRequestWindow {
            as_of: request.as_of,
            knowledge_cutoff: request.knowledge_cutoff,
        });
    }
    Ok(())
}

fn validate_required_claims(
    claims: &[ClaimIdentity],
) -> Result<BTreeSet<ClaimIdentity>, TruthProjectionError> {
    let mut out = BTreeSet::new();
    for (index, claim) in claims.iter().enumerate() {
        validate_claim(claim, &format!("required_claims[{index}]"))?;
        if !out.insert(claim.clone()) {
            return Err(TruthProjectionError::DuplicateRequiredClaim {
                referent_id: claim.referent_id.clone(),
                predicate_id: claim.predicate_id.clone(),
            });
        }
    }
    Ok(out)
}

fn validate_evidence<'a>(
    evidence: impl IntoIterator<Item = &'a TruthEvidence>,
) -> Result<BTreeMap<&'a str, &'a TruthEvidence>, TruthProjectionError> {
    let mut by_id = BTreeMap::new();
    for (index, item) in evidence.into_iter().enumerate() {
        let path = format!("evidence[{index}]");
        validate_label(&format!("{path}.evidence_id"), &item.evidence_id)?;
        validate_label(&format!("{path}.lineage_id"), &item.lineage_id)?;
        validate_claim(&item.claim, &path)?;
        for (alias_index, alias) in item.aliases.iter().enumerate() {
            validate_label(&format!("{path}.aliases[{alias_index}]"), alias)?;
        }
        if item.value.is_empty() || item.value.len() > MAX_VALUE_BYTES {
            return Err(TruthProjectionError::InvalidValue {
                evidence_id: item.evidence_id.clone(),
            });
        }
        validate_timestamp(&format!("{path}.observed_at"), item.observed_at)?;
        validate_timestamp(&format!("{path}.recorded_at"), item.recorded_at)?;
        if item.observed_at > item.recorded_at {
            return Err(TruthProjectionError::ObservationAfterRecording {
                evidence_id: item.evidence_id.clone(),
                observed_at: item.observed_at,
                recorded_at: item.recorded_at,
            });
        }
        validate_validity(item)?;
        validate_lifecycle(item)?;
        if item.source_keys.is_empty() {
            return Err(TruthProjectionError::MissingSourceKeys {
                evidence_id: item.evidence_id.clone(),
            });
        }
        for (source_index, source) in item.source_keys.iter().enumerate() {
            validate_label(&format!("{path}.source_keys[{source_index}]"), source)?;
        }
        if matches!(item.validity, TemporalValidity::Indeterminate)
            && (!item.supersedes.is_empty() || !item.invalidates.is_empty())
        {
            return Err(TruthProjectionError::IndeterminateRelationshipSource {
                evidence_id: item.evidence_id.clone(),
            });
        }
        for (relation_name, relationships) in [
            ("supersedes", &item.supersedes),
            ("invalidates", &item.invalidates),
        ] {
            for (target_index, relationship) in relationships.iter().enumerate() {
                validate_label(
                    &format!("{path}.{relation_name}[{target_index}].target_lineage_id"),
                    &relationship.target_lineage_id,
                )?;
                validate_timestamp(
                    &format!("{path}.{relation_name}[{target_index}].effective_from"),
                    relationship.effective_from,
                )?;
                if intrinsic_temporal_state(item, relationship.effective_from)
                    != TemporalState::Current
                {
                    return Err(TruthProjectionError::RelationshipOutsideSourceActivity {
                        source_id: item.evidence_id.clone(),
                        target_id: relationship.target_lineage_id.clone(),
                        effective_from: relationship.effective_from,
                    });
                }
            }
        }
        if by_id.insert(item.evidence_id.as_str(), item).is_some() {
            return Err(TruthProjectionError::DuplicateEvidenceId {
                evidence_id: item.evidence_id.clone(),
            });
        }
    }
    Ok(by_id)
}

fn validate_claim(claim: &ClaimIdentity, path: &str) -> Result<(), TruthProjectionError> {
    validate_label(&format!("{path}.referent_id"), &claim.referent_id)?;
    validate_label(&format!("{path}.predicate_id"), &claim.predicate_id)
}

fn validate_label(field: &str, value: &str) -> Result<(), TruthProjectionError> {
    let reason = if value.is_empty() {
        Some("empty".to_string())
    } else if value.len() > MAX_LABEL_BYTES {
        Some(format!("longer than {MAX_LABEL_BYTES} bytes"))
    } else if value.trim() != value {
        Some("leading or trailing whitespace".to_string())
    } else if !value.is_ascii() {
        Some("must use ASCII machine-label characters".to_string())
    } else if value.chars().any(char::is_control) {
        Some("contains a control character".to_string())
    } else {
        None
    };
    match reason {
        Some(reason) => Err(TruthProjectionError::InvalidLabel {
            field: field.to_string(),
            reason,
        }),
        None => Ok(()),
    }
}

fn validate_timestamp(field: &str, value: i64) -> Result<(), TruthProjectionError> {
    if value < 0 {
        Err(TruthProjectionError::InvalidTimestamp {
            field: field.to_string(),
            value,
        })
    } else {
        Ok(())
    }
}

fn validate_validity(item: &TruthEvidence) -> Result<(), TruthProjectionError> {
    if let TemporalValidity::Bounded {
        valid_from,
        valid_until,
    } = item.validity
    {
        if let Some(value) = valid_from {
            validate_timestamp(&format!("{}.valid_from", item.evidence_id), value)?;
        }
        if let Some(value) = valid_until {
            validate_timestamp(&format!("{}.valid_until", item.evidence_id), value)?;
        }
        if valid_from.is_none() && valid_until.is_none() {
            return Err(TruthProjectionError::EmptyBoundedValidity {
                evidence_id: item.evidence_id.clone(),
            });
        }
        if let (Some(valid_from), Some(valid_until)) = (valid_from, valid_until) {
            if valid_from > valid_until {
                return Err(TruthProjectionError::InvalidValidityInterval {
                    evidence_id: item.evidence_id.clone(),
                    valid_from,
                    valid_until,
                });
            }
        }
    }
    Ok(())
}

fn validate_lifecycle(item: &TruthEvidence) -> Result<(), TruthProjectionError> {
    match item.lifecycle {
        LifecycleState::Superseded { effective_from }
        | LifecycleState::Archived { effective_from } => validate_timestamp(
            &format!("{}.lifecycle.effective_from", item.evidence_id),
            effective_from,
        ),
        LifecycleState::Active | LifecycleState::Tombstoned => Ok(()),
    }
}

fn validate_aliases(
    visible: &BTreeMap<&str, &TruthEvidence>,
    required: &BTreeSet<ClaimIdentity>,
) -> Result<(), TruthProjectionError> {
    let mut owners: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for claim in required {
        owners
            .entry(normalize_alias(&claim.referent_id))
            .or_default()
            .insert(claim.referent_id.clone());
    }
    for item in visible.values() {
        owners
            .entry(normalize_alias(&item.claim.referent_id))
            .or_default()
            .insert(item.claim.referent_id.clone());
        for alias in &item.aliases {
            owners
                .entry(normalize_alias(alias))
                .or_default()
                .insert(item.claim.referent_id.clone());
        }
    }
    if let Some((alias, referents)) = owners.into_iter().find(|(_, refs)| refs.len() > 1) {
        return Err(TruthProjectionError::AliasCollision {
            alias,
            referents: referents.into_iter().collect(),
        });
    }
    Ok(())
}

fn normalize_alias(value: &str) -> String {
    value.to_ascii_lowercase()
}

/// Validate visible same-claim relationship edges and return suppressed targets.
fn validate_relationships(
    visible: &BTreeMap<&str, &TruthEvidence>,
    redacted_lineages: &BTreeSet<&str>,
    as_of: i64,
) -> Result<BTreeMap<String, Vec<EvidenceDispositionReason>>, TruthProjectionError> {
    let visible_by_lineage: BTreeMap<&str, &TruthEvidence> = visible
        .values()
        .map(|evidence| (evidence.lineage_id.as_str(), *evidence))
        .collect();
    let mut edges: BTreeMap<String, BTreeMap<String, (SuppressionKind, i64)>> = visible_by_lineage
        .keys()
        .map(|lineage_id| ((*lineage_id).to_string(), BTreeMap::new()))
        .collect();
    let mut indegree: BTreeMap<String, usize> = visible_by_lineage
        .keys()
        .map(|lineage_id| ((*lineage_id).to_string(), 0usize))
        .collect();

    for source in visible.values() {
        for (kind, relationships) in [
            (SuppressionKind::Supersedes, &source.supersedes),
            (SuppressionKind::Invalidates, &source.invalidates),
        ] {
            for relationship in relationships {
                let target_lineage_id = relationship.target_lineage_id.as_str();
                if redacted_lineages.contains(target_lineage_id) {
                    continue;
                }
                if target_lineage_id == source.lineage_id {
                    return Err(TruthProjectionError::SelfRelationship {
                        evidence_id: source.evidence_id.clone(),
                    });
                }
                let Some(target) = visible_by_lineage.get(target_lineage_id) else {
                    return Err(TruthProjectionError::DanglingRelationship {
                        source_id: source.evidence_id.clone(),
                        target_id: target_lineage_id.to_string(),
                    });
                };
                if source.claim != target.claim {
                    return Err(TruthProjectionError::CrossClaimRelationship {
                        source_id: source.evidence_id.clone(),
                        target_id: target_lineage_id.to_string(),
                        source_claim: display_claim(&source.claim),
                        target_claim: display_claim(&target.claim),
                    });
                }
                if source.truth_tier < target.truth_tier {
                    return Err(TruthProjectionError::InsufficientRelationshipAuthority {
                        source_id: source.evidence_id.clone(),
                        target_id: target_lineage_id.to_string(),
                        source_tier: source.truth_tier,
                        target_tier: target.truth_tier,
                    });
                }
                let source_edges = edges
                    .get_mut(&source.lineage_id)
                    .expect("visible source has edge row");
                if let Some((first_kind, first_effective_from)) = source_edges.insert(
                    target_lineage_id.to_string(),
                    (kind, relationship.effective_from),
                ) {
                    if first_kind != kind {
                        return Err(TruthProjectionError::ConflictingRelationshipKind {
                            source_id: source.evidence_id.clone(),
                            target_id: target_lineage_id.to_string(),
                        });
                    }
                    if first_effective_from != relationship.effective_from {
                        return Err(TruthProjectionError::ConflictingRelationshipEffectiveTime {
                            source_id: source.evidence_id.clone(),
                            target_id: target_lineage_id.to_string(),
                            first_effective_from,
                            second_effective_from: relationship.effective_from,
                        });
                    }
                } else {
                    *indegree
                        .get_mut(target_lineage_id)
                        .expect("visible target has indegree row") += 1;
                }
            }
        }
    }

    let mut ready: BTreeSet<String> = indegree
        .iter()
        .filter_map(|(id, degree)| (*degree == 0).then_some(id.clone()))
        .collect();
    let mut processed = 0usize;
    let mut topological_order = Vec::with_capacity(visible.len());
    while let Some(id) = ready.pop_first() {
        processed += 1;
        topological_order.push(id.clone());
        for target in edges
            .get(&id)
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
    if processed != visible_by_lineage.len() {
        let evidence_ids = indegree
            .into_iter()
            .filter_map(|(lineage_id, degree)| {
                (degree > 0).then(|| visible_by_lineage[&lineage_id.as_str()].evidence_id.clone())
            })
            .collect();
        return Err(TruthProjectionError::RelationshipCycle { evidence_ids });
    }

    // Propagate the earliest effective suppression through the DAG. A source
    // already suppressed cannot fire a later outgoing edge; an earlier edge
    // remains a durable governance fact. Suppression wins at equal timestamps.
    let mut suppressed_at: BTreeMap<String, (i64, Vec<EvidenceDispositionReason>)> =
        BTreeMap::new();
    for source_lineage_id in topological_order {
        let source_suppressed_at = suppressed_at.get(&source_lineage_id).map(|(time, _)| *time);
        let source_evidence_id = &visible_by_lineage[&source_lineage_id.as_str()].evidence_id;
        for (target_lineage_id, (kind, effective_from)) in edges
            .get(&source_lineage_id)
            .expect("topological source has edge row")
        {
            if source_suppressed_at.is_none_or(|time| *effective_from < time) {
                let reason = match kind {
                    SuppressionKind::Supersedes => EvidenceDispositionReason::SupersededBy {
                        source_id: source_evidence_id.clone(),
                        effective_from: *effective_from,
                    },
                    SuppressionKind::Invalidates => EvidenceDispositionReason::InvalidatedBy {
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
            (effective_from <= as_of).then(|| {
                (
                    visible_by_lineage[&lineage_id.as_str()].evidence_id.clone(),
                    reasons,
                )
            })
        })
        .collect())
}

fn display_claim(claim: &ClaimIdentity) -> String {
    format!("{}/{}", claim.referent_id, claim.predicate_id)
}

fn project_claim(
    claim: ClaimIdentity,
    evidence: &[&TruthEvidence],
    suppressed: &BTreeMap<String, Vec<EvidenceDispositionReason>>,
    as_of: i64,
) -> ProjectedClaim {
    let aliases: Vec<String> = evidence
        .iter()
        .flat_map(|item| item.aliases.iter().cloned())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();

    let classified: Vec<(&TruthEvidence, TemporalState)> = evidence
        .iter()
        .map(|item| (*item, temporal_state(item, suppressed, as_of)))
        .collect();
    let selected_state = [
        TemporalState::Current,
        TemporalState::Indeterminate,
        TemporalState::Future,
        TemporalState::Historical,
    ]
    .into_iter()
    .find(|state| classified.iter().any(|(_, candidate)| candidate == state));

    let Some(selected_state) = selected_state else {
        return ProjectedClaim {
            claim,
            aliases,
            truth_state: TruthState::Unknown,
            temporal_state: TemporalState::Indeterminate,
            truth_tier: None,
            values: Vec::new(),
            evidence_ids: Vec::new(),
            supporting_evidence_ids: Vec::new(),
            shadowed_evidence_ids: Vec::new(),
            noncurrent_evidence_ids: Vec::new(),
            evidence_dispositions: Vec::new(),
            source_keys: Vec::new(),
        };
    };

    let selected: Vec<&TruthEvidence> = classified
        .iter()
        .filter_map(|(item, state)| (*state == selected_state).then_some(*item))
        .collect();
    let max_tier = selected
        .iter()
        .map(|item| item.truth_tier)
        .max()
        .expect("selected temporal class is non-empty");
    let top: Vec<&TruthEvidence> = selected
        .iter()
        .copied()
        .filter(|item| item.truth_tier == max_tier)
        .collect();
    let values: Vec<String> = top
        .iter()
        .map(|item| item.value.clone())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let top_values: BTreeSet<&str> = values.iter().map(String::as_str).collect();

    let evidence_ids = sorted_ids(top.iter().copied());
    let supporting: Vec<&TruthEvidence> = selected
        .iter()
        .copied()
        .filter(|item| item.truth_tier < max_tier && top_values.contains(item.value.as_str()))
        .collect();
    let shadowed: Vec<&TruthEvidence> = selected
        .iter()
        .copied()
        .filter(|item| item.truth_tier < max_tier && !top_values.contains(item.value.as_str()))
        .collect();
    let noncurrent_evidence_ids = sorted_ids(
        classified
            .iter()
            .filter_map(|(item, state)| (*state != selected_state).then_some(*item)),
    );

    let source_keys: Vec<String> = top
        .iter()
        .copied()
        .chain(supporting.iter().copied())
        .flat_map(|item| item.source_keys.iter().cloned())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let evidence_dispositions = evidence
        .iter()
        .map(|item| evidence_disposition(item, suppressed, as_of))
        .collect();

    ProjectedClaim {
        claim,
        aliases,
        truth_state: if values.len() == 1 {
            TruthState::Supported
        } else {
            TruthState::Conflicted
        },
        temporal_state: selected_state,
        truth_tier: Some(max_tier),
        values,
        evidence_ids,
        supporting_evidence_ids: sorted_ids(supporting.into_iter()),
        shadowed_evidence_ids: sorted_ids(shadowed.into_iter()),
        noncurrent_evidence_ids,
        evidence_dispositions,
        source_keys,
    }
}

fn sorted_ids<'a>(items: impl Iterator<Item = &'a TruthEvidence>) -> Vec<String> {
    items
        .map(|item| item.evidence_id.clone())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect()
}

fn temporal_state(
    evidence: &TruthEvidence,
    suppressed: &BTreeMap<String, Vec<EvidenceDispositionReason>>,
    as_of: i64,
) -> TemporalState {
    if suppressed.contains_key(&evidence.evidence_id) {
        return TemporalState::Historical;
    }
    intrinsic_temporal_state(evidence, as_of)
}

fn evidence_disposition(
    evidence: &TruthEvidence,
    suppressed: &BTreeMap<String, Vec<EvidenceDispositionReason>>,
    as_of: i64,
) -> EvidenceDisposition {
    let intrinsic_state = intrinsic_temporal_state(evidence, as_of);
    let mut reasons = suppressed
        .get(&evidence.evidence_id)
        .cloned()
        .unwrap_or_default();
    if reasons.is_empty() || intrinsic_state != TemporalState::Current {
        reasons.push(intrinsic_disposition_reason(evidence, as_of));
    }
    reasons.sort();
    reasons.dedup();
    EvidenceDisposition {
        evidence_id: evidence.evidence_id.clone(),
        temporal_state: temporal_state(evidence, suppressed, as_of),
        reasons,
    }
}

fn intrinsic_disposition_reason(evidence: &TruthEvidence, as_of: i64) -> EvidenceDispositionReason {
    match evidence.lifecycle {
        LifecycleState::Superseded { effective_from } if as_of >= effective_from => {
            return EvidenceDispositionReason::LifecycleSuperseded { effective_from };
        }
        LifecycleState::Archived { effective_from } if as_of >= effective_from => {
            return EvidenceDispositionReason::LifecycleArchived { effective_from };
        }
        LifecycleState::Active
        | LifecycleState::Superseded { .. }
        | LifecycleState::Archived { .. }
        | LifecycleState::Tombstoned => {}
    }
    match evidence.validity {
        TemporalValidity::Timeless => EvidenceDispositionReason::Active,
        TemporalValidity::Indeterminate => EvidenceDispositionReason::IndeterminateValidity,
        TemporalValidity::Bounded {
            valid_from,
            valid_until,
        } => {
            if let Some(valid_from) = valid_from.filter(|start| as_of < *start) {
                EvidenceDispositionReason::NotYetValid { valid_from }
            } else if let Some(valid_until) = valid_until.filter(|end| as_of > *end) {
                EvidenceDispositionReason::ValidityExpired { valid_until }
            } else {
                EvidenceDispositionReason::Active
            }
        }
    }
}

fn intrinsic_temporal_state(evidence: &TruthEvidence, as_of: i64) -> TemporalState {
    match evidence.lifecycle {
        LifecycleState::Tombstoned => return TemporalState::Historical,
        LifecycleState::Superseded { effective_from }
        | LifecycleState::Archived { effective_from }
            if as_of >= effective_from =>
        {
            return TemporalState::Historical;
        }
        LifecycleState::Active
        | LifecycleState::Superseded { .. }
        | LifecycleState::Archived { .. } => {}
    }
    match evidence.validity {
        TemporalValidity::Timeless => TemporalState::Current,
        TemporalValidity::Indeterminate => TemporalState::Indeterminate,
        TemporalValidity::Bounded {
            valid_from,
            valid_until,
        } => {
            if valid_from.is_some_and(|start| as_of < start) {
                TemporalState::Future
            } else if valid_until.is_some_and(|end| as_of > end) {
                TemporalState::Historical
            } else {
                TemporalState::Current
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn claim(referent: &str, predicate: &str) -> ClaimIdentity {
        ClaimIdentity {
            referent_id: referent.to_string(),
            predicate_id: predicate.to_string(),
        }
    }

    fn evidence(id: &str, referent: &str, predicate: &str, value: &str) -> TruthEvidence {
        TruthEvidence {
            evidence_id: id.to_string(),
            lineage_id: id.to_string(),
            claim: claim(referent, predicate),
            aliases: Vec::new(),
            value: value.to_string(),
            observed_at: 10,
            recorded_at: 10,
            validity: TemporalValidity::Timeless,
            lifecycle: LifecycleState::Active,
            truth_tier: TruthTier::Verified,
            source_keys: vec![format!("source_{id}")],
            supersedes: Vec::new(),
            invalidates: Vec::new(),
        }
    }

    fn relation(target_id: &str, effective_from: i64) -> TruthRelationship {
        TruthRelationship {
            target_lineage_id: target_id.to_string(),
            effective_from,
        }
    }

    fn request(
        as_of: i64,
        required_claims: Vec<ClaimIdentity>,
        evidence: Vec<TruthEvidence>,
    ) -> TruthProjectionRequest {
        TruthProjectionRequest {
            as_of,
            knowledge_cutoff: as_of.max(100),
            required_claims,
            evidence,
        }
    }

    fn only_claim(projection: &TruthProjection) -> &ProjectedClaim {
        assert_eq!(projection.claims.len(), 1);
        &projection.claims[0]
    }

    #[test]
    fn projects_current_claim_with_schema_and_provenance() {
        let projection = project(&request(
            50,
            vec![claim("project:a", "status")],
            vec![evidence("e1", "project:a", "status", "ready")],
        ))
        .unwrap();

        assert_eq!(projection.schema, TRUTH_PROJECTION_SCHEMA);
        assert_eq!(projection.mode, TRUTH_PROJECTION_MODE);
        let result = only_claim(&projection);
        assert_eq!(result.truth_state, TruthState::Supported);
        assert_eq!(result.temporal_state, TemporalState::Current);
        assert_eq!(result.values, ["ready"]);
        assert_eq!(result.evidence_ids, ["e1"]);
        assert_eq!(result.source_keys, ["source_e1"]);
    }

    #[test]
    fn bounded_validity_is_inclusive_at_both_edges() {
        let mut item = evidence("e1", "project:a", "status", "ready");
        item.validity = TemporalValidity::Bounded {
            valid_from: Some(20),
            valid_until: Some(30),
        };

        for as_of in [20, 30] {
            let projection = project(&request(as_of, vec![], vec![item.clone()])).unwrap();
            assert_eq!(
                only_claim(&projection).temporal_state,
                TemporalState::Current
            );
        }
        let before = project(&request(19, vec![], vec![item.clone()])).unwrap();
        assert_eq!(only_claim(&before).temporal_state, TemporalState::Future);
        let after = project(&request(31, vec![], vec![item])).unwrap();
        assert_eq!(only_claim(&after).temporal_state, TemporalState::Historical);
    }

    #[test]
    fn lifecycle_transition_is_current_before_boundary_and_historical_at_boundary() {
        for lifecycle in [
            LifecycleState::Superseded { effective_from: 60 },
            LifecycleState::Archived { effective_from: 60 },
        ] {
            let mut item = evidence("e1", "project:a", "status", "ready");
            item.lifecycle = lifecycle;
            let before = project(&request(59, vec![], vec![item.clone()])).unwrap();
            assert_eq!(only_claim(&before).temporal_state, TemporalState::Current);
            let at_boundary = project(&request(60, vec![], vec![item])).unwrap();
            assert_eq!(
                only_claim(&at_boundary).temporal_state,
                TemporalState::Historical
            );
        }
    }

    #[test]
    fn indeterminate_validity_never_defaults_to_current() {
        let mut item = evidence("e1", "project:a", "status", "ready");
        item.validity = TemporalValidity::Indeterminate;
        let projection = project(&request(50, vec![], vec![item])).unwrap();
        assert_eq!(
            only_claim(&projection).temporal_state,
            TemporalState::Indeterminate
        );
    }

    #[test]
    fn knowledge_cutoff_prevents_late_recording_and_backfill_leak() {
        let required = claim("project:a", "status");
        let mut future = evidence("future", "project:a", "status", "complete");
        // The observation describes an earlier world time but was admitted
        // after the permitted knowledge boundary.
        future.observed_at = 20;
        future.recorded_at = 90;
        let mut input = request(50, vec![required], vec![future]);
        input.knowledge_cutoff = 60;

        let projection = project(&input).unwrap();
        let result = only_claim(&projection);
        assert_eq!(result.truth_state, TruthState::Unknown);
        assert_eq!(result.temporal_state, TemporalState::Indeterminate);
        assert!(result.values.is_empty());

        let mut baseline = input;
        baseline.evidence.clear();
        assert_eq!(projection, project(&baseline).unwrap());
    }

    #[test]
    fn cutoff_excluded_relationship_target_is_indistinguishable_from_missing() {
        let mut current = evidence("current", "project:a", "status", "ready");
        current.invalidates.push(relation("future", 40));
        let mut future = evidence("future", "project:a", "status", "blocked");
        future.recorded_at = 90;
        let mut input = request(50, vec![], vec![current.clone(), future]);
        input.knowledge_cutoff = 60;

        let with_future = project(&input).unwrap_err();
        let without_future = project(&request(50, vec![], vec![current])).unwrap_err();
        assert_eq!(with_future, without_future);
    }

    #[test]
    fn explicit_supersession_chain_keeps_only_terminal_current() {
        let v1 = evidence("v1", "project:a", "status", "planned");
        let mut v2 = evidence("v2", "project:a", "status", "running");
        v2.supersedes.push(relation("v1", 20));
        let mut v3 = evidence("v3", "project:a", "status", "complete");
        v3.supersedes.push(relation("v2", 30));

        let projection = project(&request(50, vec![], vec![v1, v2, v3])).unwrap();
        let result = only_claim(&projection);
        assert_eq!(result.values, ["complete"]);
        assert_eq!(result.evidence_ids, ["v3"]);
        assert_eq!(result.noncurrent_evidence_ids, ["v1", "v2"]);
    }

    #[test]
    fn explicit_invalidation_makes_target_historical() {
        let stale = evidence("stale", "service:a", "availability", "offline");
        let mut recovered = evidence("recovered", "service:a", "availability", "online");
        recovered.invalidates.push(relation("stale", 20));

        let projection = project(&request(50, vec![], vec![stale, recovered])).unwrap();
        let result = only_claim(&projection);
        assert_eq!(result.values, ["online"]);
        assert_eq!(result.noncurrent_evidence_ids, ["stale"]);
        let stale = result
            .evidence_dispositions
            .iter()
            .find(|item| item.evidence_id == "stale")
            .unwrap();
        assert_eq!(stale.temporal_state, TemporalState::Historical);
        assert_eq!(
            stale.reasons,
            [EvidenceDispositionReason::InvalidatedBy {
                source_id: "recovered".to_string(),
                effective_from: 20,
            }]
        );
    }

    #[test]
    fn relationship_effective_time_preserves_pre_correction_history() {
        let current = evidence("current", "service:a", "status", "online");
        let mut candidate = evidence("candidate", "service:a", "status", "offline");
        candidate.validity = TemporalValidity::Bounded {
            valid_from: Some(60),
            valid_until: None,
        };
        candidate.invalidates.push(relation("current", 60));

        let before = project(&request(
            50,
            vec![],
            vec![candidate.clone(), current.clone()],
        ))
        .unwrap();
        assert_eq!(only_claim(&before).values, ["online"]);
        assert_eq!(only_claim(&before).noncurrent_evidence_ids, ["candidate"]);

        let after = project(&request(60, vec![], vec![candidate, current])).unwrap();
        assert_eq!(only_claim(&after).values, ["offline"]);
        assert_eq!(only_claim(&after).noncurrent_evidence_ids, ["current"]);
    }

    #[test]
    fn suppressed_source_cannot_fire_a_later_outgoing_relationship() {
        let target = evidence("target", "service:a", "status", "online");
        let mut old_source = evidence("old", "service:a", "status", "offline");
        old_source.invalidates.push(relation("target", 30));
        let mut newer = evidence("newer", "service:a", "status", "online");
        newer.supersedes.push(relation("old", 20));

        let projection = project(&request(40, vec![], vec![old_source, newer, target])).unwrap();
        let result = only_claim(&projection);
        assert_eq!(result.truth_state, TruthState::Supported);
        assert_eq!(result.values, ["online"]);
        assert_eq!(result.evidence_ids, ["newer", "target"]);
        assert_eq!(result.noncurrent_evidence_ids, ["old"]);
    }

    #[test]
    fn relationship_must_become_effective_while_source_is_active() {
        let target = evidence("target", "service:a", "status", "online");
        let mut expired = evidence("expired", "service:a", "status", "offline");
        expired.validity = TemporalValidity::Bounded {
            valid_from: Some(10),
            valid_until: Some(20),
        };
        expired.invalidates.push(relation("target", 30));
        let err = project(&request(40, vec![], vec![expired, target])).unwrap_err();
        assert!(matches!(
            err,
            TruthProjectionError::RelationshipOutsideSourceActivity { .. }
        ));
    }

    #[test]
    fn indeterminate_source_cannot_carry_truth_relationships() {
        let current = evidence("current", "service:a", "status", "online");
        let mut candidate = evidence("candidate", "service:a", "status", "offline");
        candidate.validity = TemporalValidity::Indeterminate;
        candidate.invalidates.push(relation("current", 20));
        let err = project(&request(50, vec![], vec![candidate, current])).unwrap_err();
        assert_eq!(
            err,
            TruthProjectionError::IndeterminateRelationshipSource {
                evidence_id: "candidate".to_string()
            }
        );
    }

    #[test]
    fn equal_top_tier_distinct_values_are_conflicted() {
        let a = evidence("a", "project:a", "owner", "alice");
        let b = evidence("b", "project:a", "owner", "bob");
        let projection = project(&request(50, vec![], vec![b, a])).unwrap();
        let result = only_claim(&projection);
        assert_eq!(result.truth_state, TruthState::Conflicted);
        assert_eq!(result.values, ["alice", "bob"]);
        assert_eq!(result.evidence_ids, ["a", "b"]);
    }

    #[test]
    fn higher_truth_tier_wins_and_lower_disagreement_is_shadowed() {
        let mut inferred = evidence("inferred", "project:a", "status", "blocked");
        inferred.truth_tier = TruthTier::Inferred;
        let mut authoritative = evidence("owner", "project:a", "status", "ready");
        authoritative.truth_tier = TruthTier::Authoritative;
        let mut observed = evidence("observed", "project:a", "status", "ready");
        observed.truth_tier = TruthTier::Observed;

        let projection = project(&request(
            50,
            vec![],
            vec![inferred, authoritative, observed],
        ))
        .unwrap();
        let result = only_claim(&projection);
        assert_eq!(result.truth_state, TruthState::Supported);
        assert_eq!(result.truth_tier, Some(TruthTier::Authoritative));
        assert_eq!(result.values, ["ready"]);
        assert_eq!(result.supporting_evidence_ids, ["observed"]);
        assert_eq!(result.shadowed_evidence_ids, ["inferred"]);
    }

    #[test]
    fn missing_required_claim_is_explicit_unknown() {
        let projection = project(&request(
            50,
            vec![claim("project:missing", "status")],
            vec![],
        ))
        .unwrap();
        let result = only_claim(&projection);
        assert_eq!(result.truth_state, TruthState::Unknown);
        assert_eq!(result.temporal_state, TemporalState::Indeterminate);
        assert!(result.evidence_ids.is_empty());
    }

    #[test]
    fn same_referent_different_predicates_remain_separate() {
        let projection = project(&request(
            50,
            vec![],
            vec![
                evidence("status", "project:a", "status", "ready"),
                evidence("risk", "project:a", "risk", "low"),
            ],
        ))
        .unwrap();
        assert_eq!(projection.claims.len(), 2);
        assert_eq!(projection.claims[0].claim.predicate_id, "risk");
        assert_eq!(projection.claims[1].claim.predicate_id, "status");
    }

    #[test]
    fn alias_collision_across_referents_fails_closed() {
        let mut a = evidence("a", "artifact:s4", "status", "ready");
        a.aliases.push("compact".to_string());
        let mut b = evidence("b", "artifact:top2", "status", "ready");
        b.aliases.push("COMPACT".to_string());

        let err = project(&request(50, vec![], vec![a, b])).unwrap_err();
        assert!(matches!(err, TruthProjectionError::AliasCollision { .. }));
    }

    #[test]
    fn alias_cannot_capture_required_referent_without_evidence() {
        let mut evidence = evidence("s4", "artifact:s4", "status", "ready");
        evidence.aliases.push("compact".to_string());
        let err = project(&request(
            50,
            vec![claim("compact", "status")],
            vec![evidence],
        ))
        .unwrap_err();
        assert!(matches!(err, TruthProjectionError::AliasCollision { .. }));
    }

    #[test]
    fn relationship_to_unavailable_target_fails_closed() {
        let mut item = evidence("new", "project:a", "status", "ready");
        item.supersedes.push(relation("missing", 20));
        let err = project(&request(50, vec![], vec![item])).unwrap_err();
        assert_eq!(
            err,
            TruthProjectionError::DanglingRelationship {
                source_id: "new".to_string(),
                target_id: "missing".to_string(),
            }
        );
    }

    #[test]
    fn relationship_cycle_fails_closed() {
        let mut a = evidence("a", "project:a", "status", "one");
        let mut b = evidence("b", "project:a", "status", "two");
        a.supersedes.push(relation("b", 20));
        b.supersedes.push(relation("a", 20));
        let err = project(&request(50, vec![], vec![a, b])).unwrap_err();
        assert_eq!(
            err,
            TruthProjectionError::RelationshipCycle {
                evidence_ids: vec!["a".to_string(), "b".to_string()]
            }
        );
    }

    #[test]
    fn lower_tier_cannot_suppress_higher_tier() {
        let mut low = evidence("low", "project:a", "status", "ready");
        low.truth_tier = TruthTier::Inferred;
        low.invalidates.push(relation("high", 20));
        let mut high = evidence("high", "project:a", "status", "blocked");
        high.truth_tier = TruthTier::Verified;

        let err = project(&request(50, vec![], vec![low, high])).unwrap_err();
        assert!(matches!(
            err,
            TruthProjectionError::InsufficientRelationshipAuthority { .. }
        ));
    }

    #[test]
    fn cross_claim_relationship_fails_closed() {
        let mut status = evidence("status", "project:a", "status", "ready");
        status.invalidates.push(relation("risk", 20));
        let risk = evidence("risk", "project:a", "risk", "high");
        let err = project(&request(50, vec![], vec![status, risk])).unwrap_err();
        assert!(matches!(
            err,
            TruthProjectionError::CrossClaimRelationship { .. }
        ));
    }

    #[test]
    fn dual_relationship_kind_and_conflicting_times_fail_closed() {
        let target = evidence("target", "project:a", "status", "old");
        let mut dual = evidence("dual", "project:a", "status", "new");
        dual.supersedes.push(relation("target", 20));
        dual.invalidates.push(relation("target", 20));
        assert!(matches!(
            project(&request(50, vec![], vec![dual, target.clone()])).unwrap_err(),
            TruthProjectionError::ConflictingRelationshipKind { .. }
        ));

        let mut times = evidence("times", "project:a", "status", "new");
        times.supersedes.push(relation("target", 20));
        times.supersedes.push(relation("target", 30));
        assert!(matches!(
            project(&request(50, vec![], vec![times, target])).unwrap_err(),
            TruthProjectionError::ConflictingRelationshipEffectiveTime { .. }
        ));
    }

    #[test]
    fn non_ascii_alias_is_rejected_before_collision_matching() {
        let mut item = evidence("item", "project:a", "status", "ready");
        item.aliases.push("ｃompact".to_string());
        let err = project(&request(50, vec![], vec![item])).unwrap_err();
        assert!(matches!(err, TruthProjectionError::InvalidLabel { .. }));
    }

    #[test]
    fn archived_is_historical_and_tombstoned_is_excluded() {
        let mut archived = evidence("archived", "project:a", "status", "old");
        archived.lifecycle = LifecycleState::Archived { effective_from: 20 };
        let mut tombstoned = evidence("tomb", "project:b", "status", "secret");
        tombstoned.lifecycle = LifecycleState::Tombstoned;

        let projection = project(&request(
            50,
            vec![],
            vec![tombstoned.clone(), archived.clone()],
        ))
        .unwrap();
        assert_eq!(projection.claims.len(), 1);
        assert_eq!(
            projection.claims[0].temporal_state,
            TemporalState::Historical
        );
        assert_eq!(projection.claims[0].values, ["old"]);
        assert_eq!(
            projection,
            project(&request(50, vec![], vec![archived])).unwrap()
        );
    }

    #[test]
    fn tombstone_retroactively_redacts_every_revision_in_its_lineage() {
        let required = claim("project:a", "credential_state");
        let mut active = evidence("revision_1", "project:a", "credential_state", "present");
        active.lineage_id = "lineage:credential".to_string();
        let baseline = project(&request(50, vec![required.clone()], vec![active.clone()])).unwrap();
        assert_eq!(only_claim(&baseline).truth_state, TruthState::Supported);

        let mut tombstone = evidence("revision_2", "project:a", "credential_state", "redacted");
        tombstone.lineage_id = "lineage:credential".to_string();
        tombstone.lifecycle = LifecycleState::Tombstoned;
        // Privacy redaction intentionally overrides historical knowledge cutoff.
        tombstone.recorded_at = 90;
        let mut input = request(50, vec![required], vec![active, tombstone]);
        input.knowledge_cutoff = 60;
        let redacted = project(&input).unwrap();
        let result = only_claim(&redacted);
        assert_eq!(result.truth_state, TruthState::Unknown);
        assert!(result.values.is_empty());
        assert!(result.evidence_dispositions.is_empty());
    }

    #[test]
    fn latest_lineage_revision_is_selected_at_knowledge_cutoff() {
        let mut old = evidence("revision_1", "project:a", "status", "planned");
        old.lineage_id = "lineage:status".to_string();
        let mut newer = evidence("revision_2", "project:a", "status", "ready");
        newer.lineage_id = "lineage:status".to_string();
        newer.recorded_at = 90;
        newer.observed_at = 80;

        let mut historical_knowledge = request(50, vec![], vec![old.clone(), newer.clone()]);
        historical_knowledge.knowledge_cutoff = 60;
        let before_new_revision = project(&historical_knowledge).unwrap();
        assert_eq!(only_claim(&before_new_revision).values, ["planned"]);
        assert_eq!(
            only_claim(&before_new_revision).evidence_ids,
            ["revision_1"]
        );

        let current_knowledge = project(&request(50, vec![], vec![old, newer])).unwrap();
        assert_eq!(only_claim(&current_knowledge).values, ["ready"]);
        assert_eq!(only_claim(&current_knowledge).evidence_ids, ["revision_2"]);
    }

    #[test]
    fn same_lineage_same_recorded_at_is_ambiguous() {
        let mut first = evidence("revision_1", "project:a", "status", "planned");
        first.lineage_id = "lineage:status".to_string();
        let mut second = evidence("revision_2", "project:a", "status", "ready");
        second.lineage_id = "lineage:status".to_string();

        assert!(matches!(
            project(&request(50, vec![], vec![first, second])).unwrap_err(),
            TruthProjectionError::AmbiguousLineageRevision { .. }
        ));
    }

    #[test]
    fn relationship_targets_selected_lineage_revision() {
        let mut old = evidence("target_revision_1", "project:a", "status", "old");
        old.lineage_id = "lineage:target".to_string();
        let mut newer = evidence("target_revision_2", "project:a", "status", "stale");
        newer.lineage_id = "lineage:target".to_string();
        newer.recorded_at = 20;
        newer.observed_at = 20;
        let mut source = evidence("source", "project:a", "status", "current");
        source.invalidates.push(relation("lineage:target", 30));

        let projection = project(&request(50, vec![], vec![old, newer, source])).unwrap();
        let result = only_claim(&projection);
        assert_eq!(result.values, ["current"]);
        assert_eq!(result.noncurrent_evidence_ids, ["target_revision_2"]);
    }

    #[test]
    fn later_revision_can_carry_forward_a_durable_relationship() {
        let target = evidence("target", "project:a", "status", "old");
        let mut first = evidence("source_revision_1", "project:a", "status", "current");
        first.lineage_id = "lineage:source".to_string();
        first.invalidates.push(relation("target", 20));
        let mut newer = first.clone();
        newer.evidence_id = "source_revision_2".to_string();
        newer.recorded_at = 30;
        newer.observed_at = 30;

        let projection = project(&request(50, vec![], vec![first, newer, target])).unwrap();
        let result = only_claim(&projection);
        assert_eq!(result.evidence_ids, ["source_revision_2"]);
        assert_eq!(result.noncurrent_evidence_ids, ["target"]);
    }

    #[test]
    fn lineage_claim_drift_and_dropped_relationship_history_fail_closed() {
        let mut first = evidence("revision_1", "project:a", "status", "old");
        first.lineage_id = "lineage:source".to_string();
        let mut drift = evidence("revision_2", "project:a", "risk", "low");
        drift.lineage_id = "lineage:source".to_string();
        drift.recorded_at = 20;
        drift.observed_at = 20;
        assert_eq!(
            project(&request(50, vec![], vec![first.clone(), drift])).unwrap_err(),
            TruthProjectionError::LineageClaimDrift
        );

        let target = evidence("target", "project:a", "status", "old");
        first.supersedes.push(relation("target", 10));
        let mut drops = evidence("revision_3", "project:a", "status", "new");
        drops.lineage_id = "lineage:source".to_string();
        drops.recorded_at = 30;
        drops.observed_at = 30;
        assert!(matches!(
            project(&request(50, vec![], vec![first, drops, target])).unwrap_err(),
            TruthProjectionError::RelationshipHistoryDropped { .. }
        ));
    }

    #[test]
    fn redacted_target_edges_are_pruned_but_redacted_governance_source_fails_closed() {
        let mut source = evidence("source", "project:a", "status", "current");
        source.invalidates.push(relation("target-lineage", 20));
        let mut target = evidence("target", "project:a", "status", "old");
        target.lineage_id = "target-lineage".to_string();
        let mut target_tombstone = evidence("target-tomb", "project:a", "status", "redacted");
        target_tombstone.lineage_id = "target-lineage".to_string();
        target_tombstone.lifecycle = LifecycleState::Tombstoned;

        let projection = project(&request(
            50,
            vec![],
            vec![source.clone(), target, target_tombstone],
        ))
        .unwrap();
        assert_eq!(only_claim(&projection).evidence_ids, ["source"]);

        let mut source_tombstone = evidence("source-tomb", "project:a", "status", "redacted");
        source_tombstone.lineage_id = source.lineage_id.clone();
        source_tombstone.lifecycle = LifecycleState::Tombstoned;
        assert_eq!(
            project(&request(50, vec![], vec![source, source_tombstone])).unwrap_err(),
            TruthProjectionError::TombstonedGovernanceSource
        );
    }

    #[test]
    fn invalid_interval_and_duplicate_ids_are_rejected() {
        let mut invalid = evidence("bad", "project:a", "status", "ready");
        invalid.validity = TemporalValidity::Bounded {
            valid_from: Some(20),
            valid_until: Some(19),
        };
        assert!(matches!(
            project(&request(50, vec![], vec![invalid])).unwrap_err(),
            TruthProjectionError::InvalidValidityInterval { .. }
        ));

        let duplicate = evidence("same", "project:a", "status", "ready");
        assert!(matches!(
            project(&request(50, vec![], vec![duplicate.clone(), duplicate])).unwrap_err(),
            TruthProjectionError::DuplicateEvidenceId { .. }
        ));

        let mut empty_bounded = evidence("empty", "project:a", "status", "ready");
        empty_bounded.validity = TemporalValidity::Bounded {
            valid_from: None,
            valid_until: None,
        };
        assert_eq!(
            project(&request(50, vec![], vec![empty_bounded])).unwrap_err(),
            TruthProjectionError::EmptyBoundedValidity {
                evidence_id: "empty".to_string()
            }
        );
    }

    #[test]
    fn request_json_rejects_unknown_extension_fields() {
        let value = serde_json::json!({
            "as_of": 10,
            "knowledge_cutoff": 10,
            "required_claims": [],
            "evidence": [],
            "extension": "must-not-be-ignored"
        });
        let err = serde_json::from_value::<TruthProjectionRequest>(value).unwrap_err();
        assert!(err.to_string().contains("unknown field"));
    }

    #[test]
    fn canonical_output_is_identical_after_input_permutation() {
        let mut v1 = evidence("v1", "project:a", "status", "planned");
        v1.aliases = vec!["Alpha".to_string(), "A".to_string()];
        let mut v2 = evidence("v2", "project:a", "status", "ready");
        v2.aliases = vec!["A".to_string(), "Alpha".to_string()];
        v2.supersedes.push(relation("v1", 20));
        let risk = evidence("risk", "project:a", "risk", "low");

        let forward = project(&request(
            50,
            vec![claim("project:z", "status")],
            vec![v1.clone(), v2.clone(), risk.clone()],
        ))
        .unwrap();
        let reverse = project(&request(
            50,
            vec![claim("project:z", "status")],
            vec![risk, v2, v1],
        ))
        .unwrap();
        assert_eq!(forward, reverse);
        assert_eq!(
            serde_json::to_vec(&forward).unwrap(),
            serde_json::to_vec(&reverse).unwrap()
        );
    }
}
