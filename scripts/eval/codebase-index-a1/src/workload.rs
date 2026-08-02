use std::{fs, path::Path};

use ab_store::{CodebaseCall, CodebaseImport, CodebaseSymbol};
use sha2::{Digest, Sha256};
use thiserror::Error;

use crate::Workload;

pub const FROZEN_WORKLOAD_SCHEMA: &str = "agent_bridge.codebase_index.frozen_workload.v0";
pub const WORKLOAD_GENERATOR_REVISION: &str = "frozen-source-templates-v0";
pub const SEMANTIC_SCHEMA: &str = "agent_bridge.codebase_index.semantic_digest.v0";

#[derive(Debug, Error)]
pub enum WorkloadError {
    #[error("documents and batch_rows must both be positive")]
    Empty,
    #[error("fixture path {0} has no production language mapping")]
    UnsupportedPath(String),
    #[error("fixture path {path} resolved to {actual}, expected {expected}")]
    LanguageMismatch {
        path: String,
        expected: &'static str,
        actual: String,
    },
    #[error("workload count overflow")]
    CountOverflow,
    #[error("workload filesystem operation failed: {0}")]
    Io(#[from] std::io::Error),
}

struct FrozenTemplate {
    language: &'static str,
    extension: &'static str,
    content: &'static str,
}

const FROZEN_TEMPLATES: &[FrozenTemplate] = &[
    FrozenTemplate {
        language: "rust",
        extension: "rs",
        content: r#"use std::{collections::HashMap, sync::Arc};
use crate::engine::Engine as LocalEngine;

pub struct Worker {
    jobs: HashMap<String, usize>,
}

impl Worker {
    pub fn new() -> Self {
        helper();
        Self { jobs: HashMap::new() }
    }

    pub fn run(&self) {
        self.prepare();
        execute();
        LocalEngine::new();
        Arc::new(1usize);
    }

    fn prepare(&self) {
        helper();
    }
}

pub fn execute() {
    helper();
}

fn helper() {}
"#,
    },
    FrozenTemplate {
        language: "python",
        extension: "py",
        content: r#"import os
from pathlib import Path as LocalPath

class Worker:
    def __init__(self):
        self.path = LocalPath(os.getcwd())

    def run(self):
        self.prepare()
        helper()

    def prepare(self):
        helper()

def execute():
    helper()

def helper():
    return os.getcwd()
"#,
    },
    FrozenTemplate {
        language: "typescript",
        extension: "ts",
        content: r#"import { Engine as LocalEngine } from './engine';
import * as path from 'node:path';

export class Worker {
  run(): void {
    this.prepare();
    execute();
    LocalEngine.create();
  }

  prepare(): void {
    helper();
  }
}

export function execute(): void {
  helper();
  path.join('a', 'b');
}

function helper(): void {}
"#,
    },
    FrozenTemplate {
        language: "go",
        extension: "go",
        content: r#"package fixture

import (
    "fmt"
    alias "path/filepath"
)

type Worker struct{}

func NewWorker() *Worker {
    helper()
    return &Worker{}
}

func (w *Worker) Run() {
    w.prepare()
    execute()
    fmt.Println(alias.Join("a", "b"))
}

func (w *Worker) prepare() {
    helper()
}

func execute() {
    helper()
}

func helper() {}
"#,
    },
];

pub fn materialize(
    root: &Path,
    documents: u64,
    batch_rows: usize,
) -> Result<Workload, WorkloadError> {
    if documents == 0 || batch_rows == 0 {
        return Err(WorkloadError::Empty);
    }
    let mut semantic = SemanticAccumulator::new();
    let mut max_extractor_output_rows = 0;
    for document_index in 0..documents {
        let template = &FROZEN_TEMPLATES[(document_index as usize) % FROZEN_TEMPLATES.len()];
        let virtual_path = format!(
            "frozen-v0/{}/{document_index:08}.{}",
            template.language, template.extension
        );
        let actual_path = root.join(&virtual_path);
        let parent = actual_path
            .parent()
            .ok_or_else(|| WorkloadError::UnsupportedPath(actual_path.display().to_string()))?;
        fs::create_dir_all(parent)?;
        fs::write(&actual_path, template.content)?;

        let detected = ab_store::codebase::detect_language(Path::new(&virtual_path))
            .ok_or_else(|| WorkloadError::UnsupportedPath(virtual_path.clone()))?;
        if detected != template.language {
            return Err(WorkloadError::LanguageMismatch {
                path: virtual_path,
                expected: template.language,
                actual: detected.to_string(),
            });
        }
        let symbols =
            ab_store::codebase::extract_symbols(template.content, &virtual_path, detected);
        let imports =
            ab_store::codebase::extract_imports(template.content, &virtual_path, detected);
        let calls = ab_store::codebase::extract_calls(template.content, &virtual_path, detected);
        max_extractor_output_rows = max_extractor_output_rows.max(
            symbols
                .len()
                .saturating_add(imports.len())
                .saturating_add(calls.len()),
        );
        for symbol in symbols {
            semantic.push_symbol(&symbol)?;
        }
        for import in imports {
            semantic.push_import(&import)?;
        }
        for call in calls {
            semantic.push_call(&call)?;
        }
    }
    let receipt = semantic.finish();
    let total_rows = receipt
        .symbols
        .checked_add(receipt.imports)
        .and_then(|value| value.checked_add(receipt.calls))
        .ok_or(WorkloadError::CountOverflow)?;
    Ok(Workload {
        schema: FROZEN_WORKLOAD_SCHEMA.to_string(),
        generator_revision: WORKLOAD_GENERATOR_REVISION.to_string(),
        manifest_sha256: frozen_manifest_sha256(documents),
        corpus_sha256: actual_corpus_sha256(root, documents)?,
        documents,
        symbols: receipt.symbols,
        imports: receipt.imports,
        calls: receipt.calls,
        total_rows,
        batch_rows,
        max_extractor_output_rows,
        symbols_sha256: receipt.symbols_sha256,
        imports_sha256: receipt.imports_sha256,
        calls_sha256: receipt.calls_sha256,
        combined_sha256: receipt.combined_sha256,
    })
}

pub fn frozen_corpus_sha256(documents: u64) -> String {
    let mut digest = Sha256::new();
    frame_str(&mut digest, "agent_bridge.codebase_index.corpus_bytes.v0");
    frame_u64(&mut digest, documents);
    for document_index in 0..documents {
        let template = &FROZEN_TEMPLATES[(document_index as usize) % FROZEN_TEMPLATES.len()];
        let virtual_path = format!(
            "frozen-v0/{}/{document_index:08}.{}",
            template.language, template.extension
        );
        frame_str(&mut digest, &virtual_path);
        frame_u64(&mut digest, template.content.len() as u64);
        digest.update(template.content.as_bytes());
    }
    digest_hex(digest)
}

pub fn actual_corpus_sha256(root: &Path, documents: u64) -> Result<String, WorkloadError> {
    let mut digest = Sha256::new();
    frame_str(&mut digest, "agent_bridge.codebase_index.corpus_bytes.v0");
    frame_u64(&mut digest, documents);
    for document_index in 0..documents {
        let template = &FROZEN_TEMPLATES[(document_index as usize) % FROZEN_TEMPLATES.len()];
        let virtual_path = format!(
            "frozen-v0/{}/{document_index:08}.{}",
            template.language, template.extension
        );
        let contents = fs::read(root.join(&virtual_path))?;
        frame_str(&mut digest, &virtual_path);
        frame_u64(&mut digest, contents.len() as u64);
        digest.update(contents);
    }
    Ok(digest_hex(digest))
}

pub fn frozen_manifest_sha256(documents: u64) -> String {
    let mut digest = Sha256::new();
    frame_str(&mut digest, FROZEN_WORKLOAD_SCHEMA);
    frame_str(&mut digest, WORKLOAD_GENERATOR_REVISION);
    frame_u64(&mut digest, documents);
    for template in FROZEN_TEMPLATES {
        frame_str(&mut digest, template.language);
        frame_str(&mut digest, template.extension);
        frame_str(&mut digest, template.content);
    }
    digest_hex(digest)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct SemanticReceipt {
    pub symbols: u64,
    pub imports: u64,
    pub calls: u64,
    pub symbols_sha256: String,
    pub imports_sha256: String,
    pub calls_sha256: String,
    pub combined_sha256: String,
}

pub(crate) struct SemanticAccumulator {
    symbols: Sha256,
    imports: Sha256,
    calls: Sha256,
    symbol_count: u64,
    import_count: u64,
    call_count: u64,
}

impl SemanticAccumulator {
    pub(crate) fn new() -> Self {
        let mut symbols = Sha256::new();
        let mut imports = Sha256::new();
        let mut calls = Sha256::new();
        frame_str(&mut symbols, "agent-bridge/codebase-index/symbols/v0");
        frame_str(&mut imports, "agent-bridge/codebase-index/imports/v0");
        frame_str(&mut calls, "agent-bridge/codebase-index/calls/v0");
        Self {
            symbols,
            imports,
            calls,
            symbol_count: 0,
            import_count: 0,
            call_count: 0,
        }
    }

    fn push_symbol(&mut self, value: &CodebaseSymbol) -> Result<(), WorkloadError> {
        self.push_symbol_fields(
            &value.file_path,
            value.line,
            value.col,
            &value.kind,
            &value.name,
            &value.signature,
            &value.language,
        )
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn push_symbol_fields(
        &mut self,
        file_path: &str,
        line: u32,
        col: u32,
        kind: &str,
        name: &str,
        signature: &str,
        language: &str,
    ) -> Result<(), WorkloadError> {
        frame_str(&mut self.symbols, file_path);
        frame_u32(&mut self.symbols, line);
        frame_u32(&mut self.symbols, col);
        frame_str(&mut self.symbols, kind);
        frame_str(&mut self.symbols, name);
        frame_str(&mut self.symbols, signature);
        frame_str(&mut self.symbols, language);
        frame_optional_f32(&mut self.symbols, None);
        self.symbol_count = self
            .symbol_count
            .checked_add(1)
            .ok_or(WorkloadError::CountOverflow)?;
        Ok(())
    }

    fn push_import(&mut self, value: &CodebaseImport) -> Result<(), WorkloadError> {
        self.push_import_fields(
            &value.file_path,
            value.line,
            &value.language,
            &value.raw,
            &value.target,
            value.alias.as_deref(),
        )
    }

    pub(crate) fn push_import_fields(
        &mut self,
        file_path: &str,
        line: u32,
        language: &str,
        raw: &str,
        target: &str,
        alias: Option<&str>,
    ) -> Result<(), WorkloadError> {
        frame_str(&mut self.imports, file_path);
        frame_u32(&mut self.imports, line);
        frame_str(&mut self.imports, language);
        frame_str(&mut self.imports, raw);
        frame_str(&mut self.imports, target);
        frame_optional_str(&mut self.imports, alias);
        self.import_count = self
            .import_count
            .checked_add(1)
            .ok_or(WorkloadError::CountOverflow)?;
        Ok(())
    }

    fn push_call(&mut self, value: &CodebaseCall) -> Result<(), WorkloadError> {
        self.push_call_fields(
            &value.file_path,
            value.line,
            &value.language,
            &value.caller,
            &value.callee,
        )
    }

    pub(crate) fn push_call_fields(
        &mut self,
        file_path: &str,
        line: u32,
        language: &str,
        caller: &str,
        callee: &str,
    ) -> Result<(), WorkloadError> {
        frame_str(&mut self.calls, file_path);
        frame_u32(&mut self.calls, line);
        frame_str(&mut self.calls, language);
        frame_str(&mut self.calls, caller);
        frame_str(&mut self.calls, callee);
        self.call_count = self
            .call_count
            .checked_add(1)
            .ok_or(WorkloadError::CountOverflow)?;
        Ok(())
    }

    pub(crate) fn finish(self) -> SemanticReceipt {
        let symbols: [u8; 32] = self.symbols.finalize().into();
        let imports: [u8; 32] = self.imports.finalize().into();
        let calls: [u8; 32] = self.calls.finalize().into();
        let mut combined = Sha256::new();
        frame_str(&mut combined, SEMANTIC_SCHEMA);
        frame_u64(&mut combined, self.symbol_count);
        combined.update(symbols);
        frame_u64(&mut combined, self.import_count);
        combined.update(imports);
        frame_u64(&mut combined, self.call_count);
        combined.update(calls);
        SemanticReceipt {
            symbols: self.symbol_count,
            imports: self.import_count,
            calls: self.call_count,
            symbols_sha256: bytes_hex(&symbols),
            imports_sha256: bytes_hex(&imports),
            calls_sha256: bytes_hex(&calls),
            combined_sha256: digest_hex(combined),
        }
    }
}

pub(crate) fn frame_str(digest: &mut Sha256, value: &str) {
    frame_u64(digest, value.len() as u64);
    digest.update(value.as_bytes());
}

pub(crate) fn frame_optional_str(digest: &mut Sha256, value: Option<&str>) {
    match value {
        Some(value) => {
            digest.update([1]);
            frame_str(digest, value);
        }
        None => digest.update([0]),
    }
}

fn frame_optional_f32(digest: &mut Sha256, value: Option<f32>) {
    match value {
        Some(value) => {
            digest.update([1]);
            digest.update(value.to_bits().to_be_bytes());
        }
        None => digest.update([0]),
    }
}

pub(crate) fn frame_u32(digest: &mut Sha256, value: u32) {
    digest.update(value.to_be_bytes());
}

pub(crate) fn frame_u64(digest: &mut Sha256, value: u64) {
    digest.update(value.to_be_bytes());
}

pub(crate) fn digest_hex(digest: Sha256) -> String {
    bytes_hex(digest.finalize().as_slice())
}

pub(crate) fn bytes_hex(bytes: &[u8]) -> String {
    use std::fmt::Write as _;

    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        let _ = write!(output, "{byte:02x}");
    }
    output
}
