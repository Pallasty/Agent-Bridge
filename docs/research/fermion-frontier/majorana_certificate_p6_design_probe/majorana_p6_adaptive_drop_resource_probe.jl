#!/usr/bin/env julia

# Non-authoritative P6 D0 resource probe.  The execution harness stages the
# frozen P5 runner and changes only its step-2 drop block so that it calls the
# three p6_* hooks below.  Step 1 remains the unmodified P3 2^-34 path.  This
# driver emits aggregate resource observations only; defect-ledger values,
# observable values, allocation decisions, and scientific-result commitments
# are deliberately absent from its public object.
include(joinpath(
    @__DIR__, "..", "majorana_certificate_p5", "majorana_p5_runner.jl",
))

const P6_D0_PROBE_TYPE =
    "majorana_p6_e768_max_lazy37_resource_probe_d0_v1"
const P6_D0_FIXTURE_ID = "MAJORANA-P6-E768-MAX-LAZY37-D0-V1"
const P6_D0_FIXTURE_CANONICAL_SHA256 =
    "9b02421b53ef407531b95e1f9d4f48f29642f88962be297789ecbc88792755ba"
const P6_D0_DIRECT_PARENT = "39100195cfd04bb4de086f127e8a75da0a7548ce"
const P6_CONTROL_MODE = "P5_K37_RESOURCE_CONTROL"
const P6_ADAPTIVE_MODE = "E768_MAX_LAZY37_V1"
const P6_ALLOWED_MODES = (P6_CONTROL_MODE, P6_ADAPTIVE_MODE)
const P6_CONTROL_CANDIDATE_ID = "P5-K37-RESOURCE-CONTROL"
const P6_ADAPTIVE_CANDIDATE_ID = "E768-MAX-LAZY37-V1"

const P6_GRID_DENOMINATOR = BigInt(1) << 128
const P6_LOCAL_ALLOCATION_DENOMINATOR = BigInt(400000)
const P6_MAXIMUM_STRICTLY_LEGAL_LOCAL_TICKS =
    fld(P6_GRID_DENOMINATOR - 1, P6_LOCAL_ALLOCATION_DENOMINATOR)
const P6_BOUNDARY_COUNT = 768
const P6_K37_THRESHOLD = ldexp(1.0, -37)
const P6_K37_ABS_BITS = UInt64(0x3da0000000000000)
const P6_ABS_BITS_MASK = UInt64(0x7fffffffffffffff)

const P6_STEP2_CAP_KEYS = (
    "maximum_step2_accuracy_charged_events",
    "maximum_step2_anticommuting_events",
    "maximum_step2_boundary_retained_terms",
    "maximum_step2_cap_scan_term_visits",
    "maximum_step2_current_terms_before_constituent",
    "maximum_step2_drop_defect_events",
    "maximum_step2_final_retained_terms",
    "maximum_step2_merge_defect_events",
    "maximum_step2_premerge_terms",
    "maximum_step2_product_defect_events",
    "maximum_step2_propagation_term_visits",
    "maximum_step2_total_P2_charged_term_visits",
    "maximum_step2_total_P2_plus_accuracy_charged_events",
    "maximum_step2_truncation_term_visits",
)

const P6_SELECTION_CAP_KEYS = (
    "maximum_ranking_scan_term_visits",
    "maximum_sort_input_items",
    "maximum_tick_evaluations",
    "maximum_selected_membership_insertions",
    "maximum_peak_ranking_buffer_terms",
    "maximum_total_selection_work_units",
)

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

const P6_ACTIVE_MODE = Ref{Union{Nothing,String}}(nothing)
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
    mode::String
    boundary_index::Int
    snapshot_count::Int
    snapshot_coefficient_bits::Dict{Any,UInt64}
    selected_costs::Dict{Any,BigInt}
    callback_seen_masks::Set{Any}
    callback_visit_count::Int
    maximum_bits::Int
    context::Any
    validated::Bool
end

function p6_require_exact_keys(value, expected, context::AbstractString)
    value isa AbstractDict || error("$(context) must be an object")
    actual = Set(String.(keys(value)))
    wanted = Set(String.(expected))
    actual == wanted || error("$(context) key mismatch")
    return value
end

