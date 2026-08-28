//! Durable workload-receipt commit and restart reconciliation.
//!
//! The cgroup supervisor owns a private, persistent outbox.  SQLite commit is
//! the acknowledgement boundary; filesystem cleanup is an idempotent effect
//! performed only after that commit.  A recovered receipt proves its bounded
//! workload-accounting claim, but never fabricates the body before/after
//! observations that were process-local when the daemon stopped.

use crate::semantic_event::{Affordance, SemanticEvent, SemanticObject, Verdict, VerdictStatus};
use ab_core::{Error, Result};
use ab_store::{
    workload_receipt_commit_record_sha256, SemanticEventRecord, StateStore,
    WorkloadReceiptCommitKind, WorkloadReceiptCommitRecord, WorkloadReceiptCommitStatus,
    WORKLOAD_RECEIPT_COMMIT_SCHEMA_V1,
};
use serde::Serialize;
use serde_json::{json, Value};
use std::sync::Arc;
use std::time::Duration;

pub const WORKLOAD_RECEIPT_RECONCILIATION_SCHEMA_V1: &str =
    "agent_bridge.workload_receipt_reconciliation.v1";
const STARTUP_SEAL_GRACE: Duration = Duration::from_secs(3);
const STARTUP_RESCAN_INTERVAL: Duration = Duration::from_millis(100);

#[derive(Debug, Clone, Serialize, Default)]
pub struct WorkloadReceiptReconciliationReport {
    pub scanned_receipts: usize,
    pub inserted_commits: usize,
    pub duplicate_commits: usize,
    pub conflicts: usize,
    pub acknowledged: usize,
    pub already_acknowledged: usize,
    pub acknowledgement_failures: usize,
    pub unresolved: usize,
    pub active_producers: usize,
    pub invalid: usize,
    pub commit_failures: usize,
}

#[derive(Debug, Clone)]
pub struct WorkloadReceiptCommitAckOutcome {
    pub status: WorkloadReceiptCommitStatus,
    /// True when this call inserted the requested event, or an idempotent
    /// replay found an already committed projection with the same kind and
    /// canonical public facts. Receipt identity alone is not enough to make a
    /// different requested projection look recorded.
    pub event_projection_present: bool,
    pub acknowledged: usize,
    pub already_acknowledged: usize,
    pub acknowledgement_failures: usize,
}

fn canonical_json(value: &Value) -> Result<String> {
    let bytes = serde_json_canonicalizer::to_vec(value)
        .map_err(|error| Error::Backend(format!("canonicalize workload receipt facts: {error}")))?;
    String::from_utf8(bytes)
        .map_err(|error| Error::Backend(format!("encode workload receipt facts: {error}")))
}

fn commit_records(
    references: &[ab_agent::DurableWorkloadReceiptRef],
    span_id: &str,
    recorded_at: i64,
    commit_kind: WorkloadReceiptCommitKind,
    redacted_facts: &Value,
) -> Result<Vec<WorkloadReceiptCommitRecord>> {
    let redacted_facts_json = canonical_json(redacted_facts)?;
    references
        .iter()
        .map(|reference| {
            let mut record = WorkloadReceiptCommitRecord {
                schema_version: WORKLOAD_RECEIPT_COMMIT_SCHEMA_V1.to_string(),
                receipt_id: reference.receipt_id.clone(),
                span_id: span_id.to_string(),
                recorded_at,
                receipt_sha256: reference.sha256.clone(),
                commit_kind,
                redacted_facts_json: redacted_facts_json.clone(),
                record_sha256: String::new(),
            };
            record.record_sha256 = workload_receipt_commit_record_sha256(&record)?;
            Ok(record)
        })
        .collect()
}

/// Atomically admit one or more receipt identities with their semantic event,
/// then publish the filesystem ACK effect.  Store failure or conflict leaves
/// every outbox entry untouched for inspection/retry.
async fn commit_startup_workload_receipt_event_and_ack(
    store: &Arc<dyn StateStore>,
    references: &[ab_agent::DurableWorkloadReceiptRef],
    span_id: &str,
    recorded_at: i64,
    redacted_facts: &Value,
    event: SemanticEventRecord,
) -> Result<WorkloadReceiptCommitAckOutcome> {
    commit_workload_receipt_event_with_ack(
        store,
        references,
        span_id,
        recorded_at,
        WorkloadReceiptCommitKind::StartupReconciliation,
        redacted_facts,
        event,
        ab_agent::workload_cgroup::acknowledge_durable_workload_receipt,
    )
    .await
}

