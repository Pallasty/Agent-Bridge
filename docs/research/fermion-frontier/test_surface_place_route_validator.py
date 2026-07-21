import copy
import importlib.util
import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "surface_place_route_validator", HERE / "surface_place_route_validator.py"
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VALIDATOR)


def load_json(name):
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def small_contract():
    contract = load_json("surface_place_route_contract.json")
    contract["target_linear_size"] = 3
    contract["target_trotter_steps"] = 1
    return contract


def closed_ledger(exact=True):
    distance = 3
    physical_qubits = 2 * distance * distance - 1
    patches = [
        {"patch_id": f"d{index}", "role": "data", "physical_qubits": physical_qubits}
        for index in range(18)
    ]
    patches.extend(
        [
            {"patch_id": "a0", "role": "auxiliary", "physical_qubits": physical_qubits},
            {"patch_id": "f0", "role": "factory", "physical_qubits": physical_qubits},
            {"patch_id": "b0", "role": "buffer", "physical_qubits": physical_qubits},
        ]
    )
    placements = []
    for index, patch in enumerate(patches):
        patch_id = patch["patch_id"]
        if patch_id == "a0":
            row, col = 0, 0
        elif patch_id == "d0":
            row, col = 1, 0
        elif patch_id == "b0":
            row, col = 1, 1
        elif patch_id == "f0":
            row, col = 1, 2
        else:
            data_index = int(patch_id[1:]) - 1
            row, col = 2 + data_index // 10, data_index % 10
        placements.append(
            {
                "patch_id": patch["patch_id"],
                "row": row,
                "col": col,
                "orientation": "N",
                "available_boundaries": ["N", "E", "S", "W"],
            }
        )
    evidence = "compiler_export" if exact else "derived"
    live = [patch["patch_id"] for patch in patches]
    event_operations = [
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
            "evidence_status": evidence,
            "provenance": "synthetic operation fixture",
        }
        for event in range(10)
    ]
    return {
        "schema_version": 1,
        "workload_fingerprint": "FH_L8_UoverT8_tT1_half_filling",
        "route": "dynamic_jw_surface_code",
        "linear_size": 3,
        "trotter_steps": 1,
        "logical_sequence_fingerprint": "a" * 64,
        "logical_event_count": 10,
        "distance": distance,
        "cycle_us": 1.0,
        "patch_model": "rotated_surface_code_one_patch_per_tile",
        "compiled_exact": exact,
        "place_route_validated": exact,
        "timing_evidence_status": "measured" if exact else "derived",
        "error_evidence_status": "measured" if exact else "derived",
        "schedule_provenance": "synthetic schedule fixture",
        "timing_provenance": "synthetic timing fixture",
        "error_model_provenance": "synthetic error fixture",
        "logical_failure_budget": 0.005,
        "patches": patches,
        "layouts": [{"layout_id": "layout0", "placements": placements}],
        "intervals": [
            {
                "interval_index": 0,
                "start_cycle": 0,
                "duration_cycles": 3,
                "layout_id": "layout0",
                "live_patch_ids": live,
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
                        "evidence_status": evidence,
                        "provenance": "synthetic distillation fixture",
                    }
                ],
            },
            {
                "interval_index": 1,
                "start_cycle": 3,
                "duration_cycles": 1,
                "layout_id": "layout0",
                "live_patch_ids": live,
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
                        "evidence_status": evidence,
                        "provenance": "synthetic buffer fixture",
                    }
                ],
            },
            {
                "interval_index": 2,
                "start_cycle": 4,
                "duration_cycles": 1,
                "layout_id": "layout0",
                "live_patch_ids": live,
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
                        "evidence_status": evidence,
                        "provenance": "synthetic injection fixture",
                    }
                ],
            },
            {
                "interval_index": 3,
                "start_cycle": 5,
                "duration_cycles": 1,
                "layout_id": "layout0",
                "live_patch_ids": live,
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
                        "evidence_status": evidence,
                        "provenance": "synthetic rotation fixture",
                    }
                ],
            },
            {
                "interval_index": 4,
                "start_cycle": 6,
                "duration_cycles": 30,
                "layout_id": "layout0",
                "live_patch_ids": live,
                "operations": event_operations,
            },
        ],
    }


