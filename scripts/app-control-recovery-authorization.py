#!/usr/bin/env python3
"""Verify and atomically consume owner-bound recovery authorization receipts."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any

SCHEMA = "agent_bridge.app_control.recovery_authorization.v0"
RECEIPT_SCHEMA = "agent_bridge.app_control.recovery_authorization_receipt.v0"
HEX64 = re.compile(r"[0-9a-f]{64}")
OPAQUE_ID = re.compile(r"ab-episode-[0-9a-f]{32}")
NONCE = re.compile(r"[0-9a-f]{32,64}")
MAX_RECEIPT_BYTES = 4096


def _result(admission: str, *, consumed: bool = False, error: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema": SCHEMA, "status": "verified", "verdict": "verified",
        "recover": "proceed" if admission == "authorized" else "replan",
        "admission": admission, "read_only": not consumed, "receipt_consumed": consumed,
        "media_observed": False, "action_invoked": False,
        "automatic_recovery_authorized": False,
    }
    if error:
        out["error"] = {"code": error}
    return out


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def authorize(*, receipt: str, public_key_b64: str | None, ledger: Path | None,
              operation_id: str, record_sha256: str, request_sha256: str,
              workspace_sha256: str, session_sha256: str, consume: bool,
              now: float | None = None) -> dict[str, Any]:
    if public_key_b64 is None or ledger is None:
        return _result("source_unavailable", error="authorization_source_unavailable")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key_raw = _decode(public_key_b64)
        if len(key_raw) != 32:
            raise ValueError("invalid_public_key")
        public_key = Ed25519PublicKey.from_public_bytes(key_raw)
        meta = os.lstat(ledger)
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o700:
            raise OSError("unsafe_ledger")
    except (ImportError, OSError, ValueError):
        return _result("source_unavailable", error="authorization_source_unavailable")
    try:
        encoded, encoded_mac = receipt.split(".", 1)
        raw = _decode(encoded)
        supplied_mac = _decode(encoded_mac)
        if len(raw) > MAX_RECEIPT_BYTES or len(supplied_mac) != 64:
            raise ValueError("invalid_receipt")
        public_key.verify(supplied_mac, raw)
        payload = json.loads(raw)
    except (ValueError, TypeError, json.JSONDecodeError, InvalidSignature):
        return _result("binding_conflict", error="authorization_receipt_invalid")
    required = {
        "schema", "operation_id", "record_sha256", "request_sha256", "workspace_sha256",
        "session_sha256", "issued_at_unix_seconds", "expires_at_unix_seconds", "issuer", "nonce",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        return _result("binding_conflict", error="authorization_receipt_shape_invalid")
    issued = payload.get("issued_at_unix_seconds")
    expires = payload.get("expires_at_unix_seconds")
    shape_ok = (
        payload.get("schema") == RECEIPT_SCHEMA
        and OPAQUE_ID.fullmatch(str(payload.get("operation_id", ""))) is not None
        and all(HEX64.fullmatch(str(payload.get(name, ""))) is not None for name in
                ("record_sha256", "request_sha256", "workspace_sha256", "session_sha256"))
        and NONCE.fullmatch(str(payload.get("nonce", ""))) is not None
        and isinstance(payload.get("issuer"), str) and 0 < len(payload["issuer"]) <= 128
        and type(issued) in (int, float) and type(expires) in (int, float)
        and not isinstance(issued, bool) and not isinstance(expires, bool)
        and float(expires) > float(issued) and float(expires) - float(issued) <= 300.0
    )
    bindings = (operation_id, record_sha256, request_sha256, workspace_sha256, session_sha256)
    recorded = tuple(payload.get(name) for name in
                     ("operation_id", "record_sha256", "request_sha256", "workspace_sha256", "session_sha256"))
    if not shape_ok or bindings != recorded:
        return _result("binding_conflict", error="authorization_binding_conflict")
    current = time.time() if now is None else now
    if current < float(issued) - 5.0 or current >= float(expires):
        return _result("expired", error="authorization_expired")
    claim = ledger / f"{hashlib.sha256(payload['nonce'].encode()).hexdigest()}.consumed"
    if claim.exists():
        return _result("already_consumed", error="authorization_already_consumed")
    if not consume:
        return _result("authorized")
    try:
        fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.write(fd, json.dumps({"schema": SCHEMA, "consumed_at_unix_seconds": current},
                                separators=(",", ":")).encode())
        os.fsync(fd)
        os.close(fd)
    except FileExistsError:
        return _result("already_consumed", error="authorization_already_consumed")
    except OSError:
        return _result("source_unavailable", error="authorization_source_unavailable")
    return _result("authorized", consumed=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--record-sha256", required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--workspace-sha256", required=True)
    parser.add_argument("--session-sha256", required=True)
    parser.add_argument("--consume", action="store_true")
    args = parser.parse_args()
    public_key = os.environ.get("AB_APP_CONTROL_RECOVERY_AUTH_PUBLIC_KEY_B64")
    ledger = os.environ.get("AB_APP_CONTROL_RECOVERY_AUTH_DIR")
    out = authorize(receipt=args.receipt, public_key_b64=public_key,
                    ledger=Path(ledger) if ledger else None, operation_id=args.operation_id,
                    record_sha256=args.record_sha256, request_sha256=args.request_sha256,
                    workspace_sha256=args.workspace_sha256, session_sha256=args.session_sha256,
                    consume=args.consume)
    print(json.dumps(out, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
