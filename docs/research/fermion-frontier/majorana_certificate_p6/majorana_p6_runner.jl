#!/usr/bin/env julia

# Formal P6 S0 runner for the single E768-MAX-LAZY37-V1 candidate.  It imports
# the frozen P4 closure so step 1 remains the exact P3 2^-34 execution.  The
# P5 step-2 kernel is frozen directly below with exactly three adaptive-drop
# hooks; no runtime source transform and no D0 control path exists here.  No
# P3/P4/P5 result artifact or non-authoritative P6 D0 policy/report is opened.
include(joinpath(@__DIR__, "..", "majorana_certificate_p4", "majorana_p4_runner.jl"))

const P6_FIXTURE_CANONICAL_SHA256 =
    "10bb6f8877abcf4fe6453e65825b288f6236b8aa3c9d799ce4a5c7c81ae96760"
const P6_FIXTURE_ID = "MAJORANA-P6-L8-E768-MAX-LAZY37-S0-V1"
const P6_WITNESS_TYPE =
    "majorana_p6_L8_E768_MAX_LAZY37_execution_raw_v1"
const P6_DIRECT_DESIGN_PARENT = "f62005b435a0c033d42aae0d05c05e234faab059"
const P6_D0_POLICY_ID = "MAJORANA-P6-E768-MAX-LAZY37-D0-V1"
const P6_D0_POLICY_SHA256 =
    "6a8b9c1c2584cbe8998643e0644f35896d54fe57444eff795a93a83987fa87ab"
const P6_D0_REPORT_SHA256 =
    "7c591111ee99b18bf2ccaca2d8157e93a19a3db49b6a680c01b0be13f570fc56"
const P6_ADAPTIVE_CANDIDATE_ID = "E768-MAX-LAZY37-V1"
const P6_ALGORITHM_ID = "MAJORANA-P6-E768-MAX-LAZY37-V1"

const P6_GRID_DENOMINATOR = BigInt(1) << 128
const P6_LOCAL_ALLOCATION_DENOMINATOR = BigInt(400000)
const P6_MAXIMUM_STRICTLY_LEGAL_LOCAL_TICKS =
    fld(P6_GRID_DENOMINATOR - 1, P6_LOCAL_ALLOCATION_DENOMINATOR)
const P6_BOUNDARY_COUNT = 768
const P6_K37_THRESHOLD = ldexp(1.0, -37)
const P6_K37_ABS_BITS = UInt64(0x3da0000000000000)
const P6_ABS_BITS_MASK = UInt64(0x7fffffffffffffff)

const P6_STEP2_CAP_VALUES = (
    maximum_step2_accuracy_charged_events=67108864,
    maximum_step2_anticommuting_events=16777216,
    maximum_step2_boundary_retained_terms=1048576,
    maximum_step2_cap_scan_term_visits=536870912,
    maximum_step2_current_terms_before_constituent=1048576,
    maximum_step2_drop_defect_events=16777216,
    maximum_step2_final_retained_terms=1048576,
    maximum_step2_merge_defect_events=4194304,
    maximum_step2_premerge_terms=1048576,
    maximum_step2_product_defect_events=33554432,
    maximum_step2_propagation_term_visits=536870912,
    maximum_step2_total_P2_charged_term_visits=1073741824,
    maximum_step2_total_P2_plus_accuracy_charged_events=1073741824,
    maximum_step2_truncation_term_visits=268435456,
)

const P6_SELECTION_CAP_VALUES = (
    maximum_ranking_scan_term_visits=268435456,
    maximum_sort_input_items=67108864,
    maximum_tick_evaluations=67108864,
    maximum_selected_membership_insertions=16777216,
    maximum_peak_ranking_buffer_terms=1048576,
    maximum_total_selection_work_units=536870912,
)

function p6_require_exact_keys(value, expected, context::AbstractString)
    value isa AbstractDict || error("$(context) must be an object")
    actual = Set(String.(keys(value)))
    wanted = Set(String.(expected))
    actual == wanted || error("$(context) key mismatch")
    return value
end

function p6_require_exact_boolean(value, context::AbstractString)
    value isa Bool || error("$(context) must be Boolean")
    return value
end

function p6_require_exact_positive_cap(value, expected::Int, context::AbstractString)
    value isa Integer || error("$(context) must be an integer")
    Int(value) == expected || error("$(context) drift")
    return value
end

function p6_next_power_of_two(value::Int)
    value > 0 || error("P6 schema byte bound must be positive")
    result = 1
    while result < value
        result <= typemax(Int) ÷ 2 || error("P6 schema byte bound overflow")
        result *= 2
    end
    return result
end

