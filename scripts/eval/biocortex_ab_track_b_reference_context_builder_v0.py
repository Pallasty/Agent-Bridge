#!/usr/bin/env python3
"""Deterministic Track B reference-context projection builder.

This source artifact accepts an already selected reference page and projects it
to the telemetry-free compact JSON shape used by the S0 reference surface.  It
does not open a store, run retrieval, choose a tokenizer or budget, authorize a
runtime, or silently truncate a page.  Those values remain later, hash-bound
inputs owned by the admission workflow.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


RESULT_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_context_result.v0"
RESULT_STATUS = "SOURCE_PROJECTION_ONLY_NOT_RUNTIME_CONTEXT_RECEIPT"
MAX_HITS = 40
MAX_CONTEXT_BYTES = 16 * 1024 * 1024
MAX_LIST_ITEMS = 1024
MAX_METADATA_BYTES = 4096
MAX_CONTENT_BYTES = 4 * 1024 * 1024
MAX_TOTAL_INPUT_UTF8_BYTES = 32 * 1024 * 1024
MIN_TIMESTAMP = -9_223_372_036_854_775_808
MAX_TIMESTAMP = 9_223_372_036_854_775_807
CASE_RE = re.compile(r"^case_[0-9a-f]{32}$")

HIT_FIELDS = (
    "rank",
    "key",
    "kind",
    "content",
    "tags",
    "related_keys",
    "scope",
    "created_at",
    "updated_at",
    "status",
    "trigger_pattern",
    "superseded_by",
)


class ReferenceContextError(RuntimeError):
    """Fail-closed protocol error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise ReferenceContextError(code, message)


def _exact_keys(value: dict[str, Any], expected: tuple[str, ...], label: str) -> None:
    if set(value) != set(expected):
        fail("OBJECT_KEYS", f"{label} field set differs from the frozen profile")


def _bounded_text(
    value: Any,
    label: str,
    *,
    maximum: int,
    nullable: bool = False,
    empty: bool = False,
) -> str | None:
    if nullable and value is None:
        return None
    if type(value) is not str:
        fail("STRING_TYPE", f"{label} must be a string")
    encoded = _utf8_bytes(value, label)
    if (not empty and not encoded) or len(encoded) > maximum:
        fail("STRING_BOUND", f"{label} is outside the UTF-8 byte bound")
    return value


def _normalized_string_list(value: Any, label: str) -> list[str]:
    if type(value) is not list or len(value) > MAX_LIST_ITEMS:
        fail("ARRAY_BOUND", f"{label} must contain at most {MAX_LIST_ITEMS} strings")
    normalized: set[str] = set()
    for index, item in enumerate(value):
        text = _bounded_text(
            item,
            f"{label}[{index}]",
            maximum=MAX_METADATA_BYTES,
            empty=True,
        )
        assert text is not None
        normalized.add(text)
    return sorted(normalized, key=lambda item: item.encode("utf-8"))


def _timestamp(value: Any, label: str) -> int:
    if type(value) is not int or not MIN_TIMESTAMP <= value <= MAX_TIMESTAMP:
        fail("TIMESTAMP", f"{label} must be a signed-64-bit integer")
    return value


def _utf8_bytes(value: str, label: str) -> bytes:
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError:
        fail("STRING_UTF8", f"{label} contains an unpaired Unicode surrogate")


def _json_string_size(value: str, add: Any) -> None:
    """Count exact serde/Python compact-JSON UTF-8 bytes without allocating it."""

    add(2)  # quotation marks
    for character in value:
        codepoint = ord(character)
        if character in {'"', "\\"}:
            add(2)
        elif codepoint in (0x08, 0x09, 0x0A, 0x0C, 0x0D):
            add(2)
        elif codepoint <= 0x1F:
            add(6)
        elif codepoint <= 0x7F:
            add(1)
        elif codepoint <= 0x7FF:
            add(2)
        elif codepoint <= 0xFFFF:
            if 0xD800 <= codepoint <= 0xDFFF:
                fail("STRING_UTF8", "reference context contains an unpaired Unicode surrogate")
            add(3)
        else:
            add(4)


