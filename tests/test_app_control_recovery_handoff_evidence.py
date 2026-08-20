import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/design/evidence/app_control_recovery_handoff_live_2026_08_20.json"


class RecoveryHandoffEvidenceTests(unittest.TestCase):
    def test_live_handoff_preserves_one_dispatch_budget(self):
        value = json.loads(EVIDENCE.read_text())
        self.assertEqual(value["result"]["status"], "PASSED_BOUNDED_LIVE_MPRIS_HANDOFF")
        self.assertEqual(value["phase_1_dispatch_pending"]["dispatch_count"], 1)
        self.assertEqual(value["phase_3_new_process_recovery"]["dispatch_count"], 1)
        self.assertEqual(value["phase_4_terminal_replay"]["dispatch_count"], 1)
        self.assertFalse(value["phase_3_new_process_recovery"]["dispatch_field_present"])
        self.assertFalse(value["phase_4_terminal_replay"]["dispatch_field_present"])
        self.assertTrue(value["phase_4_terminal_replay"]["terminal_record_unchanged"])

    def test_discovery_binds_anchor_and_exact_request_without_auto_execution(self):
        value = json.loads(EVIDENCE.read_text())
        discovery = value["phase_2_readonly_discovery"]
        self.assertTrue(discovery["candidate_record_sha_matches_phase_1"])
        self.assertEqual(discovery["request_action"], "next")
        self.assertEqual(discovery["request_player"], "rhythmbox")
        self.assertEqual(discovery["request_ttl_secs"], 3600)
        self.assertFalse(discovery["automatic_execution_allowed"])
        self.assertTrue(discovery["revalidation_required"])

    def test_recovery_is_settled_but_causally_bounded(self):
        value = json.loads(EVIDENCE.read_text())
        recovery = value["phase_3_new_process_recovery"]
        self.assertTrue(recovery["recovered_after_interruption"])
        self.assertEqual(recovery["causal_attribution"], "unknown_after_restart")
        self.assertGreaterEqual(recovery["observed_consecutive"], 3)
        self.assertGreaterEqual(recovery["observed_stable_ms"], 500)
        self.assertTrue(recovery["current_track_matches_after_at_audit"])
        self.assertTrue(all(item is False for item in value["claim_boundary"].values()))


if __name__ == "__main__": unittest.main()
