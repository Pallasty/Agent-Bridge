#!/usr/bin/env julia

# The P4 runner deliberately imports the frozen P3 execution engine.  Step 1
# therefore has the identical workload, Float64 path, accounting, and public
# projection as P3.  Step 2 starts from a deepcopy of the live step-1 retained
# Majorana sum in the same process; no checkpoint or result artifact is read.
# The step2 token is also a static custody canary for the local-only second-step path.
include(joinpath(@__DIR__, "..", "majorana_certificate_p3", "majorana_p3_runner.jl"))

const P4_FIXTURE_CANONICAL_SHA256 =
    "40f79c2a7fb9119f4014c9674a7a2f87ed7104d1b49ecf439a3a99097ca18d38"
const P4_FIXTURE_ID = "MAJORANA-P4-L8-FUSED-TWO-STEP-LOCAL-DEFECT-V2"
const P4_WITNESS_TYPE = "majorana_p4_L8_two_fused_steps_execution_raw_v2"
const P4_DIRECT_PARENT_COMMIT = "d5b63abe941ff0a723dd7c15a61b9ab8298286ab"

# The P3 engine accepts the same accuracy-cap key vocabulary for each local
# step.  P4 adds a step2_ prefix and independently raises the term/visit caps.
# This ref is non-nothing only while the second in-memory step is executing or
# being finalized.  It is reset in a finally block before witness emission.
const P4_ACTIVE_STEP2_CAPS = Ref{Any}(nothing)

const P4_STEP2_CAP_VALUES = (
    maximum_step2_accuracy_charged_events=33554432,
    maximum_step2_anticommuting_events=8388608,
    maximum_step2_boundary_retained_terms=262144,
    maximum_step2_cap_scan_term_visits=268435456,
    maximum_step2_current_terms_before_constituent=262144,
    maximum_step2_drop_defect_events=8388608,
    maximum_step2_final_retained_terms=262144,
    maximum_step2_merge_defect_events=8388608,
    maximum_step2_premerge_terms=524288,
    maximum_step2_product_defect_events=16777216,
    maximum_step2_propagation_term_visits=268435456,
    maximum_step2_total_P2_charged_term_visits=805568512,
    maximum_step2_total_P2_plus_accuracy_charged_events=1073741824,
    maximum_step2_truncation_term_visits=268435456,
    maximum_two_step_accuracy_charged_events=35651584,
    maximum_two_step_total_P2_charged_term_visits=872677376,
    maximum_two_step_total_P2_plus_accuracy_charged_events=1140850688,
)

