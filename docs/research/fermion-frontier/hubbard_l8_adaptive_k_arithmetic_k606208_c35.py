#!/usr/bin/env python3
"""Source-pinned K=606208/C=35 capability wrapper for arithmetic v2.

This module adds no certificate authority and implements no arithmetic of its
own.  A normal import bootstraps a fresh same-byte copy of this wrapper.  That
copy compiles the exact pinned arithmetic-v2 source in an isolated module and
changes only ``RESOURCE_LIMITS["max_retained_K"]`` and
``RESOURCE_LIMITS["max_candidate_count"]``.  Every exported arithmetic class
and function is the object created from those pinned v2 bytes.

The prior K=589824/C=34 capability is pinned only as route-lineage evidence.
It is not read, compiled, imported, or included in the execution source
layers.
"""

from __future__ import annotations

import hashlib
import json
import types
from pathlib import Path
from typing import Any, Dict


SELF_NAME = "hubbard_l8_adaptive_k_arithmetic_k606208_c35.py"
BASE_KERNEL_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
ROUTE_PREDECESSOR_NAME = "hubbard_l8_adaptive_k_arithmetic_k589824_c34.py"
EXPECTED_BASE_KERNEL_SHA256 = (
    "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998"
)
EXPECTED_ROUTE_PREDECESSOR_SHA256 = (
    "7758cc1bf0cd71545a7135c92848059dc69e5d934c79f1d8c60ea61019459254"
)
EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256 = (
    "36694fa3e72ad78fde91826c6a1ae81ae5a7f07e51db2d008769d97eabce5b1a"
)
CAPABILITY_FINGERPRINT = (
    "hubbard_l8_adaptive_k_fixed_tick_arithmetic_v2_"
    "k606208_c35_capability_v1"
)

MAX_SELF_SOURCE_BYTES = 65_536
MAX_BASE_KERNEL_SOURCE_BYTES = 65_536
BASE_PROVIDER_MODULE_NAME = (
    "pinned_hubbard_l8_adaptive_k_arithmetic_v2_for_k606208_c35"
)
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")
_VERIFIED_BASE_KERNEL_SOURCE_BYTES = globals().get(
    "_VERIFIED_BASE_KERNEL_SOURCE_BYTES"
)

