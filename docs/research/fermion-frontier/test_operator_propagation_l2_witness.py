import importlib.util
import pathlib
import subprocess
import sys
import unittest
from fractions import Fraction


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "operator_propagation_l2_witness",
    HERE / "operator_propagation_l2_witness.py",
)
WITNESS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(WITNESS)


class OperatorPropagationL2WitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = WITNESS.build_witness()

    def test_raw_r2_gate_sequence_and_angles(self):
        gates = WITNESS.build_forward_gate_sequence()
        self.assertEqual(len(gates), 112)
        self.assertEqual(
            self.result["gate_counts_by_group"],
            {"H1": 32, "H2": 0, "HU": 48, "H3": 0, "H4": 32},
        )
        self.assertEqual(
            max(abs(WITNESS.CHECKER.parse_fraction(gate["theta"])) for gate in gates),
            Fraction(1),
        )

    def test_neel_identity_and_raw_events_are_not_fused(self):
        self.assertEqual(WITNESS.NEEL_OCCUPIED_MODES, (0, 3, 5, 6))
        self.assertEqual(WITNESS.NEEL_BITS_Q0_FIRST, "10010110")
        self.assertTrue(self.result["raw_duplicate_events_preserved"])
        gates = WITNESS.build_forward_gate_sequence()
        self.assertNotEqual(gates[55]["group_event_index"], gates[56]["group_event_index"])

    def test_mapped_pauli_and_direct_fermion_paths_agree(self):
        cross = self.result["statevector_cross_check"]
        for difference in cross["absolute_differences"].values():
            self.assertLess(difference, 1e-12)
        self.assertGreater(cross["state_overlap_magnitude"], 1 - 1e-12)
        self.assertAlmostEqual(
            cross["mapped_pauli_observables"]["staggered_magnetization"],
            0.781713978559467,
            places=12,
        )
        self.assertAlmostEqual(
            cross["mapped_pauli_observables"]["double_occupancy"],
            0.03092520630247243,
            places=12,
        )

    def test_local_fraction_probe_contains_direct_statevector_value(self):
        probe = self.result["local_fraction_probe"]
        self.assertTrue(probe["interval_contains_direct_value"])
        low = WITNESS.CHECKER.parse_fraction(probe["fraction_interval"]["lower"])
        high = WITNESS.CHECKER.parse_fraction(probe["fraction_interval"]["upper"])
        self.assertLess(low, high)

    def test_product_formula_is_not_an_ideal_reference(self):
        diagnostic = self.result["ideal_evolution_diagnostic_only"]
        self.assertGreater(
            diagnostic["product_formula_absolute_differences"][
                "staggered_magnetization"
            ],
            0.1,
        )
        self.assertGreater(
            diagnostic["product_formula_absolute_differences"]["double_occupancy"],
            0.005,
        )
        self.assertEqual(diagnostic["uncertainty_status"], "APPROXIMATE_UNBOUNDED")

    def test_status_and_resource_boundary_are_fail_closed(self):
        self.assertEqual(self.result["status"], "CHECKER_CONFORMANCE_WITNESS_ONLY")
        self.assertFalse(self.result["ready_gate_eligible"])
        self.assertEqual(
            self.result["full_112_gate_fraction_certificate"],
            "DEFERRED_RESOURCE_LIMIT",
        )
        self.assertTrue(all(self.result["not_certified"].values()))

    def test_witness_rejects_any_other_r(self):
        for value in (1, 3, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    WITNESS.build_forward_gate_sequence(value)

    def test_cli_markdown_preserves_non_ready_boundary(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(HERE / "operator_propagation_l2_witness.py"),
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("CHECKER_CONFORMANCE_WITNESS_ONLY", completed.stdout)
        self.assertIn("DEFERRED_RESOURCE_LIMIT", completed.stdout)
        self.assertIn("READY eligible: `false`", completed.stdout)


if __name__ == "__main__":
    unittest.main()
