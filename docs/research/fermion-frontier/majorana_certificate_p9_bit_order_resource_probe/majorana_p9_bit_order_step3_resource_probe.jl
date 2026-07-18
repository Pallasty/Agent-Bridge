#!/usr/bin/env julia

# Non-authoritative P9 D0 resource probe.  The already-frozen formal P6
# runner is imported byte-for-byte; no P6 D0 transform or result artifact is
# available here.  One fresh process reconstructs O0 -> step 1 -> step 2 and,
# only after exact aggregate-resource conformance, continues to step 3 from a
# live in-memory deepcopy.  The sole public output contains resource counts.
include(joinpath(
    @__DIR__, "..", "majorana_certificate_p6", "majorana_p6_runner.jl",
))

const P9_D0_PROBE_TYPE =
    "majorana_p9_step3_e768_bitorder_resource_probe_d0_v1"
const P9_D0_FIXTURE_ID = "MAJORANA-P9-STEP3-E768-BITORDER-D0-V1"
const P9_D0_FIXTURE_CANONICAL_SHA256 =
    "7b31f2f8292e46a061b93bf1c3bf5aebc63cd421b719ab349b06dcacd9f84d3d"
const P9_D0_DIRECT_PARENT = "5dcb03990037e47dd48c8166712df9855c91ed67"
const P9_D0_PROBE_MODE = "E768_BITORDER_STEP3_V1"
const P9_D0_CANDIDATE_ID = "E768-BITORDER-STEP3-V1"
const P9_D0_ALGORITHM_ID = "MAJORANA-P9-E768-BITORDER-STEP3-V1"
const P9_D0_INVALID_FAILURE_PHASE = :INVALID
const P9_D0_INDETERMINATE_FAILURE_PHASE = :INDETERMINATE
const P9_D0_FAILURE_PHASE = Ref{Symbol}(P9_D0_INVALID_FAILURE_PHASE)
const P9_P6_RUNNER_SHA256 =
    "b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c"
const P9_PROJECT_SHA256 =
    "62810ce02db16bf25cb74941f27f58ee556ee0826abc4aa47296ce8188a5048f"
const P9_MANIFEST_SHA256 =
    "987572a908176b21cfbe80c385acdd0b4ab47b6c6dcd3ea9a33dd8eb22559406"
const P9_JULIA_EXECUTABLE_SHA256 =
    "2976d17aba35be5d546e8e315e521bd9be3e58c2e64abfd588f186696e807b7d"
const P9_JULIA_SYSIMAGE_SHA256 =
    "4e6f6765863713b3088d1a8f3b3eb68913503253ac5aa3a7a13c5b21f64d23bb"
const P9_MAJORANA_PROPAGATION_SOURCE_CLOSURE = (
    file_count=42,
    total_bytes=1875632,
    closure_sha256=
        "744e743d88d7bc62da1ba11cef02909539de626bd4b0a5533b0b65d8aae309b5",
)
const P9_PAULI_PROPAGATION_SOURCE_CLOSURE = (
    file_count=119,
    total_bytes=7736347,
    closure_sha256=
        "ce1e6cac1b09573962136fce0f315fabbf8556c9075c4aa3545c41c6ee4c3783",
)

const P9_STEP3_CAP_VALUES = (
    maximum_BigInt_bit_length=2048,
    maximum_trig_table_entries=6,
    maximum_step3_accuracy_charged_events=8589934592,
    maximum_step3_anticommuting_events=2147483648,
    maximum_step3_boundary_retained_terms=1048576,
    maximum_step3_cap_scan_term_visits=2147483648,
    maximum_step3_current_terms_before_constituent=1048576,
    maximum_step3_drop_defect_events=1073741824,
    maximum_step3_final_retained_terms=1048576,
    maximum_step3_merge_defect_events=2147483648,
    maximum_step3_premerge_terms=1048576,
    maximum_step3_product_defect_events=4294967296,
    maximum_step3_propagation_term_visits=2147483648,
    maximum_step3_total_P2_charged_term_visits=4294967296,
    maximum_step3_total_P2_plus_accuracy_charged_events=8589934592,
    maximum_step3_truncation_term_visits=1073741824,
)

const P9_STEP3_SELECTION_CAP_VALUES = (
    maximum_snapshot_scan_term_visits=1073741824,
    maximum_bit_order_sort_input_items=1073741824,
    maximum_lazy_tick_evaluations=1073741824,
    maximum_selected_membership_insertions=1073741824,
    maximum_peak_bit_order_sort_input_terms=1048576,
    maximum_total_bit_order_selection_work_units=4294967296,
)

const P9_PUBLIC_EXCLUSIONS = (
    "scientific_local_or_cumulative_error_values",
    "allocation_assessment_or_candidate_selection",
    "term_or_drop_stream_commitments",
    "checkerboard_observable_center_or_interval",
    "adaptive_execution_branch_as_scientific_evidence",
    "scientific_witness_result_contract_certificate_or_READY_authority",
)

function p9_require_exact_keys(value, expected, context::AbstractString)
    value isa AbstractDict || error("$(context) must be an object")
    Set(String.(keys(value))) == Set(String.(expected)) ||
        error("$(context) key mismatch")
    return value
end

function p9_require_exact_positive_integer(value, expected::Integer, context)
    value isa Integer || error("$(context) must be an integer")
    BigInt(value) == BigInt(expected) || error("$(context) drift")
    return value
end

