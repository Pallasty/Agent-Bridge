#!/usr/bin/env python3
"""Pure-Python L=2 dual-observable screening pilot for the Hubbard group order.

This deliberately small simulator validates the convergence data path. Its
scaled-Taylor ideal-evolution values are diagnostic because the artifact does
not supply a rigorous truncation bound. It is not a replacement for a compiler
export and must not be extrapolated to L=8.
"""

from __future__ import annotations

import argparse
import cmath
import json
import math
from typing import Dict, Iterable, List, Sequence, Tuple


GROUP_ORDER = ("H1", "H2", "HU", "H3", "H4", "H4", "H3", "HU", "H2", "H1")


def _popcount(value: int) -> int:
    return value.bit_count()


def _mode(site: int, spin: int) -> int:
    return 2 * site + spin


def _site_rc(site: int, l: int) -> Tuple[int, int]:
    return divmod(site, l)


def hopping_terms(l: int, group: str) -> List[Tuple[int, int]]:
    terms: List[Tuple[int, int]] = []
    if group in ("H1", "H2"):
        parity = 0 if group == "H1" else 1
        for r in range(l):
            for c in range(parity, l - 1, 2):
                left = r * l + c
                right = left + 1
                for spin in (0, 1):
                    terms.append((_mode(left, spin), _mode(right, spin)))
    elif group in ("H3", "H4"):
        parity = 1 if group == "H3" else 0
        for r in range(parity, l - 1, 2):
            for c in range(l):
                upper = r * l + c
                lower = upper + l
                for spin in (0, 1):
                    terms.append((_mode(upper, spin), _mode(lower, spin)))
    else:
        raise ValueError(f"unknown hopping group {group}")
    return terms


def neel_state(l: int) -> List[complex]:
    n = 2 * l * l
    state = [0j] * (1 << n)
    bits = 0
    for site in range(l * l):
        r, c = _site_rc(site, l)
        spin = 0 if (r + c) % 2 == 0 else 1
        bits |= 1 << _mode(site, spin)
    state[bits] = 1.0 + 0j
    return state


def _hop_sign(source: int, i: int, j: int) -> int:
    """Sign of c_i^dagger c_j for i empty, j occupied in source."""
    after_annihilation = source ^ (1 << j)
    sign_annihilation = -1 if _popcount(source & ((1 << j) - 1)) % 2 else 1
    sign_creation = -1 if _popcount(after_annihilation & ((1 << i) - 1)) % 2 else 1
    return sign_annihilation * sign_creation


def apply_hamiltonian(state: Sequence[complex], l: int, u_over_t: float) -> List[complex]:
    n = 2 * l * l
    out = [0j] * (1 << n)
    for bits, amplitude in enumerate(state):
        if amplitude == 0:
            continue
        onsite = 0
        for site in range(l * l):
            if bits & (1 << _mode(site, 0)) and bits & (1 << _mode(site, 1)):
                onsite += 1
        out[bits] += u_over_t * onsite * amplitude
    for group in ("H1", "H2", "H3", "H4"):
        for i, j in hopping_terms(l, group):
            for source, amplitude in enumerate(state):
                if (source & (1 << i)) or not (source & (1 << j)):
                    continue
                target = source ^ (1 << i) ^ (1 << j)
                sign = _hop_sign(source, i, j)
                out[target] += -sign * amplitude
                out[source] += -sign * state[target]
    return out


def _norm(state: Sequence[complex]) -> float:
    return math.sqrt(sum(abs(value) ** 2 for value in state))


def exp_hamiltonian(state: Sequence[complex], l: int, u_over_t: float, dt: float) -> List[complex]:
    result = list(state)
    term = list(state)
    coefficient = 1.0 + 0j
    for order in range(1, 80):
        term = apply_hamiltonian(term, l, u_over_t)
        coefficient *= (-1j * dt) / order
        contribution = [coefficient * value for value in term]
        result = [left + right for left, right in zip(result, contribution)]
        if _norm(contribution) < 1e-15:
            break
    return result


def exact_evolution(state: Sequence[complex], l: int, u_over_t: float, total_time: float) -> List[complex]:
    # Scaling keeps the Taylor argument small without requiring a matrix library.
    scaled_steps = 8
    state = list(state)
    for _ in range(scaled_steps):
        state = exp_hamiltonian(state, l, u_over_t, total_time / scaled_steps)
    norm = _norm(state)
    return [value / norm for value in state]


