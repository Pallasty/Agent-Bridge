//! Fail-closed completeness preflight for future temporal-truth adapters.
//!
//! The public evaluator accepts only an opaque, producer-bound
//! [`ab_store::MemoryEvidenceSnapshot`]. It never converts store rows into
//! truth evidence and never invokes [`crate::memory_truth::project`]. A future
//! adapter must pass every gap here before a separate, reviewed mapping layer
//! may exist.

use ab_store::{MemoryEvidenceProfile, MemoryEvidenceSnapshot};
use serde::Serialize;

pub const TRUTH_ADAPTER_PREFLIGHT_SCHEMA: &str = "agent_bridge.truth_adapter_preflight.v0";
pub const TRUTH_ADAPTER_PREFLIGHT_MODE: &str = "preflight_only";

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TruthAdapterGap {
    ExactReadHasSideEffects,
    SnapshotNotAtomic,
    SnapshotTruncated,
    CompleteLineageRevisionHistoryUnavailable,
    UniqueLineageRevisionOrderUnavailable,
    CompleteTombstoneGovernanceIndexUnavailable,
    AllRelationshipChannelsAndHistoryUnavailable,
    RelationshipEndpointClosureUnprovable,
    RetainedRelationshipEndpointMissing,
    TombstoneRelationshipRedacted,
    DurableGovernanceAttestationUnavailable,
    ExplicitTemporalClaimProvenanceBindingsUnavailable,
    PredicateScopedAuthorityPolicyUnavailable,
    UnrecognizedProducerProfile,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TruthAdapterPreflight {
    pub schema: String,
    pub mode: String,
    pub adapter_allowed: bool,
    pub gaps: Vec<TruthAdapterGap>,
}

#[derive(Debug, Clone, Copy)]
struct ProducerFacts {
    recognized_profile: bool,
    exact_read_side_effect_free: bool,
    single_read_snapshot: bool,
    complete_lineage_revision_history_in_snapshot: bool,
    unique_lineage_revision_order_in_snapshot: bool,
    complete_tombstone_governance_index_in_snapshot: bool,
    all_relationship_channels_and_history_in_snapshot: bool,
    relationship_endpoint_closure_provable: bool,
    durable_governance_attestation: bool,
    explicit_temporal_claim_provenance_bindings: bool,
    predicate_scoped_authority_policy: bool,
}

impl ProducerFacts {
    #[cfg(test)]
    fn complete() -> Self {
        Self {
            recognized_profile: true,
            exact_read_side_effect_free: true,
            single_read_snapshot: true,
            complete_lineage_revision_history_in_snapshot: true,
            unique_lineage_revision_order_in_snapshot: true,
            complete_tombstone_governance_index_in_snapshot: true,
            all_relationship_channels_and_history_in_snapshot: true,
            relationship_endpoint_closure_provable: true,
            durable_governance_attestation: true,
            explicit_temporal_claim_provenance_bindings: true,
            predicate_scoped_authority_policy: true,
        }
    }
}

fn producer_facts(profile: MemoryEvidenceProfile) -> ProducerFacts {
    match profile {
        MemoryEvidenceProfile::MutableSqliteV41 => ProducerFacts {
            recognized_profile: true,
            exact_read_side_effect_free: true,
            single_read_snapshot: true,
            complete_lineage_revision_history_in_snapshot: false,
            unique_lineage_revision_order_in_snapshot: false,
            complete_tombstone_governance_index_in_snapshot: false,
            all_relationship_channels_and_history_in_snapshot: false,
            relationship_endpoint_closure_provable: false,
            durable_governance_attestation: false,
            explicit_temporal_claim_provenance_bindings: false,
            predicate_scoped_authority_policy: false,
        },
        _ => ProducerFacts {
            recognized_profile: false,
            exact_read_side_effect_free: false,
            single_read_snapshot: false,
            complete_lineage_revision_history_in_snapshot: false,
            unique_lineage_revision_order_in_snapshot: false,
            complete_tombstone_governance_index_in_snapshot: false,
            all_relationship_channels_and_history_in_snapshot: false,
            relationship_endpoint_closure_provable: false,
            durable_governance_attestation: false,
            explicit_temporal_claim_provenance_bindings: false,
            predicate_scoped_authority_policy: false,
        },
    }
}

fn evaluate(
    facts: ProducerFacts,
    truncated: bool,
    retained_edge_endpoints_closed: bool,
    tombstone_relationships_redacted: bool,
) -> TruthAdapterPreflight {
    let mut gaps = Vec::new();
    if !facts.recognized_profile {
        gaps.push(TruthAdapterGap::UnrecognizedProducerProfile);
    }
    if !facts.exact_read_side_effect_free {
        gaps.push(TruthAdapterGap::ExactReadHasSideEffects);
    }
    if !facts.single_read_snapshot {
        gaps.push(TruthAdapterGap::SnapshotNotAtomic);
    }
    if truncated {
        gaps.push(TruthAdapterGap::SnapshotTruncated);
    }
    if !facts.complete_lineage_revision_history_in_snapshot {
        gaps.push(TruthAdapterGap::CompleteLineageRevisionHistoryUnavailable);
    }
    if !facts.unique_lineage_revision_order_in_snapshot {
        gaps.push(TruthAdapterGap::UniqueLineageRevisionOrderUnavailable);
    }
    if !facts.complete_tombstone_governance_index_in_snapshot {
        gaps.push(TruthAdapterGap::CompleteTombstoneGovernanceIndexUnavailable);
    }
    if !facts.all_relationship_channels_and_history_in_snapshot {
        gaps.push(TruthAdapterGap::AllRelationshipChannelsAndHistoryUnavailable);
    }
    if !facts.relationship_endpoint_closure_provable {
        gaps.push(TruthAdapterGap::RelationshipEndpointClosureUnprovable);
    }
    if !retained_edge_endpoints_closed {
        gaps.push(TruthAdapterGap::RetainedRelationshipEndpointMissing);
    }
    if tombstone_relationships_redacted {
        gaps.push(TruthAdapterGap::TombstoneRelationshipRedacted);
    }
    if !facts.durable_governance_attestation {
        gaps.push(TruthAdapterGap::DurableGovernanceAttestationUnavailable);
    }
    if !facts.explicit_temporal_claim_provenance_bindings {
        gaps.push(TruthAdapterGap::ExplicitTemporalClaimProvenanceBindingsUnavailable);
    }
    if !facts.predicate_scoped_authority_policy {
        gaps.push(TruthAdapterGap::PredicateScopedAuthorityPolicyUnavailable);
    }
    gaps.sort();
    gaps.dedup();

    TruthAdapterPreflight {
        schema: TRUTH_ADAPTER_PREFLIGHT_SCHEMA.to_string(),
        mode: TRUTH_ADAPTER_PREFLIGHT_MODE.to_string(),
        adapter_allowed: gaps.is_empty(),
        gaps,
    }
}

/// Evaluate only facts bound to the producing store profile plus dynamic
/// integrity flags exposed by the opaque snapshot. Raw rows, values, keys, and
/// tombstone ids cannot enter the serialized result through this function.
pub fn preflight(snapshot: &MemoryEvidenceSnapshot) -> TruthAdapterPreflight {
    evaluate(
        producer_facts(snapshot.profile()),
        snapshot.truncated(),
        snapshot.retained_edge_endpoints_closed(),
        snapshot.tombstone_relationships_redacted(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_store::{MemoryEvidenceSnapshotLimits, MemoryRecord, SqliteStore, StateStore};

    #[test]
    fn complete_producer_facts_are_the_only_admissible_shape() {
        let report = evaluate(ProducerFacts::complete(), false, true, false);
        assert!(report.adapter_allowed);
        assert!(report.gaps.is_empty());
        assert_eq!(report.schema, TRUTH_ADAPTER_PREFLIGHT_SCHEMA);
        assert_eq!(report.mode, TRUTH_ADAPTER_PREFLIGHT_MODE);
    }

    #[test]
    fn every_producer_fact_independently_fails_closed() {
        let mutations: &[fn(&mut ProducerFacts)] = &[
            |facts| facts.recognized_profile = false,
            |facts| facts.exact_read_side_effect_free = false,
            |facts| facts.single_read_snapshot = false,
            |facts| facts.complete_lineage_revision_history_in_snapshot = false,
            |facts| facts.unique_lineage_revision_order_in_snapshot = false,
            |facts| facts.complete_tombstone_governance_index_in_snapshot = false,
            |facts| facts.all_relationship_channels_and_history_in_snapshot = false,
            |facts| facts.relationship_endpoint_closure_provable = false,
            |facts| facts.durable_governance_attestation = false,
            |facts| facts.explicit_temporal_claim_provenance_bindings = false,
            |facts| facts.predicate_scoped_authority_policy = false,
        ];
        for mutate in mutations {
            let mut facts = ProducerFacts::complete();
            mutate(&mut facts);
            assert!(!evaluate(facts, false, true, false).adapter_allowed);
        }
    }

    #[test]
    fn truncation_dangling_and_redaction_are_independent_blockers() {
        assert!(!evaluate(ProducerFacts::complete(), true, true, false).adapter_allowed);
        assert!(!evaluate(ProducerFacts::complete(), false, false, false).adapter_allowed);
        assert!(!evaluate(ProducerFacts::complete(), false, true, true).adapter_allowed);
    }

    #[tokio::test]
    async fn current_sqlite_snapshot_is_rejected_end_to_end_without_raw_output() {
        let dir = tempfile::tempdir().expect("tempdir");
        let store = SqliteStore::open(&dir.path().join("state.db"))
            .await
            .expect("open store");
        store
            .memory_save(&MemoryRecord {
                key: "preflight-sentinel-key".into(),
                kind: "fact".into(),
                content: "preflight-sentinel-content".into(),
                tags: vec!["preflight-sentinel-tag".into()],
                related_keys: Vec::new(),
                scope: None,
                created_at: 1,
                updated_at: 1,
                last_accessed_at: 1,
                access_count: 0,
                importance: 0.5,
                status: "active".into(),
                trigger_pattern: None,
                superseded_by: None,
            })
            .await
            .expect("save sentinel");
        let snapshot = store
            .memory_evidence_snapshot(MemoryEvidenceSnapshotLimits::default())
            .await
            .expect("snapshot");
        let report = preflight(&snapshot);
        assert!(!report.adapter_allowed);
        assert_eq!(report.gaps.len(), 8);
        assert!(report
            .gaps
            .contains(&TruthAdapterGap::CompleteLineageRevisionHistoryUnavailable));
        assert!(report
            .gaps
            .contains(&TruthAdapterGap::ExplicitTemporalClaimProvenanceBindingsUnavailable));
        let encoded = serde_json::to_string(&report).unwrap();
        for sentinel in [
            "preflight-sentinel-key",
            "preflight-sentinel-content",
            "preflight-sentinel-tag",
        ] {
            assert!(!encoded.contains(sentinel));
        }
    }
}
