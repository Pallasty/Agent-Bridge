import hashlib
import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT = VOICE_SCENE / "s600_story_guarded_deployment_receipt.json"
SCHEMA = VOICE_SCENE / "story_guarded_deployment.schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_receipt() -> dict:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_receipt_validates_and_runtime_adoption_stays_closed() -> None:
    receipt = load_receipt()
    jsonschema.validate(receipt, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert receipt["binary"]["sha256"] == receipt["binary"]["candidate_sha256"]
    assert receipt["source"]["commit"] == receipt["source"]["origin_after_build"]
    assert receipt["adoption"]["runtime_adopted"] is False
    assert receipt["decision"]["reconnect_authorized"] is False


def test_installed_binary_and_backups_match_receipt() -> None:
    receipt = load_receipt()
    binary = Path(receipt["binary"]["path"])
    binary_backup = Path(receipt["backups"]["binary_path"])
    adapter_backup = Path(receipt["backups"]["adapter_path"])
    assert sha256(binary) == receipt["binary"]["sha256"]
    assert binary.stat().st_size == receipt["binary"]["size_bytes"]
    assert sha256(binary_backup) == receipt["backups"]["binary_sha256"]
    assert sha256(adapter_backup) == receipt["backups"]["adapter_sha256"]


def test_wrapper_unchanged_and_adapter_matched() -> None:
    receipt = load_receipt()
    assert receipt["wrapper"]["sha256_before"] == receipt["wrapper"]["sha256_after"]
    assert sha256(Path(receipt["wrapper"]["path"])) == receipt["wrapper"]["sha256_after"]
    assert receipt["adapter"]["repository_sha256"] == receipt["adapter"]["installed_sha256"]
