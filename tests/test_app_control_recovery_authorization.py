import base64, importlib.util, json
from pathlib import Path
import os, tempfile, threading, unittest
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/app-control-recovery-authorization.py"
SPEC = importlib.util.spec_from_file_location("recovery_authorization", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)

class RecoveryAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); root = Path(self.tmp.name)
        self.private_key = Ed25519PrivateKey.generate()
        public = self.private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.public_key_b64 = base64.urlsafe_b64encode(public).decode().rstrip("=")
        self.ledger = root / "ledger"; self.ledger.mkdir(mode=0o700)
        self.now = 2_000_000_000.0
        self.bindings = dict(operation_id="ab-episode-" + "1" * 32, record_sha256="2" * 64,
            request_sha256="3" * 64, workspace_sha256="4" * 64, session_sha256="5" * 64)
    def tearDown(self): self.tmp.cleanup()
    def receipt(self, **changes):
        payload = {"schema": MOD.RECEIPT_SCHEMA, **self.bindings, "issued_at_unix_seconds": self.now - 1,
            "expires_at_unix_seconds": self.now + 60, "issuer": "trusted-frontend:test", "nonce": "6" * 32}
        payload.update(changes); raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        enc = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
        return enc(raw) + "." + enc(self.private_key.sign(raw))
    def call(self, receipt=None, consume=False, **bindings):
        return MOD.authorize(receipt=receipt or self.receipt(), public_key_b64=self.public_key_b64, ledger=self.ledger,
            consume=consume, now=self.now, **{**self.bindings, **bindings})
    def test_default_without_trusted_source_is_unavailable(self):
        out = MOD.authorize(receipt="x", public_key_b64=None, ledger=None, consume=False, now=self.now, **self.bindings)
        self.assertEqual(out["admission"], "source_unavailable")
    def test_boolean_or_unsigned_text_cannot_authorize(self):
        self.assertEqual(self.call(receipt="true")["admission"], "binding_conflict")
    def test_exact_receipt_reviews_without_consuming(self):
        out = self.call(); self.assertEqual(out["admission"], "authorized")
        self.assertTrue(out["read_only"]); self.assertFalse(out["automatic_recovery_authorized"])
        self.assertEqual(list(self.ledger.iterdir()), [])
    def test_cross_session_workspace_and_record_drift_conflict(self):
        for field in ("session_sha256", "workspace_sha256", "record_sha256"):
            with self.subTest(field=field): self.assertEqual(self.call(**{field: "a" * 64})["admission"], "binding_conflict")
    def test_expiry(self):
        self.assertEqual(self.call(receipt=self.receipt(expires_at_unix_seconds=self.now))["admission"], "expired")
    def test_consume_is_one_time(self):
        self.assertEqual(self.call(consume=True)["admission"], "authorized")
        self.assertEqual(self.call(consume=True)["admission"], "already_consumed")
        self.assertEqual(self.call()["admission"], "already_consumed")
    def test_concurrent_consume_has_one_winner(self):
        barrier = threading.Barrier(8); admissions = []
        def run(): barrier.wait(); admissions.append(self.call(consume=True)["admission"])
        threads = [threading.Thread(target=run) for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(admissions.count("authorized"), 1)
        self.assertEqual(admissions.count("already_consumed"), 7)
    def test_es256_exact_receipt_verifies_and_algorithm_mismatch_fails(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        public = private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        payload = {"schema": MOD.RECEIPT_SCHEMA, **self.bindings,
            "issued_at_unix_seconds": self.now - 1, "expires_at_unix_seconds": self.now + 60,
            "issuer": "trusted-frontend:test", "nonce": "7" * 32}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        enc = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
        receipt = enc(raw) + "." + enc(private_key.sign(raw, ec.ECDSA(hashes.SHA256())))
        key_b64 = enc(public)
        with patch.dict(os.environ, {"AB_APP_CONTROL_RECOVERY_AUTH_ALGORITHM": "ES256"}):
            out = MOD.authorize(receipt=receipt, public_key_b64=key_b64, ledger=self.ledger,
                consume=False, now=self.now, **self.bindings)
        self.assertEqual(out["admission"], "authorized")
        with patch.dict(os.environ, {"AB_APP_CONTROL_RECOVERY_AUTH_ALGORITHM": "Ed25519"}):
            out = MOD.authorize(receipt=receipt, public_key_b64=key_b64, ledger=self.ledger,
                consume=False, now=self.now, **self.bindings)
        self.assertEqual(out["admission"], "source_unavailable")
    def test_es256_wrong_curve_and_unknown_algorithm_fail_closed(self):
        public = ec.generate_private_key(ec.SECP384R1()).public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        key_b64 = base64.urlsafe_b64encode(public).decode().rstrip("=")
        with patch.dict(os.environ, {"AB_APP_CONTROL_RECOVERY_AUTH_ALGORITHM": "ES256"}):
            out = MOD.authorize(receipt=self.receipt(), public_key_b64=key_b64,
                ledger=self.ledger, consume=False, now=self.now, **self.bindings)
        self.assertEqual(out["admission"], "source_unavailable")
        with patch.dict(os.environ, {"AB_APP_CONTROL_RECOVERY_AUTH_ALGORITHM": "ES384"}):
            out = MOD.authorize(receipt=self.receipt(), public_key_b64=key_b64,
                ledger=self.ledger, consume=False, now=self.now, **self.bindings)
        self.assertEqual(out["admission"], "source_unavailable")

if __name__ == "__main__": unittest.main()
