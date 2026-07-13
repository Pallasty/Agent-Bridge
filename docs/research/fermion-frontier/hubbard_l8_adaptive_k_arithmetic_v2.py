#!/usr/bin/env python3
"""Pure high-cap fixed-tick arithmetic for future L=8 adaptive-K screens.

This module has no certificate authority and does not select an observable,
parent, budget, or output sidecar.  It source-pins the positive v1 arithmetic
checker only as a conformance oracle.  Formal v2 paths use the local counter,
multiply, merge, Pauli branch, gate propagation, digest, expectation, ranking,
suffix, and selection routines below; they never patch or call the root
counter, propagation, digest, or truncation implementations.
"""

from __future__ import annotations

import hashlib
import json
import types
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


HERE = Path(__file__).resolve().parent
KERNEL_FINGERPRINT = "hubbard_l8_adaptive_k_fixed_tick_arithmetic_v2"
CERTIFICATE_AUTHORITY = "NONE"
ROOT_SOURCE_PIN = {
    "relative_path": "hubbard_l8_observable_interval_step_checker.py",
    "sha256": "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a",
}

N_QUBITS = 128
TICK_DENOMINATOR = 1 << 64
TAYLOR_ORDER = 5
DIGEST_DOMAIN = b"l8_fixed_tick_interval_expansion_v1\n"

RESOURCE_LIMITS = {
    "max_source_bytes": 196_608,
    "max_retained_K": 524_288,
    "max_candidate_count": 32,
    "max_single_expansion_terms": 1_048_576,
    "max_digest_terms": 1_048_576,
    "max_term_gate_visits": 1_000_000_000,
    "max_expansion_coefficient_tick_bits": 192,
    "max_trigonometric_tick_bits": 66,
    "max_product_bits": 384,
    "max_suffix_accumulator_bits": 224,
}

PauliKey = Tuple[int, int]
TickInterval = Tuple[int, int]
TickExpansion = Dict[PauliKey, TickInterval]


class SchemaError(ValueError):
    """Malformed exact arithmetic input or a hard resource-limit failure."""


class VerificationError(ValueError):
    """A deterministic arithmetic invariant failed."""


def _exact_int(value: Any, name: str, *, nonnegative: bool = False) -> int:
    if type(value) is not int:
        raise SchemaError(f"{name} must be an exact integer")
    if nonnegative and value < 0:
        raise SchemaError(f"{name} must be nonnegative")
    return value


def _validate_key(key: Any, name: str = "Pauli key") -> PauliKey:
    if type(key) is not tuple or len(key) != 2:
        raise SchemaError(f"{name} must be an exact (x,z) tuple")
    x_mask = _exact_int(key[0], f"{name}.x", nonnegative=True)
    z_mask = _exact_int(key[1], f"{name}.z", nonnegative=True)
    if x_mask.bit_length() > N_QUBITS or z_mask.bit_length() > N_QUBITS:
        raise SchemaError(f"{name} exceeds the {N_QUBITS}-qubit mask width")
    return x_mask, z_mask


def _validate_interval(value: Any, name: str = "tick interval") -> TickInterval:
    if type(value) is not tuple or len(value) != 2:
        raise SchemaError(f"{name} must be an exact (lower,upper) tuple")
    lower = _exact_int(value[0], f"{name}.lower")
    upper = _exact_int(value[1], f"{name}.upper")
    if lower > upper:
        raise SchemaError(f"{name} is reversed")
    return lower, upper


