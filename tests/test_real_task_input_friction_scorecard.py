import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "real_task_input_friction_scorecard.py"
SPEC = importlib.util.spec_from_file_location("real_task_input_friction_scorecard", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def record():
    return {
        "schema": MODULE.SCHEMA,
        "trial_id": "real-task-input-friction-v0-1",
        "preregistered": True,
        "task": {
            "real_task": True,
            "task_reference": "active acceptance task",
            "needed_context_declared_before_input": True,
        },
        "baseline": {
            "context_recovery_actions": 2,
            "desktop_surface_switches": 1,
            "desktop_text_or_copy_actions": 1,
        },
        "trial": {
            "context_recovery_actions": 1,
            "desktop_surface_switches": 0,
            "desktop_text_or_copy_actions": 0,
            "foreground_user_confirmed": True,
            "unique_input_accepted": 1,
            "consumed_via_exact_session_status": True,
            "context_recovered": True,
            "affected_real_decision": True,
            "upstream_failure_class": "none",
        },
        "safety": {
            "background_capture": False,
            "implicit_control": False,
            "full_text_persisted": False,
            "ungranted_phone_or_runtime_action": False,
            "projection_stopped": True,
            "fresh_process_cannot_retrieve_input": True,
        },
        "diagnosis": {
            "failure_class": "none",
            "stage": "decision",
            "persisted": False,
            "persistence_reference": "",
            "evidence_digest_sha256": "",
            "retry_recommended": False,
        },
        "evidence": {
            "baseline_reference": "baseline metadata",
            "input_reference": "accepted observation id and hash",
            "consumption_reference": "exact-session status receipt",
            "decision_reference": "bounded next-step receipt",
            "cleanup_reference": "fresh-process lookup receipt",
        },
    }


def bind_failure(candidate, failure_class):
    candidate["diagnosis"].update(
        {
            "failure_class": failure_class,
            "persisted": True,
            "persistence_reference": "local metadata-only diagnostic ledger row",
        }
    )
    material = (
        f"{candidate['trial_id']}\n{failure_class}\n"
        + json.dumps(candidate["evidence"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    ).encode()
    candidate["diagnosis"]["evidence_digest_sha256"] = hashlib.sha256(material).hexdigest()


class ScorecardTests(unittest.TestCase):
    def test_useful_task_reports_context_and_input_savings(self):
        result = MODULE.decide(MODULE.validate(record()))
        self.assertEqual(result["decision"], "PASS_USEFUL")
        self.assertEqual(result["metrics"]["context_recovery_actions_saved"], 1)
        self.assertFalse(result["retains_input_text"])

    def test_context_failure_requires_bound_persisted_diagnosis(self):
        candidate = record()
        candidate["trial"]["context_recovered"] = False
        bind_failure(candidate, "context_not_recovered")
        result = MODULE.decide(MODULE.validate(candidate))
        self.assertEqual(result["decision"], "INCOMPLETE")
        self.assertTrue(result["diagnosis"]["persisted"])

    def test_unpersisted_failure_is_invalid(self):
        candidate = record()
        candidate["trial"]["affected_real_decision"] = False
        candidate["diagnosis"]["failure_class"] = "decision_unchanged"
        with self.assertRaisesRegex(MODULE.InvalidRecord, "persisted diagnosis"):
            MODULE.decide(MODULE.validate(candidate))

    def test_missing_foreground_confirmation_is_incomplete(self):
        candidate = record()
        candidate["trial"]["foreground_user_confirmed"] = False
        bind_failure(candidate, "evidence_missing")
        self.assertEqual(MODULE.decide(MODULE.validate(candidate))["decision"], "INCOMPLETE")

    def test_provider_timeout_is_persisted_and_never_auto_retried(self):
        candidate = record()
        candidate["trial"]["upstream_failure_class"] = "provider_timeout"
        bind_failure(candidate, "provider_timeout")
        result = MODULE.decide(MODULE.validate(candidate))
        self.assertEqual(result["failure_class"], "provider_timeout")
        self.assertFalse(result["diagnosis"]["retry_recommended"])

        candidate["diagnosis"]["retry_recommended"] = True
        with self.assertRaisesRegex(MODULE.InvalidRecord, "automatic retry"):
            MODULE.decide(MODULE.validate(candidate))

    def test_failure_digest_detects_evidence_drift(self):
        candidate = record()
        candidate["trial"]["consumed_via_exact_session_status"] = False
        bind_failure(candidate, "input_not_consumed")
        candidate["evidence"]["consumption_reference"] = "changed after diagnosis"
        with self.assertRaisesRegex(MODULE.InvalidRecord, "does not bind"):
            MODULE.decide(MODULE.validate(candidate))

    def test_authority_crossing_precedes_usefulness(self):
        candidate = record()
        candidate["safety"]["ungranted_phone_or_runtime_action"] = True
        bind_failure(candidate, "authority_crossed")
        self.assertEqual(MODULE.decide(MODULE.validate(candidate))["decision"], "FAIL_SAFETY")

    def test_no_value_is_classified_not_promoted(self):
        candidate = record()
        for key in MODULE.METRIC_KEYS:
            candidate["trial"][key] = candidate["baseline"][key]
        bind_failure(candidate, "no_interaction_cost_reduction")
        self.assertEqual(MODULE.decide(MODULE.validate(candidate))["decision"], "FREEZE_NO_VALUE")

    def test_unknown_text_field_is_rejected(self):
        candidate = record()
        candidate["input_text"] = "must never enter the scorecard"
        with self.assertRaisesRegex(MODULE.InvalidRecord, "unknown keys"):
            MODULE.validate(candidate)


if __name__ == "__main__":
    unittest.main()
