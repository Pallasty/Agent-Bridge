#!/usr/bin/env julia

# Formal P5 S0 candidate runner.  It imports the frozen P4 closure so step 1
# remains the exact P3 2^-34 execution.  Step 2 uses the copied P3 oracle below
# with one explicit Float64 threshold argument.  No P3/P4 result artifact or
# non-authoritative D0 report is opened by this runner.
include(joinpath(@__DIR__, "..", "majorana_certificate_p4", "majorana_p4_runner.jl"))

const P5_FIXTURE_CANONICAL_SHA256 =
    "bbac5a9281198ba87b336c6e45741d1468f85bb2997317943f1a45b6ac90de91"
const P5_FIXTURE_ID = "MAJORANA-P5-L8-CONDITIONAL-STEP2-THRESHOLD-S0-V1"
const P5_WITNESS_TYPE =
    "majorana_p5_L8_conditional_step2_threshold_candidate_execution_raw_v1"
const P5_DIRECT_DESIGN_PARENT = "0265c7a4d726bf5b875247d0412e6a1d2f909973"
const P5_ALLOWED_STEP2_EXPONENTS = (36, 37)

const P5_STEP2_CAP_VALUES = (
    maximum_step2_accuracy_charged_events=33554432,
    maximum_step2_anticommuting_events=16777216,
    maximum_step2_boundary_retained_terms=524288,
    maximum_step2_cap_scan_term_visits=536870912,
    maximum_step2_current_terms_before_constituent=524288,
    maximum_step2_drop_defect_events=8388608,
    maximum_step2_final_retained_terms=524288,
    maximum_step2_merge_defect_events=4194304,
    maximum_step2_premerge_terms=524288,
    maximum_step2_product_defect_events=33554432,
    maximum_step2_propagation_term_visits=536870912,
    maximum_step2_total_P2_charged_term_visits=1073741824,
    maximum_step2_total_P2_plus_accuracy_charged_events=1073741824,
    maximum_step2_truncation_term_visits=268435456,
)

function p5_require_exact_keys(value, expected, context::AbstractString)
    value isa AbstractDict || error("$(context) must be an object")
    actual = Set(String.(keys(value)))
    wanted = Set(String.(expected))
    actual == wanted || error("$(context) key mismatch")
    return value
end

