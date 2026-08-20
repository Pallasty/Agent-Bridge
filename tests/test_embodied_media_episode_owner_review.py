import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/design/evidence/embodied_media_episode_dogfood_owner_review_2026_08_20.json"


class OwnerReviewTests(unittest.TestCase):
    def setUp(self):
        self.raw = REVIEW.read_text(encoding="utf-8")
        self.value = json.loads(self.raw)

    def test_review_is_closed_and_bound_to_ready_aggregate(self):
        aggregate = self.value["aggregate"]
        self.assertEqual(self.value["schema"], "agent_bridge.embodied_media_episode_owner_review.v0")
        self.assertEqual(aggregate["scorecard_commit"], "d3da14a82fb9861c39247eef22de041cd73596eb")
        self.assertEqual(aggregate["scorecard_decision"], "READY_FOR_OWNER_REVIEW")
        self.assertEqual(aggregate["useful_paired_real_tasks"], 3)
        self.assertEqual(aggregate["agent_orchestration_calls_saved_per_pair"], [5, 5, 5])
        self.assertFalse(aggregate["behavior_lift_proven"])
        self.assertFalse(aggregate["runtime_influence_allowed"])

    def test_decision_is_bounded_adoption_not_rollout(self):
        decision = self.value["decision"]
        self.assertEqual(decision["status"], "CONDITIONAL_ADOPT_BOUNDED_MEDIA_EPISODE")
        self.assertFalse(decision["automatic_rollout"])
        self.assertFalse(decision["automatic_cross_domain_expansion"])
        self.assertFalse(decision["new_runtime_authority_granted"])
        self.assertTrue(decision["requires_explicit_owner_approval_for_next_scope"])

    def test_next_scope_is_design_only(self):
        scope = self.value["next_scope"]
        self.assertEqual(scope["status"], "DESIGN_ONLY_PENDING_OWNER_APPROVAL")
        self.assertEqual(scope["candidate"], "mac_window_focus_then_ax_verify")
        self.assertFalse(scope["implementation_authorized"])
        self.assertFalse(scope["live_execution_authorized"])

    def test_claim_boundary_rejects_generalization(self):
        boundary = self.value["claim_boundary"]
        self.assertFalse(boundary["this_is_a_product_decision"])
        self.assertFalse(boundary["this_is_behavior_lift"])
        self.assertFalse(boundary["this_is_general_workflow_authority"])
        self.assertFalse(boundary["this_authorizes_cross_domain_runtime_influence"])
        self.assertNotIn("p5-baseline-", self.raw)
        self.assertNotIn("3K661F0178H00000", self.raw)


if __name__ == "__main__":
    unittest.main()
