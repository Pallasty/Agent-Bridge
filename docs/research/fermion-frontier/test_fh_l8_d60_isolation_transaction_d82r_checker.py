import importlib.util
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "checker", HERE / "fh_l8_d60_isolation_transaction_d82r_checker.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D82RCheckerTests(unittest.TestCase):
    def test_current_result_is_fail_closed_and_zero_mutation(self):
        result = MODULE.verify()
        self.assertEqual(result["live_plan_blockers"], ["host_admin_credential_missing"])
        self.assertEqual(result["host_cgroup_mutations_executed"], 0)
        self.assertEqual(result["irq_mutations_executed"], 0)
        self.assertFalse(result["full53_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
