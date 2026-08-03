from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs/design/voice-scene"
RESULT_PATH = VOICE_SCENE / "s633_story_render_guardian_synthetic_prototype.json"
SCHEMA_PATH = VOICE_SCENE / "story_render_guardian_synthetic_prototype.schema.json"
ADR_PATH = VOICE_SCENE / "S633_STORY_RENDER_GUARDIAN_SYNTHETIC_PROTOTYPE.md"


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
        "protocol",
        "startup_gate",
        "custody",
        "single_failure_proofs",
        "test_effects",
        "authority",
        "runtime_effects",
        "claims",
        "nonclaims",
        "next_gate",
    )
    return {name: result[name] for name in names}


def test_s633_receipt_is_schema_valid_and_hash_bound() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    result = load_result()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(result)) == []
    assert result["receipt_sha256"] == digest(receipt_projection(result))


def test_s633_evidence_hashes_match_landed_sources() -> None:
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

    s632 = evidence["s632_review"]
    assert isinstance(s632, dict)
    s632_path = ROOT / str(s632["path"])
    assert s632["sha256"] == file_digest(s632_path)
    assert s632["decision_sha256"] == (
        "5c902205f35709c4ea4a6ebd588c608e046c3282509f772a48532793c0498227"
    )


def test_s633_proves_required_single_failure_and_lock_properties() -> None:
    result = load_result()

    assert result["protocol"] == {
        "magic": "ABG1",
        "version": 1,
        "maximum_body_bytes": 64,
        "length_prefix": "u32_big_endian",
        "frames": ["bound", "start", "cancel", "terminal", "failure"],
        "unknown_or_trailing_fields": "reject",
        "pid_binding": "worker_pid_equals_worker_pgid",
    }
    assert result["startup_gate"]["payload_before_host_acknowledgement"] is False
    assert result["startup_gate"]["worker_identity_recorded_before_payload"] is True
    assert result["custody"]["explicit_unlock_allowed"] is False
    assert result["custody"]["release_condition"] == (
        "last_descriptor_close_after_cleanup_proven"
    )

    proofs = result["single_failure_proofs"]
    assert all(proofs.values())


def test_s633_keeps_real_runtime_and_authority_closed() -> None:
    result = load_result()

    assert result["test_effects"] == {
        "repository_owned_processes_spawned": True,
        "temporary_lock_files_created": True,
        "temporary_marker_files_created": True,
        "term_ignoring_descendant_spawned": True,
        "all_fixture_processes_reaped_or_proven_not_live": True,
        "temporary_roots_removed": True,
    }
    assert all(value is False for value in result["authority"].values())
    assert all(value is False for value in result["runtime_effects"].values())
    assert result["claims"] == {
        "guardian_protocol_implemented": True,
        "synthetic_single_failure_custody_proven": True,
        "current_supervisor_modified": False,
        "runtime_integrated": False,
        "mcp_registered": False,
        "deployed": False,
    }
    assert result["next_gate"] == "story_render_guardian_supervisor_integration_review"


def test_s633_docs_and_source_preserve_dormant_boundary() -> None:
    source = (
        ROOT / "crates/bridge/src/story_render_guardian_synthetic.rs"
    ).read_text(encoding="utf-8")
    supervisor = (ROOT / "crates/bridge/src/story_render_supervisor.rs").read_text(
        encoding="utf-8"
    )
    bridge_lib = (ROOT / "crates/bridge/src/lib.rs").read_text(encoding="utf-8")
    adr = ADR_PATH.read_text(encoding="utf-8")

    assert "story_render_guardian_synthetic" not in supervisor
    assert "story_render_guardian_synthetic" not in bridge_lib
    assert "never calls\n/// `LOCK_UN`" in source
    assert "source-only synthetic prototype" in adr
    assert "does not modify `story_render_supervisor.rs`" in adr
    assert "S634" in adr
