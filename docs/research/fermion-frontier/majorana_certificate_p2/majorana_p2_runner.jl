#!/usr/bin/env julia

using JSON
using MajoranaPropagation
using SHA

const Q = Rational{BigInt}
const L = 8
const NSITES = 64
const NMODES = 128
const MASK_HEX_DIGITS = 64
const EPSILON = ldexp(1.0, -34)
const STAGE_GROUPS = ("H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1")
const FIXTURE_CANONICAL_SHA256 = "a8b0df9fd66bfaa5e1c1602fce4896de174b06e63a972f66f19fb1fe60fb3c01"
const MAXIMUM_STATUS = "VERIFIED_MAJORANA_P2_L8_STAGGERED_MAGNETIZATION_ONE_STEP_BOUNDED_PREFIX_RESOURCE_FEASIBILITY_SUBCERTIFICATE"

function parse_q(value::AbstractString)::Q
    parts = split(value, '/'; keepempty=true)
    length(parts) == 1 && return parse(BigInt, parts[1]) // BigInt(1)
    length(parts) == 2 || error("invalid rational")
    denominator_value = parse(BigInt, parts[2])
    denominator_value > 0 || error("rational denominator must be positive")
    return parse(BigInt, parts[1]) // denominator_value
end

function format_q(value::Q)::String
    denominator(value) == 1 && return string(numerator(value))
    return string(numerator(value), '/', denominator(value))
end

function exact_float_rational(value::Float64)::Q
    isfinite(value) || error("non-finite upstream constructor coefficient")
    return rationalize(BigInt, value; tol=0)
end

function write_canonical_json(io::IO, value)
    if value === nothing
        print(io, "null")
    elseif value isa Bool
        print(io, value ? "true" : "false")
    elseif value isa Integer
        print(io, value)
    elseif value isa AbstractString || value isa Symbol
        print(io, JSON.json(String(value)))
    elseif value isa NamedTuple
        print(io, '{')
        names = sort!(collect(keys(value)); by=String)
        for (index, name) in enumerate(names)
            index > 1 && print(io, ',')
            print(io, JSON.json(String(name)), ':')
            write_canonical_json(io, getproperty(value, name))
        end
        print(io, '}')
    elseif value isa AbstractDict
        pairs = sort!(collect(value); by=pair -> String(first(pair)))
        length(unique(String(first(pair)) for pair in pairs)) == length(pairs) ||
            error("canonical JSON object has duplicate stringified keys")
        print(io, '{')
        for (index, pair) in enumerate(pairs)
            index > 1 && print(io, ',')
            print(io, JSON.json(String(first(pair))), ':')
            write_canonical_json(io, last(pair))
        end
        print(io, '}')
    elseif value isa AbstractVector || value isa Tuple
        print(io, '[')
        for (index, item) in enumerate(value)
            index > 1 && print(io, ',')
            write_canonical_json(io, item)
        end
        print(io, ']')
    else
        error("unsupported canonical JSON type: $(typeof(value))")
    end
end

function canonical_json(value)::String
    io = IOBuffer()
    write_canonical_json(io, value)
    return String(take!(io))
end

canonical_sha256(value) = bytes2hex(sha256(canonical_json(value)))
file_sha256(path::AbstractString) = bytes2hex(sha256(read(path)))

function source_tree_closure(module_path::AbstractString)
    root = dirname(dirname(module_path))
    rows = NamedTuple[]
    total_bytes = 0
    paths = String[]
    for (directory, directories, files) in walkdir(root; follow_symlinks=false)
        sort!(directories)
        sort!(files)
        for filename in files
            path = joinpath(directory, filename)
            islink(path) && error("package source closure contains a symlink")
            isfile(path) || error("package source closure contains a non-file")
            push!(paths, path)
        end
    end
    sort!(paths; by=path -> relpath(path, root))
    for path in paths
        body = read(path)
        total_bytes += length(body)
        metadata = stat(path)
        push!(rows, (
            path=replace(relpath(path, root), '\\' => '/'),
            mode=Int(metadata.mode & 0o777),
            size=length(body),
            sha256=bytes2hex(sha256(body)),
        ))
    end
    return (
        file_count=length(rows),
        total_bytes=total_bytes,
        closure_sha256=canonical_sha256(rows),
    )
