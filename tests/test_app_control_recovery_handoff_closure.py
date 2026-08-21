import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "docs/design/evidence/app_control_recovery_handoff_live_closure_2026_08_20.json"


class RecoveryHandoffClosureTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(PATH.read_text())

    def test_terminal_operation_has_no_pending_recovery_candidate(self):
        closure = self.value["closure"]
        self.assertTrue(closure["journal_scan_complete"])
        self.assertEqual(closure["admission"], "no_recovery_candidate")
        self.assertEqual(closure["recover"], "replan")
        self.assertEqual(closure["candidate_count"], 0)
        self.assertEqual(closure["blocked_count"], 0)
        self.assertEqual(closure["target_operation_phase"], "terminal")
        self.assertEqual(closure["target_operation_dispatch_count"], 1)
        self.assertTrue(closure["target_operation_payload_present"])

    def test_closure_audit_has_no_side_effect_authority(self):
        decision = self.value["decision"]
        closure = self.value["closure"]
        self.assertEqual(decision["status"], "LIVE_HANDOFF_CLOSED_NO_PENDING_RECOVERY")
        self.assertTrue(closure["journal_manifest_unchanged_during_audit"])
        self.assertFalse(closure["media_observed_by_index"])
        self.assertFalse(closure["action_invoked_by_index"])
        self.assertFalse(decision["automatic_recovery_authorized"])
        self.assertFalse(decision["additional_next_authorized"])


if __name__ == "__main__":
    unittest.main()
