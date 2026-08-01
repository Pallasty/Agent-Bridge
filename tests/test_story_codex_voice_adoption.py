import hashlib
import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT = VOICE_SCENE / "s601_story_codex_voice_adoption_receipt.json"
SCHEMA = VOICE_SCENE / "story_codex_voice_adoption.schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_receipt() -> dict:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_receipt_validates_and_restart_stays_pending() -> None:
    receipt = load_receipt()
    jsonschema.validate(receipt, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert receipt["binary"]["sha256"] == receipt["binary"]["candidate_sha256"]
    assert receipt["manifest_probe"]["tool_count_after"] == receipt["manifest_probe"]["tool_count_before"] + 1
    assert receipt["adoption"]["current_client_runtime_adopted"] is False
    assert receipt["adoption"]["current_client_restart_required"] is True


def test_installed_binary_and_backups_match_receipt() -> None:
    receipt = load_receipt()
    assert sha256(Path(receipt["binary"]["path"])) == receipt["binary"]["sha256"]
    assert sha256(Path(receipt["backups"]["binary_path"])) == receipt["backups"]["binary_sha256"]
    assert sha256(Path(receipt["backups"]["adapter_path"])) == receipt["backups"]["adapter_sha256"]


def test_policy_is_narrow_and_runtime_effects_are_bounded() -> None:
    receipt = load_receipt()
    assert receipt["policy"]["added_extras"] == ["story_command_preflight"]
    assert receipt["policy"]["unrelated_niche_tools_added"] == 0
    assert receipt["runtime_effects"]["restarted_mcp"] is False
    assert receipt["runtime_effects"]["called_story_tool"] is False
