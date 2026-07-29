#!/usr/bin/env python3
"""S3 text-first character knowledge, ledger, spoiler, and resume contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Sequence


SNAPSHOT_SCHEMA = "agent_bridge.character_state_snapshot.v1"
ASK_SCHEMA = "agent_bridge.story_ask_response.v1"
LEDGER_FILES = {
    "canon": "canon_ledger.jsonl",
    "knowledge": "character_knowledge_ledger.jsonl",
    "interaction": "interaction_ledger.jsonl",
}
SAFE_UNKNOWN_RESPONSE = "以我目前知道的事情，还无法回答。"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def deterministic_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


class LedgerStore:
    """Three append-only JSONL ledgers with content-idempotent event IDs."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, ledger: str) -> Path:
        try:
            filename = LEDGER_FILES[ledger]
        except KeyError as error:
            raise ValueError(f"unknown_ledger:{ledger}") from error
        return self.root / filename

    def read(self, ledger: str) -> list[dict[str, Any]]:
        path = self._path(ledger)
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line_number, raw in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"ledger_json_invalid:{ledger}:{line_number}"
                ) from error
            if not isinstance(row, dict):
                raise ValueError(f"ledger_row_invalid:{ledger}:{line_number}")
            rows.append(row)
        return rows

    @staticmethod
    def _validate_append(ledger: str, event: dict[str, Any]) -> None:
        if not isinstance(event.get("event_id"), str):
            raise ValueError("event_id_required")
        if ledger == "canon":
            if event.get("kind") != "canon":
                raise ValueError("canon_kind_required")
            if event.get("branch_id") != "branch_canonical":
                raise ValueError("canon_branch_required")
            source_ref = event.get("source_ref")
            if not isinstance(source_ref, dict) or not source_ref.get("digest"):
                raise ValueError("canon_source_ref_required")
        elif ledger == "knowledge":
            if event.get("kind") != "character_knowledge":
                raise ValueError("character_knowledge_kind_required")
        elif ledger == "interaction":
            if event.get("kind") != "interaction":
                raise ValueError("interaction_kind_required")
            if (
                event.get("branch_id") != "branch_canonical"
                and event.get("target_branch_id") == "branch_canonical"
            ):
                raise ValueError("simulation_writeback_to_canon_forbidden")

    def append(self, ledger: str, event: dict[str, Any]) -> str:
        """Append once; identical replay is a no-op and conflicting IDs fail."""

        self._path(ledger)
        self._validate_append(ledger, event)
        for existing in self.read(ledger):
            if existing.get("event_id") != event["event_id"]:
                continue
            if canonical_json(existing) == canonical_json(event):
                return "duplicate_noop"
            raise ValueError(f"event_id_conflict:{event['event_id']}")
        path = self._path(ledger)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as target:
            target.write(canonical_json(event) + "\n")
            target.flush()
            os.fsync(target.fileno())
        return "appended"


def character_knowledge_view(
    canon: list[dict[str, Any]],
    *,
    character_id: str,
    cursor_sequence: int,
) -> list[dict[str, Any]]:
    """Project only facts already reached and explicitly knowable by a character."""

    return sorted(
        [
            event
            for event in canon
            if event.get("branch_id") == "branch_canonical"
            and isinstance(event.get("sequence"), int)
            and event["sequence"] <= cursor_sequence
            and character_id in event.get("known_by", [])
        ],
        key=lambda event: (event["sequence"], event["event_id"]),
    )


def _query_terms(text: str) -> set[str]:
    cleaned = re.sub(r"[\s，。！？、：；,.!?:;“”\"'（）()]", "", text)
    for stop in ("在哪里", "哪里", "是谁", "什么", "怎么", "为何", "为什么", "是否"):
        cleaned = cleaned.replace(stop, "")
    terms = set(cleaned)
    terms.update(cleaned[index : index + 2] for index in range(len(cleaned) - 1))
    return {term for term in terms if term}


