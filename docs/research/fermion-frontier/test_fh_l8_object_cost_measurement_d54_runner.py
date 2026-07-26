import importlib.util
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "fh_l8_object_cost_measurement_d54_runner.py"
SPEC = importlib.util.spec_from_file_location("fh_l8_d54_runner", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


class FHObjectCostMeasurementD54RunnerTests(unittest.TestCase):
    def setUp(self):
        self.d53 = json.loads(RUNNER.D53_CONTRACT.read_text(encoding="utf-8"))

    def test_sample_plan_exact_shape_without_measurement(self):
        plan = RUNNER.sample_plan(self.d53)
        self.assertEqual(len(plan), 70)
        self.assertEqual(
            sum(row["tier"] == "synthetic_object_calibration" for row in plan),
            42,
        )
        self.assertEqual(
            sum(row["tier"] == "source_bound_fixed64_micro" for row in plan),
            28,
        )
        self.assertEqual(len({tuple(sorted(row.items())) for row in plan}), 70)

    def test_authorization_requires_exact_runner_and_d53_pins(self):
        authorization = {
            "authorization_id": "FH-L8-D54-OBJECT-COST-MEASUREMENT-AUTH-V1",
            "measurement_execution_authorized": True,
            "runner_sha256": RUNNER.digest(RUNNER_PATH),
            "d53_contract_sha256": RUNNER.digest(RUNNER.D53_CONTRACT),
            "packed_q3_reads_authorized": 0,
            "full53_execution_authorized": False,
        }
        RUNNER.validate_authorization(authorization, RUNNER_PATH)
        authorization["runner_sha256"] = "0" * 64
        with self.assertRaisesRegex(RUNNER.D54RunnerError, "runner source pin mismatch"):
            RUNNER.validate_authorization(authorization, RUNNER_PATH)

    def test_authorization_rejects_full53_or_packed_q3(self):
        authorization = {
            "authorization_id": "FH-L8-D54-OBJECT-COST-MEASUREMENT-AUTH-V1",
            "measurement_execution_authorized": True,
            "runner_sha256": RUNNER.digest(RUNNER_PATH),
            "d53_contract_sha256": RUNNER.digest(RUNNER.D53_CONTRACT),
            "packed_q3_reads_authorized": 1,
            "full53_execution_authorized": False,
        }
        with self.assertRaisesRegex(RUNNER.D54RunnerError, "packed-q3"):
            RUNNER.validate_authorization(authorization, RUNNER_PATH)
        authorization["packed_q3_reads_authorized"] = 0
        authorization["full53_execution_authorized"] = True
        with self.assertRaisesRegex(RUNNER.D54RunnerError, "full53 authority"):
            RUNNER.validate_authorization(authorization, RUNNER_PATH)

    def test_owned_graph_is_alias_aware(self):
        shared = [1, 2, 3]
        aliased = {"a": shared, "b": shared}
        duplicated = {"a": [1, 2, 3], "b": [1, 2, 3]}
        self.assertLess(RUNNER.owned_graph_bytes(aliased), RUNNER.owned_graph_bytes(duplicated))


if __name__ == "__main__":
    unittest.main()
