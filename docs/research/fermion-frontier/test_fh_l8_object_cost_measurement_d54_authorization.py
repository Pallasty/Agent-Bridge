import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fh_l8_d54_authorization",
    HERE / "fh_l8_object_cost_measurement_d54_authorization_checker.py",
)
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECKER)


class FHObjectCostMeasurementD54AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.authorization = json.loads(
            CHECKER.AUTHORIZATION.read_text(encoding="utf-8")
        )

    def _mutated_check(self, mutate):
        authorization = copy.deepcopy(self.authorization)
        mutate(authorization)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "authorization.json"
            path.write_text(json.dumps(authorization), encoding="utf-8")
            return CHECKER.check(path)

    def test_committed_authorization_is_bounded_and_unused(self):
        result = CHECKER.check()
        committed = json.loads(
            (
                HERE
                / "fh_l8_object_cost_measurement_d54_authorization_result.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(result, committed)
        self.assertEqual(result["total_fresh_processes"], 70)
        self.assertEqual(result["maximum_scientific_kernel_calls_total"], 819)
        self.assertTrue(result["measurement_execution_authorized"])
        self.assertEqual(result["samples_started"], 0)
        self.assertFalse(result["full53_execution_authorized"])

    def test_sample_plan_drift_fails_closed(self):
        with self.assertRaisesRegex(
            CHECKER.D54AuthorizationError, "sample-plan arithmetic drift"
        ):
            self._mutated_check(
                lambda value: value["sample_plan"].update(
                    {"total_fresh_processes": 69}
                )
            )

    def test_used_authorization_state_fails_closed(self):
        with self.assertRaisesRegex(
            CHECKER.D54AuthorizationError, "result-blind and unused"
        ):
            self._mutated_check(
                lambda value: value["execution_state"].update(
                    {"samples_started": 1}
                )
            )

    def test_open_full53_authority_fails_closed(self):
        with self.assertRaisesRegex(
            CHECKER.D54AuthorizationError, "authority unexpectedly open"
        ):
            self._mutated_check(
                lambda value: value["authority"].update(
                    {"full53_execution_authorized": True}
                )
            )

    def test_runner_pin_drift_fails_closed(self):
        with self.assertRaisesRegex(CHECKER.D54AuthorizationError, "runner_sha256 drift"):
            self._mutated_check(
                lambda value: value.update({"runner_sha256": "0" * 64})
            )


if __name__ == "__main__":
    unittest.main()
