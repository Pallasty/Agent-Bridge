#!/usr/bin/env python3
"""Pure-Python L=2 exact-reference pilot for the common Hubbard group order.

This deliberately small simulator validates the convergence data path.  It is
not a replacement for a compiler export and must not be extrapolated to L=8.
"""

from __future__ import annotations

import argparse
import cmath
import json
import math
from pathlib import Path
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


def build_pilot(
    l: int = 2,
    u_over_t: float = 8.0,
    total_time: float = 1.0,
    r_values: Iterable[int] = (1, 2, 4, 8, 16, 32, 64, 128),
) -> Dict[str, object]:
    if l != 2:
        raise ValueError("the pure-Python pilot is deliberately restricted to L=2")
    initial = neel_state(l)
    exact = exact_evolution(initial, l, u_over_t, total_time)
    reference = staggered_magnetization(exact, l)
    points = []
    for r in r_values:
        r = int(r)
        state = trotter_evolution(initial, l, u_over_t, total_time, r)
        points.append(
            {
                "R": r,
                "estimate": staggered_magnetization(state, l),
                "standard_error": 0.0,
            }
        )
    metadata = {
        "observable": "staggered magnetization",
        "initial_state": "checkerboard Neel product state",
        "hamiltonian_fingerprint": "FH_L2_UoverT8_tT1_half_filling",
        "trotter_formula": "second-order Suzuki--Trotter (Strang)",
    }
    return {
        "schema_version": 1,
        "pilot_status": "algorithmic_product_formula_pilot_not_hardware_or_L8_evidence",
        "workload": {
            **metadata,
            "algorithmic_error_budget": 0.005,
            "statistical_error_budget": 0.0,
            "confidence_z": 2.0,
        },
        "reference": {
            "value": reference,
            "provenance": "pure-Python sparse Hamiltonian action plus scaled Taylor evolution",
        },
        "required_routes": ["group_order_pilot"],
        "routes": {"group_order_pilot": {"metadata": metadata, "points": points}},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    result = build_pilot()
    if args.format == "markdown":
        print("# L=2 product-formula pilot\n")
        print(f"Reference staggered magnetization: `{result['reference']['value']:.12g}`\n")
        for point in result["routes"]["group_order_pilot"]["points"]:
            print(f"- R={point['R']}: {point['estimate']:.12g}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
