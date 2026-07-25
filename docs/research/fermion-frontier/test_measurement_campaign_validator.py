import copy
import importlib.util
import json
import math
import pathlib
import subprocess
import sys
import tempfile
import unittest
from types import MappingProxyType


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "measurement_campaign_validator", HERE / "measurement_campaign_validator.py"
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VALIDATOR)


def load_json(name):
    with (HERE / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class MeasurementCampaignValidatorTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_json("measurement_campaign_contract.json")
        self.plan = load_json("measurement_campaign_template.json")
        self.evidence = load_json("evidence_manifest_contract.json")

    def assess(self, contract=None, plan=None, evidence=None):
        return VALIDATOR.assess_campaign(
            self.contract if contract is None else contract,
            self.plan if plan is None else plan,
            self.evidence if evidence is None else evidence,
        )

    def test_template_derives_exact_axes_family_and_residual_shots(self):
        result = self.assess()
        self.assertEqual(
            result["status"], "EFFECTIVE_TARGETS_DERIVED_RAW_UNRESOLVED"
        )
        self.assertEqual(
            result["derived_axes"]["routes"],
            [
                "native_fermions",
                "dynamic_jw_local_grid",
                "fsn_standard",
                "fsn_ladder",
            ],
        )
        self.assertEqual(result["derived_axes"]["R_values"], [25, 50, 100, 200, 400, 800])
        self.assertEqual(result["derived_axes"]["cell_count"], 24)
        self.assertEqual(result["familywise"]["point_comparisons"], 48)
        self.assertEqual(result["familywise"]["adjacent_pair_comparisons"], 40)
        self.assertEqual(result["familywise"]["reference_comparisons"], 48)
        self.assertEqual(result["familywise"]["family_size"], 136)
        floor = result["floors"]["residual_budgeted_allocation"]
        self.assertEqual(
            floor["required_effective_shots_by_observable"],
            {
                "staggered_magnetization": 4_300_768,
                "double_occupancy": 1_075_192,
            },
        )
        self.assertEqual(floor["required_joint_effective_shots_per_cell"], 4_300_768)
        self.assertEqual(floor["uniform_campaign_effective_shots"], 103_218_432)
        self.assertEqual(result["totals"]["planned_joint_effective_shots"], 103_218_432)

    def test_reports_point_and_zero_residual_pair_floors(self):
        result = self.assess()
        point = result["floors"]["point_statistical_budget"]
        pair = result["floors"]["zero_residual_adjacent_pair"]
        self.assertEqual(
            point["required_effective_shots_by_observable"],
            {"staggered_magnetization": 172_031, "double_occupancy": 43_008},
        )
        self.assertEqual(point["uniform_campaign_effective_shots"], 4_128_744)
        self.assertEqual(
            pair["required_effective_shots_by_observable"],
            {"staggered_magnetization": 2_752_491, "double_occupancy": 688_123},
        )
        self.assertEqual(pair["uniform_campaign_effective_shots"], 66_059_784)

    def test_ten_thousand_effective_shots_fail_point_budget(self):
        half_width = VALIDATOR.bounded_hoeffding_half_width(2.0, 10_000, 136, 0.05)
        self.assertGreater(half_width, 0.01)
        self.assertAlmostEqual(half_width, 0.04147658216355342)

    def test_ceiling_is_fail_closed_at_one_shot_below_threshold(self):
        raw, required = VALIDATOR.bounded_hoeffding_required_shots(
            2.0, 0.002, 136, 0.05
        )
        self.assertGreater(raw, required - 1)
        self.assertLessEqual(
            VALIDATOR.bounded_hoeffding_half_width(2.0, required, 136, 0.05),
            0.002,
        )
        self.assertGreater(
            VALIDATOR.bounded_hoeffding_half_width(2.0, required - 1, 136, 0.05),
            0.002,
        )

    def test_shared_batch_uses_maximum_not_sum(self):
        result = self.assess()
        cell = result["cells"][0]
        by_observable = cell["planned_effective_shots_by_observable"]
        self.assertEqual(cell["planned_joint_effective_shots"], max(by_observable.values()))
        self.assertNotEqual(cell["planned_joint_effective_shots"], sum(by_observable.values()))

    def test_missing_route_r_cell_is_invalid(self):
        plan = copy.deepcopy(self.plan)
        plan["cells"].pop()
        result = self.assess(plan=plan)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("missing route/R" in error for error in result["errors"]))

    def test_duplicate_or_relabelled_route_r_cell_is_invalid(self):
        plan = copy.deepcopy(self.plan)
        plan["cells"][-1]["route"] = "native_fermions"
        plan["cells"][-1]["R"] = 25
        result = self.assess(plan=plan)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("duplicates route/R" in error for error in result["errors"]))

    def test_evidence_policy_drift_breaks_canonical_hash(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["convergence_workload_policy"]["target_R"] = 200
        result = self.assess(evidence=evidence)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("canonical SHA256" in error for error in result["errors"]))

    def test_plan_hash_drift_is_invalid(self):
        plan = copy.deepcopy(self.plan)
        plan["evidence_contract_canonical_sha256"] = "0" * 64
        result = self.assess(plan=plan)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("plan evidence hash" in error for error in result["errors"]))

    def test_null_acceptance_and_effective_fraction_never_invent_raw_totals(self):
        result = self.assess()
        self.assertEqual(
            result["status"], "EFFECTIVE_TARGETS_DERIVED_RAW_UNRESOLVED"
        )
        self.assertIsNone(result["totals"]["planned_accepted_shots"])
        self.assertIsNone(result["totals"]["expected_attempted_shots"])
        self.assertTrue(all(cell["planned_accepted_shots"] is None for cell in result["cells"]))

    def test_valid_p_and_eta_produce_expected_only_attempts(self):
        plan = copy.deepcopy(self.plan)
        for cell in plan["cells"]:
            cell["effective_shot_fraction"] = 0.5
            cell["acceptance_probability"] = 0.25
            cell["sampling_assumption_provenance"] = "synthetic planning assumption"
        result = self.assess(plan=plan)
        self.assertEqual(result["status"], "EXPECTED_EXECUTION_PLAN_ONLY")
        self.assertEqual(result["cells"][0]["planned_accepted_shots"], 8_601_536)
        self.assertEqual(result["cells"][0]["expected_attempted_shots"], 34_406_144)
        self.assertEqual(result["totals"]["planned_accepted_shots"], 206_436_864)
        self.assertEqual(result["totals"]["expected_attempted_shots"], 825_747_456)
        cell_high_confidence_cap = VALIDATOR._high_confidence_attempt_cap(
            result["cells"][0]["planned_accepted_shots"],
            0.25,
            0.01,
        )
        self.assertEqual(result["cells"][0]["high_confidence_attempt_cap"], cell_high_confidence_cap)
        self.assertEqual(
            result["totals"]["high_confidence_attempt_cap"], cell_high_confidence_cap * 24
        )
        self.assertEqual(
            result["attempt_budget"]["high_confidence_method"], VALIDATOR.HIGH_CONFIDENCE_METHOD
        )
        self.assertEqual(
            result["attempt_budget"]["high_confidence_warning"],
            "ceiled_attempts is an expected-only planning quantity. high_confidence"
            "_attempt_cap uses a conservative Chernoff lower-tail bound for failure rate",
        )
        self.assertNotIn("READY", result["status"])
        self.assertEqual(result["convergence_certification"], "NOT_ASSESSED_BY_PREFLIGHT")

    def test_partial_p_eta_remains_raw_unresolved(self):
        plan = copy.deepcopy(self.plan)
        plan["cells"][0]["effective_shot_fraction"] = 1.0
        plan["cells"][0]["acceptance_probability"] = 0.5
        plan["cells"][0]["sampling_assumption_provenance"] = "one-cell assumption"
        result = self.assess(plan=plan)
        self.assertEqual(
            result["status"], "EFFECTIVE_TARGETS_DERIVED_RAW_UNRESOLVED"
        )
        self.assertIsNone(result["totals"]["planned_accepted_shots"])
        self.assertIsNone(result["totals"]["expected_attempted_shots"])

    def test_bounded_range_doubling_scales_unrounded_shots_quadratically(self):
        baseline = self.assess()
        plan = copy.deepcopy(self.plan)
        for cell in plan["cells"]:
            cell["mitigation_mode"] = "bounded_weighted"
            cell["per_shot_contribution_ranges"]["staggered_magnetization"] = [-2.0, 2.0]
        widened = self.assess(plan=plan)
        self.assertEqual(widened["status"], "EFFECTIVE_TARGETS_DERIVED_RAW_UNRESOLVED")
        base_raw = baseline["cells"][0]["unrounded_effective_shots_by_observable"][
            "staggered_magnetization"
        ]
        wide_raw = widened["cells"][0]["unrounded_effective_shots_by_observable"][
            "staggered_magnetization"
        ]
        self.assertTrue(math.isclose(wide_raw, 4.0 * base_raw, rel_tol=1e-15))
        self.assertEqual(
            widened["cells"][0]["planned_effective_shots_by_observable"][
                "staggered_magnetization"
            ],
            17_203_069,
        )
        self.assertEqual(widened["totals"]["planned_joint_effective_shots"], 412_873_656)

    def test_no_mitigation_cannot_claim_narrower_range(self):
        plan = copy.deepcopy(self.plan)
        plan["cells"][0]["per_shot_contribution_ranges"]["staggered_magnetization"] = [
            -0.5,
            0.5,
        ]
        result = self.assess(plan=plan)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("physical range" in error for error in result["errors"]))

    def test_residual_allocation_oversubscription_is_invalid(self):
        contract = copy.deepcopy(self.contract)
        contract["allocation_by_observable"]["double_occupancy"][
            "target_half_width"
        ] = 0.0021
        result = self.assess(contract=contract)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(
            any(
                "target_half_width must equal" in error or "oversubscribes" in error
                for error in result["errors"]
            )
        )

    def test_user_supplied_family_or_shot_counts_are_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["family_size"] = 1
        plan["cells"][0]["accepted_shots"] = 10_000
        result = self.assess(plan=plan)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("derived or actual" in error for error in result["errors"]))

    def test_planned_output_never_emits_actual_measurement_fields(self):
        result = self.assess()
        for cell in result["cells"]:
            self.assertNotIn("accepted_shots", cell)
            self.assertNotIn("attempted_shots", cell)
            self.assertNotIn("effective_independent_shots", cell)
            self.assertIn("planned_joint_effective_shots", cell)

    def test_invalid_acceptance_probability_is_fail_closed(self):
        plan = copy.deepcopy(self.plan)
        plan["cells"][0]["acceptance_probability"] = 1.01
        plan["cells"][0]["effective_shot_fraction"] = 1.0
        plan["cells"][0]["sampling_assumption_provenance"] = "invalid fixture"
        result = self.assess(plan=plan)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("must be in (0, 1]" in error for error in result["errors"]))

    def test_boolean_schema_versions_are_rejected(self):
        contract = copy.deepcopy(self.contract)
        contract["schema_version"] = True
        self.assertEqual(self.assess(contract=contract)["status"], "INVALID_SCHEMA")
        plan = copy.deepcopy(self.plan)
        plan["schema_version"] = True
        self.assertEqual(self.assess(plan=plan)["status"], "INVALID_SCHEMA")

    def test_non_object_top_levels_fail_closed(self):
        for contract, plan, evidence in (
            ([], self.plan, self.evidence),
            (self.contract, [], self.evidence),
            (self.contract, self.plan, []),
        ):
            with self.subTest(contract=type(contract), plan=type(plan), evidence=type(evidence)):
                result = VALIDATOR.assess_campaign(contract, plan, evidence)
                self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_cli_returns_nonzero_for_invalid_schema(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            bad_plan = pathlib.Path(temporary_directory) / "bad-plan.json"
            bad_plan.write_text("[]\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(HERE / "measurement_campaign_validator.py"),
                    "--contract",
                    str(HERE / "measurement_campaign_contract.json"),
                    "--plan",
                    str(bad_plan),
                    "--evidence-contract",
                    str(HERE / "evidence_manifest_contract.json"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertIn('"status": "INVALID_SCHEMA"', completed.stdout)

    def test_huge_json_integer_fails_closed_instead_of_overflowing(self):
        plan = copy.deepcopy(self.plan)
        plan["cells"][0]["acceptance_probability"] = 10**10_000
        plan["cells"][0]["effective_shot_fraction"] = 1.0
        plan["cells"][0]["sampling_assumption_provenance"] = "overflow fixture"
        result = self.assess(plan=plan)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("canonicalized" in error for error in result["errors"]))

    def test_huge_evidence_integer_fails_closed_before_unpinned_interpretation(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["convergence_workload_policy"]["familywise_error_rate"] = 10**10_000
        result = self.assess(evidence=evidence)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("canonicalized" in error for error in result["errors"]))

    def test_non_json_mapping_public_api_fails_closed(self):
        evidence = MappingProxyType(copy.deepcopy(self.evidence))
        result = self.assess(evidence=evidence)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertTrue(any("canonicalized" in error for error in result["errors"]))

    def test_probability_ceiling_uses_exact_float_ratio(self):
        plan = copy.deepcopy(self.plan)
        eta = 0.09999999999999999
        for cell in plan["cells"]:
            cell["effective_shot_fraction"] = eta
            cell["acceptance_probability"] = 1.0
            cell["sampling_assumption_provenance"] = "binary-ratio fixture"
        result = self.assess(plan=plan)
        numerator, denominator = eta.as_integer_ratio()
        count = 4_300_768
        expected = (count * denominator + numerator - 1) // numerator
        self.assertEqual(result["cells"][0]["planned_accepted_shots"], expected)
        self.assertEqual(expected, 43_007_681)


if __name__ == "__main__":
    unittest.main()
