#!/usr/bin/env python3
"""Preflight the fixed L=8 dual-observable measurement campaign.

This planner derives every comparison count and shot target from the pinned
evidence contract.  It plans executions; it never certifies measured data or
emits a convergence READY status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


EXPECTED_EVIDENCE_CONTRACT_SHA256 = (
    "609cbb8e94e05a868fa0ca3c974966187a37793a6f7e4322813d409e83a658b4"
)
CANONICALIZATION = "json-sort-keys-compact-utf8-v1"
OBSERVABLE_ORDER = ["staggered_magnetization", "double_occupancy"]
EXPECTED_REFERENCE_MODE = "exact_bounded_planned"
EXPECTED_ALLOCATION_SCOPE = "all_declared_points"
EXPECTED_ALPHA = 0.05
EXPECTED_BETA = 0.01
EXPECTED_ALLOCATION = {
    "target_half_width": 0.002,
    "point_systematic_abs_budget": 0.00025,
    "adjacent_delta_abs_budget": 0.0005,
    "reference_systematic_abs_budget": 0.00025,
    "reference_delta_abs_budget": 0.0025,
}
ALLOWED_MITIGATION_MODES = {"none", "bounded_weighted"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

CONTRACT_KEYS = {
    "schema_version",
    "evidence_contract_canonical_sha256",
    "canonicalization",
    "reference_mode",
    "allocation_scope",
    "familywise_error_rate",
    "campaign_attempt_failure_rate",
    "sampling_mode",
    "allowed_mitigation_modes",
    "allocation_by_observable",
    "attempt_budget_semantics",
}
PLAN_KEYS = {
    "schema_version",
    "campaign_id",
    "evidence_contract_canonical_sha256",
    "reference_mode",
    "allocation_scope",
    "cells",
}
CELL_KEYS = {
    "route",
    "R",
    "sampling_mode",
    "mitigation_mode",
    "per_shot_contribution_ranges",
    "acceptance_probability",
    "effective_shot_fraction",
    "sampling_assumption_provenance",
}
FORBIDDEN_DERIVED_OR_ACTUAL_KEYS = {
    "family_size",
    "required_effective_shots",
    "planned_effective_shots",
    "effective_independent_shots",
    "accepted_shots",
    "attempted_shots",
    "actual_effective_shots",
    "actual_accepted_shots",
    "actual_attempted_shots",
}
HIGH_CONFIDENCE_METHOD = "chernoff_lower_tail_half_gap"


def canonical_sha256(value: Any) -> str:
    """Return the pinned canonical JSON SHA256 used by this preflight."""

    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("value cannot be canonicalized as finite JSON") from exc
    return hashlib.sha256(payload).hexdigest()


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    try:
        normalized = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be finite") from None
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _positive(value: Any, name: str) -> float:
    normalized = _finite(value, name)
    if normalized <= 0:
        raise ValueError(f"{name} must be positive")
    return normalized


def _probability(value: Any, name: str) -> float:
    normalized = _positive(value, name)
    if normalized > 1:
        raise ValueError(f"{name} must be in (0, 1]")
    return normalized


def _nonnegative(value: Any, name: str) -> float:
    normalized = _finite(value, name)
    if normalized < 0:
        raise ValueError(f"{name} must be non-negative")
    return normalized


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_probability(value: Any, name: str) -> Optional[float]:
    if value is None:
        return None
    return _probability(value, name)


def _ceil_divided_by_probability(count: int, probability: float) -> int:
    """Compute ceil(count / probability) using the float's exact ratio."""

    numerator, denominator = probability.as_integer_ratio()
    scaled = count * denominator
    return (scaled + numerator - 1) // numerator


def bounded_hoeffding_required_shots(
    width: float, half_width: float, family_size: int, alpha: float
) -> Tuple[float, int]:
    """Return the unrounded and ceiling effective-shot requirements."""

    width = _positive(width, "width")
    half_width = _positive(half_width, "half_width")
    family_size = _positive_int(family_size, "family_size")
    alpha = _probability(alpha, "alpha")
    raw = width * width * math.log(2.0 * family_size / alpha) / (
        2.0 * half_width * half_width
    )
    if not math.isfinite(raw):
        raise ValueError("derived effective-shot requirement must be finite")
    return raw, math.ceil(raw)


