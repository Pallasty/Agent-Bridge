import importlib.util
import json
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path(__file__).parents[1] / "scripts" / "modelscope_abot_authority_store.py"
SPEC = importlib.util.spec_from_file_location("modelscope_abot_authority_store", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

KEY = b"synthetic-gate7f-test-key-material"
KEY_ID = "synthetic-gate7f-key"
NOW = 1_786_588_542_277


def candidate(nonce: str = "ab" * 32):
    value = {
        "schema": MODULE.CANDIDATE_SCHEMA,
        "provider_id": MODULE.PROVIDER_ID,
        "authority": {
            "schema": MODULE.AUTHORITY_SCHEMA,
            "decision_id": "owner-decision-gate7f",
            "cognitive_decision_id": "cognitive-decision-gate7f",
            "body_id": "modelscope-public-studio",
            "status": "approved",
            "boundary": "external_write",
            "owner_confirmation": True,
            "lease_id": None,
        },
        "nonce": {
            "sha256": nonce,
            "scope": MODULE.PROVIDER_ID,
            "consumed": False,
            "expires_at_unix_ms": NOW + 300_000,
        },
        "synthetic_fixture": False,
        "execution_authorized": False,
    }
    value["authenticity"] = {
        "schema": MODULE.AUTHENTICITY_SCHEMA,
        "algorithm": "hmac-sha256",
        "key_id": KEY_ID,
        "mac_sha256": MODULE.candidate_mac(value, KEY, KEY_ID),
    }
    return value


class ModelScopeAbotAuthorityStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "authority.sqlite3"
        self.store = MODULE.SingleUseAuthorityStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def claim(self, value=None, lease_id="gate7f-lease-0001", **kwargs):
        return self.store.claim(
            value or candidate(),
            key=KEY,
            key_id=KEY_ID,
            lease_id=lease_id,
            now_unix_ms=NOW,
            lease_ttl_ms=180_000,
            **kwargs,
        )

    def test_claim_atomically_consumes_and_reserves_without_execution(self):
        result = self.claim()
        self.assertTrue(result["authority_consumed"])
        self.assertTrue(result["nonce_consumed"])
        self.assertTrue(result["session_reserved"])
        self.assertFalse(result["execution_capability_issued"])
        self.assertFalse(result["studio_start_called"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["runtime_admitted"])
        self.assertEqual(self.store.snapshot()["consumed_authority_count"], 1)
        self.assertEqual(self.store.snapshot()["active_session_count"], 1)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_replay_remains_rejected_after_session_release(self):
        self.claim()
        self.assertTrue(self.store.release_session(lease_id="gate7f-lease-0001"))
        with self.assertRaisesRegex(MODULE.AuthorityStoreError, "already consumed"):
            self.claim(lease_id="gate7f-lease-0002")
        self.assertEqual(self.store.snapshot()["consumed_authority_count"], 1)
        self.assertEqual(self.store.snapshot()["active_session_count"], 0)

    def test_busy_provider_rejects_new_nonce_without_consuming_it(self):
        self.claim()
        second = candidate("cd" * 32)
        with self.assertRaisesRegex(MODULE.AuthorityStoreError, "already reserved"):
            self.claim(second, lease_id="gate7f-lease-0002")
        self.store.release_session(lease_id="gate7f-lease-0001")
        result = self.claim(second, lease_id="gate7f-lease-0002")
        self.assertTrue(result["nonce_consumed"])

    def test_transaction_interruption_rolls_back_nonce_and_session(self):
        with self.assertRaisesRegex(RuntimeError, "synthetic transaction interruption"):
            self.claim(fault_after_nonce_insert=True)
        self.assertEqual(self.store.snapshot()["consumed_authority_count"], 0)
        self.assertEqual(self.store.snapshot()["active_session_count"], 0)
        self.claim()

    def test_expired_session_recovers_but_consumed_nonce_does_not(self):
        self.claim()
        self.assertEqual(self.store.recover_expired_sessions(now_unix_ms=NOW + 179_999), 0)
        self.assertEqual(self.store.recover_expired_sessions(now_unix_ms=NOW + 180_000), 1)
        with self.assertRaisesRegex(MODULE.AuthorityStoreError, "already consumed"):
            self.claim(lease_id="gate7f-lease-0002")
        self.claim(candidate("ef" * 32), lease_id="gate7f-lease-0003")

    def test_tampering_wrong_key_expiry_and_synthetic_candidates_fail_closed(self):
        tampered = candidate()
        tampered["authority"]["body_id"] = "other-body"
        with self.assertRaisesRegex(MODULE.AuthorityStoreError, "authenticity rejected"):
            self.claim(tampered)
        with self.assertRaisesRegex(MODULE.AuthorityStoreError, "authenticity rejected"):
            self.store.claim(
                candidate(), key=b"wrong-key-material-is-at-least-32b", key_id=KEY_ID,
                lease_id="gate7f-lease-0001", now_unix_ms=NOW, lease_ttl_ms=1,
            )
        expired = candidate()
        expired["nonce"]["expires_at_unix_ms"] = NOW
        expired["authenticity"]["mac_sha256"] = MODULE.candidate_mac(expired, KEY, KEY_ID)
        with self.assertRaisesRegex(MODULE.AuthorityStoreError, "nonce expired"):
            self.claim(expired)
        synthetic = candidate()
        synthetic["synthetic_fixture"] = True
        synthetic["authenticity"]["mac_sha256"] = MODULE.candidate_mac(synthetic, KEY, KEY_ID)
        with self.assertRaisesRegex(MODULE.AuthorityStoreError, "synthetic candidate"):
            self.claim(synthetic)
        extended = candidate()
        extended["unexpected"] = True
        with self.assertRaisesRegex(MODULE.AuthorityStoreError, "candidate fields invalid"):
            self.claim(extended)

    def test_concurrent_claim_has_exactly_one_winner(self):
        barrier = threading.Barrier(2)
        outcomes = []

        def run(lease_id):
            local = MODULE.SingleUseAuthorityStore(self.path)
            barrier.wait()
            try:
                local.claim(
                    candidate(), key=KEY, key_id=KEY_ID, lease_id=lease_id,
                    now_unix_ms=NOW, lease_ttl_ms=180_000,
                )
                outcomes.append("won")
            except MODULE.AuthorityStoreError:
                outcomes.append("rejected")

        threads = [
            threading.Thread(target=run, args=("gate7f-lease-thread-a",)),
            threading.Thread(target=run, args=("gate7f-lease-thread-b",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertCountEqual(outcomes, ["won", "rejected"])
        self.assertEqual(self.store.snapshot()["consumed_authority_count"], 1)

    def test_committed_evidence_keeps_real_runtime_closed(self):
        path = (
            Path(__file__).parents[1] / "docs" / "design" / "evidence"
            / "modelscope_abot_gate7f_single_use_claim_2026_08_13.json"
        )
        evidence = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["evidence_class"], "synthetic_contract_test")
        self.assertTrue(all(evidence["tests"].values()))
        self.assertFalse(evidence["authority_key_loaded"])
        self.assertFalse(evidence["real_authority_consumed"])
        self.assertFalse(evidence["real_nonce_consumed"])
        self.assertFalse(evidence["execution_capability_issued"])
        self.assertFalse(evidence["studio_start_called"])
        self.assertFalse(evidence["runtime_admitted"])
        self.assertFalse(evidence["mcp_registered"])


if __name__ == "__main__":
    unittest.main()