def _preflight_compact_json_size(value: Any, maximum: int) -> int:
    """Reject escaped-output expansion before materializing the JSON string."""

    total = 0

    def add(amount: int) -> None:
        nonlocal total
        total += amount
        if total > maximum:
            fail(
                "CONTEXT_BUDGET_EXCEEDED",
                f"complete context exceeds the {maximum}-byte budget",
            )

    def visit(item: Any) -> None:
        if item is None:
            add(4)
        elif type(item) is bool:
            add(4 if item else 5)
        elif type(item) is int:
            add(len(str(item)))
        elif type(item) is str:
            _json_string_size(item, add)
        elif type(item) is list:
            add(1)
            for index, child in enumerate(item):
                if index:
                    add(1)
                visit(child)
            add(1)
        elif type(item) is dict:
            add(1)
            for index, (key, child) in enumerate(item.items()):
                if index:
                    add(1)
                _json_string_size(key, add)
                add(1)
                visit(child)
            add(1)
        else:
            fail("JSON_SERIALIZE", "reference context contains an unsupported value")

    visit(value)
    return total


def _compact_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        fail("JSON_SERIALIZE", f"reference context cannot be serialized: {exc}")


def _preflight_input_utf8_bytes(hits: list[Any]) -> int:
    """Bound attacker-controlled text before allocating normalized sets/JSON."""

    total = 0
    scalar_fields = (
        "key",
        "kind",
        "content",
        "scope",
        "status",
        "trigger_pattern",
        "superseded_by",
    )
    list_fields = ("tags", "related_keys")
    for index, raw in enumerate(hits):
        if type(raw) is not dict:
            fail("HIT_TYPE", f"hits[{index}] must be an object")
        _exact_keys(raw, HIT_FIELDS, f"hits[{index}]")
        for field in scalar_fields:
            value = raw[field]
            if value is not None:
                if type(value) is not str:
                    fail("STRING_TYPE", f"hits[{index}].{field} must be a string")
                total += len(_utf8_bytes(value, f"hits[{index}].{field}"))
        for field in list_fields:
            value = raw[field]
            if type(value) is not list or len(value) > MAX_LIST_ITEMS:
                fail("ARRAY_BOUND", f"hits[{index}].{field} is outside its item cap")
            for item_index, item in enumerate(value):
                if type(item) is not str:
                    fail(
                        "STRING_TYPE",
                        f"hits[{index}].{field}[{item_index}] must be a string",
                    )
                total += len(
                    _utf8_bytes(item, f"hits[{index}].{field}[{item_index}]")
                )
        if total > MAX_TOTAL_INPUT_UTF8_BYTES:
            fail("INPUT_BYTES", "reference input exceeds the 32 MiB UTF-8 cap")
    return total


