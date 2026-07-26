import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d55", HERE / "fh_l8_measurement_admissibility_d55.py"
)
D55 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(D55)


class D55Tests(unittest.TestCase):
    def test_exact_review_reproduces_committed_result(self):
        self.assertEqual(D55.review(), json.loads(D55.RESULT.read_text(encoding="utf-8")))

    def test_source_pin_drift_fails_closed(self):
        contract = json.loads(D55.CONTRACT.read_text(encoding="utf-8"))
        contract["source_pins"]["fh_l8_object_cost_measurement_d54r2_result.json"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaises(D55.D55Error):
                D55.review(path)

    def test_target_authority_and_spread_drift_fail_closed(self):
        original = json.loads(D55.CONTRACT.read_text(encoding="utf-8"))
        variants = []
        target = copy.deepcopy(original)
        target["target_decisions"].pop("filesystem_page_cache_accounting")
        variants.append(target)
        authority = copy.deepcopy(original)
        authority["authority"]["full53_execution_authorized"] = True
        variants.append(authority)
        spread = copy.deepcopy(original)
        spread["cross_replication_assessment"]["observed_maximum_is_not_an_upper_bound"] = False
        variants.append(spread)
        for value in variants:
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "contract.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(D55.D55Error):
                    D55.review(path)


if __name__ == "__main__":
    unittest.main()
