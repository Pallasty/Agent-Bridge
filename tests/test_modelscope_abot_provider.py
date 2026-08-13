import importlib.util
import json
import sys
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
            result = provider.session_contract()
        self.assertEqual(result["start_input_count"], 2)
        self.assertEqual(result["stop_input_count"], 3)
        self.assertTrue(result["hidden_state_required"])
        self.assertFalse(result["rest_lifecycle_supported"])
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


if __name__ == "__main__":
    unittest.main()
