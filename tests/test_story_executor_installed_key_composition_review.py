import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_executor_installed_key_composition_review.py"
SOURCE = ROOT / "scripts/story_executor_installed_key_composition.py"
TEST = ROOT / "tests/test_story_executor_installed_key_composition.py"
BASE = ROOT / "scripts/story_executor_secure_runtime_composition.py"
BINDING = ROOT / "scripts/story_executor_posix_runtime_binding.py"
S612 = ROOT / "docs/design/voice-scene/s612_story_executor_posix_runtime_binding_review.json"


def load_module():
    assert MODULE.exists(), "S613 review builder is missing"
    spec = importlib.util.spec_from_file_location("s613_review", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(module, **overrides):
    args = dict(composition_path=SOURCE, composition_test_path=TEST,
                base_composition_path=BASE, binding_path=BINDING,
                prior_review_path=S612)
    args.update(overrides)
    return module.build_review(**args)


def test_review_accepts_installed_key_only_public_composition():
    result = build(load_module())
    assert result["status"] == "story_executor_installed_key_composition_reviewable"
    assert result["decision"] == "installed_key_only_public_preparation_accepted_installation_blocked"
    assert all(result["boundaries"].values())
    assert result["installation_authorized"] is False
    assert result["execution_authorized"] is False
    assert not any(result["runtime_effects"].values())
    assert result["claims"]["caller_supplied_key_public_interface_absent"] is True
    assert result["blockers"] == ["secure_configuration_not_installed", "executor_invocation_not_authorized"]
    assert result["next_gate"] == "owner_authorized_story_executor_secure_configuration_installation"


def test_review_rejects_s612_drift(tmp_path):
    module = load_module()
    value = json.loads(S612.read_text())
    value["review_sha256"] = "0" * 64
    path = tmp_path / "s612.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="S612"):
        build(module, prior_review_path=path)


def test_review_rejects_public_key_parameter(tmp_path):
    module = load_module()
    path = tmp_path / "composition.py"
    path.write_text(SOURCE.read_text().replace(
        "request: dict[str, Any]", "request: dict[str, Any], key: bytes"))
    with pytest.raises(ValueError, match="public signature"):
        build(module, composition_path=path)


def test_review_rejects_missing_preload_envelope_validation(tmp_path):
    module = load_module()
    path = tmp_path / "composition.py"
    path.write_text(SOURCE.read_text().replace(
        "key_id = _validate_closed_envelope(envelope)",
        'key_id = envelope["key_id"]'))
    with pytest.raises(ValueError, match="boundary"):
        build(module, composition_path=path)
