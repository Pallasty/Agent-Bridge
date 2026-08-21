import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/app-control-recovery-authorization-request.py"
SPEC = importlib.util.spec_from_file_location("authorization_request", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)

class AuthorizationRequestTests(unittest.TestCase):
    def setUp(self):
        self.bindings = dict(operation_id="ab-episode-" + "1" * 32, record_sha256="2" * 64,
            request_sha256="3" * 64, workspace_sha256="4" * 64, session_sha256="5" * 64)
    def test_request_is_minimal_read_only_and_not_authority(self):
        out = MOD.prepare(**self.bindings, now=100.0, nonce="6" * 32)
        self.assertEqual(out["verdict"], "verified")
        self.assertTrue(out["read_only"]); self.assertFalse(out["authorization_granted"])
        self.assertFalse(out["automatic_recovery_authorized"]); self.assertFalse(out["action_invoked"])
        self.assertEqual(set(out["broker_request"]), {"schema", "operation_id", "record_sha256",
            "request_sha256", "workspace_sha256", "session_sha256", "requested_at_unix_seconds",
            "maximum_receipt_ttl_secs", "request_nonce"})
    def test_invalid_binding_fails_closed(self):
        self.assertEqual(MOD.prepare(**{**self.bindings, "session_sha256": "bad"})["recover"], "replan")
    def test_nonce_changes_between_requests(self):
        first=MOD.prepare(**self.bindings); second=MOD.prepare(**self.bindings)
        self.assertNotEqual(first["broker_request"]["request_nonce"], second["broker_request"]["request_nonce"])

if __name__ == "__main__": unittest.main()
