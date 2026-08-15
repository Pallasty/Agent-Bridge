import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_executor_posix_runtime_binding_review.py"
SOURCE = ROOT / "scripts/story_executor_posix_runtime_binding.py"
TEST = ROOT / "tests/test_story_executor_posix_runtime_binding.py"
S608 = ROOT / "docs/design/voice-scene/s608_story_executor_authority_model_nonce_contract.json"
S611 = ROOT / "docs/design/voice-scene/s611_story_executor_secure_runtime_configuration_contract.json"
VERIFIER = ROOT / "scripts/story_executor_runtime_verifiers.py"
COMPOSITION = ROOT / "scripts/story_executor_secure_runtime_composition.py"


def load_module():
    assert MODULE.exists(), "S612 binding review builder is missing"
    spec = importlib.util.spec_from_file_location("s612_review", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(module, **overrides):
    args = dict(binding_path=SOURCE, binding_test_path=TEST,
                s608_contract_path=S608, s611_contract_path=S611,
                verifier_path=VERIFIER, composition_path=COMPOSITION)
    args.update(overrides)
    return module.build_review(**args)


def test_review_accepts_posix_binding_and_fd_loader_without_installation():
    result = build(load_module())
    assert result["status"] == "story_executor_posix_runtime_binding_reviewable"
    assert result["decision"] == "posix_binding_and_fd_key_loader_accepted_installation_blocked"
    assert all(result["boundaries"].values())
    assert result["installation_authorized"] is False
    assert result["execution_authorized"] is False
    assert not any(result["runtime_effects"].values())
    assert result["claims"]["legacy_fuse_active_binding_removed"] is True
    assert result["blockers"] == ["secure_configuration_not_installed", "installed_key_not_composed_into_preparation", "executor_invocation_not_authorized"]
    assert result["next_gate"] == "story_executor_installed_key_composition_implementation_review"


def test_review_rejects_s611_digest_drift(tmp_path):
    module = load_module()
    value = json.loads(S611.read_text())
    value["contract_sha256"] = "0" * 64
    path = tmp_path / "s611.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="S611"):
        build(module, s611_contract_path=path)


def test_review_rejects_active_legacy_fuse_binding(tmp_path):
    module = load_module()
    path = tmp_path / "verifier.py"
    path.write_text(VERIFIER.read_text().replace(
        "/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3",
        "/Data/Models/agent-bridge/runtime/voice-scene/story-render-nonces.sqlite3"))
    with pytest.raises(ValueError, match="legacy FUSE"):
        build(module, verifier_path=path)
