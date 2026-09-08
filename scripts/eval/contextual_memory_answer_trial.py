#!/usr/bin/env python3
"""Bounded synthetic AB retrieval capture and fresh natural-answer baseline.

No scorer, reference answer, policy change, provider retry, or gold backfill.
The hash embedding backend measures an isolated local path, not production
semantic retrieval quality. Source-text timestamps are not DB supersession.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time

from portfolio_continuity_ab_trial import McpClient, TrialError, mcp_text, sqlite_backup

ROOT = Path(__file__).resolve().parents[2]
FEATURE_SOURCE = ROOT / "crates/agent/src/resident_codex.rs"
OS_ENV = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR")
CODEX_ENV = OS_ENV + ("CODEX_HOME", "OPENAI_API_KEY", "CODEX_API_KEY", "HTTP_PROXY",
                      "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR")
ANSWER_INSTRUCTION = "请用中文自然回答，不超过150个汉字（证据引用不计）；依据记忆的陈述请用 [记忆key] 标注来源。"
DISABLED_HOST_DIAGNOSTIC = ("Code Mode is unavailable because code-mode host is disabled. "
    "Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_input(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(spec.get("common_instruction"), str) or not spec.get("trial_id"):
        raise TrialError("input needs trial_id and common_instruction")
    ids = [c["case_id"] for c in spec["cases"]]
    if not ids or len(set(ids)) != len(ids) or any(
        not re.fullmatch(r"[A-Za-z0-9_-]+", value) for value in ids
    ):
        raise TrialError("case IDs must be unique, nonempty safe path components")
    for case in spec["cases"]:
        if any(not isinstance(case.get(k), str) or not case[k]
               for k in ("query", "scope", "request")):
            raise TrialError("case needs nonempty query, scope and request")
        if isinstance(case.get("as_of"), bool) or not (
            isinstance(case.get("as_of"), int) and case["as_of"] >= 0
        ):
            raise TrialError("case as_of must be a nonnegative synthetic time integer")
    keys = [m["key"] for m in spec["memories"]]
    if not keys or len(set(keys)) != len(keys):
        raise TrialError("memories must have unique keys")
    return spec


def fresh_directory(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise TrialError(f"output must be absent: {path}")
    path.mkdir(parents=True, mode=0o700)


def clean_mcp_env(creds: Path) -> dict[str, str]:
    if creds.is_symlink() or not creds.is_file() or creds.stat().st_size:
        raise TrialError("isolated credentials must be an empty regular file")
    env = {key: os.environ[key] for key in OS_ENV if key in os.environ}
    env.update(AGENT_BRIDGE_CREDS_FILE=str(creds), AGENT_BRIDGE_EMBED_BACKEND="hash")
    return env


def source_hashes(input_path: Path) -> dict[str, str]:
    return {"input": sha(input_path), "runner": sha(Path(__file__)),
            "mcp_helper": sha(Path(__file__).with_name("portfolio_continuity_ab_trial.py")),
            "provider_feature_source": sha(FEATURE_SOURCE)}


def finish(output: Path, manifest: dict) -> None:
    manifest["files_sha256"] = {str(p.relative_to(output)): sha(p)
                                for p in sorted(output.rglob("*"))
                                if p.is_file() and p.name != "manifest.json"}
    write_json(output / "manifest.json", manifest)


def initialize(client: McpClient, directory: Path) -> None:
    result, latency = client.request("initialize", {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "contextual-memory-answer-trial", "version": "1"},
    })
    write_json(directory / "initialize.json", {"raw_result": result, "latency_ms": latency})
    client.notify("notifications/initialized")


def tool_call(client: McpClient, directory: Path, filename: str, name: str, args: dict):
    started = time.perf_counter()
    try:
        result, latency = client.request("tools/call", {"name": name, "arguments": args})
    except Exception as exc:
        write_json(directory / filename, {"arguments": args, "error": str(exc),
                   "latency_ms": (time.perf_counter() - started) * 1000})
        raise
    # Save the exact tool-result object before any interpretation, including isError.
    write_json(directory / filename, {"arguments": args, "raw_result": result,
                                      "latency_ms": latency})
    return mcp_text(result, name), latency


def capture(input_path: Path, output: Path, binary: Path, timeout: float) -> dict:
    spec = read_input(input_path)
    fresh_directory(output)
    manifest = {"trial_id": spec["trial_id"], "phase": "capture", "status": "failed",
                "source_sha256": source_hashes(input_path), "cases": [],
                "backend_requested": "hash", "production_semantic_quality": False,
                "temporal_semantics": "source text only; no DB supersedes mutation"}
    try:
        creds = output / "empty-credentials"
        creds.touch(mode=0o600, exist_ok=False)
        env = clean_mcp_env(creds)
        manifest["child_env_keys"] = sorted(env)
        manifest["binary"] = {"path": str(binary), "sha256": sha(binary)}
        version = subprocess.run([str(binary), "--version"], env=env, capture_output=True,
                                 text=True, timeout=timeout, check=False)
        manifest["binary"].update(version=version.stdout.strip(), version_exit=version.returncode)
        (output / "binary-version.stderr").write_text(version.stderr, encoding="utf-8")
        seed = output / "seed"
        seed.mkdir()
        base_db = seed / "store.db"
        client = McpClient(binary, seed, base_db, seed / "mcp.stderr", timeout, child_env=env)
        try:
            initialize(client, seed)
            for index, memory in enumerate(spec["memories"]):
                args = {key: memory[key] for key in ("key", "kind", "content", "scope")}
                tool_call(client, seed, f"save-{index:02d}.json", "memory_save", args)
        finally:
            client.close()
        # The writer is closed before the first SQLite backup or case clone.
        snapshot = output / "base.snapshot.db"
        sqlite_backup(base_db, snapshot)
        with closing(sqlite3.connect(snapshot.as_uri() + "?mode=ro", uri=True)) as connection:
            manifest["backend_observed"] = connection.execute(
                "SELECT embedding_backend, count(*) FROM memories GROUP BY embedding_backend"
            ).fetchall()
        for case in spec["cases"]:
            directory = output / case["case_id"]
            directory.mkdir()
            db = directory / "store.db"
            sqlite_backup(snapshot, db)
            args = {"query": case["query"], "mode": "hybrid", "scope": case["scope"],
                    "scope_mode": "local_only", "limit": 8, "compact": False}
            row = {"case_id": case["case_id"], "search_arguments": args, "status": "failed"}
            manifest["cases"].append(row)
            client = McpClient(binary, directory, db, directory / "mcp.stderr", timeout,
                               child_env=env)
            try:
                initialize(client, directory)
                context, latency = tool_call(client, directory, "memory_search.json",
                                            "memory_search", args)
                context_path = directory / "context.txt"
                context_path.write_text(context, encoding="utf-8")
                hits = json.loads(context)
                row.update(context_file=str(context_path.relative_to(output)),
                           context_sha256=sha(context_path), latency_ms=latency,
                           returned_keys=[hit["record"]["key"] for hit in hits], status="complete")
            finally:
                client.close()
        if sha(input_path) != manifest["source_sha256"]["input"]:
            raise TrialError("input changed during capture")
        manifest["status"] = "complete"
    except Exception as exc:
        manifest["error"] = str(exc)
        raise
    finally:
        finish(output, manifest)
    return manifest


def build_prompt(spec: dict, case: dict, context: str) -> str:
    # Only natural instructions, the requested task/time, and observed retrieval text.
    return (f"{spec['common_instruction']}\n\n{ANSWER_INSTRUCTION}\n\n"
            f"当前时间：T{case['as_of']}\n\n用户请求：\n{case['request']}\n\n"
            f"可用记忆（工具原文）：\n{context}\n")


def disabled_features() -> list[str]:
    source = FEATURE_SOURCE.read_text(encoding="utf-8")
    block = source.split("pub const RESIDENT_DISABLED_PROVIDER_FEATURES:", 1)[1].split("];", 1)[0]
    return re.findall(r'"([a-z0-9_]+)"', block)


def codex_command(codex: str, workspace: Path, answer: Path) -> list[str]:
    command = [codex, "exec", "--strict-config", "--json", "--ephemeral",
               "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
               "--sandbox", "read-only", "--color", "never", "--model", "gpt-6-astra",
               "-c", 'model_reasoning_effort="medium"', "-c", 'approval_policy="never"',
               "-c", 'web_search="disabled"', "-c", "project_doc_max_bytes=0",
               "-C", str(workspace), "--output-last-message", str(answer)]
    for feature in disabled_features():
        command.extend(["--disable", feature])
    return command + ["-"]


def classify_answer(directory: Path, row: dict) -> None:
    events = []
    row.pop("invalid_jsonl_lines", None)
    for line in (directory / "stdout.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            row["invalid_jsonl_lines"] = row.get("invalid_jsonl_lines", 0) + 1
    def known_diagnostic(event):
        item = event.get("item", {})
        return (event.get("type") == "item.completed" and item.get("type") == "error"
                and item.get("message") == DISABLED_HOST_DIAGNOSTIC)
    row["event_metadata"] = [event for event in events if event.get("type") not in
                             ("item.started", "item.updated", "item.completed")]
    row["known_disabled_host_diagnostics"] = [event for event in events if known_diagnostic(event)]
    row["known_disabled_host_diagnostic_count"] = len(row["known_disabled_host_diagnostics"])
    row["unexpected_item_events"] = [event for event in events
        if event.get("type", "").startswith("item.")
        and event.get("item", {}).get("type") not in ("agent_message", "reasoning")
        and not known_diagnostic(event)]
    row["unexpected_item_event_count"] = len(row["unexpected_item_events"])
    row["observed_item_types"] = sorted({event.get("item", {}).get("type", "missing")
        for event in events if event.get("type", "").startswith("item.")})
    row["completed_turn_count"] = sum(event.get("type") == "turn.completed" for event in events)
    row["execution_error_events"] = [event for event in events if event.get("type") in ("error", "turn.failed")]
    row["actual_model"] = next((event["model"] for event in events if event.get("model")), None)
    row["actual_model_note"] = "null means CLI did not report model; request is not execution proof"
    row["admissible"] = bool(row.get("exit_status") == 0 and (directory / "answer.txt").stat().st_size
        and not row.get("timed_out") and not row["unexpected_item_events"]
        and not row["execution_error_events"] and not row.get("invalid_jsonl_lines")
        and row["completed_turn_count"] > 0 and "agent_message" in row["observed_item_types"])
    row["status"] = "complete" if row["admissible"] else "failed"


def reclassify(input_path: Path, generation_dir: Path, output: Path) -> dict:
    """Reclassify retained output without changing it or invoking any process."""
    original = json.loads((generation_dir / "manifest.json").read_text(encoding="utf-8"))
    if original["phase"] != "generate" or sha(input_path) != original["source_sha256"]["input"]:
        raise TrialError("not a generation manifest, or original input changed")
    for name, expected in original["files_sha256"].items():
        if sha(generation_dir / name) != expected:
            raise TrialError(f"generation artifact changed: {name}")
    fresh_directory(output)
    result = {"trial_id": original["trial_id"], "phase": "reclassify", "cases": [],
              "source_sha256": source_hashes(input_path), "generation_directory": str(generation_dir),
              "original_manifest_sha256": sha(generation_dir / "manifest.json"),
              "original_files_sha256": original["files_sha256"], "provider_calls": 0,
              "reason": "Recognize exact disabled code-mode-host diagnostic; preserve original answer and receipt."}
    for prior in original["cases"]:
        row = dict(prior)
        classify_answer(generation_dir / row["case_id"], row)
        result["cases"].append(row)
        write_json(output / f"{row['case_id']}.json", row)
    result["status"] = "complete" if all(row["admissible"] for row in result["cases"]) else "failed"
    finish(output, result)
    return result


def generate(input_path: Path, capture_dir: Path, output: Path,
             case_id: str | None, timeout: float, codex: str) -> dict:
    spec = read_input(input_path)
    captured = json.loads((capture_dir / "manifest.json").read_text(encoding="utf-8"))
    if captured["status"] != "complete" or sha(input_path) != captured["source_sha256"]["input"]:
        raise TrialError("capture incomplete or input changed since capture")
    for name, expected in captured["files_sha256"].items():
        if sha(capture_dir / name) != expected:
            raise TrialError(f"capture artifact changed: {name}")
    cases = [case for case in spec["cases"] if case_id is None or case["case_id"] == case_id]
    if not cases:
        raise TrialError("unknown case ID")
    fresh_directory(output)
    manifest = {"trial_id": spec["trial_id"], "phase": "generate", "status": "failed",
                "source_sha256": source_hashes(input_path), "cases": [],
                "capture_manifest_sha256": sha(capture_dir / "manifest.json"),
                "requested_model": "gpt-6-astra", "requested_reasoning_effort": "medium",
                "disabled_features": disabled_features(), "retries": 0}
    try:
        env = {key: os.environ[key] for key in CODEX_ENV if key in os.environ}
        version = subprocess.run([codex, "--version"], env=env, capture_output=True,
                                 text=True, timeout=10, check=False)
        manifest["cli_version"] = version.stdout.strip()
        manifest["cli_version_exit"] = version.returncode
        manifest["cli_sha256"] = sha(Path(shutil.which(codex) or codex).resolve())
        (output / "cli-version.stderr").write_text(version.stderr, encoding="utf-8")
        captures = {row["case_id"]: row for row in captured["cases"]}
        for case in cases:
            directory = output / case["case_id"]
            directory.mkdir()
            context = (capture_dir / captures[case["case_id"]]["context_file"]).read_text(encoding="utf-8")
            prompt = build_prompt(spec, case, context)
            (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
            answer = directory / "answer.txt"
            row = {"case_id": case["case_id"], "status": "failed",
                   "prompt_sha256": sha(directory / "prompt.txt"), "timeout_seconds": timeout}
            manifest["cases"].append(row)
            started = time.perf_counter()
            # CLI exposes cwd in model context: neither cwd nor its answer path
            # may contain a case label, even in an ancestor selected by the caller.
            with tempfile.TemporaryDirectory(prefix="ab-answer-", dir="/var/tmp") as neutral:
                workspace = Path(neutral) / "workspace"
                workspace.mkdir()
                provider_answer = Path(neutral) / "answer.txt"
                command = codex_command(codex, workspace, provider_answer)
                row.update(command=command, provider_workspace_initially_empty=True)
                with (directory / "stdout.jsonl").open("wb") as stdout, (directory / "stderr.txt").open("wb") as stderr:
                    try:
                        child = subprocess.Popen(command, cwd=workspace, env=env, stdin=subprocess.PIPE,
                                                 stdout=stdout, stderr=stderr, start_new_session=True)
                        try:
                            child.communicate(prompt.encode("utf-8"), timeout=timeout)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            child.communicate()
                            row["timed_out"] = True
                        row["exit_status"] = child.returncode
                    except Exception as exc:
                        row["error"] = str(exc)
                    finally:
                        row["elapsed_seconds"] = time.perf_counter() - started
                answer.write_bytes(provider_answer.read_bytes() if provider_answer.is_file() else b"")
            row["neutral_workspace_removed"] = not Path(neutral).exists()
            classify_answer(directory, row)
            write_json(directory / "result.json", row)
        manifest["status"] = "complete" if all(row["status"] == "complete" for row in manifest["cases"]) else "failed"
    except Exception as exc:
        manifest["error"] = str(exc)
        raise
    finally:
        finish(output, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("capture", "generate", "reclassify"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--generation", type=Path)
    parser.add_argument("--case")
    parser.add_argument("--binary", type=Path, default=Path("/home/pallasting/.local/bin/agent-bridge.real"))
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    if not 0 < args.timeout <= 180:
        parser.error("timeout must be > 0 and <= 180 seconds")
    if args.phase == "generate" and args.capture is None:
        parser.error("generate requires --capture")
    if args.phase == "reclassify" and args.generation is None:
        parser.error("reclassify requires --generation")
    try:
        if args.phase == "capture":
            result = capture(args.input.resolve(), args.output.absolute(), args.binary.resolve(), args.timeout)
        elif args.phase == "generate":
            result = generate(args.input.resolve(), args.capture.resolve(), args.output.absolute(),
                              args.case, args.timeout, args.codex)
        else:
            result = reclassify(args.input.resolve(), args.generation.resolve(), args.output.absolute())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"], "cases": len(result["cases"])}, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
