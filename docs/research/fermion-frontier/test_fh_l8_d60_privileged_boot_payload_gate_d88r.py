import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d88r", HERE / "fh_l8_d60_privileged_boot_payload_gate_d88r.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D88RTests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))
        self.receipt = copy.deepcopy(MODULE.load(HERE / self.contract["receipt"]))

    def test_committed_result_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertTrue(result["boot_payload_prerequisites_complete"])
        self.assertFalse(result["rootfs_build_authorized"])

    def test_digest_absence_fails_completion(self):
        self.receipt["boot_artifacts"]["/boot/vmlinuz-7.0.0-29-generic"]["sha256"] = None
        self.assertFalse(MODULE.evaluate(self.contract, self.receipt)["boot_payload_prerequisites_complete"])

    def test_mmc_mount_or_identity_drift_fails_completion(self):
        self.receipt["post_state"]["mmc_mountpoints"] = ["/mnt/test"]
        self.assertFalse(MODULE.evaluate(self.contract, self.receipt)["boot_payload_prerequisites_complete"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["rootfs_build_authorized"] = True
        with self.assertRaisesRegex(MODULE.D88RError, "authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
