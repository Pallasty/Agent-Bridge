use super::*;

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

static TEST_PATH_SEQUENCE: AtomicU64 = AtomicU64::new(0);

const S1_FIXTURE: &str = include_str!(
    "../../../../../scripts/eval/fixtures/memory_temporal_evidence_substrate_s1_synthetic_v0.json"
);

fn test_path(tag: &str) -> (PathBuf, PathBuf) {
    let sequence = TEST_PATH_SEQUENCE.fetch_add(1, Ordering::Relaxed);
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let directory = std::env::temp_dir().join(format!(
        "agent-bridge-truth-evidence-s2-{tag}-{}-{nonce}-{sequence}",
        std::process::id()
    ));
    let database = directory.join("state.db");
    (directory, database)
}

async fn fresh_store(tag: &str) -> (PathBuf, PathBuf, SqliteStore) {
    let (directory, database) = test_path(tag);
    let store = SqliteStore::open(&database)
        .await
        .expect("open isolated S2 store");
    (directory, database, store)
}

async fn remove_test_directory(directory: &Path) {
    let _ = tokio::fs::remove_dir_all(directory).await;
}

fn assert_rejection(
    error: TemporalEvidenceStoreError,
    code: &str,
    kind: TemporalEvidenceErrorKind,
) {
    assert_eq!(error.code(), code, "unexpected rejection: {error}");
    assert_eq!(error.kind(), kind, "unexpected rejection kind: {error}");
}

fn limits(
    max_lineages: usize,
    max_policy_revisions: usize,
    max_evidence_revisions: usize,
    max_relationships: usize,
    max_tombstones: usize,
    max_payload_bytes: usize,
) -> TemporalEvidenceSnapshotLimits {
    TemporalEvidenceSnapshotLimits {
        max_lineages,
        max_policy_revisions,
        max_evidence_revisions,
        max_relationships,
        max_tombstones,
        max_payload_bytes,
    }
}

fn generous_limits() -> TemporalEvidenceSnapshotLimits {
    limits(128, 128, 256, 256, 128, 2 * 1024 * 1024)
}

fn projection_limits() -> TemporalTruthProjectionLimitsV1 {
    TemporalTruthProjectionLimitsV1::try_new(128, 128, 256, 256, 128, 2 * 1024 * 1024)
        .expect("valid S4 projection limits")
}

fn projection_request(as_of: i64, knowledge_cutoff: i64) -> TemporalTruthProjectionRequestV1 {
    TemporalTruthProjectionRequestV1::try_new(
        as_of,
        knowledge_cutoff,
        Vec::new(),
        projection_limits(),
    )
    .expect("valid S4 projection request")
}

fn policy(
    revision_id: &str,
    lineage_id: &str,
    recorded_at: i64,
    predicate_id: &str,
    source_key: &str,
    tier: TruthTier,
    status: PolicyStatus,
) -> NewAuthorityPolicyRevision {
    NewAuthorityPolicyRevision {
        policy_revision_id: revision_id.to_string(),
        policy_lineage_id: lineage_id.to_string(),
        recorded_at,
        predicate_id: predicate_id.to_string(),
        source_key: source_key.to_string(),
        resolved_truth_tier: tier,
        valid_from: Some(0),
        valid_until: None,
        status,
    }
}

fn relationship(
    kind: RelationshipKind,
    target_lineage_id: &str,
    effective_from: i64,
) -> NewRelationship {
    NewRelationship {
        relationship_kind: kind,
        target_lineage_id: target_lineage_id.to_string(),
        effective_from,
    }
}

#[allow(clippy::too_many_arguments)]
fn evidence(
    evidence_id: &str,
    lineage_id: &str,
    referent_id: &str,
    predicate_id: &str,
    lineage_created_at: i64,
    recorded_at: i64,
    policy_revision_id: &str,
    source_key: &str,
    relationships: Vec<NewRelationship>,
) -> NewEvidenceRevision {
    NewEvidenceRevision {
        evidence_id: evidence_id.to_string(),
        lineage: NewTruthLineage {
            lineage_id: lineage_id.to_string(),
            referent_id: referent_id.to_string(),
            predicate_id: predicate_id.to_string(),
            created_at: lineage_created_at,
        },
        value: format!("value:{evidence_id}"),
        aliases: vec![format!("alias:{lineage_id}")],
        observed_at: recorded_at.saturating_sub(1),
        recorded_at,
        validity: EvidenceValidity {
            kind: ValidityKind::Timeless,
            valid_from: None,
            valid_until: None,
        },
        lifecycle: EvidenceLifecycle {
            state: LifecycleState::Active,
            effective_from: None,
        },
        source_bindings: vec![EvidenceSourceBinding {
            source_key: source_key.to_string(),
            provenance_sha256: sha256_hex(format!("provenance:{evidence_id}").as_bytes()),
        }],
        authority_policy_revision_id: policy_revision_id.to_string(),
        relationships,
    }
}

async fn append_policy(
    store: &SqliteStore,
    token: &SyntheticTemporalEvidenceWriteToken,
    input: NewAuthorityPolicyRevision,
) -> AuthorityPolicyRevisionRow {
    store
        .truth_evidence_append_policy_synthetic(token, input)
        .await
        .expect("append synthetic authority policy")
}

async fn append_evidence(
    store: &SqliteStore,
    token: &SyntheticTemporalEvidenceWriteToken,
    input: NewEvidenceRevision,
) -> EvidenceRevisionRow {
    store
        .truth_evidence_append_revision_synthetic(token, input)
        .await
        .expect("append synthetic evidence")
}

async fn seed_s4_source_time_relationship(store: &SqliteStore) {
    let token = synthetic_write_token();
    append_policy(
        store,
        &token,
        policy(
            "s4-target-policy-v1",
            "s4-target-policy",
            10,
            "claim.status",
            "source:target",
            TruthTier::Observed,
            PolicyStatus::Active,
        ),
    )
    .await;
    append_policy(
        store,
        &token,
        policy(
            "s4-source-policy-v1",
            "s4-source-policy",
            10,
            "claim.status",
            "source:source",
            TruthTier::Verified,
            PolicyStatus::Active,
        ),
    )
    .await;
    append_evidence(
        store,
        &token,
        evidence(
            "s4-target-v1",
            "s4-target",
            "subject:s4",
            "claim.status",
            20,
            90,
            "s4-target-policy-v1",
            "source:target",
            Vec::new(),
        ),
    )
    .await;
    let mut source = evidence(
        "s4-source-v1",
        "s4-source",
        "subject:s4",
        "claim.status",
        20,
        100,
        "s4-source-policy-v1",
        "source:source",
        vec![relationship(RelationshipKind::Supersedes, "s4-target", 110)],
    );
    source.source_bindings.push(EvidenceSourceBinding {
        source_key: "source:supplemental".to_string(),
        provenance_sha256: sha256_hex(b"provenance:s4-source-supplemental"),
    });
    append_evidence(store, &token, source).await;
}

async fn append_s4_target_upgrade(store: &SqliteStore) {
    let token = synthetic_write_token();
    append_policy(
        store,
        &token,
        policy(
            "s4-target-policy-v2",
            "s4-target-policy",
            150,
            "claim.status",
            "source:target",
            TruthTier::Authoritative,
            PolicyStatus::Active,
        ),
    )
    .await;
    append_evidence(
        store,
        &token,
        evidence(
            "s4-target-v2",
            "s4-target",
            "subject:s4",
            "claim.status",
            20,
            200,
            "s4-target-policy-v2",
            "source:target",
            Vec::new(),
        ),
    )
    .await;
}

