use ab_store::{
    BodyOperationReceiptRecord, BodyOperationReceiptWriteStatus, SqliteStore, StateStore,
};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::time::{SystemTime, UNIX_EPOCH};

fn bind_facts(record: &mut BodyOperationReceiptRecord, facts: &serde_json::Value) {
    let canonical = serde_json_canonicalizer::to_vec(facts).expect("canonical receipt fixture");
    record.redacted_facts_json = String::from_utf8(canonical.clone()).expect("canonical UTF-8");
    record.record_sha256 = format!("sha256:{:x}", Sha256::digest(canonical));
}

fn receipt(operation_id: &str, recorded_at: i64) -> BodyOperationReceiptRecord {
    let digest = |character: char| format!("sha256:{}", character.to_string().repeat(64));
    let observation = |revision: u64, source: &str, observed_at_unix_ms: u64| {
        json!({
            "schema": "agent_bridge.observation.v0",
            "body_id": "body-test",
            "source": source,
            "observed_at_unix_ms": observed_at_unix_ms,
            "freshness_ms": 0,
            "confidence": 1.0,
            "world_revision": revision,
            "payload_stored": false,
        })
    };
    let facts = json!({
        "schema_version": "agent_bridge.body_operation_envelope.v1",
        "agent_id": "agent-test",
        "body_id": "body-test",
        "environment_id": "environment-test",
        "operation_id": operation_id,
        "intent_id": "intent-test",
        "mutation": false,
        "lease_present": false,
        "action_kind": "inspect",
        "action_adapter_id": "read-adapter",
        "action_adapter_build_sha256": digest('1'),
        "action_request_sha256": digest('2'),
        "expected_postcondition_sha256": digest('3'),
        "action_started_at_unix_ms": 100,
        "action_completed_at_unix_ms": 110,
        "pre_observation": observation(1, "observer-before", 90),
        "pre_observation_max_age_ms": 60_000,
        "pre_observation_provenance": {
            "adapter_id": "observer-before",
            "adapter_build_sha256": digest('4'),
            "observation_sha256": digest('5'),
        },
        "status": "succeeded",
        "observed_after": observation(2, "observer-after", 109),
        "post_observation_provenance": {
            "adapter_id": "observer-after",
            "adapter_build_sha256": digest('6'),
            "observation_sha256": digest('7'),
        },
        "postcondition_verification_claim": {
            "status": "verified",
            "verifier_adapter_id": "observer-after",
            "verifier_build_sha256": digest('6'),
            "evidence_sha256": [digest('8')],
            "independent_from_action": true,
        },
        "recovery_decision": "none",
        "rollback_sha256": null,
        "memory_links_sha256": [],
        "raw_observation_payloads_stored": false,
        "executes_action": false,
        "grants_authority": false,
        "authenticates_adapter": false,
        "admission_provenance": "public_mcp_agent_reported",
        "trust_level": "advisory_only",
        "authority_authenticated": false,
        "adapter_attestation_authenticated": false,
    });
    let mut record = BodyOperationReceiptRecord {
        schema_version: "agent_bridge.body_operation_receipt.v1".to_string(),
        operation_id: operation_id.to_string(),
        recorded_at,
        body_id: "body-test".to_string(),
        terminal_status: "succeeded".to_string(),
        claimed_verification_status: "verified".to_string(),
        admission_provenance: "public_mcp_agent_reported".to_string(),
        redacted_facts_json: String::new(),
        record_sha256: String::new(),
    };
    bind_facts(&mut record, &facts);
    record
}

#[tokio::test]
async fn operation_receipts_are_atomic_idempotent_conflict_safe_and_durable() {
    let temp_dir = tempfile::tempdir().expect("temporary operation receipt ledger");
    let db_path = temp_dir.path().join("state.db");
    let first_store = SqliteStore::open(&db_path).await.expect("open first store");
    let second_store = SqliteStore::open(&db_path)
        .await
        .expect("open second store");
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock after Unix epoch")
        .as_secs() as i64;
    let row = receipt("operation-concurrent", now);

    let (first, second) = tokio::join!(
        first_store.record_body_operation_receipt(row.clone()),
        second_store.record_body_operation_receipt(row.clone()),
    );
    let statuses = [first.expect("first writer"), second.expect("second writer")];
    assert!(statuses.contains(&BodyOperationReceiptWriteStatus::Inserted));
    assert!(statuses.contains(&BodyOperationReceiptWriteStatus::Duplicate));

    let mut forged_same_digest = row.clone();
    forged_same_digest.terminal_status = "failed".to_string();
    assert!(first_store
        .record_body_operation_receipt(forged_same_digest)
        .await
        .is_err());

    let mut conflict = row.clone();
    conflict.recorded_at = now + 1;
    let mut conflict_facts: serde_json::Value =
        serde_json::from_str(&conflict.redacted_facts_json).expect("stored facts fixture");
    conflict_facts["action_kind"] = json!("inspect-again");
    bind_facts(&mut conflict, &conflict_facts);
    assert_eq!(
        first_store
            .record_body_operation_receipt(conflict)
            .await
            .expect("conflicting retry"),
        BodyOperationReceiptWriteStatus::Conflict
    );

    let persisted = first_store
        .recent_body_operation_receipts(3_600, 10)
        .await
        .expect("read operation receipts");
    assert_eq!(persisted, vec![row.clone()]);

    drop(first_store);
    drop(second_store);
    let reopened = SqliteStore::open(&db_path).await.expect("reopen store");
    assert_eq!(
        reopened
            .recent_body_operation_receipts(3_600, 10)
            .await
            .expect("read durable receipt"),
        vec![row]
    );
}
