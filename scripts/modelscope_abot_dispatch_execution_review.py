#!/usr/bin/env python3
"""Default-off review gate for external ModelScope dispatch execution."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
PROPOSAL_SCHEMA = "agent_bridge.modelscope_abot_dispatch_authorization_proposal.v0"
REVIEW_SCHEMA = "agent_bridge.modelscope_abot_dispatch_execution_review.v0"
ACTION = "start_simulated_projection"
ENDPOINT = "/on_click_start_ws"
MAX_TTL_MS = 30_000


class DispatchExecutionReviewError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _require_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise DispatchExecutionReviewError(f"{label} invalid")


def _validate_proposal(proposal: Any, now_unix_ms: Any) -> None:
    if (
        not isinstance(proposal, dict)
        or proposal.get("schema") != PROPOSAL_SCHEMA
        or proposal.get("provider_id") != PROVIDER_ID
        or proposal.get("plan_only") is not True
        or proposal.get("authorization_proposed") is not True
    ):
        raise DispatchExecutionReviewError("authorization proposal invalid")
    _require_digest(proposal.get("dispatch_envelope_sha256"), "dispatch envelope digest")
    for field in ("authorization_id", "attempt_id"):
        if not isinstance(proposal.get(field), str) or not proposal[field]:
            raise DispatchExecutionReviewError("authorization binding invalid")
    if proposal.get("action") != ACTION or proposal.get("endpoint") != ENDPOINT:
        raise DispatchExecutionReviewError("authorization target invalid")
    for field in (
        "dispatch_authorized",
        "dispatch_performed",
        "network_request_sent",
        "subprocess_started",
        "studio_start_called",
        "execution_authorized",
        "runtime_admitted",
        "mcp_registered",
    ):
        if proposal.get(field) is not False:
            raise DispatchExecutionReviewError("authorization boundary open")
    issued_at = proposal.get("issued_at_unix_ms")
    expires_at = proposal.get("expires_at_unix_ms")
    if (
        not isinstance(now_unix_ms, int)
        or isinstance(now_unix_ms, bool)
        or not isinstance(issued_at, int)
        or isinstance(issued_at, bool)
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
        or issued_at >= expires_at
        or expires_at - issued_at > MAX_TTL_MS
        or now_unix_ms < issued_at
        or now_unix_ms >= expires_at
    ):
        raise DispatchExecutionReviewError("authorization proposal expired")


def review_dispatch_execution(
    *,
    authorization_proposal: dict[str, Any],
    provider_live_verified: bool,
    runtime_config_verified: bool,
    network_policy_verified: bool,
    owner_authority_bound: bool,
    now_unix_ms: int,
) -> dict[str, Any]:
    _validate_proposal(authorization_proposal, now_unix_ms)
    checks = {
        "provider_live_verified": provider_live_verified,
        "runtime_config_verified": runtime_config_verified,
        "network_policy_verified": network_policy_verified,
        "owner_authority_bound": owner_authority_bound,
    }
    if any(value is not True for value in checks.values()):
        raise DispatchExecutionReviewError("review inputs incomplete")
    # This gate records readiness evidence only; it never grants dispatch.
    blockers = ["separate_runtime_execution_authority_required"]
    return {
        "schema": REVIEW_SCHEMA,
        "provider_id": PROVIDER_ID,
        "authorization_id": authorization_proposal["authorization_id"],
        "dispatch_envelope_sha256": authorization_proposal["dispatch_envelope_sha256"],
        "checks": checks,
        "status": "blocked",
        "blockers": blockers,
        "eligible_for_execution": False,
        "dispatch_authorized": False,
        "dispatch_performed": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "network_request_sent": False,
        "subprocess_started": False,
        "studio_start_called": False,
        "mcp_registered": False,
        "review_only": True,
        "next_gate": "gate7q_separate_runtime_execution_authority_review",
    }
