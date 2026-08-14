#!/usr/bin/env python3
"""Review an owner authorization receipt without converting it into execution authority."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
GATE7T_SCHEMA = "agent_bridge.modelscope_abot_owner_runtime_enablement_decision_review.v0"
RECEIPT_SCHEMA = "agent_bridge.modelscope_abot_owner_runtime_authorization_receipt.v0"
REVIEW_SCHEMA = "agent_bridge.modelscope_abot_owner_runtime_authorization_receipt_review.v0"


class OwnerRuntimeAuthorizationReceiptError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _validate_gate7t_review(review: Any) -> None:
    if (
        not isinstance(review, dict)
        or review.get("schema") != GATE7T_SCHEMA
        or review.get("provider_id") != PROVIDER_ID
        or review.get("status") not in {"deferred", "rejected"}
        or review.get("review_only") is not True
        or review.get("runtime_admitted") is not False
    ):
        raise OwnerRuntimeAuthorizationReceiptError("Gate 7T review invalid or already admitted")


def _validate_receipt(receipt: Any) -> None:
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != RECEIPT_SCHEMA
        or receipt.get("provider_id") != PROVIDER_ID
        or receipt.get("status") not in {"absent", "issued"}
        or receipt.get("execution_authorized") is not False
    ):
        raise OwnerRuntimeAuthorizationReceiptError(
            "authorization receipt must be absent or issued and never execution-authorized"
        )
    if not isinstance(receipt.get("receipt_id"), str) or not receipt["receipt_id"]:
        raise OwnerRuntimeAuthorizationReceiptError("authorization receipt id invalid")
    if receipt["status"] == "absent":
        if receipt.get("authority_issued") is not False:
            raise OwnerRuntimeAuthorizationReceiptError("absent receipt cannot issue authority")
        return
    for field in ("owner_principal", "issued_at", "scope"):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip():
            raise OwnerRuntimeAuthorizationReceiptError("issued receipt binding invalid")
    if receipt.get("authority_issued") is not True:
        raise OwnerRuntimeAuthorizationReceiptError("issued receipt must declare authority")
    if receipt.get("runtime_enablement_authorized") is not True:
        raise OwnerRuntimeAuthorizationReceiptError("issued receipt scope invalid")


def review_owner_runtime_authorization_receipt(
    *, gate7t_review: dict[str, Any], receipt: dict[str, Any]
) -> dict[str, Any]:
    _validate_gate7t_review(gate7t_review)
    _validate_receipt(receipt)
    if receipt["status"] == "absent":
        status = "blocked_missing_receipt"
        blocker = "owner_authorization_receipt_missing"
    else:
        status = "blocked_implementation_gate"
        blocker = "authorization_does_not_admit_unimplemented_runtime"
    return {
        "schema": REVIEW_SCHEMA,
        "provider_id": PROVIDER_ID,
        "receipt_id": receipt["receipt_id"],
        "gate7t_review_sha256": _digest(gate7t_review),
        "receipt_sha256": _digest(receipt),
        "status": status,
        "blockers": [blocker],
        "authorization_receipt_validated": receipt["status"] == "issued",
        "owner_authorization_issued": receipt["authority_issued"],
        "runtime_enablement_admitted": False,
        "runtime_implementation_enabled": False,
        "mcp_registered": False,
        "network_dispatcher_enabled": False,
        "subprocess_executor_enabled": False,
        "bearer_token_created": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "review_only": True,
        "next_gate": "gate7v_independent_runtime_implementation_review",
    }
