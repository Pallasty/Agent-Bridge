#!/usr/bin/env python3
"""Default-off, non-actuating external execution admission for ModelScope ABot."""
from __future__ import annotations
import hashlib, json
from typing import Any
PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
PLAN_SCHEMA = "agent_bridge.modelscope_abot_external_adapter_plan.v0"
ADMISSION_SCHEMA = "agent_bridge.modelscope_abot_execution_admission.v0"
MAX_TTL_MS = 30_000
class ExecutionAdmissionError(ValueError): pass
def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
def admit_execution(*, adapter_plan: dict[str, Any], owner_confirmation: bool, runtime_opt_in: bool, requested_ttl_ms: int = MAX_TTL_MS) -> dict[str, Any]:
    if not isinstance(adapter_plan, dict) or adapter_plan.get("schema") != PLAN_SCHEMA or adapter_plan.get("provider_id") != PROVIDER_ID: raise ExecutionAdmissionError("adapter plan invalid")
    if adapter_plan.get("plan_only") is not True: raise ExecutionAdmissionError("adapter plan not plan-only")
    if adapter_plan.get("network_allowed") is True or adapter_plan.get("subprocess_allowed") is True: raise ExecutionAdmissionError("adapter boundary open")
    if owner_confirmation is not True: raise ExecutionAdmissionError("owner confirmation required")
    if runtime_opt_in is not True: raise ExecutionAdmissionError("runtime opt-in required")
    if not isinstance(requested_ttl_ms, int) or isinstance(requested_ttl_ms, bool) or not 1 <= requested_ttl_ms <= MAX_TTL_MS: raise ExecutionAdmissionError("admission ttl invalid")
    return {"schema": ADMISSION_SCHEMA, "provider_id": PROVIDER_ID, "adapter_plan_sha256": _digest(adapter_plan), "owner_confirmation": True, "runtime_opt_in": True, "expires_in_ms": requested_ttl_ms, "admission_recorded": True, "execution_attempted": False, "studio_start_called": False, "network_request_sent": False, "subprocess_started": False, "runtime_admitted": False, "mcp_registered": False, "next_gate": "gate7l_external_execution_attempt"}
