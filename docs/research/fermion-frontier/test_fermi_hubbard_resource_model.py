import copy
import importlib.util
import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fermi_hubbard_resource_model", HERE / "fermi_hubbard_resource_model.py"
)
MODEL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODEL)


def load_example():
    with (HERE / "fermi_hubbard_resource_scenario.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def route_map(result):
    return {row["route"]: row for row in result["logical_routes"]}


class ResourceModelTests(unittest.TestCase):
    def test_candidate_gate_count_fit_all_plotted_sizes(self):
        expected = {
            4: (576, 1000, 488),
            5: (930, 1960, 960),
            6: (1368, 3396, 1668),
            7: (1890, 5404, 2660),
            8: (2496, 8080, 3984),
            9: (3186, 11520, 5688),
            10: (3960, 15820, 7820),
        }
        for l, counts in expected.items():
            with self.subTest(l=l):
                config = load_example()
                config["workload"]["linear_size"] = l
                config["workload"]["trotter_steps"] = 1
                routes = route_map(MODEL.build_model(config))
                actual = (
                    routes["dynamic_jw_local_grid_figure_candidate_fit"][
                        "counted_subtotal"
                    ],
                    routes["fsn_standard_figure_candidate_fit"]["counted_subtotal"],
                    routes["fsn_ladder_figure_candidate_fit"]["counted_subtotal"],
                )
                self.assertEqual(actual, counts)
                self.assertTrue(
                    all(
                        routes[name]["complete_count"] is None
                        for name in (
                            "dynamic_jw_local_grid_figure_candidate_fit",
                            "fsn_standard_figure_candidate_fit",
                            "fsn_ladder_figure_candidate_fit",
                        )
                    )
                )

    def test_candidate_fit_is_unresolved_outside_figure_domain(self):
        config = load_example()
        config["workload"]["linear_size"] = 11
        routes = route_map(MODEL.build_model(config))
        for name in (
            "dynamic_jw_local_grid_figure_candidate_fit",
            "fsn_standard_figure_candidate_fit",
            "fsn_ladder_figure_candidate_fit",
        ):
            self.assertIsNone(routes[name]["counted_subtotal"])
            self.assertIsNone(routes[name]["depth_subtotal"])

    def test_rejects_degenerate_grid(self):
        config = load_example()
        config["workload"]["linear_size"] = 2
        with self.assertRaisesRegex(ValueError, ">= 3"):
            MODEL.build_model(config)

    def test_native_common_order_schedule_and_angle_layers(self):
        result = MODEL.build_model(load_example())
        self.assertEqual(
            result["workload"]["target_native_gate_parameters"],
            {
                "hopping_half_abs_theta": 0.01,
                "hopping_full_abs_theta": 0.02,
                "onsite_half_abs_phi": 0.04,
                "convention": (
                    "PNAS native-gate parameter convention with hbar=1; signs follow "
                    "the Hamiltonian and are omitted from these absolute values."
                ),
            },
        )
        native = route_map(result)["native_fermions"]
        self.assertEqual(native["counted_subtotal"], 44864)
        self.assertEqual(native["complete_count"], 44864)
        self.assertEqual(native["depth_subtotal"], 801)
        self.assertEqual(native["matching_sizes"], {"g1": 64, "g2": 48, "g3": 48, "g4": 64})
        self.assertEqual(native["depth_breakdown"]["hopping_layers"], 601)
        self.assertEqual(native["depth_breakdown"]["onsite_half_angle_layers"], 200)
        self.assertEqual(native["depth_breakdown"]["half_angle_hopping_layers"], 402)
        self.assertEqual(native["depth_breakdown"]["full_h1_boundary_layers"], 99)
        self.assertEqual(native["depth_breakdown"]["full_h4_central_layers"], 100)

    def test_surface_construction_footprint_and_two_c2d_blocks(self):
        config = load_example()
        surface = MODEL.build_model(config)["physical_translation"][
            "dynamic_jw_surface_code"
        ]
        self.assertEqual(surface["ladder_cycles"], 53)
        self.assertEqual(surface["configured_optimistic_partial_switch_cycles"], 233)
        self.assertEqual(surface["configured_switch_only_us_all_steps"], 46600)
        self.assertEqual(surface["explicit_column_ladder_auxiliary_patches"], 112)
        self.assertEqual(surface["construction_layer_patch_footprint"], 240)
        self.assertEqual(
            surface["construction_layer_physical_qubit_footprint"], 240 * 881
        )
        self.assertIsNone(surface["active_layer_summed_volume_physical_qubit_cycles"])

        config2 = copy.deepcopy(config)
        config2["surface_code"]["c2d_blocks_per_switch"] = 2
        surface2 = MODEL.build_model(config2)["physical_translation"][
            "dynamic_jw_surface_code"
        ]
        self.assertEqual(surface2["configured_ladder_macros_per_switch"], 8)
        self.assertEqual(surface2["configured_cz_layers_per_switch"], 2)
        self.assertEqual(surface2["configured_optimistic_partial_switch_cycles"], 466)
        self.assertEqual(surface2["configured_switch_only_us_all_steps"], 93200)

    def test_rejects_invalid_cycle_and_factory_configs(self):
        for invalid in (0, float("inf")):
            with self.subTest(cycle=invalid):
                config = load_example()
                config["surface_code"]["cycle_us"] = invalid
                with self.assertRaises(ValueError):
                    MODEL.build_model(config)

        config = load_example()
        config["surface_code"]["magic_states_per_step"] = 1
        config["surface_code"]["factory_count"] = 0
        with self.assertRaisesRegex(ValueError, "factory_count"):
            MODEL.build_model(config)

        config = load_example()
        config["surface_code"]["magic_states_per_step"] = 1
        config["surface_code"]["factory_count"] = 1
        config["surface_code"]["factory_patches"] = 1
        config["surface_code"]["magic_state_output_interval_cycles"] = 0
        with self.assertRaisesRegex(ValueError, "output_interval"):
            MODEL.build_model(config)

        config = load_example()
        config["surface_code"]["factory_count"] = 5
        config["surface_code"]["factory_patches"] = 1
        with self.assertRaisesRegex(ValueError, "at least factory_count"):
            MODEL.build_model(config)

        config = load_example()
        config["surface_code"]["auxiliary_patches"] = 111
        with self.assertRaisesRegex(ValueError, "one-aux-per-CNOT"):
            MODEL.build_model(config)

        config = load_example()
        config["native_hardware"]["storage_traps"] = 127
        with self.assertRaisesRegex(ValueError, "one storage mode"):
            MODEL.build_model(config)

    def test_route_specific_expected_executions_are_not_common(self):
        config = load_example()
        config["workload"]["accepted_shots_per_measurement_setting"] = 101
        config["route_sampling"]["native_fermions"] = {
            "acceptance_probability": 0.5,
            "mitigation_repetition_multiplier": 3,
        }
        result = MODEL.build_model(config)
        plans = result["workload"]["route_execution_plans"]
        self.assertEqual(plans["native_fermions"]["expected_raw_circuit_executions"], 606)
        self.assertIsNone(
            plans["dynamic_jw_local_grid"]["expected_raw_circuit_executions"]
        )

    def test_first_step_unknown_blocks_complete_bare_time(self):
        config = load_example()
        config["timing_us"]["bare_qubit_routes"]["dynamic_jw"].update(
            {
                "cnot_layer_us": 1,
                "non_cnot_us_per_steady_step": 2,
                "first_step_extra_non_cnot_us": 0,
            }
        )
        physical = MODEL.build_model(config)["physical_translation"][
            "bare_qubit_routes"
        ]["dynamic_jw_local_grid_source_leading"]
        self.assertEqual(physical["planning_steady_state_subtotal_us"], 3400)
        self.assertIsNone(physical["complete_circuit_us"])

        config["first_step_extra_cnot"]["dynamic_jw"] = 0
        config["first_step_extra_cnot_depth"]["dynamic_jw"] = 0
        physical2 = MODEL.build_model(config)["physical_translation"][
            "bare_qubit_routes"
        ]["dynamic_jw_local_grid_source_leading"]
        self.assertEqual(
            physical2["first_step_closed_planning_estimate_us"], 3400
        )
        self.assertIsNone(physical2["complete_circuit_us"])

    def test_native_padded_time_is_not_mislabeled_complete(self):
        config = load_example()
        timing = config["timing_us"]
        timing.update(
            {
                "native_h1_half_layer_us": 1,
                "native_h2_half_layer_us": 1,
                "native_h3_half_layer_us": 1,
                "native_h1_full_boundary_layer_us": 2,
                "native_h4_full_central_layer_us": 2,
                "native_onsite_half_layer_us": 3,
            }
        )
        timing["route_overheads"]["native_fermions"].update(
            {
                "classical_preprocessing_us": 5,
                "prep_us": 2,
                "readout_reset_us": 3,
                "classical_postprocess_per_execution_us": 4,
            }
        )
        config["route_sampling"]["native_fermions"] = {
            "acceptance_probability": 1.0,
            "mitigation_repetition_multiplier": 1.0,
        }
        physical = MODEL.build_model(config)["physical_translation"]["native_fermions"]
        self.assertEqual(
            physical["configured_padded_circuit_time_upper_bound_us"], 1400
        )
        self.assertIsNone(physical["complete_circuit_us"])
        self.assertEqual(
            physical["expected_padded_campaign_upper_bound_us"],
            5 + 10000 * 1409,
        )
        self.assertIsNone(physical["expected_campaign_us"])

    def test_rejects_overallocated_error_budget(self):
        config = load_example()
        config["workload"]["hardware_error_budget"] = 0.006
        with self.assertRaisesRegex(ValueError, "exceed"):
            MODEL.build_model(config)


if __name__ == "__main__":
    unittest.main()