def _high_confidence_attempt_cap(
    accepted_shots: int, acceptance_probability: float, beta: float
) -> int:
    """Return a conservative high-confidence attempt cap.

    We use the lower-tail Chernoff bound
    P[X < (1-δ) n p] <= exp(-δ^2 n p / 2)
    with X ~ Bin(n,p). Solving this for n (using a conservative quadratic
    relaxation) gives a guaranteed bound under independent Bernoulli acceptance.
    """

    n_eff = _positive_int(accepted_shots, "accepted_shots")
    p = _probability(acceptance_probability, "acceptance_probability")
    beta = _probability(beta, "campaign_attempt_failure_rate")
    if p >= 1.0:
        return n_eff

    # Let t = n*p, and require t - n_eff >= sqrt(2 * t * log(1/beta))
    # with n = t / p. The conservative closed form for t is:
    # t = A + L + sqrt(L*(A + L)),  A = n_eff, L = log(1/beta).
    # (derived from enforcing (t-A)^2 >= 2 t L, which implies the Chernoff bound).
    log_factor = math.log(1.0 / beta)
    if not math.isfinite(log_factor) or log_factor <= 0:
        raise ValueError("campaign_attempt_failure_rate must imply positive log-factor")
    required_expected = (
        n_eff
        + log_factor
        + math.sqrt(log_factor * (n_eff + log_factor))
    )
    return _ceil_divided_by_probability(required_expected, p)


def bounded_hoeffding_half_width(
    width: float, effective_shots: int, family_size: int, alpha: float
) -> float:
    width = _positive(width, "width")
    effective_shots = _positive_int(effective_shots, "effective_shots")
    family_size = _positive_int(family_size, "family_size")
    alpha = _probability(alpha, "alpha")
    return width * math.sqrt(
        math.log(2.0 * family_size / alpha) / (2.0 * effective_shots)
    )


def _derive_axes(evidence_contract: Mapping[str, Any]) -> Tuple[List[str], List[int], Mapping[str, Any]]:
    required = evidence_contract.get("required_routes")
    route_map = evidence_contract.get("route_map")
    policy = evidence_contract.get("convergence_workload_policy")
    if not isinstance(required, list) or not isinstance(route_map, Mapping):
        raise ValueError("evidence contract route map is invalid")
    if set(route_map) != set(required):
        raise ValueError("evidence contract route_map keys must match required_routes")
    routes: List[str] = []
    for outer_route in required:
        link = route_map.get(outer_route)
        if not isinstance(link, Mapping):
            raise ValueError(f"evidence contract route_map.{outer_route} is invalid")
        convergence_route = _nonempty(
            link.get("convergence_route"),
            f"evidence contract route_map.{outer_route}.convergence_route",
        )
        if convergence_route not in routes:
            routes.append(convergence_route)
    if not isinstance(policy, Mapping):
        raise ValueError("evidence contract convergence_workload_policy is invalid")
    if policy.get("observable_order") != OBSERVABLE_ORDER:
        raise ValueError("evidence contract observable order is invalid")
    raw_rs = policy.get("planned_R_values")
    if not isinstance(raw_rs, list):
        raise ValueError("evidence contract planned_R_values is invalid")
    r_values = [
        _positive_int(value, f"evidence contract planned_R_values[{index}]")
        for index, value in enumerate(raw_rs)
    ]
    if r_values != sorted(set(r_values)):
        raise ValueError("evidence contract planned_R_values must be ordered and unique")
    return routes, r_values, policy


