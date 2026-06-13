use crate::lswr_snapshot_consumer::{
    ConsumerFeedback, ConsumerRollback, ConsumerVerification, ReadOnlyBridgeConsumerSummary,
};

pub const LSWR_READONLY_BRIDGE_REPORT_SCHEMA: &str = "agent_bridge.lswr.readonly_bridge_report.v0";

pub fn render_readonly_bridge_report(summary: &ReadOnlyBridgeConsumerSummary) -> String {
    let mut lines = Vec::new();

    lines.push("# LSWR Read-Only Bridge Report".to_string());
    lines.push(String::new());
    push_kv(
        &mut lines,
        "report_schema",
        LSWR_READONLY_BRIDGE_REPORT_SCHEMA,
    );
    push_kv(&mut lines, "summary_schema", &summary.schema);
    push_kv(&mut lines, "projection_schema", &summary.projection_schema);
    push_kv(&mut lines, "snapshot_sha256", &summary.snapshot_sha256);
    push_kv(&mut lines, "readback_mode", &summary.readback_mode);
    push_kv(
        &mut lines,
        "read_only_confirmed",
        bool_text(summary.read_only_confirmed),
    );

    lines.push(String::new());
    lines.push("## Safety".to_string());
    push_bullet_kv(&mut lines, "read_only", bool_text(summary.safety.read_only));
    push_bullet_kv(
        &mut lines,
        "mutation_surface",
        &summary.safety.mutation_surface,
    );
    push_bullet_kv(
        &mut lines,
        "mcp_tool_registration",
        bool_text(summary.safety.mcp_tool_registration),
    );
    push_bullet_kv(
        &mut lines,
        "affordances",
        format!(
            "snapshot={}, query={}, patch={}, action={}, invoke={}",
            bool_text(summary.safety.snapshot),
            bool_text(summary.safety.query),
            bool_text(summary.safety.patch),
            bool_text(summary.safety.action),
            bool_text(summary.safety.invoke)
        ),
    );

    lines.push(String::new());
    lines.push("## Counts".to_string());
    push_bullet_kv(&mut lines, "actions", summary.counts.actions.to_string());
    push_bullet_kv(&mut lines, "events", summary.counts.events.to_string());
    push_bullet_kv(
        &mut lines,
        "verifications",
        summary.counts.verifications.to_string(),
    );
    push_bullet_kv(&mut lines, "feedback", summary.counts.feedback.to_string());
    push_bullet_kv(
        &mut lines,
        "rollback_records",
        summary.counts.rollback_records.to_string(),
    );

    lines.push(String::new());
    lines.push("## Query Surfaces".to_string());
    push_string_list(&mut lines, &summary.query_surfaces);

    lines.push(String::new());
    lines.push("## Verification Outcomes".to_string());
    push_bullet_kv(
        &mut lines,
        "verified",
        optional_count(summary.outcome_counts.verified),
    );
    push_bullet_kv(
        &mut lines,
        "not_verified",
        optional_count(summary.outcome_counts.not_verified),
    );
    push_bullet_kv(
        &mut lines,
        "blocked",
        optional_count(summary.outcome_counts.blocked),
    );
    push_bullet_kv(
        &mut lines,
        "feedback_changes_world_verdict",
        optional_count(summary.outcome_counts.feedback_changes_world_verdict),
    );

    lines.push(String::new());
    lines.push("## Verified".to_string());
    push_verification_list(&mut lines, &summary.verified);

    lines.push(String::new());
    lines.push("## Not Verified".to_string());
    push_verification_list(&mut lines, &summary.not_verified);

    lines.push(String::new());
    lines.push("## Blocked".to_string());
    push_verification_list(&mut lines, &summary.blocked);

    lines.push(String::new());
    lines.push("## Feedback".to_string());
    push_feedback_list(&mut lines, &summary.feedback);

    lines.push(String::new());
    lines.push("## Rollbacks".to_string());
    push_rollback_list(&mut lines, &summary.rollbacks);

    lines.push(String::new());
    lines.push("## Guidance".to_string());
    push_string_list(&mut lines, &summary.guidance);

    format!("{}\n", lines.join("\n"))
}

