#!/usr/bin/env python3
"""Run and verify the non-authoritative Majorana P5 D0 resource probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Mapping, Sequence
import uuid


BASE = Path(__file__).resolve().parent
POLICY_NAME = "majorana_certificate_p5_design_probe_policy.json"
REPORT_NAME = "majorana_certificate_p5_design_probe_report.json"
PROBE_DRIVER = (
    "majorana_certificate_p5_design_probe/majorana_p5_threshold_resource_probe.jl"
)
P3_RUNNER = "majorana_certificate_p3/majorana_p3_runner.jl"
STAGED_PATHS = (
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    P3_RUNNER,
    "majorana_certificate_p4/majorana_p4_runner.jl",
    PROBE_DRIVER,
    "majorana_certificate_p2_fixture.json",
    "majorana_certificate_p3_fixture.json",
    "majorana_certificate_p4_fixture.json",
)
P3_SELECTOR_ANCHOR = (
    'const P3_ALLOWED_ANGLES = ("-1/50", "-1/100", "-1/200", '
    '"1/200", "1/100", "1/50")\n'
)
P3_SELECTOR_INSERTION = (
    "const P5_ACTIVE_STEP_THRESHOLD = Ref{Float64}(EPSILON)\n"
)
P3_DROP_NEEDLE = "should_drop = abs(coefficient) < EPSILON"
P3_DROP_REPLACEMENT = (
    "should_drop = abs(coefficient) < P5_ACTIVE_STEP_THRESHOLD[]"
)
REPORT_TYPE = "majorana_p5_conditional_step2_threshold_resource_report_d0_v1"
STEP2_CAP_KEYS = (
    "maximum_step2_accuracy_charged_events",
    "maximum_step2_anticommuting_events",
    "maximum_step2_boundary_retained_terms",
    "maximum_step2_cap_scan_term_visits",
    "maximum_step2_current_terms_before_constituent",
    "maximum_step2_drop_defect_events",
    "maximum_step2_final_retained_terms",
    "maximum_step2_merge_defect_events",
    "maximum_step2_premerge_terms",
    "maximum_step2_product_defect_events",
    "maximum_step2_propagation_term_visits",
    "maximum_step2_total_P2_charged_term_visits",
    "maximum_step2_total_P2_plus_accuracy_charged_events",
    "maximum_step2_truncation_term_visits",
)


class ProbeError(RuntimeError):
    """Fail-closed D0 probe validation error."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_canonical_json(path: Path, value: Any) -> None:
    Path(path).write_bytes(canonical_bytes(value) + b"\n")


def _run_git(*args: str) -> str:
    process = subprocess.run(
        ["git", *args], cwd=BASE, check=True, capture_output=True,
    )
    return process.stdout.decode("utf-8").strip()


def _validate_hex_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ProbeError(f"{label} is not a SHA-256 hex digest")
    try:
        bytes.fromhex(value)
    except ValueError as error:
        raise ProbeError(f"{label} is not hexadecimal") from error
    return value


def _source_pins(policy: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = policy.get("source_files")
    if not isinstance(rows, list):
        raise ProbeError("P5 D0 source_files is not a list")
    pins: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "size_bytes", "sha256",
        }:
            raise ProbeError("malformed P5 D0 source pin")
        relative = row["relative_path"]
        if relative in pins:
            raise ProbeError("duplicate P5 D0 source pin")
        pins[relative] = row
    return pins


