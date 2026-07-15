#!/usr/bin/env julia

# The P3 runner deliberately reuses only the frozen P2 workload construction,
# upstream propagation path, canonical JSON helpers, and source-custody helpers.
# It does not read the committed P2 result.  All numerical accuracy accounting
# below is recomputed from the freshly executed Float64 state.
include(joinpath(@__DIR__, "..", "majorana_certificate_p2", "majorana_p2_runner.jl"))

const P3_FIXTURE_CANONICAL_SHA256 =
    "bb252f4d7df4858fbceaae6ff22f2d6f56067f45446ec06604a8b5f937274d87"
const P3_FIXTURE_ID = "MAJORANA-P3-L8-FUSED-ONE-STEP-LOCAL-DEFECT-V1"
const P3_WITHIN_STATUS =
    "VERIFIED_MAJORANA_P3_L8_STAGGERED_MAGNETIZATION_ONE_FUSED_STEP_LOCAL_DEFECT_AND_TRUNCATION_OPERATOR_AND_NEEL_EXPECTATION_BOUND_SUBCERTIFICATE"
const P3_EXCEEDS_STATUS =
    "VERIFIED_MAJORANA_P3_L8_ONE_FUSED_STEP_ERROR_BOUND_EXCEEDS_ALLOCATION_SUBCERTIFICATE"
const P3_CAP_STATUS =
    "VERIFIED_MAJORANA_P3_L8_ONE_FUSED_STEP_ACCURACY_POLICY_CAP_EXCEEDED_SUBCERTIFICATE"

const P3_TAYLOR_ORDER = 7
const P3_GRID_DENOMINATOR = BigInt(1) << 128
const P3_ALLOCATION_DENOMINATOR = BigInt(400000)
const P3_ALLOWED_ANGLES = ("-1/50", "-1/100", "-1/200", "1/200", "1/100", "1/50")

# P2 caps are inherited by policy.  They are repeated as source constants so
# the Julia runner need not read the P2 result or any unstaged artifact.
const P2_MAX_BOUNDARY_TERMS = 65536
const P2_MAX_CURRENT_TERMS = 65536
const P2_MAX_PREMERGE_TERMS = 65536
const P2_MAX_CAP_SCAN_VISITS = 33554432
const P2_MAX_PROPAGATION_VISITS = 33554432
const P2_MAX_TRUNCATION_VISITS = 16777216
const P2_MAX_TOTAL_VISITS = 67108864

"""Incremental SHA-256 of a canonical JSON array without retaining its rows."""
mutable struct CanonicalArrayHasher
    context::SHA.SHA2_256_CTX
    count::Int
    closed::Bool
end

function CanonicalArrayHasher()
    context = SHA.SHA2_256_CTX()
    SHA.update!(context, codeunits("["))
    return CanonicalArrayHasher(context, 0, false)
end

function push_canonical_row!(hasher::CanonicalArrayHasher, row)
    hasher.closed && error("canonical array hasher is already closed")
    hasher.count > 0 && SHA.update!(hasher.context, codeunits(","))
    SHA.update!(hasher.context, codeunits(canonical_json(row)))
    hasher.count += 1
    return hasher
end

function finish_canonical_array!(hasher::CanonicalArrayHasher)::String
    hasher.closed && error("canonical array hasher is already closed")
    SHA.update!(hasher.context, codeunits("]"))
    hasher.closed = true
    return bytes2hex(SHA.digest!(hasher.context))
end

mutable struct AccuracyCounters
    anticommuting_events::Int
    product_defect_events::Int
    merge_defect_events::Int
    drop_defect_events::Int
end

AccuracyCounters() = AccuracyCounters(0, 0, 0, 0)

accuracy_charged(counters::AccuracyCounters) =
    counters.product_defect_events + counters.merge_defect_events +
    counters.drop_defect_events

function public_accuracy_counters(counters::AccuracyCounters)
    return (
        anticommuting_event_count=counters.anticommuting_events,
        product_defect_event_count=counters.product_defect_events,
        merge_defect_event_count=counters.merge_defect_events,
        drop_defect_event_count=counters.drop_defect_events,
        accuracy_charged_event_count=accuracy_charged(counters),
    )
end

mutable struct DefectTicks
    product::BigInt
    merge::BigInt
    drop::BigInt
end

DefectTicks() = DefectTicks(BigInt(0), BigInt(0), BigInt(0))
total_ticks(ticks::DefectTicks) = ticks.product + ticks.merge + ticks.drop

