import copy
import importlib.util
import json
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


STORE = load("modelscope_abot_authority_store", ROOT / "scripts" / "modelscope_abot_authority_store.py")
CAP = load("modelscope_abot_capability_contract", ROOT / "scripts" / "modelscope_abot_capability_contract.py")
ACT = load("modelscope_abot_activation_admission", ROOT / "scripts" / "modelscope_abot_activation_admission.py")

AUTHORITY_KEY = b"synthetic-gate7h-authority-key-material"
AUTHORITY_KEY_ID = "synthetic-authority-key"
CAPABILITY_KEY = b"synthetic-gate7h-capability-key-material"
CAPABILITY_KEY_ID = "synthetic-capability-key"
ACTIVATION_KEY = b"synthetic-gate7h-activation-key-material"
ACTIVATION_KEY_ID = "synthetic-activation-key"
NOW = 1_786_588_542_277


def candidate():
    value = {
        "schema": STORE.CANDIDATE_SCHEMA,
        "provider_id": STORE.PROVIDER_ID,
        "authority": {
            "schema": STORE.AUTHORITY_SCHEMA,
            "decision_id": "owner-decision-gate7h",
            "cognitive_decision_id": "cognitive-decision-gate7h",
            "body_id": "modelscope-public-studio",
            "status": "approved",
            "boundary": "external_write",
            "owner_confirmation": True,
            "lease_id": None,
        },
        "nonce": {
            "sha256": "45" * 32,
            "scope": STORE.PROVIDER_ID,
            "consumed": False,
            "expires_at_unix_ms": NOW + 300_000,
        },
        "synthetic_fixture": False,
        "execution_authorized": False,
    }
    value["authenticity"] = {
        "schema": STORE.AUTHENTICITY_SCHEMA,
        "algorithm": "hmac-sha256",
        "key_id": AUTHORITY_KEY_ID,
        "mac_sha256": STORE.candidate_mac(value, AUTHORITY_KEY, AUTHORITY_KEY_ID),
    }
    return value


class ModelScopeAbotActivationAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = STORE.SingleUseAuthorityStore(Path(self.temp.name) / "authority.sqlite3")
        claim = self.store.claim(
            candidate(), key=AUTHORITY_KEY, key_id=AUTHORITY_KEY_ID,
            lease_id="gate7h-lease-0001", now_unix_ms=NOW, lease_ttl_ms=180_000,
        )
        self.contract = CAP.build_contract(
            store=self.store, claim=claim, capability_id="gate7h-capability-0001",
            prompt_sha256="56" * 32, key=CAPABILITY_KEY, key_id=CAPABILITY_KEY_ID,
            now_unix_ms=NOW,
        )

    def tearDown(self):
        self.temp.cleanup()

    def request(self, **changes):
        value = {
            "schema": ACT.REQUEST_SCHEMA,
            "provider_id": ACT.PROVIDER_ID,
            "activation_id": "gate7h-activation-0001",
            "capability_id": self.contract["capability_id"],
            "capability_sha256": ACT.capability_digest(self.contract),
            "lease_id": self.contract["claim"]["lease_id"],
            "action": ACT.ACTION,
            "endpoint": ACT.ENDPOINT,
            "owner_confirmation": True,
            "runtime_opt_in": True,
            "requested_at_unix_ms": NOW,
            "expires_at_unix_ms": NOW + 30_000,
        }
        value.update(changes)
        value["signature"] = {
            "schema": ACT.SIGNATURE_SCHEMA,
            "algorithm": "hmac-sha256",
            "key_id": ACTIVATION_KEY_ID,
            "mac_sha256": ACT.request_mac(value, ACTIVATION_KEY, ACTIVATION_KEY_ID),
        }
        return value

    def validate_capability(self, contract, now):
        return CAP.validate_contract(
            contract, store=self.store, key=CAPABILITY_KEY,
            key_id=CAPABILITY_KEY_ID, now_unix_ms=now,
        )

    def admit(self, request=None, contract=None, now=NOW):
        return ACT.admit_activation(
            store=self.store, request=request or self.request(),
            capability_contract=contract or self.contract,
            capability_validator=self.validate_capability,
            key=ACTIVATION_KEY, key_id=ACTIVATION_KEY_ID, now_unix_ms=now,
        )

    def test_admission_records_once_without_execution(self):
        result = self.admit()
        self.assertTrue(result["activation_admitted"])
        self.assertTrue(result["request_authenticated"])
        self.assertTrue(result["capability_validated"])
        self.assertFalse(result["activation_consumed"])
        self.assertFalse(result["execution_capability_issued"])
        self.assertFalse(result["studio_start_called"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["runtime_admitted"])
        self.assertFalse(result["mcp_registered"])
        self.assertEqual(self.store.activation_snapshot()["activation_count"], 1)

    def test_default_off_or_missing_owner_confirmation_rejected_before_write(self):
        before = self.store.activation_snapshot()
        with self.assertRaisesRegex(ACT.ActivationAdmissionError, "runtime opt-in"):
            request = self.request(runtime_opt_in=False)
            self.admit(request)
        with self.assertRaisesRegex(ACT.ActivationAdmissionError, "owner confirmation"):
            request = self.request(owner_confirmation=False)
            self.admit(request)
        self.assertEqual(self.store.activation_snapshot(), before)

    def test_activation_is_single_use_for_same_capability_and_id(self):
        self.admit()
        with self.assertRaisesRegex(STORE.AuthorityStoreError, "already admitted"):
            self.admit()
        with self.assertRaisesRegex(STORE.AuthorityStoreError, "already admitted"):
            self.admit(self.request(activation_id="gate7h-activation-0002"))

    def test_concurrent_activation_has_exactly_one_ledger_winner(self):
        barrier = threading.Barrier(2)
        outcomes = []

        def run():
            barrier.wait()
            try:
                self.admit()
                outcomes.append("won")
            except STORE.AuthorityStoreError:
                outcomes.append("rejected")

        threads = [threading.Thread(target=run), threading.Thread(target=run)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertCountEqual(outcomes, ["won", "rejected"])
        self.assertEqual(self.store.activation_snapshot()["activation_count"], 1)

    def test_tamper_scope_digest_signature_and_expiry_fail_closed(self):
        request = self.request(endpoint="/on_stop_ws")
        with self.assertRaisesRegex(ACT.ActivationAdmissionError, "activation operation"):
            self.admit(request)
        request = self.request(capability_sha256="ff" * 32)
        with self.assertRaisesRegex(ACT.ActivationAdmissionError, "capability digest"):
            self.admit(request)
        request = self.request(capability_id="gate7h-other-capability")
        with self.assertRaisesRegex(ACT.ActivationAdmissionError, "capability id"):
            self.admit(request)
        request = self.request(lease_id="gate7h-other-lease")
        with self.assertRaisesRegex(ACT.ActivationAdmissionError, "lease binding"):
            self.admit(request)
        request = self.request()
        request["signature"]["mac_sha256"] = "00" * 32
        with self.assertRaisesRegex(ACT.ActivationAdmissionError, "signature invalid"):
            self.admit(request)
        request = self.request(expires_at_unix_ms=NOW + 30_001)
        request["signature"]["mac_sha256"] = ACT.request_mac(request, ACTIVATION_KEY, ACTIVATION_KEY_ID)
        with self.assertRaisesRegex(ACT.ActivationAdmissionError, "expiry invalid"):
            self.admit(request)

    def test_released_claim_and_invalid_capability_are_rejected(self):
        self.store.release_session(lease_id=self.contract["claim"]["lease_id"])
        with self.assertRaisesRegex(ACT.ActivationAdmissionError, "capability contract invalid"):
            self.admit()
        self.assertEqual(self.store.activation_snapshot()["activation_count"], 0)

    def test_activation_receipt_contract_is_closed(self):
        result = self.admit()
        self.assertEqual(result["schema"], ACT.ADMISSION_SCHEMA)
        self.assertTrue(result["activation_admitted"])
        self.assertFalse(result["activation_consumed"])
        self.assertFalse(result["execution_capability_issued"])
        self.assertFalse(result["studio_start_called"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["runtime_admitted"])
        self.assertFalse(result["mcp_registered"])

    def test_committed_evidence_keeps_real_activation_closed(self):
        path = ROOT / "docs" / "design" / "evidence" / "modelscope_abot_gate7h_activation_admission_2026_08_12.json"
        evidence = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["evidence_class"], "synthetic_contract_test")
        self.assertTrue(all(evidence["tests"].values()))
        self.assertFalse(evidence["real_activation_admitted"])
        self.assertFalse(evidence["activation_consumed"])
        self.assertFalse(evidence["execution_capability_issued"])
        self.assertFalse(evidence["studio_start_called"])
        self.assertFalse(evidence["runtime_admitted"])
        self.assertFalse(evidence["mcp_registered"])


if __name__ == "__main__":
    unittest.main()
