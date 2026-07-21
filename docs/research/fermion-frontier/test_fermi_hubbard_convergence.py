import copy
import importlib.util
import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fermi_hubbard_convergence", HERE / "fermi_hubbard_convergence.py"
)
CONVERGENCE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CONVERGENCE)


def template():
    with (HERE / "fermi_hubbard_convergence_template.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def metadata(workload, route_name):
    return {
        "route": route_name,
        **{
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
        },
    }


def point(r, magnetization, double_occupancy, variance=0.0, route_name="route"):
    record = {
        "R": r,
        "batch_id": f"{route_name}-R{r}",
        "attempted_shots": 0 if variance == 0 else 12000,
        "accepted_shots": 0 if variance == 0 else 10000,
        "observable_order": list(CONVERGENCE.OBSERVABLE_ORDER),
        "estimates": {
            "staggered_magnetization": magnetization,
            "double_occupancy": double_occupancy,
        },
        "covariance_of_estimator_mean": [[variance, 0.0], [0.0, variance]],
        "systematic_abs_bounds": {
            "staggered_magnetization": 0.0,
            "double_occupancy": 0.0,
        },
        "systematic_bound_status": "rigorous_bound",
        "covariance_provenance": "synthetic estimator covariance",
        "measurement_provenance": "synthetic shared occupation measurement",
        "mitigation_provenance": "none in synthetic fixture",
        "systematic_bound_provenance": "zero in synthetic fixture",
        "circuit_fingerprint": f"synthetic-circuit-{route_name}-R{r}",
        "term_sequence_fingerprint": f"synthetic-terms-{route_name}-R{r}",
    }
    if variance != 0:
        record.update(
            effective_independent_shots=10000,
            concentration_model="independent_bounded_samples",
            concentration_evidence_status="rigorous_bound",
            per_shot_contribution_ranges={
                "staggered_magnetization": [-1.0, 1.0],
                "double_occupancy": [0.0, 1.0],
            },
            mitigation_mode="none",
        )
    return record


def route(workload, route_name, magnetization, occupancy, variance=0.0):
    return {
        "metadata": metadata(workload, route_name),
        "sampling_mode": "deterministic_simulation" if variance == 0 else "shared_shots",
        "points": [
            point(r, m_value, d_value, variance, route_name)
            for r, m_value, d_value in zip(
                workload["planned_R_values"], magnetization, occupancy
            )
        ],
    }


class ConvergenceTests(unittest.TestCase):
    def setUp(self):
        self.manifest = template()
        workload = self.manifest["workload"]
        workload["target_R"] = 80
        workload["planned_R_values"] = [10, 20, 40, 80, 160, 320]
        workload["analysis_plan_fingerprint"] = "synthetic_dual_observable_plan_v1"
        magnetization_a = [0.70, 0.90, 0.97, 0.997, 0.999, 0.9995]
        magnetization_b = [0.60, 0.82, 0.95, 0.997, 0.999, 0.9995]
        occupancy_a = [0.05, 0.10, 0.18, 0.197, 0.199, 0.1995]
        occupancy_b = [0.03, 0.12, 0.17, 0.197, 0.199, 0.1995]
        self.manifest["required_routes"] = ["native_fermions", "dynamic_jw_local_grid"]
        self.manifest["routes"] = {
            "native_fermions": route(
                workload, "native_fermions", magnetization_a, occupancy_a
            ),
            "dynamic_jw_local_grid": route(
                workload, "dynamic_jw_local_grid", magnetization_b, occupancy_b
            ),
        }
        self.manifest["references"] = {
            "staggered_magnetization": {
                "value": 1.0,
                "kind": "exact_bounded",
                "standard_error": 0.0,
                "systematic_abs_bound": 0.0,
                "uncertainty_evidence_status": "rigorous_bound",
                "independent_of_route_estimates": True,
                "provenance": "synthetic independent exact reference",
                "hamiltonian_fingerprint": workload["hamiltonian_fingerprint"],
                "initial_state_fingerprint": workload["initial_state_fingerprint"],
                "evolution_fingerprint": workload["evolution_fingerprint"],
                "observable_definition_fingerprint": workload["observables"]
                ["staggered_magnetization"]["definition_fingerprint"],
                "reference_target": "ideal_exact_time_evolution",
            },
            "double_occupancy": {
                "value": 0.2,
                "kind": "exact_bounded",
                "standard_error": 0.0,
                "systematic_abs_bound": 0.0,
                "uncertainty_evidence_status": "rigorous_bound",
                "independent_of_route_estimates": True,
                "provenance": "synthetic independent exact reference",
                "hamiltonian_fingerprint": workload["hamiltonian_fingerprint"],
                "initial_state_fingerprint": workload["initial_state_fingerprint"],
                "evolution_fingerprint": workload["evolution_fingerprint"],
                "observable_definition_fingerprint": workload["observables"]
                ["double_occupancy"]["definition_fingerprint"],
                "reference_target": "ideal_exact_time_evolution",
            },
        }

    def test_dual_observable_target_r_and_familywise_metadata(self):
        result = CONVERGENCE.assess_manifest(self.manifest)
        self.assertEqual(result["status"], "READY_FOR_TARGET_R")
        self.assertEqual(result["common_R"], 80)
        self.assertEqual(
            result["stable_from_R_by_route_observable"]["native_fermions"],
            {"staggered_magnetization": 80, "double_occupancy": 80},
        )
        self.assertEqual(result["familywise"]["family_size"], 68)
        self.assertGreater(result["familywise"]["normal_diagnostic_z"], 3.0)
        self.assertEqual(
            result["familywise"]["binding_interval"],
            "bounded_hoeffding_or_deterministic",
        )

    def test_without_binding_reference_is_screening_not_certificate(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["references"] = None
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "SCREENED_FOR_TARGET_R")
        self.assertEqual(result["reference_mode"], "none")

    def test_approximate_unbounded_reference_is_diagnostic_only(self):
        manifest = copy.deepcopy(self.manifest)
        for reference in manifest["references"].values():
            reference["kind"] = "approximate_unbounded"
            reference["independent_of_route_estimates"] = False
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "SCREENED_FOR_TARGET_R")
        self.assertEqual(result["reference_mode"], "diagnostic")

    def test_empty_template_is_unresolved(self):
        result = CONVERGENCE.assess_manifest(template())
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("missing required routes" in item for item in result["common_errors"]))

    def test_double_occupancy_failure_blocks_joint_result(self):
        manifest = copy.deepcopy(self.manifest)
        values = [0.05, 0.08, 0.11, 0.14, 0.17, 0.20]
        for point_value, point_record in zip(
            values, manifest["routes"]["native_fermions"]["points"]
        ):
            point_record["estimates"]["double_occupancy"] = point_value
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertIsNone(
            result["routes"]["native_fermions"]["observables"]["double_occupancy"][
                "stable_from_R"
            ]
        )

    def test_target_r_before_one_observable_window_is_unresolved(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["workload"]["target_R"] = 40
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(
            result["routes"]["native_fermions"]["stable_from_R_by_observable"].get(
                "double_occupancy"
            ),
            80,
        )

    def test_missing_observable_or_target_point_fails_closed(self):
        mutations = {
            "observable": lambda manifest: manifest["routes"]["native_fermions"]["points"][3][
                "estimates"
            ].pop("double_occupancy"),
            "target": lambda manifest: manifest["routes"]["native_fermions"]["points"].pop(3),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                manifest = copy.deepcopy(self.manifest)
                mutate(manifest)
                result = CONVERGENCE.assess_manifest(manifest)
                self.assertEqual(result["status"], "UNRESOLVED")

    def test_bounded_familywise_half_width_can_fail_when_normal_diagnostic_would_pass(self):
        manifest = copy.deepcopy(self.manifest)
        for observable in manifest["workload"]["observables"].values():
            observable["algorithmic_error_budget"] = 1.0
        for route_record in manifest["routes"].values():
            route_record["sampling_mode"] = "shared_shots"
            for point_record in route_record["points"]:
                point_record["attempted_shots"] = 12000
                point_record["accepted_shots"] = 10000
                point_record["effective_independent_shots"] = 10000
                point_record["concentration_model"] = "independent_bounded_samples"
                point_record["concentration_evidence_status"] = "rigorous_bound"
                point_record["per_shot_contribution_ranges"] = {
                    "staggered_magnetization": [-1.0, 1.0],
                    "double_occupancy": [0.0, 1.0],
                }
                point_record["mitigation_mode"] = "none"
                point_record["covariance_of_estimator_mean"] = [
                    [4e-6, 0.0],
                    [0.0, 4e-6],
                ]
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")
        normal_half_width = result["familywise"]["normal_diagnostic_z"] * 0.002
        self.assertLess(normal_half_width, 0.01)
        self.assertGreater(
            result["routes"]["native_fermions"]["points"][0][
                "familywise_half_widths"
            ]["staggered_magnetization"],
            normal_half_width,
        )

    def test_covariance_must_be_symmetric_and_psd(self):
        matrices = (
            [[1e-6, 2e-6], [0.0, 1e-6]],
            [[1e-6, 2e-6], [2e-6, 1e-6]],
            [[-1e-6, 0.0], [0.0, 1e-6]],
        )
        for matrix in matrices:
            with self.subTest(matrix=matrix):
                manifest = copy.deepcopy(self.manifest)
                manifest["routes"]["native_fermions"]["points"][0][
                    "covariance_of_estimator_mean"
                ] = matrix
                result = CONVERGENCE.assess_manifest(manifest)
                self.assertEqual(result["status"], "UNRESOLVED")
                self.assertTrue(result["routes"]["native_fermions"]["errors"])

    def test_microscopic_non_psd_covariance_fails_closed(self):
        for matrix in (
            [[0.0, 1e-7], [1e-7, 0.0]],
            [[1e-12, 2e-12], [2e-12, 1e-12]],
        ):
            with self.subTest(matrix=matrix):
                manifest = copy.deepcopy(self.manifest)
                manifest["routes"]["native_fermions"]["points"][0][
                    "covariance_of_estimator_mean"
                ] = matrix
                result = CONVERGENCE.assess_manifest(manifest)
                self.assertEqual(result["status"], "UNRESOLVED")
                self.assertTrue(
                    any(
                        "positive semidefinite" in error
                        for error in result["routes"]["native_fermions"]["errors"]
                    )
                )

    def test_reference_uncertainty_and_second_observable_are_binding(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["references"]["double_occupancy"]["value"] = 0.3
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")

        manifest = copy.deepcopy(self.manifest)
        manifest["references"]["double_occupancy"]["standard_error"] = 0.01
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_reference_identity_drift_is_invalid_schema(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["references"]["double_occupancy"][
            "evolution_fingerprint"
        ] = "different_evolution"
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(
            any("does not match workload identity" in error for error in result["errors"])
        )

    def test_copied_route_evidence_cannot_be_relabelled(self):
        manifest = copy.deepcopy(self.manifest)
        copied = copy.deepcopy(manifest["routes"]["native_fermions"])
        copied["metadata"]["route"] = "dynamic_jw_local_grid"
        manifest["routes"]["dynamic_jw_local_grid"] = copied
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(
            any(
                "reused from route native_fermions" in error
                for error in result["routes"]["dynamic_jw_local_grid"]["errors"]
            )
        )

    def test_two_shared_shots_with_zero_covariance_cannot_bind(self):
        manifest = copy.deepcopy(self.manifest)
        for route_record in manifest["routes"].values():
            route_record["sampling_mode"] = "shared_shots"
            for point_record in route_record["points"]:
                point_record["attempted_shots"] = 2
                point_record["accepted_shots"] = 2
                point_record["effective_independent_shots"] = 2
                point_record["concentration_model"] = "independent_bounded_samples"
                point_record["concentration_evidence_status"] = "rigorous_bound"
                point_record["per_shot_contribution_ranges"] = {
                    "staggered_magnetization": [-1.0, 1.0],
                    "double_occupancy": [0.0, 1.0],
                }
                point_record["mitigation_mode"] = "none"
                point_record["covariance_of_estimator_mean"] = [
                    [0.0, 0.0],
                    [0.0, 0.0],
                ]
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")
        normalized = result["routes"]["native_fermions"]["points"][0]
        self.assertEqual(
            normalized["normal_diagnostic_half_widths"]["staggered_magnetization"],
            0.0,
        )
        self.assertGreater(
            normalized["familywise_half_widths"]["staggered_magnetization"],
            self.manifest["workload"]["observables"]["staggered_magnetization"][
                "statistical_half_width_budget"
            ],
        )
        for route_record in manifest["routes"].values():
            for point_record in route_record["points"]:
                point_record["attempted_shots"] = 10_000_000
                point_record["accepted_shots"] = 10_000_000
        many_correlated = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(many_correlated["status"], "UNRESOLVED")
        self.assertEqual(
            many_correlated["routes"]["native_fermions"]["points"][0][
                "familywise_half_widths"
            ],
            normalized["familywise_half_widths"],
        )

    def test_unvalidated_or_unbounded_sampling_cannot_bind(self):
        mutations = (
            ("concentration_evidence_status", "derived_unvalidated"),
            ("concentration_model", "unvalidated_samples"),
            ("mitigation_mode", "unbounded_or_unvalidated"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                manifest = copy.deepcopy(self.manifest)
                for route_record in manifest["routes"].values():
                    route_record["sampling_mode"] = "shared_shots"
                    for point_record in route_record["points"]:
                        point_record["attempted_shots"] = 10_000_000
                        point_record["accepted_shots"] = 10_000_000
                        point_record["effective_independent_shots"] = 10_000_000
                        point_record[
                            "concentration_model"
                        ] = "independent_bounded_samples"
                        point_record["concentration_evidence_status"] = "rigorous_bound"
                        point_record["per_shot_contribution_ranges"] = {
                            "staggered_magnetization": [-1.0, 1.0],
                            "double_occupancy": [0.0, 1.0],
                        }
                        point_record["mitigation_mode"] = "none"
                        point_record[field] = value
                result = CONVERGENCE.assess_manifest(manifest)
                self.assertEqual(result["status"], "SCREENED_FOR_TARGET_R")
                self.assertFalse(
                    result["routes"]["native_fermions"]["sampling_bounds_binding"]
                )

        manifest = copy.deepcopy(self.manifest)
        for route_record in manifest["routes"].values():
            route_record["sampling_mode"] = "shared_shots"
            for point_record in route_record["points"]:
                point_record["attempted_shots"] = 2
                point_record["accepted_shots"] = 2
                point_record["effective_independent_shots"] = 2
                point_record["concentration_model"] = "independent_bounded_samples"
                point_record["concentration_evidence_status"] = "rigorous_bound"
                point_record["per_shot_contribution_ranges"] = {
                    "staggered_magnetization": [0.0, 0.0],
                    "double_occupancy": [0.0, 0.0],
                }
                point_record["mitigation_mode"] = "bounded_weighted"
        incompatible_range = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(incompatible_range["status"], "UNRESOLVED")
        self.assertTrue(
            any(
                "must contain the reported estimate" in error
                for route_result in incompatible_range["routes"].values()
                for error in route_result["errors"]
            )
        )

    def test_circuit_fingerprint_is_unique_for_every_route_r_point(self):
        mutations = (
            lambda manifest: [
                point_record.update(circuit_fingerprint="same-native-circuit")
                for point_record in manifest["routes"]["native_fermions"]["points"]
            ],
            lambda manifest: manifest["routes"]["dynamic_jw_local_grid"]["points"][0].update(
                circuit_fingerprint=manifest["routes"]["native_fermions"]["points"][0][
                    "circuit_fingerprint"
                ],
                term_sequence_fingerprint="different-term-sequence",
            ),
        )
        for mutate in mutations:
            with self.subTest():
                manifest = copy.deepcopy(self.manifest)
                mutate(manifest)
                result = CONVERGENCE.assess_manifest(manifest)
                self.assertEqual(result["status"], "UNRESOLVED")
                self.assertTrue(
                    any(
                        "circuit_fingerprint is reused" in error
                        for route_result in result["routes"].values()
                        for error in route_result["errors"]
                    )
                )

    def test_nonbinding_systematic_status_downgrades_ready_to_screening(self):
        for status in ("assumed", "derived_unvalidated"):
            with self.subTest(status=status):
                manifest = copy.deepcopy(self.manifest)
                manifest["routes"]["native_fermions"]["points"][0][
                    "systematic_bound_status"
                ] = status
                result = CONVERGENCE.assess_manifest(manifest)
                self.assertEqual(result["status"], "SCREENED_FOR_TARGET_R")
                self.assertFalse(
                    result["routes"]["native_fermions"]["systematic_bounds_binding"]
                )

    def test_duplicate_r_batch_and_unplanned_grid_fail_closed(self):
        mutations = (
            lambda points: points[-1].update(R=160),
            lambda points: points[-1].update(batch_id=points[-2]["batch_id"]),
            lambda points: points.append(copy.deepcopy(points[-1])),
        )
        for mutate in mutations:
            with self.subTest():
                manifest = copy.deepcopy(self.manifest)
                mutate(manifest["routes"]["native_fermions"]["points"])
                result = CONVERGENCE.assess_manifest(manifest)
                self.assertEqual(result["status"], "UNRESOLVED")

    def test_metadata_and_sampling_provenance_are_binding(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["routes"]["native_fermions"]["metadata"]["initial_state"] = "vacuum"
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")

        manifest = copy.deepcopy(self.manifest)
        manifest["routes"]["native_fermions"]["points"][0]["covariance_provenance"] = ""
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")

    def test_partial_reference_and_v1_manifest_are_invalid_schema(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["references"].pop("double_occupancy")
        self.assertEqual(CONVERGENCE.assess_manifest(manifest)["status"], "INVALID_SCHEMA")

        legacy = {"schema_version": 1, "workload": {}, "required_routes": [], "routes": {}}
        self.assertEqual(CONVERGENCE.assess_manifest(legacy)["status"], "INVALID_SCHEMA")

    def test_physical_range_is_binding(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["routes"]["native_fermions"]["points"][0]["estimates"][
            "double_occupancy"
        ] = 1.1
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
