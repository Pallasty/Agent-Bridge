#!/usr/bin/env julia

# Non-authoritative P7 D0 resource probe.  The already-frozen formal P6
# runner is imported byte-for-byte; no P6 D0 transform or result artifact is
# available here.  One fresh process reconstructs O0 -> step 1 -> step 2 and,
# only after exact aggregate-resource conformance, continues to step 3 from a
# live in-memory deepcopy.  The sole public output contains resource counts.
include(joinpath(
    @__DIR__, "..", "majorana_certificate_p6", "majorana_p6_runner.jl",
))

const P7_D0_PROBE_TYPE =
    "majorana_p7_step3_e768_max_lazy37_resource_probe_d0_v1"
const P7_D0_FIXTURE_ID = "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D0-V1"
const P7_D0_FIXTURE_CANONICAL_SHA256 =
    "eddf6de4f36c142dfc6d725b128c3be5bab4dd2be38fb2d0a2a0143240ca82bb"
const P7_D0_DIRECT_PARENT = "254f893dc5e40c27f6c4fb17dfd1c07ab749c2e4"
const P7_D0_PROBE_MODE = "E768_MAX_LAZY37_STEP3_V1"
const P7_D0_CANDIDATE_ID = "E768-MAX-LAZY37-STEP3-V1"
const P7_D0_ALGORITHM_ID = "MAJORANA-P7-E768-MAX-LAZY37-STEP3-V1"
const P7_D0_INVALID_FAILURE_PHASE = :INVALID
const P7_D0_INDETERMINATE_FAILURE_PHASE = :INDETERMINATE
const P7_D0_FAILURE_PHASE = Ref{Symbol}(P7_D0_INVALID_FAILURE_PHASE)
const P7_P6_RUNNER_SHA256 =
    "b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c"
const P7_PROJECT_SHA256 =
    "62810ce02db16bf25cb74941f27f58ee556ee0826abc4aa47296ce8188a5048f"
const P7_MANIFEST_SHA256 =
    "987572a908176b21cfbe80c385acdd0b4ab47b6c6dcd3ea9a33dd8eb22559406"
const P7_JULIA_EXECUTABLE_SHA256 =
    "2976d17aba35be5d546e8e315e521bd9be3e58c2e64abfd588f186696e807b7d"
const P7_JULIA_SYSIMAGE_SHA256 =
    "4e6f6765863713b3088d1a8f3b3eb68913503253ac5aa3a7a13c5b21f64d23bb"
const P7_MAJORANA_PROPAGATION_SOURCE_CLOSURE = (
    file_count=42,
    total_bytes=1875632,
    closure_sha256=
        "744e743d88d7bc62da1ba11cef02909539de626bd4b0a5533b0b65d8aae309b5",
)
const P7_PAULI_PROPAGATION_SOURCE_CLOSURE = (
    file_count=119,
    total_bytes=7736347,
    closure_sha256=
        "ce1e6cac1b09573962136fce0f315fabbf8556c9075c4aa3545c41c6ee4c3783",
)

