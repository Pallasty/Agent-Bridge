from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs/design/voice-scene"
RESULT_PATH = VOICE_SCENE / "s632_story_render_descendant_custody_review.json"
SCHEMA_PATH = VOICE_SCENE / "story_render_descendant_custody_review.schema.json"
ADR_PATH = VOICE_SCENE / "S632_STORY_RENDER_DESCENDANT_CUSTODY_REVIEW.md"


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


def decision_projection(result: dict[str, object]) -> dict[str, object]:
    names = (
        "decision",
        "current_baseline",
        "threat_model",
        "option_assessment",
        "selected_architecture",
        "failure_matrix",
        "acceptance_gates",
        "authority",
    )
    return {name: result[name] for name in names}


def test_s632_receipt_is_schema_valid_and_hash_bound() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    result = load_result()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(result)) == []
    assert result["decision_sha256"] == digest(decision_projection(result))


def test_s632_source_snapshot_matches_reviewed_baseline() -> None:
    result = load_result()
    evidence = result["evidence"]
    assert isinstance(evidence, dict)
    source_snapshot = evidence["source_snapshot"]
    assert isinstance(source_snapshot, list)

    for entry in source_snapshot:
        assert isinstance(entry, dict)
        path = ROOT / str(entry["path"])
        assert path.is_file()
        assert entry["sha256"] == file_digest(path)

    baseline = result["current_baseline"]
    assert baseline == {
        "direct_worker_parent_death_signal": True,
        "worker_session_and_process_group": True,
        "controlled_path_group_termination": True,
        "host_owned_lock": True,
        "direct_worker_abrupt_exit_proven": True,
        "arbitrary_descendant_abrupt_exit_proven": False,
    }


def test_s632_selects_guardian_without_overclaiming_kernel_custody() -> None:
    result = load_result()
    options = {
        option["id"]: option
        for option in result["option_assessment"]
        if isinstance(option, dict)
    }

    assert options["repository_owned_guardian"]["decision"] == "select"
    assert options["pr_set_pdeathsig"]["decision"] == "retain"
    assert options["session_process_group"]["decision"] == "retain"
    assert options["pr_set_child_subreaper"]["decision"] == "retain"
    assert options["pidfd"]["decision"] == "defer"
    assert options["cgroup_v2"]["decision"] == "defer"
    assert options["systemd_transient_unit"]["decision"] == (
        "reject_as_baseline"
    )

    threat = result["threat_model"]
    assert threat["fault_model"] == "one_userspace_custodian_failure_at_a_time"
    assert "simultaneous_host_and_guardian_loss" in threat["out_of_scope"]
    assert (
        "privileged_or_adversarial_descendant_escape_from_process_group"
        in threat["out_of_scope"]
    )


def test_s632_couples_lock_and_descendant_cleanup_custody() -> None:
    selected = load_result()["selected_architecture"]

    assert selected["name"] == "repository_owned_guardian"
    assert "neither may call LOCK_UN" in selected["lock_invariant"]
    assert "final descriptor may close only after" in selected["lock_invariant"]
    assert "sole control-channel write end" in selected["liveness_invariant"]
    assert "proves the group absent" in selected["termination_invariant"]
    assert "drains all orphan descendants" in selected["reaping_invariant"]
    assert selected["startup_sequence"][-2:] == [
        "host_validates_and_records_identity_then_acknowledges_start",
        "guardian_releases_start_gate_and_payload_exec_closes_all_custody_descriptors",
    ]

    faults = {
        row["fault"]: row
        for row in load_result()["failure_matrix"]
        if isinstance(row, dict)
    }
    assert faults["worker_exit_with_live_group_members"]["lock_release_allowed"] is False
    assert faults["group_absence_not_proven_before_deadline"] == {
        "fault": "group_absence_not_proven_before_deadline",
        "owner": "surviving_custodian",
        "required_result": (
            "fail_closed_and_retain_lock_descriptor_for_manual_recovery"
        ),
        "lock_release_allowed": False,
    }


def test_s632_next_gate_is_dormant_synthetic_prototype_only() -> None:
    result = load_result()

    assert result["next_gate"] == (
        "story_render_guardian_protocol_and_synthetic_custody_prototype"
    )
    assert result["acceptance_gates"]["supervisor_integration_allowed"] is False
    assert all(value is False for value in result["authority"].values())
    assert all(value is False for value in result["runtime_effects"].values())
    assert result["claims"] == {
        "direct_worker_baseline_verified": True,
        "descendant_custody_gap_confirmed": True,
        "guardian_implemented": False,
        "descendant_cleanup_proven": False,
        "runtime_enabled": False,
        "deployed": False,
    }


def test_s632_did_not_modify_or_wire_the_current_supervisor() -> None:
    source = (ROOT / "crates/bridge/src/story_render_supervisor.rs").read_text(
        encoding="utf-8"
    )

    for current_marker in (
        "struct HostLock(File);",
        "libc::flock(self.0.as_raw_fd(), libc::LOCK_UN)",
        "libc::PR_SET_PDEATHSIG",
        "libc::setsid()",
        "terminate_and_wait(&mut child, worker_pid",
    ):
        assert current_marker in source
    for forbidden_runtime_marker in (
        "StoryRenderGuardian",
        "PR_SET_CHILD_SUBREAPER",
        "cgroup.kill",
        "systemd-run",
    ):
        assert forbidden_runtime_marker not in source

    adr = ADR_PATH.read_text(encoding="utf-8")
    assert "source-only architecture review" in adr
    assert "Neither copy may call `LOCK_UN`" in adr
    assert "S633 cannot integrate the prototype" in adr