end

mask_hex(mask::Integer) = lpad(string(mask; base=16), MASK_HEX_DIGITS, '0')
float_bits_hex(value::Float64) = lpad(string(reinterpret(UInt64, value); base=16), 16, '0')

function term_stream_sha256(rows)
    context = SHA.SHA2_256_CTX()
    for (mask, coefficient) in rows
        SHA.update!(context, codeunits(mask_hex(mask)))
        SHA.update!(context, UInt8['\t'])
        SHA.update!(context, codeunits(float_bits_hex(coefficient)))
        SHA.update!(context, UInt8['\n'])
    end
    return bytes2hex(SHA.digest!(context))
end

function validate_fixture(fixture)
    canonical_sha256(fixture) == FIXTURE_CANONICAL_SHA256 ||
        error("P2 fixture differs from the frozen semantic object")
    fixture["schema_version"] == 1 || error("unexpected fixture schema")
    fixture["fixture_id"] == "MAJORANA-P2-L8-FUSED-ONE-STEP-RESOURCE-PREFIX-V1" ||
        error("unexpected fixture identity")
    lattice = fixture["lattice_and_observable"]
    lattice["linear_size"] == L || error("unexpected linear size")
    lattice["n_sites"] == NSITES || error("unexpected site count")
    lattice["n_modes"] == NMODES || error("unexpected mode count")
    lattice["observable_initial_nonzero_term_count"] == 128 ||
        error("unexpected initial term count")
    prefix = fixture["heisenberg_prefix"]
    Tuple(String.(prefix["stage_order"])) == STAGE_GROUPS || error("unexpected stage order")
    prefix["planned_composite_count"] == 512 || error("unexpected composite count")
    prefix["planned_constituent_count"] == 1152 || error("unexpected constituent count")
    prefix["planned_truncation_boundary_count"] == 768 || error("unexpected boundary count")
    execution = fixture["execution_semantics"]
    execution["threshold_rational"] == "1/17179869184" || error("unexpected threshold")
    execution["threshold_Float64_bits_hex"] == float_bits_hex(EPSILON) ||
        error("threshold Float64 bits mismatch")
    return fixture
end

function forward_group_specs(group::String)
    specs = NamedTuple[]
    if group == "HU"
        for site0 in 0:(NSITES - 1)
            row, column = divrem(site0, L)
            push!(specs, (
                operator_id="HU_r$(row)_c$(column)", symbol=:nupndn,
                sites=[site0 + 1], multiplier=BigInt(8) // BigInt(1),
            ))
        end
        return specs
    end
    horizontal = group == "H1" || group == "H2"
    parity = group == "H1" || group == "H4" ? 0 : 1
    if horizontal
        for row in 0:(L - 1), column in parity:2:(L - 2)
            left = row * L + column + 1
            right = left + 1
            for (spin, symbol) in (("up", :hopup), ("down", :hopdn))
                push!(specs, (
                    operator_id="$(group)_r$(row)_c$(column)_$(spin)", symbol=symbol,
                    sites=[left, right], multiplier=-BigInt(1) // BigInt(1),
                ))
            end
        end
    else
        for row in parity:2:(L - 2), column in 0:(L - 1)
            top = row * L + column + 1
            bottom = top + L
            for (spin, symbol) in (("up", :hopup), ("down", :hopdn))
                push!(specs, (
                    operator_id="$(group)_r$(row)_c$(column)_$(spin)", symbol=symbol,
                    sites=[top, bottom], multiplier=-BigInt(1) // BigInt(1),
                ))
            end
        end
    end
    return specs
end

