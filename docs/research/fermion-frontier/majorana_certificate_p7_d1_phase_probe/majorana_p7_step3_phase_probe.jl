#!/usr/bin/env julia

# Non-authoritative P7 D1 phase diagnostic.  The child writes only a fixed,
# constant-count event language to a dedicated inherited pipe.  No timestamp,
# scientific/resource counter or index, scientific value, or free text crosses
# that channel; `sequence` is the sole non-scientific protocol ordinal.

const P7_D1_PHASE_EVENTS = (
    "D1_RUNNER_STARTED",
    "D1_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
    "D1_STATIC_SETUP_COMPLETED",
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
    "D1_DIAGNOSTIC_SERIALIZATION_STARTED",
    "D1_DIAGNOSTIC_SERIALIZATION_RETURNED",
    "D1_DIAGNOSTIC_COMPLETED",
)
const P7_D1_PHASE_FD = Ref{Cint}(-1)
const P7_D1_PHASE_SEQUENCE = Ref(0)

struct P7D1PhaseTransportError <: Exception end

function p7_d1_write_atomic(payload::Vector{UInt8})
    length(payload) <= 256 || throw(P7D1PhaseTransportError())
    fd = P7_D1_PHASE_FD[]
    fd >= 0 || throw(P7D1PhaseTransportError())
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
    written == length(payload) || throw(P7D1PhaseTransportError())
    return nothing
end

function p7_d1_emit(event::AbstractString)
    event in P7_D1_PHASE_EVENTS || error("unknown P7 D1 phase event")
    sequence = P7_D1_PHASE_SEQUENCE[]
    line = "{\"event\":\"$(event)\",\"sequence\":$(sequence)}\n"
    p7_d1_write_atomic(Vector{UInt8}(codeunits(line)))
    P7_D1_PHASE_SEQUENCE[] = sequence + 1
    return nothing
end

const P7_D1_IS_MAIN = abspath(PROGRAM_FILE) == abspath(@__FILE__)
if P7_D1_IS_MAIN
    try
        length(ARGS) == 9 || error("invalid P7 D1 argument count")
        phase_fd = parse(Int, ARGS[9])
        0 <= phase_fd <= typemax(Cint) || error("invalid P7 D1 phase fd")
        P7_D1_PHASE_FD[] = Cint(phase_fd)
        p7_d1_emit("D1_RUNNER_STARTED")
    catch error_value
        if error_value isa P7D1PhaseTransportError
            println(stderr, "P7_D1_PHASE_TRANSPORT_FAILURE")
            exit(70)
        else
            println(stderr, "P7_D1_INVALID")
            exit(66)
        end
    end
end

# This exact source-pinned D0 driver imports the frozen P6/P4/P3/P2 chain and
# supplies all scientific kernels and validation helpers.  Its program guard
# is false when included here.
include(joinpath(
    @__DIR__, "..", "majorana_certificate_p7_design_probe",
    "majorana_p7_step3_resource_probe.jl",
))

const P7_D1_FIXTURE_ID =
    "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D1-PHASE-V1"
const P7_D1_FIXTURE_CANONICAL_SHA256 =
    "7b1f52866315cb241dbb24263d95fc0d61fc3fda83b2c05720bc89d2ca35c36d"
const P7_D1_DIRECT_PARENT =
    "4ebed6b651e3c9605f84939d6a9efff8281bc38b"
const P7_D1_DIAGNOSTIC_MODE = "E768_MAX_LAZY37_STEP3_D1_PHASE_V1"
const P7_D1_INVALID_FAILURE_PHASE = :INVALID
const P7_D1_INDETERMINATE_FAILURE_PHASE = :INDETERMINATE
const P7_D1_FAILURE_PHASE = Ref{Symbol}(P7_D1_INVALID_FAILURE_PHASE)

