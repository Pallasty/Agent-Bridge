"""Contract checks for the offline harness candidate audit."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/eval/harness_candidate_audit.py"
spec = importlib.util.spec_from_file_location("harness_candidate_audit", SCRIPT)
assert spec is not None and spec.loader is not None
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def packet() -> dict:
    digest = "a" * 64
    return {
        "schema_version": 1,
        "trial_id": "bounded-new-tool-01",
        "candidate_module": "context_mgmt",
        "baseline_revision": "1" * 40,
        "candidate_revision": "2" * 40,
        "exploration_task_ids": ["practice-1"],
        "evaluation_task_ids": ["held-1", "held-2"],
        "runs": [
            {"task_id": "held-1", "arm": "baseline", "model": "fixed-model", "budget": 100,
             "memory_sha256": "b" * 64, "outcome": "fail", "verifier_kind": "independent",
             "evidence_sha256": digest, "score_visible_to_learning": False},
            {"task_id": "held-1", "arm": "candidate", "model": "fixed-model", "budget": 100,
             "memory_sha256": "c" * 64, "outcome": "pass", "verifier_kind": "independent",
             "evidence_sha256": digest, "score_visible_to_learning": False},
            {"task_id": "held-2", "arm": "baseline", "model": "fixed-model", "budget": 100,
             "memory_sha256": "b" * 64, "outcome": "pass", "verifier_kind": "independent",
             "evidence_sha256": digest, "score_visible_to_learning": False},
            {"task_id": "held-2", "arm": "candidate", "model": "fixed-model", "budget": 100,
             "memory_sha256": "c" * 64, "outcome": "pass", "verifier_kind": "independent",
             "evidence_sha256": digest, "score_visible_to_learning": False},
        ],
    }


class HarnessCandidateAuditTests(unittest.TestCase):
    def test_complete_frozen_pair_is_only_review_eligible(self) -> None:
        result = audit.evaluate(packet())
        self.assertEqual(result["verdict"], "review_candidate")
        self.assertEqual(result["paired_tasks"], 2)
        self.assertEqual(result["improvements"], 1)
        self.assertEqual(result["regressions"], 0)
        self.assertFalse(result["runtime_or_memory_promotion_authorized"])
        self.assertFalse(result["evidence_authenticated"])
        self.assertFalse(result["task_value_proven"])

    def test_rejects_exploration_leak_into_evaluation(self) -> None:
        case = packet()
        case["exploration_task_ids"].append("held-1")
        result = audit.evaluate(case)
        self.assertEqual(result["verdict"], "invalid_protocol")
        self.assertIn("task_overlap", result["reasons"])

    def test_rejects_missing_or_duplicate_arm(self) -> None:
        missing = packet()
        missing["runs"].pop()
        self.assertIn("incomplete_pair", audit.evaluate(missing)["reasons"])
        duplicate = packet()
        duplicate["runs"].append(duplicate["runs"][0].copy())
        self.assertIn("duplicate_run", audit.evaluate(duplicate)["reasons"])

    def test_rejects_unmatched_model_or_budget(self) -> None:
        for field, value, reason in (
            ("model", "other-model", "model_mismatch"),
            ("budget", 200, "budget_mismatch"),
        ):
            with self.subTest(field=field):
                case = packet()
                case["runs"][1][field] = value
                self.assertIn(reason, audit.evaluate(case)["reasons"])

    def test_rejects_unverified_or_leaked_outcome(self) -> None:
        for field, value, reason in (
            ("verifier_kind", "agent_reported", "non_independent_verifier"),
            ("score_visible_to_learning", True, "score_leakage"),
            ("evidence_sha256", "", "missing_evidence"),
        ):
            with self.subTest(field=field):
                case = packet()
                case["runs"][1][field] = value
                self.assertIn(reason, audit.evaluate(case)["reasons"])

    def test_rejects_memory_drift_and_unresolved_result(self) -> None:
        drift = packet()
        drift["runs"][3]["memory_sha256"] = "d" * 64
        self.assertIn("memory_drift", audit.evaluate(drift)["reasons"])
        unresolved = packet()
        unresolved["runs"][3]["outcome"] = "unresolved"
        self.assertIn("unresolved_outcome", audit.evaluate(unresolved)["reasons"])

    def test_regression_cannot_be_review_candidate(self) -> None:
        case = packet()
        case["runs"][3]["outcome"] = "fail"
        result = audit.evaluate(case)
        self.assertEqual(result["verdict"], "regression")
        self.assertEqual(result["regressions"], 1)

    def test_malformed_fields_fail_closed(self) -> None:
        case = packet()
        case["candidate_module"] = ["context_mgmt"]
        case["runs"][0]["task_id"] = ["held-1"]
        result = audit.evaluate(case)
        self.assertEqual(result["verdict"], "invalid_protocol")
        self.assertIn("invalid_module", result["reasons"])
        self.assertIn("unexpected_run", result["reasons"])

    def test_same_revision_is_not_candidate(self) -> None:
        case = packet()
        case["candidate_revision"] = case["baseline_revision"]
        self.assertIn("unchanged_revision", audit.evaluate(case)["reasons"])


if __name__ == "__main__":
    unittest.main()