const P7_STEP3_CAP_VALUES = (
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

const P7_STEP3_SELECTION_CAP_VALUES = (
    maximum_peak_ranking_buffer_terms=1048576,
    maximum_ranking_scan_term_visits=2147483648,
    maximum_selected_membership_insertions=1073741824,
    maximum_sort_input_items=1073741824,
    maximum_tick_evaluations=1073741824,
    maximum_total_selection_work_units=4294967296,
)

const P7_PUBLIC_EXCLUSIONS = (
    "scientific_local_or_cumulative_error_values",
    "allocation_assessment_or_candidate_selection",
    "term_or_drop_stream_commitments",
    "checkerboard_observable_center_or_interval",
    "adaptive_execution_branch_as_scientific_evidence",
    "scientific_witness_result_contract_certificate_or_READY_authority",
)

function p7_require_exact_keys(value, expected, context::AbstractString)
    value isa AbstractDict || error("$(context) must be an object")
    Set(String.(keys(value))) == Set(String.(expected)) ||
        error("$(context) key mismatch")
    return value
end

function p7_require_exact_positive_integer(value, expected::Integer, context)
    value isa Integer || error("$(context) must be an integer")
    BigInt(value) == BigInt(expected) || error("$(context) drift")
    return value
end

function validate_p7_d0_fixture(fixture)
    canonical_sha256(fixture) == P7_D0_FIXTURE_CANONICAL_SHA256 ||
        error("P7 D0 fixture differs from the frozen semantic object")
    p7_require_exact_keys(fixture, (
        "schema_version", "fixture_id", "required_direct_parent_commit",
        "scientific_authority", "certificate_eligible", "candidate_design",
        "frozen_P6_prefix", "step3_adaptive_rule",
        "exact_lazy_implementation", "deterministic_step3_probe_caps",
        "deterministic_step3_selection_probe_caps", "host_supervisor_caps",
        "outward_arithmetic", "required_base_fixture_sha256",
        "expected_P6_prefix_resource_projection", "runtime_custody", "scope",
    ), "P7 D0 fixture")
    fixture["schema_version"] == 1 || error("unexpected P7 D0 schema")
    fixture["fixture_id"] == P7_D0_FIXTURE_ID ||
        error("unexpected P7 D0 fixture identity")
    fixture["required_direct_parent_commit"] == P7_D0_DIRECT_PARENT ||
        error("unexpected P7 D0 direct parent")
    fixture["scientific_authority"] == "NONE" ||
        error("P7 D0 fixture claims scientific authority")
    fixture["certificate_eligible"] == false ||
        error("P7 D0 fixture is certificate eligible")

    design = fixture["candidate_design"]
    design["probe_mode_order"] == Any[P7_D0_PROBE_MODE] ||
        error("P7 D0 probe order drift")
    design["formal_candidates"] == Any[P7_D0_CANDIDATE_ID] ||
        error("P7 D0 candidate set drift")
    design["formal_candidate_count"] == 1 ||
        error("P7 D0 candidate count drift")
    design["candidate_id"] == P7_D0_CANDIDATE_ID ||
        error("P7 D0 candidate identity drift")
    design["probe_mode"] == P7_D0_PROBE_MODE ||
        error("P7 D0 mode drift")
    design["algorithm_id"] == P7_D0_ALGORITHM_ID ||
        error("P7 D0 algorithm identity drift")
    design["control_candidate"] === nothing ||
        error("P7 D0 unexpectedly defines a control")
    design["design_disclosure"] == "P6_INFORMED_P7_RESULT_UNPINNED" ||
        error("P7 D0 hindsight disclosure drift")
    design["all_three_steps_execute_in_one_process"] == true ||
        error("P7 D0 same-process chain drift")
    design["checkpoint_serialization_or_cross_process_resume_forbidden"] == true ||
        error("P7 D0 permits a checkpoint")

    rule = fixture["step3_adaptive_rule"]
    rule["algorithm_id"] == P7_D0_ALGORITHM_ID ||
        error("P7 D0 step-3 algorithm drift")
    rule["mapped_step_index"] == 3 || error("P7 mapped-step index drift")
    parse(BigInt, rule["grid_denominator"]) == (BigInt(1) << 128) ||
        error("P7 D0 grid drift")
    rule["local_allocation_denominator"] == 400000 ||
        error("P7 D0 allocation denominator drift")
    parse(BigInt, rule["maximum_strictly_legal_local_ticks"]) ==
        fld((BigInt(1) << 128) - 1, BigInt(400000)) ||
        error("P7 D0 local strict maximum drift")
    rule["local_boundary_count"] == 768 ||
        error("P7 D0 boundary count drift")
    rule["local_raw_boundary_indices"] == "0_through_767" ||
        error("P7 D0 local boundary domain drift")
    rule["global_raw_boundary_indices"] == "1536_through_2303" ||
        error("P7 D0 global boundary map drift")
    parse(BigInt, rule["future_S0_maximum_strictly_legal_cumulative_ticks"]) ==
        fld(3 * (BigInt(1) << 128) - 1, BigInt(400000)) ||
        error("P7 D0 three-step strict maximum drift")

    lazy = fixture["exact_lazy_implementation"]
    lazy["split_threshold_exponent"] == 37 ||
        error("P7 D0 lazy anchor drift")
    lazy["split_threshold_Float64_bits_hex"] == "3da0000000000000" ||
        error("P7 D0 lazy bits drift")
    lazy["hard_K37_eligibility_gate_is_forbidden"] == true ||
        error("P7 D0 permits a hard K37 gate")
    lazy["step2_and_step3_lazy_state_counters_membership_and_snapshots_are_disjoint"] ==
        true || error("P7 D0 selection-state separation drift")

    caps = fixture["deterministic_step3_probe_caps"]
    for (name, expected) in pairs(P7_STEP3_CAP_VALUES)
        p7_require_exact_positive_integer(
            caps[String(name)], expected, "P7 D0 cap $(name)",
        )
    end
    selection_caps = fixture["deterministic_step3_selection_probe_caps"]
    for (name, expected) in pairs(P7_STEP3_SELECTION_CAP_VALUES)
        p7_require_exact_positive_integer(
            selection_caps[String(name)], expected,
            "P7 D0 selection cap $(name)",
        )
    end
    host = fixture["host_supervisor_caps"]
    host["MemoryMax_bytes"] == 2147483648 || error("P7 memory cap drift")
    host["MemorySwapMax_bytes"] == 0 || error("P7 swap cap drift")
    host["RuntimeMaxSec"] == "1800s" || error("P7 runtime cap drift")
    host["outer_safety_timeout_seconds"] == 1830 ||
        error("P7 outer timeout drift")
    host["D0_and_future_S0_use_the_same_memory_swap_and_runtime_admission"] ==
        true || error("P7 fixed-admission relation drift")

    arithmetic = fixture["outward_arithmetic"]
    arithmetic["maximum_BigInt_bit_length"] == 2048 ||
        error("P7 BigInt cap drift")
    arithmetic["maximum_trig_table_entries"] == 6 ||
        error("P7 trig-table cap drift")
    return fixture
end

function p7_validate_parent_custody(
    p7_fixture, p6_fixture, p5_fixture, p4_fixture, p3_fixture, p2_fixture,
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
    pins = p7_fixture["required_base_fixture_sha256"]
    for label in ("P2", "P3", "P4", "P5", "P6")
        file_sha256(paths[label]) == pins[label] ||
            error("P7 inherited $(label) fixture digest mismatch")
    end

    frozen = p7_fixture["frozen_P6_prefix"]
    p6_caps = p6_fixture["deterministic_resource_caps"]
    for (key, value) in frozen["formal_step2_caps"]
        p6_caps[key] == value || error("P7 changed the P6 prefix cap $(key)")
    end
    frozen["formal_step2_selection_caps"] ==
        p6_fixture["deterministic_selection_caps"] ||
        error("P7 changed the P6 prefix selection caps")
    return nothing
end

function p7_validate_installed_source_closure(
    module_value::Module, expected::NamedTuple, label::AbstractString,
)
    module_path = pathof(module_value)
    module_path === nothing && error("P7 D0 $(label) source path is unavailable")
    observed = source_tree_closure(module_path)
    observed == expected ||
        error("P7 D0 installed $(label) source-tree closure drift")
    return observed
end

function p7_validate_fixture_source_closure(
    value, expected::NamedTuple, label::AbstractString,
)
    p7_require_exact_keys(
        value, ("file_count", "total_bytes", "closure_sha256"),
        "P7 D0 $(label) fixture source-tree closure",
    )
    p7_require_exact_positive_integer(
        value["file_count"], expected.file_count,
        "P7 D0 $(label) fixture source-tree file count",
    )
    p7_require_exact_positive_integer(
        value["total_bytes"], expected.total_bytes,
        "P7 D0 $(label) fixture source-tree byte count",
    )
    value["closure_sha256"] == expected.closure_sha256 ||
        error("P7 D0 $(label) fixture source-tree digest drift")
    return value
end

function p7_validate_runtime(p7_fixture)
    active_project = Base.active_project()
    active_project === nothing && error("P7 D0 requires an active project")
    manifest_path = joinpath(dirname(active_project), "Manifest.toml")
    isfile(manifest_path) || error("P7 D0 Manifest.toml missing")
    Threads.nthreads() == 1 || error("P7 D0 requires one Julia thread")
    rounding(Float64) == RoundNearest || error("P7 D0 requires binary64 RNE")
    Base.JLOptions().use_compiled_modules == 0 ||
        error("P7 D0 compiled modules must be disabled")
    get(ENV, "JULIA_NUM_THREADS", "") == "1" ||
        error("P7 D0 JULIA_NUM_THREADS drift")
    get(ENV, "OPENBLAS_NUM_THREADS", "") == "1" ||
        error("P7 D0 OPENBLAS_NUM_THREADS drift")
    get(ENV, "LC_ALL", "") == "C" || error("P7 D0 locale drift")
    get(ENV, "TZ", "") == "UTC" || error("P7 D0 timezone drift")
    reinterpret(UInt64, EPSILON) == 0x3dd0000000000000 ||
        error("P7 D0 step-1 threshold bits drift")
    reinterpret(UInt64, P6_K37_THRESHOLD) == P6_K37_ABS_BITS ||
        error("P7 D0 lazy-anchor bits drift")

    julia_executable = joinpath(Sys.BINDIR, Base.julia_exename())
    image_file = unsafe_string(Base.JLOptions().image_file)
    file_sha256(julia_executable) == P7_JULIA_EXECUTABLE_SHA256 ||
        error("P7 D0 Julia executable drift")
    file_sha256(image_file) == P7_JULIA_SYSIMAGE_SHA256 ||
        error("P7 D0 Julia sysimage drift")
    file_sha256(active_project) == P7_PROJECT_SHA256 ||
        error("P7 D0 Project.toml drift")
    file_sha256(manifest_path) == P7_MANIFEST_SHA256 ||
        error("P7 D0 Manifest.toml drift")
    majorana_source_closure = p7_validate_installed_source_closure(
        MajoranaPropagation, P7_MAJORANA_PROPAGATION_SOURCE_CLOSURE,
        "MajoranaPropagation",
    )
    pauli_source_closure = p7_validate_installed_source_closure(
        MajoranaPropagation.PauliPropagation,
        P7_PAULI_PROPAGATION_SOURCE_CLOSURE, "PauliPropagation",
    )
    p6_path = joinpath(
        @__DIR__, "..", "majorana_certificate_p6", "majorana_p6_runner.jl",
    )
    file_sha256(p6_path) == P7_P6_RUNNER_SHA256 ||
        error("P7 D0 imported P6 runner drift")

    runtime = p7_fixture["runtime_custody"]
    runtime["julia_executable_sha256"] == P7_JULIA_EXECUTABLE_SHA256 ||
        error("P7 D0 fixture runtime drift")
    runtime["JULIA_NUM_THREADS"] == "1" || error("P7 thread fixture drift")
    runtime["OPENBLAS_NUM_THREADS"] == "1" ||
        error("P7 BLAS fixture drift")
    runtime["compiled_modules"] == false ||
        error("P7 compiled-module fixture drift")
    runtime["Float64_rounding_mode"] == "RoundNearest" ||
        error("P7 rounding fixture drift")
    runtime["locale"] == "C" || error("P7 locale fixture drift")
    runtime["timezone"] == "UTC" || error("P7 timezone fixture drift")
    runtime["runtime_lock_bytes_verified_by_preprobe_checker"] === true ||
        error("P7 runtime-lock byte verification fixture drift")
    p7_validate_fixture_source_closure(
        runtime["MajoranaPropagation_source_tree_closure"],
        majorana_source_closure, "MajoranaPropagation",
    )
    p7_validate_fixture_source_closure(
        runtime["PauliPropagation_source_tree_closure"],
        pauli_source_closure, "PauliPropagation",
    )
    return runtime
end

function p7_step3_engine_caps(caps)
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

function p7_step3_execution_fixture(p7_fixture, p3_fixture)
    result = deepcopy(p3_fixture)
    caps = p7_fixture["deterministic_step3_probe_caps"]
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

function p7_clean_cap_context(context, mapped_step_index::Int)
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

function p7_clean_cap_event(cap_event, mapped_step_index::Int)
    cap_event === nothing && return nothing
    return (
        cap_name=String(cap_event.cap_name),
        limit=Int(cap_event.limit),
        attempted=Int(cap_event.attempted),
        context=p7_clean_cap_context(cap_event.context, mapped_step_index),
        rejected_operation_was_not_executed_after_cap_detection=true,
    )
end

function p7_resource_summary(execution, cap_event, final_state, mapped_step_index)
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
        cap_event=p7_clean_cap_event(cap_event, mapped_step_index),
    )
end

function p7_execute_adaptive_step(
    stages, execution_fixture, input_sum, trig_lookup, engine_caps,
    selection_caps, mapped_step_index::Int; copy_completed_output::Bool,
)
    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P7 adaptive engine caps are already active")
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P7 adaptive selection caps are already active")
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
                error("P7 adaptive execution has wrong boundary count")
            P6_SELECTION_RESOURCES[].completed_selection_boundary_count ==
                P6_BOUNDARY_COUNT ||
                error("P7 adaptive selection boundary count mismatch")
            # D0 invokes the complete frozen finalizer solely to preserve the
            # future-S0 resource workload.  Every scientific field it computes
            # is transient: P7 reads only retained_term_count and never exports,
            # persists, compares, or otherwise treats those fields as evidence.
            final_state, postcheck_cap =
                finalize_p3_state!(execution, execution_fixture)
            postcheck_cap === nothing ||
                error("P7 final cap escaped its precheck")
        end
        cap_event = execution.cap_event === nothing ?
            final_cap : execution.cap_event
        selection_resources = p6_public_selection_resources()
        summary = p7_resource_summary(
            execution, cap_event, final_state, mapped_step_index,
        )
        if cap_event === nothing && copy_completed_output
            live_sum = MajoranaPropagation.PropagationBase.mainsum(execution.cache)
            completed_output = deepcopy(live_sum)
            length(completed_output.Majoranas) == final_state.retained_term_count ||
                error("P7 adaptive live-output term count drift")
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

function p7_execute_prefix(
    p7_fixture, p6_fixture, p3_fixture, stages, observable, trig_lookup,
)
    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P7 prefix caps leaked into step 1")
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P7 selection caps leaked into step 1")
    P6_SELECTION_RESOURCES[] = P6SelectionResourceCounters()

    execution1 = execute_p3(stages, p3_fixture, observable, trig_lookup)
    # As on the adaptive path, complete finalization is run only for future-S0
    # resource equivalence.  Its scientific fields remain transient; P7 reads
    # only retained_term_count and never exports, persists, or compares them.
    final1, final_cap1 = finalize_p3_state!(execution1, p3_fixture)
    cap1 = execution1.cap_event === nothing ? final_cap1 : execution1.cap_event
    execution1.cap_event !== nothing && final_cap1 !== nothing &&
        error("P7 D0 step 1 produced two cap events")
    step1 = p7_resource_summary(execution1, cap1, final1, 1)
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
        error("P7 step1-to-step2 term-count drift")
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
    step2_run = p7_execute_adaptive_step(
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
        p7_fixture["expected_P6_prefix_resource_projection"],
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

function p7_assert_public_vocabulary(value, path::String="\$")
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
                error("forbidden P7 D0 public key at $(path).$(name)")
            p7_assert_public_vocabulary(
                getproperty(value, key), "$(path).$(name)",
            )
        end
    elseif value isa AbstractDict
        for (key, item) in value
            name = String(key)
            any(fragment -> occursin(fragment, lowercase(name)), forbidden) &&
                error("forbidden P7 D0 public key at $(path).$(name)")
            p7_assert_public_vocabulary(item, "$(path).$(name)")
        end
    elseif value isa AbstractVector || value isa Tuple
        for (index, item) in enumerate(value)
            p7_assert_public_vocabulary(item, "$(path)[$(index)]")
        end
    elseif value isa AbstractString
        lower = lowercase(value)
        any(fragment -> occursin(fragment, lower), forbidden) &&
            error("forbidden P7 D0 public string at $(path)")
    end
    return value
end

function main_p7_d0()
    P7_D0_FAILURE_PHASE[] = P7_D0_INVALID_FAILURE_PHASE
    length(ARGS) == 7 || error(
        "usage: majorana_p7_step3_resource_probe.jl P7_D0_FIXTURE.json " *
        "P6_FIXTURE.json P5_FIXTURE.json P4_FIXTURE.json P3_FIXTURE.json " *
        "P2_FIXTURE.json MODE",
    )
    p7_fixture_path = abspath(ARGS[1])
    p6_fixture_path = abspath(ARGS[2])
    p5_fixture_path = abspath(ARGS[3])
    p4_fixture_path = abspath(ARGS[4])
    p3_fixture_path = abspath(ARGS[5])
    p2_fixture_path = abspath(ARGS[6])
    mode = String(ARGS[7])
    mode == P7_D0_PROBE_MODE || error("unexpected P7 D0 mode")

    p7_fixture = validate_p7_d0_fixture(JSON.parsefile(p7_fixture_path))
    p6_fixture = JSON.parsefile(p6_fixture_path)
    p5_fixture = JSON.parsefile(p5_fixture_path)
    p4_fixture = JSON.parsefile(p4_fixture_path)
    p3_fixture = JSON.parsefile(p3_fixture_path)
    p2_fixture = JSON.parsefile(p2_fixture_path)
    p7_validate_parent_custody(
        p7_fixture, p6_fixture, p5_fixture, p4_fixture, p3_fixture, p2_fixture,
        p6_fixture_path, p5_fixture_path, p4_fixture_path, p3_fixture_path,
        p2_fixture_path,
    )
    runtime_custody = p7_validate_runtime(p7_fixture)

    # From this point through construction of the raw aggregate witness, any
    # failure is a host/runtime generation failure, not a custody/schema fact.
    P7_D0_FAILURE_PHASE[] = P7_D0_INDETERMINATE_FAILURE_PHASE
    maximum_bits = Int(p3_fixture["outward_arithmetic"][
        "maximum_BigInt_bit_length"
    ])
    maximum_bits == 2048 || error("P7 inherited BigInt cap drift")
    trig_lookup, trig_table = build_trig_table(p3_fixture, maximum_bits)
    length(trig_table) <= 6 || error("P7 trig table exceeds its cap")
    stages, _schedule = build_schedule()
    observable, _initial = initial_observable()

    prefix = p7_execute_prefix(
        p7_fixture, p6_fixture, p3_fixture, stages, observable, trig_lookup,
    )
    step3 = nothing
    step2_to_step3_link = nothing
    step3_selection_resources = nothing
    step3_started = false
    if prefix.prefix_conformed
        step3_started = true
        step3_input = prefix.step3_input
        step3_input_count = length(step3_input.Majoranas)
        step3_input_count == prefix.step2.final_retained_term_count ||
            error("P7 step2-to-step3 term-count drift")
        step2_to_step3_link = (
            same_process=true,
            checkpoint_or_serialized_state_used=false,
            previous_step_final_term_count=
                prefix.step2.final_retained_term_count,
            next_step_input_term_count=step3_input_count,
        )
        step3_caps = p7_step3_engine_caps(
            p7_fixture["deterministic_step3_probe_caps"],
        )
        step3_selection_caps =
            p7_fixture["deterministic_step3_selection_probe_caps"]
        step3_fixture = p7_step3_execution_fixture(p7_fixture, p3_fixture)
        step3_run = p7_execute_adaptive_step(
            stages, step3_fixture, step3_input, trig_lookup, step3_caps,
            step3_selection_caps, 3; copy_completed_output=false,
        )
        step3 = step3_run.summary
        step3_selection_resources = step3_run.selection_resources
    end

    raw = (
        schema_version=1,
        probe_type=P7_D0_PROBE_TYPE,
        fixture_id=P7_D0_FIXTURE_ID,
        fixture_sha256=file_sha256(p7_fixture_path),
        fixture_canonical_sha256=canonical_sha256(p7_fixture),
        scientific_authority="NONE",
        certificate_eligible=false,
        result_contract_eligible=false,
        resource_observations_only=true,
        candidate=(
            candidate_id=P7_D0_CANDIDATE_ID,
            probe_mode=P7_D0_PROBE_MODE,
            identity=P7_D0_PROBE_MODE,
            formal_candidate=true,
            step1_path="fixed_P3_2^-34",
            step2_path="frozen_P6_E768_MAX_LAZY37_V1",
            step3_path="full_domain_E768_MAX_LAZY37_STEP3_V1",
        ),
        runtime_custody=runtime_custody,
        step1=prefix.step1,
        step2=prefix.step2,
        step3=step3,
        step1_to_step2_link=prefix.step1_to_step2_link,
        step2_to_step3_link=step2_to_step3_link,
        step2_selection_resources=prefix.step2_selection_resources,
        step3_selection_resources=step3_selection_resources,
        P6_prefix_resource_projection_conformed=prefix.prefix_conformed,
        step3_started=step3_started,
        explicit_exclusions=P7_PUBLIC_EXCLUSIONS,
    )
    # Public-vocabulary validation and canonical serialization are schema
    # checks.  They are the only post-computation INVALID phase.
    P7_D0_FAILURE_PHASE[] = P7_D0_INVALID_FAILURE_PHASE
    p7_assert_public_vocabulary(raw)
    output = canonical_json(raw) * "\n"

    # Once the complete output string exists, writes and flushes are generation
    # I/O.  A failure here is INDETERMINATE and must never be called INVALID.
    P7_D0_FAILURE_PHASE[] = P7_D0_INDETERMINATE_FAILURE_PHASE
    write(stdout, output)
    flush(stdout)
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    try
        main_p7_d0()
    catch error_value
        if error_value isa OutOfMemoryError
            println(stderr, "P7_D0_HOST_FAILURE_OOM")
            exit(70)
        elseif error_value isa InterruptException
            println(stderr, "P7_D0_INDETERMINATE_INTERRUPT")
            exit(70)
        elseif P7_D0_FAILURE_PHASE[] === P7_D0_INVALID_FAILURE_PHASE
            println(stderr, "P7_D0_INVALID")
            exit(66)
        else
            println(stderr, "P7_D0_INDETERMINATE_GENERATION_FAILURE")
            exit(70)
        end
    end
end
