#!/usr/bin/env python3
"""Independent integer oracle for the Majorana P3 local-defect certificate.

The accuracy core in this module deliberately does not use the host floating
point implementation.  Binary64 values are transported as their hexadecimal
payloads, decoded to exact :class:`fractions.Fraction` values, and rounded by a
small integer round-to-nearest-ties-to-even implementation.  Likewise, the
trigonometric oracle is an exact rational Taylor enclosure, not Python libm.

The Git-object/cgroup replay lifecycle is intentionally kept separate from the
mathematical core.  In particular, ``source_files`` is the outer checker's
custody closure, whereas ``runner_staged_files`` is the much smaller allowlist
that may be mounted into the Julia sandbox; parent result artifacts must never
be visible in that sandbox.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Iterable, Iterator, Mapping, Sequence
import uuid


BASE = Path(__file__).resolve().parent
FIXTURE_NAME = "majorana_certificate_p3_fixture.json"
POLICY_NAME = "majorana_certificate_p3_policy.json"
PRECOMMIT_CONTRACT_NAME = "majorana_certificate_p3_precommit_contract.json"
RESULT_CONTRACT_NAME = "majorana_certificate_p3_contract.json"
CERTIFICATE_NAME = "majorana_certificate_p3_certificate.json"
RESULT_TEST_NAME = "test_majorana_certificate_p3_result.py"
CHECKER_NAME = "majorana_certificate_p3_checker.py"
RUNNER_RELATIVE_PATH = "majorana_certificate_p3/majorana_p3_runner.jl"
P2_CHECKER_NAME = "majorana_certificate_p2_checker.py"
P0_CHECKER_NAME = "majorana_certificate_p0_checker.py"
RUNTIME_LOCK_NAME = "majorana_certificate_p0_runtime_lock.json"

MAXIMUM_STATUS = (
    "VERIFIED_MAJORANA_P3_L8_STAGGERED_MAGNETIZATION_ONE_FUSED_STEP_"
    "LOCAL_DEFECT_AND_TRUNCATION_OPERATOR_AND_NEEL_EXPECTATION_BOUND_"
    "SUBCERTIFICATE"
)
EXCEEDS_STATUS = (
    "VERIFIED_MAJORANA_P3_L8_ONE_FUSED_STEP_ERROR_BOUND_EXCEEDS_"
    "ALLOCATION_SUBCERTIFICATE"
)
CAP_STATUS = (
    "VERIFIED_MAJORANA_P3_L8_ONE_FUSED_STEP_ACCURACY_POLICY_CAP_"
    "EXCEEDED_SUBCERTIFICATE"
)
REQUIRED_PARENT_COMMIT = "c90014ed8569924350d5d3fce4959d31021e0461"
FIXTURE_CANONICAL_SHA256 = "bb252f4d7df4858fbceaae6ff22f2d6f56067f45446ec06604a8b5f937274d87"
POLICY_CANONICAL_SHA256 = "eb8cc956d0812feed78396d9425a81116d919a82007d831940acc6a57d8e0e85"

GRID_BITS = 128
GRID = 1 << GRID_BITS
MASK_WIDTH = 256
MASK_HEX_DIGITS = 64
FLOAT_HEX_DIGITS = 16
SIGN_MASK = 1 << 63
EXP_MASK = 0x7FF
FRACTION_MASK = (1 << 52) - 1
INFINITY_EXPONENT = 0x7FF
EPSILON_BITS = 0x3DD0000000000000
MAX_STDOUT_BYTES = 8_388_608
MAX_JSON_INTEGER_BITS = 4096
STAGE_GROUPS = ("H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1")
ALLOWED_ANGLES = ("-1/50", "-1/100", "-1/200", "1/200", "1/100", "1/50")
ABI_TARGETS = (
    ("ELF_DYNAMIC_LOADER", "/lib64/ld-linux-x86-64.so.2"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libc.so.6"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libdl.so.2"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libm.so.6"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libpthread.so.0"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/librt.so.1"),
)
LOCALE_TARGETS = tuple(
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/" + relative)
    for relative in (
        "LC_ADDRESS", "LC_COLLATE", "LC_CTYPE", "LC_IDENTIFICATION",
        "LC_MEASUREMENT", "LC_MESSAGES/SYS_LC_MESSAGES", "LC_MONETARY",
        "LC_NAME", "LC_NUMERIC", "LC_PAPER", "LC_TELEPHONE", "LC_TIME",
    )
)
REPLAY_ENVIRONMENT_TARGETS = tuple(sorted(ABI_TARGETS + LOCALE_TARGETS, key=lambda row: row[1]))


def _load_helper(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P0 = _load_helper("majorana_p3_p0_helper", BASE / P0_CHECKER_NAME)
P2 = _load_helper("majorana_p3_p2_helper", BASE / P2_CHECKER_NAME)
SchemaError = P0.SchemaError
VerificationError = P0.VerificationError
IndeterminateReplay = P2.IndeterminateReplay
canonical_bytes = P0.canonical_bytes
canonical_sha256 = P0.canonical_sha256
file_sha256 = P0.file_sha256
require_exact_keys = P0.require_exact_keys
require_sha256 = P0.require_sha256

PARENT_STATUS = P2.MAXIMUM_STATUS
RUNNER_STAGED_PATHS = (
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    "majorana_certificate_p2_fixture.json",
    "majorana_certificate_p3/majorana_p3_runner.jl",
    "majorana_certificate_p3_fixture.json",
)
RUNNER_FORBIDDEN_PATHS = (
    "majorana_certificate_p2_contract.json",
    "majorana_certificate_p2_certificate.json",
    "test_majorana_certificate_p2_result.py",
    RESULT_CONTRACT_NAME,
    CERTIFICATE_NAME,
    RESULT_TEST_NAME,
)
PRECOMMIT_SOURCE_PATHS = tuple(sorted((
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p0_checker.py",
    "majorana_certificate_p0_runtime_lock.json",
    "majorana_certificate_p1/majorana_p1_runner.jl",
    "majorana_certificate_p1_certificate.json",
    "majorana_certificate_p1_checker.py",
    "majorana_certificate_p1_contract.json",
    "majorana_certificate_p1_fixture.json",
    "majorana_certificate_p1_policy.json",
    "majorana_certificate_p1_precommit_contract.json",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    "majorana_certificate_p2_certificate.json",
    "majorana_certificate_p2_checker.py",
    "majorana_certificate_p2_contract.json",
    "majorana_certificate_p2_fixture.json",
    "majorana_certificate_p2_policy.json",
    "majorana_certificate_p2_precommit_contract.json",
    "majorana_certificate_p3/majorana_p3_runner.jl",
    "majorana_certificate_p3_checker.py",
    "majorana_certificate_p3_fixture.json",
    "majorana_certificate_p3_policy.json",
    "test_majorana_certificate_p1_result.py",
    "test_majorana_certificate_p1.py",
    "test_majorana_certificate_p2.py",
    "test_majorana_certificate_p2_result.py",
    "test_majorana_certificate_p3.py",
)))


def _coerce_bits(bits: int | str, context: str = "binary64 bits") -> int:
    if isinstance(bits, str):
        if len(bits) != FLOAT_HEX_DIGITS or any(c not in "0123456789abcdef" for c in bits):
            raise VerificationError(f"{context} must be lowercase hexadecimal16")
        return int(bits, 16)
    if type(bits) is not int or not 0 <= bits < (1 << 64):
        raise VerificationError(f"{context} must be an unsigned 64-bit integer")
    return bits


def _bits_hex(bits: int) -> str:
    return f"{_coerce_bits(bits):016x}"


def _mask_hex(mask: int) -> str:
    if type(mask) is not int or mask < 0 or mask.bit_length() > MASK_WIDTH:
        raise VerificationError("Majorana mask is outside UInt256")
    return f"{mask:064x}"


def decode_binary64_bits(bits: int | str) -> Fraction:
    """Decode a finite IEEE-754 binary64 payload as an exact rational."""

    payload = _coerce_bits(bits)
    negative = bool(payload & SIGN_MASK)
    exponent = (payload >> 52) & EXP_MASK
    fraction = payload & FRACTION_MASK
    if exponent == INFINITY_EXPONENT:
        raise SchemaError("non-finite binary64 payload")
    if exponent == 0:
        significand = fraction
        power = -1074
    else:
        significand = (1 << 52) | fraction
        power = exponent - 1023 - 52
    if significand == 0:
        return Fraction(0)
    if power >= 0:
        value = Fraction(significand << power)
    else:
        value = Fraction(significand, 1 << (-power))
    return -value if negative else value


def _round_divide_ties_even(numerator: int, denominator: int) -> int:
    if numerator < 0 or denominator <= 0:
        raise VerificationError("RNE divider requires nonnegative numerator")
    quotient, remainder = divmod(numerator, denominator)
    twice = remainder << 1
    if twice > denominator or (twice == denominator and quotient & 1):
        quotient += 1
    return quotient


def _floor_log2_fraction(value: Fraction) -> int:
    if value <= 0:
        raise VerificationError("log2 input must be positive")
    numerator, denominator = value.numerator, value.denominator
    exponent = numerator.bit_length() - denominator.bit_length()
    if exponent >= 0:
        if numerator < (denominator << exponent):
            exponent -= 1
    elif (numerator << (-exponent)) < denominator:
        exponent -= 1
    return exponent


def _fraction_to_bits_rne(value: Fraction) -> int:
    """Round an exact rational to binary64, using integer RNE only."""

    if not isinstance(value, Fraction):
        value = Fraction(value)
    if value == 0:
        return 0
    sign = SIGN_MASK if value < 0 else 0
    magnitude = abs(value)
    exponent = _floor_log2_fraction(magnitude)
    numerator, denominator = magnitude.numerator, magnitude.denominator
    if exponent >= -1022:
        shift = 52 - exponent
        if shift >= 0:
            significand = _round_divide_ties_even(numerator << shift, denominator)
        else:
            significand = _round_divide_ties_even(numerator, denominator << (-shift))
        if significand == (1 << 53):
            significand >>= 1
            exponent += 1
        if exponent > 1023:
            return sign | (INFINITY_EXPONENT << 52)
        if significand < (1 << 52):
            raise VerificationError("normal RNE significand underflow")
        return sign | ((exponent + 1023) << 52) | (significand - (1 << 52))
    subnormal = _round_divide_ties_even(numerator << 1074, denominator)
    if subnormal == 0:
        return sign
    if subnormal >= (1 << 52):
        if subnormal != (1 << 52):
            raise VerificationError("subnormal RNE overflow")
        return sign | (1 << 52)
    return sign | subnormal


def round_fraction_to_binary64_bits(value: Fraction) -> str:
    """Public hexadecimal wrapper for exact binary64 RNE."""

    return _bits_hex(_fraction_to_bits_rne(Fraction(value)))


def _rne_add_bits(left: int, right: int) -> int:
    left = _coerce_bits(left)
    right = _coerce_bits(right)
    total = decode_binary64_bits(left) + decode_binary64_bits(right)
    if total != 0:
        return _fraction_to_bits_rne(total)
    # IEEE RN: -0 + -0 is -0; mixed zeros and exact cancellation are +0.
    if (left & ~SIGN_MASK) == 0 and (right & ~SIGN_MASK) == 0:
        return SIGN_MASK if (left & SIGN_MASK) and (right & SIGN_MASK) else 0
    return 0


def _rne_mul_bits(left: int, right: int) -> int:
    left = _coerce_bits(left)
    right = _coerce_bits(right)
    sign = (left ^ right) & SIGN_MASK
    magnitude = abs(decode_binary64_bits(left) * decode_binary64_bits(right))
    result = _fraction_to_bits_rne(magnitude)
    return (result & ~SIGN_MASK) | sign


def binary64_add_bits(left: int | str, right: int | str) -> str:
    return _bits_hex(_rne_add_bits(_coerce_bits(left), _coerce_bits(right)))


def binary64_mul_bits(left: int | str, right: int | str) -> str:
    return _bits_hex(_rne_mul_bits(_coerce_bits(left), _coerce_bits(right)))


def _negate_bits(bits: int) -> int:
    return _coerce_bits(bits) ^ SIGN_MASK


def _factorial(value: int) -> int:
    if type(value) is not int or value < 0:
        raise VerificationError("factorial input must be nonnegative")
    output = 1
    for factor in range(2, value + 1):
        output *= factor
    return output


def _floor_scaled(value: Fraction, denominator: int) -> int:
    return (value.numerator * denominator) // value.denominator


def _ceil_scaled(value: Fraction, denominator: int) -> int:
    numerator = value.numerator * denominator
    return -((-numerator) // value.denominator)


def _ceil_grid(value: Fraction, denominator: int = GRID) -> int:
    if value < 0:
        raise VerificationError("defect upper must be nonnegative")
    result = _ceil_scaled(value, denominator)
    if result.bit_length() > 2048:
        raise VerificationError("defect tick exceeds the frozen BigInt bit cap")
    return result


def trig_interval_ticks(
    theta: Fraction,
    kind: str,
    order: int = 7,
    denominator: int = GRID,
) -> tuple[int, int]:
    """Return a rigorous outward sine or cosine interval on a fixed grid."""

    theta = Fraction(theta)
    if abs(theta) > Fraction(1, 50):
        raise VerificationError("P3 exact angle exceeds 1/50")
    if type(order) is not int or order < 0 or denominator <= 0:
        raise VerificationError("invalid trig enclosure policy")
    if kind not in ("sin", "cos"):
        raise VerificationError("trig kind must be sin or cos")
    point = Fraction(0)
    if kind == "sin":
        for index in range(order + 1):
            point += ((-1) ** index) * theta ** (2 * index + 1) / _factorial(2 * index + 1)
        remainder = abs(theta) ** (2 * order + 3) / _factorial(2 * order + 3)
    else:
        for index in range(order + 1):
            point += ((-1) ** index) * theta ** (2 * index) / _factorial(2 * index)
        remainder = abs(theta) ** (2 * order + 2) / _factorial(2 * order + 2)
    lower = _floor_scaled(point - remainder, denominator)
    upper = _ceil_scaled(point + remainder, denominator)
    if lower > upper:
        raise VerificationError("reversed trig interval")
    return lower, upper


def trig_table_intervals(theta: Fraction) -> dict[str, tuple[int, int]]:
    return {
        "sin": trig_interval_ticks(theta, "sin"),
        "cos": trig_interval_ticks(theta, "cos"),
    }


def local_product_defect_upper_ticks(
    coefficient_bits: int | str,
    trig_bits: int | str,
    trig_interval: tuple[int, int],
    sign: int = 1,
) -> int:
    """Bound one actual Float product against the true-trig product box."""

    if sign not in (-1, 1):
        raise VerificationError("Majorana branch sign must be +/-1")
    lower_tick, upper_tick = trig_interval
    if type(lower_tick) is not int or type(upper_tick) is not int or lower_tick > upper_tick:
        raise VerificationError("invalid trig interval ticks")
    coefficient_payload = _coerce_bits(coefficient_bits)
    trig_payload = _coerce_bits(trig_bits)
    actual_payload = _rne_mul_bits(coefficient_payload, trig_payload)
    if sign < 0:
        actual_payload = _negate_bits(actual_payload)
    coefficient = decode_binary64_bits(coefficient_payload)
    endpoints = (
        Fraction(sign) * coefficient * Fraction(lower_tick, GRID),
        Fraction(sign) * coefficient * Fraction(upper_tick, GRID),
    )
    ideal_lower, ideal_upper = min(endpoints), max(endpoints)
    actual = decode_binary64_bits(actual_payload)
    distance = max(abs(actual - ideal_lower), abs(actual - ideal_upper))
    return _ceil_grid(distance)


def merge_defect_upper_ticks(
    left_bits: int | str, right_bits: int | str, merged_bits: int | str
) -> int:
    left = _coerce_bits(left_bits)
    right = _coerce_bits(right_bits)
    merged = _coerce_bits(merged_bits)
    expected = _rne_add_bits(left, right)
    if merged != expected:
        raise VerificationError("merged bits do not equal independent binary64 RNE addition")
    exact_sum = decode_binary64_bits(left) + decode_binary64_bits(right)
    return _ceil_grid(abs(decode_binary64_bits(merged) - exact_sum))


def drop_defect_upper_ticks(bits: int | str) -> int:
    return _ceil_grid(abs(decode_binary64_bits(_coerce_bits(bits))))


def _majorana_commutes(left: int, right: int) -> bool:
    exponent = left.bit_count() * right.bit_count() - (left & right).bit_count()
    return exponent % 2 == 0


def _omega_lower(left: int, right: int) -> int:
    parity = 0
    pending = left
    while pending:
        low = pending & -pending
        index = low.bit_length() - 1
        parity ^= (right & (low - 1)).bit_count() & 1
        pending ^= low
    return parity


def _omega_self(value: int) -> int:
    weight = value.bit_count()
    return ((weight * weight - weight) // 2) & 1


def _majorana_product_target_sign(gate: int, source: int) -> tuple[int, int]:
    """Independently derive the anticommuting target and real sine sign."""

    omega = (gate.bit_count() * source.bit_count() - (gate & source).bit_count()) & 1
    if omega != 1:
        raise VerificationError("Majorana sine branch requested for commuting masks")
    phase_sign = -1 if (
        _omega_lower(gate, source)
        + _omega_self(gate) * _omega_self(source)
        + omega * (_omega_self(gate) + _omega_self(source) + 1)
    ) & 1 else 1
    # P0's independently checked conjugation convention is -imag(phase).
    return gate ^ source, -phase_sign


def _fock_diagonal(mask: int, occupied_fermions: Sequence[int]) -> int:
    if mask < 0 or mask.bit_length() > MASK_WIDTH:
        raise VerificationError("Fock mask is outside UInt256")
    paired = mask
    if ((paired ^ (paired >> 1)) & int("55" * 32, 16)) != 0:
        return 0
    occupied_mask = 0
    for fermion in occupied_fermions:
        if type(fermion) is not int or not 1 <= fermion <= 128:
            raise VerificationError("invalid occupied fermion")
        occupied_mask |= 1 << (2 * fermion - 2)
    exponent = (_omega_self(mask) + mask.bit_count() // 2) % 4
    if exponent not in (0, 2):
        raise VerificationError("non-real independent Fock phase")
    phase = 1 if exponent == 0 else -1
    return -phase if (mask & occupied_mask).bit_count() & 1 else phase


class CanonicalArrayDigest:
    """Streaming sha256(canonical_json(full_array)) without retaining rows."""

    def __init__(self) -> None:
        self._digest = hashlib.sha256()
        self._digest.update(b"[")
        self._count = 0

    def add(self, row: Mapping[str, Any]) -> None:
        if self._count:
            self._digest.update(b",")
        self._digest.update(canonical_bytes(dict(row)))
        self._count += 1

    @property
    def count(self) -> int:
        return self._count

    def hexdigest(self) -> str:
        clone = self._digest.copy()
        clone.update(b"]")
        return clone.hexdigest()


def _strict_large_json_loads(data: bytes) -> Any:
    """Duplicate-key/float rejecting parser with the P3 8 MiB stdout cap."""

    if len(data) > MAX_STDOUT_BYTES:
        raise SchemaError("P3 JSON exceeds the frozen stdout byte cap")

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise SchemaError(f"duplicate JSON key: {key}")
            output[key] = value
        return output

    def reject_float(_: str) -> Any:
        raise SchemaError("JSON floating-point numbers are forbidden")

    def parse_integer(text: str) -> int:
        if text == "-0":
            raise SchemaError("JSON negative zero is forbidden")
        value = int(text)
        if value.bit_length() > MAX_JSON_INTEGER_BITS:
            raise SchemaError("JSON integer exceeds the P3 bit cap")
        return value

    try:
        return json.loads(
            data.decode("utf-8"), object_pairs_hook=object_pairs,
            parse_float=reject_float, parse_int=parse_integer,
            parse_constant=reject_float,
        )
    except UnicodeDecodeError as error:
        raise SchemaError("P3 JSON is not UTF-8") from error
    except json.JSONDecodeError as error:
        raise SchemaError("invalid P3 JSON") from error


def strict_json_loads(data: bytes, *, source: str = "P3 JSON") -> Any:
    try:
        return _strict_large_json_loads(data)
    except (SchemaError, VerificationError):
        raise
    except Exception as error:
        raise SchemaError(f"invalid {source}") from error


def load_json(path: Path) -> Any:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise SchemaError(f"JSON input is not a regular file: {path}")
    return strict_json_loads(path.read_bytes(), source=str(path))


def expected_schedule() -> dict[str, Any]:
    """Return the frozen topology, independently rechecking every angle cast."""

    schedule = P2.expected_schedule()
    for composite in schedule["composites"]:
        previous_mask = -1
        for row in composite["constituents"]:
            mask = int(row["mask_hex"], 16)
            if mask <= previous_mask:
                raise VerificationError("constituent masks are not unsigned ascending")
            previous_mask = mask
            expected_bits = round_fraction_to_binary64_bits(Fraction(row["applied_angle"]))
            if row["applied_angle_Float64_bits_hex"] != expected_bits:
                raise VerificationError("P2 schedule angle bits fail integer RNE oracle")
    if (
        schedule["stage_count"], schedule["composite_count"],
        schedule["constituent_count"], schedule["truncation_boundary_count"],
    ) != (9, 512, 1152, 768):
        raise VerificationError("P3 frozen schedule totals mismatch")
    return schedule


def validate_fixture(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P3 fixture must be an object")
    if canonical_sha256(value) != FIXTURE_CANONICAL_SHA256:
        raise VerificationError("P3 fixture differs from the frozen semantic object")
    if value.get("schema_version") != 1 or value.get("fixture_id") != (
        "MAJORANA-P3-L8-FUSED-ONE-STEP-LOCAL-DEFECT-V1"
    ):
        raise SchemaError("unexpected P3 fixture identity")
    parent = value["required_parent"]
    if parent["commit"] != REQUIRED_PARENT_COMMIT or parent["status"] != PARENT_STATUS:
        raise VerificationError("P3 parent anchor mismatch")
    relation = value["frozen_execution_relation"]
    if (
        relation["constituent_count"] != 1152
        or relation["truncation_boundary_count"] != 768
        or relation["threshold_Float64_bits_hex"] != _bits_hex(EPSILON_BITS)
        or not relation["P3_must_freshly_execute_the_route"]
        or not relation["P2_result_is_post_replay_conformance_evidence_not_a_runner_input"]
    ):
        raise VerificationError("P3 execution relation mismatch")
    arithmetic = value["outward_arithmetic"]
    if (
        arithmetic["taylor_order"] != 7
        or int(arithmetic["trig_grid_denominator"]) != GRID
        or int(arithmetic["defect_grid_denominator"]) != GRID
        or arithmetic["maximum_BigInt_bit_length"] != 2048
    ):
        raise VerificationError("P3 outward arithmetic mismatch")
    if Fraction(value["allocation"]["prefix_total_error_allocation"]) != Fraction(1, 400000):
        raise VerificationError("P3 allocation mismatch")
    expected_schedule()
    return value


def validate_policy(value: Any, runtime_lock: Any = None) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P3 policy must be an object")
    if canonical_sha256(value) != POLICY_CANONICAL_SHA256:
        raise VerificationError("P3 policy differs from the frozen semantic object")
    if value.get("schema_version") != 1 or value.get("policy_id") != "MAJORANA-P3-S0":
        raise SchemaError("unexpected P3 policy identity")
    if value["maximum_positive_authority"]["status"] != MAXIMUM_STATUS:
        raise VerificationError("P3 maximum status mismatch")
    branches = {row["branch"]: row for row in value["legal_terminal_branches"]}
    expected = {
        "BOUND_WITHIN_PREFIX_ALLOCATION": MAXIMUM_STATUS,
        "BOUND_EXCEEDS_PREFIX_ALLOCATION": EXCEEDS_STATUS,
        "DETERMINISTIC_POLICY_CAP_EXCEEDED": CAP_STATUS,
    }
    for branch, status in expected.items():
        if branches.get(branch, {}).get("maximum_status") != status:
            raise VerificationError(f"P3 terminal status mismatch: {branch}")
    scope = value["scope_boundary"]
    if scope["physical_reference_qualified"] or scope["ready_gate_eligible"]:
        raise VerificationError("P3 scope promotes reference or READY")
    environment = value["replay_environment_custody"]
    targets = environment["exact_sandbox_regular_file_targets"]
    expected_targets = [
        {"role": role, "sandbox_path": path}
        for role, path in REPLAY_ENVIRONMENT_TARGETS
    ]
    if (
        targets != expected_targets
        or environment["exact_sandbox_regular_file_target_count"] != 18
        or environment["only_writable_host_backed_bind_mount_target"] != "/scratch"
        or environment["private_kernel_virtual_mount_targets"] != ["/dev", "/proc"]
        or environment["package_manifest_row_exact_keys"]
        != ["role", "sandbox_path", "mode", "size_bytes", "sha256"]
        or environment["canonical_witness_excludes_replay_environment_custody"] is not True
        or value["result_determinism"]["PID_namespace_unshared"] is not True
    ):
        raise VerificationError("P3 replay environment custody policy mismatch")
    if runtime_lock is not None:
        P0.validate_runtime_lock(runtime_lock)
    return value


def validate_precommit_contract(value: Any, base: Path = BASE) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P3 precommit contract must be an object")
    require_exact_keys(
        value,
        (
            "schema_version", "contract_type", "self_relative_path",
            "required_parent_commit", "result_artifacts_required_absent",
            "forbidden_formal_result_pins", "source_files",
            "runner_staged_files", "runner_forbidden_paths",
        ),
        "P3 precommit contract",
    )
    if (
        value["schema_version"] != 1
        or value["contract_type"]
        != "majorana_p3_result_unpinned_formal_replay_input_and_isolation_contract_v1"
        or value["self_relative_path"] != PRECOMMIT_CONTRACT_NAME
        or value["required_parent_commit"] != REQUIRED_PARENT_COMMIT
    ):
        raise VerificationError("P3 precommit parent mismatch")
    policy = validate_policy(P0.load_json(base / POLICY_NAME))
    if value["forbidden_formal_result_pins"] != policy["forbidden_formal_result_pins"]:
        raise VerificationError("P3 forbidden result pins mismatch")
    if tuple(value["result_artifacts_required_absent"]) != (
        RESULT_CONTRACT_NAME, CERTIFICATE_NAME, RESULT_TEST_NAME,
    ):
        raise VerificationError("P3 result artifact absence set mismatch")
    if tuple(value["runner_staged_files"]) != RUNNER_STAGED_PATHS:
        raise VerificationError("P3 runner staging allowlist mismatch")
    if tuple(value["runner_forbidden_paths"]) != RUNNER_FORBIDDEN_PATHS:
        raise VerificationError("P3 runner forbidden path set mismatch")
    rows = value["source_files"]
    if not isinstance(rows, list):
        raise SchemaError("P3 source_files must be an array")
    paths: list[str] = []
    for row in rows:
        require_exact_keys(row, ("relative_path", "size_bytes", "sha256"), "P3 source row")
        relative = row["relative_path"]
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise SchemaError("invalid P3 source relative path")
        path = base / relative
        if path.is_symlink() or not path.is_file():
            raise VerificationError(f"P3 source is not a regular file: {relative}")
        if type(row["size_bytes"]) is not int or row["size_bytes"] != path.stat().st_size:
            raise VerificationError(f"P3 source size mismatch: {relative}")
        require_sha256(row["sha256"], f"P3 source hash {relative}")
        if row["sha256"] != file_sha256(path):
            raise VerificationError(f"P3 source hash mismatch: {relative}")
        paths.append(relative)
    if tuple(paths) != PRECOMMIT_SOURCE_PATHS:
        raise VerificationError("P3 source custody allowlist mismatch")
    if not set(RUNNER_STAGED_PATHS).issubset(paths):
        raise VerificationError("P3 staging allowlist is outside source custody")
    if set(RUNNER_STAGED_PATHS) & set(RUNNER_FORBIDDEN_PATHS):
        raise VerificationError("P3 runner staging exposes a forbidden result")
    return value


def verify_precommit(base: Path = BASE) -> dict[str, Any]:
    fixture = validate_fixture(P0.load_json(base / FIXTURE_NAME))
    runtime = P0.validate_runtime_lock(P0.load_json(base / RUNTIME_LOCK_NAME))
    validate_policy(P0.load_json(base / POLICY_NAME), runtime)
    validate_precommit_contract(P0.load_json(base / PRECOMMIT_CONTRACT_NAME), base)
    parent_summary = P2.verify_final(base)
    if parent_summary["status"] != PARENT_STATUS:
        raise VerificationError("P3 direct parent result does not carry the required status")
    repo, base_relative = P2._repo_and_base_relative(base)
    resolved_parent = P2._run_git(repo, "rev-parse", REQUIRED_PARENT_COMMIT).stdout.decode().strip()
    if resolved_parent != REQUIRED_PARENT_COMMIT:
        raise VerificationError("P3 required parent is not the frozen full commit")
    parent_paths = (
        "majorana_certificate_p2_contract.json",
        "majorana_certificate_p2_certificate.json",
        "majorana_certificate_p2_fixture.json",
        "majorana_certificate_p2_policy.json",
        "majorana_certificate_p2/majorana_p2_runner.jl",
        "majorana_certificate_p2_checker.py",
        "test_majorana_certificate_p2_result.py",
    )
    for relative in parent_paths:
        committed = P2._run_git(
            repo, "show", f"{REQUIRED_PARENT_COMMIT}:{(base_relative / relative).as_posix()}"
        ).stdout
        if committed != (base / relative).read_bytes():
            raise VerificationError(f"P3 direct-parent bytes drifted: {relative}")
    parent_pins = fixture["required_parent"]
    pinned_fields = {
        "result_contract_sha256": "majorana_certificate_p2_contract.json",
        "certificate_sha256": "majorana_certificate_p2_certificate.json",
        "fixture_sha256": "majorana_certificate_p2_fixture.json",
        "policy_sha256": "majorana_certificate_p2_policy.json",
        "runner_sha256": "majorana_certificate_p2/majorana_p2_runner.jl",
        "checker_sha256": "majorana_certificate_p2_checker.py",
    }
    for field, relative in pinned_fields.items():
        if parent_pins[field] != file_sha256(base / relative):
            raise VerificationError(f"P3 fixture direct-parent pin mismatch: {field}")
    for artifact in (RESULT_CONTRACT_NAME, CERTIFICATE_NAME, RESULT_TEST_NAME):
        if (base / artifact).exists():
            raise VerificationError(f"P3 result artifact exists at precommit: {artifact}")
    return {
        "scope_ceiling": MAXIMUM_STATUS,
        "required_parent_commit": REQUIRED_PARENT_COMMIT,
        "required_parent_status": PARENT_STATUS,
        "parent_result_contract_sha256": parent_summary["result_contract_sha256"],
        "fixture_id": fixture["fixture_id"],
    }


def _format_q(value: Fraction) -> str:
    value = Fraction(value)
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _raw_term_digest(rows: Iterable[tuple[int, int]]) -> str:
    digest = hashlib.sha256()
    for mask, bits in rows:
        digest.update(_mask_hex(mask).encode("ascii"))
        digest.update(b"\t")
        digest.update(_bits_hex(bits).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _initial_state() -> dict[int, int]:
    state: dict[int, int] = {}
    magnitude = _fraction_to_bits_rne(Fraction(1, 128))
    for site0 in range(64):
        row, column = divmod(site0, 8)
        positive = (row + column) % 2 == 0
        site = site0 + 1
        up = (1 << (4 * site - 4)) | (1 << (4 * site - 3))
        down = (1 << (4 * site - 2)) | (1 << (4 * site - 1))
        state[up] = magnitude if positive else _negate_bits(magnitude)
        state[down] = _negate_bits(magnitude) if positive else magnitude
    return state


def _validate_trig_table(value: Any) -> dict[str, dict[str, Any]]:
    require_exact_keys(
        value,
        ("taylor_order", "grid_denominator", "entry_count", "entries", "entries_sha256"),
        "P3 trig table",
    )
    if value["taylor_order"] != 7 or value["grid_denominator"] != str(GRID):
        raise VerificationError("P3 trig table policy mismatch")
    entries = value["entries"]
    if not isinstance(entries, list) or len(entries) != value["entry_count"] or value["entry_count"] != 6:
        raise SchemaError("P3 trig table cardinality mismatch")
    if value["entries_sha256"] != canonical_sha256(entries):
        raise VerificationError("P3 trig table digest mismatch")
    lookup: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(entries):
        require_exact_keys(
            row,
            (
                "angle", "angle_Float64_bits_hex", "sine_Float64_bits_hex",
                "cosine_Float64_bits_hex", "sine_lower_ticks", "sine_upper_ticks",
                "cosine_lower_ticks", "cosine_upper_ticks",
            ),
            f"P3 trig row {index}",
        )
        if row["angle"] != ALLOWED_ANGLES[index]:
            raise VerificationError("P3 trig angles are not in frozen order")
        theta = Fraction(row["angle"])
        if row["angle_Float64_bits_hex"] != round_fraction_to_binary64_bits(theta):
            raise VerificationError("P3 trig angle cast mismatch")
        sine_interval = trig_interval_ticks(theta, "sin")
        cosine_interval = trig_interval_ticks(theta, "cos")
        if (row["sine_lower_ticks"], row["sine_upper_ticks"]) != tuple(map(str, sine_interval)):
            raise VerificationError("P3 sine enclosure mismatch")
        if (row["cosine_lower_ticks"], row["cosine_upper_ticks"]) != tuple(map(str, cosine_interval)):
            raise VerificationError("P3 cosine enclosure mismatch")
        sine_bits = _coerce_bits(row["sine_Float64_bits_hex"], "P3 sine bits")
        cosine_bits = _coerce_bits(row["cosine_Float64_bits_hex"], "P3 cosine bits")
        decode_binary64_bits(sine_bits)
        decode_binary64_bits(cosine_bits)
        lookup[row["angle"]] = {
            "sine_bits": sine_bits,
            "cosine_bits": cosine_bits,
            "sine_interval": sine_interval,
            "cosine_interval": cosine_interval,
        }
    return lookup


def _point_interval_defect(
    output_bits: int, coefficient_bits: int, interval: tuple[int, int], sign: int,
) -> int:
    coefficient = decode_binary64_bits(coefficient_bits) * sign
    left = coefficient * Fraction(interval[0], GRID)
    right = coefficient * Fraction(interval[1], GRID)
    point = decode_binary64_bits(output_bits)
    return _ceil_grid(max(abs(point - left), abs(point - right)))


def _public_p2_counters(counters: Mapping[str, int]) -> dict[str, int]:
    return {
        "cap_scan_term_visits": counters["cap_scan"],
        "propagation_term_visits": counters["propagation"],
        "truncation_term_visits": counters["truncation"],
        "final_evaluation_term_visits": counters["final"],
        "total_charged_term_visits": sum(counters.values()),
    }


def _public_accuracy_counters(counters: Mapping[str, int]) -> dict[str, int]:
    return {
        "anticommuting_event_count": counters["anticommuting"],
        "product_defect_event_count": counters["product"],
        "merge_defect_event_count": counters["merge"],
        "drop_defect_event_count": counters["drop"],
        "accuracy_charged_event_count": counters["product"] + counters["merge"] + counters["drop"],
    }


def _neel_gamma_mask() -> int:
    occupied = 0
    for site0 in range(64):
        row, column = divmod(site0, 8)
        site = site0 + 1
        fermion = 2 * site - 1 if (row + column) % 2 == 0 else 2 * site
        occupied |= 1 << (2 * fermion - 2)
    return occupied


def _fock_diagonal_mask(mask: int, occupied_mask: int) -> int:
    if ((mask ^ (mask >> 1)) & int("55" * 32, 16)) != 0:
        return 0
    exponent = (_omega_self(mask) + mask.bit_count() // 2) % 4
    if exponent not in (0, 2):
        raise VerificationError("non-real independent Fock phase")
    phase = 1 if exponent == 0 else -1
    return -phase if (mask & occupied_mask).bit_count() & 1 else phase


def _upstream_fock_real_bits(mask: int, occupied_mask: int) -> int:
    """Reproduce only the signed-zero diagnostic of the frozen Fock loop."""

    phase_exponent = _omega_self(mask)
    for fermion0 in range(128):
        first = (mask >> (2 * fermion0)) & 1
        second = (mask >> (2 * fermion0 + 1)) & 1
        if first != second:
            # Complex phase times +0.0 has a negative real zero only at -1.
            return SIGN_MASK if phase_exponent % 4 == 2 else 0
        if first:
            occupied = (occupied_mask >> (2 * fermion0)) & 1
            phase_exponent += -1 if occupied else 1
    element = _fock_diagonal_mask(mask, occupied_mask)
    return _negate_bits(_fraction_to_bits_rne(Fraction(1))) if element < 0 else _fraction_to_bits_rne(Fraction(1))


def replay_accuracy_oracle(trig_table: Mapping[str, Any]) -> dict[str, Any]:
    """Replay all 1,152 Float64 constituents with integer-only binary64 RNE."""

    trig = _validate_trig_table(trig_table)
    schedule = expected_schedule()
    state = _initial_state()
    transitions: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []
    p2_transition_digest = CanonicalArrayDigest()
    p2_boundary_digest = CanonicalArrayDigest()
    p2_stage_digest = CanonicalArrayDigest()
    p2 = {"cap_scan": 0, "propagation": 0, "truncation": 0, "final": 0}
    accuracy = {"anticommuting": 0, "product": 0, "merge": 0, "drop": 0}
    ticks = {"product": 0, "merge": 0, "drop": 0}
    peak_premerge = len(state)
    peak_postmerge = len(state)
    total_splits = total_drops = total_zero_drops = 0
    cumulative_drop_bits = 0
    completed_composites = completed_constituents = completed_boundaries = 0

    for stage_index, group in enumerate(STAGE_GROUPS):
        stage_composites = [c for c in schedule["composites"] if c["stage_index"] == stage_index]
        stage_input = len(state)
        stage_peak_pre = stage_peak_post = stage_input
        splits_before, drops_before = total_splits, total_drops
        p2_before = dict(p2)
        accuracy_before = dict(accuracy)
        ticks_before = dict(ticks)
        for composite in stage_composites:
            for public in composite["constituents"]:
                gate = int(public["mask_hex"], 16)
                input_count = len(state)
                p2["cap_scan"] += input_count
                p2["propagation"] += input_count
                source_masks = sorted(mask for mask in state if not _majorana_commutes(gate, mask))
                anti_count = len(source_masks)
                accuracy["anticommuting"] += anti_count
                accuracy["product"] += 2 * anti_count
                angle_data = trig[public["applied_angle"]]
                main = dict(state)
                aux: dict[int, int] = {}
                contribution_digest = CanonicalArrayDigest()
                transition_product_ticks = 0
                for source in source_masks:
                    coefficient = state[source]
                    target, sign = _majorana_product_target_sign(gate, source)
                    cosine_output = _rne_mul_bits(coefficient, angle_data["cosine_bits"])
                    signed_sine = angle_data["sine_bits"] if sign > 0 else _negate_bits(angle_data["sine_bits"])
                    sine_output = _rne_mul_bits(coefficient, signed_sine)
                    cosine_ticks = _point_interval_defect(
                        cosine_output, coefficient, angle_data["cosine_interval"], 1,
                    )
                    sine_ticks = _point_interval_defect(
                        sine_output, coefficient, angle_data["sine_interval"], sign,
                    )
                    transition_product_ticks += cosine_ticks + sine_ticks
                    contribution_digest.add({
                        "source_mask_hex": _mask_hex(source),
                        "target_mask_hex": _mask_hex(target),
                        "branch_sign": sign,
                        "input_coefficient_Float64_bits_hex": _bits_hex(coefficient),
                        "cosine_output_Float64_bits_hex": _bits_hex(cosine_output),
                        "sine_output_Float64_bits_hex": _bits_hex(sine_output),
                        "cosine_product_defect_ticks": str(cosine_ticks),
                        "sine_product_defect_ticks": str(sine_ticks),
                    })
                    main[source] = cosine_output
                    if target in aux:
                        raise VerificationError("independent Majorana target map is not injective")
                    aux[target] = sine_output
                ticks["product"] += transition_product_ticks
                premerge_count = len(main) + len(aux)
                total_splits += anti_count
                peak_premerge = max(peak_premerge, premerge_count)
                stage_peak_pre = max(stage_peak_pre, premerge_count)
                collision_masks = sorted(set(main).intersection(aux))
                accuracy["merge"] += len(collision_masks)
                merge_digest = CanonicalArrayDigest()
                transition_merge_ticks = 0
                for mask in collision_masks:
                    left, right = main[mask], aux[mask]
                    merged = _rne_add_bits(left, right)
                    defect = _ceil_grid(abs(
                        decode_binary64_bits(merged)
                        - decode_binary64_bits(left) - decode_binary64_bits(right)
                    ))
                    transition_merge_ticks += defect
                    merge_digest.add({
                        "mask_hex": _mask_hex(mask),
                        "main_premerge_coefficient_Float64_bits_hex": _bits_hex(left),
                        "aux_premerge_coefficient_Float64_bits_hex": _bits_hex(right),
                        "merged_coefficient_Float64_bits_hex": _bits_hex(merged),
                        "merge_defect_ticks": str(defect),
                    })
                    main[mask] = merged
                for mask, value in aux.items():
                    if mask not in main:
                        main[mask] = value
                ticks["merge"] += transition_merge_ticks
                state = main
                postmerge_count = len(state)
                peak_postmerge = max(peak_postmerge, postmerge_count)
                stage_peak_post = max(stage_peak_post, postmerge_count)

                transition_drop_ticks = 0
                transition_drop_events = 0
                boundary_record = None
                if public["boundary_after"]:
                    p2["truncation"] += postmerge_count
                    dropped = sorted(
                        (mask, bits) for mask, bits in state.items()
                        if (bits & ~SIGN_MASK) < EPSILON_BITS
                    )
                    transition_drop_events = len(dropped)
                    accuracy["drop"] += transition_drop_events
                    drop_digest = CanonicalArrayDigest()
                    for mask, bits in dropped:
                        defect = drop_defect_upper_ticks(bits)
                        transition_drop_ticks += defect
                        drop_digest.add({
                            "mask_hex": _mask_hex(mask),
                            "coefficient_Float64_bits_hex": _bits_hex(bits),
                            "drop_defect_ticks": str(defect),
                        })
                    ticks["drop"] += transition_drop_ticks
                    diagnostic_increment_bits = 0
                    zero_count = 0
                    for _mask_value, bits in dropped:
                        magnitude = bits & ~SIGN_MASK
                        zero_count += magnitude == 0
                        diagnostic_increment_bits = _rne_add_bits(diagnostic_increment_bits, magnitude)
                    cumulative_drop_bits = _rne_add_bits(
                        cumulative_drop_bits, diagnostic_increment_bits,
                    )
                    for mask, _bits in dropped:
                        del state[mask]
                    retained_count = len(state)
                    total_drops += transition_drop_events
                    total_zero_drops += zero_count
                    p2_boundary = {
                        "boundary_index": public["boundary_index_after"],
                        "stage_index": stage_index,
                        "group": group,
                        "composite_index": composite["composite_index"],
                        "after_constituent_index": public["constituent_index"],
                        "boundary_kind": "after_constituent" if composite["truncate_after_each_constituent"] else "after_complete_composite",
                        "postmerge_term_count": postmerge_count,
                        "retained_term_count": retained_count,
                        "threshold_dropped_term_count": transition_drop_events,
                        "exact_zero_dropped_term_count": zero_count,
                        "dropped_term_stream_sha256": _raw_term_digest(dropped),
                        "dropped_abs_sum_Float64_diagnostic_bits_hex": _bits_hex(diagnostic_increment_bits),
                        "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex": _bits_hex(cumulative_drop_bits),
                    }
                    p2_boundary_digest.add(p2_boundary)
                    boundary_record = dict(p2_boundary)
                    boundary_record.update({
                        "drop_defect_event_count": transition_drop_events,
                        "drop_defect_ticks": str(transition_drop_ticks),
                        "drop_rows_sha256": drop_digest.hexdigest(),
                        "cumulative_product_defect_ticks": str(ticks["product"]),
                        "cumulative_merge_defect_ticks": str(ticks["merge"]),
                        "cumulative_drop_defect_ticks": str(ticks["drop"]),
                        "cumulative_total_operator_error_ticks": str(sum(ticks.values())),
                        "cumulative_accuracy_charged_event_count": accuracy["product"] + accuracy["merge"] + accuracy["drop"],
                    })
                    boundaries.append(boundary_record)
                    completed_boundaries += 1

                p2_transition = {
                    "constituent_index": public["constituent_index"],
                    "composite_index": composite["composite_index"],
                    "stage_index": stage_index,
                    "group": group,
                    "mask_hex": public["mask_hex"],
                    "applied_angle": public["applied_angle"],
                    "input_term_count": input_count,
                    "anticommuting_split_count": anti_count,
                    "premerge_contribution_count": premerge_count,
                    "postmerge_unique_term_count": postmerge_count,
                    "boundary_index_after": public["boundary_index_after"],
                    "retained_term_count_after_boundary": None if boundary_record is None else boundary_record["retained_term_count"],
                }
                p2_transition_digest.add(p2_transition)
                transition = dict(p2_transition)
                transition.update({
                    "product_defect_event_count": 2 * anti_count,
                    "product_defect_ticks": str(transition_product_ticks),
                    "product_contribution_rows_sha256": contribution_digest.hexdigest(),
                    "merge_defect_event_count": len(collision_masks),
                    "merge_defect_ticks": str(transition_merge_ticks),
                    "merge_collision_rows_sha256": merge_digest.hexdigest(),
                    "drop_defect_event_count": transition_drop_events,
                    "drop_defect_ticks": str(transition_drop_ticks),
                    "cumulative_product_defect_ticks": str(ticks["product"]),
                    "cumulative_merge_defect_ticks": str(ticks["merge"]),
                    "cumulative_drop_defect_ticks": str(ticks["drop"]),
                    "cumulative_total_operator_error_ticks": str(sum(ticks.values())),
                    "accuracy_charged_event_count_increment": 2 * anti_count + len(collision_masks) + transition_drop_events,
                    "cumulative_accuracy_charged_event_count": accuracy["product"] + accuracy["merge"] + accuracy["drop"],
                })
                transitions.append(transition)
                completed_constituents += 1
            completed_composites += 1

        p2_stage = {
            "stage_index": stage_index,
            "group": group,
            "input_term_count": stage_input,
            "final_retained_term_count": len(state),
            "peak_premerge_contribution_count": stage_peak_pre,
            "peak_postmerge_unique_term_count": stage_peak_post,
            "anticommuting_split_count": total_splits - splits_before,
            "threshold_dropped_term_count": total_drops - drops_before,
            "cap_scan_term_visits_increment": p2["cap_scan"] - p2_before["cap_scan"],
            "propagation_term_visits_increment": p2["propagation"] - p2_before["propagation"],
            "truncation_term_visits_increment": p2["truncation"] - p2_before["truncation"],
        }
        p2_stage_digest.add(p2_stage)
        stage_row = dict(p2_stage)
        stage_row.update({
            "product_defect_event_count_increment": accuracy["product"] - accuracy_before["product"],
            "product_defect_ticks_increment": str(ticks["product"] - ticks_before["product"]),
            "merge_defect_event_count_increment": accuracy["merge"] - accuracy_before["merge"],
            "merge_defect_ticks_increment": str(ticks["merge"] - ticks_before["merge"]),
            "drop_defect_event_count_increment": accuracy["drop"] - accuracy_before["drop"],
            "drop_defect_ticks_increment": str(ticks["drop"] - ticks_before["drop"]),
            "total_operator_error_ticks_increment": str(sum(ticks[key] - ticks_before[key] for key in ticks)),
            "cumulative_total_operator_error_ticks": str(sum(ticks.values())),
            "accuracy_charged_event_count_increment": sum(
                accuracy[key] - accuracy_before[key] for key in ("product", "merge", "drop")
            ),
            "cumulative_accuracy_charged_event_count": accuracy["product"] + accuracy["merge"] + accuracy["drop"],
        })
        stages.append(stage_row)

    final_rows = sorted(state.items())
    p2["final"] += len(final_rows)
    occupied_mask = _neel_gamma_mask()
    exact_center = Fraction(0)
    p2_expectation_bits = 0
    p2_expectation_stream = hashlib.sha256()
    expectation_digest = CanonicalArrayDigest()
    one_bits = _fraction_to_bits_rne(Fraction(1))
    minus_one_bits = _negate_bits(one_bits)
    for mask, coefficient in final_rows:
        element = _fock_diagonal_mask(mask, occupied_mask)
        exact_contribution = decode_binary64_bits(coefficient) * element
        exact_center += exact_contribution
        multiplier = _upstream_fock_real_bits(mask, occupied_mask)
        float_contribution = _rne_mul_bits(coefficient, multiplier)
        p2_expectation_bits = _rne_add_bits(p2_expectation_bits, float_contribution)
        p2_expectation_stream.update(_mask_hex(mask).encode("ascii"))
        p2_expectation_stream.update(b"\t")
        p2_expectation_stream.update(_bits_hex(float_contribution).encode("ascii"))
        p2_expectation_stream.update(b"\n")
        expectation_digest.add({
            "mask_hex": _mask_hex(mask),
            "coefficient_Float64_bits_hex": _bits_hex(coefficient),
            "fock_diagonal_element": element,
            "exact_dyadic_contribution": _format_q(exact_contribution),
        })
    center_lower = _floor_scaled(exact_center, GRID)
    center_upper = _ceil_scaled(exact_center, GRID)
    total_ticks = sum(ticks.values())
    declared_lower = center_lower - total_ticks
    declared_upper = center_upper + total_ticks
    final_state = {
        "retained_term_count": len(final_rows),
        "term_stream_sha256": _raw_term_digest(final_rows),
        "checkerboard_Neel_occupied_mask_hex": _mask_hex(occupied_mask),
        "checkerboard_Neel_independent_occupied_gamma_mask_hex": _mask_hex(occupied_mask),
        "checkerboard_Neel_up_count": 32,
        "checkerboard_Neel_down_count": 32,
        "checkerboard_Neel_expectation_Float64_diagnostic_bits_hex": _bits_hex(p2_expectation_bits),
        "checkerboard_Neel_contribution_stream_sha256": p2_expectation_stream.hexdigest(),
        "checkerboard_Neel_expectation_rows_sha256": expectation_digest.hexdigest(),
        "checkerboard_Neel_exact_dyadic_center": _format_q(exact_center),
        "center_lower_ticks": str(center_lower),
        "center_upper_ticks": str(center_upper),
        "declared_expectation_lower_ticks": str(declared_lower),
        "declared_expectation_upper_ticks": str(declared_upper),
        "declared_expectation_interval": {
            "lower": _format_q(Fraction(declared_lower, GRID)),
            "upper": _format_q(Fraction(declared_upper, GRID)),
        },
        "Float64_reduction_is_diagnostic_only": True,
        "exact_dyadic_center_and_declared_interval_are_authoritative": True,
    }
    p2_public = _public_p2_counters(p2)
    accuracy_public = _public_accuracy_counters(accuracy)
    execution = {
        "completed_composite_count": completed_composites,
        "completed_constituent_count": completed_constituents,
        "completed_truncation_boundary_count": completed_boundaries,
        "peak_premerge_contribution_count": peak_premerge,
        "peak_postmerge_unique_term_count": peak_postmerge,
        "anticommuting_split_count": total_splits,
        "threshold_dropped_term_count": total_drops,
        "exact_zero_dropped_term_count": total_zero_drops,
        "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex": _bits_hex(cumulative_drop_bits),
        "P2_resource_counters": p2_public,
        "accuracy_counters": accuracy_public,
        "total_P2_plus_accuracy_charged_event_count": p2_public["total_charged_term_visits"] + accuracy_public["accuracy_charged_event_count"],
        "P2_transition_records_sha256": p2_transition_digest.hexdigest(),
        "P2_boundary_records_sha256": p2_boundary_digest.hexdigest(),
        "P2_stage_records_sha256": p2_stage_digest.hexdigest(),
        "transition_records": transitions,
        "transition_records_sha256": canonical_sha256(transitions),
        "boundary_records": boundaries,
        "boundary_records_sha256": canonical_sha256(boundaries),
        "stage_records": stages,
        "stage_records_sha256": canonical_sha256(stages),
        "cap_event": None,
    }
    ledger = dict(accuracy_public)
    ledger.update({
        "product_defect_ticks": str(ticks["product"]),
        "merge_defect_ticks": str(ticks["merge"]),
        "drop_defect_ticks": str(ticks["drop"]),
        "total_operator_error_ticks": str(total_ticks),
        "grid_denominator": str(GRID),
        "allocation_rational": "1/400000",
        "allocation_grid_ceiling_ticks_diagnostic_only": str((GRID + 399999) // 400000),
        "strictly_within_allocation": total_ticks * 400000 < GRID,
        "strict_comparison": "total_operator_error_ticks_times_400000_strictly_less_than_2_pow_128",
        "outward_widening_is_absorbed_in_each_local_upper_not_added_again": True,
        "coefficient_L1_bounds_operator_norm": True,
        "no_future_L1_amplification_from_exact_unitary_conjugation": True,
    })
    return {
        "initial_observable": P2.expected_initial_observable(),
        "schedule": schedule,
        "execution": execution,
        "accuracy_ledger": ledger,
        "final_state": final_state,
    }


EXPECTED_SCOPE = {
    "maximum_positive_status": MAXIMUM_STATUS,
    "fixed_L8_first_fused_mapped_step_exact_prefix_only": True,
    "freshly_executed_Float64_threshold_path": "ASSESSED_BY_LOCAL_DEFECT_AND_DROP_BOUND",
    "operator_norm_error_enclosure": "ASSESSED",
    "checkerboard_Neel_expectation_enclosure": "ASSESSED",
    "global_coefficientwise_interval_state": "NOT_CLAIMED",
    "exact_arithmetic_threshold_drop_set": "NOT_CLAIMED_EQUAL",
    "raw_1280_constituent_threshold_path": "NOT_EXECUTED",
    "double_occupancy": "NOT_ASSESSED",
    "existing_Python_topL1_route_result_equality": "NOT_CLAIMED",
    "remaining_99_mapped_steps_or_full_R100": "NOT_ASSESSED",
    "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}


def _status_for_terminal_branch(branch: str) -> str:
    statuses = {
        "BOUND_WITHIN_PREFIX_ALLOCATION": MAXIMUM_STATUS,
        "BOUND_EXCEEDS_PREFIX_ALLOCATION": EXCEEDS_STATUS,
        "DETERMINISTIC_POLICY_CAP_EXCEEDED": CAP_STATUS,
    }
    if branch not in statuses:
        raise VerificationError("illegal P3 terminal branch")
    return statuses[branch]


def _validate_parent_p2_conformance(witness: Mapping[str, Any], fixture: Mapping[str, Any]) -> None:
    parent_path = BASE / "majorana_certificate_p2_contract.json"
    if file_sha256(parent_path) != fixture["required_parent"]["result_contract_sha256"]:
        raise VerificationError("P3 post-replay P2 contract custody mismatch")
    parent = load_json(parent_path)["witness"]
    if witness["initial_observable"] != parent["initial_observable"]:
        raise VerificationError("P3 initial observable differs from certified P2 replay")
    if witness["schedule"] != parent["schedule"]:
        raise VerificationError("P3 schedule differs from certified P2 replay")
    execution, p2_execution = witness["execution"], parent["execution"]
    direct_fields = (
        "completed_composite_count", "completed_constituent_count",
        "completed_truncation_boundary_count", "peak_premerge_contribution_count",
        "peak_postmerge_unique_term_count", "anticommuting_split_count",
        "threshold_dropped_term_count", "exact_zero_dropped_term_count",
        "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex",
    )
    for field in direct_fields:
        if execution[field] != p2_execution[field]:
            raise VerificationError(f"P3 execution differs from certified P2 replay: {field}")
    if execution["P2_resource_counters"] != p2_execution["counters"]:
        raise VerificationError("P3 resource counters differ from certified P2 replay")
    digest_fields = (
        ("P2_transition_records_sha256", "transition_records_sha256"),
        ("P2_boundary_records_sha256", "boundary_records_sha256"),
        ("P2_stage_records_sha256", "stage_records_sha256"),
    )
    for p3_field, p2_field in digest_fields:
        if execution[p3_field] != p2_execution[p2_field]:
            raise VerificationError(f"P3 digest differs from certified P2 replay: {p3_field}")
    final, p2_final = witness["final_state"], parent["final_state"]
    final_fields = (
        "retained_term_count", "term_stream_sha256",
        "checkerboard_Neel_occupied_mask_hex", "checkerboard_Neel_up_count",
        "checkerboard_Neel_down_count",
        "checkerboard_Neel_expectation_Float64_diagnostic_bits_hex",
        "checkerboard_Neel_contribution_stream_sha256",
    )
    for field in final_fields:
        if final[field] != p2_final[field]:
            raise VerificationError(f"P3 final state differs from certified P2 replay: {field}")


def validate_witness(
    witness: Any,
    fixture: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    p2_fixture: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Validate runner custody fields and compare every replayed semantic field."""

    require_exact_keys(
        witness,
        (
            "schema_version", "witness_type", "fixture_id", "fixture_sha256",
            "fixture_canonical_sha256", "inherited_P2_fixture_sha256",
            "inherited_P2_fixture_canonical_sha256", "terminal_branch", "status",
            "runtime", "upstream", "initial_observable", "schedule", "trig_table",
            "execution", "accuracy_ledger", "final_state", "scope",
        ),
        "P3 witness",
    )
    if (
        witness["schema_version"] != 1
        or witness["witness_type"] != "majorana_p3_L8_one_fused_step_local_defect_v1"
        or witness["fixture_id"] != fixture["fixture_id"]
    ):
        raise SchemaError("unexpected P3 witness identity")
    if witness["fixture_sha256"] != file_sha256(BASE / FIXTURE_NAME):
        raise VerificationError("P3 witness fixture raw digest mismatch")
    if witness["fixture_canonical_sha256"] != FIXTURE_CANONICAL_SHA256:
        raise VerificationError("P3 witness fixture canonical digest mismatch")
    if p2_fixture is None:
        p2_fixture = P0.load_json(BASE / "majorana_certificate_p2_fixture.json")
    P2.validate_fixture(p2_fixture)
    if witness["inherited_P2_fixture_sha256"] != file_sha256(BASE / "majorana_certificate_p2_fixture.json"):
        raise VerificationError("P3 inherited P2 fixture raw digest mismatch")
    if witness["inherited_P2_fixture_canonical_sha256"] != canonical_sha256(p2_fixture):
        raise VerificationError("P3 inherited P2 fixture canonical digest mismatch")
    if witness["runtime"] != P2._expected_runtime(runtime_lock):
        raise VerificationError("P3 runtime custody mismatch")
    if witness["upstream"] != P2._expected_upstream(runtime_lock):
        raise VerificationError("P3 upstream source custody mismatch")
    if witness["scope"] != EXPECTED_SCOPE:
        raise VerificationError("P3 scope boundary mismatch")
    replay = replay_accuracy_oracle(witness["trig_table"])
    for field in ("initial_observable", "schedule", "execution", "accuracy_ledger", "final_state"):
        if witness[field] != replay[field]:
            raise VerificationError(f"P3 independent replay mismatch: {field}")
    _validate_parent_p2_conformance(witness, fixture)
    expected_branch = (
        "BOUND_WITHIN_PREFIX_ALLOCATION"
        if replay["accuracy_ledger"]["strictly_within_allocation"]
        else "BOUND_EXCEEDS_PREFIX_ALLOCATION"
    )
    if witness["terminal_branch"] != expected_branch:
        raise VerificationError("P3 terminal branch differs from exact tick comparison")
    if witness["status"] != _status_for_terminal_branch(expected_branch):
        raise VerificationError("P3 status differs from terminal branch authority")
    return witness


