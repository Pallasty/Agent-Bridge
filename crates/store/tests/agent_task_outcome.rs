use ab_store::{AgentTaskOutcomeRecord, AgentTaskOutcomeWriteStatus, SqliteStore, StateStore};
use sha2::{Digest, Sha256};
use std::time::{SystemTime, UNIX_EPOCH};

fn bind_record_digest(record: &mut AgentTaskOutcomeRecord) {
    let mut value = serde_json::json!({
        "schema_version": record.schema_version,
        "outcome_id": record.outcome_id,
        "contract_id": record.contract_id,
        "revision": record.contract_revision,
        "status": record.status,
        "verification": record.verification_status,
        "verification_method": record.verification_method,
        "user_acceptance": record.user_acceptance,
        "acceptance_provenance": record.acceptance_provenance,
        "rollback_status": record.rollback_status,
        "provenance": record.provenance,
        "evidence_sha256": record.evidence_sha256,
        "counts": {},
    });
    for (field, identifier) in [
        ("agent_id", record.agent_id.as_ref()),
        ("body_id", record.body_id.as_ref()),
        ("environment_id", record.environment_id.as_ref()),
    ] {
        if let Some(identifier) = identifier {
            value[field] = serde_json::json!(identifier);
        }
    }
    for (field, count) in [
        ("manual_interventions", record.manual_interventions),
        ("owner_restatements", record.owner_restatements),
        (
            "repeated_authorization_prompts",
            record.repeated_authorization_prompts,
        ),
    ] {
        if let Some(count) = count {
            value["counts"][field] = serde_json::json!(count);
        }
    }
    let canonical = serde_json_canonicalizer::to_vec(&value).expect("canonical outcome fixture");
    record.record_sha256 = format!("sha256:{:x}", Sha256::digest(canonical));
}

fn outcome(outcome_id: &str, recorded_at: i64) -> AgentTaskOutcomeRecord {
    let mut record = AgentTaskOutcomeRecord {
        schema_version: "agent_bridge.agent_task_outcome.v1".to_string(),
        outcome_id: outcome_id.to_string(),
        recorded_at,
        contract_id: "contract-test".to_string(),
        contract_revision: 3,
        status: "achieved".to_string(),
        verification_status: "verified".to_string(),
        verification_method: "mixed".to_string(),
        evidence_sha256: vec![format!("sha256:{}", "a".repeat(64))],
        user_acceptance: "accepted".to_string(),
        acceptance_provenance: "owner_explicit".to_string(),
        manual_interventions: Some(1),
        owner_restatements: Some(2),
        repeated_authorization_prompts: Some(3),
        rollback_status: "available".to_string(),
        provenance: "harness_verified".to_string(),
        agent_id: Some("agent-test".to_string()),
        body_id: Some("body-test".to_string()),
        environment_id: Some("environment-test".to_string()),
        record_sha256: String::new(),
    };
    bind_record_digest(&mut record);
    record
}

#[tokio::test]
async fn task_outcomes_are_idempotent_conflict_safe_ordered_and_durable() {
    let temp_dir = tempfile::tempdir().expect("temporary outcome ledger fixture");
    let db_path = temp_dir.path().join("state.db");
    let store = SqliteStore::open(&db_path)
        .await
        .expect("open sqlite store");
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock after Unix epoch")
        .as_secs() as i64;

    let first = outcome("outcome-first", now - 2);
    assert_eq!(
        store
            .check_agent_task_outcome(first.clone())
            .await
            .expect("preview unused outcome id"),
        AgentTaskOutcomeWriteStatus::Inserted
    );
    assert!(store
        .recent_agent_task_outcomes(3_600, 10)
        .await
        .expect("preview is read-only")
        .is_empty());
    assert_eq!(
        store
            .record_agent_task_outcome(first.clone())
            .await
            .expect("insert first outcome"),
        AgentTaskOutcomeWriteStatus::Inserted
    );
    assert_eq!(
        store
            .record_agent_task_outcome(first.clone())
            .await
            .expect("retry first outcome"),
        AgentTaskOutcomeWriteStatus::Duplicate
    );
    assert_eq!(
        store
            .check_agent_task_outcome(first.clone())
            .await
            .expect("preview duplicate"),
        AgentTaskOutcomeWriteStatus::Duplicate
    );

    let mut forged_same_digest = first.clone();
    forged_same_digest.status = "blocked".to_string();
    assert!(store
        .check_agent_task_outcome(forged_same_digest.clone())
        .await
        .is_err());
    assert!(store
        .record_agent_task_outcome(forged_same_digest)
        .await
        .is_err());

    let mut conflicting = first.clone();
    conflicting.status = "blocked".to_string();
    bind_record_digest(&mut conflicting);
    assert_eq!(
        store
            .record_agent_task_outcome(conflicting)
            .await
            .expect("detect conflicting retry"),
        AgentTaskOutcomeWriteStatus::Conflict
    );

    let after_conflict = store
        .recent_agent_task_outcomes(3_600, 10)
        .await
        .expect("read outcome after conflict");
    assert_eq!(after_conflict, vec![first.clone()]);

    let mut second = outcome("outcome-second", now - 1);
    second.manual_interventions = None;
    second.owner_restatements = None;
    second.repeated_authorization_prompts = None;
    bind_record_digest(&mut second);
    assert_eq!(
        store
            .record_agent_task_outcome(second.clone())
            .await
            .expect("insert second outcome"),
        AgentTaskOutcomeWriteStatus::Inserted
    );

    let recent = store
        .recent_agent_task_outcomes(3_600, 10)
        .await
        .expect("read recent outcomes");
    assert_eq!(recent, vec![second.clone(), first.clone()]);
    assert_eq!(recent[0].evidence_sha256, second.evidence_sha256);
    assert_eq!(recent[0].manual_interventions, None);
    assert_eq!(recent[0].owner_restatements, None);
    assert_eq!(recent[0].repeated_authorization_prompts, None);
    assert_eq!(recent[1].manual_interventions, Some(1));
    assert_eq!(recent[0].user_acceptance, "accepted");
    assert_eq!(recent[0].provenance, "harness_verified");

    drop(store);
    let reopened = SqliteStore::open(&db_path)
        .await
        .expect("reopen sqlite store");
    let persisted = reopened
        .recent_agent_task_outcomes(3_600, 10)
        .await
        .expect("read persisted outcomes");
    assert_eq!(persisted, vec![second, first]);
}