function validate_p4_fixture(fixture)
    canonical_sha256(fixture) == P4_FIXTURE_CANONICAL_SHA256 ||
        error("P4 fixture differs from the frozen semantic object")
    fixture["schema_version"] == 1 || error("unexpected P4 fixture schema")
    fixture["fixture_id"] == P4_FIXTURE_ID || error("unexpected P4 fixture identity")

    relation = fixture["frozen_execution_relation"]
    relation["linear_size"] == L || error("unexpected P4 linear size")
    relation["n_sites"] == NSITES || error("unexpected P4 site count")
    relation["n_fermionic_modes"] == NMODES || error("unexpected P4 mode count")
    relation["n_majorana_generators"] == 2NMODES ||
        error("unexpected P4 Majorana generator count")
    relation["mapped_step_indices"] == Any[1, 2] ||
        error("unexpected P4 mapped-step indices")
    relation["composite_count_per_step"] == 512 ||
        error("unexpected P4 per-step composite count")
    relation["constituent_count_per_step"] == 1152 ||
        error("unexpected P4 per-step constituent count")
    relation["truncation_boundary_count_per_step"] == 768 ||
        error("unexpected P4 per-step boundary count")
    relation["total_composite_count_if_completed"] == 1024 ||
        error("unexpected P4 total composite count")
    relation["total_constituent_count_if_completed"] == 2304 ||
        error("unexpected P4 total constituent count")
    relation["total_truncation_boundary_count_if_completed"] == 1536 ||
        error("unexpected P4 total boundary count")
    relation["threshold_rational"] == "1/17179869184" ||
        error("unexpected P4 threshold")
    relation["threshold_Float64_bits_hex"] == float_bits_hex(EPSILON) ||
        error("unexpected P4 threshold bits")

    target = fixture["exact_two_step_target"]
    Tuple(String.(target["allowed_exact_applied_angles"])) == P3_ALLOWED_ANGLES ||
        error("unexpected P4 allowed-angle order")
    target["step_link"] == "X_2_0_equals_X_1_1152" ||
        error("unexpected P4 exact step link")

    arithmetic = fixture["outward_arithmetic"]
    Int(arithmetic["taylor_order"]) == P3_TAYLOR_ORDER ||
        error("unexpected P4 Taylor order")
    parse(BigInt, arithmetic["trig_grid_denominator"]) == P3_GRID_DENOMINATOR ||
        error("unexpected P4 trig grid")
    parse(BigInt, arithmetic["defect_grid_denominator"]) == P3_GRID_DENOMINATOR ||
        error("unexpected P4 defect grid")
    Int(arithmetic["maximum_BigInt_bit_length"]) == 2048 ||
        error("unexpected P4 BigInt cap")

    allocation = fixture["allocation"]
    parse_q(allocation["step2_local_increment_allocation"]) ==
        BigInt(1) // P3_ALLOCATION_DENOMINATOR ||
        error("unexpected P4 step-2 allocation")
    parse_q(allocation["two_step_cumulative_allocation"]) ==
        BigInt(1) // BigInt(200000) || error("unexpected P4 cumulative allocation")

    caps = fixture["deterministic_resource_caps"]
    caps["maximum_trig_table_entries"] == 6 || error("unexpected P4 trig-table cap")
    caps["maximum_BigInt_bit_length"] == 2048 ||
        error("inconsistent P4 BigInt cap")
    for (name, expected) in pairs(P4_STEP2_CAP_VALUES)
        caps[String(name)] == expected || error("P4 cap drift: $(name)")
    end

    continuity = fixture["same_process_fresh_two_step_replay"]
    continuity["fresh_process_starts_from_O0"] == true ||
        error("P4 fresh-start relation drift")
    continuity["step1_and_step2_execute_in_the_same_Julia_process"] == true ||
        error("P4 same-process relation drift")
    continuity["step2_input_is_a_deepcopy_of_the_in_memory_step1_retained_mainsum"] == true ||
        error("P4 in-memory step-link relation drift")
    continuity["checkpoint_resume_serialization_and_cross_process_step_link_are_forbidden"] == true ||
        error("P4 serialization prohibition drift")
    continuity["step2_local_resource_and_accuracy_counters_start_at_zero"] == true ||
        error("P4 local-counter reset relation drift")

    parent = fixture["required_parent_P3"]
    parent["direct_parent_commit"] == P4_DIRECT_PARENT_COMMIT ||
        error("unexpected P4 direct parent")
    parent["published_parent_numeric_error_bound_is_intentionally_not_copied_into_this_fixture"] ==
        true || error("P4 fixture exposes an impermissible parent numeric bound")
    return fixture
end

function validate_p4_parent_fixtures(
    p4_fixture, p3_fixture, p2_fixture,
    p3_fixture_path::AbstractString, p2_fixture_path::AbstractString,
)
    validate_p3_fixture(p3_fixture)
    file_sha256(p3_fixture_path) ==
        String(p4_fixture["required_parent_P3"]["fixture_sha256"]) ||
        error("staged P3 fixture SHA-256 differs from the P4 parent binding")
    validate_inherited_p2_fixture(p2_fixture, p3_fixture, p2_fixture_path)
    p4_caps = p4_fixture["deterministic_resource_caps"]
    p3_caps = p3_fixture["deterministic_resource_caps"]
    p2_caps = p2_fixture["deterministic_resource_caps"]
    p4_caps["maximum_two_step_accuracy_charged_events"] ==
        p3_caps["maximum_accuracy_charged_events"] +
        p4_caps["maximum_step2_accuracy_charged_events"] ||
        error("P4 two-step accuracy cap is not the sum of frozen local caps")
    p4_caps["maximum_two_step_total_P2_charged_term_visits"] ==
        p2_caps["maximum_total_charged_term_visits"] +
        p4_caps["maximum_step2_total_P2_charged_term_visits"] ||
        error("P4 two-step P2-visit cap is not the sum of frozen local caps")
    p4_caps["maximum_two_step_total_P2_plus_accuracy_charged_events"] ==
        p3_caps["maximum_total_P2_plus_accuracy_charged_events"] +
        p4_caps["maximum_step2_total_P2_plus_accuracy_charged_events"] ||
        error("P4 two-step combined cap is not the sum of frozen local caps")
    return p3_fixture, p2_fixture