def apply_hopping_exponential(
    state: Sequence[complex], l: int, group: str, dt: float
) -> List[complex]:
    n = 2 * l * l
    out = list(state)
    cosine = math.cos(dt)
    sine = math.sin(dt)
    for i, j in hopping_terms(l, group):
        mask_i = 1 << i
        mask_j = 1 << j
        for source in range(1 << n):
            if source & mask_i or not source & mask_j:
                continue
            target = source ^ mask_i ^ mask_j
            sign = _hop_sign(source, i, j)
            # Use the current output so successive commuting terms act on the
            # already-updated amplitudes; a basis state can belong to a pair
            # for more than one disjoint-mode term.
            a = out[source]
            b = out[target]
            out[source] = cosine * a + 1j * sign * sine * b
            out[target] = cosine * b + 1j * sign * sine * a
    return out


def apply_group_exponential(
    state: Sequence[complex], l: int, group: str, dt: float, u_over_t: float
) -> List[complex]:
    if group == "HU":
        out = list(state)
        for bits in range(1 << (2 * l * l)):
            occupied = any(
                bits & (1 << _mode(site, 0)) and bits & (1 << _mode(site, 1))
                for site in range(l * l)
            )
            if occupied:
                double_count = sum(
                    1
                    for site in range(l * l)
                    if bits & (1 << _mode(site, 0)) and bits & (1 << _mode(site, 1))
                )
                out[bits] *= cmath.exp(-1j * dt * u_over_t * double_count)
        return out
    return apply_hopping_exponential(state, l, group, dt)


def trotter_evolution(
    state: Sequence[complex], l: int, u_over_t: float, total_time: float, r: int
) -> List[complex]:
    dt = total_time / r
    state = list(state)
    for _ in range(r):
        for group in GROUP_ORDER:
            state = apply_group_exponential(state, l, group, dt / 2, u_over_t)
    return state


def staggered_magnetization(state: Sequence[complex], l: int) -> float:
    value = 0.0
    for bits, amplitude in enumerate(state):
        probability = abs(amplitude) ** 2
        if probability == 0:
            continue
        magnetization = 0.0
        for site in range(l * l):
            r, c = _site_rc(site, l)
            up = 1 if bits & (1 << _mode(site, 0)) else 0
            down = 1 if bits & (1 << _mode(site, 1)) else 0
            magnetization += ((-1) ** (r + c)) * (up - down)
        value += probability * magnetization / (l * l)
    return value


def double_occupancy(state: Sequence[complex], l: int) -> float:
    value = 0.0
    for bits, amplitude in enumerate(state):
        probability = abs(amplitude) ** 2
        if probability == 0:
            continue
        occupied_sites = sum(
            1
            for site in range(l * l)
            if bits & (1 << _mode(site, 0)) and bits & (1 << _mode(site, 1))
        )
        value += probability * occupied_sites / (l * l)
    return value


