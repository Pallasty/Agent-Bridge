import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d57_checker", HERE / "fh_l8_production_streaming_adapter_d57_checker.py"
)
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECKER)


class D57ContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = CHECKER.load(CHECKER.CONTRACT)

    def test_committed_contract_and_result_verify(self):
        result = CHECKER.verify()
        self.assertTrue(result["column_release_in_finally"])
        self.assertFalse(result["full53_execution_authorized"])

    def test_source_interface_and_handoff_drift_fail_closed(self):
        variants = []
        pin = copy.deepcopy(self.contract)
        pin["source_pins"]["fh_l8_production_streaming_adapter_d57.py"] = "0" * 64
        variants.append(pin)
        interface = copy.deepcopy(self.contract)
        interface["adapter_interfaces"]["functions"].append("missing")
        variants.append(interface)
        handoff = copy.deepcopy(self.contract)
        handoff["next_gates"].pop()
        variants.append(handoff)
        for value in variants:
            with self.assertRaises(CHECKER.D57Error):
                CHECKER.validate(value)

    def test_authority_fails_closed(self):
        for field, value in (
            ("full53_execution_authorized", True),
            ("scientific_kernel_calls_executed", 1),
            ("production_io_executed", True),
        ):
            changed = copy.deepcopy(self.contract)
            changed["authority"][field] = value
            with self.assertRaises(CHECKER.D57Error):
                CHECKER.validate(changed)


if __name__ == "__main__":
    unittest.main()