/// Live body-span variant: the owning span must hand off every exact producer
/// lease before Store commit. That lease remains held through the digest-bound
/// owner ACK, so a peer startup scanner cannot substitute a reconciliation
/// projection between terminal extraction and live event persistence.
pub(crate) async fn commit_live_workload_receipt_event_and_ack(
    store: &Arc<dyn StateStore>,
    references: &[ab_agent::DurableWorkloadReceiptRef],
    lease_guard: &ab_agent::DurableWorkloadReceiptLeaseGuard,
    span_id: &str,
    recorded_at: i64,
    redacted_facts: &Value,
    event: SemanticEventRecord,
) -> Result<WorkloadReceiptCommitAckOutcome> {
    let unique_receipt_ids = references
        .iter()
        .map(|reference| reference.receipt_id.as_str())
        .collect::<std::collections::HashSet<_>>();
    if references.is_empty()
        || unique_receipt_ids.len() != references.len()
        || !lease_guard.covers_all(references)
    {
        return Err(Error::InvalidArgument(
            "live durable workload commit requires one owned producer lease per unique receipt"
                .into(),
        ));
    }
    commit_workload_receipt_event_with_ack(
        store,
        references,
        span_id,
        recorded_at,
        WorkloadReceiptCommitKind::LiveBodySpan,
        redacted_facts,
        event,
        |reference| lease_guard.acknowledge(reference),
    )
    .await
}

async fn commit_workload_receipt_event_with_ack<F>(
    store: &Arc<dyn StateStore>,
    references: &[ab_agent::DurableWorkloadReceiptRef],
    span_id: &str,
    recorded_at: i64,
    commit_kind: WorkloadReceiptCommitKind,
    redacted_facts: &Value,
    event: SemanticEventRecord,
    mut acknowledge: F,
) -> Result<WorkloadReceiptCommitAckOutcome>
where
    F: FnMut(&ab_agent::DurableWorkloadReceiptRef) -> Result<bool>,
{
    if references.is_empty() {
        return Err(Error::InvalidArgument(
            "durable workload receipt commit requires at least one receipt".into(),
        ));
    }
    let records = commit_records(
        references,
        span_id,
        recorded_at,
        commit_kind,
        redacted_facts,
    )?;
    let status = store.commit_workload_receipt_event(records, event).await?;
    let event_projection_present = match status {
        WorkloadReceiptCommitStatus::Inserted => true,
        WorkloadReceiptCommitStatus::Conflict => false,
        WorkloadReceiptCommitStatus::Duplicate => {
            let requested_facts = canonical_json(redacted_facts)?;
            let mut projection_present = true;
            for reference in references {
                match store
                    .load_workload_receipt_commit(&reference.receipt_id)
                    .await
                {
                    Ok(Some(existing))
                        if existing.span_id == span_id
                            && existing.receipt_sha256 == reference.sha256
                            && existing.commit_kind == commit_kind
                            && existing.redacted_facts_json == requested_facts => {}
                    Ok(_) => projection_present = false,
                    Err(error) => {
                        projection_present = false;
                        tracing::warn!(
                            receipt_id = %reference.receipt_id,
                            %error,
                            "durable workload receipt replay committed, but projection lookup failed"
                        );
                    }
                }
            }
            projection_present
        }
    };
    let mut outcome = WorkloadReceiptCommitAckOutcome {
        status,
        event_projection_present,
        acknowledged: 0,
        already_acknowledged: 0,
        acknowledgement_failures: 0,
    };
    if status == WorkloadReceiptCommitStatus::Conflict {
        return Ok(outcome);
    }
    for reference in references {
        match acknowledge(reference) {
            Ok(true) => outcome.acknowledged += 1,
            Ok(false) => outcome.already_acknowledged += 1,
            Err(error) => {
                outcome.acknowledgement_failures += 1;
                tracing::warn!(
                    receipt_id = %reference.receipt_id,
                    %error,
                    "durable workload receipt committed but ACK cleanup failed"
                );
            }
        }
    }
    Ok(outcome)
}

fn recovered_receipt_is_complete(record: &ab_agent::DurableWorkloadReceiptRecord) -> bool {
    let resources = &record.resources;
    resources.status == ab_agent::WorkloadResourceStatus::Complete
        && resources.populated_zero_observed
        && resources.start_before_exec
        && resources.complete_for_cpu_memory_workload_tree
        && resources.generation_count == 1
        && resources.captured_generation_count == 1
        && resources.cpu_usage_usec.is_some()
        && resources.cpu_user_usec.is_some()
        && resources.cpu_system_usec.is_some()
        && resources.memory_peak_bytes.is_some()
        && resources.controllers.iter().any(|value| value == "cpu")
        && resources.controllers.iter().any(|value| value == "memory")
}

