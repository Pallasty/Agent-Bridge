#!/usr/bin/env python3
"""Source-pinned, diagnostic-only M K589824/C32 q86 screen.

The exact K589824/C32 q84 screen is compiled from pinned same bytes and its
private entrypoint owns a complete replay from checkpoint one.  Its execution
policy, candidate ladder, and wrapped arithmetic capability are unchanged;
only the diagnostic horizon changes from q84 to q86.  The q84 canonical
transcript is loaded only after replay as exact q1--84 prefix evidence.  It is
never compiled, executed, or used for propagation or state resume.
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
    "k589824_c32_q86_screen.py"
)
EXECUTION_PARENT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k589824_c32_q84_screen.py"
)
CONTROL_FLOW_ROOT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k589824.py"
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k589824_c32_q84_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k589824_c32_q86_transcript.json"
)

EXPECTED_EXECUTION_PARENT_SHA256 = (
    "594f03e397c5887df335d05971297a1d00e06b1ea19140003e7842a5ca897fb0"
)
EXPECTED_CONTROL_FLOW_ROOT_SHA256 = (
    "b483d9555a24dd07ea96292ed0a7ed51587259a79a2c5d69e3a8bf1408b4a614"
)
EXPECTED_V6_BASELINE_CONFIGURATION_SHA256 = (
    "3e7f9ff0546addfaa23f351f3569b102d0c3ebb578dbc4873b042bac21070af2"
)
EXPECTED_V2_ARITHMETIC_SHA256 = (
    "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998"
)
EXPECTED_KERNEL_WRAPPER_SHA256 = (
    "9eded142673fcb548d585d0071f5c550970c48c24d50c5ef1fc43b6257b1775d"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "cf93ebcccde4ff10adee2e600a13ef1c0f979e89fe151fca16d4eae79da2420f"
)
EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE = 748_013
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "2e1c35996258d985ee4808e2e86235ce004de0e4d843043bec71a29fe12f8a32"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "ba0a38f3cdf13114aaa7e00f2889bc221ad7afa1b42d038cc4a4ed710a21df5c"
)
EXPECTED_ROUTE_PREDECESSOR_Q84_RECORD_SHA256 = (
    "ed97e80cc71f6738865abf849e7fc722f42429bb7acf6a5f93f1ec319cc291fa"
)
EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256 = (
    "d06e3651d1a645e296a29dc82f6fbbb05a6d790e674c78c43649bc94bb423f41"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_SHA256 = (
    "a4d0b5a8736f2ffba7f83bf90685b5ce57920dee5028f9949159d5c3110a2138"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256 = (
    "217273e8b2918b5b56544d9db4ef862a2be7c5c0cd0bc2657fe92837ab3b0f72"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_OVERRIDE_SHA256 = (
    "99e98aa38690973611ac376f997f24b7ddba37f431027751e62e3241b4cca019"
)
EXPECTED_ROUTE_PREDECESSOR_PARENT_HORIZON_OVERRIDE_SHA256 = (
    "c0d860b56e0d4fb9c29e0227f4e8801a3d89d2e7e62de7945fd53075557aa924"
)
EXPECTED_ROUTE_PREDECESSOR_ROUTE_REFERENCE_SHA256 = (
    "4ce409275ca09feb675278ee033ca4966b9c2b90d15cab46a97f1b1a6d71774c"
)
EXPECTED_ROUTE_PREDECESSOR_HANDOFF_SHA256 = (
    "3555e090193a1df52ec56a9236086aac3a72408c2de25950fe9209b22e5194fb"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "b9c59f7a0f07b27292e50595c01d027dbf7e5d860792e3ca180a5ba4f0135361"
)
EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256 = (
    "c2aa225b96c984618d0dd0454dba9cb20f20ae8749f3f2452d8982a399f07336"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_ROUTE_TRANSCRIPT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

MODE = "magnetization"
BASE_PARENT_HORIZON = 84
EXTENDED_HORIZON = 86
K589824 = 589_824
M_CANDIDATES = tuple(range(81_920, 589_824 + 1, 16_384))
EXPECTED_CANDIDATE_SHA256 = (
    "94c062a2f562b7ce9e095ce9585ac4087b7bfef2af492b45762ca5d732ae9b80"
)
EXPECTED_Q84_RETAINED_EXPANSION_SHA256 = (
    "35971741409db21c05aaffcda87ef034a5eebe2199f3ba4b03e62c12bbc24eba"
)
EXPECTED_Q84_E_AFTER_TICKS = "1700230728891281"
EXPECTED_Q85_PREFIX_CAP_TICKS = "1700381839070373"
EXPECTED_Q86_PREFIX_CAP_TICKS = "1700486370476045"
EXPECTED_EXTENSION_CHECKPOINT_ANCHORS = {
    85: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 28,
        "gate_batch_sha256": (
            "34a10608b11edb722a301d2fd60689a6b29389d1ba6dc76376cbb124ae32d77c"
        ),
    },
    86: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 29,
        "gate_batch_sha256": (
            "890f848373b624e1b7ebe230ef5d32d07a6e862c357317657e72c95ddda4d74f"
        ),
    },
}

POLICY_CAPS_BASE = {
    "max_candidate_K": K589824,
    "max_output_terms_if_successful": K589824,
    "max_single_expansion_terms": 786_432,
    "max_digest_terms": 786_432,
    "max_term_gate_visits": 536_870_912,
    "max_expansion_coefficient_tick_bits": 192,
    "max_trigonometric_tick_bits": 66,
    "max_product_bits": 384,
    "max_suffix_accumulator_bits": 224,
}
EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS = {
    "max_candidate_count": 32,
    "max_digest_terms": 1_048_576,
    "max_expansion_coefficient_tick_bits": 192,
    "max_product_bits": 384,
    "max_retained_K": K589824,
    "max_single_expansion_terms": 1_048_576,
    "max_source_bytes": 196_608,
    "max_suffix_accumulator_bits": 224,
    "max_term_gate_visits": 1_000_000_000,
    "max_trigonometric_tick_bits": 66,
}

EXPECTED_PARENT_EXECUTION_COMPONENTS = (
    {
        "relative_path": CONTROL_FLOW_ROOT_NAME,
        "role": "four_gate_screen_execution_source",
        "sha256": EXPECTED_CONTROL_FLOW_ROOT_SHA256,
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
        "relative_path": (
            "hubbard_l8_interval_checkpoints/"
            "staggered_magnetization_boundary_003.b85"
        ),
        "role": "magnetization_encoded_input_boundary",
        "sha256": "91aecef5a3b79279e394c8995072d19565f4898e0ba29ddd7685ea9e535d9c84",
    },
)
EXPECTED_PARENT_SOURCE_CUSTODY = {
    "hubbard_l8_adaptive_k_v2_design_probe.py": (
        "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3"
    ),
    V6_BASELINE_CONFIGURATION_NAME: EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
    V2_ARITHMETIC_NAME: EXPECTED_V2_ARITHMETIC_SHA256,
    "hubbard_l8_observable_interval_step_checker.py": (
        "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a"
    ),
    "hubbard_l8_magnetization_interval_step3_checker.py": (
        "4e471b6f22838b2e9621adeeb757e7fa8277e3d8c4985eee392b182530c0c717"
    ),
    "hubbard_l8_magnetization_interval_step3_contract.json": (
        "fb1d5e82819d39f217a8c1c7f4979a689f4d46b8d691a8f464cad9012c197387"
    ),
    "hubbard_l8_magnetization_interval_step3_template.json": (
        "b68544091be417eed5310d8579eb8dc4d1a51e1863ed1fb7a8cbfa1fc6004eb6"
    ),
}

CANDIDATE_RECORD_KEYS = frozenset({
    "candidate_index",
    "configured_K",
    "effective_retained_count",
    "dropped_term_count",
    "drop_ticks",
    "E_after_if_selected_ticks",
    "feasible_under_current_prefix_cap",
})
FAILURE_ONLY_RECORD_KEYS = frozenset({
    "minimum_effective_K_to_meet_prefix",
    "required_K_excess_over_policy_maximum",
    "maximum_candidate_drop_excess_over_slack_ticks",
})
SUCCESS_ONLY_RECORD_KEYS = frozenset({
    "selected_effective_retained_count",
    "selected_dropped_term_count",
    "selected_drop_ticks",
    "selected_dropped_terms_sha256",
    "retained_expansion_count",
    "retained_expansion_sha256",
    "minimum_retained_abs_upper_ticks",
    "maximum_dropped_abs_upper_ticks",
    "E_after_ticks",
})
FAILURE_RECORD_KEYS = frozenset({
    "E_before_ticks",
    "batch_in_stage",
    "budget_prefix_cap_ticks",
    "candidate_records",
    "checkpoint_index_zero_based",
    "checkpoint_number_one_based",
    "gate_batch_sha256",
    "gate_occurrence_first_zero_based",
    "gate_occurrence_last_zero_based",
    "input_expansion_count",
    "input_expansion_sha256",
    "maximum_candidate_drop_excess_over_slack_ticks",
    "maximum_expansion_coefficient_tick_bits",
    "maximum_product_bits",
    "minimum_effective_K_to_meet_prefix",
    "peak_live_terms_cumulative",
    "peak_live_terms_this_checkpoint",
    "prefix_slack_before_selection_ticks",
    "pretruncation_expansion_count",
    "pretruncation_expansion_sha256",
    "ranked_suffix_sha256",
    "required_K_excess_over_policy_maximum",
    "rounding_cumulative_scaled_ticks_squared",
    "rounding_increment_scaled_ticks_squared",
    "selected_K",
    "selected_candidate_index",
    "stage_group",
    "stage_index",
    "status",
    "term_gate_visits_cumulative",
    "term_gate_visits_increment",
})
SUCCESS_RECORD_KEYS = (
    FAILURE_RECORD_KEYS - FAILURE_ONLY_RECORD_KEYS | SUCCESS_ONLY_RECORD_KEYS
)

EXPECTED_PARENT_RESULT_KEYS = frozenset({
    "schema_version", "transcript_fingerprint", "status",
    "screen_terminal_condition", "observable_id", "input_step_index",
    "attempted_child_step_index", "screen_source_sha256",
    "same_byte_self_execution", "v2_helper_source_sha256",
    "v2_helper_compiled_from_verified_bytes", "v2_helper_module_isolated",
    "v2_run_entrypoint_called", "v6_configuration_source_sha256",
    "v6_configuration_compiled_from_verified_bytes",
    "v6_configuration_module_isolated", "v6_execution_invoked",
    "v6_same_byte_execution_parent", "control_flow_owned_by_screen",
    "screen_execution_components", "screen_execution_components_sha256",
    "configuration_reference", "configuration_reference_sha256",
    "checkpoint_transform", "checkpoint_transform_sha256",
    "arithmetic_kernel_commit", "source_custody", "parent_expected_witness_sha256",
    "input_boundary_custody", "input_cumulative_drop_ticks",
    "maximum_cumulative_drop_ticks", "remaining_mapped_steps_including_attempt",
    "future_checkpoint_denominator", "prefix_cap_formula", "candidate_K_values",
    "candidate_K_values_sha256", "candidate_policy_precommitted_at_probe_time",
    "selection_rule", "single_propagation_and_single_ranking_per_checkpoint",
    "sequence", "screen_horizon_checkpoint_count", "horizon_checkpoint_attempted",
    "horizon_reached_with_committed_checkpoint", "kernel_capability_limits",
    "proposed_policy_caps", "root_globals_before", "root_globals_after",
    "root_globals_unchanged", "attempted_checkpoint_count",
    "completed_checkpoint_count", "failure_checkpoint_included",
    "selected_K_history", "selected_K_history_sha256", "records",
    "records_sha256", "failure_record_sha256",
    "last_committed_cumulative_drop_ticks",
    "observed_peak_single_expansion_terms",
    "observed_term_gate_visits_including_terminal_attempt",
    "observed_maximum_expansion_coefficient_tick_bits",
    "observed_maximum_product_bits",
    "observed_rounding_cumulative_scaled_ticks_squared", "child_boundary_committed",
    "positive_artifact_generated",
    "runtime_RSS_host_timestamp_and_float_fields_excluded",
})
RELABELLED_ADDED_TOP_LEVEL_KEYS = frozenset({
    "arithmetic_kernel_commit_role", "configuration_override",
    "configuration_override_sha256", "control_flow_owned_by_verified_parent",
    "control_flow_parent_compiled_from_verified_bytes",
    "control_flow_parent_module_isolated", "control_flow_parent_private_entrypoint_called",
    "control_flow_parent_relative_path",
    "control_flow_parent_runtime_horizon_override_applied",
    "control_flow_parent_same_byte_execution", "control_flow_parent_source_sha256",
    "diagnostic_candidate_ladder_precommitted_before_replay",
    "diagnostic_horizon_precommitted_before_replay", "kernel_capability_override",
    "kernel_capability_override_sha256", "kernel_capability_wrapper_compiled_from_verified_bytes",
    "kernel_capability_wrapper_module_isolated", "kernel_capability_wrapper_relative_path",
    "kernel_capability_wrapper_source_sha256", "parent_horizon_override",
    "parent_horizon_override_sha256", "predecessor_handoff_validation",
    "predecessor_handoff_validation_sha256", "route_predecessor_reference",
    "route_predecessor_reference_sha256", "v2_arithmetic_compiled_from_verified_bytes",
    "v2_arithmetic_source_sha256", "v6_configuration_source_used_as_baseline_only",
    "v6_runtime_configuration_override_applied",
})
EXPECTED_RELABELLED_RESULT_KEYS = (
    EXPECTED_PARENT_RESULT_KEYS | RELABELLED_ADDED_TOP_LEVEL_KEYS
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


def require_exact_keys(value: Any, expected: frozenset[str], label: str) -> None:
    if type(value) is not dict:
        raise RuntimeError(f"{label} is not an exact dict")
    observed = frozenset(value)
    if observed != expected:
        raise RuntimeError(
            f"{label} exact key-set drift: "
            f"missing={sorted(expected - observed)}, "
            f"extra={sorted(observed - expected)}"
        )


def exact_value_equal(observed: Any, expected: Any) -> bool:
    """Compare JSON-shaped values without Python's bool/int equivalence."""

    if type(observed) is not type(expected):
        return False
    if type(expected) is dict:
        return (
            observed.keys() == expected.keys()
            and all(
                exact_value_equal(observed[key], expected[key])
                for key in expected
            )
        )
    if type(expected) in (list, tuple):
        return (
            len(observed) == len(expected)
            and all(
                exact_value_equal(left, right)
                for left, right in zip(observed, expected)
            )
        )
    return observed == expected


