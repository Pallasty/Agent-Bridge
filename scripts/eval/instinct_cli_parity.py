#!/usr/bin/env python3
"""Bounded Instinct CLI parity against reset, private local fixtures.

Exact cases compare complete exit/stdout/stderr bytes and filesystem effects.
Memory writes additionally validate the persisted business rows and receipt;
only their explicitly named invocation timestamps are normalized, after range
checks. SQLite bytes are never an equivalence claim. Dynamic successful JSON
plans and timestamped packet/rotation paths belong to fixed-Value renderer
tests, not this real-clock comparison.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import time


COMMANDS = ["candidates", "review-packet", "review-decision", "memory-preflight",
            "memory-write", "review-status", "review-inbox", "review-context", "rotate-log"]
SCHEMA = "agent_bridge.instinct_observer.phase1_"
CANDIDATE = "instinct-candidate-0001"
MEMORY_KEY = "s18-parity-fixture-lesson"
MEMORY_BODY = "Inspect the bounded fixture before changing its result."
PROMPT = "Actually, inspect the fixture before changing its result."
SESSION = "11111111-2222-3333-4444-555555555555"
FIXED_TIME = 1_780_747_000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def setup(root, mode):
    for path in root.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    for name in ["home", "config", "data", "cache", "state", "runtime", "tmp",
                 "observer", "review", "db", "empty"]:
        (root / name).mkdir(mode=0o700)
    (root / "empty-creds").write_bytes(b"")
    (root / "not-a-directory").write_bytes(b"fixture obstruction\n")
    (root / "malformed.json").write_bytes(b"not json\n")
    write_json(root / "wrong-schema.json", {"schema": "fixture.wrong.v0"})
    observations = [{"ts": FIXED_TIME + i, "sid": SESSION if i == 0 else
                     f"11111111-2222-3333-4444-{i:012d}",
                     "ev": "UserPromptSubmit", "prompt": PROMPT} for i in range(5)]
    (root / "observer/observations.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in observations), encoding="utf-8")
    candidate = {"candidate_id": CANDIDATE, "kind": "correction_prompt",
                 "review_state": "pending_human_review", "session_id": SESSION,
                 "event_at_unix": FIXED_TIME, "matched_cues": ["actually"],
                 "prompt_chars": len(PROMPT), "raw_prompt_included": False,
                 "requires_local_log_lookup": True}
    packet = {"schema": SCHEMA + "review_packet.v0", "packet_id": "fixture-packet",
              "generated_at_unix": FIXED_TIME, "candidate_count": 1, "written": True,
              "candidate_preview": {"candidates": [candidate]}}
    write_json(root / "review/packet.json", packet)
    decision = {"schema": SCHEMA + "review_decision.v0", "decision_id": "fixture-decision",
                "generated_at_unix": FIXED_TIME + 1, "candidate_id": CANDIDATE,
                "decision": "approve", "reviewer": "fixture-reviewer"}
    write_json(root / "review/decisions.jsonl", decision)
    preflight = {"schema": SCHEMA + "memory_write_preflight.v0",
                 "preflight_id": "fixture-preflight", "candidate_id": CANDIDATE,
                 "generated_at_unix": FIXED_TIME + 2, "written": True,
                 "ready_for_separate_memory_write": True,
                 "memory_draft": {"key": MEMORY_KEY, "kind": "lesson", "body": MEMORY_BODY}}
    write_json(root / "review/ready.json", preflight)
    preflight["ready_for_separate_memory_write"] = False
    write_json(root / "review/blocked.json", preflight)
    write_json(root / "review/receipts.jsonl", {
        "schema": SCHEMA + "memory_write_receipt.v0", "generated_at_unix": FIXED_TIME + 3,
        "receipt_id": "fixture-receipt", "memory_key": "historical-fixture-key"})
    if mode == "empty-observations":
        (root / "observer/observations.jsonl").unlink()
    elif mode == "bad-decisions":
        (root / "review/decisions.jsonl").write_bytes(b"not json\n")
    elif mode == "receipt-failure":
        (root / "write-receipt.jsonl").mkdir(mode=0o700)
    # Deliberate allowlist: never inherit provider credentials, real AB paths,
    # desktop sockets, or a user's environment. The existing empty credentials
    # file prevents the loader from falling through to its machine defaults.
    return {
        "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC", "RUST_LOG": "off",
        "HOME": str(root / "home"), "TMPDIR": str(root / "tmp"),
        "XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data"),
        "XDG_CACHE_HOME": str(root / "cache"), "XDG_STATE_HOME": str(root / "state"),
        "XDG_RUNTIME_DIR": str(root / "runtime"),
        "AGENT_BRIDGE_STATE_DIR": str(root / "state"),
        "AGENT_BRIDGE_CREDS_FILE": str(root / "empty-creds"),
        "AGENT_BRIDGE_EMBED_BACKEND": "hash",
        "AB_INSTINCT_OBSERVER_LOG": str(root / "observer/observations.jsonl"),
        "AB_INSTINCT_REVIEW_DIR": str(root / "review"),
        "AB_INSTINCT_REVIEW_DECISIONS": str(root / "review/decisions.jsonl"),
        "AB_INSTINCT_MEMORY_WRITE_RECEIPTS": str(root / "review/receipts.jsonl"),
    }


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        entry = {"mode": stat.S_IMODE(path.lstat().st_mode)}
        if path.is_symlink():
            entry.update(kind="symlink", target=str(path.readlink()))
        elif path.is_dir():
            entry["kind"] = "directory"
        else:
            entry.update(kind="file", sha256=digest(path.read_bytes()))
        result[str(path.relative_to(root))] = entry
    return result


def cases(root):
    def case(name, args, mode="normal", expected=0, effect="none", contains=None):
        return {"name": name, "args": args, "mode": mode, "expected_exit": expected,
                "effect": effect, "contains": contains}

    yield case("root-help", ["--help"])
    yield case("instinct-help", ["instinct", "--help"])
    for command in COMMANDS:
        yield case(command + "-help", ["instinct", command, "--help"])
        yield case(command + "-invalid-option", ["instinct", command, "--fixture-invalid"],
                   expected=2)
    packet = str(root / "review/packet.json")
    identity = ["--packet-json", packet, "--candidate-id", CANDIDATE]
    db_args = ["--db-path", str(root / "db/state.sqlite"),
               "--receipt-out", str(root / "write-receipt.jsonl")]
    for fmt in [[], ["--json"]]:
        suffix = "-json" if fmt else "-text"
        for mode in ["normal", "empty-observations"]:
            yield case("candidates-" + mode + suffix,
                       ["instinct", "candidates", "--limit", "3", *fmt], mode)
        yield case("review-status" + suffix, ["instinct", "review-status", *fmt])
        for limit in [0, 1]:
            yield case(f"review-inbox-limit-{limit}" + suffix,
                       ["instinct", "review-inbox", "--limit", str(limit), *fmt])
        for excerpt in [[], ["--include-local-excerpt"]]:
            yield case("review-context-" + ("excerpt" if excerpt else "redacted") + suffix,
                       ["instinct", "review-context", *identity, *excerpt, *fmt],
                       contains=PROMPT if excerpt else None)
        for command in ["review-decision", "memory-preflight", "review-context"]:
            extra = ["--decision", "approve"] if command == "review-decision" else []
            for bad in ["missing.json", "malformed.json", "wrong-schema.json"]:
                yield case(command + "-" + bad + suffix,
                           ["instinct", command, "--packet-json", str(root / bad),
                            "--candidate-id", CANDIDATE, *extra, *fmt], expected=1)
            yield case(command + "-missing-candidate" + suffix,
                       ["instinct", command, "--packet-json", packet,
                        "--candidate-id", "absent", *extra, *fmt], expected=1)
        yield case("review-packet-write-obstructed" + suffix,
                   ["instinct", "review-packet", "--write", "--out-dir",
                    str(root / "not-a-directory"), *fmt], expected=1)
        yield case("review-inbox-missing" + suffix,
                   ["instinct", "review-inbox", "--review-dir", str(root / "empty"), *fmt],
                   expected=1)
        yield case("review-status-malformed-decisions" + suffix,
                   ["instinct", "review-status", *fmt], "bad-decisions", expected=1)
        for bad in ["missing.json", "malformed.json", "wrong-schema.json"]:
            yield case("memory-write-" + bad + suffix,
                       ["instinct", "memory-write", "--preflight-json", str(root / bad),
                        *db_args, "--write", *fmt], expected=1)
        yield case("memory-write-blocked" + suffix,
                   ["instinct", "memory-write", "--preflight-json",
                    str(root / "review/blocked.json"), *db_args, "--write", *fmt], expected=1)
    # These text renderers omit the runtime clock; compare their bytes exactly.
    for decision in ["approve", "reject", "defer"]:
        yield case("review-decision-preview-" + decision,
                   ["instinct", "review-decision", *identity, "--decision", decision])
    for ready in ["ready", "blocked"]:
        yield case("memory-write-preview-" + ready,
                   ["instinct", "memory-write", "--preflight-json",
                    str(root / f"review/{ready}.json"), *db_args])
    for mode in ["normal", "receipt-failure"]:
        yield case("memory-write-" + ("saved" if mode == "normal" else mode),
                   ["instinct", "memory-write", "--preflight-json",
                    str(root / "review/ready.json"), *db_args, "--write"], mode,
                   expected=0 if mode == "normal" else 1, effect="memory-write")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def timestamp(value, start, end, field):
    require(type(value) is int and int(start) <= value <= int(end),
            f"{field}={value!r} outside invocation [{start}, {end}]")
    return "<validated-invocation-time>"


def memory_effect(root, mode, start, end, run):
    db = root / "db/state.sqlite"
    require(db.is_file(), "ready write did not create explicit fixture database")
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute("SELECT * FROM memories ORDER BY key")]
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        counts = {table: connection.execute('SELECT count(*) FROM "' + table.replace('"', '""') + '"').fetchone()[0]
                  for table in tables}
    require(len(rows) == 1, "expected exactly one persisted memory")
    row = rows[0]
    expected = {"key": MEMORY_KEY, "kind": "lesson", "content": MEMORY_BODY,
                "scope": None, "importance": 0.7, "status": "active", "access_count": 0}
    for key, value in expected.items():
        require(row[key] == value, f"memory.{key}: {row[key]!r} != {value!r}")
    require(json.loads(row["tags"]) == ["instinct", "human_reviewed", "phase1"], "memory tags")
    require(json.loads(row["related_keys"]) == [], "memory related keys")
    observed_times = {}
    for key in ["created_at", "updated_at", "last_accessed_at", "last_decayed_at"]:
        observed_times[key] = row[key]
        row[key] = timestamp(row[key], start, end, "memory." + key)
    require(len(set(observed_times.values())) == 1, "fresh memory timestamp fields disagree")
    for key, value in list(row.items()):
        if isinstance(value, bytes):
            row[key] = {"bytes": len(value), "sha256": digest(value)}
    receipt_path = root / "write-receipt.jsonl"
    receipt = None
    if mode == "normal":
        require(run.returncode == 0 and b"status=saved" in run.stdout, "save success rendering missing")
        lines = receipt_path.read_text(encoding="utf-8").splitlines()
        require(len(lines) == 1, "expected exactly one receipt")
        receipt = json.loads(lines[0])
        require(receipt["schema"] == SCHEMA + "memory_write_receipt.v0", "receipt schema")
        require(receipt["memory_key"] == MEMORY_KEY and receipt["memory_kind"] == "lesson", "receipt memory")
        require(receipt["preflight_id"] == "fixture-preflight" and receipt["candidate_id"] == CANDIDATE,
                "receipt provenance")
        require(receipt["db_path"] == str(db) and receipt["receipts_path"] == str(receipt_path), "receipt paths")
        value = receipt["generated_at_unix"]
        require(receipt["receipt_id"] == f"instinct-memory-write-{value}-{MEMORY_KEY}", "receipt id/time binding")
        observed_times["receipt.generated_at_unix"] = value
        receipt["generated_at_unix"] = timestamp(value, start, end, "receipt.generated_at_unix")
        receipt["receipt_id"] = f"instinct-memory-write-<validated-invocation-time>-{MEMORY_KEY}"
        require(stat.S_IMODE(receipt_path.stat().st_mode) == 0o600, "receipt privacy mode")
    else:
        require(run.returncode == 1 and run.stdout == b"", "receipt failure printed success")
        require(b"record instinct memory write receipt" in run.stderr, "receipt failure context missing")
        require(receipt_path.is_dir() and not list(receipt_path.iterdir()), "receipt obstruction changed")
    return {"memory_rows": rows, "table_counts": counts, "receipt": receipt}, observed_times


def execute(binary, root, case):
    env = setup(root, case["mode"])
    before = snapshot(root)
    start = time.time()
    run = subprocess.run(["agent-bridge", *case["args"]], executable=str(binary), cwd=root,
                         env=env, capture_output=True, timeout=30)
    end = time.time()
    after = snapshot(root)
    changes = {key: after.get(key) for key in sorted(before.keys() | after.keys())
               if before.get(key) != after.get(key)}
    require(run.returncode == case["expected_exit"],
            f"exit {run.returncode}, expected {case['expected_exit']}: {run.stderr.decode(errors='replace')}")
    if case["contains"]:
        require(case["contains"].encode() in run.stdout, "explicit local excerpt missing")
    if case["name"].startswith("review-context-redacted"):
        require(PROMPT.encode() not in run.stdout, "local excerpt leaked without explicit flag")
    times = {}
    business = None
    if case["effect"] == "memory-write":
        business, times = memory_effect(root, case["mode"], start, end, run)
        for key in ["db/state.sqlite", "db/state.sqlite-wal", "db/state.sqlite-shm"]:
            changes.pop(key, None)
        if case["mode"] == "normal":
            changes.pop("write-receipt.jsonl", None)
        require(changes == {"db/state.sqlite.init.lock": {
            "mode": 0o600, "kind": "file", "sha256": digest(b"")}},
            f"unexpected non-database/receipt write effects: {changes}")
    else:
        require(not changes, f"unexpected fixture writes: {changes}")
        require(not list((root / "db").iterdir()), "read-only/blocked command created database")
    comparable = (run.returncode, run.stdout, run.stderr, changes, business)
    evidence = {"exit_code": run.returncode, "stdout_sha256": digest(run.stdout),
                "stderr_sha256": digest(run.stderr), "effects": changes,
                "business_effect": business, "invocation_start_unix": start,
                "invocation_end_unix": end, "validated_timestamps": times}
    return comparable, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    binaries = [args.baseline.resolve(), args.candidate.resolve()]
    binary_hashes_before = [digest(binary.read_bytes()) for binary in binaries]
    script_hash_before = digest(Path(__file__).read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix="instinct-parity-", dir=args.output.parent) as temp:
        root = Path(temp).resolve()
        for case in cases(root):
            record = {"case": case["name"], "argv": ["agent-bridge", *case["args"]],
                      "evidence_type": "exact_cli_and_validated_business_effect" if
                      case["effect"] == "memory-write" else "exact_cli_and_filesystem_effect"}
            try:
                baseline, baseline_evidence = execute(binaries[0], root, case)
                candidate, candidate_evidence = execute(binaries[1], root, case)
                record.update(equal=baseline == candidate, baseline=baseline_evidence,
                              candidate=candidate_evidence)
                if not record["equal"]:
                    record["component_equal"] = [a == b for a, b in zip(baseline, candidate)]
            except (AssertionError, OSError, subprocess.TimeoutExpired, sqlite3.Error, ValueError) as error:
                record.update(equal=False, error=str(error))
            records.append(record)
            if not record["equal"]:
                print(case["name"], "FAIL", record.get("error", record.get("component_equal")))
    binary_hashes_after = [digest(binary.read_bytes()) for binary in binaries]
    stable_binaries = binary_hashes_before == binary_hashes_after
    stable_script = script_hash_before == digest(Path(__file__).read_bytes())
    report = {"schema": "agent_bridge.instinct_cli_parity.v1",
              "baseline_sha256": binary_hashes_before[0],
              "candidate_sha256": binary_hashes_before[1],
              "script_sha256": script_hash_before,
              "binaries_unchanged_during_comparison": stable_binaries,
              "script_unchanged_during_comparison": stable_script,
              "passed": sum(record["equal"] for record in records), "total": len(records),
              "scope": "CLI bytes and fixture effects; two writes use validated business rows, not SQLite bytes",
              "excluded": ["live services", "real credentials/state", "dynamic successful JSON plans",
                           "successful timestamped packet/preflight/rotation outputs"], "cases": records}
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{report['passed']}/{report['total']} Instinct CLI parity cases passed")
    if not stable_binaries:
        print("FAIL: a binary changed during comparison; rerun after builds finish")
    if not stable_script:
        print("FAIL: this script changed during comparison; rerun after edits finish")
    return 0 if report["passed"] == report["total"] and stable_binaries and stable_script else 1


if __name__ == "__main__":
    raise SystemExit(main())
