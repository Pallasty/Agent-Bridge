#!/usr/bin/env python3
"""Source-pinned, diagnostic-only M K606208/C33 q88 screen.

The exact K606208/C33 q86 screen is compiled from pinned same bytes and its
private entrypoint owns a complete replay from checkpoint one.  Its execution
policy, candidate ladder, and wrapped arithmetic capability are unchanged;
only the diagnostic horizon changes from q86 to q88.  The q86 canonical
transcript is loaded only after replay as exact q1--86 prefix evidence.  It is
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
    "k606208_c33_q88_screen.py"
)
EXECUTION_PARENT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k606208_c33_q86_screen.py"
)
CONTROL_FLOW_ROOT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k606208_c33.py"
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k606208_c33_q86_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k606208_c33_q88_transcript.json"
)

EXPECTED_EXECUTION_PARENT_SHA256 = (
    "86e5148a51cb70d2aab21d770ad2b21928caf6e2818786542b287be7c8d02d27"
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
    "447cb116c2ca977cb2711b08e64e5795728907b8c4033bd1eb38211bf63cf558"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "fc649a90aa42429d7d746f40bdc7dfe109f1dc6921b46beb8c3396cc3012e875"
)
EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE = 785_288
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "fd0063a55e05d4d6233e3aa10a6ec760ad6e8326ed4ac967f36903ad644b1f99"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "0f209e6373265ab01f092c59ac449f75114765bca50d63029b49f2b37c64c383"
)
EXPECTED_ROUTE_PREDECESSOR_Q86_RECORD_SHA256 = (
    "19f5c0f51d5c38217a0eac9c26891c6578919c5c6f6eae0808d1e41705ee2c56"
)
EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256 = (
    "0c8dd197b62a325eb0de5bba399ab7ae3e7fb1397db410f37ffc02ae18765434"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_SHA256 = (
    "e421d9c9c57e5dc3f7d5aa3500e9e9776f588bfb65df1a03ccd9292df404e5f2"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256 = (
    "ae5002b1328fa2628d40c9e00424c84547c31d207e12be781af38e0621a37625"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_OVERRIDE_SHA256 = (
    "da7168a289c0a4cf125fb3ce69deb0f2baf32dcce73955b6355a0fecf401079b"
)
EXPECTED_ROUTE_PREDECESSOR_PARENT_HORIZON_OVERRIDE_SHA256 = (
    "f104f9d58b66f3941a9c44afa30a18fa3fc867c04a6015f5752d8826b6900949"
)
EXPECTED_ROUTE_PREDECESSOR_ROUTE_REFERENCE_SHA256 = (
    "e9e275f330be0f0bb2144bbe5f41eefd9b4e109597a334c10a34b26d8178f283"
)
EXPECTED_ROUTE_PREDECESSOR_HANDOFF_SHA256 = (
    "ad0cd1cfe671f59ddada311dc9185b0e2cc4a0415e15aa0f8f03972c9e892084"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "67d7f488b942c6b354fcd88b5d78c57abc4d77fdc00ab66d59b24ea1c336bb27"
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
BASE_PARENT_HORIZON = 86
EXTENDED_HORIZON = 88
K606208 = 606_208
M_CANDIDATES = tuple(range(81_920, 606_208 + 1, 16_384))
EXPECTED_CANDIDATE_SHA256 = (
    "8c0105608be381ce3ecaeb6178d25c0eda50713e54aa22f734b964bbd5464f86"
)
EXPECTED_Q86_RETAINED_COUNT = 589_824
EXPECTED_Q86_RETAINED_EXPANSION_SHA256 = (
    "81892d7c339a3094dbe40a531b23ddcfe642804e1c6e8f1da6ca57fa4915a59e"
)
EXPECTED_Q86_E_AFTER_TICKS = "1700472573422099"
EXPECTED_Q87_PREFIX_CAP_TICKS = "1700590901881716"
EXPECTED_Q88_PREFIX_CAP_TICKS = "1700695433287388"
EXPECTED_EXTENSION_CHECKPOINT_ANCHORS = {
    87: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 30,
        "gate_batch_sha256": (
            "4b60608343a13e9927dd20cd4bb7314e67b1432465e27d186c117935402801e7"
        ),
    },
    88: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 31,
        "gate_batch_sha256": (
            "7f8c6a2dd155412a27369e1fa8402c37127c6eadf12e4fa59ba442d345e8eaf7"
        ),
    },
}

POLICY_CAPS_BASE = {
    "max_candidate_K": K606208,
    "max_output_terms_if_successful": K606208,
    "max_single_expansion_terms": 786_432,
    "max_digest_terms": 786_432,
    "max_term_gate_visits": 536_870_912,
    "max_expansion_coefficient_tick_bits": 192,
    "max_trigonometric_tick_bits": 66,
    "max_product_bits": 384,
    "max_suffix_accumulator_bits": 224,
}
EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS = {
    "max_candidate_count": 33,
    "max_digest_terms": 1_048_576,
    "max_expansion_coefficient_tick_bits": 192,
    "max_product_bits": 384,
    "max_retained_K": K606208,
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

UPSTREAM_PARENT_RESULT_KEYS = frozenset({
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
RESOURCE_POLICY_ABORT_TOP_LEVEL_KEYS = frozenset({
    "resource_policy_abort",
    "resource_policy_abort_sha256",
})
RESOURCE_POLICY_ABORT_KEYS = frozenset({
    "schema_version",
    "abort_id",
    "abort_kind",
    "abort_frame_local_schema_id",
    "exception_type",
    "exception_message",
    "exception_args",
    "exception_source_role",
    "exception_chained_from_exact_parent_helper",
    "control_flow_root_source_sha256",
    "helper_source_sha256",
    "kernel_source_sha256",
    "checkpoint_index_zero_based",
    "checkpoint_number_one_based",
    "stage_index",
    "stage_group",
    "batch_in_stage",
    "gate_occurrence_first_zero_based",
    "gate_occurrence_last_zero_based",
    "gate_batch_sha256",
    "input_expansion_count",
    "input_expansion_sha256",
    "pretruncation_expansion_count",
    "observed_term_count",
    "policy_max_single_expansion_terms",
    "kernel_max_single_expansion_terms",
    "enforced_term_cap",
    "observed_excess_terms",
    "policy_relation",
    "gate_batch_propagation_started",
    "gate_batch_propagation_completed",
    "policy_cap_check_reached",
    "kernel_cap_violation_triggered",
    "live_expansion_snapshot_available",
    "attempted_checkpoint_pretruncation_digest_computed",
    "attempted_checkpoint_ranking_performed",
    "attempted_checkpoint_candidate_rows_constructed",
    "attempted_checkpoint_selection_performed",
    "attempted_checkpoint_commit_performed",
    "attempted_checkpoint_record_constructed",
    "attempted_checkpoint_partial_expansion_committed",
    "last_committed_record_sha256",
    "peak_live_terms_this_checkpoint",
    "peak_live_terms_cumulative",
    "term_gate_visits_increment",
    "term_gate_visits_cumulative",
    "rounding_increment_scaled_ticks_squared",
    "rounding_cumulative_scaled_ticks_squared",
    "maximum_expansion_coefficient_tick_bits",
    "maximum_product_bits",
})
EXPECTED_PARENT_RESULT_KEYS = (
    UPSTREAM_PARENT_RESULT_KEYS | RESOURCE_POLICY_ABORT_TOP_LEVEL_KEYS
)
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
    if len(M_CANDIDATES) != 33 or M_CANDIDATES[-1] != K606208:
        raise RuntimeError("M q88 candidate ladder drift")
    if any(left >= right for left, right in zip(M_CANDIDATES, M_CANDIDATES[1:])):
        raise RuntimeError("M q88 candidate order drift")
    if sha256(canonical_bytes(list(M_CANDIDATES))) != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("M q88 candidate digest drift")
    if POLICY_CAPS_BASE["max_candidate_K"] != K606208:
        raise RuntimeError("M q88 policy maximum drift")
    if POLICY_CAPS_BASE["max_output_terms_if_successful"] != K606208:
        raise RuntimeError("M q88 output cap drift")
    if EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS["max_retained_K"] != K606208:
        raise RuntimeError("M q88 kernel retained cap drift")
    if BASE_PARENT_HORIZON != 86 or EXTENDED_HORIZON != 88:
        raise RuntimeError("M q88 horizon contract drift")
    sizes = {
        "raw": len(EXPECTED_PARENT_RESULT_KEYS),
        "final": len(EXPECTED_RELABELLED_RESULT_KEYS),
        "success": len(SUCCESS_RECORD_KEYS),
        "failure": len(FAILURE_RECORD_KEYS),
        "row": len(CANDIDATE_RECORD_KEYS),
        "resource_abort": len(RESOURCE_POLICY_ABORT_KEYS),
    }
    if sizes != {
        "raw": 67,
        "final": 96,
        "success": 37,
        "failure": 31,
        "row": 7,
        "resource_abort": 50,
    }:
        raise RuntimeError("M q88 closed schema size drift")


def load_execution_parent(repo: Path) -> Any:
    path = checked_repo_file(repo, EXECUTION_PARENT_NAME)
    payload = bounded_bytes(path, MAX_PINNED_SOURCE_BYTES)
    if sha256(payload) != EXPECTED_EXECUTION_PARENT_SHA256:
        raise RuntimeError("M q86 execution-parent source pin drift")
    parent = compile_isolated(
        "pinned_m_k606208_c33_q86_parent_for_q88",
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
        "EXPECTED_WRAPPED_KERNEL_LIMITS": (
            EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        ),
    }
    for field, value in expected.items():
        if getattr(parent, field, None) != value:
            raise RuntimeError(f"M q86 execution-parent contract drift: {field}")
    if frozenset(parent.EXPECTED_PARENT_RESULT_KEYS) != EXPECTED_PARENT_RESULT_KEYS:
        raise RuntimeError("M q86 raw parent schema drift")
    if frozenset(parent.EXPECTED_RELABELLED_RESULT_KEYS) != (
        EXPECTED_RELABELLED_RESULT_KEYS
    ):
        raise RuntimeError("M q86 final parent schema drift")
    parent.validate_local_configuration()
    return parent


def build_resource_abort_parent_result(
    execution_parent: Any,
    control_parent: Any,
    kernel: Any,
    exception: BaseException,
) -> Dict[str, Any]:
    """Close a q87/q88 resource exception from the exact raw parent frame."""

    expected_run = execution_parent._require_abort_parent_authority(
        control_parent
    )
    traceback_items = execution_parent._traceback_items(exception)
    run_items = [
        item
        for item in traceback_items
        if item.tb_frame.f_code is expected_run.__code__
    ]
    if len(run_items) != 1:
        raise RuntimeError("M q88 abort parent traceback authority drift")
    run_item = run_items[0]
    local = run_item.tb_frame.f_locals
    required_locals = {
        "mode", "v6_configuration", "kernel", "root", "source_custody",
        "root_before", "boundary_custody", "sequence", "transform",
        "helper_config", "candidates", "caps", "counter", "E_input",
        "cumulative", "remaining_steps", "denominator", "horizon",
        "records", "selected_history", "failure", "horizon_reached",
        "gate_index", "stage_index", "stage", "batch_start",
        "checkpoint_index", "checkpoint_number", "batch", "input_count",
        "input_sha", "visits_before", "rounding_before",
    }
    if not required_locals <= set(local):
        raise RuntimeError("M q88 abort parent frame local schema drift")
    if local.get("kernel") is not kernel:
        raise RuntimeError("M q88 abort kernel identity drift")

    helper = local.get("helper")
    enforce_policy_caps = getattr(helper, "enforce_policy_caps", None)
    if (
        type(helper) is not types.ModuleType
        or type(getattr(helper, "_VERIFIED_SELF_SOURCE_BYTES", None))
        is not bytes
        or sha256(helper._VERIFIED_SELF_SOURCE_BYTES)
        != execution_parent.EXPECTED_V2_HELPER_SHA256
        or type(enforce_policy_caps) is not types.FunctionType
        or enforce_policy_caps.__globals__ is not helper.__dict__
        or enforce_policy_caps.__module__ != helper.__name__
        or enforce_policy_caps.__code__.co_filename != helper.__file__
    ):
        raise RuntimeError("M q88 abort helper authority drift")

    records = local["records"]
    history = local["selected_history"]
    candidates = local["candidates"]
    caps = local["caps"]
    counter = local["counter"]
    checkpoint = local["checkpoint_number"]
    if type(checkpoint) is not int or checkpoint not in (87, 88):
        raise RuntimeError("M q88 abort checkpoint number drift")
    checkpoint_index = checkpoint - 1
    expected_gate_index = 4 * checkpoint_index
    if (
        local["mode"] != MODE
        or type(records) is not list
        or len(records) != checkpoint_index
        or type(history) is not list
        or len(history) != checkpoint_index
        or local["checkpoint_index"] != checkpoint_index
        or local["horizon"] != EXTENDED_HORIZON
        or local["failure"] is not None
        or local["horizon_reached"] is not False
        or local["gate_index"] != expected_gate_index
    ):
        raise RuntimeError("M q88 abort checkpoint boundary drift")
    previous = records[-1]
    require_exact_keys(
        previous,
        SUCCESS_RECORD_KEYS,
        f"M q88 abort q{checkpoint - 1} success",
    )
    selected_index = previous.get("selected_candidate_index")
    selected_K = previous.get("selected_K")
    if (
        previous.get("checkpoint_number_one_based") != checkpoint - 1
        or previous.get("status") != "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
        or type(selected_index) is not int
        or not 0 <= selected_index < len(M_CANDIDATES)
        or type(selected_K) is not int
        or selected_K != M_CANDIDATES[selected_index]
        or previous.get("retained_expansion_count")
        != previous.get("selected_effective_retained_count")
        or history[-1] != selected_K
    ):
        raise RuntimeError("M q88 abort previous commit drift")
    if tuple(candidates) != M_CANDIDATES:
        raise RuntimeError("M q88 abort candidate ladder drift")
    expected_caps = {
        **POLICY_CAPS_BASE,
        "max_candidate_count": len(M_CANDIDATES),
    }
    if not exact_value_equal(caps, expected_caps):
        raise RuntimeError("M q88 abort policy caps drift")
    if kernel.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS:
        raise RuntimeError("M q88 abort kernel limits drift")

    batch = local["batch"]
    stage = local["stage"]
    if type(batch) is not list or len(batch) != 4 or type(stage) is not dict:
        raise RuntimeError("M q88 abort gate batch schema drift")
    observed_anchor = {
        "stage_index": local["stage_index"],
        "stage_group": stage.get("group"),
        "batch_in_stage": local["batch_start"] // 4,
        "gate_batch_sha256": helper.gate_batch_sha256(batch),
    }
    if not exact_value_equal(
        observed_anchor,
        EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint],
    ):
        raise RuntimeError("M q88 abort checkpoint anchor drift")
    if local["input_count"] != previous.get("retained_expansion_count"):
        raise RuntimeError("M q88 abort input count continuity drift")
    if local["input_sha"] != previous.get("retained_expansion_sha256"):
        raise RuntimeError("M q88 abort input digest continuity drift")

    policy_cap = caps["max_single_expansion_terms"]
    kernel_cap = kernel.RESOURCE_LIMITS["max_single_expansion_terms"]
    pre_count = None
    observed_count = None
    propagation_completed = None
    policy_check_reached = None
    kernel_violation_triggered = None
    snapshot_available = None
    exception_source_role = None
    chained_from_helper = None
    abort_kind = None
    local_schema_id = None
    policy_relation = None
    enforced_cap = None

    helper_messages = {
        "design policy live-term cap exceeded": (
            "final_live_terms",
            301,
            frozenset({"kernel", "counter", "term_count", "caps"}),
        ),
        "design policy transient live-term cap exceeded": (
            "transient_live_terms",
            313,
            frozenset({
                "kernel", "counter", "term_count", "caps",
                "checks", "key", "observed",
            }),
        ),
    }
    if type(exception) is RuntimeError and exception.args in (
        ("design policy live-term cap exceeded",),
        ("design policy transient live-term cap exceeded",),
    ):
        message = exception.args[0]
        abort_kind, helper_line, expected_helper_locals = helper_messages[
            message
        ]
        helper_items = [
            item
            for item in traceback_items
            if item.tb_frame.f_code is enforce_policy_caps.__code__
        ]
        if (
            len(helper_items) != 1
            or traceback_items[-1] is not helper_items[0]
            or run_item.tb_lineno != 589
            or helper_items[0].tb_lineno != helper_line
            or frozenset(helper_items[0].tb_frame.f_locals)
            != expected_helper_locals
        ):
            raise RuntimeError("M q88 helper abort traceback/local schema drift")
        helper_local = helper_items[0].tb_frame.f_locals
        if (
            helper_local["kernel"] is not kernel
            or helper_local["counter"] is not counter
            or helper_local["caps"] is not caps
            or type(helper_local["term_count"]) is not int
            or helper_local["term_count"] < 0
        ):
            raise RuntimeError("M q88 helper abort argument identity drift")
        pre_count = helper_local["term_count"]
        if (
            type(local.get("pre_count")) is not int
            or local["pre_count"] != pre_count
            or type(local.get("expansion")) is not dict
            or len(local["expansion"]) != pre_count
        ):
            raise RuntimeError("M q88 helper abort pretruncation binding drift")
        propagation_completed = True
        policy_check_reached = True
        kernel_violation_triggered = False
        snapshot_available = True
        exception_source_role = "exact_parent_helper"
        chained_from_helper = True
        enforced_cap = policy_cap
        if abort_kind == "final_live_terms":
            observed_count = pre_count
            local_schema_id = "helper_final_live_terms_v1"
            policy_relation = (
                "pretruncation_expansion_count>"
                "policy_max_single_expansion_terms"
            )
            if not pre_count > policy_cap:
                raise RuntimeError("M q88 final-live abort cap relation drift")
        else:
            observed_count = counter.window_peak_live_terms
            local_schema_id = "helper_transient_live_terms_v1"
            policy_relation = (
                "peak_live_terms_this_checkpoint>"
                "policy_max_single_expansion_terms>="
                "pretruncation_expansion_count"
            )
            if not pre_count <= policy_cap < observed_count:
                raise RuntimeError("M q88 transient-live abort cap relation drift")
    elif (
        type(exception) is getattr(kernel, "SchemaError", None)
        and exception.args == ("v2 single-expansion term cap exceeded",)
    ):
        if run_item.tb_lineno != 587:
            raise RuntimeError("M q88 kernel abort parent line drift")
        observed_count = execution_parent._exact_kernel_overflow_count(
            kernel,
            counter,
            traceback_items,
        )
        if observed_count <= kernel_cap:
            raise RuntimeError("M q88 kernel abort cap relation drift")
        if local.get("pre_count") != previous["pretruncation_expansion_count"]:
            raise RuntimeError("M q88 kernel abort stale pre_count binding drift")
        propagation_completed = False
        policy_check_reached = False
        kernel_violation_triggered = True
        snapshot_available = False
        exception_source_role = "exact_wrapped_v2_kernel"
        chained_from_helper = False
        abort_kind = "kernel_single_expansion_terms"
        local_schema_id = "kernel_observe_count_before_pre_count_assignment_v1"
        policy_relation = (
            "observed_term_count>kernel_max_single_expansion_terms_"
            "before_pretruncation_assignment"
        )
        enforced_cap = kernel_cap
    else:
        raise RuntimeError("M q88 resource abort exception identity drift")

    if (
        type(observed_count) is not int
        or observed_count <= enforced_cap
        or counter.peak_live_terms < observed_count
        or counter.window_peak_live_terms < observed_count
        or (
            abort_kind != "kernel_single_expansion_terms"
            and observed_count > kernel_cap
        )
    ):
        raise RuntimeError("M q88 abort observed live-term ledger drift")
    root_after = kernel.root_global_snapshot(local["root"])
    if not exact_value_equal(local["root_before"], root_after):
        raise RuntimeError("M q88 abort changed root arithmetic globals")

    message = exception.args[0]
    abort = {
        "schema_version": 1,
        "abort_id": "M_k606208_c33_q88_policy_resource_abort_v1",
        "abort_kind": abort_kind,
        "abort_frame_local_schema_id": local_schema_id,
        "exception_type": type(exception).__name__,
        "exception_message": message,
        "exception_args": [message],
        "exception_source_role": exception_source_role,
        "exception_chained_from_exact_parent_helper": chained_from_helper,
        "control_flow_root_source_sha256": EXPECTED_CONTROL_FLOW_ROOT_SHA256,
        "helper_source_sha256": execution_parent.EXPECTED_V2_HELPER_SHA256,
        "kernel_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "checkpoint_index_zero_based": checkpoint_index,
        "checkpoint_number_one_based": checkpoint,
        **observed_anchor,
        "gate_occurrence_first_zero_based": expected_gate_index,
        "gate_occurrence_last_zero_based": expected_gate_index + 3,
        "input_expansion_count": local["input_count"],
        "input_expansion_sha256": local["input_sha"],
        "pretruncation_expansion_count": pre_count,
        "observed_term_count": observed_count,
        "policy_max_single_expansion_terms": policy_cap,
        "kernel_max_single_expansion_terms": kernel_cap,
        "enforced_term_cap": enforced_cap,
        "observed_excess_terms": observed_count - enforced_cap,
        "policy_relation": policy_relation,
        "gate_batch_propagation_started": True,
        "gate_batch_propagation_completed": propagation_completed,
        "policy_cap_check_reached": policy_check_reached,
        "kernel_cap_violation_triggered": kernel_violation_triggered,
        "live_expansion_snapshot_available": snapshot_available,
        "attempted_checkpoint_pretruncation_digest_computed": False,
        "attempted_checkpoint_ranking_performed": False,
        "attempted_checkpoint_candidate_rows_constructed": False,
        "attempted_checkpoint_selection_performed": False,
        "attempted_checkpoint_commit_performed": False,
        "attempted_checkpoint_record_constructed": False,
        "attempted_checkpoint_partial_expansion_committed": False,
        "last_committed_record_sha256": sha256(canonical_bytes(previous)),
        "peak_live_terms_this_checkpoint": counter.window_peak_live_terms,
        "peak_live_terms_cumulative": counter.peak_live_terms,
        "term_gate_visits_increment": (
            counter.term_gate_visits - local["visits_before"]
        ),
        "term_gate_visits_cumulative": counter.term_gate_visits,
        "rounding_increment_scaled_ticks_squared": str(
            counter.multiplication_rounding_l1_scaled_ticks_squared
            - local["rounding_before"]
        ),
        "rounding_cumulative_scaled_ticks_squared": str(
            counter.multiplication_rounding_l1_scaled_ticks_squared
        ),
        "maximum_expansion_coefficient_tick_bits": (
            counter.maximum_expansion_coefficient_tick_bits
        ),
        "maximum_product_bits": counter.maximum_product_bits,
    }
    require_exact_keys(
        abort,
        RESOURCE_POLICY_ABORT_KEYS,
        "M q88 resource-policy abort",
    )

    raw_parent_sha = sha256(control_parent._VERIFIED_SELF_SOURCE_BYTES)
    components = control_parent.execution_components(
        MODE,
        raw_parent_sha,
        local["source_custody"],
        local["boundary_custody"],
    )
    candidate_sha = sha256(canonical_bytes(list(candidates)))
    configuration_reference = {
        "relative_path": control_parent.V6_CONFIGURATION_NAME,
        "source_sha256": control_parent.EXPECTED_V6_CONFIGURATION_SHA256,
        "role": "candidates_and_caps_reference_only",
        "fields_adopted": [
            f"MODE_CONFIG.{MODE}.candidates",
            "POLICY_CAPS_BASE",
        ],
        "candidate_K_values_sha256": candidate_sha,
        "policy_caps_base_sha256": control_parent.EXPECTED_V6_CAPS_SHA256,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }
    records_copy = copy.deepcopy(records)
    history_copy = list(history)
    result = {
        "schema_version": 1,
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
        ),
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_terminal_condition": "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
        "observable_id": local["helper_config"]["observable_id"],
        "input_step_index": local["helper_config"]["input_step_index"],
        "attempted_child_step_index": local["helper_config"][
            "child_step_index"
        ],
        "screen_source_sha256": raw_parent_sha,
        "same_byte_self_execution": True,
        "v2_helper_source_sha256": control_parent.EXPECTED_V2_HELPER_SHA256,
        "v2_helper_compiled_from_verified_bytes": True,
        "v2_helper_module_isolated": True,
        "v2_run_entrypoint_called": False,
        "v6_configuration_source_sha256": (
            control_parent.EXPECTED_V6_CONFIGURATION_SHA256
        ),
        "v6_configuration_compiled_from_verified_bytes": True,
        "v6_configuration_module_isolated": True,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
        "control_flow_owned_by_screen": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(
            canonical_bytes(components)
        ),
        "configuration_reference": configuration_reference,
        "configuration_reference_sha256": sha256(
            canonical_bytes(configuration_reference)
        ),
        "checkpoint_transform": copy.deepcopy(local["transform"]),
        "checkpoint_transform_sha256": sha256(
            canonical_bytes(local["transform"])
        ),
        "arithmetic_kernel_commit": helper.KERNEL_COMMIT,
        "source_custody": {
            control_parent.V2_HELPER_NAME: control_parent.EXPECTED_V2_HELPER_SHA256,
            control_parent.V6_CONFIGURATION_NAME: (
                control_parent.EXPECTED_V6_CONFIGURATION_SHA256
            ),
            **local["source_custody"],
        },
        "parent_expected_witness_sha256": local["helper_config"][
            "parent_expected_witness_sha256"
        ],
        "input_boundary_custody": copy.deepcopy(local["boundary_custody"]),
        "input_cumulative_drop_ticks": str(local["E_input"]),
        "maximum_cumulative_drop_ticks": str(helper.MAXIMUM_DROP_TICKS),
        "remaining_mapped_steps_including_attempt": local["remaining_steps"],
        "future_checkpoint_denominator": local["denominator"],
        "prefix_cap_formula": (
            f"E{local['helper_config']['input_step_index']}+floor(q*(B-"
            f"E{local['helper_config']['input_step_index']})/("
            f"{local['remaining_steps']}*"
            f"{control_parent.CHECKPOINTS_PER_MAPPED_STEP}))"
        ),
        "candidate_K_values": list(candidates),
        "candidate_K_values_sha256": candidate_sha,
        "candidate_policy_precommitted_at_probe_time": False,
        "selection_rule": (
            "first_candidate_whose_exact_ranked_suffix_drop_respects_"
            "current_prefix_cap"
        ),
        "single_propagation_and_single_ranking_per_checkpoint": True,
        "sequence": copy.deepcopy(local["sequence"]),
        "screen_horizon_checkpoint_count": local["horizon"],
        "horizon_checkpoint_attempted": checkpoint == EXTENDED_HORIZON,
        "horizon_reached_with_committed_checkpoint": False,
        "kernel_capability_limits": dict(kernel.RESOURCE_LIMITS),
        "proposed_policy_caps": dict(caps),
        "root_globals_before": copy.deepcopy(local["root_before"]),
        "root_globals_after": root_after,
        "root_globals_unchanged": True,
        "attempted_checkpoint_count": checkpoint,
        "completed_checkpoint_count": checkpoint - 1,
        "failure_checkpoint_included": False,
        "selected_K_history": history_copy,
        "selected_K_history_sha256": sha256(canonical_bytes(history_copy)),
        "records": records_copy,
        "records_sha256": sha256(canonical_bytes(records_copy)),
        "failure_record_sha256": None,
        "last_committed_cumulative_drop_ticks": str(local["cumulative"]),
        "observed_peak_single_expansion_terms": (
            abort["peak_live_terms_cumulative"]
        ),
        "observed_term_gate_visits_including_terminal_attempt": (
            abort["term_gate_visits_cumulative"]
        ),
        "observed_maximum_expansion_coefficient_tick_bits": (
            abort["maximum_expansion_coefficient_tick_bits"]
        ),
        "observed_maximum_product_bits": abort["maximum_product_bits"],
        "observed_rounding_cumulative_scaled_ticks_squared": abort[
            "rounding_cumulative_scaled_ticks_squared"
        ],
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
        "runtime_RSS_host_timestamp_and_float_fields_excluded": True,
        "resource_policy_abort": abort,
        "resource_policy_abort_sha256": sha256(canonical_bytes(abort)),
    }
    require_exact_keys(
        result,
        EXPECTED_PARENT_RESULT_KEYS,
        "M q88 structured resource-abort parent result",
    )
    return result


def execute_control_parent_with_structured_abort(
    execution_parent: Any,
    control_parent: Any,
    kernel: Any,
    repo: Path,
) -> Dict[str, Any]:
    try:
        return execution_parent.normalize_completed_parent_result(
            control_parent._run_verified(repo, MODE)
        )
    except RuntimeError as exception:
        if type(exception) is not RuntimeError or exception.args not in (
            ("design policy live-term cap exceeded",),
            ("design policy transient live-term cap exceeded",),
        ):
            raise
        return build_resource_abort_parent_result(
            execution_parent,
            control_parent,
            kernel,
            exception,
        )
    except Exception as exception:
        if (
            type(exception) is not getattr(kernel, "SchemaError", None)
            or exception.args != ("v2 single-expansion term cap exceeded",)
        ):
            raise
        return build_resource_abort_parent_result(
            execution_parent,
            control_parent,
            kernel,
            exception,
        )


def execute_parent_replay(parent: Any, repo: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Call the exact q86 private entrypoint with only horizon semantics changed."""

    if type(parent) is not types.ModuleType:
        raise RuntimeError("M q88 execution parent is not an isolated module")
    parent.validate_local_configuration()
    originals = {
        "EXTENDED_HORIZON": parent.EXTENDED_HORIZON,
        "validate_local_configuration": parent.validate_local_configuration,
        "load_configured_v6_baseline": parent.load_configured_v6_baseline,
        "load_kernel_wrapper": parent.load_kernel_wrapper,
        "load_route_reference": parent.load_route_reference,
        "configure_parent_execution": parent.configure_parent_execution,
        "execute_parent_with_structured_abort": (
            parent.execute_parent_with_structured_abort
        ),
        "validate_and_relabel": parent.validate_and_relabel,
    }
    context: Dict[str, Any] = {
        "execution_parent_private_entrypoint_called": False,
        "q86_canonical_loaded_before_replay": False,
        "execution_parent_route_loader_suppressed": False,
        "execution_parent_abort_adapter_installed": False,
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
        context["q86_canonical_loaded_before_replay"] = False
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

    def execute_q88(control_parent, kernel, source_repo):
        context["execution_parent_abort_adapter_installed"] = True
        return execute_control_parent_with_structured_abort(
            parent,
            control_parent,
            kernel,
            source_repo,
        )

    try:
        parent.EXTENDED_HORIZON = EXTENDED_HORIZON
        parent.validate_local_configuration = lambda: None
        parent.load_configured_v6_baseline = capture_configuration
        parent.load_kernel_wrapper = capture_wrapper
        parent.load_route_reference = no_predecessor_load
        parent.configure_parent_execution = capture_horizon
        parent.execute_parent_with_structured_abort = execute_q88
        parent.validate_and_relabel = return_raw
        context["execution_parent_private_entrypoint_called"] = True
        result = parent._run_verified(repo.resolve())
    finally:
        for field, value in originals.items():
            setattr(parent, field, value)
    if type(result) is not dict:
        raise RuntimeError("M q88 execution parent returned a non-dict result")
    required_context = {
        "baseline_m",
        "wrapper_sha",
        "wrapper_manifest",
        "raw_control_flow_horizon_override",
        "execution_parent_route_loader_suppressed",
        "execution_parent_abort_adapter_installed",
    }
    if not required_context <= context.keys():
        raise RuntimeError("M q88 execution-parent adapter did not close context")
    if context["wrapper_sha"] != EXPECTED_KERNEL_WRAPPER_SHA256:
        raise RuntimeError("M q88 captured wrapper pin drift")
    if context["execution_parent_route_loader_suppressed"] is not True:
        raise RuntimeError("M q88 execution-parent route loader was not suppressed")
    if context["execution_parent_abort_adapter_installed"] is not True:
        raise RuntimeError("M q88 execution-parent abort adapter was not installed")
    return result, context


def load_route_reference(repo: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    screen_raw = bounded_bytes(
        checked_repo_file(repo, EXECUTION_PARENT_NAME),
        MAX_PINNED_SOURCE_BYTES,
    )
    if sha256(screen_raw) != EXPECTED_EXECUTION_PARENT_SHA256:
        raise RuntimeError("route q86 screen source pin drift")
    raw = bounded_bytes(
        checked_repo_file(repo, ROUTE_PREDECESSOR_TRANSCRIPT_NAME),
        MAX_ROUTE_TRANSCRIPT_BYTES,
    )
    if len(raw) != EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE:
        raise RuntimeError("route q86 canonical file-size drift")
    if sha256(raw) != EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256:
        raise RuntimeError("route q86 canonical file pin drift")
    try:
        transcript = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("route q86 canonical is invalid JSON") from exc
    if type(transcript) is not dict or raw != canonical_bytes(transcript):
        raise RuntimeError("route q86 transcript is not canonical JSON")
    require_exact_keys(
        transcript,
        EXPECTED_RELABELLED_RESULT_KEYS,
        "route q86 canonical top-level transcript",
    )
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k606208_c33_q86_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_horizon_checkpoint_count": BASE_PARENT_HORIZON,
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "attempted_checkpoint_count": 86,
        "completed_checkpoint_count": 86,
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": True,
        "resource_policy_abort": None,
        "resource_policy_abort_sha256": None,
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
            raise RuntimeError(f"route q86 canonical drift: {field}")
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
            raise RuntimeError(f"route q86 nested digest drift: {value_field}")
    records = transcript.get("records")
    history = transcript.get("selected_K_history")
    if type(records) is not list or len(records) != 86:
        raise RuntimeError("route q86 record count drift")
    if type(history) is not list or len(history) != 86:
        raise RuntimeError("route q86 history count drift")
    if sha256(canonical_bytes(records)) != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256:
        raise RuntimeError("route q86 record digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256:
        raise RuntimeError("route q86 history digest drift")
    q86 = records[-1]
    require_exact_keys(q86, SUCCESS_RECORD_KEYS, "route q86 terminal record")
    if sha256(canonical_bytes(q86)) != EXPECTED_ROUTE_PREDECESSOR_Q86_RECORD_SHA256:
        raise RuntimeError("route q86 terminal record digest drift")
    anchors = {
        "checkpoint_number_one_based": 86,
        "selected_candidate_index": 31,
        "selected_K": EXPECTED_Q86_RETAINED_COUNT,
        "retained_expansion_count": EXPECTED_Q86_RETAINED_COUNT,
        "retained_expansion_sha256": EXPECTED_Q86_RETAINED_EXPANSION_SHA256,
        "E_after_ticks": EXPECTED_Q86_E_AFTER_TICKS,
    }
    for field, value in anchors.items():
        if not exact_value_equal(q86.get(field), value):
            raise RuntimeError(f"route q86 terminal anchor drift: {field}")
    outer_transform = transcript["checkpoint_transform"]
    raw_transform = outer_transform.get(
        "physical_four_gate_control_flow_parent_transform"
    )
    raw_transform_sha = outer_transform.get(
        "physical_four_gate_control_flow_parent_transform_sha256"
    )
    if raw_transform_sha != EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256:
        raise RuntimeError("route q86 embedded raw transform pin drift")
    if sha256(canonical_bytes(raw_transform)) != raw_transform_sha:
        raise RuntimeError("route q86 embedded raw transform digest drift")
    reference = {
        "route_id": "magnetization_k606208_c33_q86_to_q88_v1",
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
            "q86_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q86_RECORD_SHA256,
            "compiled": False,
            "executed": False,
            "loaded_before_replay": False,
            "loaded_after_full_replay_as_exact_reference": True,
            "used_only_for_post_replay_q1_q86_prefix_validation": True,
            "propagation_input": False,
            "checkpoint_86_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
        },
        "incremental_semantic_delta": {
            "candidate_K_values_changed": False,
            "policy_caps_changed": False,
            "kernel_capability_limits_changed": False,
            "horizon_checkpoint_count": {"before": 86, "after": 88},
        },
    }
    return transcript, reference


def validate_parent_source_custody(value: Any) -> Dict[str, str]:
    require_exact_keys(
        value,
        frozenset(EXPECTED_PARENT_SOURCE_CUSTODY),
        "M q88 raw parent source custody",
    )
    for path, expected_sha in EXPECTED_PARENT_SOURCE_CUSTODY.items():
        if value.get(path) != expected_sha or not is_canonical_sha256(value.get(path)):
            raise RuntimeError(f"M q88 raw parent custody drift: {path}")
    return dict(value)


def expected_final_source_custody(self_sha: str) -> Dict[str, str]:
    if not is_canonical_sha256(self_sha):
        raise RuntimeError("M q88 self custody digest drift")
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
            EXPECTED_Q87_PREFIX_CAP_TICKS
            if checkpoint == 87
            else EXPECTED_Q88_PREFIX_CAP_TICKS
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
        minimum_K <= K606208
        or minimum_K > pre_count
        or excess != minimum_K - K606208
    ):
        raise RuntimeError(f"M q{checkpoint} failure excess-K drift")
    maximum_excess = parse_canonical_nonnegative_decimal(
        record["maximum_candidate_drop_excess_over_slack_ticks"],
        f"M q{checkpoint} failure maximum excess",
    )
    if maximum_excess != drops[-1] - slack or maximum_excess <= 0:
        raise RuntimeError(f"M q{checkpoint} failure cap excess drift")
    return None


def validate_resource_policy_abort(
    result: Mapping[str, Any],
    previous: Mapping[str, Any],
    checkpoint: int,
) -> Dict[str, Any] | None:
    abort = result.get("resource_policy_abort")
    abort_sha = result.get("resource_policy_abort_sha256")
    if abort is None:
        if abort_sha is not None:
            raise RuntimeError("M q88 null resource abort has a digest")
        return None
    require_exact_keys(
        abort,
        RESOURCE_POLICY_ABORT_KEYS,
        "M q88 resource-policy abort",
    )
    if abort_sha != sha256(canonical_bytes(abort)):
        raise RuntimeError("M q88 resource-policy abort digest drift")
    if checkpoint not in (87, 88):
        raise RuntimeError("M q88 resource abort checkpoint drift")
    require_exact_keys(
        previous,
        SUCCESS_RECORD_KEYS,
        f"M q{checkpoint} abort previous success",
    )
    expected = {
        "schema_version": 1,
        "abort_id": "M_k606208_c33_q88_policy_resource_abort_v1",
        "control_flow_root_source_sha256": EXPECTED_CONTROL_FLOW_ROOT_SHA256,
        "helper_source_sha256": (
            "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3"
        ),
        "kernel_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "checkpoint_index_zero_based": checkpoint - 1,
        "checkpoint_number_one_based": checkpoint,
        "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
        "gate_occurrence_last_zero_based": 4 * checkpoint - 1,
        **EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint],
        "policy_max_single_expansion_terms": POLICY_CAPS_BASE[
            "max_single_expansion_terms"
        ],
        "kernel_max_single_expansion_terms": (
            EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS[
                "max_single_expansion_terms"
            ]
        ),
        "gate_batch_propagation_started": True,
        "attempted_checkpoint_pretruncation_digest_computed": False,
        "attempted_checkpoint_ranking_performed": False,
        "attempted_checkpoint_candidate_rows_constructed": False,
        "attempted_checkpoint_selection_performed": False,
        "attempted_checkpoint_commit_performed": False,
        "attempted_checkpoint_record_constructed": False,
        "attempted_checkpoint_partial_expansion_committed": False,
        "input_expansion_count": previous["retained_expansion_count"],
        "input_expansion_sha256": previous["retained_expansion_sha256"],
        "last_committed_record_sha256": sha256(canonical_bytes(previous)),
    }
    for key, value in expected.items():
        if not exact_value_equal(abort.get(key), value):
            raise RuntimeError(
                f"M q{checkpoint} resource abort exact drift: {key}"
            )

    kinds = {
        "final_live_terms": {
            "exception_type": "RuntimeError",
            "exception_message": "design policy live-term cap exceeded",
            "exception_source_role": "exact_parent_helper",
            "exception_chained_from_exact_parent_helper": True,
            "abort_frame_local_schema_id": "helper_final_live_terms_v1",
            "gate_batch_propagation_completed": True,
            "policy_cap_check_reached": True,
            "kernel_cap_violation_triggered": False,
            "live_expansion_snapshot_available": True,
            "policy_relation": (
                "pretruncation_expansion_count>"
                "policy_max_single_expansion_terms"
            ),
            "cap": POLICY_CAPS_BASE["max_single_expansion_terms"],
        },
        "transient_live_terms": {
            "exception_type": "RuntimeError",
            "exception_message": (
                "design policy transient live-term cap exceeded"
            ),
            "exception_source_role": "exact_parent_helper",
            "exception_chained_from_exact_parent_helper": True,
            "abort_frame_local_schema_id": "helper_transient_live_terms_v1",
            "gate_batch_propagation_completed": True,
            "policy_cap_check_reached": True,
            "kernel_cap_violation_triggered": False,
            "live_expansion_snapshot_available": True,
            "policy_relation": (
                "peak_live_terms_this_checkpoint>"
                "policy_max_single_expansion_terms>="
                "pretruncation_expansion_count"
            ),
            "cap": POLICY_CAPS_BASE["max_single_expansion_terms"],
        },
        "kernel_single_expansion_terms": {
            "exception_type": "SchemaError",
            "exception_message": "v2 single-expansion term cap exceeded",
            "exception_source_role": "exact_wrapped_v2_kernel",
            "exception_chained_from_exact_parent_helper": False,
            "abort_frame_local_schema_id": (
                "kernel_observe_count_before_pre_count_assignment_v1"
            ),
            "gate_batch_propagation_completed": False,
            "policy_cap_check_reached": False,
            "kernel_cap_violation_triggered": True,
            "live_expansion_snapshot_available": False,
            "policy_relation": (
                "observed_term_count>kernel_max_single_expansion_terms_"
                "before_pretruncation_assignment"
            ),
            "cap": EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS[
                "max_single_expansion_terms"
            ],
        },
    }
    kind = abort.get("abort_kind")
    if type(kind) is not str or kind not in kinds:
        raise RuntimeError("M q88 resource abort kind drift")
    specification = kinds[kind]
    message = specification["exception_message"]
    branch_expected = {
        key: value
        for key, value in specification.items()
        if key != "cap"
    }
    branch_expected["exception_args"] = [message]
    branch_expected["enforced_term_cap"] = specification["cap"]
    for key, value in branch_expected.items():
        if not exact_value_equal(abort.get(key), value):
            raise RuntimeError(f"M q{checkpoint} {kind} abort drift: {key}")

    for key in (
        "observed_term_count",
        "observed_excess_terms",
        "peak_live_terms_this_checkpoint",
        "peak_live_terms_cumulative",
        "term_gate_visits_increment",
        "term_gate_visits_cumulative",
        "maximum_expansion_coefficient_tick_bits",
        "maximum_product_bits",
    ):
        if type(abort.get(key)) is not int or abort[key] < 0:
            raise RuntimeError(
                f"M q{checkpoint} resource abort integer drift: {key}"
            )
    observed = abort["observed_term_count"]
    enforced = abort["enforced_term_cap"]
    if (
        observed <= enforced
        or abort["observed_excess_terms"] != observed - enforced
    ):
        raise RuntimeError("M q88 resource abort cap relation drift")
    pre_count = abort["pretruncation_expansion_count"]
    if kind == "final_live_terms":
        if type(pre_count) is not int or pre_count != observed:
            raise RuntimeError("M q88 final-live pretruncation drift")
    elif kind == "transient_live_terms":
        if (
            type(pre_count) is not int
            or pre_count < 0
            or pre_count > abort["policy_max_single_expansion_terms"]
            or abort["peak_live_terms_this_checkpoint"] != observed
        ):
            raise RuntimeError("M q88 transient-live relation drift")
    elif pre_count is not None:
        raise RuntimeError("M q88 kernel abort exposed stale pre_count")
    if (
        kind != "kernel_single_expansion_terms"
        and observed > abort["kernel_max_single_expansion_terms"]
    ):
        raise RuntimeError("M q88 helper abort bypassed kernel cap")
    if abort["peak_live_terms_this_checkpoint"] < observed:
        raise RuntimeError("M q88 resource abort peak below observed terms")
    if abort["peak_live_terms_cumulative"] != max(
        previous["peak_live_terms_cumulative"],
        abort["peak_live_terms_this_checkpoint"],
    ):
        raise RuntimeError("M q88 resource abort peak recurrence drift")
    if abort["term_gate_visits_increment"] < abort["input_expansion_count"]:
        raise RuntimeError("M q88 resource abort gate visits below input")
    if abort["term_gate_visits_cumulative"] != (
        previous["term_gate_visits_cumulative"]
        + abort["term_gate_visits_increment"]
    ):
        raise RuntimeError("M q88 resource abort visit recurrence drift")
    rounding_increment = parse_canonical_nonnegative_decimal(
        abort["rounding_increment_scaled_ticks_squared"],
        "M q88 resource abort rounding increment",
    )
    rounding_cumulative = parse_canonical_nonnegative_decimal(
        abort["rounding_cumulative_scaled_ticks_squared"],
        "M q88 resource abort rounding cumulative",
    )
    if rounding_cumulative != (
        int(previous["rounding_cumulative_scaled_ticks_squared"])
        + rounding_increment
    ):
        raise RuntimeError("M q88 resource abort rounding recurrence drift")
    for key in (
        "maximum_expansion_coefficient_tick_bits",
        "maximum_product_bits",
    ):
        if abort[key] < previous[key]:
            raise RuntimeError(f"M q88 resource abort maximum drift: {key}")
    return dict(abort)


