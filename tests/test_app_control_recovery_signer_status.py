import base64, importlib.util, os
from pathlib import Path
import tempfile, unittest
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/app-control-recovery-signer-status.py"
SPEC=importlib.util.spec_from_file_location("signer_status", SCRIPT)
MOD=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)

class SignerStatusTests(unittest.TestCase):
    def test_default_is_source_unavailable(self):
        out=MOD.status(public_key_b64=None, ledger=None)
        self.assertEqual(out["admission"], "source_unavailable")
        self.assertFalse(out["private_key_observed"]); self.assertFalse(out["action_invoked"])
        self.assertIn("signature_verifier_available",out["checks"])
        self.assertNotIn("ed25519_verifier_available",out["checks"])
    def test_public_key_and_secure_ledger_are_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Path(tmp)/"ledger"; ledger.mkdir(mode=0o700); os.chmod(ledger,0o700)
            key=Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            out=MOD.status(public_key_b64=base64.urlsafe_b64encode(key).decode().rstrip("="), ledger=ledger)
            self.assertEqual(out["admission"], "configured")
    def test_bad_key_or_permissive_ledger_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Path(tmp)/"ledger"; ledger.mkdir(); os.chmod(ledger,0o755)
            self.assertEqual(MOD.status(public_key_b64="bad", ledger=ledger)["admission"], "source_unavailable")
    def test_es256_p256_key_is_configured_only_under_explicit_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Path(tmp)/"ledger"; ledger.mkdir(mode=0o700); os.chmod(ledger,0o700)
            key=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
            key_b64=base64.urlsafe_b64encode(key).decode().rstrip("=")
            with patch.dict(os.environ, {"AB_APP_CONTROL_RECOVERY_AUTH_ALGORITHM": "ES256"}):
                self.assertEqual(MOD.status(public_key_b64=key_b64, ledger=ledger)["admission"], "configured")
            with patch.dict(os.environ, {"AB_APP_CONTROL_RECOVERY_AUTH_ALGORITHM": "Ed25519"}):
                self.assertEqual(MOD.status(public_key_b64=key_b64, ledger=ledger)["admission"], "source_unavailable")
    def test_es256_wrong_curve_and_unknown_algorithm_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Path(tmp)/"ledger"; ledger.mkdir(mode=0o700); os.chmod(ledger,0o700)
            key=ec.generate_private_key(ec.SECP384R1()).public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
            key_b64=base64.urlsafe_b64encode(key).decode().rstrip("=")
            with patch.dict(os.environ, {"AB_APP_CONTROL_RECOVERY_AUTH_ALGORITHM": "ES256"}):
                out=MOD.status(public_key_b64=key_b64,ledger=ledger)
            self.assertEqual(out["admission"],"source_unavailable")
            with patch.dict(os.environ, {"AB_APP_CONTROL_RECOVERY_AUTH_ALGORITHM": "ES384"}):
                out=MOD.status(public_key_b64=key_b64,ledger=ledger)
            self.assertEqual(out["admission"],"source_unavailable")
            self.assertFalse(out["checks"]["signature_verifier_available"])

if __name__ == "__main__": unittest.main()
