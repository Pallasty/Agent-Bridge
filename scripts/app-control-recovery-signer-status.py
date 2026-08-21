#!/usr/bin/env python3
"""Read-only readiness probe for an external recovery authorization signer."""
from __future__ import annotations
import base64, json, os, stat
from pathlib import Path

SCHEMA = "agent_bridge.app_control.recovery_authorization_signer_status.v0"

def status(*, public_key_b64: str | None, ledger: Path | None) -> dict:
    key_valid = False
    verifier_available = False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        verifier_available = True
        if public_key_b64:
            raw = base64.urlsafe_b64decode(public_key_b64 + "=" * (-len(public_key_b64) % 4))
            Ed25519PublicKey.from_public_bytes(raw)
            key_valid = len(raw) == 32
    except (ImportError, ValueError):
        pass
    ledger_ready = False
    if ledger is not None:
        try:
            meta = os.lstat(ledger)
            ledger_ready = (stat.S_ISDIR(meta.st_mode) and meta.st_uid == os.getuid()
                            and stat.S_IMODE(meta.st_mode) == 0o700)
        except OSError:
            pass
    configured = verifier_available and key_valid and ledger_ready
    return {"schema": SCHEMA, "status": "verified", "verdict": "verified",
            "recover": "proceed" if configured else "replan", "read_only": True,
            "admission": "configured" if configured else "source_unavailable",
            "external_private_key_required": True, "private_key_observed": False,
            "action_invoked": False, "automatic_recovery_authorized": False,
            "checks": {"ed25519_verifier_available": verifier_available,
                       "frontend_public_key_configured": key_valid,
                       "owner_only_nonce_ledger_ready": ledger_ready},
            "error": None if configured else {"code": "authorization_source_unavailable"}}

def main() -> int:
    ledger = os.environ.get("AB_APP_CONTROL_RECOVERY_AUTH_DIR")
    out = status(public_key_b64=os.environ.get("AB_APP_CONTROL_RECOVERY_AUTH_PUBLIC_KEY_B64"),
                 ledger=Path(ledger) if ledger else None)
    print(json.dumps(out, sort_keys=True, separators=(",", ":"))); return 0
if __name__ == "__main__": raise SystemExit(main())
