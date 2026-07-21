#!/usr/bin/env julia

# Non-authoritative P7 D2 schedule diagnostic.  The child writes only a fixed,
# constant-count event language to a dedicated inherited pipe.  No timestamp,
# scientific/resource counter or index, scientific value, or free text crosses
# that channel; `sequence` is the sole non-scientific protocol ordinal.

const P7_D2_PHASE_EVENTS = (
    "D2_RUNNER_STARTED",
    "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
    "D2_STATIC_SETUP_COMPLETED",
    "STEP1_ENGINE_STARTED",
    "STEP1_ENGINE_RETURNED",
    "STEP1_FINALIZER_STARTED",
    "STEP1_FINALIZER_RETURNED",
    "STEP1_DETERMINISTIC_CAP_TERMINAL",
    "STEP1_TO_STEP2_HANDOFF_COMPLETED",
    "STEP2_ENGINE_STARTED",
    "STEP2_ENGINE_RETURNED",
    "STEP2_FINALIZER_STARTED",
    "STEP2_FINALIZER_RETURNED",
    "STEP2_DETERMINISTIC_CAP_TERMINAL",
    "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED",
    "P6_PREFIX_RESOURCE_CONFORMANCE_FAILED_TERMINAL",
    "STEP2_TO_STEP3_HANDOFF_COMPLETED",
    "STEP3_ENGINE_STARTED",
    "STEP3_ENGINE_RETURNED",
    "STEP3_FINALIZER_STARTED",
    "STEP3_FINALIZER_RETURNED",
    "STEP3_DETERMINISTIC_CAP_TERMINAL",
    "D2_DIAGNOSTIC_SERIALIZATION_STARTED",
    "D2_DIAGNOSTIC_SERIALIZATION_RETURNED",
    "D2_DIAGNOSTIC_COMPLETED",
    "STEP3_SEGMENT_A_STARTED",
    "STEP3_SEGMENT_A_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_A_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_A_RETURNED",
    "STEP3_SEGMENT_B_STARTED",
    "STEP3_SEGMENT_B_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_B_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_B_RETURNED",
    "STEP3_SEGMENT_C_STARTED",
    "STEP3_SEGMENT_C_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_C_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_C_RETURNED",
    "STEP3_SEGMENT_D_STARTED",
    "STEP3_SEGMENT_D_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_D_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_D_RETURNED",
    "STEP3_SEGMENT_E_STARTED",
    "STEP3_SEGMENT_E_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_E_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_E_RETURNED",
    "STEP3_SEGMENT_F_STARTED",
    "STEP3_SEGMENT_F_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_F_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_F_RETURNED",
    "STEP3_SEGMENT_G_STARTED",
    "STEP3_SEGMENT_G_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_G_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_G_RETURNED",
    "STEP3_SEGMENT_H_STARTED",
    "STEP3_SEGMENT_H_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_H_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_H_RETURNED",
    "STEP3_SEGMENT_I_STARTED",
    "STEP3_SEGMENT_I_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_I_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_I_RETURNED",
)
const P7_D2_MARKER_SEGMENT_LABELS = (
    "A", "B", "C", "D", "E", "F", "G", "H", "I",
)
const P7_D2_MARKER_SEGMENT_GROUPS = (
    "H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1",
)
const P7_D2_MARKER_COMPOSITE_COUNTS = (64, 48, 64, 48, 64, 48, 64, 48, 64)
const P7_D2_MARKER_CHECKPOINT_1 = (22, 16, 22, 16, 22, 16, 22, 16, 22)
const P7_D2_MARKER_CHECKPOINT_2 = (43, 32, 43, 32, 43, 32, 43, 32, 43)
const P7_D2_PHASE_FD = Ref{Cint}(-1)
const P7_D2_PHASE_SEQUENCE = Ref(0)

length(P7_D2_PHASE_EVENTS) == 61 || error("invalid P7 D2 event count")

struct P7D2ScheduleTransportError <: Exception end

