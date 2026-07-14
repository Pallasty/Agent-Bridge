#!/usr/bin/env julia

using JSON
using MajoranaPropagation
using SHA

const Q = Rational{BigInt}
const Interval = Tuple{Q,Q}

function parse_q(value::AbstractString)::Q
    parts = split(value, '/'; keepempty=true)
    if length(parts) == 1
        return parse(BigInt, parts[1]) // BigInt(1)
    elseif length(parts) == 2
        denominator = parse(BigInt, parts[2])
        denominator > 0 || error("rational denominator must be positive")
        return parse(BigInt, parts[1]) // denominator
    end
    error("invalid rational")
end

function format_q(value::Q)::String
    denominator(value) == 1 && return string(numerator(value))
    return string(numerator(value), '/', denominator(value))
end

interval_json(value::Interval) = (
    lower=format_q(value[1]),
    upper=format_q(value[2]),
)

function quantize_outward(value::Interval, denominator_grid::BigInt)
    lower, upper = value
    lower <= upper || error("reversed interval")
    lower_tick = fld(numerator(lower) * denominator_grid, denominator(lower))
    upper_tick = cld(numerator(upper) * denominator_grid, denominator(upper))
    rounded = (lower_tick // denominator_grid, upper_tick // denominator_grid)
    widening = (lower - rounded[1]) + (rounded[2] - upper)
    widening >= 0 || error("inward interval quantization")
    return rounded, widening
end

interval_add(left::Interval, right::Interval) = (
    left[1] + right[1], left[2] + right[2]
)

function interval_multiply(left::Interval, right::Interval)
    corners = Q[
        left[1] * right[1], left[1] * right[2],
        left[2] * right[1], left[2] * right[2],
    ]
    return (minimum(corners), maximum(corners))
end

function interval_scale(value::Interval, scale::Q)
    return scale >= 0 ? (value[1] * scale, value[2] * scale) :
        (value[2] * scale, value[1] * scale)
end

interval_abs_upper(value::Interval) = max(abs(value[1]), abs(value[2]))

function taylor_sin_cos(theta::Q, order::Int, denominator_grid::BigInt)
    abs(theta) <= 1 || error("Taylor fixture requires |theta| <= 1")
    sin_point = zero(Q)
    cos_point = zero(Q)
    for k in 0:order
        sin_point += (-1)^k * theta^(2k + 1) // factorial(big(2k + 1))
        cos_point += (-1)^k * theta^(2k) // factorial(big(2k))
    end
    sin_remainder = abs(theta)^(2order + 3) // factorial(big(2order + 3))
    cos_remainder = abs(theta)^(2order + 2) // factorial(big(2order + 2))
    sine, sine_widening = quantize_outward(
        (sin_point - sin_remainder, sin_point + sin_remainder), denominator_grid,
    )
    cosine, cosine_widening = quantize_outward(
        (cos_point - cos_remainder, cos_point + cos_remainder), denominator_grid,
    )
    return sine, cosine, sine_widening + cosine_widening
end

popcount_u(value::Integer) = count_ones(value)

function omega_l(left::Integer, right::Integer, nbits::Int)
    parity = 0
    for i in 0:(nbits - 1)
        ((left >> i) & 1) == 0 && continue
        for j in 0:(i - 1)
            parity ⊻= Int((right >> j) & 1)
        end
    end
    return parity
end

omega_l_self(value::Integer) = mod((popcount_u(value)^2 - popcount_u(value)) ÷ 2, 2)
omega(left::Integer, right::Integer) = mod(
    popcount_u(left) * popcount_u(right) - popcount_u(left & right), 2,
)

function independent_multiply(left::Integer, right::Integer, nfermions::Int)
    result = left ⊻ right
    f = omega_l_self(left) * omega_l_self(right) +
        omega(left, right) * (omega_l_self(left) + omega_l_self(right) + 1)
    sign = isodd(omega_l(left, right, 2nfermions) + f) ? -1 : 1
    return omega(left, right) == 1 ? (sign * im, result) : (sign, result)
end

function phase_string(value)
    value == 1 && return "1"
    value == -1 && return "-1"
    value == im && return "i"
    value == -im && return "-i"
    error("unexpected Majorana phase")
end

function branch_sign(value)
    value == im && return -1
    value == -im && return 1
    error("anticommuting branch must have imaginary phase")
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

function canonical_json(value)
    io = IOBuffer()
    write_canonical_json(io, value)
    return String(take!(io))
end
canonical_sha256(value) = bytes2hex(sha256(canonical_json(value)))

function term_rows(expansion::Dict{UInt64,Interval})
    return [
        (mask=Int(mask), coefficient_interval=interval_json(expansion[mask]))
        for mask in sort!(collect(keys(expansion)))
    ]
end

terms_sha256(expansion::Dict{UInt64,Interval}) = canonical_sha256(term_rows(expansion))

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

function primitive_algebra(nfermions::Int, mask_minimum::Int, mask_maximum::Int)
    rows = NamedTuple[]
    pair_count = 0
    for left in mask_minimum:mask_maximum, right in mask_minimum:mask_maximum
        upstream_phase, upstream_result = MajoranaPropagation.ms_mult(
            UInt8(left), UInt8(right), nfermions,
        )
        upstream_commutes = MajoranaPropagation.commutes(UInt8(left), UInt8(right))
        local_phase, local_result = independent_multiply(left, right, nfermions)
        upstream_result == local_result || error("upstream multiplication mask mismatch")
        upstream_phase == local_phase || error("upstream multiplication phase mismatch")
        upstream_commutes == (omega(left, right) == 0) ||
            error("upstream commutation mismatch")
        push!(rows, (
            left=left,
            right=right,
            result=Int(upstream_result),
            phase=phase_string(upstream_phase),
            commutes=upstream_commutes,
        ))
        pair_count += 1
    end
    return (pair_count=pair_count, records_sha256=canonical_sha256(rows))
end

function primitive_rotations(fixture)
    primitive = fixture["primitive_conformance"]
    interval_policy = fixture["interval_policy"]
    nfermions = Int(primitive["n_fermions"])
    minimum_mask = Int(primitive["mask_minimum"])
    maximum_mask = Int(primitive["mask_maximum"])
    order = Int(interval_policy["taylor_order"])
    denominator_grid = parse(BigInt, interval_policy["outward_quantization_denominator"])
    rows = NamedTuple[]
    case_count = 0
    for gate in minimum_mask:maximum_mask
        gate == 0 && continue
        iseven(popcount_u(gate)) || continue
        for operator in minimum_mask:maximum_mask
            commutes = MajoranaPropagation.commutes(UInt8(gate), UInt8(operator))
            phase, result = independent_multiply(gate, operator, nfermions)
            for theta_text in primitive["angles_in_order"]
                theta = parse_q(theta_text)
                sine, cosine, _ = taylor_sin_cos(theta, order, denominator_grid)
                push!(rows, (
                    gate=gate,
                    operator=operator,
                    theta=theta_text,
                    commutes=commutes,
                    result=Int(result),
                    branch_sign=commutes ? 0 : branch_sign(phase),
                    sine=interval_json(sine),
                    cosine=interval_json(cosine),
                ))
                case_count += 1
            end
        end
    end
    return (case_count=case_count, records_sha256=canonical_sha256(rows))
end

function apply_rotation(
    expansion::Dict{UInt64,Interval}, gate_mask::UInt64, theta::Q,
    nfermions::Int, order::Int, denominator_grid::BigInt,
    rounding_widening::Base.RefValue{Q}, rounding_events::Base.RefValue{Int},
)
    sine, cosine, trig_widening = taylor_sin_cos(theta, order, denominator_grid)
    rounding_widening[] += trig_widening
    rounding_events[] += 2
    contributions = NamedTuple[]
    for source_mask in sort!(collect(keys(expansion)))
        coefficient = expansion[source_mask]
        if MajoranaPropagation.commutes(gate_mask, source_mask)
            push!(contributions, (
                mask=source_mask, source=source_mask, branch=0, interval=coefficient,
            ))
            continue
        end
        cosine_product, widening = quantize_outward(
            interval_multiply(coefficient, cosine), denominator_grid,
        )
        rounding_widening[] += widening
        rounding_events[] += 1
        phase, target_mask = independent_multiply(gate_mask, source_mask, nfermions)
        sine_product, widening = quantize_outward(
            interval_scale(
                interval_multiply(coefficient, sine),
                BigInt(branch_sign(phase)) // BigInt(1),
            ),
            denominator_grid,
        )
        rounding_widening[] += widening
        rounding_events[] += 1
        push!(contributions, (
            mask=source_mask, source=source_mask, branch=0, interval=cosine_product,
        ))
        push!(contributions, (
            mask=UInt64(target_mask), source=source_mask, branch=1, interval=sine_product,
        ))
    end
    sort!(contributions; by=row -> (row.mask, row.source, row.branch))
    premerge_rows = [
        (
            mask=Int(row.mask), source_mask=Int(row.source), branch=row.branch,
            coefficient_interval=interval_json(row.interval),
        ) for row in contributions
    ]
    merged = Dict{UInt64,Interval}()
    zero_pruned = 0
    index = 1
    while index <= length(contributions)
        mask = contributions[index].mask
        accumulator = (zero(Q), zero(Q))
        while index <= length(contributions) && contributions[index].mask == mask
            accumulator = interval_add(accumulator, contributions[index].interval)
            index += 1
        end
        accumulator, widening = quantize_outward(accumulator, denominator_grid)
        rounding_widening[] += widening
        rounding_events[] += 1
        if accumulator == (zero(Q), zero(Q))
            zero_pruned += 1
        else
            merged[mask] = accumulator
        end
    end
    return merged, (
        gate_mask=Int(gate_mask),
        theta=format_q(theta),
        input_term_count=length(expansion),
        premerge_term_count=length(contributions),
        postmerge_term_count=length(merged),
        exact_zero_pruned_count=zero_pruned,
        premerge_sha256=canonical_sha256(premerge_rows),
        postmerge_sha256=terms_sha256(merged),
    )
end

function drop_threshold(
    expansion::Dict{UInt64,Interval}, epsilon::Q, cumulative_before::Q,
    occurrence_index::Int, schrodinger_index::Int, symbol::String,
    boundary_kind::String, constituent_index,
)
    dropped_masks = UInt64[
        mask for mask in sort!(collect(keys(expansion)))
        if interval_abs_upper(expansion[mask]) < epsilon
    ]
    dropped_rows = [
        (
            mask=Int(mask),
            coefficient_interval=interval_json(expansion[mask]),
            abs_upper=format_q(interval_abs_upper(expansion[mask])),
            reason="strict_interval_abs_upper_below_threshold",
        ) for mask in dropped_masks
    ]
    increment = sum(
        (interval_abs_upper(expansion[mask]) for mask in dropped_masks);
        init=zero(Q),
    )
    retained = Dict{UInt64,Interval}(
        mask => expansion[mask] for mask in sort!(collect(keys(expansion)))
        if !(mask in dropped_masks)
    )
    return retained, (
        occurrence_index=occurrence_index,
        schrodinger_index=schrodinger_index,
        gate_symbol=symbol,
        boundary_kind=boundary_kind,
        constituent_index=constituent_index,
        postmerge_term_count=length(expansion),
        retained_term_count=length(retained),
        dropped_term_count=length(dropped_masks),
        postmerge_sha256=terms_sha256(expansion),
        dropped_terms=dropped_rows,
        dropped_terms_sha256=canonical_sha256(dropped_rows),
        retained_sha256=terms_sha256(retained),
        dropped_l1_increment=format_q(increment),
        cumulative_dropped_l1_before=format_q(cumulative_before),
        cumulative_dropped_l1_after=format_q(cumulative_before + increment),
    ), increment
end

function fock_expectation(mask::UInt64, occupied_fermions::Vector{Int}, nfermions::Int)
    for fermion in 1:nfermions
        first_bit = (mask >> (2fermion - 2)) & 1
        second_bit = (mask >> (2fermion - 1)) & 1
        first_bit == second_bit || return 0
    end
    occupied_mask = UInt64(0)
    for fermion in occupied_fermions
        occupied_mask |= UInt64(1) << (2fermion - 2)
    end
    exponent = mod(omega_l_self(mask) + popcount_u(mask) ÷ 2, 4)
    phase = exponent == 0 ? 1 : exponent == 2 ? -1 : error("non-real Fock phase")
    return phase * (isodd(popcount_u(mask & occupied_mask)) ? -1 : 1)
end

function expansion_expectation(
    expansion::Dict{UInt64,Interval}, occupied_fermions::Vector{Int},
    nfermions::Int, denominator_grid::BigInt,
)
    result = (zero(Q), zero(Q))
    for mask in sort!(collect(keys(expansion)))
        expectation = fock_expectation(mask, occupied_fermions, nfermions)
        expectation == 0 && continue
        result = interval_add(
            result,
            interval_scale(
                expansion[mask], BigInt(expectation) // BigInt(1),
            ),
        )
    end
    rounded, _ = quantize_outward(result, denominator_grid)
    return rounded
end

function exact_float_rational(value::Float64)
    isfinite(value) || error("non-finite upstream coefficient")
    return rationalize(BigInt, value; tol=0)
end

function composite_witness(fixture)
    composite = fixture["composite_conformance"]
    interval_policy = fixture["interval_policy"]
    nsites = Int(composite["n_sites"])
    nfermions = 2nsites
    order = Int(interval_policy["taylor_order"])
    denominator_grid = parse(BigInt, interval_policy["outward_quantization_denominator"])
    epsilon = parse_q(interval_policy["threshold_epsilon"])

    observable = composite["observable"]
    observable_sites = Int.(observable["sites"])
    observable_site_argument = length(observable_sites) == 1 ?
        observable_sites[1] : observable_sites
    upstream_observable = MajoranaSum(
        nsites, Symbol(observable["symbol"]), observable_site_argument,
    )
    expansion = Dict{UInt64,Interval}()
    for (mask, coefficient) in sort!(collect(upstream_observable); by=first)
        exact = exact_float_rational(coefficient)
        expansion[UInt64(mask)] = (exact, exact)
    end
    initial_rows = term_rows(expansion)
    initial_sha256 = canonical_sha256(initial_rows)

    schrodinger = [
        (
            schrodinger_index=index,
            symbol=String(gate["symbol"]),
            sites=Int.(gate["sites"]),
            theta=String(gate["theta"]),
        ) for (index, gate) in enumerate(composite["schrodinger_gates_in_order"])
    ]

    occurrence_rows = NamedTuple[]
    stage_rows = NamedTuple[]
    ledger_rows = NamedTuple[]
    cumulative_dropped = zero(Q)
    rounding_widening = Ref(zero(Q))
    rounding_events = Ref(0)
    reversed_gates = reverse(collect(enumerate(composite["schrodinger_gates_in_order"])))
    for (occurrence_index, indexed_gate) in enumerate(reversed_gates)
        schrodinger_index, gate = indexed_gate
        symbol = String(gate["symbol"])
        sites = Int.(gate["sites"])
        theta = parse_q(gate["theta"])
        upstream_gate = FermionicRotation(Symbol(symbol), sites)
        rotations, coefficients, truncate_after_each =
            MajoranaPropagation.getmajoranarotations(upstream_gate, nsites)
        constituents = [
            (
                mask=UInt64(rotation.ms_int),
                coefficient=exact_float_rational(coefficient),
            ) for (rotation, coefficient) in zip(rotations, coefficients)
        ]
        sort!(constituents; by=row -> row.mask)
        constituent_rows = [
            (mask=Int(row.mask), coefficient=format_q(row.coefficient))
            for row in constituents
        ]
        push!(occurrence_rows, (
            occurrence_index=occurrence_index,
            schrodinger_index=schrodinger_index,
            symbol=symbol,
            sites=sites,
            theta=format_q(theta),
            truncate_after_each_constituent=truncate_after_each,
            constituents=constituent_rows,
            constituents_sha256=canonical_sha256(constituent_rows),
        ))
        stage_input_sha256 = terms_sha256(expansion)
        merge_rows = NamedTuple[]
        stage_drop_start = cumulative_dropped
        for (constituent_index, row) in enumerate(constituents)
            constituent_theta = theta * row.coefficient * 2
            expansion, merge_row = apply_rotation(
                expansion, row.mask, constituent_theta, nfermions, order,
                denominator_grid, rounding_widening, rounding_events,
            )
            push!(merge_rows, merge_row)
            if truncate_after_each
                expansion, ledger_row, increment = drop_threshold(
                    expansion, epsilon, cumulative_dropped, occurrence_index,
                    schrodinger_index, symbol, "after_constituent", constituent_index,
                )
                cumulative_dropped += increment
                push!(ledger_rows, ledger_row)
            end
        end
        if !truncate_after_each
            expansion, ledger_row, increment = drop_threshold(
                expansion, epsilon, cumulative_dropped, occurrence_index,
                schrodinger_index, symbol, "after_complete_composite", nothing,
            )
            cumulative_dropped += increment
            push!(ledger_rows, ledger_row)
        end
        push!(stage_rows, (
            occurrence_index=occurrence_index,
            schrodinger_index=schrodinger_index,
            gate_symbol=symbol,
            input_sha256=stage_input_sha256,
            merge_steps=merge_rows,
            ledger_event_count=truncate_after_each ? length(constituents) : 1,
            dropped_l1_increment=format_q(cumulative_dropped - stage_drop_start),
            cumulative_dropped_l1=format_q(cumulative_dropped),
            output_sha256=terms_sha256(expansion),
        ))
    end

    fock = composite["fock_state"]
    occupied_fermions = Int[]
    for site in fock["up_occupied_sites"]
        push!(occupied_fermions, 2Int(site) - 1)
    end
    for site in fock["down_occupied_sites"]
        push!(occupied_fermions, 2Int(site))
    end
    sort!(occupied_fermions)
    retained_expectation = expansion_expectation(
        expansion, occupied_fermions, nfermions, denominator_grid,
    )
    declared_expectation, widening = quantize_outward((
        retained_expectation[1] - cumulative_dropped,
        retained_expectation[2] + cumulative_dropped,
    ), denominator_grid)
    rounding_widening[] += widening
    rounding_events[] += 1

    return (
        schrodinger_occurrences=schrodinger,
        schrodinger_occurrences_sha256=canonical_sha256(schrodinger),
        heisenberg_occurrences=occurrence_rows,
        heisenberg_occurrences_sha256=canonical_sha256(occurrence_rows),
        initial_terms=initial_rows,
        initial_terms_sha256=initial_sha256,
        stages=stage_rows,
        ledger_events=ledger_rows,
        ledger_events_sha256=canonical_sha256(ledger_rows),
        final_retained_terms=term_rows(expansion),
        final_retained_terms_sha256=terms_sha256(expansion),
        cumulative_dropped_l1=format_q(cumulative_dropped),
        retained_expectation_interval=interval_json(retained_expectation),
        declared_circuit_expectation_interval=interval_json(declared_expectation),
        rounding_endpoint_widening_diagnostic=format_q(rounding_widening[]),
        rounding_quantization_event_count=rounding_events[],
        rounding_accounting="absorbed_in_coefficient_boxes_not_added_again_as_scalar",
    )
end

function file_sha256(path::AbstractString)
    return bytes2hex(sha256(read(path)))
end

function main()
    length(ARGS) == 1 || error("usage: majorana_p0_runner.jl FIXTURE.json")
    fixture_path = abspath(ARGS[1])
    fixture = JSON.parsefile(fixture_path)
    active_project = Base.active_project()
    active_project === nothing && error("runner requires an active project")
    manifest_path = joinpath(dirname(active_project), "Manifest.toml")
    isfile(manifest_path) || error("Manifest.toml missing")
    image_file = unsafe_string(Base.JLOptions().image_file)
    julia_executable = joinpath(Sys.BINDIR, Base.julia_exename())
    mp_path = pathof(MajoranaPropagation)
    pp_path = pathof(MajoranaPropagation.PauliPropagation)

    algebra = primitive_algebra(
        Int(fixture["primitive_conformance"]["n_fermions"]),
        Int(fixture["primitive_conformance"]["mask_minimum"]),
        Int(fixture["primitive_conformance"]["mask_maximum"]),
    )
    rotations = primitive_rotations(fixture)
    composite = composite_witness(fixture)
    scope = (
        maximum_positive_status="VERIFIED_MAJORANA_P0_DETERMINISTIC_INTERVAL_LEDGER_CONFORMANCE_SUBCERTIFICATE",
        small_fixture_conformance_only=true,
        L8_full_propagation="NOT_ASSESSED",
        product_formula_to_exact_Hubbard_error="NOT_ASSESSED",
        physical_reference_qualified=false,
        ready_gate_eligible=false,
    )
    witness = (
        schema_version=1,
        witness_type="majorana_p0_small_fixture_deterministic_interval_ledger_v1",
        fixture_id=String(fixture["fixture_id"]),
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
        primitive_algebra=algebra,
        primitive_rotations=rotations,
        composite=composite,
        scope=scope,
    )
    print(canonical_json(witness))
    print('\n')
end

main()