function validate_p9_d0_fixture(fixture)
    canonical_sha256(fixture) == P9_D0_FIXTURE_CANONICAL_SHA256 ||
        error("P9 D0 fixture differs from the frozen semantic object")
    p9_require_exact_keys(fixture, (
        "schema_version", "fixture_id", "required_direct_parent_commit",
        "scientific_authority", "certificate_eligible",
        "result_contract_eligible", "candidate_design",
        "frozen_P6_prefix", "step3_adaptive_rule",
        "bit_order_selector", "deterministic_step3_probe_caps",
        "deterministic_step3_bit_order_selection_probe_caps",
        "P8_selector_semantics_custody", "D4_route_custody",
        "host_supervisor_caps",
        "outward_arithmetic", "required_base_fixture_sha256",
        "expected_P6_prefix_resource_projection", "runtime_custody", "scope",
    ), "P9 D0 fixture")
    fixture["schema_version"] == 1 || error("unexpected P9 D0 schema")
    fixture["fixture_id"] == P9_D0_FIXTURE_ID ||
        error("unexpected P9 D0 fixture identity")
    fixture["required_direct_parent_commit"] == P9_D0_DIRECT_PARENT ||
        error("unexpected P9 D0 direct parent")
    fixture["scientific_authority"] == "NONE" ||
        error("P9 D0 fixture claims scientific authority")
    fixture["certificate_eligible"] == false ||
        error("P9 D0 fixture is certificate eligible")
    fixture["result_contract_eligible"] == false ||
        error("P9 D0 fixture is result-contract eligible")

    design = fixture["candidate_design"]
    design["probe_mode_order"] == Any[P9_D0_PROBE_MODE] ||
        error("P9 D0 probe order drift")
    design["formal_candidates"] == Any[P9_D0_CANDIDATE_ID] ||
        error("P9 D0 candidate set drift")
    design["formal_candidate_count"] == 1 ||
        error("P9 D0 candidate count drift")
    design["candidate_id"] == P9_D0_CANDIDATE_ID ||
        error("P9 D0 candidate identity drift")
    design["probe_mode"] == P9_D0_PROBE_MODE ||
        error("P9 D0 mode drift")
    design["algorithm_id"] == P9_D0_ALGORITHM_ID ||
        error("P9 D0 algorithm identity drift")
    design["control_candidate"] === nothing ||
        error("P9 D0 unexpectedly defines a control")
    design["design_disclosure"] ==
        "P8_A_AND_P8_B_PROOF_SCOPE_INFORMED_P9_RESULT_UNPINNED" ||
        error("P9 D0 hindsight disclosure drift")
    design["all_three_steps_execute_in_one_process"] == true ||
        error("P9 D0 same-process chain drift")
    design["checkpoint_serialization_or_cross_process_resume_forbidden"] == true ||
        error("P9 D0 permits a checkpoint")
    design["fixed_execution_chain"] ==
        "O0_then_P3_2^-34_step1_then_frozen_P6_E768_MAX_LAZY37_step2_then_live_deepcopy_then_E768_BITORDER_step3" ||
        error("P9 D0 fixed execution chain drift")

    rule = fixture["step3_adaptive_rule"]
    rule["algorithm_id"] == P9_D0_ALGORITHM_ID ||
        error("P9 D0 step-3 algorithm drift")
    rule["mapped_step_index"] == 3 || error("P9 mapped-step index drift")
    parse(BigInt, rule["grid_denominator"]) == (BigInt(1) << 128) ||
        error("P9 D0 grid drift")
    rule["local_allocation_denominator"] == 400000 ||
        error("P9 D0 allocation denominator drift")
    parse(BigInt, rule["maximum_strictly_legal_local_ticks"]) ==
        fld((BigInt(1) << 128) - 1, BigInt(400000)) ||
        error("P9 D0 local strict maximum drift")
    rule["local_boundary_count"] == 768 ||
        error("P9 D0 boundary count drift")
    rule["local_raw_boundary_indices"] == "0_through_767" ||
        error("P9 D0 local boundary domain drift")
    rule["global_raw_boundary_indices"] == "1536_through_2303" ||
        error("P9 D0 global boundary map drift")
    parse(BigInt, rule["future_S0_maximum_strictly_legal_cumulative_ticks"]) ==
        fld(3 * (BigInt(1) << 128) - 1, BigInt(400000)) ||
        error("P9 D0 three-step strict maximum drift")

    rule["ranking_key"] == Any[
        "sign_cleared_binary64_magnitude_bits_ascending",
        "unsigned_majorana_mask_ascending",
    ] || error("P9 D0 bit-order key drift")
    rule["semantic_reference_rank_key"] == Any[
        "exact_point_abs_ticks_ascending",
        "sign_cleared_binary64_magnitude_bits_ascending",
        "unsigned_majorana_mask_ascending",
    ] || error("P9 D0 P6 reference-rank key drift")
    rule["P8_conditional_semantics_is_not_a_resource_or_host_equivalence_claim"] ==
        true || error("P9 D0 P8 scope drift")

    selector = fixture["bit_order_selector"]
    selector["selector_order"] ==
        "(sign_cleared_binary64_magnitude_bits,unsigned_majorana_mask)" ||
        error("P9 D0 bit-order selector key drift")
    selector["exact_point_cost"] ==
        "ceil(2^128*abs(exact_finite_Float64))" ||
        error("P9 D0 exact point-cost contract drift")
    for key in (
        "finite_Float64_snapshot_required",
        "immutable_unique_unsigned_mask_snapshot_required",
        "first_unaffordable_positive_cost_stops_without_skipping",
        "zero_cost_rows_are_selected_at_zero_available_ticks",
        "P6_K37_is_a_frozen_callback_anchor_only_not_a_selector_tier",
        "callback_only_tests_precomputed_membership",
        "callback_iteration_order_cannot_consume_budget",
        "callback_revalidates_selected_coefficient_bits",
        "prepare_helper_reads_but_never_mutates_live_merged_main_or_authoritative_ticks",
        "all_deletions_are_performed_only_by_the_existing_truncate_callback",
        "existing_drop_ledger_is_the_only_authoritative_drop_charge",
        "existing_drop_ledger_recomputes_and_must_equal_the_selection_cost",
        "P8_does_not_establish_Julia_resource_cap_or_host_equivalence",
    )
        selector[key] == true || error("P9 D0 bit-order selector drift: $(key)")
    end

    p8 = fixture["P8_selector_semantics_custody"]
    p8["P8_A_result_commit"] ==
        "5cf53d73c4e375d9c8159cb7a742b4c22edd9622" ||
        error("P9 D0 P8-A result custody drift")
    p8["P8_A_report_sha256"] ==
        "014148df4be0f1c234456a5d0a09fb84dc7cb25d91d6d67e0d7f5ff66e3bb97a" ||
        error("P9 D0 P8-A report custody drift")
    p8["P8_B_result_commit"] == P9_D0_DIRECT_PARENT ||
        error("P9 D0 P8-B result custody drift")
    p8["P8_B_report_sha256"] ==
        "b47b8379f88deb2507df89996e113df10faff795e9eb814c254065ba66ef7828" ||
        error("P9 D0 P8-B report custody drift")
    p8["allowed_P8_A_claim"] ==
        "successful_selector_membership_and_selected_cost_total_only" ||
        error("P9 D0 P8-A claim scope drift")
    p8["allowed_P8_B_claim"] ==
        "independent_Git_object_bound_selector_semantics_only" ||
        error("P9 D0 P8-B claim scope drift")
    p8["P8_resource_cap_host_performance_and_runtime_equivalence_are_not_claimed"] ==
        true || error("P9 D0 P8 nonclaim drift")

    d4 = fixture["D4_route_custody"]
    d4["D4_result_commit"] == "c82e2443dfae07af17cb9108ccb344c2f0cbebba" ||
        error("P9 D0 D4 result custody drift")
    d4["D4_report_sha256"] ==
        "269e74dd23c33b0e2d1943d7f25e44ebcd897bdde1a96645a80eba4cf4e5da19" ||
        error("P9 D0 D4 report custody drift")
    d4["P9_does_not_use_D4_phase_timing_or_host_observations_as_an_algorithm_input"] ==
        true || error("P9 D0 D4 firewall drift")

    caps = fixture["deterministic_step3_probe_caps"]
    for (name, expected) in pairs(P9_STEP3_CAP_VALUES)
        p9_require_exact_positive_integer(
            caps[String(name)], expected, "P9 D0 cap $(name)",
        )
    end
    selection_caps =
        fixture["deterministic_step3_bit_order_selection_probe_caps"]
    for (name, expected) in pairs(P9_STEP3_SELECTION_CAP_VALUES)
        p9_require_exact_positive_integer(
            selection_caps[String(name)], expected,
            "P9 D0 selection cap $(name)",
        )
    end
    host = fixture["host_supervisor_caps"]
    host["MemoryMax_bytes"] == 2147483648 || error("P9 memory cap drift")
    host["MemorySwapMax_bytes"] == 0 || error("P9 swap cap drift")
    host["RuntimeMaxSec"] == "1800s" || error("P9 runtime cap drift")
    host["outer_safety_timeout_seconds"] == 1830 ||
        error("P9 outer timeout drift")
    host["D0_and_future_S0_use_the_same_memory_swap_and_runtime_admission"] ==
        true || error("P9 fixed-admission relation drift")

    arithmetic = fixture["outward_arithmetic"]
    arithmetic["maximum_BigInt_bit_length"] == 2048 ||
        error("P9 BigInt cap drift")
    arithmetic["maximum_trig_table_entries"] == 6 ||
        error("P9 trig-table cap drift")
    return fixture
