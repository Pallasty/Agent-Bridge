#!/usr/bin/env python3
"""Assess dual-observable target-R evidence for the matched Hubbard workload.

Version 2 fixes the observable set and planned R grid in the manifest, validates
same-batch estimator covariance, uses validated independent bounded-sample
intervals for binding decisions, and distinguishes finite-grid screening from a
bound tied to an independent reference. Normal intervals are diagnostic only.
The assessor never upgrades a scalar v1 manifest or invents missing evidence.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import NormalDist
from typing import Any, Dict, List, Mapping, Optional, Sequence


OBSERVABLE_ORDER = ["staggered_magnetization", "double_occupancy"]
BINDING_REFERENCE_KINDS = {"exact_bounded"}
REFERENCE_KINDS = BINDING_REFERENCE_KINDS | {"approximate_unbounded"}
REFERENCE_KINDS.add("stochastic_unbiased")
SAMPLING_MODES = {"shared_shots", "deterministic_simulation"}
CONCENTRATION_MODELS = {"independent_bounded_samples", "unvalidated_samples"}
MITIGATION_MODES = {"none", "bounded_weighted", "unbounded_or_unvalidated"}
BINDING_SYSTEMATIC_STATUSES = {"rigorous_bound", "measured_validated"}
SYSTEMATIC_STATUSES = BINDING_SYSTEMATIC_STATUSES | {
    "derived_unvalidated",
    "assumed",
}
PROVENANCE_FIELDS = (
    "covariance_provenance",
    "measurement_provenance",
    "mitigation_provenance",
    "systematic_bound_provenance",
    "circuit_fingerprint",
    "term_sequence_fingerprint",
)


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _positive(value: Any, name: str) -> float:
    value = _number(value, name)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _nonnegative(value: Any, name: str) -> float:
    value = _number(value, name)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _exact_number_map(value: Any, keys: Sequence[str], name: str) -> Dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != set(keys):
        raise ValueError(f"{name} keys must exactly match observable_order")
    return {key: _number(value[key], f"{name}.{key}") for key in keys}


def _exact_nonnegative_map(
    value: Any, keys: Sequence[str], name: str
) -> Dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != set(keys):
        raise ValueError(f"{name} keys must exactly match observable_order")
    return {key: _nonnegative(value[key], f"{name}.{key}") for key in keys}


def _contribution_ranges(
    value: Any, keys: Sequence[str], name: str
) -> Dict[str, List[float]]:
    if not isinstance(value, Mapping) or set(value) != set(keys):
        raise ValueError(f"{name} keys must exactly match observable_order")
    ranges: Dict[str, List[float]] = {}
    for key in keys:
        raw_range = value[key]
        if not isinstance(raw_range, list) or len(raw_range) != 2:
            raise ValueError(f"{name}.{key} must contain two finite values")
        low = _number(raw_range[0], f"{name}.{key}[0]")
        high = _number(raw_range[1], f"{name}.{key}[1]")
        if low > high:
            raise ValueError(f"{name}.{key} must be ordered low-to-high")
        ranges[key] = [low, high]
    return ranges


def _covariance_matrix(value: Any, size: int, name: str) -> List[List[float]]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{name} must be a {size}x{size} matrix")
    matrix: List[List[float]] = []
    for row_index, row in enumerate(value):
        if not isinstance(row, list) or len(row) != size:
            raise ValueError(f"{name} must be a {size}x{size} matrix")
        matrix.append(
            [
                _number(item, f"{name}[{row_index}][{column_index}]")
                for column_index, item in enumerate(row)
            ]
        )
    for index in range(size):
        if matrix[index][index] < 0:
            raise ValueError(f"{name} diagonal must be non-negative")
        for other in range(index + 1, size):
            scale = max(
                abs(matrix[index][other]),
                abs(matrix[other][index]),
                sys.float_info.min,
            )
            if abs(matrix[index][other] - matrix[other][index]) > 1e-12 * scale:
                raise ValueError(f"{name} must be symmetric")
    if size == 2:
        a, b, d = matrix[0][0], matrix[0][1], matrix[1][1]
        minimum_eigenvalue = 0.5 * (a + d - math.hypot(a - d, 2.0 * b))
        scale = max(a, d, abs(b), sys.float_info.min)
        if minimum_eigenvalue < -1e-12 * scale:
            raise ValueError(f"{name} must be positive semidefinite")
    return matrix


def _metadata_mismatches(
    expected: Mapping[str, Any], actual: Any, route_name: str
) -> List[str]:
    if not isinstance(actual, Mapping):
        return ["metadata must be an object"]
    errors: List[str] = []
    for key in (
        "route",
        "observable_order",
        "measurement_setting",
        "initial_state",
        "initial_state_fingerprint",
        "hamiltonian_fingerprint",
        "evolution_fingerprint",
        "trotter_formula",
        "analysis_plan_fingerprint",
    ):
        expected_value = route_name if key == "route" else expected.get(key)
        if actual.get(key) != expected_value:
            errors.append(f"metadata.{key} does not match the manifest")
    return errors


def _validate_observable_contracts(workload: Mapping[str, Any], errors: List[str]) -> None:
    order = workload.get("observable_order")
    if order != OBSERVABLE_ORDER:
        errors.append(f"workload.observable_order must equal {OBSERVABLE_ORDER}")
        order = OBSERVABLE_ORDER
    observables = workload.get("observables")
    if not isinstance(observables, Mapping) or set(observables) != set(order):
        errors.append("workload.observables keys must exactly match observable_order")
        return
    expected_ranges = {
        "staggered_magnetization": [-1.0, 1.0],
        "double_occupancy": [0.0, 1.0],
    }
    for observable in order:
        contract = observables.get(observable)
        if not isinstance(contract, Mapping):
            errors.append(f"workload.observables.{observable} must be an object")
            continue
        try:
            _nonempty(
                contract["definition_fingerprint"],
                f"workload.observables.{observable}.definition_fingerprint",
            )
            _positive(
                contract["algorithmic_error_budget"],
                f"workload.observables.{observable}.algorithmic_error_budget",
            )
            _nonnegative(
                contract["statistical_half_width_budget"],
                f"workload.observables.{observable}.statistical_half_width_budget",
            )
            physical_range = contract["physical_range"]
            if not isinstance(physical_range, list) or len(physical_range) != 2:
                raise ValueError(
                    f"workload.observables.{observable}.physical_range must have two values"
                )
            normalized_range = [
                _number(value, f"workload.observables.{observable}.physical_range")
                for value in physical_range
            ]
            if normalized_range != expected_ranges[observable]:
                raise ValueError(
                    f"workload.observables.{observable}.physical_range must equal "
                    f"{expected_ranges[observable]}"
                )
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))


def _validate_references(manifest: Mapping[str, Any], errors: List[str]) -> None:
    references = manifest.get("references")
    if references is None:
        return
    order = manifest["workload"].get("observable_order", OBSERVABLE_ORDER)
    if not isinstance(references, Mapping) or set(references) != set(order):
        errors.append("references must be null or contain every observable exactly once")
        return
    observables = manifest["workload"].get("observables", {})
    for observable in order:
        reference = references.get(observable)
        if not isinstance(reference, Mapping):
            errors.append(f"references.{observable} must be an object")
            continue
        try:
            value = _number(reference["value"], f"references.{observable}.value")
            kind = _nonempty(reference["kind"], f"references.{observable}.kind")
            if kind not in REFERENCE_KINDS:
                raise ValueError(f"references.{observable}.kind is invalid")
            _nonnegative(
                reference["standard_error"], f"references.{observable}.standard_error"
            )
            _nonnegative(
                reference["systematic_abs_bound"],
                f"references.{observable}.systematic_abs_bound",
            )
            uncertainty_status = _nonempty(
                reference["uncertainty_evidence_status"],
                f"references.{observable}.uncertainty_evidence_status",
            )
            if uncertainty_status not in SYSTEMATIC_STATUSES:
                raise ValueError(
                    f"references.{observable}.uncertainty_evidence_status is invalid"
                )
            independent = reference["independent_of_route_estimates"]
            if not isinstance(independent, bool):
                raise ValueError(
                    f"references.{observable}.independent_of_route_estimates must be boolean"
                )
            _nonempty(reference["provenance"], f"references.{observable}.provenance")
            observable_contract = observables.get(observable, {})
            identity_fields = {
                "hamiltonian_fingerprint": manifest["workload"].get(
                    "hamiltonian_fingerprint"
                ),
                "initial_state_fingerprint": manifest["workload"].get(
                    "initial_state_fingerprint"
                ),
                "evolution_fingerprint": manifest["workload"].get(
                    "evolution_fingerprint"
                ),
                "observable_definition_fingerprint": observable_contract.get(
                    "definition_fingerprint"
                ),
                "reference_target": "ideal_exact_time_evolution",
            }
            for field, expected in identity_fields.items():
                if reference.get(field) != expected:
                    raise ValueError(
                        f"references.{observable}.{field} does not match workload identity"
                    )
            if kind == "exact_bounded" and float(reference["standard_error"]) != 0.0:
                raise ValueError(
                    f"references.{observable}.exact_bounded requires standard_error=0"
                )
            physical_range = observable_contract.get("physical_range")
            if isinstance(physical_range, list) and len(physical_range) == 2:
                if not float(physical_range[0]) <= value <= float(physical_range[1]):
                    raise ValueError(f"references.{observable}.value is outside physical range")
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))


def validate_manifest(manifest: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if manifest.get("schema_version") != 2:
        errors.append("schema_version must be 2")
    workload = manifest.get("workload")
    if not isinstance(workload, Mapping):
        return ["workload must be an object"]
    _validate_observable_contracts(workload, errors)
    for key in (
        "measurement_setting",
        "initial_state",
        "initial_state_fingerprint",
        "hamiltonian_fingerprint",
        "evolution_fingerprint",
        "trotter_formula",
        "analysis_plan_fingerprint",
    ):
        try:
            _nonempty(workload[key], f"workload.{key}")
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))
    planned = workload.get("planned_R_values")
    normalized_planned: List[int] = []
    if not isinstance(planned, list) or not planned:
        errors.append("workload.planned_R_values must be a non-empty list")
    else:
        for index, value in enumerate(planned):
            try:
                normalized_planned.append(
                    _positive_int(value, f"workload.planned_R_values[{index}]")
                )
            except ValueError as exc:
                errors.append(str(exc))
        if normalized_planned != sorted(set(normalized_planned)):
            errors.append("workload.planned_R_values must be strictly increasing and unique")
        if any(
            right != 2 * left
            for left, right in zip(normalized_planned, normalized_planned[1:])
        ):
            errors.append("workload.planned_R_values must use a fixed refinement ratio of 2")
    try:
        target_r = _positive_int(workload["target_R"], "workload.target_R")
        minimum_intervals = _positive_int(
            workload["minimum_stable_intervals"], "workload.minimum_stable_intervals"
        )
        if minimum_intervals < 2:
            raise ValueError("workload.minimum_stable_intervals must be at least 2")
        if target_r not in normalized_planned:
            raise ValueError("workload.target_R must be in planned_R_values")
        refinements_after_target = len(
            [value for value in normalized_planned if value >= target_r]
        ) - 1
        if refinements_after_target < minimum_intervals:
            raise ValueError("planned_R_values need enough refinements after target_R")
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
    try:
        familywise_error_rate = _positive(
            workload["familywise_error_rate"], "workload.familywise_error_rate"
        )
        if familywise_error_rate >= 1:
            raise ValueError("workload.familywise_error_rate must be less than 1")
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
    if workload.get("familywise_method") != "bonferroni_bounded_hoeffding":
        errors.append("workload.familywise_method must be bonferroni_bounded_hoeffding")
    if workload.get("interval_method") != "bounded_hoeffding_or_deterministic":
        errors.append(
            "workload.interval_method must be bounded_hoeffding_or_deterministic"
        )
    required = manifest.get("required_routes")
    if not isinstance(required, list) or not required or not all(
        isinstance(route, str) and route for route in required
    ):
        errors.append("required_routes must be a non-empty list of route names")
        required = []
    elif len(required) != len(set(required)):
        errors.append("required_routes must contain unique route names")
    routes = manifest.get("routes")
    if not isinstance(routes, Mapping):
        errors.append("routes must be an object keyed by route name")
    else:
        unexpected = set(routes) - set(required)
        if unexpected:
            errors.append("routes contains unexpected entries: " + ", ".join(sorted(unexpected)))
        for route_name, route in routes.items():
            if not isinstance(route_name, str) or not isinstance(route, Mapping):
                errors.append("each routes entry must be a named object")
    _validate_references(manifest, errors)
    return errors


def _references_are_binding(manifest: Mapping[str, Any]) -> bool:
    references = manifest.get("references")
    if not isinstance(references, Mapping):
        return False
    return all(
        isinstance(references.get(observable), Mapping)
        and references[observable].get("kind") in BINDING_REFERENCE_KINDS
        and references[observable].get("independent_of_route_estimates") is True
        and references[observable].get("uncertainty_evidence_status")
        in BINDING_SYSTEMATIC_STATUSES
        for observable in OBSERVABLE_ORDER
    )


def _family_size(manifest: Mapping[str, Any]) -> int:
    route_count = len(manifest["required_routes"])
    observable_count = len(OBSERVABLE_ORDER)
    point_count = len(manifest["workload"]["planned_R_values"])
    comparisons_per_cell = point_count + (point_count - 1)
    if manifest.get("references") is not None:
        comparisons_per_cell += point_count
    return route_count * observable_count * comparisons_per_cell


def _critical_z(manifest: Mapping[str, Any]) -> tuple[int, float]:
    family_size = _family_size(manifest)
    alpha = float(manifest["workload"]["familywise_error_rate"])
    critical_z = NormalDist().inv_cdf(1.0 - alpha / (2.0 * family_size))
    return family_size, critical_z


def _normalize_point(
    manifest: Mapping[str, Any],
    route_name: str,
    route: Mapping[str, Any],
    point: Mapping[str, Any],
    index: int,
    critical_z: float,
    family_size: int,
) -> Dict[str, Any]:
    prefix = f"{route_name}.points[{index}]"
    order = manifest["workload"]["observable_order"]
    r = _positive_int(point["R"], f"{prefix}.R")
    batch_id = _nonempty(point["batch_id"], f"{prefix}.batch_id")
    if point.get("observable_order") != order:
        raise ValueError(f"{prefix}.observable_order does not match the manifest")
    estimates = _exact_number_map(point.get("estimates"), order, f"{prefix}.estimates")
    systematic_bounds = _exact_nonnegative_map(
        point.get("systematic_abs_bounds"), order, f"{prefix}.systematic_abs_bounds"
    )
    covariance = _covariance_matrix(
        point.get("covariance_of_estimator_mean"), len(order), f"{prefix}.covariance"
    )
    attempted = _nonnegative_int(point["attempted_shots"], f"{prefix}.attempted_shots")
    accepted = _nonnegative_int(point["accepted_shots"], f"{prefix}.accepted_shots")
    sampling_mode = route.get("sampling_mode")
    concentration_model = "deterministic"
    concentration_evidence_status = "rigorous_bound"
    mitigation_mode = "none"
    effective_independent_shots = 0
    contribution_ranges = {
        observable: list(manifest["workload"]["observables"][observable]["physical_range"])
        for observable in order
    }
    sampling_bounds_binding = True
    if sampling_mode == "shared_shots":
        if attempted <= 0 or accepted < 2 or accepted > attempted:
            raise ValueError(
                f"{prefix} shared_shots requires attempted_shots >= accepted_shots >= 2"
            )
        effective_independent_shots = _positive_int(
            point["effective_independent_shots"],
            f"{prefix}.effective_independent_shots",
        )
        if effective_independent_shots > accepted:
            raise ValueError(
                f"{prefix}.effective_independent_shots cannot exceed accepted_shots"
            )
        concentration_model = _nonempty(
            point["concentration_model"], f"{prefix}.concentration_model"
        )
        if concentration_model not in CONCENTRATION_MODELS:
            raise ValueError(f"{prefix}.concentration_model is invalid")
        concentration_evidence_status = _nonempty(
            point["concentration_evidence_status"],
            f"{prefix}.concentration_evidence_status",
        )
        if concentration_evidence_status not in SYSTEMATIC_STATUSES:
            raise ValueError(f"{prefix}.concentration_evidence_status is invalid")
        mitigation_mode = _nonempty(
            point["mitigation_mode"], f"{prefix}.mitigation_mode"
        )
        if mitigation_mode not in MITIGATION_MODES:
            raise ValueError(f"{prefix}.mitigation_mode is invalid")
        contribution_ranges = _contribution_ranges(
            point.get("per_shot_contribution_ranges"),
            order,
            f"{prefix}.per_shot_contribution_ranges",
        )
        for observable in order:
            low, high = contribution_ranges[observable]
            if not low <= estimates[observable] <= high:
                raise ValueError(
                    f"{prefix}.per_shot_contribution_ranges.{observable} "
                    "must contain the reported estimate"
                )
        if mitigation_mode == "none":
            physical_ranges = {
                observable: list(
                    manifest["workload"]["observables"][observable]["physical_range"]
                )
                for observable in order
            }
            if contribution_ranges != physical_ranges:
                raise ValueError(
                    f"{prefix}.per_shot_contribution_ranges must equal physical ranges "
                    "when mitigation_mode is none"
                )
        sampling_bounds_binding = (
            concentration_model == "independent_bounded_samples"
            and concentration_evidence_status in BINDING_SYSTEMATIC_STATUSES
            and mitigation_mode in {"none", "bounded_weighted"}
        )
    elif sampling_mode == "deterministic_simulation":
        if attempted != 0 or accepted != 0:
            raise ValueError(f"{prefix} deterministic_simulation requires zero shot counts")
    for field in PROVENANCE_FIELDS:
        _nonempty(point[field], f"{prefix}.{field}")
    systematic_bound_status = _nonempty(
        point["systematic_bound_status"], f"{prefix}.systematic_bound_status"
    )
    if systematic_bound_status not in SYSTEMATIC_STATUSES:
        raise ValueError(f"{prefix}.systematic_bound_status is invalid")
    standard_errors = {
        observable: math.sqrt(max(0.0, covariance[position][position]))
        for position, observable in enumerate(order)
    }
    observables = manifest["workload"]["observables"]
    if sampling_mode == "shared_shots":
        log_factor = math.log(
            2.0 * family_size / float(manifest["workload"]["familywise_error_rate"])
        )
        half_widths = {
            observable: (
                contribution_ranges[observable][1] - contribution_ranges[observable][0]
            )
            * math.sqrt(log_factor / (2.0 * effective_independent_shots))
            for observable in order
        }
    else:
        half_widths = {observable: 0.0 for observable in order}
    for observable in order:
        low, high = observables[observable]["physical_range"]
        if not float(low) <= estimates[observable] <= float(high):
            raise ValueError(f"{prefix}.estimates.{observable} is outside physical range")
    return {
        "R": r,
        "batch_id": batch_id,
        "attempted_shots": attempted,
        "accepted_shots": accepted,
        "effective_independent_shots": effective_independent_shots,
        "observable_order": list(order),
        "estimates": estimates,
        "covariance_of_estimator_mean": covariance,
        "standard_errors": standard_errors,
        "familywise_half_widths": half_widths,
        "systematic_abs_bounds": systematic_bounds,
        "systematic_bound_status": systematic_bound_status,
        "concentration_model": concentration_model,
        "concentration_evidence_status": concentration_evidence_status,
        "per_shot_contribution_ranges": contribution_ranges,
        "mitigation_mode": mitigation_mode,
        "sampling_bounds_binding": sampling_bounds_binding,
        "normal_diagnostic_half_widths": {
            observable: critical_z * standard_errors[observable] for observable in order
        },
        **{field: point[field] for field in PROVENANCE_FIELDS},
    }


def assess_route(
    manifest: Mapping[str, Any],
    route_name: str,
    route: Mapping[str, Any],
    critical_z: float,
    family_size: int,
    binding_references: bool,
) -> Dict[str, Any]:
    workload = manifest["workload"]
    errors = _metadata_mismatches(workload, route.get("metadata"), route_name)
    warnings: List[str] = []
    sampling_mode = route.get("sampling_mode")
    if sampling_mode not in SAMPLING_MODES:
        errors.append(f"{route_name}.sampling_mode is invalid")
    raw_points = route.get("points")
    if not isinstance(raw_points, list) or not raw_points:
        return {
            "route": route_name,
            "status": "UNRESOLVED_NO_POINTS",
            "errors": errors,
            "warnings": ["no planned R-grid points supplied"],
            "stable_from_R": None,
            "stable_from_R_by_observable": {},
            "points": [],
        }
    normalized: List[Dict[str, Any]] = []
    seen_r = set()
    seen_batches = set()
    for index, point in enumerate(raw_points):
        if not isinstance(point, Mapping):
            errors.append(f"point {index} is not an object")
            continue
        try:
            normalized_point = _normalize_point(
                manifest, route_name, route, point, index, critical_z, family_size
            )
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))
            continue
        r = normalized_point["R"]
        batch_id = normalized_point["batch_id"]
        if r in seen_r:
            errors.append(f"duplicate R={r}")
        if batch_id in seen_batches:
            errors.append(f"duplicate batch_id={batch_id}")
        seen_r.add(r)
        seen_batches.add(batch_id)
        normalized.append(normalized_point)
    normalized.sort(key=lambda point: point["R"])
    planned = workload["planned_R_values"]
    if [point["R"] for point in normalized] != planned:
        errors.append("route R values must exactly match workload.planned_R_values")
    observable_results: Dict[str, Any] = {}
    stable_by_observable: Dict[str, int] = {}
    references = manifest.get("references")
    minimum_intervals = int(workload["minimum_stable_intervals"])
    for observable in workload["observable_order"]:
        observable_contract = workload["observables"][observable]
        algorithmic_budget = float(observable_contract["algorithmic_error_budget"])
        statistical_budget = float(observable_contract["statistical_half_width_budget"])
        point_checks = [
            {
                "R": point["R"],
                "estimate": point["estimates"][observable],
                "standard_error": point["standard_errors"][observable],
                "familywise_half_width": point["familywise_half_widths"][observable],
                "systematic_abs_bound": point["systematic_abs_bounds"][observable],
                "passes_statistical_budget": point["familywise_half_widths"][observable]
                <= statistical_budget,
            }
            for point in normalized
        ]
        pair_checks = []
        for left, right in zip(normalized, normalized[1:]):
            delta = abs(right["estimates"][observable] - left["estimates"][observable])
            bound = (
                delta
                + left["familywise_half_widths"][observable]
                + right["familywise_half_widths"][observable]
                + left["systematic_abs_bounds"][observable]
                + right["systematic_abs_bounds"][observable]
            )
            pair_checks.append(
                {
                    "from_R": left["R"],
                    "to_R": right["R"],
                    "absolute_delta": delta,
                    "simultaneous_bound": bound,
                    "passes_algorithmic_budget": bound <= algorithmic_budget,
                }
            )
        reference_checks = []
        if isinstance(references, Mapping):
            reference = references[observable]
            reference_half_width = critical_z * float(reference["standard_error"])
            for point in normalized:
                bound = (
                    abs(point["estimates"][observable] - float(reference["value"]))
                    + point["familywise_half_widths"][observable]
                    + reference_half_width
                    + point["systematic_abs_bounds"][observable]
                    + float(reference["systematic_abs_bound"])
                )
                reference_checks.append(
                    {
                        "R": point["R"],
                        "kind": reference["kind"],
                        "simultaneous_bound": bound,
                        "binding": binding_references,
                        "passes_algorithmic_budget": bound <= algorithmic_budget,
                    }
                )
        stable_from: Optional[int] = None
        for start in range(max(0, len(normalized) - minimum_intervals)):
            later_pairs = pair_checks[start:]
            if len(later_pairs) < minimum_intervals or not all(
                check["passes_algorithmic_budget"] for check in later_pairs
            ):
                continue
            if not all(check["passes_statistical_budget"] for check in point_checks[start:]):
                continue
            if binding_references and not all(
                check["passes_algorithmic_budget"] for check in reference_checks[start:]
            ):
                continue
            stable_from = normalized[start]["R"]
            break
        if stable_from is None:
            warnings.append(f"{observable} has no joint stability window")
        else:
            stable_by_observable[observable] = stable_from
        observable_results[observable] = {
            "stable_from_R": stable_from,
            "point_checks": point_checks,
            "pair_checks": pair_checks,
            "reference_checks": reference_checks,
        }
    stable_from_R: Optional[int] = None
    if len(stable_by_observable) == len(OBSERVABLE_ORDER):
        stable_from_R = max(stable_by_observable.values())
    target_r = workload["target_R"]
    target_ready = stable_from_R is not None and target_r >= stable_from_R
    if stable_from_R is not None and not target_ready:
        warnings.append(
            f"target R={target_r} is earlier than joint stable_from_R={stable_from_R}"
        )
    status = "VALIDATED" if not errors and target_ready else "UNRESOLVED"
    systematic_bounds_binding = bool(normalized) and all(
        point["systematic_bound_status"] in BINDING_SYSTEMATIC_STATUSES
        for point in normalized
    )
    sampling_bounds_binding = bool(normalized) and all(
        point["sampling_bounds_binding"] is True for point in normalized
    )
    return {
        "route": route_name,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "sampling_mode": sampling_mode,
        "points": normalized,
        "observables": observable_results,
        "stable_from_R_by_observable": stable_by_observable,
        "stable_from_R": stable_from_R,
        "target_R": target_r,
        "target_ready": target_ready,
        "systematic_bounds_binding": systematic_bounds_binding,
        "sampling_bounds_binding": sampling_bounds_binding,
    }


def assess_manifest(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    schema_errors = validate_manifest(manifest)
    if schema_errors:
        return {"status": "INVALID_SCHEMA", "errors": schema_errors, "routes": {}}
    family_size, critical_z = _critical_z(manifest)
    binding_references = _references_are_binding(manifest)
    required = manifest["required_routes"]
    routes = manifest["routes"]
    route_results: Dict[str, Any] = {}
    missing = []
    for route_name in required:
        if route_name not in routes:
            missing.append(route_name)
        else:
            route_results[route_name] = assess_route(
                manifest,
                route_name,
                routes[route_name],
                critical_z,
                family_size,
                binding_references,
            )
    seen_batches: Dict[str, str] = {}
    seen_circuits: Dict[str, tuple[str, int]] = {}
    for route_name, result in route_results.items():
        for point in result.get("points", []):
            batch_id = point["batch_id"]
            circuit_fingerprint = point["circuit_fingerprint"]
            if batch_id in seen_batches and seen_batches[batch_id] != route_name:
                result["errors"].append(
                    f"batch_id {batch_id} is reused from route {seen_batches[batch_id]}"
                )
            else:
                seen_batches[batch_id] = route_name
            if circuit_fingerprint in seen_circuits:
                owner_route, owner_r = seen_circuits[circuit_fingerprint]
                result["errors"].append(
                    f"circuit_fingerprint is reused from route {owner_route}, R={owner_r}"
                )
            else:
                seen_circuits[circuit_fingerprint] = (route_name, point["R"])
        if result.get("errors"):
            result["status"] = "UNRESOLVED"
    stable = {
        name: result["stable_from_R"]
        for name, result in route_results.items()
        if result["status"] == "VALIDATED" and result["stable_from_R"] is not None
    }
    common_errors: List[str] = []
    if missing:
        common_errors.append(f"missing required routes: {', '.join(missing)}")
    if len(stable) != len(required):
        unresolved = [name for name in required if name not in stable]
        common_errors.append(
            f"routes without target-ready joint stability: {', '.join(unresolved)}"
        )
    common_R: Optional[int] = max(stable.values()) if stable else None
    target_r = manifest["workload"]["target_R"]
    if common_R is not None and target_r < common_R:
        common_errors.append(
            f"target R={target_r} is earlier than minimum common stable R={common_R}"
        )
    if not common_errors:
        for name in required:
            point_rs = {point["R"] for point in route_results[name]["points"]}
            if target_r not in point_rs:
                common_errors.append(
                    f"route {name} has no complete vector at target R={target_r}"
                )
    if common_errors:
        status = "UNRESOLVED"
        evidence_level = "UNRESOLVED"
    systematic_bounds_binding = len(route_results) == len(required) and all(
        result.get("systematic_bounds_binding") is True for result in route_results.values()
    )
    sampling_bounds_binding = len(route_results) == len(required) and all(
        result.get("sampling_bounds_binding") is True for result in route_results.values()
    )
    if (
        not common_errors
        and binding_references
        and systematic_bounds_binding
        and sampling_bounds_binding
    ):
        status = "READY_FOR_TARGET_R"
        evidence_level = "SIMULTANEOUSLY_BOUNDED_TO_INDEPENDENT_REFERENCE_ON_DECLARED_GRID"
    elif not common_errors:
        status = "SCREENED_FOR_TARGET_R"
        evidence_level = "EMPIRICALLY_STABLE_ON_DECLARED_GRID"
    if binding_references:
        reference_mode = "binding"
    elif manifest.get("references"):
        reference_mode = "diagnostic"
    else:
        reference_mode = "none"
    return {
        "status": status,
        "errors": [],
        "target_R": target_r,
        "common_R": common_R,
        "route_stable_from_R": stable,
        "stable_from_R_by_route_observable": {
            name: result.get("stable_from_R_by_observable", {})
            for name, result in route_results.items()
        },
        "common_errors": common_errors,
        "routes": route_results,
        "reference_mode": reference_mode,
        "binding_eligibility": {
            "independent_bounded_references": binding_references,
            "route_systematic_bounds": systematic_bounds_binding,
            "sampling_concentration": sampling_bounds_binding,
        },
        "familywise": {
            "method": manifest["workload"]["familywise_method"],
            "familywise_error_rate": manifest["workload"]["familywise_error_rate"],
            "family_size": family_size,
            "normal_diagnostic_z": critical_z,
            "binding_interval": "bounded_hoeffding_or_deterministic",
        },
        "evidence_level": evidence_level,
        "coverage_scope": list(OBSERVABLE_ORDER),
        "workload_identity": manifest["workload"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    with args.manifest.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    result = assess_manifest(manifest)
    if args.format == "markdown":
        print(f"# Dual-observable target-R assessment: {result['status']}\n")
        print(f"Target R: `{result.get('target_R')}`")
        print(f"Minimum common stable R: `{result.get('common_R')}`")
        if result.get("familywise"):
            print(f"Family size: `{result['familywise']['family_size']}`")
            print(
                "Normal diagnostic z: "
                f"`{result['familywise']['normal_diagnostic_z']:.8g}`"
            )
        if result.get("common_errors"):
            unresolved = "\n".join(f"- {item}" for item in result["common_errors"])
            print("\nUnresolved conditions:\n" + unresolved)
        for name, route in result.get("routes", {}).items():
            print(f"\n## {name}: {route['status']}\n")
            print(f"Joint stable from R: `{route['stable_from_R']}`")
            for observable, stable_from in route.get("stable_from_R_by_observable", {}).items():
                print(f"- `{observable}` stable from R: `{stable_from}`")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result.get("status") != "INVALID_SCHEMA" else 1)


if __name__ == "__main__":
    main()
