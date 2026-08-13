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
        self.contract = {"schema": adapter.CONTRACT_SCHEMA, "provider_id": adapter.PROVIDER_ID, "capability_id": "gate7j-capability-0001", "claim": {}, "operation": {"action": adapter.ACTION, "endpoint": adapter.ENDPOINT, "prompt_sha256": "12" * 32}}
        self.receipt = {"schema": adapter.CONSUMPTION_SCHEMA, "provider_id": adapter.PROVIDER_ID, "activation_id": "gate7j-activation-0001", "capability_id": self.contract["capability_id"], "capability_sha256": adapter._digest(self.contract), "activation_consumed": True, "capability_validated": True, "activation_reference_validated": True, "execution_capability_issued": False, "studio_start_called": False, "execution_authorized": False, "runtime_admitted": False, "mcp_registered": False}

    def test_plan_is_non_actuating_and_network_closed(self):
        plan = adapter.prepare_adapter_plan(activation_receipt=self.receipt, capability_contract=self.contract)
        self.assertTrue(plan["plan_only"])
        self.assertFalse(plan["adapter"]["network_allowed"])
        self.assertFalse(plan["adapter"]["subprocess_allowed"])
        self.assertFalse(plan["runtime_admitted"])
        self.assertTrue(plan["capability_digest_bound"])

    def test_open_boundary_and_bad_binding_fail_closed(self):
        for field in ("execution_authorized", "runtime_admitted"):
            receipt = dict(self.receipt); receipt[field] = True
            with self.assertRaisesRegex(adapter.ExternalAdapterError, "boundary"):
                adapter.prepare_adapter_plan(activation_receipt=receipt, capability_contract=self.contract)
        with self.assertRaisesRegex(adapter.ExternalAdapterError, "binding"):
            adapter.prepare_adapter_plan(activation_receipt=self.receipt, capability_contract={**self.contract, "capability_id": "other-capability-0001"})
        with self.assertRaisesRegex(adapter.ExternalAdapterError, "digest"):
            adapter.prepare_adapter_plan(activation_receipt={**self.receipt, "capability_sha256": "ff" * 32}, capability_contract=self.contract)

    def test_timeout_and_operation_are_bounded(self):
        with self.assertRaisesRegex(adapter.ExternalAdapterError, "timeout"):
            adapter.prepare_adapter_plan(activation_receipt=self.receipt, capability_contract=self.contract, requested_timeout_ms=30_001)
        bad = {**self.contract, "operation": {"action": "stop", "endpoint": adapter.ENDPOINT, "prompt_sha256": "12" * 32}}
        with self.assertRaisesRegex(adapter.ExternalAdapterError, "operation"):
            adapter.prepare_adapter_plan(
                activation_receipt={**self.receipt, "capability_sha256": adapter._digest(bad)},
                capability_contract=bad,
            )
        malformed_prompt = {**self.contract, "operation": {**self.contract["operation"], "prompt_sha256": "not-a-digest"}}
        with self.assertRaisesRegex(adapter.ExternalAdapterError, "operation"):
            adapter.prepare_adapter_plan(
                activation_receipt={**self.receipt, "capability_sha256": adapter._digest(malformed_prompt)},
                capability_contract=malformed_prompt,
            )

    def test_missing_validation_markers_fail_closed(self):
        for field in ("capability_validated", "activation_reference_validated"):
            receipt = dict(self.receipt)
            receipt.pop(field)
            with self.assertRaisesRegex(adapter.ExternalAdapterError, "validation"):
                adapter.prepare_adapter_plan(activation_receipt=receipt, capability_contract=self.contract)

    def test_committed_evidence_remains_non_actuating(self):
        import json
        evidence = json.loads((ROOT / "docs" / "design" / "evidence" / "modelscope_abot_gate7j_external_adapter_2026_08_13.json").read_text())
        self.assertEqual(evidence["evidence_class"], "synthetic_contract_test")
        self.assertTrue(all(evidence["tests"].values()))
        self.assertTrue(evidence["plan_only"])
        self.assertFalse(evidence["network_allowed"])
        self.assertFalse(evidence["subprocess_allowed"])
        self.assertFalse(evidence["studio_start_called"])
        self.assertFalse(evidence["runtime_admitted"])
        self.assertFalse(evidence["mcp_registered"])


if __name__ == "__main__":
    unittest.main()
