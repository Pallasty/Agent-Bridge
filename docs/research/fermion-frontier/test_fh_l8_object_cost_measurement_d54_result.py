import copy
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d54_result_checker", HERE / "fh_l8_object_cost_measurement_d54_result_checker.py"
)
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECKER)


class D54ResultTests(unittest.TestCase):
    def setUp(self):
        self.result = json.loads(CHECKER.RESULT.read_text(encoding="utf-8"))

    def test_committed_result(self):
        checked = CHECKER.check(self.result)
        self.assertEqual(checked["status"], "VERIFIED_D54_BOUNDED_LOCAL_MEASUREMENT")
        self.assertFalse(checked["full53_authority_open"])

    def test_counts_digest_and_authority_fail_closed(self):
        for path, value in (
            (("raw_sample_count",), 69),
            (("full53_extrapolation_performed",), True),
            (("groups", 9, "structural_output_sha256"), "0" * 64),
            (("groups", 9, "metrics", "cgroup_memory_peak_bytes", "max"), 536_870_913),
        ):
            changed = copy.deepcopy(self.result)
            cursor = changed
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = value
            with self.assertRaises(CHECKER.ResultError):
                CHECKER.check(changed)


if __name__ == "__main__":
    unittest.main()
