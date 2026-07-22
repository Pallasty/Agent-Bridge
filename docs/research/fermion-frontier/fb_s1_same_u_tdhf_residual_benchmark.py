#!/usr/bin/env python3
"""FB-S1 same-U TDHF residual forecast benchmark (pure Python, offline)."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import pathlib
import platform
import resource
import statistics
import sys
import time
import tracemalloc
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


HERE = pathlib.Path(__file__).resolve().parent
INITIAL_CONTRACT_PATH = HERE / "fb_s1_same_u_tdhf_residual_contract.json"
CONTRACT_PATH = HERE / "fb_s1a_same_u_tdhf_residual_contract.json"
PILOT_PATH = HERE / "fermi_hubbard_l2_pilot.py"
FB_S0_CONTRACT_PATH = HERE / "fb_s0_gaussian_occupation_contract.json"
FB_S0_CHECKER_PATH = HERE / "fb_s0_gaussian_occupation_calibration.py"
FB_S0_RECEIPT_PATH = HERE / "fb_s0_gaussian_occupation_receipt.json"
FROZEN_CONTRACTS = {
    "aaaebeced5321e50964498de03f9538a32c365f065736aee4d87cc5459f67061": {
        "schema": "agent_bridge.fermion_biocortex.fb_s1_same_u_tdhf_residual_contract.v1",
        "analysis_class": "INITIAL_PRIMARY_INVALID_BUDGET_ACCOUNTING",
    },
    "363c18d668ce8ea7eb3896ccd7c72ab39fdbf3cbce6509604eb625d2ea139d0b": {
        "schema": "agent_bridge.fermion_biocortex.fb_s1a_same_u_tdhf_residual_contract.v1",
        "analysis_class": "POST_REVEAL_AMENDED_EXPLORATORY",
    },
}


class BenchmarkError(RuntimeError):
    pass


def sha256_path(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract(path: pathlib.Path = CONTRACT_PATH) -> Dict[str, Any]:
    contract_sha256 = sha256_path(path)
    frozen = FROZEN_CONTRACTS.get(contract_sha256)
    if frozen is None:
        raise BenchmarkError(
            f"frozen contract hash mismatch: {contract_sha256}"
        )
    def reject_constant(token: str) -> None:
        raise BenchmarkError(f"non-finite JSON constant is forbidden: {token}")

    value = json.loads(
        path.read_text(encoding="utf-8"), parse_constant=reject_constant
    )
    if value.get("schema") != frozen["schema"]:
        raise BenchmarkError("contract schema mismatch")
    if value.get("analysis_class", frozen["analysis_class"]) != frozen["analysis_class"]:
        raise BenchmarkError("analysis class mismatch")
    bindings = value["source_bindings"]
    actual = {
        "pilot_sha256": sha256_path(PILOT_PATH),
        "fb_s0_contract_sha256": sha256_path(FB_S0_CONTRACT_PATH),
        "fb_s0_checker_sha256": sha256_path(FB_S0_CHECKER_PATH),
        "fb_s0_receipt_sha256": sha256_path(FB_S0_RECEIPT_PATH),
    }
    if any(key not in actual or actual[key] != expected for key, expected in bindings.items()):
        raise BenchmarkError(f"source binding mismatch: {actual}")
    expected_binding_keys = {
        "pilot_sha256",
        "fb_s0_contract_sha256",
        "fb_s0_checker_sha256",
    }
    if frozen["analysis_class"] == "POST_REVEAL_AMENDED_EXPLORATORY":
        expected_binding_keys.add("fb_s0_receipt_sha256")
    if set(bindings) != expected_binding_keys:
        raise BenchmarkError("source binding key mismatch")
    fb_s0_receipt = json.loads(FB_S0_RECEIPT_PATH.read_text(encoding="utf-8"))
    if fb_s0_receipt.get("status") != "ANALYTIC_GAUSSIAN_Q2_COUNTEREXAMPLE_VERIFIED":
        raise BenchmarkError("FB-S0 predecessor status mismatch")
    predecessor_claims = fb_s0_receipt.get("claims", {})
    if predecessor_claims.get("calibration_only") is not True or any(
        predecessor_claims.get(key) is not False
        for key in (
            "fermionic_non_gaussianity_assessed",
            "hoi_application_claim",
            "physical_l8_instance_assessed",
            "ready_gate_eligible",
            "bgl_accessed",
            "runtime_authority",
            "mainline_parameter_influence",
            "portable_receipt_byte_identity",
        )
    ):
        raise BenchmarkError("FB-S0 predecessor claim boundary mismatch")
    validate_contract_semantics(value, frozen["analysis_class"])
    return value


def validate_contract_semantics(contract: Mapping[str, Any], analysis_class: str) -> None:
    physics, split, models = contract["physics"], contract["split"], contract["models"]
    u_groups = [physics["train_u"], physics["development_u"], physics["test_u"]]
    if any(not group for group in u_groups):
        raise BenchmarkError("every U split must be non-empty")
    if len(set(value for group in u_groups for value in group)) != sum(map(len, u_groups)):
        raise BenchmarkError("U splits must be disjoint and duplicate-free")
    if any(not math.isfinite(float(value)) for group in u_groups for value in group):
        raise BenchmarkError("U values must be finite")
    if not 0 <= split["warmup_steps"] < split["prefix_steps"] < physics["steps"]:
        raise BenchmarkError("invalid causal prefix/warmup split")
    if not 0 <= split["purge_steps"] < physics["steps"] - split["prefix_steps"]:
        raise BenchmarkError("invalid purge")
    for key in ("future_values_visible_to_fit", "test_u_visible_to_fit", "seed_selection_on_test"):
        if split[key] is not False:
            raise BenchmarkError(f"leakage flag must remain false: {key}")
    if not models["candidate_seeds"] or len(set(models["candidate_seeds"])) != len(models["candidate_seeds"]):
        raise BenchmarkError("candidate seeds must be non-empty and unique")
    if models["candidate_state_dimension"] <= 0 or models["ridge_lambda"] <= 0:
        raise BenchmarkError("candidate dimension and ridge must be positive")
    if any(value is not False for value in contract["nonclaims"].values()):
        raise BenchmarkError("all nonclaims must remain false")
    if analysis_class == "POST_REVEAL_AMENDED_EXPLORATORY":
        if contract["confirmation_authority"] is not False:
            raise BenchmarkError("amendment cannot carry confirmation authority")
        if contract["authority"] != {
            "research_only": True,
            "ready_gate_eligible": False,
            "runtime_authority": False,
        }:
            raise BenchmarkError("amendment authority boundary mismatch")
        if contract["amendment"]["corrected_candidate_state_dimension"] != 5:
            raise BenchmarkError("budget-derived amendment dimension mismatch")


def load_pilot() -> Any:
    spec = importlib.util.spec_from_file_location("fb_s1_l2_pilot", PILOT_PATH)
    if spec is None or spec.loader is None:
        raise BenchmarkError("cannot load L2 pilot")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def zeros(rows: int, cols: int) -> List[List[complex]]:
    return [[0j for _ in range(cols)] for _ in range(rows)]


def density(orbitals: Sequence[Sequence[complex]]) -> List[List[complex]]:
    n = len(orbitals)
    occupied = len(orbitals[0])
    out = zeros(n, n)
    for i in range(n):
        for j in range(n):
            out[i][j] = sum(orbitals[i][a] * orbitals[j][a].conjugate() for a in range(occupied))
    return out


def matmul(left: Sequence[Sequence[complex]], right: Sequence[Sequence[complex]]) -> List[List[complex]]:
    rows, inner, cols = len(left), len(right), len(right[0])
    return [[sum(left[i][k] * right[k][j] for k in range(inner)) for j in range(cols)] for i in range(rows)]


def solve_matrix(left: Sequence[Sequence[complex]], right: Sequence[Sequence[complex]]) -> List[List[complex]]:
    n, cols = len(left), len(right[0])
    augmented = [list(left[i]) + list(right[i]) for i in range(n)]
    for pivot_col in range(n):
        pivot = max(range(pivot_col, n), key=lambda row: abs(augmented[row][pivot_col]))
        if abs(augmented[pivot][pivot_col]) < 1e-14:
            raise BenchmarkError("singular complex solve")
        augmented[pivot_col], augmented[pivot] = augmented[pivot], augmented[pivot_col]
        scale = augmented[pivot_col][pivot_col]
        augmented[pivot_col] = [value / scale for value in augmented[pivot_col]]
        for row in range(n):
            if row == pivot_col:
                continue
            factor = augmented[row][pivot_col]
            if factor:
                augmented[row] = [a - factor * b for a, b in zip(augmented[row], augmented[pivot_col])]
    return [row[n : n + cols] for row in augmented]


def initial_orbitals(pilot: Any, linear_size: int) -> List[List[complex]]:
    state = pilot.neel_state(linear_size)
    basis = next(index for index, amplitude in enumerate(state) if amplitude)
    occupied_modes = [mode for mode in range(2 * linear_size * linear_size) if basis & (1 << mode)]
    out = zeros(2 * linear_size * linear_size, len(occupied_modes))
    for column, mode in enumerate(occupied_modes):
        out[mode][column] = 1.0 + 0j
    return out


def hopping_pairs(pilot: Any, linear_size: int) -> List[Tuple[int, int]]:
    pairs = set()
    for group in ("H1", "H2", "H3", "H4"):
        for left, right in pilot.hopping_terms(linear_size, group):
            pairs.add(tuple(sorted((left, right))))
    return sorted(pairs)


def hf_hamiltonian(kernel: Sequence[Sequence[complex]], u_value: float, pairs: Sequence[Tuple[int, int]]) -> List[List[complex]]:
    n = len(kernel)
    out = zeros(n, n)
    for left, right in pairs:
        out[left][right] = -1.0 + 0j
        out[right][left] = -1.0 + 0j
    for site in range(n // 2):
        up, down = 2 * site, 2 * site + 1
        out[up][up] = u_value * kernel[down][down].real
        out[down][down] = u_value * kernel[up][up].real
    return out


def crank_nicolson(orbitals: Sequence[Sequence[complex]], hamiltonian: Sequence[Sequence[complex]], dt: float) -> List[List[complex]]:
    n = len(hamiltonian)
    left = zeros(n, n)
    right_operator = zeros(n, n)
    for i in range(n):
        for j in range(n):
            identity = 1.0 if i == j else 0.0
            left[i][j] = identity + 0.5j * dt * hamiltonian[i][j]
            right_operator[i][j] = identity - 0.5j * dt * hamiltonian[i][j]
    return solve_matrix(left, matmul(right_operator, orbitals))


def tdhf_step(orbitals: Sequence[Sequence[complex]], u_value: float, pairs: Sequence[Tuple[int, int]], dt: float, iterations: int) -> List[List[complex]]:
    start_kernel = density(orbitals)
    trial = crank_nicolson(orbitals, hf_hamiltonian(start_kernel, u_value, pairs), dt)
    for _ in range(iterations):
        trial_kernel = density(trial)
        midpoint = [[0.5 * (start_kernel[i][j] + trial_kernel[i][j]) for j in range(len(start_kernel))] for i in range(len(start_kernel))]
        trial = crank_nicolson(orbitals, hf_hamiltonian(midpoint, u_value, pairs), dt)
    return trial


def nominal_observables(kernel: Sequence[Sequence[complex]], linear_size: int) -> Tuple[float, float]:
    staggered = 0.0
    double = 0.0
    for site in range(linear_size * linear_size):
        row, col = divmod(site, linear_size)
        up, down = 2 * site, 2 * site + 1
        staggered += ((-1) ** (row + col)) * (kernel[up][up].real - kernel[down][down].real)
        double += kernel[up][up].real * kernel[down][down].real - abs(kernel[up][down]) ** 2
    sites = linear_size * linear_size
    return staggered / sites, double / sites


def hf_energy(kernel: Sequence[Sequence[complex]], u_value: float, pairs: Sequence[Tuple[int, int]]) -> float:
    kinetic = sum(-2.0 * kernel[right][left].real for left, right in pairs)
    interaction = sum(u_value * kernel[2 * site][2 * site].real * kernel[2 * site + 1][2 * site + 1].real for site in range(len(kernel) // 2))
    return kinetic + interaction


def matrix_residuals(kernel: Sequence[Sequence[complex]], particles: int) -> Dict[str, float]:
    n = len(kernel)
    hermitian = max(abs(kernel[i][j] - kernel[j][i].conjugate()) for i in range(n) for j in range(n))
    trace = abs(sum(kernel[i][i].real for i in range(n)) - particles)
    square = matmul(kernel, kernel)
    idempotency = max(abs(square[i][j] - kernel[i][j]) for i in range(n) for j in range(n))
    spin_coherence = max(
        abs(kernel[2 * left][2 * right + 1])
        for left in range(n // 2)
        for right in range(n // 2)
    )
    return {
        "hermiticity": hermitian,
        "trace": trace,
        "idempotency": idempotency,
        "spin_coherence": spin_coherence,
    }


def exact_energy(pilot: Any, state: Sequence[complex], linear_size: int, u_value: float) -> float:
    norm_squared = sum(abs(value) ** 2 for value in state)
    h_state = pilot.apply_hamiltonian(state, linear_size, u_value)
    return (
        sum(
            state[index].conjugate() * h_state[index]
            for index in range(len(state))
        ).real
        / norm_squared
    )


def trajectory(pilot: Any, contract: Mapping[str, Any], u_value: float) -> Dict[str, Any]:
    physics = contract["physics"]
    l_value, dt, steps = physics["linear_size"], physics["time_step"], physics["steps"]
    exact = pilot.neel_state(l_value)
    orbitals = initial_orbitals(pilot, l_value)
    pairs = hopping_pairs(pilot, l_value)
    residuals: List[List[float]] = []
    exact_norm_max = 0.0
    exact_particle_drift = 0.0
    exact_sector_leakage = 0.0
    constraints = {
        "hermiticity": 0.0,
        "trace": 0.0,
        "idempotency": 0.0,
        "spin_coherence": 0.0,
    }
    energies: List[float] = []
    exact_energies: List[float] = []
    exact_observables: List[List[float]] = []
    for step in range(steps + 1):
        kernel = density(orbitals)
        exact_values = (pilot.staggered_magnetization(exact, l_value), pilot.double_occupancy(exact, l_value))
        exact_observables.append(list(exact_values))
        nominal_values = nominal_observables(kernel, l_value)
        residuals.append([exact_values[index] - nominal_values[index] for index in range(2)])
        exact_norm_squared = sum(abs(amplitude) ** 2 for amplitude in exact)
        exact_particle_drift = max(
            exact_particle_drift,
            abs(
                sum(
                    bits.bit_count() * abs(amplitude) ** 2
                    for bits, amplitude in enumerate(exact)
                )
                / exact_norm_squared
                - physics["particle_count"]
            ),
        )
        exact_sector_leakage = max(
            exact_sector_leakage,
            sum(
                abs(amplitude) ** 2
                for bits, amplitude in enumerate(exact)
                if bits.bit_count() != physics["particle_count"]
            )
            / exact_norm_squared,
        )
        current = matrix_residuals(kernel, physics["particle_count"])
        for key in constraints:
            constraints[key] = max(constraints[key], current[key])
        energies.append(hf_energy(kernel, u_value, pairs))
        exact_energies.append(exact_energy(pilot, exact, l_value, u_value))
        if step < steps:
            exact = pilot.exp_hamiltonian(exact, l_value, u_value, dt)
            norm = pilot._norm(exact)
            exact_norm_max = max(exact_norm_max, abs(norm - 1.0))
            exact = [value / norm for value in exact]
            orbitals = tdhf_step(orbitals, u_value, pairs, dt, physics["corrector_iterations"])
    constraints["energy_drift"] = max(energies) - min(energies)
    constraints["exact_energy_drift"] = max(exact_energies) - min(exact_energies)
    constraints["exact_state_norm"] = exact_norm_max
    constraints["exact_particle_drift"] = exact_particle_drift
    constraints["exact_sector_leakage"] = exact_sector_leakage
    return {
        "u": u_value,
        "exact_u": u_value,
        "nominal_u": u_value,
        "residuals": residuals,
        "exact_observables": exact_observables,
        "constraints": constraints,
    }


def refined_exact_observables(
    pilot: Any,
    linear_size: int,
    u_value: float,
    dt: float,
    steps: int,
    factor: int,
) -> List[List[float]]:
    state = pilot.neel_state(linear_size)
    values = []
    for step in range(steps + 1):
        values.append(
            [
                pilot.staggered_magnetization(state, linear_size),
                pilot.double_occupancy(state, linear_size),
            ]
        )
        if step < steps:
            for _ in range(factor):
                state = pilot.exp_hamiltonian(
                    state, linear_size, u_value, dt / factor
                )
                norm = pilot._norm(state)
                state = [amplitude / norm for amplitude in state]
    return values


def solve_real(left: Sequence[Sequence[float]], right: Sequence[float]) -> List[float]:
    matrix = [list(row) + [right[index]] for index, row in enumerate(left)]
    n = len(matrix)
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(matrix[row][column]))
        if abs(matrix[pivot][column]) < 1e-14:
            raise BenchmarkError("singular ridge system")
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        scale = matrix[column][column]
        matrix[column] = [value / scale for value in matrix[column]]
        for row in range(n):
            if row != column:
                factor = matrix[row][column]
                matrix[row] = [a - factor * b for a, b in zip(matrix[row], matrix[column])]
    return [matrix[index][-1] for index in range(n)]


def ridge_fit(features: Sequence[Sequence[float]], targets: Sequence[Sequence[float]], ridge: float) -> List[List[float]]:
    width, outputs = len(features[0]), len(targets[0])
    gram = [[sum(row[i] * row[j] for row in features) for j in range(width)] for i in range(width)]
    for index in range(width):
        gram[index][index] += ridge
    weights = []
    for output in range(outputs):
        rhs = [sum(features[row][i] * targets[row][output] for row in range(len(features))) for i in range(width)]
        weights.append(solve_real(gram, rhs))
    return weights


def linear_predict(weights: Sequence[Sequence[float]], features: Sequence[float]) -> List[float]:
    return [sum(weight * value for weight, value in zip(row, features)) for row in weights]


def scales(train_sequences: Sequence[Sequence[Sequence[float]]], prefix: int) -> Tuple[List[float], List[float]]:
    means, stds = [], []
    for channel in range(2):
        values = [sequence[step][channel] for sequence in train_sequences for step in range(prefix + 1)]
        mean = statistics.fmean(values)
        variance = statistics.fmean((value - mean) ** 2 for value in values)
        means.append(mean)
        stds.append(max(math.sqrt(variance), 1e-9))
    return means, stds


def normalize(sequence: Sequence[Sequence[float]], means: Sequence[float], stds: Sequence[float]) -> List[List[float]]:
    return [[(row[channel] - means[channel]) / stds[channel] for channel in range(2)] for row in sequence]


def lag_features(history: Sequence[Sequence[float]], lag: int, separate: bool = False) -> List[List[float]]:
    if separate:
        raise BenchmarkError("separate features are built per output")
    return [1.0] + [history[-offset][channel] for offset in range(1, lag + 1) for channel in range(2)]


def fit_direct(name: str, sequences: Sequence[Sequence[Sequence[float]]], prefix: int, warmup: int, ridge: float) -> Dict[str, Any]:
    lag = {"AFFINE_DMD": 1, "RIDGE_VAR4": 4, "PRONY_AR8": 8}[name]
    if name == "PRONY_AR8":
        channel_weights = []
        for channel in range(2):
            x_values, y_values = [], []
            for sequence in sequences:
                for step in range(max(lag, warmup), prefix):
                    x_values.append([1.0] + [sequence[step - offset][channel] for offset in range(lag)])
                    y_values.append([sequence[step + 1][channel]])
            channel_weights.append(ridge_fit(x_values, y_values, ridge)[0])
        feature_count = lag + 1
        return {"name": name, "lag": lag, "weights": channel_weights, "parameters": 2 * feature_count, "state": 2 * lag, "ops": 2 * (2 * feature_count - 1), "fit_rows": len(x_values)}
    x_values, y_values = [], []
    for sequence in sequences:
        for step in range(max(lag, warmup), prefix):
            x_values.append(lag_features(sequence[: step + 1], lag))
            y_values.append(sequence[step + 1])
    weights = ridge_fit(x_values, y_values, ridge)
    feature_count = 1 + 2 * lag
    return {"name": name, "lag": lag, "weights": weights, "parameters": 2 * feature_count, "state": 2 * lag, "ops": 2 * (2 * feature_count - 1), "fit_rows": len(x_values)}


def forecast_direct(model: Mapping[str, Any], observed: Sequence[Sequence[float]], count: int) -> List[List[float]]:
    history = [list(row) for row in observed]
    predictions = []
    if model["name"] == "PERSISTENCE":
        return [list(history[-1]) for _ in range(count)]
    for _ in range(count):
        if model["name"] == "PRONY_AR8":
            prediction = [sum(model["weights"][channel][offset] * ([1.0] + [history[-1 - lag][channel] for lag in range(model["lag"])])[offset] for offset in range(model["lag"] + 1)) for channel in range(2)]
        else:
            prediction = linear_predict(model["weights"], lag_features(history, model["lag"]))
        history.append(prediction)
        predictions.append(prediction)
    return predictions


def deterministic_weight(seed: int, row: int, column: int) -> float:
    return math.sin((seed + 1) * (row + 3) * (column + 5) * 0.17320508075688773)


def candidate_inventory(size: int) -> Dict[str, int]:
    return {
        "parameters": 4 * size + 4 + 2 * (size + 1),
        "state": size,
        "ops": size * 10 + 2 * (2 * (size + 1) - 1),
    }


def fixed_reservoir_weights(seed: int, size: int) -> Dict[str, Any]:
    return {
        "input": [
            [0.55 * deterministic_weight(seed, index, channel) for channel in range(2)]
            for index in range(size)
        ],
        "previous": [
            0.11 * deterministic_weight(seed, index, 2) for index in range(size)
        ],
        "previous_three": [
            0.07 * deterministic_weight(seed, index, 3) for index in range(size)
        ],
        "self": 0.82,
    }


def reservoir_step(state: Sequence[float], input_value: Sequence[float], fixed: Mapping[str, Any]) -> List[float]:
    size = len(state)
    out = []
    for index in range(size):
        drive = fixed["input"][index][0] * input_value[0] + fixed["input"][index][1] * input_value[1]
        recurrent = fixed["self"] * state[index] + fixed["previous"][index] * state[(index - 1) % size] + fixed["previous_three"][index] * state[(index - 3) % size]
        out.append(math.tanh(recurrent + drive))
    return out


def fit_reservoir(sequences: Sequence[Sequence[Sequence[float]]], prefix: int, warmup: int, ridge: float, seed: int, size: int) -> Dict[str, Any]:
    features, targets = [], []
    fixed = fixed_reservoir_weights(seed, size)
    for sequence in sequences:
        state = [0.0] * size
        for step in range(prefix):
            state = reservoir_step(state, sequence[step], fixed)
            if step >= warmup:
                features.append([1.0] + state)
                targets.append(sequence[step + 1])
    weights = ridge_fit(features, targets, ridge)
    # Count every realized input/recurrent scalar, the four shared transition
    # constants, and the fitted affine readout. Counting only the generator
    # seed would understate realized model capacity. Fixed weights are
    # precomputed, so forecast operation counts contain no sine evaluations.
    inventory = candidate_inventory(size)
    return {"seed": seed, "size": size, "weights": weights, "fixed": fixed, **inventory, "fit_rows": len(features)}


def forecast_reservoir(model: Mapping[str, Any], observed: Sequence[Sequence[float]], count: int) -> List[List[float]]:
    state = [0.0] * model["size"]
    for row in observed:
        state = reservoir_step(state, row, model["fixed"])
    current = list(observed[-1])
    predictions = []
    for _ in range(count):
        prediction = linear_predict(model["weights"], [1.0] + state)
        predictions.append(prediction)
        current = prediction
        state = reservoir_step(state, current, model["fixed"])
    return predictions


def score(predictions: Sequence[Sequence[Sequence[float]]], truths: Sequence[Sequence[Sequence[float]]], purge: int, threshold: float) -> Dict[str, float]:
    squared, target_squared = [], []
    for predicted, truth in zip(predictions, truths):
        for step in range(purge, len(truth)):
            for channel in range(2):
                squared.append((predicted[step][channel] - truth[step][channel]) ** 2)
                target_squared.append(truth[step][channel] ** 2)
    nrmse = math.sqrt(statistics.fmean(squared)) / max(math.sqrt(statistics.fmean(target_squared)), 1e-12)
    horizon = 0
    for step in range(purge, len(truths[0])):
        error = math.sqrt(statistics.fmean((predictions[case][step][channel] - truths[case][step][channel]) ** 2 for case in range(len(truths)) for channel in range(2)))
        if error > threshold:
            break
        horizon += 1
    return {"nrmse": nrmse, "effective_horizon_steps": horizon}


def assert_finite_tree(value: Any, path: str = "result") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise BenchmarkError(f"non-finite value at {path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            assert_finite_tree(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_finite_tree(child, f"{path}[{index}]")


def classify_status(
    constraints_pass: bool,
    budget_pass: bool,
    direct_reduction: bool,
    kpi_pass: bool,
) -> str:
    if not constraints_pass:
        return "INVALID_PHYSICS_CONSTRAINTS"
    if not budget_pass:
        return "INVALID_BUDGET_ACCOUNTING"
    if direct_reduction:
        return "NO_GO_DIRECT_REDUCTION"
    if not kpi_pass:
        return "NO_GO_KPI"
    return "GO_BIOCORTEX_MOTIVATED_PROXY"


def run(contract_path: pathlib.Path = CONTRACT_PATH) -> Dict[str, Any]:
    contract = load_contract(contract_path)
    physics, split, model_spec = contract["physics"], contract["split"], contract["models"]
    budgets = contract["equal_budget_caps"]
    static_candidate = candidate_inventory(model_spec["candidate_state_dimension"])
    static_budget_pass = (
        static_candidate["parameters"] <= budgets["trainable_or_fixed_scalar_parameters"]
        and static_candidate["state"] <= budgets["persistent_state_scalars"]
        and static_candidate["ops"] <= budgets["logical_scalar_operations_per_step"]
    )
    if not static_budget_pass:
        raise BenchmarkError(
            f"frozen candidate statically violates budget: {static_candidate}"
        )
    pilot = load_pilot()
    all_u = physics["train_u"] + physics["development_u"] + physics["test_u"]
    generated = {u_value: trajectory(pilot, contract, u_value) for u_value in all_u}
    refinement_factor = physics["exact_reference_refinement_factor"]
    refinement_residual = 0.0
    for u_value in all_u:
        refined = refined_exact_observables(
            pilot,
            physics["linear_size"],
            u_value,
            physics["time_step"],
            physics["steps"],
            refinement_factor,
        )
        refinement_residual = max(
            refinement_residual,
            max(
                abs(left[channel] - right[channel])
                for left, right in zip(generated[u_value]["exact_observables"], refined)
                for channel in range(2)
            ),
        )
    maxima = {
        key: max(record["constraints"][key] for record in generated.values())
        for key in (
            "exact_state_norm",
            "exact_particle_drift",
            "exact_sector_leakage",
            "exact_energy_drift",
            "hermiticity",
            "trace",
            "idempotency",
            "spin_coherence",
            "energy_drift",
        )
    }
    maxima["exact_time_step_refinement_observable"] = refinement_residual
    tolerances = contract["tolerances"]
    same_u_verified = all(
        record["u"] == record["exact_u"] == record["nominal_u"]
        for record in generated.values()
    )
    constraints_pass = (
        same_u_verified
        and
        maxima["exact_state_norm"] <= tolerances["exact_state_norm"]
        and maxima["exact_particle_drift"] <= tolerances["tdhf_trace"]
        and maxima["exact_sector_leakage"] <= tolerances["tdhf_trace"]
        and maxima["exact_energy_drift"] <= tolerances["tdhf_energy_drift"]
        and maxima["exact_time_step_refinement_observable"] <= tolerances["exact_time_step_refinement_observable"]
        and maxima["hermiticity"] <= tolerances["tdhf_hermiticity"]
        and maxima["trace"] <= tolerances["tdhf_trace"]
        and maxima["idempotency"] <= tolerances["tdhf_idempotency"]
        and maxima["spin_coherence"] <= tolerances["tdhf_hermiticity"]
        and maxima["energy_drift"] <= tolerances["tdhf_energy_drift"]
    )
    train_raw = [generated[u_value]["residuals"] for u_value in physics["train_u"]]
    means, stds = scales(train_raw, split["prefix_steps"])
    train = [normalize(sequence, means, stds) for sequence in train_raw]
    test = [normalize(generated[u_value]["residuals"], means, stds) for u_value in physics["test_u"]]
    forecast_count = physics["steps"] - split["prefix_steps"]
    observed = [sequence[: split["prefix_steps"] + 1] for sequence in test]
    truths = [sequence[split["prefix_steps"] + 1 :] for sequence in test]
    threshold = contract["success"]["effective_horizon_normalized_error_threshold"]
    direct_results: Dict[str, Dict[str, float]] = {}
    direct_models: Dict[str, Dict[str, Any]] = {"PERSISTENCE": {"name": "PERSISTENCE", "parameters": 0, "state": 2, "ops": 2, "fit_rows": 0}}
    for name in ("AFFINE_DMD", "RIDGE_VAR4", "PRONY_AR8"):
        direct_models[name] = fit_direct(name, train, split["prefix_steps"], split["warmup_steps"], model_spec["ridge_lambda"])
    for name, model in direct_models.items():
        predictions = [forecast_direct(model, case, forecast_count) for case in observed]
        direct_results[name] = {**score(predictions, truths, split["purge_steps"], threshold), "parameters": model["parameters"], "state": model["state"], "ops": model["ops"], "fit_rows": model["fit_rows"]}
    candidate_runs = []
    for seed in model_spec["candidate_seeds"]:
        model = fit_reservoir(train, split["prefix_steps"], split["warmup_steps"], model_spec["ridge_lambda"], seed, model_spec["candidate_state_dimension"])
        predictions = [forecast_reservoir(model, case, forecast_count) for case in observed]
        candidate_runs.append({"seed": seed, **score(predictions, truths, split["purge_steps"], threshold), "parameters": model["parameters"], "state": model["state"], "ops": model["ops"], "fit_rows": model["fit_rows"]})
    candidate_nrmse = statistics.median(item["nrmse"] for item in candidate_runs)
    candidate_horizon = statistics.median(item["effective_horizon_steps"] for item in candidate_runs)
    best_nrmse_name = min(direct_results, key=lambda name: direct_results[name]["nrmse"])
    best_horizon_name = max(direct_results, key=lambda name: direct_results[name]["effective_horizon_steps"])
    best_nrmse = direct_results[best_nrmse_name]
    best_horizon = direct_results[best_horizon_name]
    nrmse_lift = (best_nrmse["nrmse"] - candidate_nrmse) / best_nrmse["nrmse"]
    horizon_lift = (candidate_horizon - best_horizon["effective_horizon_steps"]) / max(best_horizon["effective_horizon_steps"], 1)
    all_budget_pass = all(item["parameters"] <= budgets["trainable_or_fixed_scalar_parameters"] and item["state"] <= budgets["persistent_state_scalars"] and item["ops"] <= budgets["logical_scalar_operations_per_step"] for item in list(direct_results.values()) + candidate_runs)
    reduction = best_nrmse["nrmse"] <= candidate_nrmse * (1.0 + contract["success"]["direct_reduction_relative_nrmse_tolerance"]) and best_nrmse["parameters"] <= statistics.median(item["parameters"] for item in candidate_runs)
    kpi_pass = nrmse_lift >= contract["success"]["minimum_nrmse_improvement_fraction"] and horizon_lift >= contract["success"]["minimum_effective_horizon_improvement_fraction"]
    go = constraints_pass and all_budget_pass and kpi_pass and not reduction
    status = classify_status(constraints_pass, all_budget_pass, reduction, kpi_pass)
    contract_sha256 = sha256_path(contract_path)
    analysis_class = FROZEN_CONTRACTS[contract_sha256]["analysis_class"]
    result = {
        "schema": "agent_bridge.fermion_biocortex.fb_s1_same_u_tdhf_residual_receipt.v1",
        "status": status,
        "analysis_class": analysis_class,
        "confirmation_authority": False,
        "implementation_scope": "OFFLINE_TANH_PROXY_NOT_BIOCORTEX_RUNTIME_OR_HBR_R1_IMPLEMENTATION",
        "contract_sha256": contract_sha256,
        "benchmark_sha256": sha256_path(pathlib.Path(__file__).resolve()),
        "split": {"train_u": physics["train_u"], "development_u": physics["development_u"], "test_u": physics["test_u"], **split},
        "physics_constraints": {"maxima": maxima, "pass": constraints_pass, "same_u_verified": same_u_verified, "nominal": physics["nominal"]},
        "direct_baselines": direct_results,
        "candidate": model_spec["candidate"],
        "candidate_runs": candidate_runs,
        "candidate_primary": {"median_nrmse": candidate_nrmse, "median_effective_horizon_steps": candidate_horizon},
        "decision": {"best_direct_nrmse_baseline": best_nrmse_name, "best_direct_horizon_baseline": best_horizon_name, "nrmse_improvement_fraction": nrmse_lift, "effective_horizon_improvement_fraction": horizon_lift, "direct_reduction_detected": reduction, "static_candidate_budget_pass": static_budget_pass, "all_budget_caps_pass": all_budget_pass, "kpi_pass": kpi_pass, "go": go},
        "evaluation_inventory": {"fit_rows_per_fitted_model": len(physics["train_u"]) * (split["prefix_steps"] - split["warmup_steps"]), "scale_values_per_observable": len(physics["train_u"]) * (split["prefix_steps"] + 1)},
        "resource_caps": budgets,
        "nonclaims": contract["nonclaims"],
        "authority": contract["authority"],
    }
    assert_finite_tree(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=pathlib.Path, default=CONTRACT_PATH)
    parser.add_argument("--output", choices=("json", "summary"), default="json")
    args = parser.parse_args()
    tracemalloc.start()
    started = time.perf_counter()
    receipt = run(args.contract)
    receipt["scientific_result_sha256"] = hashlib.sha256(
        json.dumps(
            receipt,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_bytes = peak_rss if sys.platform == "darwin" else peak_rss * 1024
    receipt["resources"] = {
        "elapsed_seconds": elapsed,
        "python_peak_traced_bytes": peak,
        "process_peak_rss_bytes": peak_rss_bytes,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "portable_byte_identity": False,
    }
    if args.output == "summary":
        print(receipt["status"])
        print(json.dumps(receipt["decision"], sort_keys=True, allow_nan=False))
    else:
        print(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
