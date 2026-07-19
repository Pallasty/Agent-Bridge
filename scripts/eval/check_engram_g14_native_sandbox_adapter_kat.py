#!/usr/bin/env python3
"""Independent checks for the Engram G1.4 native sandbox viability KAT."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

sys.dont_write_bytecode = True


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
IMPLEMENTATION_PATH = SCRIPT_DIR / "engram_g14_native_sandbox_adapter_kat.py"
CONTRACT_PATH = (
    SCRIPT_DIR / "fixtures/engram_g14_native_sandbox_adapter_kat_contract_v0.json"
)
FIXTURE_PATH = (
    SCRIPT_DIR / "fixtures/engram_g14_native_sandbox_adapter_kat_fixture_v0.json"
)
PROBE_PATH = SCRIPT_DIR / "fixtures/engram_g14_native_sandbox_adapter_probe_v0.c"

IMPLEMENTATION_SHA256 = (
    "1f79379ef480c3f0c21b901b292990460cd330ee2a627082ed2a94b8094e7c1f"
)
CONTRACT_SHA256 = "7018486db2dc3f3e751d66547828756e6d61aea91df7b3f12b7bccc9cd78615d"
FIXTURE_SHA256 = "e4e23d1a6aea78ee60047c96f76249137b2c139ced18d6731754dca229b6b239"
PROBE_SHA256 = "0824beab20f922548f0033910e1ad3eb55695c0bb802488d0e9e531279199d12"
MODE = "PUBLIC_SYNTHETIC_NATIVE_SANDBOX_ADAPTER_KAT"
VERDICT = "REJECTED_FAIL_CLOSED_WALL_CLOCK_UNCONFINED_NO_AUTHORITY"
ZERO_SHA256 = "0" * 64

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
EXPECTED_PHASE_SOURCES = {row[0]: row[2] for row in EXPECTED_PHASE_ROWS}
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
EXPECTED_CONTRACT_SECTIONS = {
    "predecessor": {
        "contract_id": "engram_g14_native_sandbox_adapter_preregistration_20260718",
        "contract_sha256": "075dd9be4f6097e539db62025e6420b9add0efc030c528c065b612a77f5d78e0",
        "integration_commit": "908412b8209056a90b3be5c2f93896c763d31311",
    },
    "scope": {
        "mode": MODE,
        "enabled_by_default": False,
        "public_synthetic_only": True,
        "fixed_probe_only": True,
        "purpose": "native_wall_clock_confinement_viability",
        "successful_native_adapter_claim_representable": False,
        "unsupported_platform_fails_closed": True,
        "unsandboxed_fallback_allowed": False,
    },
    "dependency_lock": {
        "crate": "nono",
        "version": "0.53.0",
        "crates_io_checksum_sha256": "ae7eb523cc2036e9ad6527411c3da5dc2172dc454cc3447a03b910420a39bfee",
        "agent_cargo_toml_sha256": "64bcf1afb4d3982ac6205b1c74bea322dbe58b61079e44dcc0bce1fd7c976c02",
        "existing_workspace_sandbox_is_admissible_evidence": False,
    },
    "probe": {
        "source_path": "scripts/eval/fixtures/engram_g14_native_sandbox_adapter_probe_v0.c",
        "source_sha256": PROBE_SHA256,
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
    },
    "platform_expectations": {
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
    },
    "durability": {
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
    },
    "expected_result": {
        "verdict": VERDICT,
        "receipt_count": 11,
        "native_adapter_implemented": False,
        "native_enforcement_verified": False,
        "production_admissible": False,
        "g1_4_execution_open": False,
        "only_permitted_next_action": "separate_design_and_security_review_for_stronger_clock_isolation_primitive",
    },
    "nonclaims": {
        "candidate_source_accessed": False,
        "private_material_accessed": False,
        "full_fourteen_canary_run_executed": False,
        "nono_policy_applied": False,
        "workspace_sandbox_modified": False,
        "runtime_or_mcp_surface_added": False,
        "deployment_performed": False,
    },
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_bytes(value))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


assert sha256(IMPLEMENTATION_PATH.read_bytes()) == IMPLEMENTATION_SHA256
assert sha256(CONTRACT_PATH.read_bytes()) == CONTRACT_SHA256
assert sha256(FIXTURE_PATH.read_bytes()) == FIXTURE_SHA256
assert sha256(PROBE_PATH.read_bytes()) == PROBE_SHA256

spec = importlib.util.spec_from_file_location(
    "engram_g14_native_kat", IMPLEMENTATION_PATH
)
assert spec is not None and spec.loader is not None
KAT = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = KAT
spec.loader.exec_module(KAT)

CONTRACT = load_json(CONTRACT_PATH)
FIXTURE = load_json(FIXTURE_PATH)


def expect_error(code: str, action: Callable[[], Any]) -> None:
    try:
        action()
    except KAT.KatError as exc:
        assert exc.code == code, (code, exc.code, str(exc))
    else:
        raise AssertionError(f"expected {code}")


def expect_any_kat_error(action: Callable[[], Any]) -> None:
    try:
        action()
    except KAT.KatError:
        return
    raise AssertionError("expected fail-closed KatError")


def assert_independent_contract(contract: dict[str, Any]) -> None:
    assert set(contract) == {
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
    assert (
        contract["schema"]
        == "agent_bridge.engram_g1_4_native_sandbox_adapter_kat_contract.v0"
    )
    assert contract["contract_id"] == "engram_g14_native_sandbox_adapter_kat_20260718"
    assert contract["date"] == "2026-07-18"
    for key, expected in EXPECTED_CONTRACT_SECTIONS.items():
        assert contract[key] == expected, key
    observed_phases = []
    for row in contract["phases_in_order"]:
        assert set(row) == {
            "phase",
            "schema",
            "evidence_source",
            "payload_fields_in_order",
        }
        observed_phases.append(
            (
                row["phase"],
                row["schema"],
                row["evidence_source"],
                tuple(row["payload_fields_in_order"]),
            )
        )
    assert tuple(observed_phases) == EXPECTED_PHASE_ROWS
    observed_canaries = []
    for row in contract["canaries_in_order"]:
        assert set(row) == {"name", "expected", "owner"}
        observed_canaries.append((row["name"], row["expected"], row["owner"]))
    assert tuple(observed_canaries) == EXPECTED_CANARY_ROWS


def independent_verify_receipts(events: list[dict[str, Any]]) -> str:
    assert len(events) == 11
    previous = ZERO_SHA256
    run_commitment: str | None = None
    for index, (event, phase_contract) in enumerate(zip(events, EXPECTED_PHASE_ROWS)):
        phase_name, schema, source, payload_fields = phase_contract
        assert set(event) == {
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
        }
        assert event["sequence"] == index + 1
        assert event["previous_sha256"] == previous
        assert event["phase"] == phase_name
        assert event["schema"] == schema
        assert tuple(event["payload"]) == payload_fields
        assert event["payload_sha256"] == canonical_sha256(event["payload"])
        assert event["contract_sha256"] == CONTRACT_SHA256
        if run_commitment is None:
            run_commitment = event["run_id_commitment_sha256"]
        assert event["run_id_commitment_sha256"] == run_commitment
        expected_source = canonical_sha256(
            {
                "source": source,
                "implementation_sha256": IMPLEMENTATION_SHA256,
            }
        )
        assert event["evidence_source_identity_sha256"] == expected_source
        assert event["synthetic_only"] is True
        assert event["production_admissible"] is False
        body = {key: value for key, value in event.items() if key != "event_sha256"}
        assert event["event_sha256"] == canonical_sha256(body)
        previous = event["event_sha256"]
    return previous


def assert_contract_and_fixture_closed() -> None:
    KAT.validate_contract(copy.deepcopy(CONTRACT))
    KAT.validate_fixture(copy.deepcopy(FIXTURE))
    KAT.validate_predecessors(REPO_ROOT)
    assert_independent_contract(CONTRACT)

    def reject(mutated: dict[str, Any]) -> None:
        expect_error("E_SCHEMA", lambda: KAT.validate_contract(mutated))
        try:
            assert_independent_contract(mutated)
        except AssertionError:
            return
        raise AssertionError("independent checker accepted contract mutation")

    mutated = copy.deepcopy(CONTRACT)
    mutated["canaries_in_order"][0]["name"] = "candidate_code_read_widened"
    reject(mutated)
    mutated = copy.deepcopy(CONTRACT)
    mutated["canaries_in_order"][0]["owner"] = "supervisor_mediation"
    reject(mutated)
    mutated = copy.deepcopy(CONTRACT)
    mutated["canaries_in_order"][0], mutated["canaries_in_order"][1] = (
        mutated["canaries_in_order"][1],
        mutated["canaries_in_order"][0],
    )
    reject(mutated)
    mutated = copy.deepcopy(CONTRACT)
    mutated["phases_in_order"][0]["schema"] = "agent_bridge.forged.v0"
    reject(mutated)
    mutated = copy.deepcopy(CONTRACT)
    mutated["phases_in_order"][0]["payload_fields_in_order"][0] = "forged_sha256"
    reject(mutated)
    mutated = copy.deepcopy(CONTRACT)
    mutated["phases_in_order"][0]["evidence_source"] = "candidate_reported"
    reject(mutated)
    mutated = copy.deepcopy(CONTRACT)
    mutated["expected_result"]["only_permitted_next_action"] = "OPEN_G1_4"
    reject(mutated)
    mutated = copy.deepcopy(CONTRACT)
    mutated["expected_result"]["g1_4_execution_open"] = True
    reject(mutated)
    mutated = copy.deepcopy(CONTRACT)
    mutated["scope"]["successful_native_adapter_claim_representable"] = True
    reject(mutated)
    mutated = copy.deepcopy(CONTRACT)
    mutated["platform_expectations"]["darwin"]["all_required_controls_supported"] = True
    reject(mutated)
    mutated = copy.deepcopy(CONTRACT)
    mutated["nonclaims"]["candidate_source_accessed"] = True
    reject(mutated)
    for durability_key in EXPECTED_CONTRACT_SECTIONS["durability"]:
        mutated = copy.deepcopy(CONTRACT)
        value = mutated["durability"][durability_key]
        mutated["durability"][durability_key] = (
            not value if type(value) is bool else "forged"
        )
        reject(mutated)

    mutated_fixture = copy.deepcopy(FIXTURE)
    mutated_fixture["public_synthetic_fixture"] = False
    expect_error("E_SCHEMA", lambda: KAT.validate_fixture(mutated_fixture))
    mutated_fixture = copy.deepcopy(FIXTURE)
    mutated_fixture["mode"] = "CANDIDATE"
    expect_error("E_SCHEMA", lambda: KAT.validate_fixture(mutated_fixture))
    mutated_fixture = copy.deepcopy(FIXTURE)
    mutated_fixture["run_id"] = "Changed-Public-Synthetic-Run-Identifier"
    expect_error("E_SCHEMA", lambda: KAT.validate_fixture(mutated_fixture))


def assert_default_off_and_cli_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="ab-g14-default-off-") as state_dir:
        kat = KAT.NativeSandboxKat(state_dir=Path(state_dir), enabled=False)
        expect_error(
            "E_DEFAULT_OFF",
            lambda: kat.run(copy.deepcopy(CONTRACT), copy.deepcopy(FIXTURE)),
        )
        claims = list((kat.state.claims).glob("*.json"))
        assert claims == []

        completed = subprocess.run(
            [
                sys.executable,
                str(IMPLEMENTATION_PATH),
                "run-kat",
                "--state-dir",
                state_dir,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 1
        assert "E_DEFAULT_OFF" in completed.stderr
        assert completed.stdout == ""

        unknown = subprocess.run(
            [
                sys.executable,
                str(IMPLEMENTATION_PATH),
                "run-kat",
                "--enable-public-synthetic",
                "--state-dir",
                state_dir,
                "--probe",
                "/tmp/not-admissible",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert unknown.returncode == 2
        assert "unrecognized arguments" in unknown.stderr


def assert_real_platform_negative_kat() -> None:
    with tempfile.TemporaryDirectory(prefix="ab-g14-native-kat-") as state_dir:
        kat = KAT.NativeSandboxKat(state_dir=Path(state_dir), enabled=True)
        result = kat.run(copy.deepcopy(CONTRACT), copy.deepcopy(FIXTURE))
        assert set(result) == {
            "schema",
            "contract_id",
            "contract_sha256",
            "fixture_id",
            "fixture_sha256",
            "implementation_sha256",
            "mode",
            "platform",
            "state",
            "failure_code",
            "verdict",
            "receipt_count",
            "receipt_chain_head_sha256",
            "prelaunch_anchor_sha256",
            "prelaunch_anchor_authenticated",
            "platform_kat_executed",
            "full_fourteen_canary_run_executed",
            "native_adapter_implemented",
            "native_enforcement_verified",
            "candidate_source_accessed",
            "private_material_accessed",
            "production_admissible",
            "g1_4_execution_open",
            "runtime_promotion_authority",
            "only_permitted_next_action",
            "receipts",
        }
        assert (
            result["schema"]
            == "agent_bridge.engram_g1_4_native_sandbox_adapter_kat_result.v0"
        )
        assert result["implementation_sha256"] == IMPLEMENTATION_SHA256
        assert result["mode"] == MODE
        assert result["platform"] in ("darwin", "linux")
        assert result["state"] == "REJECTED_FAIL_CLOSED"
        assert result["failure_code"] == "WALL_CLOCK_UNCONFINED"
        assert result["verdict"] == VERDICT
        assert result["receipt_count"] == 11
        assert result["platform_kat_executed"] is True
        assert result["prelaunch_anchor_authenticated"] is False
        for false_key in (
            "full_fourteen_canary_run_executed",
            "native_adapter_implemented",
            "native_enforcement_verified",
            "candidate_source_accessed",
            "private_material_accessed",
            "production_admissible",
            "g1_4_execution_open",
            "runtime_promotion_authority",
        ):
            assert result[false_key] is False

        receipts = result["receipts"]
        head = independent_verify_receipts(receipts)
        assert head == result["receipt_chain_head_sha256"]
        support = receipts[2]["payload"]
        expected_matrix = KAT.expected_support_matrix(CONTRACT, result["platform"])
        assert support["primitive_support_matrix_sha256"] == canonical_sha256(
            expected_matrix
        )
        assert support["all_required_controls_supported"] is False
        assert receipts[3]["payload"]["compile_succeeded"] is False
        assert receipts[4]["payload"]["apply_succeeded"] is False
        assert receipts[5]["payload"]["active_reported"] is False
        assert receipts[7]["payload"]["allowed_canary_count"] == 0
        assert receipts[8]["payload"]["denied_canary_count"] == 0
        assert receipts[9]["payload"]["cleanup_verified"] is True
        assert (
            receipts[10]["payload"]["previous_event_sha256"]
            == receipts[9]["event_sha256"]
        )
        assert (
            receipts[10]["payload"]["expected_chain_head_sha256"]
            == receipts[9]["event_sha256"]
        )
        assert receipts[10]["payload"]["production_admissible"] is False
        assert receipts[10]["payload"]["g1_4_execution_open"] is False

        run_commitment = receipts[0]["run_id_commitment_sha256"]
        claim_path = kat.state.claims / f"{run_commitment}.json"
        anchor_path = kat.state.anchors / f"{run_commitment}.json"
        assert claim_path.is_file() and anchor_path.is_file()
        claim = load_json(claim_path)
        anchor_raw = anchor_path.read_bytes()
        anchor = json.loads(anchor_raw)
        assert claim["claim_consumed"] is True
        assert anchor["expected_prefinal_head_sha256"] == receipts[9]["event_sha256"]
        assert anchor["expected_final_event_sha256"] == receipts[10]["event_sha256"]
        assert anchor["authenticated"] is False
        assert anchor["production_admissible"] is False
        assert sha256(anchor_raw) == result["prelaunch_anchor_sha256"]
        assert list(kat.state.obligations.glob("*.json")) == []
        assert list(kat.state.lessons.glob("*.json")) == []
        assert list(kat.state.scratch.iterdir()) == []
        assert stat.S_IMODE(claim_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(anchor_path.stat().st_mode) == 0o600

        serialized = canonical_bytes(result)
        assert state_dir.encode("utf-8") not in serialized
        assert FIXTURE["run_id"].encode("ascii") not in serialized
        assert b"clock_mask=" not in serialized
        assert b"Sandbox: exec*" not in serialized

        replay = KAT.NativeSandboxKat(state_dir=Path(state_dir), enabled=True)
        expect_error(
            "E_RUN_REPLAY",
            lambda: replay.run(copy.deepcopy(CONTRACT), copy.deepcopy(FIXTURE)),
        )

        reordered = copy.deepcopy(receipts)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        try:
            independent_verify_receipts(reordered)
        except AssertionError:
            pass
        else:
            raise AssertionError("reordered receipts accepted")
        tampered = copy.deepcopy(receipts)
        tampered[2]["payload"]["all_required_controls_supported"] = True
        try:
            independent_verify_receipts(tampered)
        except AssertionError:
            pass
        else:
            raise AssertionError("tampered receipt accepted")

        forged = copy.deepcopy(receipts)
        forged[2]["payload"]["all_required_controls_supported"] = True
        previous = ZERO_SHA256
        for event in forged:
            event["previous_sha256"] = previous
            event["payload_sha256"] = canonical_sha256(event["payload"])
            body = {key: value for key, value in event.items() if key != "event_sha256"}
            event["event_sha256"] = canonical_sha256(body)
            previous = event["event_sha256"]
        assert independent_verify_receipts(forged) == previous
        assert previous != anchor["expected_final_event_sha256"]


def assert_rollback_lesson_interlock() -> None:
    with tempfile.TemporaryDirectory(prefix="ab-g14-rollback-lesson-") as state_dir:
        kat = KAT.NativeSandboxKat(
            state_dir=Path(state_dir), enabled=True, force_cleanup_failure=True
        )
        expect_error(
            "E_INJECTED_CLEANUP",
            lambda: kat.run(copy.deepcopy(CONTRACT), copy.deepcopy(FIXTURE)),
        )
        lessons = list(kat.state.lessons.glob("*.json"))
        assert len(lessons) == 1
        lesson = load_json(lessons[0])
        assert set(lesson) == {
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
        }
        assert (
            lesson["schema"]
            == "agent_bridge.engram_g1_4_native_kat_rollback_failure_lesson.v0"
        )
        assert lesson["failure_phase"] == "cleanup"
        assert lesson["reason_code"] == "SYNTHETIC_ROOT_CLEANUP_FAILED"
        assert lesson["residue_count"] > 0
        assert lesson["lesson_sequence"] == 1
        assert lesson["previous_lesson_sha256"] == ZERO_SHA256
        body = {key: value for key, value in lesson.items() if key != "lesson_sha256"}
        assert lesson["lesson_sha256"] == canonical_sha256(body)
        assert kat.state.verify_lessons() == sha256(lessons[0].read_bytes())
        assert list(kat.state.obligations.glob("*.json")) == []
        assert list(kat.state.scratch.iterdir()) == []
        distinct_run_commitment = "f" * 64
        distinct_claim = kat.state.claim(distinct_run_commitment)
        assert distinct_claim.is_file()

        replay = KAT.NativeSandboxKat(state_dir=Path(state_dir), enabled=True)
        expect_error(
            "E_RUN_REPLAY",
            lambda: replay.run(copy.deepcopy(CONTRACT), copy.deepcopy(FIXTURE)),
        )
        lesson["residue_count"] += 1
        lessons[0].write_bytes(canonical_bytes(lesson) + b"\n")
        tampered = KAT.NativeSandboxKat(state_dir=Path(state_dir), enabled=True)
        expect_any_kat_error(lambda: tampered.state.claim("e" * 64))

    with tempfile.TemporaryDirectory(prefix="ab-g14-rollback-block-") as state_dir:
        kat = KAT.NativeSandboxKat(
            state_dir=Path(state_dir), enabled=True, force_cleanup_failure=True
        )

        def fail_lesson(**_: Any) -> dict[str, Any]:
            raise KAT.KatError("E_LESSON_DURABILITY", "injected durable lesson fault")

        kat.state.write_cleanup_lesson = fail_lesson
        expect_error(
            "E_LESSON_DURABILITY",
            lambda: kat.run(copy.deepcopy(CONTRACT), copy.deepcopy(FIXTURE)),
        )
        assert len(list(kat.state.obligations.glob("*.json"))) == 1
        assert list(kat.state.lessons.glob("*.json")) == []
        blocked = KAT.NativeSandboxKat(state_dir=Path(state_dir), enabled=True)
        expect_error(
            "E_ROLLBACK_INTERLOCK",
            lambda: blocked.run(copy.deepcopy(CONTRACT), copy.deepcopy(FIXTURE)),
        )


def assert_probe_and_supervisor_surface_closed() -> None:
    probe_text = PROBE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "system(",
        "popen(",
        "execve(",
        "posix_spawn(",
        "dlopen(",
        "socket(",
        "connect(",
        "getenv(",
    ):
        assert forbidden not in probe_text
    assert 'strcmp(argv[1], "clock-control")' in probe_text
    assert 'strcmp(argv[1], "clock-filtered")' in probe_text
    assert 'printf("clock_mask=%u\\n", mask)' in probe_text

    implementation_text = IMPLEMENTATION_PATH.read_text(encoding="utf-8")
    assert "shell=True" not in implementation_text
    assert implementation_text.index(
        "expected_final_event_sha256 = receipts[-1]"
    ) < implementation_text.index("support_observed = observe_support")
    assert implementation_text.index(
        "_durable_create_json(\n                self.state.anchors"
    ) < implementation_text.index("support_observed = observe_support")
    assert "--probe" not in implementation_text
    assert "--command" not in implementation_text
    assert "--environment" not in implementation_text

    expect_error(
        "E_PROBE_OUTPUT", lambda: KAT._parse_clock_mask(b"free form\n", b"", 0)
    )
    expect_error(
        "E_PROBE_OUTPUT", lambda: KAT._parse_clock_mask(b"clock_mask=16\n", b"", 0)
    )
    expect_error("E_PROBE", lambda: KAT._parse_clock_mask(b"clock_mask=0\n", b"", 77))

    registered_symbolic_error = (
        b"sandbox-exec: unbound variable: system-clock at <input string>, line 3, "
        b"column 7\n\nBacktrace: \n<input string>:3:7:\n\tsystem-clock\n\n"
    )
    assert (
        KAT._parse_darwin_symbolic_control(b"", registered_symbolic_error, 65, 4096)
        is False
    )
    expect_error(
        "E_PLATFORM_CONTROL_AMBIGUOUS",
        lambda: KAT._parse_darwin_symbolic_control(
            b"", registered_symbolic_error, 1, 4096
        ),
    )
    expect_error(
        "E_PLATFORM_CONTROL_AMBIGUOUS",
        lambda: KAT._parse_darwin_symbolic_control(
            b"", b"sandbox-exec: permission denied\n", 65, 4096
        ),
    )
    expect_error(
        "E_PLATFORM_CONTROL_AMBIGUOUS",
        lambda: KAT._parse_darwin_symbolic_control(
            b"", registered_symbolic_error + b"extra free text\n", 65, 4096
        ),
    )
    expect_error(
        "E_PLATFORM_CONTROL_AMBIGUOUS",
        lambda: KAT._parse_darwin_symbolic_control(b"", b"x" * 4097, 65, 4096),
    )
    expect_error(
        "E_PLATFORM_CONTROL_AMBIGUOUS",
        lambda: KAT._parse_darwin_symbolic_control(
            b"unexpected stdout\n", registered_symbolic_error, 65, 4096
        ),
    )


def main() -> None:
    assert_contract_and_fixture_closed()
    assert_default_off_and_cli_closed()
    assert_real_platform_negative_kat()
    assert_rollback_lesson_interlock()
    assert_probe_and_supervisor_surface_closed()
    print(
        "engram G1.4 native sandbox adapter KAT: validated negative; unsupported; no authority"
    )


if __name__ == "__main__":
    main()
