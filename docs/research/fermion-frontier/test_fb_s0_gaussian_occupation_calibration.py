import copy
import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
MODULE_PATH = HERE / "fb_s0_gaussian_occupation_calibration.py"
CONTRACT_PATH = HERE / "fb_s0_gaussian_occupation_contract.json"
RECEIPT_PATH = HERE / "fb_s0_gaussian_occupation_receipt.json"
SPEC = importlib.util.spec_from_file_location("fb_s0_gaussian_occupation", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FbS0GaussianOccupationCalibrationTests(unittest.TestCase):
    def setUp(self):
        with CONTRACT_PATH.open(encoding="utf-8") as handle:
            self.contract = json.load(handle)

    def test_analytic_gaussian_kernels_share_pairwise_margins_but_not_triple(self):
        report = MODULE.build_calibration(self.contract)
        self.assertEqual(report["status"], "ANALYTIC_GAUSSIAN_Q2_COUNTEREXAMPLE_VERIFIED")
        rows = report["analytic_counterexample"]["kernels"]
        self.assertEqual(
            rows["positive_loop"]["one_mode_inclusions"],
            rows["negative_loop"]["one_mode_inclusions"],
        )
        self.assertEqual(
            rows["positive_loop"]["two_mode_inclusions"],
            rows["negative_loop"]["two_mode_inclusions"],
        )
        self.assertNotEqual(
            rows["positive_loop"]["three_mode_inclusion"],
            rows["negative_loop"]["three_mode_inclusion"],
        )
        for row in rows.values():
            self.assertTrue(row["valid_gauge_invariant_quasifree_mixed_state_kernel"])
            self.assertFalse(row["fixed_particle_number_pure_state"])
            self.assertGreater(row["c3_bits"], 0.05)

    def test_q2_preserves_near_boundary_independent_bernoulli_tables(self):
        for probability in (1e-6, 2e-6):
            table = []
            for cell in range(8):
                occupied = cell.bit_count()
                table.append(
                    probability**occupied * (1.0 - probability) ** (3 - occupied)
                )
            q2 = MODULE.pairwise_maximum_entropy(table)
            self.assertLess(max(abs(left - right) for left, right in zip(table, q2)), 1e-18)
            self.assertLess(abs(MODULE.c3_bits(table, q2)), 1e-15)

    def test_q2_singleton_fibre_and_positive_over_zero_kl_boundary(self):
        singleton = [0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5]
        self.assertEqual(MODULE.pairwise_maximum_entropy(singleton), singleton)
        self.assertEqual(
            MODULE.c3_bits([1e-19, 1.0 - 1e-19], [0.0, 1.0]),
            float("inf"),
        )

    def test_fixed_l2_quadratic_fixture_scans_every_triplet_as_negative_control(self):
        report = MODULE.build_calibration(self.contract)
        control = report["l2_negative_control"]
        self.assertEqual(control["status"], "NO_DIVERGENCE_IN_FIXED_L2_FIXTURE")
        self.assertEqual(control["triplets_scanned"], 56)
        self.assertEqual(control["positive_triplets"], 0)
        self.assertLessEqual(control["maximum_c3_bits"], 1e-12)
        self.assertTrue(all(control["checks"].values()))

    def test_interpretation_and_authority_are_fail_closed(self):
        report = MODULE.build_calibration(self.contract)
        self.assertIn("classical", report["interpretation"]["supported"])
        self.assertIn("non-Gaussianity", report["interpretation"]["refuted"])
        self.assertEqual(
            report["claims"],
            {
                "calibration_only": True,
                "fermionic_non_gaussianity_assessed": False,
                "hoi_application_claim": False,
                "physical_l8_instance_assessed": False,
                "ready_gate_eligible": False,
                "bgl_accessed": False,
                "runtime_authority": False,
                "mainline_parameter_influence": False,
                "portable_receipt_byte_identity": False,
            },
        )
        self.assertFalse(report["logical_resource_counts"]["python_peak_rss_measured"])
        self.assertEqual(
            report["provenance"]["checker_sha256"], self.contract["checker_sha256"]
        )

    def test_contract_rejects_non_gaussian_kernel_eigenvalue(self):
        tampered = copy.deepcopy(self.contract)
        tampered["analytic_kernels"]["positive_loop"]["expected_eigenvalues"][0] = "51/50"
        with self.assertRaisesRegex(MODULE.CalibrationError, "eigenvalues must lie"):
            MODULE.build_calibration(tampered)

    def test_contract_rejects_pilot_source_drift(self):
        tampered = copy.deepcopy(self.contract)
        tampered["l2_negative_control"]["pilot_sha256"] = "0" * 64
        with self.assertRaisesRegex(MODULE.CalibrationError, "source hash"):
            MODULE.build_calibration(tampered)

    def test_contract_rejects_checker_source_drift(self):
        tampered = copy.deepcopy(self.contract)
        tampered["checker_sha256"] = "0" * 64
        with self.assertRaisesRegex(MODULE.CalibrationError, "checker source hash"):
            MODULE.build_calibration(tampered)

    def test_cli_is_deterministic_and_reports_only_calibration_authority(self):
        command = [
            sys.executable,
            str(MODULE_PATH),
            "--contract",
            str(CONTRACT_PATH),
            "--format",
            "json",
        ]
        first = subprocess.run(command, check=True, capture_output=True, text=True)
        second = subprocess.run(command, check=True, capture_output=True, text=True)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.stdout, RECEIPT_PATH.read_text(encoding="utf-8"))
        report = json.loads(first.stdout)
        self.assertTrue(report["claims"]["calibration_only"])
        self.assertFalse(report["claims"]["ready_gate_eligible"])
        self.assertFalse(report["claims"]["bgl_accessed"])
        self.assertFalse(report["claims"]["portable_receipt_byte_identity"])


if __name__ == "__main__":
    unittest.main()
