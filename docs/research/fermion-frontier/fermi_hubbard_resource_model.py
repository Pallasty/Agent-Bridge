#!/usr/bin/env python3
"""Evidence-bounded resource model for a matched 2D Fermi--Hubbard task.

The output separates source-reported leading terms, candidate fits to a
published figure, and new scheduling derivations.  Missing first-step or
physical-stack inputs block complete totals instead of silently becoming zero.
This is a planning model, not a hardware-performance forecast.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


Number = int | float
FIGURE_FIT_L_MIN = 4
FIGURE_FIT_L_MAX = 10
SAMPLING_ROUTES = (
    "native_fermions",
    "dynamic_jw_local_grid",
    "fsn_standard",
    "fsn_ladder",
    "dynamic_jw_surface_code",
)
FIRST_STEP_ROUTES = ("dynamic_jw", "fsn_standard", "fsn_ladder")


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _nonnegative(value: Any, name: str) -> float:
    number = _finite_number(value, name)
    if number < 0:
        raise ValueError(f"{name} must be non-negative")
    return number


def _positive(value: Any, name: str) -> float:
    number = _finite_number(value, name)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _optional_nonnegative(value: Any, name: str) -> Optional[float]:
    return None if value is None else _nonnegative(value, name)


def _optional_nonnegative_int(value: Any, name: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer or null")
    return value


def _probability(value: Any, name: str, *, allow_zero: bool = True) -> float:
    number = _nonnegative(value, name)
    if number > 1 or (not allow_zero and number == 0):
        bound = "[0, 1]" if allow_zero else "(0, 1]"
        raise ValueError(f"{name} must lie in {bound}")
    return number


def _known_sum(values: Iterable[Optional[Number]]) -> Optional[float]:
    materialized = list(values)
    if any(value is None for value in materialized):
        return None
    return float(sum(value for value in materialized if value is not None))


def _required_error(budget: float, locations: Optional[Number]) -> Optional[float]:
    if locations is None or locations <= 0:
        return None
    return budget / float(locations)


def validate_config(config: Mapping[str, Any]) -> None:
    workload = config["workload"]
    l = _positive_int(workload["linear_size"], "workload.linear_size")
    if l < 3:
        raise ValueError("workload.linear_size must be >= 3 for the four-matching 2D model")
    _positive_int(workload["trotter_steps"], "workload.trotter_steps")
    _positive_int(
        workload["accepted_shots_per_measurement_setting"],
        "workload.accepted_shots_per_measurement_setting",
    )
    total = _probability(workload["target_total_error"], "target_total_error")
    components = [
        _probability(workload["algorithmic_error_budget"], "algorithmic_error_budget"),
        _probability(workload["statistical_error_budget"], "statistical_error_budget"),
        _probability(workload["hardware_error_budget"], "hardware_error_budget"),
    ]
    if sum(components) > total + 1e-15:
        raise ValueError("algorithmic + statistical + hardware budgets exceed target_total_error")

    physics = config["physics"]
    _positive(physics["hopping_t_energy_units"], "physics.hopping_t_energy_units")
    _nonnegative(physics["onsite_u_over_t"], "physics.onsite_u_over_t")
    _positive(
        physics["dimensionless_evolution_time_tT"],
        "physics.dimensionless_evolution_time_tT",
    )
    filling = _nonnegative(
        physics["filling_particles_per_site"], "physics.filling_particles_per_site"
    )
    if filling > 2:
        raise ValueError("physics.filling_particles_per_site must be <= 2")
    _positive_int(physics["measurement_settings"], "physics.measurement_settings")
    if not isinstance(physics["initial_state"], str) or not physics["initial_state"].strip():
        raise ValueError("physics.initial_state must be a non-empty string")
    observables = physics["observables"]
    if not isinstance(observables, list) or not observables or not all(
        isinstance(item, str) and item.strip() for item in observables
    ):
        raise ValueError("physics.observables must be a non-empty list of strings")

    sampling = config["route_sampling"]
    for route in SAMPLING_ROUTES:
        row = sampling[route]
        p_accept = row.get("acceptance_probability")
        mitigation = row.get("mitigation_repetition_multiplier")
        if p_accept is not None:
            _probability(p_accept, f"route_sampling.{route}.acceptance_probability", allow_zero=False)
        if mitigation is not None and _nonnegative(
            mitigation, f"route_sampling.{route}.mitigation_repetition_multiplier"
        ) < 1:
            raise ValueError(
                f"route_sampling.{route}.mitigation_repetition_multiplier must be >= 1"
            )

    for field in ("first_step_extra_cnot", "first_step_extra_cnot_depth"):
        values = config.get(field, {})
        for route in FIRST_STEP_ROUTES:
            _optional_nonnegative_int(values.get(route), f"{field}.{route}")

    timing = config["timing_us"]
    for route in SAMPLING_ROUTES:
        for key in (
            "classical_preprocessing_us",
            "prep_us",
            "readout_reset_us",
            "classical_postprocess_per_execution_us",
        ):
            _optional_nonnegative(
                timing["route_overheads"][route].get(key),
                f"timing_us.route_overheads.{route}.{key}",
            )
    for key in (
        "native_h1_half_layer_us",
        "native_h2_half_layer_us",
        "native_h3_half_layer_us",
        "native_h1_full_boundary_layer_us",
        "native_h4_full_central_layer_us",
        "native_onsite_half_layer_us",
    ):
        _optional_nonnegative(timing.get(key), f"timing_us.{key}")
    for route in FIRST_STEP_ROUTES:
        bare = timing["bare_qubit_routes"][route]
        for key in (
            "cnot_layer_us",
            "non_cnot_us_per_steady_step",
            "first_step_extra_non_cnot_us",
        ):
            _optional_nonnegative(
                bare.get(key), f"timing_us.bare_qubit_routes.{route}.{key}"
            )

    native_hardware = config["native_hardware"]
    for key in ("storage_traps", "transport_tweezers", "workspace_sites"):
        _optional_nonnegative_int(native_hardware.get(key), f"native_hardware.{key}")
    storage_traps = native_hardware.get("storage_traps")
    storage_floor = 2 * l * l
    if storage_traps is not None and storage_traps < storage_floor:
        raise ValueError(
            "native_hardware.storage_traps must provide at least one storage mode "
            "per fermionic mode in this register model"
        )

    surface = config["surface_code"]
    d = _positive_int(surface["distance"], "surface_code.distance")
    if d % 2 == 0:
        raise ValueError("surface_code.distance must be odd in this model")
    _positive(surface["cycle_us"], "surface_code.cycle_us")
    for key in ("joint_measurement_cycles", "aux_readout_cycles", "c2d_blocks_per_switch", "cz_layer_cycles"):
        _positive_int(surface[key], f"surface_code.{key}")
    for key in ("single_qubit_clifford_cycles", "feedforward_barriers_per_ladder"):
        _optional_nonnegative_int(surface[key], f"surface_code.{key}")
    _nonnegative(surface["reaction_us"], "surface_code.reaction_us")
    for key in (
        "spinful_swap_cycles_per_switch",
        "local_rotation_cycles_per_step",
        "auxiliary_patches",
        "routing_patches",
        "factory_patches",
        "magic_states_per_step",
        "magic_state_output_interval_cycles",
        "factory_count",
    ):
        _optional_nonnegative_int(surface.get(key), f"surface_code.{key}")
    magic_states = surface.get("magic_states_per_step")
    magic_interval = surface.get("magic_state_output_interval_cycles")
    factory_count = surface.get("factory_count")
    factory_patches = surface.get("factory_patches")
    if magic_states is not None and magic_states > 0:
        if factory_count is None or factory_count <= 0:
            raise ValueError(
                "surface_code.factory_count must be > 0 when magic states are required"
            )
        if magic_interval is None or magic_interval <= 0:
            raise ValueError(
                "surface_code.magic_state_output_interval_cycles must be > 0 "
                "when magic states are required"
            )
    if factory_count is not None and factory_count > 0:
        if factory_patches is None or factory_patches < factory_count:
            raise ValueError(
                "surface_code.factory_patches must be at least factory_count; "
                "the field is total factory patches"
            )
    explicit_aux = 2 * l * (l - 1)
    configured_aux = surface.get("auxiliary_patches")
    if configured_aux is not None and configured_aux < explicit_aux:
        raise ValueError(
            "surface_code.auxiliary_patches cannot be smaller than the explicit "
            "one-aux-per-CNOT column-ladder construction"
        )


def _execution_plan(config: Mapping[str, Any], route: str) -> Dict[str, Any]:
    workload = config["workload"]
    physics = config["physics"]
    sampling = config["route_sampling"][route]
    p_accept = sampling.get("acceptance_probability")
    mitigation = sampling.get("mitigation_repetition_multiplier")
    expected = None
    if p_accept is not None and mitigation is not None:
        expected = math.ceil(
            workload["accepted_shots_per_measurement_setting"]
            * physics["measurement_settings"]
            * mitigation
            / p_accept
        )
    return {
        "accepted_shots_per_measurement_setting": workload[
            "accepted_shots_per_measurement_setting"
        ],
        "measurement_settings": physics["measurement_settings"],
        "acceptance_probability": p_accept,
        "mitigation_repetition_multiplier": mitigation,
        "expected_raw_circuit_executions": expected,
        "interpretation": (
            "Expected execution count under a stationary acceptance rate; it is not a "
            "high-confidence stopping bound and does not include parallel replicas."
        ),
    }


def workload_quantities(config: Mapping[str, Any]) -> Dict[str, Any]:
    workload = config["workload"]
    physics = config["physics"]
    l = workload["linear_size"]
    r = workload["trotter_steps"]
    sites = l * l
    n = 2 * sites
    particles_float = physics["filling_particles_per_site"] * sites
    particles = round(particles_float)
    if not math.isclose(particles_float, particles, abs_tol=1e-12):
        raise ValueError("filling times spatial sites must give an integer particle count")
    t_time = physics["dimensionless_evolution_time_tT"]
    u_over_t = physics["onsite_u_over_t"]
    return {
        "linear_size_L": l,
        "spatial_sites_V": sites,
        "fermionic_modes_N": n,
        "particle_count": particles,
        "open_boundary_spatial_edges_E": 2 * l * (l - 1),
        "spin_resolved_hopping_terms": 4 * l * (l - 1),
        "hopping_t_energy_units": physics["hopping_t_energy_units"],
        "onsite_u_over_t": physics["onsite_u_over_t"],
        "dimensionless_evolution_time_tT": physics[
            "dimensionless_evolution_time_tT"
        ],
        "filling_particles_per_site": physics["filling_particles_per_site"],
        "initial_state": physics["initial_state"],
        "observables": physics["observables"],
        "measurement_settings": physics["measurement_settings"],
        "error_metric": physics["error_metric"],
        "trotter_formula": "second-order Suzuki--Trotter (Strang)",
        "target_group_order": "H1,H2,HU,H3,H4,H4,H3,HU,H2,H1",
        "group_order_status": (
            "Reconstructed common-order target from dynamic-JW Fig. 14; a full "
            "cross-compiler circuit export is still required to validate identical "
            "individual-term ordering and preserve each quoted resource count."
        ),
        "trotter_steps_R": r,
        "target_native_gate_parameters": {
            "hopping_half_abs_theta": t_time / r,
            "hopping_full_abs_theta": 2 * t_time / r,
            "onsite_half_abs_phi": u_over_t * t_time / (2 * r),
            "convention": (
                "PNAS native-gate parameter convention with hbar=1; signs follow "
                "the Hamiltonian and are omitted from these absolute values."
            ),
        },
        "target_total_error": workload["target_total_error"],
        "algorithmic_error_budget": workload["algorithmic_error_budget"],
        "statistical_error_budget": workload["statistical_error_budget"],
        "hardware_error_budget": workload["hardware_error_budget"],
        "r_selection": (
            "R is a shared planning input, not a validated error certificate. Select it "
            "only after same-ordering convergence tests for the stated observables."
        ),
        "route_execution_plans": {
            route: _execution_plan(config, route) for route in SAMPLING_ROUTES
        },
    }


def _route_row(
    *,
    route: str,
    estimate_kind: str,
    count_subtotal: Optional[int],
    complete_count: Optional[int],
    count_unit: str,
    depth_subtotal: Optional[int],
    complete_depth: Optional[int],
    depth_unit: str,
    topology: str,
    provenance: str,
    hardware_budget: float,
    **extra: Any,
) -> Dict[str, Any]:
    denominator = complete_count if complete_count is not None else count_subtotal
    return {
        "route": route,
        "estimate_kind": estimate_kind,
        "counted_subtotal": count_subtotal,
        "complete_count": complete_count,
        "count_unit": count_unit,
        "depth_subtotal": depth_subtotal,
        "complete_depth": complete_depth,
        "depth_unit": depth_unit,
        "topology": topology,
        "provenance": provenance,
        "optimistic_max_error_per_counted_location": _required_error(
            hardware_budget, denominator
        ),
        "error_denominator_status": (
            "complete_count" if complete_count is not None else "incomplete_subtotal"
        ),
        **extra,
    }


def logical_routes(config: Mapping[str, Any], w: Mapping[str, Any]) -> List[Dict[str, Any]]:
    l = w["linear_size_L"]
    n = w["fermionic_modes_N"]
    sites = w["spatial_sites_V"]
    g_hop = w["spin_resolved_hopping_terms"]
    r = w["trotter_steps_R"]
    budget = w["hardware_error_budget"]
    first_count = config["first_step_extra_cnot"]
    first_depth = config["first_step_extra_cnot_depth"]

    large_matching = 2 * l * (l // 2)
    small_matching = 2 * l * ((l - 1) // 2)
    g1, g2, g3, g4 = (
        large_matching,
        small_matching,
        small_matching,
        large_matching,
    )
    assert g1 + g2 + g3 + g4 == g_hop
    native_hopping = r * (2 * g_hop - g4) - (r - 1) * g1
    native_onsite = 2 * r * sites
    native_total = native_hopping + native_onsite

    rows: List[Dict[str, Any]] = [
        _route_row(
            route="native_fermions",
            estimate_kind="derived_common_group_order_schedule",
            count_subtotal=native_total,
            complete_count=native_total,
            count_unit="PNAS mode-resolved native hopping/interaction macro gates",
            depth_subtotal=8 * r + 1,
            complete_depth=8 * r + 1,
            depth_unit="native macro-gate layers",
            topology="open 2D square; four edge matchings; both spins parallel",
            provenance=(
                "Root-team graph-coloring schedule using the common group-order target; "
                "not a resource table reported by PNAS or Nature."
            ),
            hardware_budget=budget,
            count_breakdown={"hopping": native_hopping, "onsite": native_onsite},
            matching_sizes={"g1": g1, "g2": g2, "g3": g3, "g4": g4},
            depth_breakdown={
                "hopping_layers": 6 * r + 1,
                "onsite_half_angle_layers": 2 * r,
                "half_angle_hopping_layers": 4 * r + 2,
                "full_h1_boundary_layers": r - 1,
                "full_h4_central_layers": r,
            },
            caveat=(
                "The matching assignment is optimized so the two large color classes "
                "occupy H1 and H4. A cross-compiler export must confirm compatibility "
                "with the dynamic-JW circuit's individual-term order."
            ),
        )
    ]

    def add_steady_route(
        route: str,
        family: str,
        kind: str,
        per_step_count: Optional[int],
        per_step_depth: Optional[int],
        count_unit: str,
        depth_unit: str,
        topology: str,
        provenance: str,
        applicability: str,
    ) -> None:
        subtotal_count = None if per_step_count is None else per_step_count * r
        subtotal_depth = None if per_step_depth is None else per_step_depth * r
        count_extra = first_count[family]
        depth_extra = first_depth[family]
        complete_count = (
            None
            if subtotal_count is None or count_extra is None
            else subtotal_count + count_extra
        )
        complete_depth = (
            None
            if subtotal_depth is None or depth_extra is None
            else subtotal_depth + depth_extra
        )
        rows.append(
            _route_row(
                route=route,
                estimate_kind=kind,
                count_subtotal=subtotal_count,
                complete_count=None,
                count_unit=count_unit,
                depth_subtotal=subtotal_depth,
                complete_depth=None,
                depth_unit=depth_unit,
                topology=topology,
                provenance=provenance,
                hardware_budget=budget,
                steady_count_per_step=per_step_count,
                steady_depth_per_step=per_step_depth,
                first_step_extra_cnot=count_extra,
                first_step_extra_cnot_depth=depth_extra,
                first_step_closed_count_estimate=complete_count,
                first_step_closed_depth_estimate=complete_depth,
                applicability=applicability,
                caveat=(
                    "The source omits the extra first-step circuit cost. Supplying both "
                    "corrections closes that bookkeeping gap but does not turn a leading "
                    "or figure-fit steady value into an exact compiled total; complete "
                    "count and depth therefore remain unresolved."
                ),
            )
        )

    add_steady_route(
        "dynamic_jw_local_grid_source_leading",
        "dynamic_jw",
        "source_reported_leading_steady_state",
        21 * n,
        4 * l,
        "logical CNOT",
        "leading logical CNOT layers",
        f"nearest-neighbor {l} x {2*l} qubit grid",
        "arXiv:2605.12600v1 Table I and Appendix I",
        "Source leading expression; fixed-range spinful square-NN construction.",
    )

    in_figure_domain = FIGURE_FIT_L_MIN <= l <= FIGURE_FIT_L_MAX
    domain_text = (
        "Candidate fit is reported only for the plotted L=4...10 points."
        if in_figure_domain
        else "Outside the plotted L=4...10 domain; numeric fit intentionally unresolved."
    )
    add_steady_route(
        "dynamic_jw_local_grid_figure_candidate_fit",
        "dynamic_jw",
        "candidate_fit_to_figure_not_source_formula",
        42 * l * l - 24 * l if in_figure_domain else None,
        4 * l + 30 if in_figure_domain else None,
        "logical CNOT",
        "candidate finite-size CNOT-layer fit",
        f"nearest-neighbor {l} x {2*l} qubit grid",
        "Candidate schedule fit to arXiv:2605.12600v1 Figs. 5, 14, and 15",
        domain_text,
    )
    add_steady_route(
        "fsn_standard_figure_candidate_fit",
        "fsn_standard",
        "candidate_fit_to_figure_not_source_formula",
        16 * l**3 - 2 * l * (l - 1) if in_figure_domain else None,
        16 * l if in_figure_domain else None,
        "logical CNOT",
        "leading figure-slope CNOT layers",
        "one-dimensional nearest-neighbor line",
        "Candidate schedule fit to arXiv:2605.12600v1 Figs. 5 and 15",
        domain_text + " The paper directly supports only O(N^(3/2)) count and O(L) depth.",
    )
    add_steady_route(
        "fsn_ladder_figure_candidate_fit",
        "fsn_ladder",
        "candidate_fit_to_figure_not_source_formula",
        8 * l**3 - 2 * l * (l - 1) if in_figure_domain else None,
        8 * l if in_figure_domain else None,
        "logical CNOT",
        "leading figure-slope CNOT layers",
        "spin-separated ladder/rung connectivity",
        "Candidate schedule fit to arXiv:2605.12600v1 Figs. 5 and 15",
        domain_text + " The paper directly supports only an approximate halving of FSN cost.",
    )
    return rows


def _overheads(
    timing: Mapping[str, Any], route: str
) -> Dict[str, Optional[float]]:
    row = timing["route_overheads"][route]
    return {
        key: _optional_nonnegative(
            row.get(key), f"timing_us.route_overheads.{route}.{key}"
        )
        for key in (
            "classical_preprocessing_us",
            "prep_us",
            "readout_reset_us",
            "classical_postprocess_per_execution_us",
        )
    }


def _campaign_time(
    circuit_us: Optional[float],
    overheads: Mapping[str, Optional[float]],
    expected_executions: Optional[int],
) -> Optional[float]:
    if circuit_us is None or expected_executions is None or any(
        value is None for value in overheads.values()
    ):
        return None
    per_execution = (
        overheads["prep_us"]
        + circuit_us
        + overheads["readout_reset_us"]
        + overheads["classical_postprocess_per_execution_us"]
    )
    return overheads["classical_preprocessing_us"] + expected_executions * per_execution


def _campaign_missing(
    overheads: Mapping[str, Optional[float]], expected_executions: Optional[int]
) -> List[str]:
    missing = [key for key, value in overheads.items() if value is None]
    if expected_executions is None:
        missing.append("route-specific acceptance_probability/mitigation_repetition_multiplier")
    return missing


def physical_translation(
    config: Mapping[str, Any], w: Mapping[str, Any], routes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    timing = config["timing_us"]
    route_map = {row["route"]: row for row in routes}
    plans = w["route_execution_plans"]
    r = w["trotter_steps_R"]
    n = w["fermionic_modes_N"]
    l = w["linear_size_L"]

    native_terms = {
        key: _optional_nonnegative(timing.get(key), f"timing_us.{key}")
        for key in (
            "native_h1_half_layer_us",
            "native_h2_half_layer_us",
            "native_h3_half_layer_us",
            "native_h1_full_boundary_layer_us",
            "native_h4_full_central_layer_us",
            "native_onsite_half_layer_us",
        )
    }
    native_padded_time_upper_bound_us = _known_sum(
        [
            None
            if native_terms["native_h1_half_layer_us"] is None
            else 2 * native_terms["native_h1_half_layer_us"],
            None
            if native_terms["native_h2_half_layer_us"] is None
            else 2 * r * native_terms["native_h2_half_layer_us"],
            None
            if native_terms["native_h3_half_layer_us"] is None
            else 2 * r * native_terms["native_h3_half_layer_us"],
            None
            if native_terms["native_h1_full_boundary_layer_us"] is None
            else (r - 1) * native_terms["native_h1_full_boundary_layer_us"],
            None
            if native_terms["native_h4_full_central_layer_us"] is None
            else r * native_terms["native_h4_full_central_layer_us"],
            None
            if native_terms["native_onsite_half_layer_us"] is None
            else 2 * r * native_terms["native_onsite_half_layer_us"],
        ]
    )
    native_plan = plans["native_fermions"]
    native_overheads = _overheads(timing, "native_fermions")
    native_hardware = config["native_hardware"]
    native_space_missing = [
        key
        for key in ("storage_traps", "transport_tweezers", "workspace_sites")
        if native_hardware.get(key) is None
    ]

    bare_routes: Dict[str, Any] = {}
    bare_specs = (
        (
            "dynamic_jw_local_grid_source_leading",
            "dynamic_jw",
            "dynamic_jw_local_grid",
        ),
        (
            "dynamic_jw_local_grid_figure_candidate_fit",
            "dynamic_jw",
            "dynamic_jw_local_grid",
        ),
        ("fsn_standard_figure_candidate_fit", "fsn_standard", "fsn_standard"),
        ("fsn_ladder_figure_candidate_fit", "fsn_ladder", "fsn_ladder"),
    )
    for route_name, timing_key, sampling_key in bare_specs:
        row = route_map[route_name]
        bare = timing["bare_qubit_routes"][timing_key]
        cnot_layer_us = _optional_nonnegative(
            bare.get("cnot_layer_us"),
            f"timing_us.bare_qubit_routes.{timing_key}.cnot_layer_us",
        )
        non_cnot_step_us = _optional_nonnegative(
            bare.get("non_cnot_us_per_steady_step"),
            f"timing_us.bare_qubit_routes.{timing_key}.non_cnot_us_per_steady_step",
        )
        first_non_cnot_us = _optional_nonnegative(
            bare.get("first_step_extra_non_cnot_us"),
            f"timing_us.bare_qubit_routes.{timing_key}.first_step_extra_non_cnot_us",
        )
        cnot_subtotal_us = (
            None
            if cnot_layer_us is None or row["depth_subtotal"] is None
            else cnot_layer_us * row["depth_subtotal"]
        )
        planning_subtotal_us = _known_sum(
            [
                cnot_subtotal_us,
                None if non_cnot_step_us is None else r * non_cnot_step_us,
            ]
        )
        first_step_closed_planning_estimate_us = _known_sum(
            [
                None
                if cnot_layer_us is None
                or row["first_step_closed_depth_estimate"] is None
                else cnot_layer_us * row["first_step_closed_depth_estimate"],
                None if non_cnot_step_us is None else r * non_cnot_step_us,
                first_non_cnot_us,
            ]
        )
        plan = plans[sampling_key]
        route_overheads = _overheads(timing, sampling_key)
        missing = [
            key
            for key, value in (
                ("cnot_layer_us", cnot_layer_us),
                ("non_cnot_us_per_steady_step", non_cnot_step_us),
                ("first_step_extra_non_cnot_us", first_non_cnot_us),
                ("first_step_extra_cnot_depth", row["first_step_extra_cnot_depth"]),
            )
            if value is None
        ]
        bare_routes[route_name] = {
            "cnot_layer_subtotal_us": cnot_subtotal_us,
            "planning_steady_state_subtotal_us": planning_subtotal_us,
            "first_step_closed_planning_estimate_us": (
                first_step_closed_planning_estimate_us
            ),
            "complete_circuit_us": None,
            "expected_campaign_us": None,
            "missing_for_complete_time": missing
            + ["exact compiled steady-state count/depth and route timing"]
            + _campaign_missing(
                route_overheads, plan["expected_raw_circuit_executions"]
            ),
        }

    surface = config["surface_code"]
    d = surface["distance"]
    cycle_us = float(surface["cycle_us"])
    reaction_cycles = math.ceil(surface["reaction_us"] / cycle_us)
    ladder_cycles = (
        2 * surface["joint_measurement_cycles"]
        + surface["aux_readout_cycles"]
        + 4 * surface["single_qubit_clifford_cycles"]
        + surface["feedforward_barriers_per_ladder"] * reaction_cycles
    )
    blocks = surface["c2d_blocks_per_switch"]
    ladder_macros = 4 * blocks
    cz_layers = blocks
    configured_switch_partial_cycles = (
        ladder_macros * ladder_cycles + cz_layers * surface["cz_layer_cycles"]
    )
    configured_switch_only_cycles = 2 * r * configured_switch_partial_cycles
    spinful_swap_cycles = _optional_nonnegative_int(
        surface.get("spinful_swap_cycles_per_switch"),
        "surface_code.spinful_swap_cycles_per_switch",
    )
    local_rotation_cycles = _optional_nonnegative_int(
        surface.get("local_rotation_cycles_per_step"),
        "surface_code.local_rotation_cycles_per_step",
    )
    algorithm_schedule_excluding_factory = _known_sum(
        [
            None
            if spinful_swap_cycles is None
            else 2 * r * (configured_switch_partial_cycles + spinful_swap_cycles),
            None
            if local_rotation_cycles is None
            else r * local_rotation_cycles,
        ]
    )

    explicit_aux = 2 * l * (l - 1)
    configured_aux = surface.get("auxiliary_patches")
    auxiliary_patches = explicit_aux if configured_aux is None else configured_aux
    q_patch = 2 * d * d - 1
    data_patch_physical_qubits = n * q_patch
    construction_layer_patches = n + auxiliary_patches
    construction_layer_physical_qubits = construction_layer_patches * q_patch
    configured_core_switch_product = (
        construction_layer_physical_qubits * configured_switch_only_cycles
    )
    routing = surface.get("routing_patches")
    factory_patches = surface.get("factory_patches")
    configured_total_patches = (
        None
        if routing is None or factory_patches is None
        else construction_layer_patches + routing + factory_patches
    )
    configured_total_physical_qubits = (
        None if configured_total_patches is None else configured_total_patches * q_patch
    )

    magic_states = surface.get("magic_states_per_step")
    magic_interval = surface.get("magic_state_output_interval_cycles")
    factory_count = surface.get("factory_count")
    optimistic_magic_throughput_cycles = None
    if (
        magic_states is not None
        and magic_interval is not None
        and factory_count is not None
        and factory_count > 0
    ):
        optimistic_magic_throughput_cycles = (
            math.ceil(r * magic_states / factory_count) * magic_interval
        )
    optimistic_overlap_bound_cycles = None
    if (
        algorithm_schedule_excluding_factory is not None
        and optimistic_magic_throughput_cycles is not None
    ):
        optimistic_overlap_bound_cycles = max(
            algorithm_schedule_excluding_factory,
            optimistic_magic_throughput_cycles,
        )

    surface_plan = plans["dynamic_jw_surface_code"]
    surface_overheads = _overheads(timing, "dynamic_jw_surface_code")
    surface_missing = [
        key
        for key, value in (
            ("spinful_swap_cycles_per_switch", spinful_swap_cycles),
            ("local_rotation_cycles_per_step", local_rotation_cycles),
            ("routing_patches", routing),
            ("factory_patches", factory_patches),
            ("magic_states_per_step", magic_states),
            ("magic_state_output_interval_cycles", magic_interval),
            ("factory_count", factory_count),
        )
        if value is None
    ]
    surface_missing.extend(
        [
            "validated active-patch layer schedule",
            "factory startup/buffer/injection/routing/failure dependency schedule",
            "distance-d logical failure allocation",
        ]
    )
    surface_missing += _campaign_missing(
        surface_overheads, surface_plan["expected_raw_circuit_executions"]
    )

    return {
        "native_fermions": {
            "configured_padded_circuit_time_upper_bound_us": (
                native_padded_time_upper_bound_us
            ),
            "complete_circuit_us": None,
            "expected_padded_campaign_upper_bound_us": _campaign_time(
                native_padded_time_upper_bound_us,
                native_overheads,
                native_plan["expected_raw_circuit_executions"],
            ),
            "expected_campaign_us": None,
            "particle_count": w["particle_count"],
            "storage_mode_capacity_floor": n,
            "storage_traps": native_hardware.get("storage_traps"),
            "transport_tweezers": native_hardware.get("transport_tweezers"),
            "workspace_sites": native_hardware.get("workspace_sites"),
            "padded_time_coefficients": {
                "h1_half": 2,
                "h2_half": 2 * r,
                "h3_half": 2 * r,
                "h1_full_boundary": r - 1,
                "h4_full_central": r,
                "onsite_half": 2 * r,
            },
            "missing_for_complete_time_or_space": [
                key for key, value in native_terms.items() if value is None
            ]
            + native_space_missing
            + ["occurrence-level incoming-layout transition schedule"]
            + _campaign_missing(
                native_overheads, native_plan["expected_raw_circuit_executions"]
            ),
            "warning": (
                "A scalar layer time is reused across multiple incoming-layout contexts. "
                "It must therefore be a padded worst-case value covering reconfiguration, "
                "ramp, gate, cooling/echo, and return policy; the sum is only a configured "
                "upper-bound scenario. Exact complete time requires an occurrence-level "
                "transition table, which PNAS does not report."
            ),
        },
        "bare_qubit_routes": bare_routes,
        "dynamic_jw_surface_code": {
            "distance": d,
            "qubits_per_rotated_patch": q_patch,
            "ladder_cycles": ladder_cycles,
            "configured_c2d_blocks_per_switch": blocks,
            "configured_ladder_macros_per_switch": ladder_macros,
            "configured_cz_layers_per_switch": cz_layers,
            "configured_optimistic_partial_switch_cycles": configured_switch_partial_cycles,
            "configured_switch_only_cycles_all_steps": configured_switch_only_cycles,
            "configured_switch_only_us_all_steps": configured_switch_only_cycles * cycle_us,
            "algorithm_schedule_cycles_excluding_factory": algorithm_schedule_excluding_factory,
            "optimistic_magic_supply_throughput_cycles": optimistic_magic_throughput_cycles,
            "optimistic_overlap_latency_bound_cycles": optimistic_overlap_bound_cycles,
            "optimistic_overlap_latency_bound_us": (
                None
                if optimistic_overlap_bound_cycles is None
                else optimistic_overlap_bound_cycles * cycle_us
            ),
            "complete_circuit_us": None,
            "expected_campaign_us": None,
            "data_patch_physical_qubits": data_patch_physical_qubits,
            "explicit_column_ladder_auxiliary_patches": explicit_aux,
            "configured_auxiliary_patches": auxiliary_patches,
            "construction_layer_patch_footprint": construction_layer_patches,
            "construction_layer_physical_qubit_footprint": (
                construction_layer_physical_qubits
            ),
            "configured_peak_core_times_switch_cycles_product": (
                configured_core_switch_product
            ),
            "configured_total_patches": configured_total_patches,
            "configured_total_physical_qubits": configured_total_physical_qubits,
            "active_layer_summed_volume_physical_qubit_cycles": None,
            "missing_for_complete_time_or_space": surface_missing,
            "warning": (
                "All switch, footprint, and max-overlap values are configured scenario "
                "quantities, not source-reported complete resources. The max of circuit "
                "and factory throughput is only an optimistic latency lower bound; it "
                "assumes perfect overlap and omits startup, injection, buffering, routing, "
                "and failure dependencies. Clifford-frame tracking can also change later "
                "boundary access and routing."
            ),
        },
    }


def build_model(config: Mapping[str, Any]) -> Dict[str, Any]:
    validate_config(config)
    workload = workload_quantities(config)
    routes = logical_routes(config, workload)
    return {
        "model_status": "evidence_bounded_planning_model_not_matched_benchmark",
        "model_version": 2,
        "workload": workload,
        "logical_routes": routes,
        "physical_translation": physical_translation(config, workload, routes),
        "interpretation_rules": [
            "The common group order is a target pending cross-compiler circuit validation.",
            "Closing first-step bookkeeping does not make leading or figure-fit steady values exact compiled totals.",
            "Figure candidate fits are numeric only inside the plotted L=4...10 domain.",
            "A native layer, CNOT layer, and lattice-surgery round are different units.",
            "Per-location union-bound requirements use heterogeneous optimistic denominators.",
            "Expected raw executions are not high-confidence stopping bounds.",
            "Surface footprint products are construction scenarios, not universal bounds or active volumes.",
        ],
    }


def _fmt(value: Any) -> str:
    if value is None:
        return "UNRESOLVED"
    if isinstance(value, float):
        if value == 0:
            return "0"
        if abs(value) < 1e-3 or abs(value) >= 1e6:
            return f"{value:.3e}"
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def markdown_summary(model: Mapping[str, Any]) -> str:
    w = model["workload"]
    lines = [
        "# Fermi--Hubbard evidence-bounded resource-model output",
        "",
        (
            f"Workload target: open {w['linear_size_L']} x {w['linear_size_L']}, "
            f"N={w['fermionic_modes_N']} modes, {w['particle_count']} particles, "
            f"U/t={w['onsite_u_over_t']}, tT={w['dimensionless_evolution_time_tT']}, "
            f"R={w['trotter_steps_R']}."
        ),
        "",
        f"Order status: {w['group_order_status']}",
        "",
        "## Logical resources",
        "",
        "| Route | Kind | Count subtotal | Complete count | Depth subtotal | Complete depth |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in model["logical_routes"]:
        lines.append(
            "| {route} | {kind} | {subtotal} | {complete} | {depth} | {complete_depth} |".format(
                route=row["route"],
                kind=row["estimate_kind"],
                subtotal=_fmt(row["counted_subtotal"]),
                complete=_fmt(row["complete_count"]),
                depth=_fmt(row["depth_subtotal"]),
                complete_depth=_fmt(row["complete_depth"]),
            )
        )
    lines.extend(
        [
            "",
            (
                "Complete dynamic/FSN totals remain unresolved: first-step corrections "
                "are null and leading/figure-fit steady values are not exact compiled totals."
            ),
            "",
            "## Physical translation",
            "",
            "| Route | Complete circuit us | Expected campaign us |",
            "|---|---:|---:|",
        ]
    )
    physical = model["physical_translation"]
    native = physical["native_fermions"]
    lines.append(
        f"| native_fermions | {_fmt(native['complete_circuit_us'])} | "
        f"{_fmt(native['expected_campaign_us'])} |"
    )
    for name, row in physical["bare_qubit_routes"].items():
        lines.append(
            f"| {name} | {_fmt(row['complete_circuit_us'])} | "
            f"{_fmt(row['expected_campaign_us'])} |"
        )
    surface = physical["dynamic_jw_surface_code"]
    lines.append("| dynamic_jw_surface_code | UNRESOLVED | UNRESOLVED |")
    lines.extend(
        [
            "",
            (
                "Surface configured partial switch subtotal: "
                f"{_fmt(surface['configured_switch_only_us_all_steps'])} us; "
                "explicit construction-layer footprint: "
                f"{_fmt(surface['construction_layer_physical_qubit_footprint'])} "
                "physical qubits (routing/factories excluded)."
            ),
            "",
            "UNRESOLVED is a result: the cited evidence does not determine a complete quantity.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    with args.config.open(encoding="utf-8") as handle:
        config = json.load(handle)
    model = build_model(config)
    if args.format == "markdown":
        print(markdown_summary(model), end="")
    else:
        print(json.dumps(model, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
