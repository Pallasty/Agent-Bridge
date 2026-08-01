import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_executor_runtime_verifiers_review.py"
SOURCE = ROOT / "scripts/story_executor_runtime_verifiers.py"
TEST = ROOT / "tests/test_story_executor_runtime_verifiers.py"
CONTRACT = ROOT / "docs/design/voice-scene/s608_story_executor_authority_model_nonce_contract.json"


def load_module():
    assert MODULE.exists(), "S609 review builder is missing"
    spec = importlib.util.spec_from_file_location("s609_review", MODULE)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def build(module, **overrides):
    args = dict(verifier_path=SOURCE, verifier_test_path=TEST, contract_path=CONTRACT)
    args.update(overrides)
    return module.build_review(**args)


def test_review_accepts_verifiers_but_keeps_runtime_closed():
    result = build(load_module())
    assert result["status"] == "story_executor_runtime_verifiers_reviewable"
    assert result["decision"] == "verifier_source_accepted_runtime_configuration_blocked"
    assert result["implementation_present"] is True
    assert result["execution_authorized"] is False
    assert not any(result["runtime_effects"].values())
    assert all(result["boundaries"].values())
    assert result["blockers"] == [
        "secure_authority_key_not_installed",
        "nonce_store_parent_not_installed",
        "executor_composition_entrypoint_not_implemented",
    ]
    assert result["next_gate"] == "story_executor_secure_runtime_composition_implementation_review"


def test_review_rejects_contract_drift(tmp_path):
    module = load_module()
    value = json.loads(CONTRACT.read_text())
    value["next_gate"] = "drift"
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="S608"):
        build(module, contract_path=path)


def test_review_rejects_forbidden_executor_import(tmp_path):
    module = load_module()
    path = tmp_path / "verifiers.py"
    path.write_text(SOURCE.read_text() + "\nimport story_bounded_render_executor\n")
    with pytest.raises(ValueError, match="forbidden"):
        build(module, verifier_path=path)
