#!/usr/bin/env python3
"""Compare real Instinct MemoryRecords, validation errors and clock reads.

The original helper comes from --baseline-commit; the candidate helper comes
from actual main.rs and includes the actual extracted module. In each helper,
only the exact SystemTime block is replaced by a counted fixture clock. Both
probes link the existing ab_store rlib and serialize its real MemoryRecord,
including optional fields omitted by serde and importance.to_bits(). No Cargo
build, database, wall-clock sampling, or application service is involved.

Example:
  python3 scripts/eval/instinct_memory_record_parity.py \
    --output-dir /Data/CascadeProjects/.analysis-reports/main-rs-governance-s20-20260913/record
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
BASELINE = "dd04c98bc58882195392f8649d88808863c77ed1"
MAIN_PATH = "crates/bridge/src/main.rs"
MODULE_PATH = "crates/bridge/src/cli/instinct_memory.rs"
STORE_PATH = "crates/store/src/lib.rs"
CLOCK_BLOCK = '''    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
'''
RECORD_FIELDS = {"key", "kind", "content", "tags", "related_keys", "scope",
                 "created_at", "updated_at", "last_accessed_at", "access_count",
                 "importance", "status", "trigger_pattern", "superseded_by"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def extract_helper(source):
    marker = "fn memory_record_from_instinct_plan(value: &Value) -> Result<ab_store::MemoryRecord> {\n"
    if source.count(marker) != 1:
        raise ValueError("expected exactly one memory_record_from_instinct_plan helper")
    start = source.index(marker)
    end = source.index("\n}\n", start) + 3
    original = source[start:end]
    if original.count(CLOCK_BLOCK) != 1:
        raise ValueError("helper does not contain the exact single original SystemTime block")
    modified = original.replace(CLOCK_BLOCK, "    let now = fixture_clock();\n", 1)
    return modified, {
        "first_line": source.count("\n", 0, start) + 1,
        "last_line": source.count("\n", 0, end),
        "original_helper_sha256": digest(original.encode()),
        "original_helper_bytes": len(original.encode()),
        "clock_fixture_helper_sha256": digest(modified.encode()),
        "replaced_clock_block_sha256": digest(CLOCK_BLOCK.encode()),
        "replacement_count": 1,
    }


def probe_source(helper, candidate_path=None):
    include = ""
    if candidate_path is not None:
        include = f'''mod cli {{
    #[path = {json.dumps(str(candidate_path))}]
    pub(crate) mod instinct_memory;
}}
'''
    return '''use anyhow::Result;
use serde_json::{json, Value};
use std::sync::atomic::{AtomicI64, AtomicUsize, Ordering};

static FIXTURE_NOW: AtomicI64 = AtomicI64::new(0);
static CLOCK_READS: AtomicUsize = AtomicUsize::new(0);

fn fixture_clock() -> i64 {
    CLOCK_READS.fetch_add(1, Ordering::SeqCst);
    FIXTURE_NOW.load(Ordering::SeqCst)
}

''' + include + "\n" + helper + '''
fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    anyhow::ensure!(args.len() == 2, "expected negative-control mode");
    let negative_control = args[1].as_str();
    let request: Value = serde_json::from_reader(std::io::stdin().lock())?;
    let now = request["now"].as_i64().ok_or_else(|| anyhow::anyhow!("missing fixture timestamp"))?;
    FIXTURE_NOW.store(now, Ordering::SeqCst);
    CLOCK_READS.store(0, Ordering::SeqCst);
    let result = memory_record_from_instinct_plan(&request["value"]);
    let mut output = match result {
        Ok(record) => {
            // Serialize the actual store type, then include its three real
            // Option fields even when its serde attributes omit their Nones.
            let mut serialized = serde_json::to_value(&record)?;
            serialized["scope"] = json!(record.scope);
            serialized["trigger_pattern"] = json!(record.trigger_pattern);
            serialized["superseded_by"] = json!(record.superseded_by);
            json!({
                "outcome": "ok",
                "record_type": std::any::type_name::<ab_store::MemoryRecord>(),
                "record": serialized,
                "importance_bits": record.importance.to_bits(),
            })
        }
        Err(error) => json!({
            "outcome": "error",
            "error_display": error.to_string(),
            "error_debug": format!("{error:?}"),
            "error_chain": error.chain().map(ToString::to_string).collect::<Vec<_>>(),
        }),
    };
    match negative_control {
        "none" => {}
        "clock" => { fixture_clock(); }
        "field" => { output["record"]["status"] = json!("intentional-negative-control"); }
        "error" => { output["error_display"] = json!("intentional-negative-control"); }
        _ => anyhow::bail!("unknown negative-control mode"),
    }
    output["clock_reads"] = json!(CLOCK_READS.load(Ordering::SeqCst));
    println!("{}", serde_json::to_string(&output)?);
    Ok(())
}
'''


def dependency_metadata(path, name):
    artifact = path.stem.removeprefix("lib").replace("ab_store-", "ab-store-")
    metadata = path.parent.parent / ".fingerprint" / artifact / f"lib-{name}.json"
    if not metadata.is_file():
        return {}
    value = json.loads(metadata.read_text())
    return {"features": json.loads(value["features"]), "profile": value["profile"]}


def dependency(deps_dir, name, explicit):
    if explicit is not None:
        path = explicit.resolve()
        if not path.is_file():
            raise ValueError(f"missing dependency: {path}")
    else:
        paths = list(deps_dir.glob(f"lib{name}-*.rlib"))
        if not paths:
            raise ValueError(f"no existing {name} rlib in {deps_dir}")
        path = max(paths, key=lambda candidate: (
            "preserve_order" in dependency_metadata(candidate, name).get("features", []),
            candidate.stat().st_mtime_ns, candidate.name))
    return path, {"path": str(path), "sha256": digest(path.read_bytes()),
                  **dependency_metadata(path, name)}


def native_search_paths(deps_dir):
    """Reuse actual build-script search paths without executing build scripts."""
    paths = set()
    for output in sorted((deps_dir.parent / "build").glob("*/output")):
        for line in output.read_text(errors="replace").splitlines():
            for prefix in ["cargo:rustc-link-search=", "cargo::rustc-link-search="]:
                if line.startswith(prefix):
                    value = line[len(prefix):]
                    if value.startswith("native="):
                        value = value[len("native="):]
                    elif "=" in value:
                        continue
                    path = Path(value)
                    if path.is_absolute() and path.is_dir():
                        paths.add(str(path))
    return sorted(paths)


def compile_probe(name, source, output_dir, deps_dir, externs, native_paths):
    path = output_dir / f"{name}_probe.rs"
    binary = output_dir / f"{name}_probe"
    path.write_text(source)
    command = ["rustc", "--edition=2021", "--crate-name", f"instinct_memory_{name}_probe",
               str(path), "-L", f"dependency={deps_dir}", "-o", str(binary)]
    for crate, dependency_path in externs.items():
        command.extend(["--extern", f"{crate}={dependency_path}"])
    for native_path in native_paths:
        command.extend(["-L", f"native={native_path}"])
    run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
    (output_dir / f"{name}_compile.stdout").write_bytes(run.stdout)
    (output_dir / f"{name}_compile.stderr").write_bytes(run.stderr)
    if run.returncode:
        raise RuntimeError(f"{name} probe compile failed; see {output_dir}/{name}_compile.stderr")
    return binary, {"command": command, "source_sha256": digest(path.read_bytes()),
                    "binary_sha256": digest(binary.read_bytes())}


def cases():
    minimal = {"key": "fixture-key", "kind": "fixture-kind", "content": "fixture content"}

    def case(label, value, error=None, now=1700000000):
        return {"case": label, "value": value, "now": now, "expected_error": error}

    for label, value in [("null", None), ("array", []), ("string", "value"),
                         ("number", 17), ("boolean", True), ("empty-object", {})]:
        yield case("invalid-" + label, value, "memory_record.key is required")
    for field in ["key", "kind", "content"]:
        for label, value in [("missing", None), ("wrong-type", 17), ("empty", ""),
                             ("unicode-whitespace", "\u2003\u00a0\t\n\u3000")]:
            record = copy.deepcopy(minimal)
            if label == "missing":
                record.pop(field)
            else:
                record[field] = value
            yield case(f"required-{field}-{label}", record, f"memory_record.{field} is required")
    yield case("error-priority-key", {"content": None, "kind": "", "key": False},
               "memory_record.key is required")
    yield case("error-priority-kind", {"content": False, "kind": [], "key": "valid"},
               "memory_record.kind is required")

    yield case("minimal", minimal)
    full = {**minimal, "tags": ["first", "second"], "related_keys": ["related-1", "related-2"],
            "scope": "project:/fixture", "importance": 0.75}
    yield case("full", full)
    yield case("required-ascii-trim", {"key": "  key\n", "kind": "\tkind ", "content": "\r content \t"})
    yield case("required-unicode-trim", {"key": "\u00a0键\u3000", "kind": "\u2003陌生种类\u2003",
                                          "content": "\u3000内容🙂\u00a0"})
    yield case("zero-width-not-trimmed", {"key": "\u200b", "kind": "\u200b", "content": "\u200b"})
    yield case("unknown-kind", {**minimal, "kind": "not-an-enumerated-kind"})
    yield case("internal-whitespace", {"key": "key\npart", "kind": "odd kind", "content": "one\n\ttwo"})
    yield case("nul-and-escape", {"key": "key\0part", "kind": '"kind"', "content": "slash\\tab\tend"})
    yield case("tags-wrong-type", {**minimal, "tags": "first,second"})
    yield case("related-keys-wrong-type", {**minimal, "related_keys": {"key": "related"}})
    mixed = [" second ", None, 17, True, [], {}, "", " \t ", "first", "second", "\u200b", "\u00a0last\u3000"]
    yield case("mixed-tags", {**minimal, "tags": mixed})
    yield case("mixed-related-keys", {**minimal, "related_keys": mixed})
    yield case("duplicates-preserve-order", {**minimal, "tags": ["z", "a", "z"], "related_keys": ["b", "a", "b"]})
    yield case("empty-arrays", {**minimal, "tags": [], "related_keys": []})
    for label, scope in [("null", None), ("wrong-type", []), ("empty", ""),
                         ("whitespace", "\u00a0\n\u3000"), ("trim", " \u3000global\u00a0 "),
                         ("zero-width", "\u200b")]:
        yield case("scope-" + label, {**minimal, "scope": scope})
    for label, importance in [("null", None), ("string", "0.9"), ("boolean", True),
                              ("array", []), ("object", {}), ("negative", -1), ("over-one", 2),
                              ("negative-zero", -0.0), ("positive-zero", 0.0), ("fraction", 0.25),
                              ("one", 1.0), ("huge", 1e308), ("huge-negative", -1e308),
                              ("tiny", 1e-300), ("u64-max", 18446744073709551615)]:
        yield case("importance-" + label, {**minimal, "importance": importance})
    ignored = {"created_at": -111, "updated_at": -222, "last_accessed_at": 333,
               "access_count": 999, "status": "superseded", "trigger_pattern": "fixture-trigger",
               "superseded_by": "replacement-key", "unknown_extra": {"nested": True}}
    yield case("input-metadata-ignored", {**full, **ignored})
    yield case("malformed-metadata-ignored", {**minimal, **{key: [] for key in ignored}})
    for label, now in [("zero", 0), ("negative", -1), ("i64-min", -9223372036854775808),
                       ("i64-max", 9223372036854775807)]:
        yield case("clock-" + label, full, now=now)


def execute(binary, case, negative_control="none"):
    payload = json.dumps({"value": case["value"], "now": case["now"]}, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode()
    run = subprocess.run([str(binary), negative_control], input=payload,
                         cwd=ROOT, capture_output=True, timeout=20)
    return (run.returncode, run.stdout, run.stderr), payload


def compare_outputs(baseline, candidate):
    fields = {name: first == second for name, first, second
              in zip(["exit_code", "stdout", "stderr"], baseline, candidate)}
    return {"equal": all(fields.values()), "equal_fields": fields}


def semantic_checks(output, case):
    if output[0] or output[2]:
        return {"success": False, "reason": "probe failed or emitted stderr"}
    try:
        value = json.loads(output[1])
    except (ValueError, UnicodeError):
        return {"success": False, "reason": "probe did not emit JSON"}
    expected_error = case["expected_error"]
    checks = {"clock_reads": value.get("clock_reads") == (0 if expected_error else 1)}
    if expected_error:
        checks.update(outcome=value.get("outcome") == "error",
                      error_priority=value.get("error_display") == expected_error)
    else:
        record = value.get("record", {})
        checks.update(outcome=value.get("outcome") == "ok",
                      real_type=value.get("record_type") == "ab_store::MemoryRecord",
                      all_record_fields=set(record) == RECORD_FIELDS,
                      timestamps=record.get("created_at") == record.get("updated_at") == case["now"],
                      importance_bits=isinstance(value.get("importance_bits"), int))
    return {"success": all(checks.values()), "checks": checks}


def record_output(directory, name, output):
    (directory / f"{name}.stdout").write_bytes(output[1])
    (directory / f"{name}.stderr").write_bytes(output[2])
    return {"exit_code": output[0], "stdout_sha256": digest(output[1]),
            "stderr_sha256": digest(output[2]), "stdout_bytes": len(output[1]),
            "stderr_bytes": len(output[2]), "stdout_file": f"{name}.stdout",
            "stderr_file": f"{name}.stderr"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-commit", default=BASELINE)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--deps-dir", type=Path,
                        default=Path("/Data/ab-main-rs-governance-target/debug/deps"))
    for crate in ["ab-store", "anyhow", "serde-json"]:
        parser.add_argument(f"--{crate}-rlib", type=Path)
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args()
    output_dir, deps_dir = args.output_dir.resolve(), args.deps_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    case_dir = output_dir / "cases"
    case_dir.mkdir(exist_ok=True)
    source_commit = git("rev-parse", "--verify", args.baseline_commit + "^{commit}").decode().strip()
    baseline_main = git("show", f"{source_commit}:{MAIN_PATH}")
    baseline_helper, baseline_evidence = extract_helper(baseline_main.decode())
    source_paths = {"harness": Path(__file__), "candidate_main": ROOT / MAIN_PATH,
                    "store_source": ROOT / STORE_PATH}
    if not args.baseline_only:
        source_paths["candidate_module"] = ROOT / MODULE_PATH
    sources_before = {key: path.read_bytes() for key, path in source_paths.items()}
    report = {
        "schema_version": 1, "mode": "baseline-only" if args.baseline_only else "memory-record-parity",
        "scope": "real MemoryRecord fields, exact validation errors, and root clock reads; no database effects",
        "baseline_commit": source_commit, "baseline_main_sha256": digest(baseline_main),
        "candidate_head": git("rev-parse", "HEAD").decode().strip(),
        **{key + "_sha256": digest(value) for key, value in sources_before.items()},
        "baseline_extraction": baseline_evidence,
        "rustc": subprocess.check_output(["rustc", "--version", "--verbose"]).decode().strip(),
        "dependencies": {}, "probes": {}, "cases": [],
    }
    externs = {}
    for crate in ["ab_store", "anyhow", "serde_json"]:
        externs[crate], report["dependencies"][crate] = dependency(deps_dir, crate, getattr(args, crate + "_rlib"))
    native_paths = native_search_paths(deps_dir)
    report["native_search_paths"] = native_paths
    baseline, report["probes"]["baseline"] = compile_probe(
        "baseline", probe_source(baseline_helper), output_dir, deps_dir, externs, native_paths)
    candidate = None
    if not args.baseline_only:
        helper, report["candidate_extraction"] = extract_helper(sources_before["candidate_main"].decode())
        candidate, report["probes"]["candidate"] = compile_probe(
            "candidate", probe_source(helper, ROOT / MODULE_PATH), output_dir, deps_dir, externs, native_paths)
    all_cases = list(cases())
    if len({case["case"] for case in all_cases}) != len(all_cases):
        raise ValueError("duplicate fixture names")
    for case in all_cases:
        name = case["case"]
        before, payload = execute(baseline, case)
        (case_dir / f"{name}.input.json").write_bytes(payload)
        row = {"case": name, "now": case["now"], "expected_error": case["expected_error"],
               "input_sha256": digest(payload), "input_bytes": len(payload),
               "baseline": record_output(case_dir, name + ".baseline", before),
               "baseline_checks": semantic_checks(before, case)}
        if candidate is not None:
            after, _ = execute(candidate, case)
            row.update(candidate=record_output(case_dir, name + ".candidate", after),
                       candidate_checks=semantic_checks(after, case), **compare_outputs(before, after))
            if not row["equal"]:
                print(f"DIFF {name}: {row['equal_fields']}")
        report["cases"].append(row)
    if candidate is not None:
        report["negative_controls"] = []
        for mode, case_name in [("clock", "invalid-null"), ("field", "minimal"), ("error", "invalid-null")]:
            case = next(item for item in all_cases if item["case"] == case_name)
            before, _ = execute(baseline, case)
            mutated, _ = execute(candidate, case, negative_control=mode)
            comparison = compare_outputs(before, mutated)
            report["negative_controls"].append({
                "mode": mode, "case": case_name, "comparison": comparison,
                "candidate": record_output(case_dir, "negative-control-" + mode, mutated),
                "semantic_checks": semantic_checks(mutated, case),
                "caught": before[0] == mutated[0] == 0 and not comparison["equal"],
            })
    sources_after = {key: path.read_bytes() for key, path in source_paths.items()}
    report["source_unchanged_during_run"] = sources_before == sources_after
    report["dependencies_unchanged_during_run"] = all(
        digest(path.read_bytes()) == report["dependencies"][crate]["sha256"]
        for crate, path in externs.items())
    report["total"] = len(report["cases"])
    report["expected_errors"] = sum(case["expected_error"] is not None for case in all_cases)
    report["expected_records"] = report["total"] - report["expected_errors"]
    report["baseline_verified"] = sum(row["baseline_checks"]["success"] for row in report["cases"])
    success = (report["source_unchanged_during_run"] and report["dependencies_unchanged_during_run"]
               and report["baseline_verified"] == report["total"])
    if candidate is not None:
        report["passed"] = sum(row["equal"] for row in report["cases"])
        report["candidate_verified"] = sum(row["candidate_checks"]["success"] for row in report["cases"])
        success = (success and report["passed"] == report["candidate_verified"] == report["total"]
                   and all(control["caught"] for control in report["negative_controls"]))
    report["success"] = success
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if candidate is None:
        print(f"{report['baseline_verified']}/{report['total']} baseline record/error/clock checks passed; candidate NOT tested")
    else:
        print(f"{report['passed']}/{report['total']} exact record/error/clock cases passed; "
              f"negative controls caught={sum(control['caught'] for control in report['negative_controls'])}/3")
    print(f"Report: {output_dir / 'report.json'}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
