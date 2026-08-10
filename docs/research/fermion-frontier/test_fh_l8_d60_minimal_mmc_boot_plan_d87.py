import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d87", HERE / "fh_l8_d60_minimal_mmc_boot_plan_d87.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D87Tests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))

    def test_committed_result_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertTrue(result["plan_complete"])
        self.assertFalse(result["execution_ready"])
        self.assertFalse(result["measurement_authorized"])

    def test_layout_capacity_is_fail_closed(self):
        self.contract["target"]["disk_bytes"] = 30000000000
        result = MODULE.evaluate(self.contract)
        self.assertFalse(result["layout_fits_candidate"])
        self.assertFalse(result["plan_complete"])

    def test_all_preflight_proofs_are_required_for_execution_readiness(self):
        for key in self.contract["required_preflight"]:
            self.contract["required_preflight"][key] = True
        self.assertTrue(MODULE.evaluate(self.contract)["execution_ready"])
        self.contract["required_preflight"]["backup_image_digest_proven"] = False
        self.assertFalse(MODULE.evaluate(self.contract)["execution_ready"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["partition_authorized"] = True
        with self.assertRaisesRegex(MODULE.D87Error, "execution authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
