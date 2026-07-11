#!/usr/bin/env bash
set -euo pipefail

# Copied-DB MCP smoke for the gated correction co-surface read path.
# The script never points MCP memory_search at the live store: it copies the
# source DB into two temporary DBs, runs one short-lived MCP subprocess with
# AGENT_BRIDGE_CORRECTION_COSURFACE unset and one with it enabled, and compares
# key/rank level results only.

export AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=eval

AB_BIN="${AB_BIN:-$HOME/.local/bin/agent-bridge.real}"
AB_SOURCE_DB="${AB_SOURCE_DB:-${HOME}/.local/share/agent-bridge/state.db}"
AB_MAX_CORRECTIONS="${AB_MAX_CORRECTIONS:-20}"
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
AB_MAX_CORRECTIONS="$AB_MAX_CORRECTIONS" \
AB_KEEP_TMP="$AB_KEEP_TMP" \
python3 - <<'PY'
import json
import os
import select
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time


ab_bin = os.environ["AB_BIN"]
source_db = os.environ["AB_SOURCE_DB"]
max_corrections = max(1, int(os.environ.get("AB_MAX_CORRECTIONS", "20")))
keep_tmp = os.environ.get("AB_KEEP_TMP") == "1"


def fail(message, *, packet=None):
    if packet is not None:
        print(json.dumps(packet, ensure_ascii=False, indent=2), file=sys.stdout)
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def read_correction_edges(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        quick_check = con.execute("PRAGMA quick_check").fetchone()[0]
        rows = [
            dict(row)
            for row in con.execute(
                """
                SELECT e.from_key AS correction_key,
                       e.to_key AS target_key,
                       e.weight AS edge_weight,
                       e.created_at AS edge_created_at
                FROM memory_edges e
                JOIN memories c
                  ON c.key = e.from_key
                 AND c.status = 'active'
                 AND c.kind = 'feedback'
                JOIN memories t
                  ON t.key = e.to_key
                 AND t.status = 'active'
                WHERE e.edge_type = 'corrects'
                  AND e.from_key LIKE 'correction:%'
                ORDER BY e.from_key
                LIMIT ?
                """,
                (max_corrections,),
            )
        ]
    finally:
        con.close()
    return quick_check, rows


def backup_db(src, dst):
    src_con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    dst_con = sqlite3.connect(dst)
    try:
        src_con.backup(dst_con)
    finally:
        dst_con.close()
        src_con.close()


class McpClient:
    def __init__(self, label, db_path, cosurface_enabled):
        self.label = label
        self.db_path = db_path
        self.next_id = 1
        env = os.environ.copy()
        env["AGENT_BRIDGE_DB"] = db_path
        env["AGENT_BRIDGE_TOOL_PROFILE"] = "all"
        env["AGENT_BRIDGE_TOOLSET"] = "all"
        env["AGENT_BRIDGE_CLIENT"] = f"codex-correction-cosurface-copied-db-{label}"
        env["AGENT_BRIDGE_EMBED_BACKEND"] = "hash"
        env["AGENT_BRIDGE_DIM_GUARD_STRICT"] = "0"
        if cosurface_enabled:
            env["AGENT_BRIDGE_CORRECTION_COSURFACE"] = "1"
        else:
            env.pop("AGENT_BRIDGE_CORRECTION_COSURFACE", None)
        self.proc = subprocess.Popen(
            [ab_bin, "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self._initialize()

    def close(self):
        proc = self.proc
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass

    def stderr_tail(self):
        try:
            if self.proc.stderr:
                return self.proc.stderr.read()[-4000:]
        except Exception:
            return ""
        return ""

    def _send(self, obj):
        if self.proc.stdin is None:
            raise RuntimeError("MCP stdin is closed")
        self.proc.stdin.write(json.dumps(obj, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def _read_until(self, ids, timeout=30):
        if self.proc.stdout is None:
            return {}
        deadline = time.time() + timeout
        found = {}
        wanted = set(ids)
        while time.time() < deadline and wanted - set(found):
            remaining = max(0.0, deadline - time.time())
            ready, _, _ = select.select([self.proc.stdout], [], [], min(0.25, remaining))
            if not ready:
                if self.proc.poll() is not None:
                    break
                continue
            line = self.proc.stdout.readline()
            if not line:
                if self.proc.poll() is not None:
                    break
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            msg_id = msg.get("id")
            if msg_id in wanted:
                found[msg_id] = msg
        return found

    def _rpc(self, method, params=None, *, timeout=30):
        msg_id = self.next_id
        self.next_id += 1
        payload = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)
        messages = self._read_until({msg_id}, timeout=timeout)
        if msg_id not in messages:
            raise RuntimeError(f"{self.label}: missing response for {method}")
        response = messages[msg_id]
        if "error" in response:
            raise RuntimeError(f"{self.label}: {method} error: {response['error']}")
        return response

    def _initialize(self):
        init_id = self.next_id
        self.next_id += 1
        list_id = self.next_id
        self.next_id += 1
        self._send(
            {
                "jsonrpc": "2.0",
                "id": init_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": f"correction-cosurface-copied-db-{self.label}",
                        "version": "0",
                    },
                },
            }
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        self._send({"jsonrpc": "2.0", "id": list_id, "method": "tools/list", "params": {}})
        messages = self._read_until({init_id, list_id})
        if list_id not in messages:
            raise RuntimeError(f"{self.label}: missing tools/list response")
        if "error" in messages[list_id]:
            raise RuntimeError(f"{self.label}: tools/list error: {messages[list_id]['error']}")
        tools = (messages[list_id].get("result") or {}).get("tools") or []
        if not any(tool.get("name") == "memory_search" for tool in tools):
            raise RuntimeError(f"{self.label}: memory_search missing from tools/list")

    def memory_search(self, query, limit, exclude_kinds=None):
        args = {"query": query, "mode": "fts", "limit": limit}
        if exclude_kinds:
            args["exclude_kinds"] = list(exclude_kinds)
        response = self._rpc(
            "tools/call",
            {"name": "memory_search", "arguments": args},
            timeout=45,
        )
        result = response.get("result") or {}
        if result.get("isError"):
            raise RuntimeError(f"{self.label}: memory_search returned isError")
        for item in result.get("content") or []:
            if item.get("type") == "text":
                try:
                    data = json.loads(item.get("text") or "[]")
                except Exception as exc:
                    raise RuntimeError(f"{self.label}: memory_search text is not JSON: {exc}")
                if not isinstance(data, list):
                    raise RuntimeError(f"{self.label}: memory_search JSON is not a list")
                return data
        raise RuntimeError(f"{self.label}: memory_search response has no text JSON")


def hit_key(hit):
    record = hit.get("record") or {}
    return record.get("key") or hit.get("key")


def hit_kind(hit):
    record = hit.get("record") or {}
    return record.get("kind") or hit.get("kind")


def summarize_hits(hits):
    keys = [hit_key(hit) for hit in hits]
    kinds = [hit_kind(hit) for hit in hits]
    return {
        "keys": keys,
        "kinds": kinds,
        "len": len(hits),
    }


def rank(keys, key):
    try:
        return keys.index(key) + 1
    except ValueError:
        return None


def count_key(keys, key):
    return sum(1 for item in keys if item == key)


def evaluate_case(edge, label, off_hits, on_hits, limit, exclude_kinds):
    target = edge["target_key"]
    correction = edge["correction_key"]
    off = summarize_hits(off_hits)
    on = summarize_hits(on_hits)
    off_keys = off["keys"]
    on_keys = on["keys"]
    off_target = rank(off_keys, target)
    on_target = rank(on_keys, target)
    off_correction = rank(off_keys, correction)
    on_correction = rank(on_keys, correction)
    status = "pass"
    reasons = []

    if len(on_keys) > limit:
        status = "fail"
        reasons.append("enabled_page_exceeds_limit")
    if on_target is None:
        status = "fail"
        reasons.append("target_missing_enabled")
    if off_target is None:
        status = "fail"
        reasons.append("target_missing_baseline")
    if count_key(on_keys, correction) > 1:
        status = "fail"
        reasons.append("correction_duplicated_enabled")

    if exclude_kinds and "feedback" in exclude_kinds:
        if on_correction is not None:
            status = "fail"
            reasons.append("feedback_correction_leaked_through_exclude")
    elif limit == 1:
        if len(on_keys) != 1:
            status = "fail"
            reasons.append("limit_one_page_size_changed")
        if on_correction is not None and on_correction != on_target:
            status = "fail"
            reasons.append("limit_one_surfaced_extra_correction")
    elif off_correction is None:
        if on_target is not None and on_target < limit:
            if on_correction != on_target + 1:
                status = "fail"
                reasons.append("correction_not_inserted_after_visible_target")
    else:
        if count_key(on_keys, correction) != 1:
            status = "fail"
            reasons.append("already_visible_correction_missing_or_duplicated")

    effect = "none"
    if status == "pass":
        if exclude_kinds and "feedback" in exclude_kinds:
            effect = "feedback_excluded"
        elif limit == 1:
            effect = "limit_one_preserved"
        elif off_correction is None and on_correction == (on_target or 0) + 1:
            effect = "inserted_after_original"
        elif off_correction is not None:
            effect = "already_visible_no_duplicate"

    return {
        "label": label,
        "query_key": target,
        "limit": limit,
        "exclude_kinds": exclude_kinds or [],
        "target_key": target,
        "correction_key": correction,
        "off_target_rank": off_target,
        "off_correction_rank": off_correction,
        "on_target_rank": on_target,
        "on_correction_rank": on_correction,
        "off_len": off["len"],
        "on_len": on["len"],
        "on_correction_count": count_key(on_keys, correction),
        "effect": effect,
        "status": status,
        "reasons": reasons,
        "off_keys": off_keys,
        "on_keys": on_keys,
    }


quick_check, edges = read_correction_edges(source_db)
if quick_check != "ok":
    fail(f"source DB quick_check was {quick_check!r}")
if not edges:
    fail("no active correction edges found")

tmp_root = tempfile.mkdtemp(prefix="ab-correction-cosurface-copied-db-")
off_db = os.path.join(tmp_root, "state.off.db")
on_db = os.path.join(tmp_root, "state.on.db")
clients = []
started_at = int(time.time())

packet = {
    "schema": "agent_bridge.correction_cosurface.copied_db_smoke.v0",
    "status": "started",
    "source_db": source_db,
    "tmp_root": tmp_root if keep_tmp else None,
    "started_at": started_at,
    "source_quick_check": quick_check,
    "correction_edge_count": len(edges),
    "live_store_writes": False,
    "runtime_default_changed": False,
    "raw_memory_content_included": False,
    "cases": [],
}

try:
    backup_db(source_db, off_db)
    backup_db(source_db, on_db)
    off = McpClient("off", off_db, False)
    on = McpClient("on", on_db, True)
    clients = [off, on]
    for edge in edges:
        target = edge["target_key"]
        scenarios = [
            ("exact_limit10", 10, []),
            ("exact_limit2", 2, []),
            ("exact_limit1", 1, []),
            ("exact_limit10_exclude_feedback", 10, ["feedback"]),
        ]
        for label, limit, exclude_kinds in scenarios:
            off_hits = off.memory_search(target, limit, exclude_kinds)
            on_hits = on.memory_search(target, limit, exclude_kinds)
            packet["cases"].append(
                evaluate_case(edge, label, off_hits, on_hits, limit, exclude_kinds)
            )
finally:
    for client in clients:
        client.close()
    if not keep_tmp:
        shutil.rmtree(tmp_root, ignore_errors=True)

failures = [case for case in packet["cases"] if case["status"] != "pass"]
packet["status"] = "pass" if not failures else "fail"
packet["finished_at"] = int(time.time())
packet["summary"] = {
    "case_count": len(packet["cases"]),
    "pass_count": len(packet["cases"]) - len(failures),
    "fail_count": len(failures),
    "effects": {},
}
for case in packet["cases"]:
    effect = case["effect"]
    packet["summary"]["effects"][effect] = packet["summary"]["effects"].get(effect, 0) + 1

print(json.dumps(packet, ensure_ascii=False, indent=2))
if failures:
    sys.exit(1)
PY
