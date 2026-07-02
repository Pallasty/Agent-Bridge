#!/usr/bin/env bash
set -euo pipefail

# Copied-DB smoke for the future-row `AB_OUTCOME_VALENCE_IMPORTANCE`
# ingest gate. This script never writes the live store or live presentations
# dir: it copies the source DB into temporary OFF/ON databases, writes fixture
# outcome sidecars into temporary presentation dirs, and invokes a short-lived
# MCP subprocess against each copy.

AB_BIN="${AB_BIN:-$HOME/.local/bin/agent-bridge.real}"
AB_SOURCE_DB="${AB_SOURCE_DB:-${HOME}/.local/share/agent-bridge/state.db}"
AB_KEEP_TMP="${AB_KEEP_TMP:-0}"

if [[ ! -x "$AB_BIN" ]]; then
  echo "AB_BIN is not executable: $AB_BIN" >&2
  exit 2
fi

if [[ ! -f "$AB_SOURCE_DB" ]]; then
  echo "AB_SOURCE_DB does not exist: $AB_SOURCE_DB" >&2
  exit 2
fi

AB_BIN="$AB_BIN" \
AB_SOURCE_DB="$AB_SOURCE_DB" \
AB_KEEP_TMP="$AB_KEEP_TMP" \
python3 - <<'PY'
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time


ab_bin = os.environ["AB_BIN"]
source_db = os.environ["AB_SOURCE_DB"]
keep_tmp = os.environ.get("AB_KEEP_TMP") == "1"


def fail(message, *, packet=None):
    if packet is not None:
        print(json.dumps(packet, ensure_ascii=False, indent=2))
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def backup_db(src, dst):
    src_con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    dst_con = sqlite3.connect(dst)
    try:
        src_con.backup(dst_con)
    finally:
        dst_con.close()
        src_con.close()


def read_rows(db_path, keys):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        quick_check = con.execute("PRAGMA quick_check").fetchone()[0]
        rows = [
            dict(row)
            for row in con.execute(
                f"""
                SELECT key, kind, status, scope, importance, tags AS tags_json
                FROM memories
                WHERE key IN ({",".join("?" for _ in keys)})
                ORDER BY key
                """,
                tuple(keys),
            )
        ]
        edge_count = con.execute(
            f"""
            SELECT COUNT(*)
            FROM memory_edges
            WHERE from_key IN ({",".join("?" for _ in keys)})
               OR to_key IN ({",".join("?" for _ in keys)})
            """,
            tuple(keys) + tuple(keys),
        ).fetchone()[0]
    finally:
        con.close()
    return quick_check, rows, edge_count


def source_key_count(keys):
    con = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    try:
        return con.execute(
            f"SELECT COUNT(*) FROM memories WHERE key IN ({','.join('?' for _ in keys)})",
            tuple(keys),
        ).fetchone()[0]
    finally:
        con.close()


