import hashlib
import hmac
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/story_executor_secure_runtime_composition.py"
VERIFIER_PATH = ROOT / "scripts/story_executor_runtime_verifiers.py"
S604 = ROOT / "docs/design/voice-scene/s604_story_bounded_render_execution_contract.json"
S608 = ROOT / "docs/design/voice-scene/s608_story_executor_authority_model_nonce_contract.json"


def load(path, name):
    assert path.exists(), f"missing module:{path}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture():
    composition = load(MODULE_PATH, "s610")
    verifier = load(VERIFIER_PATH, "s609_for_s610")
    execution_contract = json.loads(S604.read_text())
    runtime_contract = json.loads(S608.read_text())
    output = execution_contract["bounds"]["output_root"] + "/s610-prepared"
    envelope = {
        "authorization_id": "auth-s610-synthetic",
        "contract_sha256": execution_contract["contract_sha256"],
        "preflight_sha256": execution_contract["evidence"]["preflight_sha256"],
        "output_directory": output,
        "action": "render",
        "issued_at": "2026-08-01T12:00:00+00:00",
        "expires_at": "2026-08-01T12:05:00+00:00",
        "single_use_nonce": "nonce-s610-synthetic",
        "issuer": "agent-bridge-owner-console",
        "subject": "story-bounded-render-executor",
        "key_id": "synthetic-test-key",
    }
    key = b"s610-synthetic-key-material-32b!"
    message = verifier.canonical_authorization_message(envelope, runtime_contract)
    envelope["mac_sha256"] = hmac.new(key, message, hashlib.sha256).hexdigest()
    snapshot = Path(runtime_contract["model_bundle"]["snapshot"])
    request = {
        "preflight": {"preflight_sha256": envelope["preflight_sha256"], "render_requests": [{
            "event_id": "s610-event-1", "text": "准备阶段不执行。", "qwen_speaker": "Vivian",
            "style_instruction": "自然清晰。", "cache_key": "c" * 64}], "assembly_gap_seconds": []},
        "model": {"inference_path": runtime_contract["model_bundle"]["inference_path"],
                  "model_path": str(snapshot / "cpu_int4"),
                  "tts_dir": str(verifier.FIXED_TTS_DIR)},
        "output_directory": output, "playback": False, "record": False, "write_memory": False,
    }
    return composition, execution_contract, envelope, key, request


def test_prepare_composes_exact_executor_arguments_without_execution():
    module, contract, envelope, key, request = fixture()
    prepared = module.prepare_secure_bounded_render(
        execution_contract=contract, envelope=envelope, key=key, request=request)
    assert set(prepared) == {"contract", "authorization", "request", "authority_verifier", "model_verifier", "nonce_store_path"}
    assert prepared["contract"] == contract
    assert prepared["authorization"] == {name: envelope[name] for name in module.EXECUTOR_AUTHORIZATION_FIELDS}
    assert prepared["authority_verifier"](prepared["authorization"]) is True
    assert prepared["nonce_store_path"] == Path("/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3")
    assert not prepared["nonce_store_path"].exists()


def test_prepare_rejects_envelope_request_and_model_path_drift():
    module, contract, envelope, key, request = fixture()
    changed = dict(envelope, mac_sha256="0" * 64)
    with pytest.raises(ValueError, match="MAC"):
        module.prepare_secure_bounded_render(execution_contract=contract, envelope=changed, key=key, request=request)
    changed_request = dict(request, playback=True)
    with pytest.raises(ValueError, match="request"):
        module.prepare_secure_bounded_render(execution_contract=contract, envelope=envelope, key=key, request=changed_request)
    changed_request = json.loads(json.dumps(request))
    changed_request["model"]["tts_dir"] = "/tmp/caller-selected"
    with pytest.raises(ValueError, match="model"):
        module.prepare_secure_bounded_render(execution_contract=contract, envelope=envelope, key=key, request=changed_request)


def test_prepare_rejects_execution_contract_drift():
    module, contract, envelope, key, request = fixture()
    contract["bounds"]["gpu_allowed"] = True
    with pytest.raises(ValueError, match="execution contract"):
        module.prepare_secure_bounded_render(execution_contract=contract, envelope=envelope, key=key, request=request)


def test_source_has_no_execution_cli_secret_or_database_surface():
    source = MODULE_PATH.read_text()
    assert "execute_bounded_render" not in source
    assert "os.environ" not in source
    assert "import sqlite3" not in source
    assert "onnxruntime" not in source
    assert 'if __name__ == "__main__"' not in source