def _validate_contract(
    contract: Mapping[str, Any], evidence_contract: Mapping[str, Any]
) -> List[str]:
    errors: List[str] = []
    if set(contract) != CONTRACT_KEYS:
        errors.append("campaign contract keys do not match schema v1")
    if (
        isinstance(contract.get("schema_version"), bool)
        or not isinstance(contract.get("schema_version"), int)
        or contract.get("schema_version") != 1
    ):
        errors.append("campaign contract schema_version must be 1")
    try:
        canonical_sha256(contract)
    except ValueError:
        errors.append("campaign contract cannot be canonicalized as finite JSON")
        return errors
    try:
        evidence_hash = canonical_sha256(evidence_contract)
    except ValueError:
        errors.append("evidence contract cannot be canonicalized as finite JSON")
        return errors
    pinned_hash = contract.get("evidence_contract_canonical_sha256")
    if not isinstance(pinned_hash, str) or not SHA256_RE.fullmatch(pinned_hash):
        errors.append("campaign contract evidence hash must be lowercase SHA256")
    if pinned_hash != EXPECTED_EVIDENCE_CONTRACT_SHA256:
        errors.append("campaign contract evidence hash is not the pinned L=8 contract")
    if evidence_hash != EXPECTED_EVIDENCE_CONTRACT_SHA256:
        errors.append("evidence contract canonical SHA256 does not match the pinned contract")
    if contract.get("canonicalization") != CANONICALIZATION:
        errors.append(f"campaign contract canonicalization must be {CANONICALIZATION}")
    if contract.get("reference_mode") != EXPECTED_REFERENCE_MODE:
        errors.append(f"campaign contract reference_mode must be {EXPECTED_REFERENCE_MODE}")
    if contract.get("allocation_scope") != EXPECTED_ALLOCATION_SCOPE:
        errors.append(
            f"campaign contract allocation_scope must be {EXPECTED_ALLOCATION_SCOPE}"
        )
    if contract.get("sampling_mode") != "shared_shots":
        errors.append("campaign contract sampling_mode must be shared_shots")
    if contract.get("allowed_mitigation_modes") != ["none", "bounded_weighted"]:
        errors.append("campaign contract allowed_mitigation_modes is invalid")
    if contract.get("attempt_budget_semantics") != "expected_only_not_high_confidence":
        errors.append("campaign contract attempt_budget_semantics is invalid")
    # The pinned hash is the trust boundary.  Do not continue interpreting a
    # drifted evidence object merely to accumulate more schema diagnostics: an
    # untrusted numeric value could otherwise raise while being normalized.
    if evidence_hash != EXPECTED_EVIDENCE_CONTRACT_SHA256:
        return errors
    try:
        alpha = _probability(
            contract["familywise_error_rate"], "contract.familywise_error_rate"
        )
        beta = _probability(
            contract["campaign_attempt_failure_rate"],
            "contract.campaign_attempt_failure_rate",
        )
        if not math.isclose(alpha, EXPECTED_ALPHA, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError(f"contract.familywise_error_rate must equal {EXPECTED_ALPHA}")
        if not math.isclose(beta, EXPECTED_BETA, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError(
                f"contract.campaign_attempt_failure_rate must equal {EXPECTED_BETA}"
            )
        routes, r_values, policy = _derive_axes(evidence_contract)
        if len(routes) != 4 or len(r_values) != 6:
            raise ValueError("pinned evidence contract must derive four routes and six R values")
        if not math.isclose(
            _finite(
                policy.get("familywise_error_rate", -1),
                "evidence policy familywise_error_rate",
            ),
            alpha,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError("campaign alpha does not match evidence policy")
        if policy.get("familywise_method") != "bonferroni_bounded_hoeffding":
            raise ValueError("evidence policy familywise method is invalid")
        allocation = contract.get("allocation_by_observable")
        if not isinstance(allocation, Mapping) or set(allocation) != set(OBSERVABLE_ORDER):
            raise ValueError("contract allocation keys must match observable order")
        observable_contracts = policy.get("observables")
        if not isinstance(observable_contracts, Mapping):
            raise ValueError("evidence observable contracts are invalid")
        allocation_keys = {
            "target_half_width",
            "point_systematic_abs_budget",
            "adjacent_delta_abs_budget",
            "reference_systematic_abs_budget",
            "reference_delta_abs_budget",
        }
        for observable in OBSERVABLE_ORDER:
            row = allocation.get(observable)
            if not isinstance(row, Mapping) or set(row) != allocation_keys:
                raise ValueError(f"contract allocation for {observable} is invalid")
            for field, expected_value in EXPECTED_ALLOCATION.items():
                actual_value = _finite(row[field], f"allocation.{observable}.{field}")
                if not math.isclose(
                    actual_value, expected_value, rel_tol=0.0, abs_tol=1e-15
                ):
                    raise ValueError(
                        f"allocation.{observable}.{field} must equal {expected_value}"
                    )
            h = _positive(row["target_half_width"], f"allocation.{observable}.target")
            point_systematic = _nonnegative(
                row["point_systematic_abs_budget"],
                f"allocation.{observable}.point_systematic",
            )
            adjacent_delta = _nonnegative(
                row["adjacent_delta_abs_budget"],
                f"allocation.{observable}.adjacent_delta",
            )
            reference_systematic = _nonnegative(
                row["reference_systematic_abs_budget"],
                f"allocation.{observable}.reference_systematic",
            )
            reference_delta = _nonnegative(
                row["reference_delta_abs_budget"],
                f"allocation.{observable}.reference_delta",
            )
            observable_policy = observable_contracts.get(observable)
            if not isinstance(observable_policy, Mapping):
                raise ValueError(f"evidence policy for {observable} is invalid")
            statistical_budget = _positive(
                observable_policy["statistical_half_width_budget"],
                f"policy.{observable}.statistical_budget",
            )
            algorithmic_budget = _positive(
                observable_policy["algorithmic_error_budget"],
                f"policy.{observable}.algorithmic_budget",
            )
            if h > statistical_budget:
                raise ValueError(f"allocation for {observable} exceeds point budget")
            pair_total = 2.0 * h + 2.0 * point_systematic + adjacent_delta
            reference_total = h + point_systematic + reference_systematic + reference_delta
            if pair_total > algorithmic_budget + 1e-15:
                raise ValueError(f"allocation for {observable} oversubscribes adjacent budget")
            if reference_total > algorithmic_budget + 1e-15:
                raise ValueError(f"allocation for {observable} oversubscribes reference budget")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(str(exc))
    return errors


def validate_contract(
    contract: Mapping[str, Any], evidence_contract: Mapping[str, Any]
) -> List[str]:
    """Public contract-validation API."""

    if not isinstance(contract, Mapping):
        return ["campaign contract must be an object"]
    if not isinstance(evidence_contract, Mapping):
        return ["evidence contract must be an object"]
    return _validate_contract(contract, evidence_contract)


def _normalize_ranges(
    raw: Any,
    policy: Mapping[str, Any],
    mitigation_mode: str,
    prefix: str,
) -> Dict[str, List[float]]:
    if not isinstance(raw, Mapping) or set(raw) != set(OBSERVABLE_ORDER):
        raise ValueError(f"{prefix} contribution ranges must match observable order")
    result: Dict[str, List[float]] = {}
    observable_contracts = policy["observables"]
    for observable in OBSERVABLE_ORDER:
        interval = raw.get(observable)
        if not isinstance(interval, list) or len(interval) != 2:
            raise ValueError(f"{prefix}.{observable} must contain two values")
        low = _finite(interval[0], f"{prefix}.{observable}[0]")
        high = _finite(interval[1], f"{prefix}.{observable}[1]")
        width = high - low
        if not math.isfinite(width) or width <= 0:
            raise ValueError(f"{prefix}.{observable} must have positive width")
        physical = observable_contracts[observable]["physical_range"]
        physical_interval = [float(physical[0]), float(physical[1])]
        if mitigation_mode == "none" and [low, high] != physical_interval:
            raise ValueError(
                f"{prefix}.{observable} must equal physical range without mitigation"
            )
        if mitigation_mode == "bounded_weighted" and not (
            low <= physical_interval[0] and high >= physical_interval[1]
        ):
            raise ValueError(
                f"{prefix}.{observable} must contain physical range for bounded mitigation"
            )
        result[observable] = [low, high]
    return result


def _family_breakdown(route_count: int, observable_count: int, point_count: int) -> Dict[str, int]:
    point_comparisons = route_count * observable_count * point_count
    pair_comparisons = route_count * observable_count * (point_count - 1)
    reference_comparisons = route_count * observable_count * point_count
    return {
        "point_comparisons": point_comparisons,
        "adjacent_pair_comparisons": pair_comparisons,
        "reference_comparisons": reference_comparisons,
        "family_size": point_comparisons + pair_comparisons + reference_comparisons,
    }


def _physical_floor(
    policy: Mapping[str, Any], family_size: int, alpha: float, half_widths: Mapping[str, float]
) -> Dict[str, Any]:
    raw_by_observable: Dict[str, float] = {}
    required_by_observable: Dict[str, int] = {}
    for observable in OBSERVABLE_ORDER:
        physical = policy["observables"][observable]["physical_range"]
        width = float(physical[1]) - float(physical[0])
        raw, required = bounded_hoeffding_required_shots(
            width, float(half_widths[observable]), family_size, alpha
        )
        raw_by_observable[observable] = raw
        required_by_observable[observable] = required
    joint = max(required_by_observable.values())
    return {
        "target_half_widths": dict(half_widths),
        "unrounded_effective_shots_by_observable": raw_by_observable,
        "required_effective_shots_by_observable": required_by_observable,
        "required_joint_effective_shots_per_cell": joint,
    }


def assess_campaign(
    contract: Mapping[str, Any],
    plan: Mapping[str, Any],
    evidence_contract: Mapping[str, Any],
) -> Dict[str, Any]:
    """Validate and derive a campaign plan without accepting user shot totals."""

    if not isinstance(contract, Mapping):
        return {
            "status": "INVALID_SCHEMA",
            "errors": ["campaign contract must be an object"],
            "cells": [],
        }
    if not isinstance(plan, Mapping):
        return {
            "status": "INVALID_SCHEMA",
            "errors": ["campaign plan must be an object"],
            "cells": [],
        }
    if not isinstance(evidence_contract, Mapping):
        return {
            "status": "INVALID_SCHEMA",
            "errors": ["evidence contract must be an object"],
            "cells": [],
        }
    try:
        canonical_sha256(plan)
    except ValueError:
        return {
            "status": "INVALID_SCHEMA",
            "errors": ["campaign plan cannot be canonicalized as finite JSON"],
            "cells": [],
        }
    contract_errors = validate_contract(contract, evidence_contract)
    if contract_errors:
        return {"status": "INVALID_SCHEMA", "errors": contract_errors, "cells": []}
    errors: List[str] = []
    if set(plan) != PLAN_KEYS:
        errors.append("campaign plan keys do not match schema v1")
    if (
        isinstance(plan.get("schema_version"), bool)
        or not isinstance(plan.get("schema_version"), int)
        or plan.get("schema_version") != 1
    ):
        errors.append("campaign plan schema_version must be 1")
    try:
        _nonempty(plan.get("campaign_id"), "plan.campaign_id")
    except ValueError as exc:
        errors.append(str(exc))
    try:
        evidence_hash = canonical_sha256(evidence_contract)
    except ValueError:
        return {
            "status": "INVALID_SCHEMA",
            "errors": ["evidence contract cannot be canonicalized as finite JSON"],
            "cells": [],
        }
    if plan.get("evidence_contract_canonical_sha256") != evidence_hash:
        errors.append("campaign plan evidence hash does not match evidence contract")
    if plan.get("reference_mode") != contract["reference_mode"]:
        errors.append("campaign plan reference_mode does not match campaign contract")
    if plan.get("allocation_scope") != contract["allocation_scope"]:
        errors.append("campaign plan allocation_scope does not match campaign contract")
    try:
        routes, r_values, policy = _derive_axes(evidence_contract)
    except ValueError as exc:
        return {"status": "INVALID_SCHEMA", "errors": [str(exc)], "cells": []}
    raw_cells = plan.get("cells")
    if not isinstance(raw_cells, list):
        errors.append("campaign plan cells must be a list")
        raw_cells = []
    expected_identities = {(route, r) for route in routes for r in r_values}
    seen_identities = set()
    normalized_cells: List[Dict[str, Any]] = []
    for index, cell in enumerate(raw_cells):
        prefix = f"cells[{index}]"
        if not isinstance(cell, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        forbidden = set(cell) & FORBIDDEN_DERIVED_OR_ACTUAL_KEYS
        if forbidden:
            errors.append(
                f"{prefix} contains derived or actual count fields: "
                + ", ".join(sorted(forbidden))
            )
        if set(cell) != CELL_KEYS:
            errors.append(f"{prefix} keys do not match schema v1")
            continue
        try:
            route = _nonempty(cell["route"], f"{prefix}.route")
            r_value = _positive_int(cell["R"], f"{prefix}.R")
            identity = (route, r_value)
            if identity not in expected_identities:
                raise ValueError(f"{prefix} is not a derived route/R identity")
            if identity in seen_identities:
                raise ValueError(f"{prefix} duplicates route/R identity")
            seen_identities.add(identity)
            if cell["sampling_mode"] != contract["sampling_mode"]:
                raise ValueError(f"{prefix}.sampling_mode must be shared_shots")
            mitigation_mode = _nonempty(
                cell["mitigation_mode"], f"{prefix}.mitigation_mode"
            )
            if mitigation_mode not in ALLOWED_MITIGATION_MODES:
                raise ValueError(f"{prefix}.mitigation_mode is invalid")
            ranges = _normalize_ranges(
                cell["per_shot_contribution_ranges"],
                policy,
                mitigation_mode,
                f"{prefix}.per_shot_contribution_ranges",
            )
            acceptance = _optional_probability(
                cell["acceptance_probability"], f"{prefix}.acceptance_probability"
            )
            effective_fraction = _optional_probability(
                cell["effective_shot_fraction"],
                f"{prefix}.effective_shot_fraction",
            )
            provenance = cell["sampling_assumption_provenance"]
            if acceptance is not None or effective_fraction is not None:
                _nonempty(provenance, f"{prefix}.sampling_assumption_provenance")
            elif not isinstance(provenance, str):
                raise ValueError(f"{prefix}.sampling_assumption_provenance must be a string")
            normalized_cells.append(
                {
                    "route": route,
                    "R": r_value,
                    "sampling_mode": cell["sampling_mode"],
                    "mitigation_mode": mitigation_mode,
                    "per_shot_contribution_ranges": ranges,
                    "acceptance_probability": acceptance,
                    "effective_shot_fraction": effective_fraction,
                    "sampling_assumption_provenance": provenance,
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(str(exc))
    missing = expected_identities - seen_identities
    if missing:
        errors.append(
            "campaign plan is missing route/R cells: "
            + ", ".join(f"{route}@{r}" for route, r in sorted(missing))
        )
    if errors:
        return {"status": "INVALID_SCHEMA", "errors": errors, "cells": []}

    normalized_cells.sort(key=lambda cell: (routes.index(cell["route"]), r_values.index(cell["R"])))
    family = _family_breakdown(len(routes), len(OBSERVABLE_ORDER), len(r_values))
    family_size = family["family_size"]
    alpha = float(contract["familywise_error_rate"])
    point_half_widths = {
        observable: float(policy["observables"][observable]["statistical_half_width_budget"])
        for observable in OBSERVABLE_ORDER
    }
    zero_residual_pair_half_widths = {
        observable: float(policy["observables"][observable]["algorithmic_error_budget"])
        / 2.0
        for observable in OBSERVABLE_ORDER
    }
    allocated_half_widths = {
        observable: float(
            contract["allocation_by_observable"][observable]["target_half_width"]
        )
        for observable in OBSERVABLE_ORDER
    }
    cell_count = len(expected_identities)
    floors = {
        "point_statistical_budget": _physical_floor(
            policy, family_size, alpha, point_half_widths
        ),
        "zero_residual_adjacent_pair": _physical_floor(
            policy, family_size, alpha, zero_residual_pair_half_widths
        ),
        "residual_budgeted_allocation": _physical_floor(
            policy, family_size, alpha, allocated_half_widths
        ),
    }
    for floor in floors.values():
        floor["uniform_campaign_effective_shots"] = (
            floor["required_joint_effective_shots_per_cell"] * cell_count
        )

    output_cells: List[Dict[str, Any]] = []
    total_accepted = 0
    total_expected_attempted = 0
    accepted_complete = True
    attempted_complete = True
    for cell in normalized_cells:
        required_by_observable: Dict[str, int] = {}
        raw_by_observable: Dict[str, float] = {}
        widths: Dict[str, float] = {}
        try:
            for observable in OBSERVABLE_ORDER:
                interval = cell["per_shot_contribution_ranges"][observable]
                width = interval[1] - interval[0]
                widths[observable] = width
                raw, required = bounded_hoeffding_required_shots(
                    width, allocated_half_widths[observable], family_size, alpha
                )
                raw_by_observable[observable] = raw
                required_by_observable[observable] = required
        except ValueError as exc:
            return {
                "status": "INVALID_SCHEMA",
                "errors": [f"{cell['route']}@{cell['R']}: {exc}"],
                "cells": [],
            }
        joint = max(required_by_observable.values())
        eta = cell["effective_shot_fraction"]
        acceptance = cell["acceptance_probability"]
        try:
            planned_accepted = (
                _ceil_divided_by_probability(joint, eta) if eta is not None else None
            )
            expected_attempted = (
                _ceil_divided_by_probability(planned_accepted, acceptance)
                if planned_accepted is not None and acceptance is not None
                else None
            )
        except (OverflowError, ValueError):
            return {
                "status": "INVALID_SCHEMA",
                "errors": [
                    f"derived execution counts for {cell['route']}@{cell['R']} must be finite"
                ],
                "cells": [],
            }
        if planned_accepted is None:
            accepted_complete = False
        else:
            total_accepted += planned_accepted
        if expected_attempted is None:
            attempted_complete = False
        else:
            total_expected_attempted += expected_attempted
        output_cells.append(
            {
                **cell,
                "contribution_widths": widths,
                "unrounded_effective_shots_by_observable": raw_by_observable,
                "planned_effective_shots_by_observable": required_by_observable,
                "planned_joint_effective_shots": joint,
                "planned_accepted_shots": planned_accepted,
                "expected_attempted_shots": expected_attempted,
                "high_confidence_attempt_cap": (
                    _high_confidence_attempt_cap(
                        planned_accepted, acceptance, contract["campaign_attempt_failure_rate"]
                    )
                    if planned_accepted is not None and acceptance is not None
                    else None
                ),
            }
        )
    all_execution_assumptions = accepted_complete and attempted_complete
    status = (
        "EXPECTED_EXECUTION_PLAN_ONLY"
        if all_execution_assumptions
        else "EFFECTIVE_TARGETS_DERIVED_RAW_UNRESOLVED"
    )
    total_joint_effective = sum(
        cell["planned_joint_effective_shots"] for cell in output_cells
    )
    return {
        "status": status,
        "errors": [],
        "evidence_contract_canonical_sha256": evidence_hash,
        "campaign_id": plan["campaign_id"],
        "reference_mode": contract["reference_mode"],
        "allocation_scope": contract["allocation_scope"],
        "derived_axes": {
            "routes": routes,
            "R_values": r_values,
            "observable_order": list(OBSERVABLE_ORDER),
            "route_count": len(routes),
            "R_count": len(r_values),
            "cell_count": cell_count,
        },
        "familywise": {
            **family,
            "familywise_error_rate": alpha,
            "log_factor": math.log(2.0 * family_size / alpha),
            "derivation": "routes * observables * (points + adjacent_pairs + references)",
        },
        "residual_budget_allocation": contract["allocation_by_observable"],
        "floors": floors,
        "cells": output_cells,
        "totals": {
            "planned_joint_effective_shots": total_joint_effective,
            "planned_accepted_shots": total_accepted if accepted_complete else None,
            "expected_attempted_shots": (
                total_expected_attempted if attempted_complete else None
            ),
            "high_confidence_attempt_cap": (
                sum(
                    cell["high_confidence_attempt_cap"]
                    for cell in output_cells
                    if cell["high_confidence_attempt_cap"] is not None
                )
                if all_execution_assumptions
                else None
            ),
        },
        "attempt_budget": {
            "campaign_failure_rate": contract["campaign_attempt_failure_rate"],
            "semantics": contract["attempt_budget_semantics"],
            "high_confidence_method": HIGH_CONFIDENCE_METHOD,
            "high_confidence_warning": (
                "ceiled_attempts is an expected-only planning quantity. high_confidence"
                "_attempt_cap uses a conservative Chernoff lower-tail bound for"
                " failure rate"
            )
            if all_execution_assumptions
            else (
                "high-confidence attempt caps require acceptance_probability and"
                " effective_shot_fraction on every cell"
            ),
        },
        "convergence_certification": "NOT_ASSESSED_BY_PREFLIGHT",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--evidence-contract", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    with args.contract.open(encoding="utf-8") as handle:
        contract = json.load(handle)
    with args.plan.open(encoding="utf-8") as handle:
        plan = json.load(handle)
    with args.evidence_contract.open(encoding="utf-8") as handle:
        evidence_contract = json.load(handle)
    result = assess_campaign(contract, plan, evidence_contract)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"# Measurement campaign preflight: {result['status']}\n")
        if result.get("errors"):
            for error in result["errors"]:
                print(f"- {error}")
        else:
            print(f"- Family size: `{result['familywise']['family_size']}`")
            print(
                "- Planned joint effective shots: "
                f"`{result['totals']['planned_joint_effective_shots']}`"
            )
            if result["totals"]["high_confidence_attempt_cap"] is None:
                print("- High-confidence attempt cap: `not computed`")
            else:
                print(
                    "- High-confidence attempt cap: "
                    f"`{result['totals']['high_confidence_attempt_cap']}` "
                    f"(method: `{result['attempt_budget']['high_confidence_method']}`)"
                )
    if result["status"] == "INVALID_SCHEMA":
        sys.exit(1)


if __name__ == "__main__":
    main()
