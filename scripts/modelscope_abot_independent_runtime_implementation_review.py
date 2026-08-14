#!/usr/bin/env python3
"""Review a proposed runtime implementation contract without admitting execution."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
GATE7U_SCHEMA = "agent_bridge.modelscope_abot_owner_runtime_authorization_receipt_review.v0"
IMPLEMENTATION_SCHEMA = "agent_bridge.modelscope_abot_runtime_implementation_candidate.v0"
REVIEW_SCHEMA = "agent_bridge.modelscope_abot_independent_runtime_implementation_review.v0"

REQUIRED_CONTROLS = (
    "default_off",
    "review_only_path",
    "capability_allowlist",
    "audit_receipts",
    "rollback_plan",
    "tests_present",
    "network_dispatcher_guard",
    "subprocess_executor_guard",
    "mcp_registration_guard",
    "bearer_token_custody_guard",
)


class IndependentRuntimeImplementationReviewError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _validate_gate7u_review(review: Any) -> None:
    if (
        not isinstance(review, dict)
        or review.get("schema") != GATE7U_SCHEMA
        or review.get("provider_id") != PROVIDER_ID
        or review.get("status") not in {"blocked_missing_receipt", "blocked_implementation_gate"}
        or review.get("review_only") is not True
        or review.get("runtime_admitted") is not False
    ):
        raise IndependentRuntimeImplementationReviewError(
            "Gate 7U review invalid or runtime already admitted"
        )


def _validate_candidate(candidate: Any) -> None:
    if (
        not isinstance(candidate, dict)
        or candidate.get("schema") != IMPLEMENTATION_SCHEMA
        or candidate.get("provider_id") != PROVIDER_ID
        or candidate.get("runtime_admission_present") is not False
    ):
        raise IndependentRuntimeImplementationReviewError("implementation candidate invalid")
    if not isinstance(candidate.get("implementation_id"), str) or not candidate["implementation_id"]:
        raise IndependentRuntimeImplementationReviewError("implementation id invalid")
    if not isinstance(candidate.get("implementation_present"), bool):
        raise IndependentRuntimeImplementationReviewError("implementation presence invalid")
    for control in REQUIRED_CONTROLS:
        if not isinstance(candidate.get(control), bool):
            raise IndependentRuntimeImplementationReviewError(f"control missing: {control}")


def review_independent_runtime_implementation(
    *, gate7u_review: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    _validate_gate7u_review(gate7u_review)
    _validate_candidate(candidate)
    missing_controls = [control for control in REQUIRED_CONTROLS if not candidate[control]]
    if not candidate["implementation_present"]:
        status = "blocked_implementation_absent"
        blockers = ["runtime_implementation_not_present"]
        passed = False
    elif missing_controls:
        status = "blocked_controls_incomplete"
        blockers = [f"runtime_control_missing:{control}" for control in missing_controls]
        passed = False
    else:
        status = "review_passed_blocked"
        blockers = ["runtime_admission_requires_separate_gate"]
        passed = True
    return {
        "schema": REVIEW_SCHEMA,
        "provider_id": PROVIDER_ID,
        "implementation_id": candidate["implementation_id"],
        "gate7u_review_sha256": _digest(gate7u_review),
        "candidate_sha256": _digest(candidate),
        "status": status,
        "blockers": blockers,
        "implementation_review_passed": passed,
        "runtime_admission_present": False,
        "runtime_enablement_admitted": False,
        "runtime_implementation_enabled": False,
        "mcp_registered": False,
        "network_dispatcher_enabled": False,
        "subprocess_executor_enabled": False,
        "bearer_token_created": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "review_only": True,
        "next_gate": "gate7w_separate_runtime_admission_review",
    }