def build_reference_context(
    case_id: Any,
    hits: Any,
    max_context_bytes: Any,
) -> dict[str, Any]:
    """Project one complete ranked page into exact generator-facing bytes.

    Input list order is irrelevant because explicit, contiguous ranks own the
    semantic order.  The returned ``context_json`` is the exact byte string a
    later generator may receive; reserializing the normalized rows under a
    different profile invalidates the commitment.
    """

    if type(case_id) is not str or CASE_RE.fullmatch(case_id) is None:
        fail("CASE_ID", "case_id must be an opaque Track B case identifier")
    if type(max_context_bytes) is not int or not 2 <= max_context_bytes <= MAX_CONTEXT_BYTES:
        fail(
            "CONTEXT_BUDGET",
            f"max_context_bytes must be an integer in 2..={MAX_CONTEXT_BYTES}",
        )
    if type(hits) is not list or len(hits) > MAX_HITS:
        fail("HIT_COUNT", f"reference page must contain at most {MAX_HITS} hits")
    input_utf8_bytes = _preflight_input_utf8_bytes(hits)

    by_rank: dict[int, dict[str, Any]] = {}
    seen_keys: set[str] = set()
    for index, raw in enumerate(hits):
        if type(raw) is not dict:
            fail("HIT_TYPE", f"hits[{index}] must be an object")
        _exact_keys(raw, HIT_FIELDS, f"hits[{index}]")
        rank = raw["rank"]
        if type(rank) is not int or not 1 <= rank <= MAX_HITS:
            fail("RANK", f"hits[{index}].rank is outside 1..={MAX_HITS}")
        if rank in by_rank:
            fail("RANK_DUPLICATE", "reference page repeats a rank")

        key = _bounded_text(raw["key"], "hit.key", maximum=MAX_METADATA_BYTES)
        kind = _bounded_text(raw["kind"], "hit.kind", maximum=MAX_METADATA_BYTES)
        content = _bounded_text(
            raw["content"],
            "hit.content",
            maximum=MAX_CONTENT_BYTES,
            empty=True,
        )
        scope = _bounded_text(
            raw["scope"],
            "hit.scope",
            maximum=MAX_METADATA_BYTES,
            nullable=True,
            empty=True,
        )
        status = _bounded_text(raw["status"], "hit.status", maximum=MAX_METADATA_BYTES)
        trigger = _bounded_text(
            raw["trigger_pattern"],
            "hit.trigger_pattern",
            maximum=MAX_METADATA_BYTES,
            nullable=True,
            empty=True,
        )
        superseded = _bounded_text(
            raw["superseded_by"],
            "hit.superseded_by",
            maximum=MAX_METADATA_BYTES,
            nullable=True,
            empty=True,
        )
        assert key is not None and kind is not None and content is not None
        assert status is not None
        if key in seen_keys:
            fail("KEY_DUPLICATE", "reference page repeats a memory key")
        seen_keys.add(key)
        if kind == "skill":
            fail("KIND_EXCLUDED", "the frozen reference surface excludes skill rows")
        if status != "active":
            fail("STATUS", "the frozen reference surface accepts active rows only")

        # Insertion order intentionally mirrors the Rust serde struct field
        # order in MemorySearchReferenceHit.
        by_rank[rank] = {
            "rank": rank,
            "key": key,
            "kind": kind,
            "content": content,
            "tags": _normalized_string_list(raw["tags"], "hit.tags"),
            "related_keys": _normalized_string_list(
                raw["related_keys"], "hit.related_keys"
            ),
            "scope": scope,
            "created_at": _timestamp(raw["created_at"], "hit.created_at"),
            "updated_at": _timestamp(raw["updated_at"], "hit.updated_at"),
            "status": status,
            "trigger_pattern": trigger,
            "superseded_by": superseded,
        }

    expected_ranks = list(range(1, len(hits) + 1))
    if sorted(by_rank) != expected_ranks:
        fail("RANK_CONTIGUITY", "reference ranks must be exactly 1..hit_count")
    projected = [by_rank[rank] for rank in expected_ranks]
    expected_context_bytes = _preflight_compact_json_size(
        projected, max_context_bytes
    )
    context_json = _compact_json(projected)
    encoded = _utf8_bytes(context_json, "reference context")
    if len(encoded) != expected_context_bytes:
        fail("JSON_SIZE_MISMATCH", "compact-JSON size preflight disagrees with serializer")

    return {
        "schema": RESULT_SCHEMA,
        "status": RESULT_STATUS,
        "case_id": case_id,
        "context_json": context_json,
        "context_bytes": len(encoded),
        "context_sha256": hashlib.sha256(encoded).hexdigest(),
        "hit_count": len(projected),
        "input_utf8_bytes": input_utf8_bytes,
        "input_order_invariant": True,
        "mutable_access_telemetry_included": False,
        "context_json_public_diagnostic_allowed": False,
        "truncation_applied": False,
        "runtime_configuration_verified": False,
        "runtime_context_receipt_created": False,
    }