function p6_validate_positive_integer_caps(value, expected, context::AbstractString)
    p6_require_exact_keys(value, expected, context)
    for key in expected
        cap = value[key]
        cap isa Integer && cap > 0 || error("$(context) has invalid cap: $(key)")
        cap <= typemax(Int) || error("$(context) cap exceeds host Int: $(key)")
    end
    return value
end

function validate_p6_d0_fixture(fixture)
    canonical_sha256(fixture) == P6_D0_FIXTURE_CANONICAL_SHA256 ||
        error("P6 D0 fixture differs from the frozen semantic object")
    fixture["schema_version"] == 1 || error("unexpected P6 D0 fixture schema")
    fixture["fixture_id"] == P6_D0_FIXTURE_ID ||
        error("unexpected P6 D0 fixture identity")
    fixture["required_direct_parent_commit"] == P6_D0_DIRECT_PARENT ||
        error("unexpected P6 D0 direct parent")
    fixture["scientific_authority"] == "NONE" ||
        error("P6 D0 fixture claims scientific authority")
    fixture["certificate_eligible"] == false ||
        error("P6 D0 fixture is certificate eligible")

    design = fixture["candidate_design"]
    design["probe_order"] == Any[P6_CONTROL_MODE, P6_ADAPTIVE_MODE] ||
        error("P6 D0 probe order drift")
    design["formal_candidates"] == Any[P6_ADAPTIVE_MODE] ||
        error("P6 D0 formal candidate drift")
    design["control_candidate"] == P6_CONTROL_MODE ||
        error("P6 D0 control identity drift")
    design["step1_threshold_exponent"] == 34 ||
        error("P6 D0 step-1 threshold drift")
    design["control_step2_threshold_exponent"] == 37 ||
        error("P6 D0 control threshold drift")
    design["control_step2_threshold_Float64_bits_hex"] ==
        float_bits_hex(P6_K37_THRESHOLD) || error("P6 D0 K37 bits drift")
    for key in (
        "formal_candidate_is_frozen_before_any_probe_output",
        "control_helper_returns_a_noop_sentinel_and_preserves_the_original_strict_K37_callback",
        "control_selection_resource_counters_are_all_zero",
        "formal_threshold_argument_only_validates_the_2^-37_lazy_anchor_bits",
        "formal_threshold_argument_cannot_create_a_hard_scientific_eligibility_gate",
        "each_mode_runs_from_O0_in_a_fresh_process",
        "step1_and_step2_are_same_process_without_checkpoint_or_serialization",
        "candidate_state_is_not_shared",
    )
        design[key] == true || error("P6 D0 candidate relation drift: $(key)")
    end

    rule = fixture["full_domain_adaptive_rule"]
    parse(BigInt, rule["grid_denominator"]) == P6_GRID_DENOMINATOR ||
        error("P6 D0 grid drift")
    rule["local_allocation_denominator"] ==
        Int(P6_LOCAL_ALLOCATION_DENOMINATOR) ||
        error("P6 D0 local denominator drift")
    parse(BigInt, rule["maximum_strictly_legal_local_ticks"]) ==
        P6_MAXIMUM_STRICTLY_LEGAL_LOCAL_TICKS ||
        error("P6 D0 strict local integer drift")
    rule["boundary_count"] == P6_BOUNDARY_COUNT ||
        error("P6 D0 boundary count drift")
    rule["raw_boundary_indices"] == "0_through_767" ||
        error("P6 D0 boundary index drift")
    rule["released_prefix_number_q"] ==
        "raw_boundary_index_plus_one_in_1_through_768" ||
        error("P6 D0 released-prefix indexing drift")
    rule["ranking_key"] == Any[
        "exact_point_abs_ticks",
        "sign_cleared_binary64_magnitude_bits",
        "unsigned_majorana_mask",
    ] || error("P6 D0 ranking key drift")
    for key in (
        "postmerge_snapshot_precedes_any_drop", "exact_fit_is_selected",
        "stop_at_first_unaffordable_positive_cost_row_without_skipping",
        "zero_cost_rows_are_selected_at_zero_available_ticks",
        "unused_prefix_budget_carries_forward_implicitly",
        "future_prefix_budget_cannot_be_borrowed",
        "drop_ticks_are_never_refunded_after_merge_cancellation_or_reappearance",
        "product_merge_and_drop_share_one_local_prefix_ledger",
        "final_local_allocation_is_recomputed_by_the_formal_outer_checker",
        "does_not_claim_global_optimality_across_future_boundaries",
    )
        rule[key] == true || error("P6 D0 full-domain rule drift: $(key)")
    end

    lazy = fixture["exact_lazy_implementation"]
    lazy["split_threshold_exponent"] == 37 || error("P6 D0 lazy split drift")
    lazy["split_threshold_Float64_bits_hex"] == float_bits_hex(P6_K37_THRESHOLD) ||
        error("P6 D0 lazy split bits drift")
    for key in (
        "tier1_is_a_provable_initial_segment_of_the_full_ranking",
        "if_budget_is_exhausted_inside_tier1_stop_without_tier2",
        "if_tier1_is_fully_selected_with_positive_remainder_rescan_the_same_unmodified_snapshot",
        "tier2_collects_every_outside_row_whose_exact_cost_is_at_most_the_current_remainder",
        "tier2_uses_the_same_full_ranking_key_and_prefix_rule",
        "callback_only_tests_precomputed_membership",
        "callback_iteration_order_cannot_consume_budget",
        "callback_revalidates_selected_coefficient_bits",
        "prepare_helper_reads_but_never_mutates_the_live_merged_main_and_authoritative_ticks",
        "all_deletions_are_performed_only_by_the_existing_truncate_callback",
        "the_existing_drop_ledger_is_the_only_authoritative_drop_charge",
        "existing_drop_ledger_recomputes_and_must_equal_the_selection_cost",
    )
        lazy[key] == true || error("P6 D0 lazy rule drift: $(key)")
    end
    lazy["hard_K37_eligibility_gate_is_forbidden"] == true ||
        error("P6 D0 accidentally permits a hard K37 gate")

    p6_validate_positive_integer_caps(
        fixture["deterministic_step2_probe_caps"], P6_STEP2_CAP_KEYS,
        "P6 D0 step-2 caps",
    )
    p6_validate_positive_integer_caps(
        fixture["deterministic_selection_probe_caps"], P6_SELECTION_CAP_KEYS,
        "P6 D0 selection caps",
    )
    arithmetic = fixture["outward_arithmetic"]
    arithmetic["maximum_BigInt_bit_length"] == 2048 ||
        error("P6 D0 BigInt cap drift")
    arithmetic["all_budget_schedule_and_comparisons_use_BigInt"] == true ||
        error("P6 D0 integer schedule requirement drift")
    arithmetic["Float64_is_used_only_by_the_frozen_propagation_path"] == true ||
        error("P6 D0 Float64 authority boundary drift")
    accounting = fixture["selection_resource_accounting"]
    for key in (
        "live_selected_membership_peak_is_bounded_by_the_step2_postmerge_term_cap_and_cleared_after_each_boundary",
        "each_component_and_the_combined_total_are_checked_before_the_corresponding_operation",
        "control_candidate_has_zero_selection_work",
        "tier1_and_tier2_counts_are_exported_only_as_one_aggregate",
    )
        accounting[key] == true ||
            error("P6 D0 selection-resource accounting drift: $(key)")
    end
    return fixture
