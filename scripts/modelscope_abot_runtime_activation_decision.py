#!/usr/bin/env python3
"""Record a default-off runtime activation decision without activating anything."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
GATE7W_SCHEMA = "agent_bridge.modelscope_abot_runtime_admission_review.v0"
DECISION_SCHEMA = "agent_bridge.modelscope_abot_runtime_activation_decision.v0"
REVIEW_SCHEMA = "agent_bridge.modelscope_abot_runtime_activation_decision_review.v0"


class RuntimeActivationDecisionError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _validate_gate7w_review(review: Any) -> None:
    if (
        not isinstance(review, dict)
        or review.get("schema") != GATE7W_SCHEMA
        or review.get("provider_id") != PROVIDER_ID
        or review.get("status") not in {"blocked", "review_passed_blocked"}
        or review.get("review_only") is not True
        or review.get("runtime_admitted") is not False
        or review.get("execution_authorized") is not False
    ):
        raise RuntimeActivationDecisionError("Gate 7W review invalid or already active")


def _validate_decision(decision: Any) -> None:
    if (
        not isinstance(decision, dict)
        or decision.get("schema") != DECISION_SCHEMA
        or decision.get("provider_id") != PROVIDER_ID
        or decision.get("decision") not in {"defer", "reject"}
        or decision.get("authority_issued") is not False
        or decision.get("activation_requested") is not False
        or decision.get("execution_authorized") is not False
    ):
        raise RuntimeActivationDecisionError(
            "activation decision must be an explicit defer/reject with no authority"
        )
    if not isinstance(decision.get("decision_id"), str) or not decision["decision_id"]:
        raise RuntimeActivationDecisionError("activation decision id invalid")
    if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
        raise RuntimeActivationDecisionError("activation decision reason invalid")


def review_runtime_activation_decision(
    *, gate7w_review: dict[str, Any], decision: dict[str, Any]
) -> dict[str, Any]:
    _validate_gate7w_review(gate7w_review)
    _validate_decision(decision)
    outcome = "deferred" if decision["decision"] == "defer" else "rejected"
    return {
        "schema": REVIEW_SCHEMA,
        "provider_id": PROVIDER_ID,
        "decision_id": decision["decision_id"],
        "gate7w_review_sha256": _digest(gate7w_review),
        "decision_sha256": _digest(decision),
        "status": outcome,
        "decision_recorded": True,
        "activation_requested": False,
        "activation_admitted": False,
        "owner_authorization_issued": False,
        "runtime_enablement_admitted": False,
        "runtime_implementation_enabled": False,
        "mcp_registered": False,
        "network_dispatcher_enabled": False,
        "subprocess_executor_enabled": False,
        "bearer_token_created": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "review_only": True,
        "next_gate": "gate7y_explicit_owner_activation_authorization_receipt",
    }