function build_schedule()
    stages = Any[]
    public_composites = Any[]
    global_composite_index = 0
    global_constituent_index = 0
    global_boundary_index = 0
    theta_histogram = Dict{String,Int}()
    commutation_rows = NamedTuple[]
    for (stage_offset, group) in enumerate(STAGE_GROUPS)
        stage_index = stage_offset - 1
        duration = group == "H4" ? BigInt(1) // BigInt(100) : BigInt(1) // BigInt(200)
        composites = Any[]
        stage_masks = Any[]
        reversed_specs = reverse(forward_group_specs(group))
        for (occurrence_offset, spec) in enumerate(reversed_specs)
            rotations, coefficients, truncate_after_each =
                MajoranaPropagation.getmajoranarotations(
                    FermionicRotation(spec.symbol, spec.sites), NSITES,
                )
            pairs = [
                (rotation=rotation, constructor_coefficient=coefficient)
                for (rotation, coefficient) in zip(rotations, coefficients)
            ]
            sort!(pairs; by=row -> row.rotation.ms_int)
            length(unique(row.rotation.ms_int for row in pairs)) == length(pairs) ||
                error("constituent masks are not unique within a composite")
            expected_truncate_each = spec.symbol == :nupndn
            truncate_after_each == expected_truncate_each || error("upstream cadence mismatch")
            constituents = Any[]
            public_constituents = Any[]
            for (constituent_offset, pair) in enumerate(pairs)
                constructor_q = exact_float_rational(pair.constructor_coefficient)
                physical_theta = duration * spec.multiplier
                applied_q = physical_theta * constructor_q * 2
                applied_float = Float64(applied_q)
                isfinite(applied_float) || error("non-finite applied angle")
                theta_key = format_q(applied_q)
                theta_histogram[theta_key] = get(theta_histogram, theta_key, 0) + 1
                boundary_after = truncate_after_each || constituent_offset == length(pairs)
                boundary_index = boundary_after ? global_boundary_index : nothing
                public_row = (
                    constituent_index=global_constituent_index,
                    constituent_in_composite=constituent_offset - 1,
                    mask_hex=mask_hex(pair.rotation.ms_int),
                    constructor_coefficient=format_q(constructor_q),
                    applied_angle=format_q(applied_q),
                    applied_angle_Float64_bits_hex=float_bits_hex(applied_float),
                    boundary_after=boundary_after,
                    boundary_index_after=boundary_index,
                )
                push!(public_constituents, public_row)
                push!(constituents, (
                    rotation=pair.rotation,
                    applied_angle=applied_float,
                    public=public_row,
                ))
                push!(stage_masks, pair.rotation.ms_int)
                global_constituent_index += 1
                boundary_after && (global_boundary_index += 1)
            end
            public_composite = (
                stage_index=stage_index,
                group=group,
                composite_index=global_composite_index,
                occurrence_in_stage=occurrence_offset - 1,
                operator_id=spec.operator_id,
                symbol=String(spec.symbol),
                sites=spec.sites,
                event_duration=format_q(duration),
                physical_theta=format_q(duration * spec.multiplier),
                truncate_after_each_constituent=truncate_after_each,
                constituents=public_constituents,
            )
            push!(public_composites, public_composite)
            push!(composites, (
                public=public_composite,
                constituents=constituents,
            ))
            global_composite_index += 1
        end
        length(unique(stage_masks)) == length(stage_masks) ||
            error("stage contains duplicate Majorana generator masks")
        pair_count = 0
        for left in 1:length(stage_masks), right in (left + 1):length(stage_masks)
            right > length(stage_masks) && continue
            MajoranaPropagation.commutes(stage_masks[left], stage_masks[right]) ||
                error("frozen stage contains noncommuting generators")
            pair_count += 1
        end
        push!(commutation_rows, (
            stage_index=stage_index,
            group=group,
            generator_count=length(stage_masks),
            unordered_pair_count=pair_count,
            masks_sha256=canonical_sha256(mask_hex.(sort(stage_masks))),
            all_pairs_commute=true,
        ))
        push!(stages, (stage_index=stage_index, group=group, composites=composites))
    end
    global_composite_index == 512 || error("schedule composite total mismatch")
    global_constituent_index == 1152 || error("schedule constituent total mismatch")
    global_boundary_index == 768 || error("schedule boundary total mismatch")
    expected_histogram = Dict(
        "-1/100" => 64, "-1/200" => 320, "-1/50" => 128,
        "1/100" => 64, "1/200" => 320, "1/50" => 256,
    )
    theta_histogram == expected_histogram || error("applied-angle histogram mismatch")
    public_schedule = (
        stage_groups=collect(STAGE_GROUPS),
        stage_count=length(STAGE_GROUPS),
        composite_count=global_composite_index,
        constituent_count=global_constituent_index,
        truncation_boundary_count=global_boundary_index,
        theta_histogram=theta_histogram,
        composites=public_composites,
        composites_sha256=canonical_sha256(public_composites),
        stage_commutation=commutation_rows,
        stage_commutation_sha256=canonical_sha256(commutation_rows),
        central_H4_fused_before_execution=true,
        raw_and_fused_exact_stage_unitary_equal_from_internal_commutation=true,
        raw_and_fused_threshold_paths_identical=false,
    )
    return stages, public_schedule