function validate_p7_d1_fixture(d1_fixture, d0_fixture)
    canonical_sha256(d1_fixture) == P7_D1_FIXTURE_CANONICAL_SHA256 ||
        error("P7 D1 fixture differs from the frozen semantic object")
    p7_require_exact_keys(d1_fixture, (
        "schema_version", "fixture_id", "required_direct_parent_commit",
        "scientific_authority", "certificate_eligible",
        "result_contract_eligible", "diagnostic_role",
        "D0_parent_custody", "frozen_candidate_identity",
        "frozen_execution_relation", "phase_event_protocol",
        "phase_channel_custody", "host_supervisor_caps", "runtime_custody",
        "observation_scope", "authority_exclusions",
    ), "P7 D1 fixture")
    d1_fixture["schema_version"] == 1 || error("P7 D1 schema drift")
    d1_fixture["fixture_id"] == P7_D1_FIXTURE_ID ||
        error("P7 D1 fixture identity drift")
    d1_fixture["required_direct_parent_commit"] == P7_D1_DIRECT_PARENT ||
        error("P7 D1 direct parent drift")
    d1_fixture["scientific_authority"] == "NONE" ||
        error("P7 D1 fixture claims scientific authority")
    d1_fixture["certificate_eligible"] == false ||
        error("P7 D1 fixture is certificate eligible")
    d1_fixture["result_contract_eligible"] == false ||
        error("P7 D1 fixture is result-contract eligible")

    parent = d1_fixture["D0_parent_custody"]
    parent["result_commit_sha"] == P7_D1_DIRECT_PARENT ||
        error("P7 D1 parent commit custody drift")
    parent["report_sha256"] ==
        "4bf4be7f77fd499ffc9bd975f07353fd14ee7403cd6fc7759974dda37f8588cf" ||
        error("P7 D1 parent report custody drift")
    parent["terminal_status"] ==
        "INDETERMINATE_HOST_OR_RUNTIME_FAILURE" ||
        error("P7 D1 parent terminal fact drift")
    parent["resource_witness_is_null"] == true ||
        error("P7 D1 parent witness fact drift")
    parent["future_S0_admission_status"] ==
        "NOT_ESTABLISHED_INDETERMINATE_HOST_OR_RUNTIME_FAILURE" ||
        error("P7 D1 parent admission fact drift")

    identity = d1_fixture["frozen_candidate_identity"]
    identity["candidate_id"] == P7_D0_CANDIDATE_ID ||
        error("P7 D1 candidate identity drift")
    identity["scientific_probe_mode"] == P7_D0_PROBE_MODE ||
        error("P7 D1 scientific mode drift")
    identity["D1_diagnostic_mode"] == P7_D1_DIAGNOSTIC_MODE ||
        error("P7 D1 diagnostic mode drift")
    identity["algorithm_id"] == P7_D0_ALGORITHM_ID ||
        error("P7 D1 algorithm identity drift")
    identity["D1_does_not_define_a_new_scientific_candidate"] == true ||
        error("P7 D1 defines a new scientific candidate")

    protocol = d1_fixture["phase_event_protocol"]
    protocol["wire_record_exact_fields"] == Any["event", "sequence"] ||
        error("P7 D1 wire schema drift")
    protocol["sequence_origin"] == 0 || error("P7 D1 sequence drift")
    protocol["maximum_event_count"] == 32 ||
        error("P7 D1 event-count cap drift")
    protocol["maximum_line_bytes_including_newline"] == 256 ||
        error("P7 D1 line cap drift")
    protocol["maximum_total_channel_bytes"] == 8192 ||
        error("P7 D1 channel cap drift")
    protocol["allowed_events"] == Any[P7_D1_PHASE_EVENTS...] ||
        error("P7 D1 event allowlist drift")

    d1_fixture["host_supervisor_caps"] ==
        d0_fixture["host_supervisor_caps"] ||
        error("P7 D1 host admission differs from D0")
    d1_fixture["runtime_custody"] == d0_fixture["runtime_custody"] ||
        error("P7 D1 runtime custody differs from D0")
    d1_fixture["phase_channel_custody"]["stdout_is_strictly_empty"] == true ||
        error("P7 D1 stdout discipline drift")
    return d1_fixture
end

