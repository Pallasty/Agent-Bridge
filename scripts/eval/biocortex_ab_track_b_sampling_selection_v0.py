#!/usr/bin/env python3
"""Deterministic stratified SRSWOR ordering for Track B sampling.

Every case receives a full-width HMAC-SHA-256 ordering key inside its stratum.
The first n_h cases are selected and the remainder form a frozen reserve order.
No modulo reduction is used.  The result reports exact reduced inclusion
probabilities n_h/N_h and reciprocal case-grain weights N_h/n_h, but it never
applies those weights and never creates a custody receipt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
from typing import Any


REQUEST_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_selection_request.v0"
RESULT_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_selection_result.v0"
RESULT_STATUS = "SOURCE_SELECTION_ONLY_NOT_FRAME_OR_SAMPLING_RECEIPT"
SELECTION_DOMAIN = "agent-bridge/track-b/sample/v1"
SELECTION_MESSAGE_PROFILE = (
    "domain_utf8_NUL_frame_sha256_ascii_NUL_stratum_utf8_NUL_case_id_utf8"
)
MAX_CASES = 4096
MAX_STRATA = 256
SEED_BYTES = 32

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
CASE_RE = re.compile(r"^case_[0-9a-f]{32}$")
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
REQUEST_FIELDS = {
    "cases",
    "eligible_frame_manifest_sha256",
    "schema",
    "strata_allocations",
}


class SamplingSelectionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise SamplingSelectionError(code, message)


def _require_match(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        fail("IDENTIFIER", f"{label} is outside the frozen identifier profile")
    return value


def _canonical_pretty_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                indent=2,
                separators=(",", ": "),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail("JSON_CANONICAL", f"selection commitment cannot be serialized: {exc}")


def _reduced(numerator: int, denominator: int) -> dict[str, int]:
    divisor = math.gcd(numerator, denominator)
    return {
        "numerator": numerator // divisor,
        "denominator": denominator // divisor,
    }


def _selection_key(seed: bytes, frame_sha256: str, stratum: str, case_id: str) -> bytes:
    message = b"\0".join(
        (
            SELECTION_DOMAIN.encode("utf-8"),
            frame_sha256.encode("ascii"),
            stratum.encode("utf-8"),
            case_id.encode("utf-8"),
        )
    )
    return hmac.new(seed, message, hashlib.sha256).digest()


def select_stratified_cases(request: Any, seed_bytes: Any) -> dict[str, Any]:
    if type(request) is not dict or set(request) != REQUEST_FIELDS:
        fail("REQUEST_KEYS", "selection request field set differs from the frozen profile")
    if request["schema"] != REQUEST_SCHEMA:
        fail("REQUEST_SCHEMA", "selection request schema drift")
    frame_sha256 = _require_match(
        request["eligible_frame_manifest_sha256"],
        SHA_RE,
        "eligible_frame_manifest_sha256",
    )
    if type(seed_bytes) is not bytes or len(seed_bytes) != SEED_BYTES:
        fail("SEED", "selection seed must be exactly 32 bytes")

    raw_cases = request["cases"]
    if type(raw_cases) is not list or not 1 <= len(raw_cases) <= MAX_CASES:
        fail("CASE_COUNT", f"eligible frame must contain 1..={MAX_CASES} cases")
    cases_by_stratum: dict[str, list[str]] = {}
    seen_cases: set[str] = set()
    for index, raw_case in enumerate(raw_cases):
        if type(raw_case) is not dict or set(raw_case) != {"case_id", "stratum"}:
            fail("CASE_KEYS", f"cases[{index}] field set differs from the frozen profile")
        case_id = _require_match(raw_case["case_id"], CASE_RE, "case_id")
        stratum = _require_match(raw_case["stratum"], LABEL_RE, "stratum")
        if case_id in seen_cases:
            fail("CASE_DUPLICATE", "eligible frame repeats a case_id")
        seen_cases.add(case_id)
        cases_by_stratum.setdefault(stratum, []).append(case_id)
    if len(cases_by_stratum) > MAX_STRATA:
        fail("STRATUM_COUNT", f"eligible frame exceeds {MAX_STRATA} strata")

    raw_allocations = request["strata_allocations"]
    if type(raw_allocations) is not list or not 1 <= len(raw_allocations) <= MAX_STRATA:
        fail("ALLOCATION_COUNT", f"allocation must contain 1..={MAX_STRATA} strata")
    allocations: dict[str, int] = {}
    for index, raw in enumerate(raw_allocations):
        if type(raw) is not dict or set(raw) != {"sample_size", "stratum"}:
            fail("ALLOCATION_KEYS", f"strata_allocations[{index}] field set drift")
        stratum = _require_match(raw["stratum"], LABEL_RE, "allocation.stratum")
        sample_size = raw["sample_size"]
        if type(sample_size) is not int or sample_size < 1:
            fail("SAMPLE_SIZE", "every represented stratum must select at least one case")
        if stratum in allocations:
            fail("ALLOCATION_DUPLICATE", "allocation repeats a stratum")
        allocations[stratum] = sample_size
    if set(allocations) != set(cases_by_stratum):
        fail("STRATUM_COVERAGE", "allocation strata must exactly cover frame strata")

    selected: list[dict[str, Any]] = []
    reserve: list[dict[str, Any]] = []
    probabilities: list[dict[str, Any]] = []
    weights: list[dict[str, Any]] = []
    stratum_counts: list[dict[str, Any]] = []
    for stratum in sorted(cases_by_stratum, key=lambda item: item.encode("utf-8")):
        population = cases_by_stratum[stratum]
        sample_size = allocations[stratum]
        if sample_size > len(population):
            fail("SAMPLE_SIZE", "stratum sample_size exceeds its population")
        keyed = [
            (_selection_key(seed_bytes, frame_sha256, stratum, case_id), case_id)
            for case_id in population
        ]
        if len({digest for digest, _ in keyed}) != len(keyed):
            fail("HMAC_COLLISION", "full-width selection keys collide within a stratum")
        ordered = [case_id for _, case_id in sorted(keyed, key=lambda row: row[0])]
        probability = _reduced(sample_size, len(population))
        weight = _reduced(len(population), sample_size)
        for case_id in ordered[:sample_size]:
            selected.append({"case_id": case_id, "stratum": stratum})
        for rank, case_id in enumerate(ordered[sample_size:], 1):
            reserve.append(
                {"case_id": case_id, "reserve_rank": rank, "stratum": stratum}
            )
        stratum_counts.append(
            {
                "stratum": stratum,
                "population_size": len(population),
                "sample_size": sample_size,
                "reserve_size": len(population) - sample_size,
                "inclusion_probability": probability,
                "case_weight": weight,
            }
        )

    # Selected-manifest and rational rows use opaque case-id order, so they do
    # not directly serialize HMAC rank. The rank remains publicly recomputable
    # once all seed-derivation bindings have been published.
    selected.sort(key=lambda row: row["case_id"].encode("utf-8"))
    for row in selected:
        stratum = row["stratum"]
        population_size = len(cases_by_stratum[stratum])
        sample_size = allocations[stratum]
        probabilities.append(
            {"case_id": row["case_id"], **_reduced(sample_size, population_size)}
        )
        weights.append(
            {"case_id": row["case_id"], **_reduced(population_size, sample_size)}
        )

    core = {
        "eligible_frame_manifest_sha256": frame_sha256,
        "selected_cases": selected,
        "reserve_cases": reserve,
        "case_inclusion_probabilities": probabilities,
        "case_sampling_weights": weights,
        "strata": stratum_counts,
    }
    seed_sha256 = hashlib.sha256(seed_bytes).hexdigest()
    result_without_commitment = {
        "schema": RESULT_SCHEMA,
        "status": RESULT_STATUS,
        "sampling_selection_domain": SELECTION_DOMAIN,
        "sampling_selection_message": SELECTION_MESSAGE_PROFILE,
        "sampling_seed_sha256": seed_sha256,
        **core,
        "input_order_invariant": True,
        "full_width_hmac_ordering": True,
        "modulo_reduction_used": False,
        "weights_applied": False,
        "eligible_frame_bytes_verified": False,
        "sampling_receipt_created": False,
        "condition_output_authorized": False,
    }
    # Bind the complete result envelope, not only the sampling core.  The
    # commitment field itself is the sole excluded field, avoiding a cycle.
    return {
        **result_without_commitment,
        "selection_commitment_sha256": hashlib.sha256(
            _canonical_pretty_bytes(result_without_commitment)
        ).hexdigest(),
    }
