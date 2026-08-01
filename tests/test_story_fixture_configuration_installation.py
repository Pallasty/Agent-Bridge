import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT = VOICE_SCENE / "s5zx_story_fixture_configuration_installation_receipt.json"
SCHEMA = VOICE_SCENE / "story_fixture_configuration_installation.schema.json"


def test_receipt_matches_installed_configuration_and_security_blocker() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    installed = Path(receipt["installation"]["machine_env_path"])

    assert hashlib.sha256(installed.read_bytes()).hexdigest() == receipt["installation"]["machine_env_sha256"]
    assert receipt["installation"]["story_keys"] == 12
    assert receipt["probe"]["standard_profile_story_visible"] is False
    assert receipt["probe"]["all_profile_story_visible"] is True
    assert receipt["decision"]["configuration_installed"] is True
    assert receipt["decision"]["runtime_adoption_admitted"] is False
    assert receipt["blockers"] == ["machine_env_permissions_not_enforceable_on_fuseblk"]


def test_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