#[tokio::test]
async fn incompatible_preexisting_outcome_table_fails_open_closed() {
    let temp_dir = tempfile::tempdir().expect("temporary incompatible ledger fixture");
    let db_path = temp_dir.path().join("state.db");
    let connection = tokio_rusqlite::Connection::open(&db_path)
        .await
        .expect("open raw sqlite connection");
    connection
        .call(
            |connection| -> Result<(), tokio_rusqlite::rusqlite::Error> {
                connection.execute(
                    "CREATE TABLE agent_task_outcomes (outcome_id TEXT PRIMARY KEY)",
                    [],
                )?;
                Ok(())
            },
        )
        .await
        .expect("create incompatible collision table");
    drop(connection);

    assert!(SqliteStore::open(&db_path).await.is_err());
}

#[tokio::test]
async fn exact_columns_without_outcome_primary_key_fail_open_closed() {
    let temp_dir = tempfile::tempdir().expect("temporary wrong-primary-key fixture");
    let db_path = temp_dir.path().join("state.db");
    let connection = tokio_rusqlite::Connection::open(&db_path)
        .await
        .expect("open raw sqlite connection");
    connection
        .call(
            |connection| -> Result<(), tokio_rusqlite::rusqlite::Error> {
                connection.execute_batch(
                    "CREATE TABLE agent_task_outcomes (
                        schema_version TEXT NOT NULL,
                        outcome_id TEXT,
                        recorded_at INTEGER NOT NULL,
                        contract_id TEXT NOT NULL,
                        contract_revision INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        verification_status TEXT NOT NULL,
                        verification_method TEXT NOT NULL,
                        evidence_sha256 TEXT NOT NULL,
                        user_acceptance TEXT NOT NULL,
                        acceptance_provenance TEXT NOT NULL,
                        manual_interventions INTEGER,
                        owner_restatements INTEGER,
                        repeated_authorization_prompts INTEGER,
                        rollback_status TEXT NOT NULL,
                        provenance TEXT NOT NULL,
                        agent_id TEXT,
                        body_id TEXT,
                        environment_id TEXT,
                        record_sha256 TEXT NOT NULL
                    );",
                )?;
                Ok(())
            },
        )
        .await
        .expect("create exact-column collision table without primary key");
    drop(connection);

    assert!(SqliteStore::open(&db_path).await.is_err());
}

#[tokio::test]
async fn malformed_evidence_cell_does_not_abort_the_whole_ledger_read() {
    let temp_dir = tempfile::tempdir().expect("temporary corrupt row fixture");
    let db_path = temp_dir.path().join("state.db");
    let store = SqliteStore::open(&db_path).await.expect("open store");
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock after Unix epoch")
        .as_secs() as i64;
    store
        .record_agent_task_outcome(outcome("outcome-corrupt-cell", now))
        .await
        .expect("insert valid fixture");

    let connection = tokio_rusqlite::Connection::open(&db_path)
        .await
        .expect("open raw sqlite connection");
    connection
        .call(
            |connection| -> Result<(), tokio_rusqlite::rusqlite::Error> {
            connection.execute(
                "UPDATE agent_task_outcomes SET evidence_sha256='not-json' WHERE outcome_id='outcome-corrupt-cell'",
                [],
            )?;
            Ok(())
            },
        )
        .await
        .expect("inject corrupt evidence cell");

    let rows = store
        .recent_agent_task_outcomes(3_600, 10)
        .await
        .expect("corrupt row remains isolated");
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].evidence_sha256, vec!["invalid_persisted_evidence"]);
}
