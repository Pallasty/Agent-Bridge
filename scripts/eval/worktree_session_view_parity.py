#!/usr/bin/env python3
"""Compare pure worktree-session plans and rows with original Git source.

The baseline retains the exact planning and porcelain-rendering blocks from
--baseline-commit. The candidate probe includes the real extracted module.
Synthetic inputs exercise names, paths, timestamps and arbitrary porcelain
bytes; neither probe runs Git, reads the clock, or creates a worktree.

Run with existing Cargo dependencies, without a Cargo build:
  python3 scripts/eval/worktree_session_view_parity.py \
    --output-dir /Data/CascadeProjects/.analysis-reports/main-rs-governance-s19-20260913/view
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
BASELINE = "7fba67a8b006bac4fe59b5e74a260eaebc17c77b"
MAIN_PATH = "crates/bridge/src/main.rs"
MODULE_PATH = "crates/bridge/src/cli/worktree_session_view.rs"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def extract_block(source, function_name, start_marker, end_marker):
    function_start = source.index(f"async fn {function_name}(")
    function_end = source.index("\n}\n", function_start)
    function = source[function_start:function_end]
    if function.count(start_marker) != 1 or function.count(end_marker) != 1:
        raise ValueError(f"{function_name}: extraction anchors must be unique")
    relative_start = function.index(start_marker)
    relative_end = function.index(end_marker, relative_start)
    block = function[relative_start:relative_end]
    absolute_start = function_start + relative_start
    return block, {
        "function": function_name,
        "first_line": source.count("\n", 0, absolute_start) + 1,
        "last_line": source.count("\n", 0, absolute_start + len(block)),
        "original_block_sha256": digest(block.encode()),
        "original_block_bytes": len(block.encode()),
    }


def baseline_module(source):
    plan, plan_evidence = extract_block(
        source, "run_worktree_session_new", "    let name_part = name\n",
        "\n    // Make sure parent dir exists;")
    if not plan.endswith('    let path = repo_root.join(".worktrees").join(&dir_name);\n'):
        raise ValueError("planning block does not end immediately after path construction")
    rows, rows_evidence = extract_block(
        source, "run_worktree_session_list",
        "    // Porcelain blocks are separated by blank lines; each block has\n",
        "    if shown == 0 {\n")
    module = '''use std::path::{Path, PathBuf};

pub(crate) struct SessionPlan {
    pub(crate) branch: String,
    pub(crate) path: PathBuf,
}

pub(crate) fn plan_new_session(repo_root: &Path, name: Option<&str>, ts: u64) -> SessionPlan {
''' + plan + '''    SessionPlan { branch, path }
}

pub(crate) fn render_session_rows(porcelain: &[u8]) -> i32 {
    struct CapturedOutput<'a> { stdout: &'a [u8] }
    let out = CapturedOutput { stdout: porcelain };
''' + rows + '''    shown
}
'''
    return module, {"plan_new_session": plan_evidence, "render_session_rows": rows_evidence}


def probe_source(module_path):
    return f'''#[path = {json.dumps(str(module_path))}]
mod view;

use std::io::Read;

fn main() -> Result<(), Box<dyn std::error::Error>> {{
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 {{
        return Err("expected plan/list and negative-control boolean".into());
    }}
    let negative_control: bool = args[2].parse()?;
    let mut input = Vec::new();
    std::io::stdin().lock().read_to_end(&mut input)?;
    match args[1].as_str() {{
        "plan" => {{
            let request: serde_json::Value = serde_json::from_slice(&input)?;
            let repo = request["repo"].as_str().ok_or("missing repo")?;
            let name = request["name"].as_str();
            let ts = request["ts"].as_u64().ok_or("missing timestamp")?;
            let plan = view::plan_new_session(std::path::Path::new(repo), name, ts);
            println!("{{}}", serde_json::to_string(&serde_json::json!({{
                "branch": plan.branch,
                "path": plan.path.to_string_lossy(),
            }}))?);
        }}
        "list" => {{
            let shown = view::render_session_rows(&input);
            eprintln!("[probe-shown]={{shown}}");
        }}
        _ => return Err("unknown operation".into()),
    }}
    if negative_control {{
        println!("[intentional parity negative control]");
    }}
    Ok(())
}}
'''


def dependency_metadata(path):
    artifact = path.stem.removeprefix("lib")
    metadata = path.parent.parent / ".fingerprint" / artifact / "lib-serde_json.json"
    if not metadata.is_file():
        return {}
    content = json.loads(metadata.read_text())
    return {"features": json.loads(content["features"]), "profile": content["profile"]}


def serde_dependency(deps_dir, explicit):
    if explicit is not None:
        path = explicit.resolve()
        if not path.is_file():
            raise ValueError(f"missing dependency: {path}")
    else:
        candidates = list(deps_dir.glob("libserde_json-*.rlib"))
        if not candidates:
            raise ValueError(f"no built serde_json rlib in {deps_dir}")
        # Prefer the bridge's unified feature variant over build dependencies.
        path = max(candidates, key=lambda candidate: (
            "preserve_order" in dependency_metadata(candidate).get("features", []),
            candidate.stat().st_mtime_ns, candidate.name))
    return path, {"path": str(path), "sha256": digest(path.read_bytes()),
                  **dependency_metadata(path)}


def compile_probe(name, module_path, output_dir, deps_dir, serde_path):
    source = output_dir / f"{name}_probe.rs"
    binary = output_dir / f"{name}_probe"
    source.write_text(probe_source(module_path))
    command = ["rustc", "--edition=2021", "--crate-name", f"worktree_{name}_probe",
               str(source), "-L", f"dependency={deps_dir}",
               "--extern", f"serde_json={serde_path}", "-o", str(binary)]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120)
    (output_dir / f"{name}_compile.stdout").write_bytes(run.stdout)
    (output_dir / f"{name}_compile.stderr").write_bytes(run.stderr)
    if run.returncode:
        raise RuntimeError(f"{name} probe compile failed; see {output_dir}/{name}_compile.stderr")
    return binary, {"command": command, "source_sha256": digest(source.read_bytes()),
                    "binary_sha256": digest(binary.read_bytes())}


def plan_cases():
    samples = [
        ("no-name-zero", "/repo", None, 0),
        ("empty-name", "/repo", "", 1700000000),
        ("ascii", "/repo", "fix-parser", 1700000000),
        ("allowed-ascii", "/repo", "AZaz09_-", 17),
        ("unicode-scalars", "/repo", "中é🙂", 17),
        ("combining-scalars", "/repo", "e\u0301", 17),
        ("emoji-scalars", "/repo", "👩\u200d💻", 17),
        ("spaces-no-trim", "/repo", " fix issue ", 17),
        ("whitespace-only", "/repo", " \t\n\r ", 17),
        ("punctuation-no-compression", "/repo", "fix...///topic", 17),
        ("absolute-looking-name", "/repo", "/tmp/../branch", 17),
        ("backslash-name", "/repo", "C:\\work\\topic", 17),
        ("newline-name", "/repo", "line\none\ttwo", 17),
        ("embedded-nul-name", "/repo", "left\0right", 17),
        ("timestamp-max", "/repo", "edge", 18446744073709551615),
        ("relative-repo", "relative/repo", "topic", 17),
        ("empty-repo", "", "topic", 17),
        ("spaced-repo", "/a b/repo dir", "topic", 17),
        ("unicode-repo", "/工作/🙂", "topic", 17),
        ("dot-components", "./repo/../other/", "topic", 17),
        ("root-repo", "/", None, 17),
        ("newline-repo", "repo\nsecond", "topic", 17),
    ]
    for label, repo, name, ts in samples:
        payload = json.dumps({"repo": repo, "name": name, "ts": ts},
                             ensure_ascii=False, separators=(",", ":")).encode()
        yield {"case": "plan-" + label, "operation": "plan", "input": payload}


def list_cases():
    row = ("worktree /repo/.worktrees/session-one\nHEAD 0123456789abcdef\n"
           "branch refs/heads/session/one")
    other = ("worktree /repo/.worktrees/session-two\nHEAD abcdef0123456789\n"
             "branch refs/heads/other")
    samples = {
        "empty": "",
        "blank-lines": "\n\n\n",
        "no-trailing-newline": row,
        "trailing-newline": row + "\n",
        "trailing-blank-block": row + "\n\n",
        "extra-empty-blocks": "\n\n" + row + "\n\n\n\n",
        "crlf": row.replace("\n", "\r\n") + "\r\n\r\n",
        "crlf-final-no-newline": row.replace("\n", "\r\n"),
        "mixed-line-endings": row.replace("\n", "\r\n", 1) + "\n\n" + other,
        "lone-carriage-return": row + "\r",
        "missing-head-branch": "worktree /repo/.worktrees/session-minimal",
        "missing-branch": "worktree /repo/.worktrees/session-one\nHEAD abcdef012345",
        "missing-head": "worktree /repo/.worktrees/session-one\nbranch refs/heads/session/one",
        "missing-path": "HEAD abcdef01\nbranch refs/heads/session/one",
        "detached": "worktree /repo/.worktrees/session-detached\nHEAD abcdef012345\ndetached",
        "preserve-order": other + "\n\n" + row + "\n\n",
        "preserve-duplicates": row + "\n\n" + row,
        "unknown-fields": row + "\nlocked because fixture\nprunable reason\ncustom field\nbare",
        "duplicate-fields-last-value": row + "\nworktree /repo/.worktrees/session-last\n"
                                       "HEAD zzzzzzzzzzzz\nbranch refs/heads/last",
        "duplicate-path-last-excluded": row + "\nworktree /ordinary/repo",
        "duplicate-path-last-included": "worktree /ordinary/repo\n" + row,
        "duplicate-empty-values": row + "\nHEAD \nbranch ",
        "duplicate-empty-path": row + "\nworktree ",
        "session-branch-only": "worktree /ordinary/repo\nbranch refs/heads/session/one",
        "similar-path-excluded": "worktree /repo/.worktrees/sessionish-one\nHEAD abcdef01",
        "relative-path-no-slash-excluded": "worktree .worktrees/session-one\nHEAD abcdef01",
        "relative-path-with-slash": "worktree repo/.worktrees/session-one\nHEAD abcdef01",
        "backslash-path-excluded": "worktree C:\\repo\\.worktrees\\session-one",
        "substring-nested-path": "worktree /prefix/.worktrees/session-one/nested/child",
        "substring-empty-session-suffix": "worktree /repo/.worktrees/session-",
        "whitespace-line-is-not-separator": row + "\n \n" + other,
        "case-and-prefix-sensitive": "Worktree /repo/.worktrees/session-bad\n"
                                     "worktree/repo/.worktrees/session-bad\n" + row,
        "head-seven-chars": "worktree /r/.worktrees/session-h\nHEAD 1234567",
        "head-eight-chars": "worktree /r/.worktrees/session-h\nHEAD 12345678",
        "head-nine-chars": "worktree /r/.worktrees/session-h\nHEAD 123456789",
        "head-unicode-scalars": "worktree /r/.worktrees/session-h\nHEAD 中🙂éa\u0301一二三四五六",
        "unicode-path-branch": "worktree /工作/.worktrees/session-🙂\nHEAD abcdef012345\n"
                               "branch refs/heads/工作🙂",
        "path-spaces-not-trimmed": "worktree  /repo/.worktrees/session-one  \n"
                                   "branch  refs/heads/spaced  ",
        "embedded-nul": "worktree /r/.worktrees/session-a\0b\nHEAD 12\x0034567890\nbranch x\0y",
    }
    for label, value in samples.items():
        yield {"case": "list-" + label, "operation": "list", "input": value.encode()}
    invalid = {
        "invalid-utf8-fields": b"worktree /r/\xff/.worktrees/session-\xfe\nHEAD 12\xff4567890\nbranch x\xffy",
        "invalid-utf8-prefix": b"work\xfftree /r/.worktrees/session-one\nHEAD 12345678",
        "invalid-utf8-multibyte": b"worktree /r/.worktrees/session-\xf0\x28\x8c\x28\nHEAD \xe2\x82abcdefghi",
    }
    for label, value in invalid.items():
        yield {"case": "list-" + label, "operation": "list", "input": value}


def execute(binary, case, negative_control=False):
    run = subprocess.run([str(binary), case["operation"], str(negative_control).lower()],
                         input=case["input"], capture_output=True, timeout=10, cwd=ROOT)
    return run.returncode, run.stdout, run.stderr


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
    parser.add_argument("--serde-json-rlib", type=Path)
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args()
    output_dir, deps_dir = args.output_dir.resolve(), args.deps_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    case_dir = output_dir / "cases"
    case_dir.mkdir(exist_ok=True)
    source_commit = git("rev-parse", "--verify", args.baseline_commit + "^{commit}").decode().strip()
    baseline_main = git("show", f"{source_commit}:{MAIN_PATH}")
    module_source, extracted = baseline_module(baseline_main.decode())
    baseline_path = output_dir / "baseline_view.rs"
    baseline_path.write_text(module_source)
    candidate_path = ROOT / MODULE_PATH
    sources_before = {"harness": Path(__file__).read_bytes(),
                      "candidate_main": (ROOT / MAIN_PATH).read_bytes(),
                      "baseline_module": baseline_path.read_bytes()}
    if not args.baseline_only:
        sources_before["candidate_module"] = candidate_path.read_bytes()
    report = {
        "schema_version": 1, "mode": "baseline-only" if args.baseline_only else "pure-view-parity",
        "scope": "session plan branch/path and porcelain stdout/row count; no clock, Git, or filesystem effects",
        "baseline_commit": source_commit, "baseline_main_sha256": digest(baseline_main),
        "candidate_head": git("rev-parse", "HEAD").decode().strip(),
        **{key + "_sha256": digest(value) for key, value in sources_before.items()},
        "extracted_blocks": extracted,
        "rustc": subprocess.check_output(["rustc", "--version", "--verbose"]).decode().strip(),
        "probes": {}, "cases": [],
    }
    serde_path, report["serde_json_dependency"] = serde_dependency(deps_dir, args.serde_json_rlib)
    baseline, report["probes"]["baseline"] = compile_probe(
        "baseline", baseline_path, output_dir, deps_dir, serde_path)
    candidate = None
    if not args.baseline_only:
        candidate, report["probes"]["candidate"] = compile_probe(
            "candidate", candidate_path, output_dir, deps_dir, serde_path)
    all_cases = list(plan_cases()) + list(list_cases())
    if len({case["case"] for case in all_cases}) != len(all_cases):
        raise ValueError("duplicate fixture names")
    for case in all_cases:
        name = case["case"]
        (case_dir / f"{name}.input").write_bytes(case["input"])
        before = execute(baseline, case)
        record = {"case": name, "operation": case["operation"],
                  "input_sha256": digest(case["input"]), "input_bytes": len(case["input"]),
                  "baseline": record_output(case_dir, name + ".baseline", before)}
        if candidate is not None:
            after = execute(candidate, case)
            record.update(candidate=record_output(case_dir, name + ".candidate", after),
                          **compare_outputs(before, after))
            if not record["equal"]:
                print(f"DIFF {name}: {record['equal_fields']}")
        report["cases"].append(record)
    if candidate is not None:
        control = next(case for case in all_cases if case["operation"] == "list")
        before = execute(baseline, control)
        mutated = execute(candidate, control, negative_control=True)
        report["negative_control"] = {
            "case": control["case"],
            "candidate": record_output(case_dir, "negative-control.candidate", mutated),
            "comparison": compare_outputs(before, mutated),
            "caught": before[0] == mutated[0] == 0 and before[2] == mutated[2] and before[1] != mutated[1],
        }
    sources_after = {"harness": Path(__file__).read_bytes(),
                     "candidate_main": (ROOT / MAIN_PATH).read_bytes(),
                     "baseline_module": baseline_path.read_bytes()}
    if not args.baseline_only:
        sources_after["candidate_module"] = candidate_path.read_bytes()
    report["source_unchanged_during_run"] = sources_before == sources_after
    report["total"] = len(report["cases"])
    report["baseline_successes"] = sum(row["baseline"]["exit_code"] == 0 for row in report["cases"])
    report["operation_counts"] = {operation: sum(row["operation"] == operation for row in report["cases"])
                                  for operation in ["plan", "list"]}
    success = report["source_unchanged_during_run"] and report["baseline_successes"] == report["total"]
    if candidate is not None:
        report["passed"] = sum(row["equal"] for row in report["cases"])
        success = success and report["passed"] == report["total"] and report["negative_control"]["caught"]
    report["success"] = success
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if candidate is None:
        print(f"{report['baseline_successes']}/{report['total']} baseline probes succeeded; candidate NOT tested")
    else:
        print(f"{report['passed']}/{report['total']} exact exit/stdout/stderr plan/row cases passed; "
              f"negative control caught={report['negative_control']['caught']}")
    print(f"Report: {output_dir / 'report.json'}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
