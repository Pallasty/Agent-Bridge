#!/usr/bin/env python3
"""Create a minimal unsigned request for a trusted recovery-authorization frontend."""
from __future__ import annotations
import argparse, hashlib, json, re, secrets, time

SCHEMA = "agent_bridge.app_control.recovery_authorization_broker_request.v0"
OPAQUE_ID = re.compile(r"ab-episode-[0-9a-f]{32}")
HEX64 = re.compile(r"[0-9a-f]{64}")

def prepare(*, operation_id: str, record_sha256: str, request_sha256: str,
            workspace_sha256: str, session_sha256: str, now: float | None = None,
            nonce: str | None = None) -> dict:
    values = (record_sha256, request_sha256, workspace_sha256, session_sha256)
    if OPAQUE_ID.fullmatch(operation_id) is None or any(HEX64.fullmatch(value) is None for value in values):
        return {"schema": SCHEMA, "status": "error", "verdict": "error", "recover": "replan",
                "error": {"code": "invalid_authorization_request_binding"}}
    payload = {"schema": SCHEMA, "operation_id": operation_id, "record_sha256": record_sha256,
               "request_sha256": request_sha256, "workspace_sha256": workspace_sha256,
               "session_sha256": session_sha256, "requested_at_unix_seconds": time.time() if now is None else now,
               "maximum_receipt_ttl_secs": 300, "request_nonce": nonce or secrets.token_hex(16)}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {"schema": SCHEMA, "status": "verified", "verdict": "verified", "recover": "proceed",
            "read_only": True, "authorization_granted": False, "action_invoked": False,
            "automatic_recovery_authorized": False, "broker_request": payload,
            "broker_request_sha256": hashlib.sha256(canonical).hexdigest()}

def main() -> int:
    p=argparse.ArgumentParser()
    for name in ("operation-id","record-sha256","request-sha256","workspace-sha256","session-sha256"):
        p.add_argument("--"+name, required=True)
    a=p.parse_args(); out=prepare(operation_id=a.operation_id, record_sha256=a.record_sha256,
        request_sha256=a.request_sha256, workspace_sha256=a.workspace_sha256, session_sha256=a.session_sha256)
    print(json.dumps(out, sort_keys=True, separators=(",", ":"))); return 0
if __name__ == "__main__": raise SystemExit(main())
