#!/usr/bin/env python3
"""Default-off, non-actuating dispatch envelope for ModelScope ABot."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
PLAN_SCHEMA = "agent_bridge.modelscope_abot_external_adapter_plan.v0"
ATTEMPT_SCHEMA = "agent_bridge.modelscope_abot_execution_attempt.v0"
COMMIT_SCHEMA = "agent_bridge.modelscope_abot_execution_commit.v0"
DISPATCH_SCHEMA = "agent_bridge.modelscope_abot_external_dispatch.v0"
ACTION = "start_simulated_projection"
ENDPOINT = "/on_click_start_ws"
MAX_TIMEOUT_MS = 30_000


class ExternalDispatchError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _require_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ExternalDispatchError(f"{label} invalid")


def _validate_plan(plan: Any) -> None:
    if (
        not isinstance(plan, dict)
        or plan.get("schema") != PLAN_SCHEMA
        or plan.get("provider_id") != PROVIDER_ID
        or plan.get("plan_only") is not True
        or plan.get("capability_digest_bound") is not True
    ):
        raise ExternalDispatchError("adapter plan invalid")
    for field in ("activation_id", "capability_id"):
        if not isinstance(plan.get(field), str) or not plan[field]:
            raise ExternalDispatchError("adapter plan binding invalid")
    _require_digest(plan.get("capability_sha256"), "capability digest")
    for field in (
        "execution_capability_issued",
        "studio_start_called",
        "execution_authorized",
        "runtime_admitted",
        "mcp_registered",
    ):
        if plan.get(field) is not False:
            raise ExternalDispatchError("adapter boundary open")
    adapter = plan.get("adapter")
    if (
        not isinstance(adapter, dict)
        or set(adapter) != {"action", "endpoint", "timeout_ms", "network_allowed", "subprocess_allowed"}
        or adapter.get("action") != ACTION
        or adapter.get("endpoint") != ENDPOINT
        or adapter.get("network_allowed") is not False
        or adapter.get("subprocess_allowed") is not False
    ):
        raise ExternalDispatchError("dispatch target invalid")
    if (
        not isinstance(adapter.get("timeout_ms"), int)
        or isinstance(adapter.get("timeout_ms"), bool)
        or not 1 <= adapter["timeout_ms"] <= MAX_TIMEOUT_MS
    ):
        raise ExternalDispatchError("dispatch timeout invalid")


def prepare_dispatch_envelope(
    *,
    adapter_plan: dict[str, Any],
    attempt_receipt: dict[str, Any],
    commit_receipt: dict[str, Any],
    now_unix_ms: int,
    timeout_ms: int,
) -> dict[str, Any]:
    _validate_plan(adapter_plan)
    if (
        not isinstance(attempt_receipt, dict)
        or attempt_receipt.get("schema") != ATTEMPT_SCHEMA
        or attempt_receipt.get("provider_id") != PROVIDER_ID
        or attempt_receipt.get("preflight_only") is not True
        or attempt_receipt.get("adapter_plan_sha256") != _digest(adapter_plan)
    ):
        raise ExternalDispatchError("attempt receipt invalid")
    _require_digest(attempt_receipt.get("adapter_plan_sha256"), "attempt plan digest")
    attempt_id = attempt_receipt.get("attempt_id")
    if not isinstance(attempt_id, str) or re.fullmatch(r"[A-Za-z0-9._-]{16,128}", attempt_id) is None:
        raise ExternalDispatchError("attempt id invalid")
    for field in (
        "network_request_sent",
        "subprocess_started",
        "studio_start_called",
        "execution_attempted",
        "execution_authorized",
        "runtime_admitted",
        "mcp_registered",
    ):
        if attempt_receipt.get(field) is not False:
            raise ExternalDispatchError("attempt boundary open")
    prepared_at = attempt_receipt.get("prepared_at_unix_ms")
    expires_at = attempt_receipt.get("expires_at_unix_ms")
    if (
        not isinstance(now_unix_ms, int)
        or isinstance(now_unix_ms, bool)
        or not isinstance(prepared_at, int)
        or isinstance(prepared_at, bool)
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
        or prepared_at >= expires_at
        or expires_at - prepared_at > MAX_TIMEOUT_MS
        or now_unix_ms < prepared_at
        or now_unix_ms >= expires_at
    ):
        raise ExternalDispatchError("attempt expired")
    if (
        not isinstance(commit_receipt, dict)
        or commit_receipt.get("schema") != COMMIT_SCHEMA
        or commit_receipt.get("provider_id") != PROVIDER_ID
        or commit_receipt.get("commit_recorded") is not True
        or commit_receipt.get("attempt_id") != attempt_id
        or commit_receipt.get("attempt_sha256") != _digest(attempt_receipt)
    ):
        raise ExternalDispatchError("commit receipt invalid")
    _require_digest(commit_receipt.get("attempt_sha256"), "attempt digest")
    for field in (
        "execution_attempted",
        "execution_authorized",
        "network_request_sent",
        "subprocess_started",
        "studio_start_called",
        "runtime_admitted",
        "mcp_registered",
    ):
        if commit_receipt.get(field) is not False:
            raise ExternalDispatchError("commit boundary open")
    if (
        not isinstance(timeout_ms, int)
        or isinstance(timeout_ms, bool)
        or not 1 <= timeout_ms <= MAX_TIMEOUT_MS
        or timeout_ms > adapter_plan["adapter"]["timeout_ms"]
        or now_unix_ms + timeout_ms > expires_at
    ):
        raise ExternalDispatchError("dispatch timeout invalid")
    return {
        "schema": DISPATCH_SCHEMA,
        "provider_id": PROVIDER_ID,
        "attempt_id": attempt_id,
        "attempt_sha256": commit_receipt["attempt_sha256"],
        "adapter_plan_sha256": attempt_receipt["adapter_plan_sha256"],
        "action": ACTION,
        "endpoint": ENDPOINT,
        "timeout_ms": timeout_ms,
        "prepared_at_unix_ms": now_unix_ms,
        "expires_at_unix_ms": now_unix_ms + timeout_ms,
        "dispatch_ready": False,
        "dispatch_performed": False,
        "network_request_sent": False,
        "subprocess_started": False,
        "studio_start_called": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "mcp_registered": False,
        "plan_only": True,
        "next_gate": "gate7o_external_dispatch_authorization",
    }
