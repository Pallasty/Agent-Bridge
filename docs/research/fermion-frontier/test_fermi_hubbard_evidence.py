import copy
import importlib.util
import json
import pathlib
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fermi_hubbard_evidence", HERE / "fermi_hubbard_evidence.py"
)
EVIDENCE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(EVIDENCE)

VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "term_order_validator_for_evidence_test", HERE / "term_order_validator.py"
)
TERM_VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(TERM_VALIDATOR)


def load_json(name):
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class EvidenceManifestTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_json("evidence_manifest_contract.json")
        self.manifest = load_json("evidence_manifest_template.json")
        self.term_contract = load_json("term_order_contract.json")
        self.first_step_contract = load_json("first_step_contract.json")
        self.native_transition_contract = load_json("native_transition_contract.json")
        self.surface_place_route_contract = load_json("surface_place_route_contract.json")

    def test_empty_manifest_is_unresolved_with_component_statuses(self):
        result = EVIDENCE.validate_manifest(
            self.contract,
            self.manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            self.surface_place_route_contract,
        )
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(
            result["component_statuses"],
            {
                "term_order": "UNRESOLVED",
                "first_step": "UNRESOLVED",
                "native_transition": "UNRESOLVED",
                "surface_place_route": "UNRESOLVED",
                "convergence": "UNRESOLVED",
            },
        )

    def test_source_snapshot_preserves_known_subtotals_without_closure(self):
        snapshot = load_json("evidence_manifest_source_snapshot.json")
        result = EVIDENCE.validate_manifest(
            self.contract,
            snapshot,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            self.surface_place_route_contract,
        )
        self.assertEqual(result["status"], "UNRESOLVED")
        native_route = result["components"]["first_step"]["routes"]["native_fermions"]
        self.assertEqual(native_route["complete_count"], 44864)
        self.assertEqual(native_route["complete_depth"], 801)
        dynamic_route = result["components"]["first_step"]["routes"][
            "dynamic_jw_local_grid_source_leading"
        ]
        self.assertEqual(dynamic_route["steady_count_per_step"], 2688)
        self.assertEqual(result["component_statuses"]["native_transition"], "UNRESOLVED")
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(
            result["component_statuses"],
            {
                "term_order": "UNRESOLVED",
                "first_step": "UNRESOLVED",
                "native_transition": "UNRESOLVED",
                "surface_place_route": "UNRESOLVED",
                "convergence": "UNRESOLVED",
            },
        )

    def _exact_term_export(self, route, r=2):
        terms = TERM_VALIDATOR.expected_terms(8)
        events = [
            {"group": group, "terms": list(terms[group])}
            for group in TERM_VALIDATOR.GROUP_ORDER
        ]
        return {
            "schema_version": 1,
            "route": route,
            "linear_size": 8,
            "trotter_steps": r,
            "steps": [{"step": step, "events": copy.deepcopy(events)} for step in range(r)],
        }

    def _complete_first_step_route(self, r=2):
        return {
            "R": r,
            "steady_count_per_step": 10,
            "steady_depth_per_step": 4,
            "first_step_extra_count": 1,
            "first_step_extra_depth": 1,
            "compiled_exact": True,
            "provenance": "synthetic integration fixture",
            "timing": {
                "cnot_layer_us": 0.001,
                "non_cnot_us_per_steady_step": 0.01,
                "first_step_extra_non_cnot_us": 0.02,
                "timing_provenance": "synthetic integration timing",
            },
        }

    def _convergence_metadata(self, workload, route):
        metadata = {"route": route}
        metadata.update(
            {
                key: copy.deepcopy(workload[key])
                for key in (
                    "observable_order",
                    "measurement_setting",
                    "initial_state",
                    "initial_state_fingerprint",
                    "hamiltonian_fingerprint",
                    "evolution_fingerprint",
                    "trotter_formula",
                    "analysis_plan_fingerprint",
                )
            }
        )
        return metadata

    def _convergence_point(self, route, r, magnetization, double_occupancy):
        return {
            "R": r,
            "batch_id": f"synthetic-{route}-R{r}",
            "attempted_shots": 0,
            "accepted_shots": 0,
            "observable_order": list(EVIDENCE.CONVERGENCE.OBSERVABLE_ORDER),
            "estimates": {
                "staggered_magnetization": magnetization,
                "double_occupancy": double_occupancy,
            },
            "covariance_of_estimator_mean": [[0.0, 0.0], [0.0, 0.0]],
            "systematic_abs_bounds": {
                "staggered_magnetization": 0.0,
                "double_occupancy": 0.0,
            },
            "systematic_bound_status": "rigorous_bound",
            "covariance_provenance": "synthetic exact covariance",
            "measurement_provenance": "synthetic deterministic simulation",
            "mitigation_provenance": "none in synthetic fixture",
            "systematic_bound_provenance": "zero in synthetic fixture",
            "circuit_fingerprint": f"synthetic-circuit-{route}-R{r}",
            "term_sequence_fingerprint": f"synthetic-terms-{route}-R{r}",
        }

    def _convergence_route(self, workload, route):
        magnetization = [0.5, 0.996, 0.997, 0.998, 0.999, 0.9995]
        double_occupancy = [0.05, 0.196, 0.197, 0.198, 0.199, 0.1995]
        return {
            "metadata": self._convergence_metadata(workload, route),
            "sampling_mode": "deterministic_simulation",
            "points": [
                self._convergence_point(route, r, magnetization_value, occupancy_value)
                for r, magnetization_value, occupancy_value in zip(
                    workload["planned_R_values"], magnetization, double_occupancy
                )
            ],
        }

    def _binding_references(self, workload):
        references = {
            "staggered_magnetization": {
                "value": 1.0,
                "kind": "exact_bounded",
                "standard_error": 0.0,
                "systematic_abs_bound": 0.0,
                "uncertainty_evidence_status": "rigorous_bound",
                "independent_of_route_estimates": True,
                "provenance": "synthetic independent exact reference",
            },
            "double_occupancy": {
                "value": 0.2,
                "kind": "exact_bounded",
                "standard_error": 0.0,
                "systematic_abs_bound": 0.0,
                "uncertainty_evidence_status": "rigorous_bound",
                "independent_of_route_estimates": True,
                "provenance": "synthetic independent exact reference",
            },
        }
        for observable, reference in references.items():
            reference.update(
                {
                    "hamiltonian_fingerprint": workload["hamiltonian_fingerprint"],
                    "initial_state_fingerprint": workload[
                        "initial_state_fingerprint"
                    ],
                    "evolution_fingerprint": workload["evolution_fingerprint"],
                    "observable_definition_fingerprint": workload["observables"][
                        observable
                    ]["definition_fingerprint"],
                    "reference_target": "ideal_exact_time_evolution",
                }
            )
        return references

    def _complete_surface_ledger(self, manifest, surface_contract):
        term_result = EVIDENCE.TERM.compare_routes(self.term_contract, manifest["term_order"])
        self.assertEqual(term_result["status"], "MATCHED")
        distance = 3
        physical_qubits = 2 * distance * distance - 1
        patches = [
            {"patch_id": f"d{index}", "role": "data", "physical_qubits": physical_qubits}
            for index in range(2 * 8 * 8)
        ]
        patches.append(
            {"patch_id": "a0", "role": "auxiliary", "physical_qubits": physical_qubits}
        )
        patches.append(
            {"patch_id": "f0", "role": "factory", "physical_qubits": physical_qubits}
        )
        patches.append(
            {"patch_id": "b0", "role": "buffer", "physical_qubits": physical_qubits}
        )
        placements = [
            {
                "patch_id": patch["patch_id"],
                "row": (
                    0
                    if patch["patch_id"] == "a0"
                    else 1
                    if patch["patch_id"] in {"d0", "f0", "b0"}
                    else 2 + (int(patch["patch_id"][1:]) - 1) // 16
                ),
                "col": (
                    0
                    if patch["patch_id"] in {"a0", "d0"}
                    else 1
                    if patch["patch_id"] == "b0"
                    else 2
                    if patch["patch_id"] == "f0"
                    else (int(patch["patch_id"][1:]) - 1) % 16
                ),
                "orientation": "N",
                "available_boundaries": ["N", "E", "S", "W"],
            }
            for index, patch in enumerate(patches)
        ]
        logical_event_count = (
            surface_contract["target_trotter_steps"]
            * surface_contract["logical_events_per_trotter_step"]
        )
        operations = [
            {
                "operation_id": f"op{event}",
                "kind": "ladder_joint_measurement",
                "start_offset_cycles": 3 * event,
                "duration_cycles": 3,
                "participant_patch_ids": ["d0", "a0"],
                "corridor_patch_ids": [],
                "required_boundaries": [
                    {"patch_id": "d0", "boundary": "N"},
                    {"patch_id": "a0", "boundary": "S"},
                ],
                "depends_on": ["rotation0"] if event == 0 else [],
                "logical_event_ids": [event],
                "logical_failure_probability": 0.0001,
                "evidence_status": "compiler_export",
                "provenance": "synthetic integration operation",
            }
            for event in range(logical_event_count)
        ]
        return {
            "schema_version": 1,
            "workload_fingerprint": self.contract["workload_fingerprint"],
            "route": "dynamic_jw_surface_code",
            "linear_size": 8,
            "trotter_steps": surface_contract["target_trotter_steps"],
            "logical_sequence_fingerprint": term_result["common_sequence_fingerprint"],
            "logical_event_count": logical_event_count,
            "distance": distance,
            "cycle_us": 1.0,
            "patch_model": surface_contract["patch_model"],
            "compiled_exact": True,
            "place_route_validated": True,
            "timing_evidence_status": "measured",
            "error_evidence_status": "measured",
            "schedule_provenance": "synthetic integration schedule",
            "timing_provenance": "synthetic integration timing",
            "error_model_provenance": "synthetic integration error model",
            "logical_failure_budget": 0.005,
            "patches": patches,
            "layouts": [{"layout_id": "layout0", "placements": placements}],
            "intervals": [
                {
                    "interval_index": 0,
                    "start_cycle": 0,
                    "duration_cycles": 3,
                    "layout_id": "layout0",
                    "live_patch_ids": [patch["patch_id"] for patch in patches],
                    "operations": [
                        {
                            "operation_id": "distill0",
                            "kind": "distill",
                            "start_offset_cycles": 0,
                            "duration_cycles": 3,
                            "participant_patch_ids": ["f0"],
                            "corridor_patch_ids": [],
                            "required_boundaries": [],
                            "depends_on": [],
                            "logical_event_ids": [],
                            "logical_failure_probability": 0.0001,
                            "evidence_status": "compiler_export",
                            "provenance": "synthetic integration distillation",
                        }
                    ],
                },
                {
                    "interval_index": 1,
                    "start_cycle": 3,
                    "duration_cycles": 1,
                    "layout_id": "layout0",
                    "live_patch_ids": [patch["patch_id"] for patch in patches],
                    "operations": [
                        {
                            "operation_id": "buffer0",
                            "kind": "buffer",
                            "start_offset_cycles": 0,
                            "duration_cycles": 1,
                            "participant_patch_ids": ["f0", "b0"],
                            "corridor_patch_ids": [],
                            "required_boundaries": [
                                {"patch_id": "f0", "boundary": "W"},
                                {"patch_id": "b0", "boundary": "E"},
                            ],
                            "depends_on": ["distill0"],
                            "logical_event_ids": [],
                            "logical_failure_probability": 0.0001,
                            "evidence_status": "compiler_export",
                            "provenance": "synthetic integration buffer",
                        }
                    ],
                },
                {
                    "interval_index": 2,
                    "start_cycle": 4,
                    "duration_cycles": 1,
                    "layout_id": "layout0",
                    "live_patch_ids": [patch["patch_id"] for patch in patches],
                    "operations": [
                        {
                            "operation_id": "inject0",
                            "kind": "inject",
                            "start_offset_cycles": 0,
                            "duration_cycles": 1,
                            "participant_patch_ids": ["b0", "d0"],
                            "corridor_patch_ids": [],
                            "required_boundaries": [
                                {"patch_id": "b0", "boundary": "W"},
                                {"patch_id": "d0", "boundary": "E"},
                            ],
                            "depends_on": ["buffer0"],
                            "logical_event_ids": [],
                            "logical_failure_probability": 0.0001,
                            "evidence_status": "compiler_export",
                            "provenance": "synthetic integration injection",
                        }
                    ],
                },
                {
                    "interval_index": 3,
                    "start_cycle": 5,
                    "duration_cycles": 1,
                    "layout_id": "layout0",
                    "live_patch_ids": [patch["patch_id"] for patch in patches],
                    "operations": [
                        {
                            "operation_id": "rotation0",
                            "kind": "rotation",
                            "start_offset_cycles": 0,
                            "duration_cycles": 1,
                            "participant_patch_ids": ["d0"],
                            "corridor_patch_ids": [],
                            "required_boundaries": [],
                            "depends_on": ["inject0"],
                            "logical_event_ids": [],
                            "logical_failure_probability": 0.0001,
                            "evidence_status": "compiler_export",
                            "provenance": "synthetic integration rotation",
                        }
                    ],
                },
                {
                    "interval_index": 4,
                    "start_cycle": 6,
                    "duration_cycles": 3 * logical_event_count,
                    "layout_id": "layout0",
                    "live_patch_ids": [patch["patch_id"] for patch in patches],
                    "operations": operations,
                },
            ],
        }

    def _ready_manifest(self):
        contract = copy.deepcopy(self.contract)
        contract["target_trotter_steps"] = 2
        convergence_workload = contract["convergence_workload_policy"]
        convergence_workload["target_R"] = 2
        convergence_workload["planned_R_values"] = [1, 2, 4, 8, 16, 32]
        convergence_workload[
            "analysis_plan_fingerprint"
        ] = "synthetic_dual_observable_R1_2_4_8_16_32_v1"
        surface_contract = copy.deepcopy(self.surface_place_route_contract)
        surface_contract["target_trotter_steps"] = 2
        manifest = copy.deepcopy(self.manifest)
        routes = contract["required_routes"]
        manifest["term_order"]["required_routes"] = list(self.term_contract["required_routes"])
        manifest["term_order"]["exports"] = {
            route: self._exact_term_export(route)
            for route in self.term_contract["required_routes"]
        }
        manifest["first_step"]["routes"] = {
            route: self._complete_first_step_route()
            for route in routes
        }
        native_occurrences = []
        occurrence_index = 0
        for occurrence_class, count_fn in EVIDENCE.NATIVE.CLASS_COUNTS.items():
            for _ in range(count_fn(2)):
                native_occurrences.append(
                    {
                        "occurrence_index": occurrence_index,
                        "class": occurrence_class,
                        "group": EVIDENCE.NATIVE.CLASS_GROUPS[occurrence_class],
                        "incoming_layout_id": f"layout_{occurrence_index}",
                        "outgoing_layout_id": f"layout_{occurrence_index + 1}",
                        "move_legs": 1,
                        "move_distance_um": 2.0,
                        "move_us": 1.0,
                        "gate_us": 2.0,
                        "cooling_echo_us": 0.5,
                        "return_us": 0.5,
                        "other_us": 0.0,
                        "transition_us": 4.0,
                        "loss_rate": 0.001,
                        "leakage_rate": 0.002,
                        "measurement_status": "measured",
                        "provenance": "synthetic native transition fixture",
                    }
                )
                occurrence_index += 1
        manifest["native_transition"] = {
            "schema_version": 1,
            "workload_fingerprint": self.contract["workload_fingerprint"],
            "route": "native_fermions",
            "linear_size": 8,
            "trotter_steps": 2,
            "compiled_exact": True,
            "timing_provenance": "synthetic native timing fixture",
            "occurrences": native_occurrences,
        }
        manifest["surface_place_route"] = self._complete_surface_ledger(
            manifest, surface_contract
        )
        convergence_routes = list(
            dict.fromkeys(
                contract["route_map"][route]["convergence_route"] for route in routes
            )
        )
        manifest["convergence"]["schema_version"] = 2
        manifest["convergence"]["workload"] = copy.deepcopy(convergence_workload)
        manifest["convergence"]["references"] = self._binding_references(
            convergence_workload
        )
        manifest["convergence"]["required_routes"] = convergence_routes
        manifest["convergence"]["routes"] = {
            route: self._convergence_route(convergence_workload, route)
            for route in convergence_routes
        }
        return contract, manifest, surface_contract

    def test_synthetic_all_component_closure_reaches_ready(self):
        contract, manifest, surface_contract = self._ready_manifest()
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(result["status"], "READY_FOR_BENCHMARK")
        self.assertEqual(
            result["component_statuses"],
            {
                "term_order": "MATCHED",
                "first_step": "COMPLETE",
                "native_transition": "COMPLETE",
                "surface_place_route": "COMPLETE",
                "convergence": "READY_FOR_TARGET_R",
            },
        )
        self.assertEqual(result["coherence_errors"], [])

    def test_term_and_ledger_r_mismatch_is_inconsistent(self):
        contract, manifest, surface_contract = self._ready_manifest()
        manifest["first_step"]["routes"]["native_fermions"]["R"] = 3
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(result["status"], "INCONSISTENT")
        self.assertTrue(any("trotter_steps" in error for error in result["coherence_errors"]))

    def test_surface_place_route_must_close_before_ready(self):
        contract, manifest, surface_contract = self._ready_manifest()
        unresolved_surface = copy.deepcopy(self.manifest["surface_place_route"])
        unresolved_surface["trotter_steps"] = 2
        unresolved_surface["logical_event_count"] = 20
        manifest["surface_place_route"] = unresolved_surface
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(result["component_statuses"]["surface_place_route"], "UNRESOLVED")

    def test_surface_sequence_fingerprint_mismatch_is_inconsistent(self):
        contract, manifest, surface_contract = self._ready_manifest()
        manifest["surface_place_route"]["logical_sequence_fingerprint"] = "0" * 64
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(result["status"], "INCONSISTENT")
        self.assertTrue(any("logical_sequence_fingerprint" in error for error in result["errors"]))

    def test_exact_term_mismatch_takes_priority_over_r_inconsistency(self):
        contract, manifest, surface_contract = self._ready_manifest()
        mismatch_route = self.term_contract["required_routes"][1]
        manifest["term_order"]["exports"][mismatch_route]["steps"][0]["events"][0][
            "terms"
        ].reverse()
        manifest["first_step"]["routes"]["native_fermions"]["R"] = 3
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(result["component_statuses"]["term_order"], "MISMATCH")
        self.assertTrue(result["coherence_errors"])
        self.assertEqual(result["status"], "MISMATCH")

    def test_target_r_before_one_observable_window_is_unresolved(self):
        contract, manifest, surface_contract = self._ready_manifest()
        late_occupancy = [0.05, 0.08, 0.11, 0.1965, 0.198, 0.199]
        for route in manifest["convergence"]["routes"].values():
            for value, point in zip(late_occupancy, route["points"]):
                point["estimates"]["double_occupancy"] = value
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(result["component_statuses"]["convergence"], "UNRESOLVED")
        self.assertEqual(
            result["components"]["convergence"]["routes"]["native_fermions"][
                "stable_from_R_by_observable"
            ]["double_occupancy"],
            8,
        )

    def test_route_map_drift_is_invalid_schema(self):
        contract = copy.deepcopy(self.contract)
        contract["route_map"]["unexpected_route"] = {
            "term_route": "unexpected_route",
            "convergence_route": "unexpected_route",
        }
        result = EVIDENCE.validate_manifest(
            contract,
            self.manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            self.surface_place_route_contract,
        )
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("route_map keys" in error for error in result["errors"]))

    def test_physical_surface_route_cannot_be_rebound_to_fsn(self):
        contract, manifest, surface_contract = self._ready_manifest()
        contract["physical_route_map"]["surface_place_route"].update(
            term_route="fsn_standard_figure_candidate_fit",
            convergence_route="fsn_standard",
        )
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(result["component_statuses"]["surface_place_route"], "COMPLETE")
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("parent_term_route" in error for error in result["errors"]))

    def test_required_route_names_must_be_unique(self):
        contract = copy.deepcopy(self.contract)
        contract["required_routes"][-1] = contract["required_routes"][-2]
        result = EVIDENCE.validate_manifest(
            contract,
            self.manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            self.surface_place_route_contract,
        )
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("unique route names" in error for error in result["errors"]))

    def test_component_identity_error_cannot_be_ignored_by_ready_components(self):
        contract, manifest, surface_contract = self._ready_manifest()
        manifest["convergence"]["workload"]["hamiltonian_fingerprint"] = "different"
        for route in manifest["convergence"]["routes"].values():
            route["metadata"]["hamiltonian_fingerprint"] = "different"
        for reference in manifest["convergence"]["references"].values():
            reference["hamiltonian_fingerprint"] = "different"
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(result["component_statuses"]["convergence"], "READY_FOR_TARGET_R")
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(
            any("convergence_workload_policy" in error for error in result["errors"])
        )

    def test_convergence_policy_drift_is_invalid_even_when_self_consistent(self):
        contract, manifest, surface_contract = self._ready_manifest()
        manifest["convergence"]["workload"]["familywise_error_rate"] = 0.1
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(result["component_statuses"]["convergence"], "READY_FOR_TARGET_R")
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(
            any("exactly match" in error for error in result["errors"])
        )

    def test_missing_second_observable_cannot_reach_ready(self):
        contract, manifest, surface_contract = self._ready_manifest()
        target_point = manifest["convergence"]["routes"]["native_fermions"]["points"][1]
        target_point["estimates"].pop("double_occupancy")
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(result["component_statuses"]["convergence"], "UNRESOLVED")
        self.assertEqual(result["status"], "UNRESOLVED")

    def test_screening_without_binding_references_cannot_reach_ready(self):
        contract, manifest, surface_contract = self._ready_manifest()
        manifest["convergence"]["references"] = None
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(
            result["component_statuses"]["convergence"], "SCREENED_FOR_TARGET_R"
        )
        self.assertEqual(result["status"], "UNRESOLVED")

    def test_outer_gate_rechecks_route_observable_stability_matrix(self):
        contract, manifest, surface_contract = self._ready_manifest()
        convergence_result = EVIDENCE.CONVERGENCE.assess_manifest(
            manifest["convergence"]
        )
        self.assertEqual(convergence_result["status"], "READY_FOR_TARGET_R")
        convergence_result["stable_from_R_by_route_observable"]["native_fermions"][
            "double_occupancy"
        ] = 4
        with mock.patch.object(
            EVIDENCE.CONVERGENCE,
            "assess_manifest",
            return_value=convergence_result,
        ):
            result = EVIDENCE.validate_manifest(
                contract,
                manifest,
                self.term_contract,
                self.first_step_contract,
                self.native_transition_contract,
                surface_contract,
            )
        self.assertEqual(result["component_statuses"]["convergence"], "READY_FOR_TARGET_R")
        self.assertEqual(result["status"], "INCONSISTENT")
        self.assertTrue(
            any(
                "native_fermions observable double_occupancy is not stable" in error
                for error in result["coherence_errors"]
            )
        )

    def test_surface_event_cardinality_must_match_term_sequence(self):
        contract, manifest, surface_contract = self._ready_manifest()
        surface_contract["logical_events_per_trotter_step"] = 9
        manifest["surface_place_route"]["logical_event_count"] = 18
        manifest["surface_place_route"]["intervals"][-1]["operations"] = manifest[
            "surface_place_route"
        ]["intervals"][-1]["operations"][:18]
        result = EVIDENCE.validate_manifest(
            contract,
            manifest,
            self.term_contract,
            self.first_step_contract,
            self.native_transition_contract,
            surface_contract,
        )
        self.assertEqual(result["component_statuses"]["surface_place_route"], "COMPLETE")
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("logical_events_per_trotter_step" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