function validate_p6_fixture(fixture)
    canonical_sha256(fixture) == P6_FIXTURE_CANONICAL_SHA256 ||
        error("P6 fixture differs from the frozen semantic object")
    p6_require_exact_keys(fixture, (
        "schema_version", "fixture_id", "direct_design_parent",
        "frozen_execution_relation", "adaptive_candidate",
        "full_domain_adaptive_rule", "exact_lazy_implementation",
        "outward_arithmetic", "deterministic_resource_caps",
        "deterministic_selection_caps", "host_supervisor_caps",
        "conditional_authority", "scientific_output_schema_budget", "scope",
    ), "P6 fixture")
    fixture["schema_version"] == 1 || error("unexpected P6 fixture schema")
    fixture["fixture_id"] == P6_FIXTURE_ID || error("unexpected P6 fixture identity")

    expected_parent = Dict{String,Any}(
        "commit_sha" => P6_DIRECT_DESIGN_PARENT,
        "D0_policy_id" => P6_D0_POLICY_ID,
        "D0_policy_sha256" => P6_D0_POLICY_SHA256,
        "D0_report_sha256" => P6_D0_REPORT_SHA256,
        "D0_report_available_to_runner" => false,
        "formal_caps_derived_before_this_fixture" => true,
        "role" => "direct_resource_design_parent_only_not_a_formal_runner_input",
    )
    fixture["direct_design_parent"] == expected_parent ||
        error("P6 direct design-parent custody drift")

    expected_relation = Dict{String,Any}(
        "workload_fixture" => "MAJORANA-P5-L8-CONDITIONAL-STEP2-THRESHOLD-S0-V1",
        "P5_fixture_is_read_only_workload_custody_input" => true,
        "P5_runner_is_not_a_formal_stage_input" => true,
        "formal_P6_runner_is_standalone_and_precommitted" => true,
        "observable" => "normalized_staggered_magnetization",
        "initial_state" => "checkerboard_Neel_A_up_B_down_Nup32_Ndown32",
        "linear_size" => 8,
        "n_sites" => 64,
        "n_fermionic_modes" => 128,
        "n_majorana_generators" => 256,
        "mask_type" => "UInt256",
        "exact_mapped_step_duration" => "1/100",
        "trotter_steps_in_campaign" => 100,
        "mapped_step_indices" => Any[1, 2],
        "fused_stage_order_per_step" =>
            Any["H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1"],
        "composite_count_per_step" => 512,
        "constituent_count_per_step" => 1152,
        "truncation_boundary_count_per_step" => 768,
        "total_composite_count_if_completed" => 1024,
        "total_constituent_count_if_completed" => 2304,
        "total_truncation_boundary_count_if_completed" => 1536,
        "step1_threshold_exponent" => 34,
        "step1_threshold_rational" => "1/17179869184",
        "step1_threshold_Float64_bits_hex" => "3dd0000000000000",
        "step1_uses_the_unmodified_P3_2_pow_minus_34_route" => true,
        "step1_P3_fieldwise_conformance_required" => true,
        "step1_P3_fieldwise_conformance_required_before_parent_error_inheritance" => true,
        "same_process_step1_then_adaptive_step2" => true,
        "step2_input_is_live_deepcopy_of_step1_retained_mainsum" => true,
        "checkpoint_serialization_or_cross_process_resume_forbidden" => true,
        "runner_must_not_read_any_result_or_D0_bytes" => true,
        "required_base_fixture_sha256" => Dict{String,Any}(
            "P2" => "252fa0c4ed26db5581bcd9ff0101d18d858faf6d31fb9b6cdcaa821bf318e82a",
            "P3" => "a478b783ae4005f7ef79572a4b34eee72299da262e439bdc35eca13496bdc236",
            "P4" => "b020b6bcc0ed56010af9ed3b1836469c084b9244a9303a8101cf7657adb79964",
            "P5" => "fd8b46c8761f548d615042b24f8ec85b32891e4f42dbafdd9bd70d58379a8afb",
        ),
    )
    fixture["frozen_execution_relation"] == expected_relation ||
        error("P6 frozen execution relation drift")
    L == 8 && NSITES == 64 && NMODES == 128 ||
        error("P6 imported workload constants drift")
    reinterpret(UInt64, EPSILON) == 0x3dd0000000000000 ||
        error("P6 imported P3 threshold bits drift")

    expected_candidate = Dict{String,Any}(
        "candidate_id" => P6_ADAPTIVE_CANDIDATE_ID,
        "algorithm_id" => P6_ALGORITHM_ID,
        "formal_candidate_count" => 1,
        "fresh_process_count" => 2,
        "step1_threshold_Float64_bits_hex" => "3dd0000000000000",
        "lazy_anchor_Float64_bits_hex" => "3da0000000000000",
        "each_fresh_process_starts_from_O0" => true,
        "both_fresh_processes_execute_complete_step1_and_step2" => true,
        "replays_share_no_process_state_cache_checkpoint_scratch_or_depot_prefix" => true,
        "P5_K37_resource_control_is_not_a_formal_candidate_or_stage_input" => true,
        "D0_control_is_not_a_formal_candidate" => true,
        "candidate_selection_CLI_or_environment_override_forbidden" => true,
        "fallback_no_drop_fixed_threshold_or_alternative_candidate_forbidden" => true,
        "candidate_is_frozen_before_any_formal_P6_output" => true,
    )
    fixture["adaptive_candidate"] == expected_candidate ||
        error("P6 adaptive candidate drift")

    expected_rule = Dict{String,Any}(
        "grid_denominator" => string(P6_GRID_DENOMINATOR),
        "grid_definition" => "2^128",
        "local_allocation_denominator" => 400000,
        "local_allocation" => "1/400000",
        "maximum_strictly_legal_local_ticks" =>
            string(P6_MAXIMUM_STRICTLY_LEGAL_LOCAL_TICKS),
        "maximum_strictly_legal_local_ticks_formula" =>
            "floor((2^128-1)/400000)",
        "boundary_count" => P6_BOUNDARY_COUNT,
        "raw_boundary_indices" => "0_through_767",
        "released_prefix_number_q" =>
            "raw_boundary_index_plus_one_in_1_through_768",
        "prefix_target_formula" =>
            "floor(((raw_boundary_index+1)*maximum_strictly_legal_local_ticks)/768)",
        "prefix_target_is_cumulative_not_incremental" => true,
        "available_ticks_formula" =>
            "max(0,prefix_target_ticks-cumulative_product_ticks-cumulative_merge_ticks-cumulative_previous_drop_ticks)",
        "postmerge_snapshot_precedes_any_drop" => true,
        "postmerge_snapshot_is_immutable_for_the_boundary_selection" => true,
        "ranking_domain" => "every_row_in_the_immutable_postmerge_snapshot",
        "ranking_key" => Any[
            "exact_point_abs_ticks_ascending",
            "sign_cleared_binary64_magnitude_bits_ascending",
            "unsigned_majorana_mask_ascending",
        ],
        "selection_rule" =>
            "longest_sorted_prefix_whose_rowwise_tick_sum_is_at_most_available_ticks",
        "exact_fit_is_selected" => true,
        "zero_cost_rows_are_selected_at_zero_available_ticks" => true,
        "stop_at_first_unaffordable_positive_cost_row_without_skipping" => true,
        "first_unaffordable_positive_row_stops_without_skipping" => true,
        "ranking_is_not_recomputed_after_each_deletion" => true,
        "all_deletions_occur_only_after_membership_is_frozen" => true,
        "unused_prefix_budget_carries_forward_implicitly" => true,
        "future_prefix_budget_cannot_be_borrowed" => true,
        "drop_ticks_are_never_refunded_after_merge_cancellation_reappearance_or_state_removal" =>
            true,
        "product_merge_and_drop_share_one_local_prefix_ledger" => true,
        "final_local_allocation_is_recomputed_by_the_formal_outer_checker" => true,
        "does_not_claim_global_optimality_across_future_boundaries" => true,
    )
    fixture["full_domain_adaptive_rule"] == expected_rule ||
        error("P6 full-domain adaptive rule drift")

    expected_lazy = Dict{String,Any}(
        "split_threshold_exponent" => 37,
        "split_threshold_rational" => "1/137438953472",
        "split_threshold_Float64_bits_hex" => "3da0000000000000",
        "scientific_role" =>
            "implementation_only_exact_initial_segment_accelerator_not_a_scientific_eligibility_gate",
        "tier1_predicate" =>
            "sign_cleared_magnitude_bits_strictly_less_than_split_threshold_bits",
        "tier1_is_a_provable_initial_segment_of_the_full_ranking" => true,
        "one_lightweight_full_identity_and_coefficient_bits_snapshot_is_frozen" => true,
        "only_tier_rows_enter_costly_rank_buffers" => true,
        "if_budget_is_exhausted_inside_tier1_stop_without_tier2" => true,
        "if_tier1_is_fully_selected_with_positive_remainder_rescan_the_same_unmodified_snapshot" =>
            true,
        "tier2_collects_every_nonpool_row_whose_exact_cost_is_at_most_the_current_remainder" =>
            true,
        "tier2_uses_the_same_full_ranking_key_and_prefix_rule" => true,
        "hard_K37_eligibility_gate_is_forbidden" => true,
        "callback_only_tests_precomputed_membership" => true,
        "callback_iteration_order_cannot_consume_budget" => true,
        "callback_revalidates_selected_coefficient_bits" => true,
        "prepare_helper_reads_but_never_mutates_live_merged_main_or_authoritative_ticks" =>
            true,
        "all_deletions_are_performed_only_by_the_existing_truncate_callback" => true,
        "existing_drop_ledger_is_the_only_authoritative_drop_charge" => true,
        "existing_drop_ledger_recomputes_and_must_equal_the_selection_cost" => true,
        "independent_checker_uses_a_full_domain_bruteforce_sort_not_this_lazy_implementation" =>
            true,
    )
    fixture["exact_lazy_implementation"] == expected_lazy ||
        error("P6 exact lazy implementation drift")

    expected_arithmetic = Dict{String,Any}(
        "defect_grid_denominator" => string(P6_GRID_DENOMINATOR),
        "trig_grid_denominator" => string(P6_GRID_DENOMINATOR),
        "maximum_BigInt_bit_length" => 2048,
        "maximum_trig_table_entries" => 6,
        "drop_row_cost" =>
            "ceil(2^128_times_exact_abs_of_original_finite_binary64_coefficient)",
        "each_product_merge_and_drop_row_is_individually_rounded_outward_before_accumulation" =>
            true,
        "budget_schedule_ledger_and_allocation_comparisons_use_BigInt_only" => true,
        "outward_integer_binary64_RNE_oracle_required" => true,
        "rounding_mode" => "binary64_round_to_nearest_ties_to_even",
        "positive_and_negative_zero_have_zero_cost_but_remain_bitwise_distinct" => true,
        "original_coefficient_bits_are_bound_in_drop_state_and_contribution_commitments" =>
            true,
        "NaN_or_infinite_coefficients_are_invalid" => true,
    )
    fixture["outward_arithmetic"] == expected_arithmetic ||
        error("P6 outward arithmetic drift")
    P6_GRID_DENOMINATOR == P3_GRID_DENOMINATOR || error("P6/P3 grid mismatch")

    expected_caps = Dict{String,Any}(
        "cap_scope" =>
            "one_fixed_candidate_step2_local_caps_after_a_complete_fresh_P3_compatible_step1_reconstruction",
        "maximum_BigInt_bit_length" => 2048,
        "maximum_trig_table_entries" => 6,
        (String(name) => value for (name, value) in pairs(P6_STEP2_CAP_VALUES))...,
        "maximum_two_step_accuracy_charged_events" => 69206016,
        "maximum_two_step_total_P2_charged_term_visits" => 1140850688,
        "maximum_two_step_total_P2_plus_accuracy_charged_events" => 1140850688,
        "step1_reconstruction_remains_subject_to_the_pinned_P3_and_P2_caps" => true,
        "caps_are_checked_before_the_rejected_operation" => true,
        "caps_are_checked_before_the_corresponding_scan_allocation_sort_or_tick_evaluation" =>
            true,
        "no_operation_occurs_after_the_first_deterministic_cap_event" => true,
        "BigInt_bit_length_is_checked_after_each_tick_computation_and_cumulative_update" =>
            true,
        "the_same_caps_apply_to_both_fresh_replays" => true,
    )
    fixture["deterministic_resource_caps"] == expected_caps ||
        error("P6 deterministic resource caps drift")

    expected_selection_caps = Dict{String,Any}(
        (String(name) => value for (name, value) in pairs(P6_SELECTION_CAP_VALUES))...,
    )
    fixture["deterministic_selection_caps"] == expected_selection_caps ||
        error("P6 deterministic selection caps drift")

    expected_host = Dict{String,Any}(
        "MemoryMax_bytes" => 2147483648,
        "MemorySwapMax_bytes" => 0,
        "RuntimeMaxSec" => "1800s",
        "outer_safety_timeout_seconds" => 1830,
        "maximum_stdout_bytes" => 33554432,
        "maximum_stderr_bytes" => 4096,
        "maximum_persisted_result_bytes" => 67108864,
        "systemd_user_scope_cgroup_v2_required" => true,
        "network_namespace_unshared" => true,
        "PID_namespace_unshared" => true,
        "private_proc_and_dev_required" => true,
        "fresh_writable_scratch_and_depot_prefix_per_process" => true,
        "successful_formal_runner_stderr_must_be_empty" => true,
        "host_cap_failure_branch" => "INDETERMINATE",
        "host_failure_has_no_mathematical_allocation_or_candidate_authority" => true,
        "caps_cannot_be_relaxed_in_place_after_a_failure" => true,
    )
    fixture["host_supervisor_caps"] == expected_host ||
        error("P6 host supervisor caps drift")

    expected_authority = Dict{String,Any}(
        "formal_authority" =>
            "fixed_L8_P3_2^-34_step1_then_E768_MAX_LAZY37_V1_step2_two_step_operator_and_checkerboard_Neel_enclosure_only",
        "fresh_process_count" => 2,
        "both_raw_replays_must_complete_before_scientific_outer_reconstruction" => true,
        "both_raw_replays_must_be_byte_identical" => true,
        "complete_P3_step1_fieldwise_conformance_precedes_P3_E1_decoding" => true,
        "P3_E1_is_inherited_exactly_once" => true,
        "step2_local_increment" =>
            "step2_product_ticks_plus_step2_merge_ticks_plus_executed_step2_drop_ticks",
        "two_step_cumulative_increment" =>
            "once_inherited_conformed_P3_E1_plus_step2_local_increment",
        "step2_local_allocation" => "1/400000",
        "candidate_local_allocation" => "1/400000",
        "conditional_two_step_cumulative_allocation" => "1/200000",
        "local_pass_iff" =>
            "step2_local_increment_ticks_times_400000_strictly_less_than_2^128",
        "cumulative_pass_iff" =>
            "two_step_cumulative_ticks_times_200000_strictly_less_than_2^128",
        "allocation_equality_is_failure" => true,
        "allocation_comparisons_use_exact_integer_cross_multiplication_only" => true,
        "positive_iff_local_and_cumulative_pass" => true,
        "candidate_qualification_is_outer_checker_only" => true,
        "P3_E1_charge_multiplicity" => 1,
        "local_pass_and_cumulative_fail_is_invalid_after_complete_P3_conformance" => true,
        "runner_emits_no_accept_reject_selection_or_allocation_pass_bit" => true,
        "outer_checker_alone_reconstructs_membership_ledgers_allocations_and_terminal_branch" =>
            true,
        "deterministic_cap_branch_has_resource_guard_authority_only" => true,
        "host_or_generation_failure_branch" => "INDETERMINATE",
        "custody_schema_determinism_or_scientific_reconstruction_failure_branch" =>
            "INVALID_REPLAY",
    )
    fixture["conditional_authority"] == expected_authority ||
        error("P6 conditional authority drift")

    expected_budget = Dict{String,Any}(
        "derivation_is_frozen_and_result_blind_before_formal_execution" => true,
        "maximum_decimal_BigInt_characters" => 617,
        "maximum_transition_record_count" => 2304,
        "maximum_transition_record_bytes" => 8192,
        "maximum_boundary_record_count" => 1536,
        "maximum_boundary_record_bytes" => 6144,
        "maximum_stage_record_count" => 1024,
        "maximum_stage_record_bytes" => 2048,
        "fixed_envelope_max_bytes" => 2097152,
        "raw_witness_schema_max_bytes" => 32505856,
        "stdout_cap_rule" =>
            "smallest_power_of_two_at_least_raw_witness_schema_max_bytes",
        "maximum_stdout_bytes" => 33554432,
        "fresh_process_count" => 2,
        "persisted_result_cap_rule" =>
            "fresh_process_count_times_maximum_stdout_bytes",
        "maximum_persisted_result_bytes" => 67108864,
        "full_ranking_or_membership_arrays_forbidden" => true,
    )
    fixture["scientific_output_schema_budget"] == expected_budget ||
        error("P6 scientific output schema budget drift")
    raw_bound = expected_budget["maximum_transition_record_count"] *
        expected_budget["maximum_transition_record_bytes"] +
        expected_budget["maximum_boundary_record_count"] *
        expected_budget["maximum_boundary_record_bytes"] +
        expected_budget["maximum_stage_record_count"] *
        expected_budget["maximum_stage_record_bytes"] +
        expected_budget["fixed_envelope_max_bytes"]
    raw_bound == expected_budget["raw_witness_schema_max_bytes"] ||
        error("P6 raw witness schema-bound arithmetic drift")
    p6_next_power_of_two(raw_bound) == expected_budget["maximum_stdout_bytes"] ||
        error("P6 stdout cap derivation drift")
    expected_budget["fresh_process_count"] * expected_budget["maximum_stdout_bytes"] ==
        expected_budget["maximum_persisted_result_bytes"] ||
        error("P6 persisted-result cap derivation drift")
    expected_host["maximum_stdout_bytes"] == expected_budget["maximum_stdout_bytes"] ||
        error("P6 host/schema stdout cap mismatch")
    expected_host["maximum_persisted_result_bytes"] ==
        expected_budget["maximum_persisted_result_bytes"] ||
        error("P6 host/schema persisted cap mismatch")

    expected_scope = Dict{String,Any}(
        "fixed_L8_P3_step1_then_one_candidate_step2_only" => true,
        "step1_fixed_2^-34_path_is_unchanged" => true,
        "adaptive_step2_local_defect_and_Neel_enclosure" => "ASSESSED",
        "candidate_qualification_and_cumulative_allocation" => "OUTER_CHECKER_ONLY",
        "global_two_step_or_coefficientwise_interval_state" =>
            "NOT_CLAIMED_BY_RUNNER",
        "full_domain_prefix_escrow_drop_set" => "ASSESSED",
        "remaining_98_mapped_steps_or_full_R100" => "NOT_ASSESSED",
        "product_formula_to_exact_Hubbard_error_or_exact_time_evolution" =>
            "NOT_ASSESSED",
        "double_occupancy" => "NOT_ASSESSED",
        "arbitrary_initial_state_or_lattice_size" => "NOT_CLAIMED",
        "P3_P4_or_P5_result_available_to_runner" => false,
        "D0_report_is_not_a_runner_input" => true,
        "scientific_authority_claimed_by_raw_witness" => false,
        "physical_reference_qualified" => false,
        "ready_gate_eligible" => false,
    )
    fixture["scope"] == expected_scope || error("P6 scope drift")
    return fixture
