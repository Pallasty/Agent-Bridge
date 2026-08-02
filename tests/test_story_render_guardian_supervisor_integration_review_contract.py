from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs/design/voice-scene"
RESULT_PATH = (
    VOICE_SCENE / "s634_story_render_guardian_supervisor_integration_review.json"
)
SCHEMA_PATH = (
    VOICE_SCENE / "story_render_guardian_supervisor_integration_review.schema.json"
)
ADR_PATH = VOICE_SCENE / "S634_STORY_RENDER_GUARDIAN_SUPERVISOR_INTEGRATION_REVIEW.md"


def load_result() -> dict[str, object]:
    value = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt_projection(result: dict[str, object]) -> dict[str, object]:
    names = (
        "decision",
        "impact",
        "current_findings",
        "selected_integration",
        "state_machine",
        "replay_continuity",
        "error_mapping",
        "required_changes",
        "rollout_and_rollback",
        "authority",
        "runtime_effects",
        "claims",
        "nonclaims",
        "next_gate",
    )
    return {name: result[name] for name in names}


def test_s634_receipt_is_schema_valid_and_hash_bound() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    result = load_result()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(result)) == []
    assert result["receipt_sha256"] == digest(receipt_projection(result))


def test_s634_evidence_hashes_match_reviewed_current_sources() -> None:
    result = load_result()
    evidence = result["evidence"]
    assert isinstance(evidence, dict)

    source_snapshot = evidence["source_snapshot"]
    assert isinstance(source_snapshot, list)
    assert len(source_snapshot) >= 8
    for entry in source_snapshot:
        assert isinstance(entry, dict)
        path = ROOT / str(entry["path"])
        assert path.is_file()
        assert entry["sha256"] == file_digest(path)

    s633 = evidence["s633_prototype"]
    assert isinstance(s633, dict)
    s633_path = ROOT / str(s633["path"])
    assert s633["sha256"] == file_digest(s633_path)
    assert s633["receipt_sha256"] == (
        "fc1488bf4194d32f7c45aef2b50a02c0318f631721fbfe542490e28aa9154dc1"
    )


def test_s634_identifies_incompatible_current_boundaries() -> None:
    result = load_result()
    findings = result["current_findings"]

    assert findings == {
        "host_lock_explicit_unlock_on_drop": True,
        "supervisor_spawns_worker_directly": True,
        "supervisor_owns_child_wait": True,
        "start_api_is_synchronous": True,
        "worker_pid_immediately_available": True,
        "guardian_v1_carries_worker_exit_status": False,
        "guardian_v1_carries_real_exec_plan": False,
        "guardian_v1_exposes_host_async_stdio": False,
        "guardian_host_control_is_tokio_async": False,
        "guardian_registered_in_bridge_library": False,
        "runtime_callers_present": False,
    }

    required = {
        "crates/bridge/src/story_render_supervisor.rs": [
            "StoryRenderSupervisorConfig",
            "StoryRenderAdmission::start",
            "start_story_render_supervisor",
            "HostLock",
            "SupervisedWorker",
        ],
        "crates/bridge/src/story_render_synthetic_admission.rs": [
            "run_s625_synthetic_admission"
        ],
        "crates/bridge/src/story_render_synthetic_composition.rs": [
            "run_s622_synthetic_composition"
        ],
        "crates/bridge/src/story_render_durable_synthetic_composition.rs": [
            "run_s630_durable_synthetic_composition"
        ],
    }
    changes = result["required_changes"]
    by_path = {str(change["path"]): change for change in changes}
    for path, symbols in required.items():
        assert by_path[path]["symbols"] == symbols
        source = (ROOT / path).read_text(encoding="utf-8")
        for symbol in symbols:
            assert symbol.split("::")[-1] in source


