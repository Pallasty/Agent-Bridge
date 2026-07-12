import copy
import importlib.util
import json
import pathlib
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "term_order_validator", HERE / "term_order_validator.py"
)
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)
sys.modules["term_order_validator"] = VALIDATOR

COMPARATOR_SPEC = importlib.util.spec_from_file_location(
    "term_order_cross_route", HERE / "term_order_cross_route.py"
)
COMPARATOR = importlib.util.module_from_spec(COMPARATOR_SPEC)
assert COMPARATOR_SPEC.loader is not None
COMPARATOR_SPEC.loader.exec_module(COMPARATOR)


def load_json(name):
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class CrossRouteTermOrderTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_json("term_order_contract.json")
        self.fixture = load_json("term_order_native_fixture.json")
        self.terms = VALIDATOR.expected_terms(4)

    def manifest(self, exports):
        return {
            "schema_version": 1,
            "workload_fingerprint": self.contract["workload_fingerprint"],
            "required_routes": list(self.contract["required_routes"]),
            "exports": exports,
        }

    def exact_fixture(self):
        export = copy.deepcopy(self.fixture)
        for step in export["steps"]:
            for event in step["events"]:
                event["terms"] = list(self.terms[event["group"]])
        return export

    def test_empty_template_is_unresolved(self):
        result = COMPARATOR.compare_routes(
            self.contract, load_json("term_order_cross_route_template.json")
        )
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("missing required route exports" in error for error in result["errors"]))

    def test_group_only_exports_are_not_comparison_evidence(self):
        exports = {
            route: copy.deepcopy(self.fixture)
            for route in self.contract["required_routes"]
        }
        result = COMPARATOR.compare_routes(self.contract, self.manifest(exports))
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("individual-term sequence" in error for error in result["errors"]))

    def test_matching_exact_sequences_are_fingerprinted(self):
        exact = self.exact_fixture()
        exports = {route: copy.deepcopy(exact) for route in self.contract["required_routes"]}
        result = COMPARATOR.compare_routes(self.contract, self.manifest(exports))
        self.assertEqual(result["status"], "MATCHED")
        self.assertEqual(result["sequence_length"], 20)
        self.assertEqual(len(result["common_sequence_fingerprint"]), 64)

    def test_permuted_terms_are_a_cross_route_mismatch(self):
        exact = self.exact_fixture()
        exports = {route: copy.deepcopy(exact) for route in self.contract["required_routes"]}
        exports["fsn_ladder_figure_candidate_fit"]["steps"][0]["events"][0]["terms"] = list(
            reversed(exports["fsn_ladder_figure_candidate_fit"]["steps"][0]["events"][0]["terms"])
        )
        result = COMPARATOR.compare_routes(self.contract, self.manifest(exports))
        self.assertEqual(result["status"], "MISMATCH")
        self.assertIn("fsn_ladder_figure_candidate_fit", result["mismatches"])
        self.assertEqual(result["mismatches"]["fsn_ladder_figure_candidate_fit"]["first_difference_index"], 0)

    def test_invalid_export_remains_unresolved(self):
        exact = self.exact_fixture()
        exports = {route: copy.deepcopy(exact) for route in self.contract["required_routes"]}
        exports["dynamic_jw_local_grid_source_leading"]["steps"].pop()
        result = COMPARATOR.compare_routes(self.contract, self.manifest(exports))
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(
            result["routes"]["dynamic_jw_local_grid_source_leading"]["status"],
            "UNRESOLVED",
        )


if __name__ == "__main__":
    unittest.main()