end
function p6_step2_execution_fixture(p6_fixture, p3_fixture)
    result = deepcopy(p3_fixture)
    caps = p6_fixture["deterministic_resource_caps"]
    result["outward_arithmetic"]["maximum_BigInt_bit_length"] =
        p6_fixture["outward_arithmetic"]["maximum_BigInt_bit_length"]
    result["deterministic_resource_caps"] = Dict{String,Any}(
        "maximum_trig_table_entries" => caps["maximum_trig_table_entries"],
        "maximum_anticommuting_events" =>
            caps["maximum_step2_anticommuting_events"],
        "maximum_product_defect_events" =>
            caps["maximum_step2_product_defect_events"],
        "maximum_merge_defect_events" =>
            caps["maximum_step2_merge_defect_events"],
        "maximum_drop_defect_events" =>
            caps["maximum_step2_drop_defect_events"],
        "maximum_accuracy_charged_events" =>
            caps["maximum_step2_accuracy_charged_events"],
        "maximum_total_P2_plus_accuracy_charged_events" =>
            caps["maximum_step2_total_P2_plus_accuracy_charged_events"],
    )
    return result
end

mutable struct P6SelectionResourceCounters
    total_ranking_scan_term_visits::Int
    total_sort_work_items::Int
    total_tick_evaluations::Int
    total_selected_membership_insertions::Int
    peak_ranking_buffer_terms::Int
    total_selection_work_units::Int
    completed_selection_boundary_count::Int
end

P6SelectionResourceCounters() = P6SelectionResourceCounters(0, 0, 0, 0, 0, 0, 0)

const P6_ACTIVE_SELECTION_CAPS = Ref{Any}(nothing)
const P6_SELECTION_RESOURCES = Ref(P6SelectionResourceCounters())

struct P6SnapshotRow
    mask::Any
    coefficient::Float64
    coefficient_bits::UInt64
    abs_bits::UInt64
end

struct P6RankRow
    snapshot::P6SnapshotRow
    point_cost::BigInt
end

mutable struct P6BoundaryDropDecision
    boundary_index::Int
    snapshot_count::Int
    snapshot_coefficient_bits::Dict{Any,UInt64}
    selected_costs::Dict{Any,BigInt}
    callback_seen_masks::Set{Any}
    callback_visit_count::Int
    validated::Bool
end

function p6_public_selection_resources()
    counters = P6_SELECTION_RESOURCES[]
    counters.total_selection_work_units ==
        counters.total_ranking_scan_term_visits +
        counters.total_sort_work_items +
        counters.total_tick_evaluations +
        counters.total_selected_membership_insertions ||
        error("P6 selection-work accounting identity failed")
    return (
        total_ranking_scan_term_visits=
            counters.total_ranking_scan_term_visits,
        total_sort_work_items=counters.total_sort_work_items,
        total_tick_evaluations=counters.total_tick_evaluations,
        total_selected_membership_insertions=
            counters.total_selected_membership_insertions,
        peak_ranking_buffer_terms=counters.peak_ranking_buffer_terms,
        total_selection_work_units=counters.total_selection_work_units,
        completed_selection_boundary_count=
            counters.completed_selection_boundary_count,
    )
