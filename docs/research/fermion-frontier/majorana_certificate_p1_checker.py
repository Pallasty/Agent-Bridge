#!/usr/bin/env python3
"""Independent CAR oracle and formal replay checker for Majorana P1.

The expected action is generated only from exact occupation-basis CAR rules.
The Julia runner is treated as an observed implementation and is never imported.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import functools
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Iterable, Mapping, Sequence


BASE = Path(__file__).resolve().parent
P0_CHECKER_PATH = BASE / "majorana_certificate_p0_checker.py"
_P0_SPEC = importlib.util.spec_from_file_location("majorana_certificate_p0_checker", P0_CHECKER_PATH)
if _P0_SPEC is None or _P0_SPEC.loader is None:
    raise RuntimeError("cannot load pinned P0 checker infrastructure")
P0 = importlib.util.module_from_spec(_P0_SPEC)
_P0_SPEC.loader.exec_module(P0)

SchemaError = P0.SchemaError
VerificationError = P0.VerificationError
canonical_bytes = P0.canonical_bytes
canonical_sha256 = P0.canonical_sha256
file_sha256 = P0.file_sha256
strict_json_loads = P0.strict_json_loads
load_json = P0.load_json
require_exact_keys = P0.require_exact_keys
require_sha256 = P0.require_sha256
parse_q = P0.parse_q
format_q = P0.format_q

FIXTURE_NAME = "majorana_certificate_p1_fixture.json"
POLICY_NAME = "majorana_certificate_p1_policy.json"
RUNTIME_LOCK_NAME = "majorana_certificate_p0_runtime_lock.json"
PRECOMMIT_CONTRACT_NAME = "majorana_certificate_p1_precommit_contract.json"
RESULT_CONTRACT_NAME = "majorana_certificate_p1_contract.json"
CERTIFICATE_NAME = "majorana_certificate_p1_certificate.json"
RESULT_TEST_NAME = "test_majorana_certificate_p1_result.py"
CHECKER_NAME = "majorana_certificate_p1_checker.py"
PRE_RESULT_TEST_NAME = "test_majorana_certificate_p1.py"
PROJECT_DIRECTORY_NAME = "majorana_certificate_p0"
RUNNER_RELATIVE_PATH = "majorana_certificate_p1/majorana_p1_runner.jl"
RESULT_ARTIFACTS = (RESULT_CONTRACT_NAME, CERTIFICATE_NAME, RESULT_TEST_NAME)

MAXIMUM_STATUS = (
    "VERIFIED_MAJORANA_P1_L2_L3_HUBBARD_SPARSE_ACTION_AND_CADENCE_"
    "CONFORMANCE_SUBCERTIFICATE"
)
FIXTURE_CANONICAL_SHA256 = "f35f57c7c71e87e3ea60fd29fb3af11ab59b209129dcda8ea7c861d7b611938b"
POLICY_CANONICAL_SHA256 = "ee2bd1a89839c15a7f39317add50fb36514f4f451f6c3e15d9a6e7e600a4262d"
REQUIRED_PARENT_COMMIT = "87a47403bb84a52cdbe5c741cf8e14d5f7204bb1"
GROUP_ORDER = ("H1", "H2", "HU", "H3", "H4", "H4", "H3", "HU", "H2", "H1")
UNIQUE_GROUP_ORDER = ("H1", "H2", "HU", "H3", "H4")
REPLAY_TIMEOUT_SECONDS = 1800
MAX_STDOUT_BYTES = 2_000_000

EXPECTED_DEPOT_RELATIVE_PATHS = {
    "MajoranaPropagation": "packages/MajoranaPropagation/FsiWG",
    "PauliPropagation": "packages/PauliPropagation/w9vRW",
}
CERTIFICATE_CLAIMS = (
    "pinned_Julia_1.11.9_MajoranaPropagation_0.3.0_and_PauliPropagation_0.7.3_runtime_and_loaded_source_custody",
    "fixed_L2_L3_square_OBC_Hubbard_operator_term_and_candidate_action_conformance",
    "L2_all_1179648_bra_ket_entries_evaluated_by_upstream_overlapwithfock",
    "L3_all_11534336_operator_ket_candidate_actions_evaluated_at_term_derived_support",
    "sorted_certificate_wrapper_R2_apply_merge_truncate_execution_probe_conformance",
    "omitted_identity_phase_exponents_8_and_18_accounted_as_fixture_conventions",
    "two_fresh_network_isolated_processes_produced_byte_identical_canonical_transcripts",
)
CERTIFICATE_EXCLUSIONS = (
    "upstream_native_unsorted_FermionicRotation_execution_order",
    "L3_outside_candidate_support_entries_individually_executed",
    "L8_full_propagation",
    "1152_gate_or_100_mapped_step_workload",
    "product_formula_to_exact_Hubbard_error",
    "exact_time_evolution",
    "paper_figure_parameter_or_convergence_reproduction",
    "arbitrary_lattice_constructor_circuit_or_product_formula_generalization",
    "physical_reference_qualification",
    "READY",
)


def validate_fixture(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P1 fixture must be an object")
    if canonical_sha256(value) != FIXTURE_CANONICAL_SHA256:
        raise SchemaError("P1 fixture differs from the frozen semantic object")
    if type(value.get("schema_version")) is not int or value.get("schema_version") != 1 or value.get("fixture_id") != (
        "MAJORANA-P1-L2-L3-HUBBARD-ACTION-CADENCE-V1"
    ):
        raise SchemaError("unexpected P1 fixture identity")
    profiles = value.get("profiles")
    if not isinstance(profiles, list) or [row.get("profile_id") for row in profiles] != [
        "L2_OBC", "L3_OBC"
    ]:
        raise SchemaError("P1 profiles must be ordered L2_OBC,L3_OBC")
    return value


def validate_runtime_lock(value: Any) -> Mapping[str, Any]:
    return P0.validate_runtime_lock(value)


def _add_term(expansion: dict[int, Fraction], mask: int, coefficient: Fraction) -> None:
    expansion[mask] = expansion.get(mask, Fraction(0)) + coefficient
    if expansion[mask] == 0:
        del expansion[mask]


def _mask(*majorana_indices: int) -> int:
    output = 0
    for index in majorana_indices:
        if type(index) is not int or index < 1:
            raise VerificationError("Majorana indices must be positive integers")
        output |= 1 << (index - 1)
    return output


def _constructor_terms(symbol: str, sites: Sequence[int]) -> dict[int, Fraction]:
    if symbol == "nup":
        site = sites[0]
        return {_mask(4 * site - 3, 4 * site - 2): Fraction(1, 2), 0: Fraction(1, 2)}
    if symbol == "ndn":
        site = sites[0]
        return {_mask(4 * site - 1, 4 * site): Fraction(1, 2), 0: Fraction(1, 2)}
    if symbol == "nupndn":
        site = sites[0]
        up = _mask(4 * site - 3, 4 * site - 2)
        down = _mask(4 * site - 1, 4 * site)
        return {up: Fraction(1, 4), down: Fraction(1, 4), up | down: Fraction(-1, 4), 0: Fraction(1, 4)}
    if symbol == "Sz":
        site = sites[0]
        return {
            _mask(4 * site - 3, 4 * site - 2): Fraction(1, 4),
            _mask(4 * site - 1, 4 * site): Fraction(-1, 4),
        }
    if symbol in ("hopup", "hopdn"):
        left, right = sorted(sites)
        if symbol == "hopup":
            return {
                _mask(4 * left - 3, 4 * right - 2): Fraction(1, 2),
                _mask(4 * left - 2, 4 * right - 3): Fraction(-1, 2),
            }
        return {
            _mask(4 * left - 1, 4 * right): Fraction(1, 2),
            _mask(4 * left, 4 * right - 1): Fraction(-1, 2),
        }
    raise VerificationError(f"unsupported frozen constructor: {symbol}")


def _term_rows(expansion: Mapping[int, Fraction]) -> list[dict[str, Any]]:
    return [
        {"mask": mask, "coefficient": format_q(expansion[mask])}
        for mask in sorted(expansion)
    ]


def _canonical_bonds(linear_size: int) -> list[dict[str, Any]]:
    bonds: list[dict[str, Any]] = []
    for group in ("H1", "H2", "H3", "H4"):
        if group in ("H1", "H2"):
            parity = 0 if group == "H1" else 1
            endpoints = (
                ((row, column), (row, column + 1))
                for row in range(linear_size)
                for column in range(parity, linear_size - 1, 2)
            )
        else:
            parity = 1 if group == "H3" else 0
            endpoints = (
                ((row, column), (row + 1, column))
                for row in range(parity, linear_size - 1, 2)
                for column in range(linear_size)
            )
        for (row_a, col_a), (row_b, col_b) in endpoints:
            for spin, symbol in (("up", "hopup"), ("down", "hopdn")):
                bonds.append(
                    {
                        "group": group,
                        "row_a": row_a,
                        "col_a": col_a,
                        "row_b": row_b,
                        "col_b": col_b,
                        "spin": spin,
                        "symbol": symbol,
                    }
                )
    return bonds


def _cadence(symbol: str, sites: Sequence[int], multiplier: Fraction) -> dict[str, Any]:
    base = _constructor_terms(symbol, sites)
    base.pop(0, None)
    constituents = [
        {
            "mask": mask,
            "constructor_coefficient": format_q(base[mask]),
            "physical_theta_multiplier": format_q(multiplier),
            "effective_coefficient": format_q(base[mask] * multiplier),
        }
        for mask in sorted(base)
    ]
    truncate_each = symbol == "nupndn"
    applied_masks = [row["mask"] for row in constituents]
    if truncate_each:
        observed_boundaries = [
            {
                "boundary_index": index,
                "boundary_kind": "after_constituent",
                "after_constituent_index": index,
                "identity_callback_delta": 1,
            }
            for index in range(len(constituents))
        ]
    else:
        observed_boundaries = [
            {
                "boundary_index": 0,
                "boundary_kind": "after_complete_composite",
                "after_constituent_index": None,
                "identity_callback_delta": 1,
            }
        ]
    execution_probe = {
        "wrapper_id": "sorted_zero_angle_identity_truncation_callback_v1",
        "applied_masks": applied_masks,
        "applied_masks_sha256": canonical_sha256(applied_masks),
        "observed_truncation_call_count": len(observed_boundaries),
        "observed_boundaries": observed_boundaries,
        "observed_boundaries_sha256": canonical_sha256(observed_boundaries),
        "final_identity_coefficient": "1",
    }
    return {
        "truncate_after_each_constituent": truncate_each,
        "boundary_kind": "after_constituent" if truncate_each else "after_complete_composite",
        "constituent_count": len(constituents),
        "truncation_boundary_count": len(constituents) if truncate_each else 1,
        "constituents": constituents,
        "constituents_sha256": canonical_sha256(constituents),
        "execution_probe": execution_probe,
        "execution_probe_sha256": canonical_sha256(execution_probe),
    }


def _operator_specs(linear_size: int) -> list[dict[str, Any]]:
    n_sites = linear_size * linear_size
    specs: list[dict[str, Any]] = []
    bonds = _canonical_bonds(linear_size)
    for group in UNIQUE_GROUP_ORDER:
        if group == "HU":
            for site0 in range(n_sites):
                row, column = divmod(site0, linear_size)
                symbol = "nupndn"
                sites = [site0 + 1]
                multiplier = Fraction(8)
                expansion: dict[int, Fraction] = {}
                for mask, coefficient in _constructor_terms(symbol, sites).items():
                    _add_term(expansion, mask, multiplier * coefficient)
                specs.append(
                    {
                        "operator_id": f"HU_r{row}_c{column}",
                        "operator_role": "hubbard_onsite_generator",
                        "group": group,
                        "symbol": symbol,
                        "sites": sites,
                        "physical_theta_multiplier": multiplier,
                        "expansion": expansion,
                        "cadence": _cadence(symbol, sites, multiplier),
                        "site0": site0,
                    }
                )
        else:
            for bond in bonds:
                if bond["group"] != group:
                    continue
                left0 = bond["row_a"] * linear_size + bond["col_a"]
                right0 = bond["row_b"] * linear_size + bond["col_b"]
                symbol = str(bond["symbol"])
                sites = [left0 + 1, right0 + 1]
                multiplier = Fraction(-1)
                expansion = {}
                for mask, coefficient in _constructor_terms(symbol, sites).items():
                    _add_term(expansion, mask, multiplier * coefficient)
                specs.append(
                    {
                        "operator_id": f"{group}_r{bond['row_a']}_c{bond['col_a']}_{bond['spin']}",
                        "operator_role": "hubbard_hopping_generator",
                        "group": group,
                        "symbol": symbol,
                        "sites": sites,
                        "physical_theta_multiplier": multiplier,
                        "expansion": expansion,
                        "cadence": _cadence(symbol, sites, multiplier),
                        "left_mode": 2 * left0 + (0 if bond["spin"] == "up" else 1),
                        "right_mode": 2 * right0 + (0 if bond["spin"] == "up" else 1),
                    }
                )
    for site0 in range(n_sites):
        row, column = divmod(site0, linear_size)
        sites = [site0 + 1]
        specs.append(
            {
                "operator_id": f"OBS_Sz_r{row}_c{column}",
                "operator_role": "local_Sz_observable",
                "group": None,
                "symbol": "Sz",
                "sites": sites,
                "physical_theta_multiplier": Fraction(1),
                "expansion": _constructor_terms("Sz", sites),
                "cadence": None,
                "site0": site0,
            }
        )
    staggered: dict[int, Fraction] = {}
    for site0 in range(n_sites):
        row, column = divmod(site0, linear_size)
        sign = 1 if (row + column) % 2 == 0 else -1
        for symbol, spin_sign in (("nup", sign), ("ndn", -sign)):
            for mask, coefficient in _constructor_terms(symbol, [site0 + 1]).items():
                _add_term(staggered, mask, Fraction(spin_sign, n_sites) * coefficient)
    specs.append(
        {
            "operator_id": "OBS_staggered_magnetization",
            "operator_role": "campaign_observable",
            "group": None,
            "symbol": "staggered_magnetization",
            "sites": list(range(1, n_sites + 1)),
            "physical_theta_multiplier": Fraction(1),
            "expansion": staggered,
            "cadence": None,
        }
    )
    double: dict[int, Fraction] = {}
    for site0 in range(n_sites):
        for mask, coefficient in _constructor_terms("nupndn", [site0 + 1]).items():
            _add_term(double, mask, Fraction(1, n_sites) * coefficient)
    specs.append(
        {
            "operator_id": "OBS_double_occupancy",
            "operator_role": "campaign_observable",
            "group": None,
            "symbol": "double_occupancy",
            "sites": list(range(1, n_sites + 1)),
            "physical_theta_multiplier": Fraction(1),
            "expansion": double,
            "cadence": None,
        }
    )
    return specs


def _apply_ladder(source: int, mode: int, create: bool) -> tuple[int, int] | None:
    occupied = (source >> mode) & 1
    if (create and occupied) or (not create and not occupied):
        return None
    sign = -1 if (source & ((1 << mode) - 1)).bit_count() % 2 else 1
    target = source | (1 << mode) if create else source & ~(1 << mode)
    return target, sign


def _hopping_action(source: int, left: int, right: int) -> dict[int, Fraction]:
    output: dict[int, Fraction] = {}
    for create_mode, annihilate_mode in ((left, right), (right, left)):
        first = _apply_ladder(source, annihilate_mode, False)
        if first is None:
            continue
        intermediate, sign1 = first
        second = _apply_ladder(intermediate, create_mode, True)
        if second is None:
            continue
        target, sign2 = second
        output[target] = output.get(target, Fraction(0)) - sign1 * sign2
    return {target: value for target, value in output.items() if value}


def _car_action(spec: Mapping[str, Any], source: int, linear_size: int) -> dict[int, tuple[Fraction, Fraction]]:
    role = spec["operator_role"]
    n_sites = linear_size * linear_size
    if role == "hubbard_hopping_generator":
        return {
            target: (value, Fraction(0))
            for target, value in _hopping_action(source, spec["left_mode"], spec["right_mode"]).items()
        }
    if role == "hubbard_onsite_generator":
        site = spec["site0"]
        value = Fraction(8 * ((source >> (2 * site)) & 1) * ((source >> (2 * site + 1)) & 1))
    elif role == "local_Sz_observable":
        site = spec["site0"]
        value = Fraction(((source >> (2 * site)) & 1) - ((source >> (2 * site + 1)) & 1), 2)
    elif spec["operator_id"] == "OBS_staggered_magnetization":
        total = 0
        for site in range(n_sites):
            row, column = divmod(site, linear_size)
            sign = 1 if (row + column) % 2 == 0 else -1
            total += sign * (((source >> (2 * site)) & 1) - ((source >> (2 * site + 1)) & 1))
        value = Fraction(total, n_sites)
    elif spec["operator_id"] == "OBS_double_occupancy":
        total = sum(
            ((source >> (2 * site)) & 1) * ((source >> (2 * site + 1)) & 1)
            for site in range(n_sites)
        )
        value = Fraction(total, n_sites)
    else:
        raise VerificationError("unknown frozen operator role")
    return {} if value == 0 else {source: (value, Fraction(0))}


def _flip_mask(majorana_mask: int, n_modes: int) -> int:
    flip = 0
    for mode in range(n_modes):
        pair = (majorana_mask >> (2 * mode)) & 3
        if pair in (1, 2):
            flip |= 1 << mode
    return flip


def _action_line(source: int, action: Mapping[int, tuple[Fraction, Fraction]]) -> bytes:
    outputs = ";".join(
        f"{target},{format_q(value[0])},{format_q(value[1])}"
        for target, value in sorted(action.items())
    )
    return f"{source}\t{outputs}\n".encode("ascii")


def _dense_line(source: int, target: int, value: tuple[Fraction, Fraction]) -> bytes:
    return f"{source}\t{target}\t{format_q(value[0])}\t{format_q(value[1])}\n".encode("ascii")


class _ChunkedHasher:
    def __init__(self) -> None:
        self._digest = hashlib.sha256()
        self._buffer = bytearray()

    def update(self, payload: bytes) -> None:
        self._buffer.extend(payload)
        if len(self._buffer) >= 1_048_576:
            self._digest.update(self._buffer)
            self._buffer.clear()

    def hexdigest(self) -> str:
        if self._buffer:
            self._digest.update(self._buffer)
            self._buffer.clear()
        return self._digest.hexdigest()


def _public_operator_record(
    spec: Mapping[str, Any], operator_index: int, linear_size: int, dense: bool
) -> dict[str, Any]:
    n_modes = 2 * linear_size * linear_size
    dimension = 1 << n_modes
    expansion = spec["expansion"]
    terms = _term_rows(expansion)
    flips = sorted({_flip_mask(mask, n_modes) for mask in expansion})
    if len(flips) != 1:
        raise VerificationError("each frozen P1 operator must have one exact support flip")
    action_hasher = _ChunkedHasher()
    dense_hasher = _ChunkedHasher() if dense else None
    nonzero_outputs = 0
    for source in range(dimension):
        action = _car_action(spec, source, linear_size)
        expected_targets = {source ^ flip for flip in flips}
        if not set(action).issubset(expected_targets):
            raise VerificationError("CAR action escaped exact Majorana flip support")
        nonzero_outputs += len(action)
        action_hasher.update(_action_line(source, action))
        if dense_hasher is not None:
            zero = (Fraction(0), Fraction(0))
            for target in range(dimension):
                dense_hasher.update(_dense_line(source, target, action.get(target, zero)))
    logical_dense = dimension * dimension
    candidate_count = dimension * len(flips)
    return {
        "operator_index": operator_index,
        "operator_id": spec["operator_id"],
        "operator_role": spec["operator_role"],
        "group": spec["group"],
        "symbol": spec["symbol"],
        "sites": spec["sites"],
        "physical_theta_multiplier": format_q(spec["physical_theta_multiplier"]),
        "term_count": len(terms),
        "terms": terms,
        "terms_sha256": canonical_sha256(terms),
        "support_flip_masks": flips,
        "support_flip_masks_sha256": canonical_sha256(flips),
        "action_column_count": dimension,
        "support_candidate_entry_count": candidate_count,
        "action_nonzero_output_count": nonzero_outputs,
        "action_stream_sha256": action_hasher.hexdigest(),
        "logical_dense_matrix_entry_count": logical_dense,
        "explicit_dense_matrix_entry_count": logical_dense if dense else 0,
        "algebraically_implied_outside_support_zero_entry_count": (
            0 if dense else logical_dense - candidate_count
        ),
        "dense_matrix_stream_sha256": (
            dense_hasher.hexdigest() if dense_hasher is not None else "NOT_ENUMERATED_BY_POLICY"
        ),
        "cadence": spec["cadence"],
    }


def _r2_cadence(specs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    generator_specs = [spec for spec in specs if spec["cadence"] is not None]
    occurrences: list[dict[str, Any]] = []
    constituent_count = 0
    boundary_count = 0
    phase = Fraction(0)
    for step in range(2):
        for event_in_step, group in enumerate(GROUP_ORDER):
            for occurrence_in_event, spec in enumerate(
                candidate for candidate in generator_specs if candidate["group"] == group
            ):
                cadence = spec["cadence"]
                phase_increment = spec["expansion"].get(0, Fraction(0)) * Fraction(1, 4)
                record = {
                    "occurrence_index": len(occurrences),
                    "step_index": step,
                    "event_in_step": event_in_step,
                    "group": group,
                    "occurrence_in_event": occurrence_in_event,
                    "operator_id": spec["operator_id"],
                    "truncate_after_each_constituent": cadence[
                        "truncate_after_each_constituent"
                    ],
                    "boundary_kind": cadence["boundary_kind"],
                    "constituent_count": cadence["constituent_count"],
                    "truncation_boundary_count": cadence["truncation_boundary_count"],
                    "constituents_sha256": cadence["constituents_sha256"],
                    "execution_probe_sha256": cadence["execution_probe_sha256"],
                    "half_event_duration": "1/4",
                    "omitted_identity_phase_increment_in_exp_minus_i_x": format_q(
                        phase_increment
                    ),
                }
                occurrences.append(record)
                constituent_count += cadence["constituent_count"]
                boundary_count += cadence["truncation_boundary_count"]
                phase += phase_increment
    return {
        "trotter_steps": 2,
        "group_order": list(GROUP_ORDER),
        "composite_occurrence_count": len(occurrences),
        "constituent_occurrence_count": constituent_count,
        "truncation_boundary_count": boundary_count,
        "occurrences_sha256": canonical_sha256(occurrences),
        "omitted_identity_phase_exponent_in_exp_minus_i_x": format_q(phase),
    }


def _profile_witness(profile_fixture: Mapping[str, Any]) -> dict[str, Any]:
    linear_size = profile_fixture["linear_size"]
    dense = profile_fixture["dense_matrix_enumeration"]
    specs = _operator_specs(linear_size)
    records = [
        _public_operator_record(spec, index, linear_size, dense)
        for index, spec in enumerate(specs)
    ]
    generator_records = [record for record in records if record["cadence"] is not None]
    unique_constituents = sum(record["cadence"]["constituent_count"] for record in generator_records)
    unique_boundaries = sum(
        record["cadence"]["truncation_boundary_count"] for record in generator_records
    )
    r2 = _r2_cadence(specs)
    summary = {
        "profile_id": profile_fixture["profile_id"],
        "linear_size": linear_size,
        "n_sites": linear_size * linear_size,
        "n_modes": 2 * linear_size * linear_size,
        "basis_dimension": 1 << (2 * linear_size * linear_size),
        "dense_matrix_enumeration": dense,
        "operator_instance_count": len(records),
        "occupation_action_column_count": sum(record["action_column_count"] for record in records),
        "explicit_dense_matrix_entry_count": sum(
            record["explicit_dense_matrix_entry_count"] for record in records
        ),
        "logical_dense_matrix_entry_count": sum(
            record["logical_dense_matrix_entry_count"] for record in records
        ),
        "action_nonzero_output_count": sum(
            record["action_nonzero_output_count"] for record in records
        ),
        "support_candidate_entry_count": sum(
            record["support_candidate_entry_count"] for record in records
        ),
        "algebraically_implied_outside_support_zero_entry_count": sum(
            record["algebraically_implied_outside_support_zero_entry_count"]
            for record in records
        ),
        "unique_composite_count": len(generator_records),
        "unique_constituent_count": unique_constituents,
        "unique_truncation_boundary_count": unique_boundaries,
        "operator_records": records,
        "operator_records_sha256": canonical_sha256(records),
        "r2_cadence": r2,
    }
    expected_fields = {
        "n_sites": summary["n_sites"],
        "n_modes": summary["n_modes"],
        "basis_dimension": summary["basis_dimension"],
        "operator_instance_count": summary["operator_instance_count"],
        "occupation_action_column_count": summary["occupation_action_column_count"],
        "dense_matrix_entry_count": (
            summary["explicit_dense_matrix_entry_count"]
            if dense
            else summary["logical_dense_matrix_entry_count"]
        ),
        "unique_composite_count": summary["unique_composite_count"],
        "unique_constituent_count": summary["unique_constituent_count"],
        "unique_truncation_boundary_count": summary["unique_truncation_boundary_count"],
        "r2_composite_occurrence_count": r2["composite_occurrence_count"],
        "r2_constituent_occurrence_count": r2["constituent_occurrence_count"],
        "r2_truncation_boundary_count": r2["truncation_boundary_count"],
        "r2_omitted_identity_phase_exponent_in_exp_minus_i_x": r2[
            "omitted_identity_phase_exponent_in_exp_minus_i_x"
        ],
    }
    for field, actual in expected_fields.items():
        if profile_fixture[field] != actual:
            raise VerificationError(f"fixture/profile derived count mismatch: {field}")
    return summary


@functools.lru_cache(maxsize=1)
def _cached_profiles() -> tuple[dict[str, Any], ...]:
    fixture = validate_fixture(load_json(BASE / FIXTURE_NAME))
    return tuple(_profile_witness(profile) for profile in fixture["profiles"])


def expected_witness(
    fixture: Mapping[str, Any], runtime_lock: Mapping[str, Any]
) -> dict[str, Any]:
    validate_fixture(fixture)
    runtime_lock = validate_runtime_lock(runtime_lock)
    profiles = [dict(profile) for profile in _cached_profiles()]
    julia = runtime_lock["julia_runtime"]
    environment = runtime_lock["project_environment"]
    packages = runtime_lock["direct_and_semantic_upstream_packages"]
    aggregate = {
        "profile_count": len(profiles),
        "operator_instance_count": sum(row["operator_instance_count"] for row in profiles),
        "hubbard_generator_instance_count": sum(row["unique_composite_count"] for row in profiles),
        "local_Sz_observable_instance_count": sum(
            sum(record["operator_role"] == "local_Sz_observable" for record in row["operator_records"])
            for row in profiles
        ),
        "campaign_observable_instance_count": sum(
            sum(record["operator_role"] == "campaign_observable" for record in row["operator_records"])
            for row in profiles
        ),
        "occupation_action_column_count": sum(
            row["occupation_action_column_count"] for row in profiles
        ),
        "explicit_dense_matrix_entry_count": sum(
            row["explicit_dense_matrix_entry_count"] for row in profiles
        ),
        "r2_composite_occurrence_count": sum(
            row["r2_cadence"]["composite_occurrence_count"] for row in profiles
        ),
        "r2_constituent_occurrence_count": sum(
            row["r2_cadence"]["constituent_occurrence_count"] for row in profiles
        ),
        "r2_truncation_boundary_count": sum(
            row["r2_cadence"]["truncation_boundary_count"] for row in profiles
        ),
        "profiles_sha256": canonical_sha256(profiles),
    }
    if aggregate | {} != {**fixture["aggregate_planned_counts"], "profiles_sha256": aggregate["profiles_sha256"]}:
        raise VerificationError("fixture aggregate counts differ from independent oracle")
    return {
        "schema_version": 1,
        "witness_type": "majorana_p1_l2_l3_hubbard_sparse_action_cadence_v1",
        "fixture_id": fixture["fixture_id"],
        "runtime": {
            "julia_version": julia["version"],
            "julia_commit": julia["build_commit_short"],
            "machine": julia["machine"],
            "threads": 1,
            "executable_sha256": julia["executable"]["sha256"],
            "sysimage_sha256": julia["sysimage"]["sha256"],
            "project_sha256": environment["project"]["sha256"],
            "manifest_sha256": environment["manifest"]["sha256"],
        },
        "upstream": {
            "majorana_propagation_version": packages["MajoranaPropagation"]["version"],
            "pauli_propagation_version": packages["PauliPropagation"]["version"],
            "majorana_source_closure": packages["MajoranaPropagation"]["installed_source_closure"],
            "pauli_source_closure": packages["PauliPropagation"]["installed_source_closure"],
        },
        "profiles": profiles,
        "aggregate": aggregate,
        "scope": {
            "maximum_positive_status": MAXIMUM_STATUS,
            "fixed_L2_L3_square_OBC_Hubbard_workload_only": True,
            "full_occupation_basis_columns_verified": True,
            "L2_all_bra_ket_dense_entries_verified": True,
            "L3_all_ket_sparse_candidate_actions_verified": True,
            "L3_outside_support_entries_individually_executed": False,
            "arbitrary_MajoranaPropagation_constructors_or_circuits": "NOT_CLAIMED",
            "L8_full_propagation": "NOT_ASSESSED",
            "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
            "exact_time_evolution": "NOT_ASSESSED",
            "physical_reference_qualified": False,
            "ready_gate_eligible": False,
        },
    }


def validate_witness(
    witness: Any, fixture: Mapping[str, Any], runtime_lock: Mapping[str, Any]
) -> Mapping[str, Any]:
    expected = expected_witness(fixture, runtime_lock)
    # Python considers True == 1.  Canonical JSON comparison preserves the
    # JSON type distinction and therefore fails closed on bool/int mutants.
    if canonical_bytes(witness) != canonical_bytes(expected):
        raise VerificationError(
            "Julia witness differs from independent CAR oracle: "
            f"expected={canonical_sha256(expected)}, actual={canonical_sha256(witness)}"
        )
    return witness


def validate_policy(
    policy: Any, runtime_lock: Mapping[str, Any], base: Path = BASE
) -> Mapping[str, Any]:
    if not isinstance(policy, dict):
        raise SchemaError("P1 policy must be an object")
    if canonical_sha256(policy) != POLICY_CANONICAL_SHA256:
        raise SchemaError("P1 policy differs from the frozen semantic object")
    if (
        type(policy.get("schema_version")) is not int
        or policy.get("schema_version") != 1
        or policy.get("policy_id") != "MAJORANA-P1-S0"
    ):
        raise SchemaError("unexpected P1 policy identity")
    authority = policy.get("maximum_positive_authority")
    if not isinstance(authority, dict) or authority.get("status") != MAXIMUM_STATUS:
        raise SchemaError("P1 policy authority mismatch")
    boundary = policy.get("precommit_boundary")
    if not isinstance(boundary, dict) or any(
        boundary.get(field) is not False
        for field in (
            "policy_contains_observed_replay_results",
            "policy_contains_witness_or_result_hashes",
            "policy_promises_a_terminal_branch",
        )
    ):
        raise SchemaError("P1 policy is not result-unpinned")
    if tuple(policy.get("precommit_forbidden_paths", ())) != RESULT_ARTIFACTS:
        raise SchemaError("P1 policy result-artifact denylist mismatch")
    encoded = canonical_bytes(policy).decode("utf-8")
    for forbidden in policy.get("forbidden_formal_result_pins", ()):
        if not isinstance(forbidden, str):
            raise SchemaError("forbidden formal result pin names must be strings")
        if re.search(rf'"{re.escape(forbidden)}"\s*:', encoded):
            raise SchemaError(f"P1 policy contains forbidden result pin: {forbidden}")
    pins = policy.get("source_pins")
    if not isinstance(pins, list) or not pins:
        raise SchemaError("P1 policy source pins missing")
    seen: set[str] = set()
    for index, pin in enumerate(pins):
        require_exact_keys(pin, ("relative_path", "role", "size_bytes", "sha256"), f"source pin {index}")
        relative = pin["relative_path"]
        if not isinstance(relative, str) or relative in seen or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise SchemaError("invalid or duplicate P1 source pin path")
        seen.add(relative)
        require_sha256(pin["sha256"], "P1 source pin digest")
        path = base / relative
        if path.is_symlink() or not path.is_file():
            raise VerificationError(f"P1 pinned source is not a regular file: {relative}")
        if path.stat().st_size != pin["size_bytes"] or file_sha256(path) != pin["sha256"]:
            raise VerificationError(f"P1 pinned source bytes mismatch: {relative}")
    required_stable = {
        FIXTURE_NAME,
        RUNTIME_LOCK_NAME,
        f"{PROJECT_DIRECTORY_NAME}/Project.toml",
        f"{PROJECT_DIRECTORY_NAME}/Manifest.toml",
    }
    if seen != required_stable:
        raise SchemaError("P1 policy stable runtime/fixture source pin set mismatch")
    P0.validate_project_environment(runtime_lock, base)
    return policy


def validate_precommit_contract(contract: Any, base: Path = BASE) -> Mapping[str, Any]:
    require_exact_keys(
        contract,
        (
            "schema_version",
            "contract_id",
            "contract_role",
            "required_parent_commit",
            "self_relative_path",
            "source_files",
            "result_artifacts_required_absent",
            "formal_replay",
        ),
        "P1 precommit contract",
    )
    if (
        type(contract["schema_version"]) is not int
        or contract["schema_version"] != 1
        or contract["contract_id"] != "MAJORANA-P1-PRECOMMIT-S0"
        or contract["contract_role"]
        != "result_unpinned_formal_replay_input_and_isolation_contract"
    ):
        raise SchemaError("unexpected P1 precommit contract identity")
    if contract["self_relative_path"] != PRECOMMIT_CONTRACT_NAME:
        raise SchemaError("P1 precommit self path mismatch")
    if tuple(contract["result_artifacts_required_absent"]) != RESULT_ARTIFACTS:
        raise SchemaError("P1 precommit result-artifact absence list mismatch")
    if contract["required_parent_commit"] != REQUIRED_PARENT_COMMIT:
        raise SchemaError("P1 required parent commit mismatch")
    replay = contract["formal_replay"]
    expected_replay = {
        "process_count": 2,
        "fresh_scratch_and_depot_per_process": True,
        "network_namespace_isolated": True,
        "canonical_stdout_must_be_byte_identical": True,
        "independent_python_oracle_required": True,
    }
    if canonical_bytes(replay) != canonical_bytes(expected_replay):
        raise SchemaError("P1 formal replay contract mismatch")
    rows = contract["source_files"]
    if not isinstance(rows, list):
        raise SchemaError("P1 source_files must be a list")
    paths: list[str] = []
    for index, row in enumerate(rows):
        require_exact_keys(row, ("relative_path", "mode", "size_bytes", "sha256"), f"P1 source row {index}")
        relative = row["relative_path"]
        if (
            not isinstance(relative, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or row["mode"] != "100644"
            or relative in paths
            or type(row["size_bytes"]) is not int
            or row["size_bytes"] < 0
        ):
            raise SchemaError("P1 source mode or uniqueness mismatch")
        paths.append(relative)
        require_sha256(row["sha256"], "P1 precommit source digest")
        path = base / relative
        if path.is_symlink() or not path.is_file():
            raise VerificationError(f"P1 precommit source is not regular: {relative}")
        if path.stat().st_size != row["size_bytes"] or file_sha256(path) != row["sha256"]:
            raise VerificationError(f"P1 precommit source bytes mismatch: {relative}")
    required = {
        FIXTURE_NAME,
        POLICY_NAME,
        RUNTIME_LOCK_NAME,
        f"{PROJECT_DIRECTORY_NAME}/Project.toml",
        f"{PROJECT_DIRECTORY_NAME}/Manifest.toml",
        RUNNER_RELATIVE_PATH,
        P0_CHECKER_PATH.name,
        CHECKER_NAME,
        PRE_RESULT_TEST_NAME,
    }
    if set(paths) != required:
        raise SchemaError("P1 precommit source file allowlist mismatch")
    if paths != sorted(paths):
        raise SchemaError("P1 precommit source rows must be path-sorted")
    return contract


def verify_precommit(base: Path = BASE) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), runtime_lock, base)
    contract = validate_precommit_contract(load_json(base / PRECOMMIT_CONTRACT_NAME), base)
    for artifact in RESULT_ARTIFACTS:
        if (base / artifact).exists():
            raise VerificationError(f"P1 result artifact must be absent before replay: {artifact}")
    expected = expected_witness(fixture, runtime_lock)
    return {
        "status": "VERIFIED_MAJORANA_P1_RESULT_UNPINNED_PRECOMMIT_INPUTS",
        "policy_sha256": file_sha256(base / POLICY_NAME),
        "runtime_lock_sha256": file_sha256(base / RUNTIME_LOCK_NAME),
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "precommit_contract_sha256": file_sha256(base / PRECOMMIT_CONTRACT_NAME),
        "independent_expected_witness_sha256": canonical_sha256(expected),
        "scope_ceiling": MAXIMUM_STATUS,
        "result_artifacts_absent": list(contract["result_artifacts_required_absent"]),
        "policy_id": policy["policy_id"],
    }


def _run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )


def _repo_and_base_relative(base: Path = BASE) -> tuple[Path, Path]:
    repo = Path(_run_git(base, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve()
    try:
        relative = base.resolve().relative_to(repo)
    except ValueError as exc:
        raise VerificationError("P1 checker directory is outside the Git repository") from exc
    return repo, relative


def _verify_generation_git_state(
    precommit_commit: str, contract: Mapping[str, Any], base: Path = BASE
) -> tuple[Path, Path]:
    if not re.fullmatch(r"[0-9a-f]{40}", precommit_commit):
        raise SchemaError("P1 precommit commit must be a full Git SHA-1")
    repo, base_relative = _repo_and_base_relative(base)
    head = _run_git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    if head != precommit_commit:
        raise VerificationError("P1 fresh replay requires HEAD equal to precommit commit")
    if _run_git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise VerificationError("P1 fresh replay requires a completely clean worktree")
    parent = _run_git(repo, "show", "-s", "--format=%P", precommit_commit).stdout.decode().strip()
    if parent != contract["required_parent_commit"]:
        raise VerificationError("P1 precommit does not have the frozen direct parent")
    remote_contains = _run_git(repo, "branch", "-r", "--contains", precommit_commit).stdout.decode()
    if "origin/" not in remote_contains:
        raise VerificationError("P1 precommit must be pushed before formal replay")
    return repo, base_relative


def _git_blob(repo: Path, commit: str, repo_relative: str) -> tuple[str, str, bytes]:
    output = _run_git(repo, "ls-tree", "-z", commit, "--", repo_relative).stdout
    records = [record for record in output.split(b"\0") if record]
    if len(records) != 1:
        raise VerificationError(f"P1 Git input is missing or ambiguous: {repo_relative}")
    try:
        metadata, encoded_path = records[0].split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split(" ")
        decoded_path = encoded_path.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise VerificationError("malformed P1 git ls-tree record") from exc
    if decoded_path != repo_relative or mode != "100644" or object_type != "blob":
        raise VerificationError(f"non-regular P1 Git input: {repo_relative}")
    return mode, object_id, _run_git(repo, "cat-file", "blob", object_id).stdout


def _git_path_exists(repo: Path, commit: str, repo_relative: str) -> bool:
    return _run_git(repo, "cat-file", "-e", f"{commit}:{repo_relative}", check=False).returncode == 0


def _stage_precommit_tree(
    repo: Path,
    base_relative: Path,
    commit: str,
    contract: Mapping[str, Any],
    destination: Path,
) -> dict[str, Any]:
    rows_by_path = {row["relative_path"]: row for row in contract["source_files"]}
    allowlist = sorted([*rows_by_path, contract["self_relative_path"]])
    staged_rows: list[dict[str, Any]] = []
    for relative in allowlist:
        repo_relative = (base_relative / relative).as_posix()
        mode, object_id, body = _git_blob(repo, commit, repo_relative)
        if relative in rows_by_path:
            pin = rows_by_path[relative]
            if len(body) != pin["size_bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
                raise VerificationError(f"P1 Git blob differs from precommit pin: {relative}")
        elif body != (BASE / PRECOMMIT_CONTRACT_NAME).read_bytes():
            raise VerificationError("P1 Git precommit contract differs from active bytes")
        target = destination / repo_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        staged_rows.append(
            {
                "relative_path": repo_relative,
                "git_mode": mode,
                "git_blob": object_id,
                "size_bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
    for artifact in contract["result_artifacts_required_absent"]:
        repo_relative = (base_relative / artifact).as_posix()
        if _git_path_exists(repo, commit, repo_relative):
            raise VerificationError(f"P1 result artifact exists in precommit: {artifact}")
    return {
        "files": staged_rows,
        "files_sha256": canonical_sha256(staged_rows),
        "file_count": len(staged_rows),
    }


def _run_one_isolated_replay(
    staging_repo: Path,
    base_relative: Path,
    julia_executable: Path,
    depot: Path,
    run_root: Path,
) -> bytes:
    if shutil.which("bwrap") is None:
        raise VerificationError("bubblewrap is required for P1 formal replay")
    scratch = run_root / "scratch"
    depot_prefix = scratch / "depot"
    home = scratch / "home"
    tmp = scratch / "tmp"
    for path in (depot_prefix, home, tmp):
        path.mkdir(parents=True, exist_ok=False)
    staged_base = staging_repo / base_relative
    project = staged_base / PROJECT_DIRECTORY_NAME
    runner = staged_base / RUNNER_RELATIVE_PATH
    fixture = staged_base / FIXTURE_NAME
    command = [
        "bwrap", "--die-with-parent", "--unshare-net", "--ro-bind", "/", "/",
        "--dev-bind", "/dev", "/dev", "--proc", "/proc", "--bind", str(scratch), str(scratch),
        "--clearenv", "--setenv", "HOME", str(home), "--setenv", "TMPDIR", str(tmp),
        "--setenv", "LANG", "C.UTF-8", "--setenv", "LC_ALL", "C.UTF-8",
        "--setenv", "JULIA_DEPOT_PATH", f"{depot_prefix}:{depot}",
        "--setenv", "JULIA_LOAD_PATH", "@", "--setenv", "JULIA_NUM_THREADS", "1",
        "--setenv", "OPENBLAS_NUM_THREADS", "1", "--setenv", "JULIA_PKG_OFFLINE", "true",
        "--setenv", "JULIA_PKG_SERVER", "", "--chdir", str(staging_repo),
        str(julia_executable), "--startup-file=no", "--history-file=no", "--compiled-modules=no",
        f"--project={project}", str(runner), str(fixture),
    ]
    try:
        completed = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=REPLAY_TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VerificationError("P1 formal replay is INDETERMINATE after timeout") from exc
    if completed.returncode != 0:
        diagnostic = completed.stderr.decode("utf-8", errors="replace")[-4000:]
        raise VerificationError(f"isolated P1 Julia replay failed with {completed.returncode}: {diagnostic}")
    if completed.stderr:
        raise VerificationError("isolated P1 Julia replay emitted unexpected stderr")
    if len(completed.stdout) > MAX_STDOUT_BYTES:
        raise VerificationError("isolated P1 Julia replay exceeded stdout cap")
    return completed.stdout


def fresh_replay(
    precommit_commit: str,
    julia_executable: Path,
    depot: Path,
    base: Path = BASE,
) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    validate_policy(load_json(base / POLICY_NAME), runtime_lock, base)
    contract = validate_precommit_contract(load_json(base / PRECOMMIT_CONTRACT_NAME), base)
    repo, base_relative = _verify_generation_git_state(precommit_commit, contract, base)
    P0._verify_julia_runtime(julia_executable, runtime_lock)
    depot = depot.resolve()
    custody_before = P0._verify_depot_custody(depot, runtime_lock)
    with tempfile.TemporaryDirectory(prefix="majorana-p1-formal-") as temporary:
        root = Path(temporary)
        staging_repo = root / "staging"
        staging_repo.mkdir()
        manifest = _stage_precommit_tree(repo, base_relative, precommit_commit, contract, staging_repo)
        staging_before = P0._tree_digest(staging_repo)
        outputs: list[bytes] = []
        witnesses: list[Mapping[str, Any]] = []
        for index in range(2):
            run_root = root / f"run-{index + 1}"
            run_root.mkdir()
            output = _run_one_isolated_replay(
                staging_repo, base_relative, julia_executable.resolve(), depot, run_root
            )
            witness = strict_json_loads(output, source=f"P1 Julia replay {index + 1} stdout")
            if output != canonical_bytes(witness) + b"\n":
                raise VerificationError("P1 Julia stdout is not canonical JSON plus newline")
            validate_witness(witness, fixture, runtime_lock)
            outputs.append(output)
            witnesses.append(witness)
        if outputs[0] != outputs[1]:
            raise VerificationError("two fresh P1 Julia stdout byte streams differ")
        if staging_before != P0._tree_digest(staging_repo):
            raise VerificationError("P1 formal replay modified Git-object staging")
    custody_after = P0._verify_depot_custody(depot, runtime_lock)
    if custody_before != custody_after:
        raise VerificationError("P1 replay modified pinned depot custody")
    if _run_git(repo, "rev-parse", "HEAD").stdout.decode().strip() != precommit_commit:
        raise VerificationError("HEAD changed during P1 formal replay")
    if _run_git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise VerificationError("worktree changed during P1 formal replay")
    transcript = hashlib.sha256(outputs[0]).hexdigest()
    return {
        "schema_version": 1,
        "package_type": "majorana_p1_formal_fresh_replay_package_v1",
        "precommit_commit_sha": precommit_commit,
        "precommit_contract_sha256": file_sha256(base / PRECOMMIT_CONTRACT_NAME),
        "staging_manifest": manifest,
        "staging_tree_sha256": staging_before,
        "depot_custody": custody_after,
        "network_isolation": "bubblewrap_unshared_network_namespace",
        "fresh_process_count": 2,
        "stdout_byte_identical": True,
        "transcript_sha256_in_order": [transcript, transcript],
        "canonical_witness_sha256": canonical_sha256(witnesses[0]),
        "witness": witnesses[0],
        "status": MAXIMUM_STATUS,
    }


def _committed_precommit_evidence(
    precommit_commit: str,
    contract: Mapping[str, Any],
    base: Path = BASE,
) -> tuple[dict[str, Any], str]:
    """Reconstruct formal staging evidence solely from the committed Git blobs."""
    if not isinstance(precommit_commit, str) or re.fullmatch(r"[0-9a-f]{40}", precommit_commit) is None:
        raise SchemaError("P1 result precommit commit must be a full Git SHA-1")
    repo, base_relative = _repo_and_base_relative(base)
    commit_object = _run_git(
        repo, "cat-file", "-e", f"{precommit_commit}^{{commit}}", check=False
    )
    if commit_object.returncode != 0:
        raise VerificationError("P1 result precommit commit does not exist")
    parent = _run_git(repo, "show", "-s", "--format=%P", precommit_commit).stdout.decode().strip()
    if parent != contract["required_parent_commit"]:
        raise VerificationError("P1 result precommit commit has the wrong direct parent")
    if _run_git(
        repo, "merge-base", "--is-ancestor", precommit_commit, "HEAD", check=False
    ).returncode != 0:
        raise VerificationError("P1 result precommit commit is not an ancestor of HEAD")
    remote_contains = _run_git(repo, "branch", "-r", "--contains", precommit_commit).stdout.decode()
    if "origin/" not in remote_contains:
        raise VerificationError("P1 result precommit commit lacks a pushed origin ref")

    rows_by_path = {row["relative_path"]: row for row in contract["source_files"]}
    allowlist = sorted([*rows_by_path, contract["self_relative_path"]])
    manifest_rows: list[dict[str, Any]] = []
    tree_rows: list[dict[str, Any]] = []
    for relative in allowlist:
        repo_relative = (base_relative / relative).as_posix()
        mode, object_id, body = _git_blob(repo, precommit_commit, repo_relative)
        digest = hashlib.sha256(body).hexdigest()
        if relative in rows_by_path:
            pin = rows_by_path[relative]
            if mode != pin["mode"] or len(body) != pin["size_bytes"] or digest != pin["sha256"]:
                raise VerificationError(f"P1 committed source differs from precommit pin: {relative}")
        elif body != (base / PRECOMMIT_CONTRACT_NAME).read_bytes():
            raise VerificationError("P1 committed precommit contract differs from active bytes")
        manifest_rows.append(
            {
                "relative_path": repo_relative,
                "git_mode": mode,
                "git_blob": object_id,
                "size_bytes": len(body),
                "sha256": digest,
            }
        )
        tree_rows.append({"path": repo_relative, "size": len(body), "sha256": digest})
    for artifact in contract["result_artifacts_required_absent"]:
        repo_relative = (base_relative / artifact).as_posix()
        if _git_path_exists(repo, precommit_commit, repo_relative):
            raise VerificationError(f"P1 result artifact exists in precommit commit: {artifact}")
    manifest = {
        "files": manifest_rows,
        "files_sha256": canonical_sha256(manifest_rows),
        "file_count": len(manifest_rows),
    }
    return manifest, canonical_sha256(tree_rows)


def _validate_recorded_depot_custody(
    custody: Any, runtime_lock: Mapping[str, Any]
) -> Mapping[str, Any]:
    require_exact_keys(
        custody,
        EXPECTED_DEPOT_RELATIVE_PATHS,
        "P1 result depot custody",
    )
    packages = runtime_lock["direct_and_semantic_upstream_packages"]
    for package_name, relative_path in EXPECTED_DEPOT_RELATIVE_PATHS.items():
        row = require_exact_keys(
            custody[package_name],
            ("depot_relative_path", "file_count", "total_bytes", "closure_sha256"),
            f"P1 result {package_name} depot custody",
        )
        expected_closure = packages[package_name]["installed_source_closure"]
        expected = {"depot_relative_path": relative_path, **expected_closure}
        if canonical_bytes(row) != canonical_bytes(expected):
            raise VerificationError(f"P1 result {package_name} depot custody mismatch")
    return custody


def verify_final(base: Path = BASE) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), runtime_lock, base)
    precommit = validate_precommit_contract(load_json(base / PRECOMMIT_CONTRACT_NAME), base)
    result = load_json(base / RESULT_CONTRACT_NAME)
    certificate = load_json(base / CERTIFICATE_NAME)
    require_exact_keys(
        result,
        (
            "schema_version", "contract_type", "precommit_commit_sha",
            "precommit_contract_sha256", "replay_package_sha256",
            "staging_manifest_sha256", "staging_tree_sha256", "depot_custody",
            "network_isolation", "fresh_process_count", "stdout_byte_identical",
            "transcript_sha256_in_order", "canonical_witness_sha256", "witness",
            "status", "scope",
        ),
        "P1 result contract",
    )
    if (
        type(result["schema_version"]) is not int
        or result["schema_version"] != 1
        or result["contract_type"] != "majorana_p1_formal_result_contract_v1"
    ):
        raise SchemaError("unexpected P1 result contract identity")
    for field in (
        "precommit_contract_sha256",
        "replay_package_sha256",
        "staging_manifest_sha256",
        "staging_tree_sha256",
        "canonical_witness_sha256",
    ):
        require_sha256(result[field], f"P1 result {field}")
    if (
        result["status"] != MAXIMUM_STATUS
        or type(result["fresh_process_count"]) is not int
        or result["fresh_process_count"] != 2
    ):
        raise VerificationError("P1 result status or process count mismatch")
    transcripts = result["transcript_sha256_in_order"]
    if not isinstance(transcripts, list) or len(transcripts) != 2 or transcripts[0] != transcripts[1]:
        raise VerificationError("P1 transcript equality evidence mismatch")
    for digest in transcripts:
        require_sha256(digest, "P1 transcript digest")
    if result["stdout_byte_identical"] is not True:
        raise VerificationError("P1 result lacks byte-identical replay")
    validate_witness(result["witness"], fixture, runtime_lock)
    witness_bytes = canonical_bytes(result["witness"])
    if result["canonical_witness_sha256"] != hashlib.sha256(witness_bytes).hexdigest():
        raise VerificationError("P1 result witness digest mismatch")
    expected_transcript = hashlib.sha256(witness_bytes + b"\n").hexdigest()
    if transcripts != [expected_transcript, expected_transcript]:
        raise VerificationError("P1 transcript digests are not bound to canonical witness stdout")
    if result["precommit_contract_sha256"] != file_sha256(base / PRECOMMIT_CONTRACT_NAME):
        raise VerificationError("P1 result precommit contract digest mismatch")
    manifest, staging_tree_sha256 = _committed_precommit_evidence(
        result["precommit_commit_sha"], precommit, base
    )
    if result["staging_manifest_sha256"] != canonical_sha256(manifest):
        raise VerificationError("P1 result staging manifest digest mismatch")
    if result["staging_tree_sha256"] != staging_tree_sha256:
        raise VerificationError("P1 result staging tree digest mismatch")
    _validate_recorded_depot_custody(result["depot_custody"], runtime_lock)
    if result["network_isolation"] != "bubblewrap_unshared_network_namespace":
        raise VerificationError("P1 result network isolation mismatch")
    reconstructed_replay_package = {
        "schema_version": 1,
        "package_type": "majorana_p1_formal_fresh_replay_package_v1",
        "precommit_commit_sha": result["precommit_commit_sha"],
        "precommit_contract_sha256": result["precommit_contract_sha256"],
        "staging_manifest": manifest,
        "staging_tree_sha256": result["staging_tree_sha256"],
        "depot_custody": result["depot_custody"],
        "network_isolation": result["network_isolation"],
        "fresh_process_count": result["fresh_process_count"],
        "stdout_byte_identical": result["stdout_byte_identical"],
        "transcript_sha256_in_order": result["transcript_sha256_in_order"],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "witness": result["witness"],
        "status": result["status"],
    }
    reconstructed_replay_sha256 = hashlib.sha256(
        canonical_bytes(reconstructed_replay_package) + b"\n"
    ).hexdigest()
    if result["replay_package_sha256"] != reconstructed_replay_sha256:
        raise VerificationError("P1 replay package digest is not reconstructible from committed evidence")
    if canonical_bytes(result["scope"]) != canonical_bytes(result["witness"]["scope"]):
        raise VerificationError("P1 result scope differs from witness")
    require_exact_keys(
        certificate,
        (
            "schema_version", "certificate_type", "status", "authority",
            "result_contract_sha256", "precommit_commit_sha", "policy_sha256",
            "runtime_lock_sha256", "fixture_sha256", "runner_sha256",
            "checker_sha256", "canonical_witness_sha256", "claims",
            "explicit_exclusions", "ready_gate_eligible",
        ),
        "P1 certificate",
    )
    if (
        type(certificate["schema_version"]) is not int
        or certificate["schema_version"] != 1
        or certificate["certificate_type"] != "majorana_p1_subcertificate_v1"
    ):
        raise SchemaError("unexpected P1 certificate identity")
    if certificate["status"] != MAXIMUM_STATUS or certificate["authority"] != (
        "fixed_L2_L3_square_OBC_Hubbard_fixture_subcertificate_only"
    ):
        raise VerificationError("P1 certificate authority mismatch")
    if certificate["result_contract_sha256"] != file_sha256(base / RESULT_CONTRACT_NAME):
        raise VerificationError("P1 certificate result contract digest mismatch")
    if certificate["precommit_commit_sha"] != result["precommit_commit_sha"]:
        raise VerificationError("P1 certificate precommit commit mismatch")
    expected_hashes = {
        "policy_sha256": file_sha256(base / POLICY_NAME),
        "runtime_lock_sha256": file_sha256(base / RUNTIME_LOCK_NAME),
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "runner_sha256": file_sha256(base / RUNNER_RELATIVE_PATH),
        "checker_sha256": file_sha256(base / CHECKER_NAME),
        "canonical_witness_sha256": result["canonical_witness_sha256"],
    }
    for field, expected in expected_hashes.items():
        if certificate[field] != expected:
            raise VerificationError(f"P1 certificate {field} mismatch")
    if certificate["ready_gate_eligible"] is not False:
        raise VerificationError("P1 certificate improperly claims READY")
    if canonical_bytes(certificate["claims"]) != canonical_bytes(list(CERTIFICATE_CLAIMS)):
        raise VerificationError("P1 certificate claim set or order mismatch")
    if canonical_bytes(certificate["explicit_exclusions"]) != canonical_bytes(
        list(CERTIFICATE_EXCLUSIONS)
    ):
        raise VerificationError("P1 certificate exclusion set or order mismatch")
    return {
        "status": MAXIMUM_STATUS,
        "precommit_commit_sha": result["precommit_commit_sha"],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "result_contract_sha256": file_sha256(base / RESULT_CONTRACT_NAME),
        "certificate_sha256": file_sha256(base / CERTIFICATE_NAME),
        "policy_id": policy["policy_id"],
        "required_parent_commit": precommit["required_parent_commit"],
    }


def _write_canonical_json(path: Path, value: Any) -> None:
    payload = canonical_bytes(value) + b"\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh-replay", action="store_true")
    parser.add_argument("--verify-final", action="store_true")
    parser.add_argument("--precommit-commit")
    parser.add_argument("--julia", type=Path)
    parser.add_argument("--depot", type=Path)
    parser.add_argument("--replay-output", type=Path)
    args = parser.parse_args(argv)
    if args.fresh_replay and args.verify_final:
        raise SchemaError("--fresh-replay and --verify-final are mutually exclusive")
    if args.fresh_replay:
        if not all((args.precommit_commit, args.julia, args.depot, args.replay_output)):
            raise SchemaError("fresh replay requires commit, Julia, depot, and output")
        package = fresh_replay(args.precommit_commit, args.julia, args.depot)
        _write_canonical_json(args.replay_output, package)
        summary = {
            "status": package["status"],
            "precommit_commit_sha": package["precommit_commit_sha"],
            "canonical_witness_sha256": package["canonical_witness_sha256"],
            "transcript_sha256_in_order": package["transcript_sha256_in_order"],
            "replay_package_sha256": file_sha256(args.replay_output),
        }
    elif args.verify_final:
        summary = verify_final()
    else:
        summary = verify_precommit()
    print(canonical_bytes(summary).decode("utf-8"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SchemaError, VerificationError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        raise SystemExit(1)