def test_s634_selects_bounded_v2_plan_stdio_and_result_transport() -> None:
    result = load_result()
    selected = result["selected_integration"]

    assert selected["custody_mode_gate"] == "StoryRenderCustodyMode"
    assert selected["default_mode"] == "direct_v1"
    assert selected["guardian_mode"] == "guardian_v2_default_off"
    assert selected["start_api"] == "async_bound_handshake_before_run_return"
    assert selected["worker_binding_available_on_run_return"] is True
    assert selected["control_protocol"] == {
        "magic": "ABG2",
        "version": 2,
        "maximum_body_bytes": 64,
        "length_prefix": "u32_big_endian",
        "unknown_or_trailing_fields": "reject",
    }
    assert selected["exec_plan_transport"] == {
        "carrier": "sealed_memfd",
        "canonical_encoding": "length_prefixed_binary_v1",
        "maximum_bytes": 65536,
        "digest": "sha256_echoed_in_bound_frame",
        "unknown_or_trailing_fields": "reject",
    }
    assert selected["stdio_transport"] == {
        "carrier": "host_created_unix_socketpairs",
        "worker_ends": "fixed_fds_via_guardian",
        "host_io": "tokio_async_bounded",
        "guardian_relays_payload_bytes": False,
        "guardian_closes_worker_ends_after_spawn": True,
    }
    assert selected["result_transport"] == {
        "control_protocol": "ABG2",
        "terminal_carries": ["worker_pid", "worker_pgid", "exit_kind", "exit_value"],
        "terminal_requires_group_absence": True,
        "stdout_stderr_use_control_protocol": False,
    }


def test_s634_locks_state_machine_and_replay_order() -> None:
    result = load_result()
    state_machine = result["state_machine"]
    replay = result["replay_continuity"]

    assert state_machine["states"] == [
        "admitted",
        "guardian_spawned",
        "bound",
        "running",
        "cancelling",
        "terminal_clean",
        "fallback_cleaning",
        "manual_recovery_required",
        "released",
    ]
    assert state_machine["release_condition"] == (
        "last_descriptor_close_after_group_absence_and_result_capture"
    )
    assert state_machine["cleanup_unproven"] == (
        "quarantine_host_descriptor_or_guardian_hold"
    )
    assert replay["order"] == [
        "acquire_render_lock",
        "generate_request_identity",
        "reserve_sequence",
        "spawn_guardian",
        "record_worker_binding",
        "acknowledge_start",
        "bounded_worker_io",
        "prove_worker_group_absent",
        "validate_terminal_and_response",
        "release_host_custody",
        "commit_or_abort_sequence",
    ]
    assert replay["busy_before_identity_and_reservation"] is True
    assert replay["reservation_before_payload_start"] is True
    assert replay["post_reservation_failure_consumes_sequence"] is True
    assert replay["finalize_failure_hides_worker_success"] is True


def test_s634_rollout_is_default_off_and_rollback_is_admission_scoped() -> None:
    result = load_result()
    rollout = result["rollout_and_rollback"]

    assert rollout == {
        "default_off": True,
        "activation_scope": "synthetic_config_per_admission",
        "lock_namespace_shared_across_modes": True,
        "rollback_scope": "future_admissions_only",
        "in_flight_mode_switch_allowed": False,
        "guardian_loss_downgrades_in_flight_to_direct": False,
        "parity_gate_required": True,
        "single_failure_fault_matrix_required": True,
        "real_worker_gate_open": False,
        "runtime_gate_open": False,
    }


def test_s634_preserves_review_only_authority_and_source_boundary() -> None:
    result = load_result()
    supervisor = (ROOT / "crates/bridge/src/story_render_supervisor.rs").read_text(
        encoding="utf-8"
    )
    guardian = (
        ROOT / "crates/bridge/src/story_render_guardian_synthetic.rs"
    ).read_text(encoding="utf-8")
    bridge_lib = (ROOT / "crates/bridge/src/lib.rs").read_text(encoding="utf-8")
    adr = ADR_PATH.read_text(encoding="utf-8")

    assert "struct HostLock(File)" in supervisor
    assert "libc::LOCK_UN" in supervisor
    assert "ABG1" in guardian
    assert "story_render_guardian_synthetic" not in bridge_lib
    assert all(value is False for value in result["authority"].values())
    assert all(value is False for value in result["runtime_effects"].values())
    assert result["claims"] == {
        "integration_review_complete": True,
        "supervisor_modified": False,
        "guardian_v2_implemented": False,
        "real_worker_executed": False,
        "runtime_integrated": False,
        "mcp_registered": False,
        "deployed": False,
    }
    assert "source-only architecture review" in adr
    assert "S635" in adr
    assert result["next_gate"] == (
        "story_render_guardian_supervisor_synthetic_integration"
    )
