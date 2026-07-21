import copy
import importlib.util
import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "term_order_validator", HERE / "term_order_validator.py"
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VALIDATOR)


def load_json(name):
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class TermOrderValidatorTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_json("term_order_contract.json")
        self.export = load_json("term_order_native_fixture.json")

    def test_group_level_fixture_and_fusions(self):
        result = VALIDATOR.validate_export(self.contract, self.export)
        self.assertTrue(result["valid"])
        self.assertTrue(result["group_order_validated"])
        self.assertFalse(result["individual_term_sets_validated"])
        self.assertEqual(result["raw_group_events"], 20)
        self.assertEqual(result["within_step_H4_fusions"], 2)
        self.assertEqual(result["across_step_H1_fusions"], 1)
        self.assertEqual(result["fused_group_events"], 17)
        self.assertEqual(result["raw_term_calls"], 256)
        self.assertEqual(result["fused_term_calls"], 208)

    def test_individual_term_sets_are_checked(self):
        export = copy.deepcopy(self.export)
        terms = VALIDATOR.expected_terms(4)
        for step in export["steps"]:
            for event in step["events"]:
                event["terms"] = terms[event["group"]]
        result = VALIDATOR.validate_export(self.contract, export)
        self.assertTrue(result["valid"])
        self.assertTrue(result["individual_term_sets_validated"])

        export["steps"][0]["events"][0]["terms"] = terms["H2"]
        invalid = VALIDATOR.validate_export(self.contract, export)
        self.assertFalse(invalid["valid"])
        self.assertTrue(any("term set" in error for error in invalid["errors"]))

    def test_group_order_and_step_count_fail_closed(self):
        export = copy.deepcopy(self.export)
        export["steps"][0]["events"][2], export["steps"][0]["events"][3] = (
            export["steps"][0]["events"][3],
            export["steps"][0]["events"][2],
        )
        export["steps"].pop()
        result = VALIDATOR.validate_export(self.contract, export)
        self.assertFalse(result["valid"])
        self.assertTrue(any("expected 2 steps" in error for error in result["errors"]))
        self.assertTrue(any("group order mismatch" in error for error in result["errors"]))

    def test_matching_sizes_match_resource_model_convention(self):
        result = VALIDATOR.validate_export(self.contract, self.export)
        self.assertEqual(result["matching_sizes"], {"H1": 16, "H2": 8, "H3": 8, "H4": 16, "HU": 16})


if __name__ == "__main__":
    unittest.main()
