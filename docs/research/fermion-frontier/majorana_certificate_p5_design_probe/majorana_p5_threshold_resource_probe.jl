#!/usr/bin/env julia

# Non-authoritative P5 D0 resource probe.  The Python harness stages an exact
# copy of the P4 runner closure and applies one fail-closed instrumentation
# patch to the staged P3 threshold callback: step 1 remains at the frozen P3
# threshold, while step 2 reads P5_ACTIVE_STEP_THRESHOLD[].  This driver emits
# resource facts only.  It is not a P4/P5 raw witness and cannot be materialized
# as a certificate.
include(joinpath(@__DIR__, "..", "majorana_certificate_p4", "majorana_p4_runner.jl"))

const P5_D0_PROBE_TYPE =
    "majorana_p5_conditional_step2_threshold_resource_probe_d0_v1"
const P5_D0_ALLOWED_STEP2_EXPONENTS = (34, 36, 37)

function p5_d0_resource_summary(execution, cap_event, final_state)
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
        cap_event=cap_event,
    )
end

function p5_d0_source_hashes()
    base = dirname(@__DIR__)
    return (
        p2_runner_sha256=file_sha256(joinpath(
            base, "majorana_certificate_p2", "majorana_p2_runner.jl",
        )),
        instrumented_p3_runner_sha256=file_sha256(joinpath(
            base, "majorana_certificate_p3", "majorana_p3_runner.jl",
        )),
        p4_runner_sha256=file_sha256(joinpath(
            base, "majorana_certificate_p4", "majorana_p4_runner.jl",
        )),
        probe_driver_sha256=file_sha256(@__FILE__),
    )
end

