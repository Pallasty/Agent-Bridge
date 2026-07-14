//! Crate-private bridge for the default-off S4 synthetic projection feature.
//!
//! This module intentionally has no CLI, MCP, daemon, or BioCortex runtime
//! caller. It forwards exactly one consumed store permit into the store-owned
//! atomic read/map/project/seal operation and never receives the raw ledger.

use std::path::Path;

use ab_store::{
    temporal_truth_project_read_only_synthetic_v1, BoundTemporalTruthProjectionV1,
    SyntheticTemporalTruthProjectionPermitV1, TemporalTruthProjectionRequestV1,
    TemporalTruthProjectionV1Error,
};

pub(crate) async fn project_synthetic_temporal_evidence_v1(
    permit: SyntheticTemporalTruthProjectionPermitV1,
    database: &Path,
    request: TemporalTruthProjectionRequestV1,
) -> Result<BoundTemporalTruthProjectionV1, TemporalTruthProjectionV1Error> {
    temporal_truth_project_read_only_synthetic_v1(permit, database, request).await
}
