#!/usr/bin/env python3
"""Default-off, non-actuating external execution admission for ModelScope ABot."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
PLAN_SCHEMA = "agent_bridge.modelscope_abot_external_adapter_plan.v0"
ADMISSION_SCHEMA = "agent_bridge.modelscope_abot_execution_admission.v0"
ACTION = "start_simulated_projection"
ENDPOINT = "/on_click_start_ws"
MAX_TTL_MS = 30_000


class ExecutionAdmissionError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _validate_adapter_plan(adapter_plan: Any) -> None:
    if (
        not isinstance(adapter_plan, dict)
        or adapter_plan.get("schema") != PLAN_SCHEMA
        or adapter_plan.get("provider_id") != PROVIDER_ID
        or adapter_plan.get("plan_only") is not True
    ):
        raise ExecutionAdmissionError("adapter plan invalid")
    if adapter_plan.get("capability_digest_bound") is not True:
        raise ExecutionAdmissionError("capability binding missing")
    for field in (
        "execution_capability_issued",
        "studio_start_called",
        "execution_authorized",
        "runtime_admitted",
        "mcp_registered",
    ):
        if adapter_plan.get(field) is not False:
            raise ExecutionAdmissionError("adapter boundary open")
    if not isinstance(adapter_plan.get("activation_id"), str) or not adapter_plan["activation_id"]:
        raise ExecutionAdmissionError("activation binding missing")
    if not isinstance(adapter_plan.get("capability_id"), str) or not adapter_plan["capability_id"]:
        raise ExecutionAdmissionError("capability binding missing")
    if re.fullmatch(r"[0-9a-f]{64}", adapter_plan.get("capability_sha256", "")) is None:
        raise ExecutionAdmissionError("capability digest invalid")
    adapter = adapter_plan.get("adapter")
    if (
        not isinstance(adapter, dict)
        or set(adapter) != {"action", "endpoint", "timeout_ms", "network_allowed", "subprocess_allowed"}
        or adapter.get("action") != ACTION
        or adapter.get("endpoint") != ENDPOINT
        or adapter.get("network_allowed") is not False
        or adapter.get("subprocess_allowed") is not False
    ):
        raise ExecutionAdmissionError("adapter boundary open")
    if (
        not isinstance(adapter.get("timeout_ms"), int)
        or isinstance(adapter.get("timeout_ms"), bool)
        or not 1 <= adapter["timeout_ms"] <= MAX_TTL_MS
    ):
        raise ExecutionAdmissionError("adapter timeout invalid")


def admit_execution(
    *,
    adapter_plan: dict[str, Any],
    owner_confirmation: bool,
    runtime_opt_in: bool,
    now_unix_ms: int,
    requested_ttl_ms: int = MAX_TTL_MS,
) -> dict[str, Any]:
    _validate_adapter_plan(adapter_plan)
    if owner_confirmation is not True:
        raise ExecutionAdmissionError("owner confirmation required")
    if runtime_opt_in is not True:
        raise ExecutionAdmissionError("runtime opt-in required")
    if not isinstance(now_unix_ms, int) or isinstance(now_unix_ms, bool):
        raise ExecutionAdmissionError("admission time invalid")
    if (
        not isinstance(requested_ttl_ms, int)
        or isinstance(requested_ttl_ms, bool)
        or not 1 <= requested_ttl_ms <= MAX_TTL_MS
    ):
        raise ExecutionAdmissionError("admission ttl invalid")
    return {
        "schema": ADMISSION_SCHEMA,
        "provider_id": PROVIDER_ID,
        "adapter_plan_sha256": _digest(adapter_plan),
        "owner_confirmation": True,
        "runtime_opt_in": True,
        "issued_at_unix_ms": now_unix_ms,
        "expires_at_unix_ms": now_unix_ms + requested_ttl_ms,
        "admission_recorded": True,
        "execution_attempted": False,
        "studio_start_called": False,
        "network_request_sent": False,
        "subprocess_started": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "mcp_registered": False,
        "next_gate": "gate7l_external_execution_attempt",
    }
