from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import sqlite3
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_bounded_render_executor.py"
TRUSTED_RUNNER = ROOT / "scripts" / "story_voice_existing_onnx_trusted_runner.py"
NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def load_module():
    assert MODULE_PATH.exists(), "S606 bounded-render executor is missing"
    spec = importlib.util.spec_from_file_location(
        "story_bounded_render_executor", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(tmp_path: Path, *, segments: int = 2):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    model_root = tmp_path / "model"
    model_root.mkdir()
    inference = model_root / "inference.py"
    inference.write_text("# pinned inference\n", encoding="utf-8")
    onnx = model_root / "cpu_int4"
    onnx.mkdir()
    tts = model_root / "tts"
    tts.mkdir()
    output = runtime_root / "grant-001"
    render_requests = [
        {
            "event_id": f"event-{index}",
            "text": "苏岚回答。" if index == 0 else "我听见钟声了。",
            "qwen_speaker": "Vivian" if index == 0 else "Serena",
            "style_instruction": "自然清晰。",
            "cache_key": str(index + 1) * 64,
        }
        for index in range(segments)
    ]
    preflight_hash = "6" * 64
    evidence = {
        "trusted_runner_path": str(TRUSTED_RUNNER.resolve()),
        "trusted_runner_sha256": file_hash(TRUSTED_RUNNER),
        "preflight_sha256": preflight_hash,
        "model_inference_sha256": file_hash(inference),
    }
    bounds = {
        "max_segments_per_grant": 3,
        "max_codec_frames_per_segment": 100,
        "max_assembled_duration_seconds": 30.0,
        "sample_rate_hz": 24000,
        "channels": 1,
        "allowed_speakers": ["Serena", "Vivian"],
        "output_root": str(runtime_root),
        "existing_output_overwrite_allowed": False,
        "network_allowed": False,
        "gpu_allowed": False,
    }
    authority = {
        "render": {
            "grant_required": True,
            "grant_present": False,
            "single_use": True,
            "bound_fields": [
                "contract_sha256",
                "preflight_sha256",
                "output_directory",
            ],
        },
        "playback": {
            "grant_required": True,
            "grant_present": False,
            "single_use": True,
            "requires_machine_gate": True,
            "bound_fields": ["render_receipt_sha256", "audio_sha256"],
        },
        "record": {"supported": False, "grant_present": False},
        "memory_write": {"supported": False, "grant_present": False},
    }
    runtime_effects = {
        "created_output_directory": False,
        "loaded_model": False,
        "executed_onnx": False,
        "rendered_audio": False,
        "played_audio": False,
        "recorded_audio": False,
        "wrote_cache": False,
        "wrote_memory": False,
    }
    contract = {
        "schema": "agent_bridge.story_bounded_render_execution_contract.v1",
        "status": "story_bounded_render_execution_contract_reviewable",
        "evidence": evidence,
        "bounds": bounds,
        "authority": authority,
        "state_machine": [
            "preflight_reviewed",
            "render_grant_required",
            "bounded_render",
            "machine_audio_gate",
            "playback_grant_required",
            "single_playback",
            "owner_feedback",
        ],
        "execution_authorized": False,
        "runtime_effects": runtime_effects,
        "claims": {
            "executor_implemented": False,
            "runtime_execution_admitted": False,
        },
        "next_gate": "story_bounded_render_executor_implementation_review",
    }
    bound = {
        key: contract[key]
        for key in (
            "evidence",
            "bounds",
            "authority",
            "state_machine",
            "execution_authorized",
            "runtime_effects",
        )
    }
    contract["contract_sha256"] = digest(bound)
    authorization = {
        "authorization_id": "auth-001",
        "contract_sha256": contract["contract_sha256"],
        "preflight_sha256": preflight_hash,
        "output_directory": str(output),
        "action": "render",
        "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=4)).isoformat(),
        "single_use_nonce": "nonce-001",
    }
    request = {
        "preflight": {
            "preflight_sha256": preflight_hash,
            "render_requests": render_requests,
            "assembly_gap_seconds": [0.25] * max(0, segments - 1),
        },
        "model": {
            "inference_path": str(inference),
            "model_path": str(onnx),
            "tts_dir": str(tts),
        },
        "output_directory": str(output),
        "playback": False,
        "record": False,
        "write_memory": False,
    }
    return contract, authorization, request, tmp_path / "nonce.sqlite3", output


def wav_runner(*, output_path: Path, **kwargs):
    del kwargs
    with wave.open(str(output_path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24000)
        stream.writeframes((1000).to_bytes(2, "little", signed=True) * 2400)
    return {
        "generated_codec_frames": 12,
        "frame_cap": 100,
        "stopped_before_frame_cap": True,
    }


def verified(_authorization: dict) -> bool:
    return True


def verified_model(_model: dict, _contract: dict) -> bool:
    return True


def test_executor_renders_to_new_directory_and_emits_machine_receipt(
    tmp_path: Path,
) -> None:
    module = load_module()
    contract, authorization, request, nonce_store, output = fixture(tmp_path)
    module._load_runner = lambda _path: wav_runner

    receipt = module.execute_bounded_render(
        contract=contract,
        authorization=authorization,
        request=request,
        now=NOW,
        authority_verifier=verified,
        model_verifier=verified_model,
        nonce_store_path=nonce_store,
    )

    assert receipt["status"] == "bounded_render_machine_verified"
    assert len(receipt["segments"]) == 2
    assert receipt["assembly"]["duration_seconds"] == pytest.approx(0.45)
    assert receipt["runtime_effects"] == {
        "created_output_directory": True,
        "loaded_model": True,
        "executed_onnx": True,
        "rendered_audio": True,
        "played_audio": False,
        "recorded_audio": False,
        "wrote_cache": False,
        "wrote_memory": False,
        "consumed_render_nonce": True,
    }
    assert (output / "chapter.wav").is_file()
    assert (output / "render-receipt.json").is_file()
    assert not list(output.glob("*.part*"))
    assert json.loads((output / "render-receipt.json").read_text()) == receipt
    with sqlite3.connect(nonce_store) as connection:
        assert connection.execute("select count(*) from consumed_nonces").fetchone()[0] == 1


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda auth, req: auth.update(expires_at=(NOW - timedelta(seconds=1)).isoformat()), "authorization expired"),
        (lambda auth, req: auth.update(contract_sha256="0" * 64), "contract SHA-256 mismatch"),
        (lambda auth, req: req.update(playback=True), "playback requested"),
        (lambda auth, req: req.update(record=True), "recording requested"),
        (lambda auth, req: req.update(write_memory=True), "memory write requested"),
    ],
)
def test_executor_rejects_unauthorized_actions_before_side_effects(
    tmp_path: Path, mutation, message: str
) -> None:
    module = load_module()
    contract, authorization, request, nonce_store, output = fixture(tmp_path)
    mutation(authorization, request)

    with pytest.raises(ValueError, match=message):
        module.execute_bounded_render(
            contract=contract,
            authorization=authorization,
            request=request,
            now=NOW,
            authority_verifier=verified,
            model_verifier=verified_model,
            nonce_store_path=nonce_store,
        )

    assert not output.exists()
    assert not nonce_store.exists()


