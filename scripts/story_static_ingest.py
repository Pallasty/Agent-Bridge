#!/usr/bin/env python3
"""Deterministic, non-actuating `/story` static ingest for Voice Scene S1."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Sequence


STORY_PLAN_SCHEMA = "agent_bridge.story_plan.v1"
SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown"}
RUNTIME_OPTIONS = {
    "--play",
    "--emit-voice",
    "--record",
    "--download-model",
    "--write-memory",
}
RUNTIME_BOUNDARY = {
    "emits_audio": False,
    "records_audio": False,
    "writes_memory": False,
    "writes_forum": False,
    "mutates_runtime": False,
    "downloads_models": False,
}
CHAPTER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(第([0-9零〇一二三四五六七八九十百千]+)[章节回卷]\s*.*)$"
)
MARKDOWN_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")
ALIAS_RE = re.compile(
    r"([\u4e00-\u9fff]{2,8})[（(](?:又名|别名|亦称)[:：]?([\u4e00-\u9fff]{2,8})[）)]"
)
DIRECTED_SPEECH_RE = re.compile(
    r"([\u4e00-\u9fff]{2,6})对([\u4e00-\u9fff]{2,6})"
    r"(?:说|说道|问|答道|回答|喊道|低声说)"
)
SPEECH_RE = re.compile(
    r"([\u4e00-\u9fff]{2,6})(?:说|说道|问|答道|回答|喊道|低声说)"
)
RELATION_RE = re.compile(
    r"([\u4e00-\u9fff]{2,8})是([\u4e00-\u9fff]{2,8})的"
    r"(朋友|同伴|老师|师父|学生|徒弟|父亲|母亲|哥哥|姐姐|弟弟|妹妹|上司|下属)"
)
ACTION_MARKERS = (
    "走进",
    "走出",
    "打开",
    "关闭",
    "离开",
    "到达",
    "拿起",
    "放下",
    "看见",
    "听见",
    "发现",
    "决定",
)
EMOTION_MARKERS = ("害怕", "不安", "愤怒", "悲伤", "高兴", "惊讶", "紧张")


def canonical_json(value: Any) -> str:
    """Return stable JSON used by all S1 content-derived identifiers."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def deterministic_id(prefix: str, value: Any) -> str:
    """Return a bounded identifier derived only from canonical input."""

    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def sha256_bytes(content: bytes) -> str:
    """Return the SHA-256 fingerprint of exact source bytes."""

    return hashlib.sha256(content).hexdigest()


def _parse_start(tokens: list[str]) -> dict[str, Any]:
    if tokens == ["from-start"]:
        return {"kind": "from_start"}
    if len(tokens) == 2 and tokens[0] == "chapter":
        try:
            chapter = int(tokens[1])
        except ValueError as error:
            raise ValueError("story_chapter_must_be_positive_integer") from error
        if chapter < 1:
            raise ValueError("story_chapter_must_be_positive_integer")
        return {"kind": "chapter", "chapter": chapter}
    raise ValueError("story_start_selector_invalid")


def parse_story_command(command: str | Sequence[str]) -> dict[str, Any]:
    """Parse the S1 dry-run `/story PATH from-start|chapter N` contract."""

    tokens = shlex.split(command) if isinstance(command, str) else list(command)
    pretty = False
    if "--pretty" in tokens:
        tokens.remove("--pretty")
        pretty = True
    del pretty
    forbidden = sorted(set(tokens) & RUNTIME_OPTIONS)
    if forbidden:
        raise ValueError(f"runtime_option_forbidden:{forbidden[0]}")
    if len(tokens) < 3 or tokens[0] != "/story":
        raise ValueError("story_command_invalid")
    path = tokens[1]
    suffix = Path(path).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported_story_source:{suffix or '<none>'}")
    return {
        "path": path,
        "start": _parse_start(tokens[2:]),
        "dry_run": True,
    }


def _chinese_number(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000}
    total = 0
    current = 0
    for character in value:
        if character in digits:
            current = digits[character]
        elif character in units:
            total += (current or 1) * units[character]
            current = 0
        else:
            return None
    return total + current


