#!/usr/bin/env python3
"""Public-synthetic native sandbox viability KAT for Engram G1.4.

This is deliberately a negative, default-off gate.  It launches one fixed public
probe only to determine whether the registered Darwin/Linux primitives can deny
every wall-clock path.  An unsupported result is terminal and cannot authorize a
candidate, private material, G1.4 execution, or production use.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform as host_platform
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
CONTRACT_PATH = (
    SCRIPT_DIR / "fixtures/engram_g14_native_sandbox_adapter_kat_contract_v0.json"
)
FIXTURE_PATH = (
    SCRIPT_DIR / "fixtures/engram_g14_native_sandbox_adapter_kat_fixture_v0.json"
)
PROBE_PATH = SCRIPT_DIR / "fixtures/engram_g14_native_sandbox_adapter_probe_v0.c"

CONTRACT_SHA256 = "7018486db2dc3f3e751d66547828756e6d61aea91df7b3f12b7bccc9cd78615d"
FIXTURE_SHA256 = "e4e23d1a6aea78ee60047c96f76249137b2c139ced18d6731754dca229b6b239"
CONTRACT_CANONICAL_SHA256 = (
    "ff4be20f7c8779fbe7e8e9d2e4e944a79510cb6bc5774484e2d5996c8440edf2"
)
FIXTURE_CANONICAL_SHA256 = (
    "ae11f5957a7172611dd10c714661f42f1ef000976d1dfda8fe19252add3366c0"
)
PROBE_SOURCE_SHA256 = "0824beab20f922548f0033910e1ad3eb55695c0bb802488d0e9e531279199d12"
PREDECESSOR_CONTRACT_SHA256 = (
    "075dd9be4f6097e539db62025e6420b9add0efc030c528c065b612a77f5d78e0"
)
PREDECESSOR_VALIDATOR_SHA256 = (
    "91587985f1add6d71daf6e07b3b7289d33950f97b18ff810bfe20d7d23a6800c"
)
PREDECESSOR_CHECKER_SHA256 = (
    "b4227c3559701d458a36053ca9def72c20b71b06735d84a364feb840056f472e"
)
PREDECESSOR_SHELL_SHA256 = (
    "65e49095cd05c5f119a51ee46a57f64b291a264ff224ecf6a1edd3ebbcd3648e"
)
NONO_VERSION = "0.53.0"
NONO_CHECKSUM = "ae7eb523cc2036e9ad6527411c3da5dc2172dc454cc3447a03b910420a39bfee"
MODE = "PUBLIC_SYNTHETIC_NATIVE_SANDBOX_ADAPTER_KAT"
VERDICT = "REJECTED_FAIL_CLOSED_WALL_CLOCK_UNCONFINED_NO_AUTHORITY"
AUTHORITY_CLASS = "NONE_PUBLIC_SYNTHETIC_NEGATIVE_KAT_ONLY"
ZERO_SHA256 = "0" * 64
MAX_JSON_BYTES = 1_000_000
MASK_DIRECT_SYSCALL = 1 << 3
MASK_LIBC_PATHS = (1 << 0) | (1 << 1) | (1 << 2)
OUTPUT_RE = re.compile(rb"clock_mask=([0-9]{1,10})\n\Z")

DARWIN_DIRECT_SYSCALL_PROFILE = """(version 1)
(allow default)
(deny syscall-unix (syscall-number SYS_gettimeofday))
"""
DARWIN_SYMBOLIC_CLOCK_PROFILE = """(version 1)
(allow default)
(deny system-clock)
"""
DARWIN_SYMBOLIC_ERROR_RE = re.compile(
    rb"sandbox-exec: unbound variable: system-clock at <input string>, line 3, "
    rb"column 7\n(?:\nBacktrace: \n<input string>:3:7:\n\tsystem-clock\n)?\n?\Z"
)

EXPECTED_PHASE_ROWS = (
    (
        "artifact_preflight",
        "agent_bridge.engram_g1_4_native_kat_artifact_preflight_receipt.v0",
        "supervisor_prelaunch_verifier",
        (
            "contract_sha256",
            "probe_source_sha256",
            "probe_build_sha256",
            "dependency_lock_sha256",
            "fixture_sha256",
        ),
    ),
    (
        "one_shot_claim",
        "agent_bridge.engram_g1_4_native_kat_one_shot_claim_receipt.v0",
        "supervisor_attempt_registry",
        ("run_id_commitment_sha256", "claim_sequence", "claim_consumed"),
    ),
    (
        "platform_support",
        "agent_bridge.engram_g1_4_native_kat_platform_support_receipt.v0",
        "supervisor_captured_platform_probe",
        (
            "platform",
            "kernel_and_abi_commitment_sha256",
            "primitive_support_matrix_sha256",
            "all_required_controls_supported",
        ),
    ),
    (
        "policy_compile",
        "agent_bridge.engram_g1_4_native_kat_policy_compile_receipt.v0",
        "supervisor_captured_policy_compiler",
        (
            "policy_input_sha256",
            "generated_policy_sha256",
            "dependency_and_rule_order_sha256",
            "compile_succeeded",
        ),
    ),
    (
        "policy_apply",
        "agent_bridge.engram_g1_4_native_kat_policy_apply_receipt.v0",
        "native_apply_boundary_captured_by_supervisor",
        (
            "generated_policy_sha256",
            "subject_process_identity_commitment_sha256",
            "apply_result_code",
            "apply_succeeded",
        ),
    ),
    (
        "active_attestation",
        "agent_bridge.engram_g1_4_native_kat_active_attestation_receipt.v0",
        "native_subject_boundary_captured_by_supervisor",
        (
            "support_receipt_sha256",
            "apply_receipt_sha256",
            "subject_process_identity_commitment_sha256",
            "active_reported",
        ),
    ),
    (
        "negative_controls",
        "agent_bridge.engram_g1_4_native_kat_negative_controls_receipt.v0",
        "supervisor_control_runner",
        (
            "control_fixture_sha256",
            "control_attempt_set_sha256",
            "live_control_count",
            "all_controls_unambiguous",
        ),
    ),
    (
        "allowed_canaries",
        "agent_bridge.engram_g1_4_native_kat_allowed_canaries_receipt.v0",
        "sandboxed_probe_captured_by_supervisor",
        (
            "subject_process_identity_commitment_sha256",
            "allowed_canary_observations_sha256",
            "allowed_canary_count",
            "all_allowed_canaries_matched",
        ),
    ),
    (
        "denied_canaries",
        "agent_bridge.engram_g1_4_native_kat_denied_canaries_receipt.v0",
        "sandboxed_probe_captured_by_supervisor",
        (
            "subject_process_identity_commitment_sha256",
            "denied_canary_observations_sha256",
            "denied_canary_count",
            "all_denied_canaries_matched",
        ),
    ),
    (
        "cleanup",
        "agent_bridge.engram_g1_4_native_kat_cleanup_receipt.v0",
        "supervisor_cleanup_verifier",
        (
            "synthetic_root_commitment_sha256",
            "cleanup_target_set_sha256",
            "residue_count",
            "cleanup_verified",
        ),
    ),
    (
        "receipt_finalize",
        "agent_bridge.engram_g1_4_native_kat_final_receipt.v0",
        "supervisor_receipt_finalizer",
        (
            "previous_event_sha256",
            "expected_chain_head_sha256",
            "authority_class",
            "production_admissible",
            "g1_4_execution_open",
            "verdict",
        ),
    ),
)
PHASE_SOURCES = {row[0]: row[2] for row in EXPECTED_PHASE_ROWS}
EXPECTED_CANARY_ROWS = (
    ("candidate_code_read", "allow", "native_kernel"),
    ("dependency_read", "allow", "native_kernel"),
    ("ephemeral_scratch_write", "allow", "native_kernel"),
    ("repository_metadata_read", "deny", "native_kernel"),
    ("private_manifest_read", "deny", "native_kernel"),
    ("live_store_read", "deny", "native_kernel"),
    ("network_connect", "deny", "native_kernel"),
    ("subprocess_spawn", "deny", "native_kernel"),
    ("dynamic_plugin_load", "deny", "native_kernel"),
    ("non_scratch_write", "deny", "native_kernel"),
    ("wall_clock_read", "deny", "native_kernel"),
    ("external_entropy_read", "deny", "native_kernel"),
    ("extra_inherited_fd_use", "deny", "launch_boundary"),
    ("free_form_output", "deny", "supervisor_mediation"),
)
EXPECTED_PREDECESSOR = {
    "contract_id": "engram_g14_native_sandbox_adapter_preregistration_20260718",
    "contract_sha256": PREDECESSOR_CONTRACT_SHA256,
    "integration_commit": "908412b8209056a90b3be5c2f93896c763d31311",
}
EXPECTED_SCOPE = {
    "mode": MODE,
    "enabled_by_default": False,
    "public_synthetic_only": True,
    "fixed_probe_only": True,
    "purpose": "native_wall_clock_confinement_viability",
    "successful_native_adapter_claim_representable": False,
    "unsupported_platform_fails_closed": True,
    "unsandboxed_fallback_allowed": False,
}
EXPECTED_DEPENDENCY_LOCK = {
    "crate": "nono",
    "version": NONO_VERSION,
    "crates_io_checksum_sha256": NONO_CHECKSUM,
    "agent_cargo_toml_sha256": "64bcf1afb4d3982ac6205b1c74bea322dbe58b61079e44dcc0bce1fd7c976c02",
    "existing_workspace_sandbox_is_admissible_evidence": False,
}
EXPECTED_PROBE = {
    "source_path": "scripts/eval/fixtures/engram_g14_native_sandbox_adapter_probe_v0.c",
    "source_sha256": PROBE_SOURCE_SHA256,
    "compiler_argv": [
        "/usr/bin/cc",
        "-std=c11",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
    ],
    "accepted_probe_argv_in_order": ["clock-control", "clock-filtered"],
    "output_schema": "clock_mask_equals_unsigned_decimal_lf",
    "max_stdout_bytes": 64,
    "max_stderr_bytes": 4096,
    "timeout_seconds": 5,
    "accepts_arbitrary_path_command_or_environment": False,
}
EXPECTED_PLATFORM_EXPECTATIONS = {
    "darwin": {
        "primitive": "seatbelt_sandbox_exec",
        "control_mask_nonzero": True,
        "direct_syscall_filter_effective": True,
        "residual_libc_or_commpage_clock_path": True,
        "symbolic_system_clock_rule_compiles": False,
        "all_required_controls_supported": False,
        "failure_code": "WALL_CLOCK_UNCONFINED",
    },
    "linux": {
        "primitive": "seccomp_bpf_direct_syscall_filter",
        "control_mask_nonzero": True,
        "direct_syscall_filter_effective": True,
        "residual_libc_or_vdso_clock_path": True,
        "all_required_controls_supported": False,
        "failure_code": "WALL_CLOCK_UNCONFINED",
    },
}
EXPECTED_DURABILITY = {
    "state_namespace": "engram_g14_public_synthetic_native_kat",
    "claim_store": "attempt_claims_v0",
    "prelaunch_anchor_store": "prelaunch_anchors_v0",
    "rollback_obligation_store": "rollback_obligations_v0",
    "rollback_lesson_store": "rollback_lessons_v0",
    "writes_use_create_new_fsync_file_and_directory_reopen_verify": True,
    "unresolved_rollback_obligation_blocks_new_claim": True,
    "durable_verified_lesson_allows_obligation_clear": True,
    "historical_valid_lesson_permanently_blocks_new_claim": False,
    "lesson_integrity_failure_is_absorbing": True,
    "lesson_writer_reopens_and_verifies_before_acknowledgement": True,
    "lesson_schema": "agent_bridge.engram_g1_4_native_kat_rollback_failure_lesson.v0",
}
EXPECTED_RESULT = {
    "verdict": VERDICT,
    "receipt_count": 11,
    "native_adapter_implemented": False,
    "native_enforcement_verified": False,
    "production_admissible": False,
    "g1_4_execution_open": False,
    "only_permitted_next_action": "separate_design_and_security_review_for_stronger_clock_isolation_primitive",
}
EXPECTED_NONCLAIMS = {
    "candidate_source_accessed": False,
    "private_material_accessed": False,
    "full_fourteen_canary_run_executed": False,
    "nono_policy_applied": False,
    "workspace_sandbox_modified": False,
    "runtime_or_mcp_surface_added": False,
    "deployment_performed": False,
}


class KatError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _fail(code: str, message: str) -> None:
    raise KatError(code, message)


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        _fail(code, message)


def _reject_float(_: str) -> None:
    _fail("E_JSON_FLOAT", "floating-point JSON values are forbidden")


def _reject_constant(_: str) -> None:
    _fail("E_JSON_CONSTANT", "non-finite JSON values are forbidden")


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("E_JSON_DUPLICATE", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_bytes(raw: bytes) -> Any:
    _require(len(raw) <= MAX_JSON_BYTES, "E_SIZE", "JSON artifact exceeds bound")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        _fail("E_UTF8", f"JSON artifact is not UTF-8: {exc}")
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_no_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except KatError:
        raise
    except json.JSONDecodeError as exc:
        _fail("E_JSON", f"invalid JSON: {exc}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def read_stable_regular(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        _fail("E_ARTIFACT", f"cannot stat {path.name}: {exc}")
    _require(stat.S_ISREG(before.st_mode), "E_ARTIFACT", f"not regular: {path.name}")
    _require(not path.is_symlink(), "E_ARTIFACT", f"symlink forbidden: {path.name}")
    _require(before.st_size <= max_bytes, "E_SIZE", f"artifact too large: {path.name}")
    try:
        raw = path.read_bytes()
        after = path.lstat()
    except OSError as exc:
        _fail("E_ARTIFACT", f"cannot read {path.name}: {exc}")
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    _require(identity_before == identity_after, "E_ARTIFACT_RACE", path.name)
    _require(len(raw) <= max_bytes, "E_SIZE", f"artifact too large: {path.name}")
    return raw


def load_pinned_json(path: Path, expected_sha256: str) -> dict[str, Any]:
    raw = read_stable_regular(path)
    _require(sha256_bytes(raw) == expected_sha256, "E_DIGEST", path.name)
    value = strict_json_bytes(raw)
    _require(type(value) is dict, "E_SCHEMA", f"{path.name} must be an object")
    return value


def _exact_keys(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    _require(type(value) is dict, "E_SCHEMA", f"{path} must be an object")
    actual = set(value)
    _require(actual == expected, "E_SCHEMA", f"{path} keys differ")
    return value


def _exact(value: Any, expected: Any, path: str) -> None:
    _require(type(value) is type(expected), "E_SCHEMA", f"{path} type differs")
    _require(value == expected, "E_SCHEMA", f"{path} differs")


def implementation_sha256() -> str:
    return sha256_bytes(
        read_stable_regular(Path(__file__).resolve(), max_bytes=2_000_000)
    )


def validate_contract(contract: dict[str, Any]) -> None:
    expected_top = {
        "schema",
        "contract_id",
        "date",
        "predecessor",
        "scope",
        "dependency_lock",
        "probe",
        "platform_expectations",
        "phases_in_order",
        "canaries_in_order",
        "durability",
        "expected_result",
        "nonclaims",
    }
    _exact_keys(contract, expected_top, "contract")
    _exact(
        contract["schema"],
        "agent_bridge.engram_g1_4_native_sandbox_adapter_kat_contract.v0",
        "contract.schema",
    )
    _exact(
        contract["contract_id"],
        "engram_g14_native_sandbox_adapter_kat_20260718",
        "contract.contract_id",
    )
    _exact(contract["date"], "2026-07-18", "contract.date")
    _exact(contract["predecessor"], EXPECTED_PREDECESSOR, "contract.predecessor")
    _exact(contract["scope"], EXPECTED_SCOPE, "contract.scope")
    _exact(
        contract["dependency_lock"],
        EXPECTED_DEPENDENCY_LOCK,
        "contract.dependency_lock",
    )
    _exact(contract["probe"], EXPECTED_PROBE, "contract.probe")
    _exact(
        contract["platform_expectations"],
        EXPECTED_PLATFORM_EXPECTATIONS,
        "contract.platform_expectations",
    )
    phases = contract["phases_in_order"]
    _require(
        type(phases) is list and len(phases) == 11, "E_SCHEMA", "eleven phases required"
    )
    for index, row in enumerate(phases):
        _exact_keys(
            row,
            {"phase", "schema", "evidence_source", "payload_fields_in_order"},
            f"contract.phases_in_order[{index}]",
        )
    observed_phases = tuple(
        (
            row["phase"],
            row["schema"],
            row["evidence_source"],
            tuple(row["payload_fields_in_order"]),
        )
        for row in phases
    )
    _exact(observed_phases, EXPECTED_PHASE_ROWS, "contract.phases_in_order")
    canaries = contract["canaries_in_order"]
    _require(
        type(canaries) is list and len(canaries) == 14,
        "E_SCHEMA",
        "fourteen canaries required",
    )
    for index, row in enumerate(canaries):
        _exact_keys(
            row,
            {"name", "expected", "owner"},
            f"contract.canaries_in_order[{index}]",
        )
    observed_canaries = tuple(
        (row["name"], row["expected"], row["owner"]) for row in canaries
    )
    _exact(observed_canaries, EXPECTED_CANARY_ROWS, "contract.canaries_in_order")
    _exact(contract["durability"], EXPECTED_DURABILITY, "contract.durability")
    _exact(contract["expected_result"], EXPECTED_RESULT, "contract.expected_result")
    _exact(contract["nonclaims"], EXPECTED_NONCLAIMS, "contract.nonclaims")


def validate_fixture(fixture: dict[str, Any]) -> None:
    _exact_keys(
        fixture,
        {
            "schema",
            "fixture_id",
            "mode",
            "public_synthetic_fixture",
            "contains_candidate_or_private_material",
            "run_id",
            "probe_cases_in_order",
            "expected_terminal_state",
            "expected_failure_code",
            "expected_verdict",
        },
        "fixture",
    )
    _exact(
        fixture["schema"],
        "agent_bridge.engram_g1_4_native_sandbox_adapter_kat_fixture.v0",
        "fixture.schema",
    )
    _exact(fixture["mode"], MODE, "fixture.mode")
    _exact(
        fixture["public_synthetic_fixture"], True, "fixture.public_synthetic_fixture"
    )
    _exact(
        fixture["contains_candidate_or_private_material"],
        False,
        "fixture.contains_candidate_or_private_material",
    )
    _exact(
        fixture["probe_cases_in_order"],
        ["clock_control", "direct_syscall_clock_filter", "symbolic_full_clock_filter"],
        "fixture.probe_cases_in_order",
    )
    _require(
        re.fullmatch(r"[a-z0-9-]{20,96}", fixture["run_id"]) is not None,
        "E_SCHEMA",
        "fixture.run_id",
    )
    _exact(
        fixture["expected_terminal_state"],
        "REJECTED_FAIL_CLOSED",
        "fixture.expected_terminal_state",
    )
    _exact(
        fixture["expected_failure_code"],
        "WALL_CLOCK_UNCONFINED",
        "fixture.expected_failure_code",
    )
    _exact(fixture["expected_verdict"], VERDICT, "fixture.expected_verdict")


def validate_predecessors(repo_root: Path) -> None:
    expected = {
        repo_root
        / "scripts/eval/fixtures/engram_g14_native_sandbox_adapter_preregistration_contract_v0.json": PREDECESSOR_CONTRACT_SHA256,
        repo_root
        / "scripts/eval/engram_g14_native_sandbox_adapter_preregistration.py": PREDECESSOR_VALIDATOR_SHA256,
        repo_root
        / "scripts/eval/check_engram_g14_native_sandbox_adapter_preregistration.py": PREDECESSOR_CHECKER_SHA256,
        repo_root
        / "scripts/check-engram-g14-native-sandbox-adapter-preregistration.sh": PREDECESSOR_SHELL_SHA256,
    }
    for path, expected_sha256 in expected.items():
        _require(
            sha256_bytes(read_stable_regular(path, max_bytes=2_000_000))
            == expected_sha256,
            "E_PREDECESSOR",
            path.name,
        )
    cargo_lock = read_stable_regular(
        repo_root / "Cargo.lock", max_bytes=5_000_000
    ).decode("utf-8")
    package_pattern = re.compile(
        r'\[\[package\]\]\nname = "nono"\nversion = "([^"]+)"\nsource = "[^"]+"\nchecksum = "([0-9a-f]{64})"\n'
    )
    match = package_pattern.search(cargo_lock)
    _require(match is not None, "E_DEPENDENCY", "nono Cargo.lock entry missing")
    _exact(match.group(1), NONO_VERSION, "Cargo.lock nono version")
    _exact(match.group(2), NONO_CHECKSUM, "Cargo.lock nono checksum")


def default_state_dir() -> Path:
    explicit = os.environ.get("AGENT_BRIDGE_STATE_DIR")
    if explicit:
        return Path(explicit)
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "agent-bridge"
    return Path.home() / ".local/state/agent-bridge"


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    _require(
        stat.S_ISDIR(info.st_mode) and not path.is_symlink(),
        "E_STATE",
        f"unsafe state directory: {path.name}",
    )
    os.chmod(path, 0o700)


def _durable_create_json(path: Path, value: dict[str, Any]) -> bytes:
    raw = canonical_bytes(value) + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        _fail("E_CREATE_NEW", f"durable record already exists: {path.name}")
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            _require(written > 0, "E_STATE", "short durable write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(path.parent)
    reopened = read_stable_regular(path, max_bytes=MAX_JSON_BYTES)
    _require(reopened == raw, "E_DURABILITY", f"durable reopen mismatch: {path.name}")
    strict_json_bytes(reopened)
    return raw


def _durable_unlink(path: Path) -> None:
    path.unlink()
    _fsync_directory(path.parent)


class DurableRunState:
    def __init__(self, state_dir: Path) -> None:
        self.root = state_dir.resolve() / "engram_g14_public_synthetic_native_kat"
        self.claims = self.root / "attempt_claims_v0"
        self.anchors = self.root / "prelaunch_anchors_v0"
        self.obligations = self.root / "rollback_obligations_v0"
        self.lessons = self.root / "rollback_lessons_v0"
        self.scratch = self.root / "scratch_v0"
        for path in (
            self.root,
            self.claims,
            self.anchors,
            self.obligations,
            self.lessons,
            self.scratch,
        ):
            _ensure_private_directory(path)

    def verify_lessons(self) -> str:
        previous_raw_sha256 = ZERO_SHA256
        for sequence, path in enumerate(sorted(self.lessons.glob("*.json")), start=1):
            raw = read_stable_regular(path)
            lesson = strict_json_bytes(raw)
            row = _exact_keys(
                lesson,
                {
                    "schema",
                    "lesson_id_sha256",
                    "parent_run_id_commitment_sha256",
                    "failure_phase",
                    "reason_code",
                    "cleanup_target_set_sha256",
                    "residue_count",
                    "lesson_sequence",
                    "previous_lesson_sha256",
                    "lesson_sha256",
                },
                f"rollback lesson {sequence}",
            )
            _exact(
                row["schema"],
                "agent_bridge.engram_g1_4_native_kat_rollback_failure_lesson.v0",
                f"rollback lesson {sequence}.schema",
            )
            _exact(row["failure_phase"], "cleanup", f"rollback lesson {sequence}.phase")
            _exact(
                row["reason_code"],
                "SYNTHETIC_ROOT_CLEANUP_FAILED",
                f"rollback lesson {sequence}.reason",
            )
            _exact(
                row["lesson_sequence"], sequence, f"rollback lesson {sequence}.sequence"
            )
            _exact(
                row["previous_lesson_sha256"],
                previous_raw_sha256,
                f"rollback lesson {sequence}.previous",
            )
            for key in (
                "lesson_id_sha256",
                "parent_run_id_commitment_sha256",
                "cleanup_target_set_sha256",
                "previous_lesson_sha256",
                "lesson_sha256",
            ):
                _require(
                    type(row[key]) is str
                    and re.fullmatch(r"[0-9a-f]{64}", row[key]) is not None,
                    "E_LESSON_INTEGRITY",
                    f"rollback lesson {sequence}.{key}",
                )
            _require(
                type(row["residue_count"]) is int and row["residue_count"] >= 0,
                "E_LESSON_INTEGRITY",
                f"rollback lesson {sequence}.residue_count",
            )
            expected_id = canonical_sha256(
                {
                    "run_id_commitment_sha256": row["parent_run_id_commitment_sha256"],
                    "failure_phase": row["failure_phase"],
                    "reason_code": row["reason_code"],
                    "lesson_sequence": sequence,
                }
            )
            _exact(
                row["lesson_id_sha256"],
                expected_id,
                f"rollback lesson {sequence}.lesson_id_sha256",
            )
            body = {key: value for key, value in row.items() if key != "lesson_sha256"}
            _exact(
                row["lesson_sha256"],
                canonical_sha256(body),
                f"rollback lesson {sequence}.lesson_sha256",
            )
            _exact(
                path.name,
                f"{sequence:08d}-{expected_id}.json",
                f"rollback lesson {sequence}.filename",
            )
            previous_raw_sha256 = sha256_bytes(raw)
        return previous_raw_sha256

    def assert_no_unresolved_rollback(self) -> None:
        self.verify_lessons()
        pending = sorted(self.obligations.glob("*.json"))
        _require(
            not pending,
            "E_ROLLBACK_INTERLOCK",
            "unresolved rollback obligation blocks claim",
        )

    def claim(self, run_commitment: str) -> Path:
        self.assert_no_unresolved_rollback()
        path = self.claims / f"{run_commitment}.json"
        _require(not path.exists(), "E_RUN_REPLAY", "one-shot run already consumed")
        _durable_create_json(
            path,
            {
                "schema": "agent_bridge.engram_g1_4_native_kat_one_shot_claim.v0",
                "run_id_commitment_sha256": run_commitment,
                "claim_sequence": 1,
                "claim_consumed": True,
            },
        )
        return path

    def create_obligation(
        self, run_commitment: str, cleanup_target_sha256: str
    ) -> Path:
        path = self.obligations / f"{run_commitment}.json"
        _durable_create_json(
            path,
            {
                "schema": "agent_bridge.engram_g1_4_native_kat_rollback_obligation.v0",
                "run_id_commitment_sha256": run_commitment,
                "cleanup_target_set_sha256": cleanup_target_sha256,
                "state": "ROLLBACK_REQUIRED_UNTIL_CLEANUP_VERIFIED",
            },
        )
        return path

    def write_anchor(self, run_commitment: str, anchor: dict[str, Any]) -> Path:
        path = self.anchors / f"{run_commitment}.json"
        _durable_create_json(path, anchor)
        return path

    def clear_obligation(self, path: Path) -> None:
        _durable_unlink(path)

    def write_cleanup_lesson(
        self,
        *,
        run_commitment: str,
        cleanup_target_sha256: str,
        residue_count: int,
    ) -> dict[str, Any]:
        existing = sorted(self.lessons.glob("*.json"))
        previous = self.verify_lessons()
        sequence = len(existing) + 1
        lesson_id = canonical_sha256(
            {
                "run_id_commitment_sha256": run_commitment,
                "failure_phase": "cleanup",
                "reason_code": "SYNTHETIC_ROOT_CLEANUP_FAILED",
                "lesson_sequence": sequence,
            }
        )
        body = {
            "schema": "agent_bridge.engram_g1_4_native_kat_rollback_failure_lesson.v0",
            "lesson_id_sha256": lesson_id,
            "parent_run_id_commitment_sha256": run_commitment,
            "failure_phase": "cleanup",
            "reason_code": "SYNTHETIC_ROOT_CLEANUP_FAILED",
            "cleanup_target_set_sha256": cleanup_target_sha256,
            "residue_count": residue_count,
            "lesson_sequence": sequence,
            "previous_lesson_sha256": previous,
        }
        lesson = {**body, "lesson_sha256": canonical_sha256(body)}
        path = self.lessons / f"{sequence:08d}-{lesson_id}.json"
        raw = _durable_create_json(path, lesson)
        reopened = strict_json_bytes(raw)
        _exact(reopened, lesson, "rollback lesson durable bytes")
        return lesson


class ReceiptChain:
    def __init__(
        self,
        *,
        contract_sha256: str,
        run_commitment: str,
        implementation_sha256_value: str,
    ) -> None:
        self.contract_sha256 = contract_sha256
        self.run_commitment = run_commitment
        self.implementation_sha256 = implementation_sha256_value
        self.events: list[dict[str, Any]] = []

    def append(
        self, schema: str, phase: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        sequence = len(self.events) + 1
        previous = self.events[-1]["event_sha256"] if self.events else ZERO_SHA256
        source_commitment = canonical_sha256(
            {
                "source": PHASE_SOURCES[phase],
                "implementation_sha256": self.implementation_sha256,
            }
        )
        embedded = copy.deepcopy(payload)
        body = {
            "schema": schema,
            "sequence": sequence,
            "previous_sha256": previous,
            "phase": phase,
            "run_id_commitment_sha256": self.run_commitment,
            "contract_sha256": self.contract_sha256,
            "evidence_source_identity_sha256": source_commitment,
            "payload": embedded,
            "payload_sha256": canonical_sha256(embedded),
            "synthetic_only": True,
            "production_admissible": False,
        }
        event = {**body, "event_sha256": canonical_sha256(body)}
        self.events.append(event)
        return copy.deepcopy(event)

    @staticmethod
    def verify(events: list[dict[str, Any]], contract: dict[str, Any]) -> str:
        phases = contract["phases_in_order"]
        _exact(len(events), len(phases), "receipt count")
        previous = ZERO_SHA256
        for index, (event, phase_contract) in enumerate(zip(events, phases)):
            row = _exact_keys(
                event,
                {
                    "schema",
                    "sequence",
                    "previous_sha256",
                    "phase",
                    "run_id_commitment_sha256",
                    "contract_sha256",
                    "evidence_source_identity_sha256",
                    "payload",
                    "payload_sha256",
                    "synthetic_only",
                    "production_admissible",
                    "event_sha256",
                },
                f"receipts[{index}]",
            )
            _exact(row["sequence"], index + 1, f"receipts[{index}].sequence")
            _exact(row["previous_sha256"], previous, f"receipts[{index}].previous")
            _exact(row["phase"], phase_contract["phase"], f"receipts[{index}].phase")
            _exact(row["schema"], phase_contract["schema"], f"receipts[{index}].schema")
            _exact(
                list(row["payload"]),
                phase_contract["payload_fields_in_order"],
                f"receipts[{index}].payload order",
            )
            _exact(
                row["payload_sha256"],
                canonical_sha256(row["payload"]),
                f"receipts[{index}].payload_sha256",
            )
            _exact(row["synthetic_only"], True, f"receipts[{index}].synthetic_only")
            _exact(
                row["production_admissible"],
                False,
                f"receipts[{index}].production_admissible",
            )
            body = {key: value for key, value in row.items() if key != "event_sha256"}
            _exact(
                row["event_sha256"],
                canonical_sha256(body),
                f"receipts[{index}].event_sha256",
            )
            previous = row["event_sha256"]
        return previous


def _fixed_environment(scratch_root: Path) -> dict[str, str]:
    return {
        "HOME": str(scratch_root),
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
        "TMPDIR": str(scratch_root),
    }


def run_bounded(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout_seconds: int,
    stdout_limit: int,
    stderr_limit: int,
) -> tuple[int, bytes, bytes]:
    _require(
        argv and all(type(part) is str and part for part in argv),
        "E_LAUNCH",
        "closed argv required",
    )
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        start_new_session=True,
    )
    assert process.stdout is not None and process.stderr is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, ("stdout", stdout_limit))
    selector.register(process.stderr, selectors.EVENT_READ, ("stderr", stderr_limit))
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout_seconds
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _fail("E_TIMEOUT", "fixed probe exceeded timeout")
            ready = selector.select(remaining)
            if not ready:
                _fail("E_TIMEOUT", "fixed probe exceeded timeout")
            for key, _ in ready:
                label, limit = key.data
                chunk = os.read(key.fileobj.fileno(), 4096)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[label].extend(chunk)
                _require(
                    len(buffers[label]) <= limit,
                    "E_OUTPUT_BOUND",
                    f"{label} exceeded bound",
                )
        returncode = process.wait(timeout=max(0.1, deadline - time.monotonic()))
        return returncode, bytes(buffers["stdout"]), bytes(buffers["stderr"])
    except BaseException:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()


def _parse_clock_mask(stdout: bytes, stderr: bytes, returncode: int) -> int:
    _require(returncode == 0, "E_PROBE", f"fixed probe return code {returncode}")
    _require(stderr == b"", "E_PROBE_OUTPUT", "fixed probe emitted stderr")
    match = OUTPUT_RE.fullmatch(stdout)
    _require(match is not None, "E_PROBE_OUTPUT", "fixed probe output schema mismatch")
    mask = int(match.group(1))
    _require(0 <= mask <= 15, "E_PROBE_OUTPUT", "clock mask out of range")
    return mask


def _parse_darwin_symbolic_control(
    stdout: bytes, stderr: bytes, returncode: int, stderr_limit: int
) -> bool:
    _require(
        returncode == 65,
        "E_PLATFORM_CONTROL_AMBIGUOUS",
        "symbolic clock profile returned an unregistered status",
    )
    _require(
        stdout == b"",
        "E_PLATFORM_CONTROL_AMBIGUOUS",
        "symbolic clock profile emitted stdout",
    )
    _require(
        len(stderr) <= stderr_limit,
        "E_PLATFORM_CONTROL_AMBIGUOUS",
        "symbolic clock profile stderr exceeded bound",
    )
    _require(
        DARWIN_SYMBOLIC_ERROR_RE.fullmatch(stderr) is not None,
        "E_PLATFORM_CONTROL_AMBIGUOUS",
        "symbolic clock profile failure reason was not the registered reason",
    )
    return False


def _build_probe(contract: dict[str, Any], synthetic_root: Path) -> tuple[Path, str]:
    binary = synthetic_root / "probe"
    compiler = contract["probe"]["compiler_argv"]
    argv = tuple(compiler + [str(PROBE_PATH), "-o", str(binary)])
    returncode, stdout, stderr = run_bounded(
        argv,
        cwd=synthetic_root,
        environment=_fixed_environment(synthetic_root),
        timeout_seconds=30,
        stdout_limit=1024,
        stderr_limit=16_384,
    )
    _require(
        returncode == 0, "E_BUILD", f"fixed probe compiler return code {returncode}"
    )
    _require(stdout == b"", "E_BUILD", "fixed probe compiler emitted stdout")
    _require(stderr == b"", "E_BUILD", "fixed probe compiler emitted stderr")
    info = binary.lstat()
    _require(
        stat.S_ISREG(info.st_mode) and os.access(binary, os.X_OK),
        "E_BUILD",
        "probe binary missing",
    )
    return binary, sha256_bytes(read_stable_regular(binary, max_bytes=2_000_000))


def _host_commitment(platform_name: str) -> str:
    return canonical_sha256(
        {
            "platform": platform_name,
            "machine": host_platform.machine(),
            "release": host_platform.release(),
            "python_abi": sys.implementation.cache_tag or "none",
        }
    )


def expected_support_matrix(
    contract: dict[str, Any], platform_name: str
) -> dict[str, Any]:
    _require(
        platform_name in ("darwin", "linux"), "E_PLATFORM", "Darwin or Linux required"
    )
    row = contract["platform_expectations"][platform_name]
    common = {
        "platform": platform_name,
        "control_mask_nonzero": row["control_mask_nonzero"],
        "direct_syscall_filter_effective": row["direct_syscall_filter_effective"],
        "all_required_controls_supported": row["all_required_controls_supported"],
        "failure_code": row["failure_code"],
    }
    if platform_name == "darwin":
        return {
            **common,
            "residual_libc_or_commpage_clock_path": row[
                "residual_libc_or_commpage_clock_path"
            ],
            "symbolic_system_clock_rule_compiles": row[
                "symbolic_system_clock_rule_compiles"
            ],
        }
    return {
        **common,
        "residual_libc_or_vdso_clock_path": row["residual_libc_or_vdso_clock_path"],
    }


def observe_support(
    binary: Path, synthetic_root: Path, contract: dict[str, Any], platform_name: str
) -> dict[str, Any]:
    probe = contract["probe"]
    environment = _fixed_environment(synthetic_root)
    common = dict(
        cwd=synthetic_root,
        environment=environment,
        timeout_seconds=probe["timeout_seconds"],
        stdout_limit=probe["max_stdout_bytes"],
        stderr_limit=probe["max_stderr_bytes"],
    )
    control = run_bounded((str(binary), "clock-control"), **common)
    control_mask = _parse_clock_mask(control[1], control[2], control[0])
    if platform_name == "darwin":
        _require(
            Path("/usr/bin/sandbox-exec").is_file(),
            "E_PLATFORM",
            "sandbox-exec missing",
        )
        filtered = run_bounded(
            (
                "/usr/bin/sandbox-exec",
                "-p",
                DARWIN_DIRECT_SYSCALL_PROFILE,
                str(binary),
                "clock-control",
            ),
            **common,
        )
        filtered_mask = _parse_clock_mask(filtered[1], filtered[2], filtered[0])
        symbolic = run_bounded(
            (
                "/usr/bin/sandbox-exec",
                "-p",
                DARWIN_SYMBOLIC_CLOCK_PROFILE,
                "/usr/bin/true",
            ),
            **common,
        )
        symbolic_rule_compiles = _parse_darwin_symbolic_control(
            symbolic[1], symbolic[2], symbolic[0], probe["max_stderr_bytes"]
        )
        return {
            "platform": "darwin",
            "control_mask_nonzero": control_mask != 0,
            "direct_syscall_filter_effective": (filtered_mask & MASK_DIRECT_SYSCALL)
            == 0,
            "all_required_controls_supported": False,
            "failure_code": "WALL_CLOCK_UNCONFINED",
            "residual_libc_or_commpage_clock_path": (filtered_mask & MASK_LIBC_PATHS)
            != 0,
            "symbolic_system_clock_rule_compiles": symbolic_rule_compiles,
        }
    if platform_name == "linux":
        filtered = run_bounded((str(binary), "clock-filtered"), **common)
        filtered_mask = _parse_clock_mask(filtered[1], filtered[2], filtered[0])
        return {
            "platform": "linux",
            "control_mask_nonzero": control_mask != 0,
            "direct_syscall_filter_effective": (filtered_mask & MASK_DIRECT_SYSCALL)
            == 0,
            "all_required_controls_supported": False,
            "failure_code": "WALL_CLOCK_UNCONFINED",
            "residual_libc_or_vdso_clock_path": (filtered_mask & MASK_LIBC_PATHS) != 0,
        }
    _fail("E_PLATFORM", "Darwin or Linux required")


def build_expected_receipts(
    *,
    contract: dict[str, Any],
    fixture: dict[str, Any],
    probe_build_sha256: str,
    run_commitment: str,
    platform_name: str,
    kernel_commitment: str,
    support_matrix: dict[str, Any],
    synthetic_root_commitment: str,
    cleanup_target_sha256: str,
) -> list[dict[str, Any]]:
    impl_sha256 = implementation_sha256()
    chain = ReceiptChain(
        contract_sha256=CONTRACT_SHA256,
        run_commitment=run_commitment,
        implementation_sha256_value=impl_sha256,
    )
    dependency_lock_sha256 = canonical_sha256(contract["dependency_lock"])
    skipped_policy = {
        "status": "NOT_ATTEMPTED_PLATFORM_UNSUPPORTED",
        "failure_code": "WALL_CLOCK_UNCONFINED",
    }
    skipped_sha256 = canonical_sha256(skipped_policy)
    subject_sha256 = canonical_sha256(
        {
            "probe_build_sha256": probe_build_sha256,
            "platform": platform_name,
            "argv_contract": contract["probe"]["accepted_probe_argv_in_order"],
        }
    )
    phase_contracts = {row["phase"]: row for row in contract["phases_in_order"]}

    def append(phase: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = phase_contracts[phase]
        _exact(list(payload), row["payload_fields_in_order"], f"{phase} payload order")
        return chain.append(row["schema"], phase, payload)

    append(
        "artifact_preflight",
        {
            "contract_sha256": CONTRACT_SHA256,
            "probe_source_sha256": PROBE_SOURCE_SHA256,
            "probe_build_sha256": probe_build_sha256,
            "dependency_lock_sha256": dependency_lock_sha256,
            "fixture_sha256": FIXTURE_SHA256,
        },
    )
    append(
        "one_shot_claim",
        {
            "run_id_commitment_sha256": run_commitment,
            "claim_sequence": 1,
            "claim_consumed": True,
        },
    )
    support = append(
        "platform_support",
        {
            "platform": platform_name,
            "kernel_and_abi_commitment_sha256": kernel_commitment,
            "primitive_support_matrix_sha256": canonical_sha256(support_matrix),
            "all_required_controls_supported": False,
        },
    )
    compile_receipt = append(
        "policy_compile",
        {
            "policy_input_sha256": skipped_sha256,
            "generated_policy_sha256": skipped_sha256,
            "dependency_and_rule_order_sha256": dependency_lock_sha256,
            "compile_succeeded": False,
        },
    )
    apply_receipt = append(
        "policy_apply",
        {
            "generated_policy_sha256": skipped_sha256,
            "subject_process_identity_commitment_sha256": subject_sha256,
            "apply_result_code": "NOT_ATTEMPTED_PLATFORM_UNSUPPORTED",
            "apply_succeeded": False,
        },
    )
    append(
        "active_attestation",
        {
            "support_receipt_sha256": support["event_sha256"],
            "apply_receipt_sha256": apply_receipt["event_sha256"],
            "subject_process_identity_commitment_sha256": subject_sha256,
            "active_reported": False,
        },
    )
    append(
        "negative_controls",
        {
            "control_fixture_sha256": FIXTURE_SHA256,
            "control_attempt_set_sha256": canonical_sha256(
                fixture["probe_cases_in_order"]
            ),
            "live_control_count": 3 if platform_name == "darwin" else 2,
            "all_controls_unambiguous": True,
        },
    )
    append(
        "allowed_canaries",
        {
            "subject_process_identity_commitment_sha256": subject_sha256,
            "allowed_canary_observations_sha256": skipped_sha256,
            "allowed_canary_count": 0,
            "all_allowed_canaries_matched": False,
        },
    )
    append(
        "denied_canaries",
        {
            "subject_process_identity_commitment_sha256": subject_sha256,
            "denied_canary_observations_sha256": skipped_sha256,
            "denied_canary_count": 0,
            "all_denied_canaries_matched": False,
        },
    )
    cleanup = append(
        "cleanup",
        {
            "synthetic_root_commitment_sha256": synthetic_root_commitment,
            "cleanup_target_set_sha256": cleanup_target_sha256,
            "residue_count": 0,
            "cleanup_verified": True,
        },
    )
    prefinal_head = cleanup["event_sha256"]
    append(
        "receipt_finalize",
        {
            "previous_event_sha256": prefinal_head,
            "expected_chain_head_sha256": prefinal_head,
            "authority_class": AUTHORITY_CLASS,
            "production_admissible": False,
            "g1_4_execution_open": False,
            "verdict": VERDICT,
        },
    )
    ReceiptChain.verify(chain.events, contract)
    _require(
        compile_receipt["payload"]["compile_succeeded"] is False,
        "E_INTERNAL",
        "compile must remain skipped",
    )
    return chain.events


def _safe_cleanup_target(path: Path, scratch_root: Path, run_commitment: str) -> None:
    resolved_parent = path.parent.resolve()
    _require(
        resolved_parent == scratch_root.resolve(),
        "E_CLEANUP_TARGET",
        "scratch parent mismatch",
    )
    _require(
        path.name.startswith(run_commitment[:16] + "-"),
        "E_CLEANUP_TARGET",
        "scratch name mismatch",
    )
    _require(
        path != scratch_root and path != scratch_root.parent,
        "E_CLEANUP_TARGET",
        "broad cleanup forbidden",
    )


def _residue_count(path: Path) -> int:
    if not path.exists():
        return 0
    return 1 + sum(
        len(directories) + len(files) for _, directories, files in os.walk(path)
    )


class NativeSandboxKat:
    def __init__(
        self,
        *,
        state_dir: Path,
        enabled: bool = False,
        force_cleanup_failure: bool = False,
        cleanup: Callable[[Path], None] = shutil.rmtree,
    ) -> None:
        self.enabled = enabled
        self.state = DurableRunState(state_dir)
        self.force_cleanup_failure = force_cleanup_failure
        self.cleanup = cleanup

    def _resolve_cleanup(
        self,
        *,
        synthetic_root: Path,
        obligation: Path | None,
        run_commitment: str,
        cleanup_target_sha256: str,
        force_failure: bool,
    ) -> bool:
        residue_before = _residue_count(synthetic_root)
        cleanup_failed = force_failure
        if not cleanup_failed:
            try:
                if synthetic_root.exists():
                    self.cleanup(synthetic_root)
                _require(
                    not synthetic_root.exists(), "E_CLEANUP", "synthetic root residue"
                )
            except BaseException:
                cleanup_failed = True
        if cleanup_failed:
            self.state.write_cleanup_lesson(
                run_commitment=run_commitment,
                cleanup_target_sha256=cleanup_target_sha256,
                residue_count=residue_before,
            )
            if synthetic_root.exists():
                shutil.rmtree(synthetic_root)
            _require(
                not synthetic_root.exists(),
                "E_CLEANUP",
                "synthetic root residue after lesson",
            )
            if obligation is not None and obligation.exists():
                self.state.clear_obligation(obligation)
            return False
        if obligation is not None:
            try:
                self.state.clear_obligation(obligation)
            except BaseException:
                self.state.write_cleanup_lesson(
                    run_commitment=run_commitment,
                    cleanup_target_sha256=cleanup_target_sha256,
                    residue_count=0,
                )
                if obligation.exists():
                    self.state.clear_obligation(obligation)
                return False
        return True

    def run(self, contract: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
        _require(
            self.enabled is True,
            "E_DEFAULT_OFF",
            "explicit public-synthetic enable required",
        )
        validate_contract(contract)
        validate_fixture(fixture)
        _exact(
            canonical_sha256(contract),
            CONTRACT_CANONICAL_SHA256,
            "fixed contract canonical digest",
        )
        _exact(
            canonical_sha256(fixture),
            FIXTURE_CANONICAL_SHA256,
            "fixed fixture canonical digest",
        )
        validate_predecessors(REPO_ROOT)
        _require(
            sha256_bytes(read_stable_regular(PROBE_PATH)) == PROBE_SOURCE_SHA256,
            "E_PROBE_DIGEST",
            "fixed probe drifted",
        )
        platform_name = sys.platform
        _require(
            platform_name in ("darwin", "linux"),
            "E_PLATFORM",
            "Darwin or Linux required",
        )
        run_commitment = canonical_sha256(
            {
                "contract_sha256": CONTRACT_SHA256,
                "fixture_sha256": FIXTURE_SHA256,
                "run_id": fixture["run_id"],
            }
        )
        self.state.claim(run_commitment)
        synthetic_root = Path(
            tempfile.mkdtemp(prefix=run_commitment[:16] + "-", dir=self.state.scratch)
        )
        _safe_cleanup_target(synthetic_root, self.state.scratch, run_commitment)
        synthetic_root_commitment = sha256_bytes(str(synthetic_root).encode("utf-8"))
        cleanup_target_sha256 = canonical_sha256([synthetic_root_commitment])
        obligation: Path | None = None
        cleanup_attempted = False
        cleanup_completed = False
        try:
            obligation = self.state.create_obligation(
                run_commitment, cleanup_target_sha256
            )
            binary, probe_build_sha256 = _build_probe(contract, synthetic_root)
            support_expected = expected_support_matrix(contract, platform_name)
            kernel_commitment = _host_commitment(platform_name)
            receipts = build_expected_receipts(
                contract=contract,
                fixture=fixture,
                probe_build_sha256=probe_build_sha256,
                run_commitment=run_commitment,
                platform_name=platform_name,
                kernel_commitment=kernel_commitment,
                support_matrix=support_expected,
                synthetic_root_commitment=synthetic_root_commitment,
                cleanup_target_sha256=cleanup_target_sha256,
            )
            expected_final_event_sha256 = receipts[-1]["event_sha256"]
            expected_prefinal_head_sha256 = receipts[-2]["event_sha256"]
            anchor = {
                "schema": "agent_bridge.engram_g1_4_native_kat_prelaunch_anchor.v0",
                "run_id_commitment_sha256": run_commitment,
                "contract_sha256": CONTRACT_SHA256,
                "fixture_sha256": FIXTURE_SHA256,
                "probe_source_sha256": PROBE_SOURCE_SHA256,
                "probe_build_sha256": probe_build_sha256,
                "expected_prefinal_head_sha256": expected_prefinal_head_sha256,
                "expected_final_event_sha256": expected_final_event_sha256,
                "authenticated": False,
                "production_admissible": False,
            }
            anchor_raw = _durable_create_json(
                self.state.anchors / f"{run_commitment}.json", anchor
            )
            anchor_sha256 = sha256_bytes(anchor_raw)

            support_observed = observe_support(
                binary, synthetic_root, contract, platform_name
            )
            _exact(support_observed, support_expected, "observed support matrix")
            _exact(
                support_observed["all_required_controls_supported"],
                False,
                "platform support",
            )

            cleanup_attempted = True
            cleanup_clean = self._resolve_cleanup(
                synthetic_root=synthetic_root,
                obligation=obligation,
                run_commitment=run_commitment,
                cleanup_target_sha256=cleanup_target_sha256,
                force_failure=self.force_cleanup_failure,
            )
            cleanup_completed = True
            if not cleanup_clean:
                code = (
                    "E_INJECTED_CLEANUP"
                    if self.force_cleanup_failure
                    else "E_CLEANUP_DURABILITY"
                )
                _fail(code, "cleanup required a durable rollback lesson")

            head = ReceiptChain.verify(receipts, contract)
            _exact(head, expected_final_event_sha256, "final receipt head")
            return {
                "schema": "agent_bridge.engram_g1_4_native_sandbox_adapter_kat_result.v0",
                "contract_id": contract["contract_id"],
                "contract_sha256": CONTRACT_SHA256,
                "fixture_id": fixture["fixture_id"],
                "fixture_sha256": FIXTURE_SHA256,
                "implementation_sha256": implementation_sha256(),
                "mode": MODE,
                "platform": platform_name,
                "state": "REJECTED_FAIL_CLOSED",
                "failure_code": "WALL_CLOCK_UNCONFINED",
                "verdict": VERDICT,
                "receipt_count": len(receipts),
                "receipt_chain_head_sha256": head,
                "prelaunch_anchor_sha256": anchor_sha256,
                "prelaunch_anchor_authenticated": False,
                "platform_kat_executed": True,
                "full_fourteen_canary_run_executed": False,
                "native_adapter_implemented": False,
                "native_enforcement_verified": False,
                "candidate_source_accessed": False,
                "private_material_accessed": False,
                "production_admissible": False,
                "g1_4_execution_open": False,
                "runtime_promotion_authority": False,
                "only_permitted_next_action": contract["expected_result"][
                    "only_permitted_next_action"
                ],
                "receipts": receipts,
            }
        except BaseException:
            if not cleanup_completed and not cleanup_attempted:
                cleanup_attempted = True
                self._resolve_cleanup(
                    synthetic_root=synthetic_root,
                    obligation=obligation,
                    run_commitment=run_commitment,
                    cleanup_target_sha256=cleanup_target_sha256,
                    force_failure=False,
                )
            raise


def validate_artifacts() -> dict[str, Any]:
    contract = load_pinned_json(CONTRACT_PATH, CONTRACT_SHA256)
    fixture = load_pinned_json(FIXTURE_PATH, FIXTURE_SHA256)
    validate_contract(contract)
    validate_fixture(fixture)
    validate_predecessors(REPO_ROOT)
    _require(
        sha256_bytes(read_stable_regular(PROBE_PATH)) == PROBE_SOURCE_SHA256,
        "E_PROBE_DIGEST",
        "fixed probe drifted",
    )
    return {
        "schema": "agent_bridge.engram_g1_4_native_sandbox_adapter_kat_artifact_validation.v0",
        "contract_sha256": CONTRACT_SHA256,
        "fixture_sha256": FIXTURE_SHA256,
        "probe_source_sha256": PROBE_SOURCE_SHA256,
        "mode": MODE,
        "default_off": True,
        "native_adapter_implemented": False,
        "g1_4_execution_open": False,
        "verdict": "VALIDATED_ARTIFACTS_NO_EXECUTION_NO_AUTHORITY",
    }


def _write_json(value: dict[str, Any]) -> None:
    sys.stdout.buffer.write(canonical_bytes(value) + b"\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-artifacts")
    run_parser = subparsers.add_parser("run-kat")
    run_parser.add_argument("--enable-public-synthetic", action="store_true")
    run_parser.add_argument("--state-dir", type=Path, default=default_state_dir())
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-artifacts":
            _write_json(validate_artifacts())
            return 0
        contract = load_pinned_json(CONTRACT_PATH, CONTRACT_SHA256)
        fixture = load_pinned_json(FIXTURE_PATH, FIXTURE_SHA256)
        kat = NativeSandboxKat(
            state_dir=args.state_dir,
            enabled=args.enable_public_synthetic,
        )
        _write_json(kat.run(contract, fixture))
        return 0
    except KatError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