function p7_d2_write_atomic(payload::Vector{UInt8})
    length(payload) <= 256 || throw(P7D2ScheduleTransportError())
    fd = P7_D2_PHASE_FD[]
    fd >= 0 || throw(P7D2ScheduleTransportError())
    written = GC.@preserve payload ccall(
        :write, Base.Cssize_t, (Cint, Ptr{UInt8}, Csize_t),
        fd, pointer(payload), length(payload),
    )
    if written == -1 && Base.Libc.errno() == Base.Libc.EINTR
        written = GC.@preserve payload ccall(
            :write, Base.Cssize_t, (Cint, Ptr{UInt8}, Csize_t),
            fd, pointer(payload), length(payload),
        )
    end
    written == length(payload) || throw(P7D2ScheduleTransportError())
    return nothing
end

function p7_d2_emit(event::AbstractString)
    event in P7_D2_PHASE_EVENTS || error("unknown P7 D2 phase event")
    sequence = P7_D2_PHASE_SEQUENCE[]
    line = "{\"event\":\"$(event)\",\"sequence\":$(sequence)}\n"
    p7_d2_write_atomic(Vector{UInt8}(codeunits(line)))
    P7_D2_PHASE_SEQUENCE[] = sequence + 1
    return nothing
end

const P7_D2_IS_MAIN = abspath(PROGRAM_FILE) == abspath(@__FILE__)
if P7_D2_IS_MAIN
    try
        length(ARGS) == 9 || error("invalid P7 D2 argument count")
        phase_fd = parse(Int, ARGS[9])
        3 <= phase_fd <= typemax(Cint) || error("invalid P7 D2 phase fd")
        P7_D2_PHASE_FD[] = Cint(phase_fd)
        p7_d2_emit("D2_RUNNER_STARTED")
    catch error_value
        if error_value isa P7D2ScheduleTransportError
            println(stderr, "P7_D2_PHASE_TRANSPORT_FAILURE")
            exit(70)
        else
            println(stderr, "P7_D2_INVALID")
            exit(66)
        end
    end
end

# This exact source-pinned D0 driver imports the frozen P6/P4/P3/P2 chain and
# supplies every scientific kernel other than the source-normalized D2 copy
# below.  Its program guard is false when included here.  No prior diagnostic
# source or result artifact is included, opened, or staged by this driver.
include(joinpath(
    @__DIR__, "..", "majorana_certificate_p7_design_probe",
    "majorana_p7_step3_resource_probe.jl",
))

const P7_D2_FIXTURE_ID =
    "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D2-SCHEDULE-V1"
const P7_D2_DIRECT_PARENT =
    "29911a8ac46c068c550504f8b4a57d27a9441c0c"
const P7_D2_DIAGNOSTIC_MODE = "E768_MAX_LAZY37_STEP3_D2_SCHEDULE_V1"
const P7_D2_PHASE_PROTOCOL_CANONICAL_SHA256 =
    "b27caef5156aaae8946da2705c9a1956faa54e123aee341686449129c8da0e97"
const P7_D2_INVALID_FAILURE_PHASE = :INVALID
const P7_D2_INDETERMINATE_FAILURE_PHASE = :INDETERMINATE
const P7_D2_FAILURE_PHASE = Ref{Symbol}(P7_D2_INVALID_FAILURE_PHASE)