def build_pilot(
    l: int = 2,
    u_over_t: float = 8.0,
    total_time: float = 1.0,
    r_values: Iterable[int] = (1, 2, 4, 8, 16, 32, 64, 128),
) -> Dict[str, object]:
    if l != 2:
        raise ValueError("the pure-Python pilot is deliberately restricted to L=2")
    r_values = [int(value) for value in r_values]
    initial = neel_state(l)
    exact = exact_evolution(initial, l, u_over_t, total_time)
    references = {
        "staggered_magnetization": staggered_magnetization(exact, l),
        "double_occupancy": double_occupancy(exact, l),
    }
    points = []
    for r in r_values:
        state = trotter_evolution(initial, l, u_over_t, total_time, r)
        points.append(
            {
                "R": r,
                "batch_id": f"deterministic-L2-R{r}",
                "attempted_shots": 0,
                "accepted_shots": 0,
                "observable_order": ["staggered_magnetization", "double_occupancy"],
                "estimates": {
                    "staggered_magnetization": staggered_magnetization(state, l),
                    "double_occupancy": double_occupancy(state, l),
                },
                "covariance_of_estimator_mean": [[0.0, 0.0], [0.0, 0.0]],
                "systematic_abs_bounds": {
                    "staggered_magnetization": 1e-10,
                    "double_occupancy": 1e-10,
                },
                "systematic_bound_status": "derived_unvalidated",
                "covariance_provenance": "deterministic statevector; zero sampling covariance",
                "measurement_provenance": "exact occupation-basis expectation of pilot state",
                "mitigation_provenance": "not applicable to deterministic pilot",
                "systematic_bound_provenance": "declared numerical tolerance; not a rigorous truncation theorem",
                "circuit_fingerprint": f"FH_L2_group_order_product_formula_R{r}",
                "term_sequence_fingerprint": "FH_L2_common_raw_group_order_v1",
            }
        )
    workload_identity = {
        "observable_order": ["staggered_magnetization", "double_occupancy"],
        "measurement_setting": "joint_occupation_basis",
        "initial_state": "checkerboard Neel product state",
        "initial_state_fingerprint": "checkerboard_Neel_product_state_v1",
        "hamiltonian_fingerprint": "FH_L2_UoverT8_tT1_half_filling",
        "evolution_fingerprint": "FH_L2_UoverT8_tT1_ideal_time_evolution_v1",
        "trotter_formula": "second-order Suzuki--Trotter (Strang)",
        "analysis_plan_fingerprint": "FH_L2_dual_observable_R1_2_4_8_16_32_64_128_v1",
    }
    metadata = {"route": "group_order_pilot", **workload_identity}
    return {
        "schema_version": 2,
        "pilot_status": "algorithmic_product_formula_pilot_not_hardware_or_L8_evidence",
        "workload": {
            **workload_identity,
            "observables": {
                "staggered_magnetization": {
                    "definition_fingerprint": "staggered_magnetization_per_site_v1",
                    "physical_range": [-1.0, 1.0],
                    "algorithmic_error_budget": 0.005,
                    "statistical_half_width_budget": 0.0,
                },
                "double_occupancy": {
                    "definition_fingerprint": "double_occupancy_per_site_v1",
                    "physical_range": [0.0, 1.0],
                    "algorithmic_error_budget": 0.005,
                    "statistical_half_width_budget": 0.0,
                },
            },
            "target_R": 32,
            "planned_R_values": r_values,
            "minimum_stable_intervals": 2,
            "familywise_error_rate": 0.05,
            "familywise_method": "bonferroni_bounded_hoeffding",
            "interval_method": "bounded_hoeffding_or_deterministic",
        },
        "references": {
            observable: {
                "value": value,
                "kind": "approximate_unbounded",
                "standard_error": 0.0,
                "systematic_abs_bound": 0.0,
                "uncertainty_evidence_status": "derived_unvalidated",
                "independent_of_route_estimates": False,
                "hamiltonian_fingerprint": metadata["hamiltonian_fingerprint"],
                "initial_state_fingerprint": metadata["initial_state_fingerprint"],
                "evolution_fingerprint": metadata["evolution_fingerprint"],
                "observable_definition_fingerprint": (
                    "staggered_magnetization_per_site_v1"
                    if observable == "staggered_magnetization"
                    else "double_occupancy_per_site_v1"
                ),
                "reference_target": "ideal_exact_time_evolution",
                "provenance": (
                    "pure-Python sparse Hamiltonian action plus scaled Taylor evolution; "
                    "diagnostic only because no rigorous truncation bound is supplied"
                ),
            }
            for observable, value in references.items()
        },
        "required_routes": ["group_order_pilot"],
        "routes": {
            "group_order_pilot": {
                "metadata": metadata,
                "sampling_mode": "deterministic_simulation",
                "points": points,
            }
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    result = build_pilot()
    if args.format == "markdown":
        print("# L=2 product-formula pilot\n")
        print(
            "Diagnostic reference staggered magnetization: "
            f"`{result['references']['staggered_magnetization']['value']:.12g}`"
        )
        print(
            "Diagnostic reference double occupancy: "
            f"`{result['references']['double_occupancy']['value']:.12g}`\n"
        )
        for point in result["routes"]["group_order_pilot"]["points"]:
            estimates = point["estimates"]
            print(
                f"- R={point['R']}: M_s={estimates['staggered_magnetization']:.12g}, "
                f"D={estimates['double_occupancy']:.12g}"
            )
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
