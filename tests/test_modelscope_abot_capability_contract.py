import copy
import importlib.util
import json
import sys
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


STORE = load(
    "modelscope_abot_authority_store",
    ROOT / "scripts" / "modelscope_abot_authority_store.py",
)
CAP = load(
    "modelscope_abot_capability_contract",
    ROOT / "scripts" / "modelscope_abot_capability_contract.py",
)

AUTHORITY_KEY = b"synthetic-gate7g-authority-key-material"
AUTHORITY_KEY_ID = "synthetic-authority-key"
CAPABILITY_KEY = b"synthetic-gate7g-capability-key-material"
CAPABILITY_KEY_ID = "synthetic-capability-key"
NOW = 1_786_588_542_277
PROMPT_SHA256 = "12" * 32


def candidate():
    value = {
        "schema": STORE.CANDIDATE_SCHEMA,
        "provider_id": STORE.PROVIDER_ID,
        "authority": {
            "schema": STORE.AUTHORITY_SCHEMA,
            "decision_id": "owner-decision-gate7g",
            "cognitive_decision_id": "cognitive-decision-gate7g",
            "body_id": "modelscope-public-studio",
            "status": "approved",
            "boundary": "external_write",
            "owner_confirmation": True,
            "lease_id": None,
        },
        "nonce": {
            "sha256": "34" * 32,
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


class ModelScopeAbotCapabilityContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = STORE.SingleUseAuthorityStore(Path(self.temp.name) / "authority.sqlite3")
        self.claim = self.store.claim(
            candidate(),
            key=AUTHORITY_KEY,
            key_id=AUTHORITY_KEY_ID,
            lease_id="gate7g-lease-0001",
            now_unix_ms=NOW,
            lease_ttl_ms=180_000,
        )

    def tearDown(self):
        self.temp.cleanup()

    def build(self, **kwargs):
        return CAP.build_contract(
            store=self.store,
            claim=self.claim,
            capability_id="gate7g-capability-0001",
            prompt_sha256=PROMPT_SHA256,
            key=CAPABILITY_KEY,
            key_id=CAPABILITY_KEY_ID,
            now_unix_ms=NOW,
            **kwargs,
        )

    def validate(self, contract, now=NOW):
        return CAP.validate_contract(
            contract,
            store=self.store,
            key=CAPABILITY_KEY,
            key_id=CAPABILITY_KEY_ID,
            now_unix_ms=now,
        )

    def test_contract_is_bounded_signed_and_non_admitted(self):
        contract = self.build()
        self.assertTrue(self.validate(contract)["valid"])
        self.assertEqual(contract["operation"]["action"], CAP.ACTION)
        self.assertEqual(contract["operation"]["endpoint"], CAP.ENDPOINT)
        self.assertEqual(contract["operation"]["prompt_sha256"], PROMPT_SHA256)
        self.assertEqual(contract["activation_status"], "not_admitted")
        self.assertTrue(contract["capability_contract_issued"])
        self.assertFalse(contract["execution_capability_issued"])
        self.assertFalse(contract["capability_consumed"])
        self.assertFalse(contract["studio_start_called"])
        self.assertFalse(contract["execution_authorized"])
        self.assertFalse(contract["runtime_admitted"])
        self.assertFalse(contract["mcp_registered"])

    def test_contract_never_contains_raw_prompt(self):
        raw_prompt = "private synthetic prompt that must never persist"
        contract = self.build()
        encoded = json.dumps(contract, sort_keys=True)
        self.assertNotIn(raw_prompt, encoded)
        self.assertNotIn("prompt_text", encoded)
        self.assertFalse(contract["bounds"]["raw_prompt_persisted"])

    def test_ttl_is_bounded_by_thirty_seconds_and_lease(self):
        with self.assertRaisesRegex(CAP.CapabilityContractError, "ttl invalid"):
            self.build(ttl_ms=30_001)
        short_store = STORE.SingleUseAuthorityStore(Path(self.temp.name) / "short.sqlite3")
        short_claim = short_store.claim(
            candidate(), key=AUTHORITY_KEY, key_id=AUTHORITY_KEY_ID,
            lease_id="gate7g-short-lease", now_unix_ms=NOW, lease_ttl_ms=10_000,
        )
        contract = CAP.build_contract(
            store=short_store, claim=short_claim,
            capability_id="gate7g-short-capability", prompt_sha256=PROMPT_SHA256,
            key=CAPABILITY_KEY, key_id=CAPABILITY_KEY_ID,
            now_unix_ms=NOW, ttl_ms=30_000,
        )
        self.assertEqual(contract["bounds"]["expires_at_unix_ms"], NOW + 10_000)

    def test_tamper_wrong_key_and_expiry_fail_closed(self):
        contract = self.build()
        tampered = copy.deepcopy(contract)
        tampered["operation"]["endpoint"] = "/on_stop_ws"
        self.assertFalse(self.validate(tampered)["valid"])
        wrong_key = CAP.validate_contract(
            contract, store=self.store,
            key=b"wrong-capability-key-material-32bytes",
            key_id=CAPABILITY_KEY_ID, now_unix_ms=NOW,
        )
        self.assertIn("signature_invalid", wrong_key["violations"])
        expired = self.validate(contract, now=NOW + 30_000)
        self.assertIn("capability_time_invalid", expired["violations"])

    def test_released_or_mismatched_claim_is_rejected(self):
        contract = self.build()
        altered = copy.deepcopy(self.claim)
        altered["candidate_sha256"] = "ff" * 32
        with self.assertRaisesRegex(STORE.AuthorityStoreError, "digest mismatch"):
            CAP.build_contract(
                store=self.store, claim=altered,
                capability_id="gate7g-capability-0002", prompt_sha256=PROMPT_SHA256,
                key=CAPABILITY_KEY, key_id=CAPABILITY_KEY_ID, now_unix_ms=NOW,
            )
        self.store.release_session(lease_id=self.claim["lease_id"])
        self.assertIn("claim_reference_invalid", self.validate(contract)["violations"])

    def test_open_claim_boundary_is_rejected_before_contract_issue(self):
        opened = copy.deepcopy(self.claim)
        opened["runtime_admitted"] = True
        with self.assertRaisesRegex(CAP.CapabilityContractError, "boundary is open"):
            CAP.build_contract(
                store=self.store, claim=opened,
                capability_id="gate7g-capability-0002", prompt_sha256=PROMPT_SHA256,
                key=CAPABILITY_KEY, key_id=CAPABILITY_KEY_ID, now_unix_ms=NOW,
            )

    def test_malformed_contract_and_invalid_verifier_key_fail_closed(self):
        malformed = self.validate(None)
        self.assertFalse(malformed["valid"])
        contract = self.build()
        result = CAP.validate_contract(
            contract,
            store=self.store,
            key=b"short",
            key_id=CAPABILITY_KEY_ID,
            now_unix_ms=NOW,
        )
        self.assertFalse(result["valid"])
        self.assertIn("signature_invalid", result["violations"])

    def test_committed_evidence_keeps_activation_and_runtime_closed(self):
        path = (
            ROOT / "docs" / "design" / "evidence"
            / "modelscope_abot_gate7g_capability_contract_2026_08_13.json"
        )
        evidence = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["evidence_class"], "synthetic_contract_test")
        self.assertTrue(all(evidence["tests"].values()))
        self.assertFalse(evidence["execution_capability_issued"])
        self.assertFalse(evidence["capability_consumed"])
        self.assertFalse(evidence["studio_start_called"])
        self.assertFalse(evidence["execution_authorized"])
        self.assertFalse(evidence["runtime_admitted"])
        self.assertFalse(evidence["mcp_registered"])


if __name__ == "__main__":
    unittest.main()
