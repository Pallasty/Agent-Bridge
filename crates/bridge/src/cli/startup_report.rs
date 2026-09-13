//! Rendering of completed startup reconciliation evidence; no spool or store access.
pub(crate) fn log_workload_receipt_reconciliation_report(
    report: &ab_bridge::workload_receipt_reconciliation::WorkloadReceiptReconciliationReport,
) {
    if report.scanned_receipts > 0
        || report.unresolved > 0
        || report.invalid > 0
        || report.commit_failures > 0
    {
        tracing::info!(
            target: "agent_bridge",
            scanned = report.scanned_receipts,
            inserted = report.inserted_commits,
            duplicate = report.duplicate_commits,
            conflicts = report.conflicts,
            acknowledged = report.acknowledged,
            already_acknowledged = report.already_acknowledged,
            acknowledgement_failures = report.acknowledgement_failures,
            unresolved = report.unresolved,
            active_producers = report.active_producers,
            invalid = report.invalid,
            commit_failures = report.commit_failures,
            "durable workload receipt startup reconciliation completed"
        );
    }
}