function public_ticks(ticks::DefectTicks)
    return (
        product_defect_ticks=string(ticks.product),
        merge_defect_ticks=string(ticks.merge),
        drop_defect_ticks=string(ticks.drop),
        total_operator_error_ticks=string(total_ticks(ticks)),
    )
end

function validate_p3_fixture(fixture)
    canonical_sha256(fixture) == P3_FIXTURE_CANONICAL_SHA256 ||
        error("P3 fixture differs from the frozen semantic object")
    fixture["schema_version"] == 1 || error("unexpected P3 fixture schema")
    fixture["fixture_id"] == P3_FIXTURE_ID || error("unexpected P3 fixture identity")
    relation = fixture["frozen_execution_relation"]
    relation["linear_size"] == L || error("unexpected P3 linear size")
    relation["n_sites"] == NSITES || error("unexpected P3 site count")
    relation["n_fermionic_modes"] == NMODES || error("unexpected P3 mode count")
    relation["n_majorana_generators"] == 2NMODES ||
        error("unexpected P3 Majorana generator count")
    relation["composite_count"] == 512 || error("unexpected P3 composite count")
    relation["constituent_count"] == 1152 || error("unexpected P3 constituent count")
    relation["truncation_boundary_count"] == 768 || error("unexpected P3 boundary count")
    relation["threshold_rational"] == "1/17179869184" ||
        error("unexpected P3 threshold")
    relation["threshold_Float64_bits_hex"] == float_bits_hex(EPSILON) ||
        error("unexpected P3 threshold bits")
    exact_target = fixture["exact_prefix_target"]
    Tuple(String.(exact_target["allowed_exact_applied_angles"])) == P3_ALLOWED_ANGLES ||
        error("unexpected P3 allowed-angle order")
    arithmetic = fixture["outward_arithmetic"]
    Int(arithmetic["taylor_order"]) == P3_TAYLOR_ORDER ||
        error("unexpected P3 Taylor order")
    parse(BigInt, arithmetic["trig_grid_denominator"]) == P3_GRID_DENOMINATOR ||
        error("unexpected P3 trig grid")
    parse(BigInt, arithmetic["defect_grid_denominator"]) == P3_GRID_DENOMINATOR ||
        error("unexpected P3 defect grid")
    parse_q(fixture["allocation"]["prefix_total_error_allocation"]) ==
        BigInt(1) // P3_ALLOCATION_DENOMINATOR || error("unexpected P3 allocation")
    return fixture
end

function validate_inherited_p2_fixture(p2_fixture, p3_fixture, p2_fixture_path::AbstractString)
    validate_fixture(p2_fixture)
    expected_sha256 = String(p3_fixture["required_parent"]["fixture_sha256"])
    file_sha256(p2_fixture_path) == expected_sha256 ||
        error("staged P2 fixture SHA-256 differs from the P3 parent binding")
    p2_fixture["fixture_id"] ==
        p3_fixture["frozen_execution_relation"]["workload_fixture"] ||
        error("P3 workload identity differs from the staged P2 fixture")
    p2_caps = p2_fixture["deterministic_resource_caps"]
    p2_caps["maximum_boundary_retained_terms"] == P2_MAX_BOUNDARY_TERMS ||
        error("inherited P2 boundary cap drift")
    p2_caps["maximum_current_terms_before_constituent"] == P2_MAX_CURRENT_TERMS ||
        error("inherited P2 current-term cap drift")
    p2_caps["maximum_premerge_terms"] == P2_MAX_PREMERGE_TERMS ||
        error("inherited P2 premerge cap drift")
    p2_caps["maximum_cap_scan_term_visits"] == P2_MAX_CAP_SCAN_VISITS ||
        error("inherited P2 scan-visit cap drift")
    p2_caps["maximum_propagation_term_visits"] == P2_MAX_PROPAGATION_VISITS ||
        error("inherited P2 propagation-visit cap drift")
    p2_caps["maximum_truncation_term_visits"] == P2_MAX_TRUNCATION_VISITS ||
        error("inherited P2 truncation-visit cap drift")
    p2_caps["maximum_total_charged_term_visits"] == P2_MAX_TOTAL_VISITS ||
        error("inherited P2 total-visit cap drift")
    p2_caps["maximum_composites"] == 512 || error("inherited P2 composite cap drift")
    p2_caps["maximum_constituents"] == 1152 || error("inherited P2 constituent cap drift")
    p2_caps["maximum_truncation_boundaries"] == 768 ||
        error("inherited P2 boundary-count cap drift")
    return p2_fixture
end

