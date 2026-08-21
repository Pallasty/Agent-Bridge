import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "docs/design/evidence/embodied_media_episode_bounded_retention_review_2026_08_20.json"


class EmbodiedMediaRetentionReviewTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(PATH.read_text())

    def test_retention_is_private_and_bounded(self):
        decision = self.value["decision"]
        self.assertEqual(decision["status"], "RETAIN_BOUNDED_PRIVATE_CAPABILITY")
        self.assertFalse(decision["public_surface_expanded"])
        self.assertFalse(decision["automatic_routing_enabled"])
        self.assertFalse(decision["background_recovery_enabled"])
        self.assertFalse(decision["cross_domain_expansion_enabled"])
        self.assertFalse(decision["new_runtime_authority_granted"])

    def test_live_handoff_adds_evidence_without_changing_scorecard_claims(self):
        summary = self.value["evidence_summary"]
        self.assertEqual(summary["paired_real_tasks"], 3)
        self.assertEqual(summary["paired_tasks_each_saved_agent_calls"], 5)
        self.assertTrue(summary["live_cross_process_handoff_verified"])
        self.assertTrue(summary["live_same_id_recovery_without_redispatch"])
        self.assertTrue(summary["live_terminal_replay_without_journal_change"])
        self.assertFalse(summary["behavior_lift_proven"])
        self.assertFalse(summary["exclusive_causation_proven"])
        self.assertFalse(summary["global_dispatch_count_proven"])

    def test_mac_candidate_remains_separate_design_only_scope(self):
        candidate = self.value["next_candidate"]
        self.assertEqual(candidate["status"], "DESIGN_ONLY")
        self.assertFalse(candidate["implementation_authorized"])
        self.assertFalse(candidate["live_execution_authorized"])
        self.assertTrue(candidate["required_new_preregistration"])
        self.assertFalse(candidate["media_denominator_reuse_allowed"])


if __name__ == "__main__":
    unittest.main()
