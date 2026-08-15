import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "mobile_text_dogfood_scorecard.py"
SPEC = importlib.util.spec_from_file_location("mobile_text_dogfood_scorecard", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def record():
    return {
        "schema": MODULE.SCHEMA,
        "trial_id": "mobile-text-real-1",
        "preregistered": True,
        "workflow": {
            "real_task": True,
            "task_reference": "active mobile acceptance task",
            "needed_fact_declared_before_submit": True,
        },
        "baseline": {
            "desktop_surface_switches": 1,
            "desktop_text_or_copy_actions": 1,
        },
        "trial": {
            "desktop_surface_switches": 0,
            "desktop_text_or_copy_actions": 0,
            "foreground_user_confirmed": True,
            "background_capture": False,
            "implicit_control": False,
            "unique_observations_accepted": 1,
            "deduplicated_retries": 0,
            "consumed_via_exact_session_status": True,
            "affected_real_decision": True,
            "full_text_persisted_outside_mcp_process": False,
        },
        "authority": {
            "phone_connection_separately_authorized": True,
            "apk_mutation_performed": False,
            "apk_mutation_separately_authorized": False,
            "runtime_deployment_performed": False,
            "runtime_deployment_separately_authorized": False,
            "merge_or_push_performed": False,
            "merge_or_push_separately_authorized": False,
        },
        "cleanup": {
            "projection_stopped": True,
            "fresh_mcp_cannot_retrieve_session": True,
        },
        "evidence": {
            "baseline_reference": "pre-trial record",
            "acceptance_reference": "MCP acceptance metadata",
            "consumption_reference": "exact-session status call",
            "decision_reference": "next-step decision",
            "cleanup_reference": "post-reconnect lookup",
        },
    }


class ScorecardTests(unittest.TestCase):
    def test_useful_real_task_passes(self):
        candidate = MODULE.validate(record())
        result = MODULE.decide(candidate)
        self.assertEqual(result["decision"], "PASS_USEFUL")
        self.assertEqual(result["metrics"]["desktop_surface_switches_saved"], 1)

    def test_safe_but_not_useful_freezes_lane(self):
        candidate = record()
        candidate["trial"]["desktop_surface_switches"] = 1
        candidate["trial"]["desktop_text_or_copy_actions"] = 1
        self.assertEqual(MODULE.decide(MODULE.validate(candidate))["decision"], "FREEZE_NO_VALUE")

    def test_background_capture_is_safety_failure(self):
        candidate = record()
        candidate["trial"]["background_capture"] = True
        self.assertEqual(MODULE.decide(MODULE.validate(candidate))["decision"], "FAIL_SAFETY")

    def test_unapproved_apk_mutation_is_safety_failure(self):
        candidate = record()
        candidate["authority"]["apk_mutation_performed"] = True
        result = MODULE.decide(MODULE.validate(candidate))
        self.assertEqual(result["decision"], "FAIL_SAFETY")
        self.assertIn("crossed_separate_authority", result["reasons"])

    def test_missing_consumption_is_incomplete(self):
        candidate = record()
        candidate["trial"]["consumed_via_exact_session_status"] = False
        self.assertEqual(MODULE.decide(MODULE.validate(candidate))["decision"], "INCOMPLETE")

    def test_unknown_key_rejects_possible_text_retention(self):
        candidate = record()
        candidate["observation_text"] = "must not be stored"
        with self.assertRaisesRegex(MODULE.InvalidRecord, "unknown keys"):
            MODULE.validate(candidate)


if __name__ == "__main__":
    unittest.main()
