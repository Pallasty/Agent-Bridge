#!/usr/bin/env python3
"""Default-off review-only validation for an owner admission packet."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
Q_REVIEW_SCHEMA = "agent_bridge.modelscope_abot_runtime_authority_review.v0"
PACKET_SCHEMA = "agent_bridge.modelscope_abot_owner_runtime_admission_packet.v0"
REVIEW_SCHEMA = "agent_bridge.modelscope_abot_owner_admission_review.v0"
ACTION = "start_simulated_projection"
ENDPOINT = "/on_click_start_ws"
SCOPE = "modelscope.abot.external_dispatch"
MAX_TTL_MS = 30_000


class OwnerAdmissionReviewError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _require_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise OwnerAdmissionReviewError(f"{label} invalid")


def _validate_q_review(q_review: Any) -> None:
    if (
        not isinstance(q_review, dict)
        or q_review.get("schema") != Q_REVIEW_SCHEMA
        or q_review.get("provider_id") != PROVIDER_ID
        or q_review.get("status") != "blocked"
        or q_review.get("review_only") is not True
        or q_review.get("authority_issued") is not False
    ):
        raise OwnerAdmissionReviewError("authority review invalid")
    if not isinstance(q_review.get("request_id"), str) or not q_review["request_id"]:
        raise OwnerAdmissionReviewError("authority review binding invalid")


def _validate_packet(packet: Any, now_unix_ms: Any) -> None:
    if (
        not isinstance(packet, dict)
        or packet.get("schema") != PACKET_SCHEMA
        or packet.get("provider_id") != PROVIDER_ID
        or packet.get("scope") != SCOPE
        or packet.get("action") != ACTION
        or packet.get("endpoint") != ENDPOINT
        or packet.get("owner_authorized") is not True
        or packet.get("runtime_admitted") is not False
    ):
        raise OwnerAdmissionReviewError("admission packet invalid")
    if not isinstance(packet.get("packet_id"), str) or re.fullmatch(
        r"[A-Za-z0-9._-]{16,128}", packet["packet_id"]
    ) is None:
        raise OwnerAdmissionReviewError("admission packet id invalid")
    if not isinstance(packet.get("owner_decision_id"), str) or not packet["owner_decision_id"]:
        raise OwnerAdmissionReviewError("owner decision binding invalid")
    _require_digest(packet.get("owner_decision_sha256"), "owner decision digest")
    _require_digest(packet.get("authority_review_sha256"), "authority review digest")
    issued_at = packet.get("issued_at_unix_ms")
    expires_at = packet.get("expires_at_unix_ms")
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
        raise OwnerAdmissionReviewError("admission packet expired")
    for field in (
        "authority_issued",
        "bearer_token_created",
        "dispatch_authorized",
        "execution_authorized",
        "network_request_sent",
        "subprocess_started",
        "studio_start_called",
        "mcp_registered",
    ):
        if packet.get(field) is not False:
            raise OwnerAdmissionReviewError("admission packet boundary open")


def review_owner_admission_packet(
    *, q_review: dict[str, Any], admission_packet: dict[str, Any], now_unix_ms: int
) -> dict[str, Any]:
    _validate_q_review(q_review)
    _validate_packet(admission_packet, now_unix_ms)
    if admission_packet["authority_review_sha256"] != _digest(q_review):
        raise OwnerAdmissionReviewError("authority review binding mismatch")
    return {
        "schema": REVIEW_SCHEMA,
        "provider_id": PROVIDER_ID,
        "packet_id": admission_packet["packet_id"],
        "owner_decision_id": admission_packet["owner_decision_id"],
        "authority_review_sha256": admission_packet["authority_review_sha256"],
        "status": "blocked",
        "admission_packet_valid": True,
        "blockers": ["runtime_enablement_not_implemented_in_projection_gate"],
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
        "next_gate": "gate7s_runtime_enablement_implementation_review",
    }
