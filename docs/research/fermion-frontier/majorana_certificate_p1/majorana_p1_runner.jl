#!/usr/bin/env julia

using JSON
using MajoranaPropagation
using SHA

const Q = Rational{BigInt}
const GROUP_ORDER = ("H1", "H2", "HU", "H3", "H4", "H4", "H3", "HU", "H2", "H1")
const UNIQUE_GROUP_ORDER = ("H1", "H2", "HU", "H3", "H4")
const MAXIMUM_STATUS = "VERIFIED_MAJORANA_P1_L2_L3_HUBBARD_SPARSE_ACTION_AND_CADENCE_CONFORMANCE_SUBCERTIFICATE"
const HASH_BUFFER_BYTES = 1_048_576

function parse_q(value::AbstractString)::Q
    parts = split(value, '/'; keepempty=true)
    if length(parts) == 1
        return parse(BigInt, parts[1]) // BigInt(1)
    elseif length(parts) == 2
        denominator_value = parse(BigInt, parts[2])
        denominator_value > 0 || error("rational denominator must be positive")
        return parse(BigInt, parts[1]) // denominator_value
    end
    error("invalid rational")
end

function format_q(value::Q)::String
    denominator(value) == 1 && return string(numerator(value))
    return string(numerator(value), '/', denominator(value))
end

function exact_float_rational(value::Float64)::Q
    isfinite(value) || error("non-finite upstream coefficient")
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

mutable struct ChunkedHasher
    context
    buffer::IOBuffer
end

ChunkedHasher() = ChunkedHasher(SHA.SHA2_256_CTX(), IOBuffer())

function flush_hash_buffer!(hasher::ChunkedHasher)
    position(hasher.buffer) == 0 && return
    SHA.update!(hasher.context, take!(hasher.buffer))
end

function hash_update!(hasher::ChunkedHasher, payload::AbstractVector{UInt8})
    write(hasher.buffer, payload)
    position(hasher.buffer) >= HASH_BUFFER_BYTES && flush_hash_buffer!(hasher)
end

hash_update!(hasher::ChunkedHasher, payload::AbstractString) =
    hash_update!(hasher, codeunits(payload))

function hash_hexdigest!(hasher::ChunkedHasher)::String
    flush_hash_buffer!(hasher)
    return bytes2hex(SHA.digest!(hasher.context))
end

function require_object(value, context::AbstractString)
    value isa AbstractDict || error("$context must be an object")
    return value
end

function require_exact_keys(value, expected::Vector{String}, context::AbstractString)
    object = require_object(value, context)
    actual = sort!(String.(collect(keys(object))))
    expected_sorted = sort(copy(expected))
    actual == expected_sorted || error("$context has unexpected keys")
    return object
end

function require_equal(actual, expected, context::AbstractString)
    actual == expected || error("$context differs from the frozen fixture policy")
end

