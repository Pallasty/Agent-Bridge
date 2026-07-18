#!/usr/bin/env python3
"""Freeze, run, and verify the P9-D1 coarse phase-only diagnostic.

P9-D1 is not a retry of P9 D0.  It statically derives a Julia clone from a
fixed P9 Git blob, emits only a bounded phase DFA on an inherited pipe, and
stops at its first coarse terminal without materializing a P9 D0 witness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True

BASE = Path(__file__).resolve().parent
ROOT = "docs/research/fermion-frontier/"
POLICY_NAME = "majorana_certificate_p9_d1_phase_probe_policy.json"
FIXTURE_NAME = "majorana_certificate_p9_d1_phase_probe_fixture.json"
REPORT_NAME = "majorana_certificate_p9_d1_phase_probe_report.json"
TEST_NAME = "test_majorana_certificate_p9_d1_phase_probe.py"
CLONE_DRIVER = (
    "majorana_certificate_p9_d1_phase_probe/"
    "majorana_p9_bit_order_step3_phase_probe.jl"
)
EXECUTION_CLAIM_NAME = ".majorana_certificate_p9_d1_phase_probe.execution-claimed"

POLICY_ID = "MAJORANA-P9-STEP3-E768-BITORDER-D1-COARSE-PHASE-V1"
FIXTURE_ID = POLICY_ID
REPORT_TYPE = "majorana_p9_step3_e768_bitorder_coarse_phase_report_d1_v1"
P9_PREPROBE_COMMIT = "ac2125eab524ec574c855a5931e51c7f9292f0c8"
P9_RESULT_COMMIT = "92629e3049ac0dfac12c390fc5ed499597076b7f"
P8_B_RESULT_COMMIT = "5dcb03990037e47dd48c8166712df9855c91ed67"
P9_DRIVER = (
    "majorana_certificate_p9_bit_order_resource_probe/"
    "majorana_p9_bit_order_step3_resource_probe.jl"
)
P9_DRIVER_FULL_PATH = ROOT + P9_DRIVER
P9_DRIVER_SHA256 = "f12ea9a93d4079792de8b5e8bae5b5ee0b45895a4399c19f41b7041034d3f14c"
P9_DRIVER_SIZE = 78229
P9_FIXTURE = "majorana_certificate_p9_bit_order_resource_probe_fixture.json"
P9_FIXTURE_SHA256 = "8365f441765cc5dbe1658b8aba2e2371c1619a0894c73ad5c0b21f8bf74a1be8"
P9_FIXTURE_SIZE = 21575
P9_REPORT = "majorana_certificate_p9_bit_order_resource_probe_report.json"
P9_REPORT_SHA256 = "881b4e4634c324e4578a7c8acd0009fa9a8b10ac953bf5f2a085af83ccafad8d"
P9_REPORT_SIZE = 10173
P9_MODE = "E768_BITORDER_STEP3_V1"
P9_CANDIDATE = "E768-BITORDER-STEP3-V1"
RUNTIME_LOCK_NAME = "majorana_certificate_p0_runtime_lock.json"
RUNTIME_LOCK_ID = "MAJORANA-P0-JULIA-1.11.9-LINUX-X86_64-V1"
RUNTIME_LOCK_SHA256 = "d54b68d9960cc9912f09a8a20b337804e198c61d5c68852db985cc4b537a1e17"
JULIA_EXECUTABLE_SHA256 = "2976d17aba35be5d546e8e315e521bd9be3e58c2e64abfd588f186696e807b7d"
MAJORANA_SOURCE_TREE_CLOSURE = {
    "file_count": 42,
    "total_bytes": 1875632,
    "closure_sha256": "744e743d88d7bc62da1ba11cef02909539de626bd4b0a5533b0b65d8aae309b5",
}
PAULI_SOURCE_TREE_CLOSURE = {
    "file_count": 119,
    "total_bytes": 7736347,
    "closure_sha256": "ce1e6cac1b09573962136fce0f315fabbf8556c9075c4aa3545c41c6ee4c3783",
}
INVALID_D1_PROBE_EXIT_CODE = 66

STAGED_PATHS = (
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    "majorana_certificate_p3/majorana_p3_runner.jl",
    "majorana_certificate_p4/majorana_p4_runner.jl",
    "majorana_certificate_p6/majorana_p6_runner.jl",
    "majorana_certificate_p2_fixture.json",
    "majorana_certificate_p3_fixture.json",
    "majorana_certificate_p4_fixture.json",
    "majorana_certificate_p5_fixture.json",
    "majorana_certificate_p6_fixture.json",
    P9_FIXTURE,
    FIXTURE_NAME,
    CLONE_DRIVER,
)
PREPROBE_CHANGED_PATHS = (
    ROOT + POLICY_NAME,
    ROOT + FIXTURE_NAME,
    ROOT + Path(CLONE_DRIVER).as_posix(),
    ROOT + Path(__file__).name,
    ROOT + TEST_NAME,
)
RESULT_CHANGED_PATHS = (ROOT + REPORT_NAME,)
SOURCE_PATHS = tuple(dict.fromkeys((
    *STAGED_PATHS,
    RUNTIME_LOCK_NAME,
    Path(__file__).name,
    TEST_NAME,
    P9_DRIVER,
)))

P9_B1_ALLOWED_PROJECTION = {
    "scientific_authority": "NONE",
    "terminal_status": "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
    "resource_witness_is_null": True,
    "S0_admission_status": "NOT_ESTABLISHED_INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
}
PHASE_EVENTS = (
    "D1_RUNNER_STARTED",
    "D1_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
    "D1_STATIC_SETUP_COMPLETED",
    "P6_PREFIX_STARTED",
    "P6_PREFIX_RETURNED",
    "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED",
    "P6_PREFIX_RESOURCE_CONFORMANCE_NOT_ESTABLISHED_TERMINAL",
    "STEP3_ENGINE_STARTED",
    "STEP3_ENGINE_RETURNED",
    "D1_DIAGNOSTIC_COMPLETED",
)
TERMINALS = {
    "PREFIX_NOT_ESTABLISHED": [
        "D1_RUNNER_STARTED",
        "D1_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        "D1_STATIC_SETUP_COMPLETED",
        "P6_PREFIX_STARTED",
        "P6_PREFIX_RETURNED",
        "P6_PREFIX_RESOURCE_CONFORMANCE_NOT_ESTABLISHED_TERMINAL",
        "D1_DIAGNOSTIC_COMPLETED",
    ],
    "STEP3_RETURNED": [
        "D1_RUNNER_STARTED",
        "D1_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        "D1_STATIC_SETUP_COMPLETED",
        "P6_PREFIX_STARTED",
        "P6_PREFIX_RETURNED",
        "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED",
        "STEP3_ENGINE_STARTED",
        "STEP3_ENGINE_RETURNED",
        "D1_DIAGNOSTIC_COMPLETED",
    ],
}
MARKER_FORBIDDEN_TOKENS = (
    b"observable", b"cache", b"majoranas", b"coefficient", b"mask",
    b"ticks", b"budget", b"selection", b"callback", b"retained",
    b"final_state", b"term_count", b"step3_input", b"cap_event",
)


class ProbeError(RuntimeError):
    """Fail-closed P9-D1 diagnostic error."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProbeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads_json(payload: bytes, context: str) -> Any:
    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProbeError(f"invalid JSON: {context}") from error


def load_json(path: Path) -> Any:
    if not path.is_file() or path.is_symlink():
        raise ProbeError(f"missing or nonregular JSON file: {path.name}")
    return loads_json(path.read_bytes(), path.name)