function validate_p7_d2_fixture(d2_fixture, d0_fixture)
    p7_require_exact_keys(d2_fixture, (
        "schema_version", "fixture_id", "required_direct_parent_commit",
        "scientific_authority", "certificate_eligible",
        "result_contract_eligible", "diagnostic_role", "D1_parent_custody",
        "frozen_candidate_identity", "frozen_execution_relation",
        "phase_event_protocol", "step3_schedule_marker_map",
        "scientific_kernel_byte_equivalence", "phase_channel_custody",
        "host_supervisor_caps", "runtime_custody", "observation_scope",
        "authority_exclusions",
    ), "P7 D2 fixture")
    d2_fixture["schema_version"] == 1 || error("P7 D2 schema drift")
    d2_fixture["fixture_id"] == P7_D2_FIXTURE_ID ||
        error("P7 D2 fixture identity drift")
    d2_fixture["required_direct_parent_commit"] == P7_D2_DIRECT_PARENT ||
        error("P7 D2 direct parent drift")
    d2_fixture["scientific_authority"] == "NONE" ||
        error("P7 D2 fixture claims scientific authority")
    d2_fixture["certificate_eligible"] == false ||
        error("P7 D2 fixture is certificate eligible")
    d2_fixture["result_contract_eligible"] == false ||
        error("P7 D2 fixture is result-contract eligible")

    expected_role = Dict{String,Any}(
        "diagnostic_probe_id" =>
            "P7-D2-E768-MAX-LAZY37-STEP3-SCHEDULE-V1",
        "classification" =>
            "P7_D1_RESULT_INFORMED_D2_RESULT_UNPINNED_SCIENTIFIC_BLIND",
        "purpose" =>
            "locate_the_static_schedule_segment_reached_inside_the_frozen_step3_adaptive_engine_under_the_unchanged_host_admission",
        "one_fresh_process_only" => true,
        "resource_and_schedule_timing_diagnostic_only" => true,
        "D2_establishes_future_S0_admission" => false,
        "D2_may_not_change_the_candidate_algorithm_caps_host_admission_or_fallback" =>
            true,
    )
    d2_fixture["diagnostic_role"] == expected_role ||
        error("P7 D2 diagnostic role drift")

    expected_parent = Dict{String,Any}(
        "result_commit_sha" => P7_D2_DIRECT_PARENT,
        "report_relative_path" =>
            "majorana_certificate_p7_d1_phase_probe_report.json",
        "report_sha256" =>
            "9d37609c51f9149baf347fbf801338cc0abe7c7323c187fe71a4932099f8f713",
        "report_type" =>
            "majorana_p7_step3_e768_max_lazy37_phase_report_d1_v1",
        "scientific_authority" => "NONE",
        "certificate_eligible" => false,
        "result_contract_eligible" => false,
        "phase_trace_status" => "LEGAL_PREFIX_INTERRUPTED",
        "P6_prefix_resource_conformance_passed_marker_reached" => true,
        "step3_engine_started_marker_reached" => true,
        "step3_engine_returned_marker_reached" => false,
        "step3_finalizer_started_marker_reached" => false,
        "step3_finalizer_returned_marker_reached" => false,
        "resource_witness_is_null" => true,
        "future_S0_admission_status" =>
            "NOT_ESTABLISHED_BY_D1_PHASE_DIAGNOSTIC",
        "allowed_result_informed_facts_are_exhaustive" => true,
    )
    d2_fixture["D1_parent_custody"] == expected_parent ||
        error("P7 D2 parent custody drift")

    identity = d2_fixture["frozen_candidate_identity"]
    p7_require_exact_keys(identity, (
        "candidate_id", "scientific_probe_mode", "D2_diagnostic_mode",
        "algorithm_id", "D2_does_not_define_a_new_scientific_candidate",
    ), "P7 D2 candidate identity")
    identity["candidate_id"] == P7_D0_CANDIDATE_ID ||
        error("P7 D2 candidate identity drift")
    identity["scientific_probe_mode"] == P7_D0_PROBE_MODE ||
        error("P7 D2 scientific mode drift")
    identity["D2_diagnostic_mode"] == P7_D2_DIAGNOSTIC_MODE ||
        error("P7 D2 diagnostic mode drift")
    identity["algorithm_id"] == P7_D0_ALGORITHM_ID ||
        error("P7 D2 algorithm identity drift")
    identity["D2_does_not_define_a_new_scientific_candidate"] == true ||
        error("P7 D2 defines a new scientific candidate")

    expected_relation = Dict{String,Any}(
        "execution_chain" =>
            "fresh_O0_then_P3_2^-34_step1_then_P6_E768_MAX_LAZY37_step2_then_live_deepcopy_then_E768_MAX_LAZY37_step3",
        "all_three_steps_execute_in_one_process" => true,
        "checkpoint_serialization_or_cross_process_resume_forbidden" => true,
        "D2_includes_the_exact_source_pinned_D0_driver" => true,
        "D2_reuses_the_frozen_P3_and_P6_scientific_semantics" => true,
        "D2_step3_engine_is_a_source_pinned_copy_with_only_four_removable_marker_blocks" =>
            true,
        "D2_adds_only_constant_count_static_schedule_marker_emissions" => true,
        "constituent_boundary_selection_callback_and_scientific_hot_loop_instrumentation_forbidden" =>
            true,
        "D2_marker_IO_changes_the_runtime_path_and_therefore_has_no_S0_admission_authority" =>
            true,
    )
    d2_fixture["frozen_execution_relation"] == expected_relation ||
        error("P7 D2 frozen execution relation drift")

    protocol = d2_fixture["phase_event_protocol"]
    canonical_sha256(protocol) == P7_D2_PHASE_PROTOCOL_CANONICAL_SHA256 ||
        error("P7 D2 phase protocol semantic drift")
    protocol["wire_record_exact_fields"] == Any["event", "sequence"] ||
        error("P7 D2 wire schema drift")
    protocol["sequence_origin"] == 0 || error("P7 D2 sequence drift")
    protocol["maximum_event_count"] == 57 ||
        error("P7 D2 event-count cap drift")
    protocol["maximum_successful_trace_event_count"] == 57 ||
        error("P7 D2 successful event-count cap drift")
    protocol["maximum_line_bytes_including_newline"] == 256 ||
        error("P7 D2 line cap drift")
    protocol["maximum_total_channel_bytes"] == 8192 ||
        error("P7 D2 channel cap drift")
    protocol["allowed_events"] == Any[P7_D2_PHASE_EVENTS...] ||
        error("P7 D2 event allowlist drift")
    protocol["step3_internal_event_sequence"] ==
        Any[P7_D2_PHASE_EVENTS[26:61]...] ||
        error("P7 D2 internal event sequence drift")

    marker_map = d2_fixture["step3_schedule_marker_map"]
    expected_segments = Any[
        Dict{String,Any}(
            "segment" => P7_D2_MARKER_SEGMENT_LABELS[index],
            "schedule_position" => index - 1,
            "frozen_group" => P7_D2_MARKER_SEGMENT_GROUPS[index],
            "frozen_composite_count" =>
                P7_D2_MARKER_COMPOSITE_COUNTS[index],
            "checkpoint_1_completed_composites" =>
                P7_D2_MARKER_CHECKPOINT_1[index],
            "checkpoint_2_completed_composites" =>
                P7_D2_MARKER_CHECKPOINT_2[index],
        ) for index in eachindex(P7_D2_MARKER_SEGMENT_LABELS)
    ]
    expected_marker_map = Dict{String,Any}(
        "schema_version" => 1,
        "segment_order" => Any[P7_D2_MARKER_SEGMENT_LABELS...],
        "schedule_source" => "frozen_P2_build_schedule_returned_stages",
        "markers_are_static_schedule_progress_not_scientific_state" => true,
        "started_is_emitted_before_the_first_composite_of_the_segment" => true,
        "checkpoints_are_emitted_immediately_after_the_frozen_completed_composite_ordinal" =>
            true,
        "returned_is_emitted_after_the_stage_record_is_pushed_and_the_frozen_composite_count_is_checked" =>
            true,
        "segments" => expected_segments,
        "frozen_total_segment_count" => 9,
        "frozen_total_composite_count" => 512,
        "maximum_internal_marker_count" => 36,
        "marker_emission_reads_only_the_static_segment_position_and_completed_composite_ordinal" =>
            true,
        "marker_emission_must_not_read_or_branch_on_scientific_state_counts_masks_coefficients_ticks_budgets_drop_membership_or_digests" =>
            true,
    )
    marker_map == expected_marker_map || error("P7 D2 marker map drift")

    expected_kernel_custody = Dict{String,Any}(
        "frozen_P6_runner_relative_path" =>
            "majorana_certificate_p6/majorana_p6_runner.jl",
        "frozen_P6_runner_sha256" => P7_P6_RUNNER_SHA256,
        "frozen_execute_p6_step2_slice_line_start_inclusive" => 814,
        "frozen_execute_p6_step2_slice_line_end_inclusive" => 1269,
        "frozen_execute_p6_step2_slice_sha256" =>
            "a0a7f956540c602ea3f33424eee0b89189e35eb3f7a12941e556143576693f25",
        "frozen_schedule_source_relative_path" =>
            "majorana_certificate_p2/majorana_p2_runner.jl",
        "frozen_schedule_source_sha256" =>
            "03edd9640bc3d83a61ea0c9c7d9e93af3fc683972c517af4a7691e21359e25ed",
        "normalization_contract" => Dict{String,Any}(
            "D2_function_name" => "execute_p6_step2_d2",
            "frozen_function_name" => "execute_p6_step2",
            "rename_D2_function_to_frozen_function_name_before_comparison" =>
                true,
            "remove_exactly_four_lexically_delimited_D2_marker_blocks_before_comparison" =>
                true,
            "normalized_D2_function_bytes_must_equal_the_frozen_P6_function_slice_bytes" =>
                true,
            "source_or_AST_transform_at_runtime_is_forbidden" => true,
        ),
        "four_permitted_marker_blocks" => Any[
            "marker_local_initialization_immediately_before_the_frozen_try",
            "segment_started_logic_at_the_frozen_stage_loop_head",
            "checkpoint_logic_immediately_after_each_frozen_composite_completion",
            "segment_returned_logic_immediately_after_the_frozen_stage_record_push",
        ],
        "all_nonmarker_kernel_bytes_and_scientific_control_flow_are_frozen" =>
            true,
        "marker_blocks_may_only_emit_the_frozen_protocol_names_and_validate_the_static_marker_map" =>
            true,
    )
    d2_fixture["scientific_kernel_byte_equivalence"] ==
        expected_kernel_custody || error("P7 D2 kernel custody drift")

    d2_fixture["host_supervisor_caps"] == d0_fixture["host_supervisor_caps"] ||
        error("P7 D2 host admission differs from D0")
    d2_fixture["runtime_custody"] == d0_fixture["runtime_custody"] ||
        error("P7 D2 runtime custody differs from D0")
    d2_fixture["phase_channel_custody"]["stdout_is_strictly_empty"] == true ||
        error("P7 D2 stdout discipline drift")
    d2_fixture["phase_channel_custody"][
        "child_emits_no_timestamps_scientific_counts_scientific_indices_state_or_free_text_except_protocol_sequence"
    ] == true || error("P7 D2 channel scientific-blindness drift")
    d2_fixture["observation_scope"]["resource_witness"] === nothing ||
        error("P7 D2 fixture carries a resource witness")
    d2_fixture["observation_scope"][
        "completed_D2_does_not_establish_future_S0_admission"
    ] == true || error("P7 D2 observation authority drift")
    length(d2_fixture["authority_exclusions"]) == 8 ||
        error("P7 D2 authority exclusions drift")
    return d2_fixture
