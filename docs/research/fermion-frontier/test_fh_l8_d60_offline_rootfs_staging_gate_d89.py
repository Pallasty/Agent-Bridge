import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d89", HERE / "fh_l8_d60_offline_rootfs_staging_gate_d89.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D89Tests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))
        self.receipt = copy.deepcopy(MODULE.load(HERE / self.contract["receipt"]))

    def test_committed_result_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertTrue(result["rootfs_staging_complete"])
        self.assertFalse(result["payload_bundle_complete"])
        self.assertFalse(result["mmc_write_authorized"])

    def test_corrupt_archive_receipt_fails(self):
        self.receipt["artifact"]["xz_integrity_pass"] = False
        self.assertFalse(MODULE.evaluate(self.contract, self.receipt)["rootfs_staging_complete"])

    def test_mmc_mount_fails_completion(self):
        self.receipt["mmc_post_state"]["mountpoints"] = ["/mnt/mmc"]
        self.assertFalse(MODULE.evaluate(self.contract, self.receipt)["rootfs_staging_complete"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["mmc_write_authorized"] = True
        with self.assertRaisesRegex(MODULE.D89Error, "authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