end

function p9_validate_parent_custody(
    p9_fixture, p6_fixture, p5_fixture, p4_fixture, p3_fixture, p2_fixture,
    p6_fixture_path, p5_fixture_path, p4_fixture_path, p3_fixture_path,
    p2_fixture_path,
)
    validate_p6_fixture(p6_fixture)
    validate_p4_fixture(p4_fixture)
    validate_p4_parent_fixtures(
        p4_fixture, p3_fixture, p2_fixture, p3_fixture_path, p2_fixture_path,
    )
    get(p5_fixture, "fixture_id", nothing) ==
        "MAJORANA-P5-L8-CONDITIONAL-STEP2-THRESHOLD-S0-V1" ||
        error("unexpected inherited P5 fixture identity")
    canonical_sha256(p5_fixture) ==
        "bbac5a9281198ba87b336c6e45741d1468f85bb2997317943f1a45b6ac90de91" ||
        error("inherited P5 fixture semantic drift")

    paths = Dict(
        "P2" => p2_fixture_path,
        "P3" => p3_fixture_path,
        "P4" => p4_fixture_path,
        "P5" => p5_fixture_path,
        "P6" => p6_fixture_path,
    )
    pins = p9_fixture["required_base_fixture_sha256"]
    for label in ("P2", "P3", "P4", "P5", "P6")
        file_sha256(paths[label]) == pins[label] ||
            error("P9 inherited $(label) fixture digest mismatch")
    end

    frozen = p9_fixture["frozen_P6_prefix"]
    p6_caps = p6_fixture["deterministic_resource_caps"]
    for (key, value) in frozen["formal_step2_caps"]
        p6_caps[key] == value || error("P9 changed the P6 prefix cap $(key)")
    end
    frozen["formal_step2_selection_caps"] ==
        p6_fixture["deterministic_selection_caps"] ||
        error("P9 changed the P6 prefix selection caps")
    return nothing
end

function p9_validate_installed_source_closure(
    module_value::Module, expected::NamedTuple, label::AbstractString,
)
    module_path = pathof(module_value)
    module_path === nothing && error("P9 D0 $(label) source path is unavailable")
    observed = source_tree_closure(module_path)
    observed == expected ||
        error("P9 D0 installed $(label) source-tree closure drift")
    return observed
end

function p9_validate_fixture_source_closure(
    value, expected::NamedTuple, label::AbstractString,
)
    p9_require_exact_keys(
        value, ("file_count", "total_bytes", "closure_sha256"),
        "P9 D0 $(label) fixture source-tree closure",
    )
    p9_require_exact_positive_integer(
        value["file_count"], expected.file_count,
        "P9 D0 $(label) fixture source-tree file count",
    )
    p9_require_exact_positive_integer(
        value["total_bytes"], expected.total_bytes,
        "P9 D0 $(label) fixture source-tree byte count",
    )
    value["closure_sha256"] == expected.closure_sha256 ||
        error("P9 D0 $(label) fixture source-tree digest drift")
    return value
end

function p9_validate_runtime(p9_fixture)
    active_project = Base.active_project()
    active_project === nothing && error("P9 D0 requires an active project")
    manifest_path = joinpath(dirname(active_project), "Manifest.toml")
    isfile(manifest_path) || error("P9 D0 Manifest.toml missing")
    Threads.nthreads() == 1 || error("P9 D0 requires one Julia thread")
    rounding(Float64) == RoundNearest || error("P9 D0 requires binary64 RNE")
    Base.JLOptions().use_compiled_modules == 0 ||
        error("P9 D0 compiled modules must be disabled")
    get(ENV, "JULIA_NUM_THREADS", "") == "1" ||
        error("P9 D0 JULIA_NUM_THREADS drift")
    get(ENV, "OPENBLAS_NUM_THREADS", "") == "1" ||
        error("P9 D0 OPENBLAS_NUM_THREADS drift")
    get(ENV, "LC_ALL", "") == "C" || error("P9 D0 locale drift")
    get(ENV, "TZ", "") == "UTC" || error("P9 D0 timezone drift")
    reinterpret(UInt64, EPSILON) == 0x3dd0000000000000 ||
        error("P9 D0 step-1 threshold bits drift")
    reinterpret(UInt64, P6_K37_THRESHOLD) == P6_K37_ABS_BITS ||
        error("P9 D0 lazy-anchor bits drift")

    julia_executable = joinpath(Sys.BINDIR, Base.julia_exename())
    image_file = unsafe_string(Base.JLOptions().image_file)
    file_sha256(julia_executable) == P9_JULIA_EXECUTABLE_SHA256 ||
        error("P9 D0 Julia executable drift")
    file_sha256(image_file) == P9_JULIA_SYSIMAGE_SHA256 ||
        error("P9 D0 Julia sysimage drift")
    file_sha256(active_project) == P9_PROJECT_SHA256 ||
        error("P9 D0 Project.toml drift")
    file_sha256(manifest_path) == P9_MANIFEST_SHA256 ||
        error("P9 D0 Manifest.toml drift")
    majorana_source_closure = p9_validate_installed_source_closure(
        MajoranaPropagation, P9_MAJORANA_PROPAGATION_SOURCE_CLOSURE,
        "MajoranaPropagation",
    )
    pauli_source_closure = p9_validate_installed_source_closure(
        MajoranaPropagation.PauliPropagation,
        P9_PAULI_PROPAGATION_SOURCE_CLOSURE, "PauliPropagation",
    )
    p6_path = joinpath(
        @__DIR__, "..", "majorana_certificate_p6", "majorana_p6_runner.jl",
    )
    file_sha256(p6_path) == P9_P6_RUNNER_SHA256 ||
        error("P9 D0 imported P6 runner drift")

    runtime = p9_fixture["runtime_custody"]
    runtime["julia_executable_sha256"] == P9_JULIA_EXECUTABLE_SHA256 ||
        error("P9 D0 fixture runtime drift")
    runtime["JULIA_NUM_THREADS"] == "1" || error("P9 thread fixture drift")
    runtime["OPENBLAS_NUM_THREADS"] == "1" ||
        error("P9 BLAS fixture drift")
    runtime["compiled_modules"] == false ||
        error("P9 compiled-module fixture drift")
    runtime["Float64_rounding_mode"] == "RoundNearest" ||
        error("P9 rounding fixture drift")
    runtime["locale"] == "C" || error("P9 locale fixture drift")
    runtime["timezone"] == "UTC" || error("P9 timezone fixture drift")
    runtime["runtime_lock_bytes_verified_by_preprobe_checker"] === true ||
        error("P9 runtime-lock byte verification fixture drift")
    p9_validate_fixture_source_closure(
        runtime["MajoranaPropagation_source_tree_closure"],
        majorana_source_closure, "MajoranaPropagation",
    )
    p9_validate_fixture_source_closure(
        runtime["PauliPropagation_source_tree_closure"],
        pauli_source_closure, "PauliPropagation",
    )
    return runtime
