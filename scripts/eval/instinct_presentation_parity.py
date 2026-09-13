#!/usr/bin/env python3
"""Compare nine Instinct renderers with unmodified output blocks from Git.

This is completed-Value presentation parity, not a command/effect integration
test. The baseline is extracted from the specified commit, never from the new
module. Both probes receive the same fixed JSON bytes and use the same built
dependencies. All generated sources, binaries, inputs, and byte outputs remain
under --output-dir; no Cargo build or live Instinct service is involved.

Example:
  python3 scripts/eval/instinct_presentation_parity.py \
    --output-dir /Data/CascadeProjects/.analysis-reports/main-rs-governance-s18-20260913/presentation
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
BASELINE = "4e57079292d8245fe3c721d57a6bb99adb7e806a"
MAIN_PATH = "crates/bridge/src/main.rs"
MODULE_PATH = "crates/bridge/src/cli/instinct_presentation.rs"
OPERATIONS = {
    "candidates": ("Candidates", "preview", ""),
    "review_packet": ("ReviewPacket", "packet", ""),
    "review_decision": ("ReviewDecision", "record", ""),
    "memory_preflight": ("MemoryPreflight", "packet", ""),
    "memory_write": ("MemoryWrite", "plan", "write: bool, "),
    "review_status": ("ReviewStatus", "status", ""),
    "review_inbox": ("ReviewInbox", "inbox", "limit: usize, "),
    "review_context": ("ReviewContext", "context", "include_local_excerpt: bool, "),
    "rotate_log": ("RotateLog", "plan", ""),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def extract_baseline(source):
    """Fail closed unless all nine exact, terminal output blocks are found."""
    start = source.index("    if let Cmd::Instinct { op } = &cmd {\n")
    end = source.index("\n        };\n    }", start)
    command = source[start:end]
    matches = list(re.finditer(r"(?m)^            InstinctOp::(\w+)\b", command))
    expected = [spec[0] for spec in OPERATIONS.values()]
    if [match.group(1) for match in matches] != expected:
        raise ValueError("baseline Instinct arms do not match the nine expected operations")
    functions, evidence = [], {}
    for index, (operation, (arm_name, value_name, extra)) in enumerate(OPERATIONS.items()):
        arm_end = matches[index + 1].start() if index + 1 < len(matches) else len(command)
        arm = command[matches[index].start():arm_end]
        marker = "                if *json {\n"
        if arm.count(marker) != 1:
            raise ValueError(f"{arm_name}: expected exactly one JSON/text output block")
        terminal = re.search(r"(?m)^                Ok\(\(\)\)\n            }\n?\Z", arm)
        if terminal is None:
            raise ValueError(f"{arm_name}: output does not terminate directly before Ok(())")
        block_start = arm.index(marker)
        block = arm[block_start:terminal.start()]
        aliases = "    let json = &as_json;\n"
        if extra:
            flag = extra.split(":", 1)[0]
            aliases += f"    let {flag} = &{flag};\n"
        functions.append(
            f"pub(crate) fn render_{operation}({value_name}: &Value, "
            f"{extra}as_json: bool) -> anyhow::Result<()> {{\n"
            + aliases + block + "    Ok(())\n}\n"
        )
        absolute_start = start + matches[index].start() + block_start
        evidence[operation] = {
            "arm": arm_name,
            "first_line": source.count("\n", 0, absolute_start) + 1,
            "last_line": source.count("\n", 0, absolute_start + len(block)),
            "original_block_sha256": digest(block.encode()),
            "original_block_bytes": len(block.encode()),
        }
    return "use serde_json::Value;\n\n" + "\n".join(functions), evidence


def probe_source(module_path):
    dispatch = []
    for operation, (_, _, extra) in OPERATIONS.items():
        flag = extra.split(":", 1)[0] + ", " if extra else ""
        dispatch.append(
            f'        "{operation}" => presentation::render_{operation}(&value, {flag}as_json),'
        )
    return f'''#[path = {json.dumps(str(module_path))}]
mod presentation;

fn main() -> anyhow::Result<()> {{
    let args: Vec<String> = std::env::args().collect();
    anyhow::ensure!(args.len() == 7, "expected operation, json, write, limit, excerpt, negative-control");
    let as_json: bool = args[2].parse()?;
    let write: bool = args[3].parse()?;
    let limit: usize = args[4].parse()?;
    let include_local_excerpt: bool = args[5].parse()?;
    let negative_control: bool = args[6].parse()?;
    let value: serde_json::Value = serde_json::from_reader(std::io::stdin().lock())?;
    match args[1].as_str() {{
{chr(10).join(dispatch)}
        _ => anyhow::bail!("unknown operation"),
    }}?;
    if negative_control {{
        println!("[intentional parity negative control]");
    }}
    Ok(())
}}
'''


def dependency(deps_dir, name, explicit=None):
    if explicit is not None:
        path = explicit.resolve()
        if not path.is_file():
            raise ValueError(f"missing dependency: {path}")
    else:
        candidates = list(deps_dir.glob(f"lib{name}-*.rlib"))
        if not candidates:
            raise ValueError(f"no built {name} rlib in {deps_dir}")
        # The bridge's unified serde_json enables preserve_order. Prefer that
        # artifact when several build-dependency variants share this directory.
        def rank(candidate):
            metadata = dependency_metadata(candidate, name)
            return ("preserve_order" in metadata.get("features", []),
                    candidate.stat().st_mtime_ns, candidate.name)
        path = max(candidates, key=rank)
    return path, {"path": str(path), "sha256": digest(path.read_bytes()),
                  **dependency_metadata(path, name)}


def dependency_metadata(path, name):
    artifact = path.stem.removeprefix("lib")
    metadata = path.parent.parent / ".fingerprint" / artifact / f"lib-{name}.json"
    if not metadata.is_file():
        return {}
    content = json.loads(metadata.read_text())
    return {"features": json.loads(content["features"]), "profile": content["profile"]}


def compile_probe(name, source, output_dir, deps_dir, externs):
    path = output_dir / f"{name}_probe.rs"
    binary = output_dir / f"{name}_probe"
    path.write_text(source)
    command = ["rustc", "--edition=2021", "--crate-name", f"instinct_{name}_probe",
               str(path), "-L", f"dependency={deps_dir}", "-o", str(binary)]
    for crate, dependency_path in externs.items():
        command.extend(["--extern", f"{crate}={dependency_path}"])
    run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120)
    (output_dir / f"{name}_compile.stdout").write_bytes(run.stdout)
    (output_dir / f"{name}_compile.stderr").write_bytes(run.stderr)
    if run.returncode:
        raise RuntimeError(f"{name} probe compile failed; see {output_dir}/{name}_compile.stderr")
    return binary, {"command": command, "source_sha256": digest(path.read_bytes()),
                    "binary_sha256": digest(binary.read_bytes())}


def full_values():
    candidate = {"candidate_id": "candidate-01", "kind": "correction",
                 "session_id": "session-01", "review_state": "pending",
                 "decision": "approved", "matched_cues": ["first", 17, None, "last"],
                 "prompt_chars": 31}
    common = {"status": "complete", "recommended_next_step": "review",
              "candidate_count": 3, "written": True, "writes_memory": True,
              "candidate_id": "candidate-01", "json_path": "/fixture/packet.json",
              "markdown_path": "/fixture/packet.md", "decisions_path": "/fixture/decisions.jsonl"}
    values = {operation: copy.deepcopy(common) for operation in OPERATIONS}
    values["candidates"].update(density_gate={"verdict": "ready"},
                               candidates=[copy.deepcopy(candidate) for _ in range(3)])
    values["review_decision"].update(decision="approved")
    values["memory_preflight"].update(approved_by_human_decision=True,
                                      ready_for_separate_memory_write=True)
    values["memory_write"].update(memory_record={"key": "nested-key"},
                                  saved_memory_key="saved-key", db_path="/fixture/state.db",
                                  receipt={"receipts_path": "/fixture/receipts.jsonl"})
    values["review_status"].update(packet_count=8, decision_count=7, preflight_count=6,
                                  ready_preflight_count=5, memory_write_receipt_count=4,
                                  parse_error_count=3, review_dir="/fixture/review",
                                  receipts_path="/fixture/receipts.jsonl")
    values["review_inbox"].update(packet_id="packet-01", pending_count=2,
                                 approved_count=1, rejected_count=4, deferred_count=5,
                                 packet_json="/fixture/packet.json",
                                 candidates=[copy.deepcopy(candidate) for _ in range(3)])
    values["review_context"].update(packet_id="packet-01", candidate=candidate,
                                   local_log_match={"raw_prompt_included": True, "found": True,
                                                    "prompt_excerpt": "fixture excerpt"})
    values["rotate_log"].update(log_path="/fixture/observer.jsonl",
                               archive_path="/fixture/archive.jsonl")
    return values


def transform(value, mode):
    if isinstance(value, dict):
        return {key: transform(item, mode) for key, item in value.items()}
    if isinstance(value, list):
        return [transform(item, mode) for item in value]
    if mode == "unicode" and isinstance(value, str):
        return value + ' 中文🙂\nsecond\t"quoted"\\path\rreturn'
    if mode == "wrong_type":
        if isinstance(value, str):
            return 12
        if isinstance(value, bool):
            return "true"
        if isinstance(value, int):
            return -1
    return value


def cases():
    """Fixed synthetic results, including shapes producers normally reject."""
    values = full_values()

    def formats(operation, label, value, **flags):
        for as_json in [False, True]:
            yield {"case": f"{operation}-{label}-{'json' if as_json else 'text'}",
                   "operation": operation, "value": value,
                   "as_json": as_json, "write": flags.get("write", False),
                   "limit": flags.get("limit", 10),
                   "include_local_excerpt": flags.get("include_local_excerpt", False)}

    for operation, full in values.items():
        samples = {"null": None, "empty": {}, "array": [], "scalar-string": "scalar",
                   "scalar-number": 17, "full": full,
                   "wrong-type": transform(full, "wrong_type"),
                   "unicode": transform(full, "unicode")}
        malformed = copy.deepcopy(full)
        for key, value in malformed.items():
            if isinstance(value, (dict, list)):
                malformed[key] = "not-a-container"
        samples["wrong-container"] = malformed
        for label, value in samples.items():
            yield from formats(operation, label, value)

    for count in [0, 1, 10, 11, 13]:
        value = copy.deepcopy(values["candidates"])
        value["candidate_count"] = count
        value["candidates"] = [{"candidate_id": f"candidate-{i:02}", "kind": "fixture",
                                 "session_id": f"session-{i:02}", "review_state": "pending"}
                                for i in range(count)]
        yield from formats("candidates", f"count-{count}", value)

    for count in [0, 1, 13]:
        value = copy.deepcopy(values["review_inbox"])
        value["candidate_count"] = count
        # Missing cues, empty cues, mixed types, and non-object rows are distinct.
        rows = [{"candidate_id": "missing-cues"}, {"matched_cues": []},
                {"matched_cues": ["one", None, False, 2, "two"]}, None,
                {"matched_cues": "wrong-type"}, {"matched_cues": [None, 5]}]
        value["candidates"] = [copy.deepcopy(rows[i % len(rows)]) for i in range(count)]
        for limit in [0, 1, 10, 20]:
            yield from formats("review_inbox", f"count-{count}-limit-{limit}", value, limit=limit)

    memory_shapes = {
        "nested-priority": {"memory_record": {"key": "nested"}, "saved_memory_key": "saved"},
        "saved-fallback": {"saved_memory_key": "saved"},
        "invalid-nested-fallback": {"memory_record": {"key": 17}, "saved_memory_key": "saved"},
        "null-nested-fallback": {"memory_record": None, "saved_memory_key": "saved"},
        "empty-nested-priority": {"memory_record": {"key": ""}, "saved_memory_key": "saved"},
        "both-invalid": {"memory_record": {"key": False}, "saved_memory_key": 17},
    }
    for label, keys in memory_shapes.items():
        value = copy.deepcopy(values["memory_write"])
        value.pop("memory_record")
        value.pop("saved_memory_key")
        value.update(keys)
        for write in [False, True]:
            yield from formats("memory_write", f"{label}-write-{str(write).lower()}", value, write=write)

    for label, excerpt in [("missing", None), ("empty", ""), ("invalid", 17),
                           ("unicode", '中文🙂\nline two\t"quote"\\path')]:
        value = copy.deepcopy(values["review_context"])
        if excerpt is None:
            value["local_log_match"].pop("prompt_excerpt")
        else:
            value["local_log_match"]["prompt_excerpt"] = excerpt
        for include in [False, True]:
            yield from formats("review_context", f"excerpt-{label}-include-{str(include).lower()}",
                               value, include_local_excerpt=include)


def execute(binary, case, negative_control=False):
    args = [str(binary), case["operation"], str(case["as_json"]).lower(),
            str(case["write"]).lower(), str(case["limit"]),
            str(case["include_local_excerpt"]).lower(), str(negative_control).lower()]
    payload = json.dumps(case["value"], ensure_ascii=False, separators=(",", ":")).encode()
    run = subprocess.run(args, input=payload, cwd=ROOT, capture_output=True, timeout=10)
    return (run.returncode, run.stdout, run.stderr), payload


def record_output(output_dir, name, output):
    stdout = output_dir / f"{name}.stdout"
    stderr = output_dir / f"{name}.stderr"
    stdout.write_bytes(output[1])
    stderr.write_bytes(output[2])
    return {"exit_code": output[0], "stdout_sha256": digest(output[1]),
            "stderr_sha256": digest(output[2]), "stdout_bytes": len(output[1]),
            "stderr_bytes": len(output[2]), "stdout_file": stdout.name,
            "stderr_file": stderr.name}


def compare_outputs(baseline, candidate):
    fields = {name: first == second for name, first, second
              in zip(["exit_code", "stdout", "stderr"], baseline, candidate)}
    return {"equal": all(fields.values()), "equal_fields": fields}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-commit", default=BASELINE)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--deps-dir", type=Path,
                        default=Path("/Data/ab-main-rs-governance-target/debug/deps"))
    parser.add_argument("--anyhow-rlib", type=Path)
    parser.add_argument("--serde-json-rlib", type=Path)
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args()
    output_dir, deps_dir = args.output_dir.resolve(), args.deps_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_bytes_dir = output_dir / "cases"
    output_bytes_dir.mkdir(exist_ok=True)
    source_commit = git("rev-parse", "--verify", args.baseline_commit + "^{commit}").decode().strip()
    baseline_main = git("show", f"{source_commit}:{MAIN_PATH}")
    baseline_module, extracted = extract_baseline(baseline_main.decode())
    baseline_path = output_dir / "baseline_presentation.rs"
    baseline_path.write_text(baseline_module)
    harness_bytes = Path(__file__).read_bytes()
    candidate_path = ROOT / MODULE_PATH
    candidate_bytes = None if args.baseline_only else candidate_path.read_bytes()
    candidate_main = (ROOT / MAIN_PATH).read_bytes()
    report = {
        "schema_version": 1, "mode": "baseline-only" if args.baseline_only else "presentation-parity",
        "scope": "nine completed-Value renderers; no producer, CLI parsing, filesystem, or database effects",
        "baseline_commit": source_commit, "baseline_main_sha256": digest(baseline_main),
        "candidate_head": git("rev-parse", "HEAD").decode().strip(),
        "candidate_main_sha256": digest(candidate_main),
        "candidate_module_sha256": None if candidate_bytes is None else digest(candidate_bytes),
        "harness_sha256": digest(harness_bytes), "extracted_blocks": extracted,
        "rustc": subprocess.check_output(["rustc", "--version", "--verbose"]).decode().strip(),
        "dependencies": {}, "probes": {}, "cases": [],
    }
    externs = {}
    for name, explicit in [("anyhow", args.anyhow_rlib), ("serde_json", args.serde_json_rlib)]:
        externs[name], report["dependencies"][name] = dependency(deps_dir, name, explicit)
    baseline, report["probes"]["baseline"] = compile_probe(
        "baseline", probe_source(baseline_path), output_dir, deps_dir, externs)
    candidate = None
    if not args.baseline_only:
        candidate, report["probes"]["candidate"] = compile_probe(
            "candidate", probe_source(candidate_path), output_dir, deps_dir, externs)
    json_groups = {}
    all_cases = list(cases())
    if len({case["case"] for case in all_cases}) != len(all_cases):
        raise ValueError("duplicate fixture names")
    for case in all_cases:
        before, payload = execute(baseline, case)
        name = case["case"]
        (output_bytes_dir / f"{name}.input.json").write_bytes(payload)
        record = {key: value for key, value in case.items() if key != "value"}
        record.update(input_sha256=digest(payload),
                      baseline=record_output(output_bytes_dir, name + ".baseline", before))
        if candidate is not None:
            after, _ = execute(candidate, case)
            record.update(candidate=record_output(output_bytes_dir, name + ".candidate", after),
                          **compare_outputs(before, after))
            if not record["equal"]:
                print(f"DIFF {name}: {record['equal_fields']}", file=sys.stderr)
        else:
            after = before
        if case["as_json"]:
            key = (case["operation"], digest(payload))
            json_groups.setdefault(key, []).append((before, after))
        report["cases"].append(record)
    report["json_flag_invariance"] = {
        "groups_with_repeated_inputs": sum(len(group) > 1 for group in json_groups.values()),
        "equal": all(all(item == group[0] for item in group) for group in json_groups.values()),
    }
    if candidate is not None:
        control_case = all_cases[0]
        before, _ = execute(baseline, control_case)
        mutated, _ = execute(candidate, control_case, negative_control=True)
        report["negative_control"] = {
            "case": control_case["case"],
            "candidate": record_output(output_bytes_dir, "negative-control.candidate", mutated),
            "comparison": compare_outputs(before, mutated),
            "caught": before[0] == mutated[0] == 0 and before[2] == mutated[2] and before[1] != mutated[1],
        }
    unchanged = (harness_bytes == Path(__file__).read_bytes()
                 and candidate_main == (ROOT / MAIN_PATH).read_bytes()
                 and (candidate_bytes is None or candidate_bytes == candidate_path.read_bytes()))
    report["source_unchanged_during_run"] = unchanged
    report["total"] = len(report["cases"])
    report["baseline_successes"] = sum(row["baseline"]["exit_code"] == 0
                                       and row["baseline"]["stderr_bytes"] == 0
                                       for row in report["cases"])
    success = (unchanged and report["baseline_successes"] == report["total"]
               and report["json_flag_invariance"]["equal"])
    if candidate is not None:
        report["passed"] = sum(row["equal"] for row in report["cases"])
        success = success and report["passed"] == report["total"] and report["negative_control"]["caught"]
    report["success"] = success
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if candidate is None:
        print(f"{report['baseline_successes']}/{report['total']} baseline probes succeeded; candidate NOT tested")
    else:
        print(f"{report['passed']}/{report['total']} exact exit/stdout/stderr presentation cases passed; "
              f"negative control caught={report['negative_control']['caught']}")
    print(f"Report: {output_dir / 'report.json'}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