EXPECTED_BASE_RESOURCE_LIMITS = {
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
EXPECTED_ROUTE_PREDECESSOR_RESOURCE_LIMITS = {
    **EXPECTED_BASE_RESOURCE_LIMITS,
    "max_retained_K": 589_824,
    "max_candidate_count": 34,
}
EXTENDED_RESOURCE_LIMITS = {
    **EXPECTED_BASE_RESOURCE_LIMITS,
    "max_retained_K": 606_208,
    "max_candidate_count": 35,
}
DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2 = {
    "max_candidate_count": {
        "before": 32,
        "after": 35,
    },
    "max_retained_K": {
        "before": 524_288,
        "after": 606_208,
    },
}
RESOURCE_LIMIT_DELTA = DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2
ROUTE_RESOURCE_LIMIT_DELTA_FROM_K589824_C34 = {
    "max_candidate_count": {
        "before": 34,
        "after": 35,
    },
    "max_retained_K": {
        "before": 589_824,
        "after": 606_208,
    },
}

BASE_API_EXPORTS = (
    "HERE",
    "KERNEL_FINGERPRINT",
    "CERTIFICATE_AUTHORITY",
    "ROOT_SOURCE_PIN",
    "N_QUBITS",
    "TICK_DENOMINATOR",
    "TAYLOR_ORDER",
    "DIGEST_DOMAIN",
    "RESOURCE_LIMITS",
    "PauliKey",
    "TickInterval",
    "TickExpansion",
    "SchemaError",
    "VerificationError",
    "canonical_sha256",
    "read_root_source_bytes",
    "compile_root_oracle",
    "root_global_snapshot",
    "PropagationCounterV2",
    "multiply_ticks",
    "add_tick_term",
    "anticommuting_branch",
    "propagate_gate",
    "propagate_batch",
    "abs_upper",
    "tick_digest",
    "expectation_ticks",
    "rank_with_suffix",
    "validate_candidates",
    "evaluate_candidates",
    "commit_candidate",
    "select_and_truncate",
)
BASE_ARITHMETIC_FUNCTION_EXPORTS = (
    "canonical_sha256",
    "read_root_source_bytes",
    "compile_root_oracle",
    "root_global_snapshot",
    "multiply_ticks",
    "add_tick_term",
    "anticommuting_branch",
    "propagate_gate",
    "propagate_batch",
    "abs_upper",
    "tick_digest",
    "expectation_ticks",
    "rank_with_suffix",
    "validate_candidates",
    "evaluate_candidates",
    "commit_candidate",
    "select_and_truncate",
)


def exact_source_sha256(payload: bytes) -> str:
    """Return the SHA-256 of exact source bytes, rejecting coercions."""

    if type(payload) is not bytes:
        raise TypeError("source payload must be exact bytes")
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("capability manifest is not canonically serializable") from exc


def _read_bounded_source(path: Path, maximum: int) -> bytes:
    with path.open("rb") as handle:
        payload = handle.read(maximum + 1)
    if len(payload) > maximum:
        raise RuntimeError(f"source byte cap exceeded: {path.name}")
    return payload


def _check_base_contract(base: Any) -> None:
    expected_scalars = {
        "KERNEL_FINGERPRINT": "hubbard_l8_adaptive_k_fixed_tick_arithmetic_v2",
        "CERTIFICATE_AUTHORITY": "NONE",
        "N_QUBITS": 128,
        "TICK_DENOMINATOR": 1 << 64,
        "TAYLOR_ORDER": 5,
        "DIGEST_DOMAIN": b"l8_fixed_tick_interval_expansion_v1\n",
    }
    for name, expected in expected_scalars.items():
        if getattr(base, name, None) != expected:
            raise RuntimeError(f"pinned v2 global drift: {name}")
    expected_root_pin = {
        "relative_path": "hubbard_l8_observable_interval_step_checker.py",
        "sha256": (
            "5c151a63cee86d362851629aae743600dd61fcfd534339376a"
            "ca88fe030b1f1a"
        ),
    }
    if base.ROOT_SOURCE_PIN != expected_root_pin:
        raise RuntimeError("pinned v2 root-source contract drift")
    if type(base.RESOURCE_LIMITS) is not dict:
        raise RuntimeError("pinned v2 RESOURCE_LIMITS is not an exact dict")
    if base.RESOURCE_LIMITS != EXPECTED_BASE_RESOURCE_LIMITS:
        raise RuntimeError("pinned v2 resource-limit contract drift")
    missing = [name for name in BASE_API_EXPORTS if not hasattr(base, name)]
    if missing:
        raise RuntimeError(f"pinned v2 public API drift: {missing}")


def _compile_isolated_base(payload: bytes, base_path: Path) -> Any:
    if type(payload) is not bytes:
        raise RuntimeError("verified v2 source must be exact bytes")
    observed = exact_source_sha256(payload)
    if observed != EXPECTED_BASE_KERNEL_SHA256:
        raise RuntimeError(f"arithmetic-v2 source pin drift: {observed}")
    base = types.ModuleType(BASE_PROVIDER_MODULE_NAME)
    base.__file__ = str(base_path)
    base.__package__ = ""
    base.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, base.__file__, "exec"), base.__dict__)
    _check_base_contract(base)
    return base


def _changed_resource_keys(before: Dict[str, int], after: Dict[str, int]) -> set[str]:
    return {
        key
        for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    }


