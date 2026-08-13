import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "modelscope_abot_provider.py"
SPEC = importlib.util.spec_from_file_location("modelscope_abot_provider", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ModelScopeAbotProviderTests(unittest.TestCase):
    def test_sse_parser_preserves_complete_payload(self):
        events = MODULE.parse_sse('event: complete\ndata: ["ready", {"active": false}]\n')
        self.assertEqual(events[0].event, "complete")
        self.assertEqual(events[0].data[0], "ready")

    def test_readiness_requires_contract_and_ready_text(self):
        provider = MODULE.ModelScopeAbotProvider()
        with patch.object(provider, "endpoint_names", return_value=set(MODULE.REQUIRED_ENDPOINTS)), patch.object(
            provider,
            "_call",
            return_value=[MODULE.GradioEvent("complete", ["**就绪**", {}, {}, {}])],
        ):
            result = provider.readiness()
        self.assertTrue(result["ready"])
        self.assertFalse(result["runtime_admitted"])

    def test_session_contract_fails_closed_for_hidden_state(self):
        provider = MODULE.ModelScopeAbotProvider()
        config = {
            "dependencies": [
                {"api_name": "on_click_start_ws", "inputs": [14, 2], "outputs": list(range(8))},
                {"api_name": "on_stop_ws", "inputs": [1, 2, 14], "outputs": list(range(8))},
            ]
        }
        with patch.object(provider, "app_config", return_value=config):
            with patch.object(provider, "endpoint_names", return_value=set(MODULE.REQUIRED_ENDPOINTS)):
                result = provider.session_contract()
        self.assertEqual(result["start_input_count"], 2)
        self.assertEqual(result["stop_input_count"], 3)
        self.assertTrue(result["hidden_state_required"])
        self.assertFalse(result["rest_lifecycle_supported"])
        self.assertEqual(result["admission_blockers"], ["hidden_state_required"])
        self.assertFalse(result["runtime_admitted"])

    def test_session_contract_fails_closed_when_endpoint_or_dependency_is_missing(self):
        provider = MODULE.ModelScopeAbotProvider()
        with patch.object(provider, "endpoint_names", return_value={"/check_model_ready_ui"}), patch.object(
            provider, "app_config", return_value={"dependencies": []}
        ):
            result = provider.session_contract()
        self.assertFalse(result["rest_lifecycle_supported"])
        self.assertEqual(
            result["admission_blockers"],
            [
                "required_endpoint_not_advertised",
                "start_dependency_missing",
                "stop_dependency_missing",
            ],
        )
        self.assertFalse(result["runtime_admitted"])

    def test_browser_receipt_closes_lifecycle_without_rollout_admission(self):
        receipt = {
            "schema": MODULE.BROWSER_RECEIPT_SCHEMA,
            "provider_id": MODULE.PROVIDER_ID,
            "observations": {
                "start_observed": True,
                "stream_observed": True,
                "max_observed_fps": 11.8,
                "stop_requested": True,
                "stop_observed": True,
                "post_stop_ready": True,
                "post_stop_iframe_count": 0,
            },
            "generated_artifact": None,
            "rollout_emitted": False,
            "runtime_admitted": False,
        }
        result = MODULE.validate_browser_receipt(receipt)
        self.assertTrue(result["valid"])
        self.assertTrue(result["lifecycle_closed"])
        self.assertFalse(result["generated_artifact_bound"])
        self.assertFalse(result["rollout_eligible"])
        self.assertFalse(result["runtime_admitted"])

    def test_browser_receipt_rejects_missing_stop_and_false_admission(self):
        receipt = {
            "schema": MODULE.BROWSER_RECEIPT_SCHEMA,
            "provider_id": MODULE.PROVIDER_ID,
            "observations": {
                "start_observed": True,
                "stream_observed": True,
                "max_observed_fps": 2.0,
                "stop_requested": False,
                "stop_observed": False,
                "post_stop_ready": False,
                "post_stop_iframe_count": 1,
            },
            "generated_artifact": None,
            "rollout_emitted": True,
            "runtime_admitted": True,
        }
        result = MODULE.validate_browser_receipt(receipt)
        self.assertFalse(result["valid"])
        self.assertIn("stop_observed_not_true", result["violations"])
        self.assertIn("runtime_admitted_must_be_false", result["violations"])

    def test_committed_gate7b_receipt_validates(self):
        path = (
            Path(__file__).parents[1]
            / "docs"
            / "design"
            / "evidence"
            / "modelscope_abot_gate7b_browser_receipt_2026_08_12.json"
        )
        result = MODULE.validate_browser_receipt(json.loads(path.read_text(encoding="utf-8")))
        self.assertTrue(result["valid"])

    def test_committed_gate7c_artifact_and_rollout_validate(self):
        path = (
            Path(__file__).parents[1]
            / "docs"
            / "design"
            / "evidence"
            / "modelscope_abot_gate7c_artifact_receipt_2026_08_12.json"
        )
        result = MODULE.validate_artifact_receipt(
            json.loads(path.read_text(encoding="utf-8")), path
        )
        self.assertTrue(result["valid"])
        self.assertTrue(result["artifact_bound"])
        self.assertTrue(result["rollout_contract_satisfied"])
        self.assertTrue(result["rollout_eligible"])
        self.assertFalse(result["runtime_admitted"])

    def test_artifact_validator_rejects_tampering_and_truth_promotion(self):
        source_root = Path(__file__).parents[1] / "docs" / "design" / "evidence"
        source_receipt = source_root / "modelscope_abot_gate7c_artifact_receipt_2026_08_12.json"
        receipt = json.loads(source_receipt.read_text(encoding="utf-8"))
        receipt["rollout"]["truth_boundary"]["verified_to"] = "real_world"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / source_receipt.name
            path.write_text(json.dumps(receipt), encoding="utf-8")
            artifact = source_root / receipt["artifact"]["ref"]
            (root / artifact.name).write_bytes(artifact.read_bytes() + b"tampered")
            result = MODULE.validate_artifact_receipt(receipt, path)
        self.assertFalse(result["valid"])
        self.assertIn("artifact_sha256_mismatch", result["violations"])
        self.assertIn("rollout_truth_boundary_exceeded", result["violations"])

    def test_artifact_validator_rejects_dimension_and_prompt_binding_drift(self):
        source_root = Path(__file__).parents[1] / "docs" / "design" / "evidence"
        source_receipt = source_root / "modelscope_abot_gate7c_artifact_receipt_2026_08_12.json"
        receipt = json.loads(source_receipt.read_text(encoding="utf-8"))
        receipt["artifact"]["width"] = 1
        receipt["rollout"]["generation_parameters"]["prompt_sha256"] = "different"
        result = MODULE.validate_artifact_receipt(receipt, source_receipt)
        self.assertFalse(result["valid"])
        self.assertIn("artifact_dimensions_mismatch", result["violations"])
        self.assertIn("rollout_prompt_binding_mismatch", result["violations"])

    def test_artifact_validator_fails_closed_on_malformed_nested_fields(self):
        source_root = Path(__file__).parents[1] / "docs" / "design" / "evidence"
        source_receipt = source_root / "modelscope_abot_gate7c_artifact_receipt_2026_08_12.json"
        receipt = json.loads(source_receipt.read_text(encoding="utf-8"))
        receipt["request"]["constraints"] = "malformed"
        receipt["rollout"]["generation_parameters"] = ["malformed"]
        result = MODULE.validate_artifact_receipt(receipt, source_receipt)
        self.assertFalse(result["valid"])
        self.assertIn("request_constraints_not_object", result["violations"])
        self.assertIn("rollout_generation_parameters_not_object", result["violations"])

    def test_committed_gate7d_admission_packet_validates_without_admission(self):
        path = (
            Path(__file__).parents[1]
            / "docs"
            / "design"
            / "evidence"
            / "modelscope_abot_gate7d_runtime_admission_2026_08_12.json"
        )
        result = MODULE.validate_admission_packet(
            json.loads(path.read_text(encoding="utf-8")), path
        )
        self.assertTrue(result["valid"])
        self.assertTrue(result["admission_contract_ready"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["runtime_admitted"])
        self.assertFalse(result["mcp_registered"])

    def test_admission_packet_rejects_implicit_authority_and_runtime_promotion(self):
        packet, path = self._gate7d_packet()
        packet["authority_policy"]["owner_confirmation_required"] = False
        packet["decision"]["runtime_admitted"] = True
        packet["exposure"]["mcp_registered"] = True
        result = MODULE.validate_admission_packet(packet, path)
        self.assertFalse(result["valid"])
        self.assertIn("authority_owner_confirmation_required_mismatch", result["violations"])
        self.assertIn("decision_runtime_admitted_must_be_false", result["violations"])
        self.assertIn("exposure_mcp_registered_mismatch", result["violations"])

    def test_admission_packet_rejects_unbounded_or_retained_session(self):
        packet, path = self._gate7d_packet()
        packet["concurrency"]["max_active"] = 2
        packet["cancellation"]["hard_deadline_seconds"] = 0
        packet["retention"]["transport_frames"] = "persistent"
        result = MODULE.validate_admission_packet(packet, path)
        self.assertFalse(result["valid"])
        self.assertIn("concurrency_max_active_must_be_one", result["violations"])
        self.assertIn("cancellation_hard_deadline_seconds_invalid", result["violations"])
        self.assertIn("retention_transport_frames_mismatch", result["violations"])

    def _gate7d_packet(self):
        path = (
            Path(__file__).parents[1]
            / "docs"
            / "design"
            / "evidence"
            / "modelscope_abot_gate7d_runtime_admission_2026_08_12.json"
        )
        return json.loads(path.read_text(encoding="utf-8")), path

    def test_admission_packet_rejects_lineage_tampering_and_automatic_retry(self):
        packet, path = self._gate7d_packet()
        packet["evidence_lineage"]["artifact_receipt_sha256"] = "0" * 64
        packet["failure_recovery"]["automatic_retry"] = True
        packet["output_policy"]["canonical_memory_write"] = True
        result = MODULE.validate_admission_packet(packet, path)
        self.assertFalse(result["valid"])
        self.assertIn("artifact_receipt_sha256_mismatch", result["violations"])
        self.assertIn("failure_recovery_automatic_retry_mismatch", result["violations"])
        self.assertIn("output_canonical_memory_write_must_be_false", result["violations"])


if __name__ == "__main__":
    unittest.main()
