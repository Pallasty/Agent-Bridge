//! Read-only lineage / provenance audit over the semantic-event spine (T7/P5).
//!
//! Loads the `semantic_events` ledger **read-only** (`SQLITE_OPEN_READ_ONLY`),
//! projects each row into an [`AuditEvent`], runs the deterministic
//! severity-burst / cascade-depth / conservation-leak predicates, and prints the
//! report as JSON. **Nothing is written** — this is a continuity *report*, not a
//! gate (mirrors the read-only discipline of `quant_drift_eval` /
//! `connectivity_repair_eval`).
//!
//! Projection (documented so a sparse run is never mistaken for a clean one):
//!
//! - `group` = `actor` (burst grouping = the producing session).
//! - `severity` = `verdict_status` (not_verified→Adverse, unknown→Watch,
//!   verified→Benign).
//! - `provenance` = Unprovenanced when a `verified` verdict carries no
//!   `evidence` (an effect claimed without traceable proof); Admitted otherwise
//!   (an honest `not_verified` is *not* a leak).
//! - `parents` = lineage ids parsed from `facts` JSON keys `parent_event_id` /
//!   `cause_id` (int) and `parent_ids` / `lineage_ids` (int array); empty when
//!   absent.
//!
//! Usage:
//!   cargo run -p ab-store --no-default-features --example lineage_audit_eval [DB_PATH]
//! (DB_PATH defaults to `ab_store::default_db_path()`.)

use ab_store::default_db_path;
use ab_store::lineage_audit::{audit, AuditConfig, AuditEvent, Provenance, Severity};
use tokio_rusqlite::{rusqlite, Connection};

/// One raw `semantic_events` row (read-only projection input).
struct Row {
    id: i64,
    ts: i64,
    actor: String,
    source: String,
    action: String,
    verdict_status: String,
    evidence: Option<String>,
    facts: Option<String>,
}

fn severity_of(verdict: &str) -> Severity {
    match verdict {
        "not_verified" => Severity::Adverse,
        "unknown" => Severity::Watch,
        _ => Severity::Benign, // "verified" and any legacy value
    }
}

/// True when `evidence` carries real proof — parsed as JSON, present only if a
/// non-empty object/array or a non-empty scalar. Catches vacuous blobs (`{}`,
/// `[]`, `{ }`, `null`, `""`, whitespace) that a string compare would miss.
fn evidence_present(ev: &Option<String>) -> bool {
    let Some(s) = ev else { return false };
    let t = s.trim();
    if t.is_empty() {
        return false;
    }
    match serde_json::from_str::<serde_json::Value>(t) {
        Ok(serde_json::Value::Null) => false,
        Ok(serde_json::Value::Object(m)) => !m.is_empty(),
        Ok(serde_json::Value::Array(a)) => !a.is_empty(),
        Ok(serde_json::Value::String(inner)) => !inner.trim().is_empty(),
        Ok(_) => true,  // non-null number/bool = present
        Err(_) => true, // non-JSON but non-empty text = present
    }
}

/// Pull lineage parent ids out of an adapter-specific `facts` JSON blob.
fn parents_from_facts(facts: &Option<String>) -> Vec<i64> {
    let Some(raw) = facts else { return Vec::new() };
    let Ok(v) = serde_json::from_str::<serde_json::Value>(raw) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for k in ["parent_event_id", "cause_id"] {
        if let Some(n) = v.get(k).and_then(|x| x.as_i64()) {
            out.push(n);
        }
    }
    for k in ["parent_ids", "lineage_ids"] {
        if let Some(arr) = v.get(k).and_then(|x| x.as_array()) {
            out.extend(arr.iter().filter_map(|x| x.as_i64()));
        }
    }
    out.sort_unstable();
    out.dedup();
    out
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let db = args
        .next()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(default_db_path);
    eprintln!("[lineage-audit] read-only open: {}", db.display());

    let conn = Connection::open_with_flags(&db, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY).await?;

    let rows: Vec<Row> = conn
        .call(|c| -> rusqlite::Result<Vec<Row>> {
            let mut stmt = c.prepare(
                "SELECT id, ts, actor, source, action, verdict_status, evidence, facts \
                 FROM semantic_events ORDER BY id",
            )?;
            let rows = stmt
                .query_map([], |row| {
                    Ok(Row {
                        id: row.get(0)?,
                        ts: row.get(1)?,
                        actor: row.get(2)?,
                        source: row.get(3)?,
                        action: row.get(4)?,
                        verdict_status: row.get(5)?,
                        evidence: row.get(6)?,
                        facts: row.get(7)?,
                    })
                })?
                .collect::<rusqlite::Result<Vec<_>>>()?;
            Ok(rows)
        })
        .await?;

    let with_parents = rows
        .iter()
        .filter(|r| !parents_from_facts(&r.facts).is_empty())
        .count();

    let events: Vec<AuditEvent> = rows
        .into_iter()
        .map(|r| {
            let severity = severity_of(&r.verdict_status);
            let provenance = if r.verdict_status == "verified" && !evidence_present(&r.evidence) {
                Provenance::Unprovenanced
            } else {
                Provenance::Admitted
            };
            AuditEvent {
                id: r.id,
                ts: r.ts,
                group: r.actor,
                severity,
                provenance,
                parents: parents_from_facts(&r.facts),
                label: format!("{}/{}", r.source, r.action),
            }
        })
        .collect();

    // Honest substrate note — keep a sparse run visibly sparse.
    eprintln!(
        "[lineage-audit] scanned {} semantic_events; {} carry a lineage link in facts",
        events.len(),
        with_parents
    );
    if events.is_empty() {
        eprintln!("[lineage-audit] ledger empty — analyzer ready, no events to audit yet");
    }

    let report = audit(&events, &AuditConfig::default());
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}
