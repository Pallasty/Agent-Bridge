//! Instinct-specific value preparation. The root acquires time and owns writes.

use anyhow::Result;
use serde_json::Value;

pub(crate) struct PreparedMemoryRecord {
    key: String,
    kind: String,
    content: String,
    tags: Vec<String>,
    related_keys: Vec<String>,
    scope: Option<String>,
    importance: f64,
}

pub(crate) fn prepare_memory_record(value: &Value) -> Result<PreparedMemoryRecord> {
    let key = value
        .get("key")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| anyhow::anyhow!("memory_record.key is required"))?
        .to_string();
    let kind = value
        .get("kind")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| anyhow::anyhow!("memory_record.kind is required"))?
        .to_string();
    let content = value
        .get("content")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| anyhow::anyhow!("memory_record.content is required"))?
        .to_string();
    let tags = value
        .get("tags")
        .and_then(|v| v.as_array())
        .map(|items| {
            items
                .iter()
                .filter_map(|item| item.as_str())
                .map(str::trim)
                .filter(|item| !item.is_empty())
                .map(str::to_string)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let related_keys = value
        .get("related_keys")
        .and_then(|v| v.as_array())
        .map(|items| {
            items
                .iter()
                .filter_map(|item| item.as_str())
                .map(str::trim)
                .filter(|item| !item.is_empty())
                .map(str::to_string)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let scope = value
        .get("scope")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string);
    let importance = value
        .get("importance")
        .and_then(|v| v.as_f64())
        .unwrap_or(0.5)
        .clamp(0.0, 1.0);
    Ok(PreparedMemoryRecord {
        key,
        kind,
        content,
        tags,
        related_keys,
        scope,
        importance,
    })
}

impl PreparedMemoryRecord {
    pub(crate) fn into_record(self, now: i64) -> ab_store::MemoryRecord {
        let Self {
            key,
            kind,
            content,
            tags,
            related_keys,
            scope,
            importance,
        } = self;
        ab_store::MemoryRecord {
            key,
            kind,
            content,
            tags,
            related_keys,
            scope,
            created_at: now,
            updated_at: now,
            last_accessed_at: 0,
            access_count: 0,
            importance,
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        }
    }
}
