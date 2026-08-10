import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d87r", HERE / "fh_l8_d60_mmc_execution_preflight_d87r.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D87RTests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))

    def test_committed_result_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertTrue(result["stable_identity_gate_pass"])
        self.assertFalse(result["execution_admitted"])
        self.assertFalse(result["partition_authorized"])

    def test_backup_space_requires_image_plus_reserve(self):
        snapshot = copy.deepcopy(self.contract["observed_snapshot"])
        snapshot["backup_targets"]["/"]["available_bytes"] = 83864569855
        self.assertEqual(MODULE.evaluate(self.contract, snapshot)["eligible_backup_targets"], [])
        snapshot["backup_targets"]["/"]["available_bytes"] += 1
        self.assertEqual(MODULE.evaluate(self.contract, snapshot)["eligible_backup_targets"], ["/"])

    def test_disposable_media_still_requires_boot_proofs(self):
        snapshot = copy.deepcopy(self.contract["observed_snapshot"])
        snapshot["existing_mmc_data_disposable"] = True
        result = MODULE.evaluate(self.contract, snapshot)
        self.assertTrue(result["existing_data_gate_pass"])
        self.assertFalse(result["execution_admitted"])

    def test_every_gate_is_required_for_admission(self):
        snapshot = copy.deepcopy(self.contract["observed_snapshot"])
        snapshot["existing_mmc_data_disposable"] = True
        snapshot["firmware_sd_bootability_proven"] = True
        snapshot["boot_payload_manifest_complete"] = True
        self.assertTrue(MODULE.evaluate(self.contract, snapshot)["execution_admitted"])
        snapshot["stable_identity_matches"] = False
        self.assertFalse(MODULE.evaluate(self.contract, snapshot)["execution_admitted"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["format_authorized"] = True
        with self.assertRaisesRegex(MODULE.D87RError, "destructive authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
