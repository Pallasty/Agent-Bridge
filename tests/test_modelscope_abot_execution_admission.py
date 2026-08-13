import importlib.util
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("admission", ROOT / "scripts" / "modelscope_abot_execution_admission.py")
admission = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = admission
spec.loader.exec_module(admission)
class ExecutionAdmissionTests(unittest.TestCase):
    def setUp(self): self.plan = {"schema": admission.PLAN_SCHEMA, "provider_id": admission.PROVIDER_ID, "plan_only": True, "network_allowed": False, "subprocess_allowed": False}
    def test_explicit_admission_still_does_not_execute(self):
        result = admission.admit_execution(adapter_plan=self.plan, owner_confirmation=True, runtime_opt_in=True)
        for field in ("execution_attempted", "studio_start_called", "network_request_sent", "subprocess_started", "runtime_admitted"): self.assertFalse(result[field])
    def test_missing_explicit_consent_fails_closed(self):
        with self.assertRaisesRegex(admission.ExecutionAdmissionError, "owner confirmation"): admission.admit_execution(adapter_plan=self.plan, owner_confirmation=False, runtime_opt_in=True)
        with self.assertRaisesRegex(admission.ExecutionAdmissionError, "runtime opt-in"): admission.admit_execution(adapter_plan=self.plan, owner_confirmation=True, runtime_opt_in=False)
    def test_boundary_and_ttl_are_bounded(self):
        with self.assertRaisesRegex(admission.ExecutionAdmissionError, "boundary"): admission.admit_execution(adapter_plan={**self.plan, "network_allowed": True}, owner_confirmation=True, runtime_opt_in=True)
        with self.assertRaisesRegex(admission.ExecutionAdmissionError, "ttl"): admission.admit_execution(adapter_plan=self.plan, owner_confirmation=True, runtime_opt_in=True, requested_ttl_ms=30_001)
if __name__ == "__main__": unittest.main()
