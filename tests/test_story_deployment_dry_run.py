import hashlib
import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT = VOICE_SCENE / "s5zz_story_deployment_dry_run_receipt.json"
SCHEMA = VOICE_SCENE / "story_deployment_dry_run.schema.json"


def load_receipt() -> dict:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_receipt_validates_and_keeps_deployment_closed() -> None:
    receipt = load_receipt()
    jsonschema.validate(receipt, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert receipt["source"]["commit"] == receipt["source"]["origin_after_build"]
    assert receipt["installation"]["sha256_before"] == receipt["installation"]["sha256_after"]
    assert receipt["installation"]["size_bytes_before"] == receipt["installation"]["size_bytes_after"]
    assert receipt["installation"]["mtime_epoch_before"] == receipt["installation"]["mtime_epoch_after"]
    assert receipt["installation"]["inode_before"] == receipt["installation"]["inode_after"]
    assert receipt["decision"]["deployment_authorized"] is False


def test_candidate_and_installed_binary_evidence_is_hash_bound() -> None:
    receipt = load_receipt()
    assert len(receipt["candidate"]["sha256"]) == 64
    assert receipt["candidate"]["size_bytes"] > 0
    assert receipt["candidate"]["story_marker"] is True
    assert receipt["installation"]["sha256_before"] == receipt["installation"]["sha256_after"]


def test_adapter_is_already_matched_and_rollback_is_explicit() -> None:
    receipt = load_receipt()
    assert receipt["adapter"]["repository_sha256"] == receipt["adapter"]["installed_sha256"]
    assert receipt["adapter"]["already_matched"] is True
    assert receipt["rollback_plan"]["wrapper_left_untouched"] is True
    assert "<timestamp>" in receipt["rollback_plan"]["binary_backup_pattern"]
