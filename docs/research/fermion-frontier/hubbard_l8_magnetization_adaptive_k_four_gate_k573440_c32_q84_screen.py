#!/usr/bin/env python3
"""Source-pinned, diagnostic-only M K=573440/C=32 q84 screen.

Execution always starts at checkpoint one through a fresh same-byte copy of the
exact four-gate control-flow parent.  The K557056/C31 q84 route and its q82
ancestry are exact post-replay references; neither is compiled, executed, or
used for state resume.
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
    "k573440_c32_q84_screen.py"
)
CONTROL_FLOW_PARENT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k573440.py"
ROUTE_PREDECESSOR_SCREEN_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_k557056_c31_q84_screen.py"
)
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_k557056_c31_q84_transcript.json"
)
ROUTE_Q82_SCREEN_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_k557056_c31_q82_screen.py"
)
ROUTE_Q82_TRANSCRIPT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_k557056_c31_q82_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k573440_c32_q84_transcript.json"
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
    "c644dfeaf2a0b27be40403715aec8711818ae11ff575b230339af745f0a56ff1"
)
EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256 = (
    "fb6d6c241ab7ee2f535aa2f1cdff38a5e8f47bab1035ba29249332ca2d4f3f39"
)
EXPECTED_KERNEL_SOURCE_LAYERS_SHA256 = (
    "453d5915fa25b74024a89b3eeea7b86e3a202ca2a451116d73da05568d2d7d19"
)
EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256 = (
    "bea2cc57552b3ac5b70d889917fdaca0fa67485dedacb7e2ac38cf37f942785f"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256 = (
    "4c54b9a2451ad9ae76e4b4036705558cdc527f22b015fd67c035118ad2c8506f"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_MANIFEST_SHA256 = (
    "cc60b39010c55fa3a95f7160e5ccb0a4985ab6926aa8076841d75e660a954868"
)
EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256 = (
    "d778440f6a86adf7d4498d2c3496c0f650c7782379c9f5b25c1e979ad01a136f"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "2f866d658570c9cf667088662a98288c14b41144c3ffacdefd862aaf8f185138"
)
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "ec428e76d1c6e71f46a90caf0a040260174469c198a974d4c8e0f8e939441d40"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "8c6902944bc0fc1c1c533a4e3e7ca6f65c17f43fef3c6a94f633616b38123e40"
)
EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256 = (
    "6e715a8d7e1acc489c2e3424a2cafb424e30ab8dfbba19a49d5cc6a1e4089b4c"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256 = (
    "ec25a4c736f761a4b27c667b87c2c50c86ab890817c9a5f6839ffe27d8d65c58"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "d64a165cbf0cd13f269cb1d15c45bc634dafa4d990705ea95928890136afb103"
)
EXPECTED_ROUTE_Q82_SCREEN_SHA256 = (
    "ba1c221b57fa59655612ad7209b38c83337f6f21b794132f7a9e1600b8d60fed"
)
EXPECTED_ROUTE_Q82_TRANSCRIPT_SHA256 = (
    "1d6cbcddac8a8c596746f24b8c8498f24874e86db5235532d7d269220043cdd4"
)
EXPECTED_ROUTE_Q82_RECORDS_SHA256 = (
    "cb017a1202e89d5db762296b9b61ad78de132b2a0a589f8d3b21f096609a9aa9"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_PREDECESSOR_TRANSCRIPT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

MODE = "magnetization"
BASE_PARENT_HORIZON = 80
EXTENDED_HORIZON = 84
K540672 = 540_672
K557056 = 557_056
K573440 = 573_440

V6_M_CANDIDATES = tuple(range(65_536, 524_288 + 1, 16_384))
PREDECESSOR_M_CANDIDATES = V6_M_CANDIDATES + (K540672, K557056)
M_CANDIDATES = PREDECESSOR_M_CANDIDATES + (K573440,)
EXPECTED_V6_M_CANDIDATE_SHA256 = (
    "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
)
EXPECTED_V6_D_CANDIDATE_SHA256 = (
    "df55613f1fbd691f42319976d4722e614b25a8c985cdae5df9797f2e49660160"
)
EXPECTED_PREDECESSOR_CANDIDATE_SHA256 = (
    "a8262434ad7b25a36167fe4694921bbb978d4044f62de60990d135bcd403233a"
)
EXPECTED_CANDIDATE_SHA256 = (
    "b46d0b11cbb16260d7d3b76b4a42d0013c74dae767e39a5b11bf50d8fdddb428"
)
EXPECTED_Q83_SELECTED_HISTORY_PREFIX_SHA256 = (
    "cb4e935c2e8bd0458d7164701d79251b9a5d5f3d80f949ff8f8953ce561b6cc6"
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
    "max_candidate_K": K557056,
    "max_output_terms_if_successful": K557056,
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
    "max_retained_K": K557056,
}
EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS = {
    **EXPECTED_V2_KERNEL_CAPABILITY_LIMITS,
    "max_retained_K": K573440,
}
EXPECTED_PARENT_EXECUTION_COMPONENTS = (
    {
        "relative_path": CONTROL_FLOW_PARENT_NAME,
        "role": "four_gate_screen_execution_source",
        "sha256": EXPECTED_CONTROL_FLOW_PARENT_SHA256,
    },
    {
        "relative_path": "hubbard_l8_adaptive_k_v2_design_probe.py",
        "role": "v2_helper_provider_not_run_entrypoint",
        "sha256": "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3",
    },
    {
        "relative_path": V6_BASELINE_CONFIGURATION_NAME,
        "role": "v6_candidates_and_caps_reference_only",
        "sha256": EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
    },
    {
        "relative_path": V2_ARITHMETIC_NAME,
        "role": "v2_arithmetic_kernel",
        "sha256": EXPECTED_V2_ARITHMETIC_SHA256,
    },
    {
        "relative_path": "hubbard_l8_observable_interval_step_checker.py",
        "role": "root_sequence_and_trigonometry_source",
        "sha256": "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a",
    },
    {
        "relative_path": "hubbard_l8_magnetization_interval_step3_checker.py",
        "role": "magnetization_boundary_parent_source",
        "sha256": "4e471b6f22838b2e9621adeeb757e7fa8277e3d8c4985eee392b182530c0c717",
    },
    {
        "relative_path": "hubbard_l8_magnetization_interval_step3_contract.json",
        "role": "magnetization_boundary_parent_source",
        "sha256": "fb1d5e82819d39f217a8c1c7f4979a689f4d46b8d691a8f464cad9012c197387",
    },
    {
        "relative_path": "hubbard_l8_magnetization_interval_step3_template.json",
        "role": "magnetization_boundary_parent_source",
        "sha256": "b68544091be417eed5310d8579eb8dc4d1a51e1863ed1fb7a8cbfa1fc6004eb6",
    },
    {
        "relative_path": "hubbard_l8_interval_checkpoints/staggered_magnetization_boundary_003.b85",
        "role": "magnetization_encoded_input_boundary",
        "sha256": "91aecef5a3b79279e394c8995072d19565f4898e0ba29ddd7685ea9e535d9c84",
    },
)


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
    if len(PREDECESSOR_M_CANDIDATES) != 31 or len(M_CANDIDATES) != 32:
        raise RuntimeError("M route candidate count drift")
    if M_CANDIDATES != PREDECESSOR_M_CANDIDATES + (K573440,):
        raise RuntimeError("M K573440 route is not an exact append")
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
    if BASE_PARENT_HORIZON != 80 or EXTENDED_HORIZON != 84:
        raise RuntimeError("M q84 horizon contract drift")


def load_control_flow_parent(repo: Path) -> Any:
    parent, _payload = load_pinned_module(
        repo,
        CONTROL_FLOW_PARENT_NAME,
        EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "pinned_four_gate_control_flow_parent_for_m_k573440_c32_q84",
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
        "pinned_v6_baseline_configuration_for_m_k573440_c32_q84",
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
    wrapper = types.ModuleType("pinned_k573440_arithmetic_capability_wrapper")
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
    if sha256(canonical_bytes(manifest["source_layers"])) != EXPECTED_KERNEL_SOURCE_LAYERS_SHA256:
        raise RuntimeError("kernel execution source-layer digest drift")
    route = manifest.get("route_predecessor_reference")
    if type(route) is not dict:
        raise RuntimeError("kernel route predecessor reference drift")
    if sha256(canonical_bytes(route)) != EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256:
        raise RuntimeError("kernel route predecessor reference digest drift")
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
    q82_screen_payload = bounded_bytes(
        checked_repo_file(repo, ROUTE_Q82_SCREEN_NAME), MAX_PINNED_SOURCE_BYTES
    )
    if sha256(q82_screen_payload) != EXPECTED_ROUTE_Q82_SCREEN_SHA256:
        raise RuntimeError("route q82 ancestry screen source pin drift")
    q82_raw = bounded_bytes(
        checked_repo_file(repo, ROUTE_Q82_TRANSCRIPT_NAME),
        MAX_PREDECESSOR_TRANSCRIPT_BYTES,
    )
    if sha256(q82_raw) != EXPECTED_ROUTE_Q82_TRANSCRIPT_SHA256:
        raise RuntimeError("route q82 ancestry transcript pin drift")
    try:
        q82_transcript = json.loads(q82_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("route q82 ancestry transcript is invalid JSON") from exc
    if (
        type(q82_transcript) is not dict
        or q82_raw != canonical_bytes(q82_transcript)
        or q82_transcript.get("records_sha256") != EXPECTED_ROUTE_Q82_RECORDS_SHA256
        or sha256(canonical_bytes(q82_transcript.get("records")))
        != EXPECTED_ROUTE_Q82_RECORDS_SHA256
        or q82_transcript.get("selected_K_history_sha256")
        != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256
    ):
        raise RuntimeError("route q82 ancestry transcript semantic drift")
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
            "k557056_c31_q84_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "screen_horizon_checkpoint_count": EXTENDED_HORIZON,
        "attempted_checkpoint_count": 83,
        "completed_checkpoint_count": 82,
        "failure_checkpoint_included": True,
        "candidate_K_values": list(PREDECESSOR_M_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **EXPECTED_PREDECESSOR_POLICY_CAPS,
            "max_candidate_count": 31,
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
    if type(records) is not list or len(records) != 83:
        raise RuntimeError("route predecessor record count drift")
    if type(history) is not list or len(history) != 82:
        raise RuntimeError("route predecessor history count drift")
    if sha256(canonical_bytes(records)) != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256:
        raise RuntimeError("route predecessor records digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256:
        raise RuntimeError("route predecessor history digest drift")
    if sha256(canonical_bytes(records[-1])) != EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256:
        raise RuntimeError("route predecessor failure digest drift")
    failure = records[-1]
    expected_q83 = {
        "checkpoint_number_one_based": 83,
        "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "pretruncation_expansion_count": 652_016,
        "minimum_effective_K_to_meet_prefix": 565_994,
        "required_K_excess_over_policy_maximum": 8_938,
        "selected_K": None,
        "selected_candidate_index": None,
    }
    for key, value in expected_q83.items():
        if failure.get(key) != value:
            raise RuntimeError(f"route predecessor q83 drift: {key}")
    ancestry = transcript.get("base_canonical_reference_artifact")
    if type(ancestry) is not dict:
        raise RuntimeError("route q82 ancestry reference missing")
    expected_ancestry = {
        "relative_path": ROUTE_Q82_TRANSCRIPT_NAME,
        "file_sha256": EXPECTED_ROUTE_Q82_TRANSCRIPT_SHA256,
        "records_sha256": EXPECTED_ROUTE_Q82_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        "loaded_before_replay_as_exact_reference": True,
        "used_only_after_replay_for_result_prefix_validation": True,
        "post_replay_prefix_validation_input": True,
        "checkpoint_82_state_loaded": False,
        "propagation_input": False,
        "state_resume_input": False,
        "execution_source_layer": False,
    }
    for key, value in expected_ancestry.items():
        if ancestry.get(key) != value:
            raise RuntimeError(f"route q82 ancestry drift: {key}")
    reference = {
        "route_id": "magnetization_k557056_c31_q84_to_k573440_c32_q84_v1",
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
            "checkpoint_82_state_loaded": False,
            "checkpoint_83_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
        },
        "q82_ancestry": {
            "screen_relative_path": ROUTE_Q82_SCREEN_NAME,
            "screen_source_sha256": EXPECTED_ROUTE_Q82_SCREEN_SHA256,
            "transcript_relative_path": ROUTE_Q82_TRANSCRIPT_NAME,
            "transcript_file_sha256": EXPECTED_ROUTE_Q82_TRANSCRIPT_SHA256,
            "records_sha256": EXPECTED_ROUTE_Q82_RECORDS_SHA256,
            "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
            "compiled": False,
            "executed": False,
            "propagation_input": False,
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
        "override_id": "magnetization_parent_q84_horizon_override_v1",
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


def is_canonical_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_q84_terminal_ledger(
    result: Mapping[str, Any],
    q83: Mapping[str, Any],
    q84: Mapping[str, Any],
    history: list[Any],
) -> bool:
    if type(q84) is not dict:
        raise RuntimeError("M q84 terminal record is not an exact dict")
    if q84.get("checkpoint_index_zero_based") != 83:
        raise RuntimeError("M q84 terminal checkpoint index drift")
    if q84.get("checkpoint_number_one_based") != 84:
        raise RuntimeError("M q84 terminal checkpoint drift")
    for q84_key, q83_key in (
        ("input_expansion_count", "retained_expansion_count"),
        ("input_expansion_sha256", "retained_expansion_sha256"),
        ("E_before_ticks", "E_after_ticks"),
    ):
        if q84_key not in q84 or q83_key not in q83:
            raise RuntimeError(f"M q84 input continuity field missing: {q84_key}")
        if q84.get(q84_key) != q83.get(q83_key):
            raise RuntimeError(f"M q84 input continuity drift: {q84_key}")
    if not is_canonical_sha256(q84.get("input_expansion_sha256")):
        raise RuntimeError("M q84 input expansion digest drift")
    pre_count = q84.get("pretruncation_expansion_count")
    if type(pre_count) is not int or type(q84.get("input_expansion_count")) is not int:
        raise RuntimeError("M q84 expansion count type drift")
    try:
        E_before = int(q84["E_before_ticks"])
        prefix_cap = int(q84["budget_prefix_cap_ticks"])
        slack = int(q84["prefix_slack_before_selection_ticks"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("M q84 fixed-tick ledger field drift") from exc
    if slack != prefix_cap - E_before:
        raise RuntimeError("M q84 prefix slack recurrence drift")
    rows = q84.get("candidate_records")
    if type(rows) is not list or len(rows) != len(M_CANDIDATES):
        raise RuntimeError("M q84 candidate row count drift")
    feasible_indices = []
    for candidate_index, (configured_K, row) in enumerate(zip(M_CANDIDATES, rows)):
        if type(row) is not dict:
            raise RuntimeError("M q84 candidate row is not an exact dict")
        effective = min(configured_K, pre_count)
        expected = {
            "candidate_index": candidate_index,
            "configured_K": configured_K,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
        }
        for key, value in expected.items():
            if row.get(key) != value:
                raise RuntimeError(f"M q84 candidate row drift: {key}")
        try:
            drop = int(row["drop_ticks"])
            E_after = int(row["E_after_if_selected_ticks"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("M q84 candidate fixed-tick field drift") from exc
        if E_after != E_before + drop:
            raise RuntimeError("M q84 candidate E recurrence drift")
        feasible = E_after <= prefix_cap
        if row.get("feasible_under_current_prefix_cap") is not feasible:
            raise RuntimeError("M q84 candidate feasibility label drift")
        if feasible:
            feasible_indices.append(candidate_index)
    if result.get("horizon_checkpoint_attempted") is not True:
        raise RuntimeError("M q84 horizon-attempt flag drift")
    failed = q84.get("status") == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
    failure_only = {
        "minimum_effective_K_to_meet_prefix",
        "required_K_excess_over_policy_maximum",
        "maximum_candidate_drop_excess_over_slack_ticks",
    }
    success_only = {
        "selected_effective_retained_count",
        "selected_dropped_term_count",
        "selected_drop_ticks",
        "selected_dropped_terms_sha256",
        "retained_expansion_count",
        "retained_expansion_sha256",
        "minimum_retained_abs_upper_ticks",
        "maximum_dropped_abs_upper_ticks",
        "E_after_ticks",
    }
    if failed:
        if feasible_indices:
            raise RuntimeError("M q84 failure record contains a feasible candidate")
        if q84.get("selected_candidate_index") is not None or q84.get("selected_K") is not None:
            raise RuntimeError("M q84 failure selection label drift")
        if any(key in q84 for key in success_only):
            raise RuntimeError("M q84 failure record contains success-only fields")
        minimum_K = q84.get("minimum_effective_K_to_meet_prefix")
        required_excess = q84.get("required_K_excess_over_policy_maximum")
        if type(minimum_K) is not int or required_excess != max(0, minimum_K - K573440):
            raise RuntimeError("M q84 failure minimum-K ledger drift")
        try:
            maximum_excess = int(q84["maximum_candidate_drop_excess_over_slack_ticks"])
            last_drop = int(rows[-1]["drop_ticks"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("M q84 failure excess ledger drift") from exc
        if maximum_excess != last_drop - slack:
            raise RuntimeError("M q84 failure excess recurrence drift")
        expected_top = {
            "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
            "failure_checkpoint_included": True,
            "horizon_reached_with_committed_checkpoint": False,
            "last_committed_cumulative_drop_ticks": q83["E_after_ticks"],
        }
        for key, value in expected_top.items():
            if result.get(key) != value:
                raise RuntimeError(f"M q84 failure summary drift: {key}")
        if result.get("failure_record_sha256") != sha256(canonical_bytes(q84)):
            raise RuntimeError("M q84 failure record digest drift")
        return True

    if q84.get("status") != "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
        raise RuntimeError("M q84 terminal status drift")
    if any(key in q84 for key in failure_only):
        raise RuntimeError("M q84 success record contains failure-only fields")
    if not feasible_indices:
        raise RuntimeError("M q84 success record has no feasible candidate")
    selected_index = feasible_indices[0]
    selected_row = rows[selected_index]
    selected_K = M_CANDIDATES[selected_index]
    expected_selection = {
        "selected_candidate_index": selected_index,
        "selected_K": selected_K,
        "selected_effective_retained_count": selected_row["effective_retained_count"],
        "selected_dropped_term_count": selected_row["dropped_term_count"],
        "selected_drop_ticks": selected_row["drop_ticks"],
        "retained_expansion_count": selected_row["effective_retained_count"],
        "E_after_ticks": selected_row["E_after_if_selected_ticks"],
    }
    for key, value in expected_selection.items():
        if q84.get(key) != value:
            raise RuntimeError(f"M q84 success selection drift: {key}")
    if history[-1] != selected_K:
        raise RuntimeError("M q84 success history selection drift")
    for key in ("selected_dropped_terms_sha256", "retained_expansion_sha256"):
        if not is_canonical_sha256(q84.get(key)):
            raise RuntimeError(f"M q84 success digest drift: {key}")
    for key in ("minimum_retained_abs_upper_ticks", "maximum_dropped_abs_upper_ticks"):
        try:
            if int(q84[key]) < 0:
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"M q84 success interval field drift: {key}") from exc
    if int(q84["E_after_ticks"]) > prefix_cap:
        raise RuntimeError("M q84 selected candidate violates prefix cap")
    expected_top = {
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "horizon_reached_with_committed_checkpoint": True,
        "last_committed_cumulative_drop_ticks": q84["E_after_ticks"],
    }
    for key, value in expected_top.items():
        if result.get(key) != value:
            raise RuntimeError(f"M q84 success summary drift: {key}")
    return False


def validate_replay_handoff(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:
    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or len(records) != EXTENDED_HORIZON:
        raise RuntimeError("M q84 result did not attempt exactly through q84")
    if type(history) is not list or len(history) not in (83, 84):
        raise RuntimeError("M q84 selected history length drift")
    old_records = predecessor["records"]
    old_history = predecessor["selected_K_history"]
    if history[:82] != old_history:
        raise RuntimeError("M q84 changed the exact q1-82 selected history")
    for index in range(82):
        old = old_records[index]
        new = records[index]
        old_common = {key: value for key, value in old.items() if key != "candidate_records"}
        new_common = {key: value for key, value in new.items() if key != "candidate_records"}
        if new_common != old_common:
            raise RuntimeError(f"M q84 changed q{index + 1} common record state")
        old_rows = old["candidate_records"]
        new_rows = new.get("candidate_records")
        if type(new_rows) is not list or len(new_rows) != 32 or new_rows[:31] != old_rows:
            raise RuntimeError(f"M q84 changed q{index + 1} predecessor candidate rows")
        appended = new_rows[31]
        if appended.get("candidate_index") != 31 or appended.get("configured_K") != K573440:
            raise RuntimeError(f"M q84 appended candidate row drift at q{index + 1}")

    old_q83 = old_records[82]
    new_q83 = records[82]
    failure_only = {
        "minimum_effective_K_to_meet_prefix",
        "required_K_excess_over_policy_maximum",
        "maximum_candidate_drop_excess_over_slack_ticks",
    }
    excluded = {
        "candidate_records", "status", "selected_candidate_index", "selected_K",
        *failure_only,
    }
    q83_success_only = {
        "selected_effective_retained_count",
        "selected_dropped_term_count",
        "selected_drop_ticks",
        "selected_dropped_terms_sha256",
        "retained_expansion_count",
        "retained_expansion_sha256",
        "minimum_retained_abs_upper_ticks",
        "maximum_dropped_abs_upper_ticks",
        "E_after_ticks",
    }
    expected_q83_keys = (set(old_q83) - failure_only) | q83_success_only
    if set(new_q83) != expected_q83_keys:
        raise RuntimeError("M q83 failure-to-success field schema drift")
    old_shared = {key: value for key, value in old_q83.items() if key not in excluded}
    if any(key not in new_q83 for key in old_shared):
        raise RuntimeError("M q84 removed a q83 shared propagation field")
    if {key: new_q83[key] for key in old_shared} != old_shared:
        raise RuntimeError("M q84 changed the exact q83 shared propagation fields")
    if any(key in new_q83 for key in failure_only):
        raise RuntimeError("M q83 retained a predecessor failure-only field")
    old_rows = old_q83["candidate_records"]
    new_rows = new_q83.get("candidate_records")
    if type(new_rows) is not list or len(new_rows) != 32 or new_rows[:31] != old_rows:
        raise RuntimeError("M q84 changed the q83 predecessor candidate rows")
    if any(row.get("feasible_under_current_prefix_cap") is not False for row in old_rows):
        raise RuntimeError("M predecessor q83 unexpectedly had a feasible candidate")
    appended = new_rows[31]
    expected_appended = {
        "candidate_index": 31,
        "configured_K": K573440,
        "effective_retained_count": K573440,
        "dropped_term_count": 78_576,
        "feasible_under_current_prefix_cap": True,
    }
    for key, value in expected_appended.items():
        if appended.get(key) != value:
            raise RuntimeError(f"M q83 appended candidate drift: {key}")
    if int(appended["E_after_if_selected_ticks"]) != int(new_q83["E_before_ticks"]) + int(appended["drop_ticks"]):
        raise RuntimeError("M q83 appended candidate E recurrence drift")
    expected_q83 = {
        "checkpoint_number_one_based": 83,
        "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        "selected_candidate_index": 31,
        "selected_K": K573440,
        "selected_effective_retained_count": K573440,
        "selected_dropped_term_count": 78_576,
        "retained_expansion_count": K573440,
    }
    for key, value in expected_q83.items():
        if new_q83.get(key) != value:
            raise RuntimeError(f"M q83 handoff drift: {key}")
    if new_q83.get("selected_drop_ticks") != appended.get("drop_ticks"):
        raise RuntimeError("M q83 selected drop and candidate row disagree")
    if int(new_q83["E_after_ticks"]) != int(appended["E_after_if_selected_ticks"]):
        raise RuntimeError("M q83 committed E and candidate row disagree")
    if int(new_q83["E_after_ticks"]) > int(new_q83["budget_prefix_cap_ticks"]):
        raise RuntimeError("M q83 selected candidate violates the prefix cap")
    for key in ("selected_dropped_terms_sha256", "retained_expansion_sha256"):
        if not is_canonical_sha256(new_q83.get(key)):
            raise RuntimeError(f"M q83 success digest drift: {key}")
    for key in ("minimum_retained_abs_upper_ticks", "maximum_dropped_abs_upper_ticks"):
        try:
            if int(new_q83[key]) < 0:
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"M q83 success interval field drift: {key}") from exc
    if history[82] != K573440:
        raise RuntimeError("M q83 selected history handoff drift")
    if sha256(canonical_bytes(history[:83])) != EXPECTED_Q83_SELECTED_HISTORY_PREFIX_SHA256:
        raise RuntimeError("M q83 selected history prefix digest drift")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("M q84 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(canonical_bytes(history)):
        raise RuntimeError("M q84 selected history digest drift")
    if result.get("attempted_checkpoint_count") != 84:
        raise RuntimeError("M q84 attempted checkpoint count drift")
    if result.get("completed_checkpoint_count") != len(history):
        raise RuntimeError("M q84 completed checkpoint count drift")
    failed = validate_q84_terminal_ledger(result, new_q83, records[83], history)
    if failed and len(history) != 83:
        raise RuntimeError("M q84 failure/history count drift")
    if not failed and len(history) != 84:
        raise RuntimeError("M q84 success/history count drift")
    return {
        "validation_id": "M_k573440_c32_q84_predecessor_handoff_v1",
        "q1_through_q82_common_records_exact": True,
        "q1_through_q82_first_31_candidate_rows_exact": True,
        "q1_through_q82_selected_history_exact": True,
        "q83_shared_propagation_fields_exact": True,
        "q83_first_31_candidate_rows_exact": True,
        "q83_selected_candidate_index": 31,
        "q83_selected_K": K573440,
        "q83_selected_history_prefix_sha256": EXPECTED_Q83_SELECTED_HISTORY_PREFIX_SHA256,
        "q84_outcome_precommitted": False,
    }


def execution_components(
    parent_components: Any,
    self_sha: str,
    kernel_wrapper_sha: str,
) -> list[Dict[str, Any]]:
    if type(parent_components) is not list:
        raise RuntimeError("control-flow parent component list drift")
    if any(type(item) is not dict for item in parent_components):
        raise RuntimeError("control-flow parent component is not an exact dict")
    paths = [item.get("relative_path") for item in parent_components]
    if len(paths) != len(set(paths)):
        raise RuntimeError("duplicate parent execution component path")
    if parent_components != list(EXPECTED_PARENT_EXECUTION_COMPONENTS):
        raise RuntimeError("parent execution component schema drift")
    components = [{
        "relative_path": SELF_NAME,
        "role": "M_k573440_c32_q84_fresh_same_byte_screen",
        "sha256": self_sha,
    }]
    saw_parent = saw_v6 = saw_v2 = False
    forbidden_route_layers = {
        ROUTE_PREDECESSOR_SCREEN_NAME,
        ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
        ROUTE_Q82_SCREEN_NAME,
        ROUTE_Q82_TRANSCRIPT_NAME,
        "hubbard_l8_adaptive_k_arithmetic_k557056.py",
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
                "role": "k573440_capability_override_provider",
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
    if M_CANDIDATES != baseline_m + (K540672, K557056, K573440):
        raise RuntimeError("configuration override baseline M ladder drift")
    return {
        "override_id": "magnetization_k573440_c32_q84_configuration_override_v1",
        "diagnostic_ladder_precommitted_before_replay": True,
        "direct_execution_override_from_v6": {
            "baseline_candidate_K_values_sha256": EXPECTED_V6_M_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 29, "after": 32},
            "candidate_ladder_added": [K540672, K557056, K573440],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {
                "max_candidate_K": {"before": 524_288, "after": K573440},
                "max_output_terms_if_successful": {"before": 524_288, "after": K573440},
            },
        },
        "incremental_route_override_from_k557056_c31_q84": {
            "predecessor_candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 31, "after": 32},
            "candidate_ladder_added": [K573440],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {
                "max_candidate_K": {"before": K557056, "after": K573440},
                "max_output_terms_if_successful": {"before": K557056, "after": K573440},
            },
            "predecessor_configuration_override_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
            ),
        },
        "derived_policy_cap": {
            "field": "max_candidate_count",
            "derivation": "len(candidate_K_values)",
            "before_on_route": 31,
            "after": 32,
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
        "role": "separate_k573440_capability_override_provider",
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
            "max_retained_K": {"before": 524_288, "after": K573440},
        },
        "incremental_route_changes_from_k557056": {
            "max_retained_K": {"before": K557056, "after": K573440},
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
        raise RuntimeError("M q84 relabel requires fresh same-byte self execution")
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
    if (
        type(old_configuration) is not dict
        or result.get("configuration_reference_sha256")
        != sha256(canonical_bytes(old_configuration))
    ):
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
        "transform_id": "magnetization_four_gate_k573440_c32_q84_v1",
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": old_transform_sha,
        "route_predecessor_transform_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "q84_outcome_precommitted": False,
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
            "k573440_c32_q84_screen_v1"
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
        raise RuntimeError("M q84 screen requires fresh same-byte self execution")
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
    module = types.ModuleType("verified_magnetization_k573440_c32_q84_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("M q84 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("M q84 transcript exceeds output byte cap")
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
