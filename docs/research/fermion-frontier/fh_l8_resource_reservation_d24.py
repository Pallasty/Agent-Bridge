#!/usr/bin/env python3
"""D24 external-resource receipt admission, deliberately not authorization."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_SCRATCH_BYTES = 2_750_812_950
REQUIRED_FILES = 13_622
REQUIRED_KEYS = {
    "schema_version", "receipt_id", "issuer", "issued_unix_ns", "not_before_unix_ns", "not_after_unix_ns",
    "exclusive_execution_slot", "isolation_id", "scratch_free_bytes", "scratch_free_inodes",
    "memory_max_bytes", "runtime_upper_bound_ns", "immutable_receipt_sha256",
}


class ReservationError(ValueError):
    pass


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in items:
        if key in result:
            raise ReservationError("duplicate receipt key")
        result[key] = value
    return result


def load_receipt(path: Path) -> dict:
    raw = path.read_bytes()
    if not raw or len(raw) > 65_536:
        raise ReservationError("receipt size outside bound")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_float=lambda x: (_ for _ in ()).throw(ReservationError("float forbidden")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReservationError("receipt is not strict JSON") from exc
    if not isinstance(value, dict) or set(value) != REQUIRED_KEYS:
        raise ReservationError("receipt schema drift")
    return value


def admit(receipt: dict) -> dict:
    if set(receipt) != REQUIRED_KEYS or receipt["schema_version"] != 1:
        raise ReservationError("receipt schema drift")
    string_fields = ("receipt_id", "issuer", "isolation_id", "immutable_receipt_sha256")
    if any(not isinstance(receipt[key], str) or not receipt[key] for key in string_fields):
        raise ReservationError("receipt string identity drift")
    ints = ("issued_unix_ns", "not_before_unix_ns", "not_after_unix_ns", "scratch_free_bytes", "scratch_free_inodes", "memory_max_bytes", "runtime_upper_bound_ns")
    if any(type(receipt[key]) is not int or receipt[key] <= 0 for key in ints):
        raise ReservationError("receipt integer bound drift")
    if not receipt["exclusive_execution_slot"] or receipt["not_after_unix_ns"] <= receipt["not_before_unix_ns"]:
        raise ReservationError("receipt exclusivity or time window drift")
    capacity_ok = receipt["scratch_free_bytes"] >= REQUIRED_SCRATCH_BYTES and receipt["scratch_free_inodes"] >= REQUIRED_FILES
    return {
        "status": "NO_GO_D24_RESOURCE_RECEIPT_ADMISSIBLE_BUT_REQUIREMENTS_UNPROVEN",
        "receipt_admissible": True,
        "disk_and_file_reservation_satisfies_d23_guardrail": capacity_ok,
        "memory_bound_declared": True,
        "runtime_bound_declared": True,
        "full_53_scientific_execution_authorized": False,
        "scientific_action_calls": 0,
        "next_gate": "FULL_53_MEMORY_RUNTIME_REQUIREMENT_PROOF_AND_INDEPENDENT_RECEIPT_VERIFICATION",
    }


def no_receipt() -> dict:
    return {
        "status": "NO_GO_D24_EXTERNAL_RESOURCE_RECEIPT_ABSENT",
        "receipt_admissible": False,
        "full_53_scientific_execution_authorized": False,
        "scientific_action_calls": 0,
        "next_gate": "FULL_53_MEMORY_RUNTIME_REQUIREMENT_PROOF_AND_INDEPENDENT_RECEIPT_VERIFICATION",
    }
