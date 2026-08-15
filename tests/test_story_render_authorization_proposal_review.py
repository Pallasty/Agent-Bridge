import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_render_authorization_proposal_review.py"
PROPOSAL = ROOT / "scripts/story_render_authorization_proposal.py"
PROPOSAL_TEST = ROOT / "tests/test_story_render_authorization_proposal.py"
INSTALLATION_RESULT = (
    ROOT
    / "docs/design/voice-scene/"
    "s614_story_render_secure_configuration_installation_result.json"
)
SCHEMA = (
    ROOT
    / "docs/design/voice-scene/"
    "story_render_authorization_proposal_review.schema.json"
)
RECEIPT = (
    ROOT
    / "docs/design/voice-scene/"
    "s615_story_render_authorization_proposal_review.json"
)


def load_module():
    assert MODULE.exists(), "S615 proposal review builder is missing"
    spec = importlib.util.spec_from_file_location("s615_review", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(module, **overrides):
    values = {
        "proposal_path": PROPOSAL,
        "proposal_test_path": PROPOSAL_TEST,
        "installation_result_path": INSTALLATION_RESULT,
    }
    values.update(overrides)
    return module.build_review(**values)


def test_review_accepts_unsigned_proposal_and_keeps_signature_blocked():
    result = build(load_module())
    assert result["schema"] == (
        "agent_bridge.story_render_authorization_proposal_review.v1"
    )
    assert result["status"] == (
        "story_render_authorization_proposal_reviewable"
    )
    assert result["decision"] == (
        "unsigned_proposal_source_accepted_owner_signature_blocked"
    )
    assert all(result["boundaries"].values())
    assert result["boundaries"][
        "s614_installation_receipt_hash_pinned"
    ] is True
    assert result["implementation_present"] is True
    assert result["owner_signature_authorized"] is False
    assert result["execution_authorized"] is False
    assert not any(result["runtime_effects"].values())
    assert result["blockers"] == [
        "owner_authorized_envelope_signature_not_granted",
        "executor_invocation_not_authorized",
    ]
    assert result["next_gate"] == (
        "owner_authorized_story_render_envelope_signing_preflight"
    )


def test_review_rejects_installation_receipt_drift(tmp_path):
    module = load_module()
    value = json.loads(INSTALLATION_RESULT.read_text(encoding="utf-8"))
    value["execution_authorized"] = True
    path = tmp_path / "installation.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="S614"):
        build(module, installation_result_path=path)


def test_review_rejects_secret_loader_mac_or_executor_surface(tmp_path):
    module = load_module()
    path = tmp_path / "proposal.py"
    path.write_text(
        PROPOSAL.read_text(encoding="utf-8")
        + "\nload_installed_authority_key(); hmac.new(); execute_bounded_render()\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="boundary"):
        build(module, proposal_path=path)


def test_checked_in_review_is_exact_and_schema_valid():
    jsonschema = pytest.importorskip("jsonschema")
    module = load_module()
    expected = build(module)
    observed = json.loads(RECEIPT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert observed == expected
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(observed)) == []
