import copy
import importlib.util
import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "first_step_ledger_validator", HERE / "first_step_ledger_validator.py"
)
LEDGER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(LEDGER)


def contract():
    with (HERE / "first_step_contract.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def template():
    with (HERE / "first_step_ledger_template.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def route(compiled_exact=False):
    return {
        "R": 100,
        "steady_count_per_step": 448,
        "steady_depth_per_step": 8,
        "first_step_extra_count": 24,
        "first_step_extra_depth": 2,
        "compiled_exact": compiled_exact,
        "provenance": "synthetic test fixture",
        "timing": {
            "cnot_layer_us": 0.001,
            "non_cnot_us_per_steady_step": 0.01,
            "first_step_extra_non_cnot_us": 0.02,
            "timing_provenance": "synthetic timing fixture",
        },
    }


class FirstStepLedgerTests(unittest.TestCase):
    def test_template_is_unresolved_without_route_evidence(self):
        result = LEDGER.validate_ledger(contract(), template())
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(any("missing required routes" in error for error in result["errors"]))

    def test_bookkeeping_closed_estimate_is_not_complete(self):
        c = contract()
        c["required_routes"] = ["native_fermions"]
        ledger = template()
        ledger["routes"] = {"native_fermions": route(compiled_exact=False)}
        result = LEDGER.validate_ledger(c, ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        route_result = result["routes"]["native_fermions"]
        self.assertEqual(route_result["status"], "BOOKKEEPING_CLOSED_ESTIMATE")
        self.assertEqual(route_result["complete_count"], 44824)
        self.assertEqual(route_result["complete_depth"], 802)
        self.assertAlmostEqual(route_result["planning_circuit_us"], 1.822)
        self.assertIsNone(route_result["complete_circuit_us"])

    def test_exact_route_can_close_contract(self):
        c = contract()
        c["required_routes"] = ["native_fermions"]
        ledger = template()
        ledger["routes"] = {"native_fermions": route(compiled_exact=True)}
        result = LEDGER.validate_ledger(c, ledger)
        self.assertEqual(result["status"], "COMPLETE")
        route_result = result["routes"]["native_fermions"]
        self.assertEqual(route_result["status"], "COMPLETE")
        self.assertAlmostEqual(route_result["complete_circuit_us"], 1.822)

    def test_all_required_routes_must_close(self):
        c = contract()
        ledger = template()
        ledger["routes"] = {name: route(compiled_exact=True) for name in c["required_routes"]}
        ledger["routes"]["fsn_ladder_figure_candidate_fit"]["compiled_exact"] = False
        result = LEDGER.validate_ledger(c, ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(
            result["routes"]["fsn_ladder_figure_candidate_fit"]["status"],
            "BOOKKEEPING_CLOSED_ESTIMATE",
        )

    def test_invalid_timing_fails_closed_without_exception(self):
        c = contract()
        c["required_routes"] = ["native_fermions"]
        ledger = template()
        bad_route = copy.deepcopy(route(compiled_exact=True))
        bad_route["timing"]["cnot_layer_us"] = "unknown"
        ledger["routes"] = {"native_fermions": bad_route}
        result = LEDGER.validate_ledger(c, ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        route_result = result["routes"]["native_fermions"]
        self.assertEqual(route_result["status"], "UNRESOLVED")
        self.assertTrue(any("cnot_layer_us" in error for error in route_result["errors"]))

    def test_missing_timing_provenance_fails_closed(self):
        c = contract()
        c["required_routes"] = ["native_fermions"]
        ledger = template()
        bad_route = copy.deepcopy(route(compiled_exact=False))
        del bad_route["timing"]["timing_provenance"]
        ledger["routes"] = {"native_fermions": bad_route}
        result = LEDGER.validate_ledger(c, ledger)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(result["routes"]["native_fermions"]["status"], "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
