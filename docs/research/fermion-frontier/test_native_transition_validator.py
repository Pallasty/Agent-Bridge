import copy
import importlib.util
import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "native_transition_validator", HERE / "native_transition_validator.py"
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VALIDATOR)


def load_json(name):
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def occurrence(index, occurrence_class, measured="measured"):
    return {
        "occurrence_index": index,
        "class": occurrence_class,
        "group": VALIDATOR.CLASS_GROUPS[occurrence_class],
        "incoming_layout_id": f"layout_{index}",
        "outgoing_layout_id": f"layout_{index + 1}",
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
        "measurement_status": measured,
        "provenance": "synthetic transition fixture",
    }


def ledger(r=2, compiled_exact=True, measurement_status="measured"):
    occurrences = []
    index = 0
    for occurrence_class, count_fn in VALIDATOR.CLASS_COUNTS.items():
        for _ in range(count_fn(r)):
            occurrences.append(occurrence(index, occurrence_class, measurement_status))
            index += 1
    return {
        "schema_version": 1,
        "workload_fingerprint": "FH_L8_UoverT8_tT1_half_filling",
        "route": "native_fermions",
        "linear_size": 8,
        "trotter_steps": r,
        "compiled_exact": compiled_exact,
        "timing_provenance": "synthetic timing fixture",
        "occurrences": occurrences,
    }


class NativeTransitionTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_json("native_transition_contract.json")
        self.template = load_json("native_transition_template.json")

    def test_empty_template_is_unresolved(self):
        result = VALIDATOR.validate_ledger(self.contract, self.template)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("timing_provenance" in error for error in result["errors"]))

    def test_measured_occurrence_ledger_is_complete(self):
        result = VALIDATOR.validate_ledger(self.contract, ledger())
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["occurrence_count"], 17)
        self.assertEqual(result["expected_occurrence_count"], 17)
        self.assertAlmostEqual(result["complete_circuit_us"], 68.0)

    def test_derived_occurrence_is_bookkeeping_closed(self):
        result = VALIDATOR.validate_ledger(
            self.contract, ledger(compiled_exact=False, measurement_status="derived")
        )
        self.assertEqual(result["status"], "BOOKKEEPING_CLOSED_ESTIMATE")
        self.assertIsNone(result["complete_circuit_us"])
        self.assertEqual(result["planning_circuit_us"], 68.0)

    def test_class_count_mismatch_fails_closed(self):
        bad = ledger()
        bad["occurrences"].pop()
        result = VALIDATOR.validate_ledger(self.contract, bad)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("expected 17 occurrences" in error for error in result["errors"]))

    def test_timing_decomposition_mismatch_fails_closed(self):
        bad = ledger()
        bad["occurrences"][0]["transition_us"] = 5.0
        result = VALIDATOR.validate_ledger(self.contract, bad)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("does not equal timing components" in error for error in result["errors"]))

    def test_header_fingerprint_mismatch_is_invalid_schema(self):
        bad = copy.deepcopy(ledger())
        bad["workload_fingerprint"] = "other"
        result = VALIDATOR.validate_ledger(self.contract, bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")


if __name__ == "__main__":
    unittest.main()
