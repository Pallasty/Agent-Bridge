//! Default-off Slice B episode-observation storage.
//!
//! This is deliberately a private `SqliteStore` detail. It owns no producer,
//! configuration loader, public API, or retrieval path. In normal production
//! code only the disabled runtime gate exists; synthetic tests are the sole
//! place allowed to construct an enabled gate.

use super::{RusqliteResult, SqliteStore};
use crate::episode_observation_slice_a::{
    EpisodeObservationEvent, EpisodeObservationKind, EpisodeObservationSourceKind,
};
use tokio_rusqlite::{params, rusqlite};

pub(super) const SCHEMA_VERSION: &str = "44";

const TABLE: &str = "episode_observation_events";
const INDEX: &str = "idx_episode_observation_events_episode_id";

const SCHEMA_V44_EPISODE_OBSERVATION: &str = r#"
CREATE TABLE episode_observation_events (
    event_id         TEXT    PRIMARY KEY,
    episode_id       TEXT    NOT NULL,
    event_type       TEXT    NOT NULL,
    source_kind      TEXT    NOT NULL,
    producer_run_id  TEXT    NOT NULL,
    item_ref         TEXT,
    episode_position INTEGER,
    item_count       INTEGER,
    payload_sha256   TEXT    NOT NULL,
    observed_at      INTEGER NOT NULL,
    CHECK (length(CAST(event_id AS BLOB)) >= 1),
    CHECK (length(CAST(episode_id AS BLOB)) >= 1),
    CHECK (length(CAST(producer_run_id AS BLOB)) >= 1),
    CHECK (event_type IN ('episode.open', 'episode.item', 'episode.close')),
    CHECK (source_kind IN ('session', 'curation_batch', 'owner_bundle')),
    CHECK (item_ref IS NULL OR length(CAST(item_ref AS BLOB)) >= 1),
    CHECK (episode_position IS NULL OR (typeof(episode_position) = 'integer' AND episode_position >= 0)),
    CHECK (item_count IS NULL OR (typeof(item_count) = 'integer' AND item_count >= 0)),
    CHECK (typeof(observed_at) = 'integer' AND observed_at >= 0),
    CHECK (length(payload_sha256) = 64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'),
    CHECK (
        (event_type = 'episode.open' AND item_ref IS NULL AND episode_position IS NULL AND item_count IS NULL)
        OR (event_type = 'episode.item' AND item_ref IS NOT NULL AND episode_position IS NOT NULL AND item_count IS NULL)
        OR (event_type = 'episode.close' AND item_ref IS NULL AND episode_position IS NULL AND item_count IS NOT NULL)
    )
);
CREATE INDEX idx_episode_observation_events_episode_id
    ON episode_observation_events(episode_id);
"#;

#[derive(Debug, PartialEq, Eq)]
enum EpisodeObservationAppendDisposition {
    Disabled,
    Appended,
}

#[derive(Debug, PartialEq, Eq)]
enum EpisodeObservationProjectionDisposition {
    Disabled,
    AbsentOrIncomplete,
    Finalized(EpisodeObservationFinalizedProjection),
}

#[derive(Debug, PartialEq, Eq)]
struct EpisodeObservationFinalizedProjection {
    episode_id: String,
    source_kind: String,
    producer_run_id: String,
    item_refs: Vec<String>,
}

#[derive(Debug, PartialEq, Eq)]
enum EpisodeObservationStoreError {
    InvalidEvent,
    InvalidPayloadDigest,
    Database,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum EpisodeObservationRuntimeGate {
    Disabled,
    #[cfg(test)]
    SyntheticTestOnly,
}

impl EpisodeObservationRuntimeGate {
    fn permits_io(self) -> bool {
        #[cfg(test)]
        {
            return self == Self::SyntheticTestOnly;
        }
        #[cfg(not(test))]
        {
            let _ = self;
            false
        }
    }
}

fn map_store_error(error: tokio_rusqlite::Error) -> EpisodeObservationStoreError {
    let _ = error;
    EpisodeObservationStoreError::Database
}

fn source_kind_text(source_kind: &EpisodeObservationSourceKind) -> &'static str {
    match source_kind {
        EpisodeObservationSourceKind::Session => "session",
        EpisodeObservationSourceKind::CurationBatch => "curation_batch",
        EpisodeObservationSourceKind::OwnerBundle => "owner_bundle",
    }
}

fn payload_sha256_is_valid(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn event_shape<'a>(
    event: &EpisodeObservationEvent<'a>,
) -> std::result::Result<
    (&'static str, Option<&'a str>, Option<i64>, Option<i64>),
    EpisodeObservationStoreError,
> {
    if event.event_id.is_empty() || event.episode_id.is_empty() || event.producer_run_id.is_empty()
    {
        return Err(EpisodeObservationStoreError::InvalidEvent);
    }
    match &event.kind {
        EpisodeObservationKind::Open => Ok(("episode.open", None, None, None)),
        EpisodeObservationKind::Item {
            item_ref,
            episode_position,
        } if !item_ref.is_empty() => Ok((
            "episode.item",
            Some(*item_ref),
            Some(i64::from(*episode_position)),
            None,
        )),
        EpisodeObservationKind::Item { .. } => Err(EpisodeObservationStoreError::InvalidEvent),
        EpisodeObservationKind::Close { item_count } => {
            Ok(("episode.close", None, None, Some(i64::from(*item_count))))
        }
    }
}

fn normalize_sql(sql: &str) -> String {
    sql.trim()
        .trim_end_matches(';')
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn verify_v44(c: &rusqlite::Connection) -> RusqliteResult<()> {
    let version: String = c.query_row(
        "SELECT value FROM main.schema_meta WHERE key='version'",
        [],
        |row| row.get(0),
    )?;
    if version != SCHEMA_VERSION {
        return Err(rusqlite::Error::InvalidQuery);
    }
    let table_sql: String = c.query_row(
        "SELECT sql FROM main.sqlite_master WHERE type='table' AND name=?1",
        params![TABLE],
        |row| row.get(0),
    )?;
    let index_sql: String = c.query_row(
        "SELECT sql FROM main.sqlite_master WHERE type='index' AND name=?1",
        params![INDEX],
        |row| row.get(0),
    )?;
    let expected = SCHEMA_V44_EPISODE_OBSERVATION
        .split("CREATE INDEX")
        .collect::<Vec<_>>();
    if expected.len() != 2
        || normalize_sql(&table_sql) != normalize_sql(expected[0])
        || normalize_sql(&index_sql) != normalize_sql(&format!("CREATE INDEX{}", expected[1]))
    {
        return Err(rusqlite::Error::InvalidQuery);
    }
    let fk_count: i64 = c.query_row(
        "SELECT COUNT(*) FROM pragma_foreign_key_list('episode_observation_events')",
        [],
        |row| row.get(0),
    )?;
    let trigger_count: i64 = c.query_row(
        "SELECT COUNT(*) FROM main.sqlite_master WHERE type='trigger' AND tbl_name=?1",
        params![TABLE],
        |row| row.get(0),
    )?;
    if fk_count != 0 || trigger_count != 0 {
        return Err(rusqlite::Error::InvalidQuery);
    }
    Ok(())
}

pub(super) fn migrate_or_verify(c: &mut rusqlite::Connection) -> RusqliteResult<()> {
    let tx = c.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
    let version: String = tx.query_row(
        "SELECT value FROM main.schema_meta WHERE key='version'",
        [],
        |row| row.get(0),
    )?;
    match version.as_str() {
        "43" => {
            let collisions: i64 = tx.query_row(
                "SELECT COUNT(*) FROM main.sqlite_master WHERE name IN (?1, ?2)",
                params![TABLE, INDEX],
                |row| row.get(0),
            )?;
            if collisions != 0 {
                return Err(rusqlite::Error::InvalidQuery);
            }
            tx.execute_batch(SCHEMA_V44_EPISODE_OBSERVATION)?;
            let changed = tx.execute(
                "UPDATE main.schema_meta SET value=?1 WHERE key='version' AND value='43'",
                params![SCHEMA_VERSION],
            )?;
            if changed != 1 {
                return Err(rusqlite::Error::InvalidQuery);
            }
            verify_v44(&tx)?;
        }
        SCHEMA_VERSION => verify_v44(&tx)?,
        _ => return Err(rusqlite::Error::InvalidQuery),
    }
    tx.commit()?;
    Ok(())
}

impl SqliteStore {
    async fn append_episode_observation_event_inert(
        &self,
        gate: EpisodeObservationRuntimeGate,
        event: &EpisodeObservationEvent<'_>,
        payload_sha256: &str,
        observed_at: i64,
    ) -> std::result::Result<EpisodeObservationAppendDisposition, EpisodeObservationStoreError>
    {
        if !gate.permits_io() {
            return Ok(EpisodeObservationAppendDisposition::Disabled);
        }
        if observed_at < 0 {
            return Err(EpisodeObservationStoreError::InvalidEvent);
        }
        if !payload_sha256_is_valid(payload_sha256) {
            return Err(EpisodeObservationStoreError::InvalidPayloadDigest);
        }
        let (event_type, item_ref, episode_position, item_count) = event_shape(event)?;
        let event_id = event.event_id.to_owned();
        let episode_id = event.episode_id.to_owned();
        let producer_run_id = event.producer_run_id.to_owned();
        let source_kind = source_kind_text(&event.source_kind).to_owned();
        let payload_sha256 = payload_sha256.to_owned();
        let item_ref = item_ref.map(str::to_owned);
        self.conn.call(move |c| {
            c.execute(
                "INSERT INTO episode_observation_events \
                 (event_id, episode_id, event_type, source_kind, producer_run_id, item_ref, episode_position, item_count, payload_sha256, observed_at) \
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
                params![event_id, episode_id, event_type, source_kind, producer_run_id, item_ref, episode_position, item_count, payload_sha256, observed_at],
            )?;
            Ok(())
        }).await.map_err(map_store_error)?;
        Ok(EpisodeObservationAppendDisposition::Appended)
    }

    async fn read_finalized_episode_projection_inert(
        &self,
        gate: EpisodeObservationRuntimeGate,
        episode_id: &str,
    ) -> std::result::Result<EpisodeObservationProjectionDisposition, EpisodeObservationStoreError>
    {
        if !gate.permits_io() {
            return Ok(EpisodeObservationProjectionDisposition::Disabled);
        }
        if episode_id.is_empty() {
            return Ok(EpisodeObservationProjectionDisposition::AbsentOrIncomplete);
        }
        let episode_id = episode_id.to_owned();
        self.conn.call(move |c| {
            let mut statement = c.prepare(
                "SELECT event_type, source_kind, producer_run_id, item_ref, episode_position, item_count \
                 FROM episode_observation_events WHERE episode_id=?1 ORDER BY rowid ASC",
            )?;
            let rows = statement.query_map(params![episode_id.clone()], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?, row.get::<_, String>(2)?, row.get::<_, Option<String>>(3)?, row.get::<_, Option<i64>>(4)?, row.get::<_, Option<i64>>(5)?))
            })?.collect::<std::result::Result<Vec<_>, _>>()?;
            if rows.is_empty() { return Ok(EpisodeObservationProjectionDisposition::AbsentOrIncomplete); }
            let (open_type, source_kind, producer_run_id, open_ref, open_position, open_count) = &rows[0];
            if open_type != "episode.open" || open_ref.is_some() || open_position.is_some() || open_count.is_some() { return Ok(EpisodeObservationProjectionDisposition::AbsentOrIncomplete); }
            let mut item_refs = Vec::new();
            for (expected_position, row) in rows[1..].iter().take(rows.len().saturating_sub(2)).enumerate() {
                let (event_type, row_source, row_run, item_ref, position, count) = row;
                if event_type != "episode.item" || row_source != source_kind || row_run != producer_run_id || item_ref.is_none() || position != &Some(expected_position as i64) || count.is_some() { return Ok(EpisodeObservationProjectionDisposition::AbsentOrIncomplete); }
                item_refs.push(item_ref.clone().expect("checked"));
            }
            let Some((close_type, close_source, close_run, close_ref, close_position, close_count)) = rows.last() else { return Ok(EpisodeObservationProjectionDisposition::AbsentOrIncomplete); };
            if rows.len() < 2 || close_type != "episode.close" || close_source != source_kind || close_run != producer_run_id || close_ref.is_some() || close_position.is_some() || close_count != &Some(item_refs.len() as i64) { return Ok(EpisodeObservationProjectionDisposition::AbsentOrIncomplete); }
            Ok(EpisodeObservationProjectionDisposition::Finalized(EpisodeObservationFinalizedProjection { episode_id, source_kind: source_kind.clone(), producer_run_id: producer_run_id.clone(), item_refs }))
        }).await.map_err(map_store_error)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::episode_observation_slice_a::{
        EpisodeObservationKind, EpisodeObservationSourceKind,
    };

    fn digest() -> &'static str {
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }

    async fn version_and_object_counts(store: &SqliteStore) -> (String, i64, i64) {
        store
            .conn
            .call(|connection| -> RusqliteResult<(String, i64, i64)> {
                Ok((
                    connection.query_row(
                        "SELECT value FROM schema_meta WHERE key='version'",
                        [],
                        |row| row.get(0),
                    )?,
                    connection.query_row(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?1",
                        params![TABLE],
                        |row| row.get(0),
                    )?,
                    connection.query_row(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name=?1",
                        params![INDEX],
                        |row| row.get(0),
                    )?,
                ))
            })
            .await
            .expect("inspect schema")
    }

    #[tokio::test]
    async fn fresh_disposable_database_gets_v44_relation_once() {
        let dir = tempfile::tempdir().expect("temp dir");
        let store = SqliteStore::open(&dir.path().join("state.db"))
            .await
            .expect("open");
        assert_eq!(version_and_object_counts(&store).await, ("44".into(), 1, 1));
    }

    #[tokio::test]
    async fn v43_disposable_database_upgrades_to_v44() {
        let dir = tempfile::tempdir().expect("temp dir");
        let store = SqliteStore::open(&dir.path().join("state.db"))
            .await
            .expect("open");
        store
            .conn
            .call(|connection| -> RusqliteResult<()> {
                connection.execute_batch(
                    "DROP INDEX idx_episode_observation_events_episode_id; \
                     DROP TABLE episode_observation_events; \
                     UPDATE schema_meta SET value='43' WHERE key='version';",
                )?;
                Ok(())
            })
            .await
            .expect("rewind disposable database to v43");
        store
            .conn
            .call(migrate_or_verify)
            .await
            .expect("upgrade v43 to v44");
        assert_eq!(version_and_object_counts(&store).await, ("44".into(), 1, 1));
    }

    #[tokio::test]
    async fn collision_rolls_back_without_cursor_advance() {
        let dir = tempfile::tempdir().expect("temp dir");
        let store = SqliteStore::open(&dir.path().join("state.db"))
            .await
            .expect("open");
        store
            .conn
            .call(|connection| -> RusqliteResult<()> {
                connection.execute_batch(
                    "DROP INDEX idx_episode_observation_events_episode_id; \
                     DROP TABLE episode_observation_events; \
                     UPDATE schema_meta SET value='43' WHERE key='version'; \
                     CREATE TABLE episode_observation_events (spoof INTEGER);",
                )?;
                Ok(())
            })
            .await
            .expect("seed disposable collision");
        assert!(store.conn.call(migrate_or_verify).await.is_err());
        assert_eq!(version_and_object_counts(&store).await, ("43".into(), 1, 0));
    }

    #[tokio::test]
    async fn default_runtime_gate_never_writes() {
        let dir = tempfile::tempdir().expect("temp dir");
        let store = SqliteStore::open(&dir.path().join("state.db"))
            .await
            .expect("open");
        let event = EpisodeObservationEvent {
            event_id: "e1",
            episode_id: "ep",
            producer_run_id: "run",
            source_kind: EpisodeObservationSourceKind::CurationBatch,
            kind: EpisodeObservationKind::Open,
        };
        assert_eq!(
            store
                .append_episode_observation_event_inert(
                    EpisodeObservationRuntimeGate::Disabled,
                    &event,
                    digest(),
                    1
                )
                .await,
            Ok(EpisodeObservationAppendDisposition::Disabled)
        );
    }

    #[tokio::test]
    async fn synthetic_projection_requires_exact_open_items_close_shape() {
        let dir = tempfile::tempdir().expect("temp dir");
        let store = SqliteStore::open(&dir.path().join("state.db"))
            .await
            .expect("open");
        let gate = EpisodeObservationRuntimeGate::SyntheticTestOnly;
        for event in [
            EpisodeObservationEvent {
                event_id: "open",
                episode_id: "ep",
                producer_run_id: "run",
                source_kind: EpisodeObservationSourceKind::CurationBatch,
                kind: EpisodeObservationKind::Open,
            },
            EpisodeObservationEvent {
                event_id: "item",
                episode_id: "ep",
                producer_run_id: "run",
                source_kind: EpisodeObservationSourceKind::CurationBatch,
                kind: EpisodeObservationKind::Item {
                    item_ref: "epr_v1_e_a",
                    episode_position: 0,
                },
            },
            EpisodeObservationEvent {
                event_id: "close",
                episode_id: "ep",
                producer_run_id: "run",
                source_kind: EpisodeObservationSourceKind::CurationBatch,
                kind: EpisodeObservationKind::Close { item_count: 1 },
            },
        ] {
            assert_eq!(
                store
                    .append_episode_observation_event_inert(gate, &event, digest(), 1)
                    .await,
                Ok(EpisodeObservationAppendDisposition::Appended)
            );
        }
        let projection = store
            .read_finalized_episode_projection_inert(gate, "ep")
            .await
            .expect("projection");
        assert_eq!(
            projection,
            EpisodeObservationProjectionDisposition::Finalized(
                EpisodeObservationFinalizedProjection {
                    episode_id: "ep".into(),
                    source_kind: "curation_batch".into(),
                    producer_run_id: "run".into(),
                    item_refs: vec!["epr_v1_e_a".into()]
                }
            )
        );
    }
}
