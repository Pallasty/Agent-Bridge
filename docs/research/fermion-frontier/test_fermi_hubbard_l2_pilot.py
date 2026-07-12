import importlib.util
import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fermi_hubbard_l2_pilot", HERE / "fermi_hubbard_l2_pilot.py"
)
PILOT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PILOT)


class L2PilotTests(unittest.TestCase):
    def test_pilot_has_exact_reference_and_expected_r_grid(self):
        result = PILOT.build_pilot()
        self.assertEqual(result["pilot_status"], "algorithmic_product_formula_pilot_not_hardware_or_L8_evidence")
        self.assertAlmostEqual(result["reference"]["value"], 0.6557603378046181, places=12)
        self.assertEqual(
            [point["R"] for point in result["routes"]["group_order_pilot"]["points"]],
            [1, 2, 4, 8, 16, 32, 64, 128],
        )

    def test_pilot_is_converging_toward_reference(self):
        result = PILOT.build_pilot()
        reference = result["reference"]["value"]
        points = result["routes"]["group_order_pilot"]["points"]
        self.assertLess(abs(points[-1]["estimate"] - reference), abs(points[-2]["estimate"] - reference))
        self.assertLess(abs(points[-1]["estimate"] - reference), 0.001)

    def test_pilot_manifest_is_ready_at_r32(self):
        with (HERE / "fermi_hubbard_l2_pilot_manifest.json").open(encoding="utf-8") as handle:
            manifest = json.load(handle)
        convergence_spec = importlib.util.spec_from_file_location(
            "fermi_hubbard_convergence", HERE / "fermi_hubbard_convergence.py"
        )
        convergence = importlib.util.module_from_spec(convergence_spec)
        assert convergence_spec.loader is not None
        convergence_spec.loader.exec_module(convergence)
        result = convergence.assess_manifest(manifest)
        self.assertEqual(result["status"], "READY_FOR_COMMON_R")
        self.assertEqual(result["common_R"], 32)

    def test_pilot_rejects_larger_systems_by_design(self):
        with self.assertRaisesRegex(ValueError, "restricted to L=2"):
            PILOT.build_pilot(l=3)


if __name__ == "__main__":
    unittest.main()