end

function initial_observable()
    result = MajoranaSum(Float64, NSITES, true)
    for site0 in 0:(NSITES - 1)
        row, column = divrem(site0, L)
        sign = iseven(row + column) ? 1.0 : -1.0
        add!(result, (sign / NSITES) * MajoranaSum(NSITES, :nup, site0 + 1))
        add!(result, (-sign / NSITES) * MajoranaSum(NSITES, :ndn, site0 + 1))
    end
    TT = getinttype(NMODES)
    identity_coefficient = get(result.Majoranas, zero(TT), NaN)
    identity_coefficient == 0.0 || error("initial observable identity did not cancel exactly")
    delete!(result.Majoranas, zero(TT))
    length(result) == 128 || error("initial observable nonzero term count mismatch")
    for coefficient in values(result.Majoranas)
        abs(coefficient) == 1.0 / 128.0 || error("initial observable coefficient mismatch")
    end
    rows = sort!(collect(result.Majoranas); by=first)
    return result, (
        nonzero_term_count=length(rows),
        initial_exact_zero_identity_prune_count=1,
        term_stream_sha256=term_stream_sha256(rows),
    )
end

struct CapExceeded <: Exception
    cap_name::String
    limit::Int
    attempted::Int
    context
end

mutable struct ResourceCounters
    cap_scan_term_visits::Int
    propagation_term_visits::Int
    truncation_term_visits::Int
    final_evaluation_term_visits::Int
end

ResourceCounters() = ResourceCounters(0, 0, 0, 0)

charged_total(counters::ResourceCounters) =
    counters.cap_scan_term_visits + counters.propagation_term_visits +
    counters.truncation_term_visits + counters.final_evaluation_term_visits

function public_counters(counters::ResourceCounters)
    return (
        cap_scan_term_visits=counters.cap_scan_term_visits,
        propagation_term_visits=counters.propagation_term_visits,
        truncation_term_visits=counters.truncation_term_visits,
        final_evaluation_term_visits=counters.final_evaluation_term_visits,
        total_charged_term_visits=charged_total(counters),
    )
end

function check_value_cap(name::String, attempted::Int, limit::Int, context)
    attempted <= limit || throw(CapExceeded(name, limit, attempted, context))
end

function charge!(
    counters::ResourceCounters, field::Symbol, amount::Int, field_limit::Int,
    total_limit::Int, context,
)
    current = getfield(counters, field)
    attempted = current + amount
    attempted <= field_limit ||
        throw(CapExceeded(String(field), field_limit, attempted, context))
    attempted_total = charged_total(counters) + amount
    attempted_total <= total_limit ||
        throw(CapExceeded("total_charged_term_visits", total_limit, attempted_total, context))
    setfield!(counters, field, attempted)
end

function dropped_rows_digest!(rows)
    sort!(rows; by=first)
    digest = term_stream_sha256(rows)
    diagnostic_sum = 0.0
    zero_count = 0
    for (_mask, coefficient) in rows
        iszero(coefficient) && (zero_count += 1)
        diagnostic_sum += abs(coefficient)
    end
    return digest, diagnostic_sum, zero_count
end

