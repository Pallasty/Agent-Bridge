#!/usr/bin/env python3
"""Inspect MemoryArena JSONL task shapes without running a benchmark.

This script does not import MemoryArena code, does not use the Hugging Face
datasets package, does not call an LLM, and does not write AB memory. It reads
public JSONL rows, validates task-local sequence shape, builds temporary
in-memory AB-like projection counts, and emits a redacted shape packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.memoryarena_task_shape_packet.v0"
SOURCE_DATASET = "https://huggingface.co/datasets/ZexueHe/memoryarena"
SOURCE_PROJECT = "https://memoryarena.github.io/"
SOURCE_PAPER = "https://arxiv.org/abs/2602.16313"
SOURCE_REVISION = "da1a37c8b19280e18627ca01cf368195a5e1d92e"
CONFIGS = [
    "bundled_shopping",
    "formal_reasoning_math",
    "formal_reasoning_phys",
    "group_travel_planner",
    "progressive_search",
]
COUNT_TABLES = ["memories", "memory_edges", "semantic_events"]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_obj(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{path} must be an array")
    return value


def require_non_empty_list(value: Any, path: str) -> list[Any]:
    items = require_list(value, path)
    if not items:
        fail(f"{path} must not be empty")
    return items


def value_shape(value: Any) -> str:
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    return type(value).__name__


def count_existing_rows(db_path: str | None) -> dict[str, int] | None:
    if not db_path:
        return None
    path = Path(db_path)
    if not path.is_file():
        fail(f"store db not found: {db_path}")
    con = sqlite3.connect(path)
    try:
        counts: dict[str, int] = {}
        for table in COUNT_TABLES:
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if row is None:
                counts[table] = 0
            else:
                counts[table] = int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return counts
    finally:
        con.close()


def load_config_bytes(config: str, source_dir: str | None) -> tuple[bytes, str]:
    if source_dir:
        root = Path(source_dir)
        candidates = [
            root / config / "data.jsonl",
            root / f"{config}.jsonl",
        ]
        for path in candidates:
            if path.is_file():
                return path.read_bytes(), str(path)
        fail(f"missing data.jsonl for config {config!r} under {source_dir}")

    url = (
        "https://huggingface.co/datasets/ZexueHe/memoryarena/resolve/"
        f"{SOURCE_REVISION}/{config}/data.jsonl"
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "agent-bridge-memoryarena-shape-inspector"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read(), url


def inc(mapping: dict[str, int], key: str, amount: int = 1) -> None:
    mapping[key] = mapping.get(key, 0) + amount


def sorted_counts(mapping: dict[str, int]) -> dict[str, int]:
    def sort_key(item: tuple[str, int]) -> tuple[int, str]:
        key, _ = item
        if key.isdigit():
            return (0, f"{int(key):08d}")
        return (1, key)

    return dict(sorted(mapping.items(), key=sort_key))


def redact_key_shape(keys: list[str]) -> str:
    return ",".join(sorted(keys))


def inspect_config(config: str, raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(f"{config}: invalid JSON on line {line_number}: {exc}")
        rows.append(require_obj(row, f"{config}[line {line_number}]"))

    if not rows:
        fail(f"{config} must contain at least one JSONL row")

    key_shapes: dict[str, int] = {}
    id_shape_counts: dict[str, int] = {}
    question_count_distribution: dict[str, int] = {}
    answer_count_distribution: dict[str, int] = {}
    background_count_distribution: dict[str, int] = {}
    answer_value_shapes: dict[str, int] = {}
    background_value_shapes: dict[str, int] = {}
    base_person_value_shapes: dict[str, int] = {}
    optional_field_presence: dict[str, int] = {
        "backgrounds": 0,
        "base_person": 0,
        "category": 0,
        "paper_name": 0,
    }

    question_count = 0
    answer_count = 0
    background_slot_count = 0
    nonempty_background_count = 0
    base_person_count = 0
    qa_length_mismatch_count = 0
    background_length_mismatch_count = 0
    empty_question_count = 0
    empty_answer_count = 0
    empty_background_count = 0

    for row_index, row in enumerate(rows):
        keys = sorted(row.keys())
        inc(key_shapes, redact_key_shape(keys))
        inc(id_shape_counts, value_shape(row.get("id")))

        if "id" not in row:
            fail(f"{config}[{row_index}] missing id")
        questions = require_non_empty_list(row.get("questions"), f"{config}[{row_index}].questions")
        answers = require_non_empty_list(row.get("answers"), f"{config}[{row_index}].answers")
        if len(questions) != len(answers):
            qa_length_mismatch_count += 1

        for question_index, question in enumerate(questions):
            if not isinstance(question, str):
                fail(f"{config}[{row_index}].questions[{question_index}] must be a string")
            if not question.strip():
                empty_question_count += 1

        for answer in answers:
            answer_shape = value_shape(answer)
            inc(answer_value_shapes, answer_shape)
            if isinstance(answer, str) and not answer.strip():
                empty_answer_count += 1

        if "backgrounds" in row:
            optional_field_presence["backgrounds"] += 1
            backgrounds = require_list(row.get("backgrounds"), f"{config}[{row_index}].backgrounds")
            if len(backgrounds) != len(questions):
                background_length_mismatch_count += 1
            for background_index, background in enumerate(backgrounds):
                background_shape = value_shape(background)
                inc(background_value_shapes, background_shape)
                if not isinstance(background, str):
                    fail(
                        f"{config}[{row_index}].backgrounds[{background_index}] "
                        "must be a string"
                    )
                if not background.strip():
                    empty_background_count += 1
                else:
                    nonempty_background_count += 1
            background_slot_count += len(backgrounds)
            inc(background_count_distribution, str(len(backgrounds)))
        else:
            inc(background_count_distribution, "absent")

        for optional in ["base_person", "category", "paper_name"]:
            if optional in row:
                optional_field_presence[optional] += 1
                if optional == "base_person":
                    shape = value_shape(row[optional])
                    inc(base_person_value_shapes, shape)
                    if row[optional] is not None and not (
                        isinstance(row[optional], str) and not row[optional].strip()
                    ):
                        base_person_count += 1
                else:
                    if not isinstance(row[optional], str):
                        fail(f"{config}[{row_index}].{optional} must be a string")

        question_count += len(questions)
        answer_count += len(answers)
        inc(question_count_distribution, str(len(questions)))
        inc(answer_count_distribution, str(len(answers)))

    if qa_length_mismatch_count:
        fail(f"{config} has question/answer length mismatches: {qa_length_mismatch_count}")
    if background_length_mismatch_count:
        fail(f"{config} has background length mismatches: {background_length_mismatch_count}")
    if empty_question_count:
        fail(f"{config} has empty questions: {empty_question_count}")

    sequence_edge_count = question_count - len(rows)
    projection = {
        "config_record_count": 1,
        "task_record_count": len(rows),
        "question_record_count": question_count,
        "answer_record_count": answer_count,
        "background_record_count": nonempty_background_count,
        "base_person_record_count": base_person_count,
        "config_contains_task_edges": len(rows),
        "task_contains_question_edges": question_count,
        "question_precedes_question_edges": sequence_edge_count,
        "question_answered_by_edges": answer_count,
        "background_supports_question_edges": nonempty_background_count,
        "base_person_supports_task_edges": base_person_count,
    }
    projection["temporary_record_count"] = (
        projection["config_record_count"]
        + projection["task_record_count"]
        + projection["question_record_count"]
        + projection["answer_record_count"]
        + projection["background_record_count"]
        + projection["base_person_record_count"]
    )
    projection["temporary_edge_count"] = (
        projection["config_contains_task_edges"]
        + projection["task_contains_question_edges"]
        + projection["question_precedes_question_edges"]
        + projection["question_answered_by_edges"]
        + projection["background_supports_question_edges"]
        + projection["base_person_supports_task_edges"]
    )

    return {
        "row_count": len(rows),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "key_shapes": sorted_counts(key_shapes),
        "id_shapes": sorted_counts(id_shape_counts),
        "question_count": question_count,
        "answer_count": answer_count,
        "background_count": background_slot_count,
        "background_slot_count": background_slot_count,
        "nonempty_background_count": nonempty_background_count,
        "empty_answer_count": empty_answer_count,
        "empty_background_count": empty_background_count,
        "base_person_count": base_person_count,
        "question_count_distribution": sorted_counts(question_count_distribution),
        "answer_count_distribution": sorted_counts(answer_count_distribution),
        "background_count_distribution": sorted_counts(background_count_distribution),
        "answer_value_shapes": sorted_counts(answer_value_shapes),
        "background_value_shapes": sorted_counts(background_value_shapes),
        "base_person_value_shapes": sorted_counts(base_person_value_shapes),
        "optional_field_presence": sorted_counts(optional_field_presence),
        "qa_length_mismatch_count": qa_length_mismatch_count,
        "background_length_mismatch_count": background_length_mismatch_count,
        "projection": projection,
    }


def build_packet(source_dir: str | None, store_db: str | None) -> dict[str, Any]:
    before_counts = count_existing_rows(store_db)
    source_mode = "local_fixture" if source_dir else "hf_pinned_revision"
    configs: dict[str, Any] = {}
    source_files: dict[str, str] = {}

    totals = {
        "config_count": len(CONFIGS),
        "row_count": 0,
        "question_count": 0,
        "answer_count": 0,
        "background_count": 0,
        "background_slot_count": 0,
        "nonempty_background_count": 0,
        "empty_answer_count": 0,
        "empty_background_count": 0,
        "base_person_count": 0,
        "qa_length_mismatch_count": 0,
        "background_length_mismatch_count": 0,
        "temporary_record_count": 0,
        "temporary_edge_count": 0,
    }
    key_shapes_all: dict[str, int] = {}
    optional_field_presence_all: dict[str, int] = {
        "backgrounds": 0,
        "base_person": 0,
        "category": 0,
        "paper_name": 0,
    }
    answer_value_shapes_all: dict[str, int] = {}
    background_value_shapes_all: dict[str, int] = {}
    base_person_value_shapes_all: dict[str, int] = {}

    for config in CONFIGS:
        raw, source_file = load_config_bytes(config, source_dir)
        source_files[config] = source_file
        result = inspect_config(config, raw)
        configs[config] = result

        totals["row_count"] += result["row_count"]
        totals["question_count"] += result["question_count"]
        totals["answer_count"] += result["answer_count"]
        totals["background_count"] += result["background_count"]
        totals["background_slot_count"] += result["background_slot_count"]
        totals["nonempty_background_count"] += result["nonempty_background_count"]
        totals["empty_answer_count"] += result["empty_answer_count"]
        totals["empty_background_count"] += result["empty_background_count"]
        totals["base_person_count"] += result["base_person_count"]
        totals["qa_length_mismatch_count"] += result["qa_length_mismatch_count"]
        totals["background_length_mismatch_count"] += result["background_length_mismatch_count"]
        totals["temporary_record_count"] += result["projection"]["temporary_record_count"]
        totals["temporary_edge_count"] += result["projection"]["temporary_edge_count"]

        for key_shape, count in result["key_shapes"].items():
            inc(key_shapes_all, key_shape, count)
        for field, count in result["optional_field_presence"].items():
            inc(optional_field_presence_all, field, count)
        for answer_shape, count in result["answer_value_shapes"].items():
            inc(answer_value_shapes_all, answer_shape, count)
        for background_shape, count in result["background_value_shapes"].items():
            inc(background_value_shapes_all, background_shape, count)
        for base_shape, count in result["base_person_value_shapes"].items():
            inc(base_person_value_shapes_all, base_shape, count)

    totals["accepted_projection_item_count"] = (
        totals["temporary_record_count"] + totals["temporary_edge_count"]
    )

    after_counts = count_existing_rows(store_db)
    if before_counts is None:
        no_write = None
    else:
        no_write = {
            "checked": True,
            "passed": before_counts == after_counts,
            "before": before_counts,
            "after": after_counts,
            "deltas": {
                table: after_counts[table] - before_counts[table]  # type: ignore[index]
                for table in COUNT_TABLES
            },
        }

    return {
        "schema": SCHEMA,
        "source_dataset": SOURCE_DATASET,
        "source_project": SOURCE_PROJECT,
        "source_paper": SOURCE_PAPER,
        "source_revision": SOURCE_REVISION,
        "source_mode": source_mode,
        "source_files": source_files,
        "official_runner_import_allowed": False,
        "memoryarena_runner_allowed_now": False,
        "third_party_runtime_dependencies": False,
        "api_key_required": False,
        "private_memory_export_allowed": False,
        "writes_ab_store": False,
        "benchmark_performance_claim": False,
        "raw_content_in_output": False,
        "config_order": CONFIGS,
        "summary": totals,
        "field_inventory": {
            "key_shapes": sorted_counts(key_shapes_all),
            "optional_field_presence": sorted_counts(optional_field_presence_all),
            "answer_value_shapes": sorted_counts(answer_value_shapes_all),
            "background_value_shapes": sorted_counts(background_value_shapes_all),
            "base_person_value_shapes": sorted_counts(base_person_value_shapes_all),
        },
        "projection_model": {
            "record_types": [
                "config",
                "task",
                "subtask_question",
                "answer_reference",
                "background",
                "base_person",
            ],
            "edge_types": [
                "config_contains_task",
                "task_contains_question",
                "question_precedes_question",
                "question_answered_by",
                "background_supports_question",
                "base_person_supports_task",
            ],
        },
        "configs": configs,
        "no_write_invariant": no_write,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        help="Directory containing MemoryArena-style <config>/data.jsonl files. "
        "If omitted, reads the pinned Hugging Face revision.",
    )
    parser.add_argument("--store-db", help="Optional SQLite store for no-write sentinel counts.")
    parser.add_argument("--output", help="Write JSON packet to this path instead of stdout.")
    args = parser.parse_args()

    packet = build_packet(args.source_dir, args.store_db)
    text = json.dumps(packet, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
