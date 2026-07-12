import copy
import importlib.util
import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fermi_hubbard_convergence", HERE / "fermi_hubbard_convergence.py"
)
CONVERGENCE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CONVERGENCE)


def template():
    with (HERE / "fermi_hubbard_convergence_template.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def route(metadata, values):
    return {
        "metadata": copy.deepcopy(metadata),
        "points": [
            {"R": r, "estimate": estimate, "standard_error": standard_error}
            for r, estimate, standard_error in values
        ],
    }


class ConvergenceTests(unittest.TestCase):
    def setUp(self):
        self.manifest = template()
        self.metadata = self.manifest["workload"]
        values_a = [(10, 0.70, 0.03), (20, 0.90, 0.015), (40, 0.97, 0.008), (80, 0.997, 0.0008), (160, 0.999, 0.0005), (320, 0.9995, 0.0003)]
        values_b = [(10, 0.60, 0.03), (20, 0.82, 0.015), (40, 0.95, 0.008), (80, 0.997, 0.0008), (160, 0.999, 0.0005), (320, 0.9995, 0.0003)]
        self.manifest["routes"] = {
            "native_fermions": route(self.metadata, values_a),
            "dynamic_jw_local_grid": route(self.metadata, values_b),
        }
        self.manifest["required_routes"] = list(self.manifest["routes"])

    def test_two_interval_stability_and_common_r(self):
        result = CONVERGENCE.assess_manifest(self.manifest)
        self.assertEqual(result["status"], "READY_FOR_COMMON_R")
        self.assertEqual(result["route_stable_from_R"], {"native_fermions": 80, "dynamic_jw_local_grid": 80})
        self.assertEqual(result["common_R"], 80)

    def test_reference_check_is_optional_but_binding_when_present(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["reference"] = {"value": 1.0, "provenance": "independent classical reference"}
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "READY_FOR_COMMON_R")
        self.assertTrue(result["reference_used"])

        manifest["reference"]["value"] = 1.2
        unresolved = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(unresolved["status"], "UNRESOLVED")

    def test_missing_route_is_unresolved_not_fabricated(self):
        manifest = template()
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("missing required routes" in error for error in result["common_errors"]))

    def test_metadata_mismatch_fails_route(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["routes"]["native_fermions"]["metadata"]["observable"] = "double occupancy"
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(result["routes"]["native_fermions"]["errors"])

    def test_invalid_point_and_high_statistical_error_fail_closed(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["routes"]["native_fermions"]["points"][0]["standard_error"] = 0.2
        manifest["routes"]["native_fermions"]["points"].append(
            {"R": 320, "estimate": 1.0, "standard_error": 0.001}
        )
        result = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(result["status"], "UNRESOLVED")

        manifest["routes"]["dynamic_jw_local_grid"]["points"][0]["R"] = 20
        invalid = CONVERGENCE.assess_manifest(manifest)
        self.assertEqual(invalid["status"], "UNRESOLVED")
        self.assertTrue(any("duplicate R" in error for error in invalid["routes"]["dynamic_jw_local_grid"]["errors"]))


if __name__ == "__main__":
    unittest.main()
