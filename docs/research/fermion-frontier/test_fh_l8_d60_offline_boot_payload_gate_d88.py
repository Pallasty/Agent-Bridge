import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d88", HERE / "fh_l8_d60_offline_boot_payload_gate_d88.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D88Tests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))
        self.manifest = copy.deepcopy(MODULE.load(HERE / self.contract["manifest"]))

    def test_committed_result_is_exact_and_closed(self):
        result = MODULE.verify()
        self.assertEqual(result, MODULE.load(MODULE.RESULT))
        self.assertTrue(result["d82r_source_bundle_pinned"])
        self.assertFalse(result["boot_payload_manifest_complete"])

    def test_hashes_and_builder_close_manifest(self):
        for value in self.manifest["protected_boot_artifacts"].values():
            value["sha256"] = "a" * 64
        self.manifest["root_image_builder"]["complete"] = True
        self.assertTrue(MODULE.evaluate(self.contract, self.manifest)["boot_payload_manifest_complete"])

    def test_one_missing_boot_digest_blocks(self):
        self.manifest["protected_boot_artifacts"]["/boot/vmlinuz-7.0.0-29-generic"]["sha256"] = "a" * 64
        self.manifest["root_image_builder"]["complete"] = True
        self.assertFalse(MODULE.evaluate(self.contract, self.manifest)["boot_payload_manifest_complete"])

    def test_authority_mutation_is_rejected(self):
        self.contract["authority"]["package_install_authorized"] = True
        with self.assertRaisesRegex(MODULE.D88Error, "authority opened"):
            MODULE.verify_contract(self.contract)


if __name__ == "__main__":
    unittest.main()
