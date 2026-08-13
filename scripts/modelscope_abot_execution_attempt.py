#!/usr/bin/env python3
"""Non-actuating execution-attempt preflight for ModelScope ABot."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
PLAN_SCHEMA = "agent_bridge.modelscope_abot_external_adapter_plan.v0"
ADMISSION_SCHEMA = "agent_bridge.modelscope_abot_execution_admission.v0"
ATTEMPT_SCHEMA = "agent_bridge.modelscope_abot_execution_attempt.v0"
MAX_TIMEOUT_MS = 30_000


class ExecutionAttemptError(ValueError):
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


def prepare_attempt(
    *,
    adapter_plan: dict[str, Any],
    admission_receipt: dict[str, Any],
    attempt_id: str,
    now_unix_ms: int,
    timeout_ms: int,
) -> dict[str, Any]:
    if (
        not isinstance(adapter_plan, dict)
        or adapter_plan.get("schema") != PLAN_SCHEMA
        or adapter_plan.get("provider_id") != PROVIDER_ID
        or adapter_plan.get("plan_only") is not True
    ):
        raise ExecutionAttemptError("adapter plan invalid")
    adapter_digest = _digest(adapter_plan)
    if (
        not isinstance(admission_receipt, dict)
        or admission_receipt.get("schema") != ADMISSION_SCHEMA
        or admission_receipt.get("provider_id") != PROVIDER_ID
        or admission_receipt.get("adapter_plan_sha256") != adapter_digest
        or admission_receipt.get("admission_recorded") is not True
        or admission_receipt.get("owner_confirmation") is not True
        or admission_receipt.get("runtime_opt_in") is not True
    ):
        raise ExecutionAttemptError("admission receipt invalid")
    if any(
        admission_receipt.get(field) is not False
        for field in (
            "execution_attempted",
            "studio_start_called",
            "network_request_sent",
            "subprocess_started",
            "runtime_admitted",
            "mcp_registered",
        )
    ):
        raise ExecutionAttemptError("admission boundary open")
    if not isinstance(attempt_id, str) or re.fullmatch(
        r"[A-Za-z0-9._-]{16,128}", attempt_id
    ) is None:
        raise ExecutionAttemptError("attempt id invalid")
    if not isinstance(now_unix_ms, int) or isinstance(now_unix_ms, bool):
        raise ExecutionAttemptError("time invalid")
    expires_at = admission_receipt.get("expires_at_unix_ms")
    if (
        not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
        or now_unix_ms >= expires_at
    ):
        raise ExecutionAttemptError("admission expired")
    if (
        not isinstance(timeout_ms, int)
        or isinstance(timeout_ms, bool)
        or not 1 <= timeout_ms <= MAX_TIMEOUT_MS
        or now_unix_ms + timeout_ms > expires_at
    ):
        raise ExecutionAttemptError("timeout invalid")
    return {
        "schema": ATTEMPT_SCHEMA,
        "provider_id": PROVIDER_ID,
        "attempt_id": attempt_id,
        "adapter_plan_sha256": adapter_digest,
        "admission_receipt_sha256": _digest(admission_receipt),
        "prepared_at_unix_ms": now_unix_ms,
        "expires_at_unix_ms": now_unix_ms + timeout_ms,
        "preflight_only": True,
        "network_request_sent": False,
        "subprocess_started": False,
        "studio_start_called": False,
        "execution_attempted": False,
        "runtime_admitted": False,
        "mcp_registered": False,
        "next_gate": "gate7m_external_execution_commit",
    }