end

function p6_reset_selection_state!(caps)
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P6 selection caps are already active")
    caps isa AbstractDict || error("P6 selection caps must be an object")
    P6_ACTIVE_SELECTION_CAPS[] = caps
    P6_SELECTION_RESOURCES[] = P6SelectionResourceCounters()
    return nothing
end

function p6_clear_selection_state!()
    P6_ACTIVE_SELECTION_CAPS[] = nothing
    return nothing
end

function p6_prefix_target(boundary_index::Int)::BigInt
    0 <= boundary_index < P6_BOUNDARY_COUNT ||
        error("P6 boundary index outside 0:767")
    return fld(
        BigInt(boundary_index + 1) * P6_MAXIMUM_STRICTLY_LEGAL_LOCAL_TICKS,
        BigInt(P6_BOUNDARY_COUNT),
    )
end

p6_abs_bits(value::Float64)::UInt64 =
    reinterpret(UInt64, value) & P6_ABS_BITS_MASK

function p6_selection_cap_context(
    boundary_index::Int, operation::AbstractString,
)
    return (boundary_index=boundary_index, operation=String(operation))
end

function p6_charge_selection!(
    field::Symbol, amount::Int, cap_key::String,
    boundary_index::Int, operation::AbstractString,
)
    amount >= 0 || error("negative P6 selection-resource charge")
    amount == 0 && return nothing
    caps = P6_ACTIVE_SELECTION_CAPS[]
    caps === nothing && error("P6 selection caps are inactive")
    counters = P6_SELECTION_RESOURCES[]
    current = getfield(counters, field)
    amount <= typemax(Int) - current || error("P6 selection counter overflow")
    attempted = current + amount
    limit = Int(caps[cap_key])
    attempted <= limit || throw(CapExceeded(
        cap_key, limit, attempted,
        p6_selection_cap_context(boundary_index, operation),
    ))

    total_current = counters.total_selection_work_units
    amount <= typemax(Int) - total_current ||
        error("P6 total selection-work counter overflow")
    total_attempted = total_current + amount
    total_limit = Int(caps["maximum_total_selection_work_units"])
    total_attempted <= total_limit || throw(CapExceeded(
        "maximum_total_selection_work_units", total_limit, total_attempted,
        p6_selection_cap_context(boundary_index, operation),
    ))

    # Both component and combined checks precede either counter update and the
    # scan, allocation, sort, tick evaluation, or insertion being charged.
    setfield!(counters, field, attempted)
    counters.total_selection_work_units = total_attempted
    return nothing
end

function p6_observe_ranking_buffer!(
    size::Int, boundary_index::Int, operation::AbstractString,
)
    size >= 0 || error("negative P6 ranking-buffer size")
    counters = P6_SELECTION_RESOURCES[]
    attempted = max(counters.peak_ranking_buffer_terms, size)
    caps = P6_ACTIVE_SELECTION_CAPS[]
    caps === nothing && error("P6 selection caps are inactive")
    limit = Int(caps["maximum_peak_ranking_buffer_terms"])
    attempted <= limit || throw(CapExceeded(
        "maximum_peak_ranking_buffer_terms", limit, attempted,
        p6_selection_cap_context(boundary_index, operation),
    ))
    counters.peak_ranking_buffer_terms = attempted
    return nothing
end

function p6_merged_table(merged_main)
    table = hasproperty(merged_main, :Majoranas) ?
        getproperty(merged_main, :Majoranas) : merged_main
    table isa AbstractDict || error("P6 postmerge snapshot is not a dictionary")
    return table
end

function p6_snapshot_rows(merged_main, boundary_index::Int)
    table = p6_merged_table(merged_main)
    count = length(table)
    # The full-snapshot bound dominates either tier buffer, and is checked
    # before materializing any snapshot or rank vector.
    p6_observe_ranking_buffer!(count, boundary_index, "postmerge_snapshot_buffer")
    p6_charge_selection!(
        :total_ranking_scan_term_visits, count,
        "maximum_ranking_scan_term_visits", boundary_index,
        "postmerge_snapshot_scan",
    )
    rows = P6SnapshotRow[]
    sizehint!(rows, count)
    for (mask, coefficient) in table
        mask isa Unsigned || error("P6 Majorana mask is not unsigned")
        coefficient isa Float64 || error("unexpected P6 coefficient type")
        isfinite(coefficient) || error("non-finite P6 postmerge coefficient")
        bits = reinterpret(UInt64, coefficient)
        push!(rows, P6SnapshotRow(
            mask, coefficient, bits, bits & P6_ABS_BITS_MASK,
        ))
    end
    length(rows) == count || error("P6 postmerge snapshot count mismatch")
    return rows
end

function p6_point_cost(
    row::P6SnapshotRow, maximum_bits::Int,
    boundary_index::Int, operation::AbstractString,
)::BigInt
    p6_charge_selection!(
        :total_tick_evaluations, 1, "maximum_tick_evaluations",
        boundary_index, operation,
    )
    return point_abs_ticks(
        row.coefficient, maximum_bits,
        p6_selection_cap_context(boundary_index, operation),
    )
end

p6_rank_key(row::P6RankRow) =
    (row.point_cost, row.snapshot.abs_bits, row.snapshot.mask)

function p6_sort_rank_rows!(
    rows::Vector{P6RankRow}, boundary_index::Int, operation::AbstractString,
)
    p6_observe_ranking_buffer!(length(rows), boundary_index, operation)
    p6_charge_selection!(
        :total_sort_work_items, length(rows), "maximum_sort_input_items",
        boundary_index, operation,
    )
    sort!(rows; by=p6_rank_key)
    return rows
end

function p6_affordable_prefix(rows::Vector{P6RankRow}, available::BigInt)
    available >= 0 || error("negative P6 available amount")
    selected = P6RankRow[]
    remaining = available
    for row in rows
        row.point_cost <= remaining || break
        push!(selected, row)
        remaining -= row.point_cost
    end
    return selected, remaining, length(selected) == length(rows)
end

function p6_insert_selected!(
    selected_costs::Dict{Any,BigInt}, rows::Vector{P6RankRow},
    boundary_index::Int,
)
    p6_charge_selection!(
        :total_selected_membership_insertions, length(rows),
        "maximum_selected_membership_insertions", boundary_index,
        "selected_membership_insertions",
    )
    for row in rows
        haskey(selected_costs, row.snapshot.mask) &&
            error("duplicate P6 selected mask")
        selected_costs[row.snapshot.mask] = row.point_cost
    end
    return nothing
end

function p6_prepare_boundary_drop!(
    merged_main, ticks, boundary_index::Int, maximum_bits::Int, context,
)
    P6_ACTIVE_SELECTION_CAPS[] === nothing &&
        error("P6 selection caps are inactive")
    0 <= boundary_index < P6_BOUNDARY_COUNT ||
        error("P6 boundary index outside 0:767")
    maximum_bits == 2048 || error("unexpected P6 BigInt cap")

    rows = p6_snapshot_rows(merged_main, boundary_index)
    snapshot_bits = Dict{Any,UInt64}(
        row.mask => row.coefficient_bits for row in rows
    )
    length(snapshot_bits) == length(rows) || error("P6 snapshot map lost a mask")

    # Product and merge charges from this transition and every previous drop
    # are already present.  This read does not mutate the live state or ledger.
    current = total_ticks(ticks)
    current >= 0 || error("negative P6 local ledger")
    target = p6_prefix_target(boundary_index)
    available = max(BigInt(0), target - current)

    tier1 = P6RankRow[]
    for row in rows
        if row.abs_bits < P6_K37_ABS_BITS
            cost = p6_point_cost(
                row, maximum_bits, boundary_index, "tier1_row_cost",
            )
            push!(tier1, P6RankRow(row, cost))
        end
    end
    p6_sort_rank_rows!(tier1, boundary_index, "tier1_rank_sort")
    selected_tier1, remaining, tier1_complete =
        p6_affordable_prefix(tier1, available)

    selected_costs = Dict{Any,BigInt}()
    p6_insert_selected!(selected_costs, selected_tier1, boundary_index)

    # Strict K37 is only a provable initial segment.  A fully consumed tier 1
    # with positive remainder must rescan the same immutable snapshot, rank
    # every individually affordable nonpool row, and continue the full-domain
    # prefix.  No host dictionary order or callback order consumes budget.
    if tier1_complete && remaining > 0
        p6_charge_selection!(
            :total_ranking_scan_term_visits, length(rows),
            "maximum_ranking_scan_term_visits", boundary_index,
            "tier2_original_snapshot_rescan",
        )
        tier2 = P6RankRow[]
        for row in rows
            row.abs_bits < P6_K37_ABS_BITS && continue
            cost = p6_point_cost(
                row, maximum_bits, boundary_index, "tier2_row_cost",
            )
            cost <= remaining && push!(tier2, P6RankRow(row, cost))
        end
        p6_sort_rank_rows!(tier2, boundary_index, "tier2_rank_sort")
        selected_tier2, remaining_after_tier2, _ =
            p6_affordable_prefix(tier2, remaining)
        p6_insert_selected!(selected_costs, selected_tier2, boundary_index)
        remaining = remaining_after_tier2
    end

    return P6BoundaryDropDecision(
        boundary_index, length(rows), snapshot_bits, selected_costs,
        Set{Any}(), 0, false,
    )
