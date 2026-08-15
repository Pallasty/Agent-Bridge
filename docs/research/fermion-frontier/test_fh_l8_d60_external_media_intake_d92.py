import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d92", HERE / "fh_l8_d60_external_media_intake_d92.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D92Tests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))

    def test_committed_result_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertFalse(result["external_execution_admitted"])
        self.assertFalse(result["unmount_authorized"])

    def test_all_owner_inputs_are_required(self):
        snapshot = copy.deepcopy(self.contract["observed_snapshot"])
        snapshot["candidate_mmc"]["mounted_at"] = ""
        snapshot["eligible_disposable_media"] = ["/dev/sdb"]
        snapshot["eligible_backup_targets"] = ["/backup"]
        snapshot["disposable_or_data_disposition_receipt"] = True
        snapshot["backup_capacity_and_sha256"] = True
        snapshot["firmware_sd_boot_proof"] = True
        self.assertTrue(MODULE.evaluate(self.contract, snapshot)["external_execution_admitted"])

    def test_mount_blocks_even_with_other_inputs(self):
        snapshot = copy.deepcopy(self.contract["observed_snapshot"])
        snapshot["eligible_disposable_media"] = ["/dev/sdb"]
        snapshot["eligible_backup_targets"] = ["/backup"]
        snapshot["disposable_or_data_disposition_receipt"] = True
        snapshot["backup_capacity_and_sha256"] = True
        snapshot["firmware_sd_boot_proof"] = True
        self.assertFalse(MODULE.evaluate(self.contract, snapshot)["external_execution_admitted"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["format_authorized"] = True
        with self.assertRaisesRegex(MODULE.D92Error, "authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
