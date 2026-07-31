//! Pure, non-actuating contracts shared by the native `/story` path.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, HashSet},
    fs,
    path::Path,
};
use thiserror::Error;

const SUPPORTED_SOURCE_SUFFIXES: [&str; 3] = [".txt", ".md", ".markdown"];

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum StoryStart {
    FromStart,
    Chapter { chapter: u32 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StoryRequest {
    pub source_path: String,
    pub start: StoryStart,
    pub dry_run: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StorySource {
    pub source_id: String,
    pub kind: String,
    pub format: String,
    pub uri: String,
    pub sha256: String,
    pub version: String,
    pub encoding: String,
    pub byte_length: usize,
    pub char_length: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SourceSpan {
    pub source_id: String,
    pub line_start: usize,
    pub line_end: usize,
    pub char_start: usize,
    pub char_end: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StoryChapter {
    pub chapter_id: String,
    pub ordinal: u32,
    pub title: String,
    pub selected: bool,
    pub source_span: SourceSpan,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StorySelection {
    pub first_chapter: u32,
    pub selected_chapter_ids: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StorySourceIngest {
    pub source: StorySource,
    pub selection: StorySelection,
    pub chapters: Vec<StoryChapter>,
}

impl StoryRequest {
    pub fn validate(&self) -> Result<(), StoryContractError> {
        if self.source_path.trim().is_empty() {
            return Err(StoryContractError::InvalidRequest("source_path_empty"));
        }

        let lowercase_path = self.source_path.to_lowercase();
        if !SUPPORTED_SOURCE_SUFFIXES
            .iter()
            .any(|suffix| lowercase_path.ends_with(suffix))
        {
            return Err(StoryContractError::InvalidRequest(
                "story_source_suffix_unsupported",
            ));
        }
        if !self.dry_run {
            return Err(StoryContractError::InvalidRequest(
                "story_rust_contract_core_requires_dry_run",
            ));
        }
        if matches!(self.start, StoryStart::Chapter { chapter: 0 }) {
            return Err(StoryContractError::InvalidRequest(
                "story_chapter_must_be_positive_integer",
            ));
        }

        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SegmentCacheKeyInput {
    pub source_sha256: String,
    pub voice_plan_sha256: String,
    pub event_id: String,
    pub text: String,
    pub qwen_speaker: String,
    pub style_instruction: String,
    pub voice_profile_version: u32,
    pub model_inference_sha256: String,
}

impl SegmentCacheKeyInput {
    fn validate(&self) -> Result<(), StoryContractError> {
        for (field, value) in [
            ("source_sha256", self.source_sha256.as_str()),
            ("voice_plan_sha256", self.voice_plan_sha256.as_str()),
            (
                "model_inference_sha256",
                self.model_inference_sha256.as_str(),
            ),
        ] {
            if !is_lowercase_sha256(value) {
                return Err(StoryContractError::InvalidCacheKey(field));
            }
        }
        for (field, value) in [
            ("event_id", self.event_id.as_str()),
            ("text", self.text.as_str()),
            ("qwen_speaker", self.qwen_speaker.as_str()),
            ("style_instruction", self.style_instruction.as_str()),
        ] {
            if value.trim().is_empty() {
                return Err(StoryContractError::InvalidCacheKey(field));
            }
        }
        if self.voice_profile_version == 0 {
            return Err(StoryContractError::InvalidCacheKey("voice_profile_version"));
        }
        Ok(())
    }
}

#[derive(Debug, Error)]
pub enum StoryContractError {
    #[error("invalid story request: {0}")]
    InvalidRequest(&'static str),
    #[error("invalid segment cache key field: {0}")]
    InvalidCacheKey(&'static str),
    #[error("story source error: {0}")]
    InvalidSource(String),
    #[error("cannot read story source {path}: {source}")]
    SourceIo {
        path: String,
        #[source]
        source: std::io::Error,
    },
    #[error("cannot serialize canonical JSON: {0}")]
    Json(#[from] serde_json::Error),
}

/// Serialize JSON with recursively sorted object keys, compact separators, and UTF-8 text.
pub fn canonical_json(value: &Value) -> Result<String, StoryContractError> {
    Ok(serde_json::to_string(&canonicalize(value))?)
}

/// Hash the exact UTF-8 bytes returned by [`canonical_json`].
pub fn sha256_canonical_json(value: &Value) -> Result<String, StoryContractError> {
    let canonical = canonical_json(value)?;
    Ok(hex_sha256(canonical.as_bytes()))
}

/// Produce the S5ZF-compatible segment cache key without reading files or actuating audio.
pub fn segment_cache_key(input: &SegmentCacheKeyInput) -> Result<String, StoryContractError> {
    input.validate()?;
    sha256_canonical_json(&serde_json::to_value(input)?)
}

/// Read and index a UTF-8 TXT/Markdown source without producing a full story plan.
pub fn ingest_story_source(
    path: &Path,
    start: &StoryStart,
) -> Result<StorySourceIngest, StoryContractError> {
    let suffix = path
        .extension()
        .and_then(|value| value.to_str())
        .map(|value| format!(".{}", value.to_lowercase()))
        .unwrap_or_default();
    if !SUPPORTED_SOURCE_SUFFIXES.contains(&suffix.as_str()) {
        return Err(StoryContractError::InvalidSource(format!(
            "unsupported_story_source:{}",
            if suffix.is_empty() { "<none>" } else { &suffix }
        )));
    }

    let source_bytes = fs::read(path).map_err(|source| StoryContractError::SourceIo {
        path: path.display().to_string(),
        source,
    })?;
    let text = std::str::from_utf8(&source_bytes)
        .map_err(|_| StoryContractError::InvalidSource("story_source_must_be_utf8".into()))?;
    let source_sha256 = hex_sha256(&source_bytes);
    let source_id = deterministic_id(
        "source",
        &serde_json::json!({"sha256": &source_sha256, "version": "source-v1"}),
    )?;
    let mut chapters = index_chapters(text, &source_id)?;
    let first_chapter = match start {
        StoryStart::FromStart => chapters[0].ordinal,
        StoryStart::Chapter { chapter } if chapters.iter().any(|row| row.ordinal == *chapter) => {
            *chapter
        }
        StoryStart::Chapter { chapter } => {
            return Err(StoryContractError::InvalidSource(format!(
                "story_chapter_not_found:{chapter}"
            )));
        }
    };
    for chapter in &mut chapters {
        chapter.selected = chapter.ordinal >= first_chapter;
    }
    let selected_chapter_ids = chapters
        .iter()
        .filter(|chapter| chapter.selected)
        .map(|chapter| chapter.chapter_id.clone())
        .collect();
    let absolute_path = path
        .canonicalize()
        .map_err(|source| StoryContractError::SourceIo {
            path: path.display().to_string(),
            source,
        })?;

    Ok(StorySourceIngest {
        source: StorySource {
            source_id,
            kind: "novel".into(),
            format: suffix.trim_start_matches('.').into(),
            uri: absolute_path.display().to_string(),
            sha256: source_sha256,
            version: "source-v1".into(),
            encoding: "utf-8".into(),
            byte_length: source_bytes.len(),
            char_length: text.chars().count(),
        },
        selection: StorySelection {
            first_chapter,
            selected_chapter_ids,
        },
        chapters,
    })
}

#[derive(Debug)]
struct LineRecord<'a> {
    number: usize,
    text: &'a str,
    char_start: usize,
    char_end: usize,
}

fn line_records(text: &str) -> Vec<LineRecord<'_>> {
    let mut records = Vec::new();
    let mut byte_start = 0;
    let mut char_start = 0;
    for line_with_end in text.split_inclusive('\n') {
        let line = line_with_end.trim_end_matches(['\r', '\n']);
        let char_end = char_start + line_with_end.chars().count();
        records.push(LineRecord {
            number: records.len() + 1,
            text: &text[byte_start..byte_start + line.len()],
            char_start,
            char_end,
        });
        byte_start += line_with_end.len();
        char_start = char_end;
    }
    if !text.is_empty() && !text.ends_with('\n') && records.is_empty() {
        records.push(LineRecord {
            number: 1,
            text,
            char_start: 0,
            char_end: text.chars().count(),
        });
    }
    records
}

fn index_chapters(text: &str, source_id: &str) -> Result<Vec<StoryChapter>, StoryContractError> {
    let records = line_records(text);
    if records.is_empty() {
        return Err(StoryContractError::InvalidSource(
            "story_source_empty".into(),
        ));
    }
    let mut starts = records
        .iter()
        .enumerate()
        .filter_map(|(index, record)| chapter_heading(record.text).map(|row| (index, row)))
        .collect::<Vec<_>>();
    if starts.is_empty() {
        starts.push((0, ("全文".into(), Some(1))));
    } else if starts[0].0 > 0
        && records[..starts[0].0]
            .iter()
            .any(|record| !record.text.trim().is_empty())
    {
        starts.insert(0, (0, ("前言".into(), Some(0))));
    }

    let mut chapters = Vec::new();
    let mut used_ordinals = HashSet::new();
    let mut next_ordinal = 1;
    for (chapter_index, (record_start, (title, parsed_ordinal))) in starts.iter().enumerate() {
        let record_end = starts
            .get(chapter_index + 1)
            .map(|row| row.0)
            .unwrap_or(records.len());
        let mut ordinal = parsed_ordinal.unwrap_or(next_ordinal);
        if parsed_ordinal.is_none() || used_ordinals.contains(&ordinal) {
            while used_ordinals.contains(&next_ordinal) {
                next_ordinal += 1;
            }
            ordinal = next_ordinal;
        }
        used_ordinals.insert(ordinal);
        next_ordinal = next_ordinal.max(ordinal + 1);
        let first = &records[*record_start];
        let last = &records[record_end - 1];
        let chapter_id = deterministic_id(
            "chapter",
            &serde_json::json!({
                "source_id": source_id,
                "ordinal": ordinal,
                "title": title,
            }),
        )?;
        chapters.push(StoryChapter {
            chapter_id,
            ordinal,
            title: title.clone(),
            selected: false,
            source_span: SourceSpan {
                source_id: source_id.into(),
                line_start: first.number,
                line_end: last.number,
                char_start: first.char_start,
                char_end: last.char_end,
            },
        });
    }
    Ok(chapters)
}

fn chapter_heading(line: &str) -> Option<(String, Option<u32>)> {
    let trimmed = line.trim_start();
    let without_hashes = strip_optional_hash_prefix(trimmed);
    if let Some(rest) = without_hashes.strip_prefix('第') {
        let numeral_len = rest
            .chars()
            .take_while(|character| is_chapter_numeral(*character))
            .map(char::len_utf8)
            .sum::<usize>();
        let (numeral, after_numeral) = rest.split_at(numeral_len);
        if !numeral.is_empty()
            && after_numeral
                .chars()
                .next()
                .is_some_and(|marker| matches!(marker, '章' | '节' | '回' | '卷'))
        {
            return Some((without_hashes.trim().into(), chinese_number(numeral)));
        }
    }
    markdown_heading(trimmed).map(|title| (title, None))
}

fn strip_optional_hash_prefix(line: &str) -> &str {
    let count = line
        .chars()
        .take_while(|character| *character == '#')
        .count();
    if (1..=6).contains(&count) {
        line[count..].trim_start()
    } else {
        line
    }
}

fn markdown_heading(line: &str) -> Option<String> {
    let count = line
        .chars()
        .take_while(|character| *character == '#')
        .count();
    if !(1..=6).contains(&count) {
        return None;
    }
    let rest = &line[count..];
    if rest.chars().next().is_some_and(char::is_whitespace) {
        Some(rest.trim().into())
    } else {
        None
    }
}

fn is_chapter_numeral(character: char) -> bool {
    character.is_ascii_digit()
        || matches!(
            character,
            '零' | '〇'
                | '一'
                | '二'
                | '三'
                | '四'
                | '五'
                | '六'
                | '七'
                | '八'
                | '九'
                | '十'
                | '百'
                | '千'
        )
}

fn chinese_number(value: &str) -> Option<u32> {
    if value.chars().all(|character| character.is_ascii_digit()) {
        return value.parse().ok();
    }
    let mut total = 0;
    let mut current = 0;
    for character in value.chars() {
        current = match character {
            '零' | '〇' => 0,
            '一' => 1,
            '二' => 2,
            '三' => 3,
            '四' => 4,
            '五' => 5,
            '六' => 6,
            '七' => 7,
            '八' => 8,
            '九' => 9,
            _ => {
                let unit = match character {
                    '十' => 10,
                    '百' => 100,
                    '千' => 1000,
                    _ => return None,
                };
                total += current.max(1) * unit;
                0
            }
        };
    }
    Some(total + current)
}

fn deterministic_id(prefix: &str, value: &Value) -> Result<String, StoryContractError> {
    let digest = sha256_canonical_json(value)?;
    Ok(format!("{prefix}_{}", &digest[..20]))
}

fn canonicalize(value: &Value) -> Value {
    match value {
        Value::Object(object) => {
            let sorted = object
                .iter()
                .map(|(key, value)| (key.clone(), canonicalize(value)))
                .collect::<BTreeMap<_, _>>();
            Value::Object(sorted.into_iter().collect::<Map<_, _>>())
        }
        Value::Array(values) => Value::Array(values.iter().map(canonicalize).collect()),
        _ => value.clone(),
    }
}

fn is_lowercase_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn hex_sha256(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}