end

function execute_p6_step2_d2(stages, fixture, observable, trig_lookup, threshold::Float64)
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

    # P7_D2_SCHEDULE_MARKER_BLOCK_1_BEGIN
    d2_marker_segment_ordinal = 0
    d2_marker_composite_ordinal = 0
    d2_marker_label = ""
    # P7_D2_SCHEDULE_MARKER_BLOCK_1_END
    try
        for stage in stages
            # P7_D2_SCHEDULE_MARKER_BLOCK_2_BEGIN
            d2_marker_segment_ordinal += 1
            d2_marker_composite_ordinal = 0
            d2_marker_label = P7_D2_MARKER_SEGMENT_LABELS[
                d2_marker_segment_ordinal
            ]
            p7_d2_emit("STEP3_SEGMENT_$(d2_marker_label)_STARTED")
            # P7_D2_SCHEDULE_MARKER_BLOCK_2_END
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
                # P7_D2_SCHEDULE_MARKER_BLOCK_3_BEGIN
                d2_marker_composite_ordinal += 1
                if d2_marker_composite_ordinal == P7_D2_MARKER_CHECKPOINT_1[
                    d2_marker_segment_ordinal
                ]
                    p7_d2_emit(
                        "STEP3_SEGMENT_$(d2_marker_label)_CHECKPOINT_1_REACHED",
                    )
                elseif d2_marker_composite_ordinal == P7_D2_MARKER_CHECKPOINT_2[
                    d2_marker_segment_ordinal
                ]
                    p7_d2_emit(
                        "STEP3_SEGMENT_$(d2_marker_label)_CHECKPOINT_2_REACHED",
                    )
                end
                # P7_D2_SCHEDULE_MARKER_BLOCK_3_END
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
            # P7_D2_SCHEDULE_MARKER_BLOCK_4_BEGIN
            d2_marker_composite_ordinal == P7_D2_MARKER_COMPOSITE_COUNTS[
                d2_marker_segment_ordinal
            ] || error("P7 D2 marker composite-count drift")
            p7_d2_emit("STEP3_SEGMENT_$(d2_marker_label)_RETURNED")
            # P7_D2_SCHEDULE_MARKER_BLOCK_4_END
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

