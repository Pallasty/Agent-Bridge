import importlib.util
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


if __name__ == "__main__":
    unittest.main()