end

p6_abs_bits(value::Float64)::UInt64 = reinterpret(UInt64, value) & P6_ABS_BITS_MASK

function p6_prefix_target(boundary_index::Int)::BigInt
    0 <= boundary_index < P6_BOUNDARY_COUNT ||
        error("P6 boundary index outside 0:767")
    return fld(
        BigInt(boundary_index + 1) * P6_MAXIMUM_STRICTLY_LEGAL_LOCAL_TICKS,
        BigInt(P6_BOUNDARY_COUNT),
    )
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

function p6_reset_selection_state!(mode::String, caps)
    mode in P6_ALLOWED_MODES || error("unexpected P6 D0 mode")
    P6_ACTIVE_MODE[] === nothing || error("P6 mode is already active")
    P6_ACTIVE_SELECTION_CAPS[] === nothing ||
        error("P6 selection caps are already active")
    P6_ACTIVE_MODE[] = mode
    P6_ACTIVE_SELECTION_CAPS[] = caps
    P6_SELECTION_RESOURCES[] = P6SelectionResourceCounters()
    return nothing
end

function p6_clear_selection_state!()
    P6_ACTIVE_MODE[] = nothing
    P6_ACTIVE_SELECTION_CAPS[] = nothing
    return nothing
end

function p6_selection_cap_context(boundary_index::Int, operation::AbstractString)
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
    work_current = counters.total_selection_work_units
    amount <= typemax(Int) - work_current || error("P6 selection work overflow")
    work_attempted = work_current + amount
    work_limit = Int(caps["maximum_total_selection_work_units"])
    work_attempted <= work_limit || throw(CapExceeded(
        "maximum_total_selection_work_units", work_limit, work_attempted,
        p6_selection_cap_context(boundary_index, operation),
    ))
    setfield!(counters, field, attempted)
    counters.total_selection_work_units = work_attempted
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

