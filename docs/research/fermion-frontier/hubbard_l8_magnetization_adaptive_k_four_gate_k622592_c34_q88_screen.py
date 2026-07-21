#!/usr/bin/env python3
"""Source-pinned diagnostic M K622592/C34 fixed-q88 fresh replay.

The exact four-gate control-flow root is the only execution parent.  The
K606208/C33 q88 screen and canonical transcript are loaded only after a full
q1--q88 replay as route evidence; neither is compiled, executed, or used as
propagation/state/resume input.  This screen creates no certificate authority.
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
    "k622592_c34_q88_screen.py"
)
CONTROL_FLOW_PARENT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k622592_c34.py"
ROUTE_PREDECESSOR_SCREEN_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k606208_c33_q88_screen.py"
)
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k606208_c33_q88_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k622592_c34_q88_transcript.json"
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
EXPECTED_V2_HELPER_SHA256 = (
    "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3"
)
EXPECTED_KERNEL_WRAPPER_SHA256 = (
    "f4e676da40535903301181cf482119e051066b90921793e34152403b3b74b976"
)
EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256 = (
    "3c2b66149d524cc63a4d04838b3eec47fb69677466fe1f208e226df92bf0dac3"
)
EXPECTED_KERNEL_SOURCE_LAYERS_SHA256 = (
    "41be6f48e87852126c4613b79628e5d5ed870bfadd4f9d825d153b5e7164d418"
)
EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256 = (
    "92cce87c14e20f8c888d19a897d955f46afe7e0af6e64f30643400b8d0bcd99b"
)
EXPECTED_KERNEL_CROSS_ROUTE_REFERENCE_SHA256 = (
    "0c86e668b8f8e3dcc97944d0cb7c83818367089e636e4002548361c53b82388c"
)
EXPECTED_ROUTE_KERNEL_SHA256 = (
    "447cb116c2ca977cb2711b08e64e5795728907b8c4033bd1eb38211bf63cf558"
)
EXPECTED_ROUTE_KERNEL_MANIFEST_SHA256 = (
    "116c8d37e11e2762a3a47d2d5844d059de0277dbd41724b5c65018b0b234b395"
)
EXPECTED_CROSS_ROUTE_KERNEL_SHA256 = (
    "7ac6c87f3d789ad62540cbc96e81f0a092594b0524eec3f9b05e7ffec2124838"
)
EXPECTED_CROSS_ROUTE_KERNEL_MANIFEST_SHA256 = (
    "fc82c41b1a1dd82fbb34e205ea347b0ba41b08c5fd2ebed6a599593fe95c1b34"
)
EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256 = (
    "d158d00275e78b33d0246e86bf9bc7bcaf4eb4f7fa4cb9afce2298e97cb5308d"
)
EXPECTED_ROUTE_PREDECESSOR_SCREEN_SIZE = 109_288
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "f7ca4a1defd38472366c1cfcd112736f34b73e612002cce98a52f79daa5cc1b0"
)
EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE = 804_599
EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256 = (
    "8247f4f53a52d5e066f337fee6a5ef38055992f07c4efbaba08930bd390b1747"
)
EXPECTED_ROUTE_PREDECESSOR_Q1_Q87_RECORDS_SHA256 = (
    "255d3a5890db7a6ddaa39a48d5f663380ea6687c4569149f3fc2027ec2a1e2db"
)
EXPECTED_ROUTE_PREDECESSOR_Q1_Q87_COMMON_SHA256 = (
    "2ad0d8a01ca54572f056252373fcf7a9e2dfa38b96aecfc67a26fbe41fc7f353"
)
EXPECTED_ROUTE_PREDECESSOR_Q1_Q87_ROWS_SHA256 = (
    "89a45f8e68c6395cf3ee4225cfddb0261aa513bf31f30902e3cb58a268dadb01"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "e340ab1968faabaa070ba04a549ede8c7b27018897521e598ab5fd9714db3bb3"
)
EXPECTED_ROUTE_PREDECESSOR_Q87_RECORD_SHA256 = (
    "63182be225121402ee1bffa07be8ea074e6035eee08ce90ab32f120fc9d25e30"
)
EXPECTED_ROUTE_PREDECESSOR_Q87_ROWS_SHA256 = (
    "c7819c1252415979ca87ada1578a141bed50c7b9a4e566c86e3e769ec430573a"
)
EXPECTED_ROUTE_PREDECESSOR_Q88_FAILURE_SHA256 = (
    "3a43eaaa48243694d21359595c82c4091733e7ed8c6cc2955997af4dd56610ce"
)
EXPECTED_ROUTE_PREDECESSOR_Q88_ROWS_SHA256 = (
    "066028a4ed7119b5e584cc1bcdba5bd0d3c1e4a219c343281b42aa24a1ea2a2a"
)
EXPECTED_ROUTE_PREDECESSOR_Q88_PHYSICAL_COMMON_SHA256 = (
    "f9ac92d5d2d1734f239cd90688bffd048d21ae8a323764676d3038d51be1f022"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_SHA256 = (
    "e421d9c9c57e5dc3f7d5aa3500e9e9776f588bfb65df1a03ccd9292df404e5f2"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256 = (
    "1f0bfbf07b16ff0a06acfbc9fe1a91ee87840129e090da5f8341a3e70bdc86cb"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_OVERRIDE_SHA256 = (
    "d515a06d87030c5a92d0471194db60398c4a4cd4e2ff931c6729d37406d18b06"
)
EXPECTED_ROUTE_PREDECESSOR_PARENT_HORIZON_OVERRIDE_SHA256 = (
    "61d586972f3b3d83c8a53cd63730f4ce2d3560de8b5dee69a949567fde3ddbdc"
)
EXPECTED_ROUTE_PREDECESSOR_ROUTE_REFERENCE_SHA256 = (
    "9f117e1ad1f434173ae84a10ae8ea8e62d446053e25d29a60e72440c62fc659c"
)
EXPECTED_ROUTE_PREDECESSOR_HANDOFF_SHA256 = (
    "923fda9ab1df09aa12976c557a0ffbec3b6ce2ea3cb43d5dd54c71d9b7af91ae"
)
EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256 = (
    "149d43ba306359d57f5650a1fd54a5b6f85717dc58c9155eac9910e0389f0241"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "d0d101b866026e34d17424e8bddafd9905f92041c7ef2f54c31ad93968233fbe"
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
BASE_PARENT_HORIZON = 80
EXTENDED_HORIZON = 88
K540672 = 540_672
K557056 = 557_056
K573440 = 573_440
K589824 = 589_824
K606208 = 606_208
K622592 = 622_592

V6_M_CANDIDATES = (
    65_536, 81_920, 98_304, 114_688, 131_072, 147_456, 163_840,
    180_224, 196_608, 212_992, 229_376, 245_760, 262_144, 278_528,
    294_912, 311_296, 327_680, 344_064, 360_448, 376_832, 393_216,
    409_600, 425_984, 442_368, 458_752, 475_136, 491_520, 507_904,
    524_288,
)
ROUTE_M_CANDIDATES = tuple(range(81_920, K606208 + 1, 16_384))
M_CANDIDATES = ROUTE_M_CANDIDATES + (K622592,)
EXPECTED_V6_M_CANDIDATE_SHA256 = (
    "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
)
EXPECTED_ROUTE_CANDIDATE_SHA256 = (
    "8c0105608be381ce3ecaeb6178d25c0eda50713e54aa22f734b964bbd5464f86"
)
EXPECTED_CANDIDATE_SHA256 = (
    "4de63e9494a84e9603fccfa0bbf6d5e03da1be4aee08927728e8f575ad516d01"
)
EXPECTED_Q87_E_AFTER_TICKS = "1700501205265321"
EXPECTED_Q87_RETAINED_COUNT = 606_208
EXPECTED_Q87_RETAINED_EXPANSION_SHA256 = (
    "1dbf1803c6909f90aa3afffc024986aefde98d7580c1675bb6e717063c90b262"
)
EXPECTED_Q88_PREFIX_CAP_TICKS = "1700695433287388"
EXPECTED_Q88_MINIMUM_EFFECTIVE_K = 607_993
EXPECTED_Q88_OLD_POLICY_SHORTFALL = 1_785
EXPECTED_Q88_PRETRUNCATION_COUNT = 689_242
EXPECTED_Q88_PRETRUNCATION_SHA256 = (
    "565071e6410de1f107c493346dd41b9b60f0de3727a41d22be42155314da3c40"
)
EXPECTED_Q88_RANKED_SUFFIX_SHA256 = (
    "89ca8be11455b2812d6fe9a441bb9d9d182bbde987a8f9155893bbf4ae73ed68"
)
EXPECTED_Q88_GATE_BATCH_SHA256 = (
    "7f8c6a2dd155412a27369e1fa8402c37127c6eadf12e4fa59ba442d345e8eaf7"
)
Q88_THRESHOLD_EVIDENCE = {
    "scope": "fixed_predecessor_q88_state_prefix_gates_and_ranked_suffix_only",
    "minimum_effective_K_to_meet_prefix": EXPECTED_Q88_MINIMUM_EFFECTIVE_K,
    "predecessor_policy_maximum_K": K606208,
    "predecessor_shortfall": EXPECTED_Q88_OLD_POLICY_SHORTFALL,
    "next_precommitted_ladder_rung": K622592,
    "K607993_execution_row_constructed": False,
    "K607993_drop_ticks_asserted": False,
    "must_recompute_if_state_cadence_prefix_or_horizon_changes": True,
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
EXPECTED_ROUTE_POLICY_CAPS = {
    **EXPECTED_V6_POLICY_CAPS,
    "max_candidate_K": K606208,
    "max_output_terms_if_successful": K606208,
}
POLICY_CAPS_BASE = {
    **EXPECTED_ROUTE_POLICY_CAPS,
    "max_candidate_K": K622592,
    "max_output_terms_if_successful": K622592,
}

EXPECTED_V2_KERNEL_LIMITS = {
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
EXPECTED_ROUTE_KERNEL_LIMITS = {
    **EXPECTED_V2_KERNEL_LIMITS,
    "max_candidate_count": 33,
    "max_retained_K": K606208,
}
EXPECTED_WRAPPED_KERNEL_LIMITS = {
    **EXPECTED_V2_KERNEL_LIMITS,
    "max_candidate_count": 34,
    "max_retained_K": K622592,
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
RECORD_FAILURE_ONLY_KEYS = frozenset({
    "minimum_effective_K_to_meet_prefix",
    "required_K_excess_over_policy_maximum",
    "maximum_candidate_drop_excess_over_slack_ticks",
})
RECORD_SUCCESS_ONLY_KEYS = frozenset({
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
RECORD_FAILURE_RECORD_KEYS = frozenset({
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
RECORD_SUCCESS_RECORD_KEYS = (
    RECORD_FAILURE_RECORD_KEYS - RECORD_FAILURE_ONLY_KEYS | RECORD_SUCCESS_ONLY_KEYS
)
UPSTREAM_PARENT_RESULT_KEYS = frozenset({
    "schema_version",
    "transcript_fingerprint",
    "status",
    "screen_terminal_condition",
    "observable_id",
    "input_step_index",
    "attempted_child_step_index",
    "screen_source_sha256",
    "same_byte_self_execution",
    "v2_helper_source_sha256",
    "v2_helper_compiled_from_verified_bytes",
    "v2_helper_module_isolated",
    "v2_run_entrypoint_called",
    "v6_configuration_source_sha256",
    "v6_configuration_compiled_from_verified_bytes",
    "v6_configuration_module_isolated",
    "v6_execution_invoked",
    "v6_same_byte_execution_parent",
    "control_flow_owned_by_screen",
    "screen_execution_components",
    "screen_execution_components_sha256",
    "configuration_reference",
    "configuration_reference_sha256",
    "checkpoint_transform",
    "checkpoint_transform_sha256",
    "arithmetic_kernel_commit",
    "source_custody",
    "parent_expected_witness_sha256",
    "input_boundary_custody",
    "input_cumulative_drop_ticks",
    "maximum_cumulative_drop_ticks",
    "remaining_mapped_steps_including_attempt",
    "future_checkpoint_denominator",
    "prefix_cap_formula",
    "candidate_K_values",
    "candidate_K_values_sha256",
    "candidate_policy_precommitted_at_probe_time",
    "selection_rule",
    "single_propagation_and_single_ranking_per_checkpoint",
    "sequence",
    "screen_horizon_checkpoint_count",
    "horizon_checkpoint_attempted",
    "horizon_reached_with_committed_checkpoint",
    "kernel_capability_limits",
    "proposed_policy_caps",
    "root_globals_before",
    "root_globals_after",
    "root_globals_unchanged",
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
    "child_boundary_committed",
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
    "control_flow_parent_source_sha256",
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
    "arithmetic_kernel_commit_role",
    "configuration_override",
    "configuration_override_sha256",
    "control_flow_owned_by_verified_parent",
    "control_flow_parent_compiled_from_verified_bytes",
    "control_flow_parent_module_isolated",
    "control_flow_parent_private_entrypoint_called",
    "control_flow_parent_relative_path",
    "control_flow_parent_runtime_horizon_override_applied",
    "control_flow_parent_same_byte_execution",
    "control_flow_parent_source_sha256",
    "diagnostic_candidate_ladder_precommitted_before_replay",
    "diagnostic_horizon_precommitted_before_replay",
    "kernel_capability_override",
    "kernel_capability_override_sha256",
    "kernel_capability_wrapper_compiled_from_verified_bytes",
    "kernel_capability_wrapper_module_isolated",
    "kernel_capability_wrapper_relative_path",
    "kernel_capability_wrapper_source_sha256",
    "parent_horizon_override",
    "parent_horizon_override_sha256",
    "predecessor_handoff_validation",
    "predecessor_handoff_validation_sha256",
    "route_predecessor_reference",
    "route_predecessor_reference_sha256",
    "v2_arithmetic_compiled_from_verified_bytes",
    "v2_arithmetic_source_sha256",
    "v6_configuration_source_used_as_baseline_only",
    "v6_runtime_configuration_override_applied",
})
EXPECTED_RELABELLED_RESULT_KEYS = (
    EXPECTED_PARENT_RESULT_KEYS | RELABELLED_ADDED_TOP_LEVEL_KEYS
)
EXPECTED_ROUTE_PREDECESSOR_RESULT_KEYS = EXPECTED_RELABELLED_RESULT_KEYS


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True,
        separators=(",", ":"), sort_keys=True,
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


def load_pinned_module(repo: Path, relative_path: str, expected: str, name: str):
    path = checked_repo_file(repo, relative_path)
    payload = bounded_bytes(path, MAX_PINNED_SOURCE_BYTES)
    observed = sha256(payload)
    if observed != expected:
        raise RuntimeError(f"source pin drift for {relative_path}: {observed}")
    return compile_isolated(name, path, payload), payload


def changed_keys(before: Mapping[str, Any], after: Mapping[str, Any]) -> set[str]:
    return {key for key in set(before) | set(after) if before.get(key) != after.get(key)}


def exact_value_equal(observed: Any, expected: Any) -> bool:

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


def validate_local_configuration() -> None:
    if len(V6_M_CANDIDATES) != 29:
        raise RuntimeError("V6 M candidate count drift")
    if len(ROUTE_M_CANDIDATES) != 33:
        raise RuntimeError("route M candidate count drift")
    if (
        len(M_CANDIDATES) != 34
        or M_CANDIDATES != ROUTE_M_CANDIDATES + (K622592,)
        or K607993_IN_LADDER()
    ):
        raise RuntimeError("M K622592/C34 ladder is not an exact append")
    if any(left >= right for left, right in zip(M_CANDIDATES, M_CANDIDATES[1:])):
        raise RuntimeError("M candidate order drift")
    if sha256(canonical_bytes(list(ROUTE_M_CANDIDATES))) != EXPECTED_ROUTE_CANDIDATE_SHA256:
        raise RuntimeError("route candidate digest drift")
    if sha256(canonical_bytes(list(M_CANDIDATES))) != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("candidate digest drift")
    changed = {"max_candidate_K", "max_output_terms_if_successful"}
    if changed_keys(EXPECTED_V6_POLICY_CAPS, POLICY_CAPS_BASE) != changed:
        raise RuntimeError("direct policy override changed a non-K field")
    if changed_keys(EXPECTED_ROUTE_POLICY_CAPS, POLICY_CAPS_BASE) != changed:
        raise RuntimeError("route policy override changed a non-K field")
    if POLICY_CAPS_BASE["max_candidate_K"] != M_CANDIDATES[-1]:
        raise RuntimeError("policy maximum and ladder disagree")
    if {
        "upstream_raw_top_level": len(UPSTREAM_PARENT_RESULT_KEYS),
        "raw_top_level": len(EXPECTED_PARENT_RESULT_KEYS),
        "final_top_level": len(EXPECTED_RELABELLED_RESULT_KEYS),
        "success_record": len(RECORD_SUCCESS_RECORD_KEYS),
        "failure_record": len(RECORD_FAILURE_RECORD_KEYS),
        "candidate_row": len(CANDIDATE_RECORD_KEYS),
        "resource_abort": len(RESOURCE_POLICY_ABORT_KEYS),
    } != {
        "upstream_raw_top_level": 65,
        "raw_top_level": 67,
        "final_top_level": 96,
        "success_record": 37,
        "failure_record": 31,
        "candidate_row": 7,
        "resource_abort": 50,
    }:
        raise RuntimeError("closed schema size drift")


def K607993_IN_LADDER() -> bool:
    return EXPECTED_Q88_MINIMUM_EFFECTIVE_K in M_CANDIDATES

def load_control_flow_parent(repo: Path) -> Any:
    parent, _ = load_pinned_module(
        repo, CONTROL_FLOW_PARENT_NAME, EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "pinned_four_gate_parent_for_m_k622592_c34_q88",
    )
    if parent.KERNEL_NAME != V2_ARITHMETIC_NAME:
        raise RuntimeError("control-flow parent kernel path drift")
    if parent.EXPECTED_KERNEL_SHA256 != EXPECTED_V2_ARITHMETIC_SHA256:
        raise RuntimeError("control-flow parent kernel pin drift")
    if parent.EXPECTED_V6_CONFIGURATION_SHA256 != EXPECTED_V6_BASELINE_CONFIGURATION_SHA256:
        raise RuntimeError("control-flow parent v6 pin drift")
    horizons = {mode: cfg["horizon_checkpoint_count"] for mode, cfg in parent.MODE_CONFIG.items()}
    if horizons != {"magnetization": BASE_PARENT_HORIZON, "double_occupancy": 66}:
        raise RuntimeError("control-flow parent horizon drift")
    if (
        type(parent) is not types.ModuleType
        or type(parent.run_four_gate) is not types.FunctionType
        or parent.run_four_gate.__globals__ is not parent.__dict__
        or parent.run_four_gate.__module__ != parent.__name__
        or parent.run_four_gate.__code__.co_filename != parent.__file__
    ):
        raise RuntimeError("control-flow parent function authority drift")
    parent._M_K622592_EXACT_RUN_FOUR_GATE = parent.run_four_gate
    return parent


def load_configured_v6_baseline(repo: Path) -> Tuple[Any, Tuple[int, ...]]:
    configuration, _ = load_pinned_module(
        repo, V6_BASELINE_CONFIGURATION_NAME,
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "pinned_v6_baseline_for_m_k622592_c34_q88",
    )
    if configuration.POLICY_CAPS_BASE != EXPECTED_V6_POLICY_CAPS:
        raise RuntimeError("v6 policy caps drift")
    if sha256(canonical_bytes(configuration.POLICY_CAPS_BASE)) != EXPECTED_V6_POLICY_CAPS_SHA256:
        raise RuntimeError("v6 policy digest drift")
    baseline_m = tuple(configuration.MODE_CONFIG["magnetization"]["candidates"])
    if sha256(canonical_bytes(list(baseline_m))) != EXPECTED_V6_M_CANDIDATE_SHA256:
        raise RuntimeError("v6 M candidate digest drift")
    if baseline_m != V6_M_CANDIDATES:
        raise RuntimeError("M direct construction from v6 drift")
    before_other = copy.deepcopy(configuration.MODE_CONFIG["double_occupancy"])
    effective = copy.deepcopy(configuration.MODE_CONFIG)
    effective[MODE]["candidates"] = tuple(M_CANDIDATES)
    configuration.MODE_CONFIG = effective
    configuration.POLICY_CAPS_BASE = dict(POLICY_CAPS_BASE)
    if configuration.MODE_CONFIG["double_occupancy"] != before_other:
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
    wrapper = types.ModuleType("pinned_m_k622592_c34_arithmetic_wrapper")
    wrapper.__file__ = str(wrapper_path)
    wrapper.__package__ = ""
    wrapper.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = wrapper_payload
    wrapper.__dict__["_VERIFIED_BASE_KERNEL_SOURCE_BYTES"] = v2_payload
    exec(compile(wrapper_payload, wrapper.__file__, "exec"), wrapper.__dict__)
    if wrapper.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_LIMITS:
        raise RuntimeError("wrapped kernel effective limits drift")
    manifest = wrapper.capability_manifest()
    if sha256(canonical_bytes(manifest)) != EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256:
        raise RuntimeError("kernel capability manifest pin drift")
    if wrapper.capability_manifest_sha256() != EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256:
        raise RuntimeError("kernel capability manifest API drift")
    if [item.get("relative_path") for item in manifest.get("source_layers", ())] != [
        KERNEL_WRAPPER_NAME, V2_ARITHMETIC_NAME,
    ]:
        raise RuntimeError("kernel execution source layers drift")
    if sha256(canonical_bytes(manifest["source_layers"])) != EXPECTED_KERNEL_SOURCE_LAYERS_SHA256:
        raise RuntimeError("kernel execution source-layer digest drift")
    route = manifest.get("route_predecessor_reference")
    if type(route) is not dict:
        raise RuntimeError("kernel route predecessor reference drift")
    if sha256(canonical_bytes(route)) != EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256:
        raise RuntimeError("kernel route predecessor reference digest drift")
    if route.get("source_sha256") != EXPECTED_ROUTE_KERNEL_SHA256:
        raise RuntimeError("kernel route source pin drift")
    if route.get("capability_manifest_sha256") != EXPECTED_ROUTE_KERNEL_MANIFEST_SHA256:
        raise RuntimeError("kernel route manifest pin drift")
    if any(route.get(key) is not False for key in ("compiled", "executed", "execution_source_layer")):
        raise RuntimeError("kernel route predecessor became an execution layer")
    cross_route = manifest.get("cross_route_reference")
    if type(cross_route) is not dict:
        raise RuntimeError("kernel cross-route reference drift")
    if sha256(canonical_bytes(cross_route)) != EXPECTED_KERNEL_CROSS_ROUTE_REFERENCE_SHA256:
        raise RuntimeError("kernel cross-route reference digest drift")
    if cross_route.get("source_sha256") != EXPECTED_CROSS_ROUTE_KERNEL_SHA256:
        raise RuntimeError("kernel cross-route source pin drift")
    if cross_route.get("capability_manifest_sha256") != EXPECTED_CROSS_ROUTE_KERNEL_MANIFEST_SHA256:
        raise RuntimeError("kernel cross-route manifest pin drift")
    if cross_route.get("relationship") != "same_retained_K_different_candidate_count":
        raise RuntimeError("kernel cross-route relationship drift")
    if any(cross_route.get(key) is not False for key in ("compiled", "executed", "execution_source_layer")):
        raise RuntimeError("kernel cross-route reference became an execution layer")
    return wrapper, wrapper_sha, manifest


def _route_digest_pair(transcript: Mapping[str, Any], key: str, digest_key: str) -> None:
    value = transcript.get(key)
    digest = transcript.get(digest_key)
    if value is None:
        if digest is not None:
            raise RuntimeError(f"route null nested digest drift: {key}")
    elif digest != sha256(canonical_bytes(value)):
        raise RuntimeError(f"route nested digest drift: {key}")


def _without_candidate_rows(record: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in record.items() if key != "candidate_records"}


Q88_PHYSICAL_COMMON_KEYS = frozenset({
    "E_before_ticks", "batch_in_stage", "budget_prefix_cap_ticks",
    "checkpoint_index_zero_based", "checkpoint_number_one_based",
    "gate_batch_sha256", "gate_occurrence_first_zero_based",
    "gate_occurrence_last_zero_based", "input_expansion_count",
    "input_expansion_sha256", "maximum_expansion_coefficient_tick_bits",
    "maximum_product_bits", "peak_live_terms_cumulative",
    "peak_live_terms_this_checkpoint", "prefix_slack_before_selection_ticks",
    "pretruncation_expansion_count", "pretruncation_expansion_sha256",
    "ranked_suffix_sha256", "rounding_cumulative_scaled_ticks_squared",
    "rounding_increment_scaled_ticks_squared", "stage_group", "stage_index",
    "term_gate_visits_cumulative", "term_gate_visits_increment",
})


def load_route_reference(repo: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    screen_raw = bounded_bytes(
        checked_repo_file(repo, ROUTE_PREDECESSOR_SCREEN_NAME),
        MAX_PINNED_SOURCE_BYTES,
    )
    if (
        len(screen_raw) != EXPECTED_ROUTE_PREDECESSOR_SCREEN_SIZE
        or sha256(screen_raw) != EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256
    ):
        raise RuntimeError("route q88 screen source pin drift")
    raw = bounded_bytes(
        checked_repo_file(repo, ROUTE_PREDECESSOR_TRANSCRIPT_NAME),
        MAX_ROUTE_TRANSCRIPT_BYTES,
    )
    if (
        len(raw) != EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE
        or sha256(raw) != EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256
    ):
        raise RuntimeError("route q88 canonical exact-byte pin drift")
    try:
        transcript = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("route q88 canonical is invalid JSON") from exc
    if type(transcript) is not dict or raw != canonical_bytes(transcript):
        raise RuntimeError("route q88 transcript is not canonical JSON")
    require_exact_keys(
        transcript,
        EXPECTED_ROUTE_PREDECESSOR_RESULT_KEYS,
        "route q88 canonical top-level transcript",
    )
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k606208_c33_q88_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_horizon_checkpoint_count": 88,
        "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "attempted_checkpoint_count": 88,
        "completed_checkpoint_count": 87,
        "failure_checkpoint_included": True,
        "failure_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q88_FAILURE_SHA256,
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": False,
        "resource_policy_abort": None,
        "resource_policy_abort_sha256": None,
        "candidate_K_values": list(ROUTE_M_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_ROUTE_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **EXPECTED_ROUTE_POLICY_CAPS,
            "max_candidate_count": 33,
        },
        "kernel_capability_limits": EXPECTED_ROUTE_KERNEL_LIMITS,
        "records_sha256": EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
    }
    for key, value in expected.items():
        if not exact_value_equal(transcript.get(key), value):
            raise RuntimeError(f"route q88 canonical field drift: {key}")
    digest_pins = {
        "configuration_reference_sha256": EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_SHA256,
        "configuration_override_sha256": EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256,
        "kernel_capability_override_sha256": EXPECTED_ROUTE_PREDECESSOR_KERNEL_OVERRIDE_SHA256,
        "parent_horizon_override_sha256": EXPECTED_ROUTE_PREDECESSOR_PARENT_HORIZON_OVERRIDE_SHA256,
        "route_predecessor_reference_sha256": EXPECTED_ROUTE_PREDECESSOR_ROUTE_REFERENCE_SHA256,
        "predecessor_handoff_validation_sha256": EXPECTED_ROUTE_PREDECESSOR_HANDOFF_SHA256,
        "screen_execution_components_sha256": EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256,
        "checkpoint_transform_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
    }
    for key, value in digest_pins.items():
        if transcript.get(key) != value:
            raise RuntimeError(f"route q88 nested authority pin drift: {key}")
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
        _route_digest_pair(transcript, value_key, digest_key)
    records = transcript.get("records")
    history = transcript.get("selected_K_history")
    if type(records) is not list or len(records) != 88:
        raise RuntimeError("route q88 record ledger drift")
    if type(history) is not list or len(history) != 87:
        raise RuntimeError("route q88 selected-history ledger drift")
    if sha256(canonical_bytes(records)) != EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256:
        raise RuntimeError("route q88 full records digest drift")
    if sha256(canonical_bytes(records[:87])) != EXPECTED_ROUTE_PREDECESSOR_Q1_Q87_RECORDS_SHA256:
        raise RuntimeError("route q1-q87 record prefix digest drift")
    common = [_without_candidate_rows(record) for record in records[:87]]
    rows = [record["candidate_records"] for record in records[:87]]
    if sha256(canonical_bytes(common)) != EXPECTED_ROUTE_PREDECESSOR_Q1_Q87_COMMON_SHA256:
        raise RuntimeError("route q1-q87 common digest drift")
    if sha256(canonical_bytes(rows)) != EXPECTED_ROUTE_PREDECESSOR_Q1_Q87_ROWS_SHA256:
        raise RuntimeError("route q1-q87 row digest drift")
    q87, q88 = records[86], records[87]
    if sha256(canonical_bytes(q87)) != EXPECTED_ROUTE_PREDECESSOR_Q87_RECORD_SHA256:
        raise RuntimeError("route q87 record digest drift")
    if sha256(canonical_bytes(q87["candidate_records"])) != EXPECTED_ROUTE_PREDECESSOR_Q87_ROWS_SHA256:
        raise RuntimeError("route q87 rows digest drift")
    if sha256(canonical_bytes(q88)) != EXPECTED_ROUTE_PREDECESSOR_Q88_FAILURE_SHA256:
        raise RuntimeError("route q88 failure digest drift")
    if sha256(canonical_bytes(q88["candidate_records"])) != EXPECTED_ROUTE_PREDECESSOR_Q88_ROWS_SHA256:
        raise RuntimeError("route q88 rows digest drift")
    physical = {key: q88[key] for key in Q88_PHYSICAL_COMMON_KEYS}
    if sha256(canonical_bytes(physical)) != EXPECTED_ROUTE_PREDECESSOR_Q88_PHYSICAL_COMMON_SHA256:
        raise RuntimeError("route q88 physical-common digest drift")
    if (
        q88.get("minimum_effective_K_to_meet_prefix")
        != EXPECTED_Q88_MINIMUM_EFFECTIVE_K
        or q88.get("required_K_excess_over_policy_maximum")
        != EXPECTED_Q88_OLD_POLICY_SHORTFALL
    ):
        raise RuntimeError("route q88 threshold evidence drift")
    reference = {
        "route_id": "M_k606208_c33_q88_to_k622592_c34_q88_v1",
        "route_predecessor_screen": {
            "relative_path": ROUTE_PREDECESSOR_SCREEN_NAME,
            "source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
            "file_size_bytes": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SIZE,
            "compiled": False,
            "executed": False,
            "private_entrypoint_called": False,
            "execution_source_layer": False,
        },
        "canonical_transcript": {
            "relative_path": ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
            "semantic_and_file_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
            "file_size_bytes": EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE,
            "records_sha256": EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256,
            "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
            "q88_failure_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q88_FAILURE_SHA256,
            "loaded_before_replay": False,
            "loaded_after_full_replay_as_exact_reference": True,
            "compiled": False,
            "executed": False,
            "propagation_input": False,
            "state_resume_input": False,
            "execution_source_layer": False,
        },
        "q88_threshold_evidence": dict(Q88_THRESHOLD_EVIDENCE),
        "incremental_semantic_delta": {
            "candidate_K_values_changed": True,
            "policy_caps_changed": True,
            "kernel_capability_limits_changed": True,
            "horizon_checkpoint_count": {"before": 88, "after": 88},
        },
    }
    return transcript, reference

def configure_parent_execution(parent: Any, configuration: Any, kernel: Any) -> Dict[str, Any]:
    before = copy.deepcopy(parent.MODE_CONFIG)
    after = copy.deepcopy(before)
    after[MODE]["horizon_checkpoint_count"] = EXTENDED_HORIZON
    changed = []
    for mode, before_mode in before.items():
        for key, value in before_mode.items():
            if after[mode].get(key) != value:
                changed.append(f"MODE_CONFIG.{mode}.{key}")
    expected = [f"MODE_CONFIG.{MODE}.horizon_checkpoint_count"]
    if changed != expected:
        raise RuntimeError("parent configuration changed outside M horizon")
    if after["double_occupancy"] != before["double_occupancy"]:
        raise RuntimeError("parent double-occupancy configuration changed")
    parent.MODE_CONFIG = after
    original = parent.load_execution_sources
    parent.load_v6_configuration = lambda _repo: configuration

    def wrapped(source_repo, helper, mode):
        base_kernel, root, modules, custody = original(source_repo, helper, mode)
        if base_kernel.RESOURCE_LIMITS != EXPECTED_V2_KERNEL_LIMITS:
            raise RuntimeError("v2 arithmetic limits drift")
        if kernel.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_LIMITS:
            raise RuntimeError("wrapped arithmetic limits drift")
        return kernel, root, modules, custody

    parent.load_execution_sources = wrapped
    return {
        "override_id": "magnetization_parent_q88_horizon_override_v1",
        "parent_relative_path": CONTROL_FLOW_PARENT_NAME,
        "parent_source_sha256": EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "parent_module_isolated": True,
        "parent_source_bytes_changed": False,
        "changed_fields": expected,
        "semantic_delta": {expected[0]: {"before": BASE_PARENT_HORIZON, "after": EXTENDED_HORIZON}},
        "parent_mode_config_before": before,
        "parent_mode_config_before_sha256": sha256(canonical_bytes(before)),
        "parent_mode_config_after": after,
        "parent_mode_config_after_sha256": sha256(canonical_bytes(after)),
        "double_occupancy_configuration_unchanged": True,
    }


def normalize_completed_parent_result(result: Any) -> Dict[str, Any]:

    require_exact_keys(
        result,
        UPSTREAM_PARENT_RESULT_KEYS,
        "M q88 completed upstream parent result",
    )
    result = dict(result)
    result["resource_policy_abort"] = None
    result["resource_policy_abort_sha256"] = None
    require_exact_keys(
        result,
        EXPECTED_PARENT_RESULT_KEYS,
        "M q88 normalized parent result",
    )
    return result


def execute_parent_fail_closed(parent: Any, repo: Path) -> Dict[str, Any]:
    """Execute the direct parent; every exception propagates by identity."""

    return normalize_completed_parent_result(parent._run_verified(repo, MODE))

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


def require_exact_keys(
    value: Any,
    expected: frozenset[str],
    label: str,
) -> None:
    if type(value) is not dict:
        raise RuntimeError(f"{label} is not an exact dict")
    observed = frozenset(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise RuntimeError(
            f"{label} exact key-set drift: missing={missing}, extra={extra}"
        )


def validate_parent_source_custody(value: Any) -> Dict[str, str]:
    require_exact_keys(
        value,
        frozenset(EXPECTED_PARENT_SOURCE_CUSTODY),
        "M q88 raw parent source custody",
    )
    for path, expected_sha in EXPECTED_PARENT_SOURCE_CUSTODY.items():
        observed_sha = value.get(path)
        if observed_sha != expected_sha:
            raise RuntimeError(
                f"M q88 raw parent source custody hash drift: {path}"
            )
        if not is_canonical_sha256(observed_sha):
            raise RuntimeError(
                f"M q88 raw parent source custody digest schema drift: {path}"
            )
    return dict(value)


def expected_final_source_custody(
    self_sha: str,
    wrapper_sha: str,
) -> Dict[str, str]:
    if not is_canonical_sha256(self_sha):
        raise RuntimeError("M q88 self custody digest schema drift")
    if wrapper_sha != EXPECTED_KERNEL_WRAPPER_SHA256:
        raise RuntimeError("M q88 wrapper custody digest drift")
    return {
        **EXPECTED_PARENT_SOURCE_CUSTODY,
        SELF_NAME: self_sha,
        CONTROL_FLOW_PARENT_NAME: EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        KERNEL_WRAPPER_NAME: wrapper_sha,
    }


def _validate_row(
    row: Any,
    index: int,
    configured_K: int,
    pre_count: int,
    E_before: int,
    slack: int,
) -> Dict[str, Any]:
    require_exact_keys(row, CANDIDATE_RECORD_KEYS, "candidate row")
    if (
        type(row["candidate_index"]) is not int
        or row["candidate_index"] != index
        or type(row["configured_K"]) is not int
        or row["configured_K"] != configured_K
        or type(row["effective_retained_count"]) is not int
        or row["effective_retained_count"] != min(configured_K, pre_count)
        or type(row["dropped_term_count"]) is not int
        or row["dropped_term_count"] != pre_count - row["effective_retained_count"]
    ):
        raise RuntimeError("candidate row integer relationship drift")
    drop = parse_canonical_nonnegative_decimal(row["drop_ticks"], "candidate drop")
    after = parse_canonical_nonnegative_decimal(
        row["E_after_if_selected_ticks"], "candidate E after"
    )
    if after != E_before + drop:
        raise RuntimeError("candidate row E arithmetic drift")
    if row["dropped_term_count"] == 0 and (
        drop != 0 or after != E_before
    ):
        raise RuntimeError("zero dropped terms must have zero drop and unchanged E")
    if type(row["feasible_under_current_prefix_cap"]) is not bool:
        raise RuntimeError("candidate row feasibility is not boolean")
    if row["feasible_under_current_prefix_cap"] is not (drop <= slack):
        raise RuntimeError("candidate row feasibility arithmetic drift")
    return dict(row)


def _require_appended_not_worse(
    appended: Mapping[str, Any],
    predecessor_max_row: Mapping[str, Any],
    label: str,
) -> None:
    appended_drop = parse_canonical_nonnegative_decimal(
        appended.get("drop_ticks"), f"{label} appended drop"
    )
    predecessor_drop = parse_canonical_nonnegative_decimal(
        predecessor_max_row.get("drop_ticks"), f"{label} predecessor max drop"
    )
    appended_after = parse_canonical_nonnegative_decimal(
        appended.get("E_after_if_selected_ticks"), f"{label} appended E after"
    )
    predecessor_after = parse_canonical_nonnegative_decimal(
        predecessor_max_row.get("E_after_if_selected_ticks"),
        f"{label} predecessor max E after",
    )
    if appended_drop > predecessor_drop or appended_after > predecessor_after:
        raise RuntimeError(f"{label} appended candidate monotonicity drift")


def require_no_resource_policy_abort(result: Mapping[str, Any]) -> None:
    if (
        result.get("resource_policy_abort") is not None
        or result.get("resource_policy_abort_sha256") is not None
        or result.get("screen_terminal_condition") == "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
    ):
        raise RuntimeError("M C34 q88 resource result must fail closed without artifact")


def validate_replay_handoff(
    result: Mapping[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:
    require_exact_keys(result, EXPECTED_PARENT_RESULT_KEYS, "M C34 q88 raw result")
    require_exact_keys(
        predecessor,
        EXPECTED_ROUTE_PREDECESSOR_RESULT_KEYS,
        "M C33 q88 predecessor",
    )
    require_no_resource_policy_abort(result)
    if result.get("candidate_K_values") != list(M_CANDIDATES):
        raise RuntimeError("replay candidate ladder drift")
    if result.get("candidate_K_values_sha256") != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("replay candidate digest drift")
    if result.get("proposed_policy_caps") != {
        **POLICY_CAPS_BASE,
        "max_candidate_count": 34,
    }:
        raise RuntimeError("replay policy caps drift")
    if result.get("kernel_capability_limits") != EXPECTED_WRAPPED_KERNEL_LIMITS:
        raise RuntimeError("replay kernel limits drift")
    records = result.get("records")
    history = result.get("selected_K_history")
    old_records = predecessor.get("records")
    old_history = predecessor.get("selected_K_history")
    if (
        type(records) is not list or len(records) != 88
        or type(history) is not list or len(history) != 88
        or type(old_records) is not list or len(old_records) != 88
        or type(old_history) is not list or len(old_history) != 87
    ):
        raise RuntimeError("q88 replay ledger length drift")
    for index, (record, old) in enumerate(zip(records[:87], old_records[:87])):
        require_exact_keys(record, RECORD_SUCCESS_RECORD_KEYS, f"q{index + 1} success")
        require_exact_keys(old, RECORD_SUCCESS_RECORD_KEYS, f"route q{index + 1} success")
        if not exact_value_equal(_without_candidate_rows(record), _without_candidate_rows(old)):
            raise RuntimeError(f"q{index + 1} common record drift")
        new_rows = record["candidate_records"]
        old_rows = old["candidate_records"]
        if (
            type(new_rows) is not list or len(new_rows) != 34
            or type(old_rows) is not list or len(old_rows) != 33
            or not exact_value_equal(new_rows[:33], old_rows)
        ):
            raise RuntimeError(f"q{index + 1} old candidate rows drift")
        E_before = parse_canonical_nonnegative_decimal(record["E_before_ticks"], "E before")
        slack = parse_canonical_nonnegative_decimal(
            record["prefix_slack_before_selection_ticks"], "prefix slack"
        )
        appended = _validate_row(
            new_rows[33], 33, K622592,
            record["pretruncation_expansion_count"], E_before, slack,
        )
        _require_appended_not_worse(
            appended, old_rows[32], f"q{index + 1}"
        )
        if appended["feasible_under_current_prefix_cap"] is not True:
            raise RuntimeError(f"q{index + 1} appended row must be feasible")
    if not exact_value_equal(history[:87], old_history):
        raise RuntimeError("q1-q87 selected history drift")
    q87 = records[86]
    if (
        q87.get("selected_candidate_index") != 32
        or q87.get("selected_K") != K606208
        or q87.get("E_after_ticks") != EXPECTED_Q87_E_AFTER_TICKS
        or q87.get("retained_expansion_count") != EXPECTED_Q87_RETAINED_COUNT
        or q87.get("retained_expansion_sha256")
        != EXPECTED_Q87_RETAINED_EXPANSION_SHA256
    ):
        raise RuntimeError("q87 committed predecessor state drift")
    q88 = records[87]
    require_exact_keys(q88, RECORD_SUCCESS_RECORD_KEYS, "q88 success")
    old_q88 = old_records[87]
    require_exact_keys(old_q88, RECORD_FAILURE_RECORD_KEYS, "route q88 failure")
    physical = {key: q88.get(key) for key in Q88_PHYSICAL_COMMON_KEYS}
    old_physical = {key: old_q88.get(key) for key in Q88_PHYSICAL_COMMON_KEYS}
    if not exact_value_equal(physical, old_physical):
        raise RuntimeError("q88 propagation/ranking physical fields drift")
    if (
        q88.get("budget_prefix_cap_ticks") != EXPECTED_Q88_PREFIX_CAP_TICKS
        or q88.get("gate_batch_sha256") != EXPECTED_Q88_GATE_BATCH_SHA256
        or q88.get("pretruncation_expansion_count")
        != EXPECTED_Q88_PRETRUNCATION_COUNT
        or q88.get("pretruncation_expansion_sha256")
        != EXPECTED_Q88_PRETRUNCATION_SHA256
        or q88.get("ranked_suffix_sha256") != EXPECTED_Q88_RANKED_SUFFIX_SHA256
    ):
        raise RuntimeError("q88 physical anchor drift")
    rows = q88["candidate_records"]
    old_rows = old_q88["candidate_records"]
    if (
        type(rows) is not list or len(rows) != 34
        or type(old_rows) is not list or len(old_rows) != 33
        or not exact_value_equal(rows[:33], old_rows)
        or any(row["feasible_under_current_prefix_cap"] for row in rows[:33])
    ):
        raise RuntimeError("q88 old candidate rows drift")
    E_before = parse_canonical_nonnegative_decimal(q88["E_before_ticks"], "q88 E before")
    slack = parse_canonical_nonnegative_decimal(
        q88["prefix_slack_before_selection_ticks"], "q88 prefix slack"
    )
    appended = _validate_row(
        rows[33], 33, K622592,
        EXPECTED_Q88_PRETRUNCATION_COUNT, E_before, slack,
    )
    _require_appended_not_worse(appended, old_rows[32], "q88")
    if appended["feasible_under_current_prefix_cap"] is not True:
        raise RuntimeError("q88 K622592 row must be feasible")
    if not (
        EXPECTED_Q88_MINIMUM_EFFECTIVE_K <= K622592
        and EXPECTED_Q88_MINIMUM_EFFECTIVE_K not in M_CANDIDATES
        and old_q88.get("minimum_effective_K_to_meet_prefix")
        == EXPECTED_Q88_MINIMUM_EFFECTIVE_K
        and old_q88.get("required_K_excess_over_policy_maximum")
        == EXPECTED_Q88_OLD_POLICY_SHORTFALL
    ):
        raise RuntimeError("q88 local threshold evidence drift")
    if (
        q88.get("status") != "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
        or q88.get("selected_candidate_index") != 33
        or q88.get("selected_K") != K622592
        or q88.get("selected_effective_retained_count") != K622592
        or q88.get("selected_dropped_term_count")
        != EXPECTED_Q88_PRETRUNCATION_COUNT - K622592
        or q88.get("selected_drop_ticks") != appended["drop_ticks"]
        or q88.get("E_after_ticks") != appended["E_after_if_selected_ticks"]
        or q88.get("retained_expansion_count") != K622592
        or history[-1] != K622592
    ):
        raise RuntimeError("q88 appended row is not first-feasible")
    minimum_retained = parse_canonical_nonnegative_decimal(
        q88.get("minimum_retained_abs_upper_ticks"),
        "q88 minimum retained abs upper",
    )
    maximum_dropped = parse_canonical_nonnegative_decimal(
        q88.get("maximum_dropped_abs_upper_ticks"),
        "q88 maximum dropped abs upper",
    )
    if minimum_retained < maximum_dropped:
        raise RuntimeError("q88 retained/dropped ranking boundary drift")
    for key in (
        "selected_dropped_terms_sha256", "retained_expansion_sha256",
        "minimum_retained_abs_upper_ticks", "maximum_dropped_abs_upper_ticks",
    ):
        if key.endswith("sha256") and not is_canonical_sha256(q88.get(key)):
            raise RuntimeError(f"q88 selected digest drift: {key}")
    expected_summary = {
        "screen_horizon_checkpoint_count": 88,
        "attempted_checkpoint_count": 88,
        "completed_checkpoint_count": 88,
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": True,
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "last_committed_cumulative_drop_ticks": q88["E_after_ticks"],
        "resource_policy_abort": None,
        "resource_policy_abort_sha256": None,
    }
    for key, value in expected_summary.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"q88 terminal summary drift: {key}")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("records digest drift")
    if result.get("selected_K_history_sha256") != sha256(canonical_bytes(history)):
        raise RuntimeError("history digest drift")
    observed = {
        "observed_peak_single_expansion_terms": q88["peak_live_terms_cumulative"],
        "observed_term_gate_visits_including_terminal_attempt": q88[
            "term_gate_visits_cumulative"
        ],
        "observed_maximum_expansion_coefficient_tick_bits": q88[
            "maximum_expansion_coefficient_tick_bits"
        ],
        "observed_maximum_product_bits": q88["maximum_product_bits"],
        "observed_rounding_cumulative_scaled_ticks_squared": q88[
            "rounding_cumulative_scaled_ticks_squared"
        ],
    }
    for key, value in observed.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"observed resource ledger drift: {key}")
    return {
        "validation_id": "M_k622592_c34_q88_post_replay_handoff_v1",
        "fresh_replay_checkpoint_range": [1, 88],
        "q1_through_q87_common_records_exact": True,
        "q1_through_q87_first_33_candidate_rows_exact": True,
        "q1_through_q87_selected_history_exact": True,
        "q87_committed_state_exact": True,
        "q88_propagation_and_ranking_exact": True,
        "q88_first_33_candidate_rows_exact": True,
        "q88_predecessor_failure_record_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_Q88_FAILURE_SHA256
        ),
        "q88_appended_candidate_index": 33,
        "q88_appended_candidate_K": K622592,
        "q88_appended_candidate_first_feasible": True,
        "q88_terminal_branch": "Q88_INDEX33_FIRST_FEASIBLE_SUCCESS",
        "q88_threshold_evidence": dict(Q88_THRESHOLD_EVIDENCE),
        "K607993_execution_row_constructed": False,
        "K607993_drop_ticks_asserted": False,
        "resource_exceptions_fail_closed_without_artifact": True,
        "route_screen_private_entrypoint_called": False,
        "route_screen_compiled_or_executed": False,
        "route_canonical_used_as_state_or_resume_input": False,
        "q88_outcome_precommitted": False,
    }

def execution_components(
    parent_components: Any,
    self_sha: str,
    wrapper_sha: str,
) -> list[Dict[str, Any]]:
    if not exact_value_equal(
        parent_components,
        list(EXPECTED_PARENT_EXECUTION_COMPONENTS),
    ):
        raise RuntimeError("parent execution component schema drift")
    paths = [item["relative_path"] for item in parent_components]
    if len(paths) != len(set(paths)):
        raise RuntimeError("duplicate parent execution component path")
    components = [{
        "relative_path": SELF_NAME,
        "role": "M_k622592_c34_q88_fresh_same_byte_screen",
        "sha256": self_sha,
    }]
    saw_parent = saw_v6 = saw_v2 = False
    forbidden = {
        ROUTE_PREDECESSOR_SCREEN_NAME,
        ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
        "hubbard_l8_adaptive_k_arithmetic_k606208_c33.py",
        "hubbard_l8_adaptive_k_arithmetic_k622592_c36.py",
    }
    for original in parent_components:
        item = dict(original)
        path = item.get("relative_path")
        if path in forbidden:
            raise RuntimeError("reference-only route became an execution component")
        if path == CONTROL_FLOW_PARENT_NAME:
            if item.get("sha256") != EXPECTED_CONTROL_FLOW_PARENT_SHA256:
                raise RuntimeError("control-flow parent component pin drift")
            item["role"] = "four_gate_control_flow_parent_private_entrypoint"
            saw_parent = True
        elif path == V6_BASELINE_CONFIGURATION_NAME:
            if item.get("sha256") != EXPECTED_V6_BASELINE_CONFIGURATION_SHA256:
                raise RuntimeError("v6 baseline component pin drift")
            item["role"] = "v6_baseline_configuration_before_declared_override"
            saw_v6 = True
        elif path == V2_ARITHMETIC_NAME:
            if item.get("sha256") != EXPECTED_V2_ARITHMETIC_SHA256:
                raise RuntimeError("v2 arithmetic component pin drift")
            item["role"] = "v2_arithmetic_bytes_beneath_capability_wrapper"
            saw_v2 = True
        components.append(item)
        if path == V2_ARITHMETIC_NAME:
            components.append({
                "relative_path": KERNEL_WRAPPER_NAME,
                "role": "M_k622592_c34_capability_override_provider",
                "sha256": wrapper_sha,
            })
    if not (saw_parent and saw_v6 and saw_v2):
        raise RuntimeError("parent component set incomplete")
    final_paths = [item["relative_path"] for item in components]
    if len(final_paths) != 11 or len(final_paths) != len(set(final_paths)):
        raise RuntimeError("final execution component closure drift")
    return components


def configuration_reference() -> Dict[str, Any]:
    return {
        "relative_path": V6_BASELINE_CONFIGURATION_NAME,
        "source_sha256": EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "role": "v6_baseline_candidates_and_caps_before_direct_override",
        "baseline_M_candidate_K_values_sha256": (
            EXPECTED_V6_M_CANDIDATE_SHA256
        ),
        "baseline_policy_caps_sha256": EXPECTED_V6_POLICY_CAPS_SHA256,
        "compiled_from_verified_bytes": True,
        "module_isolated": True,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }


def configuration_override(
    baseline_m: Tuple[int, ...],
) -> Dict[str, Any]:
    expected_direct = baseline_m[1:] + (
        K540672, K557056, K573440, K589824, K606208, K622592,
    )
    if baseline_m != V6_M_CANDIDATES or M_CANDIDATES != expected_direct:
        raise RuntimeError("configuration baseline construction drift")
    unchanged = {
        key: value for key, value in EXPECTED_V6_POLICY_CAPS.items()
        if key not in {"max_candidate_K", "max_output_terms_if_successful"}
    }
    return {
        "override_id": "magnetization_k622592_c34_q88_configuration_override_v1",
        "diagnostic_ladder_precommitted_before_replay": True,
        "direct_execution_override_from_v6": {
            "baseline_candidate_K_values_sha256": EXPECTED_V6_M_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 29, "after": 34},
            "candidate_ladder_added": [
                K540672, K557056, K573440, K589824, K606208, K622592,
            ],
            "candidate_ladder_removed": [65_536],
            "policy_cap_changes": {
                "max_candidate_K": {"before": 524_288, "after": K622592},
                "max_output_terms_if_successful": {
                    "before": 524_288, "after": K622592,
                },
            },
        },
        "incremental_route_override_from_k606208_c33_q88": {
            "predecessor_candidate_K_values_sha256": EXPECTED_ROUTE_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 33, "after": 34},
            "candidate_ladder_added": [K622592],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {
                "max_candidate_K": {"before": K606208, "after": K622592},
                "max_output_terms_if_successful": {
                    "before": K606208, "after": K622592,
                },
            },
            "predecessor_configuration_override_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
            ),
        },
        "derived_policy_cap": {
            "field": "max_candidate_count",
            "derivation": "len(candidate_K_values)",
            "before_on_route": 33,
            "after": 34,
        },
        "unchanged_policy_caps": unchanged,
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
    if (
        wrapper_sha != EXPECTED_KERNEL_WRAPPER_SHA256
        or manifest.get("resource_limits_after_extension")
        != EXPECTED_WRAPPED_KERNEL_LIMITS
        or manifest.get("route_predecessor_resource_limits")
        != EXPECTED_ROUTE_KERNEL_LIMITS
        or manifest.get("cross_route_reference_resource_limits")
        != {**EXPECTED_WRAPPED_KERNEL_LIMITS, "max_candidate_count": 36}
    ):
        raise RuntimeError("kernel capability manifest relationship drift")
    return {
        "relative_path": KERNEL_WRAPPER_NAME,
        "source_sha256": wrapper_sha,
        "role": "separate_M_k622592_c34_capability_override_provider",
        "base_arithmetic_relative_path": V2_ARITHMETIC_NAME,
        "base_arithmetic_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "module_itself_is_extended_kernel": True,
        "verified_compilation_inputs": [
            "_VERIFIED_SELF_SOURCE_BYTES", "_VERIFIED_BASE_KERNEL_SOURCE_BYTES",
        ],
        "capability_manifest": dict(manifest),
        "capability_manifest_sha256": sha256(canonical_bytes(manifest)),
        "direct_capability_changes_from_v2": {
            "max_candidate_count": {"before": 32, "after": 34},
            "max_retained_K": {"before": 524_288, "after": K622592},
        },
        "incremental_route_changes_from_k606208_c33": {
            "max_candidate_count": {"before": 33, "after": 34},
            "max_retained_K": {"before": K606208, "after": K622592},
        },
        "same_K_cross_route_reference_to_D_k622592_c36": {
            "max_candidate_count": {"this_route": 34, "cross_route": 36},
            "max_retained_K": {"this_route": K622592, "cross_route": K622592},
            "compiled": False, "executed": False, "execution_source_layer": False,
        },
        "execution_source_layers": [KERNEL_WRAPPER_NAME, V2_ARITHMETIC_NAME],
        "route_predecessor_is_execution_source": False,
        "cross_route_reference_is_execution_source": False,
        "v2_arithmetic_module_mutated_by_screen": False,
    }

def validate_and_relabel(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
    route_reference: Mapping[str, Any],
    baseline_m: Tuple[int, ...],
    wrapper_sha: str,
    manifest: Mapping[str, Any],
    horizon_override: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("M q88 relabel requires fresh same-byte self execution")
    if (
        horizon_override.get("changed_fields")
        != [f"MODE_CONFIG.{MODE}.horizon_checkpoint_count"]
        or horizon_override.get("semantic_delta")
        != {
            f"MODE_CONFIG.{MODE}.horizon_checkpoint_count": {
                "before": BASE_PARENT_HORIZON,
                "after": EXTENDED_HORIZON,
            }
        }
        or horizon_override.get(
            "double_occupancy_configuration_unchanged"
        ) is not True
    ):
        raise RuntimeError("M q88 parent horizon override drift")

    handoff = validate_replay_handoff(result, predecessor)
    old_components = result["screen_execution_components"]
    if result["screen_execution_components_sha256"] != sha256(
        canonical_bytes(old_components)
    ):
        raise RuntimeError("parent component digest drift")
    old_configuration_reference = result["configuration_reference"]
    if result["configuration_reference_sha256"] != sha256(
        canonical_bytes(old_configuration_reference)
    ):
        raise RuntimeError("parent configuration reference digest drift")
    old_transform = result["checkpoint_transform"]
    old_transform_sha = result["checkpoint_transform_sha256"]
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("parent transform digest drift")

    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = execution_components(
        old_components,
        self_sha,
        wrapper_sha,
    )
    baseline_reference = configuration_reference()
    config = configuration_override(baseline_m)
    capability = kernel_capability_override(wrapper_sha, manifest)
    transform = {
        "transform_id": "magnetization_four_gate_k622592_c34_q88_v1",
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": (
            old_transform_sha
        ),
        "route_predecessor_transform_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256
        ),
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "q88_outcome_precommitted": False,
        "incremental_route_semantic_delta": {
            "candidate_K_values_changed": True,
            "policy_caps_changed": True,
            "kernel_capability_limits_changed": True,
            "horizon_checkpoint_count": {"before": 88, "after": 88},
        },
        "overridden_semantics": [
            "candidate_K_values",
            "policy_max_candidate_K",
            "policy_max_output_terms_if_successful",
            "derived_policy_max_candidate_count",
            "kernel_max_retained_K",
            "kernel_max_candidate_count",
        ],
    }

    parent_custody = validate_parent_source_custody(result["source_custody"])
    custody = expected_final_source_custody(self_sha, wrapper_sha)
    if parent_custody != {
        path: custody[path] for path in EXPECTED_PARENT_SOURCE_CUSTODY
    }:
        raise RuntimeError("M q88 parent custody changed during relabel")
    if len(custody) != 10:
        raise RuntimeError("M q88 final source custody cardinality drift")
    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k622592_c34_q88_screen_v1"
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
        "control_flow_parent_runtime_horizon_override_applied": True,
        "v6_configuration_source_used_as_baseline_only": True,
        "v6_runtime_configuration_override_applied": True,
        "v2_arithmetic_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "v2_arithmetic_compiled_from_verified_bytes": True,
        "arithmetic_kernel_commit_role": (
            "base_v2_arithmetic_implementation_commit_before_"
            "capability_override"
        ),
        "kernel_capability_wrapper_relative_path": KERNEL_WRAPPER_NAME,
        "kernel_capability_wrapper_source_sha256": wrapper_sha,
        "kernel_capability_wrapper_compiled_from_verified_bytes": True,
        "kernel_capability_wrapper_module_isolated": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(
            canonical_bytes(components)
        ),
        "configuration_reference": baseline_reference,
        "configuration_reference_sha256": sha256(
            canonical_bytes(baseline_reference)
        ),
        "configuration_override": config,
        "configuration_override_sha256": sha256(canonical_bytes(config)),
        "kernel_capability_override": capability,
        "kernel_capability_override_sha256": sha256(
            canonical_bytes(capability)
        ),
        "parent_horizon_override": dict(horizon_override),
        "parent_horizon_override_sha256": sha256(
            canonical_bytes(horizon_override)
        ),
        "route_predecessor_reference": dict(route_reference),
        "route_predecessor_reference_sha256": sha256(
            canonical_bytes(route_reference)
        ),
        "predecessor_handoff_validation": handoff,
        "predecessor_handoff_validation_sha256": sha256(
            canonical_bytes(handoff)
        ),
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
    if not exact_value_equal(
        result["source_custody"],
        expected_final_source_custody(self_sha, wrapper_sha),
    ):
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
    parent = load_control_flow_parent(repo)
    configuration, baseline_m = load_configured_v6_baseline(repo)
    wrapper, wrapper_sha, manifest = load_kernel_wrapper(repo)
    horizon = configure_parent_execution(parent, configuration, wrapper)
    result = execute_parent_fail_closed(parent, repo)
    predecessor, route_reference = load_route_reference(repo)
    return validate_and_relabel(
        result,
        predecessor,
        route_reference,
        baseline_m,
        wrapper_sha,
        manifest,
        horizon,
    )

def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_magnetization_k622592_c34_q88_screen")
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
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, prefix=output.name + ".", suffix=".tmp", delete=False) as handle:
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
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "attempted_checkpoint_count": result["attempted_checkpoint_count"],
        "final_status": final["status"],
        "final_checkpoint": final["checkpoint_number_one_based"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