def canonical_sha256(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise SchemaError("value cannot be canonically serialized") from exc
    return hashlib.sha256(payload).hexdigest()


def read_root_source_bytes() -> bytes:
    path = HERE / ROOT_SOURCE_PIN["relative_path"]
    with path.open("rb") as handle:
        payload = handle.read(RESOURCE_LIMITS["max_source_bytes"] + 1)
    if len(payload) > RESOURCE_LIMITS["max_source_bytes"]:
        raise SchemaError("root arithmetic source exceeds byte cap")
    if hashlib.sha256(payload).hexdigest() != ROOT_SOURCE_PIN["sha256"]:
        raise SchemaError("root arithmetic source pin drift")
    return payload


def compile_root_oracle(source: bytes | None = None) -> Any:
    payload = read_root_source_bytes() if source is None else source
    if type(payload) is not bytes:
        raise SchemaError("root source must be exact bytes")
    if hashlib.sha256(payload).hexdigest() != ROOT_SOURCE_PIN["sha256"]:
        raise SchemaError("root arithmetic source pin drift")
    module = types.ModuleType("pinned_l8_root_arithmetic_oracle_for_v2")
    module.__file__ = str(HERE / ROOT_SOURCE_PIN["relative_path"])
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    if (
        module.N_QUBITS != N_QUBITS
        or module.TICK_DENOMINATOR != TICK_DENOMINATOR
        or module.TAYLOR_ORDER != TAYLOR_ORDER
    ):
        raise VerificationError("root arithmetic convention drift")
    return module


def root_global_snapshot(root: Any) -> Dict[str, Any]:
    return {
        "retained_term_cap": root.RETAINED_TERM_CAP,
        "resource_limits": dict(root.RESOURCE_LIMITS),
        "tick_denominator": root.TICK_DENOMINATOR,
        "taylor_order": root.TAYLOR_ORDER,
    }


class PropagationCounterV2:
    def __init__(self) -> None:
        self.term_gate_visits = 0
        self.peak_live_terms = 0
        self.window_peak_live_terms = 0
        self.maximum_expansion_coefficient_tick_bits = 0
        self.maximum_product_bits = 0
        self.multiplication_rounding_l1_scaled_ticks_squared = 0

    def visit(self, count: int) -> None:
        count = _exact_int(count, "term-gate visit increment", nonnegative=True)
        self.term_gate_visits += count
        if self.term_gate_visits > RESOURCE_LIMITS["max_term_gate_visits"]:
            raise SchemaError("v2 term-gate visit cap exceeded")

    def observe_count(self, count: int) -> None:
        count = _exact_int(count, "live term count", nonnegative=True)
        self.peak_live_terms = max(self.peak_live_terms, count)
        self.window_peak_live_terms = max(self.window_peak_live_terms, count)
        if count > RESOURCE_LIMITS["max_single_expansion_terms"]:
            raise SchemaError("v2 single-expansion term cap exceeded")

    def observe(self, expansion: Mapping[PauliKey, TickInterval]) -> None:
        if type(expansion) is not dict:
            raise SchemaError("expansion must be an exact dict")
        self.observe_count(len(expansion))

    def begin_window(self, expansion: Mapping[PauliKey, TickInterval]) -> None:
        if type(expansion) is not dict:
            raise SchemaError("expansion must be an exact dict")
        self.window_peak_live_terms = len(expansion)
        self.observe_count(len(expansion))

    def observe_interval(self, value: TickInterval) -> None:
        lower, upper = _validate_interval(value)
        bits = max(abs(lower).bit_length(), abs(upper).bit_length())
        self.maximum_expansion_coefficient_tick_bits = max(
            self.maximum_expansion_coefficient_tick_bits, bits
        )
        if bits > RESOURCE_LIMITS["max_expansion_coefficient_tick_bits"]:
            raise SchemaError("v2 coefficient tick bit cap exceeded")

    def observe_product_bits(self, bits: int) -> None:
        bits = _exact_int(bits, "product bit count", nonnegative=True)
        self.maximum_product_bits = max(self.maximum_product_bits, bits)
        if bits > RESOURCE_LIMITS["max_product_bits"]:
            raise SchemaError("v2 tick product bit cap exceeded")


def multiply_ticks(
    left: TickInterval,
    right: TickInterval,
    counter: PropagationCounterV2,
) -> TickInterval:
    left = _validate_interval(left, "left interval")
    right = _validate_interval(right, "right interval")
    if not isinstance(counter, PropagationCounterV2):
        raise SchemaError("multiply_ticks requires PropagationCounterV2")
    products = (
        left[0] * right[0],
        left[0] * right[1],
        left[1] * right[0],
        left[1] * right[1],
    )
    product_bits = max(abs(value).bit_length() for value in products)
    counter.observe_product_bits(product_bits)
    minimum = min(products)
    maximum = max(products)
    lower = minimum // TICK_DENOMINATOR
    upper = -((-maximum) // TICK_DENOMINATOR)
    counter.multiplication_rounding_l1_scaled_ticks_squared += max(
        minimum - lower * TICK_DENOMINATOR,
        upper * TICK_DENOMINATOR - maximum,
    )
    return lower, upper


def add_tick_term(
    output: TickExpansion,
    key: PauliKey,
    value: TickInterval,
    counter: PropagationCounterV2,
) -> None:
    if type(output) is not dict:
        raise SchemaError("output expansion must be an exact dict")
    key = _validate_key(key)
    value = _validate_interval(value)
    if key in output:
        previous = output[key]
        value = previous[0] + value[0], previous[1] + value[1]
    if value == (0, 0):
        output.pop(key, None)
    else:
        output[key] = value
        counter.observe_interval(value)
    counter.observe_count(len(output))


def anticommuting_branch(generator: PauliKey, operator: PauliKey) -> Tuple[int, PauliKey]:
    gx, gz = _validate_key(generator, "generator")
    ox, oz = _validate_key(operator, "operator")
    output = gx ^ ox, gz ^ oz
    phase = (
        (gx & gz).bit_count()
        + (ox & oz).bit_count()
        + 2 * (gz & ox).bit_count()
        - (output[0] & output[1]).bit_count()
    ) % 4
    combined = (phase + 1) % 4
    if combined == 0:
        return 1, output
    if combined == 2:
        return -1, output
    raise VerificationError("anticommuting branch is unexpectedly non-Hermitian")


def propagate_gate(
    expansion: TickExpansion,
    generator: PauliKey,
    sine: TickInterval,
    cosine: TickInterval,
    counter: PropagationCounterV2,
) -> TickExpansion:
    if type(expansion) is not dict:
        raise SchemaError("expansion must be an exact dict")
    gx, gz = _validate_key(generator, "generator")
    sine = _validate_interval(sine, "sine interval")
    cosine = _validate_interval(cosine, "cosine interval")
    for trig_name, interval in (("sine", sine), ("cosine", cosine)):
        bits = max(abs(interval[0]).bit_length(), abs(interval[1]).bit_length())
        if bits > RESOURCE_LIMITS["max_trigonometric_tick_bits"]:
            raise SchemaError(f"{trig_name} interval exceeds trig bit cap")
    counter.observe(expansion)
    for coefficient in expansion.values():
        counter.observe_interval(coefficient)
    counter.visit(len(expansion))
    output: TickExpansion = {}
    for operator, coefficient in expansion.items():
        ox, oz = _validate_key(operator, "operator")
        coefficient = _validate_interval(coefficient, "coefficient")
        if (((gx & oz).bit_count() + (gz & ox).bit_count()) & 1) == 0:
            add_tick_term(output, operator, coefficient, counter)
        else:
            add_tick_term(
                output,
                operator,
                multiply_ticks(coefficient, cosine, counter),
                counter,
            )
            sign, branch = anticommuting_branch(generator, operator)
            value = multiply_ticks(coefficient, sine, counter)
            if sign == -1:
                value = -value[1], -value[0]
            add_tick_term(output, branch, value, counter)
    counter.observe(output)
    return output


def propagate_batch(
    expansion: TickExpansion,
    batch: Sequence[Tuple[PauliKey, Any]],
    trig_cache: Mapping[Any, Tuple[TickInterval, TickInterval]],
    counter: PropagationCounterV2,
) -> TickExpansion:
    if type(batch) not in (list, tuple) or not batch:
        raise SchemaError("batch must be a nonempty exact sequence")
    output = dict(expansion)
    counter.begin_window(output)
    for generator, theta in batch:
        if theta not in trig_cache:
            raise SchemaError("batch theta is absent from the trig cache")
        sine, cosine = trig_cache[theta]
        output = propagate_gate(output, generator, sine, cosine, counter)
    return output


def abs_upper(value: TickInterval) -> int:
    lower, upper = _validate_interval(value)
    return max(abs(lower), abs(upper))


def tick_digest(
    expansion: Mapping[PauliKey, TickInterval],
    keys: Sequence[PauliKey] | None = None,
) -> str:
    if type(expansion) is not dict:
        raise SchemaError("expansion must be an exact dict")
    if keys is None:
        selected_count = len(expansion)
        selected_source: Iterable[PauliKey] = expansion
    else:
        if type(keys) not in (list, tuple):
            raise SchemaError("tick digest keys must be an exact sequence")
        selected_count = len(keys)
        selected_source = keys
    if selected_count > RESOURCE_LIMITS["max_digest_terms"]:
        raise SchemaError("v2 tick digest term cap exceeded")
    selected = sorted(_validate_key(key) for key in selected_source)
    digest = hashlib.sha256()
    digest.update(DIGEST_DOMAIN)
    previous: PauliKey | None = None
    for raw_key in selected:
        key = raw_key
        if previous is not None and key == previous:
            raise SchemaError("tick digest key sequence contains duplicates")
        if key not in expansion:
            raise SchemaError("tick digest key is absent from expansion")
        lower, upper = _validate_interval(expansion[key])
        digest.update(f"{hex(key[0])},{hex(key[1])},{lower},{upper}\n".encode("ascii"))
        previous = key
    return digest.hexdigest()


def expectation_ticks(expansion: Mapping[PauliKey, TickInterval], basis: int) -> TickInterval:
    if type(expansion) is not dict:
        raise SchemaError("expansion must be an exact dict")
    if len(expansion) > RESOURCE_LIMITS["max_single_expansion_terms"]:
        raise SchemaError("expectation input exceeds live-term cap")
    basis = _exact_int(basis, "basis", nonnegative=True)
    if basis.bit_length() > N_QUBITS:
        raise SchemaError("basis exceeds qubit width")
    lower = 0
    upper = 0
    for raw_key, raw_interval in expansion.items():
        x_mask, z_mask = _validate_key(raw_key)
        interval = _validate_interval(raw_interval)
        bits = max(abs(interval[0]).bit_length(), abs(interval[1]).bit_length())
        if bits > RESOURCE_LIMITS["max_expansion_coefficient_tick_bits"]:
            raise SchemaError("expectation coefficient exceeds tick bit cap")
        if x_mask:
            continue
        if (z_mask & basis).bit_count() & 1:
            lower -= interval[1]
            upper -= interval[0]
        else:
            lower += interval[0]
            upper += interval[1]
    return lower, upper


def rank_with_suffix(expansion: TickExpansion) -> Tuple[List[PauliKey], List[int]]:
    if type(expansion) is not dict:
        raise SchemaError("expansion must be an exact dict")
    if len(expansion) > RESOURCE_LIMITS["max_single_expansion_terms"]:
        raise SchemaError("ranking input exceeds live-term cap")
    for key, value in expansion.items():
        _validate_key(key)
        interval = _validate_interval(value)
        bits = max(abs(interval[0]).bit_length(), abs(interval[1]).bit_length())
        if bits > RESOURCE_LIMITS["max_expansion_coefficient_tick_bits"]:
            raise SchemaError("ranking coefficient exceeds tick bit cap")
        if interval == (0, 0):
            raise SchemaError("ranking input contains an exact sparse zero")
    ranked = sorted(
        expansion,
        key=lambda key: (-abs_upper(expansion[key]), key[0], key[1]),
    )
    suffix = [0] * (len(ranked) + 1)
    for index in range(len(ranked) - 1, -1, -1):
        suffix[index] = suffix[index + 1] + abs_upper(expansion[ranked[index]])
        if suffix[index].bit_length() > RESOURCE_LIMITS["max_suffix_accumulator_bits"]:
            raise SchemaError("v2 suffix accumulator bit cap exceeded")
    return ranked, suffix


def validate_candidates(candidates: Sequence[int]) -> Tuple[int, ...]:
    if type(candidates) not in (list, tuple):
        raise SchemaError("candidate K values must be an exact sequence")
    if not candidates or len(candidates) > RESOURCE_LIMITS["max_candidate_count"]:
        raise SchemaError("candidate K count is outside the kernel cap")
    output = tuple(_exact_int(value, "candidate K") for value in candidates)
    if any(value <= 0 for value in output):
        raise SchemaError("candidate K values must be positive")
    if any(left >= right for left, right in zip(output, output[1:])):
        raise SchemaError("candidate K values must be strictly increasing")
    if output[-1] > RESOURCE_LIMITS["max_retained_K"]:
        raise SchemaError("candidate K exceeds the kernel retained cap")
    return output


def evaluate_candidates(
    pretruncation_count: int,
    suffix: Sequence[int],
    candidates: Sequence[int],
    cumulative_drop_ticks: int,
    prefix_cap_ticks: int,
) -> Tuple[List[Dict[str, Any]], int | None]:
    count = _exact_int(pretruncation_count, "pretruncation count", nonnegative=True)
    cumulative = _exact_int(cumulative_drop_ticks, "cumulative drop", nonnegative=True)
    prefix_cap = _exact_int(prefix_cap_ticks, "prefix cap", nonnegative=True)
    if count > RESOURCE_LIMITS["max_single_expansion_terms"]:
        raise SchemaError("candidate evaluation exceeds live-term cap")
    if cumulative.bit_length() > RESOURCE_LIMITS["max_suffix_accumulator_bits"]:
        raise SchemaError("cumulative drop exceeds accumulator bit cap")
    if prefix_cap.bit_length() > RESOURCE_LIMITS["max_suffix_accumulator_bits"]:
        raise SchemaError("prefix cap exceeds accumulator bit cap")
    candidate_values = validate_candidates(candidates)
    if type(suffix) not in (list, tuple) or len(suffix) != count + 1:
        raise SchemaError("suffix array length mismatch")
    if any(type(value) is not int or value < 0 for value in suffix):
        raise SchemaError("suffix entries must be nonnegative exact integers")
    if any(
        value.bit_length() > RESOURCE_LIMITS["max_suffix_accumulator_bits"]
        for value in suffix
    ):
        raise SchemaError("suffix entry exceeds accumulator bit cap")
    if any(suffix[index] < suffix[index + 1] for index in range(count)):
        raise SchemaError("suffix drop array must be nonincreasing")
    if suffix[-1] != 0:
        raise SchemaError("suffix drop array must end at zero")
    records: List[Dict[str, Any]] = []
    selected: int | None = None
    for index, configured_K in enumerate(candidate_values):
        effective = min(configured_K, count)
        drop = suffix[effective]
        feasible = cumulative + drop <= prefix_cap
        records.append(
            {
                "candidate_index": index,
                "configured_K": configured_K,
                "effective_retained_count": effective,
                "dropped_term_count": count - effective,
                "drop_ticks": str(drop),
                "E_after_if_selected_ticks": str(cumulative + drop),
                "feasible_under_current_prefix_cap": feasible,
            }
        )
        if selected is None and feasible:
            selected = index
    return records, selected


def commit_candidate(
    expansion: TickExpansion,
    ranked: Sequence[PauliKey],
    suffix: Sequence[int],
    candidates: Sequence[int],
    cumulative_drop_ticks: int,
    prefix_cap_ticks: int,
    selected_index: int,
) -> Tuple[TickExpansion, Dict[str, Any]]:
    selected_index = _exact_int(selected_index, "selected candidate index", nonnegative=True)
    if type(expansion) is not dict:
        raise SchemaError("expansion must be an exact dict")
    if type(ranked) is not list:
        raise SchemaError("ranked keys must be an exact list")
    if len(ranked) != len(expansion) or len(set(ranked)) != len(ranked):
        raise SchemaError("ranked keys are not a complete unique permutation")
    if set(ranked) != set(expansion):
        raise SchemaError("ranked keys do not match the expansion")
    previous_rank_key: Tuple[int, int, int] | None = None
    for key in ranked:
        key = _validate_key(key, "ranked key")
        interval = _validate_interval(expansion[key], "ranked coefficient")
        bits = max(abs(interval[0]).bit_length(), abs(interval[1]).bit_length())
        if bits > RESOURCE_LIMITS["max_expansion_coefficient_tick_bits"]:
            raise SchemaError("ranked coefficient exceeds tick bit cap")
        if interval == (0, 0):
            raise SchemaError("ranked expansion contains an exact sparse zero")
        rank_key = (-abs_upper(interval), key[0], key[1])
        if previous_rank_key is not None and rank_key <= previous_rank_key:
            raise SchemaError("ranked keys violate the canonical deterministic order")
        previous_rank_key = rank_key
    if type(suffix) is not list or len(suffix) != len(ranked) + 1:
        raise SchemaError("suffix array does not match the ranked expansion length")
    expected_suffix = 0
    if type(suffix[-1]) is not int or suffix[-1] != 0:
        raise SchemaError("suffix array must have an exact zero tail")
    for index in range(len(ranked) - 1, -1, -1):
        expected_suffix += abs_upper(expansion[ranked[index]])
        if type(suffix[index]) is not int or suffix[index] != expected_suffix:
            raise SchemaError("suffix array violates the canonical recurrence")
    candidate_records, expected_index = evaluate_candidates(
        len(ranked),
        suffix,
        candidates,
        cumulative_drop_ticks,
        prefix_cap_ticks,
    )
    if expected_index is None:
        raise VerificationError("no feasible candidate may be committed")
    if selected_index != expected_index:
        raise VerificationError("selected candidate is not the first feasible candidate")
    selected = candidate_records[selected_index]
    effective = selected["effective_retained_count"]
    retained_keys = list(ranked[:effective])
    dropped_keys = list(ranked[effective:])
    retained = {key: expansion[key] for key in retained_keys}
    dropped_ticks = sum(abs_upper(expansion[key]) for key in dropped_keys)
    if str(dropped_ticks) != selected.get("drop_ticks"):
        raise VerificationError("selected candidate drop disagrees with ranked suffix")
    minimum_retained = min((abs_upper(expansion[key]) for key in retained_keys), default=0)
    maximum_dropped = max((abs_upper(expansion[key]) for key in dropped_keys), default=0)
    if minimum_retained < maximum_dropped:
        raise VerificationError("deterministic ranking boundary invariant failed")
    return retained, {
        "configured_K": selected["configured_K"],
        "effective_retained_count": effective,
        "dropped_term_count": len(dropped_keys),
        "dropped_l1_ticks": dropped_ticks,
        "dropped_terms_sha256": tick_digest(expansion, dropped_keys),
        "retained_expansion_sha256": tick_digest(retained),
        "minimum_retained_abs_upper_ticks": minimum_retained,
        "maximum_dropped_abs_upper_ticks": maximum_dropped,
    }


def select_and_truncate(
    expansion: TickExpansion,
    candidates: Sequence[int],
    cumulative_drop_ticks: int,
    prefix_cap_ticks: int,
) -> Dict[str, Any]:
    ranked, suffix = rank_with_suffix(expansion)
    records, selected_index = evaluate_candidates(
        len(ranked), suffix, candidates, cumulative_drop_ticks, prefix_cap_ticks
    )
    if selected_index is None:
        return {
            "committed": False,
            "ranked": ranked,
            "candidate_records": records,
            "selected_candidate_index": None,
        }
    retained, truncation = commit_candidate(
        expansion,
        ranked,
        suffix,
        candidates,
        cumulative_drop_ticks,
        prefix_cap_ticks,
        selected_index,
    )
    return {
        "committed": True,
        "expansion": retained,
        "candidate_records": records,
        "selected_candidate_index": selected_index,
        "truncation": truncation,
    }
