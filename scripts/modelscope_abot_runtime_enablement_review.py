#!/usr/bin/env python3
"""Static, default-off review of a ModelScope runtime enablement manifest."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
OWNER_REVIEW_SCHEMA = "agent_bridge.modelscope_abot_owner_admission_review.v0"
MANIFEST_SCHEMA = "agent_bridge.modelscope_abot_runtime_enablement_manifest.v0"
REVIEW_SCHEMA = "agent_bridge.modelscope_abot_runtime_enablement_review.v0"


class RuntimeEnablementReviewError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _validate_owner_review(owner_review: Any) -> None:
    if (
        not isinstance(owner_review, dict)
        or owner_review.get("schema") != OWNER_REVIEW_SCHEMA
        or owner_review.get("provider_id") != PROVIDER_ID
        or owner_review.get("status") != "blocked"
        or owner_review.get("review_only") is not True
        or owner_review.get("authority_issued") is not False
    ):
        raise RuntimeEnablementReviewError("owner admission review invalid")
    if not isinstance(owner_review.get("packet_id"), str) or not owner_review["packet_id"]:
        raise RuntimeEnablementReviewError("owner admission binding invalid")


def _validate_manifest(manifest: Any) -> None:
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != MANIFEST_SCHEMA
        or manifest.get("provider_id") != PROVIDER_ID
        or manifest.get("default_off") is not True
        or manifest.get("dry_run_only") is not True
    ):
        raise RuntimeEnablementReviewError("enablement manifest invalid")
    if not isinstance(manifest.get("manifest_id"), str) or not manifest["manifest_id"]:
        raise RuntimeEnablementReviewError("enablement manifest id invalid")
    for field in (
        "runtime_implementation_present",
        "mcp_registration_present",
        "network_dispatcher_present",
        "subprocess_executor_present",
        "bearer_token_custody_present",
    ):
        if manifest.get(field) is not False:
            raise RuntimeEnablementReviewError("enablement surface open")
    if manifest.get("caller_count") != 0 or manifest.get("allowlist") != []:
        raise RuntimeEnablementReviewError("enablement caller surface open")


def review_runtime_enablement(
    *, owner_review: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    _validate_owner_review(owner_review)
    _validate_manifest(manifest)
    return {
        "schema": REVIEW_SCHEMA,
        "provider_id": PROVIDER_ID,
        "packet_id": owner_review["packet_id"],
        "owner_review_sha256": _digest(owner_review),
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": _digest(manifest),
        "status": "blocked",
        "implementation_review_passed": True,
        "blockers": ["runtime_enablement_requires_separate_implementation_authority"],
        "runtime_enablement_admitted": False,
        "runtime_implementation_enabled": False,
        "mcp_registered": False,
        "network_dispatcher_enabled": False,
        "subprocess_executor_enabled": False,
        "bearer_token_created": False,
        "execution_authorized": False,
        "runtime_admitted": False,
        "review_only": True,
        "next_gate": "gate7t_owner_authorized_runtime_enablement_decision",
    }
