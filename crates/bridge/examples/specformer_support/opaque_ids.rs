#![allow(dead_code)]

use anyhow::Context;
use sha2::{Digest, Sha256};

pub const OPAQUE_MEMORY_ID_PREFIX: &str = "abmkey:sha256:";
const OPAQUE_MEMORY_ID_DOMAIN: &[u8] = b"agent-bridge/specformer/memory-key/v1\0";

pub fn opaque_memory_id(key: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(OPAQUE_MEMORY_ID_DOMAIN);
    hasher.update(key.as_bytes());
    let digest = hasher.finalize();
    format!("{OPAQUE_MEMORY_ID_PREFIX}{digest:x}")
}

pub fn is_opaque_memory_id(value: &str) -> bool {
    let Some(digest) = value.strip_prefix(OPAQUE_MEMORY_ID_PREFIX) else {
        return false;
    };
    digest.len() == 64
        && digest
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

pub fn corpus_query(key: &str, content: &str) -> String {
    format!(
        "Which active memory should be recalled with `{key}`? {}",
        title_of(content)
    )
}

pub fn redact_memory_keys(text: &str, keys: &[String]) -> String {
    let mut keys = keys.iter().map(String::as_str).collect::<Vec<_>>();
    keys.sort_by_key(|key| std::cmp::Reverse(key.len()));
    keys.dedup();

    let mut redacted = text.to_string();
    for key in keys {
        if redacted.contains(key) {
            let token = format!("{{{{{}}}}}", opaque_memory_id(key));
            redacted = redacted.replace(key, &token);
        }
    }
    redacted
}

pub fn opaque_ids_in_template(template: &str) -> anyhow::Result<Vec<String>> {
    let marker = format!("{{{{{OPAQUE_MEMORY_ID_PREFIX}");
    let id_len = OPAQUE_MEMORY_ID_PREFIX.len() + 64;
    let mut cursor = 0;
    let mut ids = Vec::new();

    while let Some(relative_start) = template[cursor..].find(&marker) {
        let start = cursor + relative_start + 2;
        let end = start + id_len;
        let id = template
            .get(start..end)
            .context("truncated opaque id in query template")?;
        anyhow::ensure!(
            is_opaque_memory_id(id) && template.get(end..end + 2) == Some("}}"),
            "malformed opaque id token in query template"
        );
        ids.push(id.to_string());
        cursor = end + 2;
    }
    ids.sort();
    ids.dedup();
    Ok(ids)
}

pub fn title_of(content: &str) -> String {
    content
        .lines()
        .map(|line| {
            line.trim_start_matches(|c| c == '#' || c == '*' || c == '-' || c == ' ')
                .trim()
        })
        .find(|line| line.chars().count() >= 8)
        .unwrap_or("")
        .chars()
        .take(140)
        .collect()
}
