#!/usr/bin/env python3
"""Default-off dispatch authorization proposal for ModelScope ABot."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
ENVELOPE_SCHEMA = "agent_bridge.modelscope_abot_external_dispatch.v0"
AUTHORIZATION_SCHEMA = "agent_bridge.modelscope_abot_dispatch_authorization_proposal.v0"
ACTION = "start_simulated_projection"
ENDPOINT = "/on_click_start_ws"
MAX_TTL_MS = 30_000


class DispatchAuthorizationError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _require_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise DispatchAuthorizationError(f"{label} invalid")


def _validate_envelope(envelope: Any, now_unix_ms: Any) -> None:
    if (
        not isinstance(envelope, dict)
        or envelope.get("schema") != ENVELOPE_SCHEMA
        or envelope.get("provider_id") != PROVIDER_ID
        or envelope.get("plan_only") is not True
        or envelope.get("dispatch_ready") is not False
    ):
        raise DispatchAuthorizationError("dispatch envelope invalid")
    _require_digest(envelope.get("attempt_sha256"), "attempt digest")
    _require_digest(envelope.get("adapter_plan_sha256"), "adapter plan digest")
    if not isinstance(envelope.get("attempt_id"), str) or not envelope["attempt_id"]:
        raise DispatchAuthorizationError("attempt binding invalid")
    if envelope.get("action") != ACTION or envelope.get("endpoint") != ENDPOINT:
        raise DispatchAuthorizationError("dispatch target invalid")
    if (
        not isinstance(envelope.get("timeout_ms"), int)
        or isinstance(envelope.get("timeout_ms"), bool)
        or not 1 <= envelope["timeout_ms"] <= MAX_TTL_MS
    ):
        raise DispatchAuthorizationError("dispatch timeout invalid")
    for field in (
        "dispatch_performed",
        "network_request_sent",
        "subprocess_started",
        "studio_start_called",
        "execution_authorized",
        "runtime_admitted",
        "mcp_registered",
    ):
        if envelope.get(field) is not False:
            raise DispatchAuthorizationError("dispatch boundary open")
    prepared_at = envelope.get("prepared_at_unix_ms")
    expires_at = envelope.get("expires_at_unix_ms")
    if (
        not isinstance(now_unix_ms, int)
        or isinstance(now_unix_ms, bool)
        or not isinstance(prepared_at, int)
        or isinstance(prepared_at, bool)
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
        or prepared_at >= expires_at
        or expires_at - prepared_at > MAX_TTL_MS
        or now_unix_ms < prepared_at
        or now_unix_ms >= expires_at
    ):
        raise DispatchAuthorizationError("dispatch envelope expired")


def prepare_authorization_proposal(
    *,
    dispatch_envelope: dict[str, Any],
    owner_confirmation: bool,
    runtime_opt_in: bool,
    now_unix_ms: int,
    requested_ttl_ms: int,
) -> dict[str, Any]:
    _validate_envelope(dispatch_envelope, now_unix_ms)
    if owner_confirmation is not True:
        raise DispatchAuthorizationError("owner confirmation required")
    if runtime_opt_in is not True:
        raise DispatchAuthorizationError("runtime opt-in required")
    if (
        not isinstance(requested_ttl_ms, int)
        or isinstance(requested_ttl_ms, bool)
        or not 1 <= requested_ttl_ms <= MAX_TTL_MS
        or requested_ttl_ms > dispatch_envelope["expires_at_unix_ms"] - now_unix_ms
    ):
        raise DispatchAuthorizationError("authorization ttl invalid")
    envelope_digest = _digest(dispatch_envelope)
    return {
        "schema": AUTHORIZATION_SCHEMA,
        "provider_id": PROVIDER_ID,
        "authorization_id": f"gate7o-{envelope_digest[:24]}",
        "dispatch_envelope_sha256": envelope_digest,
        "attempt_id": dispatch_envelope["attempt_id"],
        "action": ACTION,
        "endpoint": ENDPOINT,
        "issued_at_unix_ms": now_unix_ms,
        "expires_at_unix_ms": now_unix_ms + requested_ttl_ms,
        "owner_confirmation": True,
        "runtime_opt_in": True,
        "authorization_proposed": True,
        "dispatch_authorized": False,
        "dispatch_performed": False,
        "network_request_sent": False,
        "subprocess_started": False,
        "studio_start_called": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "mcp_registered": False,
        "plan_only": True,
        "next_gate": "gate7p_external_dispatch_execution",
    }