function validate_p5_fixture(fixture)
    canonical_sha256(fixture) == P5_FIXTURE_CANONICAL_SHA256 ||
        error("P5 fixture differs from the frozen semantic object")
    p5_require_exact_keys(fixture, (
        "schema_version", "fixture_id", "direct_design_parent",
        "frozen_execution_relation", "candidate_thresholds",
        "outward_arithmetic", "deterministic_resource_caps",
        "host_supervisor_caps", "conditional_authority", "scope",
    ), "P5 fixture")
    fixture["schema_version"] == 1 || error("unexpected P5 fixture schema")
    fixture["fixture_id"] == P5_FIXTURE_ID || error("unexpected P5 fixture identity")

    parent = fixture["direct_design_parent"]
    parent["commit_sha"] == P5_DIRECT_DESIGN_PARENT ||
        error("unexpected P5 direct design parent")
    parent["D0_policy_id"] == "MAJORANA-P5-CONDITIONAL-STEP2-THRESHOLD-D0-V1" ||
        error("unexpected P5 D0 policy identity")
    parent["D0_policy_sha256"] ==
        "e47ad24291f217b0b5d54ba6aa120c479d522bd23c74faf41b5bde6da2413aa2" ||
        error("unexpected P5 D0 policy custody")
    parent["D0_report_sha256"] ==
        "602c4eddea30c20ddb793e2641b1e8b55e4767a62366b946892a19c3802dffc5" ||
        error("unexpected P5 D0 report custody")
    parent["D0_report_available_to_runner"] == false ||
        error("P5 fixture exposes D0 report to runner")
    parent["formal_caps_derived_before_this_fixture"] == true ||
        error("P5 caps were not frozen before the formal fixture")

    relation = fixture["frozen_execution_relation"]
    relation["linear_size"] == L || error("unexpected P5 linear size")
    relation["n_sites"] == NSITES || error("unexpected P5 site count")
    relation["n_fermionic_modes"] == NMODES || error("unexpected P5 mode count")
    relation["n_majorana_generators"] == 2NMODES ||
        error("unexpected P5 Majorana generator count")
    relation["mapped_step_indices"] == Any[1, 2] ||
        error("unexpected P5 mapped steps")
    relation["composite_count_per_step"] == 512 ||
        error("unexpected P5 composite count")
    relation["constituent_count_per_step"] == 1152 ||
        error("unexpected P5 constituent count")
    relation["truncation_boundary_count_per_step"] == 768 ||
        error("unexpected P5 boundary count")
    relation["step1_threshold_exponent"] == 34 ||
        error("unexpected P5 step-1 threshold exponent")
    relation["step1_threshold_rational"] == "1/17179869184" ||
        error("unexpected P5 step-1 threshold rational")
    relation["step1_threshold_Float64_bits_hex"] == "3dd0000000000000" ||
        error("unexpected P5 step-1 threshold bits")
    for key in (
        "candidate_step2_only", "same_process_step1_then_candidate_step2",
        "step1_P3_fieldwise_conformance_required",
        "step1_uses_unmodified_execute_p3",
        "step2_input_is_live_deepcopy_of_step1_retained_mainsum",
        "step2_uses_explicit_threshold_parameter",
        "candidate_exponent_selected_only_from_CLI_and_fixture_allowlist",
        "no_cross_candidate_state_or_checkpoint",
        "runner_must_not_read_P3_or_P4_result_or_D0_report",
    )
        relation[key] == true || error("P5 execution relation drift: $(key)")
    end

    candidates = fixture["candidate_thresholds"]
    length(candidates) == 2 || error("P5 requires exactly two candidates")
    expected_candidates = (
        ("K36", 36, "1/68719476736", "3db0000000000000"),
        ("K37", 37, "1/137438953472", "3da0000000000000"),
    )
    for (row, expected) in zip(candidates, expected_candidates)
        p5_require_exact_keys(row, (
            "candidate_id", "threshold_exponent", "threshold_rational",
            "threshold_Float64_bits_hex", "strict_less_than",
            "fresh_process_count",
        ), "P5 candidate")
        row["candidate_id"] == expected[1] || error("P5 candidate order drift")
        row["threshold_exponent"] == expected[2] || error("P5 exponent drift")
        row["threshold_rational"] == expected[3] || error("P5 rational drift")
        row["threshold_Float64_bits_hex"] == expected[4] ||
            error("P5 threshold bits drift")
        row["strict_less_than"] == true || error("P5 threshold rule drift")
        row["fresh_process_count"] == 2 || error("P5 freshness count drift")
    end

    arithmetic = fixture["outward_arithmetic"]
    arithmetic["taylor_order"] == P3_TAYLOR_ORDER ||
        error("unexpected P5 Taylor order")
    parse(BigInt, arithmetic["trig_grid_denominator"]) == P3_GRID_DENOMINATOR ||
        error("unexpected P5 trig grid")
    parse(BigInt, arithmetic["defect_grid_denominator"]) == P3_GRID_DENOMINATOR ||
        error("unexpected P5 defect grid")
    arithmetic["maximum_BigInt_bit_length"] == 2048 ||
        error("unexpected P5 BigInt cap")
    arithmetic["outward_integer_binary64_RNE_oracle_required"] == true ||
        error("P5 outward-oracle requirement drift")

    caps = fixture["deterministic_resource_caps"]
    caps["maximum_trig_table_entries"] == 6 || error("P5 trig-table cap drift")
    caps["maximum_BigInt_bit_length"] == 2048 || error("P5 BigInt cap drift")
    caps["caps_are_checked_before_the_rejected_operation"] == true ||
        error("P5 pre-operation cap rule drift")
    caps["no_operation_occurs_after_the_first_deterministic_cap_event"] == true ||
        error("P5 terminal cap rule drift")
    for (name, expected) in pairs(P5_STEP2_CAP_VALUES)
        caps[String(name)] == expected || error("P5 cap drift: $(name)")
    end

    host = fixture["host_supervisor_caps"]
    host["MemoryMax_bytes"] == 4294967296 || error("P5 memory cap drift")
    host["MemorySwapMax_bytes"] == 0 || error("P5 swap cap drift")
    host["RuntimeMaxSec"] == "1200s" || error("P5 runtime cap drift")
    host["maximum_stdout_bytes"] == 16777216 || error("P5 stdout cap drift")
    host["systemd_user_scope_cgroup_v2_required"] == true ||
        error("P5 cgroup requirement drift")

    authority = fixture["conditional_authority"]
    authority["selection_order"] == Any["K36", "K37"] ||
        error("P5 candidate selection order drift")
    authority["require_all_candidates_completed"] == true ||
        error("P5 all-candidate completion rule drift")
    authority["runner_outputs_candidate_local_allocation_pass_only"] == true ||
        error("P5 runner authority boundary drift")
    authority["candidate_cumulative_allocation_pass_is_outer_checker_only"] == true ||
        error("P5 cumulative authority boundary drift")
    authority["selected_candidate_is_outer_checker_only"] == true ||
        error("P5 selection authority boundary drift")
    parse_q(authority["candidate_local_allocation"]) ==
        BigInt(1) // P3_ALLOCATION_DENOMINATOR ||
        error("P5 candidate local allocation drift")
    parse_q(authority["conditional_two_step_cumulative_allocation"]) ==
        BigInt(1) // BigInt(200000) ||
        error("P5 conditional cumulative allocation drift")
    authority["formal_authority"] ==
        "conditional_step2_local_defect_and_Neel_enclosure_after_complete_P3_step1_conformance_only" ||
        error("P5 conditional authority drift")
    fixture["scope"]["scientific_authority_claimed_by_raw_witness"] == false ||
        error("P5 raw witness claims scientific authority")
    return fixture