function execute_prefix(stages, fixture, observable)
    caps = fixture["deterministic_resource_caps"]
    max_boundary = Int(caps["maximum_boundary_retained_terms"])
    max_current = Int(caps["maximum_current_terms_before_constituent"])
    max_premerge = Int(caps["maximum_premerge_terms"])
    max_scan_visits = Int(caps["maximum_cap_scan_term_visits"])
    max_propagation_visits = Int(caps["maximum_propagation_term_visits"])
    max_truncation_visits = Int(caps["maximum_truncation_term_visits"])
    max_total_visits = Int(caps["maximum_total_charged_term_visits"])

    cache = MajoranaPropagationCache(observable)
    counters = ResourceCounters()
    transition_records = Any[]
    boundary_records = Any[]
    stage_records = Any[]
    peak_premerge = length(observable)
    peak_postmerge = length(observable)
    total_splits = 0
    total_threshold_drops = 0
    total_zero_drops = 0
    cumulative_drop_diagnostic = 0.0
    cap_event = nothing
    completed_composites = 0
    completed_constituents = 0
    completed_boundaries = 0

    try
        for stage in stages
            stage_input_count = length(MajoranaPropagation.PropagationBase.mainsum(cache))
            stage_peak_premerge = stage_input_count
            stage_peak_postmerge = stage_input_count
            stage_splits_before = total_splits
            stage_drops_before = total_threshold_drops
            stage_counters_before = public_counters(counters)
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
                    isempty(aux_sum.Majoranas) || error("auxiliary sum is nonempty before apply")
                    input_count = length(main_sum)
                    check_value_cap("maximum_current_terms_before_constituent", input_count, max_current, context)
                    charge!(
                        counters, :cap_scan_term_visits, input_count, max_scan_visits,
                        max_total_visits, merge(context, (operation="predictive_anticommutation_scan",)),
                    )
                    anticommuting_count = 0
                    for mask in keys(main_sum.Majoranas)
                        !MajoranaPropagation.commutes(constituent.rotation.ms_int, mask) &&
                            (anticommuting_count += 1)
                    end
                    predicted_premerge = input_count + anticommuting_count
                    check_value_cap("maximum_premerge_terms", predicted_premerge, max_premerge, context)
                    charge!(
                        counters, :propagation_term_visits, input_count,
                        max_propagation_visits, max_total_visits,
                        merge(context, (operation="upstream_applytoall",)),
                    )
                    MajoranaPropagation.PropagationBase.applytoall!(
                        constituent.rotation, cache, constituent.applied_angle,
                    )
                    actual_main_count = length(MajoranaPropagation.PropagationBase.mainsum(cache))
                    actual_aux_count = length(MajoranaPropagation.PropagationBase.auxsum(cache))
                    actual_main_count == input_count || error("applytoall changed main term cardinality")
                    actual_aux_count == anticommuting_count ||
                        error("predictive anticommuting count differs from upstream split count")
                    premerge_count = actual_main_count + actual_aux_count
                    premerge_count == predicted_premerge || error("premerge contribution count mismatch")
                    peak_premerge = max(peak_premerge, premerge_count)
                    stage_peak_premerge = max(stage_peak_premerge, premerge_count)
                    total_splits += actual_aux_count
                    merge!(cache)
                    postmerge_count = length(MajoranaPropagation.PropagationBase.mainsum(cache))
                    postmerge_count <= premerge_count || error("merge increased term cardinality")
                    check_value_cap("maximum_premerge_terms", postmerge_count, max_premerge, context)
                    peak_postmerge = max(peak_postmerge, postmerge_count)
                    stage_peak_postmerge = max(stage_peak_postmerge, postmerge_count)

                    boundary_record = nothing
                    if public.boundary_after
                        charge!(
                            counters, :truncation_term_visits, postmerge_count,
                            max_truncation_visits, max_total_visits,
                            merge(context, (operation="threshold_callback_scan",)),
                        )
                        dropped = Tuple{typeof(constituent.rotation.ms_int),Float64}[]
                        callback_visits = Ref(0)
                        callback = function (mask, coefficient)
                            coefficient isa Float64 || error("unexpected coefficient type")
                            isfinite(coefficient) || error("non-finite coefficient at threshold boundary")
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
                            error("threshold callback did not visit every postmerge term")
                        retained_count = length(MajoranaPropagation.PropagationBase.mainsum(cache))
                        retained_count + length(dropped) == postmerge_count ||
                            error("threshold retained plus dropped count mismatch")
                        check_value_cap(
                            "maximum_boundary_retained_terms", retained_count, max_boundary,
                            merge(context, (operation="post_threshold_retained_state",)),
                        )
                        dropped_digest, diagnostic_increment, zero_drop_count =
                            dropped_rows_digest!(dropped)
                        cumulative_drop_diagnostic += diagnostic_increment
                        total_threshold_drops += length(dropped)
                        total_zero_drops += zero_drop_count
                        boundary_record = (
                            boundary_index=public.boundary_index_after,
                            stage_index=stage.stage_index,
                            group=stage.group,
                            composite_index=composite.public.composite_index,
                            after_constituent_index=public.constituent_index,
                            boundary_kind=composite.public.truncate_after_each_constituent ?
                                "after_constituent" : "after_complete_composite",
                            postmerge_term_count=postmerge_count,
                            retained_term_count=retained_count,
                            threshold_dropped_term_count=length(dropped),
                            exact_zero_dropped_term_count=zero_drop_count,
                            dropped_term_stream_sha256=dropped_digest,
                            dropped_abs_sum_Float64_diagnostic_bits_hex=float_bits_hex(diagnostic_increment),
                            cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex=
                                float_bits_hex(cumulative_drop_diagnostic),
                        )
                        push!(boundary_records, boundary_record)
                        completed_boundaries += 1
                    end
                    push!(transition_records, (
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
                        retained_term_count_after_boundary=
                            boundary_record === nothing ? nothing : boundary_record.retained_term_count,
                    ))
                    completed_constituents += 1
                end
                completed_composites += 1
            end
            counters_after = public_counters(counters)
            push!(stage_records, (
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
                    counters_after.cap_scan_term_visits - stage_counters_before.cap_scan_term_visits,
                propagation_term_visits_increment=
                    counters_after.propagation_term_visits - stage_counters_before.propagation_term_visits,
                truncation_term_visits_increment=
                    counters_after.truncation_term_visits - stage_counters_before.truncation_term_visits,
            ))
        end
    catch error_value
        if error_value isa CapExceeded
            cap_event = (
                cap_name=error_value.cap_name,
                limit=error_value.limit,
                attempted=error_value.attempted,
                context=error_value.context,
                operation_was_not_executed_after_cap_detection=true,
            )
        else
            rethrow()
        end
    end

    outcome = cap_event === nothing ? "PREFIX_COMPLETED_UNDER_CAPS" :
        "DETERMINISTIC_POLICY_CAP_EXCEEDED"
    final_state = nothing
    if cap_event === nothing
        completed_composites == 512 || error("completed composite count mismatch")
        completed_constituents == 1152 || error("completed constituent count mismatch")
        completed_boundaries == 768 || error("completed boundary count mismatch")
        final_sum = MajoranaPropagation.PropagationBase.mainsum(cache)
        final_rows = sort!(collect(final_sum.Majoranas); by=first)
        charge!(
            counters, :final_evaluation_term_visits, length(final_rows), max_boundary,
            max_total_visits, (operation="sorted_final_digest_and_Neel_diagnostic",),
        )
        neel = FockState(NSITES, :checkerboard, true; nx=L)
        expectation = 0.0
        expectation_stream = SHA.SHA2_256_CTX()
        for (mask, coefficient) in final_rows
            isfinite(coefficient) || error("non-finite final coefficient")
            matrix_element = MajoranaPropagation.overlapwithfock(mask, neel, neel, NMODES)
            imag(matrix_element) == 0.0 || error("non-real diagonal Fock matrix element")
            contribution = coefficient * real(matrix_element)
            expectation += contribution
            SHA.update!(expectation_stream, codeunits(mask_hex(mask)))
            SHA.update!(expectation_stream, UInt8['\t'])
            SHA.update!(expectation_stream, codeunits(float_bits_hex(contribution)))
            SHA.update!(expectation_stream, UInt8['\n'])
        end
        final_state = (
            retained_term_count=length(final_rows),
            term_stream_sha256=term_stream_sha256(final_rows),
            checkerboard_Neel_occupied_mask_hex=mask_hex(neel.occupied_sites),
            checkerboard_Neel_up_count=32,
            checkerboard_Neel_down_count=32,
            checkerboard_Neel_expectation_Float64_diagnostic_bits_hex=float_bits_hex(expectation),
            checkerboard_Neel_contribution_stream_sha256=bytes2hex(SHA.digest!(expectation_stream)),
            expectation_is_diagnostic_not_scientific_authority=true,
        )
    end
    resources = (
        completed_composite_count=completed_composites,
        completed_constituent_count=completed_constituents,
        completed_truncation_boundary_count=completed_boundaries,
        peak_premerge_contribution_count=peak_premerge,
        peak_postmerge_unique_term_count=peak_postmerge,
        anticommuting_split_count=total_splits,
        threshold_dropped_term_count=total_threshold_drops,
        exact_zero_dropped_term_count=total_zero_drops,
        cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex=
            float_bits_hex(cumulative_drop_diagnostic),
        counters=public_counters(counters),
        transition_records=transition_records,
        transition_records_sha256=canonical_sha256(transition_records),
        boundary_records=boundary_records,
        boundary_records_sha256=canonical_sha256(boundary_records),
        stage_records=stage_records,
        stage_records_sha256=canonical_sha256(stage_records),
        cap_event=cap_event,
    )
    return outcome, resources, final_state