function profile_expected(linear_size::Int, dense::Bool)
    nsites = linear_size^2
    nmodes = 2nsites
    dimension = 1 << nmodes
    edge_count = 2linear_size * (linear_size - 1)
    hopping_count = 2edge_count
    onsite_count = nsites
    local_sz_count = nsites
    operator_count = hopping_count + onsite_count + local_sz_count + 2
    unique_constituents = 2hopping_count + 3onsite_count
    unique_boundaries = hopping_count + 3onsite_count
    unique_composites = hopping_count + onsite_count
    logical_dense = operator_count * dimension * dimension
    return (
        profile_id="L$(linear_size)_OBC",
        linear_size=linear_size,
        n_sites=nsites,
        n_modes=nmodes,
        basis_dimension=dimension,
        dense_matrix_enumeration=dense,
        spin_resolved_hopping_instance_count=hopping_count,
        onsite_instance_count=onsite_count,
        local_Sz_observable_count=local_sz_count,
        campaign_observable_count=2,
        operator_instance_count=operator_count,
        occupation_action_column_count=operator_count * dimension,
        dense_matrix_entry_count=logical_dense,
        unique_composite_count=unique_composites,
        unique_constituent_count=unique_constituents,
        unique_truncation_boundary_count=unique_boundaries,
        r2_composite_occurrence_count=4unique_composites,
        r2_constituent_occurrence_count=4unique_constituents,
        r2_truncation_boundary_count=4unique_boundaries,
        r2_omitted_identity_phase_exponent_in_exp_minus_i_x=format_q(BigInt(2nsites) // BigInt(1)),
    )
end

function validate_fixture(fixture)
    require_exact_keys(fixture, [
        "schema_version", "fixture_id", "fixture_role", "profiles",
        "lattice_and_mode_convention", "hubbard_generator_convention",
        "campaign_observables", "local_observable_constituents",
        "action_oracle_policy", "cadence_execution_probe_policy",
        "aggregate_planned_counts",
    ], "fixture")
    require_equal(fixture["schema_version"], 1, "fixture.schema_version")
    require_equal(fixture["fixture_id"], "MAJORANA-P1-L2-L3-HUBBARD-ACTION-CADENCE-V1", "fixture.fixture_id")
    require_equal(fixture["fixture_role"], "fixed_cross_language_exact_CAR_JW_sparse_action_and_composite_cadence_conformance", "fixture.fixture_role")

    profiles = fixture["profiles"]
    profiles isa AbstractVector && length(profiles) == 2 || error("fixture.profiles must contain L2 and L3")
    expected_profiles = (profile_expected(2, true), profile_expected(3, false))
    profile_keys = String.(collect(keys(expected_profiles[1])))
    for (index, expected) in enumerate(expected_profiles)
        profile = require_exact_keys(profiles[index], profile_keys, "fixture.profiles[$index]")
        for key in keys(expected)
            require_equal(profile[String(key)], getproperty(expected, key), "fixture.profiles[$index].$(String(key))")
        end
    end

    lattice = require_exact_keys(fixture["lattice_and_mode_convention"], [
        "boundary_condition", "site_order", "mode_order", "basis_index_rule",
        "bond_group_order", "raw_strang_group_order",
        "trotter_steps_for_cadence_occurrence_matrix", "total_time", "half_event_duration",
    ], "fixture.lattice_and_mode_convention")
    require_equal(lattice["boundary_condition"], "square_open_boundary_no_wrap", "boundary condition")
    require_equal(lattice["site_order"], "row_major_zero_based_coordinates_exposed_as_one_based_Julia_sites", "site order")
    require_equal(lattice["mode_order"], "site_major_spin_minor_q_equals_2_times_site_plus_up0_down1", "mode order")
    require_equal(lattice["basis_index_rule"], "bit_q_is_occupation_of_mode_q", "basis index rule")
    require_equal(lattice["bond_group_order"], ["H1", "H2", "H3", "H4"], "bond group order")
    require_equal(lattice["raw_strang_group_order"], collect(GROUP_ORDER), "raw Strang group order")
    require_equal(lattice["trotter_steps_for_cadence_occurrence_matrix"], 2, "cadence step count")
    require_equal(lattice["total_time"], "1", "total time")
    require_equal(lattice["half_event_duration"], "1/4", "half event duration")

    hubbard = require_exact_keys(fixture["hubbard_generator_convention"], [
        "hamiltonian", "hopping_symbols", "hopping_constructor_theta_multiplier",
        "onsite_symbol", "onsite_constructor_theta_multiplier",
        "onsite_constructor_identity_coefficient", "hopping_cadence", "onsite_cadence",
        "constituent_order", "upstream_native_applymergetruncate_Dict_order",
    ], "fixture.hubbard_generator_convention")
    require_equal(hubbard["hamiltonian"], "minus_sum_OBC_hopping_plus_8_sum_unshifted_nupndn", "Hamiltonian")
    require_equal(hubbard["hopping_symbols"], ["hopup", "hopdn"], "hopping symbols")
    require_equal(hubbard["hopping_constructor_theta_multiplier"], "-1", "hopping multiplier")
    require_equal(hubbard["onsite_symbol"], "nupndn", "onsite symbol")
    require_equal(hubbard["onsite_constructor_theta_multiplier"], "8", "onsite multiplier")
    require_equal(hubbard["onsite_constructor_identity_coefficient"], "1/4", "onsite identity coefficient")
    require_equal(hubbard["hopping_cadence"], "truncate_after_complete_composite", "hopping cadence")
    require_equal(hubbard["onsite_cadence"], "truncate_after_each_constituent", "onsite cadence")
    require_equal(hubbard["constituent_order"], "certificate_wrapper_executes_unsigned_Majorana_mask_ascending", "constituent order")
    require_equal(hubbard["upstream_native_applymergetruncate_Dict_order"], "NOT_ASSESSED", "native Dict order scope")

    campaigns = fixture["campaign_observables"]
    require_equal(campaigns, Any[
        Dict(
            "observable_id" => "staggered_magnetization",
            "definition" => "(1/N)*sum_(-1)^(row+column)*(nup-ndn)",
            "normalization" => "1/N",
        ),
        Dict(
            "observable_id" => "double_occupancy",
            "definition" => "(1/N)*sum_nup*ndn",
            "normalization" => "1/N",
        ),
    ], "campaign observables")
    require_equal(fixture["local_observable_constituents"], Dict(
        "symbols" => ["Sz"],
        "site_domain" => "every_row_major_physical_site",
        "purpose" => "prevent_global_staggered_sum_from_masking_site_local_sign_or_mode_errors",
    ), "local observable policy")
    require_equal(fixture["action_oracle_policy"], Dict(
        "python_expected_route" => "direct_exact_CAR_creation_annihilation_and_diagonal_occupation_without_importing_Julia_or_upstream",
        "julia_observed_route" => "pinned_upstream_Majorana_constructors_and_overlapwithfock",
        "coefficient_domain" => "reduced_exact_rationals_with_Gaussian_integer_phases",
        "L2_coverage" => "all_operator_instances_times_all_ket_times_all_bra_entries_evaluated_by_upstream_overlapwithfock",
        "L3_coverage" => "all_operator_instances_times_all_ket_sparse_candidate_action_columns_at_term_derived_flip_support",
        "L3_outside_support_entries" => "algebraically_implied_by_Majorana_flip_support_not_individually_executed",
        "sparse_action_stream" => "UTF8_decimal_ket_tab_semicolon_joined_bra_comma_real_comma_imag_newline_v1",
        "dense_matrix_stream" => "UTF8_decimal_ket_tab_bra_tab_real_tab_imag_newline_v1",
        "zero_action_columns_are_serialized" => true,
        "action_outputs_are_sorted_by_bra" => true,
    ), "action oracle policy")
    require_equal(fixture["cadence_execution_probe_policy"], Dict(
        "wrapper" => "explicit_unsigned_mask_sorted_MajoranaRotation_apply_merge_and_truncate_sequence",
        "rotation_angle" => "0",
        "sentinel" => "identity_term_with_unit_coefficient",
        "truncation_observation" => "custom_callback_identity_visit_count_binds_each_actual_truncate_call",
        "native_unsorted_FermionicRotation_execution" => "NOT_ASSESSED",
    ), "cadence execution probe policy")

    l2, l3 = expected_profiles
    aggregate_expected = Dict(
        "profile_count" => 2,
        "operator_instance_count" => l2.operator_instance_count + l3.operator_instance_count,
        "hubbard_generator_instance_count" => l2.unique_composite_count + l3.unique_composite_count,
        "local_Sz_observable_instance_count" => l2.local_Sz_observable_count + l3.local_Sz_observable_count,
        "campaign_observable_instance_count" => 4,
        "occupation_action_column_count" => l2.occupation_action_column_count + l3.occupation_action_column_count,
        "explicit_dense_matrix_entry_count" => l2.dense_matrix_entry_count,
        "r2_composite_occurrence_count" => l2.r2_composite_occurrence_count + l3.r2_composite_occurrence_count,
        "r2_constituent_occurrence_count" => l2.r2_constituent_occurrence_count + l3.r2_constituent_occurrence_count,
        "r2_truncation_boundary_count" => l2.r2_truncation_boundary_count + l3.r2_truncation_boundary_count,
    )
    require_equal(fixture["aggregate_planned_counts"], aggregate_expected, "aggregate planned counts")
    return fixture
end

function add_term!(expansion::Dict{UInt64,Q}, mask::Integer, coefficient::Q)
    key = UInt64(mask)
    expansion[key] = get(expansion, key, zero(Q)) + coefficient
    expansion[key] == 0 && delete!(expansion, key)
    return expansion
end

function upstream_terms(msum)::Dict{UInt64,Q}
    expansion = Dict{UInt64,Q}()
    for (mask, coefficient) in msum
        coefficient isa Float64 || error("frozen P1 constructors must have Float64 coefficients")
        add_term!(expansion, mask, exact_float_rational(coefficient))
    end
    return expansion
end

function add_scaled!(target::Dict{UInt64,Q}, source::Dict{UInt64,Q}, scale::Q)
    for mask in sort!(collect(keys(source)))
        add_term!(target, mask, source[mask] * scale)
    end
    return target
end

function term_rows(expansion::Dict{UInt64,Q})
    return [
        (mask=Int(mask), coefficient=format_q(expansion[mask]))
        for mask in sort!(collect(keys(expansion)))
    ]
end

function flip_mask(majorana_mask::UInt64, nmodes::Int)::UInt64
    output = UInt64(0)
    for mode in 0:(nmodes - 1)
        pair = (majorana_mask >> (2mode)) & UInt64(3)
        pair == 1 || pair == 2 || continue
        output |= UInt64(1) << mode
    end
    return output
end

function cadence_record(symbol::String, sites::Vector{Int}, multiplier::Q, nsites::Int)
    rotations, coefficients, truncate_after_each =
        MajoranaPropagation.getmajoranarotations(FermionicRotation(Symbol(symbol), sites), nsites)
    constituent_pairs = [
        (mask=UInt64(rotation.ms_int), coefficient=exact_float_rational(coefficient))
        for (rotation, coefficient) in zip(rotations, coefficients)
    ]
    sort!(constituent_pairs; by=row -> row.mask)
    length(unique(row.mask for row in constituent_pairs)) == length(constituent_pairs) ||
        error("upstream constituent masks are not unique")
    constituents = [
        (
            mask=Int(row.mask),
            constructor_coefficient=format_q(row.coefficient),
            physical_theta_multiplier=format_q(multiplier),
            effective_coefficient=format_q(row.coefficient * multiplier),
        ) for row in constituent_pairs
    ]
    expected_truncate = symbol == "nupndn"
    truncate_after_each == expected_truncate || error("unexpected upstream truncation cadence")

    # Execute the deterministic certificate wrapper rather than treating a
    # sorted serialization of the upstream Dict as execution evidence.  The
    # identity probe survives every zero-angle rotation.  Its custom
    # truncation callback is therefore visited exactly once per real
    # truncate! invocation and binds the observed boundary count to calls on
    # the upstream cache implementation.
    TT = getinttype(2 * nsites)
    probe = MajoranaSum(Float64, nsites, true)
    set!(probe, zero(TT), 1.0)
    cache = MajoranaPropagationCache(probe)
    identity_visits = Ref(0)
    callback = function (mask, _coefficient)
        mask == zero(TT) && (identity_visits[] += 1)
        return false
    end
    applied_masks = Int[]
    observed_boundaries = NamedTuple[]
    for (constituent_index, row) in enumerate(constituent_pairs)
        push!(applied_masks, Int(row.mask))
        MajoranaPropagation.PropagationBase.applytoall!(
            MajoranaRotation(convert(TT, row.mask)), cache, 0.0,
        )
        merge!(cache)
        if truncate_after_each
            before = identity_visits[]
            truncate!(cache; min_abs_coeff=0.0, customtruncfunc=callback)
            delta = identity_visits[] - before
            delta == 1 || error("identity probe did not observe one constituent truncation")
            push!(observed_boundaries, (
                boundary_index=length(observed_boundaries),
                boundary_kind="after_constituent",
                after_constituent_index=constituent_index - 1,
                identity_callback_delta=delta,
            ))
        end
    end
    if !truncate_after_each
        before = identity_visits[]
        truncate!(cache; min_abs_coeff=0.0, customtruncfunc=callback)
        delta = identity_visits[] - before
        delta == 1 || error("identity probe did not observe one composite truncation")
        push!(observed_boundaries, (
            boundary_index=0,
            boundary_kind="after_complete_composite",
            after_constituent_index=nothing,
            identity_callback_delta=delta,
        ))
    end
    final_probe = MajoranaPropagation.PropagationBase.mainsum(cache)
    final_identity = exact_float_rational(get(final_probe.Majoranas, zero(TT), 0.0))
    final_identity == 1 || error("cadence execution probe lost the identity sentinel")
    execution_probe = (
        wrapper_id="sorted_zero_angle_identity_truncation_callback_v1",
        applied_masks=applied_masks,
        applied_masks_sha256=canonical_sha256(applied_masks),
        observed_truncation_call_count=identity_visits[],
        observed_boundaries=observed_boundaries,
        observed_boundaries_sha256=canonical_sha256(observed_boundaries),
        final_identity_coefficient=format_q(final_identity),
    )
    return (
        truncate_after_each_constituent=truncate_after_each,
        boundary_kind=truncate_after_each ? "after_constituent" : "after_complete_composite",
        constituent_count=length(constituents),
        truncation_boundary_count=truncate_after_each ? length(constituents) : 1,
        constituents=constituents,
        constituents_sha256=canonical_sha256(constituents),
        execution_probe=execution_probe,
        execution_probe_sha256=canonical_sha256(execution_probe),
    )
end

function physical_constructor(symbol::String, sites::Vector{Int}, multiplier::Q, nsites::Int)
    base = MajoranaSum(nsites, Symbol(symbol), length(sites) == 1 ? sites[1] : sites)
    physical = if multiplier == -1
        -1 * base
    elseif multiplier == 8
        8 * base
    elseif multiplier == 1
        base
    else
        error("unsupported frozen physical constructor multiplier")
    end
    return upstream_terms(physical)
end

function canonical_bonds(linear_size::Int)
    bonds = NamedTuple[]
    for group in ("H1", "H2", "H3", "H4")
        if group == "H1" || group == "H2"
            parity = group == "H1" ? 0 : 1
            for row in 0:(linear_size - 1), column in parity:2:(linear_size - 2)
                for (spin, symbol) in (("up", "hopup"), ("down", "hopdn"))
                    push!(bonds, (
                        group=group,
                        row_a=row,
                        col_a=column,
                        row_b=row,
                        col_b=column + 1,
                        spin=spin,
                        symbol=symbol,
                    ))
                end
            end
        else
            parity = group == "H3" ? 1 : 0
            for row in parity:2:(linear_size - 2), column in 0:(linear_size - 1)
                for (spin, symbol) in (("up", "hopup"), ("down", "hopdn"))
                    push!(bonds, (
                        group=group,
                        row_a=row,
                        col_a=column,
                        row_b=row + 1,
                        col_b=column,
                        spin=spin,
                        symbol=symbol,
                    ))
                end
            end
        end
    end
    return bonds
end

function operator_specs(linear_size::Int)
    nsites = linear_size^2
    specs = Any[]
    bonds = canonical_bonds(linear_size)
    for group in UNIQUE_GROUP_ORDER
        if group == "HU"
            for site0 in 0:(nsites - 1)
                row, column = divrem(site0, linear_size)
                sites = [site0 + 1]
                multiplier = BigInt(8) // BigInt(1)
                expansion = physical_constructor("nupndn", sites, multiplier, nsites)
                push!(specs, (
                    operator_id="HU_r$(row)_c$(column)",
                    operator_role="hubbard_onsite_generator",
                    group=group,
                    symbol="nupndn",
                    sites=sites,
                    physical_theta_multiplier=multiplier,
                    expansion=expansion,
                    cadence=cadence_record("nupndn", sites, multiplier, nsites),
                ))
            end
        else
            for bond in bonds
                bond.group == group || continue
                left0 = bond.row_a * linear_size + bond.col_a
                right0 = bond.row_b * linear_size + bond.col_b
                sites = [left0 + 1, right0 + 1]
                multiplier = -BigInt(1) // BigInt(1)
                expansion = physical_constructor(bond.symbol, sites, multiplier, nsites)
                push!(specs, (
                    operator_id="$(group)_r$(bond.row_a)_c$(bond.col_a)_$(bond.spin)",
                    operator_role="hubbard_hopping_generator",
                    group=group,
                    symbol=bond.symbol,
                    sites=sites,
                    physical_theta_multiplier=multiplier,
                    expansion=expansion,
                    cadence=cadence_record(bond.symbol, sites, multiplier, nsites),
                ))
            end
        end
    end

    for site0 in 0:(nsites - 1)
        row, column = divrem(site0, linear_size)
        sites = [site0 + 1]
        expansion = physical_constructor("Sz", sites, BigInt(1) // BigInt(1), nsites)
        push!(specs, (
            operator_id="OBS_Sz_r$(row)_c$(column)",
            operator_role="local_Sz_observable",
            group=nothing,
            symbol="Sz",
            sites=sites,
            physical_theta_multiplier=BigInt(1) // BigInt(1),
            expansion=expansion,
            cadence=nothing,
        ))
    end

    staggered = Dict{UInt64,Q}()
    for site0 in 0:(nsites - 1)
        row, column = divrem(site0, linear_size)
        sign = iseven(row + column) ? BigInt(1) : BigInt(-1)
        nup = upstream_terms(MajoranaSum(nsites, :nup, site0 + 1))
        ndn = upstream_terms(MajoranaSum(nsites, :ndn, site0 + 1))
        add_scaled!(staggered, nup, sign // BigInt(nsites))
        add_scaled!(staggered, ndn, -sign // BigInt(nsites))
    end
    push!(specs, (
        operator_id="OBS_staggered_magnetization",
        operator_role="campaign_observable",
        group=nothing,
        symbol="staggered_magnetization",
        sites=collect(1:nsites),
        physical_theta_multiplier=BigInt(1) // BigInt(1),
        expansion=staggered,
        cadence=nothing,
    ))

    double_occupancy = Dict{UInt64,Q}()
    for site in 1:nsites
        onsite = upstream_terms(MajoranaSum(nsites, :nupndn, site))
        add_scaled!(double_occupancy, onsite, BigInt(1) // BigInt(nsites))
    end
    push!(specs, (
        operator_id="OBS_double_occupancy",
        operator_role="campaign_observable",
        group=nothing,
        symbol="double_occupancy",
        sites=collect(1:nsites),
        physical_theta_multiplier=BigInt(1) // BigInt(1),
        expansion=double_occupancy,
        cadence=nothing,
    ))
    return specs
end

function fock_states(nsites::Int, nmodes::Int, dimension::Int)
    TT = getinttype(nmodes)
    states = Vector{FockState{TT}}(undef, dimension)
    for source in 0:(dimension - 1)
        occupied = zero(TT)
        for mode in 0:(nmodes - 1)
            ((source >> mode) & 1) == 0 && continue
            occupied |= one(TT) << (2mode)
        end
        states[source + 1] = FockState(nsites, true, occupied)
    end
    return states
end

function phase_code(value)::Int8
    value == 0 && return Int8(0)
    value == 1 && return Int8(1)
    value == -1 && return Int8(-1)
    value == im && return Int8(2)
    value == -im && return Int8(-2)
    error("upstream overlapwithfock returned a non-Gaussian-integer phase: $value")
end

function phase_cache(specs, nsites::Int, nmodes::Int, dimension::Int)
    masks = sort!(unique(UInt64[
        mask for spec in specs for mask in keys(spec.expansion)
    ]))
    states = fock_states(nsites, nmodes, dimension)
    TT = getinttype(nmodes)
    cache = Dict{UInt64,Vector{Int8}}()
    for mask in masks
        support = flip_mask(mask, nmodes)
        phases = Vector{Int8}(undef, dimension)
        upstream_mask = convert(TT, mask)
        for source in 0:(dimension - 1)
            target = Int(xor(UInt64(source), support))
            phases[source + 1] = phase_code(overlapwithfock(
                upstream_mask, states[target + 1], states[source + 1], nmodes,
            ))
        end
        cache[mask] = phases
    end
    return cache, states
end

function action_entries(spec, source::Int, nmodes::Int, phases::Dict{UInt64,Vector{Int8}})
    support_terms = Dict{UInt64,Vector{Tuple{UInt64,Q}}}()
    for mask in sort!(collect(keys(spec.expansion)))
        support = flip_mask(mask, nmodes)
        push!(get!(support_terms, support, Tuple{UInt64,Q}[]), (mask, spec.expansion[mask]))
    end
    entries = Tuple{Int,Q,Q}[]
    for support in sort!(collect(keys(support_terms)))
        real_part = zero(Q)
        imaginary_part = zero(Q)
        for (mask, coefficient) in support_terms[support]
            phase = phases[mask][source + 1]
            if phase == 1
                real_part += coefficient
            elseif phase == -1
                real_part -= coefficient
            elseif phase == 2
                imaginary_part += coefficient
            elseif phase == -2
                imaginary_part -= coefficient
            elseif phase != 0
                error("invalid cached Gaussian phase")
            end
        end
        (real_part == 0 && imaginary_part == 0) && continue
        target = Int(xor(UInt64(source), support))
        push!(entries, (target, real_part, imaginary_part))
    end
    sort!(entries; by=first)
    return entries
end

function sparse_line(source::Int, entries)::String
    io = IOBuffer()
    print(io, source, '\t')
    for (index, entry) in enumerate(entries)
        index > 1 && print(io, ';')
        print(io, entry[1], ',', format_q(entry[2]), ',', format_q(entry[3]))
    end
    print(io, '\n')
    return String(take!(io))
end

function dense_line(source::Int, target::Int, real_part::Q, imaginary_part::Q)::String
    return string(
        source, '\t', target, '\t', format_q(real_part), '\t',
        format_q(imaginary_part), '\n',
    )
end

function public_operator_record(
    spec, operator_index::Int, linear_size::Int, dense::Bool,
    phases::Dict{UInt64,Vector{Int8}}, states,
)
    nmodes = 2linear_size^2
    dimension = 1 << nmodes
    terms = term_rows(spec.expansion)
    sorted_masks = sort!(collect(keys(spec.expansion)))
    flips = sort!(unique(Int(flip_mask(mask, nmodes)) for mask in keys(spec.expansion)))
    length(flips) == 1 || error("each frozen P1 operator must have one exact support flip")
    action_hasher = ChunkedHasher()
    dense_hasher = dense ? ChunkedHasher() : nothing
    nonzero_outputs = 0
    for source in 0:(dimension - 1)
        entries = action_entries(spec, source, nmodes, phases)
        expected_target = Int(xor(UInt64(source), UInt64(only(flips))))
        all(entry[1] == expected_target for entry in entries) ||
            error("upstream action escaped exact Majorana flip support")
        nonzero_outputs += length(entries)
        hash_update!(action_hasher, sparse_line(source, entries))
        if dense_hasher !== nothing
            TT = getinttype(nmodes)
            for target in 0:(dimension - 1)
                real_part = zero(Q)
                imaginary_part = zero(Q)
                for mask in sorted_masks
                    phase = phase_code(overlapwithfock(
                        convert(TT, mask), states[target + 1], states[source + 1], nmodes,
                    ))
                    coefficient = spec.expansion[mask]
                    if phase == 1
                        real_part += coefficient
                    elseif phase == -1
                        real_part -= coefficient
                    elseif phase == 2
                        imaginary_part += coefficient
                    elseif phase == -2
                        imaginary_part -= coefficient
                    elseif phase != 0
                        error("invalid dense Gaussian phase")
                    end
                end
                hash_update!(dense_hasher, dense_line(
                    source, target, real_part, imaginary_part,
                ))
            end
        end
    end
    logical_dense = dimension * dimension
    candidate_count = dimension * length(flips)
    return (
        operator_index=operator_index,
        operator_id=spec.operator_id,
        operator_role=spec.operator_role,
        group=spec.group,
        symbol=spec.symbol,
        sites=spec.sites,
        physical_theta_multiplier=format_q(spec.physical_theta_multiplier),
        term_count=length(terms),
        terms=terms,
        terms_sha256=canonical_sha256(terms),
        support_flip_masks=flips,
        support_flip_masks_sha256=canonical_sha256(flips),
        action_column_count=dimension,
        support_candidate_entry_count=candidate_count,
        action_nonzero_output_count=nonzero_outputs,
        action_stream_sha256=hash_hexdigest!(action_hasher),
        logical_dense_matrix_entry_count=logical_dense,
        explicit_dense_matrix_entry_count=dense ? logical_dense : 0,
        algebraically_implied_outside_support_zero_entry_count=
            dense ? 0 : logical_dense - candidate_count,
        dense_matrix_stream_sha256=dense ? hash_hexdigest!(dense_hasher) : "NOT_ENUMERATED_BY_POLICY",
        cadence=spec.cadence,
    )
end

function r2_cadence(specs)
    generator_specs = [spec for spec in specs if spec.cadence !== nothing]
    occurrences = NamedTuple[]
    constituent_count = 0
    boundary_count = 0
    phase = zero(Q)
    for step in 0:1
        for (event_offset, group) in enumerate(GROUP_ORDER)
            group_specs = [spec for spec in generator_specs if spec.group == group]
            for (occurrence_offset, spec) in enumerate(group_specs)
                cadence = spec.cadence
                phase_increment = get(spec.expansion, UInt64(0), zero(Q)) *
                    (BigInt(1) // BigInt(4))
                push!(occurrences, (
                    occurrence_index=length(occurrences),
                    step_index=step,
                    event_in_step=event_offset - 1,
                    group=group,
                    occurrence_in_event=occurrence_offset - 1,
                    operator_id=spec.operator_id,
                    truncate_after_each_constituent=cadence.truncate_after_each_constituent,
                    boundary_kind=cadence.boundary_kind,
                    constituent_count=cadence.constituent_count,
                    truncation_boundary_count=cadence.truncation_boundary_count,
                    constituents_sha256=cadence.constituents_sha256,
                    execution_probe_sha256=cadence.execution_probe_sha256,
                    half_event_duration="1/4",
                    omitted_identity_phase_increment_in_exp_minus_i_x=format_q(phase_increment),
                ))
                constituent_count += cadence.constituent_count
                boundary_count += cadence.truncation_boundary_count
                phase += phase_increment
            end
        end
    end
    return (
        trotter_steps=2,
        group_order=collect(GROUP_ORDER),
        composite_occurrence_count=length(occurrences),
        constituent_occurrence_count=constituent_count,
        truncation_boundary_count=boundary_count,
        occurrences_sha256=canonical_sha256(occurrences),
        omitted_identity_phase_exponent_in_exp_minus_i_x=format_q(phase),
    )
end

function profile_witness(profile_fixture)
    linear_size = Int(profile_fixture["linear_size"])
    dense = Bool(profile_fixture["dense_matrix_enumeration"])
    nsites = linear_size^2
    nmodes = 2nsites
    dimension = 1 << nmodes
    specs = operator_specs(linear_size)
    phases, states = phase_cache(specs, nsites, nmodes, dimension)
    records = [
        public_operator_record(spec, index - 1, linear_size, dense, phases, states)
        for (index, spec) in enumerate(specs)
    ]
    generator_records = [record for record in records if record.cadence !== nothing]
    unique_constituents = sum(record.cadence.constituent_count for record in generator_records)
    unique_boundaries = sum(record.cadence.truncation_boundary_count for record in generator_records)
    r2 = r2_cadence(specs)
    summary = (
        profile_id=String(profile_fixture["profile_id"]),
        linear_size=linear_size,
        n_sites=nsites,
        n_modes=nmodes,
        basis_dimension=dimension,
        dense_matrix_enumeration=dense,
        operator_instance_count=length(records),
        occupation_action_column_count=sum(record.action_column_count for record in records),
        explicit_dense_matrix_entry_count=sum(record.explicit_dense_matrix_entry_count for record in records),
        logical_dense_matrix_entry_count=sum(record.logical_dense_matrix_entry_count for record in records),
        action_nonzero_output_count=sum(record.action_nonzero_output_count for record in records),
        support_candidate_entry_count=sum(record.support_candidate_entry_count for record in records),
        algebraically_implied_outside_support_zero_entry_count=sum(
            record.algebraically_implied_outside_support_zero_entry_count for record in records
        ),
        unique_composite_count=length(generator_records),
        unique_constituent_count=unique_constituents,
        unique_truncation_boundary_count=unique_boundaries,
        operator_records=records,
        operator_records_sha256=canonical_sha256(records),
        r2_cadence=r2,
    )
    expected = profile_expected(linear_size, dense)
    checks = (
        n_sites=summary.n_sites,
        n_modes=summary.n_modes,
        basis_dimension=summary.basis_dimension,
        operator_instance_count=summary.operator_instance_count,
        occupation_action_column_count=summary.occupation_action_column_count,
        dense_matrix_entry_count=dense ? summary.explicit_dense_matrix_entry_count : summary.logical_dense_matrix_entry_count,
        unique_composite_count=summary.unique_composite_count,
        unique_constituent_count=summary.unique_constituent_count,
        unique_truncation_boundary_count=summary.unique_truncation_boundary_count,
        r2_composite_occurrence_count=r2.composite_occurrence_count,
        r2_constituent_occurrence_count=r2.constituent_occurrence_count,
        r2_truncation_boundary_count=r2.truncation_boundary_count,
        r2_omitted_identity_phase_exponent_in_exp_minus_i_x=r2.omitted_identity_phase_exponent_in_exp_minus_i_x,
    )
    for key in keys(checks)
        require_equal(profile_fixture[String(key)], getproperty(checks, key), "derived profile field $(String(key))")
        require_equal(getproperty(expected, key), getproperty(checks, key), "embedded profile field $(String(key))")
    end
    return summary
end

function aggregate_witness(profiles)
    aggregate = (
        profile_count=length(profiles),
        operator_instance_count=sum(row.operator_instance_count for row in profiles),
        hubbard_generator_instance_count=sum(row.unique_composite_count for row in profiles),
        local_Sz_observable_instance_count=sum(
            sum(record.operator_role == "local_Sz_observable" for record in row.operator_records)
            for row in profiles
        ),
        campaign_observable_instance_count=sum(
            sum(record.operator_role == "campaign_observable" for record in row.operator_records)
            for row in profiles
        ),
        occupation_action_column_count=sum(row.occupation_action_column_count for row in profiles),
        explicit_dense_matrix_entry_count=sum(row.explicit_dense_matrix_entry_count for row in profiles),
        r2_composite_occurrence_count=sum(row.r2_cadence.composite_occurrence_count for row in profiles),
        r2_constituent_occurrence_count=sum(row.r2_cadence.constituent_occurrence_count for row in profiles),
        r2_truncation_boundary_count=sum(row.r2_cadence.truncation_boundary_count for row in profiles),
        profiles_sha256=canonical_sha256(profiles),
    )
    return aggregate
end

function main()
    length(ARGS) == 1 || error("usage: majorana_p1_runner.jl FIXTURE.json")
    fixture_path = abspath(ARGS[1])
    fixture = validate_fixture(JSON.parsefile(fixture_path))
    active_project = Base.active_project()
    active_project === nothing && error("runner requires an active project")
    manifest_path = joinpath(dirname(active_project), "Manifest.toml")
    isfile(manifest_path) || error("Manifest.toml missing")
    Threads.nthreads() == 1 || error("formal P1 runner requires exactly one Julia thread")
    image_file = unsafe_string(Base.JLOptions().image_file)
    julia_executable = joinpath(Sys.BINDIR, Base.julia_exename())
    mp_path = pathof(MajoranaPropagation)
    pp_path = pathof(MajoranaPropagation.PauliPropagation)

    profiles = [profile_witness(profile) for profile in fixture["profiles"]]
    aggregate = aggregate_witness(profiles)
    fixture_aggregate = fixture["aggregate_planned_counts"]
    for key in keys(fixture_aggregate)
        require_equal(getproperty(aggregate, Symbol(key)), fixture_aggregate[key], "aggregate.$key")
    end
    scope = (
        maximum_positive_status=MAXIMUM_STATUS,
        fixed_L2_L3_square_OBC_Hubbard_workload_only=true,
        full_occupation_basis_columns_verified=true,
        L2_all_bra_ket_dense_entries_verified=true,
        L3_all_ket_sparse_candidate_actions_verified=true,
        L3_outside_support_entries_individually_executed=false,
        arbitrary_MajoranaPropagation_constructors_or_circuits="NOT_CLAIMED",
        L8_full_propagation="NOT_ASSESSED",
        product_formula_to_exact_Hubbard_error="NOT_ASSESSED",
        exact_time_evolution="NOT_ASSESSED",
        physical_reference_qualified=false,
        ready_gate_eligible=false,
    )
    witness = (
        schema_version=1,
        witness_type="majorana_p1_l2_l3_hubbard_sparse_action_cadence_v1",
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
        profiles=profiles,
        aggregate=aggregate,
        scope=scope,
    )
    print(canonical_json(witness))
    print('\n')
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main()
end