def _repo_root() -> Path:
    completed = subprocess.run(
        ("git", "rev-parse", "--show-toplevel"),
        cwd=BASE, check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise ProbeError("P9-D1 must run inside a Git worktree")
    root = Path(completed.stdout.strip()).resolve()
    if BASE.resolve() != root / "docs" / "research" / "fermion-frontier":
        raise ProbeError("P9-D1 repository location drift")
    return root


def _git_bytes(*args: str) -> bytes:
    completed = subprocess.run(
        ("git", *args), cwd=_repo_root(), check=False, capture_output=True,
    )
    if completed.returncode != 0:
        raise ProbeError(f"Git command failed: {' '.join(args)}")
    return completed.stdout


def _git_text(*args: str) -> str:
    try:
        return _git_bytes(*args).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProbeError("Git text is not UTF-8") from error


def _require_sha(value: str, label: str) -> str:
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise ProbeError(f"invalid {label} SHA")
    return value


def _git_blob_optional(commit: str, path: str) -> bytes | None:
    _require_sha(commit, "commit")
    listing = _git_bytes("ls-tree", "-z", commit, "--", path)
    if not listing:
        return None
    rows = listing.split(b"\0")
    if rows[-1] != b"" or len(rows) != 2:
        raise ProbeError("unexpected Git tree record count")
    metadata, separator, actual = rows[0].partition(b"\t")
    if separator != b"\t" or actual != path.encode("utf-8"):
        raise ProbeError("Git tree path drift")
    fields = metadata.split(b" ")
    if len(fields) != 3 or fields[0] != b"100644" or fields[1] != b"blob":
        raise ProbeError("Git object is not a regular blob")
    return _git_bytes("cat-file", "blob", fields[2].decode("ascii"))


def _git_blob(commit: str, path: str) -> bytes:
    body = _git_blob_optional(commit, path)
    if body is None:
        raise ProbeError(f"missing Git blob: {path}")
    return body


def _git_blob_id(commit: str, path: str) -> str:
    listing = _git_bytes("ls-tree", "-z", commit, "--", path)
    rows = listing.split(b"\0")
    if not listing or rows[-1] != b"" or len(rows) != 2:
        raise ProbeError("unexpected Git object-id record count")
    metadata, separator, actual = rows[0].partition(b"\t")
    if separator != b"\t" or actual != path.encode("utf-8"):
        raise ProbeError("Git object-id path drift")
    fields = metadata.split(b" ")
    if len(fields) != 3 or fields[0] != b"100644" or fields[1] != b"blob":
        raise ProbeError("Git object-id target is not a regular blob")
    return fields[2].decode("ascii")


def _checked_blob(commit: str, path: str, digest: str, size: int, label: str) -> bytes:
    body = _git_blob(commit, path)
    if len(body) != size or sha256_bytes(body) != digest:
        raise ProbeError(f"{label} raw Git-object custody drift")
    return body


def _parents(commit: str) -> tuple[str, ...]:
    fields = _git_text("rev-list", "--parents", "-n", "1", commit).strip().split()
    if not fields or fields[0] != commit:
        raise ProbeError("Git parent receipt drift")
    return tuple(fields[1:])


def _changed_paths(commit: str) -> tuple[str, ...]:
    raw = _git_bytes("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", commit)
    values = raw.split(b"\0")
    if values[-1] != b"":
        raise ProbeError("Git changed paths are not NUL terminated")
    try:
        paths = tuple(sorted(value.decode("utf-8") for value in values[:-1]))
    except UnicodeDecodeError as error:
        raise ProbeError("Git changed path is not UTF-8") from error
    if len(set(paths)) != len(paths):
        raise ProbeError("duplicate Git changed path")
    return paths


def _status_paths() -> tuple[str, ...]:
    raw = _git_bytes("status", "--porcelain=v1", "-z")
    records = raw.split(b"\0")
    if records[-1] != b"":
        raise ProbeError("Git status is not NUL terminated")
    try:
        return tuple(sorted(record[3:].decode("utf-8") for record in records[:-1]))
    except UnicodeDecodeError as error:
        raise ProbeError("Git status path is not UTF-8") from error


def _read_regular(name: str) -> bytes:
    path = BASE / name
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise ProbeError(f"missing current source: {name}") from error
    if not stat.S_ISREG(mode):
        raise ProbeError(f"current source is not regular: {name}")
    return path.read_bytes()


def _target_p9_b1_projection() -> tuple[bytes, bytes, dict[str, Any]]:
    if _parents(P9_PREPROBE_COMMIT) != (P8_B_RESULT_COMMIT,):
        raise ProbeError("P9 B0 parent topology drift")
    if _parents(P9_RESULT_COMMIT) != (P9_PREPROBE_COMMIT,):
        raise ProbeError("P9 B1 parent topology drift")
    if _changed_paths(P9_RESULT_COMMIT) != (ROOT + P9_REPORT,):
        raise ProbeError("P9 B1 changed-path set drift")
    driver = _checked_blob(
        P9_RESULT_COMMIT, P9_DRIVER_FULL_PATH, P9_DRIVER_SHA256,
        P9_DRIVER_SIZE, "frozen P9 driver",
    )
    fixture = _checked_blob(
        P9_RESULT_COMMIT, ROOT + P9_FIXTURE, P9_FIXTURE_SHA256,
        P9_FIXTURE_SIZE, "frozen P9 fixture",
    )
    report_raw = _checked_blob(
        P9_RESULT_COMMIT, ROOT + P9_REPORT, P9_REPORT_SHA256,
        P9_REPORT_SIZE, "P9 B1 report",
    )
    report = loads_json(report_raw, "P9 B1 report")
    if not isinstance(report, dict):
        raise ProbeError("P9 B1 report is not an object")
    observations = report.get("observations")
    admission = report.get("fixed_formal_admission")
    if not isinstance(observations, list) or len(observations) != 1 or not isinstance(admission, dict):
        raise ProbeError("P9 B1 minimal parent projection is malformed")
    projection = {
        "scientific_authority": report.get("scientific_authority"),
        "terminal_status": observations[0].get("status") if isinstance(observations[0], dict) else None,
        "resource_witness_is_null": (
            observations[0].get("resource_witness") is None
            if isinstance(observations[0], dict) else False
        ),
        "S0_admission_status": admission.get("status"),
    }
    if projection != P9_B1_ALLOWED_PROJECTION:
        raise ProbeError("P9 B1 allowed parent projection drift")
    return driver, fixture, projection


def _validate_runtime_lock_bytes(runtime: Any) -> None:
    """Bind D1's inherited runtime declaration to the immutable P0 lock."""
    if not isinstance(runtime, dict) or (
        runtime.get("runtime_lock_id") != RUNTIME_LOCK_ID
        or runtime.get("runtime_lock_relative_path") != RUNTIME_LOCK_NAME
        or runtime.get("runtime_lock_sha256") != RUNTIME_LOCK_SHA256
        or runtime.get("julia_executable_sha256") != JULIA_EXECUTABLE_SHA256
        or runtime.get("MajoranaPropagation_source_tree_closure") != MAJORANA_SOURCE_TREE_CLOSURE
        or runtime.get("PauliPropagation_source_tree_closure") != PAULI_SOURCE_TREE_CLOSURE
        or runtime.get("runtime_lock_bytes_verified_by_preprobe_checker") is not True
    ):
        raise ProbeError("P9-D1 runtime custody declaration drift")
    path = BASE / RUNTIME_LOCK_NAME
    if not path.is_file() or path.is_symlink():
        raise ProbeError("P9-D1 runtime lock is missing or nonregular")
    body = path.read_bytes()
    if sha256_bytes(body) != RUNTIME_LOCK_SHA256:
        raise ProbeError("P9-D1 runtime-lock bytes SHA-256 mismatch")
    lock = loads_json(body, RUNTIME_LOCK_NAME)
    if (
        not isinstance(lock, dict)
        or lock.get("schema_version") != 1
        or lock.get("runtime_lock_id") != RUNTIME_LOCK_ID
    ):
        raise ProbeError("P9-D1 runtime-lock identity drift")
    try:
        executable = lock["julia_runtime"]["executable"]["sha256"]
        packages = lock["direct_and_semantic_upstream_packages"]
        majorana = packages["MajoranaPropagation"]["installed_source_closure"]
        pauli = packages["PauliPropagation"]["installed_source_closure"]
    except (KeyError, TypeError) as error:
        raise ProbeError("P9-D1 runtime-lock closure custody is malformed") from error
    if executable != JULIA_EXECUTABLE_SHA256:
        raise ProbeError("P9-D1 runtime-lock Julia executable drift")
    if majorana != MAJORANA_SOURCE_TREE_CLOSURE:
        raise ProbeError("P9-D1 MajoranaPropagation closure custody drift")
    if pauli != PAULI_SOURCE_TREE_CLOSURE:
        raise ProbeError("P9-D1 PauliPropagation closure custody drift")


def _validate_fixture(fixture: Any) -> Mapping[str, Any]:
    expected = {
        "schema_version", "fixture_id", "required_direct_parent_commit",
        "scientific_authority", "certificate_eligible", "result_contract_eligible",
        "diagnostic_identity", "p9_b1_parent_custody", "frozen_p9_source_custody",
        "phase_event_protocol", "phase_channel_custody", "host_supervisor_caps",
        "runtime_custody", "authority_exclusions",
    }
    if not isinstance(fixture, dict) or set(fixture) != expected:
        raise ProbeError("P9-D1 fixture key set drift")
    if (
        fixture.get("schema_version") != 1
        or fixture.get("fixture_id") != FIXTURE_ID
        or fixture.get("required_direct_parent_commit") != P9_RESULT_COMMIT
        or fixture.get("scientific_authority") != "NONE"
        or fixture.get("certificate_eligible") is not False
        or fixture.get("result_contract_eligible") is not False
    ):
        raise ProbeError("P9-D1 fixture identity or authority drift")
    identity = fixture["diagnostic_identity"]
    if not isinstance(identity, dict) or (
        identity.get("candidate_id") != P9_CANDIDATE
        or identity.get("scientific_probe_mode") != P9_MODE
        or identity.get("one_fresh_process_only") is not True
        or identity.get("does_not_define_a_new_scientific_candidate") is not True
        or identity.get("does_not_establish_future_S0_admission") is not True
    ):
        raise ProbeError("P9-D1 fixture candidate identity drift")
    if fixture["p9_b1_parent_custody"] != {
        "result_commit_sha": P9_RESULT_COMMIT,
        "report_relative_path": P9_REPORT,
        "report_size_bytes": P9_REPORT_SIZE,
        "report_sha256": P9_REPORT_SHA256,
        **P9_B1_ALLOWED_PROJECTION,
        "allowed_result_informed_facts_are_exhaustive": True,
    }:
        raise ProbeError("P9-D1 fixture parent custody drift")
    source = fixture["frozen_p9_source_custody"]
    if not isinstance(source, dict) or (
        source.get("p9_preprobe_commit_sha") != P9_PREPROBE_COMMIT
        or source.get("p9_driver_sha256") != P9_DRIVER_SHA256
        or source.get("p9_driver_size_bytes") != P9_DRIVER_SIZE
        or source.get("p9_fixture_sha256") != P9_FIXTURE_SHA256
        or source.get("p9_fixture_size_bytes") != P9_FIXTURE_SIZE
        or source.get("frozen_candidate_mode_is_passed_unchanged_to_main_p9_d0") is not True
    ):
        raise ProbeError("P9-D1 fixture frozen-source custody drift")
    protocol = fixture["phase_event_protocol"]
    if not isinstance(protocol, dict) or (
        protocol.get("schema_version") != 1
        or protocol.get("wire_record_exact_fields") != ["event", "sequence"]
        or protocol.get("sequence_origin") != 0
        or protocol.get("sequence_is_contiguous") is not True
        or protocol.get("maximum_event_count") != 9
        or protocol.get("maximum_line_bytes_including_newline") != 256
        or protocol.get("maximum_total_channel_bytes") != 2048
        or protocol.get("allowed_events") != list(PHASE_EVENTS)
        or protocol.get("legal_terminal_sequences") != TERMINALS
    ):
        raise ProbeError("P9-D1 phase protocol drift")
    channel = fixture["phase_channel_custody"]
    if not isinstance(channel, dict) or any(
        channel.get(key) is not True for key in (
            "writer_runs_inside_the_same_systemd_scope_as_Julia",
            "reader_runs_in_the_outer_supervisor",
            "wire_records_are_single_atomic_POSIX_pipe_writes",
            "child_emits_only_fixed_event_names_and_sequence",
            "child_emits_no_timestamp_term_count_index_mask_coefficient_tick_budget_cap_resource_or_free_text",
            "stdout_is_strictly_empty",
            "stderr_is_not_a_phase_channel",
            "raw_phase_channel_bytes_are_not_persisted",
            "no_phase_file_FIFO_checkpoint_or_persistent_sidecar_is_created",
            "phase_trace_must_not_enter_S0_or_a_future_D2_runner",
        )
    ):
        raise ProbeError("P9-D1 phase-channel custody drift")
    _driver, p9_fixture_raw, projection = _target_p9_b1_projection()
    p9_fixture = loads_json(p9_fixture_raw, P9_FIXTURE)
    if not isinstance(p9_fixture, dict) or (
        fixture["host_supervisor_caps"] != p9_fixture.get("host_supervisor_caps")
        or fixture["runtime_custody"] != p9_fixture.get("runtime_custody")
    ):
        raise ProbeError("P9-D1 host/runtime custody differs from frozen P9")
    _validate_runtime_lock_bytes(fixture["runtime_custody"])
    if projection != P9_B1_ALLOWED_PROJECTION or not isinstance(fixture["authority_exclusions"], list):
        raise ProbeError("P9-D1 authority scope drift")
    return fixture


def _source_pins(policy: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = policy.get("source_files")
    if not isinstance(rows, list) or not rows:
        raise ProbeError("P9-D1 source pin manifest is empty")
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"relative_path", "size_bytes", "sha256"}:
            raise ProbeError("malformed P9-D1 source pin")
        path = row.get("relative_path")
        if not isinstance(path, str) or path in result:
            raise ProbeError("duplicate P9-D1 source pin")
        result[path] = row
    if set(result) != set(SOURCE_PATHS):
        raise ProbeError("P9-D1 source pin allowlist drift")
    return result


def validate_policy(policy: Any, *, require_report_absent: bool) -> Mapping[str, Any]:
    expected = {
        "schema_version", "policy_id", "required_direct_parent_commit",
        "policy_role", "scientific_authority", "certificate_eligible",
        "result_contract_eligible", "hindsight_firewall",
        "phase_only_execution_contract", "source_clone_contract",
        "phase_report_contract", "staged_source_custody", "source_files",
    }
    if not isinstance(policy, dict) or set(policy) != expected:
        raise ProbeError("P9-D1 policy key set drift")
    if (
        policy.get("schema_version") != 1
        or policy.get("policy_id") != POLICY_ID
        or policy.get("required_direct_parent_commit") != P9_RESULT_COMMIT
        or policy.get("scientific_authority") != "NONE"
        or policy.get("certificate_eligible") is not False
        or policy.get("result_contract_eligible") is not False
    ):
        raise ProbeError("P9-D1 policy identity or authority drift")
    firewall = policy["hindsight_firewall"]
    if not isinstance(firewall, dict) or firewall.get("D1_does_not_rerun_D0") is not True:
        raise ProbeError("P9-D1 hindsight firewall drift")
    if firewall.get("allowed_P9_B1_result_facts_are_exhaustive") != [
        "P9_B1_report_identity_and_scientific_authority_NONE",
        "P9_B1_terminal_status_INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        "P9_B1_resource_witness_is_null",
        "P9_B1_S0_admission_is_not_established",
    ]:
        raise ProbeError("P9-D1 allowed parent-result facts drift")
    clone = policy["source_clone_contract"]
    if not isinstance(clone, dict) or (
        clone.get("frozen_P9_driver_git_commit") != P9_RESULT_COMMIT
        or clone.get("frozen_P9_driver_sha256") != P9_DRIVER_SHA256
        or clone.get("frozen_P9_driver_size_bytes") != P9_DRIVER_SIZE
        or clone.get("clone_driver_relative_path") != CLONE_DRIVER
        or clone.get("exact_marker_block_count") != 8
        or clone.get("forward_byte_construction_and_reverse_deletion_are_required") is not True
        or clone.get("runtime_source_or_AST_transform_is_forbidden") is not True
    ):
        raise ProbeError("P9-D1 source-clone contract drift")
    staged = policy["staged_source_custody"]
    if not isinstance(staged, dict) or (
        staged.get("staged_path_order") != list(STAGED_PATHS)
        or staged.get(
            "P9_B1_report_policy_Python_original_Julia_driver_and_runtime_lock_are_outer_checker_only_and_not_staged"
        ) is not True
    ):
        raise ProbeError("P9-D1 staged path order drift")
    pins = _source_pins(policy)
    for path, row in pins.items():
        body = _read_regular(path)
        if row.get("size_bytes") != len(body) or row.get("sha256") != sha256_bytes(body):
            raise ProbeError(f"P9-D1 source pin drift: {path}")
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    _validate_static_clone(fixture)
    if require_report_absent:
        for name in (REPORT_NAME, EXECUTION_CLAIM_NAME):
            path = BASE / name
            if path.exists() or path.is_symlink():
                raise ProbeError(f"P9-D1 preprobe artifact already exists: {name}")
    return policy


def _preamble(fixture: Mapping[str, Any]) -> bytes:
    fixture_hash = canonical_sha256(fixture)
    events = ",\n    ".join(f'"{event}"' for event in PHASE_EVENTS)
    return (
        "#!/usr/bin/env julia\n"
        "# P9_D1_STATIC_TRANSPORT_PREAMBLE_BEGIN\n"
        "# Checker-owned phase transport and bootstrap.  This block contains no\n"
        "# P9 scientific state and is outside the byte-derived P9 clone region.\n"
        f"const P9_D1_FIXTURE_CANONICAL_SHA256 = \"{fixture_hash}\"\n"
        f"const P9_D1_FIXTURE_ID = \"{FIXTURE_ID}\"\n"
        f"const P9_D1_DIRECT_PARENT = \"{P9_RESULT_COMMIT}\"\n"
        "const P9_D1_PHASE_EVENTS = (\n"
        f"    {events},\n"
        ")\n"
        "const P9_D1_PHASE_FD = Ref{Cint}(-1)\n"
        "const P9_D1_PHASE_SEQUENCE = Ref(0)\n"
        "struct P9D1PhaseTransportError <: Exception end\n"
        "function p9_d1_write_atomic(payload::Vector{UInt8})\n"
        "    length(payload) <= 256 || throw(P9D1PhaseTransportError())\n"
        "    fd = P9_D1_PHASE_FD[]\n"
        "    fd >= 3 || throw(P9D1PhaseTransportError())\n"
        "    written = GC.@preserve payload ccall(\n"
        "        :write, Base.Cssize_t, (Cint, Ptr{UInt8}, Csize_t),\n"
        "        fd, pointer(payload), length(payload),\n"
        "    )\n"
        "    if written == -1 && Base.Libc.errno() == Base.Libc.EINTR\n"
        "        written = GC.@preserve payload ccall(\n"
        "            :write, Base.Cssize_t, (Cint, Ptr{UInt8}, Csize_t),\n"
        "            fd, pointer(payload), length(payload),\n"
        "        )\n"
        "    end\n"
        "    written == length(payload) || throw(P9D1PhaseTransportError())\n"
        "    return nothing\n"
        "end\n"
        "function p9_d1_emit(event::AbstractString)\n"
        "    event in P9_D1_PHASE_EVENTS || error(\"unknown P9 D1 phase event\")\n"
        "    sequence = P9_D1_PHASE_SEQUENCE[]\n"
        "    line = \"{\\\"event\\\":\\\"$(event)\\\",\\\"sequence\\\":$(sequence)}\\n\"\n"
        "    p9_d1_write_atomic(Vector{UInt8}(codeunits(line)))\n"
        "    P9_D1_PHASE_SEQUENCE[] = sequence + 1\n"
        "    return nothing\n"
        "end\n"
        "function p9_d1_validate_fixture(d1_fixture)\n"
        "    canonical_sha256(d1_fixture) == P9_D1_FIXTURE_CANONICAL_SHA256 ||\n"
        "        error(\"P9 D1 fixture differs from frozen semantic object\")\n"
        "    d1_fixture[\"fixture_id\"] == P9_D1_FIXTURE_ID || error(\"P9 D1 fixture id drift\")\n"
        "    d1_fixture[\"required_direct_parent_commit\"] == P9_D1_DIRECT_PARENT || error(\"P9 D1 parent drift\")\n"
        "    d1_fixture[\"scientific_authority\"] == \"NONE\" || error(\"P9 D1 authority drift\")\n"
        "    d1_fixture[\"certificate_eligible\"] == false || error(\"P9 D1 certificate drift\")\n"
        "    d1_fixture[\"result_contract_eligible\"] == false || error(\"P9 D1 contract drift\")\n"
        "    protocol = d1_fixture[\"phase_event_protocol\"]\n"
        "    protocol[\"allowed_events\"] == Any[P9_D1_PHASE_EVENTS...] || error(\"P9 D1 phase vocabulary drift\")\n"
        "    protocol[\"maximum_event_count\"] == 9 || error(\"P9 D1 event cap drift\")\n"
        "    protocol[\"maximum_line_bytes_including_newline\"] == 256 || error(\"P9 D1 line cap drift\")\n"
        "    protocol[\"maximum_total_channel_bytes\"] == 2048 || error(\"P9 D1 channel cap drift\")\n"
        "    host = d1_fixture[\"host_supervisor_caps\"]\n"
        "    host[\"MemoryMax_bytes\"] == 2147483648 || error(\"P9 D1 memory cap drift\")\n"
        "    host[\"MemorySwapMax_bytes\"] == 0 || error(\"P9 D1 swap cap drift\")\n"
        "    host[\"RuntimeMaxSec\"] == \"1800s\" || error(\"P9 D1 runtime cap drift\")\n"
        "    return d1_fixture\n"
        "end\n"
        "function p9_d1_bootstrap!()\n"
        "    length(ARGS) == 9 || error(\"invalid P9 D1 argument count\")\n"
        "    d1_fixture = JSON.parsefile(abspath(ARGS[1]))\n"
        "    p9_d1_validate_fixture(d1_fixture)\n"
        "    phase_fd = parse(Int, ARGS[9])\n"
        "    3 <= phase_fd <= typemax(Cint) || error(\"invalid P9 D1 phase fd\")\n"
        "    P9_D1_PHASE_FD[] = Cint(phase_fd)\n"
        "    deleteat!(ARGS, 1)\n"
        "    pop!(ARGS)\n"
        "    length(ARGS) == 7 || error(\"P9 D1 core argument normalization drift\")\n"
        "    p9_d1_emit(\"D1_RUNNER_STARTED\")\n"
        "    return nothing\n"
        "end\n"
        "# P9_D1_STATIC_TRANSPORT_PREAMBLE_END\n\n"
        "# P9_D1_STATIC_P9_D0_CLONE_BEGIN\n"
    ).encode("utf-8")


CLONE_END = b"\n# P9_D1_STATIC_P9_D0_CLONE_END\n"


def _marker_blocks() -> tuple[tuple[bytes, bytes, bool], ...]:
    return (
        (
            b"function main_p9_d0()\n    P9_D0_FAILURE_PHASE[] = P9_D0_INVALID_FAILURE_PHASE\n",
            b"    # P9_D1_MARKER_BLOCK_1_BEGIN\n"
            b"    p9_d1_bootstrap!()\n"
            b"    # P9_D1_MARKER_BLOCK_1_END\n",
            False,
        ),
        (
            b"function p9_execute_prefix(\n"
            b"    p9_fixture, p6_fixture, p3_fixture, stages, observable, trig_lookup,\n"
            b")\n",
            b"    # P9_D1_MARKER_BLOCK_2_BEGIN\n"
            b"    p9_d1_emit(\"P6_PREFIX_STARTED\")\n"
            b"    # P9_D1_MARKER_BLOCK_2_END\n",
            False,
        ),
        (
            b"function p9_execute_bit_order_step(\n"
            b"    stages, execution_fixture, input_sum, trig_lookup, engine_caps,\n"
            b"    selection_caps; copy_completed_output::Bool,\n"
            b")\n",
            b"    # P9_D1_MARKER_BLOCK_3_BEGIN\n"
            b"    p9_d1_emit(\"STEP3_ENGINE_STARTED\")\n"
            b"    # P9_D1_MARKER_BLOCK_3_END\n",
            False,
        ),
        (
            b"    runtime_custody = p9_validate_runtime(p9_fixture)\n",
            b"    # P9_D1_MARKER_BLOCK_4_BEGIN\n"
            b"    p9_d1_emit(\"D1_INPUT_AND_RUNTIME_CUSTODY_VALIDATED\")\n"
            b"    # P9_D1_MARKER_BLOCK_4_END\n",
            False,
        ),
        (
            b"    observable, _initial = initial_observable()\n",
            b"    # P9_D1_MARKER_BLOCK_5_BEGIN\n"
            b"    p9_d1_emit(\"D1_STATIC_SETUP_COMPLETED\")\n"
            b"    # P9_D1_MARKER_BLOCK_5_END\n",
            False,
        ),
        (
            b"    prefix = p9_execute_prefix(\n"
            b"        p9_fixture, p6_fixture, p3_fixture, stages, observable, trig_lookup,\n"
            b"    )\n",
            b"    # P9_D1_MARKER_BLOCK_6_BEGIN\n"
            b"    p9_d1_emit(\"P6_PREFIX_RETURNED\")\n"
            b"    p9_d1_emit(prefix.prefix_conformed ?\n"
            b"        \"P6_PREFIX_RESOURCE_CONFORMANCE_PASSED\" :\n"
            b"        \"P6_PREFIX_RESOURCE_CONFORMANCE_NOT_ESTABLISHED_TERMINAL\")\n"
            b"    # P9_D1_MARKER_BLOCK_6_END\n",
            False,
        ),
        (
            b"        step3_run = p9_execute_bit_order_step(\n"
            b"            stages, step3_fixture, step3_input, trig_lookup, step3_caps,\n"
            b"            step3_selection_caps; copy_completed_output=false,\n"
            b"        )\n",
            b"        # P9_D1_MARKER_BLOCK_7_BEGIN\n"
            b"        p9_d1_emit(\"STEP3_ENGINE_RETURNED\")\n"
            b"        p9_d1_emit(\"D1_DIAGNOSTIC_COMPLETED\")\n"
            b"        return nothing\n"
            b"        # P9_D1_MARKER_BLOCK_7_END\n",
            False,
        ),
        (
            b"    raw = (\n",
            b"    # P9_D1_MARKER_BLOCK_8_BEGIN\n"
            b"    p9_d1_emit(\"D1_DIAGNOSTIC_COMPLETED\")\n"
            b"    return nothing\n"
            b"    # P9_D1_MARKER_BLOCK_8_END\n",
            True,
        ),
    )


def _build_expected_clone(frozen: bytes, fixture: Mapping[str, Any]) -> tuple[bytes, list[bytes]]:
    expected = frozen
    blocks: list[bytes] = []
    for anchor, block, before in _marker_blocks():
        if expected.count(anchor) != 1:
            raise ProbeError("P9-D1 frozen marker anchor drift")
        lowered = block.lower()
        if any(token in lowered for token in MARKER_FORBIDDEN_TOKENS):
            raise ProbeError("P9-D1 marker block references forbidden live state")
        expected = expected.replace(anchor, (block + anchor) if before else (anchor + block), 1)
        blocks.append(block)
    return _preamble(fixture) + expected + CLONE_END, blocks


def _validate_static_clone(fixture: Mapping[str, Any]) -> dict[str, Any]:
    frozen, _fixture, _projection = _target_p9_b1_projection()
    expected, blocks = _build_expected_clone(frozen, fixture)
    actual = _read_regular(CLONE_DRIVER)
    if actual != expected:
        raise ProbeError("P9-D1 clone is not exactly checker-derived from frozen P9")
    preamble = _preamble(fixture)
    if not actual.startswith(preamble) or not actual.endswith(CLONE_END):
        raise ProbeError("P9-D1 clone envelope drift")
    reversed_body = actual[len(preamble):-len(CLONE_END)]
    for block in reversed(blocks):
        if reversed_body.count(block) != 1:
            raise ProbeError("P9-D1 marker block multiplicity drift")
        reversed_body = reversed_body.replace(block, b"", 1)
    if reversed_body != frozen:
        raise ProbeError("P9-D1 reverse marker deletion differs from frozen P9")
    return {
        "frozen_P9_driver_sha256": P9_DRIVER_SHA256,
        "frozen_P9_driver_size_bytes": P9_DRIVER_SIZE,
        "clone_driver_sha256": sha256_bytes(actual),
        "exact_marker_insertion_block_count": len(blocks),
        "forward_byte_construction_matches": True,
        "reverse_deletion_matches_frozen_P9": True,
        "marker_blocks_contain_no_forbidden_live_state_tokens": True,
        "P9_D0_resource_witness_construction_is_unreached_after_coarse_terminal": True,
    }


def _stage_probe_tree(staging: Path, policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    pins = _source_pins(policy)
    rows: list[dict[str, Any]] = []
    for relative in STAGED_PATHS:
        source = BASE / relative
        if not source.is_file() or source.is_symlink():
            raise ProbeError(f"invalid P9-D1 staged source: {relative}")
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target, follow_symlinks=False)
        body = source.read_bytes()
        staged = target.read_bytes()
        digest = sha256_bytes(body)
        if (
            pins[relative]["sha256"] != digest
            or pins[relative]["size_bytes"] != len(body)
            or staged != body
        ):
            raise ProbeError(f"P9-D1 staging custody drift: {relative}")
        rows.append({
            "relative_path": relative,
            "repository_sha256": digest,
            "staged_size_bytes": len(staged),
            "staged_sha256": sha256_bytes(staged),
            "byte_identical_to_repository": True,
        })
    return rows


class _PhaseCollector:
    def __init__(self, read_fd: int, *, maximum_line_bytes: int, maximum_total_bytes: int, maximum_events: int) -> None:
        self.read_fd = read_fd
        self.maximum_line_bytes = maximum_line_bytes
        self.maximum_total_bytes = maximum_total_bytes
        self.maximum_events = maximum_events
        self.lines: list[bytes] = []
        self.total_bytes = 0
        self.eof = False
        self.overflow = False
        self.partial = False
        self.failure = False

    def run(self) -> None:
        pending = bytearray()
        try:
            while True:
                block = os.read(self.read_fd, 4096)
                if not block:
                    self.eof = True
                    break
                self.total_bytes += len(block)
                if self.total_bytes > self.maximum_total_bytes:
                    self.overflow = True
                    continue
                pending.extend(block)
                while b"\n" in pending:
                    end = pending.index(0x0A) + 1
                    line = bytes(pending[:end])
                    del pending[:end]
                    if len(line) > self.maximum_line_bytes or len(self.lines) >= self.maximum_events:
                        self.overflow = True
                    else:
                        self.lines.append(line)
                if len(pending) >= self.maximum_line_bytes:
                    self.overflow = True
                    pending.clear()
        except OSError:
            self.failure = True
        finally:
            self.partial = bool(pending)
            try:
                os.close(self.read_fd)
            except OSError:
                pass


def _validate_phase_trace(collector: _PhaseCollector, fixture: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    if collector.overflow or collector.partial or collector.failure:
        raise ProbeError("invalid P9-D1 phase transport")
    protocol = fixture["phase_event_protocol"]
    events: list[dict[str, Any]] = []
    for sequence, line in enumerate(collector.lines):
        record = loads_json(line, "P9-D1 phase record")
        if (
            not isinstance(record, dict)
            or set(record) != {"event", "sequence"}
            or record.get("sequence") != sequence
            or record.get("event") not in PHASE_EVENTS
            or line != canonical_bytes(record) + b"\n"
        ):
            raise ProbeError("invalid P9-D1 phase record")
        events.append({"sequence": sequence, "event": record["event"]})
    names = [event["event"] for event in events]
    terminal = [
        branch for branch, sequence in protocol["legal_terminal_sequences"].items()
        if names == sequence
    ]
    prefixes = [
        branch for branch, sequence in protocol["legal_terminal_sequences"].items()
        if names == sequence[:len(names)]
    ]
    if not prefixes or len(terminal) > 1:
        raise ProbeError("P9-D1 phase trace is not a legal DFA prefix")
    return events, terminal[0] if terminal else None


def _terminate_scope(unit: str, process: subprocess.Popen[bytes]) -> None:
    subprocess.run(
        ("systemctl", "--user", "kill", "--kill-who=all", f"{unit}.scope"),
        check=False, capture_output=True,
    )
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _run_candidate(staging: Path, julia: Path, depot: Path, fixture: Mapping[str, Any], scratch_root: Path) -> dict[str, Any]:
    host = fixture["host_supervisor_caps"]
    protocol = fixture["phase_event_protocol"]
    scratch = scratch_root / "candidate"
    for name in ("depot", "home", "tmp"):
        (scratch / name).mkdir(parents=True, exist_ok=False)
    read_fd, write_fd = os.pipe()
    if read_fd < 3 or write_fd < 3:
        raise ProbeError("P9-D1 pipe descriptor is too small")
    os.set_inheritable(write_fd, True)
    collector = _PhaseCollector(
        read_fd,
        maximum_line_bytes=protocol["maximum_line_bytes_including_newline"],
        maximum_total_bytes=protocol["maximum_total_channel_bytes"],
        maximum_events=protocol["maximum_event_count"],
    )
    reader = threading.Thread(target=collector.run, name="p9-d1-phase-reader", daemon=True)
    reader.start()
    unit = "majorana-p9-d1-coarse-phase-" + uuid.uuid4().hex
    command = [
        "systemd-run", "--user", "--scope", "--quiet", f"--unit={unit}",
        "-p", f"MemoryMax={host['MemoryMax_bytes']}",
        "-p", f"MemorySwapMax={host['MemorySwapMax_bytes']}",
        "-p", f"RuntimeMaxSec={host['RuntimeMaxSec']}",
        "--", str(julia), "--startup-file=no", "--history-file=no",
        "--compiled-modules=no", f"--project={staging / 'majorana_certificate_p0'}",
        str(staging / CLONE_DRIVER), str(staging / FIXTURE_NAME),
        str(staging / P9_FIXTURE),
        str(staging / "majorana_certificate_p6_fixture.json"),
        str(staging / "majorana_certificate_p5_fixture.json"),
        str(staging / "majorana_certificate_p4_fixture.json"),
        str(staging / "majorana_certificate_p3_fixture.json"),
        str(staging / "majorana_certificate_p2_fixture.json"),
        P9_MODE, str(write_fd),
    ]
    environment = os.environ.copy()
    environment.update({
        "HOME": str(scratch / "home"), "TMPDIR": str(scratch / "tmp"),
        "LANG": "C", "LC_ALL": "C", "TZ": "UTC",
        "JULIA_DEPOT_PATH": f"{scratch / 'depot'}:{depot}",
        "JULIA_LOAD_PATH": "@", "JULIA_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1", "JULIA_PKG_OFFLINE": "true",
        "JULIA_PKG_SERVER": "",
    })
    process: subprocess.Popen[bytes] | None = None
    timed_out = False
    stdout = b""
    stderr = b""
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            pass_fds=(write_fd,), close_fds=True,
        )
        os.close(write_fd)
        write_fd = -1
        try:
            stdout, stderr = process.communicate(timeout=host["outer_safety_timeout_seconds"])
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_scope(unit, process)
            stdout, stderr = process.communicate()
        returncode = process.returncode
        started = True
    except OSError:
        if process is not None and process.poll() is None:
            _terminate_scope(unit, process)
        returncode = -1
        started = False
    finally:
        if write_fd >= 0:
            os.close(write_fd)
        reader.join(timeout=15)
    if reader.is_alive():
        raise ProbeError("P9-D1 phase reader did not terminate")
    if stdout:
        raise ProbeError("invalid P9-D1 probe: stdout is not empty")
    if returncode == INVALID_D1_PROBE_EXIT_CODE:
        raise ProbeError("invalid P9-D1 probe: inner custody or protocol rejection")
    events, terminal = _validate_phase_trace(collector, fixture)
    host_failed = (
        not started
        or timed_out
        or returncode != 0
        or len(stderr) > host["maximum_stderr_bytes"]
        or not collector.eof
    )
    complete = terminal is not None
    if not host_failed and not complete:
        raise ProbeError("P9-D1 clean process lacks a complete terminal sequence")
    if not host_failed and complete:
        status = "COMPLETED_PHASE_DIAGNOSTIC"
        trace_status = "COMPLETE_TERMINAL_SEQUENCE"
    else:
        status = "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
        trace_status = "LEGAL_PREFIX_INTERRUPTED"
    observation = {
        "status": status,
        "diagnostic_terminal_branch": terminal,
        "phase_trace_status": trace_status,
        "phase_events": events,
        "phase_event_count": len(events),
        "phase_trace_protocol_sha256": canonical_sha256(events),
        "last_phase_event": events[-1]["event"] if events else None,
        "outer_timeout_triggered": timed_out,
        "host_failure_observed": host_failed,
        "resource_witness": None,
        "host_failure_has_no_mathematical_authority": True,
    }
    _validate_observation(observation, fixture)
    return observation


def _validate_observation(observation: Any, fixture: Mapping[str, Any]) -> None:
    expected = {
        "status", "diagnostic_terminal_branch", "phase_trace_status",
        "phase_events", "phase_event_count", "phase_trace_protocol_sha256",
        "last_phase_event", "outer_timeout_triggered", "host_failure_observed",
        "resource_witness", "host_failure_has_no_mathematical_authority",
    }
    if not isinstance(observation, dict) or set(observation) != expected:
        raise ProbeError("P9-D1 observation key set drift")
    if observation["status"] not in {
        "COMPLETED_PHASE_DIAGNOSTIC", "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
    }:
        raise ProbeError("P9-D1 observation status drift")
    if (
        type(observation["outer_timeout_triggered"]) is not bool
        or type(observation["host_failure_observed"]) is not bool
        or observation["resource_witness"] is not None
        or observation["host_failure_has_no_mathematical_authority"] is not True
    ):
        raise ProbeError("P9-D1 observation host boundary drift")
    events = observation["phase_events"]
    if not isinstance(events, list) or len(events) != observation["phase_event_count"]:
        raise ProbeError("P9-D1 phase-event count drift")
    if len(events) > fixture["phase_event_protocol"]["maximum_event_count"]:
        raise ProbeError("P9-D1 phase-event cap drift")
    names: list[str] = []
    for sequence, event in enumerate(events):
        if not isinstance(event, dict) or set(event) != {"sequence", "event"}:
            raise ProbeError("P9-D1 reported phase row drift")
        if event.get("sequence") != sequence or event.get("event") not in PHASE_EVENTS:
            raise ProbeError("P9-D1 reported phase order drift")
        names.append(event["event"])
    if observation["phase_trace_protocol_sha256"] != canonical_sha256(events):
        raise ProbeError("P9-D1 phase protocol digest drift")
    if observation["last_phase_event"] != (names[-1] if names else None):
        raise ProbeError("P9-D1 last phase event drift")
    terminals = fixture["phase_event_protocol"]["legal_terminal_sequences"]
    prefixes = [branch for branch, sequence in terminals.items() if names == sequence[:len(names)]]
    exact = [branch for branch, sequence in terminals.items() if names == sequence]
    if not prefixes or len(exact) > 1:
        raise ProbeError("P9-D1 report trace grammar drift")
    if observation["status"] == "COMPLETED_PHASE_DIAGNOSTIC":
        if (
            observation["host_failure_observed"]
            or observation["outer_timeout_triggered"]
            or len(exact) != 1
            or observation["diagnostic_terminal_branch"] != exact[0]
            or observation["phase_trace_status"] != "COMPLETE_TERMINAL_SEQUENCE"
        ):
            raise ProbeError("P9-D1 completed observation drift")
    elif (
        not observation["host_failure_observed"]
        or observation["phase_trace_status"] != "LEGAL_PREFIX_INTERRUPTED"
        or observation["diagnostic_terminal_branch"] != (exact[0] if exact else None)
    ):
        raise ProbeError("P9-D1 indeterminate observation drift")


def _validate_preprobe_commit_identity(commit: str) -> None:
    _require_sha(commit, "P9-D1 preprobe")
    if _parents(commit) != (P9_RESULT_COMMIT,):
        raise ProbeError("P9-D1 preprobe direct-parent drift")
    if _changed_paths(commit) != tuple(sorted(PREPROBE_CHANGED_PATHS)):
        raise ProbeError("P9-D1 preprobe changed-path set drift")
    for path in PREPROBE_CHANGED_PATHS:
        if _git_blob_optional(P9_RESULT_COMMIT, path) is not None:
            raise ProbeError("P9-D1 preprobe changed a non-new path")
        relative = path.removeprefix(ROOT)
        if _git_blob(commit, path) != _read_regular(relative):
            raise ProbeError("P9-D1 preprobe Git blob/current byte mismatch")
    if _git_blob_optional(commit, ROOT + REPORT_NAME) is not None:
        raise ProbeError("P9-D1 preprobe already contains a result report")


def _validate_result_commit_identity(commit: str, report: Mapping[str, Any]) -> None:
    """Require the immutable B1 receipt to add only the canonical report."""
    _require_sha(commit, "P9-D1 result")
    preprobe = report.get("preprobe_commit_sha")
    if not isinstance(preprobe, str):
        raise ProbeError("P9-D1 result report preprobe receipt is malformed")
    _require_sha(preprobe, "P9-D1 report preprobe")
    if _parents(commit) != (preprobe,):
        raise ProbeError("P9-D1 result direct-parent drift")
    if _changed_paths(commit) != RESULT_CHANGED_PATHS:
        raise ProbeError("P9-D1 result changed-path set drift")
    if _git_blob_optional(preprobe, ROOT + REPORT_NAME) is not None:
        raise ProbeError("P9-D1 result parent already contains a report")
    report_blob = _git_blob(commit, ROOT + REPORT_NAME)
    if report_blob != canonical_bytes(report):
        raise ProbeError("P9-D1 result Git blob is not canonical report bytes")
    if report_blob != _read_regular(REPORT_NAME):
        raise ProbeError("P9-D1 result Git blob/current byte mismatch")


def _index_blob(path: str) -> bytes:
    raw = _git_bytes("ls-files", "--stage", "-z", "--", path)
    rows = raw.split(b"\0")
    if rows[-1] != b"" or len(rows) != 2:
        raise ProbeError("unexpected P9-D1 index record count")
    metadata, separator, actual = rows[0].partition(b"\t")
    fields = metadata.split(b" ")
    if separator != b"\t" or actual != path.encode("utf-8") or len(fields) != 3 or fields[0] != b"100644" or fields[2] != b"0":
        raise ProbeError("P9-D1 staged path is not a stage-zero regular blob")
    return _git_bytes("cat-file", "blob", fields[1].decode("ascii"))


def _validate_staged_preprobe() -> None:
    if _git_text("rev-parse", "HEAD").strip() != P9_RESULT_COMMIT:
        raise ProbeError("P9-D1 staged preprobe must start at P9 B1")
    raw = _git_bytes("diff", "--cached", "--name-only", "-z").split(b"\0")
    added = _git_bytes("diff", "--cached", "--name-only", "--diff-filter=A", "-z").split(b"\0")
    if raw[-1] != b"" or added[-1] != b"":
        raise ProbeError("P9-D1 staged paths are not NUL terminated")
    paths = tuple(sorted(item.decode("utf-8") for item in raw[:-1]))
    additions = tuple(sorted(item.decode("utf-8") for item in added[:-1]))
    if paths != tuple(sorted(PREPROBE_CHANGED_PATHS)) or paths != additions:
        raise ProbeError("P9-D1 staged preprobe path set drift")
    for path in PREPROBE_CHANGED_PATHS:
        if _index_blob(path) != _read_regular(path.removeprefix(ROOT)):
            raise ProbeError("P9-D1 staged/current byte mismatch")


def verify_preprobe() -> dict[str, Any]:
    policy = validate_policy(load_json(BASE / POLICY_NAME), require_report_absent=True)
    head = _git_text("rev-parse", "HEAD").strip()
    if head == P9_RESULT_COMMIT:
        _validate_staged_preprobe()
    else:
        if _status_paths():
            raise ProbeError("frozen P9-D1 preprobe worktree is not clean")
        _validate_preprobe_commit_identity(head)
    return {"status": "VERIFIED_P9_D1_COARSE_PHASE_PREPROBE", "policy_id": policy["policy_id"]}


def _acquire_claim(commit: str) -> Path:
    claim = BASE / EXECUTION_CLAIM_NAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(claim, flags, 0o600)
    except FileExistsError as error:
        raise ProbeError("P9-D1 execution was already claimed") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write((commit + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def _write_canonical_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise ProbeError("P9-D1 report already exists")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


S0_ADMISSION = {
    "status": "NOT_ESTABLISHED_BY_P9_D1_COARSE_PHASE_DIAGNOSTIC",
    "derived_from_D1": False,
    "P9_B1_status_unchanged": P9_B1_ALLOWED_PROJECTION["S0_admission_status"],
    "same_host_admission_as_P9_D0": True,
}


def run_probe(preprobe_commit: str, julia: Path, depot: Path, output: Path) -> Mapping[str, Any]:
    policy = validate_policy(load_json(BASE / POLICY_NAME), require_report_absent=True)
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    _validate_preprobe_commit_identity(preprobe_commit)
    if _git_text("rev-parse", "HEAD").strip() != preprobe_commit or _status_paths():
        raise ProbeError("P9-D1 must execute a clean frozen preprobe")
    if output.resolve() != (BASE / REPORT_NAME).resolve():
        raise ProbeError("P9-D1 report path must be canonical")
    julia = julia.resolve()
    depot = depot.resolve()
    if not julia.is_file() or file_sha256(julia) != fixture["runtime_custody"]["julia_executable_sha256"]:
        raise ProbeError("P9-D1 Julia executable custody mismatch")
    if not depot.is_dir():
        raise ProbeError("P9-D1 depot is missing")
    for executable in ("systemd-run", "systemctl"):
        if shutil.which(executable) is None:
            raise ProbeError(f"P9-D1 missing executable: {executable}")
    with tempfile.TemporaryDirectory(prefix="majorana-p9-d1-") as temporary:
        root = Path(temporary)
        staging = root / "staging"
        staging.mkdir()
        manifest = _stage_probe_tree(staging, policy)
        scratch = root / "scratch"
        scratch.mkdir()
        claim = _acquire_claim(preprobe_commit)
        observation = _run_candidate(staging, julia, depot, fixture, scratch)
    report = {
        "schema_version": 1,
        "report_type": REPORT_TYPE,
        "policy_id": POLICY_ID,
        "policy_sha256": file_sha256(BASE / POLICY_NAME),
        "fixture_id": FIXTURE_ID,
        "fixture_sha256": file_sha256(BASE / FIXTURE_NAME),
        "fixture_canonical_sha256": canonical_sha256(fixture),
        "preprobe_commit_sha": preprobe_commit,
        "P9_B1_parent_commit_sha": P9_RESULT_COMMIT,
        "P9_B1_parent_report_sha256": P9_REPORT_SHA256,
        "scientific_authority": "NONE",
        "certificate_eligible": False,
        "result_contract_eligible": False,
        "staging_manifest": manifest,
        "staging_manifest_sha256": canonical_sha256(manifest),
        "source_clone_custody": _validate_static_clone(fixture),
        "observation": observation,
        "S0_admission": S0_ADMISSION,
        "authority_exclusions": fixture["authority_exclusions"],
    }
    validate_report(report)
    _write_canonical_json_exclusive(output, report)
    claim.unlink()
    return report


def _validate_manifest(rows: Any, policy: Mapping[str, Any], digest: Any) -> None:
    if not isinstance(rows, list) or [row.get("relative_path") for row in rows if isinstance(row, dict)] != list(STAGED_PATHS):
        raise ProbeError("P9-D1 staging manifest path drift")
    pins = _source_pins(policy)
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "repository_sha256", "staged_size_bytes",
            "staged_sha256", "byte_identical_to_repository",
        }:
            raise ProbeError("malformed P9-D1 staging row")
        body = _read_regular(row["relative_path"])
        digest_now = sha256_bytes(body)
        if (
            row["repository_sha256"] != pins[row["relative_path"]]["sha256"]
            or row["staged_size_bytes"] != len(body)
            or row["staged_sha256"] != digest_now
            or row["repository_sha256"] != row["staged_sha256"]
            or row["byte_identical_to_repository"] is not True
        ):
            raise ProbeError("P9-D1 staging manifest custody drift")
    if digest != canonical_sha256(rows):
        raise ProbeError("P9-D1 staging manifest digest drift")


def validate_report(
    report: Any, *, require_result_commit: bool = False,
) -> Mapping[str, Any]:
    policy = validate_policy(load_json(BASE / POLICY_NAME), require_report_absent=False)
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    expected = {
        "schema_version", "report_type", "policy_id", "policy_sha256",
        "fixture_id", "fixture_sha256", "fixture_canonical_sha256",
        "preprobe_commit_sha", "P9_B1_parent_commit_sha", "P9_B1_parent_report_sha256",
        "scientific_authority", "certificate_eligible", "result_contract_eligible",
        "staging_manifest", "staging_manifest_sha256", "source_clone_custody",
        "observation", "S0_admission", "authority_exclusions",
    }
    if not isinstance(report, dict) or set(report) != expected:
        raise ProbeError("P9-D1 report key set drift")
    if (
        report.get("schema_version") != 1
        or report.get("report_type") != REPORT_TYPE
        or report.get("policy_id") != POLICY_ID
        or report.get("fixture_id") != FIXTURE_ID
        or report.get("P9_B1_parent_commit_sha") != P9_RESULT_COMMIT
        or report.get("P9_B1_parent_report_sha256") != P9_REPORT_SHA256
        or report.get("scientific_authority") != "NONE"
        or report.get("certificate_eligible") is not False
        or report.get("result_contract_eligible") is not False
    ):
        raise ProbeError("P9-D1 report identity or authority drift")
    if (
        report["policy_sha256"] != file_sha256(BASE / POLICY_NAME)
        or report["fixture_sha256"] != file_sha256(BASE / FIXTURE_NAME)
        or report["fixture_canonical_sha256"] != canonical_sha256(fixture)
        or report["source_clone_custody"] != _validate_static_clone(fixture)
        or report["S0_admission"] != S0_ADMISSION
        or report["authority_exclusions"] != fixture["authority_exclusions"]
    ):
        raise ProbeError("P9-D1 report source custody drift")
    _validate_preprobe_commit_identity(report["preprobe_commit_sha"])
    _validate_manifest(report["staging_manifest"], policy, report["staging_manifest_sha256"])
    _validate_observation(report["observation"], fixture)
    if require_result_commit:
        _validate_result_commit_identity(
            _git_text("rev-parse", "HEAD").strip(), report,
        )
    return report


def verify_report(output: Path) -> Mapping[str, Any]:
    if output.resolve() != (BASE / REPORT_NAME).resolve():
        raise ProbeError("P9-D1 report path must be canonical")
    report = validate_report(load_json(output), require_result_commit=True)
    if output.read_bytes() != canonical_bytes(report):
        raise ProbeError("P9-D1 report is not canonical JSON")
    if _status_paths():
        raise ProbeError("frozen P9-D1 result worktree is not clean")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-preprobe", action="store_true")
    group.add_argument("--run", action="store_true")
    group.add_argument("--verify-report", action="store_true")
    parser.add_argument("--preprobe-commit")
    parser.add_argument("--julia", type=Path)
    parser.add_argument("--depot", type=Path)
    parser.add_argument("--output", type=Path, default=BASE / REPORT_NAME)
    args = parser.parse_args(argv)
    try:
        if args.verify_preprobe:
            result = verify_preprobe()
        elif args.run:
            if not all((args.preprobe_commit, args.julia, args.depot)):
                parser.error("--run requires --preprobe-commit, --julia, and --depot")
            report = run_probe(args.preprobe_commit, args.julia, args.depot, args.output)
            result = {
                "status": "COMPLETED_P9_D1_COARSE_PHASE_PROBE",
                "observation_status": report["observation"]["status"],
                "last_phase_event": report["observation"]["last_phase_event"],
                "report_sha256": file_sha256(args.output),
            }
        else:
            report = verify_report(args.output)
            result = {
                "status": "VERIFIED_P9_D1_COARSE_PHASE_REPORT",
                "observation_status": report["observation"]["status"],
                "last_phase_event": report["observation"]["last_phase_event"],
                "report_sha256": file_sha256(args.output),
            }
    except ProbeError as error:
        print(f"P9_D1_PROBE_ERROR: {error}", file=sys.stderr)
        return 2
    print(canonical_bytes(result).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