fn recovered_event(
    record: &ab_agent::DurableWorkloadReceiptRecord,
    recorded_at: i64,
) -> Result<(Value, SemanticEventRecord)> {
    let complete = recovered_receipt_is_complete(record);
    let facts = json!({
        "schema_version": WORKLOAD_RECEIPT_RECONCILIATION_SCHEMA_V1,
        "receipt_id": record.receipt_ref.receipt_id,
        "span_id": record.span_id,
        "runtime": record.runtime,
        "recovery_scope": "standalone_workload_accounting",
        "body_before_after_recovered": false,
        "task_span_closed_reconstructed": false,
        "resources": record.resources,
    });
    let event = SemanticEvent {
        ts: recorded_at,
        actor: "node".to_string(),
        source: "body_telemetry".to_string(),
        action: "workload_receipt_reconciled".to_string(),
        target: Some(record.span_id.clone()),
        object: SemanticObject {
            object_type: "task_workload_receipt".to_string(),
            source_adapter: "body_telemetry".to_string(),
            label: Some(record.runtime.clone()),
            object_id: Some(record.receipt_ref.receipt_id.clone()),
        },
        affordance: Affordance {
            action_type: "observe".to_string(),
            risk_level: "low".to_string(),
            requires_gate: false,
            expected_effect: Some(
                "commit one restart-reconciled standalone workload receipt".to_string(),
            ),
        },
        verdict: Verdict {
            status: if complete {
                VerdictStatus::Verified
            } else {
                VerdictStatus::Unknown
            },
            method: if complete {
                "restart_reconciled_durable_cgroup_receipt"
            } else {
                "restart_reconciled_incomplete_cgroup_receipt"
            }
            .to_string(),
            evidence: json!({
                "durable_manifest_binding_verified": true,
                "terminal_receipt_digest_verified": true,
                "final_populated_zero": record.resources.populated_zero_observed,
                "standalone_workload_accounting_only": true,
                "body_before_after_recovered": false,
            }),
        },
        facts: facts.clone(),
    };
    Ok((facts, event.to_record()))
}

fn startup_scan_needs_seal_grace(scan: &ab_agent::DurableWorkloadReceiptScan) -> bool {
    scan.unresolved
        .iter()
        .any(|issue| issue.state == "receipt_commit_unknown")
}