function bigint_bit_length(value::BigInt)::Int
    iszero(value) && return 0
    return ndigits(abs(value); base=2)
end

function check_bigint_cap!(value::BigInt, maximum_bits::Int, context)
    attempted = bigint_bit_length(value)
    attempted <= maximum_bits ||
        throw(CapExceeded("maximum_BigInt_bit_length", maximum_bits, attempted, context))
    return value
end

function floor_grid(value::Q)::BigInt
    return fld(numerator(value) * P3_GRID_DENOMINATOR, denominator(value))
end

function ceil_grid(value::Q)::BigInt
    value >= 0 || error("ceil_grid requires a nonnegative rational")
    return cld(numerator(value) * P3_GRID_DENOMINATOR, denominator(value))
end

function upper_grid(value::Q)::BigInt
    return cld(numerator(value) * P3_GRID_DENOMINATOR, denominator(value))
end

function exact_float_q(value::Float64)::Q
    isfinite(value) || error("non-finite Float64 point in P3 accuracy ledger")
    bits = reinterpret(UInt64, value)
    negative = (bits >> 63) == 1
    exponent_bits = Int((bits >> 52) & 0x7ff)
    fraction_bits = bits & 0x000fffffffffffff
    if exponent_bits == 0 && fraction_bits == 0
        return zero(Q)
    end
    significand = exponent_bits == 0 ? BigInt(fraction_bits) :
        (BigInt(1) << 52) + BigInt(fraction_bits)
    exponent = exponent_bits == 0 ? -1074 : exponent_bits - 1023 - 52
    numerator_value = negative ? -significand : significand
    result = exponent >= 0 ?
        (numerator_value << exponent) // BigInt(1) :
        numerator_value // (BigInt(1) << (-exponent))
    reinterpret(UInt64, Float64(result)) == bits ||
        error("Float64 exact-dyadic bit round trip failed for $(float_bits_hex(value))")
    return result
end

function p3_taylor_trig(theta::Q, maximum_bits::Int)
    abs(theta) <= BigInt(1) // BigInt(50) || error("P3 exact angle exceeds 1/50")
    sine_point = zero(Q)
    cosine_point = zero(Q)
    for k in 0:P3_TAYLOR_ORDER
        sine_point += (-1)^k * theta^(2k + 1) // factorial(big(2k + 1))
        cosine_point += (-1)^k * theta^(2k) // factorial(big(2k))
    end
    sine_remainder = abs(theta)^(2P3_TAYLOR_ORDER + 3) //
        factorial(big(2P3_TAYLOR_ORDER + 3))
    cosine_remainder = abs(theta)^(2P3_TAYLOR_ORDER + 2) //
        factorial(big(2P3_TAYLOR_ORDER + 2))
    sine_lower = floor_grid(sine_point - sine_remainder)
    sine_upper = upper_grid(sine_point + sine_remainder)
    cosine_lower = floor_grid(cosine_point - cosine_remainder)
    cosine_upper = upper_grid(cosine_point + cosine_remainder)
    for (name, value) in (
        ("sine_lower", sine_lower), ("sine_upper", sine_upper),
        ("cosine_lower", cosine_lower), ("cosine_upper", cosine_upper),
    )
        check_bigint_cap!(value, maximum_bits, (operation="trig_table", endpoint=name))
    end
    return (
        sine_lower_ticks=sine_lower,
        sine_upper_ticks=sine_upper,
        cosine_lower_ticks=cosine_lower,
        cosine_upper_ticks=cosine_upper,
    )
end

function build_trig_table(fixture, maximum_bits::Int)
    entries = Any[]
    lookup = Dict{String,Any}()
    maximum_entries = Int(fixture["deterministic_resource_caps"]["maximum_trig_table_entries"])
    length(P3_ALLOWED_ANGLES) <= maximum_entries ||
        throw(CapExceeded("maximum_trig_table_entries", maximum_entries,
            length(P3_ALLOWED_ANGLES), (operation="build_trig_table",)))
    for angle in P3_ALLOWED_ANGLES
        theta = parse_q(angle)
        theta_float = Float64(theta)
        enclosure = p3_taylor_trig(theta, maximum_bits)
        row = (
            angle=angle,
            angle_Float64_bits_hex=float_bits_hex(theta_float),
            sine_Float64_bits_hex=float_bits_hex(sin(theta_float)),
            cosine_Float64_bits_hex=float_bits_hex(cos(theta_float)),
            sine_lower_ticks=string(enclosure.sine_lower_ticks),
            sine_upper_ticks=string(enclosure.sine_upper_ticks),
            cosine_lower_ticks=string(enclosure.cosine_lower_ticks),
            cosine_upper_ticks=string(enclosure.cosine_upper_ticks),
        )
        push!(entries, row)
        lookup[angle] = merge(enclosure, (
            angle_float=theta_float,
            sine_float=sin(theta_float),
            cosine_float=cos(theta_float),
        ))
    end
    return lookup, (
        taylor_order=P3_TAYLOR_ORDER,
        grid_denominator=string(P3_GRID_DENOMINATOR),
        entry_count=length(entries),
        entries=entries,
        entries_sha256=canonical_sha256(entries),
    )
