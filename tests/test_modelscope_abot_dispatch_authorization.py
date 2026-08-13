import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


auth = load("auth", ROOT / "scripts" / "modelscope_abot_dispatch_authorization.py")
dispatch = load("dispatch_auth", ROOT / "scripts" / "modelscope_abot_external_dispatch.py")
admission = load("admission_auth", ROOT / "scripts" / "modelscope_abot_execution_admission.py")
attempt = load("attempt_auth", ROOT / "scripts" / "modelscope_abot_execution_attempt.py")
commit = load("commit_auth", ROOT / "scripts" / "modelscope_abot_execution_commit.py")
NOW = 1_786_600_000_000


class DispatchAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        plan = {
            "schema": auth.ENVELOPE_SCHEMA.replace("external_dispatch", "external_adapter_plan"),
            "provider_id": auth.PROVIDER_ID,
            "activation_id": "gate7o-activation-0001",
            "capability_id": "gate7o-capability-0001",
            "capability_sha256": "12" * 32,
            "capability_digest_bound": True,
            "plan_only": True,
            "adapter": {
                "action": auth.ACTION,
                "endpoint": auth.ENDPOINT,
                "timeout_ms": auth.MAX_TTL_MS,
                "network_allowed": False,
                "subprocess_allowed": False,
            },
            "execution_capability_issued": False,
            "studio_start_called": False,
            "execution_authorized": False,
            "runtime_admitted": False,
            "mcp_registered": False,
        }
        admitted = admission.admit_execution(
            adapter_plan=plan, owner_confirmation=True, runtime_opt_in=True, now_unix_ms=NOW
        )
        receipt = attempt.prepare_attempt(
            adapter_plan=plan,
            admission_receipt=admitted,
            attempt_id="gate7o-attempt-0001",
            now_unix_ms=NOW,
            timeout_ms=auth.MAX_TTL_MS,
        )
        store = commit.ExecutionCommitStore(Path(self.temp.name) / "commit.sqlite3")
        committed = store.commit(attempt_receipt=receipt, now_unix_ms=NOW)
        self.envelope = dispatch.prepare_dispatch_envelope(
            adapter_plan=plan,
            attempt_receipt=receipt,
            commit_receipt=committed,
            now_unix_ms=NOW,
            timeout_ms=auth.MAX_TTL_MS,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_proposal_requires_explicit_inputs_but_stays_non_authorizing(self):
        result = auth.prepare_authorization_proposal(
            dispatch_envelope=self.envelope,
            owner_confirmation=True,
            runtime_opt_in=True,
            now_unix_ms=NOW,
            requested_ttl_ms=auth.MAX_TTL_MS,
        )
        self.assertTrue(result["authorization_proposed"])
        self.assertFalse(result["dispatch_authorized"])
        self.assertFalse(result["dispatch_performed"])
        self.assertFalse(result["network_request_sent"])
        self.assertFalse(result["runtime_admitted"])

    def test_consent_and_ttl_fail_closed(self):
        with self.assertRaisesRegex(auth.DispatchAuthorizationError, "owner confirmation"):
            auth.prepare_authorization_proposal(
                dispatch_envelope=self.envelope,
                owner_confirmation=False,
                runtime_opt_in=True,
                now_unix_ms=NOW,
                requested_ttl_ms=1,
            )
        with self.assertRaisesRegex(auth.DispatchAuthorizationError, "runtime opt-in"):
            auth.prepare_authorization_proposal(
                dispatch_envelope=self.envelope,
                owner_confirmation=True,
                runtime_opt_in=False,
                now_unix_ms=NOW,
                requested_ttl_ms=1,
            )
        with self.assertRaisesRegex(auth.DispatchAuthorizationError, "ttl"):
            auth.prepare_authorization_proposal(
                dispatch_envelope=self.envelope,
                owner_confirmation=True,
                runtime_opt_in=True,
                now_unix_ms=NOW,
                requested_ttl_ms=30_001,
            )

    def test_open_envelope_fails_closed(self):
        with self.assertRaisesRegex(auth.DispatchAuthorizationError, "boundary"):
            auth.prepare_authorization_proposal(
                dispatch_envelope={**self.envelope, "dispatch_performed": True},
                owner_confirmation=True,
                runtime_opt_in=True,
                now_unix_ms=NOW,
                requested_ttl_ms=1,
            )
        with self.assertRaisesRegex(auth.DispatchAuthorizationError, "target"):
            auth.prepare_authorization_proposal(
                dispatch_envelope={**self.envelope, "endpoint": "/other"},
                owner_confirmation=True,
                runtime_opt_in=True,
                now_unix_ms=NOW,
                requested_ttl_ms=1,
            )


if __name__ == "__main__":
    unittest.main()