def _install_verified_capability(
    self_payload: bytes,
    base_payload: bytes,
) -> None:
    if type(self_payload) is not bytes:
        raise RuntimeError("verified wrapper source must be exact bytes")
    if type(base_payload) is not bytes:
        raise RuntimeError("verified v2 source must be exact bytes")
    base_path = Path(__file__).resolve().parent / BASE_KERNEL_NAME
    base = _compile_isolated_base(base_payload, base_path)
    before = dict(base.RESOURCE_LIMITS)
    predecessor = dict(EXPECTED_ROUTE_PREDECESSOR_RESOURCE_LIMITS)
    after = dict(EXTENDED_RESOURCE_LIMITS)
    changed = {"max_candidate_count", "max_retained_K"}
    if _changed_resource_keys(before, after) != changed:
        raise RuntimeError("K=606208/C=35 wrapper changed an undeclared capability")
    if _changed_resource_keys(before, predecessor) != changed:
        raise RuntimeError("K=589824/C=34 route predecessor limit reference drift")
    if _changed_resource_keys(predecessor, after) != changed:
        raise RuntimeError("K=606208/C=35 route delta changed an undeclared capability")
    if not (
        before["max_candidate_count"] == 32
        and predecessor["max_candidate_count"] == 34
        and after["max_candidate_count"] == 35
    ):
        raise RuntimeError("K=606208/C=35 candidate-count route drift")
    if DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2 != {
        "max_candidate_count": {
            "before": before["max_candidate_count"],
            "after": after["max_candidate_count"],
        },
        "max_retained_K": {
            "before": before["max_retained_K"],
            "after": after["max_retained_K"],
        },
    }:
        raise RuntimeError("direct v2 resource delta manifest drift")
    if ROUTE_RESOURCE_LIMIT_DELTA_FROM_K589824_C34 != {
        "max_candidate_count": {
            "before": predecessor["max_candidate_count"],
            "after": after["max_candidate_count"],
        },
        "max_retained_K": {
            "before": predecessor["max_retained_K"],
            "after": after["max_retained_K"],
        },
    }:
        raise RuntimeError("K=589824/C=34 route resource delta manifest drift")

    # Arithmetic functions resolve RESOURCE_LIMITS in this isolated v2 module.
    # Point both the provider and this wrapper at the same exact effective dict.
    base.RESOURCE_LIMITS = after
    for name in BASE_API_EXPORTS:
        globals()[name] = getattr(base, name)
    if globals()["RESOURCE_LIMITS"] is not base.RESOURCE_LIMITS:
        raise RuntimeError("wrapper and isolated v2 resource limits are not identical")
    for name in BASE_ARITHMETIC_FUNCTION_EXPORTS:
        function = globals()[name]
        if function is not getattr(base, name):
            raise RuntimeError(f"arithmetic export was replaced: {name}")
        if function.__module__ != BASE_PROVIDER_MODULE_NAME:
            raise RuntimeError(f"arithmetic function provider drift: {name}")
        if Path(function.__code__.co_filename).name != BASE_KERNEL_NAME:
            raise RuntimeError(f"arithmetic function source-path drift: {name}")
        if function.__globals__.get("RESOURCE_LIMITS") is not base.RESOURCE_LIMITS:
            raise RuntimeError(f"arithmetic function capability binding drift: {name}")
    counter_class = globals()["PropagationCounterV2"]
    if counter_class is not base.PropagationCounterV2:
        raise RuntimeError("PropagationCounterV2 was replaced")
    if counter_class.__module__ != BASE_PROVIDER_MODULE_NAME:
        raise RuntimeError("PropagationCounterV2 provider drift")
    for method_name in (
        "__init__",
        "visit",
        "observe_count",
        "observe",
        "begin_window",
        "observe_interval",
        "observe_product_bits",
    ):
        method = getattr(counter_class, method_name)
        if method.__globals__.get("RESOURCE_LIMITS") is not base.RESOURCE_LIMITS:
            raise RuntimeError(
                f"PropagationCounterV2 capability binding drift: {method_name}"
            )

    wrapper_sha = exact_source_sha256(self_payload)
    source_layers = [
        {
            "relative_path": SELF_NAME,
            "role": "k606208_c35_kernel_capability_wrapper",
            "sha256": wrapper_sha,
        },
        {
            "relative_path": BASE_KERNEL_NAME,
            "role": "pinned_arithmetic_v2_implementation",
            "sha256": EXPECTED_BASE_KERNEL_SHA256,
        },
    ]
    route_predecessor_reference = {
        "relative_path": ROUTE_PREDECESSOR_NAME,
        "role": "route_predecessor_capability_reference_only",
        "source_sha256": EXPECTED_ROUTE_PREDECESSOR_SHA256,
        "capability_manifest_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256
        ),
        "effective_resource_limits": predecessor,
        "compiled": False,
        "executed": False,
        "execution_source_layer": False,
    }
    manifest = {
        "schema_version": 1,
        "capability_fingerprint": CAPABILITY_FINGERPRINT,
        "certificate_authority": "NONE",
        "fresh_same_byte_wrapper_execution": True,
        "base_kernel_compiled_from_verified_bytes": True,
        "base_kernel_module_isolated": True,
        "base_kernel_registered_in_sys_modules": False,
        "base_kernel_fingerprint": base.KERNEL_FINGERPRINT,
        "base_kernel_source_sha256": EXPECTED_BASE_KERNEL_SHA256,
        "wrapper_source_sha256": wrapper_sha,
        "source_layers": source_layers,
        "source_layers_sha256": exact_source_sha256(_canonical_bytes(source_layers)),
        "route_predecessor_reference": route_predecessor_reference,
        "route_predecessor_reference_sha256": exact_source_sha256(
            _canonical_bytes(route_predecessor_reference)
        ),
        "resource_limits_before_extension": before,
        "route_predecessor_resource_limits": predecessor,
        "resource_limits_after_extension": after,
        "resource_limit_delta": DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2,
        "direct_resource_limit_delta_from_v2": (
            DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2
        ),
        "route_resource_limit_delta_from_k589824_c34": (
            ROUTE_RESOURCE_LIMIT_DELTA_FROM_K589824_C34
        ),
        "changed_resource_limit_keys": [
            "max_candidate_count",
            "max_retained_K",
        ],
        "arithmetic_provider_module": BASE_PROVIDER_MODULE_NAME,
        "arithmetic_function_exports": list(BASE_ARITHMETIC_FUNCTION_EXPORTS),
    }
    manifest_bytes = _canonical_bytes(manifest)
    globals().update({
        "_BASE_KERNEL_MODULE": base,
        "_CAPABILITY_MANIFEST_BYTES": manifest_bytes,
        "WRAPPER_SOURCE_SHA256": wrapper_sha,
        "RESOURCE_LIMITS_BEFORE_EXTENSION": before,
        "ROUTE_PREDECESSOR_RESOURCE_LIMITS": predecessor,
        "SOURCE_LAYERS": source_layers,
        "SOURCE_LAYERS_SHA256": manifest["source_layers_sha256"],
        "ROUTE_PREDECESSOR_REFERENCE": route_predecessor_reference,
        "ROUTE_PREDECESSOR_REFERENCE_SHA256": manifest[
            "route_predecessor_reference_sha256"
        ],
        "CAPABILITY_MANIFEST": manifest,
        "CAPABILITY_MANIFEST_SHA256": exact_source_sha256(manifest_bytes),
    })