def is_canonical_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def parse_canonical_nonnegative_decimal(value: Any, label: str) -> int:
    if type(value) is not str or not value:
        raise RuntimeError(f"{label} is not a canonical decimal string")
    if any(character not in "0123456789" for character in value):
        raise RuntimeError(f"{label} is not a canonical decimal string")
    if len(value) > 1 and value[0] == "0":
        raise RuntimeError(f"{label} is not a canonical decimal string")
    return int(value)


def validate_local_configuration() -> None:
    if len(M_CANDIDATES) != 32 or M_CANDIDATES[-1] != K589824:
        raise RuntimeError("M q86 candidate ladder drift")
    if any(left >= right for left, right in zip(M_CANDIDATES, M_CANDIDATES[1:])):
        raise RuntimeError("M q86 candidate order drift")
    if sha256(canonical_bytes(list(M_CANDIDATES))) != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("M q86 candidate digest drift")
    if POLICY_CAPS_BASE["max_candidate_K"] != K589824:
        raise RuntimeError("M q86 policy maximum drift")
    if POLICY_CAPS_BASE["max_output_terms_if_successful"] != K589824:
        raise RuntimeError("M q86 output cap drift")
    if EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS["max_retained_K"] != K589824:
        raise RuntimeError("M q86 kernel retained cap drift")
    if BASE_PARENT_HORIZON != 84 or EXTENDED_HORIZON != 86:
        raise RuntimeError("M q86 horizon contract drift")
    sizes = {
        "raw": len(EXPECTED_PARENT_RESULT_KEYS),
        "final": len(EXPECTED_RELABELLED_RESULT_KEYS),
        "success": len(SUCCESS_RECORD_KEYS),
        "failure": len(FAILURE_RECORD_KEYS),
        "row": len(CANDIDATE_RECORD_KEYS),
    }
    if sizes != {"raw": 65, "final": 94, "success": 37, "failure": 31, "row": 7}:
        raise RuntimeError("M q86 closed schema size drift")


