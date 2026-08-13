#!/usr/bin/env python3
"""Signed, non-admitted execution-capability contract for ModelScope ABot."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
CONTRACT_SCHEMA = "agent_bridge.modelscope_abot_execution_capability_contract.v0"
SIGNATURE_SCHEMA = "agent_bridge.modelscope_abot_capability_hmac.v0"
ACTION = "start_simulated_projection"
ENDPOINT = "/on_click_start_ws"
MAX_CAPABILITY_TTL_MS = 30_000
MAX_SESSION_DURATION_MS = 180_000


class CapabilityContractError(ValueError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _unsigned(contract: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in contract.items() if key != "signature"}


def _mac(contract: dict[str, Any], *, key: bytes, key_id: str) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise CapabilityContractError("capability key missing")
    if not isinstance(key_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{8,128}", key_id):
        raise CapabilityContractError("capability key id invalid")
    signed = {
        "contract": _unsigned(contract),
        "signature": {
            "schema": SIGNATURE_SCHEMA,
            "algorithm": "hmac-sha256",
            "key_id": key_id,
        },
    }
    return hmac.new(key, _canonical_json(signed), hashlib.sha256).hexdigest()


def build_contract(
    *,
    store: Any,
    claim: dict[str, Any],
    capability_id: str,
    prompt_sha256: str,
    key: bytes,
    key_id: str,
    now_unix_ms: int,
    ttl_ms: int = MAX_CAPABILITY_TTL_MS,
) -> dict[str, Any]:
    if not isinstance(claim, dict):
        raise CapabilityContractError("claim not object")
    if claim.get("schema") != "agent_bridge.modelscope_abot_single_use_claim.v0":
        raise CapabilityContractError("claim schema mismatch")
    if claim.get("provider_id") != PROVIDER_ID:
        raise CapabilityContractError("claim provider mismatch")
    committed_fields = ("authority_consumed", "nonce_consumed", "session_reserved")
    if not all(claim.get(field) is True for field in committed_fields):
        raise CapabilityContractError("claim is not committed")
    closed_fields = (
        "execution_capability_issued",
        "studio_start_called",
        "execution_authorized",
        "runtime_admitted",
        "mcp_registered",
    )
    if any(claim.get(field) is not False for field in closed_fields):
        raise CapabilityContractError("claim boundary is open")
    if not isinstance(capability_id, str) or not re.fullmatch(
        r"[A-Za-z0-9._-]{16,128}", capability_id
    ):
        raise CapabilityContractError("capability id invalid")
    if not isinstance(prompt_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", prompt_sha256
    ):
        raise CapabilityContractError("prompt digest invalid")
    if (
        not isinstance(ttl_ms, int)
        or isinstance(ttl_ms, bool)
        or not 1 <= ttl_ms <= MAX_CAPABILITY_TTL_MS
    ):
        raise CapabilityContractError("capability ttl invalid")

    lease = store.validate_claim_reference(
        lease_id=claim["lease_id"],
        candidate_sha256=claim["candidate_sha256"],
        now_unix_ms=now_unix_ms,
    )
    expires_at = min(now_unix_ms + ttl_ms, lease["expires_at_unix_ms"])
    if expires_at <= now_unix_ms:
        raise CapabilityContractError("capability expiry invalid")
    contract = {
        "schema": CONTRACT_SCHEMA,
        "provider_id": PROVIDER_ID,
        "capability_id": capability_id,
        "claim": {
            "lease_id": lease["lease_id"],
            "candidate_sha256": lease["candidate_sha256"],
            "nonce_sha256": lease["nonce_sha256"],
        },
        "operation": {
            "action": ACTION,
            "endpoint": ENDPOINT,
            "prompt_sha256": prompt_sha256,
        },
        "bounds": {
            "issued_at_unix_ms": now_unix_ms,
            "expires_at_unix_ms": expires_at,
            "max_session_duration_ms": MAX_SESSION_DURATION_MS,
            "max_concurrent_sessions": 1,
            "single_use": True,
            "queue_allowed": False,
            "retry_allowed": False,
            "raw_prompt_persisted": False,
            "transport_frames_persisted": False,
        },
        "activation_status": "not_admitted",
        "capability_contract_issued": True,
        "execution_capability_issued": False,
        "capability_consumed": False,
        "studio_start_called": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "mcp_registered": False,
    }
    contract["signature"] = {
        "schema": SIGNATURE_SCHEMA,
        "algorithm": "hmac-sha256",
        "key_id": key_id,
        "mac_sha256": _mac(contract, key=key, key_id=key_id),
    }
    return contract


def validate_contract(
    contract: Any,
    *,
    store: Any,
    key: bytes,
    key_id: str,
    now_unix_ms: int,
) -> dict[str, Any]:
    violations: list[str] = []
    if not isinstance(contract, dict):
        contract = {}
        violations.append("contract_not_object")
    expected_fields = {
        "schema",
        "provider_id",
        "capability_id",
        "claim",
        "operation",
        "bounds",
        "activation_status",
        "capability_contract_issued",
        "execution_capability_issued",
        "capability_consumed",
        "studio_start_called",
        "execution_authorized",
        "runtime_admitted",
        "mcp_registered",
        "signature",
    }
    if set(contract) != expected_fields:
        violations.append("contract_fields_invalid")
    if contract.get("schema") != CONTRACT_SCHEMA or contract.get("provider_id") != PROVIDER_ID:
        violations.append("contract_identity_mismatch")
    if not isinstance(contract.get("capability_id"), str) or not re.fullmatch(
        r"[A-Za-z0-9._-]{16,128}", contract.get("capability_id", "")
    ):
        violations.append("capability_id_invalid")
    operation = contract.get("operation", {})
    if not isinstance(operation, dict) or set(operation) != {
        "action",
        "endpoint",
        "prompt_sha256",
    }:
        violations.append("operation_fields_invalid")
        operation = {}
    if operation.get("action") != ACTION or operation.get("endpoint") != ENDPOINT:
        violations.append("operation_scope_mismatch")
    if not isinstance(operation.get("prompt_sha256"), str) or not re.fullmatch(
        r"[0-9a-f]{64}", operation.get("prompt_sha256", "")
    ):
        violations.append("prompt_digest_invalid")
    bounds = contract.get("bounds", {})
    if not isinstance(bounds, dict):
        violations.append("bounds_not_object")
        bounds = {}
    expected_bound_fields = {
        "issued_at_unix_ms",
        "expires_at_unix_ms",
        "max_session_duration_ms",
        "max_concurrent_sessions",
        "single_use",
        "queue_allowed",
        "retry_allowed",
        "raw_prompt_persisted",
        "transport_frames_persisted",
    }
    if set(bounds) != expected_bound_fields:
        violations.append("bounds_fields_invalid")
    issued = bounds.get("issued_at_unix_ms")
    expires = bounds.get("expires_at_unix_ms")
    if (
        not isinstance(now_unix_ms, int)
        or isinstance(now_unix_ms, bool)
        or not isinstance(issued, int)
        or isinstance(issued, bool)
        or not isinstance(expires, int)
        or isinstance(expires, bool)
        or not issued <= now_unix_ms < expires
        or expires - issued > MAX_CAPABILITY_TTL_MS
    ):
        violations.append("capability_time_invalid")
    expected_bounds = {
        "max_session_duration_ms": MAX_SESSION_DURATION_MS,
        "max_concurrent_sessions": 1,
        "single_use": True,
        "queue_allowed": False,
        "retry_allowed": False,
        "raw_prompt_persisted": False,
        "transport_frames_persisted": False,
    }
    if any(bounds.get(field) != value for field, value in expected_bounds.items()):
        violations.append("capability_bounds_invalid")
    closed = {
        "activation_status": "not_admitted",
        "capability_contract_issued": True,
        "execution_capability_issued": False,
        "capability_consumed": False,
        "studio_start_called": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "mcp_registered": False,
    }
    if any(contract.get(field) != value for field, value in closed.items()):
        violations.append("runtime_boundary_open")
    claim = contract.get("claim", {})
    try:
        if not isinstance(claim, dict) or set(claim) != {
            "lease_id",
            "candidate_sha256",
            "nonce_sha256",
        }:
            raise ValueError
        lease = store.validate_claim_reference(
            lease_id=claim["lease_id"],
            candidate_sha256=claim["candidate_sha256"],
            now_unix_ms=now_unix_ms,
        )
        if lease["nonce_sha256"] != claim["nonce_sha256"] or expires > lease["expires_at_unix_ms"]:
            raise ValueError
    except Exception:
        violations.append("claim_reference_invalid")
    signature = contract.get("signature", {})
    if not isinstance(signature, dict) or set(signature) != {
        "schema",
        "algorithm",
        "key_id",
        "mac_sha256",
    }:
        violations.append("signature_fields_invalid")
    else:
        try:
            signature_valid = (
                signature.get("schema") == SIGNATURE_SCHEMA
                and signature.get("algorithm") == "hmac-sha256"
                and signature.get("key_id") == key_id
                and isinstance(signature.get("mac_sha256"), str)
                and hmac.compare_digest(
                    signature["mac_sha256"],
                    _mac(contract, key=key, key_id=key_id),
                )
            )
        except (CapabilityContractError, TypeError, ValueError):
            signature_valid = False
        if not signature_valid:
            violations.append("signature_invalid")
    valid = not violations
    return {
        "schema": "agent_bridge.modelscope_abot_execution_capability_validation.v0",
        "valid": valid,
        "violations": violations,
        "capability_contract_valid": valid,
        "execution_capability_issued": False,
        "studio_start_called": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "mcp_registered": False,
        "next_gate": "gate7h_capability_activation_admission" if valid else None,
    }
