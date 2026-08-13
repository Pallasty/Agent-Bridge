import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("adapter", ROOT / "scripts" / "modelscope_abot_external_adapter.py")
adapter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = adapter
spec.loader.exec_module(adapter)


class ExternalAdapterTests(unittest.TestCase):
    def setUp(self):
        self.contract = {"provider_id": adapter.PROVIDER_ID, "capability_id": "gate7j-capability-0001", "operation": {"action": adapter.ACTION, "endpoint": adapter.ENDPOINT}}
        self.receipt = {"schema": "agent_bridge.modelscope_abot_activation_consumption.v0", "activation_id": "gate7j-activation-0001", "capability_id": self.contract["capability_id"], "activation_consumed": True, "execution_capability_issued": False, "studio_start_called": False, "execution_authorized": False, "runtime_admitted": False, "mcp_registered": False}

    def test_plan_is_non_actuating_and_network_closed(self):
        plan = adapter.prepare_adapter_plan(activation_receipt=self.receipt, capability_contract=self.contract)
        self.assertTrue(plan["plan_only"])
        self.assertFalse(plan["adapter"]["network_allowed"])
        self.assertFalse(plan["adapter"]["subprocess_allowed"])
        self.assertFalse(plan["runtime_admitted"])

    def test_open_boundary_and_bad_binding_fail_closed(self):
        for field in ("execution_authorized", "runtime_admitted"):
            receipt = dict(self.receipt); receipt[field] = True
            with self.assertRaisesRegex(adapter.ExternalAdapterError, "boundary"):
                adapter.prepare_adapter_plan(activation_receipt=receipt, capability_contract=self.contract)
        with self.assertRaisesRegex(adapter.ExternalAdapterError, "binding"):
            adapter.prepare_adapter_plan(activation_receipt=self.receipt, capability_contract={**self.contract, "capability_id": "other-capability-0001"})

    def test_timeout_and_operation_are_bounded(self):
        with self.assertRaisesRegex(adapter.ExternalAdapterError, "timeout"):
            adapter.prepare_adapter_plan(activation_receipt=self.receipt, capability_contract=self.contract, requested_timeout_ms=30_001)
        bad = {**self.contract, "operation": {"action": "stop", "endpoint": adapter.ENDPOINT}}
        with self.assertRaisesRegex(adapter.ExternalAdapterError, "operation"):
            adapter.prepare_adapter_plan(activation_receipt=self.receipt, capability_contract=bad)


if __name__ == "__main__":
    unittest.main()