async fn rewind_empty_truth_schema_to_v42(store: &SqliteStore, insert_legacy_row: bool) {
    store
        .conn
        .call(move |connection| -> RusqliteResult<()> {
            if insert_legacy_row {
                connection.execute(
                    "INSERT INTO memories(
                         key,kind,content,tags,related_keys,created_at,updated_at,
                         last_accessed_at,access_count
                     ) VALUES(
                         'legacy-s2-row','fact','legacy content','[]','[]',1,1,1,0
                     )",
                    [],
                )?;
            }
            connection.execute_batch(
                "DROP TABLE truth_evidence_relationships;
                 DROP TABLE truth_lineage_tombstones;
                 DROP TABLE truth_evidence_revisions;
                 DROP TABLE truth_authority_policy_revisions;
                 DROP TABLE truth_lineages;",
            )?;
            connection.execute(
                "DELETE FROM schema_meta
                  WHERE key IN (?1,?2,?3)",
                params![
                    SCHEMA_DIGEST_META_KEY,
                    MIGRATION_DIGEST_META_KEY,
                    LEDGER_FORMAT_META_KEY
                ],
            )?;
            connection.execute("UPDATE schema_meta SET value='42' WHERE key='version'", [])?;
            Ok(())
        })
        .await
        .expect("rewind empty temporal evidence schema to v42");
}

async fn truth_table_counts(store: &SqliteStore) -> [i64; 5] {
    store
        .conn
        .call(|connection| -> RusqliteResult<[i64; 5]> {
            Ok([
                connection
                    .query_row("SELECT COUNT(*) FROM truth_lineages", [], |row| row.get(0))?,
                connection.query_row(
                    "SELECT COUNT(*) FROM truth_authority_policy_revisions",
                    [],
                    |row| row.get(0),
                )?,
                connection.query_row(
                    "SELECT COUNT(*) FROM truth_evidence_revisions",
                    [],
                    |row| row.get(0),
                )?,
                connection.query_row(
                    "SELECT COUNT(*) FROM truth_evidence_relationships",
                    [],
                    |row| row.get(0),
                )?,
                connection.query_row(
                    "SELECT COUNT(*) FROM truth_lineage_tombstones",
                    [],
                    |row| row.get(0),
                )?,
            ])
        })
        .await
        .expect("read truth table counts")
}

async fn replay_s1_fixture(store: &SqliteStore) -> TemporalEvidenceSnapshot {
    let token = synthetic_write_token();
    let fixture: serde_json::Value = serde_json::from_str(S1_FIXTURE).expect("parse S1 fixture");
    let lineages: Vec<TruthLineageRow> =
        serde_json::from_value(fixture["lineages"].clone()).expect("decode S1 lineages");
    let policies: Vec<AuthorityPolicyRevisionRow> =
        serde_json::from_value(fixture["authority_policies"].clone()).expect("decode S1 policies");
    let mut revisions: Vec<EvidenceRevisionRow> =
        serde_json::from_value(fixture["revisions"].clone()).expect("decode S1 revisions");
    let relationships: Vec<EvidenceRelationshipRow> =
        serde_json::from_value(fixture["relationships"].clone()).expect("decode S1 relationships");
    let tombstones: Vec<LineageTombstoneRow> =
        serde_json::from_value(fixture["tombstones"].clone()).expect("decode S1 tombstones");

    for expected in policies {
        let inserted = append_policy(
            store,
            &token,
            NewAuthorityPolicyRevision {
                policy_revision_id: expected.policy_revision_id.clone(),
                policy_lineage_id: expected.policy_lineage_id.clone(),
                recorded_at: expected.recorded_at,
                predicate_id: expected.predicate_id.clone(),
                source_key: expected.source_key.clone(),
                resolved_truth_tier: expected.resolved_truth_tier,
                valid_from: expected.valid_from,
                valid_until: expected.valid_until,
                status: expected.status,
            },
        )
        .await;
        assert_eq!(inserted, expected);
    }

    revisions.sort_by(|left, right| {
        left.recorded_at
            .cmp(&right.recorded_at)
            .then_with(|| left.lineage_id.cmp(&right.lineage_id))
            .then_with(|| left.revision_seq.cmp(&right.revision_seq))
    });
    for expected in revisions {
        let lineage = lineages
            .iter()
            .find(|candidate| candidate.lineage_id == expected.lineage_id)
            .expect("S1 revision lineage");
        let revision_relationships = relationships
            .iter()
            .filter(|candidate| candidate.declared_evidence_id == expected.evidence_id)
            .map(|candidate| NewRelationship {
                relationship_kind: candidate.relationship_kind,
                target_lineage_id: candidate.target_lineage_id.clone(),
                effective_from: candidate.effective_from,
            })
            .collect();
        let inserted = append_evidence(
            store,
            &token,
            NewEvidenceRevision {
                evidence_id: expected.evidence_id.clone(),
                lineage: NewTruthLineage {
                    lineage_id: lineage.lineage_id.clone(),
                    referent_id: lineage.referent_id.clone(),
                    predicate_id: lineage.predicate_id.clone(),
                    created_at: lineage.created_at,
                },
                value: expected.value.clone(),
                aliases: expected.aliases.clone(),
                observed_at: expected.observed_at,
                recorded_at: expected.recorded_at,
                validity: expected.validity.clone(),
                lifecycle: expected.lifecycle.clone(),
                source_bindings: expected.source_bindings.clone(),
                authority_policy_revision_id: expected.authority_policy_revision_id.clone(),
                relationships: revision_relationships,
            },
        )
        .await;
        assert_eq!(inserted, expected);
    }

    for expected in tombstones {
        let inserted = store
            .truth_evidence_tombstone_lineage_synthetic(
                &token,
                NewLineageTombstone {
                    tombstone_id: expected.tombstone_id.clone(),
                    lineage_id: expected.lineage_id.clone(),
                    tombstoned_at: expected.tombstoned_at,
                },
            )
            .await
            .expect("replay S1 tombstone");
        assert_eq!(inserted, expected);
    }

    store
        .truth_evidence_snapshot_internal(limits(32, 32, 64, 64, 32, 1024 * 1024), 300)
        .await
        .expect("load replayed S1 snapshot")
}

