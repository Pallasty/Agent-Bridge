#!/usr/bin/env python3
"""Executable L=2 conformance witness for the Pauli proof kernel.

The witness independently maps the L=2 OBC Hubbard Strang circuit to 112
declared Pauli rotations at R=2 and compares its statevector observables with
the existing direct-fermion pilot.  Only a one-gate local probe is propagated
with exact Fraction intervals.  A full 112-gate Fraction certificate is
explicitly deferred because this unoptimized reference kernel suffers rapid
term and rational-size growth.

Nothing in this file certifies the fermion-to-Pauli mapping, product-formula
error relative to ideal evolution, L=8 behavior, or a READY condition.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple


HERE = Path(__file__).resolve().parent


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKER = _load_module(
    "operator_propagation_certificate_checker",
    "operator_propagation_certificate_checker.py",
)
PILOT = _load_module("fermi_hubbard_l2_pilot", "fermi_hubbard_l2_pilot.py")

N_QUBITS = 8
NEEL_OCCUPIED_MODES = (0, 3, 5, 6)
NEEL_BITS_Q0_FIRST = "10010110"
GROUP_ORDER = ("H1", "H2", "HU", "H3", "H4", "H4", "H3", "HU", "H2", "H1")
H1_MODE_PAIRS = ((0, 2), (1, 3), (4, 6), (5, 7))
H4_MODE_PAIRS = ((0, 4), (1, 5), (2, 6), (3, 7))


def _pauli_string(assignments: Mapping[int, str]) -> str:
    result = ["I"] * N_QUBITS
    for qubit, operator in assignments.items():
        result[qubit] = operator
    return "".join(result)


def _hopping_group(group: str) -> List[Tuple[str, Fraction]]:
    if group == "H1":
        pairs = H1_MODE_PAIRS
    elif group == "H4":
        pairs = H4_MODE_PAIRS
    elif group in {"H2", "H3"}:
        return []
    else:
        raise ValueError(f"unknown hopping group {group}")
    gates: List[Tuple[str, Fraction]] = []
    for left, right in pairs:
        parity = {qubit: "Z" for qubit in range(left + 1, right)}
        gates.append(
            (_pauli_string({**parity, left: "X", right: "X"}), Fraction(-1, 4))
        )
        gates.append(
            (_pauli_string({**parity, left: "Y", right: "Y"}), Fraction(-1, 4))
        )
    return gates


def _onsite_group() -> List[Tuple[str, Fraction]]:
    gates: List[Tuple[str, Fraction]] = []
    for site in range(4):
        up = 2 * site
        down = up + 1
        gates.extend(
            (
                (_pauli_string({up: "Z"}), Fraction(-1)),
                (_pauli_string({down: "Z"}), Fraction(-1)),
                (_pauli_string({up: "Z", down: "Z"}), Fraction(1)),
            )
        )
    return gates


def build_forward_gate_sequence(r: int = 2) -> List[Dict[str, Any]]:
    """Return the raw, unfused Schrödinger gate sequence for T=1, R=2."""

    if isinstance(r, bool) or r != 2:
        raise ValueError("the conformance witness is fixed to R=2")
    gates: List[Dict[str, Any]] = []
    event_index = 0
    for step in range(r):
        for group in GROUP_ORDER:
            if group == "HU":
                group_gates = _onsite_group()
            else:
                group_gates = _hopping_group(group)
            for gate_in_event, (pauli, theta) in enumerate(group_gates):
                gates.append(
                    {
                        "step": step,
                        "group": group,
                        "group_event_index": event_index,
                        "gate_in_event": gate_in_event,
                        "pauli": pauli,
                        "theta": CHECKER.format_fraction(theta),
                    }
                )
            event_index += 1
    return gates


def _initial_state() -> List[complex]:
    state = [0j] * (1 << N_QUBITS)
    bits = sum(1 << mode for mode in NEEL_OCCUPIED_MODES)
    state[bits] = 1 + 0j
    return state


def _apply_pauli(state: Sequence[complex], pauli: str) -> List[complex]:
    output = [0j] * len(state)
    for bits, amplitude in enumerate(state):
        if amplitude == 0:
            continue
        target = bits
        phase = 1 + 0j
        for qubit, operator in enumerate(pauli):
            occupied = (bits >> qubit) & 1
            if operator == "Z":
                phase *= -1 if occupied else 1
            elif operator == "X":
                target ^= 1 << qubit
            elif operator == "Y":
                target ^= 1 << qubit
                phase *= -1j if occupied else 1j
        output[target] += phase * amplitude
    return output


def _apply_rotation(
    state: Sequence[complex], pauli: str, theta: Fraction
) -> List[complex]:
    transformed = _apply_pauli(state, pauli)
    cosine = math.cos(float(theta) / 2.0)
    sine_factor = -1j * math.sin(float(theta) / 2.0)
    return [
        cosine * amplitude + sine_factor * branch
        for amplitude, branch in zip(state, transformed)
    ]


def mapped_product_formula_state() -> List[complex]:
    state = _initial_state()
    for gate in build_forward_gate_sequence():
        state = _apply_rotation(
            state, gate["pauli"], CHECKER.parse_fraction(gate["theta"])
        )
    return state


def _observables(state: Sequence[complex]) -> Dict[str, float]:
    magnetization = 0.0
    occupancy = 0.0
    site_signs = (1, -1, -1, 1)
    for bits, amplitude in enumerate(state):
        probability = abs(amplitude) ** 2
        if probability == 0:
            continue
        local_magnetization = 0
        double_count = 0
        for site, sign in enumerate(site_signs):
            up = 1 if bits & (1 << (2 * site)) else 0
            down = 1 if bits & (1 << (2 * site + 1)) else 0
            local_magnetization += sign * (up - down)
            double_count += up * down
        magnetization += probability * local_magnetization / 4
        occupancy += probability * double_count / 4
    return {
        "staggered_magnetization": magnetization,
        "double_occupancy": occupancy,
    }


def _state_overlap_magnitude(left: Sequence[complex], right: Sequence[complex]) -> float:
    return abs(sum(a.conjugate() * b for a, b in zip(left, right)))


def _local_fraction_probe() -> Dict[str, Any]:
    gate = build_forward_gate_sequence()[0]
    theta = CHECKER.parse_fraction(gate["theta"])
    sine, cosine = CHECKER.taylor_sin_cos_interval(theta, 6)
    observable = "Z" + "I" * (N_QUBITS - 1)
    expansion = CHECKER._propagate_gate(
        {observable: (Fraction(1), Fraction(1))},
        gate["pauli"],
        sine,
        cosine,
        16,
    )
    interval = (Fraction(0), Fraction(0))
    for pauli, coefficient in expansion.items():
        expectation = CHECKER.computational_basis_pauli_expectation(
            pauli, NEEL_BITS_Q0_FIRST
        )
        interval = CHECKER.interval_add(
            interval, CHECKER.interval_scale(coefficient, expectation)
        )

    state = _apply_rotation(_initial_state(), gate["pauli"], theta)
    transformed = _apply_pauli(state, observable)
    exact_float = sum(a.conjugate() * b for a, b in zip(state, transformed)).real
    return {
        "gate": {"pauli": gate["pauli"], "theta": gate["theta"]},
        "taylor_order": 6,
        "fraction_interval": {
            "lower": CHECKER.format_fraction(interval[0]),
            "upper": CHECKER.format_fraction(interval[1]),
        },
        "direct_statevector_expectation": exact_float,
        "interval_contains_direct_value": float(interval[0]) <= exact_float <= float(interval[1]),
    }


def build_witness() -> Dict[str, Any]:
    gates = build_forward_gate_sequence()
    mapped_state = mapped_product_formula_state()
    direct_state = PILOT.trotter_evolution(
        PILOT.neel_state(2), 2, 8.0, 1.0, 2
    )
    mapped = _observables(mapped_state)
    direct = _observables(direct_state)
    ideal_state = PILOT.exact_evolution(PILOT.neel_state(2), 2, 8.0, 1.0)
    ideal = _observables(ideal_state)
    counts = {
        group: sum(1 for gate in gates if gate["group"] == group)
        for group in ("H1", "H2", "HU", "H3", "H4")
    }
    return {
        "schema_version": 1,
        "status": "CHECKER_CONFORMANCE_WITNESS_ONLY",
        "ready_gate_eligible": False,
        "workload": {
            "lattice": "L=2 open-boundary square",
            "U_over_t": 8,
            "tT": 1,
            "R": 2,
            "qubit_order": "site-major_spin-minor_JW",
            "neel_occupied_modes": list(NEEL_OCCUPIED_MODES),
            "neel_bits_q0_first": NEEL_BITS_Q0_FIRST,
        },
        "gate_convention": CHECKER.CONVENTION,
        "raw_gate_count": len(gates),
        "gate_counts_by_group": counts,
        "maximum_abs_theta": CHECKER.format_fraction(
            max(abs(CHECKER.parse_fraction(gate["theta"])) for gate in gates)
        ),
        "raw_duplicate_events_preserved": True,
        "statevector_cross_check": {
            "mapped_pauli_observables": mapped,
            "direct_fermion_observables": direct,
            "absolute_differences": {
                observable: abs(mapped[observable] - direct[observable])
                for observable in mapped
            },
            "state_overlap_magnitude": _state_overlap_magnitude(
                mapped_state, direct_state
            ),
        },
        "ideal_evolution_diagnostic_only": {
            "observables": ideal,
            "product_formula_absolute_differences": {
                observable: abs(mapped[observable] - ideal[observable])
                for observable in mapped
            },
            "uncertainty_status": "APPROXIMATE_UNBOUNDED",
        },
        "local_fraction_probe": _local_fraction_probe(),
        "full_112_gate_fraction_certificate": "DEFERRED_RESOURCE_LIMIT",
        "limitations": [
            "The Pauli gate list is cross-checked, not machine-certified as a Hubbard mapping.",
            "No product-formula bound to ideal time evolution is supplied.",
            "H2 and H3 are empty at L=2, so odd-parity matchings are untested.",
            "The local Fraction probe does not certify the full 112-gate circuit.",
            "No result is transferable to L=8 or any READY gate.",
        ],
        "not_certified": {
            "fermion_to_pauli_mapping": True,
            "product_formula_to_exact_hamiltonian": True,
            "full_fraction_propagation": True,
            "L8_reference": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    result = build_witness()
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        cross = result["statevector_cross_check"]
        print(f"# L=2 proof-kernel witness: {result['status']}\n")
        print(f"- Raw Pauli rotations: `{result['raw_gate_count']}`")
        print(
            "- Mapped/direct staggered magnetization: "
            f"`{cross['mapped_pauli_observables']['staggered_magnetization']:.12g}` / "
            f"`{cross['direct_fermion_observables']['staggered_magnetization']:.12g}`"
        )
        print(
            "- Mapped/direct double occupancy: "
            f"`{cross['mapped_pauli_observables']['double_occupancy']:.12g}` / "
            f"`{cross['direct_fermion_observables']['double_occupancy']:.12g}`"
        )
        print("- Full Fraction certificate: `DEFERRED_RESOURCE_LIMIT`")
        print("- READY eligible: `false`")


if __name__ == "__main__":
    main()
