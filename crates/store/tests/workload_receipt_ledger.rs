use ab_store::{
    workload_receipt_commit_record_sha256, SemanticEventRecord, SqliteStore, StateStore,
    WorkloadReceiptCommitKind, WorkloadReceiptCommitRecord, WorkloadReceiptCommitStatus,
    SEMANTIC_EVENT_RING_CAP, WORKLOAD_RECEIPT_COMMIT_SCHEMA_V1,
};
use serde_json::{json, Value};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio_rusqlite::{params, Connection};

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock after Unix epoch")
        .as_secs() as i64
}

fn digest(character: char) -> String {
    format!("sha256:{}", character.to_string().repeat(64))
}

fn canonical(value: &Value) -> String {
    String::from_utf8(
        serde_json_canonicalizer::to_vec(value).expect("canonical workload receipt fixture"),
    )
    .expect("canonical JSON is UTF-8")
}

fn receipt(
    receipt_id: &str,
    span_id: &str,
    receipt_digest_character: char,
    recorded_at: i64,
    commit_kind: WorkloadReceiptCommitKind,
    facts: Value,
) -> WorkloadReceiptCommitRecord {
    let mut record = WorkloadReceiptCommitRecord {
        schema_version: WORKLOAD_RECEIPT_COMMIT_SCHEMA_V1.to_string(),
        receipt_id: receipt_id.to_string(),
        span_id: span_id.to_string(),
        recorded_at,
        receipt_sha256: digest(receipt_digest_character),
        commit_kind,
        redacted_facts_json: canonical(&facts),
        record_sha256: String::new(),
    };
    record.record_sha256 =
        workload_receipt_commit_record_sha256(&record).expect("bind receipt fixture");
    record
}

fn event(
    action: &str,
    target: &str,
    ts: i64,
    projection: &WorkloadReceiptCommitRecord,
) -> SemanticEventRecord {
    SemanticEventRecord {
        ts,
        actor: "bridge-test".to_string(),
        source: "body_telemetry".to_string(),
        action: action.to_string(),
        target: Some(target.to_string()),
        verdict_status: "verified".to_string(),
        verdict_method: "delegated_cgroup_receipt_commit".to_string(),
        evidence: Some("{\"durable_commit\":true}".to_string()),
        facts: projection.redacted_facts_json.clone(),
        descriptor: Some(
            json!({
                "object": {
                    "object_type": "task_workload_receipt",
                    "source_adapter": "body_telemetry",
                    "label": "store-test",
                    "object_id": projection.receipt_id,
                },
                "affordance": {
                    "action_type": "observe",
                    "risk_level": "low",
                    "requires_gate": false,
                    "expected_effect": "commit a durable workload receipt projection",
                }
            })
            .to_string(),
        ),
    }
}

async fn table_counts(path: &Path) -> (i64, i64) {
    let connection = Connection::open(path)
        .await
        .expect("open raw count connection");
    connection
        .call(|connection| {
            Ok::<_, tokio_rusqlite::rusqlite::Error>((
                connection.query_row(
                    "SELECT COUNT(*) FROM workload_receipt_commits",
                    [],
                    |row| row.get(0),
                )?,
                connection
                    .query_row("SELECT COUNT(*) FROM semantic_events", [], |row| row.get(0))?,
            ))
        })
        .await
        .expect("count receipt ledger and semantic events")
}

