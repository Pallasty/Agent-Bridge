import base64, hashlib, hmac, importlib.util, json, os
from pathlib import Path
import tempfile, threading, unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/app-control-recovery-authorization.py"
SPEC = importlib.util.spec_from_file_location("recovery_authorization", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)

class RecoveryAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); root = Path(self.tmp.name)
        self.key = root / "key"; self.key.write_bytes(b"k" * 32); os.chmod(self.key, 0o600)
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
        return enc(raw) + "." + enc(hmac.new(b"k" * 32, raw, hashlib.sha256).digest())
    def call(self, receipt=None, consume=False, **bindings):
        return MOD.authorize(receipt=receipt or self.receipt(), key_path=self.key, ledger=self.ledger,
            consume=consume, now=self.now, **{**self.bindings, **bindings})
    def test_default_without_trusted_source_is_unavailable(self):
        out = MOD.authorize(receipt="x", key_path=None, ledger=None, consume=False, now=self.now, **self.bindings)
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

if __name__ == "__main__": unittest.main()
