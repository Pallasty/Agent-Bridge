#!/usr/bin/env python3
"""Isolated Dream identity CLI assertions and baseline/candidate comparison.

Use --baseline-only before the candidate exists. JSON comparison validates the
two adjacent windows against the invocation clock before normalizing exactly
their four bounds; all other stdout/stderr bytes stay intact. SQLite evidence
compares business rows, never database/index/WAL byte identity.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
from cli_fixture_paths import database_path
import time


DAY = 86400
TABLES = ["mcp_tool_calls", "forum_threads", "forum_posts", "memories"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def setup(root):
    for path in root.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    for name in ["home", "config", "data", "cache", "state", "runtime", "tmp"]:
        (root / name).mkdir(mode=0o700)
    (root / "empty-creds").write_bytes(b"")
    db = database_path(root)
    db.parent.mkdir(mode=0o700, parents=True)
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC", "RUST_LOG": "off",
           "HOME": str(root / "home"), "TMPDIR": str(root / "tmp"),
           "XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data"),
           "XDG_CACHE_HOME": str(root / "cache"), "XDG_STATE_HOME": str(root / "state"),
           "XDG_RUNTIME_DIR": str(root / "runtime"),
           "AGENT_BRIDGE_STATE_DIR": str(root / "state"),
           "AGENT_BRIDGE_CREDS_FILE": str(root / "empty-creds"),
           "AGENT_BRIDGE_EMBED_BACKEND": "hash"}
    return env, db


def invoke(binary, root, env, argv):
    start = time.time()
    run = subprocess.run(["agent-bridge", *argv], executable=str(binary), cwd=root,
                         env=env, capture_output=True, timeout=30)
    return run, start, time.time()


def business(db):
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
        result = {}
        for table in TABLES:
            cursor = connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
            columns = [column[0] for column in cursor.description]
            result[table] = [{key: {"blob_sha256": digest(value), "bytes": len(value)}
                             if isinstance(value, bytes) else value
                             for key, value in zip(columns, row)} for row in cursor]
        return result


def filesystem(root):
    result = {}
    db_key = str(database_path(root).relative_to(root.resolve()))
    for path in sorted(root.rglob("*")):
        key = str(path.relative_to(root))
        if key in {db_key, db_key + "-wal", db_key + "-shm"}:
            continue
        result[key] = {"kind": "directory" if path.is_dir() else "file",
                       "mode": stat.S_IMODE(path.stat().st_mode)}
        if path.is_file():
            result[key]["sha256"] = digest(path.read_bytes())
    return result


def expected_window(which, mode):
    empty = {"tool_calls_total": 0, "tool_calls_ok": 0, "top_tools": [], "forum_posts": 0,
             "forum_kinds": [], "forum_avg_body_len": 0.0, "memory_saves": 0}
    if mode == "empty" or (mode == "current-only" and which == "prior") or (
            mode == "prior-only" and which == "current"):
        return empty
    if which == "current":
        return {"tool_calls_total": 4, "tool_calls_ok": 3, "top_tools": [["alpha", 3], ["beta", 1]],
                "forum_posts": 2, "forum_kinds": [["decision", 1], ["msg", 1]],
                "forum_avg_body_len": 3.0, "memory_saves": 2}
    return {"tool_calls_total": 3, "tool_calls_ok": 1, "top_tools": [["alpha", 2], ["gamma", 1]],
            "forum_posts": 1, "forum_kinds": [["observation", 1]],
            "forum_avg_body_len": 6.0, "memory_saves": 1}


def seed(db, mode, anchor, days):
    with sqlite3.connect(db) as connection:
        connection.execute("INSERT INTO forum_threads (board,title,created_by,created_at,last_post_at) VALUES (?,?,?,?,?)",
                           ("fixture", "fixture", "fixture", anchor, anchor))
        for which, offset in [("current", days * DAY // 2), ("prior", days * DAY * 3 // 2),
                              ("outside-old", days * DAY * 3), ("outside-future", -DAY)]:
            ts = anchor - offset
            if which == "current" and mode == "prior-only" or which == "prior" and mode == "current-only":
                continue
            tools = [("alpha", 1), ("alpha", 1), ("alpha", 0), ("beta", 1)] if which == "current" else (
                [("alpha", 1), ("alpha", 0), ("gamma", 0)] if which == "prior" else [("outside", 1)])
            for name, ok in tools:
                connection.execute("INSERT INTO mcp_tool_calls (ts,tool_name,ok,duration_ms) VALUES (?,?,?,?)",
                                   (ts, name, ok, 1))
            posts = [("decision", "甲乙"), ("msg", "abcd")] if which == "current" else [("observation", "abcdef")]
            for kind, body in posts:
                connection.execute("INSERT INTO forum_posts (thread_id,author,kind,body,created_at) VALUES (1,?,?,?,?)",
                                   ("fixture", kind, body, ts))
            for index in range(2 if which == "current" else 1):
                connection.execute("INSERT INTO memories (key,kind,content,created_at,updated_at,last_accessed_at) VALUES (?,?,?,?,?,?)",
                                   (f"fixture-{which}-{index}", "fact", "fixture", ts, ts, ts))


def normalize_json(stdout, days, mode, start, end):
    payload = json.loads(stdout)
    require(set(payload) == {"days", "current", "prior"} and payload["days"] == days, "JSON top-level contract")
    current, prior = payload["current"], payload["prior"]
    now = current["window_end"]
    require(type(now) is int and int(start) <= now <= int(end), "JSON window end outside invocation")
    expected_bounds = {"current": (now - days * DAY, now), "prior": (now - 2 * days * DAY, now - days * DAY)}
    observed = {}
    for label, window in [("current", current), ("prior", prior)]:
        bounds = expected_bounds[label]
        require(type(window["window_start"]) is int and type(window["window_end"]) is int and
                (window["window_start"], window["window_end"]) == bounds, "windows must be adjacent and exactly N days")
        observed[label] = dict(window_start=bounds[0], window_end=bounds[1])
        values = {key: value for key, value in window.items() if key not in ["window_start", "window_end"]}
        require(values == expected_window(label, mode), f"{label} aggregate contract changed: {values}")
    # Preserve all formatting and bytes outside these four validated integers.
    normalized, count = re.subn(rb'("window_(?:start|end)": )-?\d+', rb'\1"<validated-window-bound>"', stdout)
    require(count == 4, "expected precisely four serialized window bound fields")
    return normalized, observed


def cases():
    def case(name, argv, **kwargs):
        return {"name": name, "argv": argv, "mode": "none", "exit": 0, "days": 7, **kwargs}
    for name, argv in [("root-help", ["--help"]), ("dream-help", ["dream", "--help"]),
                       ("identity-help", ["dream", "identity", "--help"])]:
        yield case(name, argv)
    for days in ["-1", "not-a-number", "4294967296"]:
        yield case("invalid-days-" + days, ["dream", "identity", "--days", days], exit=2)
    for json_flag in [[], ["--json"]]:
        suffix = "-json" if json_flag else "-text"
        for mode in ["none", "open-blocked"]:
            yield case("zero-days-" + mode + suffix, ["dream", "identity", "--days", "0", *json_flag],
                       mode=mode, exit=1, error="--days must be ≥ 1", no_open=True)
        yield case("default-empty" + suffix, ["dream", "identity", *json_flag], mode="empty")
        yield case("one-day-empty" + suffix, ["dream", "identity", "--days", "1", *json_flag], mode="empty", days=1)
        for days in [1, 7]:
            yield case(f"populated-{days}-days" + suffix, ["dream", "identity", "--days", str(days), *json_flag],
                       mode="populated", days=days)
        for mode in ["current-only", "prior-only"]:
            yield case(mode + suffix, ["dream", "identity", "--days", "1", *json_flag], mode=mode, days=1)
        for mode in ["open-blocked", "open-corrupt", "query-current", "query-prior"]:
            yield case(mode + suffix, ["dream", "identity", "--days", "1", *json_flag], mode=mode, days=1, exit=1,
                       error="open state.db at" if mode.startswith("open-") else "identity_window " +
                       ("cur" if mode == "query-current" else "prior"))


def execute(binary, root, template, case, anchor):
    env, db = setup(root)
    mode = case["mode"]
    readable = mode in ["empty", "populated", "current-only", "prior-only", "query-current", "query-prior"]
    if readable:
        shutil.copyfile(template, db)
        if mode in ["populated", "current-only", "prior-only"]:
            seed(db, mode, anchor, case["days"])
        elif mode.startswith("query-"):
            ts = anchor - (DAY // 2 if mode == "query-current" else DAY * 3 // 2)
            with sqlite3.connect(db) as connection:
                connection.execute("INSERT INTO mcp_tool_calls (ts,tool_name,ok,duration_ms) VALUES (?,?,1,1)",
                                   (ts, sqlite3.Binary(b"fixture invalid UTF8 \xff")))
    elif mode == "open-blocked":
        db.parent.rmdir()
        db.parent.write_bytes(b"fixture parent obstruction\n")
    elif mode == "open-corrupt":
        db.write_bytes(b"fixture is not SQLite\n")
    before = business(db) if readable else None
    before_fs = filesystem(root)
    run, start, end = invoke(binary, root, env, case["argv"])
    require(run.returncode == case["exit"], f"exit {run.returncode}, expected {case['exit']}: {run.stderr!r}")
    after = business(db) if readable else None
    require(before == after, "read-only identity changed business rows")
    changes = {key: value for key, value in filesystem(root).items() if before_fs.get(key) != value}
    deleted = sorted(set(before_fs) - set(filesystem(root)))
    require(not deleted, f"deleted fixture files: {deleted}")
    lock = str(db.relative_to(root.resolve())) + ".init.lock"
    if lock in changes:
        require(changes.pop(lock) == {"kind": "file", "mode": 0o600, "sha256": digest(b"")}, "unexpected init lock")
    require(not changes, f"unexpected fixture effects: {changes}")
    if mode == "none" or case.get("no_open") or mode == "open-blocked":
        require(not db.exists() and not (db.parent / "state.db.init.lock").exists(), "DB opened before validation")
    stdout = run.stdout
    bounds = None
    if case["exit"] != 0:
        require(stdout == b"", "failure emitted success stdout")
        if "error" in case:
            require(case["error"].encode() in run.stderr, "required error context absent")
    elif readable:
        require(run.stderr == b"", "success emitted stderr")
        require(abs(start - anchor) < DAY // 4, "relative seed aged beyond bounded fixture lifetime")
        if "--json" in case["argv"]:
            stdout, bounds = normalize_json(stdout, case["days"], mode, start, end)
        else:
            expected_header = f"# v21 — Identity continuity (last {case['days']}d vs prior {case['days']}d)\nDB: {db}\n\n"
            require(stdout.startswith(expected_header.encode()), "text heading/default days/DB path changed")
            text = stdout.decode()
            for heading in ["## Tool calls\n", "## Top tools (current window)\n", "## Forum tone\n", "## Memory\n"]:
                require(text.count(heading) == 1, "text section missing or duplicated")
            cur, prior = expected_window("current", mode), expected_window("prior", mode)
            for label, key in [("total", "tool_calls_total"), ("posts", "forum_posts"), ("saves", "memory_saves")]:
                require(re.search(r"  " + label + r" +: +" + str(cur[key]) + r" +prior +" + str(prior[key]) + r" +", text),
                        "text count assertion failed: " + label)
    comparable = (run.returncode, stdout, run.stderr, after)
    evidence = {"exit_code": run.returncode, "stdout_sha256": digest(run.stdout), "stderr_sha256": digest(run.stderr),
                "compared_stdout_sha256": digest(stdout), "business_rows_unchanged": before == after,
                "business_rows": after, "invocation_start_unix": start, "invocation_end_unix": end,
                "validated_window_bounds": bounds}
    return comparable, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.baseline_only and args.candidate is None:
        parser.error("--candidate is required unless --baseline-only is selected")
    binaries = [args.baseline.resolve()] + ([] if args.baseline_only else [args.candidate.resolve()])
    guarded = [*binaries, Path(__file__).with_name('cli_fixture_paths.py'), Path(__file__)]
    hashes_before = [digest(path.read_bytes()) for path in guarded]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix="dream-identity-parity-", dir=args.output.parent) as temp:
        temp = Path(temp).resolve()
        root = temp / "fixture"
        root.mkdir(mode=0o700)
        env, db = setup(root)
        run, start, end = invoke(binaries[0], root, env, ["dream", "identity", "--days", "1", "--json"])
        require(run.returncode == 0 and not run.stderr, "baseline empty database initialization failed")
        normalize_json(run.stdout, 1, "empty", start, end)
        require(all(not rows for rows in business(db).values()), "fresh database contains business rows")
        template = temp / "empty-template.db"
        with sqlite3.connect(db) as source, sqlite3.connect(template) as destination:
            source.backup(destination)
        for case in cases():
            record = {"case": case["name"], "argv": ["agent-bridge", *case["argv"]],
                      "evidence_type": "validated_window_json_and_business_rows" if
                      "--json" in case["argv"] and case["exit"] == 0 else "exact_cli_and_business_rows"}
            anchor = int(time.time())
            try:
                baseline, evidence = execute(binaries[0], root, template, case, anchor)
                record.update(baseline=evidence, passed=True)
                if not args.baseline_only:
                    candidate, evidence = execute(binaries[1], root, template, case, anchor)
                    record.update(candidate=evidence, passed=baseline == candidate)
                    if not record["passed"]:
                        record["component_equal"] = [a == b for a, b in zip(baseline, candidate)]
            except (AssertionError, OSError, sqlite3.Error, subprocess.TimeoutExpired, ValueError) as error:
                record.update(passed=False, error=str(error))
            records.append(record)
            if not record["passed"]:
                print(case["name"], "FAIL", record.get("error", record.get("component_equal")))
    hashes_after = [digest(path.read_bytes()) for path in guarded]
    report = {"schema": "agent_bridge.dream_identity_cli_parity.v1", "comparison_performed": not args.baseline_only,
              "baseline_sha256": hashes_before[0], "candidate_sha256": None if args.baseline_only else hashes_before[1],
              "script_sha256": hashes_before[-1], "inputs_unchanged_during_run": hashes_before == hashes_after,
              "path_helper_sha256": hashes_before[-2],
              "passed": sum(row["passed"] for row in records), "total": len(records),
              "business_tables": TABLES, "excluded": ["SQLite byte identity", "real credentials/configuration/database",
                                                       "uncontrolled query-boundary timing"], "cases": records}
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{report['passed']}/{report['total']} Dream identity {'baseline assertions' if args.baseline_only else 'CLI parity'} passed")
    return 0 if report["passed"] == report["total"] and report["inputs_unchanged_during_run"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
