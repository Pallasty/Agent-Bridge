import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "docs/design/evidence/macos_ax_focus_continuity_design_preregistration_2026_08_20.json"
)
IMPLEMENTATION = (
    ROOT
    / "docs/design/evidence/macos_ax_focus_continuity_offline_implementation_2026_08_20.json"
)
ELIGIBILITY = (
    ROOT
    / "docs/design/evidence/macos_ax_focus_continuity_readonly_eligibility_2026_08_20.json"
)
NATIVE_ELIGIBILITY = (
    ROOT
    / "docs/design/evidence/macos_ax_focus_continuity_native_readonly_eligibility_2026_08_20.json"
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


class MacosAxFocusContinuityImplementationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))

    def test_offline_authority_does_not_expand_runtime_or_live_scope(self):
        self.assertEqual(
            self.value["schema"],
            "agent_bridge.macos_ax_focus_continuity_offline_implementation.v0",
        )
        self.assertEqual(
            self.value["design_commit"],
            "55d0c8a2777a654c5fb72b7a01e210b649972382",
        )
        authority = self.value["authority"]
        self.assertTrue(authority["offline_implementation_authorized"])
        self.assertFalse(authority["live_mac_action_authorized"])
        self.assertFalse(authority["deployment_authorized"])
        self.assertFalse(authority["public_tool_expansion_authorized"])
        self.assertFalse(self.value["implementation"]["public_mcp_tool_added"])
        self.assertFalse(self.value["implementation"]["runtime_asset_added"])

    def test_journal_and_state_machine_pin_at_most_once_recovery(self):
        journal = self.value["journal_contract"]
        self.assertEqual(journal["maximum_dispatch_count"], 1)
        self.assertTrue(journal["nonblocking_exclusive_flock"])
        self.assertTrue(journal["atomic_replace_and_fsync"])
        self.assertTrue(journal["terminal_receipt_validated_before_replay"])
        state = self.value["state_machine"]
        self.assertEqual(state["phases"], ["prepared", "dispatch_started", "terminal"])
        self.assertTrue(state["dispatch_started_recovery_read_only"])
        self.assertFalse(state["dispatch_started_may_redispatch"])
        self.assertFalse(state["terminal_replay_calls_tools"])

    def test_offline_evidence_makes_no_live_or_general_claim(self):
        self.assertEqual(self.value["offline_tests"]["runner_and_design_tests_passed"], 23)
        for value in self.value["claim_boundary"].values():
            self.assertIs(value, False)


class MacosAxFocusContinuityEligibilityEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(ELIGIBILITY.read_text(encoding="utf-8"))

    def test_negative_gate_is_read_only_and_does_not_expand_authority(self):
        self.assertEqual(
            self.value["schema"],
            "agent_bridge.macos_ax_focus_continuity_readonly_eligibility.v0",
        )
        authority = self.value["authority"]
        self.assertTrue(authority["readonly_eligibility_authorized"])
        for key in (
            "live_focus_authorized",
            "application_activation_authorized",
            "window_creation_authorized",
            "permission_prompt_authorized",
        ):
            self.assertFalse(authority[key])
        self.assertFalse(self.value["source"]["remote_probe_file_written"])
        self.assertFalse(self.value["source"]["raw_receipt_retained"])
        self.assertFalse(self.value["source"]["titles_retained"])

    def test_incomplete_system_events_surface_blocks_before_action(self):
        observation = self.value["observation"]
        self.assertTrue(observation["ax_trusted"])
        self.assertFalse(observation["permission_prompted"])
        self.assertEqual(observation["probe_status"], "degraded")
        self.assertFalse(observation["coverage_complete"])
        self.assertEqual(observation["error_stages"], ["system_events"])
        self.assertFalse(observation["system_events_running"])
        self.assertFalse(observation["action_performed"])
        decision = self.value["decision"]
        self.assertEqual(decision["status"], "INELIGIBLE_NO_LIVE_ACTION")
        self.assertFalse(decision["may_manufacture_eligibility"])
        self.assertFalse(decision["may_run_focus_transaction"])
        self.assertFalse(decision["may_acquire_write_lease"])

    def test_negative_gate_makes_no_effect_or_recovery_claim(self):
        for value in self.value["claim_boundary"].values():
            self.assertIs(value, False)


class MacosAxFocusContinuityNativeEligibilityEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(NATIVE_ELIGIBILITY.read_text(encoding="utf-8"))

    def test_native_probe_removes_automation_without_authorizing_action(self):
        source = self.value["source"]
        self.assertFalse(source["uses_system_events"])
        self.assertFalse(source["uses_apple_events"])
        self.assertFalse(source["uses_ax_setters"])
        self.assertFalse(source["remote_source_file_written"])
        self.assertFalse(source["raw_receipt_retained"])
        self.assertFalse(source["titles_retained"])
        authority = self.value["authority"]
        self.assertTrue(authority["native_readonly_probe_authorized"])
        self.assertFalse(authority["live_focus_authorized"])
        self.assertFalse(authority["identity_fallback_authorized"])

    def test_complete_two_window_surface_without_identifiers_is_ineligible(self):
        observed = self.value["observation"]
        self.assertTrue(observed["counts_consistent"])
        self.assertFalse(observed["truncated"])
        self.assertEqual(observed["returned_window_count"], 2)
        self.assertEqual(observed["source_window_count"], 2)
        self.assertEqual(
            observed["readable_attribute_counts"],
            {"ax_identifier": 0, "title": 2, "role": 2, "focused": 2},
        )
        self.assertEqual(observed["stable_window_count"], 0)
        decision = self.value["decision"]
        self.assertEqual(decision["status"], "INELIGIBLE_NO_STABLE_WINDOW_IDENTITY")
        for key in (
            "may_use_sample_index",
            "may_use_title_as_identity",
            "may_use_coordinate_or_visual_fallback",
            "may_switch_to_another_application",
            "may_run_focus_transaction",
        ):
            self.assertFalse(decision[key])

    def test_native_gate_makes_no_effect_or_rollout_claim(self):
        for value in self.value["claim_boundary"].values():
            self.assertIs(value, False)


if __name__ == "__main__":
    unittest.main()