def _line_records(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        records.append(
            {
                "number": number,
                "text": line.rstrip("\r\n"),
                "char_start": offset,
                "char_end": offset + len(line),
            }
        )
        offset += len(line)
    if not records and text == "":
        return []
    if text and not text.endswith(("\n", "\r")):
        records[-1]["char_end"] = len(text)
    return records


def _chapter_heading(line: str) -> tuple[str, int | None] | None:
    match = CHAPTER_RE.match(line)
    if match:
        return match.group(1).strip(), _chinese_number(match.group(2))
    match = MARKDOWN_HEADING_RE.match(line)
    if match:
        return match.group(1).strip(), None
    return None


def index_chapters(text: str, source_id: str) -> list[dict[str, Any]]:
    """Index chapter boundaries with exact line and character spans."""

    records = _line_records(text)
    if not records:
        raise ValueError("story_source_empty")
    starts: list[tuple[int, str, int | None]] = []
    for index, record in enumerate(records):
        heading = _chapter_heading(record["text"])
        if heading:
            starts.append((index, heading[0], heading[1]))
    if not starts:
        starts = [(0, "全文", 1)]
    elif starts[0][0] > 0 and any(
        record["text"].strip() for record in records[: starts[0][0]]
    ):
        starts.insert(0, (0, "前言", 0))

    chapters: list[dict[str, Any]] = []
    used_ordinals: set[int] = set()
    next_ordinal = 1
    for chapter_index, (start_index, title, parsed_ordinal) in enumerate(starts):
        end_index = (
            starts[chapter_index + 1][0]
            if chapter_index + 1 < len(starts)
            else len(records)
        )
        ordinal = parsed_ordinal
        if ordinal is None or ordinal in used_ordinals:
            while next_ordinal in used_ordinals:
                next_ordinal += 1
            ordinal = next_ordinal
        used_ordinals.add(ordinal)
        next_ordinal = max(next_ordinal, ordinal + 1)
        last = records[end_index - 1]
        chapters.append(
            {
                "chapter_id": deterministic_id(
                    "chapter", {"source_id": source_id, "ordinal": ordinal, "title": title}
                ),
                "ordinal": ordinal,
                "title": title,
                "selected": False,
                "source_span": {
                    "source_id": source_id,
                    "line_start": records[start_index]["number"],
                    "line_end": last["number"],
                    "char_start": records[start_index]["char_start"],
                    "char_end": last["char_end"],
                },
                "_record_start": start_index,
                "_record_end": end_index,
            }
        )
    return chapters


def _candidate_names(text: str) -> tuple[list[str], dict[str, list[str]]]:
    aliases: dict[str, list[str]] = {}
    ordered: list[str] = []

    def add(name: str) -> None:
        if name not in ordered:
            ordered.append(name)

    for canonical, alias in ALIAS_RE.findall(text):
        add(canonical)
        aliases.setdefault(canonical, [canonical])
        if alias not in aliases[canonical]:
            aliases[canonical].append(alias)
    for subject, target in DIRECTED_SPEECH_RE.findall(text):
        add(subject)
        add(target)
    for speaker in SPEECH_RE.findall(text):
        if "对" not in speaker:
            add(speaker)
    for subject, target, _predicate in RELATION_RE.findall(text):
        add(subject)
        add(target)
    return ordered, aliases


def _cast_registry(text: str, source_sha256: str) -> list[dict[str, Any]]:
    names, alias_map = _candidate_names(text)
    rows: list[dict[str, Any]] = []
    for display_name, kind, status in [
        ("旁白", "narrator", "source_grounded"),
        *((name, "character", "needs_review") for name in names),
    ]:
        speaker_id = deterministic_id(
            "speaker", {"source_sha256": source_sha256, "name": display_name}
        )
        rows.append(
            {
                "speaker_id": speaker_id,
                "kind": kind,
                "display_name": display_name,
                "aliases": alias_map.get(display_name, [display_name]),
                "identity_status": status,
                "voice_profile": {
                    "voice_profile_id": deterministic_id(
                        "voice", {"speaker_id": speaker_id, "version": 1}
                    ),
                    "speaker_id": speaker_id,
                    "version": 1,
                    "backend": "unassigned",
                    "model": "unassigned",
                    "voice": "unassigned",
                    "language": "zh",
                    "audition_status": "needs_review",
                },
            }
        )
    return rows


def _source_ref(
    source_id: str, line_number: int, char_start: int, char_end: int
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "line_start": line_number,
        "line_end": line_number,
        "char_start": char_start,
        "char_end": char_end,
    }


def _extract_relationships(
    records: list[dict[str, Any]], source_id: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        for subject, target, predicate in RELATION_RE.findall(record["text"]):
            rows.append(
                {
                    "relation_id": deterministic_id(
                        "relation",
                        {
                            "source_id": source_id,
                            "line": record["number"],
                            "subject": subject,
                            "predicate": predicate,
                            "object": target,
                        },
                    ),
                    "subject": subject,
                    "predicate": predicate,
                    "object": target,
                    "confidence": 0.8,
                    "status": "needs_review",
                    "source_span": _source_ref(
                        source_id,
                        record["number"],
                        record["char_start"],
                        record["char_end"],
                    ),
                }
            )
    return rows


def _extract_events(
    records: list[dict[str, Any]], source_id: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        summary = record["text"].strip()
        if not summary or _chapter_heading(summary):
            continue
        if not any(marker in summary for marker in ACTION_MARKERS):
            continue
        rows.append(
            {
                "event_id": deterministic_id(
                    "extracted_event",
                    {"source_id": source_id, "line": record["number"], "text": summary},
                ),
                "summary": summary,
                "confidence": 0.65,
                "status": "needs_review",
                "source_span": _source_ref(
                    source_id,
                    record["number"],
                    record["char_start"],
                    record["char_end"],
                ),
            }
        )
    return rows


def _speaker_for_line(text: str, cast: list[dict[str, Any]]) -> str:
    known = {row["display_name"]: row["speaker_id"] for row in cast}
    directed = DIRECTED_SPEECH_RE.search(text)
    if directed and directed.group(1) in known:
        return known[directed.group(1)]
    spoken = SPEECH_RE.search(text)
    if spoken and spoken.group(1) in known:
        return known[spoken.group(1)]
    return known["旁白"]


def _voice_scene(
    path: Path,
    source: dict[str, Any],
    records: list[dict[str, Any]],
    selected_chapters: list[dict[str, Any]],
    cast: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_lines: set[int] = set()
    for chapter in selected_chapters:
        selected_lines.update(
            range(
                chapter["source_span"]["line_start"],
                chapter["source_span"]["line_end"] + 1,
            )
        )
    paragraphs = [
        record
        for record in records
        if record["number"] in selected_lines
        and record["text"].strip()
        and not _chapter_heading(record["text"])
    ]
    timeline: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    for sequence, record in enumerate(paragraphs, 1):
        text = record["text"].strip()
        event_id = deterministic_id(
            "event",
            {"source_id": source["source_id"], "line": record["number"], "text": text},
        )
        timeline.append(
            {
                "event_id": event_id,
                "sequence": sequence,
                "idempotency_key": deterministic_id(
                    "idem", {"source_sha256": source["sha256"], "line": record["number"]}
                ),
                "branch_id": "branch_canonical",
                "event_type": "utterance",
                "source_ref": {
                    "source_id": source["source_id"],
                    "locator": (
                        f"line={record['number']};"
                        f"chars={record['char_start']}:{record['char_end']}"
                    ),
                },
                "utterance": {
                    "speaker_id": _speaker_for_line(text, cast),
                    "text": text,
                    "language": "zh",
                    "origin": "source",
                },
            }
        )
        claims.append(
            {
                "claim_id": deterministic_id("claim", {"event_id": event_id}),
                "kind": "source_truth",
                "text": text,
                "branch_id": "branch_canonical",
                "evidence_refs": [event_id],
                "derived_from_claim_ids": [],
                "confidence": 1.0,
                "counter_evidence_refs": [],
            }
        )
    if not timeline:
        raise ValueError("selected_chapter_has_no_content")
    return {
        "schema": "agent_bridge.voice_scene.v0",
        "scene": {
            "scene_id": deterministic_id(
                "scene",
                {
                    "source_sha256": source["sha256"],
                    "selected": [row["ordinal"] for row in selected_chapters],
                },
            ),
            "mode": "story",
            "source_id": source["source_id"],
            "canonical_branch_id": "branch_canonical",
            "policy_profile": "story_s1_static",
        },
        "sources": [
            {
                "source_id": source["source_id"],
                "kind": "novel",
                "uri": str(path.resolve()),
                "sha256": source["sha256"],
                "version": source["version"],
                "consent_status": "not_applicable",
            }
        ],
        "speakers": [
            {key: value for key, value in row.items() if key != "voice_profile"}
            for row in cast
        ],
        "voice_profiles": [row["voice_profile"] for row in cast],
        "branches": [
            {
                "branch_id": "branch_canonical",
                "kind": "canonical",
                "parent_branch_id": None,
                "fork_event_id": None,
            }
        ],
        "timeline": timeline,
        "claims": claims,
        "runtime_boundary": dict(RUNTIME_BOUNDARY),
    }


def _review_queue(
    chapters: list[dict[str, Any]],
    cast: list[dict[str, Any]],
    records: list[dict[str, Any]],
    source_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(kind: str, subject_ref: str, reason: str, confidence: float) -> None:
        rows.append(
            {
                "review_id": deterministic_id(
                    "review",
                    {"kind": kind, "subject_ref": subject_ref, "reason": reason},
                ),
                "kind": kind,
                "subject_ref": subject_ref,
                "reason": reason,
                "confidence": confidence,
                "status": "needs_review",
            }
        )

    for chapter in chapters:
        add(
            "chapter_boundary",
            chapter["chapter_id"],
            "heuristic chapter heading boundary",
            0.9,
        )
    for character in cast:
        if character["kind"] == "character":
            add(
                "character_identity",
                character["speaker_id"],
                "heuristic name and alias extraction",
                0.7,
            )
        add(
            "voice_audition",
            character["voice_profile"]["voice_profile_id"],
            "voice profile is intentionally unassigned",
            0.0,
        )
    for record in records:
        if any(marker in record["text"] for marker in EMOTION_MARKERS):
            add(
                "emotion",
                deterministic_id(
                    "span", {"source_id": source_id, "line": record["number"]}
                ),
                "emotion marker is an inference, not source truth",
                0.55,
            )
    return rows


def ingest_story(path: Path, *, start: dict[str, Any]) -> dict[str, Any]:
    """Build one deterministic and reviewable S1 plan from TXT or Markdown."""

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported_story_source:{suffix or '<none>'}")
    try:
        source_bytes = path.read_bytes()
        text = source_bytes.decode("utf-8")
    except OSError as error:
        raise ValueError(f"story_source_unreadable:{path}") from error
    except UnicodeDecodeError as error:
        raise ValueError("story_source_must_be_utf8") from error

    source_sha256 = sha256_bytes(source_bytes)
    source_id = deterministic_id(
        "source", {"sha256": source_sha256, "version": "source-v1"}
    )
    chapters = index_chapters(text, source_id)
    if start.get("kind") == "from_start":
        first_chapter = chapters[0]["ordinal"]
    elif start.get("kind") == "chapter" and isinstance(start.get("chapter"), int):
        first_chapter = start["chapter"]
        if first_chapter not in {chapter["ordinal"] for chapter in chapters}:
            raise ValueError(f"story_chapter_not_found:{first_chapter}")
    else:
        raise ValueError("story_start_selector_invalid")
    for chapter in chapters:
        chapter["selected"] = chapter["ordinal"] >= first_chapter
        chapter.pop("_record_start")
        chapter.pop("_record_end")

    records = _line_records(text)
    cast = _cast_registry(text, source_sha256)
    source = {
        "source_id": source_id,
        "kind": "novel",
        "format": suffix.lstrip("."),
        "uri": str(path.resolve()),
        "sha256": source_sha256,
        "version": "source-v1",
        "encoding": "utf-8",
        "byte_length": len(source_bytes),
        "char_length": len(text),
    }
    selected = [chapter for chapter in chapters if chapter["selected"]]
    return {
        "schema": STORY_PLAN_SCHEMA,
        "status": "story_plan_reviewable",
        "command": {
            "path": str(path),
            "start": start,
            "dry_run": True,
        },
        "source": source,
        "selection": {
            "first_chapter": first_chapter,
            "selected_chapter_ids": [row["chapter_id"] for row in selected],
        },
        "chapters": chapters,
        "cast_registry": cast,
        "relationships": _extract_relationships(records, source_id),
        "events": _extract_events(records, source_id),
        "review_queue": _review_queue(chapters, cast, records, source_id),
        "voice_scene": _voice_scene(path, source, records, selected, cast),
        "runtime_boundary": dict(RUNTIME_BOUNDARY),
    }


def validate_legacy_import(payload: Any) -> list[str]:
    """Reject v1 prototype claims that cannot be migrated honestly into S1."""

    if not isinstance(payload, dict):
        return ["legacy_payload_must_be_object"]
    errors: list[str] = []
    output_file = str(payload.get("output_file", "")).lower()
    if payload.get("verify_status") == "verified" and "placeholder" in output_file:
        errors.append("legacy_placeholder_verified_forbidden")
    tool_args = payload.get("tool_args")
    if isinstance(tool_args, dict):
        for field in ("play", "emit_voice", "record", "write_memory"):
            if tool_args.get(field):
                errors.append(f"legacy_live_argument_forbidden:{field}")
        backend = tool_args.get("backend")
        if backend == "ab-tts":
            errors.append("legacy_live_backend_forbidden:ab-tts")
    return sorted(errors)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the static command and print its plan without writing artifacts."""

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("tokens", nargs=argparse.REMAINDER)
    args = parser.parse_args(list(argv) if argv is not None else None)
    tokens = args.tokens
    pretty = "--pretty" in tokens
    try:
        command = parse_story_command(tokens)
        payload = ingest_story(Path(command["path"]), start=command["start"])
        exit_code = 0
    except ValueError as error:
        payload = {
            "schema": "agent_bridge.story_plan.validation.v1",
            "status": "invalid",
            "errors": [str(error)],
            "runtime_effects": "none",
        }
        exit_code = 1
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2 if pretty else None,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
