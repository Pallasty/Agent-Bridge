#!/usr/bin/env python3
"""Source-pinned, diagnostic-only M K=557056/C=31 q82 screen.

Execution always starts at checkpoint one through a fresh same-byte copy of the
exact four-gate control-flow parent.  The canonical K=540672 q82 transcript is
an exact route reference used only after replay for prefix/handoff validation;
it is never an execution source or state-resume input.
"""

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
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k557056_c31_q82_screen.py"
)
CONTROL_FLOW_PARENT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k557056.py"
ROUTE_PREDECESSOR_SCREEN_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_k540672_q82_screen.py"
)
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_k540672_q82_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k557056_c31_q82_transcript.json"
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
    "4c54b9a2451ad9ae76e4b4036705558cdc527f22b015fd67c035118ad2c8506f"
)
EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256 = (
    "cc60b39010c55fa3a95f7160e5ccb0a4985ab6926aa8076841d75e660a954868"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256 = (
    "327837e4646cb79cb237611ab49e645b51a47a36a97006e94838d1f5fa05af60"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_MANIFEST_SHA256 = (
    "d51151fc1d6c73c33f1b50da0a09de4d3346212599716feaba578839dde37526"
)
EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256 = (
    "c06d2be38215266f1d19dc64116041b456e2a597e6aa24aa63b9ffbaeda86b03"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "0486a8b19077de9e90f134c7b3c0d43fdf3504a4876d6e0b2c3d01b37b89cb52"
)
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "55e74ae79a1761817f1e80e4922476b5dbc6a01b9125c6e04ad68596e7cf221c"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "43dabd7d34c8de39a91388080dac5e941c162867771fe39fe8a216f7ad00dcc9"
)
EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256 = (
    "00a66d441fa03dde95596dd689576933dd63ee340d2ec2f4c615dadb799f323d"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256 = (
    "abc21d86243ad2460afaadc7c09f0f15f7eb544c5aeb40abdba01c7f9d6eedcf"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "68b6ee4d4647cf4d49bc854f6e5f42b0d029eaf8fba070527f0dac35155566c1"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_PREDECESSOR_TRANSCRIPT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

MODE = "magnetization"
BASE_PARENT_HORIZON = 80
EXTENDED_HORIZON = 82
K540672 = 540_672
K557056 = 557_056

V6_M_CANDIDATES = tuple(range(65_536, 524_288 + 1, 16_384))
PREDECESSOR_M_CANDIDATES = V6_M_CANDIDATES + (K540672,)
M_CANDIDATES = PREDECESSOR_M_CANDIDATES + (K557056,)
EXPECTED_V6_M_CANDIDATE_SHA256 = (
    "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
)
EXPECTED_V6_D_CANDIDATE_SHA256 = (
    "df55613f1fbd691f42319976d4722e614b25a8c985cdae5df9797f2e49660160"
)
EXPECTED_PREDECESSOR_CANDIDATE_SHA256 = (
    "9baadb7bea90ac503ec3f68cd05fa01d967376fedff59aaedcbf2d009c46fb95"
)
EXPECTED_CANDIDATE_SHA256 = (
    "a8262434ad7b25a36167fe4694921bbb978d4044f62de60990d135bcd403233a"
)
EXPECTED_Q81_SELECTED_HISTORY_PREFIX_SHA256 = (
    "f2742a2159b582d6c7a7c3d146f6feeba4565a08750b77d5f321d07776287923"
)

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
    "max_candidate_K": K540672,
    "max_output_terms_if_successful": K540672,
}
POLICY_CAPS_BASE = {
    **EXPECTED_PREDECESSOR_POLICY_CAPS,
    "max_candidate_K": K557056,
    "max_output_terms_if_successful": K557056,
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
    "max_retained_K": K540672,
}
EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS = {
    **EXPECTED_V2_KERNEL_CAPABILITY_LIMITS,
    "max_retained_K": K557056,
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
        key for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    }


def validate_local_configuration() -> None:
    if len(V6_M_CANDIDATES) != 29:
        raise RuntimeError("v6 M candidate count drift")
    if len(PREDECESSOR_M_CANDIDATES) != 30 or len(M_CANDIDATES) != 31:
        raise RuntimeError("M route candidate count drift")
    if M_CANDIDATES != PREDECESSOR_M_CANDIDATES + (K557056,):
        raise RuntimeError("M K557056 route is not an exact append")
    if any(type(value) is not int or value <= 0 for value in M_CANDIDATES):
        raise RuntimeError("M candidate value drift")
    if any(left >= right for left, right in zip(M_CANDIDATES, M_CANDIDATES[1:])):
        raise RuntimeError("M candidate order drift")
    if sha256(canonical_bytes(list(PREDECESSOR_M_CANDIDATES))) != (
        EXPECTED_PREDECESSOR_CANDIDATE_SHA256
    ):
        raise RuntimeError("M predecessor candidate digest drift")
    if sha256(canonical_bytes(list(M_CANDIDATES))) != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("M candidate digest drift")
    expected = {"max_candidate_K", "max_output_terms_if_successful"}
    if changed_mapping_keys(EXPECTED_V6_POLICY_CAPS, POLICY_CAPS_BASE) != expected:
        raise RuntimeError("direct v6 policy override changed a non-K field")
    if changed_mapping_keys(EXPECTED_PREDECESSOR_POLICY_CAPS, POLICY_CAPS_BASE) != expected:
        raise RuntimeError("route policy override changed a non-K field")
    if POLICY_CAPS_BASE["max_candidate_K"] != M_CANDIDATES[-1]:
        raise RuntimeError("policy maximum and M ladder maximum disagree")
    if BASE_PARENT_HORIZON != 80 or EXTENDED_HORIZON != 82:
        raise RuntimeError("M q82 horizon contract drift")


def load_control_flow_parent(repo: Path) -> Any:
    parent, _payload = load_pinned_module(
        repo,
        CONTROL_FLOW_PARENT_NAME,
        EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "pinned_four_gate_control_flow_parent_for_m_k557056_c31_q82",
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
    horizons = {
        mode: config["horizon_checkpoint_count"]
        for mode, config in parent.MODE_CONFIG.items()
    }
    if horizons != {MODE: BASE_PARENT_HORIZON, "double_occupancy": 66}:
        raise RuntimeError("control-flow parent baseline horizon drift")
    return parent


def load_configured_v6_baseline(repo: Path) -> Tuple[Any, Tuple[int, ...]]:
    configuration, _payload = load_pinned_module(
        repo,
        V6_BASELINE_CONFIGURATION_NAME,
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "pinned_v6_baseline_configuration_for_m_k557056_c31_q82",
    )
    if configuration.POLICY_CAPS_BASE != EXPECTED_V6_POLICY_CAPS:
        raise RuntimeError("v6 baseline policy caps drift")
    if sha256(canonical_bytes(configuration.POLICY_CAPS_BASE)) != (
        EXPECTED_V6_POLICY_CAPS_SHA256
    ):
        raise RuntimeError("v6 baseline policy digest drift")
    baseline_m = tuple(configuration.MODE_CONFIG[MODE]["candidates"])
    baseline_d = tuple(configuration.MODE_CONFIG["double_occupancy"]["candidates"])
    if sha256(canonical_bytes(list(baseline_m))) != EXPECTED_V6_M_CANDIDATE_SHA256:
        raise RuntimeError("v6 baseline M candidate digest drift")
    if sha256(canonical_bytes(list(baseline_d))) != EXPECTED_V6_D_CANDIDATE_SHA256:
        raise RuntimeError("v6 baseline D candidate digest drift")
    if baseline_m != V6_M_CANDIDATES:
        raise RuntimeError("M direct construction from v6 drift")
    before_d = copy.deepcopy(configuration.MODE_CONFIG["double_occupancy"])
    runtime_config = copy.deepcopy(configuration.MODE_CONFIG)
    runtime_config[MODE]["candidates"] = tuple(M_CANDIDATES)
    configuration.MODE_CONFIG = runtime_config
    configuration.POLICY_CAPS_BASE = dict(POLICY_CAPS_BASE)
    if configuration.MODE_CONFIG["double_occupancy"] != before_d:
        raise RuntimeError("configured v6 changed double occupancy")
    return configuration, baseline_m


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
    wrapper = types.ModuleType("pinned_k557056_arithmetic_capability_wrapper")
    wrapper.__file__ = str(wrapper_path)
    wrapper.__package__ = ""
    wrapper.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = wrapper_payload
    wrapper.__dict__["_VERIFIED_BASE_KERNEL_SOURCE_BYTES"] = v2_payload
    exec(compile(wrapper_payload, wrapper.__file__, "exec"), wrapper.__dict__)
    expected_constants = {
        "BASE_KERNEL_NAME": V2_ARITHMETIC_NAME,
        "EXPECTED_BASE_KERNEL_SHA256": EXPECTED_V2_ARITHMETIC_SHA256,
        "EXPECTED_ROUTE_PREDECESSOR_SHA256": EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256,
        "EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256": (
            EXPECTED_ROUTE_PREDECESSOR_KERNEL_MANIFEST_SHA256
        ),
        "EXPECTED_BASE_RESOURCE_LIMITS": EXPECTED_V2_KERNEL_CAPABILITY_LIMITS,
        "EXPECTED_ROUTE_PREDECESSOR_RESOURCE_LIMITS": (
            EXPECTED_PREDECESSOR_KERNEL_CAPABILITY_LIMITS
        ),
        "EXTENDED_RESOURCE_LIMITS": EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
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
    if [item.get("relative_path") for item in manifest.get("source_layers", ())] != [
        KERNEL_WRAPPER_NAME,
        V2_ARITHMETIC_NAME,
    ]:
        raise RuntimeError("kernel execution source-layer drift")
    route = manifest.get("route_predecessor_reference")
    if type(route) is not dict:
        raise RuntimeError("kernel route predecessor reference drift")
    if route.get("source_sha256") != EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256:
        raise RuntimeError("kernel route predecessor source pin drift")
    if route.get("capability_manifest_sha256") != (
        EXPECTED_ROUTE_PREDECESSOR_KERNEL_MANIFEST_SHA256
    ):
        raise RuntimeError("kernel route predecessor manifest pin drift")
    if any(route.get(key) is not False for key in (
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
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k540672_q82_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "screen_horizon_checkpoint_count": EXTENDED_HORIZON,
        "attempted_checkpoint_count": 81,
        "completed_checkpoint_count": 80,
        "failure_checkpoint_included": True,
        "candidate_K_values": list(PREDECESSOR_M_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **EXPECTED_PREDECESSOR_POLICY_CAPS,
            "max_candidate_count": 30,
        },
        "kernel_capability_limits": EXPECTED_PREDECESSOR_KERNEL_CAPABILITY_LIMITS,
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
    if type(records) is not list or len(records) != 81:
        raise RuntimeError("route predecessor record count drift")
    if type(history) is not list or len(history) != 80:
        raise RuntimeError("route predecessor history count drift")
    if sha256(canonical_bytes(records)) != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256:
        raise RuntimeError("route predecessor records digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256:
        raise RuntimeError("route predecessor history digest drift")
    if sha256(canonical_bytes(records[-1])) != EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256:
        raise RuntimeError("route predecessor failure digest drift")
    failure = records[-1]
    expected_q81 = {
        "checkpoint_number_one_based": 81,
        "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "pretruncation_expansion_count": 597_254,
        "minimum_effective_K_to_meet_prefix": 545_129,
        "required_K_excess_over_policy_maximum": 4_457,
        "selected_K": None,
        "selected_candidate_index": None,
    }
    for key, value in expected_q81.items():
        if failure.get(key) != value:
            raise RuntimeError(f"route predecessor q81 drift: {key}")
    reference = {
        "route_id": "magnetization_k540672_q82_to_k557056_c31_q82_v1",
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
            "checkpoint_80_state_loaded": False,
            "checkpoint_81_state_loaded": False,
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
    baseline = copy.deepcopy(parent.MODE_CONFIG)
    if baseline[MODE]["horizon_checkpoint_count"] != BASE_PARENT_HORIZON:
        raise RuntimeError("parent M horizon baseline drift")
    effective = copy.deepcopy(baseline)
    effective[MODE]["horizon_checkpoint_count"] = EXTENDED_HORIZON
    changed = []
    for mode, before_mode in baseline.items():
        for key, before_value in before_mode.items():
            if effective[mode].get(key) != before_value:
                changed.append(f"MODE_CONFIG.{mode}.{key}")
    expected_changed = [f"MODE_CONFIG.{MODE}.horizon_checkpoint_count"]
    if changed != expected_changed:
        raise RuntimeError("parent configuration changed outside M horizon")
    if effective["double_occupancy"] != baseline["double_occupancy"]:
        raise RuntimeError("parent double-occupancy configuration changed")
    parent.MODE_CONFIG = effective
    original_load_execution_sources = parent.load_execution_sources
    parent.load_v6_configuration = lambda _repo: configuration

    def load_wrapped_execution_sources(
        source_repo: Path,
        helper: Any,
        mode: str,
    ) -> Tuple[Any, Any, Dict[str, Any], Dict[str, str]]:
        base_kernel, root, modules, custody = original_load_execution_sources(
            source_repo, helper, mode
        )
        if base_kernel.RESOURCE_LIMITS != EXPECTED_V2_KERNEL_CAPABILITY_LIMITS:
            raise RuntimeError("v2 arithmetic capability limits drift")
        if kernel_wrapper.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS:
            raise RuntimeError("wrapped kernel capability limits drift")
        return kernel_wrapper, root, modules, custody

    parent.load_execution_sources = load_wrapped_execution_sources
    return {
        "override_id": "magnetization_parent_q82_horizon_override_v1",
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
        "parent_mode_config_before": baseline,
        "parent_mode_config_before_sha256": sha256(canonical_bytes(baseline)),
        "parent_mode_config_after": effective,
        "parent_mode_config_after_sha256": sha256(canonical_bytes(effective)),
        "double_occupancy_configuration_unchanged": True,
    }


def validate_replay_handoff(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:
    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or len(records) != EXTENDED_HORIZON:
        raise RuntimeError("M q82 result did not attempt exactly through q82")
    if type(history) is not list or len(history) not in (81, 82):
        raise RuntimeError("M q82 selected history length drift")
    old_records = predecessor["records"]
    old_history = predecessor["selected_K_history"]
    if history[:80] != old_history:
        raise RuntimeError("M q82 changed the exact q1-80 selected history")
    for index in range(80):
        old = old_records[index]
        new = records[index]
        old_common = {key: value for key, value in old.items() if key != "candidate_records"}
        new_common = {key: value for key, value in new.items() if key != "candidate_records"}
        if new_common != old_common:
            raise RuntimeError(f"M q82 changed q{index + 1} common record state")
        old_rows = old["candidate_records"]
        new_rows = new.get("candidate_records")
        if type(new_rows) is not list or len(new_rows) != 31:
            raise RuntimeError(f"M q82 candidate row count drift at q{index + 1}")
        if new_rows[:30] != old_rows:
            raise RuntimeError(f"M q82 changed q{index + 1} predecessor candidate rows")
        appended = new_rows[30]
        if appended.get("candidate_index") != 30 or appended.get("configured_K") != K557056:
            raise RuntimeError(f"M q82 appended candidate row drift at q{index + 1}")

    old_q81 = old_records[80]
    new_q81 = records[80]
    excluded = {"candidate_records", "status", "selected_candidate_index", "selected_K"}
    old_shared = {
        key: value for key, value in old_q81.items()
        if key in new_q81 and key not in excluded
    }
    new_shared = {
        key: value for key, value in new_q81.items()
        if key in old_q81 and key not in excluded
    }
    if new_shared != old_shared:
        raise RuntimeError("M q82 changed the exact q81 shared propagation fields")
    old_rows = old_q81["candidate_records"]
    new_rows = new_q81.get("candidate_records")
    if type(new_rows) is not list or len(new_rows) != 31 or new_rows[:30] != old_rows:
        raise RuntimeError("M q82 changed the q81 predecessor candidate rows")
    if any(row.get("feasible_under_current_prefix_cap") is not False for row in old_rows):
        raise RuntimeError("M predecessor q81 unexpectedly had a feasible candidate")
    appended = new_rows[30]
    expected_appended = {
        "candidate_index": 30,
        "configured_K": K557056,
        "effective_retained_count": K557056,
        "dropped_term_count": 40_198,
        "feasible_under_current_prefix_cap": True,
    }
    for key, value in expected_appended.items():
        if appended.get(key) != value:
            raise RuntimeError(f"M q81 appended candidate drift: {key}")
    if int(appended["E_after_if_selected_ticks"]) != (
        int(new_q81["E_before_ticks"]) + int(appended["drop_ticks"])
    ):
        raise RuntimeError("M q81 appended candidate E recurrence drift")
    expected_q81 = {
        "checkpoint_number_one_based": 81,
        "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        "selected_candidate_index": 30,
        "selected_K": K557056,
        "selected_effective_retained_count": K557056,
        "selected_dropped_term_count": 40_198,
        "retained_expansion_count": K557056,
    }
    for key, value in expected_q81.items():
        if new_q81.get(key) != value:
            raise RuntimeError(f"M q81 handoff drift: {key}")
    if new_q81.get("selected_drop_ticks") != appended.get("drop_ticks"):
        raise RuntimeError("M q81 selected drop and candidate row disagree")
    if int(new_q81["E_after_ticks"]) != int(appended["E_after_if_selected_ticks"]):
        raise RuntimeError("M q81 committed E and candidate row disagree")
    if int(new_q81["E_after_ticks"]) > int(new_q81["budget_prefix_cap_ticks"]):
        raise RuntimeError("M q81 selected candidate violates the prefix cap")
    if history[80] != K557056:
        raise RuntimeError("M q81 selected history handoff drift")
    if sha256(canonical_bytes(history[:81])) != EXPECTED_Q81_SELECTED_HISTORY_PREFIX_SHA256:
        raise RuntimeError("M q81 selected history prefix digest drift")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("M q82 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(canonical_bytes(history)):
        raise RuntimeError("M q82 selected history digest drift")
    if result.get("attempted_checkpoint_count") != 82:
        raise RuntimeError("M q82 attempted checkpoint count drift")
    if result.get("completed_checkpoint_count") != len(history):
        raise RuntimeError("M q82 completed checkpoint count drift")
    q82 = records[81]
    if q82.get("checkpoint_number_one_based") != 82:
        raise RuntimeError("M q82 terminal checkpoint number drift")
    failed = q82.get("status") == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
    if failed:
        if len(history) != 81:
            raise RuntimeError("M q82 failure/history count drift")
        if result.get("screen_terminal_condition") != "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE":
            raise RuntimeError("M q82 failure terminal label drift")
    else:
        if q82.get("status") != "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
            raise RuntimeError("M q82 unknown terminal status")
        if len(history) != 82:
            raise RuntimeError("M q82 success/history count drift")
        if result.get("screen_terminal_condition") != "DIAGNOSTIC_HORIZON_REACHED":
            raise RuntimeError("M q82 horizon terminal label drift")
    return {
        "validation_id": "M_k557056_c31_q82_predecessor_handoff_v1",
        "q1_through_q80_common_records_exact": True,
        "q1_through_q80_first_30_candidate_rows_exact": True,
        "q1_through_q80_selected_history_exact": True,
        "q81_shared_propagation_fields_exact": True,
        "q81_first_30_candidate_rows_exact": True,
        "q81_selected_candidate_index": 30,
        "q81_selected_K": K557056,
        "q81_selected_history_prefix_sha256": EXPECTED_Q81_SELECTED_HISTORY_PREFIX_SHA256,
        "q82_outcome_precommitted": False,
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
        "role": "M_k557056_c31_q82_fresh_same_byte_screen",
        "sha256": self_sha,
    }]
    saw_parent = saw_v6 = saw_v2 = False
    forbidden_route_layers = {
        ROUTE_PREDECESSOR_SCREEN_NAME,
        "hubbard_l8_adaptive_k_arithmetic_k540672.py",
    }
    for original in parent_components:
        if type(original) is not dict:
            raise RuntimeError("control-flow parent component is not a dict")
        item = dict(original)
        relative_path = item.get("relative_path")
        if relative_path in forbidden_route_layers:
            raise RuntimeError("route predecessor became an execution component")
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
                "role": "k557056_capability_override_provider",
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
        "baseline_M_candidate_K_values_sha256": EXPECTED_V6_M_CANDIDATE_SHA256,
        "baseline_D_candidate_K_values_sha256": EXPECTED_V6_D_CANDIDATE_SHA256,
        "baseline_policy_caps_sha256": EXPECTED_V6_POLICY_CAPS_SHA256,
        "compiled_from_verified_bytes": True,
        "module_isolated": True,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }


def configuration_override(baseline_m: Tuple[int, ...]) -> Dict[str, Any]:
    if M_CANDIDATES != baseline_m + (K540672, K557056):
        raise RuntimeError("configuration override baseline M ladder drift")
    return {
        "override_id": "magnetization_k557056_c31_q82_configuration_override_v1",
        "diagnostic_ladder_precommitted_before_replay": True,
        "direct_execution_override_from_v6": {
            "baseline_candidate_K_values_sha256": EXPECTED_V6_M_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 29, "after": 31},
            "candidate_ladder_added": [K540672, K557056],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {
                "max_candidate_K": {"before": 524_288, "after": K557056},
                "max_output_terms_if_successful": {"before": 524_288, "after": K557056},
            },
        },
        "incremental_route_override_from_k540672_q82": {
            "predecessor_candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 30, "after": 31},
            "candidate_ladder_added": [K557056],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {
                "max_candidate_K": {"before": K540672, "after": K557056},
                "max_output_terms_if_successful": {"before": K540672, "after": K557056},
            },
            "predecessor_configuration_override_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
            ),
        },
        "derived_policy_cap": {
            "field": "max_candidate_count",
            "derivation": "len(candidate_K_values)",
            "before_on_route": 30,
            "after": 31,
        },
        "unchanged_policy_caps": {
            key: value for key, value in EXPECTED_V6_POLICY_CAPS.items()
            if key not in {"max_candidate_K", "max_output_terms_if_successful"}
        },
        "double_occupancy_candidate_configuration_unchanged": True,
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
        "role": "separate_k557056_capability_override_provider",
        "base_arithmetic_relative_path": V2_ARITHMETIC_NAME,
        "base_arithmetic_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "module_itself_is_extended_kernel": True,
        "verified_compilation_inputs": [
            "_VERIFIED_SELF_SOURCE_BYTES",
            "_VERIFIED_BASE_KERNEL_SOURCE_BYTES",
        ],
        "capability_manifest": dict(manifest),
        "capability_manifest_sha256": sha256(canonical_bytes(manifest)),
        "direct_capability_changes_from_v2": {
            "max_retained_K": {"before": 524_288, "after": K557056},
        },
        "incremental_route_changes_from_k540672": {
            "max_retained_K": {"before": K540672, "after": K557056},
        },
        "execution_source_layers": [KERNEL_WRAPPER_NAME, V2_ARITHMETIC_NAME],
        "route_predecessor_is_execution_source": False,
        "v2_arithmetic_module_mutated_by_screen": False,
    }


def validate_and_relabel(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
    predecessor_reference: Mapping[str, Any],
    baseline_m: Tuple[int, ...],
    kernel_wrapper_sha: str,
    kernel_manifest: Mapping[str, Any],
    horizon_override: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("M q82 relabel requires fresh same-byte self execution")
    if type(result) is not dict:
        raise RuntimeError("control-flow parent result is not an exact dict")
    expected_parent_fields = {
        "schema_version": 1,
        "transcript_fingerprint": "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1",
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
        "candidate_K_values": list(M_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **POLICY_CAPS_BASE,
            "max_candidate_count": len(M_CANDIDATES),
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
    if result.get("configuration_reference_sha256") != sha256(canonical_bytes(old_configuration)):
        raise RuntimeError("control-flow parent configuration digest drift")
    old_transform = result.get("checkpoint_transform")
    old_transform_sha = result.get("checkpoint_transform_sha256")
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("control-flow parent transform digest drift")

    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = execution_components(old_components, self_sha, kernel_wrapper_sha)
    baseline_reference = configuration_reference()
    config_override = configuration_override(baseline_m)
    capability = kernel_capability_override(kernel_wrapper_sha, kernel_manifest)
    route_reference = dict(predecessor_reference)
    transform = {
        "transform_id": "magnetization_four_gate_k557056_c31_q82_v1",
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": old_transform_sha,
        "route_predecessor_transform_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "overridden_semantics": [
            "candidate_K_values",
            "policy_max_candidate_K",
            "policy_max_output_terms_if_successful",
            "derived_policy_max_candidate_count",
            "kernel_max_retained_K",
            "magnetization_horizon_checkpoint_count",
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
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k557056_c31_q82_screen_v1"
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
        raise RuntimeError("M q82 screen requires fresh same-byte self execution")
    validate_local_configuration()
    repo = repo.resolve()
    parent = load_control_flow_parent(repo)
    configuration, baseline_m = load_configured_v6_baseline(repo)
    kernel_wrapper, kernel_wrapper_sha, kernel_manifest = load_kernel_wrapper(repo)
    predecessor, predecessor_reference = load_route_predecessor_reference(repo)
    horizon_override = configure_parent_execution(parent, configuration, kernel_wrapper)
    result = parent._run_verified(repo, MODE)
    return validate_and_relabel(
        result,
        predecessor,
        predecessor_reference,
        baseline_m,
        kernel_wrapper_sha,
        kernel_manifest,
        horizon_override,
    )


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_magnetization_k557056_c31_q82_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("M q82 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("M q82 transcript exceeds output byte cap")
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
    final = result["records"][-1]
    print(json.dumps({
        "output": output.name,
        "semantic_and_file_sha256": sha256(raw),
        "records_sha256": result["records_sha256"],
        "screen_terminal_condition": result["screen_terminal_condition"],
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "attempted_checkpoint_count": result["attempted_checkpoint_count"],
        "final_status": final["status"],
        "final_checkpoint": final["checkpoint_number_one_based"],
        "last_committed_cumulative_drop_ticks": result[
            "last_committed_cumulative_drop_ticks"
        ],
        "peak": result["observed_peak_single_expansion_terms"],
        "visits": result["observed_term_gate_visits_including_terminal_attempt"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