function p7_d2_execute_adaptive_step(
    stages, execution_fixture, input_sum, trig_lookup, engine_caps,
    selection_caps, mapped_step_index::Int; copy_completed_output::Bool,
)
    mapped_step_index in (2, 3) || error("invalid P7 D2 adaptive step")
    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P7 D2 adaptive engine caps are already active")
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P7 D2 adaptive selection caps are already active")
    execution = nothing
    final_state = nothing
    cap_event = nothing
    selection_resources = nothing
    completed_output = nothing
    prefix = mapped_step_index == 2 ? "STEP2" : "STEP3"
    try
        P4_ACTIVE_STEP2_CAPS[] = engine_caps
        p6_reset_selection_state!(selection_caps)
        p7_d2_emit("$(prefix)_ENGINE_STARTED")
        if mapped_step_index == 2
            execution = execute_p6_step2(
                stages, execution_fixture, input_sum, trig_lookup,
                P6_K37_THRESHOLD,
            )
        else
            execution = execute_p6_step2_d2(
                stages, execution_fixture, input_sum, trig_lookup,
                P6_K37_THRESHOLD,
            )
        end
        p7_d2_emit("$(prefix)_ENGINE_RETURNED")
        final_cap = execution.cap_event === nothing ?
            precheck_p4_final_cap(execution, engine_caps) : nothing
        if execution.cap_event === nothing && final_cap === nothing
            execution.completed_boundaries == P6_BOUNDARY_COUNT ||
                error("P7 D2 adaptive execution has wrong boundary count")
            P6_SELECTION_RESOURCES[].completed_selection_boundary_count ==
                P6_BOUNDARY_COUNT ||
                error("P7 D2 adaptive selection boundary count mismatch")
            p7_d2_emit("$(prefix)_FINALIZER_STARTED")
            final_state, postcheck_cap =
                finalize_p3_state!(execution, execution_fixture)
            p7_d2_emit("$(prefix)_FINALIZER_RETURNED")
            postcheck_cap === nothing ||
                error("P7 D2 final cap escaped its precheck")
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
                error("P7 D2 adaptive live-output term count drift")
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