def validate_policy(policy: Any, *, require_report_absent: bool) -> Mapping[str, Any]:
    if not isinstance(policy, dict):
        raise ProbeError("P5 D0 policy is not an object")
    if policy.get("schema_version") != 1:
        raise ProbeError("unexpected P5 D0 policy schema")
    if policy.get("policy_id") != "MAJORANA-P5-CONDITIONAL-STEP2-THRESHOLD-D0-V1":
        raise ProbeError("unexpected P5 D0 policy identity")
    if policy.get("scientific_authority") != "NONE":
        raise ProbeError("P5 D0 policy claims scientific authority")
    if policy.get("certificate_eligible") is not False:
        raise ProbeError("P5 D0 policy is certificate eligible")
    if policy.get("required_direct_parent_commit") != (
        "b0028fbd9ac079a64406bc2808ef7943045887a3"
    ):
        raise ProbeError("unexpected P5 D0 direct parent")
    candidates = policy.get("candidate_design")
    if not isinstance(candidates, dict):
        raise ProbeError("missing P5 D0 candidate design")
    if candidates.get("probe_order_step2_threshold_exponents") != [34, 36, 37]:
        raise ProbeError("P5 D0 candidate order drift")
    if candidates.get("formal_candidates_step2_threshold_exponents") != [36, 37]:
        raise ProbeError("P5 D0 formal candidate set drift")
    if candidates.get("step1_threshold_exponent_for_every_candidate") != 34:
        raise ProbeError("P5 D0 common prefix threshold drift")

    pins = _source_pins(policy)
    if set(pins) != set((*STAGED_PATHS, Path(__file__).name)):
        raise ProbeError("P5 D0 source pin allowlist drift")
    for relative, row in pins.items():
        path = BASE / relative
        if not path.is_file() or path.is_symlink():
            raise ProbeError(f"missing or nonregular P5 D0 source: {relative}")
        body = path.read_bytes()
        if len(body) != row["size_bytes"]:
            raise ProbeError(f"P5 D0 source size drift: {relative}")
        if hashlib.sha256(body).hexdigest() != row["sha256"]:
            raise ProbeError(f"P5 D0 source hash drift: {relative}")

    transform = policy.get("staged_instrumentation_transform")
    expected_transform = {
        "source_relative_path": P3_RUNNER,
        "selector_anchor": P3_SELECTOR_ANCHOR.rstrip("\n"),
        "selector_insertion": P3_SELECTOR_INSERTION.rstrip("\n"),
        "drop_needle": P3_DROP_NEEDLE,
        "drop_replacement": P3_DROP_REPLACEMENT,
        "each_needle_and_anchor_must_have_exactly_one_occurrence": True,
        "repository_source_is_not_modified": True,
    }
    if transform != expected_transform:
        raise ProbeError("P5 D0 instrumentation transform drift")
    _instrument_p3((BASE / P3_RUNNER).read_bytes())

    host = policy.get("host_caps")
    if host != {
        "MemoryMax_bytes": 3221225472,
        "MemorySwapMax_bytes": 0,
        "RuntimeMaxSec": "600s",
        "outer_timeout_seconds": 630,
        "maximum_stdout_bytes": 1048576,
        "maximum_stderr_bytes": 1048576,
    }:
        raise ProbeError("P5 D0 host caps drift")
    p4_caps = load_json(BASE / "majorana_certificate_p4_fixture.json")[
        "deterministic_resource_caps"
    ]
    expected_step2_caps = {key: p4_caps[key] for key in STEP2_CAP_KEYS}
    if policy.get("deterministic_step2_probe_caps") != expected_step2_caps:
        raise ProbeError("P5 D0 deterministic step-2 probe caps drift")
    if require_report_absent and (BASE / REPORT_NAME).exists():
        raise ProbeError("P5 D0 report exists before the probe commit")
    return policy


def _instrument_p3(body: bytes) -> bytes:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProbeError("P3 runner is not UTF-8") from error
    if text.count(P3_SELECTOR_ANCHOR) != 1:
        raise ProbeError("P3 selector anchor occurrence count is not one")
    if text.count(P3_DROP_NEEDLE) != 1:
        raise ProbeError("P3 threshold callback occurrence count is not one")
    if P3_SELECTOR_INSERTION.strip() in text:
        raise ProbeError("repository P3 runner is already instrumented")
    text = text.replace(
        P3_SELECTOR_ANCHOR,
        P3_SELECTOR_ANCHOR + P3_SELECTOR_INSERTION,
        1,
    )
    text = text.replace(P3_DROP_NEEDLE, P3_DROP_REPLACEMENT, 1)
    if text.count(P3_DROP_NEEDLE) != 0 or text.count(P3_DROP_REPLACEMENT) != 1:
        raise ProbeError("P3 threshold callback transform did not close")
    return text.encode("utf-8")


