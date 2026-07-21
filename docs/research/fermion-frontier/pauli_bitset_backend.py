#!/usr/bin/env python3
"""Exact bitset Pauli arithmetic and deterministic expansion checkpoints.

This module is a performance/conformance prototype, not a certificate checker.
It deliberately has no authority to validate a fermion-to-qubit mapping, a
product-formula error bound, the physical L=8 workload, or any READY gate.

Encoding (with q0 stored in bit 0, matching the string character at index 0):

    I -> (x=0, z=0)    X -> (x=1, z=0)
    Y -> (x=1, z=1)    Z -> (x=0, z=1)

An n-qubit Pauli key is ``(x_mask, z_mask)``.  Multiplication returns the
power ``p`` in ``left * right = i**p * output``.  Sparse coefficients are
closed exact ``Fraction`` intervals.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any, Dict, List, Mapping, Sequence, Tuple


PROTOTYPE_STATUS = "BITSET_CONSISTENCY_AND_PERFORMANCE_PROTOTYPE_ONLY"
CHECKPOINT_FORMAT = "pauli_bitset_fraction_interval_checkpoint_v1"
SCOPE_CLAIMS = {
    "certificate_authority": "NONE",
    "fermion_to_qubit_mapping_identity": "NOT_ASSESSED",
    "product_formula_to_exact_hamiltonian": "NOT_ASSESSED",
    "physical_L8_instance_identity": "NOT_ASSESSED",
    "ready_gate_eligible": False,
}

MAX_QUBITS = 4_096
MAX_CHECKPOINT_TERMS = 65_536
MAX_RATIONAL_DIGITS = 256
MAX_CHECKPOINT_BYTES = 16 * 1_048_576
MAX_BATCH_GATES = 65_536

PauliKey = Tuple[int, int]
Interval = Tuple[Fraction, Fraction]
Expansion = Dict[PauliKey, Interval]
TermRecord = Tuple[PauliKey, Interval]
GateRecord = Tuple[PauliKey, Interval, Interval]


class BitsetSchemaError(ValueError):
    """The caller supplied a malformed or non-canonical value."""


class BitsetResourceError(BitsetSchemaError):
    """A hard prototype resource bound was exceeded."""


def _bounded_positive_integer(value: Any, name: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise BitsetSchemaError(f"{name} must be an integer in [1, {maximum}]")
    return value


def _validate_caps(
    max_qubits: Any,
    max_terms: Any,
    max_rational_digits: Any,
    max_bytes: Any,
) -> Tuple[int, int, int, int]:
    return (
        _bounded_positive_integer(max_qubits, "max_qubits", MAX_QUBITS),
        _bounded_positive_integer(max_terms, "max_terms", MAX_CHECKPOINT_TERMS),
        _bounded_positive_integer(
            max_rational_digits, "max_rational_digits", MAX_RATIONAL_DIGITS
        ),
        _bounded_positive_integer(max_bytes, "max_bytes", MAX_CHECKPOINT_BYTES),
    )


def _validate_n_qubits(n_qubits: Any, maximum: int = MAX_QUBITS) -> int:
    return _bounded_positive_integer(n_qubits, "n_qubits", maximum)


def _validate_key(key: Any, n_qubits: int, name: str = "Pauli key") -> PauliKey:
    if type(key) is not tuple or len(key) != 2:
        raise BitsetSchemaError(f"{name} must be an (x_mask, z_mask) tuple")
    x_mask, z_mask = key
    if type(x_mask) is not int or type(z_mask) is not int:
        raise BitsetSchemaError(f"{name} masks must be integers (not bools)")
    if x_mask < 0 or z_mask < 0:
        raise BitsetSchemaError(f"{name} masks must be non-negative")
    limit = 1 << n_qubits
    if x_mask >= limit or z_mask >= limit:
        raise BitsetSchemaError(f"{name} has bits outside the {n_qubits}-qubit width")
    return x_mask, z_mask


def pauli_string_to_masks(pauli: Any) -> PauliKey:
    """Convert a non-empty q0-first IXYZ string to ``(x_mask, z_mask)``."""

    if type(pauli) is not str or not pauli or len(pauli) > MAX_QUBITS:
        raise BitsetSchemaError("pauli must be a non-empty bounded IXYZ string")
    x_mask = 0
    z_mask = 0
    for qubit, operator in enumerate(pauli):
        if operator not in "IXYZ":
            raise BitsetSchemaError("pauli must contain only I, X, Y, and Z")
        if operator in "XY":
            x_mask |= 1 << qubit
        if operator in "YZ":
            z_mask |= 1 << qubit
    return x_mask, z_mask


def masks_to_pauli_string(x_mask: Any, z_mask: Any, n_qubits: Any) -> str:
    """Convert bit masks to the q0-first IXYZ string representation."""

    width = _validate_n_qubits(n_qubits)
    x_mask, z_mask = _validate_key((x_mask, z_mask), width)
    symbols = ("I", "X", "Z", "Y")
    output: List[str] = []
    for qubit in range(width):
        code = ((z_mask >> qubit) & 1) * 2 + ((x_mask >> qubit) & 1)
        output.append(symbols[code])
    return "".join(output)


def canonical_sort_key(key: Any) -> Tuple[int, int]:
    """Stable numeric order for already width-bounded ``(x_mask, z_mask)`` keys."""

    if type(key) is not tuple or len(key) != 2:
        raise BitsetSchemaError("Pauli key must be an (x_mask, z_mask) tuple")
    x_mask, z_mask = key
    if type(x_mask) is not int or type(z_mask) is not int:
        raise BitsetSchemaError("Pauli masks must be integers (not bools)")
    if x_mask < 0 or z_mask < 0:
        raise BitsetSchemaError("Pauli masks must be non-negative")
    return x_mask, z_mask


def pauli_multiply(left: Any, right: Any, n_qubits: Any) -> Tuple[int, PauliKey]:
    """Return ``(phase_power, key)`` for ``left * right`` exactly.

    For the Hermitian convention ``P(x,z)=i**popcount(x&z) X**x Z**z``, the
    phase is evaluated with integer popcounts and then reduced modulo four.
    """

    width = _validate_n_qubits(n_qubits)
    left_x, left_z = _validate_key(left, width, "left Pauli key")
    right_x, right_z = _validate_key(right, width, "right Pauli key")
    output = left_x ^ right_x, left_z ^ right_z
    phase = (
        (left_x & left_z).bit_count()
        + (right_x & right_z).bit_count()
        + 2 * (left_z & right_x).bit_count()
        - (output[0] & output[1]).bit_count()
    ) % 4
    return phase, output


def pauli_commutes(left: Any, right: Any, n_qubits: Any) -> bool:
    """Return the exact symplectic commutation predicate."""

    width = _validate_n_qubits(n_qubits)
    left_x, left_z = _validate_key(left, width, "left Pauli key")
    right_x, right_z = _validate_key(right, width, "right Pauli key")
    parity = ((left_x & right_z).bit_count() + (left_z & right_x).bit_count()) & 1
    return parity == 0


def anticommuting_branch(
    generator: Any, operator: Any, n_qubits: Any
) -> Tuple[int, PauliKey]:
    """Return ``(real_sign, key)`` for ``i * generator * operator``."""

    width = _validate_n_qubits(n_qubits)
    generator = _validate_key(generator, width, "generator")
    operator = _validate_key(operator, width, "operator")
    if pauli_commutes(generator, operator, width):
        raise BitsetSchemaError("anticommuting_branch requires anticommuting Paulis")
    phase, output = pauli_multiply(generator, operator, width)
    combined = (phase + 1) % 4
    if combined == 0:
        return 1, output
    if combined == 2:
        return -1, output
    raise AssertionError("i*generator*operator was unexpectedly non-Hermitian")


def _validate_fraction(value: Any, name: str, digit_limit: int) -> Fraction:
    if type(value) is not Fraction:
        raise BitsetSchemaError(f"{name} must be an exact Fraction")
    numerator_digits = len(str(abs(value.numerator)))
    denominator_digits = len(str(value.denominator))
    if numerator_digits > digit_limit or denominator_digits > digit_limit:
        raise BitsetResourceError(f"{name} exceeds the rational digit limit")
    return value


def _validate_interval(value: Any, name: str, digit_limit: int) -> Interval:
    if type(value) is not tuple or len(value) != 2:
        raise BitsetSchemaError(f"{name} must be a (lower, upper) tuple")
    lower = _validate_fraction(value[0], f"{name}.lower", digit_limit)
    upper = _validate_fraction(value[1], f"{name}.upper", digit_limit)
    if lower > upper:
        raise BitsetSchemaError(f"{name} has lower > upper")
    return lower, upper


def _format_fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _interval_add(left: Interval, right: Interval) -> Interval:
    return left[0] + right[0], left[1] + right[1]


def _interval_multiply(left: Interval, right: Interval) -> Interval:
    corners = (
        left[0] * right[0],
        left[0] * right[1],
        left[1] * right[0],
        left[1] * right[1],
    )
    return min(corners), max(corners)


def _interval_scale(value: Interval, scale: int) -> Interval:
    if scale == 1:
        return value
    if scale == -1:
        return -value[1], -value[0]
    raise AssertionError("Pauli branch scale must be +/-1")


def _validated_term_records(
    n_qubits: int,
    term_records: Any,
    max_terms: int,
    digit_limit: int,
) -> List[TermRecord]:
    if type(term_records) not in (list, tuple):
        raise BitsetSchemaError("term_records must be a bounded list or tuple")
    if len(term_records) > max_terms:
        raise BitsetResourceError("checkpoint term-count cap exceeded")
    output: List[TermRecord] = []
    seen = set()
    zero = (Fraction(0), Fraction(0))
    for index, record in enumerate(term_records):
        if type(record) is not tuple or len(record) != 2:
            raise BitsetSchemaError(f"term_records[{index}] must be (key, interval)")
        key = _validate_key(record[0], n_qubits, f"term_records[{index}].key")
        if key in seen:
            raise BitsetSchemaError("duplicate Pauli key in sparse expansion")
        seen.add(key)
        interval = _validate_interval(
            record[1], f"term_records[{index}].interval", digit_limit
        )
        if interval == zero:
            raise BitsetSchemaError("exact-zero entries are forbidden in sparse expansion")
        output.append((key, interval))
    output.sort(key=lambda record: canonical_sort_key(record[0]))
    return output


def canonical_checkpoint_payload(
    n_qubits: Any,
    term_records: Any,
    *,
    max_qubits: Any = MAX_QUBITS,
    max_terms: Any = MAX_CHECKPOINT_TERMS,
    max_rational_digits: Any = MAX_RATIONAL_DIGITS,
) -> Dict[str, Any]:
    """Build a canonical, order-independent JSON-compatible payload.

    ``term_records`` is intentionally a sequence rather than a mapping so a
    producer cannot hide duplicate keys before validation.  Coefficients must
    already be exact ``Fraction`` objects: rational strings, including
    non-reduced spellings such as ``"2/4"``, are rejected rather than parsed.
    """

    max_qubits, max_terms, digit_limit, _ = _validate_caps(
        max_qubits, max_terms, max_rational_digits, MAX_CHECKPOINT_BYTES
    )
    width = _validate_n_qubits(n_qubits, max_qubits)
    records = _validated_term_records(width, term_records, max_terms, digit_limit)
    terms = []
    for (x_mask, z_mask), (lower, upper) in records:
        terms.append(
            {
                "lower": _format_fraction(lower),
                "upper": _format_fraction(upper),
                "x_mask": f"0x{x_mask:x}",
                "z_mask": f"0x{z_mask:x}",
            }
        )
    return {
        "format": CHECKPOINT_FORMAT,
        "n_qubits": width,
        "prototype_status": PROTOTYPE_STATUS,
        "scope_claims": dict(SCOPE_CLAIMS),
        "term_count": len(terms),
        "terms": terms,
    }


def canonical_checkpoint_bytes(
    n_qubits: Any,
    term_records: Any,
    *,
    max_qubits: Any = MAX_QUBITS,
    max_terms: Any = MAX_CHECKPOINT_TERMS,
    max_rational_digits: Any = MAX_RATIONAL_DIGITS,
    max_bytes: Any = MAX_CHECKPOINT_BYTES,
) -> bytes:
    """Serialize the canonical checkpoint with stable UTF-8 JSON bytes.

    ``max_bytes`` caps emitted serialization bytes, not process peak memory: the
    canonical payload is constructed first.  The independent term-count and
    rational-digit caps keep that construction bounded.
    """

    max_qubits, max_terms, digit_limit, byte_limit = _validate_caps(
        max_qubits, max_terms, max_rational_digits, max_bytes
    )
    payload = canonical_checkpoint_payload(
        n_qubits,
        term_records,
        max_qubits=max_qubits,
        max_terms=max_terms,
        max_rational_digits=digit_limit,
    )
    encoder = json.JSONEncoder(
        ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    chunks: List[bytes] = []
    total_bytes = 0
    for chunk in encoder.iterencode(payload):
        encoded_chunk = chunk.encode("ascii")
        total_bytes += len(encoded_chunk)
        if total_bytes > byte_limit:
            raise BitsetResourceError("canonical checkpoint byte cap exceeded")
        chunks.append(encoded_chunk)
    return b"".join(chunks)


def checkpoint_sha256(
    n_qubits: Any,
    term_records: Any,
    **limits: Any,
) -> str:
    """Return the SHA-256 digest of ``canonical_checkpoint_bytes``."""

    return hashlib.sha256(
        canonical_checkpoint_bytes(n_qubits, term_records, **limits)
    ).hexdigest()


def expansion_term_records(expansion: Any) -> List[TermRecord]:
    """Copy a built-in sparse dictionary into duplicate-detectable records."""

    if type(expansion) is not dict:
        raise BitsetSchemaError("expansion must be a built-in dictionary")
    return list(expansion.items())


def _validate_expansion(
    expansion: Any,
    n_qubits: int,
    max_terms: int,
    digit_limit: int,
) -> Expansion:
    if type(expansion) is not dict:
        raise BitsetSchemaError("expansion must be a built-in dictionary")
    if len(expansion) > max_terms:
        raise BitsetResourceError("checkpoint term-count cap exceeded")
    records = _validated_term_records(
        n_qubits, expansion_term_records(expansion), max_terms, digit_limit
    )
    return dict(records)


def propagate_gate(
    expansion: Any,
    generator: Any,
    sine: Any,
    cosine: Any,
    n_qubits: Any,
    *,
    max_live_terms: Any = MAX_CHECKPOINT_TERMS,
    max_rational_digits: Any = MAX_RATIONAL_DIGITS,
) -> Expansion:
    """Apply one checker-compatible Heisenberg Pauli-rotation update.

    The convention is ``G_P(theta)=exp(-i theta P/2)`` and the returned
    operator is ``G_P(theta)^dagger O G_P(theta)``.  The supplied sine and
    cosine intervals are presumed to enclose ``sin(theta)`` and
    ``cos(theta)``; constructing those enclosures remains the checker's job.
    """

    width = _validate_n_qubits(n_qubits)
    live_limit = _bounded_positive_integer(
        max_live_terms, "max_live_terms", MAX_CHECKPOINT_TERMS
    )
    digit_limit = _bounded_positive_integer(
        max_rational_digits, "max_rational_digits", MAX_RATIONAL_DIGITS
    )
    source = _validate_expansion(expansion, width, live_limit, digit_limit)
    generator = _validate_key(generator, width, "generator")
    sine = _validate_interval(sine, "sine", digit_limit)
    cosine = _validate_interval(cosine, "cosine", digit_limit)

    output: Expansion = {}
    zero = (Fraction(0), Fraction(0))

    def add(key: PauliKey, coefficient: Interval) -> None:
        merged = _interval_add(output.get(key, zero), coefficient)
        _validate_interval(merged, "propagated coefficient", digit_limit)
        if merged == zero:
            output.pop(key, None)
        else:
            if key not in output and len(output) >= live_limit:
                raise BitsetResourceError("live-term resource cap exceeded")
            output[key] = merged

    for operator, coefficient in source.items():
        if pauli_commutes(generator, operator, width):
            add(operator, coefficient)
            continue
        sign, branch = anticommuting_branch(generator, operator, width)
        add(operator, _interval_multiply(coefficient, cosine))
        add(branch, _interval_scale(_interval_multiply(coefficient, sine), sign))
    return output


def propagate_batch(
    expansion: Any,
    gates: Any,
    n_qubits: Any,
    *,
    max_live_terms: Any = MAX_CHECKPOINT_TERMS,
    max_gates: Any = MAX_BATCH_GATES,
    max_rational_digits: Any = MAX_RATIONAL_DIGITS,
) -> Expansion:
    """Apply ``(generator, sine, cosine)`` records left-to-right.

    This mirrors the existing proof kernel's declared backpropagation order.
    It is an arithmetic adapter only and does not make a certificate claim.
    """

    width = _validate_n_qubits(n_qubits)
    gate_limit = _bounded_positive_integer(max_gates, "max_gates", MAX_BATCH_GATES)
    live_limit = _bounded_positive_integer(
        max_live_terms, "max_live_terms", MAX_CHECKPOINT_TERMS
    )
    digit_limit = _bounded_positive_integer(
        max_rational_digits, "max_rational_digits", MAX_RATIONAL_DIGITS
    )
    if type(gates) not in (list, tuple):
        raise BitsetSchemaError("gates must be a bounded list or tuple")
    if len(gates) > gate_limit:
        raise BitsetResourceError("batch gate-count cap exceeded")
    current = _validate_expansion(expansion, width, live_limit, digit_limit)
    for index, gate in enumerate(gates):
        if type(gate) is not tuple or len(gate) != 3:
            raise BitsetSchemaError(
                f"gates[{index}] must be (generator, sine, cosine)"
            )
        current = propagate_gate(
            current,
            gate[0],
            gate[1],
            gate[2],
            width,
            max_live_terms=live_limit,
            max_rational_digits=digit_limit,
        )
    return current