/// Scan and reconcile the persistent supervisor outbox before the Bridge opens
/// an MCP/HTTP serving surface.  Individual invalid/pending entries remain
/// non-green and unacknowledged; one bad entry does not hide other recoverable
/// receipts.
pub async fn reconcile_workload_receipt_spool(
    store: &Arc<dyn StateStore>,
) -> Result<WorkloadReceiptReconciliationReport> {
    // A supervisor inherited from the previous Bridge detects parent EOF and
    // may need its bounded TERM -> KILL grace before it can seal the terminal
    // receipt. Keep the serving surface closed during a matching bounded scan
    // grace. Anything still unsealed afterwards remains explicitly unknown.
    let deadline = tokio::time::Instant::now() + STARTUP_SEAL_GRACE;
    let scan = loop {
        let scan =
            tokio::task::spawn_blocking(ab_agent::workload_cgroup::scan_durable_workload_receipts)
                .await
                .map_err(|error| {
                    Error::Backend(format!("join workload receipt scan: {error}"))
                })??;
        // A healthy peer Bridge holds the producer lease for its own live
        // entries. It must not add a fixed startup delay here. Only an
        // ownerless manifest whose supervisor may still be sealing a receipt
        // receives the bounded restart grace.
        let receipt_may_still_seal = startup_scan_needs_seal_grace(&scan);
        if !receipt_may_still_seal || tokio::time::Instant::now() >= deadline {
            break scan;
        }
        tokio::time::sleep(STARTUP_RESCAN_INTERVAL).await;
    };
    let mut report = WorkloadReceiptReconciliationReport {
        scanned_receipts: scan.receipts.len(),
        unresolved: scan.unresolved.len(),
        active_producers: scan
            .unresolved
            .iter()
            .filter(|issue| issue.state == "producer_active")
            .count(),
        invalid: scan.issues.len(),
        ..WorkloadReceiptReconciliationReport::default()
    };
    for issue in scan.unresolved.iter().chain(scan.issues.iter()) {
        tracing::warn!(
            receipt_id = issue.receipt_id.as_deref().unwrap_or("unknown"),
            state = %issue.state,
            reason = %issue.reason,
            "durable workload receipt was not eligible for restart commit"
        );
    }
    for record in scan.receipts {
        let recorded_at = ab_store::now_secs();
        let (facts, event) = recovered_event(&record, recorded_at)?;
        match commit_startup_workload_receipt_event_and_ack(
            store,
            std::slice::from_ref(&record.receipt_ref),
            &record.span_id,
            recorded_at,
            &facts,
            event,
        )
        .await
        {
            Ok(outcome) => {
                match outcome.status {
                    WorkloadReceiptCommitStatus::Inserted => report.inserted_commits += 1,
                    WorkloadReceiptCommitStatus::Duplicate => report.duplicate_commits += 1,
                    WorkloadReceiptCommitStatus::Conflict => report.conflicts += 1,
                }
                report.acknowledged += outcome.acknowledged;
                report.already_acknowledged += outcome.already_acknowledged;
                report.acknowledgement_failures += outcome.acknowledgement_failures;
            }
            Err(error) => {
                report.commit_failures += 1;
                tracing::warn!(
                    receipt_id = %record.receipt_ref.receipt_id,
                    %error,
                    "durable workload receipt restart commit failed; preserving outbox entry"
                );
            }
        }
    }
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_agent::{
        DurableWorkloadReceiptRecord, DurableWorkloadReceiptRef, WorkloadResourceSnapshot,
        WorkloadResourceStatus,
    };
    use ab_store::{SqliteStore, StateStore};

    fn complete_record() -> DurableWorkloadReceiptRecord {
        let receipt_ref = DurableWorkloadReceiptRef {
            receipt_id: "a".repeat(32),
            sha256: format!("sha256:{}", "b".repeat(64)),
        };
        DurableWorkloadReceiptRecord {
            receipt_ref: receipt_ref.clone(),
            span_id: "agent-spawn-restart-bound".to_string(),
            runtime: "claude-code".to_string(),
            resources: WorkloadResourceSnapshot {
                status: WorkloadResourceStatus::Complete,
                source: Some("linux_cgroup_v2_systemd_delegated_scope".to_string()),
                scope: Some("delegated_session_workload_tree".to_string()),
                controllers: vec!["cpu".to_string(), "memory".to_string(), "pids".to_string()],
                cpu_usage_usec: Some(12),
                cpu_user_usec: Some(8),
                cpu_system_usec: Some(4),
                memory_peak_bytes: Some(4096),
                pids_peak: Some(2),
                oom_events: Some(0),
                oom_kill_events: Some(0),
                populated_zero_observed: true,
                start_before_exec: true,
                complete_for_cpu_memory_workload_tree: true,
                complete_for_pids_workload_tree: true,
                generation_count: 1,
                captured_generation_count: 1,
                incomplete_reasons: Vec::new(),
                durable_receipts: vec![receipt_ref],
            },
        }
    }

    fn contains_exact_key(value: &Value, needle: &str) -> bool {
        match value {
            Value::Object(object) => {
                object.contains_key(needle)
                    || object
                        .values()
                        .any(|child| contains_exact_key(child, needle))
            }
            Value::Array(array) => array.iter().any(|child| contains_exact_key(child, needle)),
            _ => false,
        }
    }

    #[test]
    fn recovered_receipt_proves_only_standalone_workload_accounting() {
        let record = complete_record();
        let (facts, event) = recovered_event(&record, 42).expect("build recovered event");

        assert_eq!(event.action, "workload_receipt_reconciled");
        assert_eq!(event.target.as_deref(), Some(record.span_id.as_str()));
        assert_eq!(event.verdict_status, "verified");
        assert_eq!(
            event.verdict_method,
            "restart_reconciled_durable_cgroup_receipt"
        );
        assert_eq!(facts["recovery_scope"], "standalone_workload_accounting");
        assert_eq!(facts["body_before_after_recovered"], false);
        assert_eq!(facts["task_span_closed_reconstructed"], false);
        for private_key in ["unit", "nonce", "pid", "pidfd", "path", "socket"] {
            assert!(!contains_exact_key(&facts, private_key));
        }
    }

    #[test]
    fn incomplete_recovered_receipt_remains_unknown() {
        let mut record = complete_record();
        record.resources.populated_zero_observed = false;
        record.resources.complete_for_cpu_memory_workload_tree = false;
        let (_, event) = recovered_event(&record, 43).expect("build incomplete event");
        assert_eq!(event.verdict_status, "unknown");
        assert_eq!(
            event.verdict_method,
            "restart_reconciled_incomplete_cgroup_receipt"
        );
    }

    #[test]
    fn active_peer_producer_does_not_consume_startup_seal_grace() {
        let active = ab_agent::DurableWorkloadReceiptScan {
            receipts: Vec::new(),
            unresolved: vec![ab_agent::DurableWorkloadReceiptIssue {
                receipt_id: Some("a".repeat(32)),
                state: "producer_active".to_string(),
                reason: "producer lease is held".to_string(),
            }],
            issues: Vec::new(),
        };
        assert!(!startup_scan_needs_seal_grace(&active));

        let ownerless = ab_agent::DurableWorkloadReceiptScan {
            receipts: Vec::new(),
            unresolved: vec![ab_agent::DurableWorkloadReceiptIssue {
                receipt_id: Some("b".repeat(32)),
                state: "receipt_commit_unknown".to_string(),
                reason: "terminal receipt is not yet durable".to_string(),
            }],
            issues: Vec::new(),
        };
        assert!(startup_scan_needs_seal_grace(&ownerless));
    }

    #[tokio::test]
    async fn recovered_projection_passes_store_privacy_and_atomic_commit_gate() {
        let directory = tempfile::tempdir().expect("temporary receipt store");
        let database = directory.path().join("state.db");
        let store: Arc<dyn StateStore> = Arc::new(
            SqliteStore::open(&database)
                .await
                .expect("open receipt store"),
        );
        let record = complete_record();
        let (facts, event) = recovered_event(&record, 44).expect("build recovered event");
        let records = commit_records(
            std::slice::from_ref(&record.receipt_ref),
            &record.span_id,
            44,
            WorkloadReceiptCommitKind::StartupReconciliation,
            &facts,
        )
        .expect("bind commit record");

        assert_eq!(
            store
                .commit_workload_receipt_event(records, event)
                .await
                .expect("commit privacy-minimal projection"),
            WorkloadReceiptCommitStatus::Inserted
        );
        assert!(store
            .load_workload_receipt_commit(&record.receipt_ref.receipt_id)
            .await
            .expect("load receipt commit")
            .is_some());
    }

    #[tokio::test]
    async fn store_failure_never_reaches_filesystem_ack() {
        let directory = tempfile::tempdir().expect("temporary failed receipt store");
        let database = directory.path().join("state.db");
        let store: Arc<dyn StateStore> = Arc::new(
            SqliteStore::open(&database)
                .await
                .expect("open failed receipt store"),
        );
        let raw = tokio_rusqlite::Connection::open(&database)
            .await
            .expect("open raw failure connection");
        raw.call(|connection| {
            connection.execute("DROP TABLE workload_receipt_commits", [])?;
            Ok::<_, tokio_rusqlite::rusqlite::Error>(())
        })
        .await
        .expect("remove temporary ledger table");

        let record = complete_record();
        let recorded_at = ab_store::now_secs();
        let (facts, event) = recovered_event(&record, recorded_at).expect("build failed event");
        let mut ack_calls = 0usize;
        let result = commit_workload_receipt_event_with_ack(
            &store,
            std::slice::from_ref(&record.receipt_ref),
            &record.span_id,
            recorded_at,
            WorkloadReceiptCommitKind::StartupReconciliation,
            &facts,
            event,
            |_| {
                ack_calls += 1;
                Ok(true)
            },
        )
        .await;

        assert!(result.is_err());
        assert_eq!(ack_calls, 0);
    }

    #[tokio::test]
    async fn live_commit_without_handed_off_owner_lease_writes_nothing() {
        let directory = tempfile::tempdir().expect("temporary lease-gated receipt store");
        let database = directory.path().join("state.db");
        let store: Arc<dyn StateStore> = Arc::new(
            SqliteStore::open(&database)
                .await
                .expect("open lease-gated receipt store"),
        );
        let record = complete_record();
        let recorded_at = ab_store::now_secs();
        let (facts, event) =
            recovered_event(&record, recorded_at).expect("build lease-gated event");

        let error = commit_live_workload_receipt_event_and_ack(
            &store,
            std::slice::from_ref(&record.receipt_ref),
            &ab_agent::DurableWorkloadReceiptLeaseGuard::default(),
            &record.span_id,
            recorded_at,
            &facts,
            event,
        )
        .await
        .expect_err("live commit without its producer lease must fail closed");

        assert!(error.to_string().contains("owned producer lease"));
        assert!(store
            .load_workload_receipt_commit(&record.receipt_ref.receipt_id)
            .await
            .expect("load absent lease-gated receipt")
            .is_none());
        assert!(store
            .recent_semantic_events(3_600, 10)
            .await
            .expect("read absent lease-gated event")
            .is_empty());
    }

    #[tokio::test]
    async fn commit_before_ack_failure_replays_without_second_event() {
        let directory = tempfile::tempdir().expect("temporary replay receipt store");
        let database = directory.path().join("state.db");
        let store: Arc<dyn StateStore> = Arc::new(
            SqliteStore::open(&database)
                .await
                .expect("open replay receipt store"),
        );
        let record = complete_record();
        let recorded_at = ab_store::now_secs();
        let (facts, event) = recovered_event(&record, recorded_at).expect("build replay event");

        let inserted = commit_workload_receipt_event_with_ack(
            &store,
            std::slice::from_ref(&record.receipt_ref),
            &record.span_id,
            recorded_at,
            WorkloadReceiptCommitKind::StartupReconciliation,
            &facts,
            event.clone(),
            |_| Err(Error::Backend("simulated crash-before-ACK".into())),
        )
        .await
        .expect("database commit survives ACK failure");
        assert_eq!(inserted.status, WorkloadReceiptCommitStatus::Inserted);
        assert!(inserted.event_projection_present);
        assert_eq!(inserted.acknowledgement_failures, 1);

        let replayed = commit_workload_receipt_event_with_ack(
            &store,
            std::slice::from_ref(&record.receipt_ref),
            &record.span_id,
            recorded_at + 1,
            WorkloadReceiptCommitKind::StartupReconciliation,
            &facts,
            event,
            |_| Ok(true),
        )
        .await
        .expect("replay committed receipt");
        assert_eq!(replayed.status, WorkloadReceiptCommitStatus::Duplicate);
        assert!(replayed.event_projection_present);
        assert_eq!(replayed.acknowledged, 1);
        assert_eq!(
            store
                .recent_workload_receipt_commits(3_600, 10)
                .await
                .expect("read replay ledger")
                .len(),
            1
        );
        assert_eq!(
            store
                .recent_semantic_events(3_600, 10)
                .await
                .expect("read replay event ring")
                .len(),
            1
        );
    }

    #[tokio::test]
    async fn duplicate_identity_does_not_claim_a_different_projection() {
        let directory = tempfile::tempdir().expect("temporary projection receipt store");
        let database = directory.path().join("state.db");
        let store: Arc<dyn StateStore> = Arc::new(
            SqliteStore::open(&database)
                .await
                .expect("open projection receipt store"),
        );
        let record = complete_record();
        let recorded_at = ab_store::now_secs();
        let (recovered_facts, recovered_event) =
            recovered_event(&record, recorded_at).expect("build recovered projection");
        let inserted = commit_workload_receipt_event_with_ack(
            &store,
            std::slice::from_ref(&record.receipt_ref),
            &record.span_id,
            recorded_at,
            WorkloadReceiptCommitKind::StartupReconciliation,
            &recovered_facts,
            recovered_event.clone(),
            |_| Ok(false),
        )
        .await
        .expect("commit recovered projection");
        assert_eq!(inserted.status, WorkloadReceiptCommitStatus::Inserted);

        let mut live_facts = recovered_facts;
        live_facts["recovery_scope"] = json!("live_body_span");
        let mut live_event = recovered_event;
        live_event.action = "task_span_closed".to_string();
        live_event.facts = live_facts.to_string();
        let duplicate = commit_workload_receipt_event_with_ack(
            &store,
            std::slice::from_ref(&record.receipt_ref),
            &record.span_id,
            recorded_at + 1,
            WorkloadReceiptCommitKind::LiveBodySpan,
            &live_facts,
            live_event,
            |_| Ok(true),
        )
        .await
        .expect("classify different projection replay");

        assert_eq!(duplicate.status, WorkloadReceiptCommitStatus::Duplicate);
        assert!(!duplicate.event_projection_present);
        assert_eq!(duplicate.acknowledged, 1);
        assert_eq!(
            store
                .recent_semantic_events(3_600, 10)
                .await
                .expect("read projection event ring")
                .len(),
            1
        );
    }
}