end

function interval_scale_ticks(lower::BigInt, upper::BigInt, scale::Q)
    left = scale * (lower // P3_GRID_DENOMINATOR)
    right = scale * (upper // P3_GRID_DENOMINATOR)
    return min(left, right), max(left, right)
end

function point_to_interval_defect_ticks(
    point::Float64, input::Float64, lower_ticks::BigInt, upper_ticks::BigInt,
    branch_sign::Int, maximum_bits::Int, context,
)
    branch_sign in (-1, 1) || error("P3 branch sign must be +/-1")
    input_q = exact_float_q(input) * BigInt(branch_sign)
    lower_q, upper_q = interval_scale_ticks(lower_ticks, upper_ticks, input_q)
    point_q = exact_float_q(point)
    defect = max(abs(point_q - lower_q), abs(point_q - upper_q))
    ticks = ceil_grid(defect)
    return check_bigint_cap!(ticks, maximum_bits, context)
end

function point_sum_defect_ticks(
    merged::Float64, left::Float64, right::Float64, maximum_bits::Int, context,
)
    defect = abs(exact_float_q(merged) - exact_float_q(left) - exact_float_q(right))
    ticks = ceil_grid(defect)
    return check_bigint_cap!(ticks, maximum_bits, context)
end

function point_abs_ticks(value::Float64, maximum_bits::Int, context)
    ticks = ceil_grid(abs(exact_float_q(value)))
    return check_bigint_cap!(ticks, maximum_bits, context)
end

function add_ticks!(ticks::DefectTicks, field::Symbol, increment::BigInt,
    maximum_bits::Int, context)
    increment >= 0 || error("negative defect increment")
    updated = getfield(ticks, field) + increment
    check_bigint_cap!(updated, maximum_bits, merge(context, (accumulator=String(field),)))
    setfield!(ticks, field, updated)
    check_bigint_cap!(total_ticks(ticks), maximum_bits,
        merge(context, (accumulator="total_operator_error",)))
    return ticks
end

function lower_parity(left::Integer, right::Integer)::Int
    parity = 0
    remaining = left
    one_value = one(left)
    while !iszero(remaining)
        index = trailing_zeros(remaining)
        lower_mask = index == 0 ? zero(left) : (one_value << index) - one_value
        parity ⊻= Int(isodd(count_ones(right & lower_mask)))
        remaining &= remaining - one_value
    end
    return parity
end

function independent_target_and_branch(gate::Integer, source::Integer)
    omega_value = mod(count_ones(gate) * count_ones(source) - count_ones(gate & source), 2)
    omega_value == 1 || error("independent P3 action called for a commuting pair")
    self_gate = mod((count_ones(gate)^2 - count_ones(gate)) ÷ 2, 2)
    self_source = mod((count_ones(source)^2 - count_ones(source)) ÷ 2, 2)
    f_value = self_gate * self_source +
        omega_value * (self_gate + self_source + 1)
    phase_sign = isodd(lower_parity(gate, source) + f_value) ? -1 : 1
    # For an anticommuting pair the product phase is phase_sign * i and
    # upstream uses -imag(phase) as the sine-branch coefficient.
    return gate ⊻ source, -phase_sign
end

function occupied_gamma_mask_checkerboard(::Type{TT}) where {TT<:Integer}
    result = zero(TT)
    for site0 in 0:(NSITES - 1)
        row, column = divrem(site0, L)
        site = site0 + 1
        fermion = iseven(row + column) ? 2site - 1 : 2site
        result |= one(TT) << (2fermion - 2)
    end
    return result
end

function independent_fock_diagonal(mask::TT, occupied_gamma_mask::TT)::Int where {TT<:Integer}
    for fermion in 1:NMODES
        first_bit = (mask >> (2fermion - 2)) & one(TT)
        second_bit = (mask >> (2fermion - 1)) & one(TT)
        first_bit == second_bit || return 0
    end
    self_parity = mod((count_ones(mask)^2 - count_ones(mask)) ÷ 2, 2)
    exponent = mod(self_parity + count_ones(mask) ÷ 2, 4)
    phase = exponent == 0 ? 1 : exponent == 2 ? -1 :
        error("independent Fock diagonal has a non-real phase")
    return phase * (isodd(count_ones(mask & occupied_gamma_mask)) ? -1 : 1)
end

function charge_p2!(
    counters::ResourceCounters, accuracy::AccuracyCounters, field::Symbol, amount::Int,
    field_limit::Int, accuracy_plus_p2_limit::Int, context,
)
    amount >= 0 || error("negative P2 resource charge")
    current = getfield(counters, field)
    attempted = current + amount
    attempted <= field_limit ||
        throw(CapExceeded(String(field), field_limit, attempted, context))
    attempted_p2_total = charged_total(counters) + amount
    attempted_p2_total <= P2_MAX_TOTAL_VISITS ||
        throw(CapExceeded("total_charged_term_visits", P2_MAX_TOTAL_VISITS,
            attempted_p2_total, context))
    attempted_combined = attempted_p2_total + accuracy_charged(accuracy)
    attempted_combined <= accuracy_plus_p2_limit ||
        throw(CapExceeded("maximum_total_P2_plus_accuracy_charged_events",
            accuracy_plus_p2_limit, attempted_combined, context))
    setfield!(counters, field, attempted)
    return counters
end

function charge_product_events!(
    counters::AccuracyCounters, p2_counters::ResourceCounters, source_count::Int,
    caps, context,
)
    source_count >= 0 || error("negative anticommuting event charge")
    attempted_anticommuting = counters.anticommuting_events + source_count
    maximum_anticommuting = Int(caps["maximum_anticommuting_events"])
    attempted_anticommuting <= maximum_anticommuting ||
        throw(CapExceeded("maximum_anticommuting_events", maximum_anticommuting,
            attempted_anticommuting, context))
    product_count = 2source_count
    attempted_product = counters.product_defect_events + product_count
    maximum_product = Int(caps["maximum_product_defect_events"])
    attempted_product <= maximum_product ||
        throw(CapExceeded("maximum_product_defect_events", maximum_product,
            attempted_product, context))
    attempted_accuracy = accuracy_charged(counters) + product_count
    maximum_accuracy = Int(caps["maximum_accuracy_charged_events"])
    attempted_accuracy <= maximum_accuracy ||
        throw(CapExceeded("maximum_accuracy_charged_events", maximum_accuracy,
            attempted_accuracy, context))
    maximum_combined = Int(caps["maximum_total_P2_plus_accuracy_charged_events"])
    attempted_combined = charged_total(p2_counters) + attempted_accuracy
    attempted_combined <= maximum_combined ||
        throw(CapExceeded("maximum_total_P2_plus_accuracy_charged_events",
            maximum_combined, attempted_combined, context))
    counters.anticommuting_events = attempted_anticommuting
    counters.product_defect_events = attempted_product
    return counters
end

function charge_accuracy_events!(
    counters::AccuracyCounters, p2_counters::ResourceCounters, field::Symbol,
    amount::Int, field_cap_name::String, caps, context,
)
    amount >= 0 || error("negative accuracy event charge")
    attempted_field = getfield(counters, field) + amount
    maximum_field = Int(caps[field_cap_name])
    attempted_field <= maximum_field ||
        throw(CapExceeded(field_cap_name, maximum_field, attempted_field, context))
    attempted_accuracy = accuracy_charged(counters) + amount
    maximum_accuracy = Int(caps["maximum_accuracy_charged_events"])
    attempted_accuracy <= maximum_accuracy ||
        throw(CapExceeded("maximum_accuracy_charged_events", maximum_accuracy,
            attempted_accuracy, context))
    maximum_combined = Int(caps["maximum_total_P2_plus_accuracy_charged_events"])
    attempted_combined = charged_total(p2_counters) + attempted_accuracy
    attempted_combined <= maximum_combined ||
        throw(CapExceeded("maximum_total_P2_plus_accuracy_charged_events",
            maximum_combined, attempted_combined, context))
    setfield!(counters, field, attempted_field)
    return counters
end

function execute_p3(stages, fixture, observable, trig_lookup)
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
                            should_drop = abs(coefficient) < EPSILON
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

function finalize_p3_state!(execution, fixture)
    execution.cap_event === nothing || return nothing, nothing
    execution.completed_composites == 512 || error("P3 completed composite count mismatch")
    execution.completed_constituents == 1152 || error("P3 completed constituent count mismatch")
    execution.completed_boundaries == 768 || error("P3 completed boundary count mismatch")
    maximum_combined = Int(fixture["deterministic_resource_caps"][
        "maximum_total_P2_plus_accuracy_charged_events"
    ])
    maximum_bits = Int(fixture["outward_arithmetic"]["maximum_BigInt_bit_length"])
    final_sum = MajoranaPropagation.PropagationBase.mainsum(execution.cache)
    final_rows = sort!(collect(final_sum.Majoranas); by=first)
    final_cap_event = nothing
    try
        charge_p2!(execution.p2_counters, execution.accuracy_counters,
            :final_evaluation_term_visits, length(final_rows),
            P2_MAX_BOUNDARY_TERMS, maximum_combined,
            (operation="sorted_final_digest_and_exact_Neel_center",))
    catch error_value
        if error_value isa CapExceeded
            final_cap_event = (
                cap_name=error_value.cap_name,
                limit=error_value.limit,
                attempted=error_value.attempted,
                context=error_value.context,
                rejected_operation_was_not_executed_after_cap_detection=true,
            )
            return nothing, final_cap_event
        end
        rethrow()
    end

    TT = keytype(final_sum.Majoranas)
    occupied_gamma_mask = occupied_gamma_mask_checkerboard(TT)
    neel = FockState(NSITES, :checkerboard, true; nx=L)
    neel.occupied_sites == occupied_gamma_mask ||
        error("independent checkerboard occupation mask differs from upstream")
    exact_center = zero(Q)
    p2_expectation = 0.0
    p2_expectation_stream = SHA.SHA2_256_CTX()
    expectation_hasher = CanonicalArrayHasher()
    for (mask, coefficient) in final_rows
        coefficient isa Float64 || error("unexpected P3 final coefficient type")
        isfinite(coefficient) || error("non-finite P3 final coefficient")
        independent_element = independent_fock_diagonal(mask, occupied_gamma_mask)
        upstream_element = MajoranaPropagation.overlapwithfock(mask, neel, neel, NMODES)
        imag(upstream_element) == 0.0 || error("non-real upstream P3 Fock element")
        upstream_integer = Int(round(real(upstream_element)))
        upstream_integer in (-1, 0, 1) || error("unexpected upstream P3 Fock element")
        upstream_integer == independent_element ||
            error("independent P3 Fock diagonal mismatch")
        exact_contribution = exact_float_q(coefficient) * BigInt(independent_element)
        exact_center += exact_contribution
        float_contribution = coefficient * real(upstream_element)
        p2_expectation += float_contribution
        SHA.update!(p2_expectation_stream, codeunits(mask_hex(mask)))
        SHA.update!(p2_expectation_stream, UInt8['\t'])
        SHA.update!(p2_expectation_stream, codeunits(float_bits_hex(float_contribution)))
        SHA.update!(p2_expectation_stream, UInt8['\n'])
        push_canonical_row!(expectation_hasher, (
            mask_hex=mask_hex(mask),
            coefficient_Float64_bits_hex=float_bits_hex(coefficient),
            fock_diagonal_element=independent_element,
            exact_dyadic_contribution=format_q(exact_contribution),
        ))
    end
    expectation_rows_digest = finish_canonical_array!(expectation_hasher)
    center_lower_ticks = floor_grid(exact_center)
    center_upper_ticks = upper_grid(exact_center)
    check_bigint_cap!(center_lower_ticks, maximum_bits,
        (operation="final_center_lower_ticks",))
    check_bigint_cap!(center_upper_ticks, maximum_bits,
        (operation="final_center_upper_ticks",))
    error_ticks = total_ticks(execution.ticks)
    declared_lower_ticks = center_lower_ticks - error_ticks
    declared_upper_ticks = center_upper_ticks + error_ticks
    check_bigint_cap!(declared_lower_ticks, maximum_bits,
        (operation="declared_expectation_lower_ticks",))
    check_bigint_cap!(declared_upper_ticks, maximum_bits,
        (operation="declared_expectation_upper_ticks",))

    final_state = (
        retained_term_count=length(final_rows),
        term_stream_sha256=term_stream_sha256(final_rows),
        checkerboard_Neel_occupied_mask_hex=mask_hex(neel.occupied_sites),
        checkerboard_Neel_independent_occupied_gamma_mask_hex=
            mask_hex(occupied_gamma_mask),
        checkerboard_Neel_up_count=32,
        checkerboard_Neel_down_count=32,
        checkerboard_Neel_expectation_Float64_diagnostic_bits_hex=
            float_bits_hex(p2_expectation),
        checkerboard_Neel_contribution_stream_sha256=
            bytes2hex(SHA.digest!(p2_expectation_stream)),
        checkerboard_Neel_expectation_rows_sha256=expectation_rows_digest,
        checkerboard_Neel_exact_dyadic_center=format_q(exact_center),
        center_lower_ticks=string(center_lower_ticks),
        center_upper_ticks=string(center_upper_ticks),
        declared_expectation_lower_ticks=string(declared_lower_ticks),
        declared_expectation_upper_ticks=string(declared_upper_ticks),
        declared_expectation_interval=(
            lower=format_q(declared_lower_ticks // P3_GRID_DENOMINATOR),
            upper=format_q(declared_upper_ticks // P3_GRID_DENOMINATOR),
        ),
        Float64_reduction_is_diagnostic_only=true,
        exact_dyadic_center_and_declared_interval_are_authoritative=true,
    )
    return final_state, final_cap_event
end

function build_execution_witness(execution, cap_event)
    accuracy_transition_digest = canonical_sha256(execution.transition_records)
    accuracy_boundary_digest = canonical_sha256(execution.boundary_records)
    accuracy_stage_digest = canonical_sha256(execution.stage_records)
    return (
        completed_composite_count=execution.completed_composites,
        completed_constituent_count=execution.completed_constituents,
        completed_truncation_boundary_count=execution.completed_boundaries,
        peak_premerge_contribution_count=execution.peak_premerge,
        peak_postmerge_unique_term_count=execution.peak_postmerge,
        anticommuting_split_count=execution.total_splits,
        threshold_dropped_term_count=execution.total_threshold_drops,
        exact_zero_dropped_term_count=execution.total_zero_drops,
        cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex=
            float_bits_hex(execution.cumulative_drop_diagnostic),
        P2_resource_counters=public_counters(execution.p2_counters),
        accuracy_counters=public_accuracy_counters(execution.accuracy_counters),
        total_P2_plus_accuracy_charged_event_count=
            charged_total(execution.p2_counters) +
            accuracy_charged(execution.accuracy_counters),
        P2_transition_records_sha256=execution.p2_transition_records_sha256,
        P2_boundary_records_sha256=execution.p2_boundary_records_sha256,
        P2_stage_records_sha256=execution.p2_stage_records_sha256,
        transition_records=execution.transition_records,
        transition_records_sha256=accuracy_transition_digest,
        boundary_records=execution.boundary_records,
        boundary_records_sha256=accuracy_boundary_digest,
        stage_records=execution.stage_records,
        stage_records_sha256=accuracy_stage_digest,
        cap_event=cap_event,
    )
end

function build_accuracy_ledger(execution, within_allocation)
    counters = public_accuracy_counters(execution.accuracy_counters)
    ticks = public_ticks(execution.ticks)
    allocation_upper_ticks = cld(P3_GRID_DENOMINATOR, P3_ALLOCATION_DENOMINATOR)
    return merge(counters, ticks, (
        grid_denominator=string(P3_GRID_DENOMINATOR),
        allocation_rational="1/400000",
        allocation_grid_ceiling_ticks_diagnostic_only=string(allocation_upper_ticks),
        strictly_within_allocation=within_allocation,
        strict_comparison=
            "total_operator_error_ticks_times_400000_strictly_less_than_2_pow_128",
        outward_widening_is_absorbed_in_each_local_upper_not_added_again=true,
        coefficient_L1_bounds_operator_norm=true,
        no_future_L1_amplification_from_exact_unitary_conjugation=true,
    ))
end

function main_p3()
    length(ARGS) == 2 ||
        error("usage: majorana_p3_runner.jl P3_FIXTURE.json P2_FIXTURE.json")
    P3_fixture_path = abspath(ARGS[1])
    P2_fixture_path = abspath(ARGS[2])
    fixture = validate_p3_fixture(JSON.parsefile(P3_fixture_path))
    p2_fixture = validate_inherited_p2_fixture(
        JSON.parsefile(P2_fixture_path), fixture, P2_fixture_path,
    )
    active_project = Base.active_project()
    active_project === nothing && error("P3 runner requires an active project")
    manifest_path = joinpath(dirname(active_project), "Manifest.toml")
    isfile(manifest_path) || error("P3 Manifest.toml missing")
    Threads.nthreads() == 1 || error("formal P3 runner requires exactly one Julia thread")
    rounding(Float64) == RoundNearest ||
        error("formal P3 runner requires Float64 round-to-nearest-ties-to-even")
    image_file = unsafe_string(Base.JLOptions().image_file)
    julia_executable = joinpath(Sys.BINDIR, Base.julia_exename())
    mp_path = pathof(MajoranaPropagation)
    pp_path = pathof(MajoranaPropagation.PauliPropagation)

    reinterpret(UInt64, EPSILON) == 0x3dd0000000000000 ||
        error("P3 threshold bits drift")
    maximum_bits = Int(fixture["outward_arithmetic"]["maximum_BigInt_bit_length"])
    trig_lookup, trig_table = build_trig_table(fixture, maximum_bits)
    stages, schedule = build_schedule()
    observable, initial = initial_observable()
    execution = execute_p3(stages, fixture, observable, trig_lookup)
    final_state, final_cap_event = finalize_p3_state!(execution, fixture)
    cap_event = execution.cap_event === nothing ? final_cap_event : execution.cap_event
    if execution.cap_event !== nothing && final_cap_event !== nothing
        error("P3 produced two deterministic cap events")
    end

    within_allocation = cap_event === nothing ?
        total_ticks(execution.ticks) * P3_ALLOCATION_DENOMINATOR <
            P3_GRID_DENOMINATOR : nothing
    terminal_branch = cap_event !== nothing ? "DETERMINISTIC_POLICY_CAP_EXCEEDED" :
        within_allocation ? "BOUND_WITHIN_PREFIX_ALLOCATION" :
        "BOUND_EXCEEDS_PREFIX_ALLOCATION"
    status = terminal_branch == "DETERMINISTIC_POLICY_CAP_EXCEEDED" ? P3_CAP_STATUS :
        terminal_branch == "BOUND_WITHIN_PREFIX_ALLOCATION" ? P3_WITHIN_STATUS :
        P3_EXCEEDS_STATUS
    execution_witness = build_execution_witness(execution, cap_event)
    accuracy_ledger = build_accuracy_ledger(execution, within_allocation)
    scope = (
        maximum_positive_status=P3_WITHIN_STATUS,
        fixed_L8_first_fused_mapped_step_exact_prefix_only=true,
        freshly_executed_Float64_threshold_path="ASSESSED_BY_LOCAL_DEFECT_AND_DROP_BOUND",
        operator_norm_error_enclosure="ASSESSED",
        checkerboard_Neel_expectation_enclosure="ASSESSED",
        global_coefficientwise_interval_state="NOT_CLAIMED",
        exact_arithmetic_threshold_drop_set="NOT_CLAIMED_EQUAL",
        raw_1280_constituent_threshold_path="NOT_EXECUTED",
        double_occupancy="NOT_ASSESSED",
        existing_Python_topL1_route_result_equality="NOT_CLAIMED",
        remaining_99_mapped_steps_or_full_R100="NOT_ASSESSED",
        product_formula_to_exact_Hubbard_error="NOT_ASSESSED",
        physical_reference_qualified=false,
        ready_gate_eligible=false,
    )
    witness = (
        schema_version=1,
        witness_type="majorana_p3_L8_one_fused_step_local_defect_v1",
        fixture_id=String(fixture["fixture_id"]),
        fixture_sha256=file_sha256(P3_fixture_path),
        fixture_canonical_sha256=canonical_sha256(fixture),
        inherited_P2_fixture_sha256=file_sha256(P2_fixture_path),
        inherited_P2_fixture_canonical_sha256=canonical_sha256(p2_fixture),
        terminal_branch=terminal_branch,
        status=status,
        runtime=(
            julia_version=string(VERSION),
            julia_commit=String(Base.GIT_VERSION_INFO.commit_short),
            machine=String(Sys.MACHINE),
            threads=Threads.nthreads(),
            executable_sha256=file_sha256(julia_executable),
            sysimage_sha256=file_sha256(image_file),
            project_sha256=file_sha256(active_project),
            manifest_sha256=file_sha256(manifest_path),
        ),
        upstream=(
            majorana_propagation_version=string(Base.pkgversion(MajoranaPropagation)),
            pauli_propagation_version=string(Base.pkgversion(MajoranaPropagation.PauliPropagation)),
            majorana_source_closure=source_tree_closure(mp_path),
            pauli_source_closure=source_tree_closure(pp_path),
        ),
        initial_observable=initial,
        schedule=schedule,
        trig_table=trig_table,
        execution=execution_witness,
        accuracy_ledger=accuracy_ledger,
        final_state=final_state,
        scope=scope,
    )
    print(canonical_json(witness))
    print('\n')
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main_p3()
end