#[tokio::test]
async fn truth_evidence_s2_v42_migration_is_zero_backfill_idempotent_and_concurrent() {
    let (directory, database, store) = fresh_store("migration-concurrent").await;
    rewind_empty_truth_schema_to_v42(&store, true).await;
    drop(store);

    let (left, right) = tokio::join!(SqliteStore::open(&database), SqliteStore::open(&database));
    let left = left.expect("first concurrent v42 -> v43 open");
    let right = right.expect("second concurrent v42 -> v43 open");
    assert_eq!(truth_table_counts(&left).await, [0, 0, 0, 0, 0]);
    let (version, legacy_rows, identity_rows): (String, i64, i64) = left
        .conn
        .call(|connection| -> RusqliteResult<(String, i64, i64)> {
            Ok((
                connection.query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |row| row.get(0),
                )?,
                connection.query_row(
                    "SELECT COUNT(*) FROM memories WHERE key='legacy-s2-row'",
                    [],
                    |row| row.get(0),
                )?,
                connection.query_row(
                    "SELECT COUNT(*) FROM schema_meta WHERE key IN (?1,?2,?3)",
                    params![
                        SCHEMA_DIGEST_META_KEY,
                        MIGRATION_DIGEST_META_KEY,
                        LEDGER_FORMAT_META_KEY
                    ],
                    |row| row.get(0),
                )?,
            ))
        })
        .await
        .expect("inspect migrated identity");
    assert_eq!(version, "43");
    assert_eq!(legacy_rows, 1, "migration must retain the legacy row");
    assert_eq!(identity_rows, 3);
    assert_eq!(truth_table_counts(&right).await, [0, 0, 0, 0, 0]);

    drop(left);
    drop(right);
    let reopened = SqliteStore::open(&database)
        .await
        .expect("idempotent v43 reopen");
    assert_eq!(truth_table_counts(&reopened).await, [0, 0, 0, 0, 0]);
    drop(reopened);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn truth_evidence_s2_v42_reserved_collision_rolls_back_without_backfill() {
    let (directory, database, store) = fresh_store("migration-collision").await;
    rewind_empty_truth_schema_to_v42(&store, true).await;
    store
        .conn
        .call(|connection| -> RusqliteResult<()> {
            connection.execute(
                "CREATE VIEW TrUtH_reserved_collision AS SELECT 'owned' AS marker",
                [],
            )?;
            Ok(())
        })
        .await
        .expect("install reserved collision");
    drop(store);

    let error = match SqliteStore::open(&database).await {
        Ok(_) => panic!("reserved v42 collision must fail closed"),
        Err(error) => error,
    };
    assert!(
        error
            .to_string()
            .contains("truth_evidence_migration_collision"),
        "unexpected migration error: {error}"
    );

    let connection = rusqlite::Connection::open(&database).expect("inspect collision database");
    let version: String = connection
        .query_row(
            "SELECT value FROM schema_meta WHERE key='version'",
            [],
            |row| row.get(0),
        )
        .expect("read rolled-back version");
    let legacy_rows: i64 = connection
        .query_row(
            "SELECT COUNT(*) FROM memories WHERE key='legacy-s2-row'",
            [],
            |row| row.get(0),
        )
        .expect("read legacy row");
    let created_truth_tables: i64 = connection
        .query_row(
            "SELECT COUNT(*) FROM sqlite_master
              WHERE type='table' AND name IN (
                'truth_lineages','truth_authority_policy_revisions',
                'truth_evidence_revisions','truth_evidence_relationships',
                'truth_lineage_tombstones'
              )",
            [],
            |row| row.get(0),
        )
        .expect("count truth tables");
    assert_eq!(version, "42");
    assert_eq!(legacy_rows, 1);
    assert_eq!(created_truth_tables, 0);
    drop(connection);
    remove_test_directory(&directory).await;

    let (directory, database, store) = fresh_store("migration-meta-collision").await;
    rewind_empty_truth_schema_to_v42(&store, true).await;
    store
        .conn
        .call(|connection| -> RusqliteResult<()> {
            connection.execute(
                "INSERT INTO schema_meta(key,value)
                 VALUES('truth_evidence.unreviewed','foreign-owner')",
                [],
            )?;
            Ok(())
        })
        .await
        .expect("install unknown reserved identity row");
    drop(store);
    let error = match SqliteStore::open(&database).await {
        Ok(_) => panic!("unknown v42 truth_evidence meta key must collide"),
        Err(error) => error,
    };
    assert!(
        error
            .to_string()
            .contains("truth_evidence_migration_collision"),
        "unexpected meta collision error: {error}"
    );
    let connection = rusqlite::Connection::open(&database).expect("inspect meta collision");
    let (version, unknown_rows): (String, i64) = connection
        .query_row(
            "SELECT
                 (SELECT value FROM schema_meta WHERE key='version'),
                 (SELECT COUNT(*) FROM schema_meta
                   WHERE key='truth_evidence.unreviewed')",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .expect("read meta collision rollback");
    assert_eq!(version, "42");
    assert_eq!(unknown_rows, 1);
    drop(connection);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn truth_evidence_s2_schema_identity_rejects_view_temp_shadow_and_meta_drift() {
    let token_limits = TemporalEvidenceSnapshotLimits::default();

    let (view_directory, _database, view_store) = fresh_store("identity-view").await;
    view_store
        .conn
        .call(|connection| -> RusqliteResult<()> {
            connection.execute("CREATE VIEW truth_shadow AS SELECT 1 AS value", [])?;
            Ok(())
        })
        .await
        .expect("create persistent reserved view");
    let error = view_store
        .truth_evidence_snapshot_internal(token_limits, 0)
        .await
        .expect_err("persistent reserved view must drift schema identity");
    assert_rejection(
        error,
        "truth_evidence_identity",
        TemporalEvidenceErrorKind::SchemaIdentity,
    );
    drop(view_store);
    remove_test_directory(&view_directory).await;

    let (trigger_directory, _database, trigger_store) = fresh_store("identity-trigger").await;
    trigger_store
        .conn
        .call(|connection| -> RusqliteResult<()> {
            connection.execute_batch(
                "CREATE TRIGGER evil_s2_trigger
                 AFTER INSERT ON truth_lineages
                 BEGIN SELECT 1; END;",
            )?;
            Ok(())
        })
        .await
        .expect("create non-reserved persistent trigger on truth table");
    let error = trigger_store
        .truth_evidence_snapshot_internal(token_limits, 0)
        .await
        .expect_err("foreign trigger attached to truth table must drift identity");
    assert_rejection(
        error,
        "truth_evidence_identity",
        TemporalEvidenceErrorKind::SchemaIdentity,
    );
    drop(trigger_store);
    remove_test_directory(&trigger_directory).await;

    let (temp_directory, _database, temp_store) = fresh_store("identity-temp").await;
    temp_store
        .conn
        .call(|connection| -> RusqliteResult<()> {
            connection.execute(
                "CREATE TEMP VIEW truth_lineages AS SELECT 'shadow' AS lineage_id",
                [],
            )?;
            Ok(())
        })
        .await
        .expect("create reserved temp shadow");
    let error = temp_store
        .truth_evidence_snapshot_internal(token_limits, 0)
        .await
        .expect_err("reserved temp shadow must fail closed");
    assert_rejection(
        error,
        "truth_evidence_identity",
        TemporalEvidenceErrorKind::SchemaIdentity,
    );
    drop(temp_store);
    remove_test_directory(&temp_directory).await;

    let (uppercase_temp_directory, _database, uppercase_temp_store) =
        fresh_store("identity-uppercase-temp").await;
    uppercase_temp_store
        .conn
        .call(|connection| -> RusqliteResult<()> {
            connection.execute(
                "CREATE TEMP VIEW TRUTH_LINEAGES AS SELECT 'shadow' AS lineage_id",
                [],
            )?;
            Ok(())
        })
        .await
        .expect("create case-variant reserved temp shadow");
    let error = uppercase_temp_store
        .truth_evidence_snapshot_internal(token_limits, 0)
        .await
        .expect_err("SQLite case-insensitive temp shadow must fail closed");
    assert_rejection(
        error,
        "truth_evidence_identity",
        TemporalEvidenceErrorKind::SchemaIdentity,
    );
    drop(uppercase_temp_store);
    remove_test_directory(&uppercase_temp_directory).await;

    let (temp_trigger_directory, _database, temp_trigger_store) =
        fresh_store("identity-temp-trigger").await;
    temp_trigger_store
        .conn
        .call(|connection| -> RusqliteResult<()> {
            connection.execute_batch(
                "CREATE TEMP TRIGGER evil_s2_temp_trigger
                 AFTER INSERT ON main.truth_lineages
                 BEGIN SELECT 1; END;",
            )?;
            Ok(())
        })
        .await
        .expect("create non-reserved temp trigger on truth table");
    let error = temp_trigger_store
        .truth_evidence_snapshot_internal(token_limits, 0)
        .await
        .expect_err("foreign temp trigger attached to truth table must fail closed");
    assert_rejection(
        error,
        "truth_evidence_identity",
        TemporalEvidenceErrorKind::SchemaIdentity,
    );
    drop(temp_trigger_store);
    remove_test_directory(&temp_trigger_directory).await;

    let (meta_directory, _database, meta_store) = fresh_store("identity-meta").await;
    meta_store
        .conn
        .call(|connection| -> RusqliteResult<()> {
            connection.execute(
                "UPDATE schema_meta SET value=?1 WHERE key=?2",
                params!["00", SCHEMA_DIGEST_META_KEY],
            )?;
            Ok(())
        })
        .await
        .expect("drift schema identity meta");
    let error = meta_store
        .truth_evidence_snapshot_internal(token_limits, 0)
        .await
        .expect_err("schema meta drift must fail closed");
    assert_rejection(
        error,
        "truth_evidence_identity",
        TemporalEvidenceErrorKind::SchemaIdentity,
    );
    drop(meta_store);
    remove_test_directory(&meta_directory).await;

    let (unknown_meta_directory, _database, unknown_meta_store) =
        fresh_store("identity-unknown-meta").await;
    unknown_meta_store
        .conn
        .call(|connection| -> RusqliteResult<()> {
            connection.execute(
                "INSERT INTO schema_meta(key,value)
                 VALUES('truth_evidence.unreviewed','foreign-owner')",
                [],
            )?;
            Ok(())
        })
        .await
        .expect("insert unknown v43 identity row");
    let error = unknown_meta_store
        .truth_evidence_snapshot_internal(token_limits, 0)
        .await
        .expect_err("unknown truth_evidence meta key must fail identity");
    assert_rejection(
        error,
        "truth_evidence_identity",
        TemporalEvidenceErrorKind::SchemaIdentity,
    );
    drop(unknown_meta_store);
    remove_test_directory(&unknown_meta_directory).await;
}

#[tokio::test]
async fn truth_evidence_s2_s1_fixture_replay_has_exact_payload_and_keeps_late_row() {
    let (directory, _database, store) = fresh_store("s1-replay").await;
    let snapshot = replay_s1_fixture(&store).await;

    assert_eq!(
        snapshot.counts,
        TemporalEvidenceSnapshotCounts {
            lineages: 9,
            policy_revisions: 5,
            evidence_revisions: 10,
            relationships: 4,
            tombstones: 2,
        }
    );
    assert_eq!(snapshot.knowledge_cutoff, 300);
    assert!(snapshot
        .revisions
        .iter()
        .any(|revision| revision.evidence_id == "status-late-v1" && revision.recorded_at == 350));
    assert_eq!(snapshot.payload_bytes, 9_566);
    assert_eq!(
        snapshot.payload_sha256,
        "a69fe303e42cf43a644195fa3e7a845e36303034d6014219455485335fbe812d"
    );
    assert_eq!(snapshot.canonical_order, "binary_utf8_v0");
    assert_eq!(snapshot.producer_identity.schema_meta_version, "43");
    assert_eq!(
        snapshot.producer_identity.schema_digest,
        EXPECTED_SCHEMA_SHA256
    );
    assert_eq!(
        snapshot.producer_identity.ledger_format_version,
        TEMPORAL_EVIDENCE_LEDGER_FORMAT_VERSION
    );
    assert_eq!(
        snapshot
            .relationships
            .iter()
            .filter(|row| row.target_lineage_id == "employment-old")
            .map(|row| row.declared_evidence_id.as_str())
            .collect::<Vec<_>>(),
        vec!["employment-new-v1", "employment-new-v2"]
    );

    drop(store);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn truth_evidence_s2_policy_sequence_latest_revocation_and_backdated_rollback() {
    let token = synthetic_write_token();
    let (directory, _database, store) = fresh_store("policy").await;
    let first = append_policy(
        &store,
        &token,
        policy(
            "policy-v1",
            "policy-lineage",
            10,
            "claim.status",
            "source:registry",
            TruthTier::Verified,
            PolicyStatus::Active,
        ),
    )
    .await;
    assert_eq!(first.revision_seq, 1);
    let second = append_policy(
        &store,
        &token,
        policy(
            "policy-v2",
            "policy-lineage",
            200,
            "claim.status",
            "source:registry",
            TruthTier::Verified,
            PolicyStatus::Revoked,
        ),
    )
    .await;
    assert_eq!(second.revision_seq, 2);

    let input = evidence(
        "latest-rejected",
        "latest-lineage",
        "subject:one",
        "claim.status",
        240,
        250,
        "policy-v1",
        "source:registry",
        Vec::new(),
    );
    let error = store
        .truth_evidence_append_revision_synthetic(&token, input)
        .await
        .expect_err("superseded policy revision must not be cited");
    assert_rejection(
        error,
        "truth_evidence_policy_not_latest_visible",
        TemporalEvidenceErrorKind::Conflict,
    );
    let input = evidence(
        "revoked-rejected",
        "revoked-lineage",
        "subject:two",
        "claim.status",
        240,
        250,
        "policy-v2",
        "source:registry",
        Vec::new(),
    );
    let error = store
        .truth_evidence_append_revision_synthetic(&token, input)
        .await
        .expect_err("latest revoked policy must be inactive");
    assert_rejection(
        error,
        "truth_evidence_authority_policy_inactive",
        TemporalEvidenceErrorKind::Conflict,
    );
    assert_eq!(truth_table_counts(&store).await, [0, 2, 0, 0, 0]);
    drop(store);
    remove_test_directory(&directory).await;

    let (directory, _database, store) = fresh_store("policy-backdated").await;
    append_policy(
        &store,
        &token,
        policy(
            "backdated-policy-v1",
            "backdated-policy",
            10,
            "claim.status",
            "source:registry",
            TruthTier::Verified,
            PolicyStatus::Active,
        ),
    )
    .await;
    append_evidence(
        &store,
        &token,
        evidence(
            "existing-v1",
            "existing-lineage",
            "subject:three",
            "claim.status",
            90,
            100,
            "backdated-policy-v1",
            "source:registry",
            Vec::new(),
        ),
    )
    .await;
    let error = store
        .truth_evidence_append_policy_synthetic(
            &token,
            policy(
                "backdated-policy-v2",
                "backdated-policy",
                50,
                "claim.status",
                "source:registry",
                TruthTier::Verified,
                PolicyStatus::Active,
            ),
        )
        .await
        .expect_err("backdated policy must not invalidate admitted evidence");
    assert_rejection(
        error,
        "truth_evidence_policy_not_latest_visible",
        TemporalEvidenceErrorKind::Conflict,
    );
    let snapshot = store
        .truth_evidence_snapshot_internal(generous_limits(), 500)
        .await
        .expect("snapshot after policy rollback");
    assert_eq!(snapshot.authority_policies.len(), 1);
    assert_eq!(
        snapshot.authority_policies[0].policy_revision_id,
        "backdated-policy-v1"
    );
    assert_eq!(snapshot.revisions.len(), 1);
    drop(store);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn truth_evidence_s2_relationship_carry_forward_and_drop_guard_are_atomic() {
    let token = synthetic_write_token();
    let (directory, _database, store) = fresh_store("relationship-carry").await;
    append_policy(
        &store,
        &token,
        policy(
            "p-v1",
            "p",
            10,
            "claim.location",
            "source:registry",
            TruthTier::Verified,
            PolicyStatus::Active,
        ),
    )
    .await;
    append_evidence(
        &store,
        &token,
        evidence(
            "old-v1",
            "old",
            "subject:one",
            "claim.location",
            90,
            100,
            "p-v1",
            "source:registry",
            Vec::new(),
        ),
    )
    .await;
    let edge = relationship(RelationshipKind::Supersedes, "old", 200);
    append_evidence(
        &store,
        &token,
        evidence(
            "current-v1",
            "current",
            "subject:one",
            "claim.location",
            140,
            150,
            "p-v1",
            "source:registry",
            vec![edge.clone()],
        ),
    )
    .await;
    append_evidence(
        &store,
        &token,
        evidence(
            "current-v2",
            "current",
            "subject:one",
            "claim.location",
            140,
            180,
            "p-v1",
            "source:registry",
            vec![edge],
        ),
    )
    .await;
    let error = store
        .truth_evidence_append_revision_synthetic(
            &token,
            evidence(
                "current-v3",
                "current",
                "subject:one",
                "claim.location",
                140,
                190,
                "p-v1",
                "source:registry",
                Vec::new(),
            ),
        )
        .await
        .expect_err("later revision must carry durable relationship tuple");
    assert_rejection(
        error,
        "truth_evidence_dropped_relationship",
        TemporalEvidenceErrorKind::Conflict,
    );
    let snapshot = store
        .truth_evidence_snapshot_internal(generous_limits(), 500)
        .await
        .expect("snapshot carry-forward ledger");
    assert_eq!(snapshot.revisions.len(), 3);
    assert_eq!(snapshot.relationships.len(), 2);
    drop(store);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn truth_evidence_s2_relationship_rejects_same_second_lower_tier_cross_claim_and_cycle() {
    let token = synthetic_write_token();

    let (directory, _database, store) = fresh_store("relationship-same-second").await;
    append_policy(
        &store,
        &token,
        policy(
            "p-v1",
            "p",
            10,
            "claim.state",
            "source:registry",
            TruthTier::Verified,
            PolicyStatus::Active,
        ),
    )
    .await;
    append_evidence(
        &store,
        &token,
        evidence(
            "target-v1",
            "target",
            "subject:one",
            "claim.state",
            140,
            150,
            "p-v1",
            "source:registry",
            Vec::new(),
        ),
    )
    .await;
    let error = store
        .truth_evidence_append_revision_synthetic(
            &token,
            evidence(
                "source-v1",
                "source",
                "subject:one",
                "claim.state",
                140,
                150,
                "p-v1",
                "source:registry",
                vec![relationship(RelationshipKind::Invalidates, "target", 170)],
            ),
        )
        .await
        .expect_err("same-second target is ambiguous");
    assert_rejection(
        error,
        "truth_evidence_same_second_target_ambiguity",
        TemporalEvidenceErrorKind::Conflict,
    );
    assert_eq!(truth_table_counts(&store).await, [1, 1, 1, 0, 0]);
    drop(store);
    remove_test_directory(&directory).await;

    let (directory, _database, store) = fresh_store("relationship-tier").await;
    append_policy(
        &store,
        &token,
        policy(
            "verified-v1",
            "verified",
            10,
            "claim.state",
            "source:verified",
            TruthTier::Verified,
            PolicyStatus::Active,
        ),
    )
    .await;
    append_policy(
        &store,
        &token,
        policy(
            "observed-v1",
            "observed",
            10,
            "claim.state",
            "source:observed",
            TruthTier::Observed,
            PolicyStatus::Active,
        ),
    )
    .await;
    append_evidence(
        &store,
        &token,
        evidence(
            "target-v1",
            "target",
            "subject:one",
            "claim.state",
            90,
            100,
            "verified-v1",
            "source:verified",
            Vec::new(),
        ),
    )
    .await;
    let error = store
        .truth_evidence_append_revision_synthetic(
            &token,
            evidence(
                "source-v1",
                "source",
                "subject:one",
                "claim.state",
                140,
                150,
                "observed-v1",
                "source:observed",
                vec![relationship(RelationshipKind::Invalidates, "target", 170)],
            ),
        )
        .await
        .expect_err("lower-tier source must not suppress higher-tier target");
    assert_rejection(
        error,
        "truth_evidence_lower_tier_suppression",
        TemporalEvidenceErrorKind::Conflict,
    );
    drop(store);
    remove_test_directory(&directory).await;

    let (directory, _database, store) = fresh_store("relationship-cross-claim").await;
    append_policy(
        &store,
        &token,
        policy(
            "p-v1",
            "p",
            10,
            "claim.state",
            "source:registry",
            TruthTier::Verified,
            PolicyStatus::Active,
        ),
    )
    .await;
    append_evidence(
        &store,
        &token,
        evidence(
            "target-v1",
            "target",
            "subject:other",
            "claim.state",
            90,
            100,
            "p-v1",
            "source:registry",
            Vec::new(),
        ),
    )
    .await;
    let error = store
        .truth_evidence_append_revision_synthetic(
            &token,
            evidence(
                "source-v1",
                "source",
                "subject:one",
                "claim.state",
                140,
                150,
                "p-v1",
                "source:registry",
                vec![relationship(RelationshipKind::Invalidates, "target", 170)],
            ),
        )
        .await
        .expect_err("relationship endpoints must share exact claim identity");
    assert_rejection(
        error,
        "truth_evidence_cross_claim_relationship",
        TemporalEvidenceErrorKind::Conflict,
    );
    drop(store);
    remove_test_directory(&directory).await;

    let (directory, _database, store) = fresh_store("relationship-cycle").await;
    append_policy(
        &store,
        &token,
        policy(
            "p-v1",
            "p",
            10,
            "claim.state",
            "source:registry",
            TruthTier::Verified,
            PolicyStatus::Active,
        ),
    )
    .await;
    append_evidence(
        &store,
        &token,
        evidence(
            "b-v1",
            "b",
            "subject:one",
            "claim.state",
            90,
            100,
            "p-v1",
            "source:registry",
            Vec::new(),
        ),
    )
    .await;
    append_evidence(
        &store,
        &token,
        evidence(
            "a-v1",
            "a",
            "subject:one",
            "claim.state",
            140,
            150,
            "p-v1",
            "source:registry",
            vec![relationship(RelationshipKind::Supersedes, "b", 170)],
        ),
    )
    .await;
    let error = store
        .truth_evidence_append_revision_synthetic(
            &token,
            evidence(
                "b-v2",
                "b",
                "subject:one",
                "claim.state",
                90,
                200,
                "p-v1",
                "source:registry",
                vec![relationship(RelationshipKind::Supersedes, "a", 220)],
            ),
        )
        .await
        .expect_err("latest-lineage governance graph must remain acyclic");
    assert_rejection(
        error,
        "truth_evidence_relationship_cycle",
        TemporalEvidenceErrorKind::Conflict,
    );
    let snapshot = store
        .truth_evidence_snapshot_internal(generous_limits(), 500)
        .await
        .expect("cycle rejection rollback snapshot");
    assert_eq!(snapshot.revisions.len(), 2);
    assert_eq!(snapshot.relationships.len(), 1);
    drop(store);
    remove_test_directory(&directory).await;
}

#[test]
fn truth_evidence_s2_cycle_validation_handles_maximum_depth_without_recursion() {
    let node_count = MAX_LINEAGES - 1;
    let mut adjacency = HashMap::with_capacity(node_count);
    for index in 0..node_count {
        let targets = (index + 1 < node_count)
            .then(|| vec![format!("lineage-{}", index + 1)])
            .unwrap_or_default();
        adjacency.insert(format!("lineage-{index}"), targets);
    }

    validate_acyclic_adjacency(&adjacency)
        .expect("a maximum-depth acyclic graph must not consume the call stack");
    adjacency
        .get_mut(&format!("lineage-{}", node_count - 1))
        .expect("last lineage")
        .push("lineage-0".to_string());
    let error = validate_acyclic_adjacency(&adjacency)
        .expect_err("the iterative validator must still reject a deep cycle");
    assert!(
        error
            .to_string()
            .contains("truth_evidence_relationship_cycle"),
        "unexpected deep-cycle rejection: {error}"
    );
}

#[tokio::test]
async fn truth_evidence_s2_backdated_target_revision_cannot_invalidate_existing_relationship() {
    let token = synthetic_write_token();
    let (directory, _database, store) = fresh_store("relationship-retroactive-target").await;
    for input in [
        policy(
            "target-observed-v1",
            "target-observed-policy",
            10,
            "claim.state",
            "source:target-observed",
            TruthTier::Observed,
            PolicyStatus::Active,
        ),
        policy(
            "source-verified-v1",
            "source-verified-policy",
            10,
            "claim.state",
            "source:source-verified",
            TruthTier::Verified,
            PolicyStatus::Active,
        ),
        policy(
            "target-authoritative-v1",
            "target-authoritative-policy",
            10,
            "claim.state",
            "source:target-authoritative",
            TruthTier::Authoritative,
            PolicyStatus::Active,
        ),
    ] {
        append_policy(&store, &token, input).await;
    }
    append_evidence(
        &store,
        &token,
        evidence(
            "target-v1",
            "target",
            "subject:one",
            "claim.state",
            90,
            100,
            "target-observed-v1",
            "source:target-observed",
            Vec::new(),
        ),
    )
    .await;
    append_evidence(
        &store,
        &token,
        evidence(
            "source-v1",
            "source",
            "subject:one",
            "claim.state",
            190,
            200,
            "source-verified-v1",
            "source:source-verified",
            vec![relationship(RelationshipKind::Invalidates, "target", 220)],
        ),
    )
    .await;
    let baseline = store
        .truth_evidence_snapshot_internal(generous_limits(), 500)
        .await
        .expect("baseline relationship snapshot");
    assert_eq!(
        baseline.counts,
        TemporalEvidenceSnapshotCounts {
            lineages: 2,
            policy_revisions: 3,
            evidence_revisions: 2,
            relationships: 1,
            tombstones: 0,
        }
    );

    let error = store
        .truth_evidence_append_revision_synthetic(
            &token,
            evidence(
                "target-v2-same-second",
                "target",
                "subject:one",
                "claim.state",
                90,
                200,
                "target-authoritative-v1",
                "source:target-authoritative",
                Vec::new(),
            ),
        )
        .await
        .expect_err("retroactive same-second target revision must roll back");
    assert_rejection(
        error,
        "truth_evidence_same_second_target_ambiguity",
        TemporalEvidenceErrorKind::Conflict,
    );
    let after_same_second = store
        .truth_evidence_snapshot_internal(generous_limits(), 500)
        .await
        .expect("snapshot after same-second rollback");
    assert_eq!(after_same_second.counts, baseline.counts);
    assert_eq!(after_same_second.payload_bytes, baseline.payload_bytes);
    assert_eq!(after_same_second.payload_sha256, baseline.payload_sha256);
    assert_eq!(
        after_same_second
            .revisions
            .iter()
            .filter(|revision| revision.lineage_id == "target")
            .map(|revision| revision.revision_seq)
            .collect::<Vec<_>>(),
        vec![1]
    );

    let error = store
        .truth_evidence_append_revision_synthetic(
            &token,
            evidence(
                "target-v2-higher-tier",
                "target",
                "subject:one",
                "claim.state",
                90,
                150,
                "target-authoritative-v1",
                "source:target-authoritative",
                Vec::new(),
            ),
        )
        .await
        .expect_err("retroactive higher-tier target revision must roll back");
    assert_rejection(
        error,
        "truth_evidence_lower_tier_suppression",
        TemporalEvidenceErrorKind::Conflict,
    );
    let after_tier_raise = store
        .truth_evidence_snapshot_internal(generous_limits(), 500)
        .await
        .expect("snapshot after target tier rollback");
    assert_eq!(after_tier_raise.counts, baseline.counts);
    assert_eq!(after_tier_raise.payload_bytes, baseline.payload_bytes);
    assert_eq!(after_tier_raise.payload_sha256, baseline.payload_sha256);
    assert_eq!(
        after_tier_raise
            .revisions
            .iter()
            .filter(|revision| revision.lineage_id == "target")
            .map(|revision| revision.revision_seq)
            .collect::<Vec<_>>(),
        vec![1]
    );

    drop(store);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn truth_evidence_s2_tombstone_attests_governance_allows_inbound_and_blocks_future_source() {
    let token = synthetic_write_token();
    let (directory, _database, store) = fresh_store("tombstone").await;
    append_policy(
        &store,
        &token,
        policy(
            "p-v1",
            "p",
            10,
            "claim.state",
            "source:registry",
            TruthTier::Verified,
            PolicyStatus::Active,
        ),
    )
    .await;
    append_evidence(
        &store,
        &token,
        evidence(
            "target-v1",
            "target",
            "subject:one",
            "claim.state",
            90,
            100,
            "p-v1",
            "source:registry",
            Vec::new(),
        ),
    )
    .await;
    let target_tombstone = store
        .truth_evidence_tombstone_lineage_synthetic(
            &token,
            NewLineageTombstone {
                tombstone_id: "target-tombstone".into(),
                lineage_id: "target".into(),
                tombstoned_at: 110,
            },
        )
        .await
        .expect("tombstone target");
    assert!(!target_tombstone.had_outgoing_governance);
    assert_eq!(
        target_tombstone.attestation_sha256,
        tombstone_attestation_sha256("target-tombstone", "target", 110, false)
            .expect("expected target tombstone digest")
    );

    let inbound = relationship(RelationshipKind::Invalidates, "target", 170);
    append_evidence(
        &store,
        &token,
        evidence(
            "source-v1",
            "source",
            "subject:one",
            "claim.state",
            140,
            150,
            "p-v1",
            "source:registry",
            vec![inbound.clone()],
        ),
    )
    .await;
    let source_tombstone = store
        .truth_evidence_tombstone_lineage_synthetic(
            &token,
            NewLineageTombstone {
                tombstone_id: "source-tombstone".into(),
                lineage_id: "source".into(),
                tombstoned_at: 160,
            },
        )
        .await
        .expect("tombstone governed source");
    assert!(source_tombstone.had_outgoing_governance);
    assert_eq!(
        source_tombstone.attestation_sha256,
        tombstone_attestation_sha256("source-tombstone", "source", 160, true)
            .expect("expected governed tombstone digest")
    );

    let error = store
        .truth_evidence_append_revision_synthetic(
            &token,
            evidence(
                "source-v2",
                "source",
                "subject:one",
                "claim.state",
                140,
                180,
                "p-v1",
                "source:registry",
                vec![inbound],
            ),
        )
        .await
        .expect_err("tombstoned source lineage must reject future revision");
    assert_rejection(
        error,
        "truth_evidence_tombstoned_lineage",
        TemporalEvidenceErrorKind::Conflict,
    );
    let snapshot = store
        .truth_evidence_snapshot_internal(generous_limits(), 500)
        .await
        .expect("snapshot tombstone ledger");
    assert_eq!(snapshot.relationships.len(), 1);
    assert_eq!(snapshot.relationships[0].target_lineage_id, "target");
    assert_eq!(snapshot.tombstones.len(), 2);
    drop(store);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn truth_evidence_s2_snapshot_strict_cap_equality_rejects_every_ledger_and_payload() {
    let (directory, _database, store) = fresh_store("caps").await;
    let baseline = replay_s1_fixture(&store).await;
    let cases = [
        limits(9, 32, 64, 64, 32, 1024 * 1024),
        limits(32, 5, 64, 64, 32, 1024 * 1024),
        limits(32, 32, 10, 64, 32, 1024 * 1024),
        limits(32, 32, 64, 4, 32, 1024 * 1024),
        limits(32, 32, 64, 64, 2, 1024 * 1024),
    ];
    for configured in cases {
        let error = store
            .truth_evidence_snapshot_internal(configured, 300)
            .await
            .expect_err("count equal to configured cap is sentinel overflow");
        assert_rejection(
            error,
            "truth_evidence_snapshot_truncated",
            TemporalEvidenceErrorKind::Capacity,
        );
    }

    let error = store
        .truth_evidence_snapshot_internal(limits(32, 32, 64, 64, 32, baseline.payload_bytes), 300)
        .await
        .expect_err("payload equal to byte cap is sentinel overflow");
    assert_rejection(
        error,
        "truth_evidence_snapshot_payload",
        TemporalEvidenceErrorKind::Capacity,
    );
    drop(store);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn truth_evidence_s2_snapshot_streaming_cap_rejects_control_character_expansion() {
    let token = synthetic_write_token();
    let (directory, _database, store) = fresh_store("streaming-cap").await;
    append_policy(
        &store,
        &token,
        policy(
            "p-v1",
            "p",
            10,
            "claim.state",
            "source:registry",
            TruthTier::Verified,
            PolicyStatus::Active,
        ),
    )
    .await;
    let mut expanded = evidence(
        "expanded-v1",
        "expanded",
        "subject:one",
        "claim.state",
        20,
        30,
        "p-v1",
        "source:registry",
        Vec::new(),
    );
    expanded.value = "\0".repeat(200_000);
    append_evidence(&store, &token, expanded).await;

    let error = store
        .truth_evidence_snapshot_internal(limits(4, 4, 4, 4, 4, 300_000), 100)
        .await
        .expect_err("escaped canonical output must stop at the configured byte sentinel");
    assert_rejection(
        error,
        "truth_evidence_snapshot_payload",
        TemporalEvidenceErrorKind::Capacity,
    );
    drop(store);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn truth_evidence_s2_every_ledger_table_rejects_raw_update_and_delete() {
    let (directory, _database, store) = fresh_store("append-only").await;
    let baseline = replay_s1_fixture(&store).await;
    let statements = [
        "UPDATE truth_lineages SET referent_id=referent_id WHERE lineage_id='employment-old'",
        "DELETE FROM truth_lineages WHERE lineage_id='employment-old'",
        "UPDATE truth_authority_policy_revisions SET status=status WHERE policy_revision_id='policy-employment-v1'",
        "DELETE FROM truth_authority_policy_revisions WHERE policy_revision_id='policy-employment-v1'",
        "UPDATE truth_evidence_revisions SET value=value WHERE evidence_id='employment-old-v1'",
        "DELETE FROM truth_evidence_revisions WHERE evidence_id='employment-old-v1'",
        "UPDATE truth_evidence_relationships SET effective_from=effective_from WHERE declared_evidence_id='employment-new-v1'",
        "DELETE FROM truth_evidence_relationships WHERE declared_evidence_id='employment-new-v1'",
        "UPDATE truth_lineage_tombstones SET tombstoned_at=tombstoned_at WHERE tombstone_id='tombstone-language-private-v1'",
        "DELETE FROM truth_lineage_tombstones WHERE tombstone_id='tombstone-language-private-v1'",
    ];
    for statement in statements {
        let statement = statement.to_string();
        let result = store
            .conn
            .call(move |connection| -> RusqliteResult<()> {
                connection.execute(&statement, [])?;
                Ok(())
            })
            .await;
        assert!(
            result.is_err(),
            "append-only statement unexpectedly succeeded"
        );
    }
    let after = store
        .truth_evidence_snapshot_internal(limits(32, 32, 64, 64, 32, 1024 * 1024), 300)
        .await
        .expect("snapshot after rejected raw mutations");
    assert_eq!(after.payload_bytes, baseline.payload_bytes);
    assert_eq!(after.payload_sha256, baseline.payload_sha256);
    drop(store);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn truth_evidence_s2_read_only_store_returns_the_exact_snapshot_without_writes() {
    let (directory, database, store) = fresh_store("read-only").await;
    let writable_snapshot = replay_s1_fixture(&store).await;
    drop(store);

    let read_only = SqliteStore::open_read_only(&database)
        .await
        .expect("open migrated truth ledger read-only");
    let query_only: i64 = read_only
        .conn
        .call(|connection| -> RusqliteResult<i64> {
            connection.query_row("PRAGMA query_only", [], |row| row.get(0))
        })
        .await
        .expect("inspect read-only query_only pragma");
    assert_eq!(query_only, 1);
    let read_only_snapshot = read_only
        .truth_evidence_snapshot_internal(limits(32, 32, 64, 64, 32, 1024 * 1024), 300)
        .await
        .expect("read-only temporal evidence snapshot");
    assert_eq!(read_only_snapshot, writable_snapshot);

    let write_result = read_only
        .conn
        .call(|connection| -> RusqliteResult<()> {
            connection.execute("UPDATE schema_meta SET value=value WHERE key='version'", [])?;
            Ok(())
        })
        .await;
    assert!(write_result.is_err(), "read-only handle performed a write");
    drop(read_only);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn temporal_truth_projection_s4_empty_ledger_is_deterministic_and_read_only() {
    let (directory, database, store) = fresh_store("s4-empty-pinned").await;
    drop(store);
    let required = TemporalTruthRequiredClaimV1::try_new("subject:empty", "claim.status")
        .expect("valid required claim");
    let request =
        TemporalTruthProjectionRequestV1::try_new(0, 0, vec![required], projection_limits())
            .expect("valid empty projection request");
    let first = temporal_truth_project_read_only_synthetic_v1(
        synthetic_projection_permit_v1(),
        &database,
        request.clone(),
    )
    .await
    .expect("project canonical empty fixture");
    let second = temporal_truth_project_read_only_synthetic_v1(
        synthetic_projection_permit_v1(),
        &database,
        request,
    )
    .await
    .expect("repeat canonical empty fixture projection");

    assert_eq!(first.synthetic_fixture_id(), "crate_unit_test_only_v0");
    assert_eq!(first.snapshot_payload_bytes(), 89);
    assert_eq!(
        first.snapshot_payload_sha256(),
        "7617db2143811b72f1d1059d4b75cafb3c77756af3a3e930010c7241a5172e16"
    );
    assert!(first.read_only_attested());
    assert!(first.query_only_attested());
    assert!(first.zero_total_changes_attested());
    assert_eq!(first.snapshot_counts().lineages(), 0);
    assert_eq!(first.snapshot_counts().evidence_revisions(), 0);
    let claims: Vec<_> = first.claims().collect();
    assert_eq!(claims.len(), 1);
    assert_eq!(claims[0].truth_state(), TemporalTruthStateV1::Unknown);
    assert_eq!(
        first.prepared_input_sha256(),
        second.prepared_input_sha256()
    );
    assert_eq!(first.projection_sha256(), second.projection_sha256());
    assert_eq!(
        truth_table_counts(&SqliteStore::open_read_only(&database).await.unwrap()).await,
        [0; 5]
    );

    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn temporal_truth_projection_s4_source_time_authority_survives_later_target_upgrade() {
    let (directory, database, store) = fresh_store("s4-source-time").await;
    seed_s4_source_time_relationship(&store).await;
    append_s4_target_upgrade(&store).await;
    drop(store);

    let result = temporal_truth_project_read_only_synthetic_v1(
        synthetic_projection_permit_v1(),
        &database,
        projection_request(250, 250),
    )
    .await
    .expect("source-time authority basis must survive later target upgrade");
    let bases: Vec<_> = result.authority_bases().collect();
    assert_eq!(bases.len(), 1);
    assert_eq!(bases[0].source_evidence_id(), "s4-source-v1");
    assert_eq!(bases[0].source_recorded_at(), 100);
    assert_eq!(bases[0].target_evidence_id(), "s4-target-v1");
    assert_eq!(bases[0].target_recorded_at(), 90);
    assert_eq!(bases[0].target_revision_seq(), 1);
    assert_eq!(bases[0].target_truth_tier(), TemporalTruthTierV1::Observed);

    let claim = result.claims().next().expect("projected S4 claim");
    assert_eq!(claim.truth_state(), TemporalTruthStateV1::Supported);
    assert_eq!(claim.truth_tier(), Some(TemporalTruthTierV1::Verified));
    assert_eq!(claim.evidence_ids(), ["s4-source-v1"]);
    let target_disposition = claim
        .evidence_dispositions()
        .find(|disposition| disposition.evidence_id() == "s4-target-v2")
        .expect("latest target disposition");
    let suppression = target_disposition
        .reasons()
        .find(|reason| reason.suppression_kind().is_some())
        .expect("auditable suppression reason");
    assert_eq!(
        suppression.suppression_kind(),
        Some(TemporalTruthSuppressionKindV1::Supersedes)
    );
    assert_eq!(suppression.source_evidence_id(), Some("s4-source-v1"));
    assert_eq!(suppression.effective_from(), Some(110));

    let source_provenance = result
        .evidence_provenance()
        .find(|entry| entry.evidence_id() == "s4-source-v1")
        .expect("source provenance entry");
    let bindings: Vec<_> = source_provenance
        .source_bindings()
        .map(|binding| {
            (
                binding.source_key().to_string(),
                binding.provenance_sha256().to_string(),
            )
        })
        .collect();
    assert_eq!(bindings.len(), 2);
    assert_eq!(bindings[0].0, "source:source");
    assert_eq!(bindings[1].0, "source:supplemental");
    assert!(bindings.iter().all(|(_, digest)| digest.len() == 64));

    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn temporal_truth_projection_s4_post_cutoff_is_bound_but_not_projected() {
    let (directory, database, store) = fresh_store("s4-post-cutoff").await;
    seed_s4_source_time_relationship(&store).await;
    let baseline = temporal_truth_project_read_only_synthetic_v1(
        synthetic_projection_permit_v1(),
        &database,
        projection_request(120, 120),
    )
    .await
    .expect("baseline cutoff projection");
    append_s4_target_upgrade(&store).await;
    let after = temporal_truth_project_read_only_synthetic_v1(
        synthetic_projection_permit_v1(),
        &database,
        projection_request(120, 120),
    )
    .await
    .expect("projection with retained post-cutoff revision");

    assert_ne!(
        baseline.snapshot_payload_sha256(),
        after.snapshot_payload_sha256()
    );
    assert_ne!(
        baseline.prepared_input_sha256(),
        after.prepared_input_sha256()
    );
    assert_eq!(baseline.projection_sha256(), after.projection_sha256());
    assert_eq!(baseline.snapshot_counts().evidence_revisions(), 2);
    assert_eq!(after.snapshot_counts().evidence_revisions(), 3);
    assert_eq!(
        baseline.claims().next().unwrap().values(),
        after.claims().next().unwrap().values()
    );

    drop(store);
    remove_test_directory(&directory).await;
}

#[tokio::test]
async fn temporal_truth_projection_s4_tombstoned_target_prunes_but_governed_source_rejects() {
    let token = synthetic_write_token();
    let (pruned_directory, pruned_database, pruned_store) = fresh_store("s4-tombstone-prune").await;
    seed_s4_source_time_relationship(&pruned_store).await;
    let tombstone = pruned_store
        .truth_evidence_tombstone_lineage_synthetic(
            &token,
            NewLineageTombstone {
                tombstone_id: "s4-target-tombstone-v1".to_string(),
                lineage_id: "s4-target".to_string(),
                tombstoned_at: 130,
            },
        )
        .await
        .expect("tombstone inbound relationship target");
    assert!(!tombstone.had_outgoing_governance);
    drop(pruned_store);
    let pruned = temporal_truth_project_read_only_synthetic_v1(
        synthetic_projection_permit_v1(),
        &pruned_database,
        projection_request(200, 200),
    )
    .await
    .expect("content-free target tombstone is prunable");
    assert_eq!(pruned.pruned_inbound_relationships(), 1);
    assert_eq!(pruned.authority_bases().count(), 0);
    assert!(pruned
        .evidence_provenance()
        .all(|entry| entry.evidence_id() != "s4-target-v1"));
    assert_eq!(
        pruned.claims().next().unwrap().evidence_ids(),
        ["s4-source-v1"]
    );
    remove_test_directory(&pruned_directory).await;

    let (blocked_directory, blocked_database, blocked_store) =
        fresh_store("s4-tombstone-governed").await;
    seed_s4_source_time_relationship(&blocked_store).await;
    let tombstone = blocked_store
        .truth_evidence_tombstone_lineage_synthetic(
            &token,
            NewLineageTombstone {
                tombstone_id: "s4-source-tombstone-v1".to_string(),
                lineage_id: "s4-source".to_string(),
                tombstoned_at: 130,
            },
        )
        .await
        .expect("tombstone governed relationship source");
    assert!(tombstone.had_outgoing_governance);
    drop(blocked_store);
    let error = temporal_truth_project_read_only_synthetic_v1(
        synthetic_projection_permit_v1(),
        &blocked_database,
        projection_request(200, 200),
    )
    .await
    .expect_err("governed tombstone source must terminate projection");
    assert_eq!(
        error.code(),
        "truth_projection_v1_governed_tombstone_source"
    );
    remove_test_directory(&blocked_directory).await;
}

#[tokio::test]
async fn temporal_truth_projection_s4_required_claim_order_is_canonical_and_missing_path_is_not_created(
) {
    let (directory, database, store) = fresh_store("s4-request-canonical").await;
    drop(store);
    let left = TemporalTruthRequiredClaimV1::try_new("subject:a", "claim.status").unwrap();
    let right = TemporalTruthRequiredClaimV1::try_new("subject:b", "claim.status").unwrap();
    let first_request = TemporalTruthProjectionRequestV1::try_new(
        0,
        0,
        vec![right.clone(), left.clone()],
        projection_limits(),
    )
    .unwrap();
    let second_request =
        TemporalTruthProjectionRequestV1::try_new(0, 0, vec![left, right], projection_limits())
            .unwrap();
    let first = temporal_truth_project_read_only_synthetic_v1(
        synthetic_projection_permit_v1(),
        &database,
        first_request,
    )
    .await
    .unwrap();
    let second = temporal_truth_project_read_only_synthetic_v1(
        synthetic_projection_permit_v1(),
        &database,
        second_request,
    )
    .await
    .unwrap();
    assert_eq!(
        first.prepared_input_sha256(),
        second.prepared_input_sha256()
    );
    assert_eq!(first.projection_sha256(), second.projection_sha256());
    remove_test_directory(&directory).await;

    let (missing_directory, missing_database) = test_path("s4-missing-read-only");
    let error = temporal_truth_project_read_only_synthetic_v1(
        synthetic_projection_permit_v1(),
        &missing_database,
        projection_request(0, 0),
    )
    .await
    .expect_err("read-only projection must not create a missing database");
    assert_eq!(error.code(), "truth_projection_v1_open_read_only");
    assert!(!missing_database.exists());
    assert!(!missing_directory.exists());
}

#[tokio::test]
async fn temporal_truth_projection_s4_identity_drift_rejects_without_migration() {
    let (directory, database, store) = fresh_store("s4-identity-drift").await;
    rewind_empty_truth_schema_to_v42(&store, false).await;
    drop(store);
    let error = temporal_truth_project_read_only_synthetic_v1(
        synthetic_projection_permit_v1(),
        &database,
        projection_request(0, 0),
    )
    .await
    .expect_err("read-only v1 must reject v42 rather than migrating it");
    assert_eq!(error.code(), "truth_projection_v1_sqlite");
    let connection = tokio_rusqlite::Connection::open_with_flags(
        &database,
        rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY,
    )
    .await
    .expect("reopen drifted database read-only");
    let version: String = connection
        .call(|connection| -> RusqliteResult<String> {
            connection.query_row(
                "SELECT value FROM schema_meta WHERE key='version'",
                [],
                |row| row.get(0),
            )
        })
        .await
        .expect("read unchanged schema version");
    assert_eq!(version, "42");
    remove_test_directory(&directory).await;
}

#[test]
fn temporal_truth_projection_s4_request_rejects_duplicate_claims_and_invalid_window() {
    let claim = TemporalTruthRequiredClaimV1::try_new("subject:a", "claim.status").unwrap();
    let duplicate = TemporalTruthProjectionRequestV1::try_new(
        0,
        0,
        vec![claim.clone(), claim],
        projection_limits(),
    )
    .expect_err("duplicate required claim must reject");
    assert_eq!(
        duplicate.code(),
        "truth_projection_v1_duplicate_required_claim"
    );
    let invalid = TemporalTruthProjectionRequestV1::try_new(2, 1, Vec::new(), projection_limits())
        .expect_err("as_of after cutoff must reject");
    assert_eq!(invalid.code(), "truth_projection_v1_invalid_window");
}
