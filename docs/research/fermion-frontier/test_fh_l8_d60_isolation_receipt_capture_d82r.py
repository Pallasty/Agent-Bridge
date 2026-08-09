import importlib.util
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "capture", HERE / "fh_l8_d60_isolation_receipt_capture_d82r.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class FakeD82:
    CONTRACT = Path(__file__)

    @staticmethod
    def load(path):
        return {"load_isolation_requirement": {}}

    @staticmethod
    def verify_contract(contract):
        return None

    @staticmethod
    def current_isolation_snapshot(requirement):
        return {}

    @staticmethod
    def build_result(contract, snapshot):
        return {
            "load_isolation_admitted": True,
            "load_isolation_failed_predicates": [],
            "full53_execution_authorized": False,
        }


class D82ReceiptTests(unittest.TestCase):
    def test_admitted_receipt_preserves_closed_full53_authority(self):
        receipt = MODULE.build_receipt(FakeD82)
        self.assertTrue(receipt["result"]["load_isolation_admitted"])
        self.assertFalse(receipt["result"]["full53_execution_authorized"])

    def test_capture_refuses_nonadmitted_result(self):
        class Blocked(FakeD82):
            @staticmethod
            def build_result(contract, snapshot):
                return {
                    "load_isolation_admitted": False,
                    "load_isolation_failed_predicates": ["irq_affinity_excludes_target"],
                }

        with self.assertRaisesRegex(MODULE.D82ReceiptError, "irq_affinity"):
            MODULE.build_receipt(Blocked)

    def test_receipt_write_is_exclusive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "receipt.json"
            MODULE.write_exclusive(path, {"status": "ok"})
            with self.assertRaisesRegex(MODULE.D82ReceiptError, "already exists"):
                MODULE.write_exclusive(path, {"status": "replacement"})


if __name__ == "__main__":
    unittest.main()