class SurfacePlaceRouteTests(unittest.TestCase):
    def test_empty_template_is_unresolved(self):
        result = VALIDATOR.validate_ledger(
            load_json("surface_place_route_contract.json"),
            load_json("surface_place_route_template.json"),
        )
        self.assertEqual(result["status"], "UNRESOLVED")

    def test_closed_exact_schedule_computes_active_volume(self):
        result = VALIDATOR.validate_ledger(small_contract(), closed_ledger())
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["complete_total_cycles"], 36)
        self.assertEqual(result["peak_physical_qubits"], 21 * 17)
        self.assertEqual(result["complete_active_physical_qubit_cycles"], 36 * 21 * 17)

    def test_derived_schedule_is_bookkeeping_closed_estimate(self):
        result = VALIDATOR.validate_ledger(small_contract(), closed_ledger(exact=False))
        self.assertEqual(result["status"], "BOOKKEEPING_CLOSED_ESTIMATE")
        self.assertIsNone(result["complete_active_physical_qubit_cycles"])

    def test_interval_gap_or_overlap_fails_closed(self):
        ledger = closed_ledger()
        second = copy.deepcopy(ledger["intervals"][0])
        second["interval_index"] = 5
        second["start_cycle"] = 37
        second["operations"] = []
        ledger["intervals"].append(second)
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("gap or overlap" in error for error in result["errors"]))

    def test_unknown_live_patch_fails_closed(self):
        ledger = closed_ledger()
        ledger["intervals"][0]["live_patch_ids"].append("unknown")
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("unknown live patch" in error for error in result["errors"]))

    def test_dependency_must_reference_prior_interval(self):
        ledger = closed_ledger()
        ledger["intervals"][0]["operations"][0]["depends_on"] = ["missing"]
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("depends on unknown" in error for error in result["errors"]))

    def test_failure_union_bound_must_fit_budget(self):
        ledger = closed_ledger()
        ledger["intervals"][0]["operations"][0]["logical_failure_probability"] = 0.01
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("failure union bound" in error for error in result["errors"]))

    def test_each_logical_event_requires_an_individual_operation_binding(self):
        ledger = closed_ledger()
        operation = ledger["intervals"][-1]["operations"][0]
        operation["logical_event_ids"] = list(range(10))
        ledger["intervals"][-1]["operations"] = [operation]
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(
            any("max_logical_events_per_operation" in error for error in result["errors"])
        )

    def test_operations_sharing_a_patch_cannot_overlap(self):
        ledger = closed_ledger()
        ledger["intervals"][-1]["operations"][1]["start_offset_cycles"] = 0
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("overlaps" in error for error in result["errors"]))

    def test_operation_window_must_fit_inside_interval(self):
        ledger = closed_ledger()
        ledger["intervals"][-1]["operations"][-1]["start_offset_cycles"] = 30
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("extends beyond" in error for error in result["errors"]))

    def test_logical_events_must_execute_in_term_order(self):
        ledger = closed_ledger()
        for event, operation in enumerate(ledger["intervals"][-1]["operations"]):
            operation["start_offset_cycles"] = 3 * (9 - event)
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("must finish before" in error for error in result["errors"]))

    def test_non_ladder_operation_cannot_bind_logical_events(self):
        ledger = closed_ledger()
        for operation in ledger["intervals"][-1]["operations"][1:]:
            operation["kind"] = "readout"
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("cannot implement logical events" in error for error in result["errors"]))

    def test_ladder_measurement_arity_and_distance_duration_are_binding(self):
        mutations = {
            "arity": lambda operation: operation.update(participant_patch_ids=["d0"]),
            "duration": lambda operation: operation.update(duration_cycles=2),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                ledger = closed_ledger()
                mutate(ledger["intervals"][-1]["operations"][0])
                result = VALIDATOR.validate_ledger(small_contract(), ledger)
                self.assertEqual(result["status"], "UNRESOLVED")

    def test_cycle_time_must_match_contract(self):
        ledger = closed_ledger()
        ledger["cycle_us"] = 1e-12
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("cycle_us" in error for error in result["errors"]))

    def test_every_data_patch_must_remain_live(self):
        ledger = closed_ledger()
        ledger["intervals"][0]["live_patch_ids"] = ["d0", "a0"]
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("data patch" in error for error in result["errors"]))

    def test_rotated_patch_qubits_must_match_distance(self):
        ledger = closed_ledger()
        for patch in ledger["patches"]:
            patch["physical_qubits"] = 1
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("2d^2-1" in error for error in result["errors"]))

    def test_surface_code_distance_must_be_odd(self):
        ledger = closed_ledger()
        ledger["distance"] = 4
        for patch in ledger["patches"]:
            patch["physical_qubits"] = 2 * 4 * 4 - 1
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("odd" in error for error in result["errors"]))

    def test_ledger_cannot_relax_contract_failure_budget(self):
        contract = small_contract()
        contract["logical_failure_budget"] = 0.005
        ledger = closed_ledger()
        ledger["logical_failure_budget"] = 1.0
        result = VALIDATOR.validate_ledger(contract, ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("contract" in error and "failure" in error for error in result["errors"]))

    def test_contract_cannot_relax_scenario_failure_budget(self):
        contract = small_contract()
        contract["logical_failure_budget"] = 1.0
        ledger = closed_ledger()
        ledger["logical_failure_budget"] = 1.0
        result = VALIDATOR.validate_ledger(contract, ledger)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("logical_failure_budget" in error for error in result["errors"]))

    def test_distant_participants_require_a_corridor(self):
        ledger = closed_ledger()
        auxiliary = next(
            placement
            for placement in ledger["layouts"][0]["placements"]
            if placement["patch_id"] == "a0"
        )
        auxiliary["row"] = 100
        auxiliary["col"] = 100
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("corridor" in error or "adjacent" in error for error in result["errors"]))

    def test_declared_boundary_must_face_the_operation_path(self):
        ledger = closed_ledger()
        ledger["intervals"][-1]["operations"][0]["required_boundaries"][0][
            "boundary"
        ] = "E"
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("does not face" in error for error in result["errors"]))

    def test_live_patch_cannot_teleport_between_layouts(self):
        ledger = closed_ledger()
        moved_layout = copy.deepcopy(ledger["layouts"][0])
        moved_layout["layout_id"] = "layout1"
        d0 = next(
            placement
            for placement in moved_layout["placements"]
            if placement["patch_id"] == "d0"
        )
        d0["row"], d0["col"] = 100, 100
        ledger["layouts"].append(moved_layout)
        ledger["intervals"][1]["layout_id"] = "layout1"
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("moves live patch" in error for error in result["errors"]))

    def test_corridor_must_form_a_contiguous_path(self):
        ledger = closed_ledger()
        physical_qubits = 2 * ledger["distance"] * ledger["distance"] - 1
        ledger["patches"].extend(
            [
                {"patch_id": "r0", "role": "routing", "physical_qubits": physical_qubits},
                {"patch_id": "r1", "role": "routing", "physical_qubits": physical_qubits},
            ]
        )
        auxiliary = next(
            placement
            for placement in ledger["layouts"][0]["placements"]
            if placement["patch_id"] == "a0"
        )
        auxiliary["row"] = 0
        auxiliary["col"] = 4
        ledger["layouts"][0]["placements"].extend(
            [
                {
                    "patch_id": "r0",
                    "row": 0,
                    "col": 0,
                    "orientation": "N",
                    "available_boundaries": ["N", "E", "S", "W"],
                },
                {
                    "patch_id": "r1",
                    "row": 0,
                    "col": 3,
                    "orientation": "N",
                    "available_boundaries": ["N", "E", "S", "W"],
                },
            ]
        )
        ledger["intervals"][-1]["live_patch_ids"].extend(["r0", "r1"])
        ledger["intervals"][-1]["operations"][0]["corridor_patch_ids"] = ["r0", "r1"]
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("corridor" in error or "contiguous" in error for error in result["errors"]))

    def test_interval_overlap_fails_closed(self):
        ledger = closed_ledger()
        second = copy.deepcopy(ledger["intervals"][0])
        second["interval_index"] = 5
        second["start_cycle"] = 35
        second["operations"] = []
        ledger["intervals"].append(second)
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("gap or overlap" in error for error in result["errors"]))

    def test_malformed_patch_ids_fail_closed_without_exception(self):
        mutations = {
            "live": lambda ledger: ledger["intervals"][0]["live_patch_ids"].append([]),
            "participant": lambda ledger: ledger["intervals"][-1]["operations"][0][
                "participant_patch_ids"
            ].append([]),
            "corridor": lambda ledger: ledger["intervals"][-1]["operations"][0][
                "corridor_patch_ids"
            ].append([]),
        }
        for name, mutate in mutations.items():
            with self.subTest(field=name):
                ledger = closed_ledger()
                mutate(ledger)
                result = VALIDATOR.validate_ledger(small_contract(), ledger)
                self.assertEqual(result["status"], "UNRESOLVED")

    def test_inject_must_depend_on_distill_or_buffer(self):
        ledger = closed_ledger()
        ledger["intervals"][0]["operations"][0]["kind"] = "readout"
        ledger["intervals"][2]["operations"][0]["depends_on"] = ["distill0"]
        result = VALIDATOR.validate_ledger(small_contract(), ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("distill" in error or "buffer" in error for error in result["errors"]))

    def test_exact_evidence_statuses_must_be_allowed(self):
        for extra_status in ("not-an-allowed-status", "assumed"):
            with self.subTest(extra_status=extra_status):
                contract = small_contract()
                contract["exact_evidence_statuses"].append(extra_status)
                result = VALIDATOR.validate_ledger(contract, closed_ledger())
                self.assertEqual(result["status"], "INVALID_SCHEMA")
                self.assertTrue(any("exact_evidence" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