end

function p6_should_drop(
    decision::P6BoundaryDropDecision, mask, coefficient,
    threshold::Float64,
)::Bool
    decision.validated && error("P6 decision was reused after validation")
    coefficient isa Float64 || error("unexpected P6 callback coefficient type")
    isfinite(coefficient) || error("non-finite P6 callback coefficient")
    reinterpret(UInt64, threshold) == P6_K37_ABS_BITS ||
        error("P6 formal lazy anchor differs from K37")
    decision.callback_visit_count += 1

    haskey(decision.snapshot_coefficient_bits, mask) ||
        error("P6 callback mask absent from frozen snapshot")
    mask in decision.callback_seen_masks &&
        error("P6 callback visited a mask more than once")
    push!(decision.callback_seen_masks, mask)
    reinterpret(UInt64, coefficient) == decision.snapshot_coefficient_bits[mask] ||
        error("P6 callback coefficient differs from frozen snapshot")
    return haskey(decision.selected_costs, mask)
end

function p6_validate_selected_drop_ticks!(
    decision::P6BoundaryDropDecision,
    transition_drop_ticks::Integer, dropped,
)
    decision.validated && error("P6 decision was validated twice")
    decision.callback_visit_count == decision.snapshot_count ||
        error("P6 callback visit count differs from the postmerge snapshot")
    length(decision.callback_seen_masks) == decision.snapshot_count ||
        error("P6 adaptive callback did not cover the full snapshot")

    actual_masks = Set{Any}()
    for row in dropped
        length(row) == 2 || error("invalid P6 adaptive dropped row")
        mask, coefficient = row
        haskey(decision.selected_costs, mask) ||
            error("P6 upstream dropped a mask outside frozen membership")
        mask in actual_masks && error("P6 upstream dropped a duplicate mask")
        push!(actual_masks, mask)
        reinterpret(UInt64, coefficient) == decision.snapshot_coefficient_bits[mask] ||
            error("P6 dropped coefficient differs from frozen snapshot")
    end
    actual_masks == Set(keys(decision.selected_costs)) ||
        error("P6 upstream dropped membership differs from frozen selection")
    expected = sum(values(decision.selected_costs); init=BigInt(0))
    BigInt(transition_drop_ticks) == expected ||
        error("P6 adaptive selection cost differs from existing drop ledger")

    counters = P6_SELECTION_RESOURCES[]
    counters.completed_selection_boundary_count += 1
    counters.completed_selection_boundary_count <= P6_BOUNDARY_COUNT ||
        error("too many P6 selection boundaries")
    decision.validated = true
    return nothing
end

# Copied from the formal P5 execute_p5_step2 kernel.  Apart from the function
# identity/fixed K37 anchor guard, the only algorithmic differences are the
# three direct hook calls at prepare, callback membership, and ledger
# validation.  Arithmetic, cap charging, full records, and hashes remain on
# the frozen P3/P4/P5 path.