function p7_d2_execute_prefix(
    p7_fixture, p6_fixture, p3_fixture, stages, observable, trig_lookup,
)
    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P7 D2 prefix caps leaked into step 1")
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P7 D2 selection caps leaked into step 1")
    P6_SELECTION_RESOURCES[] = P6SelectionResourceCounters()

    p7_d2_emit("STEP1_ENGINE_STARTED")
    execution1 = execute_p3(stages, p3_fixture, observable, trig_lookup)
    p7_d2_emit("STEP1_ENGINE_RETURNED")
    p7_d2_emit("STEP1_FINALIZER_STARTED")
    final1, final_cap1 = finalize_p3_state!(execution1, p3_fixture)
    p7_d2_emit("STEP1_FINALIZER_RETURNED")
    cap1 = execution1.cap_event === nothing ? final_cap1 : execution1.cap_event
    execution1.cap_event !== nothing && final_cap1 !== nothing &&
        error("P7 D2 step 1 produced two cap events")
    step1 = p7_resource_summary(execution1, cap1, final1, 1)
    if cap1 !== nothing
        p7_d2_emit("STEP1_DETERMINISTIC_CAP_TERMINAL")
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
        error("P7 D2 step1-to-step2 term-count drift")
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
    p7_d2_emit("STEP1_TO_STEP2_HANDOFF_COMPLETED")

    step2_fixture = p6_step2_execution_fixture(p6_fixture, p3_fixture)
    step2_run = p7_d2_execute_adaptive_step(
        stages, step2_fixture, step2_input, trig_lookup,
        p6_fixture["deterministic_resource_caps"],
        p6_fixture["deterministic_selection_caps"], 2;
        copy_completed_output=true,
    )
    step2 = step2_run.summary
    step2_selection_resources = step2_run.selection_resources
    if step2.cap_event !== nothing
        p7_d2_emit("STEP2_DETERMINISTIC_CAP_TERMINAL")
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
    p7_d2_emit(prefix_conformed ?
        "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED" :
        "P6_PREFIX_RESOURCE_CONFORMANCE_FAILED_TERMINAL")
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

