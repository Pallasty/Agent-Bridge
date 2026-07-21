#!/usr/bin/env python3
"""Source-pinned, diagnostic-only four-gate K=540672 screen wrapper."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
import types
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple


SELF_NAME = "hubbard_l8_adaptive_k_four_gate_k540672_screen.py"
CONTROL_FLOW_PARENT_NAME = (
    "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
)
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k540672.py"

EXPECTED_CONTROL_FLOW_PARENT_SHA256 = (
    "b483d9555a24dd07ea96292ed0a7ed51587259a79a2c5d69e3a8bf1408b4a614"
)
EXPECTED_V6_BASELINE_CONFIGURATION_SHA256 = (
    "3e7f9ff0546addfaa23f351f3569b102d0c3ebb578dbc4873b042bac21070af2"
)
EXPECTED_V2_ARITHMETIC_SHA256 = (
    "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998"
)
EXPECTED_KERNEL_WRAPPER_SHA256 = (
    "327837e4646cb79cb237611ab49e645b51a47a36a97006e94838d1f5fa05af60"
)
EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256 = (
    "d51151fc1d6c73c33f1b50da0a09de4d3346212599716feaba578839dde37526"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

K540672 = 540_672
KERNEL_MAX_CANDIDATE_COUNT = 32

M_CANDIDATES = (
    65_536, 81_920, 98_304, 114_688, 131_072, 147_456, 163_840,
    180_224, 196_608, 212_992, 229_376, 245_760, 262_144, 278_528,
    294_912, 311_296, 327_680, 344_064, 360_448, 376_832, 393_216,
    409_600, 425_984, 442_368, 458_752, 475_136, 491_520, 507_904,
    524_288, 540_672,
)
D_CANDIDATES = (
    73_728, 81_920, 90_112, 98_304, 106_496, 114_688, 122_880,
    131_072, 147_456, 163_840, 180_224, 196_608, 212_992, 229_376,
    245_760, 262_144, 278_528, 294_912, 311_296, 327_680, 344_064,
    360_448, 376_832, 393_216, 409_600, 425_984, 442_368, 458_752,
    475_136, 507_904, 524_288, 540_672,
)

EXPECTED_CANDIDATE_SHA256 = {
    "magnetization": (
        "9baadb7bea90ac503ec3f68cd05fa01d967376fedff59aaedcbf2d009c46fb95"
    ),
    "double_occupancy": (
        "071999328539f944d72affe0dc14999ef6c1d728bef8a4f94266b1b9950e1133"
    ),
}
EXPECTED_V6_BASELINE_CANDIDATE_SHA256 = {
    "magnetization": (
        "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
    ),
    "double_occupancy": (
        "df55613f1fbd691f42319976d4722e614b25a8c985cdae5df9797f2e49660160"
    ),
}
BASE_FOUR_GATE_CANONICAL_ANCHORS = {
    "magnetization": {
        "transcript_file_sha256": (
            "18629c9a0841e1e3308eda0bc7f3cbc568c8ed2925a6b95d1c3e7b7665b142a0"
        ),
        "records_sha256": (
            "2c96c89edd65e47e9fc6ba60d70b52d11d3a0f24b110e32a25ae60a2f2fe5c94"
        ),
        "selected_K_history_sha256": (
            "5812a3b5d996102c3e2393fea0e514466afd01026467b702407c634229f34171"
        ),
        "attempted_checkpoint_count": 78,
        "completed_checkpoint_count": 77,
    },
    "double_occupancy": {
        "transcript_file_sha256": (
            "2b83f7f349cb0b7fedab4ad8b8058606c239b01d45579722afc490c35f684060"
        ),
        "records_sha256": (
            "b1f27ae52362150f5522cccf7aa2056c3197c6048855654836a57c40a0c30bec"
        ),
        "selected_K_history_sha256": (
            "ecb91ccb56d8138d2acb61f20a44b3fe52ed9cdfcbc615f418595be4e6b7ce24"
        ),
        "attempted_checkpoint_count": 65,
        "completed_checkpoint_count": 64,
    },
}

EXPECTED_V6_POLICY_CAPS = {
    "max_candidate_K": 524_288,
    "max_output_terms_if_successful": 524_288,
    "max_single_expansion_terms": 786_432,
    "max_digest_terms": 786_432,
    "max_term_gate_visits": 536_870_912,
    "max_expansion_coefficient_tick_bits": 192,
    "max_trigonometric_tick_bits": 66,
    "max_product_bits": 384,
    "max_suffix_accumulator_bits": 224,
}
EXPECTED_V6_POLICY_CAPS_SHA256 = (
    "32a0619246b07e67e6d4f237f808fc5c5163c1149c50230bf962ab1851a6f25a"
)
POLICY_CAPS_BASE = {
    **EXPECTED_V6_POLICY_CAPS,
    "max_candidate_K": K540672,
    "max_output_terms_if_successful": K540672,
}

EXPECTED_V2_KERNEL_CAPABILITY_LIMITS = {
    "max_candidate_count": 32,
    "max_digest_terms": 1_048_576,
    "max_expansion_coefficient_tick_bits": 192,
    "max_product_bits": 384,
    "max_retained_K": 524_288,
    "max_single_expansion_terms": 1_048_576,
    "max_source_bytes": 196_608,
    "max_suffix_accumulator_bits": 224,
    "max_term_gate_visits": 1_000_000_000,
    "max_trigonometric_tick_bits": 66,
}
EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS = {
    **EXPECTED_V2_KERNEL_CAPABILITY_LIMITS,
    "max_retained_K": K540672,
}
KERNEL_CAPABILITY_CHANGE = {
    "max_retained_K": {"before": 524_288, "after": K540672},
}

MODE_CONFIG = {
    "magnetization": {
        "candidates": M_CANDIDATES,
        "candidate_ladder_added": (K540672,),
        "candidate_ladder_removed": (),
        "horizon_checkpoint_count": 80,
        "output_name": (
            "hubbard_l8_magnetization_adaptive_k_"
            "four_gate_k540672_transcript.json"
        ),
    },
    "double_occupancy": {
        "candidates": D_CANDIDATES,
        "candidate_ladder_added": (K540672,),
        "candidate_ladder_removed": (65_536,),
        "horizon_checkpoint_count": 66,
        "output_name": (
            "hubbard_l8_double_occupancy_adaptive_k_"
            "four_gate_k540672_transcript.json"
        ),
    },
}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def bounded_source_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as handle:
        payload = handle.read(maximum + 1)
    if len(payload) > maximum:
        raise RuntimeError(f"source byte cap exceeded: {path.name}")
    return payload


def checked_repo_file(repo: Path, relative_path: str) -> Path:
    if type(relative_path) is not str or not relative_path:
        raise RuntimeError("source relative path is not a nonempty string")
    repo = repo.resolve()
    path = (repo / relative_path).resolve()
    try:
        path.relative_to(repo)
    except ValueError as exc:
        raise RuntimeError("source path escapes the repository") from exc
    return path


def compile_isolated(name: str, path: Path, payload: bytes) -> Any:
    if type(payload) is not bytes:
        raise RuntimeError("isolated module payload must be exact bytes")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def load_pinned_module(
    repo: Path,
    relative_path: str,
    expected_sha: str,
    module_name: str,
) -> Tuple[Any, bytes]:
    path = checked_repo_file(repo, relative_path)
    payload = bounded_source_bytes(path, MAX_PINNED_SOURCE_BYTES)
    observed = sha256(payload)
    if observed != expected_sha:
        raise RuntimeError(f"source pin drift for {relative_path}: {observed}")
    return compile_isolated(module_name, path, payload), payload


def validate_local_configuration() -> None:
    expected_counts = {"magnetization": 30, "double_occupancy": 32}
    for mode, config in MODE_CONFIG.items():
        candidates = config["candidates"]
        if type(candidates) is not tuple or not candidates:
            raise RuntimeError(f"candidate ladder type drift: {mode}")
        if len(candidates) != expected_counts[mode]:
            raise RuntimeError(f"candidate ladder count drift: {mode}")
        if len(candidates) > KERNEL_MAX_CANDIDATE_COUNT:
            raise RuntimeError(f"candidate count capability exceeded: {mode}")
        if any(type(value) is not int or value <= 0 for value in candidates):
            raise RuntimeError(f"candidate ladder value drift: {mode}")
        if any(left >= right for left, right in zip(candidates, candidates[1:])):
            raise RuntimeError(f"candidate ladder order drift: {mode}")
        if candidates[-1] != K540672:
            raise RuntimeError(f"candidate ladder maximum drift: {mode}")
        if sha256(canonical_bytes(list(candidates))) != (
            EXPECTED_CANDIDATE_SHA256[mode]
        ):
            raise RuntimeError(f"candidate ladder digest drift: {mode}")
        if config["horizon_checkpoint_count"] != {
            "magnetization": 80,
            "double_occupancy": 66,
        }[mode]:
            raise RuntimeError(f"screen horizon drift: {mode}")
    if 65_536 not in M_CANDIDATES:
        raise RuntimeError("magnetization append-only baseline drift")
    if 65_536 in D_CANDIDATES or 491_520 in D_CANDIDATES:
        raise RuntimeError("double-occupancy replacement rule drift")
    changed_policy_fields = {
        key for key in POLICY_CAPS_BASE
        if POLICY_CAPS_BASE[key] != EXPECTED_V6_POLICY_CAPS[key]
    }
    if changed_policy_fields != {
        "max_candidate_K",
        "max_output_terms_if_successful",
    }:
        raise RuntimeError("policy override is not the exact two-field K change")


def load_control_flow_parent(repo: Path) -> Any:
    parent, _payload = load_pinned_module(
        repo,
        CONTROL_FLOW_PARENT_NAME,
        EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "pinned_four_gate_control_flow_parent_for_k540672",
    )
    if parent.KERNEL_NAME != V2_ARITHMETIC_NAME:
        raise RuntimeError("control-flow parent v2 kernel path drift")
    if parent.EXPECTED_KERNEL_SHA256 != EXPECTED_V2_ARITHMETIC_SHA256:
        raise RuntimeError("control-flow parent v2 kernel pin drift")
    if parent.V6_CONFIGURATION_NAME != V6_BASELINE_CONFIGURATION_NAME:
        raise RuntimeError("control-flow parent v6 configuration path drift")
    if parent.EXPECTED_V6_CONFIGURATION_SHA256 != (
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
    ):
        raise RuntimeError("control-flow parent v6 configuration pin drift")
    for mode, config in MODE_CONFIG.items():
        if parent.MODE_CONFIG[mode]["horizon_checkpoint_count"] != (
            config["horizon_checkpoint_count"]
        ):
            raise RuntimeError(f"control-flow parent horizon drift: {mode}")
    return parent


def load_configured_v6_baseline(repo: Path, mode: str) -> Any:
    if mode not in MODE_CONFIG:
        raise RuntimeError(f"unknown mode: {mode}")
    configuration, _payload = load_pinned_module(
        repo,
        V6_BASELINE_CONFIGURATION_NAME,
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "pinned_v6_baseline_configuration_for_k540672",
    )
    if configuration.POLICY_CAPS_BASE != EXPECTED_V6_POLICY_CAPS:
        raise RuntimeError("v6 baseline policy caps drift")
    if sha256(canonical_bytes(configuration.POLICY_CAPS_BASE)) != (
        EXPECTED_V6_POLICY_CAPS_SHA256
    ):
        raise RuntimeError("v6 baseline policy digest drift")
    for configured_mode in MODE_CONFIG:
        baseline = configuration.MODE_CONFIG[configured_mode]["candidates"]
        if type(baseline) is not tuple:
            raise RuntimeError(
                f"v6 baseline candidate type drift: {configured_mode}"
            )
        if sha256(canonical_bytes(list(baseline))) != (
            EXPECTED_V6_BASELINE_CANDIDATE_SHA256[configured_mode]
        ):
            raise RuntimeError(
                f"v6 baseline candidate digest drift: {configured_mode}"
            )
    baseline_m = tuple(configuration.MODE_CONFIG["magnetization"]["candidates"])
    baseline_d = tuple(configuration.MODE_CONFIG["double_occupancy"]["candidates"])
    if M_CANDIDATES != baseline_m + (K540672,):
        raise RuntimeError("magnetization append-only construction drift")
    if baseline_d[0] != 65_536 or baseline_d.count(65_536) != 1:
        raise RuntimeError("double-occupancy removable slot drift")
    if D_CANDIDATES != baseline_d[1:] + (K540672,):
        raise RuntimeError("double-occupancy replacement construction drift")

    runtime_config = copy.deepcopy(configuration.MODE_CONFIG)
    runtime_config[mode]["candidates"] = tuple(MODE_CONFIG[mode]["candidates"])
    configuration.MODE_CONFIG = runtime_config
    configuration.POLICY_CAPS_BASE = dict(POLICY_CAPS_BASE)
    return configuration


def load_kernel_wrapper(repo: Path) -> Tuple[Any, str, Dict[str, Any]]:
    wrapper_path = checked_repo_file(repo, KERNEL_WRAPPER_NAME)
    wrapper_payload = bounded_source_bytes(wrapper_path, MAX_PINNED_SOURCE_BYTES)
    wrapper_sha = sha256(wrapper_payload)
    if wrapper_sha != EXPECTED_KERNEL_WRAPPER_SHA256:
        raise RuntimeError(f"source pin drift for {KERNEL_WRAPPER_NAME}: {wrapper_sha}")
    v2_path = checked_repo_file(repo, V2_ARITHMETIC_NAME)
    v2_payload = bounded_source_bytes(v2_path, MAX_PINNED_SOURCE_BYTES)
    v2_sha = sha256(v2_payload)
    if v2_sha != EXPECTED_V2_ARITHMETIC_SHA256:
        raise RuntimeError(f"source pin drift for {V2_ARITHMETIC_NAME}: {v2_sha}")

    wrapper = types.ModuleType("pinned_k540672_arithmetic_capability_wrapper")
    wrapper.__file__ = str(wrapper_path)
    wrapper.__package__ = ""
    wrapper.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = wrapper_payload
    wrapper.__dict__["_VERIFIED_BASE_KERNEL_SOURCE_BYTES"] = v2_payload
    exec(compile(wrapper_payload, wrapper.__file__, "exec"), wrapper.__dict__)
    if wrapper.BASE_KERNEL_NAME != V2_ARITHMETIC_NAME:
        raise RuntimeError("kernel wrapper base path drift")
    if wrapper.EXPECTED_BASE_KERNEL_SHA256 != EXPECTED_V2_ARITHMETIC_SHA256:
        raise RuntimeError("kernel wrapper base digest drift")
    if wrapper.RESOURCE_LIMIT_DELTA != KERNEL_CAPABILITY_CHANGE:
        raise RuntimeError("kernel wrapper capability declaration drift")
    if wrapper.EXPECTED_BASE_RESOURCE_LIMITS != (
        EXPECTED_V2_KERNEL_CAPABILITY_LIMITS
    ):
        raise RuntimeError("kernel wrapper base resource manifest drift")
    if wrapper.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS:
        raise RuntimeError("kernel wrapper effective resource limits drift")
    if not callable(wrapper.capability_manifest):
        raise RuntimeError("kernel wrapper manifest entrypoint drift")
    if not callable(wrapper.capability_manifest_sha256):
        raise RuntimeError("kernel wrapper manifest-digest entrypoint drift")
    manifest = wrapper.capability_manifest()
    if type(manifest) is not dict:
        raise RuntimeError("kernel capability manifest is not an exact dict")
    manifest_sha = sha256(canonical_bytes(manifest))
    if wrapper.capability_manifest_sha256() != manifest_sha:
        raise RuntimeError("kernel capability manifest digest drift")
    if manifest_sha != EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256:
        raise RuntimeError("kernel capability manifest pin drift")
    expected_manifest_fields = {
        "schema_version": 1,
        "certificate_authority": "NONE",
        "fresh_same_byte_wrapper_execution": True,
        "base_kernel_compiled_from_verified_bytes": True,
        "base_kernel_module_isolated": True,
        "base_kernel_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "wrapper_source_sha256": wrapper_sha,
        "resource_limits_before_extension": (
            EXPECTED_V2_KERNEL_CAPABILITY_LIMITS
        ),
        "resource_limits_after_extension": (
            EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        ),
        "resource_limit_delta": KERNEL_CAPABILITY_CHANGE,
        "changed_resource_limit_keys": ["max_retained_K"],
    }
    for key, expected in expected_manifest_fields.items():
        if manifest.get(key) != expected:
            raise RuntimeError(f"kernel capability manifest drift: {key}")
    return wrapper, wrapper_sha, manifest


def configure_parent_execution(
    repo: Path,
    parent: Any,
    configuration: Any,
    kernel_wrapper: Any,
) -> None:
    """Inject configuration and a separately sourced kernel capability provider."""

    original_load_execution_sources = parent.load_execution_sources
    parent.load_v6_configuration = lambda _repo: configuration

    def load_wrapped_execution_sources(
        source_repo: Path,
        helper: Any,
        mode: str,
    ) -> Tuple[Any, Any, Dict[str, Any], Dict[str, str]]:
        base_kernel, root, modules, custody = original_load_execution_sources(
            source_repo,
            helper,
            mode,
        )
        if base_kernel.RESOURCE_LIMITS != EXPECTED_V2_KERNEL_CAPABILITY_LIMITS:
            raise RuntimeError("v2 arithmetic capability limits drift")
        if kernel_wrapper.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS:
            raise RuntimeError("wrapped kernel capability limits drift")
        if base_kernel.RESOURCE_LIMITS != EXPECTED_V2_KERNEL_CAPABILITY_LIMITS:
            raise RuntimeError("kernel wrapper mutated the v2 arithmetic module")
        return kernel_wrapper, root, modules, custody

    parent.load_execution_sources = load_wrapped_execution_sources


def baseline_configuration_reference(mode: str) -> Dict[str, Any]:
    return {
        "relative_path": V6_BASELINE_CONFIGURATION_NAME,
        "source_sha256": EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "role": "v6_baseline_candidates_and_caps_before_declared_override",
        "baseline_candidate_K_values_sha256": (
            EXPECTED_V6_BASELINE_CANDIDATE_SHA256[mode]
        ),
        "baseline_policy_caps_sha256": EXPECTED_V6_POLICY_CAPS_SHA256,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }


def configuration_override(mode: str) -> Dict[str, Any]:
    config = MODE_CONFIG[mode]
    override = {
        "override_id": "four_gate_k540672_configuration_override_v1",
        "diagnostic_ladder_precommitted_before_replay": True,
        "base_four_gate_canonical_anchor": dict(
            BASE_FOUR_GATE_CANONICAL_ANCHORS[mode]
        ),
        "baseline_candidate_K_values_sha256": (
            EXPECTED_V6_BASELINE_CANDIDATE_SHA256[mode]
        ),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256[mode],
        "candidate_count_after": len(config["candidates"]),
        "candidate_ladder_added": list(config["candidate_ladder_added"]),
        "candidate_ladder_removed": list(config["candidate_ladder_removed"]),
        "policy_cap_changes": {
            "max_candidate_K": {"before": 524_288, "after": K540672},
            "max_output_terms_if_successful": {
                "before": 524_288,
                "after": K540672,
            },
        },
        "unchanged_policy_caps": {
            key: value for key, value in EXPECTED_V6_POLICY_CAPS.items()
            if key not in {"max_candidate_K", "max_output_terms_if_successful"}
        },
        "overridden_fields": [
            f"MODE_CONFIG.{mode}.candidates",
            "POLICY_CAPS_BASE.max_candidate_K",
            "POLICY_CAPS_BASE.max_output_terms_if_successful",
        ],
    }
    if mode == "double_occupancy":
        override["removed_candidate_precommit_basis"] = {
            "configured_K": 65_536,
            "canonical_checkpoint_number_range_audited": [1, 65],
            "canonical_candidate_row_feasible_checkpoint_numbers": [],
            "canonical_selected_checkpoint_numbers": [],
            "smallest_baseline_candidate": True,
            "claim_scope": (
                "all_65_candidate_rows_in_the_pinned_base_four_gate_transcript"
            ),
        }
    else:
        override["removed_candidate_precommit_basis"] = None
    return override


def kernel_capability_override(
    wrapper_sha: str,
    manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "relative_path": KERNEL_WRAPPER_NAME,
        "source_sha256": wrapper_sha,
        "role": "separate_k540672_capability_override_provider",
        "base_arithmetic_relative_path": V2_ARITHMETIC_NAME,
        "base_arithmetic_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "module_itself_is_extended_kernel": True,
        "verified_compilation_inputs": [
            "_VERIFIED_SELF_SOURCE_BYTES",
            "_VERIFIED_BASE_KERNEL_SOURCE_BYTES",
        ],
        "capability_manifest": dict(manifest),
        "capability_manifest_sha256": sha256(canonical_bytes(manifest)),
        "capability_changes": KERNEL_CAPABILITY_CHANGE,
        "v2_arithmetic_module_mutated_by_screen": False,
    }


def execution_components(
    parent_components: Any,
    self_sha: str,
    kernel_wrapper_sha: str,
) -> list[Dict[str, Any]]:
    if type(parent_components) is not list:
        raise RuntimeError("control-flow parent execution components are not a list")
    components = [{
        "relative_path": SELF_NAME,
        "role": "k540672_fresh_same_byte_screen_wrapper",
        "sha256": self_sha,
    }]
    saw_parent = False
    saw_v6 = False
    saw_v2_kernel = False
    for original in parent_components:
        if type(original) is not dict:
            raise RuntimeError("control-flow parent component is not a dict")
        item = dict(original)
        relative_path = item.get("relative_path")
        if relative_path == CONTROL_FLOW_PARENT_NAME:
            if item.get("sha256") != EXPECTED_CONTROL_FLOW_PARENT_SHA256:
                raise RuntimeError("control-flow parent component digest drift")
            item["role"] = "four_gate_control_flow_parent_private_entrypoint"
            saw_parent = True
        elif relative_path == V6_BASELINE_CONFIGURATION_NAME:
            if item.get("sha256") != EXPECTED_V6_BASELINE_CONFIGURATION_SHA256:
                raise RuntimeError("v6 baseline component digest drift")
            item["role"] = "v6_baseline_configuration_before_declared_override"
            saw_v6 = True
        elif relative_path == V2_ARITHMETIC_NAME:
            if item.get("sha256") != EXPECTED_V2_ARITHMETIC_SHA256:
                raise RuntimeError("v2 arithmetic component digest drift")
            item["role"] = "v2_arithmetic_bytes_beneath_capability_wrapper"
            saw_v2_kernel = True
        components.append(item)
        if relative_path == V2_ARITHMETIC_NAME:
            components.append({
                "relative_path": KERNEL_WRAPPER_NAME,
                "role": "k540672_capability_override_provider",
                "sha256": kernel_wrapper_sha,
            })
    if not (saw_parent and saw_v6 and saw_v2_kernel):
        raise RuntimeError("control-flow parent component set is incomplete")
    return components


def validate_and_relabel(
    result: Dict[str, Any],
    mode: str,
    kernel_wrapper_sha: str,
    kernel_manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("K=540672 relabel requires fresh same-byte self execution")
    if type(result) is not dict:
        raise RuntimeError("control-flow parent result is not an exact dict")
    validate_local_configuration()

    expected_parent_fields = {
        "schema_version": 1,
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "same_byte_self_execution": True,
        "v2_run_entrypoint_called": False,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
        "control_flow_owned_by_screen": True,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, expected in expected_parent_fields.items():
        if result.get(key) != expected:
            raise RuntimeError(f"control-flow parent result drift: {key}")

    candidates = list(MODE_CONFIG[mode]["candidates"])
    candidate_sha = EXPECTED_CANDIDATE_SHA256[mode]
    if result.get("candidate_K_values") != candidates:
        raise RuntimeError("configured candidate ladder was not used")
    if result.get("candidate_K_values_sha256") != candidate_sha:
        raise RuntimeError("configured candidate ladder digest drift")
    expected_caps = {
        **POLICY_CAPS_BASE,
        "max_candidate_count": len(candidates),
    }
    if result.get("proposed_policy_caps") != expected_caps:
        raise RuntimeError("configured policy caps were not used")
    if result.get("kernel_capability_limits") != (
        EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
    ):
        raise RuntimeError("wrapped kernel limits were not recorded")
    if result.get("screen_horizon_checkpoint_count") != (
        MODE_CONFIG[mode]["horizon_checkpoint_count"]
    ):
        raise RuntimeError("configured horizon was not used")

    custody = result.get("source_custody")
    if type(custody) is not dict:
        raise RuntimeError("control-flow parent source custody is not a dict")
    for relative_path, expected in {
        V6_BASELINE_CONFIGURATION_NAME: EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        V2_ARITHMETIC_NAME: EXPECTED_V2_ARITHMETIC_SHA256,
    }.items():
        if custody.get(relative_path) != expected:
            raise RuntimeError(f"control-flow parent custody drift: {relative_path}")

    old_components = result.get("screen_execution_components")
    old_components_sha = result.get("screen_execution_components_sha256")
    if type(old_components) is not list:
        raise RuntimeError("control-flow parent component list drift")
    if old_components_sha != sha256(canonical_bytes(old_components)):
        raise RuntimeError("control-flow parent component digest drift")
    old_configuration = result.get("configuration_reference")
    old_configuration_sha = result.get("configuration_reference_sha256")
    if type(old_configuration) is not dict:
        raise RuntimeError("control-flow parent configuration reference drift")
    if old_configuration_sha != sha256(canonical_bytes(old_configuration)):
        raise RuntimeError("control-flow parent configuration digest drift")
    if old_configuration.get("source_sha256") != (
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
    ):
        raise RuntimeError("control-flow parent v6 reference drift")
    old_transform = result.get("checkpoint_transform")
    old_transform_sha = result.get("checkpoint_transform_sha256")
    if type(old_transform) is not dict:
        raise RuntimeError("control-flow parent checkpoint transform drift")
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("control-flow parent transform digest drift")

    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = execution_components(old_components, self_sha, kernel_wrapper_sha)
    baseline_reference = baseline_configuration_reference(mode)
    override = configuration_override(mode)
    capability = kernel_capability_override(kernel_wrapper_sha, kernel_manifest)
    transform = {
        "transform_id": "l8_adaptive_k_four_gate_k540672_screen_v1",
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": (
            old_transform_sha
        ),
        "configuration_and_capability_override_outside_parent_transform": True,
        "overridden_semantics": [
            "candidate_K_values",
            "policy_max_candidate_K",
            "policy_max_output_terms_if_successful",
            "kernel_max_retained_K",
        ],
    }

    new_custody = dict(custody)
    for relative_path in (SELF_NAME, CONTROL_FLOW_PARENT_NAME, KERNEL_WRAPPER_NAME):
        if relative_path in new_custody:
            raise RuntimeError(f"unexpected preexisting custody entry: {relative_path}")
    new_custody[SELF_NAME] = self_sha
    new_custody[CONTROL_FLOW_PARENT_NAME] = EXPECTED_CONTROL_FLOW_PARENT_SHA256
    new_custody[KERNEL_WRAPPER_NAME] = kernel_wrapper_sha

    result.update({
        "schema_version": 1,
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_k540672_screen_v1"
        ),
        "screen_source_sha256": self_sha,
        "same_byte_self_execution": True,
        "control_flow_owned_by_screen": False,
        "control_flow_owned_by_verified_parent": True,
        "control_flow_parent_relative_path": CONTROL_FLOW_PARENT_NAME,
        "control_flow_parent_source_sha256": (
            EXPECTED_CONTROL_FLOW_PARENT_SHA256
        ),
        "control_flow_parent_compiled_from_verified_bytes": True,
        "control_flow_parent_module_isolated": True,
        "control_flow_parent_same_byte_execution": True,
        "control_flow_parent_private_entrypoint_called": True,
        "control_flow_parent_original_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
        ),
        "control_flow_parent_effective_execution_components_sha256_before_relabel": (
            old_components_sha
        ),
        "control_flow_parent_effective_configuration_reference_sha256_before_relabel": (
            old_configuration_sha
        ),
        "v6_configuration_source_used_as_baseline_only": True,
        "v6_runtime_configuration_override_applied": True,
        "v2_arithmetic_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "v2_arithmetic_compiled_from_verified_bytes": True,
        "arithmetic_kernel_commit_role": (
            "base_v2_arithmetic_implementation_commit_before_capability_override"
        ),
        "kernel_capability_wrapper_relative_path": KERNEL_WRAPPER_NAME,
        "kernel_capability_wrapper_source_sha256": kernel_wrapper_sha,
        "kernel_capability_wrapper_compiled_from_verified_bytes": True,
        "kernel_capability_wrapper_module_isolated": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(canonical_bytes(components)),
        "configuration_reference": baseline_reference,
        "configuration_reference_sha256": sha256(
            canonical_bytes(baseline_reference)
        ),
        "configuration_override": override,
        "configuration_override_sha256": sha256(canonical_bytes(override)),
        "kernel_capability_override": capability,
        "kernel_capability_override_sha256": sha256(canonical_bytes(capability)),
        "checkpoint_transform": transform,
        "checkpoint_transform_sha256": sha256(canonical_bytes(transform)),
        "source_custody": new_custody,
        "diagnostic_candidate_ladder_precommitted_before_replay": True,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    })
    return result


def _run_verified(repo: Path, mode: str) -> Dict[str, Any]:
    """Run the exact parent private path with declared configuration providers."""

    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("K=540672 screen requires fresh same-byte self execution")
    if mode not in MODE_CONFIG:
        raise RuntimeError(f"unknown mode: {mode}")
    validate_local_configuration()
    repo = repo.resolve()
    parent = load_control_flow_parent(repo)
    configuration = load_configured_v6_baseline(repo, mode)
    kernel_wrapper, kernel_wrapper_sha, kernel_manifest = load_kernel_wrapper(repo)
    configure_parent_execution(repo, parent, configuration, kernel_wrapper)
    result = parent._run_verified(repo, mode)
    return validate_and_relabel(
        result,
        mode,
        kernel_wrapper_sha,
        kernel_manifest,
    )


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_source_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_four_gate_k540672_screen_wrapper")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path, mode: str) -> Dict[str, Any]:
    """Public fresh-self entry point for one diagnostic K=540672 screen."""

    return fresh_self_module()._run_verified(repo, mode)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("K=540672 screen transcript exceeds output byte cap")
    output = output.resolve()
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output.parent,
            prefix=output.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=tuple(MODE_CONFIG))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp"))
    args = parser.parse_args()
    result = run(args.repo, args.mode)
    raw = canonical_bytes(result)
    output = args.output_dir / MODE_CONFIG[args.mode]["output_name"]
    write_atomic_bounded(output, raw)
    final_record = result["records"][-1] if result["records"] else None
    print(json.dumps({
        "output": output.name,
        "semantic_and_file_sha256": sha256(raw),
        "records_sha256": result["records_sha256"],
        "screen_terminal_condition": result["screen_terminal_condition"],
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "attempted_checkpoint_count": result["attempted_checkpoint_count"],
        "final_status": final_record["status"] if final_record else None,
        "final_checkpoint": (
            final_record.get("checkpoint_number_one_based") if final_record else None
        ),
        "last_committed_cumulative_drop_ticks": (
            result["last_committed_cumulative_drop_ticks"]
        ),
        "peak": result["observed_peak_single_expansion_terms"],
        "visits": result["observed_term_gate_visits_including_terminal_attempt"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
