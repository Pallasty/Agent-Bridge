import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fh_l8_d52", HERE / "fh_l8_full53_adapter_static_cost_d52.py"
)
D52 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(D52)


def contract():
    return json.loads(
        (HERE / "fh_l8_full53_adapter_static_cost_d52_contract.json").read_text()
    )


def temporary_contract(value):
    temporary = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(value, temporary)
    temporary.close()
    return Path(temporary.name)


class FHFull53AdapterStaticCostD52Tests(unittest.TestCase):
    def test_contract_verifies(self):
        result = D52.check()
        expected = json.loads(
            (HERE / "fh_l8_full53_adapter_static_cost_d52_result.json").read_text()
        )
        self.assertEqual(result, expected)
        self.assertEqual(
            result["status"],
            "VERIFIED_D52_STATIC_ADAPTER_IR_AND_OPERATION_BOUNDS_COSTS_UNRESOLVED",
        )
        self.assertEqual(result["total_fraction_constructions_upper"], 95894550)
        self.assertFalse(result["full53_execution_authorized"])

    def test_ir_lifetime_drift_fails_closed(self):
        value = contract()
        value["adapter_ir"][-1]["output"] = "column_still_live"
        path = temporary_contract(value)
        try:
            with self.assertRaisesRegex(D52.D52Error, "column lifetime release"):
                D52.check(path)
        finally:
            path.unlink()

    def test_operation_bound_drift_fails_closed(self):
        value = contract()
        value["operation_bounds"]["total_basis_images_upper"] += 1
        path = temporary_contract(value)
        try:
            with self.assertRaisesRegex(D52.D52Error, "operation-bound arithmetic"):
                D52.check(path)
        finally:
            path.unlink()

    def test_authority_drift_fails_closed(self):
        value = contract()
        value["authority"]["full53_execution_authorized"] = True
        path = temporary_contract(value)
        try:
            with self.assertRaisesRegex(D52.D52Error, "authority unexpectedly open"):
                D52.check(path)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