function main_p7_d2()
    P7_D2_FAILURE_PHASE[] = P7_D2_INVALID_FAILURE_PHASE
    length(ARGS) == 9 || error(
        "usage: schedule probe D2_FIXTURE D0_FIXTURE P6 P5 P4 P3 P2 MODE FD",
    )
    d2_fixture_path = abspath(ARGS[1])
    d0_fixture_path = abspath(ARGS[2])
    p6_fixture_path = abspath(ARGS[3])
    p5_fixture_path = abspath(ARGS[4])
    p4_fixture_path = abspath(ARGS[5])
    p3_fixture_path = abspath(ARGS[6])
    p2_fixture_path = abspath(ARGS[7])
    mode = String(ARGS[8])
    mode == P7_D2_DIAGNOSTIC_MODE || error("unexpected P7 D2 mode")

    d2_fixture = JSON.parsefile(d2_fixture_path)
    d0_fixture = validate_p7_d0_fixture(JSON.parsefile(d0_fixture_path))
    validate_p7_d2_fixture(d2_fixture, d0_fixture)
    p6_fixture = JSON.parsefile(p6_fixture_path)
    p5_fixture = JSON.parsefile(p5_fixture_path)
    p4_fixture = JSON.parsefile(p4_fixture_path)
    p3_fixture = JSON.parsefile(p3_fixture_path)
    p2_fixture = JSON.parsefile(p2_fixture_path)
    p7_validate_parent_custody(
        d0_fixture, p6_fixture, p5_fixture, p4_fixture, p3_fixture, p2_fixture,
        p6_fixture_path, p5_fixture_path, p4_fixture_path, p3_fixture_path,
        p2_fixture_path,
    )
    runtime_custody = p7_validate_runtime(d0_fixture)
    runtime_custody == d2_fixture["runtime_custody"] ||
        error("P7 D2 runtime witness drift")
    p7_d2_emit("D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED")

    P7_D2_FAILURE_PHASE[] = P7_D2_INDETERMINATE_FAILURE_PHASE
    maximum_bits = Int(p3_fixture["outward_arithmetic"][
        "maximum_BigInt_bit_length"
    ])
    maximum_bits == 2048 || error("P7 D2 inherited BigInt cap drift")
    trig_lookup, trig_table = build_trig_table(p3_fixture, maximum_bits)
    length(trig_table) <= 6 || error("P7 D2 trig table exceeds its cap")
    stages, _schedule = build_schedule()
    observable, _initial = initial_observable()
    p7_d2_emit("D2_STATIC_SETUP_COMPLETED")

    prefix = p7_d2_execute_prefix(
        d0_fixture, p6_fixture, p3_fixture, stages, observable, trig_lookup,
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
            error("P7 D2 step2-to-step3 term-count drift")
        step2_to_step3_link = (
            same_process=true,
            checkpoint_or_serialized_state_used=false,
            previous_step_final_term_count=
                prefix.step2.final_retained_term_count,
            next_step_input_term_count=step3_input_count,
        )
        p7_d2_emit("STEP2_TO_STEP3_HANDOFF_COMPLETED")
        step3_caps = p7_step3_engine_caps(
            d0_fixture["deterministic_step3_probe_caps"],
        )
        step3_selection_caps =
            d0_fixture["deterministic_step3_selection_probe_caps"]
        step3_fixture = p7_step3_execution_fixture(d0_fixture, p3_fixture)
        step3_run = p7_d2_execute_adaptive_step(
            stages, step3_fixture, step3_input, trig_lookup, step3_caps,
            step3_selection_caps, 3;
            copy_completed_output=false,
        )
        step3 = step3_run.summary
        step3_selection_resources = step3_run.selection_resources
        if step3.cap_event !== nothing
            p7_d2_emit("STEP3_DETERMINISTIC_CAP_TERMINAL")
        end
    end

    # Preserve D0's aggregate-public-object construction and canonicalization
    # workload, but deliberately discard the bytes: D2 stdout stays empty.
    p7_d2_emit("D2_DIAGNOSTIC_SERIALIZATION_STARTED")
    raw = (
        schema_version=1,
        probe_type=P7_D0_PROBE_TYPE,
        fixture_id=P7_D0_FIXTURE_ID,
        fixture_sha256=file_sha256(d0_fixture_path),
        fixture_canonical_sha256=canonical_sha256(d0_fixture),
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
    P7_D2_FAILURE_PHASE[] = P7_D2_INVALID_FAILURE_PHASE
    p7_assert_public_vocabulary(raw)
    discarded_output = canonical_json(raw) * "\n"
    isempty(discarded_output) && error("P7 D2 serialization was empty")
    discarded_output = nothing
    p7_d2_emit("D2_DIAGNOSTIC_SERIALIZATION_RETURNED")
    P7_D2_FAILURE_PHASE[] = P7_D2_INDETERMINATE_FAILURE_PHASE
    p7_d2_emit("D2_DIAGNOSTIC_COMPLETED")
    return nothing
end

if P7_D2_IS_MAIN
    try
        main_p7_d2()
    catch error_value
        if error_value isa P7D2ScheduleTransportError
            println(stderr, "P7_D2_PHASE_TRANSPORT_FAILURE")
            exit(70)
        elseif error_value isa OutOfMemoryError
            println(stderr, "P7_D2_HOST_FAILURE_OOM")
            exit(70)
        elseif error_value isa InterruptException
            println(stderr, "P7_D2_INDETERMINATE_INTERRUPT")
            exit(70)
        elseif P7_D2_FAILURE_PHASE[] === P7_D2_INVALID_FAILURE_PHASE
            println(stderr, "P7_D2_INVALID")
            exit(66)
        else
            println(stderr, "P7_D2_INDETERMINATE_GENERATION_FAILURE")
            exit(70)
        end
    end
end
