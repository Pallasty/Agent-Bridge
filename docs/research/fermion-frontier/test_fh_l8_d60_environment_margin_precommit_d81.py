import importlib.util
import copy
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d81", HERE / "fh_l8_d60_environment_margin_precommit_d81.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class D81Tests(unittest.TestCase):
    def test_packet_is_fail_closed_on_three_inputs(self):
        result = MODULE.verify()
        self.assertEqual(
            result["missing_inputs"],
            [
                "concurrent_load_exclusion_mechanism",
                "measurement_margin",
                "timeout_policy",
            ],
        )
        self.assertFalse(result["full53_execution_authorized"])

    def test_rule_form_is_frozen_without_numeric_inference(self):
        result = MODULE.verify()
        self.assertEqual(
            result["selected_rule_form"],
            "precommitted_measurement_population_margin_and_timeout_rule",
        )
        self.assertEqual(
            result["next_gate"],
            "OWNER_NUMERIC_MARGIN_TIMEOUT_AND_LOAD_ISOLATION_INPUT",
        )

    def test_environment_drift_fails_closed(self):
        observed = MODULE.current_environment()
        observed["python_version"] = "0.0.0-drift"
        with mock.patch.object(MODULE, "current_environment", return_value=observed):
            with self.assertRaisesRegex(MODULE.D81Error, "environment identity drift"):
                MODULE.verify()

    def test_inferred_numeric_margin_is_rejected(self):
        contract = copy.deepcopy(MODULE.load(MODULE.CONTRACT))
        result = MODULE.load(MODULE.RESULT)
        contract["rule_precommit"]["measurement_margin"] = "2.0x"
        with mock.patch.object(MODULE, "load", side_effect=[contract, result]):
            with self.assertRaisesRegex(MODULE.D81Error, "owner numeric policy was inferred"):
                MODULE.verify()


if __name__ == "__main__":
    unittest.main()
