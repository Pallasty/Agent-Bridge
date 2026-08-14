#!/usr/bin/env python3
"""Validate a bounded, browser-owned ModelScope ABot live activation receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
RECEIPT_SCHEMA = "agent_bridge.modelscope_abot_live_activation_receipt.v0"


class LiveActivationReceiptError(ValueError):
    pass


def _png_dimensions(content: bytes) -> tuple[int, int] | None:
    if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n" or content[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", content[16:24])


def validate_live_activation_receipt(receipt: Any, receipt_path: Path) -> dict[str, Any]:
    violations: list[str] = []
    if not isinstance(receipt, dict):
        raise LiveActivationReceiptError("receipt_not_object")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        violations.append("schema_mismatch")
    if receipt.get("provider_id") != PROVIDER_ID:
        violations.append("provider_id_mismatch")

    authorization = receipt.get("authorization")
    if not isinstance(authorization, dict):
        authorization = {}
        violations.append("authorization_not_object")
    if authorization.get("source") != "interactive_user_instruction":
        violations.append("authorization_source_mismatch")
    if authorization.get("owner_confirmed") is not True:
        violations.append("owner_confirmation_missing")
    if authorization.get("scope") != "one_shot_browser_smoke":
        violations.append("authorization_scope_mismatch")
    if authorization.get("persistent_registration_authorized") is not False:
        violations.append("persistent_registration_authority_open")

    observations = receipt.get("observations")
    if not isinstance(observations, dict):
        observations = {}
        violations.append("observations_not_object")
    for field in (
        "start_observed",
        "gpu_allocated",
        "stream_observed",
        "stop_requested",
        "stop_observed",
        "post_stop_ready",
    ):
        if observations.get(field) is not True:
            violations.append(f"{field}_not_true")
    fps = observations.get("max_observed_fps")
    if not isinstance(fps, (int, float)) or isinstance(fps, bool) or fps <= 0:
        violations.append("positive_fps_required")
    if observations.get("post_stop_iframe_count") != 0:
        violations.append("post_stop_iframe_count_not_zero")

    execution = receipt.get("execution")
    if not isinstance(execution, dict):
        execution = {}
        violations.append("execution_not_object")
    for field in ("network_request_sent", "studio_start_called", "execution_attempted"):
        if execution.get(field) is not True:
            violations.append(f"{field}_not_true")
    for field in ("runtime_admitted", "mcp_registered", "persistent_runtime"):
        if execution.get(field) is not False:
            violations.append(f"{field}_must_be_false")

    artifact = receipt.get("artifact")
    if not isinstance(artifact, dict):
        artifact = {}
        violations.append("artifact_not_object")
    artifact_ref = artifact.get("ref")
    if not isinstance(artifact_ref, str) or not artifact_ref:
        violations.append("artifact_ref_missing")
    else:
        evidence_root = receipt_path.resolve().parent
        artifact_path = (evidence_root / artifact_ref).resolve()
        if artifact_path.parent != evidence_root:
            violations.append("artifact_ref_outside_evidence_root")
        elif not artifact_path.is_file():
            violations.append("artifact_file_missing")
        else:
            content = artifact_path.read_bytes()
            if hashlib.sha256(content).hexdigest() != artifact.get("sha256"):
                violations.append("artifact_sha256_mismatch")
            if len(content) != artifact.get("bytes"):
                violations.append("artifact_size_mismatch")
            if _png_dimensions(content) != (artifact.get("width"), artifact.get("height")):
                violations.append("artifact_dimensions_mismatch")
    if artifact.get("content_type") != "image/png":
        violations.append("artifact_content_type_mismatch")
    if artifact.get("evidence_type") != "presentation_screenshot":
        violations.append("artifact_evidence_type_mismatch")

    valid = not violations
    return {
        "schema": "agent_bridge.modelscope_abot_live_activation_validation.v0",
        "provider_id": PROVIDER_ID,
        "valid": valid,
        "violations": violations,
        "live_activation_verified": valid,
        "lifecycle_closed": valid,
        "provider_native_artifact_bound": False,
        "runtime_admitted": False,
        "mcp_registered": False,
        "persistent_runtime": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text())
    result = validate_live_activation_receipt(receipt, args.receipt)
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