def story_ask(
    canon: list[dict[str, Any]],
    *,
    character_id: str,
    question: str,
    cursor_sequence: int,
) -> dict[str, Any]:
    """Return a deterministic evidence extract, never an ungrounded completion."""

    visible = character_knowledge_view(
        canon, character_id=character_id, cursor_sequence=cursor_sequence
    )
    query_terms = _query_terms(question)
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for event in visible:
        overlap = len(query_terms & _query_terms(str(event.get("text", ""))))
        if overlap:
            ranked.append((overlap, -event["sequence"], event))
    if not ranked:
        return {
            "schema": ASK_SCHEMA,
            "status": "insufficient_grounded_knowledge",
            "character_id": character_id,
            "cursor_sequence": cursor_sequence,
            "answer": SAFE_UNKNOWN_RESPONSE,
            "evidence_event_ids": [],
            "max_evidence_sequence": None,
            "claim_kind": "observation",
        }
    selected = max(ranked, key=lambda row: (row[0], row[1]))[2]
    return {
        "schema": ASK_SCHEMA,
        "status": "grounded_answer",
        "character_id": character_id,
        "cursor_sequence": cursor_sequence,
        "answer": selected["text"],
        "evidence_event_ids": [selected["event_id"]],
        "max_evidence_sequence": selected["sequence"],
        "claim_kind": "source_truth",
    }


def spoiler_falsifier(
    candidate_response: str,
    canon: list[dict[str, Any]],
    *,
    character_id: str,
    cursor_sequence: int,
) -> dict[str, Any]:
    """Reject verbatim future/unknowable canon facts from a candidate response."""

    visible_ids = {
        event["event_id"]
        for event in character_knowledge_view(
            canon,
            character_id=character_id,
            cursor_sequence=cursor_sequence,
        )
    }
    violations: list[str] = []
    for event in canon:
        text = str(event.get("text", "")).strip()
        if (
            event.get("event_id") not in visible_ids
            and text
            and text in candidate_response
        ):
            violations.append(f"future_fact:{event['event_id']}")
    return {
        "allowed": not violations,
        "violations": sorted(violations),
        "safe_response": candidate_response
        if not violations
        else SAFE_UNKNOWN_RESPONSE,
    }