def validate_replay_handoff(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:
    require_exact_keys(
        result,
        EXPECTED_PARENT_RESULT_KEYS,
        "M q88 raw execution-parent result",
    )
    require_exact_keys(
        predecessor,
        EXPECTED_RELABELLED_RESULT_KEYS,
        "M q86 route canonical",
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
            raise RuntimeError(f"M q88 raw parent drift: {field}")
    validate_parent_source_custody(result.get("source_custody"))
    if result.get("screen_execution_components") != list(
        EXPECTED_PARENT_EXECUTION_COMPONENTS
    ):
        raise RuntimeError("M q88 raw component closure drift")
    for value_field, digest_field in (
        ("screen_execution_components", "screen_execution_components_sha256"),
        ("configuration_reference", "configuration_reference_sha256"),
        ("checkpoint_transform", "checkpoint_transform_sha256"),
    ):
        if result.get(digest_field) != sha256(
            canonical_bytes(result.get(value_field))
        ):
            raise RuntimeError(f"M q88 raw nested digest drift: {value_field}")
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
        "resource_policy_abort",
        "resource_policy_abort_sha256",
    }
    for field in EXPECTED_PARENT_RESULT_KEYS - dynamic_or_relabelled_fields:
        if not exact_value_equal(result.get(field), predecessor.get(field)):
            raise RuntimeError(f"M q88 invariant top-level drift: {field}")
    expected_raw_transform = predecessor["checkpoint_transform"].get(
        "physical_four_gate_control_flow_parent_transform"
    )
    expected_raw_transform_sha = predecessor["checkpoint_transform"].get(
        "physical_four_gate_control_flow_parent_transform_sha256"
    )
    if expected_raw_transform_sha != EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256:
        raise RuntimeError("M q88 q86 raw transform authority pin drift")
    if not exact_value_equal(
        result.get("checkpoint_transform"), expected_raw_transform
    ):
        raise RuntimeError("M q88 raw checkpoint transform authority drift")
    if result.get("checkpoint_transform_sha256") != (
        EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256
    ):
        raise RuntimeError("M q88 raw checkpoint transform digest pin drift")
    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or len(records) not in (86, 87, 88):
        raise RuntimeError("M q88 must attempt q87 and at most q88")
    if type(history) is not list:
        raise RuntimeError("M q88 selected history is not an exact list")
    old_records = predecessor["records"]
    old_history = predecessor["selected_K_history"]
    if not exact_value_equal(records[:86], old_records):
        raise RuntimeError("M q88 changed the exact q1-q86 record prefix")
    if not exact_value_equal(history[:86], old_history):
        raise RuntimeError("M q88 changed the exact q1-q86 selected history")
    if sha256(canonical_bytes(records[:86])) != (
        EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
    ):
        raise RuntimeError("M q88 q1-q86 record prefix digest drift")
    if sha256(canonical_bytes(history[:86])) != (
        EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256
    ):
        raise RuntimeError("M q88 q1-q86 history prefix digest drift")
    q86 = records[85]
    if sha256(canonical_bytes(q86)) != EXPECTED_ROUTE_PREDECESSOR_Q86_RECORD_SHA256:
        raise RuntimeError("M q88 q86 record anchor drift")
    if q86.get("retained_expansion_count") != EXPECTED_Q86_RETAINED_COUNT:
        raise RuntimeError("M q88 q86 retained-count anchor drift")
    if q86.get("retained_expansion_sha256") != EXPECTED_Q86_RETAINED_EXPANSION_SHA256:
        raise RuntimeError("M q88 q86 retained digest anchor drift")
    if q86.get("E_after_ticks") != EXPECTED_Q86_E_AFTER_TICKS:
        raise RuntimeError("M q88 q86 E anchor drift")

    extension_history = []
    abort = None
    if len(records) == 86:
        abort = validate_resource_policy_abort(result, q86, 87)
        if abort is None or len(history) != 86:
            raise RuntimeError("M q87 resource abort ledger drift")
        branch = "Q87_RESOURCE_ABORT_Q88_NOT_ATTEMPTED"
        expected_summary = {
            "attempted_checkpoint_count": 87,
            "completed_checkpoint_count": 86,
            "horizon_checkpoint_attempted": False,
            "horizon_reached_with_committed_checkpoint": False,
            "screen_terminal_condition": "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
            "failure_checkpoint_included": False,
            "last_committed_cumulative_drop_ticks": EXPECTED_Q86_E_AFTER_TICKS,
        }
    else:
        q87 = records[86]
        selected_q87 = validate_extended_record(q87, q86, 87)
        if selected_q87 is None:
            if len(records) != 87 or len(history) != 86:
                raise RuntimeError("M q87 failure must terminate before q88")
            if validate_resource_policy_abort(result, q86, 87) is not None:
                raise RuntimeError("M q87 failure cannot carry resource abort")
            branch = "Q87_FAILURE_Q88_NOT_ATTEMPTED"
            expected_summary = {
                "attempted_checkpoint_count": 87,
                "completed_checkpoint_count": 86,
                "horizon_checkpoint_attempted": False,
                "horizon_reached_with_committed_checkpoint": False,
                "screen_terminal_condition": (
                    "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
                ),
                "failure_checkpoint_included": True,
                "last_committed_cumulative_drop_ticks": (
                    EXPECTED_Q86_E_AFTER_TICKS
                ),
            }
        else:
            extension_history.append(selected_q87)
            if len(records) == 87:
                abort = validate_resource_policy_abort(result, q87, 88)
                if abort is None or len(history) != 87:
                    raise RuntimeError("M q88 resource abort ledger drift")
                branch = "Q87_SUCCESS_Q88_RESOURCE_ABORT"
                expected_summary = {
                    "attempted_checkpoint_count": 88,
                    "completed_checkpoint_count": 87,
                    "horizon_checkpoint_attempted": True,
                    "horizon_reached_with_committed_checkpoint": False,
                    "screen_terminal_condition": (
                        "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
                    ),
                    "failure_checkpoint_included": False,
                    "last_committed_cumulative_drop_ticks": q87[
                        "E_after_ticks"
                    ],
                }
            else:
                if validate_resource_policy_abort(result, q87, 88) is not None:
                    raise RuntimeError("M q88 record cannot carry resource abort")
                q88 = records[87]
                selected_q88 = validate_extended_record(q88, q87, 88)
                if selected_q88 is None:
                    if len(history) != 87:
                        raise RuntimeError("M q88 failure history count drift")
                    branch = "Q87_SUCCESS_Q88_FAILURE"
                    expected_summary = {
                        "attempted_checkpoint_count": 88,
                        "completed_checkpoint_count": 87,
                        "horizon_checkpoint_attempted": True,
                        "horizon_reached_with_committed_checkpoint": False,
                        "screen_terminal_condition": (
                            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
                        ),
                        "failure_checkpoint_included": True,
                        "last_committed_cumulative_drop_ticks": q87[
                            "E_after_ticks"
                        ],
                    }
                else:
                    extension_history.append(selected_q88)
                    if len(history) != 88:
                        raise RuntimeError("M q88 success history count drift")
                    branch = "Q87_AND_Q88_SUCCESS_HORIZON_REACHED"
                    expected_summary = {
                        "attempted_checkpoint_count": 88,
                        "completed_checkpoint_count": 88,
                        "horizon_checkpoint_attempted": True,
                        "horizon_reached_with_committed_checkpoint": True,
                        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
                        "failure_checkpoint_included": False,
                        "last_committed_cumulative_drop_ticks": q88[
                            "E_after_ticks"
                        ],
                    }
    if not exact_value_equal(
        history,
        list(old_history) + extension_history,
    ):
        raise RuntimeError("M q88 selected history is not the exact replay ledger")
    for field, value in expected_summary.items():
        if not exact_value_equal(result.get(field), value):
            raise RuntimeError(f"M q88 terminal summary drift: {field}")
    final = records[-1]
    failed = (
        abort is None
        and final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
    )
    expected_failure_sha = sha256(canonical_bytes(final)) if failed else None
    if result.get("failure_record_sha256") != expected_failure_sha:
        raise RuntimeError("M q88 failure-record digest drift")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("M q88 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(canonical_bytes(history)):
        raise RuntimeError("M q88 history digest drift")
    resource_source = abort if abort is not None else final
    resources = {
        "observed_peak_single_expansion_terms": resource_source[
            "peak_live_terms_cumulative"
        ],
        "observed_term_gate_visits_including_terminal_attempt": resource_source[
            "term_gate_visits_cumulative"
        ],
        "observed_maximum_expansion_coefficient_tick_bits": resource_source[
            "maximum_expansion_coefficient_tick_bits"
        ],
        "observed_maximum_product_bits": resource_source[
            "maximum_product_bits"
        ],
        "observed_rounding_cumulative_scaled_ticks_squared": resource_source[
            "rounding_cumulative_scaled_ticks_squared"
        ],
    }
    for field, value in resources.items():
        if not exact_value_equal(result.get(field), value):
            raise RuntimeError(f"M q88 observed resource drift: {field}")
    return {
        "validation_id": "M_k606208_c33_q88_same_cap_handoff_v1",
        "q1_through_q86_records_exact": True,
        "q1_through_q86_all_33_candidate_rows_exact": True,
        "q1_through_q86_selected_history_exact": True,
        "q86_records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        "q86_selected_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        "q86_terminal_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q86_RECORD_SHA256,
        "q87_input_retained_count": EXPECTED_Q86_RETAINED_COUNT,
        "q87_input_retained_sha256": EXPECTED_Q86_RETAINED_EXPANSION_SHA256,
        "q87_input_E_before_ticks": EXPECTED_Q86_E_AFTER_TICKS,
        "q87_prefix_cap_ticks": EXPECTED_Q87_PREFIX_CAP_TICKS,
        "q88_prefix_cap_ticks_if_attempted": EXPECTED_Q88_PREFIX_CAP_TICKS,
        "legal_terminal_branches": [
            "Q87_FAILURE_Q88_NOT_ATTEMPTED",
            "Q87_RESOURCE_ABORT_Q88_NOT_ATTEMPTED",
            "Q87_SUCCESS_Q88_FAILURE",
            "Q87_SUCCESS_Q88_RESOURCE_ABORT",
            "Q87_AND_Q88_SUCCESS_HORIZON_REACHED",
        ],
        "terminal_branch": branch,
        "resource_policy_abort_structured": abort is not None,
        "resource_policy_abort_checkpoint": (
            abort["checkpoint_number_one_based"] if abort is not None else None
        ),
        "resource_policy_abort_kind": (
            abort["abort_kind"] if abort is not None else None
        ),
        "resource_policy_abort_sha256": result["resource_policy_abort_sha256"],
        "q88_checkpoint_record_constructed": len(records) == 88,
        "q87_and_q88_outcomes_precommitted": False,
    }


def execution_components(parent_components: Any, self_sha: str) -> list[Dict[str, Any]]:
    if parent_components != list(EXPECTED_PARENT_EXECUTION_COMPONENTS):
        raise RuntimeError("M q88 raw execution component closure drift")
    if not is_canonical_sha256(self_sha):
        raise RuntimeError("M q88 component self digest drift")
    components = [
        {
            "relative_path": SELF_NAME,
            "role": "M_k606208_c33_q88_fresh_same_byte_screen",
            "sha256": self_sha,
        },
        {
            "relative_path": EXECUTION_PARENT_NAME,
            "role": "M_k606208_c33_q86_same_byte_private_execution_parent",
            "sha256": EXPECTED_EXECUTION_PARENT_SHA256,
        },
    ]
    saw_root = saw_v6 = saw_v2 = False
    forbidden = {ROUTE_PREDECESSOR_TRANSCRIPT_NAME}
    for original in parent_components:
        item = dict(original)
        path = item.get("relative_path")
        if path in forbidden:
            raise RuntimeError("q86 canonical became an execution component")
        if path == CONTROL_FLOW_ROOT_NAME:
            if item.get("sha256") != EXPECTED_CONTROL_FLOW_ROOT_SHA256:
                raise RuntimeError("raw control-flow root component pin drift")
            saw_root = True
            continue
        if path == V6_BASELINE_CONFIGURATION_NAME:
            item["role"] = "v6_baseline_configuration_before_q86_parent_override"
            saw_v6 = True
        elif path == V2_ARITHMETIC_NAME:
            item["role"] = "v2_arithmetic_bytes_beneath_k606208_c33_wrapper"
            saw_v2 = True
        components.append(item)
        if path == V2_ARITHMETIC_NAME:
            components.append({
                "relative_path": KERNEL_WRAPPER_NAME,
                "role": "M_k606208_c33_capability_override_provider",
                "sha256": EXPECTED_KERNEL_WRAPPER_SHA256,
            })
    if not (saw_root and saw_v6 and saw_v2):
        raise RuntimeError("M q88 raw component set incomplete")
    paths = [item["relative_path"] for item in components]
    if len(paths) != len(set(paths)) or len(components) != 11:
        raise RuntimeError("M q88 final component cardinality drift")
    return components


def configuration_reference(parent: Any) -> Dict[str, Any]:
    reference = parent.configuration_reference()
    if type(reference) is not dict:
        raise RuntimeError("M q88 parent configuration reference drift")
    return dict(reference)


def configuration_override(parent: Any, baseline_m: Tuple[int, ...]) -> Dict[str, Any]:
    parent_override = parent.configuration_override(baseline_m)
    return {
        "override_id": "magnetization_k606208_c33_q88_configuration_override_v1",
        "execution_parent_configuration_override": parent_override,
        "execution_parent_configuration_override_sha256": sha256(
            canonical_bytes(parent_override)
        ),
        "incremental_route_override_from_k606208_c33_q86": {
            "predecessor_candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 33, "after": 33},
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
        raise RuntimeError("M q88 wrapper pin drift")
    parent_override = parent.kernel_capability_override(wrapper_sha, manifest)
    return {
        "relative_path": KERNEL_WRAPPER_NAME,
        "source_sha256": wrapper_sha,
        "role": "unchanged_k606208_capability_override_provider",
        "execution_parent_kernel_capability_override": parent_override,
        "execution_parent_kernel_capability_override_sha256": sha256(
            canonical_bytes(parent_override)
        ),
        "effective_kernel_capability_limits": (
            EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        ),
        "incremental_route_changes_from_k606208_c33_q86": {},
        "execution_source_layers": [KERNEL_WRAPPER_NAME, V2_ARITHMETIC_NAME],
        "q86_canonical_is_execution_source": False,
        "v2_arithmetic_module_mutated_by_screen": False,
    }


def parent_horizon_override(context: Mapping[str, Any]) -> Dict[str, Any]:
    raw = context.get("raw_control_flow_horizon_override")
    if type(raw) is not dict:
        raise RuntimeError("M q88 raw horizon adapter evidence drift")
    changed = raw.get("changed_fields")
    if changed != ["MODE_CONFIG.magnetization.horizon_checkpoint_count"]:
        raise RuntimeError("M q88 raw horizon adapter changed extra fields")
    raw_delta = raw.get("semantic_delta", {}).get(
        "MODE_CONFIG.magnetization.horizon_checkpoint_count"
    )
    if raw_delta != {"before": 80, "after": EXTENDED_HORIZON}:
        raise RuntimeError("M q88 raw horizon adapter semantic delta drift")
    if context.get("execution_parent_private_entrypoint_called") is not True:
        raise RuntimeError("M q88 q86 private entrypoint evidence drift")
    if context.get("q86_canonical_loaded_before_replay") is not False:
        raise RuntimeError("M q88 q86 canonical was loaded before replay")
    if context.get("execution_parent_route_loader_suppressed") is not True:
        raise RuntimeError("M q88 q86 parent route-loader suppression drift")
    if context.get("execution_parent_abort_adapter_installed") is not True:
        raise RuntimeError("M q88 q86 parent abort-adapter evidence drift")
    return {
        "override_id": "magnetization_q86_parent_to_q88_horizon_override_v1",
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
        "q86_canonical_loaded_before_replay": context.get(
            "q86_canonical_loaded_before_replay"
        ),
        "execution_parent_route_loader_suppressed": context.get(
            "execution_parent_route_loader_suppressed"
        ),
        "execution_parent_abort_adapter_installed": context.get(
            "execution_parent_abort_adapter_installed"
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
        raise RuntimeError("M q88 relabel requires fresh same-byte self execution")
    require_exact_keys(result, EXPECTED_PARENT_RESULT_KEYS, "M q88 raw parent result")
    handoff = validate_replay_handoff(result, predecessor)
    old_components = result.get("screen_execution_components")
    if result.get("screen_execution_components_sha256") != sha256(
        canonical_bytes(old_components)
    ):
        raise RuntimeError("M q88 raw component digest drift")
    old_configuration = result.get("configuration_reference")
    if result.get("configuration_reference_sha256") != sha256(
        canonical_bytes(old_configuration)
    ):
        raise RuntimeError("M q88 raw configuration digest drift")
    old_transform = result.get("checkpoint_transform")
    old_transform_sha = result.get("checkpoint_transform_sha256")
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("M q88 raw transform digest drift")
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
        "transform_id": "magnetization_four_gate_k606208_c33_q88_v1",
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": old_transform_sha,
        "execution_parent_q86_transform_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256
        ),
        "q86_execution_parent_replaces_raw_root_component_at_outer_boundary": True,
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "q87_and_q88_outcomes_precommitted": False,
        "incremental_route_semantic_delta": {
            "candidate_K_values_changed": False,
            "policy_caps_changed": False,
            "kernel_capability_limits_changed": False,
            "horizon_checkpoint_count": {"before": 86, "after": 88},
        },
        "overridden_semantics": ["magnetization_horizon_checkpoint_count"],
    }
    parent_custody = validate_parent_source_custody(result.get("source_custody"))
    custody = expected_final_source_custody(self_sha)
    if parent_custody != {
        path: custody[path] for path in EXPECTED_PARENT_SOURCE_CUSTODY
    }:
        raise RuntimeError("M q88 parent custody changed during relabel")
    if len(custody) != 10:
        raise RuntimeError("M q88 final source custody cardinality drift")
    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k606208_c33_q88_screen_v1"
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
        "M q88 relabelled top-level result",
    )
    if result["source_custody"] != expected_final_source_custody(self_sha):
        raise RuntimeError("M q88 final source custody closure drift")
    for value_key, digest_key in (
        ("screen_execution_components", "screen_execution_components_sha256"),
        ("configuration_reference", "configuration_reference_sha256"),
        ("configuration_override", "configuration_override_sha256"),
        ("kernel_capability_override", "kernel_capability_override_sha256"),
        ("parent_horizon_override", "parent_horizon_override_sha256"),
        ("route_predecessor_reference", "route_predecessor_reference_sha256"),
        ("predecessor_handoff_validation", "predecessor_handoff_validation_sha256"),
        ("checkpoint_transform", "checkpoint_transform_sha256"),
        ("resource_policy_abort", "resource_policy_abort_sha256"),
    ):
        value = result[value_key]
        digest = result[digest_key]
        if value is None:
            if digest is not None:
                raise RuntimeError(f"M q88 null nested digest drift: {value_key}")
        elif digest != sha256(canonical_bytes(value)):
            raise RuntimeError(f"M q88 final nested digest drift: {value_key}")
    return result


def _run_verified(repo: Path) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("M q88 screen requires fresh same-byte self execution")
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
    module = types.ModuleType("verified_magnetization_k606208_c33_q88_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("M q88 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("M q88 transcript exceeds output byte cap")
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