end

function p9_step3_engine_caps(caps)
    return Dict{String,Any}(
        "maximum_step2_accuracy_charged_events" =>
            caps["maximum_step3_accuracy_charged_events"],
        "maximum_step2_anticommuting_events" =>
            caps["maximum_step3_anticommuting_events"],
        "maximum_step2_boundary_retained_terms" =>
            caps["maximum_step3_boundary_retained_terms"],
        "maximum_step2_cap_scan_term_visits" =>
            caps["maximum_step3_cap_scan_term_visits"],
        "maximum_step2_current_terms_before_constituent" =>
            caps["maximum_step3_current_terms_before_constituent"],
        "maximum_step2_drop_defect_events" =>
            caps["maximum_step3_drop_defect_events"],
        "maximum_step2_final_retained_terms" =>
            caps["maximum_step3_final_retained_terms"],
        "maximum_step2_merge_defect_events" =>
            caps["maximum_step3_merge_defect_events"],
        "maximum_step2_premerge_terms" =>
            caps["maximum_step3_premerge_terms"],
        "maximum_step2_product_defect_events" =>
            caps["maximum_step3_product_defect_events"],
        "maximum_step2_propagation_term_visits" =>
            caps["maximum_step3_propagation_term_visits"],
        "maximum_step2_total_P2_charged_term_visits" =>
            caps["maximum_step3_total_P2_charged_term_visits"],
        "maximum_step2_total_P2_plus_accuracy_charged_events" =>
            caps["maximum_step3_total_P2_plus_accuracy_charged_events"],
        "maximum_step2_truncation_term_visits" =>
            caps["maximum_step3_truncation_term_visits"],
    )
end

function p9_step3_execution_fixture(p9_fixture, p3_fixture)
    result = deepcopy(p3_fixture)
    caps = p9_fixture["deterministic_step3_probe_caps"]
    result["outward_arithmetic"]["maximum_BigInt_bit_length"] =
        caps["maximum_BigInt_bit_length"]
    result["deterministic_resource_caps"] = Dict{String,Any}(
        "maximum_anticommuting_events" =>
            caps["maximum_step3_anticommuting_events"],
        "maximum_product_defect_events" =>
            caps["maximum_step3_product_defect_events"],
        "maximum_merge_defect_events" =>
            caps["maximum_step3_merge_defect_events"],
        "maximum_drop_defect_events" =>
            caps["maximum_step3_drop_defect_events"],
        "maximum_accuracy_charged_events" =>
            caps["maximum_step3_accuracy_charged_events"],
        "maximum_total_P2_plus_accuracy_charged_events" =>
            caps["maximum_step3_total_P2_plus_accuracy_charged_events"],
    )
    return result
end

function p9_clean_cap_context(context, mapped_step_index::Int)
    context === nothing && return Dict{String,Any}(
        "mapped_step_index" => mapped_step_index,
        "operation" => "resource_cap_precheck",
    )
    allowed = (
        "stage_index", "group", "composite_index", "constituent_index",
        "boundary_index",
    )
    result = Dict{String,Any}("mapped_step_index" => mapped_step_index)
    for key in allowed
        symbol = Symbol(key)
        if context isa NamedTuple && hasproperty(context, symbol)
            result[key] = getproperty(context, symbol)
        elseif context isa AbstractDict && haskey(context, key)
            result[key] = context[key]
        elseif context isa AbstractDict && haskey(context, symbol)
            result[key] = context[symbol]
        end
    end
    result["operation"] = "resource_cap_precheck"
    return result
end

function p9_clean_cap_event(cap_event, mapped_step_index::Int)
    cap_event === nothing && return nothing
    return (
        cap_name=String(cap_event.cap_name),
        limit=Int(cap_event.limit),
        attempted=Int(cap_event.attempted),
        context=p9_clean_cap_context(cap_event.context, mapped_step_index),
        rejected_operation_was_not_executed_after_cap_detection=true,
    )
end

function p9_resource_summary(execution, cap_event, final_state, mapped_step_index)
    execution === nothing && return nothing
    return (
        completed_composite_count=execution.completed_composites,
        completed_constituent_count=execution.completed_constituents,
        completed_truncation_boundary_count=execution.completed_boundaries,
        peak_premerge_contribution_count=execution.peak_premerge,
        peak_postmerge_unique_term_count=execution.peak_postmerge,
        anticommuting_split_count=execution.total_splits,
        threshold_dropped_term_count=execution.total_threshold_drops,
        exact_zero_dropped_term_count=execution.total_zero_drops,
        P2_resource_counters=public_counters(execution.p2_counters),
        accuracy_event_counters=public_accuracy_counters(execution.accuracy_counters),
        total_P2_plus_accuracy_charged_event_count=
            charged_total(execution.p2_counters) +
            accuracy_charged(execution.accuracy_counters),
        final_retained_term_count=
            final_state === nothing ? nothing : final_state.retained_term_count,
        cap_event=p9_clean_cap_event(cap_event, mapped_step_index),
    )
end

mutable struct P9SelectionResourceCounters
    total_snapshot_scan_term_visits::Int
    total_bit_order_sort_input_items::Int
    total_lazy_tick_evaluations::Int
    total_selected_membership_insertions::Int
    peak_bit_order_sort_input_terms::Int
    total_bit_order_selection_work_units::Int
    completed_selection_boundary_count::Int
