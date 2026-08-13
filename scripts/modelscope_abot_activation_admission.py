#!/usr/bin/env python3
"""Default-off, non-actuating activation admission for ModelScope ABot."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
REQUEST_SCHEMA = "agent_bridge.modelscope_abot_activation_request.v0"
ADMISSION_SCHEMA = "agent_bridge.modelscope_abot_activation_admission.v0"
SIGNATURE_SCHEMA = "agent_bridge.modelscope_abot_activation_hmac.v0"
ACTION = "start_simulated_projection"
ENDPOINT = "/on_click_start_ws"


class ActivationAdmissionError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def capability_digest(contract: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(contract)).hexdigest()


def _unsigned(request: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in request.items() if key != "signature"}


def request_mac(request: dict[str, Any], key: bytes, key_id: str) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ActivationAdmissionError("activation key missing")
    if not isinstance(key_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{8,128}", key_id):
        raise ActivationAdmissionError("activation key id invalid")
    signed = {
        "request": _unsigned(request),
        "signature": {
            "schema": SIGNATURE_SCHEMA,
            "algorithm": "hmac-sha256",
            "key_id": key_id,
        },
    }
    return hmac.new(key, _canonical(signed), hashlib.sha256).hexdigest()


def _validate_request(request: Any, *, key: bytes, key_id: str, now_unix_ms: int) -> None:
    if not isinstance(request, dict):
        raise ActivationAdmissionError("activation request not object")
    if set(request) != {
        "schema", "provider_id", "activation_id", "capability_id", "capability_sha256",
        "lease_id", "action", "endpoint", "owner_confirmation", "runtime_opt_in",
        "requested_at_unix_ms", "expires_at_unix_ms", "signature",
    }:
        raise ActivationAdmissionError("activation request fields invalid")
    if request["schema"] != REQUEST_SCHEMA or request["provider_id"] != PROVIDER_ID:
        raise ActivationAdmissionError("activation identity mismatch")
    if request["action"] != ACTION or request["endpoint"] != ENDPOINT:
        raise ActivationAdmissionError("activation operation mismatch")
    for field, pattern in (
        ("activation_id", r"[A-Za-z0-9._-]{16,128}"),
        ("capability_id", r"[A-Za-z0-9._-]{16,128}"),
        ("lease_id", r"[A-Za-z0-9._-]{16,128}"),
        ("capability_sha256", r"[0-9a-f]{64}"),
    ):
        if not isinstance(request[field], str) or not re.fullmatch(pattern, request[field]):
            raise ActivationAdmissionError(f"{field} invalid")
    if request["owner_confirmation"] is not True:
        raise ActivationAdmissionError("owner confirmation required")
    if request["runtime_opt_in"] is not True:
        raise ActivationAdmissionError("runtime opt-in required")
    issued = request["requested_at_unix_ms"]
    expires = request["expires_at_unix_ms"]
    if (
        not isinstance(issued, int) or isinstance(issued, bool)
        or not isinstance(expires, int) or isinstance(expires, bool)
        or not issued <= now_unix_ms < expires
        or expires - issued > 30_000
    ):
        raise ActivationAdmissionError("activation request expiry invalid")
    signature = request["signature"]
    if not isinstance(signature, dict) or set(signature) != {"schema", "algorithm", "key_id", "mac_sha256"}:
        raise ActivationAdmissionError("activation signature fields invalid")
    if (
        signature["schema"] != SIGNATURE_SCHEMA
        or signature["algorithm"] != "hmac-sha256"
        or signature["key_id"] != key_id
        or not isinstance(signature["mac_sha256"], str)
        or not hmac.compare_digest(signature["mac_sha256"], request_mac(request, key, key_id))
    ):
        raise ActivationAdmissionError("activation signature invalid")


def admit_activation(
    *,
    store: Any,
    request: dict[str, Any],
    capability_contract: dict[str, Any],
    capability_validator: Any,
    key: bytes,
    key_id: str,
    now_unix_ms: int,
) -> dict[str, Any]:
    _validate_request(request, key=key, key_id=key_id, now_unix_ms=now_unix_ms)
    if request["capability_sha256"] != capability_digest(capability_contract):
        raise ActivationAdmissionError("capability digest mismatch")
    if request["capability_id"] != capability_contract.get("capability_id"):
        raise ActivationAdmissionError("capability id mismatch")
    claim = capability_contract.get("claim")
    if not isinstance(claim, dict) or request["lease_id"] != claim.get("lease_id"):
        raise ActivationAdmissionError("lease binding mismatch")
    validation = capability_validator(capability_contract, now_unix_ms)
    if validation.get("valid") is not True:
        raise ActivationAdmissionError("capability contract invalid")
    result = store.admit_activation(
        activation_id=request["activation_id"],
        capability_id=request["capability_id"],
        capability_sha256=request["capability_sha256"],
        lease_id=request["lease_id"],
        now_unix_ms=now_unix_ms,
        expires_at_unix_ms=request["expires_at_unix_ms"],
    )
    result["request_authenticated"] = True
    result["capability_validated"] = True
    result["activation_key_loaded"] = True
    return result
