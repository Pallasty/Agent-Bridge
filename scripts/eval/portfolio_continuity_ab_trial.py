#!/usr/bin/env python3
"""Capture and assemble a private AB-native portfolio-continuity trial.

The capture path opens the source SQLite database read-only, makes an online
backup, and points a child Agent-Bridge MCP process at that temporary snapshot.
Raw prompts and memory content stay in caller-selected private files. The
assembler emits scorer-compatible fixtures/candidates plus a redacted summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import select
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


SPEC_SCHEMA = "agent_bridge.portfolio_continuity_capture_spec.v0"
CAPTURE_SCHEMA = "agent_bridge.portfolio_continuity_ab_capture.v0"
REDACTED_CAPTURE_SCHEMA = "agent_bridge.portfolio_continuity_ab_capture_redacted.v0"
REVIEW_SCHEMA = "agent_bridge.portfolio_continuity_evidence_review.v0"
REVIEW_DECISIONS_SCHEMA = "agent_bridge.portfolio_continuity_review_decisions.v0"
ASSEMBLY_SCHEMA = "agent_bridge.portfolio_continuity_ab_assembly.v0"
SCORER_FIXTURE_SCHEMA = "agent_bridge.portfolio_continuity_eval_fixture.v0"
SCORER_CANDIDATE_SCHEMA = "agent_bridge.portfolio_continuity_candidate.v0"

CONDITIONS = ("hybrid_retrieval", "session_bootstrap", "portfolio_digest")
EVIDENCE_STATUS = {"active", "superseded", "archived", "unknown"}
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SECTION_RE = re.compile(r"^=== (.+?) ===$")


class TrialError(ValueError):
    """Raised when a trial input or child response violates the contract."""


def reject_json_constant(value: str) -> None:
    raise TrialError(f"non-standard JSON numeric constant is forbidden: {value}")


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise TrialError("JSON object contains a duplicate field")
        out[key] = value
    return out


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=reject_json_constant,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrialError(f"failed to read JSON input: {exc}") from exc
    return require_object(value, str(path)), raw


def write_json(path: Path, value: dict[str, Any]) -> bytes:
    try:
        rendered = (
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rendered)
    except (OSError, ValueError) as exc:
        raise TrialError(f"failed to write JSON output: {exc}") from exc
    return rendered


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise TrialError(f"failed to hash file: {exc}") from exc
    return digest.hexdigest()


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TrialError(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise TrialError(f"{path} must be an array")
    return value


def require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrialError(f"{path} must be a non-empty string")
    return value


def require_label(value: Any, path: str) -> str:
    label = require_string(value, path)
    if not LABEL_RE.fullmatch(label):
        raise TrialError(f"{path} must be a bounded machine label")
    return label


def require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise TrialError(f"{path} must be a boolean")
    return value


def require_nonnegative_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TrialError(f"{path} must be a non-negative integer")
    return value


def require_finite_number(value: Any, path: str, *, positive: bool = False) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TrialError(f"{path} must be numeric")
    try:
        number = float(value)
    except OverflowError as exc:
        raise TrialError(f"{path} must be finite") from exc
    if not math.isfinite(number) or number < 0 or (positive and number <= 0):
        qualifier = "positive finite" if positive else "non-negative finite"
        raise TrialError(f"{path} must be a {qualifier} number")
    return number


def reject_unknown_fields(value: dict[str, Any], allowed: set[str], path: str) -> None:
    count = len(set(value) - allowed)
    if count:
        raise TrialError(f"{path} contains {count} unsupported field(s)")


def unique_labels(value: Any, path: str, *, allow_empty: bool = True) -> list[str]:
    items = require_list(value, path)
    labels = [require_label(item, f"{path}[{index}]") for index, item in enumerate(items)]
    if len(labels) != len(set(labels)):
        raise TrialError(f"{path} must not contain duplicates")
    if not allow_empty and not labels:
        raise TrialError(f"{path} must not be empty")
    return labels


def is_cjk(ch: str) -> bool:
    code = ord(ch)
    return (
        0x3000 <= code <= 0x303F
        or 0x3040 <= code <= 0x309F
        or 0x30A0 <= code <= 0x30FF
        or 0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
    )


def estimate_tokens(text: str) -> int:
    alpha = digit = punct = cjk = 0
    for ch in text:
        if ch.isspace():
            continue
        if is_cjk(ch):
            cjk += 1
        elif ch.isalpha():
            alpha += 1
        elif ch.isascii() and ch.isdigit():
            digit += 1
        else:
            punct += 1
    return (
        math.ceil(alpha / 4.0)
        + math.ceil(digit / 2.5)
        + math.ceil(punct / 1.2)
        + math.ceil(cjk / 1.1)
    )


def validate_thresholds(value: Any, path: str) -> dict[str, Any]:
    thresholds = require_object(value, path)
    allowed = {
        "min_supported_claim_coverage",
        "min_evidence_precision",
        "max_stale_evidence_refs",
        "max_unknown_evidence_refs",
        "max_unsupported_claims",
        "max_forbidden_claims",
        "max_unsupported_evidence_claims",
        "require_all_cases_pass",
        "require_all_abstention_cases_pass",
    }
    reject_unknown_fields(thresholds, allowed, path)
    for key in ["min_supported_claim_coverage", "min_evidence_precision"]:
        number = require_finite_number(thresholds.get(key), f"{path}.{key}")
        if number > 1:
            raise TrialError(f"{path}.{key} must be between 0 and 1")
    for key in [
        "max_stale_evidence_refs",
        "max_unknown_evidence_refs",
        "max_unsupported_claims",
        "max_forbidden_claims",
        "max_unsupported_evidence_claims",
    ]:
        require_nonnegative_int(thresholds.get(key), f"{path}.{key}")
    require_bool(thresholds.get("require_all_cases_pass"), f"{path}.require_all_cases_pass")
    require_bool(
        thresholds.get("require_all_abstention_cases_pass"),
        f"{path}.require_all_abstention_cases_pass",
    )
    return thresholds


def validate_claim_rubric(value: Any, path: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(require_list(value, path)):
        item_path = f"{path}[{index}]"
        item = require_object(raw, item_path)
        reject_unknown_fields(item, {"claim_id", "weight"}, item_path)
        claim_id = require_label(item.get("claim_id"), f"{item_path}.claim_id")
        if claim_id in seen:
            raise TrialError(f"{path} contains duplicate claim ids")
        seen.add(claim_id)
        weight = require_finite_number(
            item.get("weight", 1.0), f"{item_path}.weight", positive=True
        )
        out.append({"claim_id": claim_id, "weight": weight})
    return out


def validate_spec(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema") != SPEC_SCHEMA:
        raise TrialError(f"spec schema must be {SPEC_SCHEMA}")
    reject_unknown_fields(
        value,
        {
            "schema",
            "trial_id",
            "source_commit",
            "digest_key",
            "repo",
            "thresholds",
            "search",
            "bootstrap",
            "cases",
        },
        "spec",
    )
    trial_id = require_label(value.get("trial_id"), "spec.trial_id")
    source_commit = require_string(value.get("source_commit"), "spec.source_commit")
    if not COMMIT_RE.fullmatch(source_commit):
        raise TrialError("spec.source_commit must be a full lowercase git SHA")
    digest_key = require_string(value.get("digest_key"), "spec.digest_key")
    repo = require_string(value.get("repo"), "spec.repo")
    if not Path(repo).is_absolute():
        raise TrialError("spec.repo must be an absolute path")
    thresholds = validate_thresholds(value.get("thresholds"), "spec.thresholds")

    search = require_object(value.get("search"), "spec.search")
    reject_unknown_fields(
        search, {"mode", "compact", "limit", "exclude_kinds"}, "spec.search"
    )
    mode = require_label(search.get("mode"), "spec.search.mode")
    if mode != "hybrid":
        raise TrialError("spec.search.mode must be hybrid for this trial contract")
    compact = require_bool(search.get("compact"), "spec.search.compact")
    if compact:
        raise TrialError("the preregistered hybrid_retrieval condition requires compact=false")
    search_limit = require_nonnegative_int(search.get("limit"), "spec.search.limit")
    if not 1 <= search_limit <= 100:
        raise TrialError("spec.search.limit must be between 1 and 100")
    exclude_kinds = unique_labels(search.get("exclude_kinds", []), "spec.search.exclude_kinds")

    bootstrap = require_object(value.get("bootstrap"), "spec.bootstrap")
    reject_unknown_fields(bootstrap, {"limit", "frontend"}, "spec.bootstrap")
    bootstrap_limit = require_nonnegative_int(bootstrap.get("limit"), "spec.bootstrap.limit")
    if not 1 <= bootstrap_limit <= 100:
        raise TrialError("spec.bootstrap.limit must be between 1 and 100")
    frontend = require_label(bootstrap.get("frontend"), "spec.bootstrap.frontend")
    if frontend not in {"claude-code", "cursor", "warp"}:
        raise TrialError("spec.bootstrap.frontend is unsupported")

    cases_raw = require_list(value.get("cases"), "spec.cases")
    if not cases_raw:
        raise TrialError("spec.cases must not be empty")
    cases: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    for index, raw in enumerate(cases_raw):
        path = f"spec.cases[{index}]"
        case = require_object(raw, path)
        reject_unknown_fields(
            case,
            {
                "case_id",
                "prompt_class",
                "prompt",
                "requires_abstention",
                "required_claims",
                "optional_claims",
                "forbidden_claim_ids",
            },
            path,
        )
        case_id = require_label(case.get("case_id"), f"{path}.case_id")
        if case_id in seen_cases:
            raise TrialError("spec contains duplicate case ids")
        seen_cases.add(case_id)
        prompt_class = require_label(case.get("prompt_class"), f"{path}.prompt_class")
        prompt = require_string(case.get("prompt"), f"{path}.prompt")
        requires_abstention = require_bool(
            case.get("requires_abstention"), f"{path}.requires_abstention"
        )
        required = validate_claim_rubric(case.get("required_claims"), f"{path}.required_claims")
        optional = validate_claim_rubric(case.get("optional_claims", []), f"{path}.optional_claims")
        forbidden = unique_labels(
            case.get("forbidden_claim_ids", []), f"{path}.forbidden_claim_ids"
        )
        claim_ids = {row["claim_id"] for row in required + optional}
        if claim_ids & set(forbidden):
            raise TrialError(f"{path} claim classes overlap")
        if requires_abstention and (required or optional):
            raise TrialError(f"{path} abstention cases cannot define claims")
        if not requires_abstention and not required:
            raise TrialError(f"{path} non-abstention cases require claims")
        cases.append(
            {
                "case_id": case_id,
                "prompt_class": prompt_class,
                "prompt": prompt,
                "requires_abstention": requires_abstention,
                "required_claims": required,
                "optional_claims": optional,
                "forbidden_claim_ids": forbidden,
            }
        )
    return {
        "trial_id": trial_id,
        "source_commit": source_commit,
        "digest_key": digest_key,
        "repo": repo,
        "thresholds": thresholds,
        "search": {
            "mode": mode,
            "compact": compact,
            "limit": search_limit,
            "exclude_kinds": exclude_kinds,
        },
        "bootstrap": {"limit": bootstrap_limit, "frontend": frontend},
        "cases": cases,
    }


class McpClient:
    def __init__(self, binary: Path, cwd: Path, db_path: Path, stderr_path: Path, timeout: float):
        env = os.environ.copy()
        env.update(
            {
                "AGENT_BRIDGE_DB": str(db_path),
                "AGENT_BRIDGE_TOOL_PROFILE": "all",
                "AB_BOOTSTRAP_SURFACING_DISABLE": "1",
                "AGENT_BRIDGE_OUTCOME_COLLECTOR": "0",
                "RUST_LOG": "info",
            }
        )
        self._stderr = stderr_path.open("wb")
        try:
            self._process = subprocess.Popen(
                [str(binary), "mcp"],
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._stderr,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            self._stderr.close()
            raise TrialError(f"failed to start Agent-Bridge MCP: {exc}") from exc
        if self._process.stdin is None or self._process.stdout is None:
            raise TrialError("failed to open MCP stdio pipes")
        self._timeout = timeout
        self._next_id = 1

    def request(self, method: str, params: dict[str, Any]) -> tuple[dict[str, Any], float]:
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        started = time.perf_counter()
        try:
            self._process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise TrialError("MCP child closed stdin") from exc
        ready, _, _ = select.select([self._process.stdout], [], [], self._timeout)
        if not ready:
            raise TrialError(f"MCP request timed out: {method}")
        line = self._process.stdout.readline()
        latency_ms = (time.perf_counter() - started) * 1000.0
        if not line:
            raise TrialError(f"MCP child closed stdout during {method}")
        try:
            response = json.loads(
                line,
                parse_constant=reject_json_constant,
                object_pairs_hook=reject_duplicate_json_keys,
            )
        except json.JSONDecodeError as exc:
            raise TrialError(f"MCP returned invalid JSON for {method}") from exc
        response = require_object(response, f"MCP response {method}")
        if response.get("id") != request_id:
            raise TrialError(f"MCP response id mismatch for {method}")
        if response.get("error") is not None:
            raise TrialError(f"MCP returned an error for {method}")
        return require_object(response.get("result"), f"MCP result {method}"), latency_ms

    def notify(self, method: str) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        try:
            self._process.stdin.write(json.dumps(payload) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise TrialError("MCP child closed during notification") from exc

    def close(self) -> None:
        if self._process.stdin is not None and not self._process.stdin.closed:
            self._process.stdin.close()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._stderr.close()
        if self._process.returncode != 0:
            raise TrialError(f"MCP child exited with status {self._process.returncode}")


def mcp_text(result: dict[str, Any], path: str) -> str:
    if result.get("isError") is True:
        raise TrialError(f"{path} returned isError=true")
    content = require_list(result.get("content"), f"{path}.content")
    text_blocks = [
        block.get("text")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    if len(text_blocks) != 1 or not isinstance(text_blocks[0], str):
        raise TrialError(f"{path} must return exactly one text block")
    return text_blocks[0]


def evidence_id(seed: str) -> str:
    return "ev_" + sha256_text(seed)[:32]


def memory_evidence(record: dict[str, Any], rank: int | None) -> dict[str, Any]:
    key = require_string(record.get("key"), "memory record key")
    content = require_string(record.get("content"), "memory record content")
    content_sha = sha256_text(content)
    status = record.get("status", "unknown")
    if status not in EVIDENCE_STATUS:
        status = "unknown"
    created_at = record.get("created_at")
    if not isinstance(created_at, int) or isinstance(created_at, bool) or created_at < 0:
        created_at = None
    updated_at = record.get("updated_at")
    if not isinstance(updated_at, int) or isinstance(updated_at, bool) or updated_at < 0:
        updated_at = None
    kind = record.get("kind") if isinstance(record.get("kind"), str) else "unknown"
    return {
        "evidence_id": evidence_id(f"memory\0{key}\0{content_sha}"),
        "source_type": "memory_record",
        "source_key": key,
        "source_title": None,
        "kind": kind,
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
        "rank": rank,
        "content": content,
        "content_sha256": content_sha,
        "content_bytes": len(content.encode("utf-8")),
        "content_tokens_estimate": estimate_tokens(content),
    }


def bootstrap_evidence(text: str) -> list[dict[str, Any]]:
    blocks: list[tuple[str, list[str]]] = []
    title = "preamble"
    lines: list[str] = []
    for line in text.splitlines():
        match = SECTION_RE.fullmatch(line.strip())
        if match:
            if any(part.strip() for part in lines):
                blocks.append((title, lines))
            title = match.group(1).strip()
            lines = []
        else:
            lines.append(line)
    if any(part.strip() for part in lines):
        blocks.append((title, lines))

    out: list[dict[str, Any]] = []
    for rank, (block_title, block_lines) in enumerate(blocks, start=1):
        content = "\n".join(block_lines).strip()
        if not content:
            continue
        content_sha = sha256_text(content)
        out.append(
            {
                "evidence_id": evidence_id(f"bootstrap\0{block_title}\0{content_sha}"),
                "source_type": "bootstrap_block",
                "source_key": None,
                "source_title": block_title,
                "kind": "bootstrap_block",
                "status": "unknown",
                "created_at": None,
                "updated_at": None,
                "rank": rank,
                "content": content,
                "content_sha256": content_sha,
                "content_bytes": len(content.encode("utf-8")),
                "content_tokens_estimate": estimate_tokens(content),
            }
        )
    if not out:
        raise TrialError("session_bootstrap returned no non-empty sections")
    return out


def normalize_search(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        hits = json.loads(
            text,
            parse_constant=reject_json_constant,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise TrialError("memory_search returned invalid nested JSON") from exc
    hits = require_list(hits, "memory_search hits")
    evidence: list[dict[str, Any]] = []
    raw_hits: list[dict[str, Any]] = []
    for index, raw in enumerate(hits, start=1):
        hit = require_object(raw, f"memory_search hit {index}")
        record = require_object(hit.get("record"), f"memory_search hit {index}.record")
        score = hit.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            score = None
        raw_hits.append({"rank": index, "score": score, "record": record})
        evidence.append(memory_evidence(record, index))
    return raw_hits, evidence


def normalize_memory_get(text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        record = json.loads(
            text,
            parse_constant=reject_json_constant,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise TrialError("memory_get returned invalid nested JSON") from exc
    record = require_object(record, "memory_get record")
    return record, memory_evidence(record, 1)


def make_condition(
    *,
    latency_ms: float,
    context: str,
    evidence: list[dict[str, Any]],
    raw_result: Any,
) -> dict[str, Any]:
    return {
        "latency_ms": round(latency_ms, 3),
        "context": context,
        "context_sha256": sha256_text(context),
        "context_bytes": len(context.encode("utf-8")),
        "context_tokens_estimate": estimate_tokens(context),
        "evidence": evidence,
        "raw_result": raw_result,
    }


def sqlite_backup(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise TrialError("source SQLite database does not exist")
    try:
        source_uri = source.resolve().as_uri() + "?mode=ro"
        source_conn = sqlite3.connect(source_uri, uri=True)
        destination_conn = sqlite3.connect(destination)
        try:
            source_conn.backup(destination_conn)
        finally:
            destination_conn.close()
            source_conn.close()
    except sqlite3.Error as exc:
        raise TrialError(f"SQLite online backup failed: {exc}") from exc


def observe_binary_identity(
    binary: Path, cwd: Path, source_commit: str, timeout: float
) -> str:
    try:
        completed = subprocess.run(
            [str(binary), "--version"],
            cwd=cwd,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=min(timeout, 30.0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TrialError(f"failed to observe Agent-Bridge binary identity: {exc}") from exc
    observation = "\n".join(
        part.strip() for part in [completed.stdout, completed.stderr] if part.strip()
    )
    if completed.returncode != 0 or not observation:
        raise TrialError("Agent-Bridge --version did not complete successfully")
    if source_commit[:12] not in observation:
        raise TrialError("Agent-Bridge binary identity does not match spec.source_commit")
    if len(observation.encode("utf-8")) > 4096:
        raise TrialError("Agent-Bridge --version output is unexpectedly large")
    return observation


def validate_capture_output_paths(
    source_db: Path,
    repo: Path,
    raw_output: Path,
    redacted_output: Path,
) -> None:
    source_path = source_db.resolve()
    repo_path = repo.resolve()
    raw_path = raw_output.resolve(strict=False)
    redacted_path = redacted_output.resolve(strict=False)
    if raw_path == redacted_path:
        raise TrialError("raw and redacted capture outputs must be different files")
    if source_path in {raw_path, redacted_path}:
        raise TrialError("capture output must not overwrite the source SQLite database")
    if raw_path.is_relative_to(repo_path):
        private_root = (repo_path / "data").resolve(strict=False)
        if not raw_path.is_relative_to(private_root):
            raise TrialError("raw capture inside the repo must be stored under data/")
        relative = raw_path.relative_to(repo_path)
        try:
            ignored = subprocess.run(
                ["git", "check-ignore", "-q", "--no-index", "--", str(relative)],
                cwd=repo_path,
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TrialError(f"failed to verify raw capture ignore policy: {exc}") from exc
        if ignored.returncode != 0:
            raise TrialError("raw capture data/ path is not ignored by git")


def capture_trial(
    spec_path: Path,
    source_db: Path,
    binary: Path,
    raw_output: Path,
    redacted_output: Path,
    timeout: float,
) -> dict[str, Any]:
    spec_raw, _ = read_json(spec_path)
    spec = validate_spec(spec_raw)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise TrialError("Agent-Bridge binary must be an executable file")
    repo = Path(spec["repo"])
    if not repo.is_dir():
        raise TrialError("spec.repo does not exist")
    validate_capture_output_paths(source_db, repo, raw_output, redacted_output)
    binary_observation = observe_binary_identity(
        binary, repo, spec["source_commit"], timeout
    )

    captured_at = int(time.time())
    with tempfile.TemporaryDirectory(prefix="ab-portfolio-continuity-") as tmp:
        tmpdir = Path(tmp)
        snapshot = tmpdir / "state.snapshot.db"
        stderr_path = tmpdir / "mcp.stderr.log"
        sqlite_backup(source_db, snapshot)
        if os.path.samefile(source_db, snapshot):
            raise TrialError("source DB and snapshot must be different files")
        snapshot_sha_before = sha256_file(snapshot)
        client = McpClient(binary, repo, snapshot, stderr_path, timeout)
        close_error: TrialError | None = None
        try:
            initialized, _ = client.request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "portfolio-continuity-ab-trial", "version": "1"},
                },
            )
            client.notify("notifications/initialized")
            server_info = require_object(initialized.get("serverInfo"), "initialize.serverInfo")
            cases: list[dict[str, Any]] = []
            for case in spec["cases"]:
                prompt = case["prompt"]
                search_result, search_latency = client.request(
                    "tools/call",
                    {
                        "name": "memory_search",
                        "arguments": {
                            "query": prompt,
                            "mode": spec["search"]["mode"],
                            "compact": spec["search"]["compact"],
                            "limit": spec["search"]["limit"],
                            "exclude_kinds": spec["search"]["exclude_kinds"],
                        },
                    },
                )
                search_text = mcp_text(search_result, "memory_search")
                search_hits, search_evidence = normalize_search(search_text)

                bootstrap_result, bootstrap_latency = client.request(
                    "tools/call",
                    {
                        "name": "session_bootstrap",
                        "arguments": {
                            "cwd": spec["repo"],
                            "query": prompt,
                            "limit": spec["bootstrap"]["limit"],
                            "frontend": spec["bootstrap"]["frontend"],
                        },
                    },
                )
                bootstrap_text = mcp_text(bootstrap_result, "session_bootstrap")
                bootstrap_items = bootstrap_evidence(bootstrap_text)

                digest_result, digest_latency = client.request(
                    "tools/call",
                    {"name": "memory_get", "arguments": {"key": spec["digest_key"]}},
                )
                digest_text = mcp_text(digest_result, "memory_get")
                digest_record, digest_item = normalize_memory_get(digest_text)
                if digest_record.get("key") != spec["digest_key"]:
                    raise TrialError("memory_get returned the wrong digest key")

                cases.append(
                    {
                        **case,
                        "prompt_sha256": sha256_text(prompt),
                        "conditions": {
                            "hybrid_retrieval": make_condition(
                                latency_ms=search_latency,
                                context=search_text,
                                evidence=search_evidence,
                                raw_result=search_hits,
                            ),
                            "session_bootstrap": make_condition(
                                latency_ms=bootstrap_latency,
                                context=bootstrap_text,
                                evidence=bootstrap_items,
                                raw_result={"text": bootstrap_text},
                            ),
                            "portfolio_digest": make_condition(
                                latency_ms=digest_latency,
                                context=digest_text,
                                evidence=[digest_item],
                                raw_result=digest_record,
                            ),
                        },
                    }
                )
        finally:
            try:
                client.close()
            except TrialError as exc:
                close_error = exc
        if close_error is not None:
            raise close_error
        try:
            stderr_bytes = stderr_path.read_bytes()
        except OSError as exc:
            raise TrialError(f"failed to read MCP stderr log: {exc}") from exc
        snapshot_confirmed = str(snapshot).encode("utf-8") in stderr_bytes
        if not snapshot_confirmed:
            raise TrialError("MCP child did not confirm the temporary snapshot path")
        snapshot_sha_after = sha256_file(snapshot)

        capture = {
            "schema": CAPTURE_SCHEMA,
            "trial_id": spec["trial_id"],
            "captured_at": captured_at,
            "source_commit": spec["source_commit"],
            "snapshot_sha256_before": snapshot_sha_before,
            "snapshot_sha256_after": snapshot_sha_after,
            "mcp_server": {
                "name": server_info.get("name"),
                "version": server_info.get("version"),
                "binary_observation": binary_observation,
                "stderr_sha256": sha256_bytes(stderr_bytes),
                "stderr_bytes": len(stderr_bytes),
            },
            "thresholds": spec["thresholds"],
            "cases": cases,
            "boundary": {
                "source_db_opened_read_only": True,
                "source_db_passed_to_child": False,
                "child_db_is_temporary_snapshot": True,
                "child_snapshot_path_confirmed": snapshot_confirmed,
                "snapshot_removed_after_capture": True,
                "live_store_writes": False,
                "calls_llm": False,
                "raw_capture_is_private": True,
                "repository_fixture_is_synthetic_only": True,
                "answer_quality_claim": False,
                "runtime_promotion_allowed": False,
            },
        }
        raw_bytes = write_json(raw_output, capture)

        redacted_cases: list[dict[str, Any]] = []
        for case in cases:
            condition_rows: dict[str, Any] = {}
            for condition in CONDITIONS:
                row = case["conditions"][condition]
                condition_rows[condition] = {
                    "latency_ms": row["latency_ms"],
                    "context_sha256": row["context_sha256"],
                    "context_bytes": row["context_bytes"],
                    "context_tokens_estimate": row["context_tokens_estimate"],
                    "evidence": [
                        {
                            "evidence_id": item["evidence_id"],
                            "source_type": item["source_type"],
                            "status": item["status"],
                            "rank": item["rank"],
                            "content_sha256": item["content_sha256"],
                            "content_bytes": item["content_bytes"],
                            "content_tokens_estimate": item["content_tokens_estimate"],
                        }
                        for item in row["evidence"]
                    ],
                }
            redacted_cases.append(
                {
                    "case_id": case["case_id"],
                    "prompt_class": case["prompt_class"],
                    "prompt_sha256": case["prompt_sha256"],
                    "conditions": condition_rows,
                }
            )
        redacted = {
            "schema": REDACTED_CAPTURE_SCHEMA,
            "trial_id": spec["trial_id"],
            "captured_at": captured_at,
            "source_commit": spec["source_commit"],
            "binary_observation": binary_observation,
            "capture_sha256": sha256_bytes(raw_bytes),
            "snapshot_sha256_before": snapshot_sha_before,
            "snapshot_sha256_after": snapshot_sha_after,
            "cases": redacted_cases,
            "boundary": capture["boundary"],
        }
        write_json(redacted_output, redacted)
        return redacted


def capture_evidence_index(capture: dict[str, Any], case_id: str) -> dict[str, dict[str, Any]]:
    case = next((row for row in capture["cases"] if row.get("case_id") == case_id), None)
    if not isinstance(case, dict):
        raise TrialError(f"capture is missing case {case_id}")
    evidence: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        row = require_object(case["conditions"].get(condition), f"capture {case_id}.{condition}")
        for raw in require_list(row.get("evidence"), f"capture {case_id}.{condition}.evidence"):
            item = require_object(raw, "capture evidence")
            evidence_id_value = require_label(item.get("evidence_id"), "capture evidence id")
            prior = evidence.get(evidence_id_value)
            if prior is not None and prior.get("content_sha256") != item.get("content_sha256"):
                raise TrialError("capture reuses an evidence id for different content")
            evidence[evidence_id_value] = item
    return evidence


def make_review_template(capture_path: Path, output: Path) -> dict[str, Any]:
    capture, capture_bytes = read_json(capture_path)
    if capture.get("schema") != CAPTURE_SCHEMA:
        raise TrialError(f"capture schema must be {CAPTURE_SCHEMA}")
    cases: list[dict[str, Any]] = []
    for raw_case in require_list(capture.get("cases"), "capture.cases"):
        case = require_object(raw_case, "capture case")
        case_id = require_label(case.get("case_id"), "capture case_id")
        evidence = capture_evidence_index(capture, case_id)
        reviews = []
        for evidence_id_value, item in sorted(evidence.items()):
            status = item.get("status")
            if status not in EVIDENCE_STATUS:
                status = "unknown"
            reviews.append(
                {
                    "evidence_id": evidence_id_value,
                    "status": status,
                    "valid_from": item.get("created_at"),
                    "valid_until": None,
                    "supports_claim_ids": [],
                    "forbidden_claim_ids": [],
                }
            )
        cases.append(
            {
                "case_id": case_id,
                "evidence_reviews": reviews,
            }
        )
    review = {
        "schema": REVIEW_SCHEMA,
        "review_id": f"{capture['trial_id']}.review",
        "capture_sha256": sha256_bytes(capture_bytes),
        "reviewer": "pending_reviewer",
        "cases": cases,
    }
    write_json(output, review)
    return review


def validate_review_decision(
    value: Any,
    path: str,
    claim_ids: set[str],
    forbidden_ids: set[str],
) -> dict[str, Any]:
    decision = require_object(value, path)
    reject_unknown_fields(decision, {"status", "supports", "forbidden"}, path)
    status = require_label(decision.get("status"), f"{path}.status")
    if status not in EVIDENCE_STATUS:
        raise TrialError(f"{path}.status is unsupported")
    supports = unique_labels(decision.get("supports", []), f"{path}.supports")
    forbidden = unique_labels(decision.get("forbidden", []), f"{path}.forbidden")
    if set(supports) - claim_ids:
        raise TrialError(f"{path} references an unknown supported claim")
    if set(forbidden) - forbidden_ids:
        raise TrialError(f"{path} references an unknown forbidden claim")
    return {"status": status, "supports": supports, "forbidden": forbidden}


def apply_review_decisions(
    capture_path: Path,
    template_path: Path,
    decisions_path: Path,
    output: Path,
) -> dict[str, Any]:
    capture, capture_bytes = read_json(capture_path)
    if capture.get("schema") != CAPTURE_SCHEMA:
        raise TrialError(f"capture schema must be {CAPTURE_SCHEMA}")
    capture_sha = sha256_bytes(capture_bytes)
    template, _ = read_json(template_path)
    validate_review(template, capture, capture_sha)
    decisions, _ = read_json(decisions_path)
    if decisions.get("schema") != REVIEW_DECISIONS_SCHEMA:
        raise TrialError(f"review decisions schema must be {REVIEW_DECISIONS_SCHEMA}")
    reject_unknown_fields(decisions, {"schema", "reviewer", "cases"}, "decisions")
    reviewer = require_label(decisions.get("reviewer"), "decisions.reviewer")
    decision_cases = require_object(decisions.get("cases"), "decisions.cases")
    capture_cases = {
        require_label(case.get("case_id"), "capture case_id"): case
        for case in require_list(capture.get("cases"), "capture.cases")
        if isinstance(case, dict)
    }
    if set(decision_cases) != set(capture_cases):
        raise TrialError("review decisions must cover exactly the capture cases")

    review = json.loads(json.dumps(template))
    review["reviewer"] = reviewer
    for review_case in review["cases"]:
        case_id = require_label(review_case.get("case_id"), "review case_id")
        capture_case = capture_cases[case_id]
        raw_case_decisions = require_object(
            decision_cases.get(case_id), f"decisions.cases.{case_id}"
        )
        reject_unknown_fields(
            raw_case_decisions,
            {"source_keys", "source_titles"},
            f"decisions.cases.{case_id}",
        )
        raw_key_decisions = require_object(
            raw_case_decisions.get("source_keys", {}),
            f"decisions.cases.{case_id}.source_keys",
        )
        raw_title_decisions = require_object(
            raw_case_decisions.get("source_titles", {}),
            f"decisions.cases.{case_id}.source_titles",
        )
        claim_ids = {
            row["claim_id"]
            for row in capture_case["required_claims"] + capture_case["optional_claims"]
        }
        forbidden_ids = set(capture_case["forbidden_claim_ids"])
        key_decisions = {
            key: validate_review_decision(
                value,
                f"decisions.cases.{case_id}.source_keys",
                claim_ids,
                forbidden_ids,
            )
            for key, value in raw_key_decisions.items()
        }
        title_decisions = {
            title: validate_review_decision(
                value,
                f"decisions.cases.{case_id}.source_titles",
                claim_ids,
                forbidden_ids,
            )
            for title, value in raw_title_decisions.items()
        }
        metadata: dict[str, dict[str, Any]] = {}
        for condition in CONDITIONS:
            for item in capture_case["conditions"][condition]["evidence"]:
                metadata[item["evidence_id"]] = item
        used_keys: set[str] = set()
        used_titles: set[str] = set()
        for row in review_case["evidence_reviews"]:
            item = metadata[row["evidence_id"]]
            source_key = item.get("source_key")
            source_title = item.get("source_title")
            if isinstance(source_key, str):
                decision = key_decisions.get(source_key)
                used_keys.add(source_key)
            elif isinstance(source_title, str):
                decision = title_decisions.get(source_title)
                used_titles.add(source_title)
            else:
                raise TrialError(f"capture evidence in {case_id} has no review selector")
            if decision is None:
                raise TrialError(f"review decisions leave evidence unreviewed in {case_id}")
            row["status"] = decision["status"]
            row["supports_claim_ids"] = decision["supports"]
            row["forbidden_claim_ids"] = decision["forbidden"]
            if item.get("source_type") == "bootstrap_block":
                row["valid_from"] = None
                row["valid_until"] = None
        if used_keys != set(key_decisions) or used_titles != set(title_decisions):
            raise TrialError(f"review decisions contain unused selectors in {case_id}")
    validate_review(review, capture, capture_sha)
    write_json(output, review)
    return review


def validate_review(
    review: dict[str, Any], capture: dict[str, Any], capture_sha: str
) -> dict[str, dict[str, dict[str, Any]]]:
    if review.get("schema") != REVIEW_SCHEMA:
        raise TrialError(f"review schema must be {REVIEW_SCHEMA}")
    reject_unknown_fields(
        review,
        {"schema", "review_id", "capture_sha256", "reviewer", "cases"},
        "review",
    )
    require_label(review.get("review_id"), "review.review_id")
    require_label(review.get("reviewer"), "review.reviewer")
    if review.get("capture_sha256") != capture_sha:
        raise TrialError("review.capture_sha256 does not match the raw capture")
    capture_cases = {
        require_label(case.get("case_id"), "capture case_id"): case
        for case in require_list(capture.get("cases"), "capture.cases")
        if isinstance(case, dict)
    }
    normalized: dict[str, dict[str, dict[str, Any]]] = {}
    seen_cases: set[str] = set()
    for case_index, raw_case in enumerate(require_list(review.get("cases"), "review.cases")):
        path = f"review.cases[{case_index}]"
        case = require_object(raw_case, path)
        reject_unknown_fields(case, {"case_id", "evidence_reviews"}, path)
        case_id = require_label(case.get("case_id"), f"{path}.case_id")
        if case_id not in capture_cases or case_id in seen_cases:
            raise TrialError(f"{path} has an unknown or duplicate case id")
        seen_cases.add(case_id)
        capture_index = capture_evidence_index(capture, case_id)
        rubric_ids = {
            item["claim_id"]
            for item in capture_cases[case_id]["required_claims"]
            + capture_cases[case_id]["optional_claims"]
        }
        forbidden_ids = set(capture_cases[case_id]["forbidden_claim_ids"])
        rows: dict[str, dict[str, Any]] = {}
        for item_index, raw_item in enumerate(
            require_list(case.get("evidence_reviews"), f"{path}.evidence_reviews")
        ):
            item_path = f"{path}.evidence_reviews[{item_index}]"
            item = require_object(raw_item, item_path)
            reject_unknown_fields(
                item,
                {
                    "evidence_id",
                    "status",
                    "valid_from",
                    "valid_until",
                    "supports_claim_ids",
                    "forbidden_claim_ids",
                },
                item_path,
            )
            evidence_id_value = require_label(item.get("evidence_id"), f"{item_path}.evidence_id")
            if evidence_id_value not in capture_index or evidence_id_value in rows:
                raise TrialError(f"{item_path} has an unknown or duplicate evidence id")
            status = require_label(item.get("status"), f"{item_path}.status")
            if status not in EVIDENCE_STATUS:
                raise TrialError(f"{item_path}.status is unsupported")
            valid_from = item.get("valid_from")
            valid_until = item.get("valid_until")
            if valid_from is not None:
                valid_from = require_nonnegative_int(valid_from, f"{item_path}.valid_from")
            if valid_until is not None:
                valid_until = require_nonnegative_int(valid_until, f"{item_path}.valid_until")
            if valid_from is not None and valid_until is not None and valid_from > valid_until:
                raise TrialError(f"{item_path} has an invalid validity interval")
            supports = unique_labels(
                item.get("supports_claim_ids"), f"{item_path}.supports_claim_ids"
            )
            forbidden = unique_labels(
                item.get("forbidden_claim_ids"), f"{item_path}.forbidden_claim_ids"
            )
            if set(supports) - rubric_ids:
                raise TrialError(f"{item_path} references an unknown supported claim")
            if set(forbidden) - forbidden_ids:
                raise TrialError(f"{item_path} references an unknown forbidden claim")
            rows[evidence_id_value] = {
                "evidence_id": evidence_id_value,
                "status": status,
                "valid_from": valid_from,
                "valid_until": valid_until,
                "supports_claim_ids": supports,
                "forbidden_claim_ids": forbidden,
            }
        if set(rows) != set(capture_index):
            raise TrialError(f"{path} must review every observed evidence item exactly once")
        normalized[case_id] = rows
    if seen_cases != set(capture_cases):
        raise TrialError("review must cover every capture case")
    return normalized


def percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def assemble_trial(capture_path: Path, review_path: Path, output_dir: Path) -> dict[str, Any]:
    capture, capture_bytes = read_json(capture_path)
    if capture.get("schema") != CAPTURE_SCHEMA:
        raise TrialError(f"capture schema must be {CAPTURE_SCHEMA}")
    capture_sha = sha256_bytes(capture_bytes)
    review, _ = read_json(review_path)
    reviews = validate_review(review, capture, capture_sha)
    trial_id = require_label(capture.get("trial_id"), "capture.trial_id")
    captured_at = require_nonnegative_int(capture.get("captured_at"), "capture.captured_at")
    thresholds = validate_thresholds(capture.get("thresholds"), "capture.thresholds")

    fixture_cases: list[dict[str, Any]] = []
    candidates: dict[str, dict[str, Any]] = {
        condition: {
            "schema": SCORER_CANDIDATE_SCHEMA,
            "candidate_id": f"{trial_id}.{condition}",
            "condition": condition,
            "cases": [],
        }
        for condition in CONDITIONS
    }
    condition_metrics = {
        condition: {
            "case_count": 0,
            "observed_evidence_count": 0,
            "relevant_evidence_count": 0,
            "irrelevant_evidence_count": 0,
            "stale_or_unknown_evidence_count": 0,
            "forbidden_evidence_count": 0,
            "context_tokens_total": 0,
            "latencies_ms": [],
        }
        for condition in CONDITIONS
    }

    for raw_case in require_list(capture.get("cases"), "capture.cases"):
        case = require_object(raw_case, "capture case")
        case_id = require_label(case.get("case_id"), "capture case_id")
        prompt_class = require_label(case.get("prompt_class"), "capture prompt_class")
        requires_abstention = require_bool(
            case.get("requires_abstention"), "capture requires_abstention"
        )
        required = validate_claim_rubric(case.get("required_claims"), "capture required_claims")
        optional = validate_claim_rubric(case.get("optional_claims"), "capture optional_claims")
        forbidden_ids = unique_labels(
            case.get("forbidden_claim_ids"), "capture forbidden_claim_ids"
        )
        case_reviews = reviews[case_id]
        accepted: dict[str, list[str]] = {
            row["claim_id"]: [] for row in required + optional
        }
        for evidence_id_value, review_row in case_reviews.items():
            for claim_id in review_row["supports_claim_ids"]:
                accepted[claim_id].append(evidence_id_value)
        for claim_id, ids in accepted.items():
            if not ids:
                raise TrialError(f"claim {claim_id} has no reviewed evidence in case {case_id}")

        fixture_cases.append(
            {
                "case_id": case_id,
                "prompt_class": prompt_class,
                "as_of": captured_at,
                "requires_abstention": requires_abstention,
                "evidence_catalog": [
                    {
                        "key": row["evidence_id"],
                        "status": row["status"],
                        "valid_from": row["valid_from"],
                        "valid_until": row["valid_until"],
                    }
                    for row in sorted(case_reviews.values(), key=lambda item: item["evidence_id"])
                ],
                "required_claims": [
                    {
                        "claim_id": row["claim_id"],
                        "weight": row["weight"],
                        "accepted_evidence_keys": sorted(accepted[row["claim_id"]]),
                    }
                    for row in required
                ],
                "optional_claims": [
                    {
                        "claim_id": row["claim_id"],
                        "weight": row["weight"],
                        "accepted_evidence_keys": sorted(accepted[row["claim_id"]]),
                    }
                    for row in optional
                ],
                "forbidden_claim_ids": forbidden_ids,
            }
        )

        for condition in CONDITIONS:
            condition_row = require_object(
                case["conditions"].get(condition), f"capture {case_id}.{condition}"
            )
            observed = [
                require_label(item.get("evidence_id"), "observed evidence id")
                for item in require_list(condition_row.get("evidence"), "observed evidence")
                if isinstance(item, dict)
            ]
            if len(observed) != len(set(observed)):
                raise TrialError(f"capture {case_id}.{condition} repeats evidence ids")
            claims: list[dict[str, Any]] = []
            for claim in required + optional:
                evidence_keys = sorted(
                    evidence_id_value
                    for evidence_id_value in observed
                    if claim["claim_id"]
                    in case_reviews[evidence_id_value]["supports_claim_ids"]
                )
                if evidence_keys:
                    claims.append(
                        {
                            "claim_id": claim["claim_id"],
                            "confidence": "supported",
                            "evidence_keys": evidence_keys,
                        }
                    )
            for forbidden_id in forbidden_ids:
                evidence_keys = sorted(
                    evidence_id_value
                    for evidence_id_value in observed
                    if forbidden_id in case_reviews[evidence_id_value]["forbidden_claim_ids"]
                )
                if evidence_keys:
                    claims.append(
                        {
                            "claim_id": forbidden_id,
                            "confidence": "supported",
                            "evidence_keys": evidence_keys,
                        }
                    )
            abstained = requires_abstention and not claims
            if abstained:
                claims = [
                    {
                        "claim_id": "insufficient_evidence",
                        "confidence": "abstained",
                        "evidence_keys": [],
                    }
                ]
            context_tokens = require_nonnegative_int(
                condition_row.get("context_tokens_estimate"),
                f"capture {case_id}.{condition}.context_tokens_estimate",
            )
            latency = require_finite_number(
                condition_row.get("latency_ms"), f"capture {case_id}.{condition}.latency_ms"
            )
            candidates[condition]["cases"].append(
                {
                    "case_id": case_id,
                    "abstained": abstained,
                    "context_tokens": context_tokens,
                    "latency_ms": latency,
                    "claims": sorted(claims, key=lambda row: row["claim_id"]),
                }
            )
            metrics = condition_metrics[condition]
            relevant = [
                evidence_id_value
                for evidence_id_value in observed
                if case_reviews[evidence_id_value]["supports_claim_ids"]
                or case_reviews[evidence_id_value]["forbidden_claim_ids"]
            ]
            metrics["case_count"] += 1
            metrics["observed_evidence_count"] += len(observed)
            metrics["relevant_evidence_count"] += len(relevant)
            metrics["irrelevant_evidence_count"] += len(observed) - len(relevant)
            metrics["stale_or_unknown_evidence_count"] += sum(
                case_reviews[evidence_id_value]["status"] != "active"
                for evidence_id_value in observed
            )
            metrics["forbidden_evidence_count"] += sum(
                bool(case_reviews[evidence_id_value]["forbidden_claim_ids"])
                for evidence_id_value in observed
            )
            metrics["context_tokens_total"] += context_tokens
            metrics["latencies_ms"].append(latency)

    fixture = {
        "schema": SCORER_FIXTURE_SCHEMA,
        "fixture_id": f"{trial_id}.reviewed",
        "description": "Private AB-native reviewed evidence corpus; raw content stays outside git.",
        "thresholds": thresholds,
        "cases": fixture_cases,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = output_dir / "fixture.reviewed.json"
    fixture_bytes = write_json(fixture_path, fixture)
    candidate_files: dict[str, Any] = {}
    for condition, candidate in candidates.items():
        path = output_dir / f"candidate.{condition}.json"
        candidate_bytes = write_json(path, candidate)
        candidate_files[condition] = {
            "file": path.name,
            "sha256": sha256_bytes(candidate_bytes),
        }

    summary_metrics: dict[str, Any] = {}
    for condition, raw_metrics in condition_metrics.items():
        observed_count = raw_metrics["observed_evidence_count"]
        summary_metrics[condition] = {
            "case_count": raw_metrics["case_count"],
            "observed_evidence_count": observed_count,
            "relevant_evidence_count": raw_metrics["relevant_evidence_count"],
            "irrelevant_evidence_count": raw_metrics["irrelevant_evidence_count"],
            "relevant_evidence_ratio": round(
                1.0
                if observed_count == 0
                else raw_metrics["relevant_evidence_count"] / observed_count,
                6,
            ),
            "stale_or_unknown_evidence_count": raw_metrics[
                "stale_or_unknown_evidence_count"
            ],
            "forbidden_evidence_count": raw_metrics["forbidden_evidence_count"],
            "context_tokens_total": raw_metrics["context_tokens_total"],
            "latency_ms_p95": round(percentile_95(raw_metrics["latencies_ms"]), 3),
        }
    summary = {
        "schema": ASSEMBLY_SCHEMA,
        "trial_id": trial_id,
        "capture_sha256": capture_sha,
        "source_commit": capture.get("source_commit"),
        "snapshot_sha256_before": capture.get("snapshot_sha256_before"),
        "fixture": {"file": fixture_path.name, "sha256": sha256_bytes(fixture_bytes)},
        "candidates": candidate_files,
        "conditions": summary_metrics,
        "boundary": {
            "raw_content_in_summary": False,
            "raw_evidence_keys_in_summary": False,
            "private_capture_required": True,
            "calls_llm": False,
            "writes_live_ab_store": False,
            "answer_quality_claim": False,
            "runtime_promotion_allowed": False,
        },
    }
    write_json(output_dir / "assembly.summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="Capture three surfaces on a DB snapshot.")
    capture.add_argument("--spec", required=True)
    capture.add_argument("--source-db", required=True)
    capture.add_argument("--agent-bridge-bin", required=True)
    capture.add_argument("--raw-output", required=True)
    capture.add_argument("--redacted-output", required=True)
    capture.add_argument("--timeout-secs", type=float, default=120.0)

    template = subparsers.add_parser(
        "review-template", help="Create a complete evidence-review template from a capture."
    )
    template.add_argument("--capture", required=True)
    template.add_argument("--output", required=True)

    apply_review = subparsers.add_parser(
        "apply-review", help="Apply complete private selector decisions to a review template."
    )
    apply_review.add_argument("--capture", required=True)
    apply_review.add_argument("--template", required=True)
    apply_review.add_argument("--decisions", required=True)
    apply_review.add_argument("--output", required=True)

    assemble = subparsers.add_parser(
        "assemble", help="Assemble scorer fixtures/candidates from a reviewed capture."
    )
    assemble.add_argument("--capture", required=True)
    assemble.add_argument("--review", required=True)
    assemble.add_argument("--output-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "capture":
            if args.timeout_secs <= 0 or not math.isfinite(args.timeout_secs):
                raise TrialError("--timeout-secs must be a positive finite number")
            packet = capture_trial(
                Path(args.spec),
                Path(args.source_db),
                Path(args.agent_bridge_bin),
                Path(args.raw_output),
                Path(args.redacted_output),
                args.timeout_secs,
            )
        elif args.command == "review-template":
            packet = make_review_template(Path(args.capture), Path(args.output))
        elif args.command == "apply-review":
            packet = apply_review_decisions(
                Path(args.capture),
                Path(args.template),
                Path(args.decisions),
                Path(args.output),
            )
        else:
            packet = assemble_trial(
                Path(args.capture), Path(args.review), Path(args.output_dir)
            )
    except TrialError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (KeyError, TypeError, IndexError):
        print("ERROR: malformed trial packet", file=sys.stderr)
        return 2
    print(json.dumps(packet, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
