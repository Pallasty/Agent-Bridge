#!/usr/bin/env python3
"""Default-off review-only contract for ModelScope runtime authority."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
DISPATCH_REVIEW_SCHEMA = "agent_bridge.modelscope_abot_dispatch_execution_review.v0"
REQUEST_SCHEMA = "agent_bridge.modelscope_abot_runtime_execution_authority_request.v0"
AUTHORITY_REVIEW_SCHEMA = "agent_bridge.modelscope_abot_runtime_authority_review.v0"
ACTION = "start_simulated_projection"
ENDPOINT = "/on_click_start_ws"
SCOPE = "modelscope.abot.external_dispatch"
MAX_TTL_MS = 30_000


class RuntimeAuthorityReviewError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _require_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise RuntimeAuthorityReviewError(f"{label} invalid")


def _validate_dispatch_review(review: Any) -> None:
    if (
        not isinstance(review, dict)
        or review.get("schema") != DISPATCH_REVIEW_SCHEMA
        or review.get("provider_id") != PROVIDER_ID
        or review.get("review_only") is not True
        or review.get("status") != "blocked"
        or review.get("eligible_for_execution") is not False
    ):
        raise RuntimeAuthorityReviewError("dispatch review invalid")
    _require_digest(review.get("dispatch_envelope_sha256"), "dispatch envelope digest")
    if not isinstance(review.get("authorization_id"), str) or not review["authorization_id"]:
        raise RuntimeAuthorityReviewError("authorization binding invalid")
    if review.get("dispatch_authorized") is not False or review.get("execution_authorized") is not False:
        raise RuntimeAuthorityReviewError("dispatch review boundary open")


def _validate_request(request: Any, now_unix_ms: Any) -> None:
    if (
        not isinstance(request, dict)
        or request.get("schema") != REQUEST_SCHEMA
        or request.get("provider_id") != PROVIDER_ID
        or request.get("scope") != SCOPE
        or request.get("action") != ACTION
        or request.get("endpoint") != ENDPOINT
    ):
        raise RuntimeAuthorityReviewError("authority request invalid")
    if not isinstance(request.get("request_id"), str) or re.fullmatch(
        r"[A-Za-z0-9._-]{16,128}", request["request_id"]
    ) is None:
        raise RuntimeAuthorityReviewError("authority request id invalid")
    _require_digest(request.get("dispatch_review_sha256"), "dispatch review digest")
    requested_at = request.get("requested_at_unix_ms")
    requested_ttl = request.get("requested_ttl_ms")
    if (
        not isinstance(now_unix_ms, int)
        or isinstance(now_unix_ms, bool)
        or not isinstance(requested_at, int)
        or isinstance(requested_at, bool)
        or not isinstance(requested_ttl, int)
        or isinstance(requested_ttl, bool)
        or not 1 <= requested_ttl <= MAX_TTL_MS
        or now_unix_ms < requested_at
        or now_unix_ms - requested_at > MAX_TTL_MS
    ):
        raise RuntimeAuthorityReviewError("authority request window invalid")


def review_runtime_authority(
    *,
    dispatch_review: dict[str, Any],
    authority_request: dict[str, Any],
    owner_reauthorized: bool,
    runtime_sandbox_verified: bool,
    secret_custody_verified: bool,
    rollback_verified: bool,
    now_unix_ms: int,
) -> dict[str, Any]:
    _validate_dispatch_review(dispatch_review)
    _validate_request(authority_request, now_unix_ms)
    if authority_request.get("dispatch_review_sha256") != _digest(dispatch_review):
        raise RuntimeAuthorityReviewError("dispatch review binding mismatch")
    checks = {
        "owner_reauthorized": owner_reauthorized,
        "runtime_sandbox_verified": runtime_sandbox_verified,
        "secret_custody_verified": secret_custody_verified,
        "rollback_verified": rollback_verified,
    }
    if any(value is not True for value in checks.values()):
        raise RuntimeAuthorityReviewError("authority review inputs incomplete")
    return {
        "schema": AUTHORITY_REVIEW_SCHEMA,
        "provider_id": PROVIDER_ID,
        "request_id": authority_request["request_id"],
        "scope": SCOPE,
        "dispatch_review_sha256": authority_request["dispatch_review_sha256"],
        "checks": checks,
        "status": "blocked",
        "blockers": ["authority_issuance_requires_separate_owner_decision"],
        "authority_issued": False,
        "bearer_token_created": False,
        "dispatch_authorized": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "network_request_sent": False,
        "subprocess_started": False,
        "studio_start_called": False,
        "mcp_registered": False,
        "review_only": True,
        "next_gate": "gate7r_owner_authorized_runtime_admission_review",
    }