end

function p5_select_candidate(fixture, exponent::Int)
    exponent in P5_ALLOWED_STEP2_EXPONENTS ||
        error("unexpected P5 step-2 threshold exponent")
    rows = filter(row -> Int(row["threshold_exponent"]) == exponent,
        fixture["candidate_thresholds"])
    length(rows) == 1 || error("P5 candidate lookup is not unique")
    row = only(rows)
    threshold = ldexp(1.0, -exponent)
    float_bits_hex(threshold) == row["threshold_Float64_bits_hex"] ||
        error("P5 CLI threshold bits differ from fixture")
    row["threshold_rational"] == "1/$(string(BigInt(1) << exponent))" ||
        error("P5 CLI threshold rational differs from fixture")
    return row, threshold
end

function p5_step2_execution_fixture(p5_fixture, p3_fixture)
    result = deepcopy(p3_fixture)
    caps = p5_fixture["deterministic_resource_caps"]
    result["outward_arithmetic"]["maximum_BigInt_bit_length"] =
        p5_fixture["outward_arithmetic"]["maximum_BigInt_bit_length"]
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

# Copied byte-for-byte from P3 execute_p3 except for the function name,
# explicit threshold argument/guard, and the threshold callback comparison.
# All arithmetic, upstream checks, cap charging, ledgers, and record hashes stay
# on the frozen P3/P4 path.

function execute_p5_step2(stages, fixture, observable, trig_lookup, threshold::Float64)
    isfinite(threshold) && threshold > 0.0 || error("invalid P5 step-2 threshold")
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
                        dropped = Tuple{typeof(constituent.rotation.ms_int),Float64}[]
                        callback_visits = Ref(0)
                        callback = function (mask, coefficient)
                            coefficient isa Float64 || error("unexpected P3 threshold coefficient type")
                            isfinite(coefficient) || error("non-finite P3 threshold coefficient")
                            callback_visits[] += 1
                            should_drop = abs(coefficient) < threshold
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

