#!/usr/bin/env python3
"""Build a no-write MemoryArena -> Agent-Bridge adapter contract packet.

The helper reads MemoryArena-style JSONL, reuses the local shape inspector for
validation, and builds deterministic temporary record and edge identifiers in
memory. It does not import or run MemoryArena, call an LLM, expose source
content, install dependencies, or write Agent-Bridge memory.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.memoryarena_adapter_contract.v0"
SCOPE = "benchmark:memoryarena"
SHAPE_MODULE_NAME = "memoryarena_task_shape_inspector"
REALMEM_REFERENCE_SCHEMA = "agent_bridge.realmem_adapter_contract.v0"
RECORD_KINDS = {
    "config": "benchmark_synthetic_memoryarena_config",
    "task": "benchmark_synthetic_memoryarena_task",
    "question": "benchmark_synthetic_memoryarena_question",
    "answer_reference": "benchmark_synthetic_memoryarena_answer_reference",
    "background": "benchmark_synthetic_memoryarena_background",
    "base_person": "benchmark_synthetic_memoryarena_base_person",
}
EDGE_KINDS = [
    "config_contains_task",
    "task_contains_question",
    "question_precedes_question",
    "question_answered_by",
    "background_supports_question",
    "base_person_supports_task",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_shape_module() -> Any:
    module_path = Path(__file__).with_name("memoryarena-task-shape-inspector.py")
    spec = importlib.util.spec_from_file_location(SHAPE_MODULE_NAME, module_path)
    if spec is None or spec.loader is None:
        fail(f"unable to load shape inspector module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHAPE = load_shape_module()
SOURCE_REVISION = SHAPE.SOURCE_REVISION
CONFIGS = SHAPE.CONFIGS


def require_obj(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{path} must be an array")
    return value


def add_count(counts: dict[str, int], key: str, delta: int = 1) -> None:
    counts[key] = counts.get(key, 0) + delta


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def task_key(config: str, source_id: Any) -> str:
    identity = "\n".join([SOURCE_REVISION, config, canonical_json(source_id)])
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"memoryarena:{config}:task:{digest}"


def edge_key(from_key: str, to_key: str, logical_edge_kind: str) -> str:
    identity = "\n".join([logical_edge_kind, from_key, to_key])
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"memoryarena:edge:{logical_edge_kind}:{digest}"


def source_value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def parse_rows(config: str, raw: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail(f"{config}: invalid UTF-8: {exc}")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(f"{config}: invalid JSON on line {line_number}: {exc}")
        rows.append(require_obj(value, f"{config}[line {line_number}]"))
    if not rows:
        fail(f"{config} must contain at least one JSONL row")
    return rows


def record_descriptor(
    *,
    key: str,
    kind: str,
    source_path: str,
    content_source: str,
    tags: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    descriptor: dict[str, Any] = {
        "key": key,
        "kind": kind,
        "content_policy": "source_content_redacted_from_packet",
        "content_source": content_source,
        "source_path": source_path,
        "tags": tags,
        "scope": SCOPE,
        "status": "active",
        "importance": 0.3,
    }
    if extra:
        descriptor.update(extra)
    return descriptor


def edge_descriptor(
    *,
    from_key: str,
    to_key: str,
    logical_edge_kind: str,
    source_path: str,
    weight: float,
) -> dict[str, Any]:
    return {
        "id": edge_key(from_key, to_key, logical_edge_kind),
        "from_key": from_key,
        "to_key": to_key,
        "edge_type": logical_edge_kind,
        "logical_edge_kind": logical_edge_kind,
        "source_path": source_path,
        "weight": weight,
    }


class ProjectionCollector:
    def __init__(self) -> None:
        self.record_kind_counts = {kind: 0 for kind in RECORD_KINDS.values()}
        self.edge_kind_counts = {kind: 0 for kind in EDGE_KINDS}
        self.record_ids: set[str] = set()
        self.edge_ids: set[str] = set()
        self.duplicate_record_id_count = 0
        self.duplicate_edge_id_count = 0
        self.dangling_edge_endpoint_count = 0
        self.record_samples: dict[str, dict[str, Any]] = {}
        self.edge_samples: dict[str, dict[str, Any]] = {}

    def add_record(self, descriptor: dict[str, Any]) -> None:
        key = descriptor["key"]
        kind = descriptor["kind"]
        add_count(self.record_kind_counts, kind)
        if key in self.record_ids:
            self.duplicate_record_id_count += 1
        else:
            self.record_ids.add(key)
        self.record_samples.setdefault(kind, descriptor)

    def add_edge(self, descriptor: dict[str, Any]) -> None:
        edge_id = descriptor["id"]
        kind = descriptor["logical_edge_kind"]
        add_count(self.edge_kind_counts, kind)
        if edge_id in self.edge_ids:
            self.duplicate_edge_id_count += 1
        else:
            self.edge_ids.add(edge_id)
        for endpoint in [descriptor["from_key"], descriptor["to_key"]]:
            if endpoint not in self.record_ids:
                self.dangling_edge_endpoint_count += 1
        self.edge_samples.setdefault(kind, descriptor)

    def ordered_record_samples(self) -> list[dict[str, Any]]:
        return [
            self.record_samples[kind]
            for kind in RECORD_KINDS.values()
            if kind in self.record_samples
        ]

    def ordered_edge_samples(self) -> list[dict[str, Any]]:
        return [self.edge_samples[kind] for kind in EDGE_KINDS if kind in self.edge_samples]


def add_task_projection(
    collector: ProjectionCollector,
    *,
    config: str,
    config_key: str,
    row: dict[str, Any],
    row_index: int,
) -> None:
    row_path = f"configs[{config}].rows[{row_index}]"
    if "id" not in row:
        fail(f"{row_path} missing id")
    questions = require_list(row.get("questions"), f"{row_path}.questions")
    answers = require_list(row.get("answers"), f"{row_path}.answers")
    if len(questions) != len(answers):
        fail(f"{row_path} question/answer lengths do not match")

    candidate_task_key = task_key(config, row["id"])
    optional_fields = [
        field
        for field in ["backgrounds", "base_person", "category", "paper_name"]
        if field in row
    ]
    collector.add_record(
        record_descriptor(
            key=candidate_task_key,
            kind=RECORD_KINDS["task"],
            source_path=row_path,
            content_source="id,category,paper_name,task-local counts",
            tags=["memoryarena", "synthetic", "no_write", "record:task", f"config:{config}"],
            extra={
                "source_id_shape": SHAPE.value_shape(row["id"]),
                "question_count": len(questions),
                "optional_fields": optional_fields,
            },
        )
    )
    collector.add_edge(
        edge_descriptor(
            from_key=config_key,
            to_key=candidate_task_key,
            logical_edge_kind="config_contains_task",
            source_path=row_path,
            weight=1.0,
        )
    )

    backgrounds: list[Any] | None = None
    if "backgrounds" in row:
        backgrounds = require_list(row["backgrounds"], f"{row_path}.backgrounds")
        if len(backgrounds) != len(questions):
            fail(f"{row_path} question/background lengths do not match")

    previous_question_key: str | None = None
    for item_index, (question, answer) in enumerate(zip(questions, answers, strict=True)):
        item_number = item_index + 1
        item_suffix = f"{item_number:04d}"
        question_path = f"{row_path}.questions[{item_index}]"
        answer_path = f"{row_path}.answers[{item_index}]"
        if not isinstance(question, str) or not question.strip():
            fail(f"{question_path} must be a non-empty string")

        question_key = f"{candidate_task_key}:question:{item_suffix}"
        answer_key = f"{candidate_task_key}:answer:{item_suffix}"
        collector.add_record(
            record_descriptor(
                key=question_key,
                kind=RECORD_KINDS["question"],
                source_path=question_path,
                content_source="questions[item]",
                tags=[
                    "memoryarena",
                    "synthetic",
                    "no_write",
                    "record:question",
                    f"config:{config}",
                ],
                extra={"ordinal": item_number},
            )
        )
        collector.add_record(
            record_descriptor(
                key=answer_key,
                kind=RECORD_KINDS["answer_reference"],
                source_path=answer_path,
                content_source="answers[item]",
                tags=[
                    "memoryarena",
                    "synthetic",
                    "no_write",
                    "record:answer_reference",
                    f"config:{config}",
                ],
                extra={"ordinal": item_number, "value_shape": SHAPE.value_shape(answer)},
            )
        )
        collector.add_edge(
            edge_descriptor(
                from_key=candidate_task_key,
                to_key=question_key,
                logical_edge_kind="task_contains_question",
                source_path=question_path,
                weight=1.0,
            )
        )
        if previous_question_key is not None:
            collector.add_edge(
                edge_descriptor(
                    from_key=previous_question_key,
                    to_key=question_key,
                    logical_edge_kind="question_precedes_question",
                    source_path=question_path,
                    weight=1.0,
                )
            )
        collector.add_edge(
            edge_descriptor(
                from_key=question_key,
                to_key=answer_key,
                logical_edge_kind="question_answered_by",
                source_path=answer_path,
                weight=1.0,
            )
        )

        if backgrounds is not None and source_value_present(backgrounds[item_index]):
            background_path = f"{row_path}.backgrounds[{item_index}]"
            background_key = f"{candidate_task_key}:background:{item_suffix}"
            collector.add_record(
                record_descriptor(
                    key=background_key,
                    kind=RECORD_KINDS["background"],
                    source_path=background_path,
                    content_source="backgrounds[item]",
                    tags=[
                        "memoryarena",
                        "synthetic",
                        "no_write",
                        "record:background",
                        f"config:{config}",
                    ],
                    extra={
                        "ordinal": item_number,
                        "value_shape": SHAPE.value_shape(backgrounds[item_index]),
                    },
                )
            )
            collector.add_edge(
                edge_descriptor(
                    from_key=background_key,
                    to_key=question_key,
                    logical_edge_kind="background_supports_question",
                    source_path=background_path,
                    weight=0.9,
                )
            )
        previous_question_key = question_key

    if "base_person" in row and source_value_present(row["base_person"]):
        base_path = f"{row_path}.base_person"
        base_key = f"{candidate_task_key}:base-person"
        collector.add_record(
            record_descriptor(
                key=base_key,
                kind=RECORD_KINDS["base_person"],
                source_path=base_path,
                content_source="base_person",
                tags=[
                    "memoryarena",
                    "synthetic",
                    "no_write",
                    "record:base_person",
                    f"config:{config}",
                ],
                extra={"value_shape": SHAPE.value_shape(row["base_person"])},
            )
        )
        collector.add_edge(
            edge_descriptor(
                from_key=base_key,
                to_key=candidate_task_key,
                logical_edge_kind="base_person_supports_task",
                source_path=base_path,
                weight=0.9,
            )
        )


def build_packet(source_dir: str | None, store_db: str | None) -> dict[str, Any]:
    before = SHAPE.count_existing_rows(store_db)
    source_mode = "local_fixture" if source_dir else "hf_pinned_revision"
    collector = ProjectionCollector()
    source_sha256: dict[str, str] = {}
    shape_summary = {
        "config_count": len(CONFIGS),
        "row_count": 0,
        "question_count": 0,
        "answer_count": 0,
        "background_slot_count": 0,
        "nonempty_background_count": 0,
        "empty_background_count": 0,
        "base_person_count": 0,
        "temporary_record_count": 0,
        "temporary_edge_count": 0,
    }
    answer_value_shapes: dict[str, int] = {}
    base_person_value_shapes: dict[str, int] = {}

    for config in CONFIGS:
        raw, _source_file = SHAPE.load_config_bytes(config, source_dir)
        source_sha256[config] = hashlib.sha256(raw).hexdigest()
        shape_result = SHAPE.inspect_config(config, raw)
        rows = parse_rows(config, raw)

        shape_summary["row_count"] += shape_result["row_count"]
        shape_summary["question_count"] += shape_result["question_count"]
        shape_summary["answer_count"] += shape_result["answer_count"]
        shape_summary["background_slot_count"] += shape_result["background_slot_count"]
        shape_summary["nonempty_background_count"] += shape_result["nonempty_background_count"]
        shape_summary["empty_background_count"] += shape_result["empty_background_count"]
        shape_summary["base_person_count"] += shape_result["base_person_count"]
        shape_summary["temporary_record_count"] += shape_result["projection"][
            "temporary_record_count"
        ]
        shape_summary["temporary_edge_count"] += shape_result["projection"][
            "temporary_edge_count"
        ]
        for value_shape, count in shape_result["answer_value_shapes"].items():
            add_count(answer_value_shapes, value_shape, count)
        for value_shape, count in shape_result["base_person_value_shapes"].items():
            add_count(base_person_value_shapes, value_shape, count)

        config_key = f"memoryarena:{config}:config"
        collector.add_record(
            record_descriptor(
                key=config_key,
                kind=RECORD_KINDS["config"],
                source_path=f"configs[{config}]",
                content_source="config identity and source digest",
                tags=[
                    "memoryarena",
                    "synthetic",
                    "no_write",
                    "record:config",
                    f"config:{config}",
                ],
                extra={"row_count": len(rows)},
            )
        )
        for row_index, row in enumerate(rows):
            add_task_projection(
                collector,
                config=config,
                config_key=config_key,
                row=row,
                row_index=row_index,
            )

    after = SHAPE.count_existing_rows(store_db)
    if before is not None and after is not None:
        no_write = {
            "checked": True,
            "passed": before == after,
            "before": before,
            "after": after,
            "deltas": {
                table: after[table] - before[table]
                for table in SHAPE.COUNT_TABLES
            },
        }
    else:
        no_write = {
            "checked": False,
            "passed": True,
            "before": None,
            "after": None,
            "deltas": {table: 0 for table in SHAPE.COUNT_TABLES},
        }

    projected_record_count = sum(collector.record_kind_counts.values())
    accepted_edge_count = sum(collector.edge_kind_counts.values())
    acceptance_gates = {
        "source_revision_pinned": SOURCE_REVISION
        == "da1a37c8b19280e18627ca01cf368195a5e1d92e",
        "shape_schema_matches": SHAPE.SCHEMA
        == "agent_bridge.memoryarena_task_shape_packet.v0",
        "all_five_configs_present": list(CONFIGS)
        == [
            "bundled_shopping",
            "formal_reasoning_math",
            "formal_reasoning_phys",
            "group_travel_planner",
            "progressive_search",
        ],
        "record_count_matches_shape_packet": projected_record_count
        == shape_summary["temporary_record_count"],
        "edge_count_matches_shape_packet": accepted_edge_count
        == shape_summary["temporary_edge_count"],
        "record_ids_unique": collector.duplicate_record_id_count == 0,
        "edge_ids_unique": collector.duplicate_edge_id_count == 0,
        "edge_endpoints_resolve": collector.dangling_edge_endpoint_count == 0,
        "raw_content_redacted": True,
        "no_ab_store_write": no_write["passed"],
        "no_benchmark_performance_claim": True,
    }
    verdict = "PASS" if all(acceptance_gates.values()) else "FAIL"

    return {
        "schema": SCHEMA,
        "shape_schema": SHAPE.SCHEMA,
        "source_dataset": SHAPE.SOURCE_DATASET,
        "source_project": SHAPE.SOURCE_PROJECT,
        "source_paper": SHAPE.SOURCE_PAPER,
        "source_revision": SOURCE_REVISION,
        "source_mode": source_mode,
        "source_sha256": dict(sorted(source_sha256.items())),
        "official_runner_import_allowed": False,
        "memoryarena_runner_allowed_now": False,
        "third_party_runtime_dependencies": False,
        "api_key_required": False,
        "private_memory_export_allowed": False,
        "writes_ab_store": False,
        "benchmark_performance_claim": False,
        "raw_content_in_output": False,
        "verdict": verdict,
        "scope": SCOPE,
        "identifier_contract": {
            "stability_scope": "pinned_source_revision",
            "task_identity_input": "source_revision,config,canonical_json(source_id)",
            "task_identity_digest": "sha256_first_20_hex",
            "edge_identity_input": "logical_edge_kind,from_key,to_key",
            "edge_identity_digest": "sha256_first_24_hex",
            "templates": {
                "config": "memoryarena:{config}:config",
                "task": "memoryarena:{config}:task:{task_identity_digest}",
                "question": "{task_key}:question:{one_based_ordinal_4d}",
                "answer_reference": "{task_key}:answer:{one_based_ordinal_4d}",
                "background": "{task_key}:background:{one_based_ordinal_4d}",
                "base_person": "{task_key}:base-person",
                "edge": "memoryarena:edge:{logical_edge_kind}:{edge_identity_digest}",
            },
            "source_id_exposed": False,
        },
        "record_projection": {
            "record_kinds": list(RECORD_KINDS.values()),
            "record_kind_counts": collector.record_kind_counts,
            "projected_record_count": projected_record_count,
            "unique_record_id_count": len(collector.record_ids),
        },
        "edge_projection": {
            "accepted_logical_edge_kinds": EDGE_KINDS,
            "accepted_logical_edge_counts": collector.edge_kind_counts,
            "accepted_memory_edge_count": accepted_edge_count,
            "unique_edge_id_count": len(collector.edge_ids),
        },
        "shape_parity": {
            **shape_summary,
            "accepted_projection_item_count": projected_record_count + accepted_edge_count,
            "answer_value_shapes": dict(sorted(answer_value_shapes.items())),
            "base_person_value_shapes": dict(sorted(base_person_value_shapes.items())),
        },
        "data_quality_flags": {
            "duplicate_record_id_count": collector.duplicate_record_id_count,
            "duplicate_edge_id_count": collector.duplicate_edge_id_count,
            "dangling_edge_endpoint_count": collector.dangling_edge_endpoint_count,
            "empty_backgrounds_not_projected": True,
            "heterogeneous_answer_shapes_preserved_as_metadata": True,
            "source_values_redacted": True,
        },
        "adapter_family_comparison": {
            "reference_schema": REALMEM_REFERENCE_SCHEMA,
            "shared_packet_fields": [
                "schema",
                "shape_schema",
                "scope",
                "verdict",
                "record_projection",
                "edge_projection",
                "acceptance_gates",
                "samples",
                "no_write_invariant",
            ],
            "shared_record_descriptor_fields": [
                "key",
                "kind",
                "content_policy",
                "content_source",
                "source_path",
                "tags",
                "scope",
                "status",
                "importance",
            ],
            "shared_edge_descriptor_fields": [
                "from_key",
                "to_key",
                "edge_type",
                "logical_edge_kind",
                "source_path",
                "weight",
            ],
            "memoryarena_reference_resolver_required": False,
            "realmem_reference_resolver_required": True,
            "compatible_no_write_adapter_structure": True,
            "runtime_compatibility_claim": False,
        },
        "acceptance_gates": acceptance_gates,
        "samples": {
            "records": collector.ordered_record_samples(),
            "accepted_edges": collector.ordered_edge_samples(),
        },
        "no_write_invariant": no_write,
    }


def write_output(packet: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        help="Directory containing MemoryArena-style <config>/data.jsonl files. "
        "If omitted, reads the pinned Hugging Face revision.",
    )
    parser.add_argument(
        "--store-db",
        help="Optional AB SQLite store path used only to prove row counts are unchanged.",
    )
    parser.add_argument("--output", help="Optional output JSON path.")
    args = parser.parse_args(argv)

    packet = build_packet(args.source_dir, args.store_db)
    write_output(packet, args.output)
    return 0 if packet["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