#[tokio::test]
async fn concurrent_replay_commits_one_receipt_and_one_event_then_reopens() {
    let directory = tempfile::tempdir().expect("temporary workload receipt ledger");
    let database = directory.path().join("state.db");
    let first = SqliteStore::open(&database)
        .await
        .expect("open first store");
    let second = SqliteStore::open(&database)
        .await
        .expect("open second store");
    let now = now_secs();
    let row = receipt(
        "receipt-concurrent",
        "span-concurrent",
        'a',
        now,
        WorkloadReceiptCommitKind::LiveBodySpan,
        json!({
            "schema_version": "agent_bridge.task_workload_resources.v0",
            "source": "linux_cgroup_v2_systemd_delegated_scope",
            "final_populated_zero": true,
            "known_total_cpu_us": 1234,
        }),
    );

    let (left, right) = tokio::join!(
        first.commit_workload_receipt_event(
            vec![row.clone()],
            event("workload_receipt_committed", "span-concurrent", now, &row),
        ),
        second.commit_workload_receipt_event(
            vec![row.clone()],
            event("workload_receipt_committed", "span-concurrent", now, &row),
        ),
    );
    let statuses = [left.expect("first commit"), right.expect("second commit")];
    assert!(statuses.contains(&WorkloadReceiptCommitStatus::Inserted));
    assert!(statuses.contains(&WorkloadReceiptCommitStatus::Duplicate));
    assert_eq!(table_counts(&database).await, (1, 1));
    assert_eq!(
        first
            .load_workload_receipt_commit("receipt-concurrent")
            .await
            .expect("load committed receipt"),
        Some(row.clone())
    );
    assert_eq!(
        first
            .recent_workload_receipt_commits(3_600, 10)
            .await
            .expect("list committed receipts"),
        vec![row.clone()]
    );

    drop(first);
    drop(second);
    let reopened = SqliteStore::open(&database)
        .await
        .expect("reopen receipt ledger");
    assert_eq!(
        reopened
            .load_workload_receipt_commit("receipt-concurrent")
            .await
            .expect("load receipt after reopen"),
        Some(row)
    );
    assert_eq!(table_counts(&database).await, (1, 1));
}

#[tokio::test]
async fn multi_receipt_batches_deduplicate_once_and_conflicts_roll_back_everything() {
    let directory = tempfile::tempdir().expect("temporary batch receipt ledger");
    let database = directory.path().join("state.db");
    let store = SqliteStore::open(&database)
        .await
        .expect("open receipt store");
    let now = now_secs();
    let first = receipt(
        "receipt-first",
        "span-batch",
        'a',
        now,
        WorkloadReceiptCommitKind::LiveBodySpan,
        json!({"generation": 1, "complete": true}),
    );
    let sealed_projection = json!({"generations": [1, 2], "complete": true});
    let first_live_replay = receipt(
        "receipt-first",
        "span-batch",
        'a',
        now + 1,
        WorkloadReceiptCommitKind::LiveBodySpan,
        sealed_projection.clone(),
    );
    let second = receipt(
        "receipt-second",
        "span-batch",
        'b',
        now + 1,
        WorkloadReceiptCommitKind::LiveBodySpan,
        sealed_projection,
    );

    assert_eq!(
        store
            .commit_workload_receipt_event(
                vec![first.clone()],
                event("first_generation", "span-batch", now, &first),
            )
            .await
            .expect("commit first generation"),
        WorkloadReceiptCommitStatus::Inserted
    );
    assert_eq!(
        store
            .commit_workload_receipt_event(
                vec![first_live_replay.clone(), second.clone(), {
                    let mut replay = second.clone();
                    replay.recorded_at += 20;
                    replay.record_sha256 = workload_receipt_commit_record_sha256(&replay)
                        .expect("bind same-batch replay");
                    replay
                }],
                event("sealed_generations", "span-batch", now + 1, &second),
            )
            .await
            .expect("commit mixed duplicate and new generation"),
        WorkloadReceiptCommitStatus::Inserted
    );
    assert_eq!(table_counts(&database).await, (2, 2));

    let mut restart_replay = first_live_replay;
    restart_replay.commit_kind = WorkloadReceiptCommitKind::StartupReconciliation;
    restart_replay.recorded_at += 10;
    restart_replay.record_sha256 =
        workload_receipt_commit_record_sha256(&restart_replay).expect("bind restart replay");
    assert_eq!(
        store
            .commit_workload_receipt_event(
                vec![restart_replay, second.clone()],
                event("must_not_duplicate", "span-batch", now + 2, &second),
            )
            .await
            .expect("all duplicate receipt replay"),
        WorkloadReceiptCommitStatus::Duplicate
    );
    assert_eq!(table_counts(&database).await, (2, 2));

    let mut conflicting = first.clone();
    conflicting.span_id = "span-forged".to_string();
    conflicting.record_sha256 =
        workload_receipt_commit_record_sha256(&conflicting).expect("bind conflict fixture");
    let never_inserted = receipt(
        "receipt-never-inserted",
        "span-batch",
        'c',
        now + 2,
        WorkloadReceiptCommitKind::StartupReconciliation,
        json!({"generation": 3, "complete": true}),
    );
    assert_eq!(
        store
            .commit_workload_receipt_event(
                vec![conflicting, never_inserted.clone()],
                event("conflicting_batch", "span-batch", now + 2, &never_inserted),
            )
            .await
            .expect("classify conflicting batch"),
        WorkloadReceiptCommitStatus::Conflict
    );
    assert_eq!(table_counts(&database).await, (2, 2));
    assert!(store
        .load_workload_receipt_commit(&never_inserted.receipt_id)
        .await
        .expect("check rolled-back receipt")
        .is_none());

    let recovered_projection = json!({"generations": [3, 4], "complete": true});
    let third = receipt(
        "receipt-third",
        "span-batch",
        'd',
        now + 3,
        WorkloadReceiptCommitKind::StartupReconciliation,
        recovered_projection.clone(),
    );
    let fourth = receipt(
        "receipt-fourth",
        "span-batch",
        'e',
        now + 4,
        WorkloadReceiptCommitKind::StartupReconciliation,
        recovered_projection,
    );
    assert_eq!(
        store
            .commit_workload_receipt_event(
                vec![third.clone(), fourth],
                event("two_recovered_generations", "span-batch", now + 4, &third),
            )
            .await
            .expect("commit two receipts with one event"),
        WorkloadReceiptCommitStatus::Inserted
    );
    assert_eq!(table_counts(&database).await, (4, 3));
}