function p7_d1_execute_adaptive_step(
    stages, execution_fixture, input_sum, trig_lookup, engine_caps,
    selection_caps, mapped_step_index::Int; copy_completed_output::Bool,
)
    mapped_step_index in (2, 3) || error("invalid P7 D1 adaptive step")
    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P7 D1 adaptive engine caps are already active")
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P7 D1 adaptive selection caps are already active")
    execution = nothing
    final_state = nothing
    cap_event = nothing
    selection_resources = nothing
    completed_output = nothing
    prefix = mapped_step_index == 2 ? "STEP2" : "STEP3"
    try
        P4_ACTIVE_STEP2_CAPS[] = engine_caps
        p6_reset_selection_state!(selection_caps)
        p7_d1_emit("$(prefix)_ENGINE_STARTED")
        execution = execute_p6_step2(
            stages, execution_fixture, input_sum, trig_lookup,
            P6_K37_THRESHOLD,
        )
        p7_d1_emit("$(prefix)_ENGINE_RETURNED")
        final_cap = execution.cap_event === nothing ?
            precheck_p4_final_cap(execution, engine_caps) : nothing
        if execution.cap_event === nothing && final_cap === nothing
            execution.completed_boundaries == P6_BOUNDARY_COUNT ||
                error("P7 D1 adaptive execution has wrong boundary count")
            P6_SELECTION_RESOURCES[].completed_selection_boundary_count ==
                P6_BOUNDARY_COUNT ||
                error("P7 D1 adaptive selection boundary count mismatch")
            p7_d1_emit("$(prefix)_FINALIZER_STARTED")
            final_state, postcheck_cap =
                finalize_p3_state!(execution, execution_fixture)
            p7_d1_emit("$(prefix)_FINALIZER_RETURNED")
            postcheck_cap === nothing ||
                error("P7 D1 final cap escaped its precheck")
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
                error("P7 D1 adaptive live-output term count drift")
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