def psychological_profile(
    *,
    character_id: str,
    cursor_sequence: int,
    hypothesis: str,
    evidence_event_ids: list[str],
    counter_evidence_event_ids: list[str],
    confidence: float,
    state_delta: dict[str, float],
    canon: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create an explicitly inferential psychological state projection."""

    event_by_id = {event["event_id"]: event for event in canon}
    referenced = evidence_event_ids + counter_evidence_event_ids
    for event_id in referenced:
        event = event_by_id.get(event_id)
        if event is None:
            raise ValueError(f"profile_evidence_unknown:{event_id}")
        if event["sequence"] > cursor_sequence:
            raise ValueError(f"profile_future_evidence_forbidden:{event_id}")
    profile = {
        "profile_id": deterministic_id(
            "psych",
            {
                "character_id": character_id,
                "cursor_sequence": cursor_sequence,
                "hypothesis": hypothesis,
                "evidence": evidence_event_ids,
                "counter_evidence": counter_evidence_event_ids,
            },
        ),
        "character_id": character_id,
        "cursor_sequence": cursor_sequence,
        "hypothesis": hypothesis,
        "claim_kind": "inference",
        "evidence_event_ids": evidence_event_ids,
        "counter_evidence_event_ids": counter_evidence_event_ids,
        "confidence": confidence,
        "state_delta": state_delta,
    }
    errors = validate_psychological_profile(profile)
    if errors:
        raise ValueError(";".join(errors))
    return profile


def validate_psychological_profile(profile: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(profile, dict):
        return ["psychological_profile_must_be_object"]
    if profile.get("claim_kind") != "inference":
        errors.append("psychological_profile_must_be_inference")
    confidence = profile.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        errors.append("psychological_profile_confidence_invalid")
    if not isinstance(profile.get("evidence_event_ids"), list):
        errors.append("psychological_profile_evidence_invalid")
    if not isinstance(profile.get("counter_evidence_event_ids"), list):
        errors.append("psychological_profile_counter_evidence_invalid")
    if not isinstance(profile.get("state_delta"), dict):
        errors.append("psychological_profile_state_delta_invalid")
    return sorted(errors)


def memory_snapshot(
    *,
    session_id: str,
    scene_id: str,
    cursor_sequence: int,
    canon: list[dict[str, Any]],
    knowledge_events: list[dict[str, Any]],
    psychological_profiles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic AB-memory-compatible state snapshot payload."""

    bounded_canon = [
        event for event in canon if event.get("sequence", 0) <= cursor_sequence
    ]
    return {
        "schema": SNAPSHOT_SCHEMA,
        "status": "character_interaction_text_grounded",
        "session_id": session_id,
        "scene_id": scene_id,
        "cursor_sequence": cursor_sequence,
        "active_branch_id": "branch_canonical",
        "canon_ledger": bounded_canon,
        "character_knowledge_ledger": knowledge_events,
        "psychological_profiles": psychological_profiles,
        "snapshot_digest": deterministic_id(
            "snapshot",
            {
                "session_id": session_id,
                "scene_id": scene_id,
                "cursor_sequence": cursor_sequence,
                "canon": bounded_canon,
                "knowledge": knowledge_events,
                "profiles": psychological_profiles,
            },
        ),
        "write_posture": "proposal_only_owner_review_required",
    }


def resume_session(
    memory: dict[str, Any],
    event_log: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rebuild current branch and interaction history from snapshot plus log."""

    if memory.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError("character_state_snapshot_schema_invalid")
    unique: dict[str, dict[str, Any]] = {}
    for event in event_log:
        event_id = event.get("event_id")
        if not isinstance(event_id, str):
            raise ValueError("resume_event_id_required")
        prior = unique.get(event_id)
        if prior is not None and canonical_json(prior) != canonical_json(event):
            raise ValueError(f"resume_event_id_conflict:{event_id}")
        unique[event_id] = event
    interactions = sorted(
        [
            event
            for event in unique.values()
            if event.get("kind") == "interaction"
        ],
        key=lambda event: (event.get("sequence", 0), event["event_id"]),
    )
    active_branch = (
        interactions[-1]["branch_id"]
        if interactions
        else memory.get("active_branch_id", "branch_canonical")
    )
    return {
        "schema": "agent_bridge.character_session_resume.v1",
        "status": "character_interaction_text_grounded",
        "session_id": memory["session_id"],
        "scene_id": memory["scene_id"],
        "cursor_sequence": memory["cursor_sequence"],
        "canon_event_count": len(memory.get("canon_ledger", [])),
        "knowledge_event_count": len(
            memory.get("character_knowledge_ledger", [])
        ),
        "psychological_profile_count": len(
            memory.get("psychological_profiles", [])
        ),
        "interaction_event_ids": [event["event_id"] for event in interactions],
        "active_branch_id": active_branch,
        "write_posture": "proposal_only_owner_review_required",
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the read-only `/story ask` text contract against one snapshot."""

    parser = argparse.ArgumentParser(
        description="S3 text-only grounded character query"
    )
    parser.add_argument("story_command", choices=("/story",))
    parser.add_argument("operation", choices=("ask",))
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--character", required=True)
    parser.add_argument("--question", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        if snapshot.get("schema") != SNAPSHOT_SCHEMA:
            raise ValueError("character_state_snapshot_schema_invalid")
        response = story_ask(
            snapshot.get("canon_ledger", []),
            character_id=args.character,
            question=args.question,
            cursor_sequence=snapshot["cursor_sequence"],
        )
        exit_code = 0
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as error:
        response = {
            "schema": ASK_SCHEMA,
            "status": "invalid",
            "errors": [str(error)],
        }
        exit_code = 1
    print(
        json.dumps(
            response,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
