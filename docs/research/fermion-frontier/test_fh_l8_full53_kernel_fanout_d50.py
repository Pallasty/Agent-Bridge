import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fh_l8_d50",
    HERE / "fh_l8_full53_kernel_fanout_d50.py",
)
D50 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(D50)


class FHFull53KernelFanoutD50Tests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(D50.CONTRACT.read_text(encoding="utf-8"))

    def _check_mutation(self, mutate):
        contract = copy.deepcopy(self.contract)
        mutate(contract)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            return D50.check(path)

    def test_committed_contract_verifies_exact_structural_bounds(self):
        result = D50.check()
        self.assertEqual(
            result["status"],
            "VERIFIED_D50_SOURCE_BOUND_KERNEL_AND_STRUCTURAL_FANOUT_CONTRACT",
        )
        self.assertEqual(result["total_candidate_actions"], 47_947_275)
        self.assertEqual(result["total_spill_bytes"], 1_534_312_800)
        self.assertEqual(result["scientific_kernel_calls"], 0)
        self.assertFalse(result["streaming_peak_memory_proven"])
        self.assertFalse(result["worst_case_runtime_proven"])
        self.assertFalse(result["full53_execution_authorized"])
        committed = json.loads(
            (HERE / "fh_l8_full53_kernel_fanout_d50_result.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(result, committed)

    def test_candidate_arithmetic_drift_fails_closed(self):
        with self.assertRaisesRegex(D50.D50Error, "structural bound arithmetic drift"):
            self._check_mutation(
                lambda contract: contract["expected_structural_bounds"].update(
                    {"total_candidate_actions": 47_947_274}
                )
            )

    def test_open_authority_fails_closed(self):
        with self.assertRaisesRegex(D50.D50Error, "proof boundary unexpectedly open"):
            self._check_mutation(
                lambda contract: contract["proof_boundary"].update(
                    {"full53_execution_authorized": True}
                )
            )

    def test_source_pin_drift_fails_closed(self):
        with self.assertRaisesRegex(D50.D50Error, "source pin mismatch"):
            self._check_mutation(
                lambda contract: contract["source_pins"].update(
                    {"fh_l8_tiny_recovery_d22_runner.py": "0" * 64}
                )
            )

    def test_kernel_call_boundary_drift_fails_closed(self):
        source_path = HERE / "fh_l8_symmetry_orbit_quotient_d5_checker.py"
        original_read_text = Path.read_text

        def altered_read_text(path, *args, **kwargs):
            value = original_read_text(path, *args, **kwargs)
            if path == source_path:
                return value.replace("d4._sector_action(", "d4._other_action(")
            return value

        with patch.object(Path, "read_text", new=altered_read_text):
            with self.assertRaisesRegex(D50.D50Error, "sector-action binding drift"):
                D50.check()


if __name__ == "__main__":
    unittest.main()