end

function p4_step2_limit(name::String, passed_limit::Int, caps)
    caps === nothing && return name, passed_limit
    key = name == "maximum_current_terms_before_constituent" ?
        "maximum_step2_current_terms_before_constituent" :
        name == "maximum_premerge_terms" ? "maximum_step2_premerge_terms" :
        name == "maximum_boundary_retained_terms" ?
            "maximum_step2_boundary_retained_terms" :
        error("unmapped P4 term cap: $(name)")
    return name, Int(caps[key])
end

# These methods are more specific than the imported P3 methods only in their
# NamedTuple context argument.  With no active step-2 caps they reproduce P3's
# checks exactly; while step 2 is active they substitute the independently
# frozen P4-local cap names and values.
function check_value_cap(
    name::String, attempted::Int, passed_limit::Int, context::NamedTuple,
)
    cap_name, limit = p4_step2_limit(name, passed_limit, P4_ACTIVE_STEP2_CAPS[])
    attempted <= limit || throw(CapExceeded(cap_name, limit, attempted, context))
    return nothing
end

function p4_step2_visit_limit(field::Symbol, passed_limit::Int, caps)
    caps === nothing && return String(field), passed_limit
    key = field == :cap_scan_term_visits ? "maximum_step2_cap_scan_term_visits" :
        field == :propagation_term_visits ?
            "maximum_step2_propagation_term_visits" :
        field == :truncation_term_visits ?
            "maximum_step2_truncation_term_visits" :
        field == :final_evaluation_term_visits ?
            "maximum_step2_final_retained_terms" :
        error("unmapped P4 visit counter: $(field)")
    normalized_name = field == :cap_scan_term_visits ?
        "maximum_cap_scan_term_visits" :
        field == :propagation_term_visits ? "maximum_propagation_term_visits" :
        field == :truncation_term_visits ? "maximum_truncation_term_visits" :
        "maximum_final_evaluation_term_visits"
    return normalized_name, Int(caps[key])
end

function charge_p2!(
    counters::ResourceCounters, accuracy::AccuracyCounters, field::Symbol, amount::Int,
    passed_field_limit::Int, passed_combined_limit::Int, context::NamedTuple,
)
    amount >= 0 || error("negative P2 resource charge")
    caps = P4_ACTIVE_STEP2_CAPS[]
    field_name, field_limit = p4_step2_visit_limit(field, passed_field_limit, caps)
    attempted = getfield(counters, field) + amount
    attempted <= field_limit ||
        throw(CapExceeded(field_name, field_limit, attempted, context))

    total_limit = caps === nothing ? P2_MAX_TOTAL_VISITS :
        Int(caps["maximum_step2_total_P2_charged_term_visits"])
    total_name = caps === nothing ? "total_charged_term_visits" :
        "maximum_total_charged_term_visits"
    attempted_p2_total = charged_total(counters) + amount
    attempted_p2_total <= total_limit ||
        throw(CapExceeded(total_name, total_limit, attempted_p2_total, context))

    combined_limit = caps === nothing ? passed_combined_limit :
        Int(caps["maximum_step2_total_P2_plus_accuracy_charged_events"])
    combined_name = "maximum_total_P2_plus_accuracy_charged_events"
    attempted_combined = attempted_p2_total + accuracy_charged(accuracy)
    attempted_combined <= combined_limit ||
        throw(CapExceeded(combined_name, combined_limit, attempted_combined, context))
    setfield!(counters, field, attempted)
    return counters
end

