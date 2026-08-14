#!/usr/bin/env python3
"""Record a default-off owner runtime-enablement decision without admitting execution."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
OWNER_REVIEW_SCHEMA = "agent_bridge.modelscope_abot_owner_admission_review.v0"
DECISION_SCHEMA = "agent_bridge.modelscope_abot_owner_runtime_enablement_decision.v0"
REVIEW_SCHEMA = "agent_bridge.modelscope_abot_owner_runtime_enablement_decision_review.v0"


class OwnerRuntimeEnablementDecisionError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _validate_gate7s_review(review: Any) -> None:
    if (
        not isinstance(review, dict)
        or review.get("schema") != "agent_bridge.modelscope_abot_runtime_enablement_review.v0"
        or review.get("provider_id") != PROVIDER_ID
        or review.get("status") != "blocked"
        or review.get("review_only") is not True
        or review.get("runtime_enablement_admitted") is not False
        or review.get("runtime_admitted") is not False
    ):
        raise OwnerRuntimeEnablementDecisionError("Gate 7S review invalid or already admitted")
    if not isinstance(review.get("packet_id"), str) or not review["packet_id"]:
        raise OwnerRuntimeEnablementDecisionError("Gate 7S packet binding invalid")


def _validate_decision(decision: Any) -> None:
    if (
        not isinstance(decision, dict)
        or decision.get("schema") != DECISION_SCHEMA
        or decision.get("provider_id") != PROVIDER_ID
        or decision.get("decision") not in {"defer", "reject"}
        or decision.get("authority_issued") is not False
        or decision.get("runtime_enablement_requested") is not False
    ):
        raise OwnerRuntimeEnablementDecisionError(
            "decision must be an explicit defer/reject with no authority"
        )
    if not isinstance(decision.get("decision_id"), str) or not decision["decision_id"]:
        raise OwnerRuntimeEnablementDecisionError("decision id invalid")
    if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
        raise OwnerRuntimeEnablementDecisionError("decision reason invalid")


def review_owner_runtime_enablement_decision(
    *, gate7s_review: dict[str, Any], decision: dict[str, Any]
) -> dict[str, Any]:
    _validate_gate7s_review(gate7s_review)
    _validate_decision(decision)
    outcome = "deferred" if decision["decision"] == "defer" else "rejected"
    return {
        "schema": REVIEW_SCHEMA,
        "provider_id": PROVIDER_ID,
        "decision_id": decision["decision_id"],
        "gate7s_review_sha256": _digest(gate7s_review),
        "decision_sha256": _digest(decision),
        "status": outcome,
        "decision_recorded": True,
        "owner_authorization_issued": False,
        "runtime_enablement_requested": False,
        "runtime_enablement_admitted": False,
        "runtime_implementation_enabled": False,
        "mcp_registered": False,
        "network_dispatcher_enabled": False,
        "subprocess_executor_enabled": False,
        "bearer_token_created": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "review_only": True,
        "next_gate": "gate7u_separate_owner_authorization_receipt",
    }