def test_executor_requires_external_authority_verification(tmp_path: Path) -> None:
    module = load_module()
    contract, authorization, request, nonce_store, output = fixture(tmp_path)

    with pytest.raises(ValueError, match="authority proof rejected"):
        module.execute_bounded_render(
            contract=contract,
            authorization=authorization,
            request=request,
            now=NOW,
            authority_verifier=lambda _value: False,
            model_verifier=verified_model,
            nonce_store_path=nonce_store,
        )

    assert not output.exists()
    assert not nonce_store.exists()


def test_executor_requires_external_model_bundle_verification(tmp_path: Path) -> None:
    module = load_module()
    contract, authorization, request, nonce_store, output = fixture(tmp_path)

    with pytest.raises(ValueError, match="model bundle proof rejected"):
        module.execute_bounded_render(
            contract=contract,
            authorization=authorization,
            request=request,
            now=NOW,
            authority_verifier=verified,
            model_verifier=lambda _model, _contract: False,
            nonce_store_path=nonce_store,
        )

    assert not output.exists()
    assert not nonce_store.exists()


def test_authority_is_verified_before_model_bundle_admission(tmp_path: Path) -> None:
    module = load_module()
    contract, authorization, request, nonce_store, _output = fixture(tmp_path)
    order: list[str] = []

    def authority(_authorization: dict) -> bool:
        order.append("authority")
        return True

    def model(_model: dict, _contract: dict) -> bool:
        order.append("model")
        assert order == ["authority", "model"]
        return True

    module._load_runner = lambda _path: wav_runner
    module.execute_bounded_render(
        contract=contract,
        authorization=authorization,
        request=request,
        now=NOW,
        authority_verifier=authority,
        model_verifier=model,
        nonce_store_path=nonce_store,
    )

    assert order == ["authority", "model"]