def load_execution_parent(repo: Path) -> Any:
    path = checked_repo_file(repo, EXECUTION_PARENT_NAME)
    payload = bounded_bytes(path, MAX_PINNED_SOURCE_BYTES)
    if sha256(payload) != EXPECTED_EXECUTION_PARENT_SHA256:
        raise RuntimeError("M q84 execution-parent source pin drift")
    parent = compile_isolated(
        "pinned_m_k589824_c32_q84_parent_for_q86",
        path,
        payload,
    )
    expected = {
        "SELF_NAME": EXECUTION_PARENT_NAME,
        "CONTROL_FLOW_PARENT_NAME": CONTROL_FLOW_ROOT_NAME,
        "KERNEL_WRAPPER_NAME": KERNEL_WRAPPER_NAME,
        "EXPECTED_CONTROL_FLOW_PARENT_SHA256": EXPECTED_CONTROL_FLOW_ROOT_SHA256,
        "EXPECTED_KERNEL_WRAPPER_SHA256": EXPECTED_KERNEL_WRAPPER_SHA256,
        "EXTENDED_HORIZON": BASE_PARENT_HORIZON,
        "M_CANDIDATES": M_CANDIDATES,
        "POLICY_CAPS_BASE": POLICY_CAPS_BASE,
        "EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS": (
            EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        ),
    }
    for field, value in expected.items():
        if getattr(parent, field, None) != value:
            raise RuntimeError(f"M q84 execution-parent contract drift: {field}")
    if frozenset(parent.EXPECTED_PARENT_RESULT_KEYS) != EXPECTED_PARENT_RESULT_KEYS:
        raise RuntimeError("M q84 raw parent schema drift")
    if frozenset(parent.EXPECTED_RELABELLED_RESULT_KEYS) != (
        EXPECTED_RELABELLED_RESULT_KEYS
    ):
        raise RuntimeError("M q84 final parent schema drift")
    parent.validate_local_configuration()
    return parent