function charge_product_events!(
    counters::AccuracyCounters, p2_counters::ResourceCounters, source_count::Int,
    passed_caps, context::NamedTuple,
)
    source_count >= 0 || error("negative anticommuting event charge")
    caps = P4_ACTIVE_STEP2_CAPS[]
    anti_name = "maximum_anticommuting_events"
    anti_limit = caps === nothing ? Int(passed_caps[anti_name]) :
        Int(caps["maximum_step2_anticommuting_events"])
    attempted_anti = counters.anticommuting_events + source_count
    attempted_anti <= anti_limit ||
        throw(CapExceeded(anti_name, anti_limit, attempted_anti, context))

    product_count = 2source_count
    product_name = "maximum_product_defect_events"
    product_limit = caps === nothing ? Int(passed_caps[product_name]) :
        Int(caps["maximum_step2_product_defect_events"])
    attempted_product = counters.product_defect_events + product_count
    attempted_product <= product_limit ||
        throw(CapExceeded(product_name, product_limit, attempted_product, context))

    accuracy_name = "maximum_accuracy_charged_events"
    accuracy_limit = caps === nothing ? Int(passed_caps[accuracy_name]) :
        Int(caps["maximum_step2_accuracy_charged_events"])
    attempted_accuracy = accuracy_charged(counters) + product_count
    attempted_accuracy <= accuracy_limit ||
        throw(CapExceeded(accuracy_name, accuracy_limit, attempted_accuracy, context))

    combined_name = "maximum_total_P2_plus_accuracy_charged_events"
    combined_limit = caps === nothing ? Int(passed_caps[combined_name]) :
        Int(caps["maximum_step2_total_P2_plus_accuracy_charged_events"])
    attempted_combined = charged_total(p2_counters) + attempted_accuracy
    attempted_combined <= combined_limit ||
        throw(CapExceeded(combined_name, combined_limit, attempted_combined, context))
    counters.anticommuting_events = attempted_anti
    counters.product_defect_events = attempted_product
    return counters
end

function charge_accuracy_events!(
    counters::AccuracyCounters, p2_counters::ResourceCounters, field::Symbol,
    amount::Int, passed_field_name::String, passed_caps, context::NamedTuple,
)
    amount >= 0 || error("negative accuracy event charge")
    caps = P4_ACTIVE_STEP2_CAPS[]
    field_name = passed_field_name
    field_key = field == :merge_defect_events ? "maximum_step2_merge_defect_events" :
        field == :drop_defect_events ? "maximum_step2_drop_defect_events" :
        error("unmapped P4 accuracy counter: $(field)")
    field_limit = caps === nothing ? Int(passed_caps[field_name]) : Int(caps[field_key])
    attempted_field = getfield(counters, field) + amount
    attempted_field <= field_limit ||
        throw(CapExceeded(field_name, field_limit, attempted_field, context))

    accuracy_name = "maximum_accuracy_charged_events"
    accuracy_limit = caps === nothing ? Int(passed_caps[accuracy_name]) :
        Int(caps["maximum_step2_accuracy_charged_events"])
    attempted_accuracy = accuracy_charged(counters) + amount
    attempted_accuracy <= accuracy_limit ||
        throw(CapExceeded(accuracy_name, accuracy_limit, attempted_accuracy, context))

    combined_name = "maximum_total_P2_plus_accuracy_charged_events"
    combined_limit = caps === nothing ? Int(passed_caps[combined_name]) :
        Int(caps["maximum_step2_total_P2_plus_accuracy_charged_events"])
    attempted_combined = charged_total(p2_counters) + attempted_accuracy
    attempted_combined <= combined_limit ||
        throw(CapExceeded(combined_name, combined_limit, attempted_combined, context))
    setfield!(counters, field, attempted_field)
    return counters
end

function translated_step2_execution_fixture(p4_fixture, p3_fixture)
    result = deepcopy(p3_fixture)
    p4_caps = p4_fixture["deterministic_resource_caps"]
    result["outward_arithmetic"]["maximum_BigInt_bit_length"] =
        p4_fixture["outward_arithmetic"]["maximum_BigInt_bit_length"]
    # execute_p3 reads the combined cap once before entering its loop.  The
    # specialized charge methods above read all authoritative P4 names.
    result["deterministic_resource_caps"] = Dict{String,Any}(
        "maximum_trig_table_entries" => p4_caps["maximum_trig_table_entries"],
        "maximum_anticommuting_events" =>
            p4_caps["maximum_step2_anticommuting_events"],
        "maximum_product_defect_events" =>
            p4_caps["maximum_step2_product_defect_events"],
        "maximum_merge_defect_events" =>
            p4_caps["maximum_step2_merge_defect_events"],
        "maximum_drop_defect_events" =>
            p4_caps["maximum_step2_drop_defect_events"],
        "maximum_accuracy_charged_events" =>
            p4_caps["maximum_step2_accuracy_charged_events"],
        "maximum_total_P2_plus_accuracy_charged_events" =>
            p4_caps["maximum_step2_total_P2_plus_accuracy_charged_events"],
    )
    return result