end

P9SelectionResourceCounters() = P9SelectionResourceCounters(
    0, 0, 0, 0, 0, 0, 0,
)

const P9_ACTIVE_SELECTION_CAPS = Ref{Any}(nothing)
const P9_SELECTION_RESOURCES = Ref(P9SelectionResourceCounters())

mutable struct P9BoundaryDropDecision
    boundary_index::Int
    snapshot_count::Int
    snapshot_coefficient_bits::Dict{Any,UInt64}
    selected_masks::Set{Any}
    selected_cost_total::BigInt
    callback_seen_masks::Set{Any}
    callback_visit_count::Int
    validated::Bool
end

function p9_public_selection_resources()
    counters = P9_SELECTION_RESOURCES[]
    counters.total_bit_order_selection_work_units ==
        counters.total_snapshot_scan_term_visits +
        counters.total_bit_order_sort_input_items +
        counters.total_lazy_tick_evaluations +
        counters.total_selected_membership_insertions ||
        error("P9 bit-order selection-work accounting identity failed")
    return (
        total_snapshot_scan_term_visits=
            counters.total_snapshot_scan_term_visits,
        total_bit_order_sort_input_items=
            counters.total_bit_order_sort_input_items,
        total_lazy_tick_evaluations=
            counters.total_lazy_tick_evaluations,
        total_selected_membership_insertions=
            counters.total_selected_membership_insertions,
        peak_bit_order_sort_input_terms=
            counters.peak_bit_order_sort_input_terms,
        total_bit_order_selection_work_units=
            counters.total_bit_order_selection_work_units,
        completed_selection_boundary_count=
            counters.completed_selection_boundary_count,
    )
end

function p9_reset_selection_state!(caps)
    P9_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P9 bit-order selection caps are already active")
    caps isa AbstractDict || error("P9 bit-order selection caps must be an object")
    P9_ACTIVE_SELECTION_CAPS[] = caps
    P9_SELECTION_RESOURCES[] = P9SelectionResourceCounters()
    return nothing
end

function p9_clear_selection_state!()
    P9_ACTIVE_SELECTION_CAPS[] = nothing
    return nothing
end

function p9_selection_cap_context(
    boundary_index::Int, operation::AbstractString,
)
    return (boundary_index=boundary_index, operation=String(operation))
end

function p9_charge_selection!(
    field::Symbol, amount::Int, cap_key::String,
    boundary_index::Int, operation::AbstractString,
)
    amount >= 0 || error("negative P9 bit-order selection-resource charge")
    amount == 0 && return nothing
    caps = P9_ACTIVE_SELECTION_CAPS[]
    caps === nothing && error("P9 bit-order selection caps are inactive")
    counters = P9_SELECTION_RESOURCES[]
    current = getfield(counters, field)
    amount <= typemax(Int) - current ||
        error("P9 bit-order selection counter overflow")
    attempted = current + amount
    limit = Int(caps[cap_key])
    attempted <= limit || throw(CapExceeded(
        cap_key, limit, attempted,
        p9_selection_cap_context(boundary_index, operation),
    ))

    total_current = counters.total_bit_order_selection_work_units
    amount <= typemax(Int) - total_current ||
        error("P9 bit-order total-selection counter overflow")
    total_attempted = total_current + amount
    total_limit = Int(caps["maximum_total_bit_order_selection_work_units"])
    total_attempted <= total_limit || throw(CapExceeded(
        "maximum_total_bit_order_selection_work_units", total_limit,
        total_attempted, p9_selection_cap_context(boundary_index, operation),
    ))

    setfield!(counters, field, attempted)
    counters.total_bit_order_selection_work_units = total_attempted
    return nothing
end

function p9_observe_bit_order_sort_input!(
    size::Int, boundary_index::Int, operation::AbstractString,
)
    size >= 0 || error("negative P9 bit-order buffer size")
    counters = P9_SELECTION_RESOURCES[]
    attempted = max(counters.peak_bit_order_sort_input_terms, size)
    caps = P9_ACTIVE_SELECTION_CAPS[]
    caps === nothing && error("P9 bit-order selection caps are inactive")
    limit = Int(caps["maximum_peak_bit_order_sort_input_terms"])
    attempted <= limit || throw(CapExceeded(
        "maximum_peak_bit_order_sort_input_terms", limit, attempted,
        p9_selection_cap_context(boundary_index, operation),
    ))
    counters.peak_bit_order_sort_input_terms = attempted
    return nothing
end

function p9_snapshot_rows(merged_main, boundary_index::Int)
    table = p6_merged_table(merged_main)
    count = length(table)
    p9_observe_bit_order_sort_input!(
        count, boundary_index, "postmerge_snapshot_buffer",
    )
    p9_charge_selection!(
        :total_snapshot_scan_term_visits, count,
        "maximum_snapshot_scan_term_visits", boundary_index,
        "postmerge_snapshot_scan",
    )
    rows = P6SnapshotRow[]
    sizehint!(rows, count)
    for (mask, coefficient) in table
        mask isa Unsigned || error("P9 Majorana mask is not unsigned")
        coefficient isa Float64 || error("unexpected P9 coefficient type")
        isfinite(coefficient) || error("non-finite P9 postmerge coefficient")
        bits = reinterpret(UInt64, coefficient)
        push!(rows, P6SnapshotRow(
            mask, coefficient, bits, bits & P6_ABS_BITS_MASK,
        ))
    end
    length(rows) == count || error("P9 snapshot count mismatch")
    return rows
end

p9_bit_order_key(row::P6SnapshotRow) = (row.abs_bits, row.mask)

function p9_sort_bit_order_rows!(
    rows::Vector{P6SnapshotRow}, boundary_index::Int,
)
    p9_observe_bit_order_sort_input!(
        length(rows), boundary_index, "bit_order_sort_buffer",
    )
    p9_charge_selection!(
        :total_bit_order_sort_input_items, length(rows),
        "maximum_bit_order_sort_input_items", boundary_index,
        "bit_order_sort",
    )
    sort!(rows; by=p9_bit_order_key)
    return rows
end

function p9_point_cost(
    row::P6SnapshotRow, maximum_bits::Int, boundary_index::Int,
)::BigInt
    p9_charge_selection!(
        :total_lazy_tick_evaluations, 1,
        "maximum_lazy_tick_evaluations", boundary_index,
        "bit_order_lazy_point_cost",
    )
    return point_abs_ticks(
        row.coefficient, maximum_bits,
        p9_selection_cap_context(boundary_index, "bit_order_lazy_point_cost"),
    )
end

function p9_record_selected!(
    selected_masks::Set{Any}, rows::Vector{P6RankRow}, boundary_index::Int,
)::BigInt
    p9_charge_selection!(
        :total_selected_membership_insertions, length(rows),
        "maximum_selected_membership_insertions", boundary_index,
        "selected_membership_insertions",
    )
    total = BigInt(0)
    for row in rows
        mask = row.snapshot.mask
        mask in selected_masks && error("duplicate P9 selected mask")
        push!(selected_masks, mask)
        total += row.point_cost
    end
    return total