end

function main()
    length(ARGS) == 1 || error("usage: majorana_p2_runner.jl FIXTURE.json")
    fixture_path = abspath(ARGS[1])
    fixture = validate_fixture(JSON.parsefile(fixture_path))
    active_project = Base.active_project()
    active_project === nothing && error("runner requires an active project")
    manifest_path = joinpath(dirname(active_project), "Manifest.toml")
    isfile(manifest_path) || error("Manifest.toml missing")
    Threads.nthreads() == 1 || error("formal P2 runner requires exactly one Julia thread")
    image_file = unsafe_string(Base.JLOptions().image_file)
    julia_executable = joinpath(Sys.BINDIR, Base.julia_exename())
    mp_path = pathof(MajoranaPropagation)
    pp_path = pathof(MajoranaPropagation.PauliPropagation)

    reinterpret(UInt64, EPSILON) == 0x3dd0000000000000 || error("threshold bits drift")
    stages, schedule = build_schedule()
    observable, initial = initial_observable()
    outcome, resources, final_state = execute_prefix(stages, fixture, observable)
    scope = (
        maximum_positive_status=MAXIMUM_STATUS,
        fixed_L8_first_fused_mapped_step_Float64_resource_feasibility_only=true,
        binary64_coefficient_accuracy="NOT_ASSESSED",
        threshold_drop_is_a_certified_error_bound=false,
        raw_1280_constituent_threshold_path="NOT_EXECUTED",
        existing_Python_topL1_route_result_equality="NOT_CLAIMED",
        double_occupancy="NOT_ASSESSED",
        remaining_99_mapped_steps="NOT_ASSESSED",
        product_formula_to_exact_Hubbard_error="NOT_ASSESSED",
        exact_time_evolution="NOT_ASSESSED",
        physical_reference_qualified=false,
        ready_gate_eligible=false,
    )
    witness = (
        schema_version=1,
        witness_type="majorana_p2_L8_one_step_Float64_resource_feasibility_v1",
        fixture_id=String(fixture["fixture_id"]),
        fixture_sha256=file_sha256(fixture_path),
        fixture_canonical_sha256=canonical_sha256(fixture),
        outcome=outcome,
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
        execution=resources,
        final_state=final_state,
        scope=scope,
    )
    print(canonical_json(witness))
    print('\n')
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main()
end
