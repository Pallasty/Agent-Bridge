from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_config_provenance_gate.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_config_provenance_gate.schema.json"
)
MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_config_provenance_gate", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def config_fixture() -> dict:
    return {
        "tts_model_size": "1b7",
        "tts_model_type": "custom_voice",
        "talker_config": {
            "vocab_size": 3072,
            "hidden_size": 2048,
            "num_code_groups": 16,
            "num_hidden_layers": 28,
            "num_key_value_heads": 8,
            "head_dim": 128,
            "codec_pad_id": 2148,
            "codec_bos_id": 2149,
            "codec_eos_token_id": 2150,
            "code_predictor_config": {
                "vocab_size": 2048,
                "hidden_size": 1024,
                "num_code_groups": 16,
            },
        },
    }


def make_inputs(root: Path) -> tuple[Path, Path, str]:
    snapshot = root / "snapshot"
    model_dir = snapshot / "cpu_int4"
    model_dir.mkdir(parents=True)
    for name in (
        "talker_cache.onnx",
        "code_predictor.onnx",
        "residual_embed.onnx",
    ):
        (model_dir / name).write_bytes(b"fixture")
    (snapshot / "STATUS.md").write_text(
        f"target: `{MODEL_ID}` from local `customvoice/`\n"
    )
    config = root / "config.json"
    config.write_text(json.dumps(config_fixture(), sort_keys=True))
    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    return snapshot, config, digest


def compatible_graphs() -> dict:
    return {
        "talker_cache": {
            "logits_width": 3072,
            "hidden_width": 2048,
            "kv_input_count": 56,
            "kv_heads": 8,
            "head_dim": 128,
        },
        "code_predictor": {
            "group_count": 15,
            "logits_width": 2048,
            "hidden_width": 2048,
            "codec_input_width": 16,
        },
        "residual_embed": {
            "codec_input_width": 16,
            "output_width": 2048,
        },
    }


def test_owner_authorization_blocks_session_metadata_read(
    tmp_path: Path,
) -> None:
    probe = load_module()
    snapshot, config, digest = make_inputs(tmp_path)
    calls = []

    receipt = probe.run_config_provenance_gate(
        snapshot,
        config,
        expected_config_sha256=digest,
        owner_authorized=False,
        inspector=lambda paths: calls.append(paths),
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["owner_authorization_required"]
    assert calls == []


def test_compatible_config_stays_provenance_incomplete(
    tmp_path: Path,
) -> None:
    probe = load_module()
    snapshot, config, digest = make_inputs(tmp_path)

    receipt = probe.run_config_provenance_gate(
        snapshot,
        config,
        expected_config_sha256=digest,
        owner_authorized=True,
        inspector=lambda _paths: compatible_graphs(),
    )

    assert receipt["status"] == "configuration_compatible_provenance_incomplete"
    assert receipt["config_graph_compatible"] is True
    assert receipt["reference_generation_ready"] is False
    assert receipt["blockers"] == [
        "converter_source_revision_missing",
        "observed_modelscope_revision_mutable",
        "fixed_huggingface_config_not_locally_acquired",
    ]
    assert receipt["runtime_effects"] == {
        "created_inference_sessions": 3,
        "executed_graphs": False,
        "downloaded_weights": False,
        "generated_codec_frames": False,
        "decoded_waveform": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def test_hash_mismatch_fails_before_session_creation(tmp_path: Path) -> None:
    probe = load_module()
    snapshot, config, _digest = make_inputs(tmp_path)
    calls = []

    receipt = probe.run_config_provenance_gate(
        snapshot,
        config,
        expected_config_sha256="0" * 64,
        owner_authorized=True,
        inspector=lambda paths: calls.append(paths),
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["official_config_hash_mismatch"]
    assert calls == []


def test_config_graph_width_mismatch_fails_closed(tmp_path: Path) -> None:
    probe = load_module()
    snapshot, config, digest = make_inputs(tmp_path)
    graphs = compatible_graphs()
    graphs["talker_cache"]["logits_width"] = 4096

    receipt = probe.run_config_provenance_gate(
        snapshot,
        config,
        expected_config_sha256=digest,
        owner_authorized=True,
        inspector=lambda _paths: graphs,
    )

    assert receipt["status"] == "blocked"
    assert receipt["config_graph_compatible"] is False
    assert "config_graph_contract_mismatch" in receipt["blockers"]


def test_wrong_model_identity_fails_closed(tmp_path: Path) -> None:
    probe = load_module()
    snapshot, config, digest = make_inputs(tmp_path)
    (snapshot / "STATUS.md").write_text(
        "target: `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`\n"
    )

    receipt = probe.run_config_provenance_gate(
        snapshot,
        config,
        expected_config_sha256=digest,
        owner_authorized=True,
        inspector=lambda _paths: compatible_graphs(),
    )

    assert receipt["status"] == "blocked"
    assert "converter_model_identity_missing" in receipt["blockers"]


def test_fixed_config_alone_cannot_replace_converter_revision(
    tmp_path: Path,
) -> None:
    probe = load_module()
    snapshot, config, digest = make_inputs(tmp_path)

    receipt = probe.run_config_provenance_gate(
        snapshot,
        config,
        expected_config_sha256=digest,
        owner_authorized=True,
        inspector=lambda _paths: compatible_graphs(),
        fixed_huggingface_config_locally_acquired=True,
    )

    assert receipt["reference_generation_ready"] is False
    assert receipt["blockers"] == [
        "converter_source_revision_missing",
        "observed_modelscope_revision_mutable",
    ]


def test_receipt_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = __import__("jsonschema")
    probe = load_module()
    snapshot, config, digest = make_inputs(tmp_path)
    receipt = probe.run_config_provenance_gate(
        snapshot,
        config,
        expected_config_sha256=digest,
        owner_authorized=False,
        inspector=lambda _paths: compatible_graphs(),
    )

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(receipt, schema)
