from __future__ import annotations

import copy
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/story_executor_runtime_verifiers.py"
S608 = ROOT / "docs/design/voice-scene/s608_story_executor_authority_model_nonce_contract.json"


def load_module():
    assert MODULE_PATH.exists(), "S609 runtime verifier module is missing"
    spec = importlib.util.spec_from_file_location("s609", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def authority_fixture(module, key: bytes = b"k" * 32):
    contract = json.loads(S608.read_text())
    envelope = {
        "authorization_id": "auth-609-001",
        "contract_sha256": "a" * 64,
        "preflight_sha256": "b" * 64,
        "output_directory": "/Data/Models/agent-bridge/evidence/story-render/auth-609-001",
        "action": "render",
        "issued_at": "2026-08-01T12:00:00+00:00",
        "expires_at": "2026-08-01T12:05:00+00:00",
        "single_use_nonce": "nonce-609-001",
        "issuer": "agent-bridge-owner-console",
        "subject": "story-bounded-render-executor",
        "key_id": "story-render-owner-v1",
    }
    message = module.canonical_authorization_message(envelope, contract)
    envelope["mac_sha256"] = hmac.new(key, message, hashlib.sha256).hexdigest()
    view = {key: envelope[key] for key in module.EXECUTOR_AUTHORIZATION_FIELDS}
    return contract, envelope, view, key


def test_authority_verifier_accepts_only_exact_signed_executor_view():
    module = load_module()
    contract, envelope, view, key = authority_fixture(module)
    verifier = module.build_authority_verifier(envelope=envelope, key=key, contract=contract)
    assert verifier(view) is True
    changed = dict(view, output_directory=view["output_directory"] + "-changed")
    assert verifier(changed) is False


def test_authority_verifier_rejects_mac_key_and_envelope_drift():
    module = load_module()
    contract, envelope, view, key = authority_fixture(module)
    for mutation in (
        lambda row: row.update(mac_sha256="0" * 64),
        lambda row: row.update(subject="different-executor"),
        lambda row: row.update(extra="unsigned"),
    ):
        changed = copy.deepcopy(envelope)
        mutation(changed)
        with pytest.raises(ValueError, match="authorization envelope"):
            module.build_authority_verifier(envelope=changed, key=key, contract=contract)
    with pytest.raises(ValueError, match="key"):
        module.build_authority_verifier(envelope=envelope, key=b"short", contract=contract)


def model_fixture(tmp_path: Path):
    contract = json.loads(S608.read_text())
    snapshot = tmp_path / "snapshot"
    cpu = snapshot / "cpu_int4"
    cpu.mkdir(parents=True)
    inference = snapshot / "inference.py"
    inference.write_text("# synthetic inference\n")
    manifest = cpu / "manifest.json"
    manifest.write_text('{"synthetic":true}\n')
    files = []
    for index, original in enumerate(contract["model_bundle"]["files"]):
        path = cpu / Path(original["path"]).name
        path.write_bytes(f"model-{index}".encode())
        files.append({"path": f"cpu_int4/{path.name}", "size": path.stat().st_size,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    bundle = contract["model_bundle"]
    bundle.update(
        snapshot=str(snapshot), manifest_path=str(manifest),
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        inference_path=str(inference),
        inference_sha256=hashlib.sha256(inference.read_bytes()).hexdigest(), files=files,
    )
    bound = {key: contract[key] for key in (
        "evidence", "authority_proof", "model_bundle", "nonce_store",
        "receipt_schema", "blockers", "execution_authorized", "runtime_effects")}
    contract["contract_sha256"] = hashlib.sha256(json.dumps(
        bound, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()
    model = {"inference_path": str(inference), "model_path": str(cpu), "tts_dir": str(snapshot / "tts")}
    (snapshot / "tts").mkdir()
    return contract, model, cpu


def test_model_verifier_stream_hashes_exact_bound_bundle(tmp_path, monkeypatch):
    module = load_module()
    contract, model, _cpu = model_fixture(tmp_path)
    monkeypatch.setattr(module, "FIXED_TTS_DIR", Path(model["tts_dir"]))
    verifier = module.build_model_verifier(contract)
    assert verifier(model, contract) is True


def test_model_verifier_rejects_content_path_and_symlink_drift(tmp_path, monkeypatch):
    module = load_module()
    contract, model, cpu = model_fixture(tmp_path)
    monkeypatch.setattr(module, "FIXED_TTS_DIR", Path(model["tts_dir"]))
    verifier = module.build_model_verifier(contract)
    (cpu / "tok_encoder.onnx").write_bytes(b"tampered")
    assert verifier(model, contract) is False
    contract, model, cpu = model_fixture(tmp_path / "second")
    monkeypatch.setattr(module, "FIXED_TTS_DIR", Path(model["tts_dir"]))
    verifier = module.build_model_verifier(contract)
    assert verifier(dict(model, model_path=str(tmp_path)), contract) is False
    target = cpu / "tok_encoder.onnx"
    target.unlink()
    target.symlink_to(cpu / "tok_decoder.onnx")
    assert verifier(model, contract) is False


def test_real_tts_support_assets_are_fixed_outside_onnx_snapshot():
    module = load_module()
    contract = json.loads(S608.read_text())
    expected = Path("/4TNVMe2/aiot_weights/modelscope/models/Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/master")
    assert module.FIXED_TTS_DIR == expected
    assert module.FIXED_TTS_DIR.is_dir()
    assert module.FIXED_TTS_DIR != Path(contract["model_bundle"]["snapshot"]) / "tts"


def test_fixed_nonce_path_is_contract_bound_without_creation(tmp_path):
    module = load_module()
    contract = json.loads(S608.read_text())
    expected = Path("/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3")
    before = expected.lstat() if expected.exists() else None
    nonce = module.fixed_nonce_store_path(contract)
    assert nonce == expected
    after = expected.lstat() if expected.exists() else None
    assert (None if before is None else (before.st_ino, before.st_size, before.st_mtime_ns)) == (
        None if after is None else (after.st_ino, after.st_size, after.st_mtime_ns)
    )
    changed = copy.deepcopy(contract)
    changed["nonce_store"]["path"] = str(tmp_path / "caller.sqlite3")
    with pytest.raises(ValueError, match="contract"):
        module.fixed_nonce_store_path(changed)


def test_source_has_no_secret_loading_executor_import_or_runtime_effects():
    source = MODULE_PATH.read_text()
    assert "story_bounded_render_executor" not in source
    assert "open(key" not in source
    assert "os.environ" not in source
    assert "import sqlite3" not in source
    assert "onnxruntime" not in source
