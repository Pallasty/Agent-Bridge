#!/usr/bin/env python3
"""Source-pinned, diagnostic-only D K=573440/C=33 q68 screen."""

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


SELF_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k573440_c33_q68_screen.py"
)
CONTROL_FLOW_PARENT_NAME = (
    "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
)
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k573440_c33.py"
ROUTE_PREDECESSOR_SCREEN_NAME = (
    "hubbard_l8_adaptive_k_four_gate_k540672_screen.py"
)
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_"
    "four_gate_k540672_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k573440_c33_q68_transcript.json"
)

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
    "811a16b6a47bca60281fb4afe8280783146e6f4ee28955dde7907b47fc65bb49"
)
EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256 = (
    "c2787b105553b80ee9a1e5e1d925d6cac2ab819b0cdfab305484bf89bbba32c5"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256 = (
    "327837e4646cb79cb237611ab49e645b51a47a36a97006e94838d1f5fa05af60"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_MANIFEST_SHA256 = (
    "d51151fc1d6c73c33f1b50da0a09de4d3346212599716feaba578839dde37526"
)
EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256 = (
    "81ac62fa093c48d57667cb56958ad58a8ed26e8ff81abd7c35365e01fb981d6f"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "5ced57f7f6fc8aef50a6536920243d00af083b0a113b09d19f239bc1266fd8a5"
)
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "6e38b93fadec1baee53621c3a9ea28c25c8a39ead0d7fbd25a26fcc4295c4423"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "81da7db6f4553e0411d30b23bf6b6e45966158178c3c3e55880b821bbad7ea37"
)
EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256 = (
    "c70ba1f0c695af397f15083859d25119e20ca4f40c103a605af7c37dea449d24"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256 = (
    "46e1483315c259fb7afc8686466b29e9938e8372fd6c7b99d64c9cac6c47f90c"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "b82a83a062881bf7ce02de1f962a51b07215696aa150a1821d5df1c0154e5b19"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_PREDECESSOR_TRANSCRIPT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

MODE = "double_occupancy"
BASE_PARENT_HORIZON = 66
EXTENDED_HORIZON = 68
K573440 = 573_440
KERNEL_MAX_CANDIDATE_COUNT = 33

PREDECESSOR_D_CANDIDATES = (
    73_728, 81_920, 90_112, 98_304, 106_496, 114_688, 122_880,
    131_072, 147_456, 163_840, 180_224, 196_608, 212_992, 229_376,
    245_760, 262_144, 278_528, 294_912, 311_296, 327_680, 344_064,
    360_448, 376_832, 393_216, 409_600, 425_984, 442_368, 458_752,
    475_136, 507_904, 524_288, 540_672,
)
D_CANDIDATES = PREDECESSOR_D_CANDIDATES + (K573440,)
EXPECTED_PREDECESSOR_CANDIDATE_SHA256 = (
    "071999328539f944d72affe0dc14999ef6c1d728bef8a4f94266b1b9950e1133"
)
EXPECTED_CANDIDATE_SHA256 = (
    "461517a4e7d5f6ffbb610b53240f01071cc7f7a9ac1b2dfdbc6e4b0addd59a27"
)
EXPECTED_Q66_SELECTED_HISTORY_PREFIX_SHA256 = (
    "2c28a8b1b7450f300aa251320582ed13660d6919f0bb2a7b0c5ebe1369599f95"
)
EXPECTED_V6_BASELINE_CANDIDATE_SHA256 = {
    "magnetization": (
        "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
    ),
    MODE: "df55613f1fbd691f42319976d4722e614b25a8c985cdae5df9797f2e49660160",
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
EXPECTED_PREDECESSOR_POLICY_CAPS = {
    **EXPECTED_V6_POLICY_CAPS,
    "max_candidate_K": 540_672,
    "max_output_terms_if_successful": 540_672,
}
POLICY_CAPS_BASE = {
    **EXPECTED_PREDECESSOR_POLICY_CAPS,
    "max_candidate_K": K573440,
    "max_output_terms_if_successful": K573440,
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
EXPECTED_PREDECESSOR_KERNEL_CAPABILITY_LIMITS = {
    **EXPECTED_V2_KERNEL_CAPABILITY_LIMITS,
    "max_retained_K": 540_672,
}
EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS = {
    **EXPECTED_V2_KERNEL_CAPABILITY_LIMITS,
    "max_candidate_count": 33,
    "max_retained_K": K573440,
}
DIRECT_KERNEL_CAPABILITY_CHANGE_FROM_V2 = {
    "max_candidate_count": {"before": 32, "after": 33},
    "max_retained_K": {"before": 524_288, "after": K573440},
}
ROUTE_KERNEL_CAPABILITY_CHANGE_FROM_K540672 = {
    "max_candidate_count": {"before": 32, "after": 33},
    "max_retained_K": {"before": 540_672, "after": K573440},
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


def bounded_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as handle:
        payload = handle.read(maximum + 1)
    if len(payload) > maximum:
        raise RuntimeError(f"byte cap exceeded: {path.name}")
    return payload


def checked_repo_file(repo: Path, relative_path: str) -> Path:
    if type(relative_path) is not str or not relative_path:
        raise RuntimeError("relative path is not a nonempty string")
    repo = repo.resolve()
    path = (repo / relative_path).resolve()
    try:
        path.relative_to(repo)
    except ValueError as exc:
        raise RuntimeError("path escapes the repository") from exc
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
    payload = bounded_bytes(path, MAX_PINNED_SOURCE_BYTES)
    observed = sha256(payload)
    if observed != expected_sha:
        raise RuntimeError(f"source pin drift for {relative_path}: {observed}")
    return compile_isolated(module_name, path, payload), payload


def changed_mapping_keys(before: Mapping[str, Any], after: Mapping[str, Any]) -> set[str]:
    return {
        key
        for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    }


def validate_local_configuration() -> None:
    if len(PREDECESSOR_D_CANDIDATES) != 32 or len(D_CANDIDATES) != 33:
        raise RuntimeError("D candidate count drift")
    if D_CANDIDATES != PREDECESSOR_D_CANDIDATES + (K573440,):
        raise RuntimeError("D route is not an exact append")
    if any(type(value) is not int or value <= 0 for value in D_CANDIDATES):
        raise RuntimeError("D candidate value drift")
    if any(left >= right for left, right in zip(D_CANDIDATES, D_CANDIDATES[1:])):
        raise RuntimeError("D candidate order drift")
    if sha256(canonical_bytes(list(PREDECESSOR_D_CANDIDATES))) != (
        EXPECTED_PREDECESSOR_CANDIDATE_SHA256
    ):
        raise RuntimeError("D predecessor candidate digest drift")
    if sha256(canonical_bytes(list(D_CANDIDATES))) != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("D candidate digest drift")
    if len(D_CANDIDATES) > KERNEL_MAX_CANDIDATE_COUNT:
        raise RuntimeError("D candidate count exceeds the declared kernel limit")
    expected_policy_fields = {
        "max_candidate_K",
        "max_output_terms_if_successful",
    }
    if changed_mapping_keys(EXPECTED_V6_POLICY_CAPS, POLICY_CAPS_BASE) != (
        expected_policy_fields
    ):
        raise RuntimeError("direct v6 policy override changed a non-K field")
    if changed_mapping_keys(EXPECTED_PREDECESSOR_POLICY_CAPS, POLICY_CAPS_BASE) != (
        expected_policy_fields
    ):
        raise RuntimeError("route policy override changed a non-K field")
    if POLICY_CAPS_BASE["max_candidate_K"] != D_CANDIDATES[-1]:
        raise RuntimeError("policy maximum and D ladder maximum disagree")
    if EXTENDED_HORIZON != 68 or BASE_PARENT_HORIZON != 66:
        raise RuntimeError("D horizon contract drift")


def load_control_flow_parent(repo: Path) -> Any:
    parent, _payload = load_pinned_module(
        repo,
        CONTROL_FLOW_PARENT_NAME,
        EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "pinned_four_gate_control_flow_parent_for_k573440_c33_q68",
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
    expected_horizons = {"magnetization": 80, MODE: BASE_PARENT_HORIZON}
    observed_horizons = {
        mode: config["horizon_checkpoint_count"]
        for mode, config in parent.MODE_CONFIG.items()
    }
    if observed_horizons != expected_horizons:
        raise RuntimeError("control-flow parent baseline horizon drift")
    return parent


def load_configured_v6_baseline(repo: Path) -> Tuple[Any, Tuple[int, ...]]:
    configuration, _payload = load_pinned_module(
        repo,
        V6_BASELINE_CONFIGURATION_NAME,
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "pinned_v6_baseline_configuration_for_k573440_c33_q68",
    )
    if configuration.POLICY_CAPS_BASE != EXPECTED_V6_POLICY_CAPS:
        raise RuntimeError("v6 baseline policy caps drift")
    if sha256(canonical_bytes(configuration.POLICY_CAPS_BASE)) != (
        EXPECTED_V6_POLICY_CAPS_SHA256
    ):
        raise RuntimeError("v6 baseline policy digest drift")
    for configured_mode, expected_sha in EXPECTED_V6_BASELINE_CANDIDATE_SHA256.items():
        candidates = configuration.MODE_CONFIG[configured_mode]["candidates"]
        if type(candidates) is not tuple:
            raise RuntimeError(f"v6 baseline candidate type drift: {configured_mode}")
        if sha256(canonical_bytes(list(candidates))) != expected_sha:
            raise RuntimeError(f"v6 baseline candidate digest drift: {configured_mode}")
    baseline_d = tuple(configuration.MODE_CONFIG[MODE]["candidates"])
    if baseline_d[0] != 65_536 or baseline_d.count(65_536) != 1:
        raise RuntimeError("v6 D removable slot drift")
    if PREDECESSOR_D_CANDIDATES != baseline_d[1:] + (540_672,):
        raise RuntimeError("D predecessor construction from v6 drift")
    if D_CANDIDATES != baseline_d[1:] + (540_672, K573440):
        raise RuntimeError("D direct construction from v6 drift")
    runtime_config = copy.deepcopy(configuration.MODE_CONFIG)
    runtime_config[MODE]["candidates"] = tuple(D_CANDIDATES)
    configuration.MODE_CONFIG = runtime_config
    configuration.POLICY_CAPS_BASE = dict(POLICY_CAPS_BASE)
    return configuration, baseline_d


def load_kernel_wrapper(repo: Path) -> Tuple[Any, str, Dict[str, Any]]:
    wrapper_path = checked_repo_file(repo, KERNEL_WRAPPER_NAME)
    wrapper_payload = bounded_bytes(wrapper_path, MAX_PINNED_SOURCE_BYTES)
    wrapper_sha = sha256(wrapper_payload)
    if wrapper_sha != EXPECTED_KERNEL_WRAPPER_SHA256:
        raise RuntimeError(f"source pin drift for {KERNEL_WRAPPER_NAME}: {wrapper_sha}")
    v2_path = checked_repo_file(repo, V2_ARITHMETIC_NAME)
    v2_payload = bounded_bytes(v2_path, MAX_PINNED_SOURCE_BYTES)
    if sha256(v2_payload) != EXPECTED_V2_ARITHMETIC_SHA256:
        raise RuntimeError("arithmetic-v2 source pin drift")
    wrapper = types.ModuleType("pinned_k573440_c33_arithmetic_capability_wrapper")
    wrapper.__file__ = str(wrapper_path)
    wrapper.__package__ = ""
    wrapper.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = wrapper_payload
    wrapper.__dict__["_VERIFIED_BASE_KERNEL_SOURCE_BYTES"] = v2_payload
    exec(compile(wrapper_payload, wrapper.__file__, "exec"), wrapper.__dict__)
    expected_constants = {
        "BASE_KERNEL_NAME": V2_ARITHMETIC_NAME,
        "EXPECTED_BASE_KERNEL_SHA256": EXPECTED_V2_ARITHMETIC_SHA256,
        "EXPECTED_ROUTE_PREDECESSOR_SHA256": (
            EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256
        ),
        "EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256": (
            EXPECTED_ROUTE_PREDECESSOR_KERNEL_MANIFEST_SHA256
        ),
        "EXPECTED_BASE_RESOURCE_LIMITS": EXPECTED_V2_KERNEL_CAPABILITY_LIMITS,
        "EXPECTED_ROUTE_PREDECESSOR_RESOURCE_LIMITS": (
            EXPECTED_PREDECESSOR_KERNEL_CAPABILITY_LIMITS
        ),
        "EXTENDED_RESOURCE_LIMITS": EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        "RESOURCE_LIMIT_DELTA": DIRECT_KERNEL_CAPABILITY_CHANGE_FROM_V2,
        "ROUTE_RESOURCE_LIMIT_DELTA_FROM_K540672": (
            ROUTE_KERNEL_CAPABILITY_CHANGE_FROM_K540672
        ),
    }
    for name, expected in expected_constants.items():
        if getattr(wrapper, name, None) != expected:
            raise RuntimeError(f"kernel wrapper contract drift: {name}")
    if wrapper.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS:
        raise RuntimeError("kernel wrapper effective limits drift")
    manifest = wrapper.capability_manifest()
    manifest_sha = sha256(canonical_bytes(manifest))
    if manifest_sha != EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256:
        raise RuntimeError("kernel capability manifest pin drift")
    if wrapper.capability_manifest_sha256() != manifest_sha:
        raise RuntimeError("kernel capability manifest digest API drift")
    expected_layers = [KERNEL_WRAPPER_NAME, V2_ARITHMETIC_NAME]
    if [item.get("relative_path") for item in manifest.get("source_layers", ())] != (
        expected_layers
    ):
        raise RuntimeError("kernel execution source-layer drift")
    route_reference = manifest.get("route_predecessor_reference")
    if type(route_reference) is not dict:
        raise RuntimeError("kernel route predecessor reference drift")
    if route_reference.get("source_sha256") != (
        EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256
    ):
        raise RuntimeError("kernel route predecessor source pin drift")
    if route_reference.get("capability_manifest_sha256") != (
        EXPECTED_ROUTE_PREDECESSOR_KERNEL_MANIFEST_SHA256
    ):
        raise RuntimeError("kernel route predecessor manifest pin drift")
    if any(route_reference.get(key) is not False for key in (
        "compiled", "executed", "execution_source_layer"
    )):
        raise RuntimeError("kernel route predecessor became an execution layer")
    return wrapper, wrapper_sha, manifest


def load_route_predecessor_reference(
    repo: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    screen_path = checked_repo_file(repo, ROUTE_PREDECESSOR_SCREEN_NAME)
    screen_payload = bounded_bytes(screen_path, MAX_PINNED_SOURCE_BYTES)
    if sha256(screen_payload) != EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256:
        raise RuntimeError("route predecessor screen source pin drift")
    transcript_path = checked_repo_file(repo, ROUTE_PREDECESSOR_TRANSCRIPT_NAME)
    raw = bounded_bytes(transcript_path, MAX_PREDECESSOR_TRANSCRIPT_BYTES)
    if sha256(raw) != EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256:
        raise RuntimeError("route predecessor transcript pin drift")
    try:
        transcript = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("route predecessor transcript is invalid JSON") from exc
    if type(transcript) is not dict or raw != canonical_bytes(transcript):
        raise RuntimeError("route predecessor transcript is not canonical JSON")
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_k540672_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "screen_horizon_checkpoint_count": BASE_PARENT_HORIZON,
        "attempted_checkpoint_count": 66,
        "completed_checkpoint_count": 65,
        "failure_checkpoint_included": True,
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": False,
        "candidate_K_values": list(PREDECESSOR_D_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **EXPECTED_PREDECESSOR_POLICY_CAPS,
            "max_candidate_count": 32,
        },
        "kernel_capability_limits": (
            EXPECTED_PREDECESSOR_KERNEL_CAPABILITY_LIMITS
        ),
        "records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        "failure_record_sha256": EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256,
        "configuration_override_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
        ),
        "checkpoint_transform_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, value in expected.items():
        if transcript.get(key) != value:
            raise RuntimeError(f"route predecessor transcript drift: {key}")
    records = transcript.get("records")
    history = transcript.get("selected_K_history")
    if type(records) is not list or len(records) != 66:
        raise RuntimeError("route predecessor record count drift")
    if type(history) is not list or len(history) != 65:
        raise RuntimeError("route predecessor history count drift")
    if sha256(canonical_bytes(records)) != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256:
        raise RuntimeError("route predecessor records digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256:
        raise RuntimeError("route predecessor history digest drift")
    if sha256(canonical_bytes(records[-1])) != EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256:
        raise RuntimeError("route predecessor failure digest drift")
    failure = records[-1]
    expected_q66 = {
        "checkpoint_number_one_based": 66,
        "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "pretruncation_expansion_count": 679_285,
        "minimum_effective_K_to_meet_prefix": 558_598,
        "required_K_excess_over_policy_maximum": 17_926,
        "selected_K": None,
        "selected_candidate_index": None,
    }
    for key, value in expected_q66.items():
        if failure.get(key) != value:
            raise RuntimeError(f"route predecessor q66 drift: {key}")
    reference = {
        "route_id": "double_occupancy_k540672_to_k573440_c33_q68_v1",
        "screen": {
            "relative_path": ROUTE_PREDECESSOR_SCREEN_NAME,
            "source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
            "compiled": False,
            "executed": False,
            "execution_source_layer": False,
        },
        "canonical_transcript": {
            "relative_path": ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
            "file_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
            "records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
            "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
            "failure_record_sha256": EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256,
            "loaded_before_replay_as_exact_reference": True,
            "used_only_after_replay_for_result_prefix_validation": True,
            "propagation_input": False,
            "checkpoint_65_state_loaded": False,
            "checkpoint_66_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
        },
    }
    return transcript, reference


def configure_parent_execution(
    parent: Any,
    configuration: Any,
    kernel_wrapper: Any,
) -> Dict[str, Any]:
    baseline_parent_config = copy.deepcopy(parent.MODE_CONFIG)
    if baseline_parent_config[MODE]["horizon_checkpoint_count"] != (
        BASE_PARENT_HORIZON
    ):
        raise RuntimeError("parent D horizon baseline drift")
    effective_parent_config = copy.deepcopy(baseline_parent_config)
    effective_parent_config[MODE]["horizon_checkpoint_count"] = EXTENDED_HORIZON
    changed = []
    for mode, before_mode in baseline_parent_config.items():
        after_mode = effective_parent_config[mode]
        for key, before_value in before_mode.items():
            if after_mode.get(key) != before_value:
                changed.append(f"MODE_CONFIG.{mode}.{key}")
    expected_changed = [f"MODE_CONFIG.{MODE}.horizon_checkpoint_count"]
    if changed != expected_changed:
        raise RuntimeError("parent configuration changed outside D horizon")
    if effective_parent_config["magnetization"] != (
        baseline_parent_config["magnetization"]
    ):
        raise RuntimeError("parent magnetization configuration changed")
    parent.MODE_CONFIG = effective_parent_config

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
        if kernel_wrapper.RESOURCE_LIMITS != (
            EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        ):
            raise RuntimeError("wrapped kernel capability limits drift")
        if base_kernel.RESOURCE_LIMITS != EXPECTED_V2_KERNEL_CAPABILITY_LIMITS:
            raise RuntimeError("kernel wrapper mutated parent v2 arithmetic")
        return kernel_wrapper, root, modules, custody

    parent.load_execution_sources = load_wrapped_execution_sources
    return {
        "override_id": "double_occupancy_parent_q68_horizon_override_v1",
        "parent_relative_path": CONTROL_FLOW_PARENT_NAME,
        "parent_source_sha256": EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "parent_module_isolated": True,
        "parent_source_bytes_changed": False,
        "changed_fields": expected_changed,
        "semantic_delta": {
            expected_changed[0]: {
                "before": BASE_PARENT_HORIZON,
                "after": EXTENDED_HORIZON,
            },
        },
        "parent_mode_config_before": baseline_parent_config,
        "parent_mode_config_before_sha256": sha256(
            canonical_bytes(baseline_parent_config)
        ),
        "parent_mode_config_after": effective_parent_config,
        "parent_mode_config_after_sha256": sha256(
            canonical_bytes(effective_parent_config)
        ),
        "magnetization_configuration_unchanged": True,
    }


def validate_replay_handoff(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:
    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or not 67 <= len(records) <= EXTENDED_HORIZON:
        raise RuntimeError("D q68 result did not commit q66 and attempt beyond it")
    if type(history) is not list or not 66 <= len(history) <= EXTENDED_HORIZON:
        raise RuntimeError("D q68 selected history length drift")
    old_records = predecessor["records"]
    old_history = predecessor["selected_K_history"]
    if history[:65] != old_history:
        raise RuntimeError("D q68 changed the exact q1-65 selected history")
    for index in range(65):
        old = old_records[index]
        new = records[index]
        old_common = {key: value for key, value in old.items() if key != "candidate_records"}
        new_common = {key: value for key, value in new.items() if key != "candidate_records"}
        if new_common != old_common:
            raise RuntimeError(f"D q68 changed q{index + 1} common record state")
        old_rows = old["candidate_records"]
        new_rows = new.get("candidate_records")
        if type(new_rows) is not list or new_rows[:32] != old_rows:
            raise RuntimeError(f"D q68 changed q{index + 1} predecessor candidate rows")
        if len(new_rows) != 33:
            raise RuntimeError(f"D q68 candidate row count drift at q{index + 1}")
        appended = new_rows[32]
        if appended.get("candidate_index") != 32 or appended.get("configured_K") != K573440:
            raise RuntimeError(f"D q68 appended candidate row drift at q{index + 1}")

    old_q66 = old_records[65]
    new_q66 = records[65]
    excluded = {
        "candidate_records",
        "status",
        "selected_candidate_index",
        "selected_K",
        "removed_491520_counterfactual",
    }
    old_shared = {
        key: value for key, value in old_q66.items()
        if key in new_q66 and key not in excluded
    }
    new_shared = {
        key: value for key, value in new_q66.items()
        if key in old_q66 and key not in excluded
    }
    if new_shared != old_shared:
        raise RuntimeError("D q68 changed the exact q66 shared propagation fields")
    old_rows = old_q66["candidate_records"]
    new_rows = new_q66.get("candidate_records")
    if type(new_rows) is not list or len(new_rows) != 33 or new_rows[:32] != old_rows:
        raise RuntimeError("D q68 changed the q66 predecessor candidate rows")
    appended = new_rows[32]
    expected_appended = {
        "candidate_index": 32,
        "configured_K": K573440,
        "effective_retained_count": K573440,
        "dropped_term_count": 105_845,
        "feasible_under_current_prefix_cap": True,
    }
    for key, value in expected_appended.items():
        if appended.get(key) != value:
            raise RuntimeError(f"D q66 appended candidate drift: {key}")
    if int(appended["E_after_if_selected_ticks"]) != (
        int(new_q66["E_before_ticks"]) + int(appended["drop_ticks"])
    ):
        raise RuntimeError("D q66 appended candidate E recurrence drift")
    expected_q66 = {
        "checkpoint_number_one_based": 66,
        "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        "selected_candidate_index": 32,
        "selected_K": K573440,
        "selected_effective_retained_count": K573440,
        "selected_dropped_term_count": 105_845,
        "retained_expansion_count": K573440,
    }
    for key, value in expected_q66.items():
        if new_q66.get(key) != value:
            raise RuntimeError(f"D q66 handoff drift: {key}")
    if new_q66.get("selected_drop_ticks") != appended.get("drop_ticks"):
        raise RuntimeError("D q66 selected drop and candidate row disagree")
    if int(new_q66["E_after_ticks"]) != int(appended["E_after_if_selected_ticks"]):
        raise RuntimeError("D q66 committed E and candidate row disagree")
    if int(new_q66["E_after_ticks"]) > int(new_q66["budget_prefix_cap_ticks"]):
        raise RuntimeError("D q66 selected candidate violates the prefix cap")
    old_counterfactual = dict(old_q66["removed_491520_counterfactual"])
    new_counterfactual = dict(new_q66["removed_491520_counterfactual"])
    old_counterfactual.pop("actual_selected_K", None)
    new_counterfactual.pop("actual_selected_K", None)
    if new_counterfactual != old_counterfactual:
        raise RuntimeError("D q66 removed-491520 counterfactual drift")
    if new_q66["removed_491520_counterfactual"].get("actual_selected_K") != K573440:
        raise RuntimeError("D q66 counterfactual selected-K label drift")
    if history[65] != K573440:
        raise RuntimeError("D q66 selected history handoff drift")
    if sha256(canonical_bytes(history[:66])) != (
        EXPECTED_Q66_SELECTED_HISTORY_PREFIX_SHA256
    ):
        raise RuntimeError("D q66 selected history prefix digest drift")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("D q68 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(canonical_bytes(history)):
        raise RuntimeError("D q68 selected history digest drift")
    if result.get("attempted_checkpoint_count") != len(records):
        raise RuntimeError("D q68 attempted checkpoint count drift")
    if result.get("completed_checkpoint_count") != len(history):
        raise RuntimeError("D q68 completed checkpoint count drift")
    final = records[-1]
    failure = final.get("status") == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
    if failure:
        if len(history) != len(records) - 1:
            raise RuntimeError("D q68 failure/history count drift")
        if result.get("screen_terminal_condition") != (
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        ):
            raise RuntimeError("D q68 failure terminal label drift")
    else:
        if len(records) != EXTENDED_HORIZON or len(history) != EXTENDED_HORIZON:
            raise RuntimeError("D q68 non-failure did not commit the horizon")
        if result.get("screen_terminal_condition") != "DIAGNOSTIC_HORIZON_REACHED":
            raise RuntimeError("D q68 horizon terminal label drift")
    return {
        "validation_id": "D_k573440_c33_q68_predecessor_handoff_v1",
        "q1_through_q65_common_records_exact": True,
        "q1_through_q65_first_32_candidate_rows_exact": True,
        "q1_through_q65_selected_history_exact": True,
        "q66_shared_propagation_fields_exact": True,
        "q66_first_32_candidate_rows_exact": True,
        "q66_selected_candidate_index": 32,
        "q66_selected_K": K573440,
        "q66_selected_history_prefix_sha256": (
            EXPECTED_Q66_SELECTED_HISTORY_PREFIX_SHA256
        ),
        "q67_and_q68_outcomes_precommitted": False,
    }


def execution_components(
    parent_components: Any,
    self_sha: str,
    kernel_wrapper_sha: str,
) -> list[Dict[str, Any]]:
    if type(parent_components) is not list:
        raise RuntimeError("control-flow parent component list drift")
    components = [{
        "relative_path": SELF_NAME,
        "role": "D_k573440_c33_q68_fresh_same_byte_screen",
        "sha256": self_sha,
    }]
    saw_parent = False
    saw_v6 = False
    saw_v2 = False
    for original in parent_components:
        if type(original) is not dict:
            raise RuntimeError("control-flow parent component is not a dict")
        item = dict(original)
        relative_path = item.get("relative_path")
        if relative_path == CONTROL_FLOW_PARENT_NAME:
            if item.get("sha256") != EXPECTED_CONTROL_FLOW_PARENT_SHA256:
                raise RuntimeError("control-flow parent component pin drift")
            item["role"] = "four_gate_control_flow_parent_private_entrypoint"
            saw_parent = True
        elif relative_path == V6_BASELINE_CONFIGURATION_NAME:
            if item.get("sha256") != EXPECTED_V6_BASELINE_CONFIGURATION_SHA256:
                raise RuntimeError("v6 baseline component pin drift")
            item["role"] = "v6_baseline_configuration_before_declared_override"
            saw_v6 = True
        elif relative_path == V2_ARITHMETIC_NAME:
            if item.get("sha256") != EXPECTED_V2_ARITHMETIC_SHA256:
                raise RuntimeError("v2 arithmetic component pin drift")
            item["role"] = "v2_arithmetic_bytes_beneath_capability_wrapper"
            saw_v2 = True
        components.append(item)
        if relative_path == V2_ARITHMETIC_NAME:
            components.append({
                "relative_path": KERNEL_WRAPPER_NAME,
                "role": "k573440_c33_capability_override_provider",
                "sha256": kernel_wrapper_sha,
            })
    if not (saw_parent and saw_v6 and saw_v2):
        raise RuntimeError("control-flow parent component set is incomplete")
    return components


def configuration_reference() -> Dict[str, Any]:
    return {
        "relative_path": V6_BASELINE_CONFIGURATION_NAME,
        "source_sha256": EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "role": "v6_baseline_candidates_and_caps_before_direct_override",
        "baseline_D_candidate_K_values_sha256": (
            EXPECTED_V6_BASELINE_CANDIDATE_SHA256[MODE]
        ),
        "baseline_policy_caps_sha256": EXPECTED_V6_POLICY_CAPS_SHA256,
        "compiled_from_verified_bytes": True,
        "module_isolated": True,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }


def configuration_override(baseline_d: Tuple[int, ...]) -> Dict[str, Any]:
    if D_CANDIDATES != baseline_d[1:] + (540_672, K573440):
        raise RuntimeError("configuration override baseline D ladder drift")
    return {
        "override_id": "double_occupancy_k573440_c33_configuration_override_v1",
        "diagnostic_ladder_precommitted_before_replay": True,
        "direct_execution_override_from_v6": {
            "baseline_candidate_K_values_sha256": (
                EXPECTED_V6_BASELINE_CANDIDATE_SHA256[MODE]
            ),
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 32, "after": 33},
            "candidate_ladder_added": [540_672, K573440],
            "candidate_ladder_removed": [65_536],
            "policy_cap_changes": {
                "max_candidate_K": {"before": 524_288, "after": K573440},
                "max_output_terms_if_successful": {
                    "before": 524_288,
                    "after": K573440,
                },
            },
        },
        "incremental_route_override_from_k540672": {
            "predecessor_candidate_K_values_sha256": (
                EXPECTED_PREDECESSOR_CANDIDATE_SHA256
            ),
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 32, "after": 33},
            "candidate_ladder_added": [K573440],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {
                "max_candidate_K": {"before": 540_672, "after": K573440},
                "max_output_terms_if_successful": {
                    "before": 540_672,
                    "after": K573440,
                },
            },
            "predecessor_configuration_override_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
            ),
        },
        "derived_policy_cap": {
            "field": "max_candidate_count",
            "derivation": "len(candidate_K_values)",
            "before_on_route": 32,
            "after": 33,
        },
        "unchanged_policy_caps": {
            key: value for key, value in EXPECTED_V6_POLICY_CAPS.items()
            if key not in {"max_candidate_K", "max_output_terms_if_successful"}
        },
        "overridden_fields": [
            f"MODE_CONFIG.{MODE}.candidates",
            "POLICY_CAPS_BASE.max_candidate_K",
            "POLICY_CAPS_BASE.max_output_terms_if_successful",
        ],
    }


def kernel_capability_override(
    wrapper_sha: str,
    manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "relative_path": KERNEL_WRAPPER_NAME,
        "source_sha256": wrapper_sha,
        "role": "separate_k573440_c33_capability_override_provider",
        "base_arithmetic_relative_path": V2_ARITHMETIC_NAME,
        "base_arithmetic_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "module_itself_is_extended_kernel": True,
        "verified_compilation_inputs": [
            "_VERIFIED_SELF_SOURCE_BYTES",
            "_VERIFIED_BASE_KERNEL_SOURCE_BYTES",
        ],
        "capability_manifest": dict(manifest),
        "capability_manifest_sha256": sha256(canonical_bytes(manifest)),
        "direct_capability_changes_from_v2": (
            DIRECT_KERNEL_CAPABILITY_CHANGE_FROM_V2
        ),
        "incremental_route_changes_from_k540672": (
            ROUTE_KERNEL_CAPABILITY_CHANGE_FROM_K540672
        ),
        "execution_source_layers": [KERNEL_WRAPPER_NAME, V2_ARITHMETIC_NAME],
        "route_predecessor_is_execution_source": False,
        "v2_arithmetic_module_mutated_by_screen": False,
    }


def validate_and_relabel(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
    predecessor_reference: Mapping[str, Any],
    baseline_d: Tuple[int, ...],
    kernel_wrapper_sha: str,
    kernel_manifest: Mapping[str, Any],
    horizon_override: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("D q68 relabel requires fresh same-byte self execution")
    if type(result) is not dict:
        raise RuntimeError("control-flow parent result is not an exact dict")
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
        "screen_horizon_checkpoint_count": EXTENDED_HORIZON,
        "candidate_K_values": list(D_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **POLICY_CAPS_BASE,
            "max_candidate_count": len(D_CANDIDATES),
        },
        "kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
    }
    for key, expected in expected_parent_fields.items():
        if result.get(key) != expected:
            raise RuntimeError(f"control-flow parent result drift: {key}")
    handoff = validate_replay_handoff(result, predecessor)

    old_components = result.get("screen_execution_components")
    old_components_sha = result.get("screen_execution_components_sha256")
    if old_components_sha != sha256(canonical_bytes(old_components)):
        raise RuntimeError("control-flow parent component digest drift")
    old_configuration = result.get("configuration_reference")
    old_configuration_sha = result.get("configuration_reference_sha256")
    if old_configuration_sha != sha256(canonical_bytes(old_configuration)):
        raise RuntimeError("control-flow parent configuration digest drift")
    old_transform = result.get("checkpoint_transform")
    old_transform_sha = result.get("checkpoint_transform_sha256")
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("control-flow parent transform digest drift")

    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = execution_components(
        old_components,
        self_sha,
        kernel_wrapper_sha,
    )
    baseline_reference = configuration_reference()
    config_override = configuration_override(baseline_d)
    capability = kernel_capability_override(kernel_wrapper_sha, kernel_manifest)
    route_reference = dict(predecessor_reference)
    transform = {
        "transform_id": "double_occupancy_four_gate_k573440_c33_q68_v1",
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": old_transform_sha,
        "route_predecessor_transform_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256
        ),
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "overridden_semantics": [
            "candidate_K_values",
            "policy_max_candidate_K",
            "policy_max_output_terms_if_successful",
            "derived_policy_max_candidate_count",
            "kernel_max_retained_K",
            "kernel_max_candidate_count",
            "double_occupancy_horizon_checkpoint_count",
        ],
    }
    custody = dict(result.get("source_custody", {}))
    for relative_path in (SELF_NAME, CONTROL_FLOW_PARENT_NAME, KERNEL_WRAPPER_NAME):
        if relative_path in custody:
            raise RuntimeError(f"unexpected preexisting custody entry: {relative_path}")
    custody[SELF_NAME] = self_sha
    custody[CONTROL_FLOW_PARENT_NAME] = EXPECTED_CONTROL_FLOW_PARENT_SHA256
    custody[KERNEL_WRAPPER_NAME] = kernel_wrapper_sha

    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k573440_c33_q68_screen_v1"
        ),
        "screen_source_sha256": self_sha,
        "same_byte_self_execution": True,
        "control_flow_owned_by_screen": False,
        "control_flow_owned_by_verified_parent": True,
        "control_flow_parent_relative_path": CONTROL_FLOW_PARENT_NAME,
        "control_flow_parent_source_sha256": EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "control_flow_parent_compiled_from_verified_bytes": True,
        "control_flow_parent_module_isolated": True,
        "control_flow_parent_same_byte_execution": True,
        "control_flow_parent_private_entrypoint_called": True,
        "control_flow_parent_runtime_horizon_override_applied": True,
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
        "configuration_reference_sha256": sha256(canonical_bytes(baseline_reference)),
        "configuration_override": config_override,
        "configuration_override_sha256": sha256(canonical_bytes(config_override)),
        "kernel_capability_override": capability,
        "kernel_capability_override_sha256": sha256(canonical_bytes(capability)),
        "parent_horizon_override": dict(horizon_override),
        "parent_horizon_override_sha256": sha256(canonical_bytes(horizon_override)),
        "route_predecessor_reference": route_reference,
        "route_predecessor_reference_sha256": sha256(canonical_bytes(route_reference)),
        "predecessor_handoff_validation": handoff,
        "predecessor_handoff_validation_sha256": sha256(canonical_bytes(handoff)),
        "checkpoint_transform": transform,
        "checkpoint_transform_sha256": sha256(canonical_bytes(transform)),
        "source_custody": custody,
        "diagnostic_candidate_ladder_precommitted_before_replay": True,
        "diagnostic_horizon_precommitted_before_replay": True,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    })
    return result


def _run_verified(repo: Path) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("D q68 screen requires fresh same-byte self execution")
    validate_local_configuration()
    repo = repo.resolve()
    parent = load_control_flow_parent(repo)
    configuration, baseline_d = load_configured_v6_baseline(repo)
    kernel_wrapper, kernel_wrapper_sha, kernel_manifest = load_kernel_wrapper(repo)
    predecessor, predecessor_reference = load_route_predecessor_reference(repo)
    horizon_override = configure_parent_execution(
        parent,
        configuration,
        kernel_wrapper,
    )
    result = parent._run_verified(repo, MODE)
    return validate_and_relabel(
        result,
        predecessor,
        predecessor_reference,
        baseline_d,
        kernel_wrapper_sha,
        kernel_manifest,
        horizon_override,
    )


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_double_occupancy_k573440_c33_q68_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("D q68 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("D q68 transcript exceeds output byte cap")
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
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp"))
    args = parser.parse_args()
    result = run(args.repo)
    raw = canonical_bytes(result)
    output = args.output_dir / OUTPUT_NAME
    write_atomic_bounded(output, raw)
    final_record = result["records"][-1]
    print(json.dumps({
        "output": output.name,
        "semantic_and_file_sha256": sha256(raw),
        "records_sha256": result["records_sha256"],
        "screen_terminal_condition": result["screen_terminal_condition"],
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "attempted_checkpoint_count": result["attempted_checkpoint_count"],
        "final_status": final_record["status"],
        "final_checkpoint": final_record["checkpoint_number_one_based"],
        "last_committed_cumulative_drop_ticks": (
            result["last_committed_cumulative_drop_ticks"]
        ),
        "peak": result["observed_peak_single_expansion_terms"],
        "visits": result["observed_term_gate_visits_including_terminal_attempt"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