end

function p9_prepare_boundary_drop!(
    merged_main, ticks, boundary_index::Int, maximum_bits::Int, _context,
)
    P9_ACTIVE_SELECTION_CAPS[] === nothing &&
        error("P9 bit-order selection caps are inactive")
    0 <= boundary_index < P6_BOUNDARY_COUNT ||
        error("P9 boundary index outside 0:767")
    maximum_bits == 2048 || error("unexpected P9 BigInt cap")

    rows = p9_snapshot_rows(merged_main, boundary_index)
    snapshot_bits = Dict{Any,UInt64}(
        row.mask => row.coefficient_bits for row in rows
    )
    length(snapshot_bits) == length(rows) ||
        error("P9 snapshot map lost a mask")

    current = total_ticks(ticks)
    current >= 0 || error("negative P9 local ledger")
    target = p6_prefix_target(boundary_index)
    available = max(BigInt(0), target - current)

    p9_sort_bit_order_rows!(rows, boundary_index)
    selected = P6RankRow[]
    remaining = available
    for row in rows
        cost = p9_point_cost(row, maximum_bits, boundary_index)
        cost <= remaining || break
        push!(selected, P6RankRow(row, cost))
        remaining -= cost
    end

    selected_masks = Set{Any}()
    selected_total = p9_record_selected!(
        selected_masks, selected, boundary_index,
    )
    selected_total == available - remaining ||
        error("P9 selected cost total drift")
    return P9BoundaryDropDecision(
        boundary_index, length(rows), snapshot_bits, selected_masks,
        selected_total, Set{Any}(), 0, false,
    )
end

function p9_should_drop(
    decision::P9BoundaryDropDecision, mask, coefficient, threshold::Float64,
)::Bool
    decision.validated && error("P9 decision was reused after validation")
    coefficient isa Float64 || error("unexpected P9 callback coefficient type")
    isfinite(coefficient) || error("non-finite P9 callback coefficient")
    reinterpret(UInt64, threshold) == P6_K37_ABS_BITS ||
        error("P9 frozen threshold anchor differs from K37")
    decision.callback_visit_count += 1

    haskey(decision.snapshot_coefficient_bits, mask) ||
        error("P9 callback mask absent from frozen snapshot")
    mask in decision.callback_seen_masks &&
        error("P9 callback visited a mask more than once")
    push!(decision.callback_seen_masks, mask)
    reinterpret(UInt64, coefficient) == decision.snapshot_coefficient_bits[mask] ||
        error("P9 callback coefficient differs from frozen snapshot")
    return mask in decision.selected_masks
end

function p9_validate_selected_drop_ticks!(
    decision::P9BoundaryDropDecision,
    transition_drop_ticks::Integer, dropped,
)
    decision.validated && error("P9 decision was validated twice")
    decision.callback_visit_count == decision.snapshot_count ||
        error("P9 callback visit count differs from the postmerge snapshot")
    length(decision.callback_seen_masks) == decision.snapshot_count ||
        error("P9 adaptive callback did not cover the full snapshot")

    actual_masks = Set{Any}()
    for row in dropped
        length(row) == 2 || error("invalid P9 adaptive dropped row")
        mask, coefficient = row
        mask in decision.selected_masks ||
            error("P9 upstream dropped a mask outside frozen membership")
        mask in actual_masks &&
            error("P9 upstream dropped a duplicate mask")
        push!(actual_masks, mask)
        reinterpret(UInt64, coefficient) ==
            decision.snapshot_coefficient_bits[mask] ||
            error("P9 dropped coefficient differs from frozen snapshot")
    end
    actual_masks == decision.selected_masks ||
        error("P9 upstream dropped membership differs from frozen selection")
    BigInt(transition_drop_ticks) == decision.selected_cost_total ||
        error("P9 adaptive selection cost differs from existing drop ledger")

    counters = P9_SELECTION_RESOURCES[]
    counters.completed_selection_boundary_count += 1
    counters.completed_selection_boundary_count <= P6_BOUNDARY_COUNT ||
        error("too many P9 selection boundaries")
    decision.validated = true
    return nothing
end

function p9_execute_adaptive_step(
    stages, execution_fixture, input_sum, trig_lookup, engine_caps,
    selection_caps, mapped_step_index::Int; copy_completed_output::Bool,
)
    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P9 adaptive engine caps are already active")
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P9 adaptive selection caps are already active")
    execution = nothing
    final_state = nothing
    cap_event = nothing
    selection_resources = nothing
    completed_output = nothing
    try
        P4_ACTIVE_STEP2_CAPS[] = engine_caps
        p6_reset_selection_state!(selection_caps)
        execution = execute_p6_step2(
            stages, execution_fixture, input_sum, trig_lookup,
            P6_K37_THRESHOLD,
        )
        final_cap = execution.cap_event === nothing ?
            precheck_p4_final_cap(execution, engine_caps) : nothing
        if execution.cap_event === nothing && final_cap === nothing
            execution.completed_boundaries == P6_BOUNDARY_COUNT ||
                error("P9 adaptive execution has wrong boundary count")
            P6_SELECTION_RESOURCES[].completed_selection_boundary_count ==
                P6_BOUNDARY_COUNT ||
                error("P9 adaptive selection boundary count mismatch")
            # D0 invokes the complete frozen finalizer solely to preserve the
            # future-S0 resource workload.  Every scientific field it computes
            # is transient: P9 reads only retained_term_count and never exports,
            # persists, compares, or otherwise treats those fields as evidence.
            final_state, postcheck_cap =
                finalize_p3_state!(execution, execution_fixture)
            postcheck_cap === nothing ||
                error("P9 final cap escaped its precheck")
        end
        cap_event = execution.cap_event === nothing ?
            final_cap : execution.cap_event
        selection_resources = p6_public_selection_resources()
        summary = p9_resource_summary(
            execution, cap_event, final_state, mapped_step_index,
        )
        if cap_event === nothing && copy_completed_output
            live_sum = MajoranaPropagation.PropagationBase.mainsum(execution.cache)
            completed_output = deepcopy(live_sum)
            length(completed_output.Majoranas) == final_state.retained_term_count ||
                error("P9 adaptive live-output term count drift")
        end
        return (
            summary=summary,
            selection_resources=selection_resources,
            completed_output=completed_output,
        )
    finally
        p6_clear_selection_state!()
        P6_SELECTION_RESOURCES[] = P6SelectionResourceCounters()
        P4_ACTIVE_STEP2_CAPS[] = nothing
    end
end

