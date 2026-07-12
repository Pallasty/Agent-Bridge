import copy
import importlib.util
import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fermi_hubbard_evidence", HERE / "fermi_hubbard_evidence.py"
)
EVIDENCE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(EVIDENCE)

VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "term_order_validator_for_evidence_test", HERE / "term_order_validator.py"
)
TERM_VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(TERM_VALIDATOR)


def load_json(name):
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class EvidenceManifestTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_json("evidence_manifest_contract.json")
        self.manifest = load_json("evidence_manifest_template.json")
        self.term_contract = load_json("term_order_contract.json")
        self.first_step_contract = load_json("first_step_contract.json")

    def test_empty_manifest_is_unresolved_with_component_statuses(self):
        result = EVIDENCE.validate_manifest(
            self.contract, self.manifest, self.term_contract, self.first_step_contract
        )
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(
            result["component_statuses"],
            {
                "term_order": "UNRESOLVED",
                "first_step": "UNRESOLVED",
                "convergence": "UNRESOLVED",
            },
        )

    def _exact_term_export(self, route, r=2):
        terms = TERM_VALIDATOR.expected_terms(8)
        events = [
            {"group": group, "terms": list(terms[group])}
            for group in TERM_VALIDATOR.GROUP_ORDER
        ]
        return {
            "schema_version": 1,
            "route": route,
            "linear_size": 8,
            "trotter_steps": r,
            "steps": [{"step": step, "events": copy.deepcopy(events)} for step in range(r)],
        }

    def _complete_first_step_route(self, r=2):
        return {
            "R": r,
            "steady_count_per_step": 10,
            "steady_depth_per_step": 4,
            "first_step_extra_count": 1,
            "first_step_extra_depth": 1,
            "compiled_exact": True,
            "provenance": "synthetic integration fixture",
            "timing": {
                "cnot_layer_us": 0.001,
                "non_cnot_us_per_steady_step": 0.01,
                "first_step_extra_non_cnot_us": 0.02,
                "timing_provenance": "synthetic integration timing",
            },
        }

    def _ready_manifest(self):
        contract = copy.deepcopy(self.contract)
        contract["target_trotter_steps"] = 2
        manifest = copy.deepcopy(self.manifest)
        routes = contract["required_routes"]
        manifest["term_order"]["required_routes"] = list(self.term_contract["required_routes"])
        manifest["term_order"]["exports"] = {
            route: self._exact_term_export(route)
            for route in self.term_contract["required_routes"]
        }
        manifest["first_step"]["routes"] = {
            route: self._complete_first_step_route()
            for route in routes
        }
        convergence_workload = manifest["convergence"]["workload"]
        points = [
            {"R": 1, "estimate": 0.5, "standard_error": 0.0},
            {"R": 2, "estimate": 0.8, "standard_error": 0.0},
            {"R": 4, "estimate": 0.95, "standard_error": 0.0},
            {"R": 8, "estimate": 0.995, "standard_error": 0.0},
            {"R": 16, "estimate": 0.999, "standard_error": 0.0},
            {"R": 32, "estimate": 0.9995, "standard_error": 0.0},
        ]
        manifest["convergence"]["routes"] = {
            route: {"metadata": copy.deepcopy(convergence_workload), "points": copy.deepcopy(points)}
            for route in manifest["convergence"]["required_routes"]
        }
        return contract, manifest

    def test_synthetic_all_component_closure_reaches_ready(self):
        contract, manifest = self._ready_manifest()
        result = EVIDENCE.validate_manifest(
            contract, manifest, self.term_contract, self.first_step_contract
        )
        self.assertEqual(result["status"], "READY_FOR_BENCHMARK")
        self.assertEqual(
            result["component_statuses"],
            {
                "term_order": "MATCHED",
                "first_step": "COMPLETE",
                "convergence": "READY_FOR_COMMON_R",
            },
        )
        self.assertEqual(result["coherence_errors"], [])

    def test_term_and_ledger_r_mismatch_is_inconsistent(self):
        contract, manifest = self._ready_manifest()
        manifest["first_step"]["routes"]["native_fermions"]["R"] = 3
        result = EVIDENCE.validate_manifest(
            contract, manifest, self.term_contract, self.first_step_contract
        )
        self.assertEqual(result["status"], "INCONSISTENT")
        self.assertTrue(any("trotter_steps" in error for error in result["coherence_errors"]))

    def test_route_map_drift_is_invalid_schema(self):
        contract = copy.deepcopy(self.contract)
        contract["route_map"]["unexpected_route"] = {
            "term_route": "unexpected_route",
            "convergence_route": "unexpected_route",
        }
        result = EVIDENCE.validate_manifest(
            contract, self.manifest, self.term_contract, self.first_step_contract
        )
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("route_map keys" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