fn push_kv(lines: &mut Vec<String>, key: &str, value: impl AsRef<str>) {
    lines.push(format!("{key}: {}", one_line(value.as_ref())));
}

fn push_bullet_kv(lines: &mut Vec<String>, key: &str, value: impl AsRef<str>) {
    lines.push(format!("- {key}: {}", one_line(value.as_ref())));
}

fn push_string_list(lines: &mut Vec<String>, values: &[String]) {
    if values.is_empty() {
        lines.push("- none".to_string());
        return;
    }

    for value in values {
        lines.push(format!("- {}", one_line(value)));
    }
}

fn push_verification_list(lines: &mut Vec<String>, verifications: &[ConsumerVerification]) {
    if verifications.is_empty() {
        lines.push("- none".to_string());
        return;
    }

    for verification in verifications {
        let action_id = optional_text(verification.action_id.as_deref());
        let target = target_text(
            verification.target_kind.as_deref(),
            verification.target_id.as_deref(),
        );
        lines.push(format!(
            "- action: {}; verdict: {}; method: {}; target: {}; raw_available: {}",
            one_line(&action_id),
            one_line(&verification.verdict),
            one_line(&verification.method),
            one_line(&target),
            bool_text(verification.raw_available)
        ));
        push_bullet_kv(
            lines,
            "evidence",
            format!(
                "{}/{} - {}",
                verification.evidence_adapter,
                verification.evidence_method,
                verification.evidence_summary
            ),
        );
        if let Some(reason) = verification.reason.as_deref() {
            push_bullet_kv(lines, "reason", reason);
        }
    }
}

fn push_feedback_list(lines: &mut Vec<String>, feedback: &[ConsumerFeedback]) {
    if feedback.is_empty() {
        lines.push("- none".to_string());
        return;
    }

    for entry in feedback {
        lines.push(format!(
            "- feedback: {}; source_event: {}; decision: {}; changes_world_verdict: {}",
            one_line(&entry.feedback_id),
            one_line(&entry.source_event_id),
            one_line(&optional_text(entry.decision.as_deref())),
            bool_text(entry.changes_world_verdict)
        ));
        push_bullet_kv(
            lines,
            "targets",
            format!(
                "entities={}, actions={}, events={}, rollback_groups={}",
                join_or_none(&entry.target_entities),
                join_or_none(&entry.target_actions),
                join_or_none(&entry.target_events),
                join_or_none(&entry.target_rollback_groups)
            ),
        );
    }
}

fn push_rollback_list(lines: &mut Vec<String>, rollbacks: &[ConsumerRollback]) {
    if rollbacks.is_empty() {
        lines.push("- none".to_string());
        return;
    }

    for rollback in rollbacks {
        lines.push(format!(
            "- rollback_group: {}; actions: {}; verification_event_id: {}",
            one_line(&rollback.rollback_group),
            join_or_none(&rollback.actions),
            one_line(&optional_text(rollback.verification_event_id.as_deref()))
        ));
    }
}

fn optional_count(count: Option<usize>) -> String {
    count
        .map(|count| count.to_string())
        .unwrap_or_else(|| "unknown".to_string())
}

fn optional_text(value: Option<&str>) -> String {
    value
        .map(one_line)
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| "none".to_string())
}

fn target_text(kind: Option<&str>, id: Option<&str>) -> String {
    match (kind, id) {
        (Some(kind), Some(id)) => format!("{}={}", one_line(kind), one_line(id)),
        _ => "none".to_string(),
    }
}

fn join_or_none(values: &[String]) -> String {
    if values.is_empty() {
        "none".to_string()
    } else {
        values
            .iter()
            .map(|value| one_line(value))
            .collect::<Vec<_>>()
            .join(",")
    }
}

fn bool_text(value: bool) -> &'static str {
    if value {
        "true"
    } else {
        "false"
    }
}

fn one_line(value: &str) -> String {
    value
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .trim()
        .to_string()
}