function p7_d1_execute_prefix(
    p7_fixture, p6_fixture, p3_fixture, stages, observable, trig_lookup,
)
    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P7 D1 prefix caps leaked into step 1")
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P7 D1 selection caps leaked into step 1")
    P6_SELECTION_RESOURCES[] = P6SelectionResourceCounters()

    p7_d1_emit("STEP1_ENGINE_STARTED")
    execution1 = execute_p3(stages, p3_fixture, observable, trig_lookup)
    p7_d1_emit("STEP1_ENGINE_RETURNED")
    p7_d1_emit("STEP1_FINALIZER_STARTED")
    final1, final_cap1 = finalize_p3_state!(execution1, p3_fixture)
    p7_d1_emit("STEP1_FINALIZER_RETURNED")
    cap1 = execution1.cap_event === nothing ? final_cap1 : execution1.cap_event
    execution1.cap_event !== nothing && final_cap1 !== nothing &&
        error("P7 D1 step 1 produced two cap events")
    step1 = p7_resource_summary(execution1, cap1, final1, 1)
    if cap1 !== nothing
        p7_d1_emit("STEP1_DETERMINISTIC_CAP_TERMINAL")
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
        error("P7 D1 step1-to-step2 term-count drift")
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
    p7_d1_emit("STEP1_TO_STEP2_HANDOFF_COMPLETED")

    step2_fixture = p6_step2_execution_fixture(p6_fixture, p3_fixture)
    step2_run = p7_d1_execute_adaptive_step(
        stages, step2_fixture, step2_input, trig_lookup,
        p6_fixture["deterministic_resource_caps"],
        p6_fixture["deterministic_selection_caps"], 2;
        copy_completed_output=true,
    )
    step2 = step2_run.summary
    step2_selection_resources = step2_run.selection_resources
    if step2.cap_event !== nothing
        p7_d1_emit("STEP2_DETERMINISTIC_CAP_TERMINAL")
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
    p7_d1_emit(prefix_conformed ?
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

function main_p7_d1()
    P7_D1_FAILURE_PHASE[] = P7_D1_INVALID_FAILURE_PHASE
    length(ARGS) == 9 || error(
        "usage: phase probe D1_FIXTURE D0_FIXTURE P6 P5 P4 P3 P2 MODE FD",
    )
    d1_fixture_path = abspath(ARGS[1])
    d0_fixture_path = abspath(ARGS[2])
    p6_fixture_path = abspath(ARGS[3])
    p5_fixture_path = abspath(ARGS[4])
    p4_fixture_path = abspath(ARGS[5])
    p3_fixture_path = abspath(ARGS[6])
    p2_fixture_path = abspath(ARGS[7])
    mode = String(ARGS[8])
    mode == P7_D1_DIAGNOSTIC_MODE || error("unexpected P7 D1 mode")

    d1_fixture = JSON.parsefile(d1_fixture_path)
    d0_fixture = validate_p7_d0_fixture(JSON.parsefile(d0_fixture_path))
    validate_p7_d1_fixture(d1_fixture, d0_fixture)
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
    runtime_custody == d1_fixture["runtime_custody"] ||
        error("P7 D1 runtime witness drift")
    p7_d1_emit("D1_INPUT_AND_RUNTIME_CUSTODY_VALIDATED")

    P7_D1_FAILURE_PHASE[] = P7_D1_INDETERMINATE_FAILURE_PHASE
    maximum_bits = Int(p3_fixture["outward_arithmetic"][
        "maximum_BigInt_bit_length"
    ])
    maximum_bits == 2048 || error("P7 D1 inherited BigInt cap drift")
    trig_lookup, trig_table = build_trig_table(p3_fixture, maximum_bits)
    length(trig_table) <= 6 || error("P7 D1 trig table exceeds its cap")
    stages, _schedule = build_schedule()
    observable, _initial = initial_observable()
    p7_d1_emit("D1_STATIC_SETUP_COMPLETED")

    prefix = p7_d1_execute_prefix(
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
            error("P7 D1 step2-to-step3 term-count drift")
        step2_to_step3_link = (
            same_process=true,
            checkpoint_or_serialized_state_used=false,
            previous_step_final_term_count=
                prefix.step2.final_retained_term_count,
            next_step_input_term_count=step3_input_count,
        )
        p7_d1_emit("STEP2_TO_STEP3_HANDOFF_COMPLETED")
        step3_caps = p7_step3_engine_caps(
            d0_fixture["deterministic_step3_probe_caps"],
        )
        step3_selection_caps =
            d0_fixture["deterministic_step3_selection_probe_caps"]
        step3_fixture = p7_step3_execution_fixture(d0_fixture, p3_fixture)
        step3_run = p7_d1_execute_adaptive_step(
            stages, step3_fixture, step3_input, trig_lookup, step3_caps,
            step3_selection_caps, 3;
            copy_completed_output=false,
        )
        step3 = step3_run.summary
        step3_selection_resources = step3_run.selection_resources
        if step3.cap_event !== nothing
            p7_d1_emit("STEP3_DETERMINISTIC_CAP_TERMINAL")
        end
    end

    # Preserve D0's aggregate-public-object construction and canonicalization
    # workload, but deliberately discard the bytes: D1 stdout must stay empty.
    p7_d1_emit("D1_DIAGNOSTIC_SERIALIZATION_STARTED")
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
    P7_D1_FAILURE_PHASE[] = P7_D1_INVALID_FAILURE_PHASE
    p7_assert_public_vocabulary(raw)
    discarded_output = canonical_json(raw) * "\n"
    isempty(discarded_output) && error("P7 D1 serialization was empty")
    discarded_output = nothing
    p7_d1_emit("D1_DIAGNOSTIC_SERIALIZATION_RETURNED")
    P7_D1_FAILURE_PHASE[] = P7_D1_INDETERMINATE_FAILURE_PHASE
    p7_d1_emit("D1_DIAGNOSTIC_COMPLETED")
    return nothing
end

if P7_D1_IS_MAIN
    try
        main_p7_d1()
    catch error_value
        if error_value isa P7D1PhaseTransportError
            println(stderr, "P7_D1_PHASE_TRANSPORT_FAILURE")
            exit(70)
        elseif error_value isa OutOfMemoryError
            println(stderr, "P7_D1_HOST_FAILURE_OOM")
            exit(70)
        elseif error_value isa InterruptException
            println(stderr, "P7_D1_INDETERMINATE_INTERRUPT")
            exit(70)
        elseif P7_D1_FAILURE_PHASE[] === P7_D1_INVALID_FAILURE_PHASE
            println(stderr, "P7_D1_INVALID")
            exit(66)
        else
            println(stderr, "P7_D1_INDETERMINATE_GENERATION_FAILURE")
            exit(70)
        end
    end
end