end

function cap_event(error_value::CapExceeded)
    return (
        cap_name=error_value.cap_name,
        limit=error_value.limit,
        attempted=error_value.attempted,
        context=error_value.context,
        rejected_operation_was_not_executed_after_cap_detection=true,
    )
end

function precheck_p4_final_cap(execution, caps)
    execution.cap_event === nothing || return nothing
    final_count = length(MajoranaPropagation.PropagationBase.mainsum(execution.cache))
    context = (operation="sorted_final_digest_and_exact_Neel_center",)
    final_limit = Int(caps["maximum_step2_final_retained_terms"])
    attempted_final = execution.p2_counters.final_evaluation_term_visits + final_count
    attempted_final <= final_limit || return cap_event(CapExceeded(
        "maximum_final_evaluation_term_visits", final_limit, attempted_final, context,
    ))
    total_limit = Int(caps["maximum_step2_total_P2_charged_term_visits"])
    attempted_total = charged_total(execution.p2_counters) + final_count
    attempted_total <= total_limit || return cap_event(CapExceeded(
        "maximum_total_charged_term_visits", total_limit, attempted_total, context,
    ))
    combined_limit = Int(caps["maximum_step2_total_P2_plus_accuracy_charged_events"])
    attempted_combined = attempted_total + accuracy_charged(execution.accuracy_counters)
    attempted_combined <= combined_limit || return cap_event(CapExceeded(
        "maximum_total_P2_plus_accuracy_charged_events", combined_limit,
        attempted_combined, context,
    ))
    return nothing
end

function local_step_row(step_index::Int, input_state, execution, cap, final_state)
    within = cap === nothing ?
        total_ticks(execution.ticks) * P3_ALLOCATION_DENOMINATOR < P3_GRID_DENOMINATOR :
        nothing
    return (
        step_index=step_index,
        input_state=input_state,
        execution=build_execution_witness(execution, cap),
        accuracy_ledger=build_accuracy_ledger(execution, within),
        final_state=final_state,
    )
end

function raw_scope()
    return (
        fixed_L8_two_adjacent_fused_mapped_steps_execution_only=true,
        fresh_process_started_from_initial_observable=true,
        step1_and_step2_same_process_in_memory=true,
        checkpoint_or_serialized_state_used=false,
        P3_result_available_to_runner=false,
        scientific_authority_claimed_by_raw_witness=false,
    )
end