function p6_prepare_adaptive_decision(
    merged_main, ticks, boundary_index::Int, maximum_bits::Int, context,
)
    rows = p6_snapshot_rows(merged_main, boundary_index)
    snapshot_bits = Dict{Any,UInt64}(
        row.mask => row.coefficient_bits for row in rows
    )
    length(snapshot_bits) == length(rows) || error("P6 snapshot map lost a mask")

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

    # The strict-K37 segment is only a lazy initial segment.  If it was fully
    # consumed and a positive amount remains, rescan the original immutable
    # snapshot and admit every outside row individually affordable at that
    # point before applying the identical full-domain ranking/prefix rule.
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
        P6_ADAPTIVE_MODE, boundary_index, length(rows), snapshot_bits,
        selected_costs, Set{Any}(), 0, maximum_bits, context, false,
    )
end

function p6_prepare_control_decision(
    merged_main, boundary_index::Int, maximum_bits::Int, context,
)
    # The control is the existing P5 K37 callback projection.  It performs no
    # adaptive ranking work, so all seven public selection-resource fields stay
    # exactly zero.
    p6_merged_table(merged_main)
    return nothing
end

"""
    p6_prepare_boundary_drop!(merged_main, ticks, boundary_index, maximum_bits, context)

Freeze one complete postmerge adaptive decision before `truncate!` invokes its
streaming callback.  This exact five-argument interface is called by the staged
P5 runner.
"""
function p6_prepare_boundary_drop!(
    merged_main, ticks, boundary_index::Int, maximum_bits::Int, context,
)
    mode = P6_ACTIVE_MODE[]
    mode === nothing && error("P6 drop mode is inactive")
    0 <= boundary_index < P6_BOUNDARY_COUNT ||
        error("P6 boundary index outside 0:767")
    maximum_bits == 2048 || error("unexpected P6 BigInt cap")
    if mode == P6_CONTROL_MODE
        return p6_prepare_control_decision(
            merged_main, boundary_index, maximum_bits, context,
        )
    elseif mode == P6_ADAPTIVE_MODE
        return p6_prepare_adaptive_decision(
            merged_main, ticks, boundary_index, maximum_bits, context,
        )
    end
    error("unexpected active P6 mode")
end

"""
    p6_should_drop(decision, mask, coefficient, threshold)

Return only the already-frozen membership decision.  Callback order never
changes the adaptive amount consumed.
"""
function p6_should_drop(
    decision::P6BoundaryDropDecision, mask, coefficient, threshold::Float64,
)::Bool
    decision.validated && error("P6 decision was reused after validation")
    coefficient isa Float64 || error("unexpected P6 callback coefficient type")
    isfinite(coefficient) || error("non-finite P6 callback coefficient")
    reinterpret(UInt64, threshold) == P6_K37_ABS_BITS ||
        error("P6 staged runner threshold differs from K37")
    decision.mode == P6_ADAPTIVE_MODE ||
        error("typed P6 decision is not the adaptive candidate")
    decision.callback_visit_count += 1

    haskey(decision.snapshot_coefficient_bits, mask) ||
        error("P6 callback mask absent from frozen snapshot")
    mask in decision.callback_seen_masks &&
        error("P6 callback visited a mask more than once")
    push!(decision.callback_seen_masks, mask)
    reinterpret(UInt64, coefficient) ==
        decision.snapshot_coefficient_bits[mask] ||
        error("P6 callback coefficient differs from frozen snapshot")
    return haskey(decision.selected_costs, mask)
end

