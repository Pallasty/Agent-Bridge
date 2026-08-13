#!/usr/bin/env python3
"""Default-off, non-actuating external execution admission for ModelScope ABot."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
PLAN_SCHEMA = "agent_bridge.modelscope_abot_external_adapter_plan.v0"
ADMISSION_SCHEMA = "agent_bridge.modelscope_abot_execution_admission.v0"
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


def admit_execution(
    *,
    adapter_plan: dict[str, Any],
    owner_confirmation: bool,
    runtime_opt_in: bool,
    now_unix_ms: int,
    requested_ttl_ms: int = MAX_TTL_MS,
) -> dict[str, Any]:
    if (
        not isinstance(adapter_plan, dict)
        or adapter_plan.get("schema") != PLAN_SCHEMA
        or adapter_plan.get("provider_id") != PROVIDER_ID
        or adapter_plan.get("plan_only") is not True
    ):
        raise ExecutionAdmissionError("adapter plan invalid")
    adapter = adapter_plan.get("adapter")
    if (
        not isinstance(adapter, dict)
        or adapter.get("network_allowed") is not False
        or adapter.get("subprocess_allowed") is not False
    ):
        raise ExecutionAdmissionError("adapter boundary open")
    if any(
        adapter_plan.get(field) is not False
        for field in (
            "execution_capability_issued",
            "studio_start_called",
            "execution_authorized",
            "runtime_admitted",
            "mcp_registered",
        )
    ):
        raise ExecutionAdmissionError("adapter boundary open")
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
        "runtime_admitted": False,
        "mcp_registered": False,
        "next_gate": "gate7l_external_execution_attempt",
    }
