//! Current-use projection for digest reads. No mutation, refresh or replacement
//! following. This guards one MCP entry, not all memory retrieval surfaces.
use ab_store::{MemoryPeekResult, MemoryRecord, StateStore};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashSet;

use crate::dream_digest::{source_revision_hash, EXCLUDED_MANIFEST_KINDS};

pub(crate) const BINDING_TAG: &str = "digest_sources_v1:";

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Bindings {
    schema: String,
    sources: Vec<Source>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Source {
    key: String,
    sha256: String,
}

pub(crate) struct DigestRead {
    pub record: Option<MemoryRecord>,
    pub validity: Value,
}

fn withheld(status: &str, reason: &str) -> DigestRead {
    DigestRead {
        record: None,
        validity: json!({"status": status, "reason": reason,
            "eligible_for_current_use": false, "source_revision_verified": false,
            "answer_validated": false}),
    }
}

fn bindings(record: &MemoryRecord) -> Option<Bindings> {
    let tags: Vec<_> = record
        .tags
        .iter()
        .filter_map(|t| t.strip_prefix(BINDING_TAG))
        .collect();
    if tags.len() != 1 || tags[0].len() > 64 * 1024 {
        return None;
    }
    let binding: Bindings = serde_json::from_str(tags[0]).ok()?;
    if binding.schema != "ab.digest.sources.v1"
        || binding.sources.is_empty()
        || binding.sources.len() > 12
    {
        return None;
    }
    let mut keys = HashSet::new();
    for source in &binding.sources {
        if source.key.trim().is_empty()
            || source.key.len() > 4096
            || source.key == record.key
            || !keys.insert(source.key.as_str())
            || source.sha256.len() != 64
            || !source
                .sha256
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        {
            return None;
        }
    }
    let cited: HashSet<_> = record.related_keys.iter().map(String::as_str).collect();
    if cited.is_empty() || cited.len() != record.related_keys.len() || !cited.is_subset(&keys) {
        return None;
    }
    Some(binding)
}

fn active(record: &MemoryRecord) -> bool {
    record.status == "active" && record.superseded_by.is_none()
}

fn scope_compatible(source: &MemoryRecord, digest: &MemoryRecord) -> bool {
    source.scope.is_none()
        || source.scope.as_deref() == Some("global")
        || source.scope == digest.scope
}

pub(crate) async fn assess(store: &dyn StateStore, initial: &MemoryRecord) -> DigestRead {
    if !active(initial) {
        return withheld("needs_review", "digest_not_active");
    }
    let Some(binding) = bindings(initial) else {
        return withheld("unknown", "source_binding_missing_or_invalid");
    };
    let mut keys = vec![initial.key.clone()];
    keys.extend(binding.sources.iter().map(|s| s.key.clone()));
    let snapshot = match store.memory_peek_many(&keys).await {
        Ok(rows) if rows.len() == keys.len() => rows,
        _ => return withheld("unknown", "source_snapshot_unavailable"),
    };
    let mut rows = snapshot.into_iter();
    let digest = match rows.next() {
        Some(MemoryPeekResult::Present { record }) if record.key == initial.key => *record,
        Some(MemoryPeekResult::Missing | MemoryPeekResult::Tombstoned { .. }) => {
            return withheld("needs_review", "digest_withdrawn")
        }
        _ => return withheld("unknown", "source_snapshot_invalid"),
    };
    if source_revision_hash(&digest) != source_revision_hash(initial) {
        return withheld("unknown", "digest_changed_during_read");
    }
    for (source, row) in binding.sources.iter().zip(rows) {
        let record = match row {
            MemoryPeekResult::Present { record } if record.key == source.key => record,
            MemoryPeekResult::Missing | MemoryPeekResult::Tombstoned { .. } => {
                return withheld("needs_review", "source_missing_or_withdrawn")
            }
            _ => return withheld("unknown", "source_snapshot_invalid"),
        };
        if !active(&record) {
            return withheld("needs_review", "source_not_active");
        }
        if EXCLUDED_MANIFEST_KINDS.contains(&record.kind.as_str()) {
            return withheld("unknown", "source_not_primary");
        }
        if !scope_compatible(&record, &digest) {
            return withheld("unknown", "source_scope_incompatible");
        }
        if record.created_at <= 0 || record.updated_at <= 0 {
            return withheld("unknown", "source_time_unknown");
        }
        if source_revision_hash(&record) != source.sha256 {
            return withheld("needs_review", "source_revision_changed");
        }
    }
    DigestRead {
        record: Some(digest),
        validity: json!({"status": "current", "reason": "bound_sources_match_read_snapshot",
            "eligible_for_current_use": true, "source_revision_verified": true,
            "answer_validated": false}),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_mcp::{ContentBlock, McpTool, ToolContext};
    use ab_store::SqliteStore;
    use std::sync::Arc;
    use tokio_rusqlite::rusqlite::{params, Connection};

    struct Fixture {
        dir: tempfile::TempDir,
        store: Arc<SqliteStore>,
        digest: MemoryRecord,
    }

    fn record(key: &str, kind: &str, content: &str) -> MemoryRecord {
        serde_json::from_value(json!({"key": key, "kind": kind, "content": content,
            "tags": [], "related_keys": [], "scope": null, "created_at": 10,
            "updated_at": 10, "last_accessed_at": 0, "access_count": 0,
            "status": "active", "superseded_by": null, "trigger_pattern": null}))
        .unwrap()
    }

    fn insert(conn: &Connection, r: &MemoryRecord) {
        conn.execute(
            "INSERT INTO memories VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14)",
            params![
                r.key,
                r.kind,
                r.content,
                serde_json::to_string(&r.tags).unwrap(),
                serde_json::to_string(&r.related_keys).unwrap(),
                r.scope,
                r.created_at,
                r.updated_at,
                r.last_accessed_at,
                r.access_count,
                r.importance,
                r.status,
                r.trigger_pattern,
                r.superseded_by
            ],
        )
        .unwrap();
    }

    async fn fixture(source_scope: Option<&str>, digest_scope: Option<&str>) -> Fixture {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("state.db");
        let conn = Connection::open(&path).unwrap();
        conn.execute_batch(
            "CREATE TABLE memories (key TEXT PRIMARY KEY,kind TEXT,content TEXT,
            tags TEXT,related_keys TEXT,scope TEXT,created_at INTEGER,updated_at INTEGER,
            last_accessed_at INTEGER,access_count INTEGER,importance REAL,status TEXT,
            trigger_pattern TEXT,superseded_by TEXT);",
        )
        .unwrap();
        let mut source = record("source", "fact", "original source evidence");
        source.scope = source_scope.map(str::to_string);
        let mut digest = record("digest", "digest", "retained digest conclusion");
        digest.scope = digest_scope.map(str::to_string);
        digest.related_keys = vec![source.key.clone()];
        digest.tags = vec![format!(
            "{BINDING_TAG}{}",
            json!({"schema":"ab.digest.sources.v1",
            "sources":[{"key":source.key,"sha256":source_revision_hash(&source)}]})
        )];
        insert(&conn, &source);
        insert(&conn, &digest);
        drop(conn);
        let store = Arc::new(SqliteStore::open_read_only(&path).await.unwrap());
        Fixture { dir, store, digest }
    }

    impl Fixture {
        fn sql(&self, sql: &str) {
            Connection::open(self.dir.path().join("state.db"))
                .unwrap()
                .execute_batch(sql)
                .unwrap();
        }
        async fn get(&self) -> Value {
            let hub = crate::Hub::builder().store(self.store.clone()).build();
            let result = crate::mcp_tools::MemoryGetTool::new(hub)
                .execute(json!({"key":"digest"}), &ToolContext::default())
                .await
                .unwrap();
            assert!(!result.is_error);
            let ContentBlock::Text { text } = &result.content[0] else {
                panic!("expected text")
            };
            serde_json::from_str(text).unwrap()
        }
    }

    #[tokio::test]
    async fn digest_read_mcp_valid_then_changed_source_without_writes() {
        let f = fixture(None, None).await;
        let path = f.dir.path().join("state.db");
        let before = std::fs::read(&path).unwrap();
        let valid = f.get().await;
        assert_eq!(valid["content"], f.digest.content);
        assert_eq!(valid["source_validity"]["status"], "current");
        assert_eq!(valid["source_validity"]["answer_validated"], false);
        assert_eq!(std::fs::read(&path).unwrap(), before);
        f.sql("UPDATE memories SET content='same-second change' WHERE key='source'");
        let before = std::fs::read(&path).unwrap();
        let stale = f.get().await;
        assert!(stale["content"].is_null());
        assert_eq!(stale["source_validity"]["status"], "needs_review");
        assert_eq!(stale["source_validity"]["eligible_for_current_use"], false);
        assert!(stale["proactive_hint"].is_null());
        assert_eq!(std::fs::read(&path).unwrap(), before);
        let MemoryPeekResult::Present { record } = f.store.memory_peek("digest").await.unwrap()
        else {
            panic!("history lost")
        };
        assert_eq!(record.content, f.digest.content);
        assert_eq!(record.access_count, 0);
    }

    #[tokio::test]
    async fn digest_read_withdrawal_and_replacement_never_redirect() {
        for sql in [
            "DELETE FROM memories WHERE key='source'",
            "UPDATE memories SET status='tombstoned' WHERE key='source'",
            "UPDATE memories SET status='archived' WHERE key='source'",
            "UPDATE memories SET status='conflict' WHERE key='source'",
            "UPDATE memories SET status='superseded',superseded_by='new' WHERE key='source'",
            "UPDATE memories SET superseded_by='new' WHERE key='source'",
        ] {
            let f = fixture(None, None).await;
            f.sql(sql);
            let got = f.get().await;
            assert!(got["content"].is_null(), "{sql}");
            assert_eq!(got["source_validity"]["status"], "needs_review", "{sql}");
            assert!(!got.to_string().contains("original source evidence"));
        }
    }

    #[tokio::test]
    async fn digest_read_unknown_binding_and_scope_are_withheld() {
        let f = fixture(Some("project:/private"), None).await;
        assert_eq!(
            f.get().await["source_validity"]["reason"],
            "source_scope_incompatible"
        );
        let matching = fixture(Some("project:/private"), Some("project:/private")).await;
        assert_eq!(matching.get().await["source_validity"]["status"], "current");
        let f = fixture(None, None).await;
        for tags in [
            vec![],
            vec!["digest_sources_v1:bad".to_string()],
            vec![f.digest.tags[0].clone(), f.digest.tags[0].clone()],
        ] {
            let mut initial = f.digest.clone();
            initial.tags = tags;
            let result = assess(f.store.as_ref(), &initial).await;
            assert!(result.record.is_none());
            assert_eq!(result.validity["status"], "unknown");
        }
    }

    #[tokio::test]
    async fn digest_read_digest_changed_or_withdrawn_between_reads() {
        let f = fixture(None, None).await;
        f.sql("UPDATE memories SET content='new digest' WHERE key='digest'");
        let got = assess(f.store.as_ref(), &f.digest).await;
        assert_eq!(got.validity["reason"], "digest_changed_during_read");
        assert!(got.record.is_none());
        f.sql("UPDATE memories SET status='tombstoned' WHERE key='digest'");
        let got = assess(f.store.as_ref(), &f.digest).await;
        assert_eq!(got.validity["reason"], "digest_withdrawn");
        assert!(got.record.is_none());
    }

    #[tokio::test]
    async fn digest_read_snapshot_limits_order_and_tombstone_redaction() {
        let f = fixture(None, None).await;
        for keys in [
            vec![],
            vec!["digest".into(), "digest".into()],
            (0..14).map(|i| i.to_string()).collect(),
            vec!["x".repeat(4097)],
        ] {
            assert!(f.store.memory_peek_many(&keys).await.is_err());
        }
        let thirteen: Vec<_> = (0..13).map(|i| i.to_string()).collect();
        assert_eq!(f.store.memory_peek_many(&thirteen).await.unwrap().len(), 13);
        f.sql("UPDATE memories SET status='tombstoned' WHERE key='source'");
        let rows = f
            .store
            .memory_peek_many(&["missing".into(), "source".into(), "digest".into()])
            .await
            .unwrap();
        assert!(matches!(rows[0], MemoryPeekResult::Missing));
        assert!(matches!(rows[1], MemoryPeekResult::Tombstoned { .. }));
        assert!(matches!(rows[2], MemoryPeekResult::Present { .. }));
        assert!(!serde_json::to_string(&rows)
            .unwrap()
            .contains("original source evidence"));
    }
}