def stage_probe_tree(destination: Path, policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    pins = _source_pins(policy)
    rows: list[dict[str, Any]] = []
    for relative in STAGED_PATHS:
        source = BASE / relative
        body = source.read_bytes()
        if relative == P3_RUNNER:
            body = _instrument_p3(body)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        rows.append({
            "relative_path": relative,
            "repository_sha256": pins[relative]["sha256"],
            "staged_size_bytes": len(body),
            "staged_sha256": hashlib.sha256(body).hexdigest(),
            "instrumented_copy": relative == P3_RUNNER,
        })
    return rows


def _parse_time_stderr(stderr: bytes) -> dict[str, Any]:
    text = stderr.decode("utf-8", errors="replace")
    values: dict[str, Any] = {}
    keys = {
        "User time (seconds)": "user_time_seconds",
        "System time (seconds)": "system_time_seconds",
        "Elapsed (wall clock) time (h:mm:ss or m:ss)": "elapsed_wall_clock",
        "Maximum resident set size (kbytes)": "maximum_resident_set_size_KiB",
        "Minor (reclaiming a frame) page faults": "minor_page_faults",
        "Major (requiring I/O) page faults": "major_page_faults",
    }
    for line in text.splitlines():
        stripped = line.strip()
        for source, target in keys.items():
            prefix = source + ": "
            if stripped.startswith(prefix):
                raw = stripped[len(prefix):]
                values[target] = int(raw) if raw.isdigit() else raw
                break
    return values


def _terminate_scope(unit: str, process: subprocess.Popen[bytes]) -> None:
    subprocess.run(
        ["systemctl", "--user", "kill", "--kill-who=all", f"{unit}.scope"],
        check=False, capture_output=True,
    )
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _run_candidate(
    staging: Path,
    exponent: int,
    julia: Path,
    depot: Path,
    host: Mapping[str, Any],
    scratch_root: Path,
) -> dict[str, Any]:
    scratch = scratch_root / f"candidate-{exponent}"
    for relative in ("depot", "home", "tmp"):
        (scratch / relative).mkdir(parents=True, exist_ok=False)
    unit = f"majorana-p5-d0-{exponent}-{uuid.uuid4().hex}"
    julia_command = [
        "/usr/bin/time", "-v", str(julia), "--startup-file=no",
        "--history-file=no", "--compiled-modules=no",
        f"--project={staging / 'majorana_certificate_p0'}",
        str(staging / PROBE_DRIVER),
        str(staging / "majorana_certificate_p4_fixture.json"),
        str(staging / "majorana_certificate_p3_fixture.json"),
        str(staging / "majorana_certificate_p2_fixture.json"),
        str(exponent),
    ]
    command = [
        "systemd-run", "--user", "--scope", "--quiet", f"--unit={unit}",
        "-p", f"MemoryMax={host['MemoryMax_bytes']}",
        "-p", f"MemorySwapMax={host['MemorySwapMax_bytes']}",
        "-p", f"RuntimeMaxSec={host['RuntimeMaxSec']}",
        "--", *julia_command,
    ]
    environment = os.environ.copy()
    environment.update({
        "HOME": str(scratch / "home"),
        "TMPDIR": str(scratch / "tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "JULIA_DEPOT_PATH": f"{scratch / 'depot'}:{depot}",
        "JULIA_LOAD_PATH": "@",
        "JULIA_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "JULIA_PKG_OFFLINE": "true",
        "JULIA_PKG_SERVER": "",
    })
    started_ns = time.monotonic_ns()
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=host["outer_timeout_seconds"])
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_scope(unit, process)
        stdout, stderr = process.communicate()
    elapsed_ns = time.monotonic_ns() - started_ns
    stdout_exceeded = len(stdout) > host["maximum_stdout_bytes"]
    stderr_exceeded = len(stderr) > host["maximum_stderr_bytes"]
    observation: dict[str, Any] = {
        "step2_threshold_exponent": exponent,
        "process_returncode": process.returncode,
        "outer_timeout_triggered": timed_out,
        "stdout_bytes": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "outer_monotonic_elapsed_ns": elapsed_ns,
        "time_diagnostics": _parse_time_stderr(stderr),
        "host_failure_has_no_mathematical_authority": True,
    }
    if timed_out or stdout_exceeded or stderr_exceeded or process.returncode != 0:
        observation["status"] = "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
        observation["resource_witness"] = None
        observation["stderr_tail_diagnostic"] = stderr.decode(
            "utf-8", errors="replace",
        )[-4000:]
        return observation
    try:
        witness = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise ProbeError(f"candidate {exponent} stdout is not JSON") from error
    if stdout != canonical_bytes(witness) + b"\n":
        raise ProbeError(f"candidate {exponent} stdout is not canonical JSON")
    if witness.get("probe_type") != (
        "majorana_p5_conditional_step2_threshold_resource_probe_d0_v1"
    ):
        raise ProbeError(f"candidate {exponent} probe identity drift")
    candidate = witness.get("candidate", {})
    if candidate.get("step2_threshold_exponent") != exponent:
        raise ProbeError(f"candidate {exponent} threshold identity drift")
    if witness.get("scientific_authority") != "NONE":
        raise ProbeError(f"candidate {exponent} claims scientific authority")
    observation["status"] = "COMPLETED_RESOURCE_OBSERVATION"
    observation["resource_witness"] = witness
    observation["resource_witness_sha256"] = canonical_sha256(witness)
    return observation


def _control_projection(witness: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "step1": witness["step1"],
        "step2": witness["step2"],
        "step_link": witness["step_link"],
    }


def _validate_control(
    observation: Mapping[str, Any], policy: Mapping[str, Any],
) -> None:
    if observation["status"] != "COMPLETED_RESOURCE_OBSERVATION":
        raise ProbeError("P5 D0 2^-34 control did not complete")
    expected = policy["expected_2^-34_control_resource_projection"]
    actual = _control_projection(observation["resource_witness"])
    if actual != expected:
        raise ProbeError("P5 D0 2^-34 control differs from formal P4 resources")


def run_probe(
    preprobe_commit: str, julia: Path, depot: Path, output: Path,
) -> Mapping[str, Any]:
    policy = validate_policy(load_json(BASE / POLICY_NAME), require_report_absent=True)
    if _run_git("rev-parse", "HEAD") != preprobe_commit:
        raise ProbeError("P5 D0 HEAD differs from requested preprobe commit")
    if _run_git("status", "--porcelain=v1", "--untracked-files=all"):
        raise ProbeError("P5 D0 worktree is not clean before execution")
    if _run_git("rev-parse", f"{preprobe_commit}^") != policy[
        "required_direct_parent_commit"
    ]:
        raise ProbeError("P5 D0 preprobe commit has the wrong direct parent")
    julia = Path(julia).resolve()
    depot = Path(depot).resolve()
    if not julia.is_file() or file_sha256(julia) != policy["runtime"][
        "julia_executable_sha256"
    ]:
        raise ProbeError("P5 D0 Julia executable custody mismatch")
    if not depot.is_dir():
        raise ProbeError("P5 D0 depot is missing")
    for executable in ("systemd-run", "systemctl", "/usr/bin/time"):
        if shutil.which(executable) is None:
            raise ProbeError(f"P5 D0 missing required executable: {executable}")

    with tempfile.TemporaryDirectory(prefix="majorana-p5-d0-") as temporary:
        root = Path(temporary)
        staging = root / "staging"
        staging.mkdir()
        staging_manifest = stage_probe_tree(staging, policy)
        staging_sha = canonical_sha256(staging_manifest)
        scratch = root / "scratch"
        scratch.mkdir()
        observations: list[dict[str, Any]] = []
        for exponent in policy["candidate_design"][
            "probe_order_step2_threshold_exponents"
        ]:
            observation = _run_candidate(
                staging, exponent, julia, depot, policy["host_caps"], scratch,
            )
            observations.append(observation)
            if exponent == 34:
                _validate_control(observation, policy)
            if (
                exponent == 36
                and observation["status"] == "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
                and policy["stop_rules"]["skip_2^-37_after_2^-36_host_failure"]
            ):
                break

    report = {
        "schema_version": 1,
        "report_type": REPORT_TYPE,
        "policy_id": policy["policy_id"],
        "policy_sha256": file_sha256(BASE / POLICY_NAME),
        "preprobe_commit_sha": preprobe_commit,
        "scientific_authority": "NONE",
        "certificate_eligible": False,
        "probe_results_must_not_be_runner_inputs_for_formal_P5": True,
        "probe_results_must_not_select_or_remove_formal_candidates": True,
        "formal_candidates_were_frozen_before_probe": [36, 37],
        "staging_manifest": staging_manifest,
        "staging_manifest_sha256": staging_sha,
        "host_caps": policy["host_caps"],
        "observations": observations,
        "formal_cap_derivation_rule": policy["formal_cap_derivation_rule"],
        "explicit_exclusions": policy["explicit_exclusions"],
    }
    write_canonical_json(output, report)
    return report


def validate_report(report: Any) -> Mapping[str, Any]:
    policy = validate_policy(load_json(BASE / POLICY_NAME), require_report_absent=False)
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ProbeError("malformed P5 D0 report")
    if report.get("report_type") != REPORT_TYPE:
        raise ProbeError("unexpected P5 D0 report identity")
    if report.get("scientific_authority") != "NONE":
        raise ProbeError("P5 D0 report claims scientific authority")
    if report.get("certificate_eligible") is not False:
        raise ProbeError("P5 D0 report is certificate eligible")
    if report.get("policy_sha256") != file_sha256(BASE / POLICY_NAME):
        raise ProbeError("P5 D0 report policy hash mismatch")
    observations = report.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ProbeError("P5 D0 report has no observations")
    exponents = [row.get("step2_threshold_exponent") for row in observations]
    if exponents not in ([34, 36, 37], [34, 36]):
        raise ProbeError("P5 D0 report candidate execution order drift")
    _validate_control(observations[0], policy)
    if report.get("formal_candidates_were_frozen_before_probe") != [36, 37]:
        raise ProbeError("P5 D0 formal candidate set changed after probe")
    if report.get("explicit_exclusions") != policy["explicit_exclusions"]:
        raise ProbeError("P5 D0 report exclusions drift")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-preprobe", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--verify-report", action="store_true")
    parser.add_argument("--preprobe-commit")
    parser.add_argument("--julia", type=Path)
    parser.add_argument("--depot", type=Path)
    parser.add_argument("--output", type=Path, default=BASE / REPORT_NAME)
    args = parser.parse_args(argv)
    selected = sum(map(int, (args.verify_preprobe, args.run, args.verify_report)))
    if selected != 1:
        parser.error("select exactly one operation")
    if args.verify_preprobe:
        policy = validate_policy(
            load_json(BASE / POLICY_NAME), require_report_absent=True,
        )
        summary = {"status": "VERIFIED_P5_D0_PREPROBE", "policy_id": policy["policy_id"]}
    elif args.run:
        if not all((args.preprobe_commit, args.julia, args.depot)):
            parser.error("run requires preprobe commit, Julia, and depot")
        report = run_probe(args.preprobe_commit, args.julia, args.depot, args.output)
        summary = {
            "status": "COMPLETED_P5_D0_RESOURCE_PROBE",
            "report_sha256": file_sha256(args.output),
            "observation_statuses": [row["status"] for row in report["observations"]],
        }
    else:
        report = validate_report(load_json(args.output))
        if args.output.read_bytes() != canonical_bytes(report) + b"\n":
            raise ProbeError("P5 D0 report is not canonical JSON plus newline")
        summary = {
            "status": "VERIFIED_P5_D0_RESOURCE_REPORT",
            "report_sha256": file_sha256(args.output),
        }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
