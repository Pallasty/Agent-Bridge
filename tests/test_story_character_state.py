from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_character_state.py"
SCHEMA_PATH = (
    ROOT / "docs" / "design" / "voice-scene" / "character_state.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location("story_character_state", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canon_events() -> list[dict]:
    return [
        {
            "event_id": "canon_001",
            "sequence": 1,
            "branch_id": "branch_canonical",
            "kind": "canon",
            "text": "林默走进旧车站。",
            "known_by": ["character_lin"],
            "source_ref": {
                "source_id": "source_story",
                "locator": "chapter=1;line=3",
                "digest": "1" * 64,
            },
        },
        {
            "event_id": "canon_002",
            "sequence": 2,
            "branch_id": "branch_canonical",
            "kind": "canon",
            "text": "钥匙藏在车站时钟下面。",
            "known_by": ["character_lin", "character_su"],
            "source_ref": {
                "source_id": "source_story",
                "locator": "chapter=1;line=5",
                "digest": "2" * 64,
            },
        },
        {
            "event_id": "canon_003",
            "sequence": 3,
            "branch_id": "branch_canonical",
            "kind": "canon",
            "text": "沈川是林默失散多年的父亲。",
            "known_by": ["character_su"],
            "source_ref": {
                "source_id": "source_story",
                "locator": "chapter=3;line=8",
                "digest": "3" * 64,
            },
        },
    ]


def test_append_only_ledgers_are_idempotent_and_detect_conflict(
    tmp_path: Path,
) -> None:
    state = load_module()
    ledgers = state.LedgerStore(tmp_path)
    event = canon_events()[0]

    assert ledgers.append("canon", event) == "appended"
    assert ledgers.append("canon", dict(event)) == "duplicate_noop"
    conflicting = dict(event)
    conflicting["text"] = "冲突文本"
    with pytest.raises(ValueError, match="event_id_conflict"):
        ledgers.append("canon", conflicting)

    rows = ledgers.read("canon")
    assert rows == [event]
    assert (tmp_path / "canon_ledger.jsonl").read_text().count("\n") == 1


def test_canon_ledger_rejects_simulation_branch(tmp_path: Path) -> None:
    state = load_module()
    ledgers = state.LedgerStore(tmp_path)
    event = dict(canon_events()[0])
    event["branch_id"] = "branch_what_if"

    with pytest.raises(ValueError, match="canon_branch_required"):
        ledgers.append("canon", event)


def test_character_knowledge_is_bounded_by_cursor_and_known_by() -> None:
    state = load_module()

    view = state.character_knowledge_view(
        canon_events(), character_id="character_lin", cursor_sequence=2
    )

    assert [row["event_id"] for row in view] == ["canon_001", "canon_002"]
    assert all(row["sequence"] <= 2 for row in view)
    assert "canon_003" not in {row["event_id"] for row in view}


def test_story_ask_returns_only_grounded_pre_cursor_evidence() -> None:
    state = load_module()

    answer = state.story_ask(
        canon_events(),
        character_id="character_lin",
        question="钥匙在哪里？",
        cursor_sequence=2,
    )

    assert answer["status"] == "grounded_answer"
    assert answer["answer"] == "钥匙藏在车站时钟下面。"
    assert answer["evidence_event_ids"] == ["canon_002"]
    assert answer["max_evidence_sequence"] == 2


def test_story_ask_fails_closed_for_future_or_unknown_information() -> None:
    state = load_module()

    answer = state.story_ask(
        canon_events(),
        character_id="character_lin",
        question="沈川是谁？",
        cursor_sequence=2,
    )

    assert answer == {
        "schema": "agent_bridge.story_ask_response.v1",
        "status": "insufficient_grounded_knowledge",
        "character_id": "character_lin",
        "cursor_sequence": 2,
        "answer": "以我目前知道的事情，还无法回答。",
        "evidence_event_ids": [],
        "max_evidence_sequence": None,
        "claim_kind": "observation",
    }


def test_spoiler_falsifier_rejects_future_fact_even_if_model_generated_it() -> None:
    state = load_module()

    result = state.spoiler_falsifier(
        "沈川是林默失散多年的父亲。",
        canon_events(),
        character_id="character_lin",
        cursor_sequence=2,
    )

    assert result["allowed"] is False
    assert result["violations"] == ["future_fact:canon_003"]
    assert result["safe_response"] == "以我目前知道的事情，还无法回答。"


def test_psychological_profile_remains_inference_with_counter_evidence() -> None:
    state = load_module()
    profile = state.psychological_profile(
        character_id="character_lin",
        cursor_sequence=2,
        hypothesis="林默可能对离开车站感到犹豫。",
        evidence_event_ids=["canon_001"],
        counter_evidence_event_ids=["canon_002"],
        confidence=0.62,
        state_delta={"caution": 0.2, "trust_su": 0.1},
        canon=canon_events(),
    )

    assert profile["claim_kind"] == "inference"
    assert profile["confidence"] == 0.62
    assert profile["counter_evidence_event_ids"] == ["canon_002"]
    assert state.validate_psychological_profile(profile) == []

    profile["claim_kind"] = "source_truth"
    assert state.validate_psychological_profile(profile) == [
        "psychological_profile_must_be_inference"
    ]


def test_simulation_interaction_cannot_mutate_canon(tmp_path: Path) -> None:
    state = load_module()
    ledgers = state.LedgerStore(tmp_path)
    interaction = {
        "event_id": "interaction_001",
        "sequence": 3,
        "branch_id": "branch_what_if",
        "kind": "interaction",
        "character_id": "character_lin",
        "text": "听众劝林默留下。",
        "target_branch_id": "branch_what_if",
        "idempotency_key": "session-a:interaction-1",
    }

    assert ledgers.append("interaction", interaction) == "appended"
    invalid = dict(interaction)
    invalid["event_id"] = "interaction_002"
    invalid["target_branch_id"] = "branch_canonical"
    with pytest.raises(ValueError, match="simulation_writeback_to_canon_forbidden"):
        ledgers.append("interaction", invalid)


def test_resume_rebuilds_cursor_state_and_interaction_history() -> None:
    state = load_module()
    memory_snapshot = state.memory_snapshot(
        session_id="session-a",
        scene_id="scene-story",
        cursor_sequence=2,
        canon=canon_events()[:2],
        knowledge_events=[],
        psychological_profiles=[],
    )
    event_log = [
        {
            "event_id": "interaction_001",
            "sequence": 3,
            "branch_id": "branch_what_if",
            "kind": "interaction",
            "character_id": "character_lin",
            "text": "听众劝林默留下。",
            "target_branch_id": "branch_what_if",
            "idempotency_key": "session-a:interaction-1",
        }
    ]

    resumed = state.resume_session(memory_snapshot, event_log)

    assert resumed["status"] == "character_interaction_text_grounded"
    assert resumed["cursor_sequence"] == 2
    assert resumed["canon_event_count"] == 2
    assert resumed["interaction_event_ids"] == ["interaction_001"]
    assert resumed["active_branch_id"] == "branch_what_if"


def test_snapshot_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    state = load_module()
    snapshot = state.memory_snapshot(
        session_id="session-a",
        scene_id="scene-story",
        cursor_sequence=2,
        canon=canon_events()[:2],
        knowledge_events=[],
        psychological_profiles=[],
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(snapshot)) == []


def test_story_ask_cli_is_read_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = load_module()
    snapshot = state.memory_snapshot(
        session_id="session-a",
        scene_id="scene-story",
        cursor_sequence=2,
        canon=canon_events()[:2],
        knowledge_events=[],
        psychological_profiles=[],
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False), encoding="utf-8"
    )

    exit_code = state.main(
        [
            "/story",
            "ask",
            "--snapshot",
            str(snapshot_path),
            "--character",
            "character_lin",
            "--question",
            "钥匙在哪里？",
        ]
    )

    response = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert response["status"] == "grounded_answer"
    assert response["evidence_event_ids"] == ["canon_002"]
    assert list(tmp_path.iterdir()) == [snapshot_path]
