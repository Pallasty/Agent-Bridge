import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fh_l8_d53", HERE / "fh_l8_object_cost_measurement_d53.py"
)
D53 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(D53)


def contract():
    return json.loads((HERE / "fh_l8_object_cost_measurement_d53_contract.json").read_text())


def temporary_contract(value):
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(value, handle)
    handle.close()
    return Path(handle.name)


class FHObjectCostMeasurementD53Tests(unittest.TestCase):
    def test_committed_contract_and_result_verify(self):
        result = D53.check()
        expected = json.loads((HERE / "fh_l8_object_cost_measurement_d53_result.json").read_text())
        self.assertEqual(result, expected)
        self.assertFalse(result["measurement_runner_implemented"])
        self.assertFalse(result["full53_execution_authorized"])

    def test_source_bound_execution_authority_fails_closed(self):
        value = contract()
        value["fixture_tiers"][1]["execution_authorized_by_d53"] = True
        path = temporary_contract(value)
        try:
            with self.assertRaisesRegex(D53.D53Error, "must not authorize"):
                D53.check(path)
        finally:
            path.unlink()

    def test_missing_metric_fails_closed(self):
        value = contract()
        value["required_metrics"].remove("cgroup_memory_peak_bytes")
        path = temporary_contract(value)
        try:
            with self.assertRaisesRegex(D53.D53Error, "required metric set drift"):
                D53.check(path)
        finally:
            path.unlink()

    def test_baseline_subtraction_scope_fails_closed(self):
        value = contract()
        value["aggregation"]["ru_maxrss_and_cgroup_peak_are_not_baseline_subtracted"] = False
        path = temporary_contract(value)
        try:
            with self.assertRaisesRegex(D53.D53Error, "subtraction boundary"):
                D53.check(path)
        finally:
            path.unlink()

    def test_authority_fails_closed(self):
        value = contract()
        value["authority"]["measurement_runner_implemented"] = True
        path = temporary_contract(value)
        try:
            with self.assertRaisesRegex(D53.D53Error, "authority unexpectedly open"):
                D53.check(path)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