function p9_execute_bit_order_step(
    stages, execution_fixture, input_sum, trig_lookup, engine_caps,
    selection_caps; copy_completed_output::Bool,
)
    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P9 bit-order engine caps are already active")
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P9 bit-order execution inherited P6 selection state")
    P9_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P9 bit-order selection caps are already active")
    execution = nothing
    final_state = nothing
    cap_event = nothing
    selection_resources = nothing
    completed_output = nothing
    try
        P4_ACTIVE_STEP2_CAPS[] = engine_caps
        p9_reset_selection_state!(selection_caps)
        execution = execute_p9_step3_bitorder(
            stages, execution_fixture, input_sum, trig_lookup,
            P6_K37_THRESHOLD,
        )
        final_cap = execution.cap_event === nothing ?
            precheck_p4_final_cap(execution, engine_caps) : nothing
        if execution.cap_event === nothing && final_cap === nothing
            execution.completed_boundaries == P6_BOUNDARY_COUNT ||
                error("P9 bit-order execution has wrong boundary count")
            P9_SELECTION_RESOURCES[].completed_selection_boundary_count ==
                P6_BOUNDARY_COUNT ||
                error("P9 bit-order selection boundary count mismatch")
            # The complete finalizer remains a transient resource workload.
            # P9 reads only the retained count and does not export scientific
            # fields that it computes internally.
            final_state, postcheck_cap =
                finalize_p3_state!(execution, execution_fixture)
            postcheck_cap === nothing ||
                error("P9 bit-order final cap escaped its precheck")
        end
        cap_event = execution.cap_event === nothing ?
            final_cap : execution.cap_event
        selection_resources = p9_public_selection_resources()
        summary = p9_resource_summary(execution, cap_event, final_state, 3)
        if cap_event === nothing && copy_completed_output
            live_sum = MajoranaPropagation.PropagationBase.mainsum(execution.cache)
            completed_output = deepcopy(live_sum)
            length(completed_output.Majoranas) ==
                final_state.retained_term_count ||
                error("P9 bit-order live-output term count drift")
        end
        return (
            summary=summary,
            selection_resources=selection_resources,
            completed_output=completed_output,
        )
    finally
        p9_clear_selection_state!()
        P9_SELECTION_RESOURCES[] = P9SelectionResourceCounters()
        P4_ACTIVE_STEP2_CAPS[] = nothing
    end
end

function p9_execute_prefix(
    p9_fixture, p6_fixture, p3_fixture, stages, observable, trig_lookup,
)
    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P9 prefix caps leaked into step 1")
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P9 selection caps leaked into step 1")
    P6_SELECTION_RESOURCES[] = P6SelectionResourceCounters()

    execution1 = execute_p3(stages, p3_fixture, observable, trig_lookup)
    # As on the adaptive path, complete finalization is run only for future-S0
    # resource equivalence.  Its scientific fields remain transient; P9 reads
    # only retained_term_count and never exports, persists, or compares them.
    final1, final_cap1 = finalize_p3_state!(execution1, p3_fixture)
    cap1 = execution1.cap_event === nothing ? final_cap1 : execution1.cap_event
    execution1.cap_event !== nothing && final_cap1 !== nothing &&
        error("P9 D0 step 1 produced two cap events")
    step1 = p9_resource_summary(execution1, cap1, final1, 1)
    if cap1 !== nothing
        return (
            step1=step1, step2=nothing, step1_to_step2_link=nothing,
            step2_selection_resources=nothing,
            prefix_conformed=false, step3_input=nothing,
        )
    end

    live_step1_sum = MajoranaPropagation.PropagationBase.mainsum(execution1.cache)
    step2_input = deepcopy(live_step1_sum)
    step2_input_count = length(step2_input.Majoranas)
    step2_input_count == final1.retained_term_count ||
        error("P9 step1-to-step2 term-count drift")
    step1_to_step2_link = (
        same_process=true,
        checkpoint_or_serialized_state_used=false,
        previous_step_final_term_count=final1.retained_term_count,
        next_step_input_term_count=step2_input_count,
    )
    expected_step_link = (
        same_process=true,
        checkpoint_or_serialized_state_used=false,
        step1_final_term_count=final1.retained_term_count,
        step2_input_term_count=step2_input_count,
    )
    live_step1_sum = nothing
    execution1 = nothing
    final1 = nothing
    GC.gc()

    step2_fixture = p6_step2_execution_fixture(p6_fixture, p3_fixture)
    step2_caps = p6_fixture["deterministic_resource_caps"]
    step2_selection_caps = p6_fixture["deterministic_selection_caps"]
    step2_run = p9_execute_adaptive_step(
        stages, step2_fixture, step2_input, trig_lookup, step2_caps,
        step2_selection_caps, 2; copy_completed_output=true,
    )
    step2 = step2_run.summary
    step2_selection_resources = step2_run.selection_resources
    if step2.cap_event !== nothing
        return (
            step1=step1, step2=step2,
            step1_to_step2_link=step1_to_step2_link,
            step2_selection_resources=step2_selection_resources,
            prefix_conformed=false, step3_input=nothing,
        )
    end

    projection = (
        step1=step1,
        step2=step2,
        step_link=expected_step_link,
        selection_resources=step2_selection_resources,
    )
    prefix_conformed = canonical_json(projection) == canonical_json(
        p9_fixture["expected_P6_prefix_resource_projection"],
    )
    step3_input = prefix_conformed ? step2_run.completed_output : nothing
    step2_run = nothing
    step2_input = nothing
    GC.gc()
    return (
        step1=step1, step2=step2,
        step1_to_step2_link=step1_to_step2_link,
        step2_selection_resources=step2_selection_resources,
        prefix_conformed=prefix_conformed, step3_input=step3_input,
    )
end

function p9_assert_public_vocabulary(value, path::String="\$")
    forbidden = (
        "budget", "slack", "cutoff", "winner", "fallback", "neel",
        "coefficient_bits", "mask_hex", "drop_rows", "term_stream",
        "allocation_pass", "operator_error_ticks", "product_defect_ticks",
        "merge_defect_ticks", "drop_defect_ticks",
    )
    if value isa NamedTuple
        for key in keys(value)
            name = String(key)
            any(fragment -> occursin(fragment, lowercase(name)), forbidden) &&
                error("forbidden P9 D0 public key at $(path).$(name)")
            p9_assert_public_vocabulary(
                getproperty(value, key), "$(path).$(name)",
            )
        end
    elseif value isa AbstractDict
        for (key, item) in value
            name = String(key)
            any(fragment -> occursin(fragment, lowercase(name)), forbidden) &&
                error("forbidden P9 D0 public key at $(path).$(name)")
            p9_assert_public_vocabulary(item, "$(path).$(name)")
        end
    elseif value isa AbstractVector || value isa Tuple
        for (index, item) in enumerate(value)
            p9_assert_public_vocabulary(item, "$(path)[$(index)]")
        end
    elseif value isa AbstractString
        lower = lowercase(value)
        any(fragment -> occursin(fragment, lower), forbidden) &&
            error("forbidden P9 D0 public string at $(path)")
    end
    return value
