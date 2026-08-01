import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_executor_secure_runtime_composition_review.py"
SOURCE = ROOT / "scripts/story_executor_secure_runtime_composition.py"
TEST = ROOT / "tests/test_story_executor_secure_runtime_composition.py"
S609 = ROOT / "docs/design/voice-scene/s609_story_executor_runtime_verifiers_review.json"


def load_module():
    assert MODULE.exists(), "S610 review builder is missing"
    spec = importlib.util.spec_from_file_location("s610_review", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(module, **overrides):
    values = dict(composition_path=SOURCE, composition_test_path=TEST, verifier_review_path=S609)
    values.update(overrides)
    return module.build_review(**values)


def test_review_accepts_preparation_composition_without_execution():
    result = build(load_module())
    assert result["status"] == "story_executor_secure_runtime_composition_reviewable"
    assert result["decision"] == "preparation_composition_accepted_invocation_blocked"
    assert all(result["boundaries"].values())
    assert result["execution_authorized"] is False
    assert not any(result["runtime_effects"].values())
    assert result["claims"]["external_tts_support_path_corrected"] is True
    assert result["blockers"] == ["secure_authority_key_not_installed", "nonce_store_parent_not_installed", "executor_invocation_not_authorized"]
    assert result["next_gate"] == "story_executor_secure_runtime_configuration_installation_contract"


def test_review_rejects_s609_drift(tmp_path):
    module = load_module()
    value = json.loads(S609.read_text())
    value["review_sha256"] = "0" * 64
    path = tmp_path / "s609.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="S609"):
        build(module, verifier_review_path=path)


def test_review_rejects_executor_invocation_surface(tmp_path):
    module = load_module()
    path = tmp_path / "composition.py"
    path.write_text(SOURCE.read_text() + "\nexecute_bounded_render()\n")
    with pytest.raises(ValueError, match="execution"):
        build(module, composition_path=path)
