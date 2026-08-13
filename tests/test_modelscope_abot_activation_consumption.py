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
CONSUME = load("modelscope_abot_activation_consumption", ROOT / "scripts" / "modelscope_abot_activation_consumption.py")

AUTHORITY_KEY = b"synthetic-gate7i-authority-key-material"
AUTHORITY_KEY_ID = "synthetic-authority-key"
CAPABILITY_KEY = b"synthetic-gate7i-capability-key-material"
CAPABILITY_KEY_ID = "synthetic-capability-key"
ACTIVATION_KEY = b"synthetic-gate7i-activation-key-material"
ACTIVATION_KEY_ID = "synthetic-activation-key"
NOW = 1_786_588_542_277


def candidate():
    value = {
        "schema": STORE.CANDIDATE_SCHEMA,
        "provider_id": STORE.PROVIDER_ID,
        "authority": {
            "schema": STORE.AUTHORITY_SCHEMA,
            "decision_id": "owner-decision-gate7i",
            "cognitive_decision_id": "cognitive-decision-gate7i",
            "body_id": "modelscope-public-studio",
            "status": "approved",
            "boundary": "external_write",
            "owner_confirmation": True,
            "lease_id": None,
        },
        "nonce": {
            "sha256": "67" * 32,
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


class ModelScopeAbotActivationConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = STORE.SingleUseAuthorityStore(Path(self.temp.name) / "authority.sqlite3")
        claim = self.store.claim(
            candidate(), key=AUTHORITY_KEY, key_id=AUTHORITY_KEY_ID,
            lease_id="gate7i-lease-0001", now_unix_ms=NOW, lease_ttl_ms=180_000,
        )
        self.contract = CAP.build_contract(
            store=self.store, claim=claim, capability_id="gate7i-capability-0001",
            prompt_sha256="78" * 32, key=CAPABILITY_KEY, key_id=CAPABILITY_KEY_ID,
            now_unix_ms=NOW,
        )
        request = {
            "schema": ACT.REQUEST_SCHEMA,
            "provider_id": ACT.PROVIDER_ID,
            "activation_id": "gate7i-activation-0001",
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
        request["signature"] = {
            "schema": ACT.SIGNATURE_SCHEMA,
            "algorithm": "hmac-sha256",
            "key_id": ACTIVATION_KEY_ID,
            "mac_sha256": ACT.request_mac(request, ACTIVATION_KEY, ACTIVATION_KEY_ID),
        }
        ACT.admit_activation(
            store=self.store, request=request, capability_contract=self.contract,
            capability_validator=self.validate_capability, key=ACTIVATION_KEY,
            key_id=ACTIVATION_KEY_ID, now_unix_ms=NOW,
        )

    def tearDown(self):
        self.temp.cleanup()

    def validate_capability(self, contract, now):
        return CAP.validate_contract(
            contract, store=self.store, key=CAPABILITY_KEY,
            key_id=CAPABILITY_KEY_ID, now_unix_ms=now,
        )

    def consume(self, contract=None, now=NOW, **kwargs):
        return CONSUME.consume_activation(
            store=self.store, activation_id="gate7i-activation-0001",
            capability_contract=contract or self.contract,
            capability_validator=self.validate_capability,
            now_unix_ms=now, **kwargs,
        )

    def test_consumes_activation_once_without_external_execution(self):
        result = self.consume()
        self.assertEqual(result["schema"], CONSUME.CONSUMPTION_SCHEMA)
        self.assertTrue(result["activation_consumed"])
        self.assertTrue(result["capability_validated"])
        self.assertTrue(result["activation_reference_validated"])
        self.assertFalse(result["execution_capability_issued"])
        self.assertFalse(result["studio_start_called"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["runtime_admitted"])
        self.assertFalse(result["mcp_registered"])
        self.assertEqual(self.store.activation_snapshot()["consumed_activation_count"], 1)

    def test_replay_is_rejected(self):
        self.consume()
        with self.assertRaisesRegex(CONSUME.ActivationConsumptionError, "activation consumption rejected"):
            self.consume()

    def test_concurrent_consumption_has_exactly_one_winner(self):
        barrier = threading.Barrier(2)
        outcomes = []

        def run():
            barrier.wait()
            try:
                self.consume()
                outcomes.append("won")
            except CONSUME.ActivationConsumptionError:
                outcomes.append("rejected")

        threads = [threading.Thread(target=run), threading.Thread(target=run)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertCountEqual(outcomes, ["won", "rejected"])
        self.assertEqual(self.store.activation_snapshot()["consumed_activation_count"], 1)

    def test_transaction_interruption_rolls_back_consumption(self):
        with self.assertRaisesRegex(CONSUME.ActivationConsumptionError, "activation consumption rejected"):
            self.consume(fault_after_mark=True)
        self.assertEqual(self.store.activation_snapshot()["consumed_activation_count"], 0)
        self.consume()

    def test_tampering_release_and_wrong_contract_fail_closed(self):
        tampered = copy.deepcopy(self.contract)
        tampered["operation"]["endpoint"] = "/on_stop_ws"
        with self.assertRaisesRegex(CONSUME.ActivationConsumptionError, "capability contract invalid"):
            self.consume(tampered)
        self.store.release_session(lease_id=self.contract["claim"]["lease_id"])
        with self.assertRaisesRegex(CONSUME.ActivationConsumptionError, "capability contract invalid"):
            self.consume()

    def test_committed_evidence_keeps_external_runtime_closed(self):
        path = ROOT / "docs" / "design" / "evidence" / "modelscope_abot_gate7i_activation_consumption_2026_08_12.json"
        evidence = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["evidence_class"], "synthetic_contract_test")
        self.assertTrue(all(evidence["tests"].values()))
        self.assertFalse(evidence["studio_start_called"])
        self.assertFalse(evidence["execution_authorized"])
        self.assertFalse(evidence["runtime_admitted"])
        self.assertFalse(evidence["mcp_registered"])


if __name__ == "__main__":
    unittest.main()