def capability_manifest() -> Dict[str, Any]:
    """Return a detached JSON-exact copy of the active capability manifest."""

    return json.loads(_CAPABILITY_MANIFEST_BYTES.decode("ascii"))


def capability_manifest_sha256() -> str:
    """Return the canonical SHA-256 of :func:`capability_manifest`."""

    return exact_source_sha256(_CAPABILITY_MANIFEST_BYTES)


def _fresh_self_module(expected_self_sha256: str | None) -> Any:
    self_path = Path(__file__).resolve()
    if self_path.name != SELF_NAME:
        raise RuntimeError("K=606208/C=35 wrapper filename drift")
    self_payload = _read_bounded_source(self_path, MAX_SELF_SOURCE_BYTES)
    observed_self = exact_source_sha256(self_payload)
    if expected_self_sha256 is not None:
        if (
            type(expected_self_sha256) is not str
            or len(expected_self_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_self_sha256
            )
        ):
            raise RuntimeError("expected wrapper SHA-256 is not canonical lowercase hex")
        if observed_self != expected_self_sha256:
            raise RuntimeError(
                f"K=606208/C=35 wrapper source pin drift: {observed_self}"
            )
    base_path = self_path.parent / BASE_KERNEL_NAME
    base_payload = _read_bounded_source(base_path, MAX_BASE_KERNEL_SOURCE_BYTES)
    observed = exact_source_sha256(base_payload)
    if observed != EXPECTED_BASE_KERNEL_SHA256:
        raise RuntimeError(f"arithmetic-v2 source pin drift: {observed}")

    module = types.ModuleType(
        "verified_hubbard_l8_adaptive_k_arithmetic_k606208_c35"
    )
    module.__file__ = str(self_path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = self_payload
    module.__dict__["_VERIFIED_BASE_KERNEL_SOURCE_BYTES"] = base_payload
    exec(compile(self_payload, module.__file__, "exec"), module.__dict__)
    return module


def fresh_self_module() -> Any:
    """Compile a fresh wrapper and isolated v2 provider from the same bytes."""

    return _fresh_self_module(None)


def load_pinned_capability(expected_self_sha256: str) -> Any:
    """Load one fresh capability after an exact wrapper-source pin check."""

    if (
        type(expected_self_sha256) is not str
        or len(expected_self_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in expected_self_sha256
        )
    ):
        raise RuntimeError("expected wrapper SHA-256 is not canonical lowercase hex")
    return _fresh_self_module(expected_self_sha256)


def _adopt_fresh_module(module: Any) -> None:
    for name in BASE_API_EXPORTS:
        globals()[name] = getattr(module, name)
    for name in (
        "_BASE_KERNEL_MODULE",
        "_CAPABILITY_MANIFEST_BYTES",
        "WRAPPER_SOURCE_SHA256",
        "RESOURCE_LIMITS_BEFORE_EXTENSION",
        "ROUTE_PREDECESSOR_RESOURCE_LIMITS",
        "SOURCE_LAYERS",
        "SOURCE_LAYERS_SHA256",
        "ROUTE_PREDECESSOR_REFERENCE",
        "ROUTE_PREDECESSOR_REFERENCE_SHA256",
        "CAPABILITY_MANIFEST",
        "CAPABILITY_MANIFEST_SHA256",
    ):
        globals()[name] = getattr(module, name)
    globals()["_VERIFIED_SELF_SOURCE_BYTES"] = module._VERIFIED_SELF_SOURCE_BYTES
    globals()["_VERIFIED_BASE_KERNEL_SOURCE_BYTES"] = (
        module._VERIFIED_BASE_KERNEL_SOURCE_BYTES
    )


if _VERIFIED_SELF_SOURCE_BYTES is None and _VERIFIED_BASE_KERNEL_SOURCE_BYTES is None:
    _adopt_fresh_module(fresh_self_module())
elif (
    type(_VERIFIED_SELF_SOURCE_BYTES) is bytes
    and type(_VERIFIED_BASE_KERNEL_SOURCE_BYTES) is bytes
):
    _install_verified_capability(
        _VERIFIED_SELF_SOURCE_BYTES,
        _VERIFIED_BASE_KERNEL_SOURCE_BYTES,
    )
else:
    raise RuntimeError(
        "K=606208/C=35 wrapper requires exact self and arithmetic-v2 bytes together"
    )


__all__ = tuple(BASE_API_EXPORTS) + (
    "SELF_NAME",
    "BASE_KERNEL_NAME",
    "ROUTE_PREDECESSOR_NAME",
    "EXPECTED_BASE_KERNEL_SHA256",
    "EXPECTED_ROUTE_PREDECESSOR_SHA256",
    "EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256",
    "CAPABILITY_FINGERPRINT",
    "EXPECTED_BASE_RESOURCE_LIMITS",
    "EXPECTED_ROUTE_PREDECESSOR_RESOURCE_LIMITS",
    "EXTENDED_RESOURCE_LIMITS",
    "DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2",
    "RESOURCE_LIMIT_DELTA",
    "ROUTE_RESOURCE_LIMIT_DELTA_FROM_K589824_C34",
    "BASE_API_EXPORTS",
    "BASE_ARITHMETIC_FUNCTION_EXPORTS",
    "WRAPPER_SOURCE_SHA256",
    "RESOURCE_LIMITS_BEFORE_EXTENSION",
    "ROUTE_PREDECESSOR_RESOURCE_LIMITS",
    "SOURCE_LAYERS",
    "SOURCE_LAYERS_SHA256",
    "ROUTE_PREDECESSOR_REFERENCE",
    "ROUTE_PREDECESSOR_REFERENCE_SHA256",
    "CAPABILITY_MANIFEST",
    "CAPABILITY_MANIFEST_SHA256",
    "exact_source_sha256",
    "capability_manifest",
    "capability_manifest_sha256",
    "fresh_self_module",
    "load_pinned_capability",
)