#[tokio::test]
async fn semantic_fifo_pruning_never_prunes_the_receipt_ledger() {
    let directory = tempfile::tempdir().expect("temporary ring receipt ledger");
    let database = directory.path().join("state.db");
    let store = SqliteStore::open(&database)
        .await
        .expect("open receipt store");

    let connection = Connection::open(&database)
        .await
        .expect("open raw semantic prefill connection");
    connection
        .call(|connection| {
            let transaction = connection.transaction()?;
            for index in 0..(SEMANTIC_EVENT_RING_CAP + 5) {
                transaction.execute(
                    "INSERT INTO semantic_events
                       (ts, actor, source, action, target, verdict_status,
                        verdict_method, evidence, facts, descriptor)
                     VALUES (?1, 'prefill', 'test', 'prefill', NULL, 'unknown',
                             'prefill', NULL, '{}', NULL)",
                    params![index],
                )?;
            }
            transaction.commit()
        })
        .await
        .expect("prefill semantic ring");
    drop(connection);

    let now = now_secs();
    let row = receipt(
        "receipt-ring-survivor",
        "span-ring",
        'f',
        now,
        WorkloadReceiptCommitKind::LiveBodySpan,
        json!({"complete": true}),
    );
    assert_eq!(
        store
            .commit_workload_receipt_event(
                vec![row.clone()],
                event("ring_survivor", "span-ring", now, &row),
            )
            .await
            .expect("commit receipt and prune semantic ring"),
        WorkloadReceiptCommitStatus::Inserted
    );
    assert_eq!(table_counts(&database).await, (1, SEMANTIC_EVENT_RING_CAP));
    drop(store);

    let reopened = SqliteStore::open(&database)
        .await
        .expect("reopen pruned receipt ledger");
    assert_eq!(
        reopened
            .load_workload_receipt_commit("receipt-ring-survivor")
            .await
            .expect("load receipt after ring prune"),
        Some(row)
    );
}

