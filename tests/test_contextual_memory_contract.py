"""Exercise contextual memory obligations using the existing offline scorer.

The six synthetic pairs share identical evidence catalogs. Only the explicit
request (audience, task, entity, purpose) or time changes. These are illustrative
review constraints, not learned social rules or inferred permissions:

* Owner requests detail; an explicitly authorized collaborator requests only the
  shared summary. The same owner-detail claim/evidence becomes forbidden.
* The same next-action evidence supports a related memory request but cannot
  answer an unrelated memory request. Abstention means no supported memory for
  that request, not refusal to help or silence in general conversation.
* The same deadline claim must switch from v1 to v2 evidence across the update.
* The same commitment claim must cite project A or B according to the request.
* The same revocation-audit claim is optional for current action and required
  for retrospective. History remains valid; the old plan is never current again.
* An attributed tentative inference is the only supported status before an
  external check; verified status requires the external check afterward.
  A separate prior-inference-history label remains optional afterward, preserving
  provenance without restoring an outdated tentative current status.
  ``supported`` on ``status_tentative_inference`` supports its *attribution as
  an unverified inference*, never its underlying proposition. These are reviewed
  semantic labels; the scorer does not read or judge natural-language answers.

The hand-authored ``synthetic_reference`` candidate is a scorer oracle, not
model output. All token and latency values are unmeasured placeholders (0),
not performance measurements. No model, retrieval, AB runtime, or store is used.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "scripts/eval/fixtures"
SPEC = importlib.util.spec_from_file_location(
    "contextual_memory_existing_scorer",
    ROOT / "scripts/eval/portfolio_continuity_eval.py",
)
assert SPEC and SPEC.loader
SCORER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCORER)

PAIRS = (
    ("audience_owner_detail", "audience_collaborator_summary"),
    ("task_relevant", "task_unrelated"),
    ("deadline_before_update", "deadline_after_update"),
    ("entity_project_a", "entity_project_b"),
    ("revocation_current_action", "revocation_retrospective"),
    ("provenance_inference_only", "provenance_externally_verified"),
)


def find_case(packet, case_id):
    return next(case for case in packet["cases"] if case["case_id"] == case_id)


def find_claim(case, claim_id):
    return next(claim for claim in case["claims"] if claim["claim_id"] == claim_id)


class ContextualMemoryContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture, _ = SCORER.read_json(FIXTURES / "contextual_memory_contract.json")
        self.candidate, _ = SCORER.read_json(
            FIXTURES / "contextual_memory_candidate_reference.json"
        )

    def score(self):
        return SCORER.build_packet(
            self.fixture,
            self.candidate,
            json.dumps(self.fixture, sort_keys=True).encode(),
            json.dumps(self.candidate, sort_keys=True).encode(),
        )

    def failed_case(self, case_id):
        result = self.score()
        self.assertEqual(result["verdict"], "FAIL")
        row = find_case(result, case_id)
        self.assertFalse(row["passed"])
        return row

    def test_reference_passes_only_as_unmeasured_synthetic_oracle(self):
        result = self.score()
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["condition"], "synthetic_reference")
        self.assertEqual(result["aggregate"]["case_pass_count"], 12)
        self.assertEqual(result["aggregate"]["supported_claim_coverage"], 1.0)
        self.assertEqual(result["aggregate"]["evidence_precision"], 1.0)
        self.assertTrue(all(result["gate_checks"].values()))
        for case in self.candidate["cases"]:
            self.assertEqual(case["context_tokens"], 0)
            self.assertEqual(case["latency_ms"], 0)
        # The old schema calls present cost fields "complete" even when they
        # are placeholders. This result makes no measured-cost claim.
        self.assertIn("unmeasured placeholders (0)", self.fixture["description"])
        for capability in (
            "calls_llm", "calls_retrieval", "reads_ab_store", "writes_ab_store",
            "natural_language_semantics_scored", "benchmark_performance_claim",
            "runtime_promotion_allowed",
        ):
            self.assertFalse(result["contract"][capability])

    def test_all_six_pairs_share_catalogs_but_change_reference_outcomes(self):
        self.assertEqual(len(self.fixture["cases"]), 2 * len(PAIRS))
        original = copy.deepcopy(self.candidate)
        for left, right in PAIRS:
            with self.subTest(pair=(left, right)):
                left_fixture = find_case(self.fixture, left)
                right_fixture = find_case(self.fixture, right)
                self.assertEqual(
                    left_fixture["evidence_catalog"], right_fixture["evidence_catalog"]
                )
                # Transplant the same output and evidence into the paired
                # context, changing only case identity. Every forward
                # transplant must fail; merely duplicating catalogs cannot pass.
                self.candidate = copy.deepcopy(original)
                transplanted = copy.deepcopy(find_case(self.candidate, left))
                transplanted["case_id"] = right
                target = find_case(self.candidate, right)
                target.clear()
                target.update(transplanted)
                self.failed_case(right)

    def test_forbidden_detail_remains_forbidden_when_uncertain(self):
        owner = find_case(self.candidate, "audience_owner_detail")
        detail = copy.deepcopy(find_claim(owner, "owner_detail"))
        detail["confidence"] = "uncertain"
        target = find_case(self.candidate, "audience_collaborator_summary")
        target["claims"].append(detail)
        row = self.failed_case(target["case_id"])
        self.assertEqual(row["forbidden_claim_ids"], ["owner_detail"])

    def test_unrelated_memory_cannot_be_smuggled_by_case_abstention(self):
        target = find_case(self.candidate, "task_unrelated")
        target["claims"] = copy.deepcopy(
            find_case(self.candidate, "task_relevant")["claims"]
        )
        # Keep abstained=True; carrying a non-abstained claim still fails.
        row = self.failed_case(target["case_id"])
        self.assertFalse(row["abstention_passed"])
        self.assertEqual(row["forbidden_claim_ids"], ["project_next_action"])

    def test_same_entity_claim_rejects_other_projects_current_evidence(self):
        for target_id, wrong_key in (
            ("entity_project_a", "syn_project_b_commitment"),
            ("entity_project_b", "syn_project_a_commitment"),
        ):
            with self.subTest(target=target_id):
                self.setUp()
                target = find_case(self.candidate, target_id)
                target["claims"][0]["evidence_keys"] = [wrong_key]
                row = self.failed_case(target_id)
                self.assertEqual(row["stale_evidence_ref_count"], 0)
                self.assertEqual(row["unknown_evidence_ref_count"], 0)
                self.assertEqual(
                    row["unsupported_evidence_claim_ids"],
                    ["current_project_commitment"],
                )

    def test_deadline_rejects_expired_superseded_and_future_evidence(self):
        for target_id, wrong_key in (
            ("deadline_after_update", "syn_deadline_v1"),
            ("deadline_after_update", "syn_deadline_draft"),
            ("deadline_before_update", "syn_deadline_v2"),
        ):
            with self.subTest(target=target_id, evidence=wrong_key):
                self.setUp()
                target = find_case(self.candidate, target_id)
                target["claims"][0]["evidence_keys"] = [wrong_key]
                row = self.failed_case(target_id)
                self.assertEqual(row["stale_evidence_ref_count"], 1)
                self.assertEqual(
                    row["unsupported_evidence_claim_ids"],
                    ["current_commitment_deadline"],
                )

    def test_missing_current_commitment_is_not_offset_by_valid_history(self):
        target = find_case(self.candidate, "revocation_retrospective")
        target["claims"] = [
            claim for claim in target["claims"]
            if claim["claim_id"] != "current_commitment"
        ]
        row = self.failed_case(target["case_id"])
        self.assertEqual(row["missing_required_claim_ids"], ["current_commitment"])
        self.assertEqual(row["evidence_precision"], 1.0)

    def test_valid_revocation_history_is_allowed_for_current_action(self):
        history = find_claim(
            find_case(self.candidate, "revocation_retrospective"),
            "revoked_plan_history",
        )
        find_case(self.candidate, "revocation_current_action")["claims"].append(
            copy.deepcopy(history)
        )
        self.assertEqual(self.score()["verdict"], "PASS")

    def test_revocation_history_requires_active_audit_not_stale_plan(self):
        target = find_case(self.candidate, "revocation_retrospective")
        find_claim(target, "revoked_plan_history")["evidence_keys"] = ["syn_plan_v1"]
        row = self.failed_case(target["case_id"])
        self.assertEqual(row["stale_evidence_ref_count"], 1)
        self.assertEqual(row["unsupported_evidence_claim_ids"], ["revoked_plan_history"])

    def test_stale_plan_revival_fails_even_with_valid_revocation_audit(self):
        for target_id in ("revocation_current_action", "revocation_retrospective"):
            with self.subTest(target=target_id):
                self.setUp()
                find_case(self.candidate, target_id)["claims"].append({
                    "claim_id": "revoked_plan_is_current",
                    "confidence": "supported",
                    "evidence_keys": ["syn_revocation_audit"],
                })
                row = self.failed_case(target_id)
                self.assertEqual(row["forbidden_claim_ids"], ["revoked_plan_is_current"])
                self.assertEqual(row["stale_evidence_ref_count"], 0)

    def test_unverified_inference_cannot_be_relabelled_as_verified_fact(self):
        target = find_case(self.candidate, "provenance_inference_only")
        target["claims"][0]["claim_id"] = "status_verified_fact"
        row = self.failed_case(target["case_id"])
        self.assertEqual(row["forbidden_claim_ids"], ["status_verified_fact"])
        self.assertEqual(row["missing_required_claim_ids"], ["status_tentative_inference"])

    def test_verified_fact_cannot_cite_agent_inference_instead_of_external_check(self):
        target = find_case(self.candidate, "provenance_externally_verified")
        target["claims"][0]["evidence_keys"] = ["syn_agent_inference"]
        row = self.failed_case(target["case_id"])
        self.assertEqual(row["unsupported_evidence_claim_ids"], ["status_verified_fact"])
        self.assertEqual(row["stale_evidence_ref_count"], 0)

    def test_verified_status_allows_prior_inference_history_without_promoting_it(self):
        target = find_case(self.candidate, "provenance_externally_verified")
        target["claims"].append({
            "claim_id": "prior_inference_history",
            "confidence": "supported",
            "evidence_keys": ["syn_agent_inference"],
        })
        self.assertEqual(self.score()["verdict"], "PASS")
        # Keeping correct historical attribution cannot replace external
        # evidence for the current verified status.
        find_claim(target, "status_verified_fact")["evidence_keys"] = ["syn_agent_inference"]
        row = self.failed_case(target["case_id"])
        self.assertEqual(row["unsupported_evidence_claim_ids"], ["status_verified_fact"])

    def test_over_suppression_of_authorized_summary_fails(self):
        target = find_case(self.candidate, "audience_collaborator_summary")
        target.update({"abstained": True, "claims": []})
        row = self.failed_case(target["case_id"])
        self.assertEqual(row["missing_required_claim_ids"], ["shared_commitment_summary"])

    def test_abstain_all_cannot_game_forbidden_claim_avoidance(self):
        for target in self.candidate["cases"]:
            target.update({"abstained": True, "claims": []})
        result = self.score()
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["aggregate"]["case_pass_count"], 1)
        self.assertEqual(result["aggregate"]["supported_claim_coverage"], 0.0)
        self.assertEqual(result["aggregate"]["forbidden_claim_count"], 0)

    def test_unknown_fields_rejected_at_candidate_and_fixture_levels(self):
        for path in (
            ("candidate",), ("candidate", "cases", 0),
            ("candidate", "cases", 0, "claims", 0),
            ("fixture",), ("fixture", "thresholds"), ("fixture", "cases", 0),
            ("fixture", "cases", 0, "evidence_catalog", 0),
            ("fixture", "cases", 0, "required_claims", 0),
        ):
            with self.subTest(path=path):
                self.setUp()
                node = self.candidate if path[0] == "candidate" else self.fixture
                for key in path[1:]:
                    node = node[key]
                node["inferred_permission"] = True
                with self.assertRaisesRegex(SCORER.InputError, "unsupported field"):
                    self.score()


if __name__ == "__main__":
    unittest.main()
