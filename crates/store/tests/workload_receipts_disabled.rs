#![cfg(not(feature = "r9-workload-receipts"))]

use ab_store::{SemanticEventRecord, SqliteStore, StateStore};
use tokio_rusqlite::Connection;

#[tokio::test]
async fn maintenance_open_does_not_create_or_admit_a_workload_receipt_ledger() {
    let dir = tempfile::tempdir().unwrap();
    let database = dir.path().join("state.db");
    let store = SqliteStore::open(&database).await.unwrap();
    let event = SemanticEventRecord {
        ts: 1,
        actor: "test".into(),
        source: "body_telemetry".into(),
        action: "must_not_commit".into(),
        target: None,
        verdict_status: "unknown".into(),
        verdict_method: "test".into(),
        evidence: None,
        facts: "{}".into(),
        descriptor: None,
    };
    for result in [
        store
            .commit_workload_receipt_event(vec![], event)
            .await
            .map(|_| ()),
        store
            .load_workload_receipt_commit("historical")
            .await
            .map(|_| ()),
        store
            .recent_workload_receipt_commits(60, 10)
            .await
            .map(|_| ()),
    ] {
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("not supported by this store"));
    }
    assert!(store
        .recent_semantic_events(60, 10)
        .await
        .unwrap()
        .is_empty());
    let connection = Connection::open(&database).await.unwrap();
    connection
        .call(|connection| {
            let count: i64 = connection.query_row(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%workload_receipt%'",
                [],
                |row| row.get(0),
            )?;
            assert_eq!(count, 0);
            let events: i64 =
                connection
                    .query_row("SELECT COUNT(*) FROM semantic_events", [], |row| row.get(0))?;
            assert_eq!(events, 0);
            Ok::<_, tokio_rusqlite::rusqlite::Error>(())
        })
        .await
        .unwrap();
}

#[tokio::test]
async fn maintenance_reopen_preserves_existing_workload_state_without_adopting_it() {
    let dir = tempfile::tempdir().unwrap();
    let database = dir.path().join("state.db");
    drop(SqliteStore::open(&database).await.unwrap());
    let connection = Connection::open(&database).await.unwrap();
    // Opaque historical state deliberately has an incompatible shape. A build
    // that does not adopt R9 must neither repair it nor require its admission.
    connection
        .call(|connection| {
            connection.execute_batch(
                "CREATE TABLE workload_receipt_commits (receipt_id TEXT PRIMARY KEY, payload BLOB);
             INSERT INTO workload_receipt_commits VALUES ('historical', X'0001FF');
             CREATE INDEX historical_receipt_index ON workload_receipt_commits(payload);",
            )?;
            Ok::<_, tokio_rusqlite::rusqlite::Error>(())
        })
        .await
        .unwrap();
    let store = SqliteStore::open(&database)
        .await
        .expect("ordinary open ignores unadopted R9 state");
    assert!(store
        .load_workload_receipt_commit("historical")
        .await
        .is_err());
    connection
        .call(|connection| {
            let payload: Vec<u8> = connection.query_row(
                "SELECT payload FROM workload_receipt_commits WHERE receipt_id = 'historical'",
                [],
                |row| row.get(0),
            )?;
            assert_eq!(payload, vec![0, 1, 255]);
            let count: i64 = connection.query_row(
                "SELECT COUNT(*) FROM sqlite_master WHERE tbl_name = 'workload_receipt_commits'",
                [],
                |row| row.get(0),
            )?;
            assert_eq!(
                count, 3,
                "original table, primary-key index and historical index only"
            );
            Ok::<_, tokio_rusqlite::rusqlite::Error>(())
        })
        .await
        .unwrap();
}