#[tokio::test]
async fn new_rows_require_one_span_one_projection_and_a_private_bound_event() {
    let directory = tempfile::tempdir().expect("temporary projection-bound receipt ledger");
    let database = directory.path().join("state.db");
    let store = SqliteStore::open(&database)
        .await
        .expect("open receipt store");
    let now = now_secs();
    let shared_projection = json!({
        "schema_version": "agent_bridge.task_workload_resources.v1",
        "complete": true,
        "known_total_cpu_us": 99,
    });
    let first = receipt(
        "receipt-bound-first",
        "span-bound",
        '1',
        now,
        WorkloadReceiptCommitKind::LiveBodySpan,
        shared_projection.clone(),
    );

    let other_span = receipt(
        "receipt-bound-other-span",
        "span-other",
        '2',
        now,
        WorkloadReceiptCommitKind::LiveBodySpan,
        shared_projection.clone(),
    );
    let error = store
        .commit_workload_receipt_event(
            vec![first.clone(), other_span],
            event("mixed_span", "span-bound", now, &first),
        )
        .await
        .expect_err("new rows from different spans must be rejected");
    assert!(error.to_string().contains("multiple span_id"));
    assert_eq!(table_counts(&database).await, (0, 0));

    let mut wrong_target = event("wrong_target", "span-forged", now, &first);
    wrong_target.target = Some("span-forged".to_string());
    let error = store
        .commit_workload_receipt_event(vec![first.clone()], wrong_target)
        .await
        .expect_err("event target must bind the receipt span");
    assert!(error.to_string().contains("target does not match"));
    assert_eq!(table_counts(&database).await, (0, 0));

    let mut wrong_facts = event("wrong_facts", "span-bound", now, &first);
    wrong_facts.facts = canonical(&json!({"complete": false}));
    let error = store
        .commit_workload_receipt_event(vec![first.clone()], wrong_facts)
        .await
        .expect_err("event facts must equal the canonical row projection");
    assert!(error.to_string().contains("facts do not match"));
    assert_eq!(table_counts(&database).await, (0, 0));

    let mut private_facts = event("private_facts", "span-bound", now, &first);
    private_facts.facts = canonical(&json!({"root_pid": 42}));
    let error = store
        .commit_workload_receipt_event(vec![first.clone()], private_facts)
        .await
        .expect_err("private event facts must be rejected before insertion");
    assert!(error
        .to_string()
        .contains("forbidden private key 'root_pid'"));
    assert_eq!(table_counts(&database).await, (0, 0));

    let different_projection = receipt(
        "receipt-bound-other-projection",
        "span-bound",
        '3',
        now,
        WorkloadReceiptCommitKind::LiveBodySpan,
        json!({"complete": true, "known_total_cpu_us": 100}),
    );
    let error = store
        .commit_workload_receipt_event(
            vec![first.clone(), different_projection],
            event("mixed_projection", "span-bound", now, &first),
        )
        .await
        .expect_err("one event cannot authorize mixed canonical projections");
    assert!(error.to_string().contains("multiple redacted projections"));
    assert_eq!(table_counts(&database).await, (0, 0));

    let other_kind = receipt(
        "receipt-bound-other-kind",
        "span-bound",
        '5',
        now,
        WorkloadReceiptCommitKind::StartupReconciliation,
        shared_projection,
    );
    let error = store
        .commit_workload_receipt_event(
            vec![first.clone(), other_kind],
            event("mixed_commit_kind", "span-bound", now, &first),
        )
        .await
        .expect_err("one event cannot authorize mixed commit kinds");
    assert!(error.to_string().contains("multiple commit kinds"));
    assert_eq!(table_counts(&database).await, (0, 0));

    let mut missing_descriptor = event("missing_descriptor", "span-bound", now, &first);
    missing_descriptor.descriptor = None;
    let error = store
        .commit_workload_receipt_event(vec![first.clone()], missing_descriptor)
        .await
        .expect_err("new receipt events require the minimum SSB descriptor");
    assert!(error.to_string().contains("missing its SSB descriptor"));
    assert_eq!(table_counts(&database).await, (0, 0));

    let mut private_descriptor = event("private_descriptor", "span-bound", now, &first);
    let mut descriptor: Value = serde_json::from_str(
        private_descriptor
            .descriptor
            .as_deref()
            .expect("fixture descriptor"),
    )
    .expect("parse fixture descriptor");
    descriptor["socket_path"] = Value::String("must-not-persist".to_string());
    private_descriptor.descriptor = Some(descriptor.to_string());
    let error = store
        .commit_workload_receipt_event(vec![first.clone()], private_descriptor)
        .await
        .expect_err("private SSB descriptor fields must be rejected");
    assert!(error
        .to_string()
        .contains("forbidden private key 'socket_path'"));
    assert_eq!(table_counts(&database).await, (0, 0));

    let mut private_evidence = event("private_evidence", "span-bound", now, &first);
    private_evidence.evidence = Some("{\"pidfd\":7}".to_string());
    let error = store
        .commit_workload_receipt_event(vec![first], private_evidence)
        .await
        .expect_err("private evidence fields must be rejected");
    assert!(error.to_string().contains("forbidden private key 'pidfd'"));
    assert_eq!(table_counts(&database).await, (0, 0));
}