def execute_parent_replay(parent: Any, repo: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Call the exact q84 private entrypoint with only horizon semantics changed."""

    if type(parent) is not types.ModuleType:
        raise RuntimeError("M q86 execution parent is not an isolated module")
    parent.validate_local_configuration()
    originals = {
        "EXTENDED_HORIZON": parent.EXTENDED_HORIZON,
        "validate_local_configuration": parent.validate_local_configuration,
        "load_configured_v6_baseline": parent.load_configured_v6_baseline,
        "load_kernel_wrapper": parent.load_kernel_wrapper,
        "load_route_predecessor_reference": parent.load_route_predecessor_reference,
        "configure_parent_execution": parent.configure_parent_execution,
        "validate_and_relabel": parent.validate_and_relabel,
    }
    context: Dict[str, Any] = {
        "execution_parent_private_entrypoint_called": False,
        "q84_canonical_loaded_before_replay": False,
        "execution_parent_route_loader_suppressed": False,
    }

    def capture_configuration(source_repo):
        configuration, baseline_m = originals["load_configured_v6_baseline"](
            source_repo
        )
        context["baseline_m"] = tuple(baseline_m)
        return configuration, baseline_m

    def capture_wrapper(source_repo):
        wrapper, wrapper_sha, manifest = originals["load_kernel_wrapper"](
            source_repo
        )
        context.update({
            "wrapper_sha": wrapper_sha,
            "wrapper_manifest": copy.deepcopy(manifest),
        })
        return wrapper, wrapper_sha, manifest

    def no_predecessor_load(_source_repo):
        context["q84_canonical_loaded_before_replay"] = False
        context["execution_parent_route_loader_suppressed"] = True
        return {}, {}

    def capture_horizon(control_parent, configuration, wrapper):
        horizon = originals["configure_parent_execution"](
            control_parent,
            configuration,
            wrapper,
        )
        context["raw_control_flow_horizon_override"] = copy.deepcopy(horizon)
        return horizon

    def return_raw(result, *_args):
        return result

    try:
        parent.EXTENDED_HORIZON = EXTENDED_HORIZON
        parent.validate_local_configuration = lambda: None
        parent.load_configured_v6_baseline = capture_configuration
        parent.load_kernel_wrapper = capture_wrapper
        parent.load_route_predecessor_reference = no_predecessor_load
        parent.configure_parent_execution = capture_horizon
        parent.validate_and_relabel = return_raw
        context["execution_parent_private_entrypoint_called"] = True
        result = parent._run_verified(repo.resolve())
    finally:
        for field, value in originals.items():
            setattr(parent, field, value)
    if type(result) is not dict:
        raise RuntimeError("M q86 execution parent returned a non-dict result")
    required_context = {
        "baseline_m",
        "wrapper_sha",
        "wrapper_manifest",
        "raw_control_flow_horizon_override",
        "execution_parent_route_loader_suppressed",
    }
    if not required_context <= context.keys():
        raise RuntimeError("M q86 execution-parent adapter did not close context")
    if context["wrapper_sha"] != EXPECTED_KERNEL_WRAPPER_SHA256:
        raise RuntimeError("M q86 captured wrapper pin drift")
    if context["execution_parent_route_loader_suppressed"] is not True:
        raise RuntimeError("M q86 execution-parent route loader was not suppressed")
    return result, context


def load_route_reference(repo: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    screen_raw = bounded_bytes(
        checked_repo_file(repo, EXECUTION_PARENT_NAME),
        MAX_PINNED_SOURCE_BYTES,
    )
    if sha256(screen_raw) != EXPECTED_EXECUTION_PARENT_SHA256:
        raise RuntimeError("route q84 screen source pin drift")
    raw = bounded_bytes(
        checked_repo_file(repo, ROUTE_PREDECESSOR_TRANSCRIPT_NAME),
        MAX_ROUTE_TRANSCRIPT_BYTES,
    )
    if len(raw) != EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE:
        raise RuntimeError("route q84 canonical file-size drift")
    if sha256(raw) != EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256:
        raise RuntimeError("route q84 canonical file pin drift")
    try:
        transcript = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("route q84 canonical is invalid JSON") from exc
    if type(transcript) is not dict or raw != canonical_bytes(transcript):
        raise RuntimeError("route q84 transcript is not canonical JSON")
    require_exact_keys(
        transcript,
        EXPECTED_RELABELLED_RESULT_KEYS,
        "route q84 canonical top-level transcript",
    )
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k589824_c32_q84_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_horizon_checkpoint_count": BASE_PARENT_HORIZON,
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "attempted_checkpoint_count": 84,
        "completed_checkpoint_count": 84,
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": True,
        "candidate_K_values": list(M_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **POLICY_CAPS_BASE,
            "max_candidate_count": len(M_CANDIDATES),
        },
        "kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        "records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        "screen_execution_components_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256
        ),
        "configuration_reference_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_SHA256
        ),
        "configuration_override_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
        ),
        "kernel_capability_override_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_KERNEL_OVERRIDE_SHA256
        ),
        "parent_horizon_override_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_PARENT_HORIZON_OVERRIDE_SHA256
        ),
        "route_predecessor_reference_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_ROUTE_REFERENCE_SHA256
        ),
        "predecessor_handoff_validation_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_HANDOFF_SHA256
        ),
        "checkpoint_transform_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256
        ),
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for field, value in expected.items():
        if transcript.get(field) != value:
            raise RuntimeError(f"route q84 canonical drift: {field}")
    for value_field, digest_field in (
        ("records", "records_sha256"),
        ("selected_K_history", "selected_K_history_sha256"),
        ("screen_execution_components", "screen_execution_components_sha256"),
        ("configuration_reference", "configuration_reference_sha256"),
        ("configuration_override", "configuration_override_sha256"),
        ("kernel_capability_override", "kernel_capability_override_sha256"),
        ("parent_horizon_override", "parent_horizon_override_sha256"),
        ("route_predecessor_reference", "route_predecessor_reference_sha256"),
        ("predecessor_handoff_validation", "predecessor_handoff_validation_sha256"),
        ("checkpoint_transform", "checkpoint_transform_sha256"),
    ):
        if sha256(canonical_bytes(transcript[value_field])) != transcript[digest_field]:
            raise RuntimeError(f"route q84 nested digest drift: {value_field}")
    records = transcript.get("records")
    history = transcript.get("selected_K_history")
    if type(records) is not list or len(records) != 84:
        raise RuntimeError("route q84 record count drift")
    if type(history) is not list or len(history) != 84:
        raise RuntimeError("route q84 history count drift")
    if sha256(canonical_bytes(records)) != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256:
        raise RuntimeError("route q84 record digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256:
        raise RuntimeError("route q84 history digest drift")
    q84 = records[-1]
    require_exact_keys(q84, SUCCESS_RECORD_KEYS, "route q84 terminal record")
    if sha256(canonical_bytes(q84)) != EXPECTED_ROUTE_PREDECESSOR_Q84_RECORD_SHA256:
        raise RuntimeError("route q84 terminal record digest drift")
    anchors = {
        "checkpoint_number_one_based": 84,
        "selected_candidate_index": 31,
        "selected_K": K589824,
        "retained_expansion_count": K589824,
        "retained_expansion_sha256": EXPECTED_Q84_RETAINED_EXPANSION_SHA256,
        "E_after_ticks": EXPECTED_Q84_E_AFTER_TICKS,
    }
    for field, value in anchors.items():
        if not exact_value_equal(q84.get(field), value):
            raise RuntimeError(f"route q84 terminal anchor drift: {field}")
    outer_transform = transcript["checkpoint_transform"]
    raw_transform = outer_transform.get(
        "physical_four_gate_control_flow_parent_transform"
    )
    raw_transform_sha = outer_transform.get(
        "physical_four_gate_control_flow_parent_transform_sha256"
    )
    if raw_transform_sha != EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256:
        raise RuntimeError("route q84 embedded raw transform pin drift")
    if sha256(canonical_bytes(raw_transform)) != raw_transform_sha:
        raise RuntimeError("route q84 embedded raw transform digest drift")
    reference = {
        "route_id": "magnetization_k589824_c32_q84_to_q86_v1",
        "execution_parent_screen": {
            "relative_path": EXECUTION_PARENT_NAME,
            "source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
            "compiled": True,
            "executed": True,
            "private_entrypoint_called": True,
            "execution_source_layer": True,
        },
        "canonical_transcript": {
            "relative_path": ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
            "file_size_bytes": EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE,
            "file_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
            "records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
            "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
            "q84_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q84_RECORD_SHA256,
            "compiled": False,
            "executed": False,
            "loaded_before_replay": False,
            "loaded_after_full_replay_as_exact_reference": True,
            "used_only_for_post_replay_q1_q84_prefix_validation": True,
            "propagation_input": False,
            "checkpoint_84_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
        },
        "incremental_semantic_delta": {
            "candidate_K_values_changed": False,
            "policy_caps_changed": False,
            "kernel_capability_limits_changed": False,
            "horizon_checkpoint_count": {"before": 84, "after": 86},
        },
    }
    return transcript, reference


def validate_parent_source_custody(value: Any) -> Dict[str, str]:
    require_exact_keys(
        value,
        frozenset(EXPECTED_PARENT_SOURCE_CUSTODY),
        "M q86 raw parent source custody",
    )
    for path, expected_sha in EXPECTED_PARENT_SOURCE_CUSTODY.items():
        if value.get(path) != expected_sha or not is_canonical_sha256(value.get(path)):
            raise RuntimeError(f"M q86 raw parent custody drift: {path}")
    return dict(value)


def expected_final_source_custody(self_sha: str) -> Dict[str, str]:
    if not is_canonical_sha256(self_sha):
        raise RuntimeError("M q86 self custody digest drift")
    return {
        **EXPECTED_PARENT_SOURCE_CUSTODY,
        SELF_NAME: self_sha,
        EXECUTION_PARENT_NAME: EXPECTED_EXECUTION_PARENT_SHA256,
        KERNEL_WRAPPER_NAME: EXPECTED_KERNEL_WRAPPER_SHA256,
    }


def validate_extended_record(
    record: Mapping[str, Any],
    previous: Mapping[str, Any],
    checkpoint: int,
) -> int | None:
    if type(record) is not dict or type(previous) is not dict:
        raise RuntimeError(f"M q{checkpoint} record continuity type drift")
    status = record.get("status")
    if status == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
        expected_keys = SUCCESS_RECORD_KEYS
    elif status == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE":
        expected_keys = FAILURE_RECORD_KEYS
    else:
        raise RuntimeError(f"M q{checkpoint} status drift")
    require_exact_keys(record, expected_keys, f"M q{checkpoint} record")
    expected_scalars = {
        "checkpoint_index_zero_based": checkpoint - 1,
        "checkpoint_number_one_based": checkpoint,
        "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
        "gate_occurrence_last_zero_based": 4 * checkpoint - 1,
        "input_expansion_count": previous["retained_expansion_count"],
        "input_expansion_sha256": previous["retained_expansion_sha256"],
        "E_before_ticks": previous["E_after_ticks"],
        "budget_prefix_cap_ticks": (
            EXPECTED_Q85_PREFIX_CAP_TICKS
            if checkpoint == 85
            else EXPECTED_Q86_PREFIX_CAP_TICKS
        ),
        **EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint],
    }
    for field, value in expected_scalars.items():
        if not exact_value_equal(record.get(field), value):
            raise RuntimeError(f"M q{checkpoint} exact ledger drift: {field}")
    for field in (
        "gate_batch_sha256",
        "input_expansion_sha256",
        "pretruncation_expansion_sha256",
        "ranked_suffix_sha256",
    ):
        if not is_canonical_sha256(record.get(field)):
            raise RuntimeError(f"M q{checkpoint} digest schema drift: {field}")
    integer_fields = (
        "input_expansion_count",
        "pretruncation_expansion_count",
        "peak_live_terms_this_checkpoint",
        "peak_live_terms_cumulative",
        "term_gate_visits_increment",
        "term_gate_visits_cumulative",
        "maximum_expansion_coefficient_tick_bits",
        "maximum_product_bits",
    )
    for field in integer_fields:
        if type(record.get(field)) is not int or record[field] < 0:
            raise RuntimeError(f"M q{checkpoint} integer ledger drift: {field}")
    pre_count = record["pretruncation_expansion_count"]
    if pre_count > min(
        POLICY_CAPS_BASE["max_single_expansion_terms"],
        POLICY_CAPS_BASE["max_digest_terms"],
    ):
        raise RuntimeError(f"M q{checkpoint} pretruncation cap exceeded")
    if record["peak_live_terms_this_checkpoint"] < max(
        record["input_expansion_count"], pre_count
    ):
        raise RuntimeError(f"M q{checkpoint} checkpoint peak below live terms")
    if record["peak_live_terms_this_checkpoint"] > POLICY_CAPS_BASE[
        "max_single_expansion_terms"
    ]:
        raise RuntimeError(f"M q{checkpoint} checkpoint peak cap exceeded")
    if record["term_gate_visits_increment"] < record["input_expansion_count"]:
        raise RuntimeError(f"M q{checkpoint} visit increment below input")
    if record["term_gate_visits_cumulative"] > POLICY_CAPS_BASE[
        "max_term_gate_visits"
    ]:
        raise RuntimeError(f"M q{checkpoint} visit cap exceeded")

    E_before = parse_canonical_nonnegative_decimal(
        record["E_before_ticks"], f"M q{checkpoint} E-before"
    )
    prefix_cap = parse_canonical_nonnegative_decimal(
        record["budget_prefix_cap_ticks"], f"M q{checkpoint} prefix cap"
    )
    slack = parse_canonical_nonnegative_decimal(
        record["prefix_slack_before_selection_ticks"],
        f"M q{checkpoint} prefix slack",
    )
    if slack != prefix_cap - E_before:
        raise RuntimeError(f"M q{checkpoint} prefix slack recurrence drift")
    rounding_increment = parse_canonical_nonnegative_decimal(
        record["rounding_increment_scaled_ticks_squared"],
        f"M q{checkpoint} rounding increment",
    )
    rounding_cumulative = parse_canonical_nonnegative_decimal(
        record["rounding_cumulative_scaled_ticks_squared"],
        f"M q{checkpoint} rounding cumulative",
    )
    previous_rounding = parse_canonical_nonnegative_decimal(
        previous["rounding_cumulative_scaled_ticks_squared"],
        f"M q{checkpoint - 1} rounding cumulative",
    )
    if rounding_cumulative != previous_rounding + rounding_increment:
        raise RuntimeError(f"M q{checkpoint} rounding recurrence drift")
    if record["term_gate_visits_cumulative"] != (
        previous["term_gate_visits_cumulative"]
        + record["term_gate_visits_increment"]
    ):
        raise RuntimeError(f"M q{checkpoint} visit recurrence drift")
    if record["peak_live_terms_cumulative"] != max(
        previous["peak_live_terms_cumulative"],
        record["peak_live_terms_this_checkpoint"],
    ):
        raise RuntimeError(f"M q{checkpoint} peak recurrence drift")
    for field, policy_field in (
        (
            "maximum_expansion_coefficient_tick_bits",
            "max_expansion_coefficient_tick_bits",
        ),
        ("maximum_product_bits", "max_product_bits"),
    ):
        if record[field] < previous[field]:
            raise RuntimeError(f"M q{checkpoint} cumulative maximum decreased: {field}")
        if record[field] > POLICY_CAPS_BASE[policy_field]:
            raise RuntimeError(f"M q{checkpoint} cumulative maximum cap exceeded: {field}")

    rows = record.get("candidate_records")
    if type(rows) is not list or len(rows) != len(M_CANDIDATES):
        raise RuntimeError(f"M q{checkpoint} candidate row count drift")
    feasible_indices = []
    drops = []
    for candidate_index, (configured_K, row) in enumerate(
        zip(M_CANDIDATES, rows)
    ):
        require_exact_keys(
            row,
            CANDIDATE_RECORD_KEYS,
            f"M q{checkpoint} candidate row {candidate_index}",
        )
        effective = min(configured_K, pre_count)
        expected = {
            "candidate_index": candidate_index,
            "configured_K": configured_K,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
        }
        for field, value in expected.items():
            if not exact_value_equal(row.get(field), value):
                raise RuntimeError(
                    f"M q{checkpoint} candidate row drift: {field}"
                )
        drop = parse_canonical_nonnegative_decimal(
            row["drop_ticks"],
            f"M q{checkpoint} candidate {candidate_index} drop",
        )
        if (row["dropped_term_count"] == 0) is not (drop == 0):
            raise RuntimeError(
                f"M q{checkpoint} dropped-count/drop zero equivalence drift"
            )
        E_after = parse_canonical_nonnegative_decimal(
            row["E_after_if_selected_ticks"],
            f"M q{checkpoint} candidate {candidate_index} E-after",
        )
        if E_after != E_before + drop:
            raise RuntimeError(f"M q{checkpoint} candidate E recurrence drift")
        feasible = E_after <= prefix_cap
        if row.get("feasible_under_current_prefix_cap") is not feasible:
            raise RuntimeError(f"M q{checkpoint} candidate feasibility drift")
        drops.append(drop)
        if feasible:
            feasible_indices.append(candidate_index)
    if drops != sorted(drops, reverse=True):
        raise RuntimeError(f"M q{checkpoint} candidate drop ranking drift")

    if status == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
        if not feasible_indices:
            raise RuntimeError(f"M q{checkpoint} success has no feasible row")
        selected_index = feasible_indices[0]
        if feasible_indices != list(range(selected_index, len(M_CANDIDATES))):
            raise RuntimeError(f"M q{checkpoint} feasible rows are not a suffix")
        selected_row = rows[selected_index]
        expected_selection = {
            "selected_candidate_index": selected_index,
            "selected_K": selected_row["configured_K"],
            "selected_effective_retained_count": selected_row[
                "effective_retained_count"
            ],
            "selected_dropped_term_count": selected_row["dropped_term_count"],
            "selected_drop_ticks": selected_row["drop_ticks"],
            "retained_expansion_count": selected_row["effective_retained_count"],
            "E_after_ticks": selected_row["E_after_if_selected_ticks"],
        }
        for field, value in expected_selection.items():
            if not exact_value_equal(record.get(field), value):
                raise RuntimeError(f"M q{checkpoint} first-feasible drift: {field}")
        for field in (
            "selected_dropped_terms_sha256",
            "retained_expansion_sha256",
        ):
            if not is_canonical_sha256(record.get(field)):
                raise RuntimeError(f"M q{checkpoint} success digest drift: {field}")
        minimum_retained = parse_canonical_nonnegative_decimal(
            record["minimum_retained_abs_upper_ticks"],
            f"M q{checkpoint} minimum retained",
        )
        maximum_dropped = parse_canonical_nonnegative_decimal(
            record["maximum_dropped_abs_upper_ticks"],
            f"M q{checkpoint} maximum dropped",
        )
        if minimum_retained < maximum_dropped:
            raise RuntimeError(f"M q{checkpoint} ranked boundary order drift")
        return record["selected_K"]

    if feasible_indices:
        raise RuntimeError(f"M q{checkpoint} failure contains a feasible row")
    if record.get("selected_candidate_index") is not None:
        raise RuntimeError(f"M q{checkpoint} failure selected an index")
    if record.get("selected_K") is not None:
        raise RuntimeError(f"M q{checkpoint} failure selected K")
    minimum_K = record.get("minimum_effective_K_to_meet_prefix")
    excess = record.get("required_K_excess_over_policy_maximum")
    if type(minimum_K) is not int or type(excess) is not int:
        raise RuntimeError(f"M q{checkpoint} failure minimum-K type drift")
    if (
        minimum_K <= K589824
        or minimum_K > pre_count
        or excess != minimum_K - K589824
    ):
        raise RuntimeError(f"M q{checkpoint} failure excess-K drift")
    maximum_excess = parse_canonical_nonnegative_decimal(
        record["maximum_candidate_drop_excess_over_slack_ticks"],
        f"M q{checkpoint} failure maximum excess",
    )
    if maximum_excess != drops[-1] - slack or maximum_excess <= 0:
        raise RuntimeError(f"M q{checkpoint} failure cap excess drift")
    return None


def validate_replay_handoff(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:
    require_exact_keys(
        result,
        EXPECTED_PARENT_RESULT_KEYS,
        "M q86 raw execution-parent result",
    )
    require_exact_keys(
        predecessor,
        EXPECTED_RELABELLED_RESULT_KEYS,
        "M q84 route canonical",
    )
    invariants = {
        "schema_version": 1,
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_CONTROL_FLOW_ROOT_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "same_byte_self_execution": True,
        "control_flow_owned_by_screen": True,
        "v2_run_entrypoint_called": False,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
        "screen_horizon_checkpoint_count": EXTENDED_HORIZON,
        "candidate_K_values": list(M_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **POLICY_CAPS_BASE,
            "max_candidate_count": len(M_CANDIDATES),
        },
        "kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for field, value in invariants.items():
        if not exact_value_equal(result.get(field), value):
            raise RuntimeError(f"M q86 raw parent drift: {field}")
    validate_parent_source_custody(result.get("source_custody"))
    if result.get("screen_execution_components") != list(
        EXPECTED_PARENT_EXECUTION_COMPONENTS
    ):
        raise RuntimeError("M q86 raw component closure drift")
    for value_field, digest_field in (
        ("screen_execution_components", "screen_execution_components_sha256"),
        ("configuration_reference", "configuration_reference_sha256"),
        ("checkpoint_transform", "checkpoint_transform_sha256"),
    ):
        if result.get(digest_field) != sha256(
            canonical_bytes(result.get(value_field))
        ):
            raise RuntimeError(f"M q86 raw nested digest drift: {value_field}")
    dynamic_or_relabelled_fields = {
        "transcript_fingerprint",
        "screen_terminal_condition",
        "screen_source_sha256",
        "control_flow_owned_by_screen",
        "screen_execution_components",
        "screen_execution_components_sha256",
        "configuration_reference",
        "configuration_reference_sha256",
        "checkpoint_transform",
        "checkpoint_transform_sha256",
        "source_custody",
        "screen_horizon_checkpoint_count",
        "horizon_checkpoint_attempted",
        "horizon_reached_with_committed_checkpoint",
        "attempted_checkpoint_count",
        "completed_checkpoint_count",
        "failure_checkpoint_included",
        "selected_K_history",
        "selected_K_history_sha256",
        "records",
        "records_sha256",
        "failure_record_sha256",
        "last_committed_cumulative_drop_ticks",
        "observed_peak_single_expansion_terms",
        "observed_term_gate_visits_including_terminal_attempt",
        "observed_maximum_expansion_coefficient_tick_bits",
        "observed_maximum_product_bits",
        "observed_rounding_cumulative_scaled_ticks_squared",
    }
    for field in EXPECTED_PARENT_RESULT_KEYS - dynamic_or_relabelled_fields:
        if not exact_value_equal(result.get(field), predecessor.get(field)):
            raise RuntimeError(f"M q86 invariant top-level drift: {field}")
    expected_raw_transform = predecessor["checkpoint_transform"].get(
        "physical_four_gate_control_flow_parent_transform"
    )
    expected_raw_transform_sha = predecessor["checkpoint_transform"].get(
        "physical_four_gate_control_flow_parent_transform_sha256"
    )
    if expected_raw_transform_sha != EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256:
        raise RuntimeError("M q86 q84 raw transform authority pin drift")
    if not exact_value_equal(
        result.get("checkpoint_transform"), expected_raw_transform
    ):
        raise RuntimeError("M q86 raw checkpoint transform authority drift")
    if result.get("checkpoint_transform_sha256") != (
        EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256
    ):
        raise RuntimeError("M q86 raw checkpoint transform digest pin drift")
    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or len(records) not in (85, 86):
        raise RuntimeError("M q86 must attempt q85 and at most q86")
    if type(history) is not list:
        raise RuntimeError("M q86 selected history is not an exact list")
    old_records = predecessor["records"]
    old_history = predecessor["selected_K_history"]
    if not exact_value_equal(records[:84], old_records):
        raise RuntimeError("M q86 changed the exact q1-q84 record prefix")
    if not exact_value_equal(history[:84], old_history):
        raise RuntimeError("M q86 changed the exact q1-q84 selected history")
    if sha256(canonical_bytes(records[:84])) != (
        EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
    ):
        raise RuntimeError("M q86 q1-q84 record prefix digest drift")
    if sha256(canonical_bytes(history[:84])) != (
        EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256
    ):
        raise RuntimeError("M q86 q1-q84 history prefix digest drift")
    q84 = records[83]
    if sha256(canonical_bytes(q84)) != EXPECTED_ROUTE_PREDECESSOR_Q84_RECORD_SHA256:
        raise RuntimeError("M q86 q84 record anchor drift")
    if q84.get("retained_expansion_count") != K589824:
        raise RuntimeError("M q86 q84 retained-count anchor drift")
    if q84.get("retained_expansion_sha256") != EXPECTED_Q84_RETAINED_EXPANSION_SHA256:
        raise RuntimeError("M q86 q84 retained digest anchor drift")
    if q84.get("E_after_ticks") != EXPECTED_Q84_E_AFTER_TICKS:
        raise RuntimeError("M q86 q84 E anchor drift")

    selected_q85 = validate_extended_record(records[84], q84, 85)
    extension_history = []
    if selected_q85 is None:
        if len(records) != 85 or len(history) != 84:
            raise RuntimeError("M q85 failure must terminate before q86")
        branch = "Q85_FAILURE_Q86_NOT_ATTEMPTED"
        expected_summary = {
            "attempted_checkpoint_count": 85,
            "completed_checkpoint_count": 84,
            "horizon_checkpoint_attempted": False,
            "horizon_reached_with_committed_checkpoint": False,
            "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
            "failure_checkpoint_included": True,
            "last_committed_cumulative_drop_ticks": EXPECTED_Q84_E_AFTER_TICKS,
        }
    else:
        extension_history.append(selected_q85)
        if len(records) != 86:
            raise RuntimeError("M q85 success must continue through q86")
        selected_q86 = validate_extended_record(records[85], records[84], 86)
        if selected_q86 is None:
            if len(history) != 85:
                raise RuntimeError("M q86 failure history count drift")
            branch = "Q85_SUCCESS_Q86_FAILURE"
            expected_summary = {
                "attempted_checkpoint_count": 86,
                "completed_checkpoint_count": 85,
                "horizon_checkpoint_attempted": True,
                "horizon_reached_with_committed_checkpoint": False,
                "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                "failure_checkpoint_included": True,
                "last_committed_cumulative_drop_ticks": records[84]["E_after_ticks"],
            }
        else:
            extension_history.append(selected_q86)
            if len(history) != 86:
                raise RuntimeError("M q86 success history count drift")
            branch = "Q85_AND_Q86_SUCCESS_HORIZON_REACHED"
            expected_summary = {
                "attempted_checkpoint_count": 86,
                "completed_checkpoint_count": 86,
                "horizon_checkpoint_attempted": True,
                "horizon_reached_with_committed_checkpoint": True,
                "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
                "failure_checkpoint_included": False,
                "last_committed_cumulative_drop_ticks": records[85]["E_after_ticks"],
            }
    if history != list(old_history) + extension_history:
        raise RuntimeError("M q86 selected history is not the exact replay ledger")
    for field, value in expected_summary.items():
        if not exact_value_equal(result.get(field), value):
            raise RuntimeError(f"M q86 terminal summary drift: {field}")
    final = records[-1]
    failed = final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
    expected_failure_sha = sha256(canonical_bytes(final)) if failed else None
    if result.get("failure_record_sha256") != expected_failure_sha:
        raise RuntimeError("M q86 failure-record digest drift")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("M q86 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(canonical_bytes(history)):
        raise RuntimeError("M q86 history digest drift")
    resources = {
        "observed_peak_single_expansion_terms": final["peak_live_terms_cumulative"],
        "observed_term_gate_visits_including_terminal_attempt": final[
            "term_gate_visits_cumulative"
        ],
        "observed_maximum_expansion_coefficient_tick_bits": final[
            "maximum_expansion_coefficient_tick_bits"
        ],
        "observed_maximum_product_bits": final["maximum_product_bits"],
        "observed_rounding_cumulative_scaled_ticks_squared": final[
            "rounding_cumulative_scaled_ticks_squared"
        ],
    }
    for field, value in resources.items():
        if result.get(field) != value:
            raise RuntimeError(f"M q86 observed resource drift: {field}")
    return {
        "validation_id": "M_k589824_c32_q86_same_cap_handoff_v1",
        "q1_through_q84_records_exact": True,
        "q1_through_q84_all_32_candidate_rows_exact": True,
        "q1_through_q84_selected_history_exact": True,
        "q84_records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        "q84_selected_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        "q84_terminal_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q84_RECORD_SHA256,
        "q85_input_retained_count": K589824,
        "q85_input_retained_sha256": EXPECTED_Q84_RETAINED_EXPANSION_SHA256,
        "q85_input_E_before_ticks": EXPECTED_Q84_E_AFTER_TICKS,
        "q85_prefix_cap_ticks": EXPECTED_Q85_PREFIX_CAP_TICKS,
        "q86_prefix_cap_ticks_if_attempted": EXPECTED_Q86_PREFIX_CAP_TICKS,
        "terminal_branch": branch,
        "q85_and_q86_outcomes_precommitted": False,
    }


def execution_components(parent_components: Any, self_sha: str) -> list[Dict[str, Any]]:
    if parent_components != list(EXPECTED_PARENT_EXECUTION_COMPONENTS):
        raise RuntimeError("M q86 raw execution component closure drift")
    if not is_canonical_sha256(self_sha):
        raise RuntimeError("M q86 component self digest drift")
    components = [
        {
            "relative_path": SELF_NAME,
            "role": "M_k589824_c32_q86_fresh_same_byte_screen",
            "sha256": self_sha,
        },
        {
            "relative_path": EXECUTION_PARENT_NAME,
            "role": "M_k589824_c32_q84_same_byte_private_execution_parent",
            "sha256": EXPECTED_EXECUTION_PARENT_SHA256,
        },
    ]
    saw_root = saw_v6 = saw_v2 = False
    forbidden = {ROUTE_PREDECESSOR_TRANSCRIPT_NAME}
    for original in parent_components:
        item = dict(original)
        path = item.get("relative_path")
        if path in forbidden:
            raise RuntimeError("q84 canonical became an execution component")
        if path == CONTROL_FLOW_ROOT_NAME:
            if item.get("sha256") != EXPECTED_CONTROL_FLOW_ROOT_SHA256:
                raise RuntimeError("raw control-flow root component pin drift")
            saw_root = True
            continue
        if path == V6_BASELINE_CONFIGURATION_NAME:
            item["role"] = "v6_baseline_configuration_before_q84_parent_override"
            saw_v6 = True
        elif path == V2_ARITHMETIC_NAME:
            item["role"] = "v2_arithmetic_bytes_beneath_k589824_wrapper"
            saw_v2 = True
        components.append(item)
        if path == V2_ARITHMETIC_NAME:
            components.append({
                "relative_path": KERNEL_WRAPPER_NAME,
                "role": "k589824_capability_override_provider",
                "sha256": EXPECTED_KERNEL_WRAPPER_SHA256,
            })
    if not (saw_root and saw_v6 and saw_v2):
        raise RuntimeError("M q86 raw component set incomplete")
    paths = [item["relative_path"] for item in components]
    if len(paths) != len(set(paths)) or len(components) != 11:
        raise RuntimeError("M q86 final component cardinality drift")
    return components


def configuration_reference(parent: Any) -> Dict[str, Any]:
    reference = parent.configuration_reference()
    if type(reference) is not dict:
        raise RuntimeError("M q86 parent configuration reference drift")
    return dict(reference)


def configuration_override(parent: Any, baseline_m: Tuple[int, ...]) -> Dict[str, Any]:
    parent_override = parent.configuration_override(baseline_m)
    return {
        "override_id": "magnetization_k589824_c32_q86_configuration_override_v1",
        "execution_parent_configuration_override": parent_override,
        "execution_parent_configuration_override_sha256": sha256(
            canonical_bytes(parent_override)
        ),
        "incremental_route_override_from_k589824_c32_q84": {
            "predecessor_candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 32, "after": 32},
            "candidate_ladder_added": [],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {},
            "predecessor_configuration_override_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
            ),
        },
        "effective_candidate_K_values": list(M_CANDIDATES),
        "effective_policy_caps": {
            **POLICY_CAPS_BASE,
            "max_candidate_count": len(M_CANDIDATES),
        },
        "candidate_policy_and_kernel_capability_unchanged_on_route": True,
        "overridden_fields_on_incremental_route": [
            "screen_horizon_checkpoint_count"
        ],
    }


def kernel_capability_override(
    parent: Any,
    wrapper_sha: str,
    manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    if wrapper_sha != EXPECTED_KERNEL_WRAPPER_SHA256:
        raise RuntimeError("M q86 wrapper pin drift")
    parent_override = parent.kernel_capability_override(wrapper_sha, manifest)
    return {
        "relative_path": KERNEL_WRAPPER_NAME,
        "source_sha256": wrapper_sha,
        "role": "unchanged_k589824_capability_override_provider",
        "execution_parent_kernel_capability_override": parent_override,
        "execution_parent_kernel_capability_override_sha256": sha256(
            canonical_bytes(parent_override)
        ),
        "effective_kernel_capability_limits": (
            EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        ),
        "incremental_route_changes_from_k589824_c32_q84": {},
        "execution_source_layers": [KERNEL_WRAPPER_NAME, V2_ARITHMETIC_NAME],
        "q84_canonical_is_execution_source": False,
        "v2_arithmetic_module_mutated_by_screen": False,
    }


def parent_horizon_override(context: Mapping[str, Any]) -> Dict[str, Any]:
    raw = context.get("raw_control_flow_horizon_override")
    if type(raw) is not dict:
        raise RuntimeError("M q86 raw horizon adapter evidence drift")
    changed = raw.get("changed_fields")
    if changed != ["MODE_CONFIG.magnetization.horizon_checkpoint_count"]:
        raise RuntimeError("M q86 raw horizon adapter changed extra fields")
    raw_delta = raw.get("semantic_delta", {}).get(
        "MODE_CONFIG.magnetization.horizon_checkpoint_count"
    )
    if raw_delta != {"before": 80, "after": EXTENDED_HORIZON}:
        raise RuntimeError("M q86 raw horizon adapter semantic delta drift")
    if context.get("execution_parent_private_entrypoint_called") is not True:
        raise RuntimeError("M q86 q84 private entrypoint evidence drift")
    if context.get("q84_canonical_loaded_before_replay") is not False:
        raise RuntimeError("M q86 q84 canonical was loaded before replay")
    if context.get("execution_parent_route_loader_suppressed") is not True:
        raise RuntimeError("M q86 q84 parent route-loader suppression drift")
    return {
        "override_id": "magnetization_q84_parent_to_q86_horizon_override_v1",
        "parent_relative_path": EXECUTION_PARENT_NAME,
        "parent_source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
        "parent_module_isolated": True,
        "parent_source_bytes_changed": False,
        "changed_fields": ["screen_horizon_checkpoint_count"],
        "semantic_delta": {
            "screen_horizon_checkpoint_count": {
                "before": BASE_PARENT_HORIZON,
                "after": EXTENDED_HORIZON,
            }
        },
        "candidate_K_values_changed": False,
        "policy_caps_changed": False,
        "kernel_capability_limits_changed": False,
        "execution_parent_private_entrypoint_called": context.get(
            "execution_parent_private_entrypoint_called"
        ),
        "q84_canonical_loaded_before_replay": context.get(
            "q84_canonical_loaded_before_replay"
        ),
        "execution_parent_route_loader_suppressed": context.get(
            "execution_parent_route_loader_suppressed"
        ),
    }


def validate_and_relabel(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
    route_reference: Mapping[str, Any],
    parent: Any,
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("M q86 relabel requires fresh same-byte self execution")
    require_exact_keys(result, EXPECTED_PARENT_RESULT_KEYS, "M q86 raw parent result")
    handoff = validate_replay_handoff(result, predecessor)
    old_components = result.get("screen_execution_components")
    if result.get("screen_execution_components_sha256") != sha256(
        canonical_bytes(old_components)
    ):
        raise RuntimeError("M q86 raw component digest drift")
    old_configuration = result.get("configuration_reference")
    if result.get("configuration_reference_sha256") != sha256(
        canonical_bytes(old_configuration)
    ):
        raise RuntimeError("M q86 raw configuration digest drift")
    old_transform = result.get("checkpoint_transform")
    old_transform_sha = result.get("checkpoint_transform_sha256")
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("M q86 raw transform digest drift")
    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = execution_components(old_components, self_sha)
    baseline_reference = configuration_reference(parent)
    config = configuration_override(parent, tuple(context["baseline_m"]))
    capability = kernel_capability_override(
        parent,
        context["wrapper_sha"],
        context["wrapper_manifest"],
    )
    horizon = parent_horizon_override(context)
    transform = {
        "transform_id": "magnetization_four_gate_k589824_c32_q86_v1",
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": old_transform_sha,
        "execution_parent_q84_transform_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256
        ),
        "q84_execution_parent_replaces_raw_root_component_at_outer_boundary": True,
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "q85_and_q86_outcomes_precommitted": False,
        "incremental_route_semantic_delta": {
            "candidate_K_values_changed": False,
            "policy_caps_changed": False,
            "kernel_capability_limits_changed": False,
            "horizon_checkpoint_count": {"before": 84, "after": 86},
        },
        "overridden_semantics": ["magnetization_horizon_checkpoint_count"],
    }
    parent_custody = validate_parent_source_custody(result.get("source_custody"))
    custody = expected_final_source_custody(self_sha)
    if parent_custody != {
        path: custody[path] for path in EXPECTED_PARENT_SOURCE_CUSTODY
    }:
        raise RuntimeError("M q86 parent custody changed during relabel")
    if len(custody) != 10:
        raise RuntimeError("M q86 final source custody cardinality drift")
    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k589824_c32_q86_screen_v1"
        ),
        "screen_source_sha256": self_sha,
        "same_byte_self_execution": True,
        "control_flow_owned_by_screen": False,
        "control_flow_owned_by_verified_parent": True,
        "control_flow_parent_relative_path": EXECUTION_PARENT_NAME,
        "control_flow_parent_source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
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
        "kernel_capability_wrapper_source_sha256": EXPECTED_KERNEL_WRAPPER_SHA256,
        "kernel_capability_wrapper_compiled_from_verified_bytes": True,
        "kernel_capability_wrapper_module_isolated": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(canonical_bytes(components)),
        "configuration_reference": baseline_reference,
        "configuration_reference_sha256": sha256(canonical_bytes(baseline_reference)),
        "configuration_override": config,
        "configuration_override_sha256": sha256(canonical_bytes(config)),
        "kernel_capability_override": capability,
        "kernel_capability_override_sha256": sha256(canonical_bytes(capability)),
        "parent_horizon_override": horizon,
        "parent_horizon_override_sha256": sha256(canonical_bytes(horizon)),
        "route_predecessor_reference": dict(route_reference),
        "route_predecessor_reference_sha256": sha256(
            canonical_bytes(route_reference)
        ),
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
    require_exact_keys(
        result,
        EXPECTED_RELABELLED_RESULT_KEYS,
        "M q86 relabelled top-level result",
    )
    if result["source_custody"] != expected_final_source_custody(self_sha):
        raise RuntimeError("M q86 final source custody closure drift")
    return result


def _run_verified(repo: Path) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("M q86 screen requires fresh same-byte self execution")
    validate_local_configuration()
    repo = repo.resolve()
    parent = load_execution_parent(repo)
    result, context = execute_parent_replay(parent, repo)
    predecessor, route_reference = load_route_reference(repo)
    return validate_and_relabel(
        result,
        predecessor,
        route_reference,
        parent,
        context,
    )


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_magnetization_k589824_c32_q86_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("M q86 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("M q86 transcript exceeds output byte cap")
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
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
