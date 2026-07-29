from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "voice_scene_contract.py"
SCHEMA_PATH = ROOT / "docs" / "design" / "voice-scene" / "voice_scene.schema.json"
FIXTURE_DIR = ROOT / "docs" / "design" / "voice-scene" / "fixtures"


def load_contract_module():
    spec = importlib.util.spec_from_file_location("voice_scene_contract", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def minimal_scene() -> dict:
    return {
        "schema": "agent_bridge.voice_scene.v0",
        "scene": {
            "scene_id": "scene_story_demo",
            "mode": "story",
            "source_id": "source_story_demo",
            "canonical_branch_id": "branch_canonical",
        },
        "sources": [
            {
                "source_id": "source_story_demo",
                "kind": "novel",
                "uri": "fixture://story.txt",
                "sha256": "1" * 64,
                "version": "fixture-v1",
            }
        ],
        "speakers": [
            {
                "speaker_id": "character_lin",
                "kind": "character",
                "display_name": "林默",
                "aliases": ["林默"],
                "identity_status": "source_grounded",
            }
        ],
        "voice_profiles": [
            {
                "voice_profile_id": "voice_lin_v1",
                "speaker_id": "character_lin",
                "version": 1,
                "backend": "unassigned",
                "model": "unassigned",
                "voice": "unassigned",
                "language": "zh",
                "audition_status": "needs_review",
            }
        ],
        "branches": [
            {
                "branch_id": "branch_canonical",
                "kind": "canonical",
                "parent_branch_id": None,
                "fork_event_id": None,
            }
        ],
        "timeline": [
            {
                "event_id": "event_0001",
                "sequence": 1,
                "idempotency_key": "story-demo:1",
                "branch_id": "branch_canonical",
                "event_type": "utterance",
                "source_ref": {
                    "source_id": "source_story_demo",
                    "locator": "chapter=1;paragraph=1",
                },
                "utterance": {
                    "speaker_id": "character_lin",
                    "text": "夜色沉了下来。",
                    "language": "zh",
                    "origin": "source",
                },
            }
        ],
        "claims": [
            {
                "claim_id": "claim_0001",
                "kind": "source_truth",
                "text": "夜色沉了下来。",
                "branch_id": "branch_canonical",
                "evidence_refs": ["event_0001"],
                "derived_from_claim_ids": [],
                "confidence": 1.0,
                "counter_evidence_refs": [],
            }
        ],
        "runtime_boundary": {
            "emits_audio": False,
            "records_audio": False,
            "writes_memory": False,
            "writes_forum": False,
            "mutates_runtime": False,
            "downloads_models": False,
        },
    }


def test_deterministic_id_is_canonical_across_key_order() -> None:
    contract = load_contract_module()
    left = {"speaker": "林默", "source": {"chapter": 1, "paragraph": 2}}
    right = {"source": {"paragraph": 2, "chapter": 1}, "speaker": "林默"}

    assert contract.deterministic_id("event", left) == contract.deterministic_id(
        "event", right
    )


def test_source_fingerprint_binds_content_and_edition() -> None:
    contract = load_contract_module()

    first = contract.source_fingerprint("第一章".encode(), version="edition-a")
    repeated = contract.source_fingerprint("第一章".encode(), version="edition-a")

    assert first == repeated
    assert first != contract.source_fingerprint("第一章".encode(), version="edition-b")
    assert first != contract.source_fingerprint("第二章".encode(), version="edition-a")


def test_valid_scene_has_no_contract_errors() -> None:
    contract = load_contract_module()

    assert contract.validate_scene(minimal_scene()) == []


def test_timeline_rejects_non_contiguous_sequence_and_duplicate_idempotency() -> None:
    contract = load_contract_module()
    scene = minimal_scene()
    duplicate = copy.deepcopy(scene["timeline"][0])
    duplicate["event_id"] = "event_0002"
    duplicate["sequence"] = 3
    scene["timeline"].append(duplicate)

    errors = contract.validate_scene(scene)

    assert any("timeline_sequence_not_contiguous" in error for error in errors)
    assert any("duplicate_idempotency_key" in error for error in errors)


def test_source_truth_cannot_be_derived_from_inference() -> None:
    contract = load_contract_module()
    scene = minimal_scene()
    scene["claims"].insert(
        0,
        {
            "claim_id": "claim_inference",
            "kind": "inference",
            "text": "林默感到不安。",
            "branch_id": "branch_canonical",
            "evidence_refs": ["event_0001"],
            "derived_from_claim_ids": [],
            "confidence": 0.62,
            "counter_evidence_refs": [],
        },
    )
    scene["claims"][1]["derived_from_claim_ids"] = ["claim_inference"]

    errors = contract.validate_scene(scene)

    assert any("claim_kind_upgrade_forbidden" in error for error in errors)


def test_simulation_branch_cannot_write_back_to_canonical() -> None:
    contract = load_contract_module()
    scene = minimal_scene()
    scene["branches"].append(
        {
            "branch_id": "branch_what_if",
            "kind": "simulation",
            "parent_branch_id": "branch_canonical",
            "fork_event_id": "event_0001",
        }
    )
    scene["timeline"].append(
        {
            "event_id": "event_0002",
            "sequence": 2,
            "idempotency_key": "story-demo:2",
            "branch_id": "branch_what_if",
            "event_type": "memory_event",
            "target_branch_id": "branch_canonical",
            "memory_event": {
                "kind": "interaction",
                "subject_id": "character_lin",
                "summary": "听众改变了角色选择。",
            },
        }
    )

    errors = contract.validate_scene(scene)

    assert any("simulation_writeback_to_canonical_forbidden" in error for error in errors)


@pytest.mark.parametrize(
    "field",
    [
        "emits_audio",
        "records_audio",
        "writes_memory",
        "writes_forum",
        "mutates_runtime",
        "downloads_models",
    ],
)
def test_s0_runtime_boundary_fails_closed(field: str) -> None:
    contract = load_contract_module()
    scene = minimal_scene()
    scene["runtime_boundary"][field] = True

    errors = contract.validate_scene(scene)

    assert any(f"runtime_boundary_forbidden:{field}" in error for error in errors)


def test_schema_and_three_fixtures_validate() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    contract = load_contract_module()

    fixtures = sorted(FIXTURE_DIR.glob("*.json"))
    assert [path.stem for path in fixtures] == [
        "agent_theater",
        "meeting",
        "story",
    ]
    for fixture_path in fixtures:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        assert list(validator.iter_errors(fixture)) == []
        assert contract.validate_scene(fixture) == []


def test_plan_summary_is_read_only_and_bounded() -> None:
    contract = load_contract_module()
    scene = minimal_scene()

    summary = contract.plan_summary(scene)

    assert summary == {
        "schema": "agent_bridge.voice_scene.plan.v0",
        "status": "contract_ready_no_runtime",
        "scene_id": "scene_story_demo",
        "mode": "story",
        "source_count": 1,
        "speaker_count": 1,
        "branch_count": 1,
        "timeline_event_count": 1,
        "claim_counts": {
            "source_truth": 1,
            "observation": 0,
            "inference": 0,
            "simulation_branch": 0,
        },
        "runtime_effects_enabled": [],
    }