#[tokio::test]
async fn all_duplicate_replay_does_not_revalidate_or_rewrite_projection() {
    let directory = tempfile::tempdir().expect("temporary duplicate receipt ledger");
    let database = directory.path().join("state.db");
    let store = SqliteStore::open(&database)
        .await
        .expect("open receipt store");
    let now = now_secs();
    let original = receipt(
        "receipt-duplicate-projection",
        "span-duplicate-projection",
        '4',
        now,
        WorkloadReceiptCommitKind::LiveBodySpan,
        json!({"projection": "original"}),
    );
    assert_eq!(
        store
            .commit_workload_receipt_event(
                vec![original.clone()],
                event(
                    "original_projection",
                    "span-duplicate-projection",
                    now,
                    &original,
                ),
            )
            .await
            .expect("commit original projection"),
        WorkloadReceiptCommitStatus::Inserted
    );

    let replay = receipt(
        "receipt-duplicate-projection",
        "span-duplicate-projection",
        '4',
        now + 1,
        WorkloadReceiptCommitKind::StartupReconciliation,
        json!({"projection": "later_restart_projection"}),
    );
    let mut ignored_event = event(
        "must_not_insert",
        "span-duplicate-projection",
        now + 1,
        &replay,
    );
    ignored_event.target = Some("span-unrelated".to_string());
    ignored_event.facts = "{\"root_pid\":99}".to_string();
    ignored_event.descriptor = None;
    ignored_event.evidence = Some("not-json".to_string());
    assert_eq!(
        store
            .commit_workload_receipt_event(vec![replay], ignored_event)
            .await
            .expect("all-duplicate replay skips a non-writing later projection"),
        WorkloadReceiptCommitStatus::Duplicate
    );
    assert_eq!(table_counts(&database).await, (1, 1));
    assert_eq!(
        store
            .load_workload_receipt_commit(&original.receipt_id)
            .await
            .expect("load immutable original projection"),
        Some(original)
    );
}

#[tokio::test]
async fn validation_rejects_private_keys_bad_identity_and_noncanonical_claims() {
    let directory = tempfile::tempdir().expect("temporary validation receipt ledger");
    let database = directory.path().join("state.db");
    let store = SqliteStore::open(&database)
        .await
        .expect("open receipt store");
    let now = now_secs();

    for (index, forbidden_key) in [
        "nonce",
        "systemd_unit",
        "root_pid",
        "pidfd",
        "cgroupPath",
        "socket_path",
        "private_runtime_dir",
    ]
    .into_iter()
    .enumerate()
    {
        let mut private_facts = serde_json::Map::new();
        private_facts.insert(
            forbidden_key.to_string(),
            Value::String("must-not-persist".to_string()),
        );
        let row = receipt(
            &format!("receipt-private-{index}"),
            "span-private",
            char::from(b'a' + index as u8),
            now,
            WorkloadReceiptCommitKind::StartupReconciliation,
            json!({"safe_outer": private_facts}),
        );
        assert!(store
            .commit_workload_receipt_event(
                vec![row.clone()],
                event("private_rejected", "span-private", now, &row),
            )
            .await
            .is_err());
    }

    let mut invalid_id = receipt(
        "receipt-valid-before-mutation",
        "span-valid",
        '8',
        now,
        WorkloadReceiptCommitKind::LiveBodySpan,
        json!({"complete": true}),
    );
    invalid_id.receipt_id = "/private/spool/receipt".to_string();
    invalid_id.record_sha256 =
        workload_receipt_commit_record_sha256(&invalid_id).expect("bind invalid id fixture");
    assert!(store
        .commit_workload_receipt_event(
            vec![invalid_id.clone()],
            event("invalid_id", "span-valid", now, &invalid_id),
        )
        .await
        .is_err());

    let noncanonical = WorkloadReceiptCommitRecord {
        schema_version: WORKLOAD_RECEIPT_COMMIT_SCHEMA_V1.to_string(),
        receipt_id: "receipt-noncanonical".to_string(),
        span_id: "span-noncanonical".to_string(),
        recorded_at: now,
        receipt_sha256: digest('9'),
        commit_kind: WorkloadReceiptCommitKind::LiveBodySpan,
        redacted_facts_json: "{\"z\":1,\"a\":2}".to_string(),
        record_sha256: digest('0'),
    };
    assert!(store
        .commit_workload_receipt_event(
            vec![noncanonical.clone()],
            event("noncanonical", "span-noncanonical", now, &noncanonical),
        )
        .await
        .is_err());

    let mut bad_record_digest = receipt(
        "receipt-bad-record-digest",
        "span-valid",
        '1',
        now,
        WorkloadReceiptCommitKind::LiveBodySpan,
        json!({"complete": true}),
    );
    bad_record_digest.record_sha256 = digest('2');
    assert!(store
        .commit_workload_receipt_event(
            vec![bad_record_digest.clone()],
            event("bad_digest", "span-valid", now, &bad_record_digest),
        )
        .await
        .is_err());

    assert_eq!(table_counts(&database).await, (0, 0));
}