function main_p5_d0()
    length(ARGS) == 4 || error(
        "usage: majorana_p5_threshold_resource_probe.jl " *
        "P4_FIXTURE.json P3_FIXTURE.json P2_FIXTURE.json STEP2_EXPONENT",
    )
    p4_fixture_path = abspath(ARGS[1])
    p3_fixture_path = abspath(ARGS[2])
    p2_fixture_path = abspath(ARGS[3])
    step2_exponent = parse(Int, ARGS[4])
    step2_exponent in P5_D0_ALLOWED_STEP2_EXPONENTS ||
        error("unexpected P5 D0 step-2 threshold exponent")

    # Validate the unmodified P4/P3/P2 semantic inputs before the probe-only
    # threshold selector is changed.  EPSILON itself remains the frozen 2^-34.
    p4_fixture = validate_p4_fixture(JSON.parsefile(p4_fixture_path))
    p3_fixture = JSON.parsefile(p3_fixture_path)
    p2_fixture = JSON.parsefile(p2_fixture_path)
    validate_p4_parent_fixtures(
        p4_fixture, p3_fixture, p2_fixture, p3_fixture_path, p2_fixture_path,
    )
    isdefined(@__MODULE__, :P5_ACTIVE_STEP_THRESHOLD) ||
        error("P5 D0 staged P3 instrumentation selector is missing")
    P5_ACTIVE_STEP_THRESHOLD[] == EPSILON ||
        error("P5 D0 threshold selector did not start at frozen P3 threshold")

    Threads.nthreads() == 1 || error("P5 D0 requires exactly one Julia thread")
    rounding(Float64) == RoundNearest ||
        error("P5 D0 requires Float64 round-to-nearest-ties-to-even")
    reinterpret(UInt64, EPSILON) == 0x3dd0000000000000 ||
        error("P5 D0 frozen step-1 threshold bits drift")
    step2_threshold = ldexp(1.0, -step2_exponent)
    expected_step2_bits = step2_exponent == 34 ? 0x3dd0000000000000 :
        step2_exponent == 36 ? 0x3db0000000000000 : 0x3da0000000000000
    reinterpret(UInt64, step2_threshold) == expected_step2_bits ||
        error("P5 D0 step-2 threshold bits drift")

    maximum_bits = Int(p3_fixture["outward_arithmetic"]["maximum_BigInt_bit_length"])
    trig_lookup, _trig_table = build_trig_table(p3_fixture, maximum_bits)
    stages, schedule = build_schedule()
    observable, initial = initial_observable()

    P5_ACTIVE_STEP_THRESHOLD[] = EPSILON
    execution1 = execute_p3(stages, p3_fixture, observable, trig_lookup)
    final1, final_cap1 = finalize_p3_state!(execution1, p3_fixture)
    cap1 = execution1.cap_event === nothing ? final_cap1 : execution1.cap_event
    execution1.cap_event !== nothing && final_cap1 !== nothing &&
        error("P5 D0 step 1 produced two deterministic cap events")
    step1_summary = p5_d0_resource_summary(execution1, cap1, final1)

    step2_summary = nothing
    step_link = nothing
    if cap1 === nothing
        live_step1_sum = MajoranaPropagation.PropagationBase.mainsum(execution1.cache)
        step2_input_sum = deepcopy(live_step1_sum)
        step2_input_count = length(step2_input_sum.Majoranas)
        step2_input_count == final1.retained_term_count ||
            error("P5 D0 step-link term count mismatch")
        GC.gc()

        step2_fixture = translated_step2_execution_fixture(p4_fixture, p3_fixture)
        step2_caps = p4_fixture["deterministic_resource_caps"]
        execution2 = nothing
        final2 = nothing
        cap2 = nothing
        P4_ACTIVE_STEP2_CAPS[] = step2_caps
        P5_ACTIVE_STEP_THRESHOLD[] = step2_threshold
        try
            execution2 = execute_p3(stages, step2_fixture, step2_input_sum, trig_lookup)
            final_cap2 = execution2.cap_event === nothing ?
                precheck_p4_final_cap(execution2, step2_caps) : nothing
            if execution2.cap_event === nothing && final_cap2 === nothing
                final2, postcheck_cap2 = finalize_p3_state!(execution2, step2_fixture)
                postcheck_cap2 === nothing ||
                    error("P5 D0 step-2 final cap escaped the precheck")
            end
            cap2 = execution2.cap_event === nothing ? final_cap2 : execution2.cap_event
        finally
            P5_ACTIVE_STEP_THRESHOLD[] = EPSILON
            P4_ACTIVE_STEP2_CAPS[] = nothing
        end
        step2_summary = p5_d0_resource_summary(execution2, cap2, final2)
        step_link = (
            same_process=true,
            checkpoint_or_serialized_state_used=false,
            step1_final_term_count=final1.retained_term_count,
            step2_input_term_count=step2_input_count,
        )
    end

    raw = (
        schema_version=1,
        probe_type=P5_D0_PROBE_TYPE,
        scientific_authority="NONE",
        certificate_eligible=false,
        result_contract_eligible=false,
        resource_observations_only=true,
        P4_result_or_P3_numeric_error_bound_read_by_runner=false,
        base_fixture_identity=(
            p4_fixture_id=String(p4_fixture["fixture_id"]),
            p4_fixture_sha256=file_sha256(p4_fixture_path),
            p3_fixture_id=String(p3_fixture["fixture_id"]),
            p3_fixture_sha256=file_sha256(p3_fixture_path),
            p2_fixture_id=String(p2_fixture["fixture_id"]),
            p2_fixture_sha256=file_sha256(p2_fixture_path),
        ),
        source_hashes=p5_d0_source_hashes(),
        workload=(
            linear_size=L,
            step_count=2,
            composite_count_per_step=schedule.composite_count,
            constituent_count_per_step=schedule.constituent_count,
            truncation_boundary_count_per_step=schedule.truncation_boundary_count,
            initial_nonzero_term_count=initial.nonzero_term_count,
        ),
        candidate=(
            identity="step1_fixed_2^-34_then_step2_fixed_2^-$(step2_exponent)",
            control_candidate=step2_exponent == 34,
            step1_threshold_exponent=34,
            step1_threshold_rational="1/17179869184",
            step1_threshold_Float64_bits_hex=float_bits_hex(EPSILON),
            step2_threshold_exponent=step2_exponent,
            step2_threshold_rational=
                "1/$(string(BigInt(1) << step2_exponent))",
            step2_threshold_Float64_bits_hex=float_bits_hex(step2_threshold),
            strict_drop_rule="abs_binary64_coefficient_strictly_less_than_threshold",
            step1_path_is_not_rethresholded=true,
        ),
        step1=step1_summary,
        step2=step2_summary,
        step_link=step_link,
        explicit_exclusions=(
            "product_merge_or_drop_defect_ticks",
            "allocation_comparison_or_candidate_ranking",
            "term_or_drop_stream_digests",
            "Neel_center_expectation_or_interval",
            "scientific_witness_result_certificate_or_READY_authority",
        ),
    )
    print(canonical_json(raw))
    print('\n')
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main_p5_d0()
end
