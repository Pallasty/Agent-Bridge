from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_model_research_gate.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_model_research_receipt.schema.json"
)
PROFILE_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "mi50_qwen_onnx.compose.yaml"
)
SUPPLY_CHAIN_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "qwen3_tts_streaming_onnx_supply_chain.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_model_research_gate", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_privileged_compose_is_blocked(tmp_path: Path) -> None:
    gate = load_module()
    compose = tmp_path / "compose.yml"
    compose.write_text(
        """
services:
  voice:
    image: rocm/dev-ubuntu-22.04:5.7
    privileged: true
    environment:
      - HSA_OVERRIDE_GFX_VERSION=9.0.6
""".strip()
    )

    result = gate.audit_mi50_container(compose)

    assert result["status"] == "blocked"
    assert result["execution_attempted"] is False
    assert result["observed_gfx_override"] == "9.0.6"
    assert "privileged_container" in result["blockers"]
    assert "missing_explicit_kfd_mapping" in result["blockers"]
    assert "missing_explicit_mi50_render_node" in result["blockers"]


def test_minimal_explicit_mi50_mapping_is_static_ready(tmp_path: Path) -> None:
    gate = load_module()
    compose = tmp_path / "compose.yml"
    compose.write_text(
        """
services:
  voice:
    image: local/qwen-onnx-mi50@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    devices:
      - /dev/kfd:/dev/kfd
      - /dev/dri/renderD129:/dev/dri/renderD129
    group_add:
      - render
      - video
    security_opt:
      - no-new-privileges:true
    read_only: true
    network_mode: none
    environment:
      - HSA_OVERRIDE_GFX_VERSION=9.0.6
""".strip()
    )

    result = gate.audit_mi50_container(compose)

    assert result["status"] == "static_ready"
    assert result["blockers"] == []
    assert result["image_digest_pinned"] is True
    assert result["network_disabled"] is True
    assert result["read_only_rootfs"] is True


def test_commented_device_mappings_are_not_security_evidence(
    tmp_path: Path,
) -> None:
    gate = load_module()
    compose = tmp_path / "compose.yml"
    compose.write_text(
        """
services:
  voice:
    # devices:
    #   - /dev/kfd:/dev/kfd
    #   - /dev/dri:/dev/dri
    environment:
      - HSA_OVERRIDE_GFX_VERSION=9.0.6
""".strip()
    )

    result = gate.audit_mi50_container(compose)

    assert "missing_explicit_kfd_mapping" in result["blockers"]
    assert "missing_explicit_mi50_render_node" in result["blockers"]
    assert "broad_dri_mapping" not in result["blockers"]


def test_repository_mi50_profile_is_least_privilege_static_ready() -> None:
    gate = load_module()

    result = gate.audit_mi50_container(PROFILE_PATH)

    assert result["status"] == "static_ready"
    assert result["capabilities_dropped"] is True
    assert result["no_new_privileges"] is True
    assert result["mi50_only"] is True
    assert result["runtime_profile_gated"] is True


def test_pinned_metadata_does_not_upgrade_unverified_weights() -> None:
    gate = load_module()
    snapshot = json.loads(SUPPLY_CHAIN_PATH.read_text())

    result = gate.audit_supply_chain_snapshot(snapshot)

    assert result["status"] == "metadata_pinned_weights_blocked"
    assert result["source_revision"] == (
        "3717103c6fa278c1810e97672c02b185a7239737"
    )
    assert result["license_claim"] == "Apache-2.0"
    assert result["blockers"] == [
        "current_head_unresolved",
        "standalone_license_file_unverified",
        "model_artifact_hashes_unverified",
        "operator_inventory_unverified",
        "reference_parity_missing",
        "mi50_execution_provider_unverified",
    ]
    assert result["downloads_models"] is False


def candidate(**overrides) -> dict:
    value = {
        "candidate_id": "qwen3-tts-0.6b-onnx-community",
        "upstream_model": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        "source_url": "https://example.invalid/community/qwen-onnx",
        "source_revision": None,
        "license": {"status": "unverified", "spdx": None},
        "artifact_manifest": [],
        "operator_inventory": [],
        "components": {
            "text_model": False,
            "speech_tokenizer": False,
            "vocoder": False,
        },
        "reference_parity": {
            "status": "not_run",
            "reference_wav_sha256": None,
        },
    }
    value.update(overrides)
    return value


def test_unverified_community_onnx_fails_closed() -> None:
    gate = load_module()

    result = gate.audit_onnx_candidate(candidate())

    assert result["status"] == "blocked"
    assert result["execution_attempted"] is False
    assert result["blockers"] == [
        "source_revision_unpinned",
        "license_unverified",
        "artifact_manifest_missing",
        "operator_inventory_missing",
        "text_model_missing",
        "speech_tokenizer_missing",
        "vocoder_missing",
        "reference_parity_missing",
    ]


def test_hash_bound_complete_candidate_is_only_trial_ready() -> None:
    gate = load_module()
    complete = candidate(
        source_revision="1" * 40,
        license={"status": "verified", "spdx": "Apache-2.0"},
        artifact_manifest=[
            {
                "path": "model.onnx",
                "size": 123,
                "sha256": "a" * 64,
            }
        ],
        operator_inventory=["MatMul", "Softmax"],
        components={
            "text_model": True,
            "speech_tokenizer": True,
            "vocoder": True,
        },
        reference_parity={
            "status": "verified",
            "reference_wav_sha256": "b" * 64,
        },
    )

    result = gate.audit_onnx_candidate(complete)

    assert result["status"] == "trial_ready"
    assert result["production_eligible"] is False
    assert result["execution_attempted"] is False


def test_report_keeps_container_and_model_gates_independent(
    tmp_path: Path,
) -> None:
    gate = load_module()
    compose = tmp_path / "compose.yml"
    compose.write_text("services:\n  voice:\n    privileged: true\n")
    manifest = {
        "schema": "agent_bridge.voice_model_research_manifest.v1",
        "candidates": [candidate()],
    }

    report = gate.build_report(
        manifest, container_config=compose, supply_chain_snapshot=None
    )

    assert report["status"] == "blocked"
    assert report["runtime_effects"] == {
        "downloads_models": False,
        "starts_containers": False,
        "uses_gpu": False,
        "plays_audio": False,
        "writes_memory": False,
    }
    assert report["container"]["status"] == "blocked"
    assert report["candidates"][0]["status"] == "blocked"
    assert report["supply_chain"] is None


def test_cli_receipt_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = __import__("jsonschema")
    compose = tmp_path / "compose.yml"
    compose.write_text("services:\n  voice:\n    privileged: true\n")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "agent_bridge.voice_model_research_manifest.v1",
                "candidates": [candidate()],
            }
        )
    )
    output = tmp_path / "receipt.json"

    completed = subprocess.run(
        [
            "python3",
            str(MODULE_PATH),
            "--manifest",
            str(manifest_path),
            "--container-config",
            str(compose),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    receipt = json.loads(output.read_text())
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(receipt, schema)
    assert receipt["status"] == "blocked"
