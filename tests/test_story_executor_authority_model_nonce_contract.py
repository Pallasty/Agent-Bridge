import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/story_executor_authority_model_nonce_contract.py"
S607 = ROOT / "docs/design/voice-scene/s607_story_bounded_render_executor_source_review.json"
S5G = ROOT / "docs/design/voice-scene/s5g_modelscope_snapshot_static_audit.json"
SNAPSHOT = Path("/4TNVMe2/aiot_weights/modelscope/models/onnx-community--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/master")
NONCE = Path("/Data/Models/agent-bridge/runtime/voice-scene/story-render-nonces.sqlite3")


def _load():
    assert MODULE_PATH.exists(), "S608 contract builder is missing"
    spec = importlib.util.spec_from_file_location("s608", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build(module, **overrides):
    args = dict(
        source_review_path=S607,
        snapshot_audit_path=S5G,
        snapshot_path=SNAPSHOT,
        executor_path=ROOT / "scripts/story_bounded_render_executor.py",
        receipt_schema_path=ROOT / "docs/design/voice-scene/story_bounded_render_receipt.schema.json",
        nonce_store_path=NONCE,
    )
    args.update(overrides)
    return module.build_contract(**args)


def test_contract_binds_authority_model_nonce_and_receipt_without_actuation():
    result = _build(_load())
    assert result["status"] == "story_executor_authority_model_nonce_contract_reviewable"
    assert result["decision"] == "static_contract_complete_runtime_configuration_uninstalled"
    assert result["execution_authorized"] is False
    assert not any(result["runtime_effects"].values())
    authority = result["authority_proof"]
    assert authority["algorithm"] == "hmac-sha256"
    assert authority["domain_separator"] == "agent-bridge.story-render-authorization.v1"
    assert authority["maximum_ttl_seconds"] == 600
    assert authority["secret_material_in_envelope"] is False
    assert authority["key_custody"] == "external_secure_runtime_configuration"
    assert authority["canonicalization"] == "utf8-jcs-rfc8785"

    bundle = result["model_bundle"]
    assert bundle["variant"] == "cpu_int4"
    assert bundle["execution_provider"] == "CPUExecutionProvider"
    assert len(bundle["files"]) == 7
    assert all(len(row["sha256"]) == 64 and row["size"] > 0 for row in bundle["files"])
    assert bundle["large_files_rehashed_now"] is False
    assert bundle["large_files_size_checked_now"] is True

    nonce = result["nonce_store"]
    assert nonce["path"] == str(NONCE)
    assert nonce["parent_mode"] == "0700"
    assert nonce["database_mode"] == "0600"
    assert nonce["caller_configurable"] is False
    assert nonce["installed_now"] is False

    assert result["receipt_schema"]["schema_id"] == "agent_bridge.story_bounded_render_receipt.v1"
    assert result["next_gate"] == "story_executor_authority_model_nonce_verifier_implementation_review"


def test_contract_rejects_s607_digest_drift(tmp_path):
    module = _load()
    value = json.loads(S607.read_text())
    value["decision"] = "drifted"
    path = tmp_path / "s607.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="S607"):
        _build(module, source_review_path=path)


def test_contract_rejects_incomplete_cpu_int4_audit(tmp_path):
    module = _load()
    value = json.loads(S5G.read_text())
    hashes = value["integrity"]["file_hashes"]
    value["integrity"]["file_hashes"] = [r for r in hashes if r["path"] != "cpu_int4/tok_encoder.onnx"]
    path = tmp_path / "s5g.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="CPU INT4 audit"):
        _build(module, snapshot_audit_path=path)


def test_contract_rejects_manifest_submodel_drift(tmp_path):
    module = _load()
    snapshot = tmp_path / "snapshot"
    cpu = snapshot / "cpu_int4"
    cpu.mkdir(parents=True)
    real_manifest = json.loads((SNAPSHOT / "cpu_int4/manifest.json").read_text())
    real_manifest["sub_models"].pop("tok_encoder")
    (cpu / "manifest.json").write_text(json.dumps(real_manifest))
    for name in module.EXPECTED_MODEL_FILES:
        (cpu / name).touch()
    (snapshot / "inference.py").write_bytes((SNAPSHOT / "inference.py").read_bytes())
    audit = json.loads(S5G.read_text())
    audit["snapshot"] = str(snapshot)
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="manifest"):
        _build(module, snapshot_path=snapshot, snapshot_audit_path=audit_path)


def test_nonce_store_must_be_absolute_and_outside_render_output():
    module = _load()
    with pytest.raises(ValueError, match="nonce store"):
        _build(module, nonce_store_path=Path("relative.sqlite3"))
    with pytest.raises(ValueError, match="nonce store"):
        _build(module, nonce_store_path=Path("/Data/Models/agent-bridge/evidence/story-render/nonces.sqlite3"))