def _outer_commit_closure(
    repo: Path, base_relative: Path, commit: str, contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    pins = {row["relative_path"]: row for row in contract["source_files"]}
    rows: list[dict[str, Any]] = []
    for relative in (*PRECOMMIT_SOURCE_PATHS, PRECOMMIT_CONTRACT_NAME):
        mode, blob, body = P2._git_blob(repo, commit, (base_relative / relative).as_posix())
        if relative in pins:
            pin = pins[relative]
            if len(body) != pin["size_bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
                raise VerificationError(f"P3 committed outer input differs from pin: {relative}")
        elif body != (BASE / PRECOMMIT_CONTRACT_NAME).read_bytes():
            raise VerificationError("P3 committed precommit contract differs from active bytes")
        rows.append({
            "relative_path": relative, "git_mode": mode, "git_blob": blob,
            "size_bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
        })
    for relative in contract["result_artifacts_required_absent"]:
        if P2._git_path_exists(repo, commit, (base_relative / relative).as_posix()):
            raise VerificationError(f"P3 result artifact exists in precommit: {relative}")
    return rows


def _stage_runner_tree(
    repo: Path, base_relative: Path, commit: str,
    contract: Mapping[str, Any], destination: Path,
) -> list[dict[str, Any]]:
    pins = {row["relative_path"]: row for row in contract["source_files"]}
    rows: list[dict[str, Any]] = []
    if tuple(contract["runner_staged_files"]) != RUNNER_STAGED_PATHS:
        raise VerificationError("P3 runner staging allowlist drift")
    for relative in RUNNER_STAGED_PATHS:
        mode, blob, body = P2._git_blob(repo, commit, (base_relative / relative).as_posix())
        pin = pins[relative]
        if len(body) != pin["size_bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
            raise VerificationError(f"P3 staged Git blob differs from pin: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        rows.append({
            "relative_path": relative, "git_mode": mode, "git_blob": blob,
            "size_bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
        })
    if any((destination / relative).exists() for relative in RUNNER_FORBIDDEN_PATHS):
        raise VerificationError("P3 runner staging exposes a forbidden result")
    return rows


def _host_abi_mounts_and_custody(
    snapshot_root: Path | None = None,
) -> tuple[list[tuple[Path, str]], list[dict[str, Any]]]:
    mounts: list[tuple[Path, str]] = []
    rows: list[dict[str, Any]] = []
    for role, destination in ABI_TARGETS:
        source = Path(destination).resolve()
        if source.is_symlink() or not source.is_file():
            raise IndeterminateReplay(f"required host ABI file is unavailable: {destination}")
        body = source.read_bytes()
        mount_source = source
        if snapshot_root is not None:
            mount_source = snapshot_root / destination.lstrip("/")
            mount_source.parent.mkdir(parents=True, exist_ok=True)
            mount_source.write_bytes(body)
            mount_source.chmod(source.stat().st_mode & 0o777)
        mounts.append((mount_source, destination))
        rows.append({
            "role": role, "sandbox_path": destination,
            "mode": source.stat().st_mode & 0o777, "size_bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        })
    for role, destination in LOCALE_TARGETS:
        path = Path(destination)
        if path.is_symlink() or not path.is_file():
            raise IndeterminateReplay(f"required locale file is unavailable: {destination}")
        body = path.read_bytes()
        mount_source = path.resolve()
        if snapshot_root is not None:
            mount_source = snapshot_root / destination.lstrip("/")
            mount_source.parent.mkdir(parents=True, exist_ok=True)
            mount_source.write_bytes(body)
            mount_source.chmod(path.stat().st_mode & 0o777)
        mounts.append((mount_source, destination))
        rows.append({
            "role": role, "sandbox_path": destination,
            "mode": path.stat().st_mode & 0o777, "size_bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        })
    rows.sort(key=lambda row: row["sandbox_path"])
    if tuple((row["role"], row["sandbox_path"]) for row in rows) != REPLAY_ENVIRONMENT_TARGETS:
        raise IndeterminateReplay("host replay environment target set differs from frozen policy")
    return mounts, rows


def _run_one_isolated_replay(
    staging: Path, julia_executable: Path, depot: Path, run_root: Path,
    fixture: Mapping[str, Any], abi_mounts: Sequence[tuple[Path, str]],
) -> bytes:
    for executable in ("bwrap", "systemd-run", "systemctl"):
        if shutil.which(executable) is None:
            raise IndeterminateReplay(f"{executable} is required for P3 formal replay")
    cgroup = subprocess.run(
        ["stat", "-fc", "%T", "/sys/fs/cgroup"], capture_output=True, check=False,
    )
    if cgroup.stdout.strip() != b"cgroup2fs":
        raise IndeterminateReplay("P3 formal replay requires cgroup v2")
    scratch = run_root / "scratch"
    for relative in ("depot", "home", "tmp"):
        (scratch / relative).mkdir(parents=True, exist_ok=False)
    verified_julia = julia_executable.resolve()
    runtime_root = verified_julia.parent.parent
    if verified_julia != (runtime_root / "bin" / "julia").resolve():
        raise IndeterminateReplay("sandbox Julia executable differs from the verified runtime_root/bin/julia")
    bwrap = [
        "bwrap", "--die-with-parent", "--unshare-net", "--unshare-pid",
        "--ro-bind", str(staging), "/repo",
        "--ro-bind", str(runtime_root), "/runtime",
        "--ro-bind", str(depot), "/depot-ro",
        "--bind", str(scratch), "/scratch",
        "--proc", "/proc", "--dev", "/dev",
        "--dir", "/lib64", "--dir", "/usr", "--dir", "/usr/lib",
        "--dir", "/usr/lib/x86_64-linux-gnu", "--dir", "/usr/lib/locale",
        "--dir", "/usr/lib/locale/C.utf8",
        "--dir", "/usr/lib/locale/C.utf8/LC_MESSAGES",
    ]
    for source, destination in abi_mounts:
        bwrap.extend(("--ro-bind", str(source), destination))
    bwrap.extend((
        "--clearenv", "--setenv", "HOME", "/scratch/home",
        "--setenv", "TMPDIR", "/scratch/tmp", "--setenv", "LANG", "C.UTF-8",
        "--setenv", "LC_ALL", "C.UTF-8", "--setenv", "JULIA_DEPOT_PATH",
        "/scratch/depot:/depot-ro", "--setenv", "JULIA_LOAD_PATH", "@",
        "--setenv", "JULIA_NUM_THREADS", "1", "--setenv", "OPENBLAS_NUM_THREADS", "1",
        "--setenv", "JULIA_PKG_OFFLINE", "true", "--setenv", "JULIA_PKG_SERVER", "",
        "--chdir", "/repo", "/runtime/bin/julia", "--startup-file=no",
        "--history-file=no", "--compiled-modules=no", "--project=/repo/majorana_certificate_p0",
        "/repo/majorana_certificate_p3/majorana_p3_runner.jl",
        "/repo/majorana_certificate_p3_fixture.json",
        "/repo/majorana_certificate_p2_fixture.json",
    ))
    host = fixture["host_supervisor_caps"]
    unit = f"majorana-p3-{uuid.uuid4().hex}"
    command = [
        "systemd-run", "--user", "--scope", "--quiet", f"--unit={unit}",
        "-p", f"MemoryMax={host['MemoryMax_bytes']}",
        "-p", f"RuntimeMaxSec={host['RuntimeMaxSec']}", "--", *bwrap,
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    stdout_exceeded, stderr_exceeded = threading.Event(), threading.Event()
    readers = (
        threading.Thread(target=P2._read_limited_stream, args=(
            process.stdout, host["maximum_stdout_bytes"], stdout_chunks, stdout_exceeded,
        ), daemon=True),
        threading.Thread(target=P2._read_limited_stream, args=(
            process.stderr, host["maximum_stderr_bytes"], stderr_chunks, stderr_exceeded,
        ), daemon=True),
    )
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + host["subprocess_safety_timeout_seconds"]
    reason = None
    while process.poll() is None:
        if stdout_exceeded.is_set() or stderr_exceeded.is_set():
            reason = "stdout/stderr byte cap"
            break
        if time.monotonic() >= deadline:
            reason = "outer safety timeout"
            break
        time.sleep(0.01)
    if reason:
        P2._kill_systemd_scope(unit, process)
    try:
        returncode = process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        P2._kill_systemd_scope(unit, process)
        try:
            returncode = process.wait(timeout=10)
        except subprocess.TimeoutExpired as error:
            raise IndeterminateReplay("P3 scope termination failure") from error
    for reader in readers:
        reader.join(timeout=10)
    stdout, stderr = b"".join(stdout_chunks), b"".join(stderr_chunks)
    if reason:
        raise IndeterminateReplay(f"P3 host resource abort: {reason}")
    if stdout_exceeded.is_set() or len(stdout) > host["maximum_stdout_bytes"]:
        raise IndeterminateReplay("P3 isolated replay exceeded stdout cap")
    if stderr_exceeded.is_set() or len(stderr) > host["maximum_stderr_bytes"]:
        raise IndeterminateReplay("P3 isolated replay exceeded stderr cap")
    if returncode != 0 or stderr:
        diagnostic = stderr.decode("utf-8", errors="replace")[-4000:]
        raise IndeterminateReplay(f"P3 isolated replay failed ({returncode}): {diagnostic}")
    return stdout


def fresh_replay(
    precommit_commit: str, julia_executable: Path, depot: Path, base: Path = BASE,
) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    validate_policy(load_json(base / POLICY_NAME), runtime_lock)
    contract = validate_precommit_contract(load_json(base / PRECOMMIT_CONTRACT_NAME), base)
    verify_precommit(base)
    repo, base_relative = P2._verify_generation_git_state(precommit_commit, contract, base)
    P0._verify_julia_runtime(Path(julia_executable), runtime_lock)
    depot = Path(depot).resolve()
    depot_before = P0._verify_depot_custody(depot, runtime_lock)
    _live_mounts, abi_before = _host_abi_mounts_and_custody()
    outer_manifest = _outer_commit_closure(repo, base_relative, precommit_commit, contract)
    with tempfile.TemporaryDirectory(prefix="majorana-p3-formal-") as temporary:
        root = Path(temporary)
        environment_snapshot = root / "environment-snapshot"
        environment_snapshot.mkdir()
        abi_mounts, abi_snapshot = _host_abi_mounts_and_custody(environment_snapshot)
        if abi_snapshot != abi_before:
            raise IndeterminateReplay("host ABI/locale changed while taking replay snapshot")
        environment_snapshot_digest = P0._tree_digest(environment_snapshot)
        staging = root / "runner-staging"
        staging.mkdir()
        runner_manifest = _stage_runner_tree(
            repo, base_relative, precommit_commit, contract, staging,
        )
        staging_before = P0._tree_digest(staging)
        outputs: list[bytes] = []
        witnesses: list[Mapping[str, Any]] = []
        for index in range(2):
            run_root = root / f"run-{index + 1}"
            run_root.mkdir()
            output = _run_one_isolated_replay(
                staging, Path(julia_executable), depot, run_root, fixture, abi_mounts,
            )
            witness = strict_json_loads(output, source=f"P3 Julia replay {index + 1} stdout")
            if output != canonical_bytes(witness) + b"\n":
                raise VerificationError("P3 Julia stdout is not canonical JSON plus newline")
            validate_witness(witness, fixture, runtime_lock)
            outputs.append(output)
            witnesses.append(witness)
        if outputs[0] != outputs[1]:
            raise VerificationError("two fresh P3 Julia stdout byte streams differ")
        if P0._tree_digest(staging) != staging_before:
            raise VerificationError("P3 runner staging was modified")
        if P0._tree_digest(environment_snapshot) != environment_snapshot_digest:
            raise IndeterminateReplay("captured host ABI/locale snapshot changed during replay")
    if P0._verify_depot_custody(depot, runtime_lock) != depot_before:
        raise VerificationError("P3 replay modified pinned depot custody")
    _mounts_after, abi_after = _host_abi_mounts_and_custody()
    if abi_after != abi_before:
        raise IndeterminateReplay("host ABI/locale custody changed during P3 replay")
    if P2._run_git(repo, "rev-parse", "HEAD").stdout.decode().strip() != precommit_commit:
        raise VerificationError("HEAD changed during P3 replay")
    if P2._run_git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise VerificationError("worktree changed during P3 replay")
    witness = witnesses[0]
    transcript = hashlib.sha256(outputs[0]).hexdigest()
    return {
        "schema_version": 1,
        "package_type": "majorana_p3_formal_fresh_replay_package_v1",
        "precommit_commit_sha": precommit_commit,
        "precommit_contract_sha256": file_sha256(base / PRECOMMIT_CONTRACT_NAME),
        "outer_custody_manifest": outer_manifest,
        "outer_custody_manifest_sha256": canonical_sha256(outer_manifest),
        "runner_staging_manifest": runner_manifest,
        "runner_staging_manifest_sha256": canonical_sha256(runner_manifest),
        "runner_staging_tree_sha256": staging_before,
        "depot_custody": depot_before,
        "host_abi_and_locale_custody": abi_after,
        "host_abi_and_locale_custody_sha256": canonical_sha256(abi_after),
        "network_isolation": "bubblewrap_unshared_network_namespace",
        "PID_isolation": "bubblewrap_unshared_PID_namespace",
        "mount_isolation": "six_file_runner_stage_plus_runtime_depot_scratch_18_file_host_environment_and_private_proc_dev_only",
        "host_resource_enforcement": {
            "cgroup_version": 2, "supervisor": "systemd_user_scope",
            "MemoryMax_bytes": fixture["host_supervisor_caps"]["MemoryMax_bytes"],
            "RuntimeMaxSec": fixture["host_supervisor_caps"]["RuntimeMaxSec"],
            "observed_runtime_or_memory_peak_in_canonical_package": False,
        },
        "fresh_process_count": 2, "stdout_byte_identical": True,
        "transcript_sha256_in_order": [transcript, transcript],
        "canonical_witness_sha256": canonical_sha256(witness), "witness": witness,
        "terminal_branch": witness["terminal_branch"], "status": witness["status"],
    }


CERTIFICATE_CLAIMS = (
    "fixed_L8_first_fused_mapped_step_fresh_Float64_threshold_execution",
    "independent_integer_binary64_RNE_replay_of_all_1152_constituents",
    "exact_rational_order7_outward_trigonometric_enclosures",
    "complete_product_merge_and_executed_drop_local_defect_ledger",
    "telescoping_operator_norm_error_bound_without_future_L1_amplification",
    "exact_dyadic_checkerboard_Neel_center_and_declared_expectation_interval",
    "strict_total_tick_comparison_to_the_one_over_400000_prefix_allocation",
    "post_replay_conformance_to_the_certified_P2_execution_digests",
    "two_byte_identical_network_isolated_cgroup_limited_fresh_transcripts",
    "six_file_runner_stage_and_18_file_read_only_host_environment_custody",
)

CERTIFICATE_EXCLUSIONS = (
    "global_coefficientwise_interval_state",
    "equality_of_executed_and_exact_arithmetic_threshold_drop_sets",
    "raw_1280_constituent_threshold_path",
    "double_occupancy",
    "existing_Python_topL1_route_result_equality",
    "remaining_99_mapped_steps_or_full_R100",
    "product_formula_to_exact_Hubbard_error_or_exact_time_evolution",
    "physical_reference_qualification_or_READY",
    "host_runtime_RSS_paths_timestamps_inodes_or_process_identifiers",
)


def _validate_environment_manifest(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(REPLAY_ENVIRONMENT_TARGETS):
        raise SchemaError("P3 replay environment manifest cardinality mismatch")
    observed_targets: list[tuple[str, str]] = []
    previous = ""
    for index, row in enumerate(value):
        require_exact_keys(
            row, ("role", "sandbox_path", "mode", "size_bytes", "sha256"),
            f"P3 replay environment row {index}",
        )
        path = row["sandbox_path"]
        if not isinstance(path, str) or path <= previous:
            raise SchemaError("P3 replay environment paths are not strict ascending")
        previous = path
        if type(row["mode"]) is not int or not 0 <= row["mode"] <= 0o777:
            raise SchemaError("P3 replay environment mode is invalid")
        if type(row["size_bytes"]) is not int or row["size_bytes"] <= 0:
            raise SchemaError("P3 replay environment size is invalid")
        require_sha256(row["sha256"], "P3 replay environment file digest")
        observed_targets.append((row["role"], path))
        if any(key in row for key in ("source_realpath", "mtime", "inode")):
            raise SchemaError("P3 replay environment leaks forbidden host metadata")
    if tuple(observed_targets) != REPLAY_ENVIRONMENT_TARGETS:
        raise VerificationError("P3 recorded replay environment target set mismatch")
    return value


def _committed_replay_evidence(
    commit: str, contract: Mapping[str, Any], base: Path = BASE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    if not isinstance(commit, str) or len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise SchemaError("P3 precommit commit must be a full lowercase Git SHA-1")
    repo, base_relative = P2._repo_and_base_relative(base)
    resolved = P2._run_git(repo, "rev-parse", commit).stdout.decode().strip()
    object_type = P2._run_git(repo, "cat-file", "-t", commit).stdout.decode().strip()
    if resolved != commit or object_type != "commit":
        raise VerificationError("P3 precommit commit does not resolve exactly")
    parent = P2._run_git(repo, "show", "-s", "--format=%P", commit).stdout.decode().strip()
    if parent != REQUIRED_PARENT_COMMIT:
        raise VerificationError("P3 replay commit does not have the frozen direct parent")
    if P2._run_git(repo, "merge-base", "--is-ancestor", commit, "HEAD", check=False).returncode != 0:
        raise VerificationError("P3 replay commit is not an ancestor of current HEAD")
    remote_contains = P2._run_git(repo, "branch", "-r", "--contains", commit).stdout.decode()
    if "origin/" not in remote_contains:
        raise VerificationError("P3 replay commit was not pushed to an origin remote branch")
    outer = _outer_commit_closure(repo, base_relative, commit, contract)
    with tempfile.TemporaryDirectory(prefix="majorana-p3-evidence-") as temporary:
        staging = Path(temporary) / "stage"
        staging.mkdir()
        runner = _stage_runner_tree(repo, base_relative, commit, contract, staging)
        tree_digest = P0._tree_digest(staging)
    return outer, runner, tree_digest


def _validate_replay_package(package: Any, base: Path = BASE) -> Mapping[str, Any]:
    require_exact_keys(
        package,
        (
            "schema_version", "package_type", "precommit_commit_sha",
            "precommit_contract_sha256", "outer_custody_manifest",
            "outer_custody_manifest_sha256", "runner_staging_manifest",
            "runner_staging_manifest_sha256", "runner_staging_tree_sha256",
            "depot_custody", "host_abi_and_locale_custody",
            "host_abi_and_locale_custody_sha256", "network_isolation", "PID_isolation",
            "mount_isolation", "host_resource_enforcement", "fresh_process_count",
            "stdout_byte_identical", "transcript_sha256_in_order",
            "canonical_witness_sha256", "witness", "terminal_branch", "status",
        ),
        "P3 replay package",
    )
    if (
        package["schema_version"] != 1
        or package["package_type"] != "majorana_p3_formal_fresh_replay_package_v1"
    ):
        raise SchemaError("unexpected P3 replay package identity")
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    validate_policy(load_json(base / POLICY_NAME), runtime_lock)
    precommit = validate_precommit_contract(load_json(base / PRECOMMIT_CONTRACT_NAME), base)
    parent_summary = P2.verify_final(base)
    if parent_summary["status"] != PARENT_STATUS:
        raise VerificationError("P3 replay package lacks required certified P2 parent")
    validate_witness(package["witness"], fixture, runtime_lock)
    branch = package["witness"]["terminal_branch"]
    if package["terminal_branch"] != branch or package["status"] != _status_for_terminal_branch(branch):
        raise VerificationError("P3 replay terminal status mismatch")
    if package["fresh_process_count"] != 2 or package["stdout_byte_identical"] is not True:
        raise VerificationError("P3 replay freshness/equality evidence mismatch")
    witness_bytes = canonical_bytes(package["witness"])
    witness_sha = hashlib.sha256(witness_bytes).hexdigest()
    transcript = hashlib.sha256(witness_bytes + b"\n").hexdigest()
    if package["canonical_witness_sha256"] != witness_sha:
        raise VerificationError("P3 replay witness digest mismatch")
    if package["transcript_sha256_in_order"] != [transcript, transcript]:
        raise VerificationError("P3 replay transcript digest mismatch")
    if package["precommit_contract_sha256"] != file_sha256(base / PRECOMMIT_CONTRACT_NAME):
        raise VerificationError("P3 replay precommit contract digest mismatch")
    if package["network_isolation"] != "bubblewrap_unshared_network_namespace" or package[
        "PID_isolation"
    ] != "bubblewrap_unshared_PID_namespace" or package[
        "mount_isolation"
    ] != "six_file_runner_stage_plus_runtime_depot_scratch_18_file_host_environment_and_private_proc_dev_only":
        raise VerificationError("P3 replay isolation declaration mismatch")
    expected_host = {
        "cgroup_version": 2, "supervisor": "systemd_user_scope",
        "MemoryMax_bytes": fixture["host_supervisor_caps"]["MemoryMax_bytes"],
        "RuntimeMaxSec": fixture["host_supervisor_caps"]["RuntimeMaxSec"],
        "observed_runtime_or_memory_peak_in_canonical_package": False,
    }
    if package["host_resource_enforcement"] != expected_host:
        raise VerificationError("P3 replay host resource declaration mismatch")
    environment = _validate_environment_manifest(package["host_abi_and_locale_custody"])
    if package["host_abi_and_locale_custody_sha256"] != canonical_sha256(environment):
        raise VerificationError("P3 replay environment manifest digest mismatch")
    P2._validate_recorded_depot_custody(package["depot_custody"], runtime_lock)
    outer, runner, tree_digest = _committed_replay_evidence(
        package["precommit_commit_sha"], precommit, base,
    )
    if package["outer_custody_manifest"] != outer or package[
        "outer_custody_manifest_sha256"
    ] != canonical_sha256(outer):
        raise VerificationError("P3 outer custody evidence mismatch")
    if package["runner_staging_manifest"] != runner or package[
        "runner_staging_manifest_sha256"
    ] != canonical_sha256(runner):
        raise VerificationError("P3 runner staging evidence mismatch")
    if package["runner_staging_tree_sha256"] != tree_digest:
        raise VerificationError("P3 runner staging tree digest mismatch")
    for field in (
        "precommit_contract_sha256", "outer_custody_manifest_sha256",
        "runner_staging_manifest_sha256", "runner_staging_tree_sha256",
        "host_abi_and_locale_custody_sha256", "canonical_witness_sha256",
    ):
        require_sha256(package[field], f"P3 replay {field}")
    return package


def materialize_result(
    replay_package: Mapping[str, Any], base: Path = BASE,
) -> tuple[dict[str, Any], dict[str, Any]]:
    package = _validate_replay_package(replay_package, base)
    contract = {
        "schema_version": 1,
        "contract_type": "majorana_p3_formal_result_contract_v1",
        "precommit_commit_sha": package["precommit_commit_sha"],
        "precommit_contract_sha256": package["precommit_contract_sha256"],
        "replay_package_sha256": hashlib.sha256(canonical_bytes(package) + b"\n").hexdigest(),
        "outer_custody_manifest_sha256": package["outer_custody_manifest_sha256"],
        "runner_staging_manifest_sha256": package["runner_staging_manifest_sha256"],
        "runner_staging_tree_sha256": package["runner_staging_tree_sha256"],
        "depot_custody": package["depot_custody"],
        "host_abi_and_locale_custody": package["host_abi_and_locale_custody"],
        "host_abi_and_locale_custody_sha256": package["host_abi_and_locale_custody_sha256"],
        "network_isolation": package["network_isolation"],
        "PID_isolation": package["PID_isolation"],
        "mount_isolation": package["mount_isolation"],
        "host_resource_enforcement": package["host_resource_enforcement"],
        "fresh_process_count": package["fresh_process_count"],
        "stdout_byte_identical": package["stdout_byte_identical"],
        "transcript_sha256_in_order": package["transcript_sha256_in_order"],
        "canonical_witness_sha256": package["canonical_witness_sha256"],
        "witness": package["witness"],
        "terminal_branch": package["terminal_branch"],
        "status": package["status"],
        "scope": package["witness"]["scope"],
    }
    certificate = {
        "schema_version": 1,
        "certificate_type": "majorana_p3_local_defect_and_expectation_bound_subcertificate_v1",
        "status": package["status"],
        "terminal_branch": package["terminal_branch"],
        "authority": "fixed_L8_first_fused_mapped_step_exact_prefix_local_defect_operator_and_Neel_expectation_enclosure_only",
        "result_contract_sha256": hashlib.sha256(canonical_bytes(contract) + b"\n").hexdigest(),
        "precommit_commit_sha": package["precommit_commit_sha"],
        "policy_sha256": file_sha256(base / POLICY_NAME),
        "runtime_lock_sha256": file_sha256(base / RUNTIME_LOCK_NAME),
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "runner_sha256": file_sha256(base / RUNNER_RELATIVE_PATH),
        "checker_sha256": file_sha256(base / CHECKER_NAME),
        "parent_P2_result_contract_sha256": file_sha256(base / "majorana_certificate_p2_contract.json"),
        "parent_P2_certificate_sha256": file_sha256(base / "majorana_certificate_p2_certificate.json"),
        "canonical_witness_sha256": package["canonical_witness_sha256"],
        "accuracy_ledger_sha256": canonical_sha256(package["witness"]["accuracy_ledger"]),
        "claims": list(CERTIFICATE_CLAIMS),
        "explicit_exclusions": list(CERTIFICATE_EXCLUSIONS),
        "ready_gate_eligible": False,
    }
    return contract, certificate


def _package_from_result(
    result: Mapping[str, Any], precommit: Mapping[str, Any], base: Path,
) -> dict[str, Any]:
    outer, runner, tree_digest = _committed_replay_evidence(
        result["precommit_commit_sha"], precommit, base,
    )
    if result["outer_custody_manifest_sha256"] != canonical_sha256(outer):
        raise VerificationError("P3 result outer custody digest mismatch")
    if result["runner_staging_manifest_sha256"] != canonical_sha256(runner):
        raise VerificationError("P3 result runner staging manifest digest mismatch")
    if result["runner_staging_tree_sha256"] != tree_digest:
        raise VerificationError("P3 result runner staging tree digest mismatch")
    return {
        "schema_version": 1,
        "package_type": "majorana_p3_formal_fresh_replay_package_v1",
        "precommit_commit_sha": result["precommit_commit_sha"],
        "precommit_contract_sha256": result["precommit_contract_sha256"],
        "outer_custody_manifest": outer,
        "outer_custody_manifest_sha256": result["outer_custody_manifest_sha256"],
        "runner_staging_manifest": runner,
        "runner_staging_manifest_sha256": result["runner_staging_manifest_sha256"],
        "runner_staging_tree_sha256": result["runner_staging_tree_sha256"],
        "depot_custody": result["depot_custody"],
        "host_abi_and_locale_custody": result["host_abi_and_locale_custody"],
        "host_abi_and_locale_custody_sha256": result["host_abi_and_locale_custody_sha256"],
        "network_isolation": result["network_isolation"],
        "PID_isolation": result["PID_isolation"],
        "mount_isolation": result["mount_isolation"],
        "host_resource_enforcement": result["host_resource_enforcement"],
        "fresh_process_count": result["fresh_process_count"],
        "stdout_byte_identical": result["stdout_byte_identical"],
        "transcript_sha256_in_order": result["transcript_sha256_in_order"],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "witness": result["witness"],
        "terminal_branch": result["terminal_branch"],
        "status": result["status"],
    }


def verify_final(base: Path = BASE) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), runtime_lock)
    precommit = validate_precommit_contract(load_json(base / PRECOMMIT_CONTRACT_NAME), base)
    parent = P2.verify_final(base)
    if parent["status"] != PARENT_STATUS:
        raise VerificationError("P3 final verification lost required P2 authority")
    result_path, certificate_path = base / RESULT_CONTRACT_NAME, base / CERTIFICATE_NAME
    result, certificate = load_json(result_path), load_json(certificate_path)
    require_exact_keys(
        result,
        (
            "schema_version", "contract_type", "precommit_commit_sha",
            "precommit_contract_sha256", "replay_package_sha256",
            "outer_custody_manifest_sha256", "runner_staging_manifest_sha256",
            "runner_staging_tree_sha256", "depot_custody",
            "host_abi_and_locale_custody", "host_abi_and_locale_custody_sha256",
            "network_isolation", "PID_isolation", "mount_isolation", "host_resource_enforcement",
            "fresh_process_count", "stdout_byte_identical",
            "transcript_sha256_in_order", "canonical_witness_sha256", "witness",
            "terminal_branch", "status", "scope",
        ),
        "P3 result contract",
    )
    if result["schema_version"] != 1 or result[
        "contract_type"
    ] != "majorana_p3_formal_result_contract_v1":
        raise SchemaError("unexpected P3 result contract identity")
    if result_path.read_bytes() != canonical_bytes(result) + b"\n":
        raise VerificationError("P3 result contract is not canonical JSON plus newline")
    package = _package_from_result(result, precommit, base)
    _validate_replay_package(package, base)
    if result["replay_package_sha256"] != hashlib.sha256(
        canonical_bytes(package) + b"\n"
    ).hexdigest():
        raise VerificationError("P3 replay package digest is not reconstructible")
    if result["scope"] != result["witness"]["scope"]:
        raise VerificationError("P3 result scope mismatch")
    require_exact_keys(
        certificate,
        (
            "schema_version", "certificate_type", "status", "terminal_branch",
            "authority", "result_contract_sha256", "precommit_commit_sha",
            "policy_sha256", "runtime_lock_sha256", "fixture_sha256",
            "runner_sha256", "checker_sha256", "parent_P2_result_contract_sha256",
            "parent_P2_certificate_sha256", "canonical_witness_sha256",
            "accuracy_ledger_sha256", "claims", "explicit_exclusions",
            "ready_gate_eligible",
        ),
        "P3 certificate",
    )
    if certificate_path.read_bytes() != canonical_bytes(certificate) + b"\n":
        raise VerificationError("P3 certificate is not canonical JSON plus newline")
    expected_certificate = {
        "schema_version": 1,
        "certificate_type": "majorana_p3_local_defect_and_expectation_bound_subcertificate_v1",
        "status": result["status"],
        "terminal_branch": result["terminal_branch"],
        "authority": "fixed_L8_first_fused_mapped_step_exact_prefix_local_defect_operator_and_Neel_expectation_enclosure_only",
        "result_contract_sha256": file_sha256(result_path),
        "precommit_commit_sha": result["precommit_commit_sha"],
        "policy_sha256": file_sha256(base / POLICY_NAME),
        "runtime_lock_sha256": file_sha256(base / RUNTIME_LOCK_NAME),
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "runner_sha256": file_sha256(base / RUNNER_RELATIVE_PATH),
        "checker_sha256": file_sha256(base / CHECKER_NAME),
        "parent_P2_result_contract_sha256": fixture["required_parent"]["result_contract_sha256"],
        "parent_P2_certificate_sha256": fixture["required_parent"]["certificate_sha256"],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "accuracy_ledger_sha256": canonical_sha256(result["witness"]["accuracy_ledger"]),
        "claims": list(CERTIFICATE_CLAIMS),
        "explicit_exclusions": list(CERTIFICATE_EXCLUSIONS),
        "ready_gate_eligible": False,
    }
    if certificate != expected_certificate:
        raise VerificationError("P3 certificate content mismatch")
    return {
        "status": result["status"], "terminal_branch": result["terminal_branch"],
        "precommit_commit_sha": result["precommit_commit_sha"],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "result_contract_sha256": file_sha256(result_path),
        "certificate_sha256": file_sha256(certificate_path),
        "policy_id": policy["policy_id"],
    }


def _write_canonical_json(path: Path, value: Any) -> None:
    path = Path(path)
    payload = canonical_bytes(value) + b"\n"
    temporary = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-precommit", action="store_true")
    parser.add_argument("--fresh-replay", action="store_true")
    parser.add_argument("--verify-final", action="store_true")
    parser.add_argument("--materialize-result", action="store_true")
    parser.add_argument("--precommit-commit")
    parser.add_argument("--julia", type=Path)
    parser.add_argument("--depot", type=Path)
    parser.add_argument("--replay-output", type=Path)
    parser.add_argument("--contract-output", type=Path)
    parser.add_argument("--certificate-output", type=Path)
    args = parser.parse_args(argv)
    selected = sum(map(int, (
        args.verify_precommit, args.fresh_replay, args.verify_final,
        args.materialize_result,
    )))
    if selected != 1:
        parser.error("select exactly one operation")
    if args.verify_precommit:
        summary = verify_precommit()
    elif args.fresh_replay:
        if not all((args.precommit_commit, args.julia, args.depot, args.replay_output)):
            parser.error("fresh replay requires commit, Julia, depot, and replay output")
        package = fresh_replay(args.precommit_commit, args.julia, args.depot)
        _write_canonical_json(args.replay_output, package)
        summary = {
            "status": package["status"],
            "terminal_branch": package["terminal_branch"],
            "canonical_witness_sha256": package["canonical_witness_sha256"],
            "transcript_sha256_in_order": package["transcript_sha256_in_order"],
        }
    elif args.materialize_result:
        if not all((args.replay_output, args.contract_output, args.certificate_output)):
            parser.error("materialization requires replay, contract, and certificate paths")
        package = strict_json_loads(
            args.replay_output.read_bytes(), source="P3 replay package",
        )
        contract, certificate = materialize_result(package)
        _write_canonical_json(args.contract_output, contract)
        _write_canonical_json(args.certificate_output, certificate)
        summary = {
            "status": contract["status"],
            "terminal_branch": contract["terminal_branch"],
            "result_contract_sha256": file_sha256(args.contract_output),
            "certificate_sha256": file_sha256(args.certificate_output),
        }
    else:
        summary = verify_final()
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
