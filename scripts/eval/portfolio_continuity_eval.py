#!/usr/bin/env python3
"""Score redacted portfolio-continuity evidence packets without side effects.

The scorer consumes a versioned evaluation fixture plus a structured candidate.
It never calls an LLM, reads the Agent-Bridge store, executes retrieval, or
writes memory. Candidate claim ids are review labels supplied by an upstream
adapter or human reviewer; this script deliberately does not pretend that
string matching is semantic answer evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


FIXTURE_SCHEMA = "agent_bridge.portfolio_continuity_eval_fixture.v0"
CANDIDATE_SCHEMA = "agent_bridge.portfolio_continuity_candidate.v0"
OUTPUT_SCHEMA = "agent_bridge.portfolio_continuity_eval.v0"
CLAIM_CONFIDENCE = {"supported", "uncertain", "abstained"}
EVIDENCE_STATUS = {"active", "superseded", "archived", "unknown"}
RAW_CONTENT_FIELDS = {"answer", "content", "prompt", "question", "text"}
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")


class InputError(ValueError):
    """Raised when an input packet violates the evaluation contract."""


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise InputError(f"{path} must be an array")
    return value


def require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{path} must be a non-empty string")
    return value


def require_label(value: Any, path: str) -> str:
    label = require_string(value, path)
    if not LABEL_RE.fullmatch(label):
        raise InputError(
            f"{path} must match {LABEL_RE.pattern!r}; free-form text is forbidden"
        )
    return label


def reject_unknown_fields(value: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown_count = len(set(value) - allowed)
    if unknown_count:
        raise InputError(f"{path} contains {unknown_count} unsupported field(s)")


def require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise InputError(f"{path} must be a boolean")
    return value


def require_nonnegative_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InputError(f"{path} must be a non-negative integer")
    return value


def require_nonnegative_number(value: Any, path: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InputError(f"{path} must be a non-negative number")
    try:
        number = float(value)
    except OverflowError as exc:
        raise InputError(f"{path} must be a finite number") from exc
    if not math.isfinite(number) or number < 0:
        raise InputError(f"{path} must be a non-negative finite number")
    return number


def reject_json_constant(value: str) -> None:
    raise InputError(f"non-standard JSON numeric constant is forbidden: {value}")


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise InputError("JSON object contains a duplicate field")
        value[key] = child
    return value


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=reject_json_constant,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"failed to read {path}: {exc}") from exc
    return require_object(value, str(path)), raw


def reject_raw_content_fields(value: Any, path: str = "candidate") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in RAW_CONTENT_FIELDS:
                raise InputError(
                    f"{path}: raw-content field is forbidden; use redacted claim ids"
                )
            reject_raw_content_fields(child, path)
    elif isinstance(value, list):
        for child in value:
            reject_raw_content_fields(child, path)


def unique_labels(value: Any, path: str, *, allow_empty: bool = True) -> list[str]:
    raw = require_list(value, path)
    out = [require_label(item, f"{path}[{index}]") for index, item in enumerate(raw)]
    if len(out) != len(set(out)):
        raise InputError(f"{path} must not contain duplicates")
    if not allow_empty and not out:
        raise InputError(f"{path} must not be empty")
    return out


def validate_claim_specs(
    value: Any,
    path: str,
    catalog: dict[str, dict[str, Any]],
    *,
    evidence_required: bool,
) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(require_list(value, path)):
        item_path = f"{path}[{index}]"
        spec = require_object(raw, item_path)
        reject_unknown_fields(
            spec,
            {"claim_id", "weight", "accepted_evidence_keys"},
            item_path,
        )
        claim_id = require_label(spec.get("claim_id"), f"{item_path}.claim_id")
        if claim_id in specs:
            raise InputError(f"duplicate claim_id {claim_id!r} in {path}")
        weight = require_nonnegative_number(
            spec.get("weight", 1.0), f"{item_path}.weight"
        )
        if weight <= 0:
            raise InputError(f"{item_path}.weight must be a positive number")
        accepted = unique_labels(
            spec.get("accepted_evidence_keys", []),
            f"{item_path}.accepted_evidence_keys",
            allow_empty=not evidence_required,
        )
        unknown = sorted(set(accepted) - set(catalog))
        if unknown:
            raise InputError(f"{item_path} references unknown catalog keys: {unknown}")
        specs[claim_id] = {
            "claim_id": claim_id,
            "weight": weight,
            "accepted_evidence_keys": accepted,
        }
    return specs


def evidence_is_current(evidence: dict[str, Any], as_of: int) -> bool:
    if evidence["status"] != "active":
        return False
    valid_from = evidence["valid_from"]
    valid_until = evidence["valid_until"]
    return (valid_from is None or valid_from <= as_of) and (
        valid_until is None or as_of <= valid_until
    )


def validate_fixture(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema") != FIXTURE_SCHEMA:
        raise InputError(f"fixture schema must be {FIXTURE_SCHEMA}")
    reject_unknown_fields(
        value,
        {"schema", "fixture_id", "description", "thresholds", "cases"},
        "fixture",
    )
    require_label(value.get("fixture_id"), "fixture.fixture_id")
    if "description" in value:
        require_string(value["description"], "fixture.description")
    thresholds = require_object(value.get("thresholds"), "fixture.thresholds")
    reject_unknown_fields(
        thresholds,
        {
            "min_supported_claim_coverage",
            "min_evidence_precision",
            "max_stale_evidence_refs",
            "max_unknown_evidence_refs",
            "max_unsupported_claims",
            "max_forbidden_claims",
            "max_unsupported_evidence_claims",
            "require_all_cases_pass",
            "require_all_abstention_cases_pass",
        },
        "fixture.thresholds",
    )
    for key in ["min_supported_claim_coverage", "min_evidence_precision"]:
        number = require_nonnegative_number(
            thresholds.get(key), f"fixture.thresholds.{key}"
        )
        if number > 1:
            raise InputError(f"fixture.thresholds.{key} must be between 0 and 1")
    for key in [
        "max_stale_evidence_refs",
        "max_unknown_evidence_refs",
        "max_unsupported_claims",
        "max_forbidden_claims",
        "max_unsupported_evidence_claims",
    ]:
        require_nonnegative_int(thresholds.get(key), f"fixture.thresholds.{key}")
    require_bool(
        thresholds.get("require_all_cases_pass"),
        "fixture.thresholds.require_all_cases_pass",
    )
    require_bool(
        thresholds.get("require_all_abstention_cases_pass"),
        "fixture.thresholds.require_all_abstention_cases_pass",
    )

    cases = require_list(value.get("cases"), "fixture.cases")
    if not cases:
        raise InputError("fixture.cases must not be empty")
    seen_case_ids: set[str] = set()
    normalized_cases: list[dict[str, Any]] = []
    for index, raw in enumerate(cases):
        path = f"fixture.cases[{index}]"
        case = require_object(raw, path)
        reject_unknown_fields(
            case,
            {
                "case_id",
                "prompt_class",
                "as_of",
                "requires_abstention",
                "evidence_catalog",
                "required_claims",
                "optional_claims",
                "forbidden_claim_ids",
            },
            path,
        )
        case_id = require_label(case.get("case_id"), f"{path}.case_id")
        if case_id in seen_case_ids:
            raise InputError(f"duplicate case_id {case_id!r}")
        seen_case_ids.add(case_id)
        prompt_class = require_label(case.get("prompt_class"), f"{path}.prompt_class")
        as_of = require_nonnegative_int(case.get("as_of"), f"{path}.as_of")
        requires_abstention = require_bool(
            case.get("requires_abstention"), f"{path}.requires_abstention"
        )

        catalog: dict[str, dict[str, Any]] = {}
        for evidence_index, evidence_raw in enumerate(
            require_list(case.get("evidence_catalog"), f"{path}.evidence_catalog")
        ):
            evidence_path = f"{path}.evidence_catalog[{evidence_index}]"
            evidence = require_object(evidence_raw, evidence_path)
            reject_unknown_fields(
                evidence,
                {"key", "status", "valid_from", "valid_until"},
                evidence_path,
            )
            key = require_label(evidence.get("key"), f"{evidence_path}.key")
            if key in catalog:
                raise InputError(f"duplicate evidence key {key!r} in {path}")
            status = require_string(evidence.get("status"), f"{evidence_path}.status")
            if status not in EVIDENCE_STATUS:
                raise InputError(f"{evidence_path}.status must be one of {sorted(EVIDENCE_STATUS)}")
            valid_from = evidence.get("valid_from")
            valid_until = evidence.get("valid_until")
            if valid_from is not None:
                valid_from = require_nonnegative_int(valid_from, f"{evidence_path}.valid_from")
            if valid_until is not None:
                valid_until = require_nonnegative_int(valid_until, f"{evidence_path}.valid_until")
            if valid_from is not None and valid_until is not None and valid_from > valid_until:
                raise InputError(f"{evidence_path} has valid_from after valid_until")
            catalog[key] = {
                "key": key,
                "status": status,
                "valid_from": valid_from,
                "valid_until": valid_until,
            }

        required = validate_claim_specs(
            case.get("required_claims"),
            f"{path}.required_claims",
            catalog,
            evidence_required=not requires_abstention,
        )
        optional = validate_claim_specs(
            case.get("optional_claims", []),
            f"{path}.optional_claims",
            catalog,
            evidence_required=True,
        )
        forbidden = unique_labels(
            case.get("forbidden_claim_ids", []), f"{path}.forbidden_claim_ids"
        )
        overlaps = (set(required) & set(optional)) | (set(required) & set(forbidden)) | (
            set(optional) & set(forbidden)
        )
        if overlaps:
            raise InputError(f"{path} claim classes overlap: {sorted(overlaps)}")
        if requires_abstention and (required or optional):
            raise InputError(
                f"{path} abstention cases must not define required or optional claims"
            )
        if not requires_abstention and not required:
            raise InputError(f"{path} non-abstention cases must define required claims")
        for group_name, specs in [("required_claims", required), ("optional_claims", optional)]:
            for claim_id, spec in specs.items():
                if not any(
                    evidence_is_current(catalog[key], as_of)
                    for key in spec["accepted_evidence_keys"]
                ):
                    raise InputError(
                        f"{path}.{group_name} claim {claim_id!r} has no current accepted evidence"
                    )
        normalized_cases.append(
            {
                "case_id": case_id,
                "prompt_class": prompt_class,
                "as_of": as_of,
                "requires_abstention": requires_abstention,
                "catalog": catalog,
                "required": required,
                "optional": optional,
                "forbidden": set(forbidden),
            }
        )
    try:
        total_required_weight = math.fsum(
            spec["weight"]
            for case in normalized_cases
            for spec in case["required"].values()
        )
    except OverflowError as exc:
        raise InputError("fixture required-claim weight total must be finite") from exc
    if not math.isfinite(total_required_weight):
        raise InputError("fixture required-claim weight total must be finite")
    return {"thresholds": thresholds, "cases": normalized_cases}


def validate_candidate(value: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema") != CANDIDATE_SCHEMA:
        raise InputError(f"candidate schema must be {CANDIDATE_SCHEMA}")
    reject_raw_content_fields(value)
    reject_unknown_fields(
        value, {"schema", "candidate_id", "condition", "cases"}, "candidate"
    )
    candidate_id = require_label(value.get("candidate_id"), "candidate.candidate_id")
    condition = require_label(value.get("condition"), "candidate.condition")
    fixture_case_ids = {case["case_id"] for case in fixture["cases"]}
    cases: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(require_list(value.get("cases"), "candidate.cases")):
        path = f"candidate.cases[{index}]"
        case = require_object(raw, path)
        reject_unknown_fields(
            case,
            {"case_id", "abstained", "context_tokens", "latency_ms", "claims"},
            path,
        )
        case_id = require_label(case.get("case_id"), f"{path}.case_id")
        if case_id not in fixture_case_ids:
            raise InputError(f"{path} has unknown case_id {case_id!r}")
        if case_id in cases:
            raise InputError(f"candidate contains duplicate case_id {case_id!r}")
        abstained = require_bool(case.get("abstained"), f"{path}.abstained")
        context_tokens = require_nonnegative_int(
            case.get("context_tokens"), f"{path}.context_tokens"
        )
        latency_ms = require_nonnegative_number(case.get("latency_ms"), f"{path}.latency_ms")
        claims: dict[str, dict[str, Any]] = {}
        for claim_index, claim_raw in enumerate(require_list(case.get("claims"), f"{path}.claims")):
            claim_path = f"{path}.claims[{claim_index}]"
            claim = require_object(claim_raw, claim_path)
            reject_unknown_fields(
                claim,
                {"claim_id", "confidence", "evidence_keys"},
                claim_path,
            )
            claim_id = require_label(claim.get("claim_id"), f"{claim_path}.claim_id")
            if claim_id in claims:
                raise InputError(f"duplicate claim_id {claim_id!r} in {path}")
            confidence = require_string(claim.get("confidence"), f"{claim_path}.confidence")
            if confidence not in CLAIM_CONFIDENCE:
                raise InputError(
                    f"{claim_path}.confidence must be one of {sorted(CLAIM_CONFIDENCE)}"
                )
            evidence_keys = unique_labels(
                claim.get("evidence_keys"), f"{claim_path}.evidence_keys"
            )
            if confidence == "abstained" and evidence_keys:
                raise InputError(
                    f"{claim_path}.evidence_keys must be empty when confidence=abstained"
                )
            claims[claim_id] = {
                "claim_id": claim_id,
                "confidence": confidence,
                "evidence_keys": evidence_keys,
            }
        cases[case_id] = {
            "case_id": case_id,
            "abstained": abstained,
            "context_tokens": context_tokens,
            "latency_ms": latency_ms,
            "claims": claims,
        }
    return {"candidate_id": candidate_id, "condition": condition, "cases": cases}


def score_case(
    case: dict[str, Any],
    candidate: dict[str, Any] | None,
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    required = case["required"]
    optional = case["optional"]
    catalog = case["catalog"]
    claims = candidate["claims"] if candidate else {}
    abstained = candidate["abstained"] if candidate else False

    total_weight = sum(spec["weight"] for spec in required.values())
    present_weight = 0.0
    supported_weight = 0.0
    missing_required: list[str] = []
    unsupported_evidence_claims: list[str] = []
    accepted_valid_refs = 0
    total_refs = 0
    stale_refs = 0
    unknown_refs = 0

    for claim_id, spec in required.items():
        claim = claims.get(claim_id)
        present = bool(
            claim
            and not abstained
            and claim["confidence"] in {"supported", "uncertain"}
        )
        if present:
            present_weight += spec["weight"]
        else:
            missing_required.append(claim_id)
        supported = False
        if claim and claim["confidence"] == "supported" and not abstained:
            for key in claim["evidence_keys"]:
                evidence = catalog.get(key)
                if evidence and evidence_is_current(evidence, case["as_of"]):
                    if key in spec["accepted_evidence_keys"]:
                        supported = True
            if not supported:
                unsupported_evidence_claims.append(claim_id)
        if supported:
            supported_weight += spec["weight"]

    for claim_id, claim in claims.items():
        spec = required.get(claim_id) or optional.get(claim_id)
        for key in claim["evidence_keys"]:
            total_refs += 1
            evidence = catalog.get(key)
            if evidence is None:
                unknown_refs += 1
                continue
            if not evidence_is_current(evidence, case["as_of"]):
                stale_refs += 1
                continue
            if spec and key in spec["accepted_evidence_keys"]:
                accepted_valid_refs += 1
        if (
            spec
            and claim["confidence"] == "supported"
            and not any(
                key in spec["accepted_evidence_keys"]
                and key in catalog
                and evidence_is_current(catalog[key], case["as_of"])
                for key in claim["evidence_keys"]
            )
            and claim_id not in unsupported_evidence_claims
        ):
            unsupported_evidence_claims.append(claim_id)

    unsupported_claims = sorted(
        claim_id
        for claim_id, claim in claims.items()
        if claim_id not in required
        and claim_id not in optional
        and claim_id not in case["forbidden"]
        and claim["confidence"] != "abstained"
    )
    forbidden_claims = sorted(
        claim_id
        for claim_id, claim in claims.items()
        if claim_id in case["forbidden"] and claim["confidence"] != "abstained"
    )
    non_abstained_claims = [
        claim for claim in claims.values() if claim["confidence"] != "abstained"
    ]
    evidence_ref_count = sum(len(claim["evidence_keys"]) for claim in claims.values())
    if case["requires_abstention"]:
        abstention_passed = bool(
            candidate and abstained and not non_abstained_claims and evidence_ref_count == 0
        )
    else:
        abstention_passed = bool(candidate and not abstained)

    claim_coverage = 1.0 if total_weight == 0 else present_weight / total_weight
    supported_coverage = 1.0 if total_weight == 0 else supported_weight / total_weight
    evidence_precision = 1.0 if total_refs == 0 else accepted_valid_refs / total_refs
    case_passed = bool(
        candidate
        and supported_coverage >= float(thresholds["min_supported_claim_coverage"])
        and evidence_precision >= float(thresholds["min_evidence_precision"])
        and stale_refs <= int(thresholds["max_stale_evidence_refs"])
        and unknown_refs <= int(thresholds["max_unknown_evidence_refs"])
        and len(unsupported_claims) <= int(thresholds["max_unsupported_claims"])
        and len(forbidden_claims) <= int(thresholds["max_forbidden_claims"])
        and len(unsupported_evidence_claims)
        <= int(thresholds["max_unsupported_evidence_claims"])
        and abstention_passed
    )
    return {
        "case_id": case["case_id"],
        "prompt_class": case["prompt_class"],
        "candidate_present": candidate is not None,
        "requires_abstention": case["requires_abstention"],
        "abstention_passed": abstention_passed,
        "required_claim_count": len(required),
        "required_claim_weight": total_weight,
        "supported_claim_weight": supported_weight,
        "claim_coverage": round(claim_coverage, 6),
        "supported_claim_coverage": round(supported_coverage, 6),
        "evidence_precision": round(evidence_precision, 6),
        "missing_required_claim_ids": sorted(missing_required),
        "unsupported_claim_ids": unsupported_claims,
        "forbidden_claim_ids": forbidden_claims,
        "unsupported_evidence_claim_ids": sorted(unsupported_evidence_claims),
        "evidence_ref_count": total_refs,
        "accepted_valid_evidence_ref_count": accepted_valid_refs,
        "stale_evidence_ref_count": stale_refs,
        "unknown_evidence_ref_count": unknown_refs,
        "context_tokens": candidate["context_tokens"] if candidate else 0,
        "latency_ms": candidate["latency_ms"] if candidate else 0.0,
        "passed": case_passed,
    }


def percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def build_packet(
    fixture_raw: dict[str, Any],
    candidate_raw: dict[str, Any],
    fixture_bytes: bytes,
    candidate_bytes: bytes,
) -> dict[str, Any]:
    fixture = validate_fixture(fixture_raw)
    candidate = validate_candidate(candidate_raw, fixture)
    thresholds = fixture["thresholds"]
    scored_cases = [
        score_case(case, candidate["cases"].get(case["case_id"]), thresholds)
        for case in fixture["cases"]
    ]
    candidate_cases = [row for row in scored_cases if row["candidate_present"]]

    required_claim_count = sum(row["required_claim_count"] for row in scored_cases)
    required_claim_weight = sum(row["required_claim_weight"] for row in scored_cases)
    supported_claim_weight = sum(row["supported_claim_weight"] for row in scored_cases)
    total_refs = sum(row["evidence_ref_count"] for row in scored_cases)
    accepted_refs = sum(row["accepted_valid_evidence_ref_count"] for row in scored_cases)
    aggregate_supported_coverage = (
        1.0
        if required_claim_weight == 0
        else supported_claim_weight / required_claim_weight
    )
    aggregate_evidence_precision = 1.0 if total_refs == 0 else accepted_refs / total_refs
    aggregate = {
        "case_count": len(scored_cases),
        "candidate_case_count": len(candidate_cases),
        "cost_diagnostics_complete": len(candidate_cases) == len(scored_cases),
        "case_pass_count": sum(int(row["passed"]) for row in scored_cases),
        "required_claim_count": required_claim_count,
        "required_claim_weight": round(required_claim_weight, 6),
        "supported_claim_weight": round(supported_claim_weight, 6),
        "supported_claim_coverage": round(aggregate_supported_coverage, 6),
        "evidence_precision": round(aggregate_evidence_precision, 6),
        "missing_required_claim_count": sum(
            len(row["missing_required_claim_ids"]) for row in scored_cases
        ),
        "unsupported_claim_count": sum(
            len(row["unsupported_claim_ids"]) for row in scored_cases
        ),
        "forbidden_claim_count": sum(
            len(row["forbidden_claim_ids"]) for row in scored_cases
        ),
        "unsupported_evidence_claim_count": sum(
            len(row["unsupported_evidence_claim_ids"]) for row in scored_cases
        ),
        "stale_evidence_ref_count": sum(
            row["stale_evidence_ref_count"] for row in scored_cases
        ),
        "unknown_evidence_ref_count": sum(
            row["unknown_evidence_ref_count"] for row in scored_cases
        ),
        "abstention_case_count": sum(int(row["requires_abstention"]) for row in scored_cases),
        "abstention_pass_count": sum(
            int(row["requires_abstention"] and row["abstention_passed"])
            for row in scored_cases
        ),
        "context_tokens_total": sum(row["context_tokens"] for row in candidate_cases),
        "latency_ms_p95": round(
            percentile_95([row["latency_ms"] for row in candidate_cases]), 3
        ),
    }
    gate_checks = {
        "supported_claim_coverage": aggregate["supported_claim_coverage"]
        >= float(thresholds["min_supported_claim_coverage"]),
        "evidence_precision": aggregate["evidence_precision"]
        >= float(thresholds["min_evidence_precision"]),
        "stale_evidence_refs": aggregate["stale_evidence_ref_count"]
        <= int(thresholds["max_stale_evidence_refs"]),
        "unknown_evidence_refs": aggregate["unknown_evidence_ref_count"]
        <= int(thresholds["max_unknown_evidence_refs"]),
        "unsupported_claims": aggregate["unsupported_claim_count"]
        <= int(thresholds["max_unsupported_claims"]),
        "forbidden_claims": aggregate["forbidden_claim_count"]
        <= int(thresholds["max_forbidden_claims"]),
        "unsupported_evidence_claims": aggregate["unsupported_evidence_claim_count"]
        <= int(thresholds["max_unsupported_evidence_claims"]),
        "all_cases": (
            aggregate["case_pass_count"] == aggregate["case_count"]
            if thresholds["require_all_cases_pass"]
            else True
        ),
        "abstention": (
            aggregate["abstention_pass_count"] == aggregate["abstention_case_count"]
            if thresholds["require_all_abstention_cases_pass"]
            else True
        ),
    }
    verdict = "PASS" if all(gate_checks.values()) else "FAIL"
    return {
        "schema": OUTPUT_SCHEMA,
        "verdict": verdict,
        "candidate_id": candidate["candidate_id"],
        "condition": candidate["condition"],
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
        "thresholds": thresholds,
        "aggregate": aggregate,
        "gate_checks": gate_checks,
        "cases": scored_cases,
        "contract": {
            "claim_ids_are_review_labels": True,
            "natural_language_semantics_scored": False,
            "raw_content_in_output": False,
            "raw_evidence_keys_in_output": False,
            "calls_llm": False,
            "calls_retrieval": False,
            "reads_ab_store": False,
            "writes_ab_store": False,
            "benchmark_performance_claim": False,
            "runtime_promotion_allowed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, help="Versioned evaluation fixture JSON.")
    parser.add_argument("--candidate", required=True, help="Redacted candidate JSON.")
    parser.add_argument("--output", help="Optional output JSON path; stdout otherwise.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when the verdict is FAIL.")
    args = parser.parse_args(argv)

    try:
        fixture, fixture_bytes = read_json(Path(args.fixture))
        candidate, candidate_bytes = read_json(Path(args.candidate))
        packet = build_packet(fixture, candidate, fixture_bytes, candidate_bytes)
    except InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rendered = (
        json.dumps(
            packet,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    if args.strict and packet["verdict"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
