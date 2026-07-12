#!/usr/bin/env python3
"""Validate bounded-reference qualification for the matched Hubbard workload.

The ledger records reference values; it does not generate or qualify them.  A
binding-looking record must have a verified local hash, a JSON artifact whose
content binds every decision-relevant field, a complete error decomposition, and
an externally supplied route-input snapshot.  No fixed machine checker exists,
so even a complete record is only ``STRUCTURALLY_COMPLETE_UNVERIFIED``.  That
state does not establish that ``total_abs_bound`` fits the campaign reference
allocation and is never eligible for a convergence or benchmark READY gate.
Certificate JSON is parsed as data and is never imported, evaluated, or executed.
Uncertified tensor-network, Krylov, and stochastic methods remain diagnostic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


HERE = Path(__file__).resolve().parent
EVIDENCE_CONTRACT = HERE / "evidence_manifest_contract.json"

BINDING_METHOD_CLASSES = {
    "exact_diagonalization",
    "certified_operator_propagation",
    "certified_tensor_network",
    "certified_locality_bound",
    "other_rigorous",
}
DIAGNOSTIC_METHOD_CLASSES = {
    "uncertified_tensor_network",
    "uncertified_krylov",
    "stochastic_estimator",
    "other_unbounded",
}
REQUIRED_ERROR_COMPONENTS = (
    "time_evolution",
    "representation_truncation",
    "floating_point",
    "observable_evaluation",
)
REFERENCE_TARGET = "ideal_exact_time_evolution"
BOUNDARY_CONDITION_FINGERPRINT = "square_lattice_L8_open_boundary_v1"
HAMILTONIAN_CONVENTION_FINGERPRINT = (
    "spinful_FH_minus_t_hopping_plus_U_nup_ndown_unshifted_v1"
)
QUALIFICATION_POLICY_FINGERPRINT = (
    "reference_qualification_v2_structural_unverified_json_binding"
)
BINDING_CERTIFICATE_CLAIM = "rigorous_absolute_error_bound"
CERTIFICATE_CLAIMS = {BINDING_CERTIFICATE_CLAIM, "diagnostic_only"}
BINDING_ROUNDING_MODE = "directed_interval"
METHOD_CLAIM_REQUIREMENTS = {
    "exact_diagonalization": ("full_target_sector_covered",),
    "certified_operator_propagation": (
        "deduplicate_before_truncation",
        "dropped_l1_ledger_included",
        "product_formula_bound_included",
    ),
    "certified_tensor_network": (
        "state_norm_bound_included",
        "contraction_bound_included",
    ),
    "certified_locality_bound": (
        "locality_tail_bound_included",
        "solver_defect_bound_included",
    ),
    "other_rigorous": ("external_checker_passed",),
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMPLEMENTATION_COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
MAXIMUM_POSITIVE_STATUS = "STRUCTURALLY_COMPLETE_UNVERIFIED"
ALLOWED_STATUSES = frozenset(
    {
        "INVALID_SCHEMA",
        "UNRESOLVED",
        "DIAGNOSTIC_ONLY",
        "STRUCTURALLY_COMPLETE_UNVERIFIED",
    }
)
CERTIFICATE_BOUND_FIELDS = (
    "observable",
    "value",
    "total_abs_bound",
    "error_decomposition",
    "hamiltonian_fingerprint",
    "initial_state_fingerprint",
    "evolution_fingerprint",
    "observable_definition_fingerprint",
    "reference_target",
    "boundary_condition_fingerprint",
    "hamiltonian_convention_fingerprint",
    "reference_formula_fingerprint",
    "reference_term_sequence_fingerprint",
    "method_class",
    "method_description",
    "solver_fingerprint",
    "configuration_fingerprint",
    "certificate_checker_fingerprint",
    "implementation_commit",
    "environment_lock_sha256",
    "theorem_and_assumptions_fingerprint",
    "rounding_mode",
    "method_claims",
    "certificate_claim",
    "independent_of_route_estimates",
    "independence_provenance",
    "input_fingerprints",
    "provenance",
)


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _nonnegative(value: Any, name: str) -> float:
    result = _finite(value, name)
    if result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def _unique_strings(value: Any, name: str, *, allow_empty: bool) -> List[str]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    result = [_nonempty(item, f"{name}[{index}]") for index, item in enumerate(value)]
    if not allow_empty and not result:
        raise ValueError(f"{name} must be non-empty")
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must contain unique fingerprints")
    return result


def _expected_convergence_policy() -> Mapping[str, Any]:
    with EVIDENCE_CONTRACT.open(encoding="utf-8") as handle:
        evidence_contract = json.load(handle)
    policy = evidence_contract.get("convergence_workload_policy")
    if not isinstance(policy, Mapping):
        raise ValueError("evidence convergence_workload_policy is unavailable")
    return policy


def validate_contract(
    contract: Any,
    convergence_policy: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    """Return contract errors, including drift from the evidence policy."""

    if not isinstance(contract, Mapping):
        return ["contract must be an object"]
    errors: List[str] = []
    if (
        isinstance(contract.get("schema_version"), bool)
        or not isinstance(contract.get("schema_version"), int)
        or contract.get("schema_version") != 1
    ):
        errors.append("contract schema_version must be 1")
    try:
        expected_policy = convergence_policy or _expected_convergence_policy()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
        expected_policy = None
    if expected_policy is not None and not _type_exact_json_equal(
        contract.get("workload"), expected_policy
    ):
        errors.append(
            "contract workload must exactly match evidence convergence_workload_policy"
        )
    if contract.get("reference_target") != REFERENCE_TARGET:
        errors.append(f"contract reference_target must be {REFERENCE_TARGET}")
    if contract.get("boundary_condition_fingerprint") != BOUNDARY_CONDITION_FINGERPRINT:
        errors.append("contract boundary_condition_fingerprint does not match policy")
    if (
        contract.get("hamiltonian_convention_fingerprint")
        != HAMILTONIAN_CONVENTION_FINGERPRINT
    ):
        errors.append("contract hamiltonian_convention_fingerprint does not match policy")
    if contract.get("qualification_policy_fingerprint") != QUALIFICATION_POLICY_FINGERPRINT:
        errors.append("contract qualification_policy_fingerprint does not match validator policy")
    binding_methods = contract.get("binding_method_classes")
    if (
        not isinstance(binding_methods, list)
        or len(binding_methods) != len(BINDING_METHOD_CLASSES)
        or set(binding_methods) != BINDING_METHOD_CLASSES
    ):
        errors.append("contract binding_method_classes do not match validator policy")
    diagnostic_methods = contract.get("diagnostic_method_classes")
    if (
        not isinstance(diagnostic_methods, list)
        or len(diagnostic_methods) != len(DIAGNOSTIC_METHOD_CLASSES)
        or set(diagnostic_methods) != DIAGNOSTIC_METHOD_CLASSES
    ):
        errors.append("contract diagnostic_method_classes do not match validator policy")
    if contract.get("required_error_components") != list(REQUIRED_ERROR_COMPONENTS):
        errors.append("contract required_error_components do not match validator policy")
    if contract.get("binding_rounding_mode") != BINDING_ROUNDING_MODE:
        errors.append("contract binding_rounding_mode does not match validator policy")
    claim_requirements = contract.get("method_claim_requirements")
    expected_claim_requirements = {
        method: list(claims) for method, claims in METHOD_CLAIM_REQUIREMENTS.items()
    }
    if claim_requirements != expected_claim_requirements:
        errors.append("contract method_claim_requirements do not match validator policy")
    if contract.get("binding_certificate_claim") != BINDING_CERTIFICATE_CLAIM:
        errors.append("contract binding_certificate_claim does not match validator policy")
    if contract.get("certificate_hash_algorithm") != "sha256":
        errors.append("contract certificate_hash_algorithm must be sha256")
    if contract.get("certificate_format") != "json_record_binding_v1":
        errors.append("contract certificate_format must be json_record_binding_v1")
    if contract.get("machine_checker_policy") != "none_structural_validation_only":
        errors.append("contract machine_checker_policy must disable qualification")
    if contract.get("bound_budget_policy") != "not_assessed_no_campaign_contract":
        errors.append("contract bound_budget_policy must leave adequacy unassessed")
    if contract.get("maximum_positive_status") != MAXIMUM_POSITIVE_STATUS:
        errors.append("contract maximum_positive_status does not match validator policy")
    return errors


def _parse_route_inputs(value: Any, name: str) -> Tuple[Set[str], List[str]]:
    errors: List[str] = []
    if not isinstance(value, Mapping):
        return set(), [f"{name} must be an object"]
    if set(value) != {"batch_fingerprints", "circuit_fingerprints"}:
        errors.append(
            f"{name} keys must exactly equal batch_fingerprints and circuit_fingerprints"
        )
    inputs: List[str] = []
    for field in ("batch_fingerprints", "circuit_fingerprints"):
        try:
            inputs.extend(
                _unique_strings(value.get(field), f"{name}.{field}", allow_empty=True)
            )
        except ValueError as exc:
            errors.append(str(exc))
    if len(inputs) != len(set(inputs)):
        errors.append(f"{name} fingerprints must be globally unique")
    return set(inputs), errors


def _ledger_header_errors(contract: Mapping[str, Any], ledger: Mapping[str, Any]) -> List[str]:
    workload = contract.get("workload", {})
    expected = {
        "schema_version": 1,
        "workload_fingerprint": workload.get("hamiltonian_fingerprint"),
        "initial_state_fingerprint": workload.get("initial_state_fingerprint"),
        "evolution_fingerprint": workload.get("evolution_fingerprint"),
        "analysis_plan_fingerprint": workload.get("analysis_plan_fingerprint"),
        "reference_target": contract.get("reference_target"),
        "boundary_condition_fingerprint": contract.get(
            "boundary_condition_fingerprint"
        ),
        "hamiltonian_convention_fingerprint": contract.get(
            "hamiltonian_convention_fingerprint"
        ),
        "qualification_policy_fingerprint": contract.get(
            "qualification_policy_fingerprint"
        ),
        "observable_order": workload.get("observable_order"),
    }
    errors = [
        f"ledger {field} does not match contract"
        for field, expected_value in expected.items()
        if ledger.get(field) != expected_value
    ]
    if isinstance(ledger.get("schema_version"), bool):
        errors.append("ledger schema_version must be integer 1")
    return errors


def _reject_duplicate_object_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_nonfinite_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _type_exact_json_equal(left: Any, right: Any) -> bool:
    """Compare parsed JSON without Python's bool/int or int/float coercions."""

    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(
            _type_exact_json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _type_exact_json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def _certificate_error(
    artifact_root: Path,
    artifact_name: str,
    expected_sha256: str,
    expected_binding: Mapping[str, Any],
    prefix: str,
) -> Optional[str]:
    relative_path = Path(artifact_name)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return f"{prefix}.certificate_artifact must be a safe relative path"
    if relative_path.suffix != ".json":
        return f"{prefix}.certificate_artifact must be a JSON file"
    root = artifact_root.resolve()
    artifact = (root / relative_path).resolve()
    try:
        artifact.relative_to(root)
    except ValueError:
        return f"{prefix}.certificate_artifact escapes artifact_root"
    if not artifact.is_file():
        return f"{prefix}.certificate_artifact is not a local file"
    try:
        artifact_bytes = artifact.read_bytes()
    except OSError:
        return f"{prefix}.certificate_artifact could not be read"
    digest = hashlib.sha256(artifact_bytes).hexdigest()
    if digest != expected_sha256:
        return f"{prefix}.certificate_sha256 does not match local artifact"
    try:
        certificate = json.loads(
            artifact_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_nonfinite_json_constant,
        )
    except (RecursionError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return f"{prefix}.certificate_artifact must contain strict UTF-8 JSON"
    if not isinstance(certificate, Mapping) or set(certificate) != {
        "schema_version",
        "record_binding",
        "method_specific_details",
    }:
        return f"{prefix}.certificate_artifact JSON schema is invalid"
    if (
        isinstance(certificate.get("schema_version"), bool)
        or not isinstance(certificate.get("schema_version"), int)
        or certificate.get("schema_version") != 1
    ):
        return f"{prefix}.certificate_artifact schema_version must be integer 1"
    try:
        binding_matches = _type_exact_json_equal(
            certificate.get("record_binding"), expected_binding
        )
    except RecursionError:
        binding_matches = False
    if not binding_matches:
        return f"{prefix}.certificate_artifact record_binding does not match ledger"
    if not isinstance(certificate.get("method_specific_details"), Mapping):
        return f"{prefix}.certificate_artifact method_specific_details must be an object"
    return None


def _assess_reference(
    contract: Mapping[str, Any],
    observable: str,
    reference: Mapping[str, Any],
    artifact_root: Path,
    route_inputs: Set[str],
    external_route_snapshot_supplied: bool,
) -> Dict[str, Any]:
    prefix = f"references.{observable}"
    workload = contract["workload"]
    observable_contract = workload["observables"][observable]
    identity_expected = {
        "observable": observable,
        "hamiltonian_fingerprint": workload["hamiltonian_fingerprint"],
        "initial_state_fingerprint": workload["initial_state_fingerprint"],
        "evolution_fingerprint": workload["evolution_fingerprint"],
        "observable_definition_fingerprint": observable_contract[
            "definition_fingerprint"
        ],
        "reference_target": contract["reference_target"],
        "boundary_condition_fingerprint": contract[
            "boundary_condition_fingerprint"
        ],
        "hamiltonian_convention_fingerprint": contract[
            "hamiltonian_convention_fingerprint"
        ],
    }
    identity_errors = [
        f"{prefix}.{field} does not match contract identity"
        for field, expected in identity_expected.items()
        if reference.get(field) != expected
    ]
    errors: List[str] = []
    diagnostic_reasons: List[str] = []
    normalized: Dict[str, Any] = {}
    try:
        value = _finite(reference["value"], f"{prefix}.value")
        low, high = observable_contract["physical_range"]
        if not float(low) <= value <= float(high):
            raise ValueError(f"{prefix}.value is outside the observable physical range")
        method_class = _nonempty(reference["method_class"], f"{prefix}.method_class")
        if method_class not in BINDING_METHOD_CLASSES | DIAGNOSTIC_METHOD_CLASSES:
            raise ValueError(f"{prefix}.method_class is not allowed by the contract")
        method_description = _nonempty(
            reference["method_description"], f"{prefix}.method_description"
        )
        solver_fingerprint = _nonempty(
            reference["solver_fingerprint"], f"{prefix}.solver_fingerprint"
        )
        configuration_fingerprint = _nonempty(
            reference["configuration_fingerprint"],
            f"{prefix}.configuration_fingerprint",
        )
        reference_formula_fingerprint = _nonempty(
            reference["reference_formula_fingerprint"],
            f"{prefix}.reference_formula_fingerprint",
        )
        reference_term_sequence_fingerprint = _nonempty(
            reference["reference_term_sequence_fingerprint"],
            f"{prefix}.reference_term_sequence_fingerprint",
        )
        certificate_checker_fingerprint = _nonempty(
            reference["certificate_checker_fingerprint"],
            f"{prefix}.certificate_checker_fingerprint",
        )
        implementation_commit = _nonempty(
            reference["implementation_commit"], f"{prefix}.implementation_commit"
        )
        if not IMPLEMENTATION_COMMIT_RE.fullmatch(implementation_commit):
            raise ValueError(
                f"{prefix}.implementation_commit must be a full lowercase commit hash"
            )
        environment_lock_sha256 = _nonempty(
            reference["environment_lock_sha256"],
            f"{prefix}.environment_lock_sha256",
        )
        if not SHA256_RE.fullmatch(environment_lock_sha256):
            raise ValueError(
                f"{prefix}.environment_lock_sha256 must be lowercase SHA-256"
            )
        theorem_and_assumptions_fingerprint = _nonempty(
            reference["theorem_and_assumptions_fingerprint"],
            f"{prefix}.theorem_and_assumptions_fingerprint",
        )
        rounding_mode = _nonempty(
            reference["rounding_mode"], f"{prefix}.rounding_mode"
        )
        method_claims = reference["method_claims"]
        if not isinstance(method_claims, Mapping):
            raise ValueError(f"{prefix}.method_claims must be an object")
        normalized_method_claims: Dict[str, bool] = {}
        for claim, enabled in method_claims.items():
            claim_name = _nonempty(claim, f"{prefix}.method_claims key")
            if not isinstance(enabled, bool):
                raise ValueError(f"{prefix}.method_claims.{claim_name} must be boolean")
            normalized_method_claims[claim_name] = enabled
        certificate_artifact = _nonempty(
            reference["certificate_artifact"], f"{prefix}.certificate_artifact"
        )
        certificate_sha256 = _nonempty(
            reference["certificate_sha256"], f"{prefix}.certificate_sha256"
        )
        if not SHA256_RE.fullmatch(certificate_sha256):
            raise ValueError(f"{prefix}.certificate_sha256 must be lowercase SHA-256")
        certificate_claim = _nonempty(
            reference["certificate_claim"], f"{prefix}.certificate_claim"
        )
        if certificate_claim not in CERTIFICATE_CLAIMS:
            raise ValueError(f"{prefix}.certificate_claim is invalid")
        total_abs_bound = _nonnegative(
            reference["total_abs_bound"], f"{prefix}.total_abs_bound"
        )
        decomposition = reference["error_decomposition"]
        if not isinstance(decomposition, Mapping) or set(decomposition) != set(
            REQUIRED_ERROR_COMPONENTS
        ):
            raise ValueError(
                f"{prefix}.error_decomposition keys must exactly match the contract"
            )
        normalized_decomposition = {
            component: _nonnegative(
                decomposition[component], f"{prefix}.error_decomposition.{component}"
            )
            for component in REQUIRED_ERROR_COMPONENTS
        }
        try:
            component_sum = math.fsum(normalized_decomposition.values())
        except OverflowError as exc:
            raise ValueError(
                f"{prefix}.error_decomposition sum must be finite"
            ) from exc
        if not math.isfinite(component_sum):
            raise ValueError(f"{prefix}.error_decomposition sum must be finite")
        if component_sum > total_abs_bound:
            raise ValueError(
                f"{prefix}.error_decomposition sum exceeds total_abs_bound"
            )
        independent = reference["independent_of_route_estimates"]
        if not isinstance(independent, bool):
            raise ValueError(f"{prefix}.independent_of_route_estimates must be boolean")
        independence_provenance = _nonempty(
            reference["independence_provenance"],
            f"{prefix}.independence_provenance",
        )
        input_fingerprints = _unique_strings(
            reference["input_fingerprints"],
            f"{prefix}.input_fingerprints",
            allow_empty=False,
        )
        provenance = _nonempty(reference["provenance"], f"{prefix}.provenance")
        expected_certificate_binding = {
            "observable": reference.get("observable"),
            "value": value,
            "total_abs_bound": total_abs_bound,
            "error_decomposition": normalized_decomposition,
            "hamiltonian_fingerprint": reference.get("hamiltonian_fingerprint"),
            "initial_state_fingerprint": reference.get("initial_state_fingerprint"),
            "evolution_fingerprint": reference.get("evolution_fingerprint"),
            "observable_definition_fingerprint": reference.get(
                "observable_definition_fingerprint"
            ),
            "reference_target": reference.get("reference_target"),
            "boundary_condition_fingerprint": reference.get(
                "boundary_condition_fingerprint"
            ),
            "hamiltonian_convention_fingerprint": reference.get(
                "hamiltonian_convention_fingerprint"
            ),
            "reference_formula_fingerprint": reference_formula_fingerprint,
            "reference_term_sequence_fingerprint": (
                reference_term_sequence_fingerprint
            ),
            "method_class": method_class,
            "method_description": method_description,
            "solver_fingerprint": solver_fingerprint,
            "configuration_fingerprint": configuration_fingerprint,
            "certificate_checker_fingerprint": certificate_checker_fingerprint,
            "implementation_commit": implementation_commit,
            "environment_lock_sha256": environment_lock_sha256,
            "theorem_and_assumptions_fingerprint": (
                theorem_and_assumptions_fingerprint
            ),
            "rounding_mode": rounding_mode,
            "method_claims": normalized_method_claims,
            "certificate_claim": certificate_claim,
            "independent_of_route_estimates": independent,
            "independence_provenance": independence_provenance,
            "input_fingerprints": input_fingerprints,
            "provenance": provenance,
        }
        certificate_problem = _certificate_error(
            artifact_root,
            certificate_artifact,
            certificate_sha256,
            expected_certificate_binding,
            prefix,
        )
        if certificate_problem:
            raise ValueError(certificate_problem)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(str(exc))
        return {
            "status": "UNRESOLVED",
            "errors": errors,
            "identity_errors": identity_errors,
            "diagnostic_reasons": diagnostic_reasons,
        }

    if method_class in DIAGNOSTIC_METHOD_CLASSES:
        diagnostic_reasons.append(f"method_class {method_class} is diagnostic-only")
    if method_class in BINDING_METHOD_CLASSES:
        missing_claims = [
            claim
            for claim in METHOD_CLAIM_REQUIREMENTS[method_class]
            if normalized_method_claims.get(claim) is not True
        ]
        if missing_claims:
            diagnostic_reasons.append(
                "binding method claims are not satisfied: " + ", ".join(missing_claims)
            )
        if rounding_mode != BINDING_ROUNDING_MODE:
            diagnostic_reasons.append(
                f"binding rounding_mode must be {BINDING_ROUNDING_MODE}"
            )
        if not external_route_snapshot_supplied:
            diagnostic_reasons.append(
                "binding-looking record requires a complete external route-input snapshot"
            )
    if certificate_claim != BINDING_CERTIFICATE_CLAIM:
        diagnostic_reasons.append("certificate_claim is diagnostic-only")
    if not independent:
        diagnostic_reasons.append("reference is not independent of route estimates")
    reused_inputs = sorted(set(input_fingerprints) & route_inputs)
    if reused_inputs:
        diagnostic_reasons.append(
            "reference reuses route batch/circuit inputs: " + ", ".join(reused_inputs)
        )
    status = (
        "DIAGNOSTIC_ONLY"
        if diagnostic_reasons
        else "STRUCTURALLY_COMPLETE_UNVERIFIED"
    )
    normalized.update(
        {
            "observable": observable,
            "status": status,
            "value": value,
            "hamiltonian_fingerprint": reference.get("hamiltonian_fingerprint"),
            "initial_state_fingerprint": reference.get("initial_state_fingerprint"),
            "evolution_fingerprint": reference.get("evolution_fingerprint"),
            "observable_definition_fingerprint": reference.get(
                "observable_definition_fingerprint"
            ),
            "reference_target": reference.get("reference_target"),
            "boundary_condition_fingerprint": reference.get(
                "boundary_condition_fingerprint"
            ),
            "hamiltonian_convention_fingerprint": reference.get(
                "hamiltonian_convention_fingerprint"
            ),
            "method_class": method_class,
            "method_description": method_description,
            "solver_fingerprint": solver_fingerprint,
            "configuration_fingerprint": configuration_fingerprint,
            "reference_formula_fingerprint": reference_formula_fingerprint,
            "reference_term_sequence_fingerprint": (
                reference_term_sequence_fingerprint
            ),
            "certificate_checker_fingerprint": certificate_checker_fingerprint,
            "implementation_commit": implementation_commit,
            "environment_lock_sha256": environment_lock_sha256,
            "theorem_and_assumptions_fingerprint": theorem_and_assumptions_fingerprint,
            "rounding_mode": rounding_mode,
            "method_claims": normalized_method_claims,
            "certificate_artifact": certificate_artifact,
            "certificate_sha256": certificate_sha256,
            "certificate_claim": certificate_claim,
            "total_abs_bound": total_abs_bound,
            "error_decomposition": normalized_decomposition,
            "error_decomposition_sum": component_sum,
            "independent_of_route_estimates": independent,
            "independence_provenance": independence_provenance,
            "input_fingerprints": input_fingerprints,
            "provenance": provenance,
            "errors": errors,
            "identity_errors": identity_errors,
            "diagnostic_reasons": diagnostic_reasons,
        }
    )
    return normalized


def validate_ledger(
    contract: Any,
    ledger: Any,
    *,
    artifact_root: Optional[Path | str] = None,
    route_input_fingerprints: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, Any]:
    """Validate a ledger and derive one of the four qualification states.

    ``route_input_fingerprints`` is an externally supplied snapshot from a
    convergence manifest.  It is unioned with the ledger snapshot.  Without a
    valid complete external batch-and-circuit snapshot, a binding-looking record
    is diagnostic.
    """

    schema_errors = validate_contract(contract)
    if schema_errors:
        return {"status": "INVALID_SCHEMA", "errors": schema_errors, "references": {}}
    if not isinstance(ledger, Mapping):
        return {
            "status": "INVALID_SCHEMA",
            "errors": ["ledger must be an object"],
            "references": {},
        }
    schema_errors.extend(_ledger_header_errors(contract, ledger))
    if schema_errors:
        return {"status": "INVALID_SCHEMA", "errors": schema_errors, "references": {}}

    route_inputs, route_errors = _parse_route_inputs(
        ledger.get("route_inputs"), "ledger.route_inputs"
    )
    external_route_snapshot_supplied = False
    if route_input_fingerprints is not None:
        external_inputs, external_errors = _parse_route_inputs(
            route_input_fingerprints, "route_input_fingerprints"
        )
        route_inputs.update(external_inputs)
        route_errors.extend(external_errors)
        external_route_snapshot_supplied = (
            not external_errors
            and isinstance(route_input_fingerprints, Mapping)
            and all(
                isinstance(route_input_fingerprints.get(field), list)
                and bool(route_input_fingerprints[field])
                for field in ("batch_fingerprints", "circuit_fingerprints")
            )
        )
    references = ledger.get("references")
    observable_order = contract["workload"]["observable_order"]
    if not isinstance(references, Mapping):
        route_errors.append("ledger references must be an object")
        references = {}
    if set(references) != set(observable_order):
        route_errors.append("ledger references must contain every observable exactly once")
    root = Path(artifact_root) if artifact_root is not None else HERE
    results: Dict[str, Any] = {}
    for observable in observable_order:
        reference = references.get(observable)
        if not isinstance(reference, Mapping):
            continue
        results[observable] = _assess_reference(
            contract,
            observable,
            reference,
            root,
            route_inputs,
            external_route_snapshot_supplied,
        )

    identity_errors = [
        error
        for result in results.values()
        for error in result.get("identity_errors", [])
    ]
    if identity_errors:
        return {
            "status": "INVALID_SCHEMA",
            "errors": route_errors + identity_errors,
            "references": results,
            "route_input_fingerprints": sorted(route_inputs),
        }
    reference_errors = [
        error for result in results.values() for error in result.get("errors", [])
    ]
    if route_errors or reference_errors or len(results) != len(observable_order):
        status = "UNRESOLVED"
    elif all(
        result.get("status") == "STRUCTURALLY_COMPLETE_UNVERIFIED"
        for result in results.values()
    ):
        status = "STRUCTURALLY_COMPLETE_UNVERIFIED"
    else:
        status = "DIAGNOSTIC_ONLY"
    return {
        "status": status,
        "errors": route_errors + reference_errors,
        "warnings": [
            reason
            for result in results.values()
            for reason in result.get("diagnostic_reasons", [])
        ],
        "references": results,
        "structurally_complete_observables": [
            observable
            for observable, result in results.items()
            if result.get("status") == "STRUCTURALLY_COMPLETE_UNVERIFIED"
        ],
        "route_input_fingerprints": sorted(route_inputs),
        "bound_budget_adequacy": "NOT_ASSESSED_NO_CAMPAIGN_CONTRACT",
        "ready_gate_eligible": False,
        "limitations": [
            "No fixed machine checker is executed by this validator.",
            "The campaign reference-systematic budget is not loaded or assessed.",
            (
                "External route-input snapshot completeness is shape-checked, "
                "not proven against convergence data."
            ),
            "Structural completeness and self-consistency are not reference qualification.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--route-inputs", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    with args.contract.open(encoding="utf-8") as handle:
        contract = json.load(handle)
    with args.ledger.open(encoding="utf-8") as handle:
        ledger = json.load(handle)
    external_inputs = None
    if args.route_inputs is not None:
        with args.route_inputs.open(encoding="utf-8") as handle:
            external_inputs = json.load(handle)
    result = validate_ledger(
        contract,
        ledger,
        artifact_root=args.artifact_root or args.ledger.parent,
        route_input_fingerprints=external_inputs,
    )
    if args.format == "markdown":
        print(f"# Reference qualification: {result['status']}\n")
        for observable, reference in result.get("references", {}).items():
            print(f"- `{observable}`: {reference.get('status')}")
        for error in result.get("errors", []):
            print(f"\nError: {error}")
        for warning in result.get("warnings", []):
            print(f"\nWarning: {warning}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    # Structural self-consistency is deliberately not a qualification success.
    # Exit zero is reserved for a future state backed by a fixed machine checker.
    sys.exit(1)


if __name__ == "__main__":
    main()
