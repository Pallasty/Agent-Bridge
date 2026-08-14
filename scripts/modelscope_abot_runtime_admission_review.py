#!/usr/bin/env python3
"""Review runtime admission evidence without activating or executing the runtime."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
GATE7U_SCHEMA = "agent_bridge.modelscope_abot_owner_runtime_authorization_receipt_review.v0"
GATE7V_SCHEMA = "agent_bridge.modelscope_abot_independent_runtime_implementation_review.v0"
ADMISSION_SCHEMA = "agent_bridge.modelscope_abot_runtime_admission_request.v0"
REVIEW_SCHEMA = "agent_bridge.modelscope_abot_runtime_admission_review.v0"


class RuntimeAdmissionReviewError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _validate_gate7u(review: Any) -> None:
    if (
        not isinstance(review, dict)
        or review.get("schema") != GATE7U_SCHEMA
        or review.get("provider_id") != PROVIDER_ID
        or review.get("review_only") is not True
        or review.get("runtime_admitted") is not False
    ):
        raise RuntimeAdmissionReviewError("Gate 7U review invalid")


def _validate_gate7v(review: Any) -> None:
    if (
        not isinstance(review, dict)
        or review.get("schema") != GATE7V_SCHEMA
        or review.get("provider_id") != PROVIDER_ID
        or review.get("review_only") is not True
        or review.get("runtime_admitted") is not False
    ):
        raise RuntimeAdmissionReviewError("Gate 7V review invalid")


def _validate_request(request: Any) -> None:
    if (
        not isinstance(request, dict)
        or request.get("schema") != ADMISSION_SCHEMA
        or request.get("provider_id") != PROVIDER_ID
        or request.get("default_off") is not True
        or request.get("dry_run_only") is not True
        or request.get("runtime_admitted") is not False
        or request.get("execution_authorized") is not False
    ):
        raise RuntimeAdmissionReviewError("admission request invalid or open")
    if not isinstance(request.get("request_id"), str) or not request["request_id"]:
        raise RuntimeAdmissionReviewError("admission request id invalid")
    if not isinstance(request.get("admission_requested"), bool):
        raise RuntimeAdmissionReviewError("admission request flag invalid")
    for field in (
        "mcp_registration_enabled",
        "network_dispatcher_enabled",
        "subprocess_executor_enabled",
        "bearer_token_created",
    ):
        if request.get(field) is not False:
            raise RuntimeAdmissionReviewError(f"admission execution surface open: {field}")


def review_runtime_admission(
    *, gate7u_review: dict[str, Any], gate7v_review: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    _validate_gate7u(gate7u_review)
    _validate_gate7v(gate7v_review)
    _validate_request(request)
    blockers = []
    if request["admission_requested"] is not True:
        blockers.append("runtime_admission_not_requested")
    if gate7u_review.get("authorization_receipt_validated") is not True:
        blockers.append("owner_authorization_receipt_not_validated")
    if gate7v_review.get("implementation_review_passed") is not True:
        blockers.append("runtime_implementation_review_not_passed")
    status = "review_passed_blocked" if not blockers else "blocked"
    return {
        "schema": REVIEW_SCHEMA,
        "provider_id": PROVIDER_ID,
        "request_id": request["request_id"],
        "gate7u_review_sha256": _digest(gate7u_review),
        "gate7v_review_sha256": _digest(gate7v_review),
        "request_sha256": _digest(request),
        "status": status,
        "blockers": blockers or ["activation_requires_separate_gate"],
        "admission_review_passed": not blockers,
        "admission_requested": request["admission_requested"],
        "runtime_enablement_admitted": False,
        "runtime_implementation_enabled": False,
        "mcp_registered": False,
        "network_dispatcher_enabled": False,
        "subprocess_executor_enabled": False,
        "bearer_token_created": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "review_only": True,
        "next_gate": "gate7x_separate_runtime_activation_decision",
    }