#[tokio::test]
async fn incompatible_preexisting_receipt_table_fails_open_closed() {
    let directory = tempfile::tempdir().expect("temporary incompatible receipt ledger");
    let database = directory.path().join("state.db");
    let connection = Connection::open(&database)
        .await
        .expect("open raw collision database");
    connection
        .call(|connection| {
            connection.execute(
                "CREATE TABLE workload_receipt_commits (receipt_id TEXT PRIMARY KEY)",
                [],
            )?;
            Ok::<_, tokio_rusqlite::rusqlite::Error>(())
        })
        .await
        .expect("create incompatible receipt table");
    drop(connection);

    assert!(SqliteStore::open(&database).await.is_err());

    let directory = tempfile::tempdir().expect("temporary constraintless receipt ledger");
    let database = directory.path().join("state.db");
    let connection = Connection::open(&database)
        .await
        .expect("open raw constraintless database");
    connection
        .call(|connection| {
            connection.execute_batch(
                "CREATE TABLE workload_receipt_commits (
                    schema_version TEXT NOT NULL,
                    receipt_id TEXT PRIMARY KEY,
                    span_id TEXT NOT NULL,
                    recorded_at INTEGER NOT NULL,
                    receipt_sha256 TEXT NOT NULL,
                    commit_kind TEXT NOT NULL,
                    redacted_facts_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL
                 );
                 CREATE INDEX idx_workload_receipt_commits_recorded_at
                    ON workload_receipt_commits(recorded_at DESC, receipt_id);
                 CREATE INDEX idx_workload_receipt_commits_span
                    ON workload_receipt_commits(span_id, recorded_at DESC, receipt_id);",
            )?;
            Ok::<_, tokio_rusqlite::rusqlite::Error>(())
        })
        .await
        .expect("create constraintless receipt schema");
    drop(connection);

    assert!(SqliteStore::open(&database).await.is_err());
}

#[tokio::test]
async fn semantic_event_failure_rolls_back_new_receipt_rows() {
    let directory = tempfile::tempdir().expect("temporary atomic receipt ledger");
    let database = directory.path().join("state.db");
    let store = SqliteStore::open(&database)
        .await
        .expect("open receipt store");
    let connection = Connection::open(&database)
        .await
        .expect("open trigger connection");
    connection
        .call(|connection| {
            connection.execute_batch(
                "CREATE TRIGGER reject_receipt_projection
                 BEFORE INSERT ON semantic_events
                 WHEN NEW.action = 'reject_projection'
                 BEGIN
                   SELECT RAISE(ABORT, 'injected semantic projection failure');
                 END;",
            )?;
            Ok::<_, tokio_rusqlite::rusqlite::Error>(())
        })
        .await
        .expect("install semantic projection failpoint");
    drop(connection);

    let now = now_secs();
    let row = receipt(
        "receipt-atomic-rollback",
        "span-atomic-rollback",
        '7',
        now,
        WorkloadReceiptCommitKind::LiveBodySpan,
        json!({"complete": true}),
    );
    assert!(store
        .commit_workload_receipt_event(
            vec![row.clone()],
            event("reject_projection", "span-atomic-rollback", now, &row),
        )
        .await
        .is_err());
    assert_eq!(table_counts(&database).await, (0, 0));
}

#[test]
fn state_store_default_commit_cannot_silently_ack() {
    let source = include_str!("../src/lib.rs");
    let start = source
        .find("async fn commit_workload_receipt_event")
        .expect("StateStore exposes workload receipt commit");
    let implementation = &source[start..source.len().min(start + 1_200)];
    assert!(implementation.contains("Err(ab_core::Error::Backend"));
    assert!(implementation.contains("not supported by this store"));
}
