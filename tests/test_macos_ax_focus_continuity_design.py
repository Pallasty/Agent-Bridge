import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "docs/design/evidence/macos_ax_focus_continuity_design_preregistration_2026_08_20.json"
)


class MacosAxFocusContinuityDesignTests(unittest.TestCase):
    def setUp(self):
        self.raw = PREREGISTRATION.read_text(encoding="utf-8")
        self.value = json.loads(self.raw)

    def test_preregistration_is_closed_and_precedes_implementation(self):
        self.assertEqual(
            set(self.value),
            {
                "schema",
                "registered_at",
                "registered_before_implementation",
                "owner_authorized_candidate",
                "authority",
                "existing_primitives",
                "offline_baseline",
                "scope",
                "episode_contract",
                "live_admission",
                "paired_measurement",
                "required_before_implementation",
                "claim_boundary",
            },
        )
        self.assertEqual(
            self.value["schema"],
            "agent_bridge.macos_ax_focus_continuity_design_preregistration.v0",
        )
        self.assertTrue(self.value["registered_before_implementation"])
        self.assertTrue(self.value["owner_authorized_candidate"])

    def test_authority_is_design_only(self):
        self.assertEqual(
            self.value["authority"],
            {
                "design_authorized": True,
                "implementation_authorized_after_design_gate": False,
                "live_execution_authorized": False,
                "new_runtime_influence_authorized": False,
            },
        )
        self.assertFalse(self.value["offline_baseline"]["live_mac_action_performed"])

    def test_existing_transaction_is_not_misrepresented_as_restart_continuity(self):
        primitives = self.value["existing_primitives"]
        self.assertEqual(primitives["transaction"], "macos_ax_focus_transaction")
        self.assertEqual(primitives["postcondition"], "macos_ax_verify")
        self.assertFalse(primitives["transaction_resumes_action"])
        self.assertFalse(primitives["caller_supplied_operation_id_already_supported"])
        self.assertEqual(
            self.value["offline_baseline"],
            {
                "implementation_commit": "4435369cda1fec5763ba2b5be908d3d0311a7a4a",
                "rust_focus_tests_passed": 9,
                "python_ax_tests_passed": 64,
                "live_mac_action_performed": False,
            },
        )

    def test_scope_is_exact_frontmost_window_navigation(self):
        scope = self.value["scope"]
        self.assertEqual(scope["operation"], "focus_window")
        self.assertEqual(scope["risk_rank"], 1)
        self.assertTrue(scope["already_frontmost_app_required"])
        self.assertTrue(scope["stable_ax_identifier_required"])
        for field in (
            "sample_local_index_allowed",
            "cross_app_activation_allowed",
            "content_mutation_allowed",
            "coordinate_or_visual_fallback_allowed",
        ):
            self.assertFalse(scope[field])

    def test_recovery_can_observe_but_never_redispatch(self):
        contract = self.value["episode_contract"]
        self.assertTrue(contract["caller_supplied_operation_id_required"])
        self.assertTrue(contract["canonical_request_binding_required"])
        self.assertEqual(contract["write_ahead_phase"], "dispatch_started")
        self.assertTrue(contract["same_id_recovery_is_read_only"])
        self.assertFalse(contract["redispatch_after_dispatch_started_allowed"])
        self.assertEqual(contract["recovery_postcondition"], "window_focused")
        self.assertEqual(
            contract["recovery_causal_attribution"],
            "unknown_after_interruption",
        )
        self.assertFalse(contract["automatic_new_operation_id_allowed"])

    def test_live_admission_cannot_be_manufactured(self):
        admission = self.value["live_admission"]
        self.assertTrue(admission["complete_untruncated_probe_required"])
        self.assertEqual(admission["maximum_probe_age_ms"], 5000)
        self.assertTrue(admission["two_distinct_stable_windows_required"])
        self.assertTrue(admission["target_initially_unfocused_required"])
        self.assertFalse(admission["hidden_or_unknown_candidates_allowed"])
        self.assertFalse(admission["permission_prompt_allowed"])
        self.assertTrue(admission["owner_only_journal_required"])
        self.assertFalse(admission["ineligible_surface_may_be_manufactured"])

    def test_pair_compares_five_calls_with_two_invocations(self):
        measurement = self.value["paired_measurement"]
        self.assertEqual(measurement["baseline_agent_visible_calls"], 5)
        self.assertEqual(measurement["trial_agent_visible_calls"], 2)
        self.assertEqual(len(measurement["baseline_steps"]), 5)
        self.assertEqual(len(measurement["trial_steps"]), 2)
        self.assertEqual(measurement["target_useful_pairs"], 3)
        self.assertTrue(measurement["elapsed_ms_descriptive_only"])

    def test_claim_boundary_rejects_scope_and_evidence_inflation(self):
        for value in self.value["claim_boundary"].values():
            self.assertIs(value, False)
        self.assertNotIn("window_title", self.raw)
        self.assertNotIn("AXIdentifier=", self.raw)
        self.assertNotIn("bundle_id=com.", self.raw)


if __name__ == "__main__":
    unittest.main()