function main_p5()
    length(ARGS) == 5 || error(
        "usage: majorana_p5_runner.jl P5_FIXTURE.json P4_FIXTURE.json " *
        "P3_FIXTURE.json P2_FIXTURE.json STEP2_EXPONENT",
    )
    p5_fixture_path = abspath(ARGS[1])
    p4_fixture_path = abspath(ARGS[2])
    p3_fixture_path = abspath(ARGS[3])
    p2_fixture_path = abspath(ARGS[4])
    exponent = parse(Int, ARGS[5])

    p5_fixture = validate_p5_fixture(JSON.parsefile(p5_fixture_path))
    p4_fixture = validate_p4_fixture(JSON.parsefile(p4_fixture_path))
    p3_fixture = JSON.parsefile(p3_fixture_path)
    p2_fixture = JSON.parsefile(p2_fixture_path)
    validate_p4_parent_fixtures(
        p4_fixture, p3_fixture, p2_fixture, p3_fixture_path, p2_fixture_path,
    )
    base_pins = p5_fixture["frozen_execution_relation"][
        "required_base_fixture_sha256"
    ]
    file_sha256(p4_fixture_path) == base_pins["P4"] ||
        error("P5 inherited P4 fixture digest mismatch")
    file_sha256(p3_fixture_path) == base_pins["P3"] ||
        error("P5 inherited P3 fixture digest mismatch")
    file_sha256(p2_fixture_path) == base_pins["P2"] ||
        error("P5 inherited P2 fixture digest mismatch")
    candidate_row, step2_threshold = p5_select_candidate(p5_fixture, exponent)

    active_project = Base.active_project()
    active_project === nothing && error("P5 runner requires an active project")
    manifest_path = joinpath(dirname(active_project), "Manifest.toml")
    isfile(manifest_path) || error("P5 Manifest.toml missing")
    Threads.nthreads() == 1 || error("formal P5 runner requires one Julia thread")
    rounding(Float64) == RoundNearest ||
        error("formal P5 runner requires Float64 RNE")
    reinterpret(UInt64, EPSILON) == 0x3dd0000000000000 ||
        error("P5 frozen step-1 threshold bits drift")

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

    # Step 1 intentionally calls the unmodified imported P3 function.  No P5
    # cap or threshold selector is active on this path.
    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P5 step-2 caps leaked into step 1")
    execution1 = execute_p3(stages, p3_fixture, observable, trig_lookup)
    final1, final_cap1 = finalize_p3_state!(execution1, p3_fixture)
    cap1 = execution1.cap_event === nothing ? final_cap1 : execution1.cap_event
    execution1.cap_event !== nothing && final_cap1 !== nothing &&
        error("P5 step 1 produced two deterministic cap events")
    step1 = local_step_row(1, initial_input, execution1, cap1, final1)

    step2 = nothing
    step_boundary_link = nothing
    candidate_local_allocation_pass = nothing
    if cap1 === nothing
        live_step1_sum = MajoranaPropagation.PropagationBase.mainsum(execution1.cache)
        step2_input_sum = deepcopy(live_step1_sum)
        input_rows = sort!(collect(step2_input_sum.Majoranas); by=first)
        input_digest = term_stream_sha256(input_rows)
        length(input_rows) == final1.retained_term_count ||
            error("P5 step-link term count differs from step-1 final state")
        input_digest == final1.term_stream_sha256 ||
            error("P5 step-link term digest differs from step-1 final state")
        step2_input = (
            term_count=length(input_rows),
            term_stream_sha256=input_digest,
        )
        empty!(input_rows)
        GC.gc()

        step2_fixture = p5_step2_execution_fixture(p5_fixture, p3_fixture)
        step2_caps = p5_fixture["deterministic_resource_caps"]
        execution2 = nothing
        final2 = nothing
        cap2 = nothing
        P4_ACTIVE_STEP2_CAPS[] = step2_caps
        try
            execution2 = execute_p5_step2(
                stages, step2_fixture, step2_input_sum, trig_lookup,
                step2_threshold,
            )
            final_cap2 = execution2.cap_event === nothing ?
                precheck_p4_final_cap(execution2, step2_caps) : nothing
            if execution2.cap_event === nothing && final_cap2 === nothing
                final2, postcheck_cap2 =
                    finalize_p3_state!(execution2, step2_fixture)
                postcheck_cap2 === nothing ||
                    error("P5 step-2 final cap escaped precheck")
                final2 = merge(final2, (
                    exact_dyadic_center_and_declared_interval_are_authoritative=false,
                    exact_dyadic_center_is_authoritative_execution_fact=true,
                    local_only_interval_is_not_two_step_authority=true,
                ))
            end
            cap2 = execution2.cap_event === nothing ? final_cap2 :
                execution2.cap_event
            candidate_local_allocation_pass = cap2 === nothing ?
                total_ticks(execution2.ticks) * P3_ALLOCATION_DENOMINATOR <
                    P3_GRID_DENOMINATOR : nothing
        finally
            P4_ACTIVE_STEP2_CAPS[] = nothing
        end
        step2 = local_step_row(2, step2_input, execution2, cap2, final2)
        step2.accuracy_ledger.strictly_within_allocation ==
            candidate_local_allocation_pass ||
            error("P5 candidate local-allocation truth mismatch")
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
        candidate_id=String(candidate_row["candidate_id"]),
        identity="step1_fixed_2^-34_then_step2_fixed_2^-$(exponent)",
        required_fresh_process_count=Int(candidate_row["fresh_process_count"]),
        step1_threshold_exponent=34,
        step1_threshold_rational="1/17179869184",
        step1_threshold_Float64_bits_hex=float_bits_hex(EPSILON),
        step2_threshold_exponent=exponent,
        step2_threshold_rational=String(candidate_row["threshold_rational"]),
        step2_threshold_Float64_bits_hex=float_bits_hex(step2_threshold),
        strict_drop_rule="abs_binary64_coefficient_strictly_less_than_threshold",
        step1_path_is_not_rethresholded=true,
    )

    raw = (
        schema_version=1,
        witness_type=P5_WITNESS_TYPE,
        fixture_id=String(p5_fixture["fixture_id"]),
        fixture_sha256=file_sha256(p5_fixture_path),
        fixture_canonical_sha256=canonical_sha256(p5_fixture),
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
        candidate_local_allocation_pass=candidate_local_allocation_pass,
        scope=p5_fixture["scope"],
    )
    print(canonical_json(raw))
    print('\n')
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main_p5()
end
