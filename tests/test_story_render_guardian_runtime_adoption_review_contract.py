from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs/design/voice-scene"
RESULT_PATH = VOICE_SCENE / "s636_story_render_guardian_runtime_adoption_review.json"
SCHEMA_PATH = VOICE_SCENE / "story_render_guardian_runtime_adoption_review.schema.json"
ADR_PATH = VOICE_SCENE / "S636_STORY_RENDER_GUARDIAN_RUNTIME_ADOPTION_REVIEW.md"
REVIEWED_TREE = "d3e22778aa21146ca734520ea15c0a0a8fed958d"


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


def reviewed_bytes(path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{REVIEWED_TREE}:{path}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def reviewed_text(path: str) -> str:
    return reviewed_bytes(path).decode("utf-8")


def reviewed_path_exists(path: str) -> bool:
    return (
        subprocess.run(
            ["git", "cat-file", "-e", f"{REVIEWED_TREE}:{path}"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def receipt_projection(result: dict[str, object]) -> dict[str, object]:
    names = (
        "decision",
        "impact",
        "source_findings",
        "installed_findings",
        "model_and_python_compatibility",
        "runtime_compatibility",
        "blockers",
        "implementation_ladder",
        "rollback",
        "authority",
        "runtime_effects",
        "claims",
        "nonclaims",
        "next_gate",
    )
    return {name: result[name] for name in names}


def test_s636_receipt_is_schema_valid_and_hash_bound() -> None:
    result = load_result()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(result)) == []
    assert result["receipt_sha256"] == digest(receipt_projection(result))


def test_s636_source_evidence_matches_reviewed_tree() -> None:
    result = load_result()
    source_evidence = result["source_evidence"]
    assert isinstance(source_evidence, list)
    assert len(source_evidence) >= 12

    for entry in source_evidence:
        assert isinstance(entry, dict)
        path = str(entry["path"])
        assert entry["sha256"] == hashlib.sha256(reviewed_bytes(path)).hexdigest()


def test_s636_distinguishes_synthetic_guardian_from_product_adoption() -> None:
    result = load_result()
    findings = result["source_findings"]

    assert findings == {
        "guardian_v2_implemented": True,
        "guardian_v2_default": False,
        "guardian_entrypoint_has_product_caller": False,
        "guardian_product_binary_present": False,
        "real_one_shot_worker_present": False,
        "render_mcp_module_present": False,
        "render_mcp_registered": False,
        "preflight_mcp_registered": True,
        "preflight_is_read_only_dry_run": True,
        "deployment_packages_guardian_or_worker": False,
        "sealed_plan_binds_file_content_identity": False,
    }

    assert not reviewed_path_exists("scripts/story_render_one_shot_worker.py")
    assert not reviewed_path_exists("crates/bridge/src/mcp_tools/story_render.rs")

    guardian = reviewed_text("crates/bridge/src/story_render_guardian.rs")
    supervisor = reviewed_text("crates/bridge/src/story_render_supervisor.rs")
    mcp_story = reviewed_text("crates/bridge/src/mcp_tools/story.rs")
    deploy = reviewed_text("scripts/deploy_from_master.sh")

    assert "run_guardian_entrypoint" in guardian
    assert "StoryRenderCustodyMode::DirectV1" in supervisor
    assert '"const": true' in mcp_story
    assert "story_render_one_shot_worker.py" not in deploy


def test_s636_accepts_model_files_but_rejects_runtime_plan_compatibility() -> None:
    result = load_result()
    model = result["model_and_python_compatibility"]
    compatibility = result["runtime_compatibility"]

    assert model["original_model_snapshot_present"] is True
    assert model["community_cpu_int4_snapshot_present"] is True
    assert model["s608_full_bundle_hash_verified"] is True
    assert model["model_redownload_required"] is False
    assert model["synthetic_python_executable"] == "/usr/bin/python3"
    assert model["synthetic_python_has_required_tts_modules"] is False
    assert model["real_model_loaded_in_s636"] is False

    assert compatibility == {
        "worker_protocol_codec": "implemented_and_unit_testable",
        "bounded_executor": "implemented_as_in_process_callable",
        "installed_key_composition": "implemented_but_not_worker_wrapped",
        "guardian_transport": "synthetic_verified_only",
        "real_worker_protocol_entrypoint": "absent",
        "immutable_worker_package": "absent",
        "fixed_python_environment": "absent",
        "secure_output_contract": "incompatible_roots",
        "owner_authorization_broker": "absent",
        "mcp_render_adapter": "absent",
        "current_client_render_tool": "absent",
        "runtime_adoption_ready": False,
    }


def test_s636_blocks_adoption_on_identity_packaging_and_authority() -> None:
    result = load_result()
    blockers = result["blockers"]
    by_id = {str(item["id"]): item for item in blockers}

    assert set(by_id) == {
        "B1_REAL_WORKER_ENTRYPOINT",
        "B2_GUARDIAN_PRODUCT_ENTRYPOINT",
        "B3_EXECUTABLE_IDENTITY_TOCTOU",
        "B4_IMMUTABLE_PACKAGE_AND_PYTHON",
        "B5_SECURE_OUTPUT_ROOT",
        "B6_OWNER_AUTHORIZATION_BROKER",
        "B7_RENDER_MCP_SURFACE",
        "B8_DEPLOYED_BINARY_AND_INSTALL_TRUST",
    }
    assert by_id["B3_EXECUTABLE_IDENTITY_TOCTOU"]["severity"] == "critical"
    assert by_id["B8_DEPLOYED_BINARY_AND_INSTALL_TRUST"]["severity"] == "critical"
    assert all(item["closed"] is False for item in blockers)


def test_s636_selects_source_only_s637_before_packaging_or_runtime() -> None:
    result = load_result()
    ladder = result["implementation_ladder"]
    ids = [item["id"] for item in ladder]

    assert ids == ["S637", "S638", "S639", "S640", "S641", "S642", "S643"]
    assert ladder[0] == {
        "id": "S637",
        "name": "story_render_real_worker_adapter_implementation",
        "authority": "source_only_synthetic_tests",
        "closes": ["B1_REAL_WORKER_ENTRYPOINT"],
        "forbids": [
            "installed_key_read",
            "model_load",
            "audio_write_or_playback",
            "mcp_registration",
            "deployment",
        ],
    }
    assert result["next_gate"] == {
        "id": "S637",
        "name": "story_render_real_worker_adapter_implementation",
        "authority": "source_only_synthetic_tests",
        "runtime_enablement": "not_authorized",
    }


def test_s636_preserves_review_only_authority_and_effect_boundary() -> None:
    result = load_result()
    adr = ADR_PATH.read_text(encoding="utf-8")

    assert all(value is False for value in result["authority"].values())
    assert all(value is False for value in result["runtime_effects"].values())
    assert result["claims"] == {
        "runtime_adoption_review_complete": True,
        "model_bundle_present_and_hash_verified": True,
        "guardian_real_worker_compatible": False,
        "runtime_configuration_ready": False,
        "mcp_render_registered": False,
        "current_client_render_visible": False,
        "deployed": False,
    }
    assert "review-only" in adr
    assert "S637" in adr