function execute_p6_step2(stages, fixture, observable, trig_lookup, threshold::Float64)
    reinterpret(UInt64, threshold) == P6_K37_ABS_BITS ||
        error("invalid P6 lazy-anchor threshold bits")
    caps = fixture["deterministic_resource_caps"]
    maximum_combined = Int(caps["maximum_total_P2_plus_accuracy_charged_events"])
    maximum_bits = Int(fixture["outward_arithmetic"]["maximum_BigInt_bit_length"])

    cache = MajoranaPropagationCache(observable)
    p2_counters = ResourceCounters()
    accuracy_counters = AccuracyCounters()
    ticks = DefectTicks()
    transition_records = Any[]
    boundary_records = Any[]
    stage_records = Any[]
    p2_transition_hasher = CanonicalArrayHasher()
    p2_boundary_hasher = CanonicalArrayHasher()
    p2_stage_hasher = CanonicalArrayHasher()

    peak_premerge = length(observable)
    peak_postmerge = length(observable)
    total_splits = 0
    total_threshold_drops = 0
    total_zero_drops = 0
    cumulative_drop_diagnostic = 0.0
    completed_composites = 0
    completed_constituents = 0
    completed_boundaries = 0
    cap_event = nothing

    try
        for stage in stages
            stage_input_count = length(MajoranaPropagation.PropagationBase.mainsum(cache))
            stage_peak_premerge = stage_input_count
            stage_peak_postmerge = stage_input_count
            stage_splits_before = total_splits
            stage_drops_before = total_threshold_drops
            stage_p2_before = public_counters(p2_counters)
            stage_accuracy_before = public_accuracy_counters(accuracy_counters)
            stage_product_ticks_before = ticks.product
            stage_merge_ticks_before = ticks.merge
            stage_drop_ticks_before = ticks.drop

            for composite in stage.composites
                for constituent in composite.constituents
                    public = constituent.public
                    context = (
                        stage_index=stage.stage_index,
                        group=stage.group,
                        composite_index=composite.public.composite_index,
                        constituent_index=public.constituent_index,
                    )
                    main_sum = MajoranaPropagation.PropagationBase.mainsum(cache)
                    aux_sum = MajoranaPropagation.PropagationBase.auxsum(cache)
                    isempty(aux_sum.Majoranas) || error("P3 auxiliary sum is nonempty before apply")
                    input_count = length(main_sum)
                    check_value_cap("maximum_current_terms_before_constituent", input_count,
                        P2_MAX_CURRENT_TERMS, context)
                    charge_p2!(p2_counters, accuracy_counters, :cap_scan_term_visits,
                        input_count, P2_MAX_CAP_SCAN_VISITS, maximum_combined,
                        merge(context, (operation="predictive_anticommutation_scan",)))

                    source_masks = sort!(collect(
                        mask for mask in keys(main_sum.Majoranas)
                        if !MajoranaPropagation.commutes(constituent.rotation.ms_int, mask)
                    ))
                    anticommuting_count = length(source_masks)
                    predicted_premerge = input_count + anticommuting_count
                    check_value_cap("maximum_premerge_terms", predicted_premerge,
                        P2_MAX_PREMERGE_TERMS, context)
                    charge_product_events!(accuracy_counters, p2_counters,
                        anticommuting_count, caps,
                        merge(context, (operation="independent_actions_and_product_defects",)))

                    actions = NamedTuple[]
                    for source_mask in source_masks
                        input_coefficient = main_sum.Majoranas[source_mask]
                        input_coefficient isa Float64 || error("unexpected P3 input coefficient type")
                        isfinite(input_coefficient) || error("non-finite P3 input coefficient")
                        target_mask, branch_sign = independent_target_and_branch(
                            constituent.rotation.ms_int, source_mask,
                        )
                        upstream_sign, upstream_target = MajoranaPropagation.ms_mult(
                            constituent.rotation.ms_int, source_mask, NMODES,
                        )
                        upstream_branch = Int(round(-imag(upstream_sign)))
                        upstream_target == target_mask || error("independent P3 target mismatch")
                        upstream_branch == branch_sign || error("independent P3 branch-sign mismatch")
                        push!(actions, (
                            source_mask=source_mask,
                            target_mask=target_mask,
                            branch_sign=branch_sign,
                            input_coefficient=input_coefficient,
                        ))
                    end

                    charge_p2!(p2_counters, accuracy_counters, :propagation_term_visits,
                        input_count, P2_MAX_PROPAGATION_VISITS, maximum_combined,
                        merge(context, (operation="upstream_applytoall",)))
                    MajoranaPropagation.PropagationBase.applytoall!(
                        constituent.rotation, cache, constituent.applied_angle,
                    )
                    actual_main = MajoranaPropagation.PropagationBase.mainsum(cache)
                    actual_aux = MajoranaPropagation.PropagationBase.auxsum(cache)
                    length(actual_main) == input_count ||
                        error("P3 applytoall changed main cardinality")
                    length(actual_aux) == anticommuting_count ||
                        error("P3 independent split count differs from upstream")
                    trig = trig_lookup[public.applied_angle]
                    float_bits_hex(constituent.applied_angle) == public.applied_angle_Float64_bits_hex ||
                        error("P3 schedule Float64 angle bits drift")

                    contribution_hasher = CanonicalArrayHasher()
                    transition_product_ticks = BigInt(0)
                    for action in actions
                        cosine_output = actual_main.Majoranas[action.source_mask]
                        sine_output = actual_aux.Majoranas[action.target_mask]
                        isfinite(cosine_output) && isfinite(sine_output) ||
                            error("non-finite P3 product output")
                        expected_cosine = action.input_coefficient * trig.cosine_float
                        expected_sine = action.input_coefficient *
                            (trig.sine_float * Float64(action.branch_sign))
                        reinterpret(UInt64, cosine_output) == reinterpret(UInt64, expected_cosine) ||
                            error("P3 upstream cosine product bits mismatch")
                        reinterpret(UInt64, sine_output) == reinterpret(UInt64, expected_sine) ||
                            error("P3 upstream sine product bits mismatch")
                        cosine_ticks = point_to_interval_defect_ticks(
                            cosine_output, action.input_coefficient,
                            trig.cosine_lower_ticks, trig.cosine_upper_ticks, 1,
                            maximum_bits, merge(context, (
                                operation="cosine_product_defect",
                                source_mask_hex=mask_hex(action.source_mask),
                            )),
                        )
                        sine_ticks = point_to_interval_defect_ticks(
                            sine_output, action.input_coefficient,
                            trig.sine_lower_ticks, trig.sine_upper_ticks,
                            action.branch_sign, maximum_bits, merge(context, (
                                operation="sine_product_defect",
                                source_mask_hex=mask_hex(action.source_mask),
                            )),
                        )
                        add_ticks!(ticks, :product, cosine_ticks + sine_ticks,
                            maximum_bits, merge(context, (operation="product_defect_accumulate",)))
                        transition_product_ticks += cosine_ticks + sine_ticks
                        check_bigint_cap!(transition_product_ticks, maximum_bits,
                            merge(context, (operation="transition_product_accumulate",)))
                        push_canonical_row!(contribution_hasher, (
                            source_mask_hex=mask_hex(action.source_mask),
                            target_mask_hex=mask_hex(action.target_mask),
                            branch_sign=action.branch_sign,
                            input_coefficient_Float64_bits_hex=
                                float_bits_hex(action.input_coefficient),
                            cosine_output_Float64_bits_hex=float_bits_hex(cosine_output),
                            sine_output_Float64_bits_hex=float_bits_hex(sine_output),
                            cosine_product_defect_ticks=string(cosine_ticks),
                            sine_product_defect_ticks=string(sine_ticks),
                        ))
                    end
                    contribution_digest = finish_canonical_array!(contribution_hasher)

                    premerge_count = length(actual_main) + length(actual_aux)
                    premerge_count == predicted_premerge ||
                        error("P3 premerge contribution count mismatch")
                    peak_premerge = max(peak_premerge, premerge_count)
                    stage_peak_premerge = max(stage_peak_premerge, premerge_count)
                    total_splits += anticommuting_count

                    collision_masks = sort!(collect(intersect(
                        keys(actual_main.Majoranas), keys(actual_aux.Majoranas),
                    )))
                    charge_accuracy_events!(accuracy_counters, p2_counters,
                        :merge_defect_events, length(collision_masks),
                        "maximum_merge_defect_events", caps,
                        merge(context, (operation="merge_defects",)))
                    collision_inputs = [(
                        mask=mask,
                        main=actual_main.Majoranas[mask],
                        aux=actual_aux.Majoranas[mask],
                    ) for mask in collision_masks]
                    merge!(cache)
                    merged_main = MajoranaPropagation.PropagationBase.mainsum(cache)
                    postmerge_count = length(merged_main)
                    postmerge_count <= premerge_count || error("P3 merge increased cardinality")
                    premerge_count - postmerge_count == length(collision_masks) ||
                        error("P3 merge collision count mismatch")
                    check_value_cap("maximum_premerge_terms", postmerge_count,
                        P2_MAX_PREMERGE_TERMS, context)
                    peak_postmerge = max(peak_postmerge, postmerge_count)
                    stage_peak_postmerge = max(stage_peak_postmerge, postmerge_count)

                    merge_hasher = CanonicalArrayHasher()
                    transition_merge_ticks = BigInt(0)
                    for collision in collision_inputs
                        merged_coefficient = merged_main.Majoranas[collision.mask]
                        isfinite(merged_coefficient) || error("non-finite P3 merged coefficient")
                        expected_merged = collision.main + collision.aux
                        reinterpret(UInt64, merged_coefficient) ==
                            reinterpret(UInt64, expected_merged) ||
                            error("P3 upstream merge bits mismatch")
                        defect_ticks = point_sum_defect_ticks(
                            merged_coefficient, collision.main, collision.aux,
                            maximum_bits, merge(context, (
                                operation="merge_defect",
                                mask_hex=mask_hex(collision.mask),
                            )),
                        )
                        add_ticks!(ticks, :merge, defect_ticks, maximum_bits,
                            merge(context, (operation="merge_defect_accumulate",)))
                        transition_merge_ticks += defect_ticks
                        check_bigint_cap!(transition_merge_ticks, maximum_bits,
                            merge(context, (operation="transition_merge_accumulate",)))
                        push_canonical_row!(merge_hasher, (
                            mask_hex=mask_hex(collision.mask),
                            main_premerge_coefficient_Float64_bits_hex=
                                float_bits_hex(collision.main),
                            aux_premerge_coefficient_Float64_bits_hex=
                                float_bits_hex(collision.aux),
                            merged_coefficient_Float64_bits_hex=
                                float_bits_hex(merged_coefficient),
                            merge_defect_ticks=string(defect_ticks),
                        ))
                    end
                    merge_digest = finish_canonical_array!(merge_hasher)

                    boundary_record = nothing
                    transition_drop_ticks = BigInt(0)
                    transition_drop_events = 0
                    if public.boundary_after
                        charge_p2!(p2_counters, accuracy_counters,
                            :truncation_term_visits, postmerge_count,
                            P2_MAX_TRUNCATION_VISITS, maximum_combined,
                            merge(context, (operation="threshold_callback_scan",)))
                        p6_drop_decision = p6_prepare_boundary_drop!(
                            merged_main, ticks, Int(public.boundary_index_after),
                            maximum_bits, merge(context, (
                                operation="p6_drop_selection",
                            )),
                        )
                        dropped = Tuple{typeof(constituent.rotation.ms_int),Float64}[]
                        callback_visits = Ref(0)
                        callback = function (mask, coefficient)
                            coefficient isa Float64 || error("unexpected P3 threshold coefficient type")
                            isfinite(coefficient) || error("non-finite P3 threshold coefficient")
                            callback_visits[] += 1
                            should_drop = p6_should_drop(
                                p6_drop_decision, mask, coefficient, threshold,
                            )
                            should_drop && push!(dropped, (mask, coefficient))
                            return should_drop
                        end
                        truncate!(
                            cache; min_abs_coeff=0.0, max_weight=Inf, max_unpaired=Inf,
                            max_freq=Inf, max_sins=Inf, customtruncfunc=callback,
                        )
                        callback_visits[] == postmerge_count ||
                            error("P3 threshold callback visit count mismatch")
                        sort!(dropped; by=first)
                        transition_drop_events = length(dropped)
                        charge_accuracy_events!(accuracy_counters, p2_counters,
                            :drop_defect_events, transition_drop_events,
                            "maximum_drop_defect_events", caps,
                            merge(context, (operation="drop_defects",)))
                        drop_hasher = CanonicalArrayHasher()
                        for (mask, coefficient) in dropped
                            defect_ticks = point_abs_ticks(
                                coefficient, maximum_bits, merge(context, (
                                    operation="drop_defect", mask_hex=mask_hex(mask),
                                )),
                            )
                            add_ticks!(ticks, :drop, defect_ticks, maximum_bits,
                                merge(context, (operation="drop_defect_accumulate",)))
                            transition_drop_ticks += defect_ticks
                            check_bigint_cap!(transition_drop_ticks, maximum_bits,
                                merge(context, (operation="transition_drop_accumulate",)))
                            push_canonical_row!(drop_hasher, (
                                mask_hex=mask_hex(mask),
                                coefficient_Float64_bits_hex=float_bits_hex(coefficient),
                                drop_defect_ticks=string(defect_ticks),
                            ))
                        end
                        p6_validate_selected_drop_ticks!(
                            p6_drop_decision, transition_drop_ticks, dropped,
                        )
                        drop_rows_digest = finish_canonical_array!(drop_hasher)
                        retained_count = length(MajoranaPropagation.PropagationBase.mainsum(cache))
                        retained_count + transition_drop_events == postmerge_count ||
                            error("P3 retained plus dropped count mismatch")
                        check_value_cap("maximum_boundary_retained_terms", retained_count,
                            P2_MAX_BOUNDARY_TERMS,
                            merge(context, (operation="post_threshold_retained_state",)))
                        dropped_digest, diagnostic_increment, zero_drop_count =
                            dropped_rows_digest!(dropped)
                        cumulative_drop_diagnostic += diagnostic_increment
                        total_threshold_drops += transition_drop_events
                        total_zero_drops += zero_drop_count
                        p2_boundary_row = (
                            boundary_index=public.boundary_index_after,
                            stage_index=stage.stage_index,
                            group=stage.group,
                            composite_index=composite.public.composite_index,
                            after_constituent_index=public.constituent_index,
                            boundary_kind=composite.public.truncate_after_each_constituent ?
                                "after_constituent" : "after_complete_composite",
                            postmerge_term_count=postmerge_count,
                            retained_term_count=retained_count,
                            threshold_dropped_term_count=transition_drop_events,
                            exact_zero_dropped_term_count=zero_drop_count,
                            dropped_term_stream_sha256=dropped_digest,
                            dropped_abs_sum_Float64_diagnostic_bits_hex=
                                float_bits_hex(diagnostic_increment),
                            cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex=
                                float_bits_hex(cumulative_drop_diagnostic),
                        )
                        push_canonical_row!(p2_boundary_hasher, p2_boundary_row)
                        boundary_record = merge(p2_boundary_row, (
                            drop_defect_event_count=transition_drop_events,
                            drop_defect_ticks=string(transition_drop_ticks),
                            drop_rows_sha256=drop_rows_digest,
                            cumulative_product_defect_ticks=string(ticks.product),
                            cumulative_merge_defect_ticks=string(ticks.merge),
                            cumulative_drop_defect_ticks=string(ticks.drop),
                            cumulative_total_operator_error_ticks=string(total_ticks(ticks)),
                            cumulative_accuracy_charged_event_count=
                                accuracy_charged(accuracy_counters),
                        ))
                        push!(boundary_records, boundary_record)
                        completed_boundaries += 1
                    end

                    retained_after = boundary_record === nothing ? nothing :
                        boundary_record.retained_term_count
                    p2_transition_row = (
                        constituent_index=public.constituent_index,
                        composite_index=composite.public.composite_index,
                        stage_index=stage.stage_index,
                        group=stage.group,
                        mask_hex=public.mask_hex,
                        applied_angle=public.applied_angle,
                        input_term_count=input_count,
                        anticommuting_split_count=anticommuting_count,
                        premerge_contribution_count=premerge_count,
                        postmerge_unique_term_count=postmerge_count,
                        boundary_index_after=public.boundary_index_after,
                        retained_term_count_after_boundary=retained_after,
                    )
                    push_canonical_row!(p2_transition_hasher, p2_transition_row)
                    accuracy_increment = 2anticommuting_count +
                        length(collision_masks) + transition_drop_events
                    push!(transition_records, merge(p2_transition_row, (
                        product_defect_event_count=2anticommuting_count,
                        product_defect_ticks=string(transition_product_ticks),
                        product_contribution_rows_sha256=contribution_digest,
                        merge_defect_event_count=length(collision_masks),
                        merge_defect_ticks=string(transition_merge_ticks),
                        merge_collision_rows_sha256=merge_digest,
                        drop_defect_event_count=transition_drop_events,
                        drop_defect_ticks=string(transition_drop_ticks),
                        cumulative_product_defect_ticks=string(ticks.product),
                        cumulative_merge_defect_ticks=string(ticks.merge),
                        cumulative_drop_defect_ticks=string(ticks.drop),
                        cumulative_total_operator_error_ticks=string(total_ticks(ticks)),
                        accuracy_charged_event_count_increment=accuracy_increment,
                        cumulative_accuracy_charged_event_count=
                            accuracy_charged(accuracy_counters),
                    )))
                    completed_constituents += 1
                end
                completed_composites += 1
            end

            p2_after = public_counters(p2_counters)
            accuracy_after = public_accuracy_counters(accuracy_counters)
            p2_stage_row = (
                stage_index=stage.stage_index,
                group=stage.group,
                input_term_count=stage_input_count,
                final_retained_term_count=
                    length(MajoranaPropagation.PropagationBase.mainsum(cache)),
                peak_premerge_contribution_count=stage_peak_premerge,
                peak_postmerge_unique_term_count=stage_peak_postmerge,
                anticommuting_split_count=total_splits - stage_splits_before,
                threshold_dropped_term_count=total_threshold_drops - stage_drops_before,
                cap_scan_term_visits_increment=
                    p2_after.cap_scan_term_visits - stage_p2_before.cap_scan_term_visits,
                propagation_term_visits_increment=
                    p2_after.propagation_term_visits - stage_p2_before.propagation_term_visits,
                truncation_term_visits_increment=
                    p2_after.truncation_term_visits - stage_p2_before.truncation_term_visits,
            )
            push_canonical_row!(p2_stage_hasher, p2_stage_row)
            product_event_increment = accuracy_after.product_defect_event_count -
                stage_accuracy_before.product_defect_event_count
            merge_event_increment = accuracy_after.merge_defect_event_count -
                stage_accuracy_before.merge_defect_event_count
            drop_event_increment = accuracy_after.drop_defect_event_count -
                stage_accuracy_before.drop_defect_event_count
            stage_product_ticks = ticks.product - stage_product_ticks_before
            stage_merge_ticks = ticks.merge - stage_merge_ticks_before
            stage_drop_ticks = ticks.drop - stage_drop_ticks_before
            push!(stage_records, merge(p2_stage_row, (
                product_defect_event_count_increment=product_event_increment,
                product_defect_ticks_increment=string(stage_product_ticks),
                merge_defect_event_count_increment=merge_event_increment,
                merge_defect_ticks_increment=string(stage_merge_ticks),
                drop_defect_event_count_increment=drop_event_increment,
                drop_defect_ticks_increment=string(stage_drop_ticks),
                total_operator_error_ticks_increment=
                    string(stage_product_ticks + stage_merge_ticks + stage_drop_ticks),
                cumulative_total_operator_error_ticks=string(total_ticks(ticks)),
                accuracy_charged_event_count_increment=
                    accuracy_after.accuracy_charged_event_count -
                    stage_accuracy_before.accuracy_charged_event_count,
                cumulative_accuracy_charged_event_count=
                    accuracy_after.accuracy_charged_event_count,
            )))
        end
    catch error_value
        if error_value isa CapExceeded
            cap_event = (
                cap_name=error_value.cap_name,
                limit=error_value.limit,
                attempted=error_value.attempted,
                context=error_value.context,
                rejected_operation_was_not_executed_after_cap_detection=true,
            )
        else
            rethrow()
        end
    end

    p2_transition_digest = finish_canonical_array!(p2_transition_hasher)
    p2_boundary_digest = finish_canonical_array!(p2_boundary_hasher)
    p2_stage_digest = finish_canonical_array!(p2_stage_hasher)
    return (
        cache=cache,
        cap_event=cap_event,
        completed_composites=completed_composites,
        completed_constituents=completed_constituents,
        completed_boundaries=completed_boundaries,
        peak_premerge=peak_premerge,
        peak_postmerge=peak_postmerge,
        total_splits=total_splits,
        total_threshold_drops=total_threshold_drops,
        total_zero_drops=total_zero_drops,
        cumulative_drop_diagnostic=cumulative_drop_diagnostic,
        p2_counters=p2_counters,
        accuracy_counters=accuracy_counters,
        ticks=ticks,
        transition_records=transition_records,
        boundary_records=boundary_records,
        stage_records=stage_records,
        p2_transition_records_sha256=p2_transition_digest,
        p2_boundary_records_sha256=p2_boundary_digest,
        p2_stage_records_sha256=p2_stage_digest,
    )