def test_consumed_nonce_cannot_be_retried_after_render_failure(tmp_path: Path) -> None:
    module = load_module()
    contract, authorization, request, nonce_store, output = fixture(tmp_path)

    def failing_runner(**_kwargs):
        raise RuntimeError("synthetic runner failure")

    module._load_runner = lambda _path: failing_runner
    with pytest.raises(RuntimeError, match="synthetic runner failure"):
        module.execute_bounded_render(
            contract=contract,
            authorization=authorization,
            request=request,
            now=NOW,
            authority_verifier=verified,
            model_verifier=verified_model,
            nonce_store_path=nonce_store,
        )
    assert not output.exists()

    module._load_runner = lambda _path: wav_runner
    with pytest.raises(ValueError, match="single-use nonce already consumed"):
        module.execute_bounded_render(
            contract=contract,
            authorization=authorization,
            request=request,
            now=NOW,
            authority_verifier=verified,
            model_verifier=verified_model,
            nonce_store_path=nonce_store,
        )


def test_machine_gate_rejects_silent_audio_and_cleans_owned_output(
    tmp_path: Path,
) -> None:
    module = load_module()
    contract, authorization, request, nonce_store, output = fixture(tmp_path)

    def silent_runner(*, output_path: Path, **_kwargs):
        with wave.open(str(output_path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(24000)
            stream.writeframes(b"\x00\x00" * 2400)
        return {
            "generated_codec_frames": 12,
            "frame_cap": 100,
            "stopped_before_frame_cap": True,
        }

    module._load_runner = lambda _path: silent_runner
    with pytest.raises(ValueError, match="audio is silent"):
        module.execute_bounded_render(
            contract=contract,
            authorization=authorization,
            request=request,
            now=NOW,
            authority_verifier=verified,
            model_verifier=verified_model,
            nonce_store_path=nonce_store,
        )
    assert not output.exists()


def test_executor_rejects_existing_or_escaping_output_directory(
    tmp_path: Path,
) -> None:
    module = load_module()
    contract, authorization, request, nonce_store, output = fixture(tmp_path)
    output.mkdir()
    with pytest.raises(ValueError, match="output target exists"):
        module.execute_bounded_render(
            contract=contract,
            authorization=authorization,
            request=request,
            now=NOW,
            authority_verifier=verified,
            model_verifier=verified_model,
            nonce_store_path=nonce_store,
        )
    assert not nonce_store.exists()

    contract, authorization, request, nonce_store, _ = fixture(
        tmp_path / "escape-case"
    )
    escape = tmp_path / "outside"
    authorization["output_directory"] = str(escape)
    request["output_directory"] = str(escape)
    with pytest.raises(ValueError, match="output directory outside contract root"):
        module.execute_bounded_render(
            contract=contract,
            authorization=authorization,
            request=request,
            now=NOW,
            authority_verifier=verified,
            model_verifier=verified_model,
            nonce_store_path=nonce_store,
        )
    assert not escape.exists()


def test_source_has_no_shell_playback_or_memory_integration() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert "subprocess" not in imports
    assert "pw-play" not in source
    assert "present_voice" not in source
    assert "mcp_tools" not in source
    assert "write_memory" not in source
    assert "runner_override" not in source