def write_fixture_sidecars(present_dir, suffix):
    os.makedirs(present_dir, exist_ok=True)
    ts = int(time.time())
    records = [
        {
            "artifact_id": f"ab_valence_ingest_{suffix}_approved",
            "ts": ts,
            "intent": "copied-db fixture: approved rendered outcome",
            "action_tool": "present",
            "kind": "fixture",
            "verify_status": "rendered_ok",
            "verify_method": "browser_eval",
            "decision": "approved",
            "embody_status": "not_applicable",
        },
        {
            "artifact_id": f"ab_valence_ingest_{suffix}_neutral",
            "ts": ts - 1,
            "intent": "copied-db fixture: rendered outcome without human decision",
            "action_tool": "present",
            "kind": "fixture",
            "verify_status": "rendered_ok",
            "verify_method": "browser_eval",
            "embody_status": "not_applicable",
        },
        {
            "artifact_id": f"ab_valence_ingest_{suffix}_rejected",
            "ts": ts - 2,
            "intent": "copied-db fixture: rejected rendered outcome",
            "action_tool": "present",
            "kind": "fixture",
            "verify_status": "rendered_ok",
            "verify_method": "browser_eval",
            "decision": "rejected",
            "embody_status": "not_applicable",
        },
    ]
    for rec in records:
        path = os.path.join(present_dir, f"{rec['artifact_id']}.outcome.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, separators=(",", ":"))
    return records


def call_ingest(label, db_path, present_dir, valence_gate):
    env = os.environ.copy()
    env["AGENT_BRIDGE_DB"] = db_path
    env["AGENT_BRIDGE_PRESENTATIONS_DIR"] = present_dir
    env["AGENT_BRIDGE_TOOL_PROFILE"] = "all"
    env["AGENT_BRIDGE_TOOLSET"] = "all"
    env["AGENT_BRIDGE_CLIENT"] = f"codex-valence-ingest-copied-db-{label}"
    env["AGENT_BRIDGE_EMBED_BACKEND"] = "hash"
    env["AGENT_BRIDGE_DIM_GUARD_STRICT"] = "0"
    if valence_gate:
        env["AB_OUTCOME_VALENCE_IMPORTANCE"] = "true"
    else:
        env.pop("AB_OUTCOME_VALENCE_IMPORTANCE", None)

    msgs = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": f"valence-ingest-{label}", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "present_outcomes_ingest",
                "arguments": {
                    "window_secs": 31536000,
                    "limit": 20,
                    "max_writes": 10,
                    "dry_run": False,
                },
            },
        },
    ]
    proc = subprocess.Popen(
        [ab_bin, "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    out, err = proc.communicate(
        "\n".join(json.dumps(m, separators=(",", ":")) for m in msgs) + "\n",
        timeout=60,
    )
    result = None
    for line in out.splitlines():
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("id") == 2:
            result = obj
            break
    if result is None:
        fail(
            f"{label}: no MCP result",
            packet={"stdout_tail": out.splitlines()[-10:], "stderr_tail": err.splitlines()[-10:]},
        )
    if "error" in result:
        fail(f"{label}: MCP error", packet=result)
    text = "".join(
        c.get("text", "")
        for c in result.get("result", {}).get("content", [])
        if c.get("type") == "text"
    )
    try:
        payload = json.loads(text)
    except Exception as exc:
        fail(
            f"{label}: cannot parse tool text as JSON: {exc}",
            packet={"text_head": text[:1000], "stderr_tail": err.splitlines()[-10:]},
        )
    return payload, err.splitlines()[-10:]


tmp = tempfile.mkdtemp(prefix="ab-valence-ingest-copied-db-")
try:
    suffix = f"{int(time.time())}_{os.getpid()}"
    cases = {
        "off": {
            "db": os.path.join(tmp, "off.state.db"),
            "present_dir": os.path.join(tmp, "presentations-off"),
            "gate": False,
        },
        "on": {
            "db": os.path.join(tmp, "on.state.db"),
            "present_dir": os.path.join(tmp, "presentations-on"),
            "gate": True,
        },
    }
    for case in cases.values():
        backup_db(source_db, case["db"])
    records = write_fixture_sidecars(cases["off"]["present_dir"], suffix)
    shutil.copytree(cases["off"]["present_dir"], cases["on"]["present_dir"])
    keys = [f"outcome_{rec['artifact_id']}" for rec in records]
    source_before = source_key_count(keys)

    results = {}
    for label, case in cases.items():
        tool_payload, stderr_tail = call_ingest(
            label, case["db"], case["present_dir"], case["gate"]
        )
        quick_check, rows, edge_count = read_rows(case["db"], keys)
        results[label] = {
            "valence_gate": case["gate"],
            "tool": {
                "schema": tool_payload.get("schema"),
                "dry_run": tool_payload.get("dry_run"),
                "verified_count": tool_payload.get("verified_count"),
                "planned_count": tool_payload.get("planned_count"),
                "written_count": tool_payload.get("written_count"),
                "skipped_over_cap": tool_payload.get("skipped_over_cap"),
                "rows": tool_payload.get("rows", []),
            },
            "quick_check": quick_check,
            "memory_rows": rows,
            "memory_edge_count_for_fixture_keys": edge_count,
            "stderr_tail": stderr_tail,
        }

    source_after = source_key_count(keys)
    def row_by_suffix(label):
        out = {}
        for row in results[label]["memory_rows"]:
            suffix_name = row["key"].split("_")[-1]
            tags = json.loads(row["tags_json"])
            out[suffix_name] = {
                "importance": round(float(row["importance"]), 6),
                "tags": tags,
            }
        return out

    packet = {
        "schema": "agent_bridge.outcome_valence_ingest_copied_db_smoke.v0",
        "read_only_live_store": True,
        "source_db": source_db,
        "tmp_dir": tmp,
        "fixture_artifact_ids": [rec["artifact_id"] for rec in records],
        "source_fixture_key_count_before": source_before,
        "source_fixture_key_count_after": source_after,
        "expected": {
            "off_importances": {
                "approved": 0.5,
                "neutral": 0.5,
                "rejected": 0.5,
            },
            "on_importances": {
                "approved": 0.9,
                "neutral": 0.8,
                "rejected": 0.3,
            },
            "off_tags": {
                "approved": ["valence:+1.000", "valence_class:positive"],
                "neutral": ["valence:+0.600", "valence_class:positive"],
                "rejected": ["valence:-0.400", "valence_class:negative"],
                "applied_stamp": "absent",
            },
            "on_tags": {
                "approved": [
                    "valence:+1.000",
                    "valence_class:positive",
                    "valence_applied:+1.000",
                ],
                "neutral": [
                    "valence:+0.600",
                    "valence_class:positive",
                    "valence_applied:+0.600",
                ],
                "rejected": [
                    "valence:-0.400",
                    "valence_class:negative",
                    "valence_applied:-0.400",
                ],
            },
            "edge_count_for_fixture_keys": 0,
        },
        "results": results,
    }

    off = row_by_suffix("off")
    on = row_by_suffix("on")

    def importance_only(rows):
        return {k: v["importance"] for k, v in rows.items()}

    def has_tags(rows, expected, *, applied_expected):
        for suffix_name, required in expected.items():
            tags = rows.get(suffix_name, {}).get("tags", [])
            for tag in required:
                if tag not in tags:
                    return False
            has_applied = any(t.startswith("valence_applied:") for t in tags)
            if has_applied != applied_expected:
                return False
        return True

    checks = {
        "source_untouched": source_before == 0 and source_after == 0,
        "off_rows_written": results["off"]["tool"]["written_count"] == 3
        and len(results["off"]["memory_rows"]) == 3,
        "on_rows_written": results["on"]["tool"]["written_count"] == 3
        and len(results["on"]["memory_rows"]) == 3,
        "off_importance_default_half": importance_only(off)
        == {"approved": 0.5, "neutral": 0.5, "rejected": 0.5},
        "on_importance_derived": importance_only(on)
        == {"approved": 0.9, "neutral": 0.8, "rejected": 0.3},
        "off_labels_without_apply_stamp": has_tags(
            off,
            {
                "approved": ["valence:+1.000", "valence_class:positive"],
                "neutral": ["valence:+0.600", "valence_class:positive"],
                "rejected": ["valence:-0.400", "valence_class:negative"],
            },
            applied_expected=False,
        ),
        "on_labels_with_birth_apply_stamp": has_tags(
            on,
            {
                "approved": [
                    "valence:+1.000",
                    "valence_class:positive",
                    "valence_applied:+1.000",
                ],
                "neutral": [
                    "valence:+0.600",
                    "valence_class:positive",
                    "valence_applied:+0.600",
                ],
                "rejected": [
                    "valence:-0.400",
                    "valence_class:negative",
                    "valence_applied:-0.400",
                ],
            },
            applied_expected=True,
        ),
        "no_fixture_edges": results["off"]["memory_edge_count_for_fixture_keys"] == 0
        and results["on"]["memory_edge_count_for_fixture_keys"] == 0,
        "quick_check_ok": results["off"]["quick_check"] == "ok"
        and results["on"]["quick_check"] == "ok",
    }
    packet["checks"] = checks
    packet["verdict"] = "PASS" if all(checks.values()) else "FAIL"

    print(json.dumps(packet, ensure_ascii=False, indent=2))
    if packet["verdict"] != "PASS":
        sys.exit(1)
finally:
    if not keep_tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"kept_tmp_dir={tmp}", file=sys.stderr)
PY
