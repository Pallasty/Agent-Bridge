import importlib.util
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d80", HERE / "fh_l8_d79_successor_preflight_d80.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D80Tests(unittest.TestCase):
    def test_current_master_preflight_is_blocked(self):
        result = MODULE.verify()
        self.assertEqual(result["blocker_count"], 5)
        self.assertEqual(result["decision"], "NO_GO_D80_SUCCESSOR_EXECUTION_BLOCKED")
        self.assertFalse(result["full53_execution_authorized"])

    def test_only_d60_precommit_packet_is_next(self):
        self.assertEqual(
            MODULE.verify()["allowed_next_unit"],
            "D60_ENVIRONMENT_AND_MARGIN_PRECOMMIT_PACKET_ONLY",
        )


if __name__ == "__main__":
    unittest.main()
