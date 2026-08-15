import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_executor_secure_configuration_installer_review.py"
INSTALLER = ROOT / "scripts/story_executor_secure_configuration_installer.py"
INSTALLER_TEST = ROOT / "tests/test_story_executor_secure_configuration_installer.py"
S611 = ROOT / "docs/design/voice-scene/s611_story_executor_secure_runtime_configuration_contract.json"
S613 = ROOT / "docs/design/voice-scene/s613_story_executor_installed_key_composition_review.json"
RESULT_SCHEMA = ROOT / "docs/design/voice-scene/story_render_secure_configuration_installation_result.schema.json"


def load_module():
    assert MODULE.exists(), "S614 installer review builder is missing"
    spec = importlib.util.spec_from_file_location("s614_review", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(module, **overrides):
    values = dict(
        installer_path=INSTALLER,
        installer_test_path=INSTALLER_TEST,
        s611_contract_path=S611,
        s613_review_path=S613,
        result_schema_path=RESULT_SCHEMA,
    )
    values.update(overrides)
    return module.build_review(**values)


def test_review_accepts_installer_source_without_installation():
    result = build(load_module())
    assert result["status"] == "story_executor_secure_configuration_installer_reviewable"
    assert result["decision"] == "installer_source_accepted_installation_still_blocked"
    assert all(result["boundaries"].values())
    assert result["implementation_present"] is True
    assert result["installation_authorized"] is False
    assert result["execution_authorized"] is False
    assert not any(result["runtime_effects"].values())
    assert len(result["evidence"]["result_schema_sha256"]) == 64
    assert result["boundaries"]["installation_result_schema_bound"] is True
    assert result["boundaries"]["policy_json_parsed_from_hashed_bytes"] is True
    assert result["blockers"] == [
        "owner_authorized_secure_configuration_installation_not_granted",
        "executor_invocation_not_authorized",
    ]
    assert result["next_gate"] == (
        "owner_authorized_story_executor_secure_configuration_installation")


def test_review_rejects_s613_drift(tmp_path):
    module = load_module()
    value = json.loads(S613.read_text(encoding="utf-8"))
    value["review_sha256"] = "0" * 64
    path = tmp_path / "s613.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="S613"):
        build(module, s613_review_path=path)


def test_review_rejects_public_path_or_key_parameters(tmp_path):
    module = load_module()
    path = tmp_path / "installer.py"
    path.write_text(INSTALLER.read_text(encoding="utf-8").replace(
        "def install_story_render_secure_configuration()",
        "def install_story_render_secure_configuration(key: bytes, path: Path)"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="public signature"):
        build(module, installer_path=path)


def test_review_rejects_cli_or_executor_surface(tmp_path):
    module = load_module()
    path = tmp_path / "installer.py"
    path.write_text(
        INSTALLER.read_text(encoding="utf-8")
        + '\nif __name__ == "__main__":\n    execute_bounded_render()\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="boundary"):
        build(module, installer_path=path)
