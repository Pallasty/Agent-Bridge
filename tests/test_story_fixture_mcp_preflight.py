import hashlib
import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
VOICE_SCENE = ROOT / "docs" / "design" / "voice-scene"
RECEIPT = VOICE_SCENE / "s602_story_fixture_mcp_preflight_receipt.json"
SCHEMA = VOICE_SCENE / "story_fixture_mcp_preflight.schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_receipt() -> dict:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_receipt_validates_and_execution_stays_unauthorized() -> None:
    receipt = load_receipt()
    jsonschema.validate(receipt, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert receipt["result"]["execution_authorized"] is False
    assert receipt["request"]["dry_run"] is True
    assert all(value is False for key, value in receipt["runtime_effects"].items() if key != "persistent_mcp_processes_after")


def test_source_and_evidence_files_match_bound_hashes() -> None:
    receipt = load_receipt()
    assert sha256(Path(receipt["request"]["source_path"])) == receipt["request"]["source_sha256"]
    expected = {
        "voice_plan_file_sha256": VOICE_SCENE / "s5zc_source_grounded_utterance_plan_receipt.json",
        "mapping_file_sha256": VOICE_SCENE / "s5x_story_voice_mapping_receipt.json",
        "role_acceptance_file_sha256": VOICE_SCENE / "s5y_character_voice_audition_receipt.json",
        "continuity_file_sha256": VOICE_SCENE / "s5ze_cross_chapter_continuity_receipt.json",
    }
    for field, path in expected.items():
        assert sha256(path) == receipt["evidence"][field]


def test_render_plan_is_bounded_and_cache_keys_are_distinct() -> None:
    receipt = load_receipt()
    assert receipt["selection"]["selected_segments"] == 3
    assert len(receipt["render_plan"]["speakers"]) == 3
    assert len(set(receipt["render_plan"]["cache_keys"])) == 3
