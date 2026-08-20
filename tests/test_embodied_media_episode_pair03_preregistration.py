import importlib.util
import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "docs/design/evidence/embodied_media_episode_dogfood_pair_03_preregistration_2026_08_20.json"
)
SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load("embodied_media_pair03_runner", "scripts/embodied-media-episode-dogfood-runner.py")
collector = runner.collector


class Pair03PreregistrationTests(unittest.TestCase):
    def setUp(self):
        self.raw = PREREGISTRATION.read_text(encoding="utf-8")
        self.value = json.loads(self.raw)

    def test_registration_is_closed_and_bound_to_versioned_runner(self):
        self.assertEqual(
            set(self.value),
            {
                "schema", "pair_id", "registered_at", "registered_before_actuation",
                "task_kind", "real_task_operator_attested", "intent",
                "private_bindings", "admission", "baseline", "trial",
                "success_contract", "measurement", "stop_conditions",
                "claim_boundary",
            },
        )
        self.assertEqual(self.value["pair_id"], "embodied-media-pair-03")
        self.assertTrue(self.value["registered_before_actuation"])
        self.assertEqual(self.value["admission"]["required_runner_schema"], runner.RUNNER_SCHEMA)
        self.assertEqual(
            self.value["admission"]["required_collector_schema"],
            collector.RESULT_SCHEMA,
        )
        self.assertEqual(
            self.value["admission"]["required_master_commit"],
            "3f677c9bd0447c9526d262e285752e7e62a9f609",
        )

    def test_sequence_and_measurement_were_fixed_before_action(self):
        self.assertEqual(
            self.value["baseline"]["steps"],
            [
                "app_control_pending", "app_control_same_id_recovery",
                "mobile_projection_start", "mobile_projection_wait_connection",
                "mobile_projection_sync_exact_player",
                "mobile_projection_wait_exact_draw", "mobile_projection_stop",
            ],
        )
        self.assertEqual(
            self.value["trial"]["steps"],
            ["app_control_pending", "advance_track_then_project_same_id_recovery"],
        )
        self.assertEqual(
            list(collector.BASELINE_TOOLS),
            [
                "app_control", "app_control", "mobile_projection_start",
                "mobile_projection_wait", "mobile_projection_sync_media",
                "mobile_projection_wait", "mobile_projection_stop",
            ],
        )
        self.assertEqual(
            list(collector.TRIAL_TOOLS),
            ["app_control", "advance_track_then_project"],
        )
        self.assertEqual(self.value["baseline"]["expected_agent_orchestration_calls"], 7)
        self.assertEqual(self.value["trial"]["expected_agent_orchestration_calls"], 2)
        self.assertTrue(self.value["measurement"]["enrollment_requires_both_normalized_runner_results"])
        self.assertTrue(self.value["success_contract"]["collector_is_sole_success_authority"])

    def test_public_evidence_contains_hashes_but_no_private_identifiers(self):
        bindings = self.value["private_bindings"]
        for key in (
            "baseline_operation_id_sha256", "trial_operation_id_sha256",
            "adb_serial_sha256", "bind_address_sha256",
        ):
            self.assertRegex(bindings[key], SHA256)
        self.assertNotIn("p3-baseline-", self.raw)
        self.assertNotIn("p3-trial-", self.raw)
        self.assertNotIn("3K661F0178H00000", self.raw)
        self.assertNotIn("192.168.1.16", self.raw)
        self.assertFalse(bindings["raw_values_persisted_in_git"])

    def test_claim_boundary_does_not_overstate_the_pair(self):
        claims = self.value["claim_boundary"]
        self.assertFalse(claims["pair_proves_behavior_lift"])
        self.assertFalse(claims["pair_proves_global_dispatch_count"])
        self.assertFalse(claims["pair_proves_exclusive_causation"])
        self.assertFalse(claims["long_lived_stability_proven"])
        self.assertFalse(claims["human_observation_proven"])
        self.assertFalse(claims["pixel_verification_proven"])
        self.assertFalse(
            claims["pair_authorizes_runtime_influence_beyond_two_preregistered_next_operations"]
        )


if __name__ == "__main__":
    unittest.main()