function p6_should_drop(
    ::Nothing, mask, coefficient, threshold::Float64,
)::Bool
    coefficient isa Float64 || error("unexpected P6 control coefficient type")
    isfinite(coefficient) || error("non-finite P6 control coefficient")
    reinterpret(UInt64, threshold) == P6_K37_ABS_BITS ||
        error("P6 control threshold differs from K37")
    return abs(coefficient) < threshold
end

"""
    p6_validate_selected_drop_ticks!(decision, transition_drop_ticks, dropped)

After the unchanged P5 drop-ledger loop, prove that its recomputed row costs and
actual dropped rows equal the precomputed decision.
"""
function p6_validate_selected_drop_ticks!(
    decision::P6BoundaryDropDecision, transition_drop_ticks::Integer, dropped,
)
    decision.validated && error("P6 decision was validated twice")
    decision.mode == P6_ADAPTIVE_MODE ||
        error("typed P6 decision is not the adaptive candidate")
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
        reinterpret(UInt64, coefficient) ==
            decision.snapshot_coefficient_bits[mask] ||
            error("P6 dropped coefficient differs from frozen snapshot")
    end
    actual_masks == Set(keys(decision.selected_costs)) ||
        error("P6 upstream dropped membership differs from frozen selection")
    expected = sum(values(decision.selected_costs); init=BigInt(0))
    BigInt(transition_drop_ticks) == expected ||
        error("P6 adaptive selection cost differs from the existing drop ledger")

    counters = P6_SELECTION_RESOURCES[]
    counters.completed_selection_boundary_count += 1
    counters.completed_selection_boundary_count <= P6_BOUNDARY_COUNT ||
        error("too many P6 selection boundaries")
    decision.validated = true
    return nothing
end

function p6_validate_selected_drop_ticks!(
    ::Nothing, transition_drop_ticks::Integer, dropped,
)
    # The unchanged P5 ledger already computed the control charge.  Repeating
    # millions of exact row-cost evaluations would distort D0 CPU resources;
    # only the frozen strict-K37 predicate is revalidated here.
    for row in dropped
        length(row) == 2 || error("invalid P6 control dropped row")
        _mask, coefficient = row
        coefficient isa Float64 || error("invalid P6 control dropped coefficient")
        isfinite(coefficient) || error("non-finite P6 control dropped coefficient")
        abs(coefficient) < P6_K37_THRESHOLD ||
            error("P6 control dropped a non-K37 row")
    end
    return nothing
end

function p6_step2_execution_fixture(p6_fixture, p3_fixture)
    result = deepcopy(p3_fixture)
    caps = p6_fixture["deterministic_step2_probe_caps"]
    result["outward_arithmetic"]["maximum_BigInt_bit_length"] =
        p6_fixture["outward_arithmetic"]["maximum_BigInt_bit_length"]
    result["deterministic_resource_caps"] = Dict{String,Any}(
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

function p6_clean_cap_context(context)
    context === nothing && return nothing
    allowed = (
        "stage_index", "group", "composite_index", "constituent_index",
        "boundary_index", "operation",
    )
    result = Dict{String,Any}()
    for key in allowed
        symbol = Symbol(key)
        if context isa NamedTuple && hasproperty(context, symbol)
            result[key] = key == "operation" ?
                "resource_cap_precheck" : getproperty(context, symbol)
        elseif context isa AbstractDict && haskey(context, key)
            result[key] = key == "operation" ?
                "resource_cap_precheck" : context[key]
        elseif context isa AbstractDict && haskey(context, symbol)
            result[key] = key == "operation" ?
                "resource_cap_precheck" : context[symbol]
        end
    end
    # Some inherited term-count prechecks carry only schedule coordinates.
    # Public D0 cap contexts nevertheless use one frozen resource-only
    # operation label, independent of the private upstream operation shape.
    result["operation"] = "resource_cap_precheck"
    return result
end

function p6_clean_cap_event(cap_event)
    cap_event === nothing && return nothing
    return (
        cap_name=String(cap_event.cap_name),
        limit=Int(cap_event.limit),
        attempted=Int(cap_event.attempted),
        context=p6_clean_cap_context(cap_event.context),
        rejected_operation_was_not_executed_after_cap_detection=true,
    )
end

function p6_d0_resource_summary(execution, cap_event, final_state)
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
        cap_event=p6_clean_cap_event(cap_event),
    )