end

function main_p6()
    length(ARGS) == 5 || error(
        "usage: majorana_p6_runner.jl P6_FIXTURE.json P5_FIXTURE.json " *
        "P4_FIXTURE.json P3_FIXTURE.json P2_FIXTURE.json",
    )
    p6_fixture_path = abspath(ARGS[1])
    p5_fixture_path = abspath(ARGS[2])
    p4_fixture_path = abspath(ARGS[3])
    p3_fixture_path = abspath(ARGS[4])
    p2_fixture_path = abspath(ARGS[5])

    p6_fixture = validate_p6_fixture(JSON.parsefile(p6_fixture_path))
    # P5 is a read-only workload-custody fixture.  Its runner, selector, result,
    # policy, and D0 artifacts are neither included nor available in this stage.
    p5_fixture = JSON.parsefile(p5_fixture_path)
    p4_fixture = validate_p4_fixture(JSON.parsefile(p4_fixture_path))
    p3_fixture = JSON.parsefile(p3_fixture_path)
    p2_fixture = JSON.parsefile(p2_fixture_path)
    validate_p4_parent_fixtures(
        p4_fixture, p3_fixture, p2_fixture, p3_fixture_path, p2_fixture_path,
    )

    base_pins = p6_fixture["frozen_execution_relation"][
        "required_base_fixture_sha256"
    ]
    file_sha256(p5_fixture_path) == base_pins["P5"] ||
        error("P6 inherited P5 fixture digest mismatch")
    canonical_sha256(p5_fixture) ==
        "bbac5a9281198ba87b336c6e45741d1468f85bb2997317943f1a45b6ac90de91" ||
        error("P6 inherited P5 fixture canonical digest mismatch")
    get(p5_fixture, "fixture_id", nothing) ==
        "MAJORANA-P5-L8-CONDITIONAL-STEP2-THRESHOLD-S0-V1" ||
        error("P6 inherited P5 fixture identity mismatch")
    file_sha256(p4_fixture_path) == base_pins["P4"] ||
        error("P6 inherited P4 fixture digest mismatch")
    file_sha256(p3_fixture_path) == base_pins["P3"] ||
        error("P6 inherited P3 fixture digest mismatch")
    file_sha256(p2_fixture_path) == base_pins["P2"] ||
        error("P6 inherited P2 fixture digest mismatch")

    active_project = Base.active_project()
    active_project === nothing && error("P6 runner requires an active project")
    manifest_path = joinpath(dirname(active_project), "Manifest.toml")
    isfile(manifest_path) || error("P6 Manifest.toml missing")
    Threads.nthreads() == 1 || error("formal P6 runner requires one Julia thread")
    rounding(Float64) == RoundNearest ||
        error("formal P6 runner requires Float64 RNE")
    reinterpret(UInt64, EPSILON) == 0x3dd0000000000000 ||
        error("P6 frozen step-1 threshold bits drift")
    reinterpret(UInt64, P6_K37_THRESHOLD) == P6_K37_ABS_BITS ||
        error("P6 frozen lazy-anchor bits drift")

    image_file = unsafe_string(Base.JLOptions().image_file)
    julia_executable = joinpath(Sys.BINDIR, Base.julia_exename())
    mp_path = pathof(MajoranaPropagation)
    pp_path = pathof(MajoranaPropagation.PauliPropagation)
    runtime = (
        julia_version=string(VERSION),
        julia_commit=String(Base.GIT_VERSION_INFO.commit_short),
        machine=String(Sys.MACHINE),
        threads=Threads.nthreads(),
        executable_sha256=file_sha256(julia_executable),
        sysimage_sha256=file_sha256(image_file),
        project_sha256=file_sha256(active_project),
        manifest_sha256=file_sha256(manifest_path),
    )
    upstream = (
        majorana_propagation_version=string(Base.pkgversion(MajoranaPropagation)),
        pauli_propagation_version=
            string(Base.pkgversion(MajoranaPropagation.PauliPropagation)),
        majorana_source_closure=source_tree_closure(mp_path),
        pauli_source_closure=source_tree_closure(pp_path),
    )

    maximum_bits = Int(p3_fixture["outward_arithmetic"]["maximum_BigInt_bit_length"])
    maximum_bits == 2048 || error("P6 inherited P3 BigInt cap drift")
    trig_lookup, trig_table = build_trig_table(p3_fixture, maximum_bits)
    length(trig_table) <=
        Int(p6_fixture["outward_arithmetic"]["maximum_trig_table_entries"]) ||
        error("P6 trigonometric table exceeds its frozen cap")
    stages, schedule = build_schedule()
    observable, initial = initial_observable()
    initial_input = (
        term_count=initial.nonzero_term_count,
        term_stream_sha256=initial.term_stream_sha256,
        P3_fixture_id=String(p3_fixture["fixture_id"]),
        P3_fixture_sha256=file_sha256(p3_fixture_path),
        P3_fixture_canonical_sha256=canonical_sha256(p3_fixture),
    )

    # Step 1 is exactly the imported P3 2^-34 route.  No P6 resource selector,
    # adaptive membership, or step-2 cap is active on this path.
    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P6 step-2 caps leaked into step 1")
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P6 selection caps leaked into step 1")
    P6_SELECTION_RESOURCES[] = P6SelectionResourceCounters()
    execution1 = execute_p3(stages, p3_fixture, observable, trig_lookup)
    final1, final_cap1 = finalize_p3_state!(execution1, p3_fixture)
    cap1 = execution1.cap_event === nothing ? final_cap1 : execution1.cap_event
    execution1.cap_event !== nothing && final_cap1 !== nothing &&
        error("P6 step 1 produced two deterministic cap events")
    step1 = local_step_row(1, initial_input, execution1, cap1, final1)

    step2 = nothing
    step_boundary_link = nothing
    if cap1 === nothing
        live_step1_sum = MajoranaPropagation.PropagationBase.mainsum(execution1.cache)
        step2_input_sum = deepcopy(live_step1_sum)
        input_rows = sort!(collect(step2_input_sum.Majoranas); by=first)
        input_digest = term_stream_sha256(input_rows)
        length(input_rows) == final1.retained_term_count ||
            error("P6 step-link term count differs from step-1 final state")
        input_digest == final1.term_stream_sha256 ||
            error("P6 step-link term digest differs from step-1 final state")
        step2_input = (
            term_count=length(input_rows),
            term_stream_sha256=input_digest,
        )
        empty!(input_rows)
        GC.gc()

        step2_fixture = p6_step2_execution_fixture(p6_fixture, p3_fixture)
        step2_caps = p6_fixture["deterministic_resource_caps"]
        selection_caps = p6_fixture["deterministic_selection_caps"]
        execution2 = nothing
        final2 = nothing
        cap2 = nothing
        P4_ACTIVE_STEP2_CAPS[] = step2_caps
        p6_reset_selection_state!(selection_caps)
        try
            execution2 = execute_p6_step2(
                stages, step2_fixture, step2_input_sum, trig_lookup,
                P6_K37_THRESHOLD,
            )
            final_cap2 = execution2.cap_event === nothing ?
                precheck_p4_final_cap(execution2, step2_caps) : nothing
            if execution2.cap_event === nothing && final_cap2 === nothing
                execution2.completed_boundaries == P6_BOUNDARY_COUNT ||
                    error("P6 completed execution has wrong boundary count")
                P6_SELECTION_RESOURCES[].completed_selection_boundary_count ==
                    P6_BOUNDARY_COUNT ||
                    error("P6 completed selection boundary count mismatch")
                final2, postcheck_cap2 =
                    finalize_p3_state!(execution2, step2_fixture)
                postcheck_cap2 === nothing ||
                    error("P6 step-2 final cap escaped precheck")
                final2 = merge(final2, (
                    exact_dyadic_center_and_declared_interval_are_authoritative=false,
                    exact_dyadic_center_is_authoritative_execution_fact=true,
                    local_only_interval_is_not_two_step_authority=true,
                ))
            end
            cap2 = execution2.cap_event === nothing ? final_cap2 :
                execution2.cap_event
        finally
            p6_clear_selection_state!()
            P4_ACTIVE_STEP2_CAPS[] = nothing
        end
        step2 = local_step_row(2, step2_input, execution2, cap2, final2)
        step_boundary_link = (
            same_process=true,
            no_serialization=true,
            step1_output_term_count=final1.retained_term_count,
            step1_output_term_stream_sha256=final1.term_stream_sha256,
            step2_input_term_count=step2_input.term_count,
            step2_input_term_stream_sha256=step2_input.term_stream_sha256,
        )
    end

    candidate = (
        candidate_id=P6_ADAPTIVE_CANDIDATE_ID,
        identity="step1_fixed_2^-34_then_step2_E768_MAX_LAZY37_V1",
        required_fresh_process_count=2,
        step1_threshold_exponent=34,
        step1_threshold_rational="1/17179869184",
        step1_threshold_Float64_bits_hex=float_bits_hex(EPSILON),
        adaptive_rule_id=P6_ADAPTIVE_CANDIDATE_ID,
        boundary_count=P6_BOUNDARY_COUNT,
        local_allocation="1/400000",
        lazy_anchor_threshold_exponent=37,
        lazy_anchor_Float64_bits_hex=float_bits_hex(P6_K37_THRESHOLD),
        lazy_anchor_is_not_a_scientific_eligibility_gate=true,
        full_domain_longest_affordable_prefix=true,
        step1_path_is_not_rethresholded=true,
        D0_control_candidate_excluded=true,
    )

    raw = (
        schema_version=1,
        witness_type=P6_WITNESS_TYPE,
        fixture_id=String(p6_fixture["fixture_id"]),
        fixture_sha256=file_sha256(p6_fixture_path),
        fixture_canonical_sha256=canonical_sha256(p6_fixture),
        inherited_P5_fixture_sha256=file_sha256(p5_fixture_path),
        inherited_P5_fixture_canonical_sha256=canonical_sha256(p5_fixture),
        inherited_P4_fixture_sha256=file_sha256(p4_fixture_path),
        inherited_P4_fixture_canonical_sha256=canonical_sha256(p4_fixture),
        inherited_P3_fixture_sha256=file_sha256(p3_fixture_path),
        inherited_P3_fixture_canonical_sha256=canonical_sha256(p3_fixture),
        inherited_P2_fixture_sha256=file_sha256(p2_fixture_path),
        inherited_P2_fixture_canonical_sha256=canonical_sha256(p2_fixture),
        runtime=runtime,
        upstream=upstream,
        initial_observable=initial,
        schedule=schedule,
        trig_table=trig_table,
        candidate=candidate,
        step1=step1,
        step_boundary_link=step_boundary_link,
        step2=step2,
        selection_resources=p6_public_selection_resources(),
        scope=p6_fixture["scope"],
    )
    print(canonical_json(raw))
    print('\n')
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main_p6()
end