end

function execute_p9_step3_bitorder(stages, fixture, observable, trig_lookup, threshold::Float64)
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
                        p6_drop_decision = p9_prepare_boundary_drop!(
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
                            should_drop = p9_should_drop(
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
                        p9_validate_selected_drop_ticks!(
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

function main_p9_d0()
    P9_D0_FAILURE_PHASE[] = P9_D0_INVALID_FAILURE_PHASE
    length(ARGS) == 7 || error(
        "usage: majorana_p9_bit_order_step3_resource_probe.jl P9_D0_FIXTURE.json " *
        "P6_FIXTURE.json P5_FIXTURE.json P4_FIXTURE.json P3_FIXTURE.json " *
        "P2_FIXTURE.json MODE",
    )
    p9_fixture_path = abspath(ARGS[1])
    p6_fixture_path = abspath(ARGS[2])
    p5_fixture_path = abspath(ARGS[3])
    p4_fixture_path = abspath(ARGS[4])
    p3_fixture_path = abspath(ARGS[5])
    p2_fixture_path = abspath(ARGS[6])
    mode = String(ARGS[7])
    mode == P9_D0_PROBE_MODE || error("unexpected P9 D0 mode")

    p9_fixture = validate_p9_d0_fixture(JSON.parsefile(p9_fixture_path))
    p6_fixture = JSON.parsefile(p6_fixture_path)
    p5_fixture = JSON.parsefile(p5_fixture_path)
    p4_fixture = JSON.parsefile(p4_fixture_path)
    p3_fixture = JSON.parsefile(p3_fixture_path)
    p2_fixture = JSON.parsefile(p2_fixture_path)
    p9_validate_parent_custody(
        p9_fixture, p6_fixture, p5_fixture, p4_fixture, p3_fixture, p2_fixture,
        p6_fixture_path, p5_fixture_path, p4_fixture_path, p3_fixture_path,
        p2_fixture_path,
    )
    runtime_custody = p9_validate_runtime(p9_fixture)

    # From this point through construction of the raw aggregate witness, any
    # failure is a host/runtime generation failure, not a custody/schema fact.
    P9_D0_FAILURE_PHASE[] = P9_D0_INDETERMINATE_FAILURE_PHASE
    maximum_bits = Int(p3_fixture["outward_arithmetic"][
        "maximum_BigInt_bit_length"
    ])
    maximum_bits == 2048 || error("P9 inherited BigInt cap drift")
    trig_lookup, trig_table = build_trig_table(p3_fixture, maximum_bits)
    length(trig_table) <= 6 || error("P9 trig table exceeds its cap")
    stages, _schedule = build_schedule()
    observable, _initial = initial_observable()

    prefix = p9_execute_prefix(
        p9_fixture, p6_fixture, p3_fixture, stages, observable, trig_lookup,
    )
    step3 = nothing
    step2_to_step3_link = nothing
    step3_bit_order_selection_resources = nothing
    step3_started = false
    if prefix.prefix_conformed
        step3_started = true
        step3_input = prefix.step3_input
        step3_input_count = length(step3_input.Majoranas)
        step3_input_count == prefix.step2.final_retained_term_count ||
            error("P9 step2-to-step3 term-count drift")
        step2_to_step3_link = (
            same_process=true,
            checkpoint_or_serialized_state_used=false,
            previous_step_final_term_count=
                prefix.step2.final_retained_term_count,
            next_step_input_term_count=step3_input_count,
        )
        step3_caps = p9_step3_engine_caps(
            p9_fixture["deterministic_step3_probe_caps"],
        )
        step3_selection_caps =
            p9_fixture["deterministic_step3_bit_order_selection_probe_caps"]
        step3_fixture = p9_step3_execution_fixture(p9_fixture, p3_fixture)
        step3_run = p9_execute_bit_order_step(
            stages, step3_fixture, step3_input, trig_lookup, step3_caps,
            step3_selection_caps; copy_completed_output=false,
        )
        step3 = step3_run.summary
        step3_bit_order_selection_resources = step3_run.selection_resources
    end

    raw = (
        schema_version=1,
        probe_type=P9_D0_PROBE_TYPE,
        fixture_id=P9_D0_FIXTURE_ID,
        fixture_sha256=file_sha256(p9_fixture_path),
        fixture_canonical_sha256=canonical_sha256(p9_fixture),
        scientific_authority="NONE",
        certificate_eligible=false,
        result_contract_eligible=false,
        resource_observations_only=true,
        candidate=(
            candidate_id=P9_D0_CANDIDATE_ID,
            probe_mode=P9_D0_PROBE_MODE,
            identity=P9_D0_PROBE_MODE,
            formal_candidate=true,
            step1_path="fixed_P3_2^-34",
            step2_path="frozen_P6_E768_MAX_LAZY37_V1",
            step3_path="full_domain_bit_order_E768_STEP3_V1",
        ),
        runtime_custody=runtime_custody,
        step1=prefix.step1,
        step2=prefix.step2,
        step3=step3,
        step1_to_step2_link=prefix.step1_to_step2_link,
        step2_to_step3_link=step2_to_step3_link,
        step2_selection_resources=prefix.step2_selection_resources,
        step3_bit_order_selection_resources=
            step3_bit_order_selection_resources,
        P6_prefix_resource_projection_conformed=prefix.prefix_conformed,
        step3_started=step3_started,
        explicit_exclusions=P9_PUBLIC_EXCLUSIONS,
    )
    # Public-vocabulary validation and canonical serialization are schema
    # checks.  They are the only post-computation INVALID phase.
    P9_D0_FAILURE_PHASE[] = P9_D0_INVALID_FAILURE_PHASE
    p9_assert_public_vocabulary(raw)
    output = canonical_json(raw) * "\n"

    # Once the complete output string exists, writes and flushes are generation
    # I/O.  A failure here is INDETERMINATE and must never be called INVALID.
    P9_D0_FAILURE_PHASE[] = P9_D0_INDETERMINATE_FAILURE_PHASE
    write(stdout, output)
    flush(stdout)
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    try
        main_p9_d0()
    catch error_value
        if error_value isa OutOfMemoryError
            println(stderr, "P9_D0_HOST_FAILURE_OOM")
            exit(70)
        elseif error_value isa InterruptException
            println(stderr, "P9_D0_INDETERMINATE_INTERRUPT")
            exit(70)
        elseif P9_D0_FAILURE_PHASE[] === P9_D0_INVALID_FAILURE_PHASE
            println(stderr, "P9_D0_INVALID")
            exit(66)
        else
            println(stderr, "P9_D0_INDETERMINATE_GENERATION_FAILURE")
            exit(70)
        end
    end
end