end

function p6_assert_public_vocabulary(value, path::String="\$")
    forbidden = (
        "_ticks", "budget", "slack", "digest", "neel", "winner",
        "fallback", "pass", "bits", "cutoff",
    )
    if value isa NamedTuple
        for key in keys(value)
            name = String(key)
            lower = lowercase(name)
            for fragment in forbidden
                occursin(fragment, lower) &&
                    error("forbidden P6 D0 public key at $(path).$(name)")
            end
            p6_assert_public_vocabulary(getproperty(value, key), "$(path).$(name)")
        end
    elseif value isa AbstractDict
        for (key, item) in value
            name = String(key)
            lower = lowercase(name)
            for fragment in forbidden
                occursin(fragment, lower) &&
                    error("forbidden P6 D0 public key at $(path).$(name)")
            end
            p6_assert_public_vocabulary(item, "$(path).$(name)")
        end
    elseif value isa AbstractVector || value isa Tuple
        for (index, item) in enumerate(value)
            p6_assert_public_vocabulary(item, "$(path)[$(index)]")
        end
    elseif value isa AbstractString
        lower = lowercase(value)
        for fragment in forbidden
            occursin(fragment, lower) &&
                error("forbidden P6 D0 public string at $(path)")
        end
    end
    return value
end

function main_p6_d0()
    length(ARGS) == 6 || error(
        "usage: majorana_p6_adaptive_drop_resource_probe.jl " *
        "P6_FIXTURE.json P5_FIXTURE.json P4_FIXTURE.json P3_FIXTURE.json " *
        "P2_FIXTURE.json MODE",
    )
    p6_fixture_path = abspath(ARGS[1])
    p5_fixture_path = abspath(ARGS[2])
    p4_fixture_path = abspath(ARGS[3])
    p3_fixture_path = abspath(ARGS[4])
    p2_fixture_path = abspath(ARGS[5])
    mode = String(ARGS[6])
    mode in P6_ALLOWED_MODES || error("unexpected P6 D0 mode")

    p6_fixture = validate_p6_d0_fixture(JSON.parsefile(p6_fixture_path))
    p5_fixture = validate_p5_fixture(JSON.parsefile(p5_fixture_path))
    p4_fixture = validate_p4_fixture(JSON.parsefile(p4_fixture_path))
    p3_fixture = JSON.parsefile(p3_fixture_path)
    p2_fixture = JSON.parsefile(p2_fixture_path)
    validate_p4_parent_fixtures(
        p4_fixture, p3_fixture, p2_fixture, p3_fixture_path, p2_fixture_path,
    )
    pins = p6_fixture["required_base_fixture_sha256"]
    file_sha256(p5_fixture_path) == pins["P5"] ||
        error("P6 inherited P5 fixture digest mismatch")
    file_sha256(p4_fixture_path) == pins["P4"] ||
        error("P6 inherited P4 fixture digest mismatch")
    file_sha256(p3_fixture_path) == pins["P3"] ||
        error("P6 inherited P3 fixture digest mismatch")
    file_sha256(p2_fixture_path) == pins["P2"] ||
        error("P6 inherited P2 fixture digest mismatch")
    _candidate_row, step2_threshold = p5_select_candidate(p5_fixture, 37)

    Threads.nthreads() == 1 || error("P6 D0 requires exactly one Julia thread")
    rounding(Float64) == RoundNearest || error("P6 D0 requires binary64 RNE")
    reinterpret(UInt64, EPSILON) == 0x3dd0000000000000 ||
        error("P6 D0 frozen step-1 threshold bits drift")
    reinterpret(UInt64, step2_threshold) == P6_K37_ABS_BITS ||
        error("P6 D0 K37 control threshold bits drift")
    P6_GRID_DENOMINATOR == P3_GRID_DENOMINATOR || error("P6/P3 grid mismatch")

    maximum_bits = Int(p3_fixture["outward_arithmetic"]["maximum_BigInt_bit_length"])
    trig_lookup, _trig_table = build_trig_table(p3_fixture, maximum_bits)
    stages, schedule = build_schedule()
    observable, initial = initial_observable()

    P4_ACTIVE_STEP2_CAPS[] === nothing ||
        error("P6 step-2 caps leaked into step 1")
    execution1 = execute_p3(stages, p3_fixture, observable, trig_lookup)
    final1, final_cap1 = finalize_p3_state!(execution1, p3_fixture)
    cap1 = execution1.cap_event === nothing ? final_cap1 : execution1.cap_event
    execution1.cap_event !== nothing && final_cap1 !== nothing &&
        error("P6 D0 step 1 produced two deterministic cap events")
    step1 = p6_d0_resource_summary(execution1, cap1, final1)

    execution2 = nothing
    final2 = nothing
    cap2 = nothing
    step_link = nothing
    P6_SELECTION_RESOURCES[] = P6SelectionResourceCounters()
    if cap1 === nothing
        live_step1_sum = MajoranaPropagation.PropagationBase.mainsum(execution1.cache)
        step2_input_sum = deepcopy(live_step1_sum)
        step2_input_count = length(step2_input_sum.Majoranas)
        step2_input_count == final1.retained_term_count ||
            error("P6 D0 step-link term count mismatch")
        GC.gc()

        step2_fixture = p6_step2_execution_fixture(p6_fixture, p3_fixture)
        step2_caps = p6_fixture["deterministic_step2_probe_caps"]
        selection_caps = p6_fixture["deterministic_selection_probe_caps"]
        P4_ACTIVE_STEP2_CAPS[] = step2_caps
        p6_reset_selection_state!(mode, selection_caps)
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
                    error("P6 D0 step-2 final cap escaped precheck")
            end
            cap2 = execution2.cap_event === nothing ? final_cap2 :
                execution2.cap_event
            if cap2 === nothing
                execution2.completed_boundaries == P6_BOUNDARY_COUNT ||
                    error("P6 D0 completed execution has wrong boundary count")
                if mode == P6_ADAPTIVE_MODE
                    P6_SELECTION_RESOURCES[].completed_selection_boundary_count ==
                        execution2.completed_boundaries ||
                        error("P6 adaptive selection boundary count mismatch")
                else
                    p6_public_selection_resources() == (
                        total_ranking_scan_term_visits=0,
                        total_sort_work_items=0,
                        total_tick_evaluations=0,
                        total_selected_membership_insertions=0,
                        peak_ranking_buffer_terms=0,
                        total_selection_work_units=0,
                        completed_selection_boundary_count=0,
                    ) || error("P6 control accumulated adaptive selection work")
                end
            end
        finally
            p6_clear_selection_state!()
            P4_ACTIVE_STEP2_CAPS[] = nothing
        end
        step_link = (
            same_process=true,
            checkpoint_or_serialized_state_used=false,
            step1_final_term_count=final1.retained_term_count,
            step2_input_term_count=step2_input_count,
        )
    end

    step2 = p6_d0_resource_summary(execution2, cap2, final2)
    raw = (
        schema_version=1,
        probe_type=P6_D0_PROBE_TYPE,
        scientific_authority="NONE",
        certificate_eligible=false,
        result_contract_eligible=false,
        resource_observations_only=true,
        candidate=(
            candidate_id=mode == P6_CONTROL_MODE ?
                P6_CONTROL_CANDIDATE_ID : P6_ADAPTIVE_CANDIDATE_ID,
            probe_mode=mode,
            identity=mode,
            control_candidate=mode == P6_CONTROL_MODE,
            formal_candidate=mode == P6_ADAPTIVE_MODE,
            step1_path="fixed_P3_2^-34",
            step2_path=mode == P6_CONTROL_MODE ?
                "fixed_P5_K37_resource_control" :
                "full_domain_E768_MAX_LAZY37_V1",
        ),
        step1=step1,
        step2=step2,
        step_link=step_link,
        selection_resources=p6_public_selection_resources(),
        explicit_exclusions=(
            "scientific_local_or_cumulative_error_values",
            "allocation_assessment_or_candidate_selection",
            "term_or_drop_stream_commitments",
            "checkerboard_observable_center_or_interval",
            "adaptive_execution_branch_as_scientific_evidence",
            "scientific_witness_result_contract_certificate_or_READY_authority",
        ),
    )
    p6_assert_public_vocabulary(raw)
    print(canonical_json(raw))
    print('\n')
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main_p6_d0()
end
