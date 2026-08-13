#!/usr/bin/env python3
"""Default-off, non-actuating external adapter boundary for ModelScope ABot."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
PLAN_SCHEMA = "agent_bridge.modelscope_abot_external_adapter_plan.v0"
CONTRACT_SCHEMA = "agent_bridge.modelscope_abot_execution_capability_contract.v0"
CONSUMPTION_SCHEMA = "agent_bridge.modelscope_abot_activation_consumption.v0"
ACTION = "start_simulated_projection"
ENDPOINT = "/on_click_start_ws"
MAX_TIMEOUT_MS = 30_000


class ExternalAdapterError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def prepare_adapter_plan(
    *,
    activation_receipt: dict[str, Any],
    capability_contract: dict[str, Any],
    requested_timeout_ms: int = MAX_TIMEOUT_MS,
) -> dict[str, Any]:
    if (
        not isinstance(activation_receipt, dict)
        or activation_receipt.get("schema") != CONSUMPTION_SCHEMA
        or activation_receipt.get("provider_id") != PROVIDER_ID
    ):
        raise ExternalAdapterError("activation receipt invalid")
    if activation_receipt.get("activation_consumed") is not True:
        raise ExternalAdapterError("activation not consumed")
    if activation_receipt.get("capability_validated") is not True or activation_receipt.get("activation_reference_validated") is not True:
        raise ExternalAdapterError("activation validation incomplete")
    if any(
        activation_receipt.get(field) is not False
        for field in (
            "execution_capability_issued",
            "studio_start_called",
            "execution_authorized",
            "runtime_admitted",
            "mcp_registered",
        )
    ):
        raise ExternalAdapterError("activation boundary open")
    if (
        not isinstance(capability_contract, dict)
        or capability_contract.get("schema") != CONTRACT_SCHEMA
        or capability_contract.get("provider_id") != PROVIDER_ID
    ):
        raise ExternalAdapterError("capability contract invalid")
    if capability_contract.get("capability_id") != activation_receipt.get("capability_id"):
        raise ExternalAdapterError("capability binding mismatch")
    capability_digest = _digest(capability_contract)
    if capability_digest != activation_receipt.get("capability_sha256"):
        raise ExternalAdapterError("capability digest mismatch")
    if activation_receipt.get("activation_id") in (None, ""):
        raise ExternalAdapterError("activation id missing")
    if not isinstance(requested_timeout_ms, int) or isinstance(requested_timeout_ms, bool) or not 1 <= requested_timeout_ms <= MAX_TIMEOUT_MS:
        raise ExternalAdapterError("adapter timeout invalid")
    operation = capability_contract.get("operation")
    if (
        not isinstance(operation, dict)
        or set(operation) != {"action", "endpoint", "prompt_sha256"}
        or operation.get("action") != ACTION
        or operation.get("endpoint") != ENDPOINT
        or not isinstance(operation.get("prompt_sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", operation["prompt_sha256"]) is None
    ):
        raise ExternalAdapterError("adapter operation invalid")
    return {
        "schema": PLAN_SCHEMA,
        "provider_id": PROVIDER_ID,
        "activation_id": activation_receipt["activation_id"],
        "capability_id": capability_contract["capability_id"],
        "capability_sha256": capability_digest,
        "capability_digest_bound": True,
        "adapter": {
            "action": ACTION,
            "endpoint": ENDPOINT,
            "timeout_ms": requested_timeout_ms,
            "network_allowed": False,
            "subprocess_allowed": False,
        },
        "execution_capability_issued": False,
        "studio_start_called": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "mcp_registered": False,
        "plan_only": True,
        "next_gate": "gate7k_external_adapter_execution_admission",
    }
