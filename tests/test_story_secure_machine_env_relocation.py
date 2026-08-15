import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT = VOICE_SCENE / "s5zy_story_secure_machine_env_relocation_receipt.json"
SCHEMA = VOICE_SCENE / "story_secure_machine_env_relocation.schema.json"


def test_receipt_matches_secure_live_target() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    link = Path(receipt["installation"]["compatibility_path"])
    target = Path(receipt["installation"]["secure_target"])

    assert link.is_symlink()
    assert link.resolve() == target
    assert oct(target.parent.stat().st_mode & 0o777) == "0o700"
    assert oct(target.stat().st_mode & 0o777) == "0o600"
    assert hashlib.sha256(target.read_bytes()).hexdigest() == receipt["installation"]["content_sha256"]
    assert receipt["decision"]["security_blocker_closed"] is True
    assert receipt["decision"]["deployment_dry_run_admitted"] is True
    assert receipt["decision"]["deployment_authorized"] is False


def test_receipt_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(receipt)) == []
