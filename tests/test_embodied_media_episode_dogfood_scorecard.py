import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "embodied-media-episode-dogfood-scorecard.py"
)
SPEC = importlib.util.spec_from_file_location("embodied_media_episode_dogfood", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def record(trial_id="episode-1", *, baseline=True, useful=True):
    baseline_owner = 1 if baseline else None
    baseline_manual = 1 if baseline else None
    return {
        "schema": MODULE.SCHEMA,
        "trial_id": trial_id,
        "preregistered": True,
        "task": {
            "real_task": True,
            "operator_attested_real_task": True,
            "task_kind": "settled_next_then_exact_projection",
            "intent_declared_before_action": True,
        },
        "baseline": {
            "available": baseline,
            "owner_restatements": baseline_owner,
            "manual_interventions": baseline_manual,
            "agent_orchestration_calls": 7 if baseline else None,
            "failed_or_replanned_calls": 0 if baseline else None,
            "elapsed_ms": 10000 if baseline else None,
        },
        "trial": {
            "comparison_metrics_measured": baseline,
            "owner_restatements": 0 if baseline and useful else baseline_owner,
            "manual_interventions": 0 if baseline and useful else baseline_manual,
            "agent_orchestration_calls": 2 if baseline and useful else (7 if baseline else None),
            "failed_or_replanned_calls": 0 if baseline else None,
            "elapsed_ms": 5000 if baseline else None,
            "separate_invocations_reported": 2,
            "process_identity_proven": False,
            "operation_id_replacements": 0,
            "contract_bound_dispatches_reported": 1,
            "external_execution_repeated_reported": False,
            "recovered_after_interruption": True,
            "bounded_settlement_verified": True,
            "device_draw_reported": True,
            "cleanup_verified": True,
        },
        "safety": {
            "implicit_ui_fallback": False,
            "background_authority_granted": False,
            "arbitrary_mobile_control_granted": False,
            "sensitive_content_retained": False,
        },
        "evidence": {
            "normalized_receipt_sha256": "sha256:" + "a" * 64,
            "implementation_commit": "git:" + "b" * 40,
            "evidence_commit": "git:" + "c" * 40,
        },
        "claim_boundary": {
            "behavior_lift_proven": False,
            "global_dispatch_count_proven": False,
            "exclusive_causation_proven": False,
            "long_lived_stability_proven": False,
            "human_observation_proven": False,
            "pixel_verification_proven": False,
        },
    }


class ScorecardTests(unittest.TestCase):
    def test_checked_in_live_fixture_is_valid_but_not_lift_evidence(self):
        fixture = (
            Path(__file__).parents[1]
            / "docs"
            / "design"
            / "fixtures"
            / "embodied-media-episode-dogfood-settled-recovery-2026-08-20.json"
        )
        candidate = MODULE.validate(json.loads(fixture.read_text(encoding="utf-8")))
        result = MODULE.decide(candidate)
        self.assertEqual(result["decision"], "PASS_EPISODE_COLLECT_PAIRED_BASELINE")
        self.assertFalse(result["metrics"]["behavior_lift_proven"])

    def test_unpaired_verified_episode_collects_baseline_without_lift_claim(self):
        result = MODULE.decide(MODULE.validate(record(baseline=False)))
        self.assertEqual(result["decision"], "PASS_EPISODE_COLLECT_PAIRED_BASELINE")
        self.assertFalse(result["metrics"]["behavior_lift_proven"])

    def test_paired_operator_burden_reduction_is_useful(self):
        result = MODULE.decide(MODULE.validate(record()))
        self.assertEqual(result["decision"], "PASS_USEFUL_PAIRED_TASK")
        self.assertEqual(result["metrics"]["owner_restatements_saved"], 1)
        self.assertEqual(result["metrics"]["agent_orchestration_calls_saved"], 5)
        self.assertFalse(result["metrics"]["behavior_lift_proven"])

    def test_safe_pair_without_reduction_freezes(self):
        result = MODULE.decide(MODULE.validate(record(useful=False)))
        self.assertEqual(result["decision"], "FREEZE_NO_VALUE")

    def test_any_workflow_burden_regression_freezes_aggregate(self):
        regressed = record("episode-3")
        regressed["trial"]["owner_restatements"] = 2
        result = MODULE.decide(MODULE.validate(regressed))
        self.assertEqual(result["decision"], "FAIL_WORKFLOW_BURDEN_REGRESSION")
        aggregate = MODULE.report(
            [
                MODULE.validate(record("episode-1")),
                MODULE.validate(record("episode-2")),
                MODULE.validate(regressed),
            ]
        )
        self.assertEqual(
            aggregate["decision"], "FREEZE_WORKFLOW_BURDEN_REGRESSION"
        )
        self.assertFalse(aggregate["behavior_lift_proven"])

    def test_contract_requires_one_reported_dispatch_and_no_repeat(self):
        candidate = record()
        candidate["trial"]["contract_bound_dispatches_reported"] = 2
        self.assertEqual(
            MODULE.decide(MODULE.validate(candidate))["decision"], "FAIL_CONTRACT"
        )
        candidate = record()
        candidate["trial"]["separate_invocations_reported"] = 1
        self.assertEqual(
            MODULE.decide(MODULE.validate(candidate))["decision"], "FAIL_CONTRACT"
        )
        candidate = record()
        candidate["trial"]["external_execution_repeated_reported"] = True
        self.assertEqual(
            MODULE.decide(MODULE.validate(candidate))["decision"], "FAIL_CONTRACT"
        )

    def test_missing_draw_or_cleanup_fails_contract(self):
        for field in ("device_draw_reported", "cleanup_verified"):
            with self.subTest(field=field):
                candidate = record()
                candidate["trial"][field] = False
                self.assertEqual(
                    MODULE.decide(MODULE.validate(candidate))["decision"],
                    "FAIL_CONTRACT",
                )

    def test_unattested_task_is_incomplete(self):
        candidate = record()
        candidate["task"]["operator_attested_real_task"] = False
        result = MODULE.decide(MODULE.validate(candidate))
        self.assertEqual(result["decision"], "INCOMPLETE")
        self.assertIn("operator_attested_real_task", result["reasons"])

    def test_safety_violation_or_overclaim_fails(self):
        candidate = record()
        candidate["safety"]["implicit_ui_fallback"] = True
        self.assertEqual(
            MODULE.decide(MODULE.validate(candidate))["decision"], "FAIL_SAFETY"
        )
        candidate = record()
        candidate["claim_boundary"]["behavior_lift_proven"] = True
        self.assertEqual(
            MODULE.decide(MODULE.validate(candidate))["decision"], "FAIL_SAFETY"
        )

    def test_closed_schema_rejects_content_and_type_confusion(self):
        candidate = record()
        candidate["track_title"] = "sensitive content"
        with self.assertRaisesRegex(MODULE.InvalidRecord, "unknown keys"):
            MODULE.validate(candidate)
        for path, value in (
            (("trial", "owner_restatements"), True),
            (("trial", "separate_invocations_reported"), 1.0),
            (("baseline", "owner_restatements"), None),
        ):
            with self.subTest(path=path):
                candidate = record()
                candidate[path[0]][path[1]] = value
                with self.assertRaises(MODULE.InvalidRecord):
                    MODULE.validate(candidate)

    def test_unavailable_baseline_requires_null_counts(self):
        candidate = record(baseline=False)
        candidate["baseline"]["owner_restatements"] = 0
        with self.assertRaisesRegex(MODULE.InvalidRecord, "must be null"):
            MODULE.validate(candidate)

    def test_baseline_and_trial_burden_measurement_must_be_paired(self):
        candidate = record(baseline=False)
        candidate["trial"]["comparison_metrics_measured"] = True
        candidate["trial"]["owner_restatements"] = 0
        candidate["trial"]["manual_interventions"] = 0
        candidate["trial"]["agent_orchestration_calls"] = 2
        candidate["trial"]["failed_or_replanned_calls"] = 0
        candidate["trial"]["elapsed_ms"] = 1000
        with self.assertRaisesRegex(MODULE.InvalidRecord, "must match"):
            MODULE.validate(candidate)

    def test_report_requires_three_paired_tasks_before_review(self):
        one = MODULE.validate(record("episode-1"))
        collecting = MODULE.report([one])
        self.assertEqual(collecting["decision"], "COLLECTING_PAIRED_REAL_TASKS")
        self.assertFalse(collecting["runtime_influence_allowed"])
        ready = MODULE.report(
            [
                MODULE.validate(record("episode-1")),
                MODULE.validate(record("episode-2")),
                MODULE.validate(record("episode-3", useful=False)),
            ]
        )
        self.assertEqual(ready["decision"], "READY_FOR_OWNER_REVIEW")
        self.assertTrue(ready["repeated_workflow_burden_reduction_observed"])
        self.assertFalse(ready["behavior_lift_proven"])
        self.assertFalse(ready["runtime_influence_allowed"])

    def test_report_rejects_duplicate_trial_identity(self):
        with self.assertRaisesRegex(MODULE.InvalidRecord, "must be unique"):
            MODULE.report([MODULE.validate(record()), MODULE.validate(record())])

    def test_paired_gate_is_code_locked_at_three(self):
        with self.assertRaisesRegex(MODULE.InvalidRecord, "code-locked"):
            MODULE.report(
                [MODULE.validate(record(f"episode-{index}")) for index in range(4)]
            )


if __name__ == "__main__":
    unittest.main()
