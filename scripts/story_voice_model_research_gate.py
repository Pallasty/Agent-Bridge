#!/usr/bin/env python3
"""Static, fail-closed S5D research gate for voice models and MI50 containers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40,64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_mi50_container(config_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(config_path),
        "exists": config_path.is_file(),
        "sha256": None,
        "status": "blocked",
        "execution_attempted": False,
        "observed_gfx_override": None,
        "image_digest_pinned": False,
        "network_disabled": False,
        "read_only_rootfs": False,
        "blockers": [],
    }
    if not config_path.is_file():
        result["blockers"].append("container_config_missing")
        return result

    text = config_path.read_text()
    active_text = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    result["sha256"] = sha256_file(config_path)
    gfx_match = re.search(
        r"HSA_OVERRIDE_GFX_VERSION\s*=\s*([0-9.]+)", active_text
    )
    if gfx_match:
        result["observed_gfx_override"] = gfx_match.group(1)

    lower = active_text.lower()
    if re.search(r"(?m)^\s*privileged\s*:\s*true\s*$", lower):
        result["blockers"].append("privileged_container")
    if "/dev/kfd:/dev/kfd" not in active_text:
        result["blockers"].append("missing_explicit_kfd_mapping")
    if "/dev/dri/renderD129:/dev/dri/renderD129" not in active_text:
        result["blockers"].append("missing_explicit_mi50_render_node")
    if "/dev/dri:/dev/dri" in active_text:
        result["blockers"].append("broad_dri_mapping")
    if "/dev/dri/renderD128" in active_text:
        result["blockers"].append("wx3200_render_node_exposed")
    if result["observed_gfx_override"] != "9.0.6":
        result["blockers"].append("gfx906_override_missing")

    result["image_digest_pinned"] = bool(
        re.search(
            r"(?m)^\s*image\s*:\s*\S+@sha256:[0-9a-f]{64}\s*$",
            active_text,
        )
    )
    result["network_disabled"] = bool(
        re.search(r'(?m)^\s*network_mode\s*:\s*["\']?none["\']?\s*$', lower)
    )
    result["read_only_rootfs"] = bool(
        re.search(r"(?m)^\s*read_only\s*:\s*true\s*$", lower)
    )
    if not result["image_digest_pinned"]:
        result["blockers"].append("image_digest_unpinned")
    if not result["network_disabled"]:
        result["blockers"].append("runtime_network_not_disabled")
    if not result["read_only_rootfs"]:
        result["blockers"].append("rootfs_not_read_only")

    if not result["blockers"]:
        result["status"] = "static_ready"
    return result


def _valid_artifact_manifest(rows: Any) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if not isinstance(row, dict):
            return False
        if not isinstance(row.get("path"), str) or not row["path"]:
            return False
        if not isinstance(row.get("size"), int) or row["size"] <= 0:
            return False
        if not SHA256_RE.fullmatch(str(row.get("sha256", ""))):
            return False
    return True


def audit_onnx_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    revision = candidate.get("source_revision")
    if not isinstance(revision, str) or not REVISION_RE.fullmatch(revision):
        blockers.append("source_revision_unpinned")

    license_info = candidate.get("license", {})
    if (
        not isinstance(license_info, dict)
        or license_info.get("status") != "verified"
        or not license_info.get("spdx")
    ):
        blockers.append("license_unverified")

    if not _valid_artifact_manifest(candidate.get("artifact_manifest")):
        blockers.append("artifact_manifest_missing")
    operators = candidate.get("operator_inventory")
    if not isinstance(operators, list) or not operators:
        blockers.append("operator_inventory_missing")

    components = candidate.get("components", {})
    for component in ("text_model", "speech_tokenizer", "vocoder"):
        if not isinstance(components, dict) or components.get(component) is not True:
            blockers.append(f"{component}_missing")

    parity = candidate.get("reference_parity", {})
    if (
        not isinstance(parity, dict)
        or parity.get("status") != "verified"
        or not SHA256_RE.fullmatch(str(parity.get("reference_wav_sha256", "")))
    ):
        blockers.append("reference_parity_missing")

    return {
        "candidate_id": candidate.get("candidate_id"),
        "upstream_model": candidate.get("upstream_model"),
        "source_url": candidate.get("source_url"),
        "status": "blocked" if blockers else "trial_ready",
        "production_eligible": False,
        "execution_attempted": False,
        "blockers": blockers,
    }


def build_report(
    manifest: dict[str, Any], *, container_config: Path
) -> dict[str, Any]:
    container = audit_mi50_container(container_config)
    candidates = [
        audit_onnx_candidate(candidate)
        for candidate in manifest.get("candidates", [])
    ]
    blockers = []
    if container["status"] != "static_ready":
        blockers.append("mi50_container_not_static_ready")
    if not candidates:
        blockers.append("candidate_manifest_empty")
    elif not any(row["status"] == "trial_ready" for row in candidates):
        blockers.append("no_trial_ready_candidate")
    return {
        "schema": "agent_bridge.voice_model_research_receipt.v1",
        "status": "blocked" if blockers else "trial_plan_ready",
        "manifest_schema": manifest.get("schema"),
        "container": container,
        "candidates": candidates,
        "blockers": blockers,
        "runtime_effects": {
            "downloads_models": False,
            "starts_containers": False,
            "uses_gpu": False,
            "plays_audio": False,
            "writes_memory": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a non-actuating S5D voice-model research receipt"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--container-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    report = build_report(manifest, container_config=args.container_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "trial_plan_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