function main_p4()
    length(ARGS) == 3 || error(
        "usage: majorana_p4_runner.jl P4_FIXTURE.json P3_FIXTURE.json P2_FIXTURE.json",
    )
    p4_fixture_path = abspath(ARGS[1])
    p3_fixture_path = abspath(ARGS[2])
    p2_fixture_path = abspath(ARGS[3])
    p4_fixture = validate_p4_fixture(JSON.parsefile(p4_fixture_path))
    p3_fixture = JSON.parsefile(p3_fixture_path)
    p2_fixture = JSON.parsefile(p2_fixture_path)
    validate_p4_parent_fixtures(
        p4_fixture, p3_fixture, p2_fixture, p3_fixture_path, p2_fixture_path,
    )

    active_project = Base.active_project()
    active_project === nothing && error("P4 runner requires an active project")
    manifest_path = joinpath(dirname(active_project), "Manifest.toml")
    isfile(manifest_path) || error("P4 Manifest.toml missing")
    Threads.nthreads() == 1 || error("formal P4 runner requires exactly one Julia thread")
    rounding(Float64) == RoundNearest ||
        error("formal P4 runner requires Float64 round-to-nearest-ties-to-even")
    reinterpret(UInt64, EPSILON) == 0x3dd0000000000000 ||
        error("P4 threshold bits drift")

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
    trig_lookup, trig_table = build_trig_table(p3_fixture, maximum_bits)
    stages, schedule = build_schedule()
    observable, initial = initial_observable()

    initial_input = (
        term_count=initial.nonzero_term_count,
        term_stream_sha256=initial.term_stream_sha256,
        P3_fixture_id=String(p3_fixture["fixture_id"]),
        P3_fixture_sha256=file_sha256(p3_fixture_path),
        P3_fixture_canonical_sha256=canonical_sha256(p3_fixture),
    )
    execution1 = execute_p3(stages, p3_fixture, observable, trig_lookup)
    final1, final_cap1 = finalize_p3_state!(execution1, p3_fixture)
    cap1 = execution1.cap_event === nothing ? final_cap1 : execution1.cap_event
    execution1.cap_event !== nothing && final_cap1 !== nothing &&
        error("P4 step 1 produced two deterministic cap events")
    step1 = local_step_row(1, initial_input, execution1, cap1, final1)

    steps = Any[step1]
    boundary_link = nothing
    if cap1 === nothing
        live_step1_sum = MajoranaPropagation.PropagationBase.mainsum(execution1.cache)
        step2_input_sum = deepcopy(live_step1_sum)
        input_rows = sort!(collect(step2_input_sum.Majoranas); by=first)
        input_digest = term_stream_sha256(input_rows)
        length(input_rows) == final1.retained_term_count ||
            error("P4 step-link term count differs from step-1 final state")
        input_digest == final1.term_stream_sha256 ||
            error("P4 step-link term digest differs from step-1 final state")
        step2_input = (
            term_count=length(input_rows),
            term_stream_sha256=input_digest,
        )
        empty!(input_rows)
        GC.gc()

        step2_fixture = translated_step2_execution_fixture(p4_fixture, p3_fixture)
        step2_caps = p4_fixture["deterministic_resource_caps"]
        execution2 = nothing
        final2 = nothing
        cap2 = nothing
        P4_ACTIVE_STEP2_CAPS[] = step2_caps
        try
            execution2 = execute_p3(stages, step2_fixture, step2_input_sum, trig_lookup)
            final_cap2 = execution2.cap_event === nothing ?
                precheck_p4_final_cap(execution2, step2_caps) : nothing
            if execution2.cap_event === nothing && final_cap2 === nothing
                final2, postcheck_cap2 = finalize_p3_state!(execution2, step2_fixture)
                postcheck_cap2 === nothing ||
                    error("P4 step-2 final cap escaped the precheck")
                final2 = merge(final2, (
                    exact_dyadic_center_and_declared_interval_are_authoritative=false,
                    exact_dyadic_center_is_authoritative_execution_fact=true,
                    local_only_interval_is_not_two_step_authority=true,
                ))
            end
            cap2 = execution2.cap_event === nothing ? final_cap2 : execution2.cap_event
        finally
            P4_ACTIVE_STEP2_CAPS[] = nothing
        end
        push!(steps, local_step_row(2, step2_input, execution2, cap2, final2))
        boundary_link = (
            same_process=true,
            no_serialization=true,
            step1_output_term_count=final1.retained_term_count,
            step1_output_term_stream_sha256=final1.term_stream_sha256,
            step2_input_term_count=step2_input.term_count,
            step2_input_term_stream_sha256=step2_input.term_stream_sha256,
        )
    end

    raw = (
        schema_version=1,
        witness_type=P4_WITNESS_TYPE,
        fixture_id=String(p4_fixture["fixture_id"]),
        fixture_sha256=file_sha256(p4_fixture_path),
        fixture_canonical_sha256=canonical_sha256(p4_fixture),
        inherited_P2_fixture_sha256=file_sha256(p2_fixture_path),
        inherited_P2_fixture_canonical_sha256=canonical_sha256(p2_fixture),
        runtime=runtime,
        upstream=upstream,
        initial_observable=initial,
        schedule=schedule,
        trig_table=trig_table,
        steps=steps,
        step_boundary_link=boundary_link,
        scope=raw_scope(),
    )
    print(canonical_json(raw))
    print('\n')
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main_p4()
end
