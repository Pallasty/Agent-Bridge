//! Crate-private S5 candidate-evidence source-artifact binding.
//!
//! There is intentionally no CLI, MCP, daemon, network, or BioCortex runtime
//! caller. The wrapper only consumes already-sealed store objects.

use ab_store::{
    bind_synthetic_track_b_candidate_evidence_v1 as bind_store_candidate_evidence_v1,
    BoundTrackBCandidateEvidenceV1, SyntheticTrackBCandidateEvidencePermitV1,
    SyntheticTrackBCandidateProjectionPairV1, TrackBCandidateEvidenceV1Error,
};

pub(crate) fn bind_synthetic_track_b_candidate_evidence_v1(
    permit: SyntheticTrackBCandidateEvidencePermitV1,
    pair: SyntheticTrackBCandidateProjectionPairV1,
    evaluated_at_utc: i64,
) -> Result<BoundTrackBCandidateEvidenceV1, TrackBCandidateEvidenceV1Error> {
    bind_store_candidate_evidence_v1(permit, pair, evaluated_at_utc)
}
