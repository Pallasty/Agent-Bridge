#!/usr/bin/env python3
"""Compare Dream identity rendering against exact functions from Git.

Baseline pct_delta/print_identity_section come unchanged from main.rs at
--baseline-commit. Candidate rendering includes the real extracted module.
Each probe uses the actual ab_store::IdentityWindow and an exact short_key
function extracted from its corresponding cli/dream.rs source. Fixed completed
windows exercise presentation only; no database, clock, or Cargo build runs.

Example:
  python3 scripts/eval/dream_identity_view_parity.py \
    --output-dir /Data/CascadeProjects/.analysis-reports/main-rs-governance-s21-20260913/view
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
BASELINE = "02141eeab7a31ca55b2bc91584848747ea5e1f4e"
MAIN_PATH = "crates/bridge/src/main.rs"
MODULE_PATH = "crates/bridge/src/cli/dream_identity_view.rs"
DREAM_PATH = "crates/bridge/src/cli/dream.rs"
STORE_PATH = "crates/store/src/lib.rs"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def extract_function(source, marker):
    if source.count(marker) != 1:
        raise ValueError(f"expected exactly one function marker: {marker}")
    start = source.index(marker)
    end = source.index("\n}\n", start) + 3
    function = source[start:end]
    return function, {"first_line": source.count("\n", 0, start) + 1,
                      "last_line": source.count("\n", 0, end),
                      "original_function_sha256": digest(function.encode()),
                      "original_function_bytes": len(function.encode())}


def probe_source(short_key, root_functions=None, candidate_path=None):
    if root_functions is not None:
        include = ""
        render = "print_identity_section(&current, &prior);"
        functions = "use cli::dream::short_key;\n\n" + root_functions
    else:
        include = f'''    #[path = {json.dumps(str(candidate_path))}]
    pub(crate) mod dream_identity_view;
'''
        render = "cli::dream_identity_view::print_identity_section(&current, &prior);"
        functions = ""
    return '''mod cli {
    pub(crate) mod dream {
''' + short_key + "    }\n" + include + "}\n\n" + functions + '''
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        return Err("expected negative-control boolean".into());
    }
    let negative_control: bool = args[1].parse()?;
    let request: serde_json::Value = serde_json::from_reader(std::io::stdin().lock())?;
    let mut current: ab_store::IdentityWindow = serde_json::from_value(request["current"].clone())?;
    let mut prior: ab_store::IdentityWindow = serde_json::from_value(request["prior"].clone())?;
    // JSON cannot represent NaN/infinity. The fixture explicitly supplies
    // their bits; this changes only test input construction, never rendering.
    if let Some(bits) = request["current_average_bits"].as_u64() {
        current.forum_avg_body_len = f64::from_bits(bits);
    }
    if let Some(bits) = request["prior_average_bits"].as_u64() {
        prior.forum_avg_body_len = f64::from_bits(bits);
    }
    ''' + render + '''
    if negative_control {
        println!("[intentional parity negative control]");
    }
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
            raise ValueError(f"no built {name} rlib in {deps_dir}")
        path = max(paths, key=lambda candidate: (
            "preserve_order" in dependency_metadata(candidate, name).get("features", []),
            candidate.stat().st_mtime_ns, candidate.name))
    return path, {"path": str(path), "sha256": digest(path.read_bytes()),
                  **dependency_metadata(path, name)}


def native_search_paths(deps_dir):
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
    command = ["rustc", "--edition=2021", "--crate-name", f"dream_identity_{name}_probe",
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


def window(**overrides):
    value = {"window_start": 0, "window_end": 1, "tool_calls_total": 0, "tool_calls_ok": 0,
             "top_tools": [], "forum_posts": 0, "forum_kinds": [],
             "forum_avg_body_len": 0.0, "memory_saves": 0}
    value.update(overrides)
    return value


def cases():
    def case(name, current=None, prior=None, **extras):
        return {"case": name, "request": {"current": window(**(current or {})),
                                           "prior": window(**(prior or {})), **extras}}

    maximum = 18446744073709551615
    yield case("empty-windows")
    yield case("all-growth-from-zero", {"tool_calls_total": 7, "tool_calls_ok": 6,
                                       "forum_posts": 3, "memory_saves": 4})
    yield case("all-decline-to-zero", prior={"tool_calls_total": 7, "tool_calls_ok": 6,
                                            "forum_posts": 3, "memory_saves": 4})
    yield case("equal-counts", {"tool_calls_total": 7, "tool_calls_ok": 5, "forum_posts": 3,
                                "memory_saves": 4}, {"tool_calls_total": 7, "tool_calls_ok": 5,
                                                     "forum_posts": 3, "memory_saves": 4})
    yield case("growth-and-decline", {"tool_calls_total": 11, "tool_calls_ok": 7,
                                     "forum_posts": 3, "memory_saves": 8},
               {"tool_calls_total": 7, "tool_calls_ok": 6, "forum_posts": 8, "memory_saves": 3})
    yield case("fraction-rounding", {"tool_calls_total": 2, "tool_calls_ok": 1,
                                     "forum_posts": 7, "memory_saves": 8},
               {"tool_calls_total": 3, "tool_calls_ok": 2, "forum_posts": 6, "memory_saves": 6})
    yield case("zero-total-nonzero-ok", {"tool_calls_ok": maximum}, {"tool_calls_ok": 17})
    yield case("ok-count-not-clamped", {"tool_calls_total": 1, "tool_calls_ok": maximum},
               {"tool_calls_total": 3, "tool_calls_ok": 7})
    for name, current, prior in [("max-from-zero", maximum, 0), ("max-from-one", maximum, 1),
                                 ("max-equal", maximum, maximum), ("max-adjacent", maximum - 1, maximum),
                                 ("f64-integer-boundary", 9007199254740993, 9007199254740992)]:
        yield case(name, {"tool_calls_total": current, "forum_posts": current, "memory_saves": current},
                   {"tool_calls_total": prior, "forum_posts": prior, "memory_saves": prior})
    for count in [7, 8, 9, 12]:
        yield case(f"top-tools-cap-{count}", {"top_tools": [[f"tool-{i:02}", i + 1] for i in range(count)]})
    yield case("top-tools-current-order-and-duplicates",
               {"top_tools": [["z", 3], ["a", 5], ["z", 1], ["middle", 7]]},
               {"top_tools": [["a", 2], ["z", 4], ["middle", 8]]})
    yield case("top-tools-prior-last-duplicate", {"top_tools": [["same", 8], ["unknown", 3]]},
               {"top_tools": [["same", 1], ["prior-only", 9], ["same", 4]]})
    yield case("top-tools-prior-only", prior={"top_tools": [["invisible", 10]]})
    for count in [31, 32, 33]:
        yield case(f"ascii-name-{count}", {"top_tools": [["a" * count, 1]]})
        yield case(f"unicode-name-{count}", {"top_tools": [["中" * (count - 1) + "🙂", 1]]})
    yield case("combining-scalar-truncation", {"top_tools": [["e\u0301" * 17, 1]]})
    yield case("name-whitespace-and-escapes", {"top_tools": [[" a\n\tb\\c\0d ", 1], ["", 2]]})
    yield case("forum-current-only", {"forum_kinds": [["z", 1], ["a", 2]]})
    yield case("forum-prior-only", prior={"forum_kinds": [["z", 1], ["a", 2]]})
    yield case("forum-union-lexical-sort", {"forum_kinds": [["z", 1], ["中", 2], ["A", 3]]},
               {"forum_kinds": [["a", 4], ["🙂", 5], ["A", 6], ["", 7]]})
    yield case("forum-current-first-prior-last-duplicates",
               {"forum_kinds": [["dup", 3], ["other", 7], ["dup", 99]]},
               {"forum_kinds": [["dup", 1], ["dup", 6], ["other", 4], ["other", 8]]})
    yield case("forum-kind-no-truncation", {"forum_kinds": [["长" * 33, 2], [" a\n\tb ", 1]]})
    for label, current, prior in [("below-half", 0.49, 0.4999999), ("half-ties", 0.5, 1.5),
                                  ("even-ties", 2.5, 3.5), ("negative", -0.5, -1.5),
                                  ("huge", 1e100, 1e308), ("tiny", 1e-300, -1e-300)]:
        yield case("average-" + label, {"forum_avg_body_len": current}, {"forum_avg_body_len": prior})
    yield case("average-signed-zero", current_average_bits=9223372036854775808, prior_average_bits=0)
    yield case("average-infinities", current_average_bits=9218868437227405312,
               prior_average_bits=18442240474082181120)
    yield case("average-nans", current_average_bits=9221120237041090560,
               prior_average_bits=18444492273895866368)
    yield case("memory-only-delta", {"memory_saves": 23}, {"memory_saves": 17})
    yield case("window-bounds-not-presented", {"window_start": -9223372036854775808,
                                             "window_end": 9223372036854775807},
               {"window_start": 99, "window_end": -1})


def execute(binary, case, negative_control=False):
    payload = json.dumps(case["request"], ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    run = subprocess.run([str(binary), str(negative_control).lower()], input=payload,
                         cwd=ROOT, capture_output=True, timeout=20)
    return (run.returncode, run.stdout, run.stderr), payload


def compare_outputs(baseline, candidate):
    fields = {name: first == second for name, first, second
              in zip(["exit_code", "stdout", "stderr"], baseline, candidate)}
    return {"equal": all(fields.values()), "equal_fields": fields}


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
    parser.add_argument("--ab-store-rlib", type=Path)
    parser.add_argument("--serde-json-rlib", type=Path)
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args()
    output_dir, deps_dir = args.output_dir.resolve(), args.deps_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    case_dir = output_dir / "cases"
    case_dir.mkdir(exist_ok=True)
    source_commit = git("rev-parse", "--verify", args.baseline_commit + "^{commit}").decode().strip()
    baseline_main = git("show", f"{source_commit}:{MAIN_PATH}")
    baseline_dream = git("show", f"{source_commit}:{DREAM_PATH}")
    functions, extracted = [], {}
    for name in ["pct_delta", "print_identity_section"]:
        function, extracted[name] = extract_function(baseline_main.decode(), f"fn {name}(")
        functions.append(function)
    baseline_short_key, extracted["short_key"] = extract_function(
        baseline_dream.decode(), "pub(crate) fn short_key(")
    source_paths = {"harness": Path(__file__), "candidate_main": ROOT / MAIN_PATH,
                    "candidate_dream": ROOT / DREAM_PATH, "store_source": ROOT / STORE_PATH}
    if not args.baseline_only:
        source_paths["candidate_module"] = ROOT / MODULE_PATH
    sources_before = {key: path.read_bytes() for key, path in source_paths.items()}
    report = {
        "schema_version": 1, "mode": "baseline-only" if args.baseline_only else "identity-view-parity",
        "scope": "completed real IdentityWindow text presentation; no collection, database, clock, or JSON CLI output",
        "baseline_commit": source_commit, "baseline_main_sha256": digest(baseline_main),
        "baseline_dream_sha256": digest(baseline_dream),
        "candidate_head": git("rev-parse", "HEAD").decode().strip(),
        **{key + "_sha256": digest(value) for key, value in sources_before.items()},
        "baseline_extraction": extracted,
        "rustc": subprocess.check_output(["rustc", "--version", "--verbose"]).decode().strip(),
        "dependencies": {}, "probes": {}, "cases": [],
    }
    externs = {}
    for crate in ["ab_store", "serde_json"]:
        externs[crate], report["dependencies"][crate] = dependency(deps_dir, crate, getattr(args, crate + "_rlib"))
    native_paths = native_search_paths(deps_dir)
    report["native_search_paths"] = native_paths
    baseline, report["probes"]["baseline"] = compile_probe(
        "baseline", probe_source(baseline_short_key, root_functions="\n".join(functions)),
        output_dir, deps_dir, externs, native_paths)
    candidate = None
    if not args.baseline_only:
        short_key, report["candidate_short_key_extraction"] = extract_function(
            sources_before["candidate_dream"].decode(), "pub(crate) fn short_key(")
        candidate, report["probes"]["candidate"] = compile_probe(
            "candidate", probe_source(short_key, candidate_path=ROOT / MODULE_PATH),
            output_dir, deps_dir, externs, native_paths)
    all_cases = list(cases())
    if len({case["case"] for case in all_cases}) != len(all_cases):
        raise ValueError("duplicate fixture names")
    for case in all_cases:
        name = case["case"]
        before, payload = execute(baseline, case)
        (case_dir / f"{name}.input.json").write_bytes(payload)
        row = {"case": name, "input_sha256": digest(payload), "input_bytes": len(payload),
               "baseline": record_output(case_dir, name + ".baseline", before)}
        if candidate is not None:
            after, _ = execute(candidate, case)
            row.update(candidate=record_output(case_dir, name + ".candidate", after),
                       **compare_outputs(before, after))
            if not row["equal"]:
                print(f"DIFF {name}: {row['equal_fields']}")
        report["cases"].append(row)
    if candidate is not None:
        control = all_cases[0]
        before, _ = execute(baseline, control)
        mutated, _ = execute(candidate, control, negative_control=True)
        report["negative_control"] = {
            "case": control["case"], "comparison": compare_outputs(before, mutated),
            "candidate": record_output(case_dir, "negative-control.candidate", mutated),
            "caught": before[0] == mutated[0] == 0 and before[2] == mutated[2] and before[1] != mutated[1],
        }
    sources_after = {key: path.read_bytes() for key, path in source_paths.items()}
    report["source_unchanged_during_run"] = sources_before == sources_after
    report["dependencies_unchanged_during_run"] = all(
        digest(path.read_bytes()) == report["dependencies"][crate]["sha256"]
        for crate, path in externs.items())
    report["total"] = len(report["cases"])
    report["baseline_successes"] = sum(row["baseline"]["exit_code"] == 0
                                       and row["baseline"]["stderr_bytes"] == 0
                                       and row["baseline"]["stdout_bytes"] > 0 for row in report["cases"])
    success = (report["source_unchanged_during_run"] and report["dependencies_unchanged_during_run"]
               and report["baseline_successes"] == report["total"])
    if candidate is not None:
        report["passed"] = sum(row["equal"] for row in report["cases"])
        success = success and report["passed"] == report["total"] and report["negative_control"]["caught"]
    report["success"] = success
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if candidate is None:
        print(f"{report['baseline_successes']}/{report['total']} baseline windows rendered; candidate NOT tested")
    else:
        print(f"{report['passed']}/{report['total']} exact IdentityWindow exit/stdout/stderr cases passed; "
              f"negative control caught={report['negative_control']['caught']}")
    print(f"Report: {output_dir / 'report.json'}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
