#!/usr/bin/env python3
"""Statically audit the Qwen ONNX/quantization toolchain without executing it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pep723_dependencies(source: str) -> list[str]:
    match = re.search(
        r"# dependencies = \[(.*?)# \]",
        source,
        flags=re.DOTALL,
    )
    if not match:
        return []
    return re.findall(r'"([^"]+)"', match.group(1))


def _package_name(requirement: str) -> str:
    return re.split(r"[<>=!~\[]", requirement, maxsplit=1)[0]


def _arrowquant_reasons(facts: dict[str, Any]) -> list[str]:
    reasons = []
    if not facts.get("repo_digests"):
        reasons.append("image_has_no_repo_digest")
    if facts.get("default_command_uses_apt"):
        reasons.append("default_command_mutates_packages")
    if facts.get("contains_cloudflare_warp"):
        reasons.append("build_history_contains_network_tunnel")
    if not facts.get("olive_version") or not facts.get("onnxruntime_version"):
        reasons.append("tts_toolchain_versions_not_present")
    return reasons


def _manifest_payload_bytes(directory: Path) -> int:
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return 0
    manifest = json.loads(manifest_path.read_text())
    total = 0
    for item in manifest.get("sub_models", {}).values():
        model_path = directory / item["filename"]
        if model_path.is_file():
            total += model_path.stat().st_size
        external_path = model_path.with_name(model_path.name + ".data")
        if external_path.is_file():
            total += external_path.stat().st_size
    return total


def audit_toolchain(
    snapshot: Path,
    *,
    host: dict[str, Any],
    arrowquant_image: dict[str, Any],
) -> dict[str, Any]:
    snapshot = snapshot.resolve()
    optimize_path = snapshot / "optimize.py"
    user_script_path = snapshot / "user_script.py"
    requirements_path = snapshot / "requirements.txt"
    optimize = optimize_path.read_text()
    requirements = requirements_path.read_text()
    dependencies = _pep723_dependencies(optimize)
    unlocked = sorted(
        _package_name(item)
        for item in dependencies
        if "==" not in item
    )
    transformers = next(
        (
            item.split("==", 1)[1]
            for item in dependencies
            if item.startswith("transformers==")
        ),
        None,
    )
    requirements_conflict = (
        transformers is not None and "transformers>=5.10" in requirements
    )
    variants = {
        name: (snapshot / name / "manifest.json").is_file()
        for name in (
            "cpu_fp32",
            "cpu_fp16",
            "cpu_int4",
            "cuda_fp32",
            "cuda_fp16",
            "cuda_int4",
        )
    }
    fp32_bytes = _manifest_payload_bytes(snapshot / "cpu_fp32")
    int4_bytes = _manifest_payload_bytes(snapshot / "cpu_int4")
    compression_ratio = fp32_bytes / int4_bytes if int4_bytes else None
    reduction_fraction = (
        1 - int4_bytes / fp32_bytes if fp32_bytes else None
    )
    rtn_implemented = all(
        marker in optimize
        for marker in (
            "OnnxBlockwiseRtnQuantization",
            '"bits": 4',
            '"block_size": 32',
            '"is_symmetric": False',
        )
    )
    arrow_reasons = _arrowquant_reasons(arrowquant_image)
    blockers = [
        "community_converter_source_revision_unpinned",
        "build_dependencies_not_fully_locked",
    ]
    if requirements_conflict:
        blockers.append("requirements_transformers_conflicts_with_pep723")
    if not host.get("uv_available"):
        blockers.append("uv_not_installed")
    blockers.extend(
        [
            "converter_output_root_inside_community_snapshot",
            "converter_can_download_without_skip_download",
        ]
    )
    if arrow_reasons:
        blockers.append("arrowquant_image_not_admitted_for_tts")
    blockers.extend(
        [
            "fixed_source_fp32_export_not_executed",
            "fixed_source_int4_quantization_not_executed",
            "fp32_int4_parity_not_verified",
            "mi50_execution_not_verified",
        ]
    )
    return {
        "schema": "agent_bridge.voice_quantization_toolchain_audit.v1",
        "status": "audited_lock_and_execution_blocked",
        "snapshot": str(snapshot),
        "source_identity": {
            "declared_revision": "master",
            "declared_revision_immutable": False,
            "files": {
                "optimize.py": _sha256(optimize_path),
                "user_script.py": _sha256(user_script_path),
                "requirements.txt": _sha256(requirements_path),
            },
        },
        "converter": {
            "uses_olive": "from olive import run" in optimize,
            "uses_subprocess_isolation": "subprocess.run(cmd)" in optimize,
            "supports_skip_download": "--skip-download" in optimize,
            "can_download_without_skip_download": (
                "snapshot_download(" in optimize
            ),
            "output_root_inside_source_snapshot": (
                'return HERE / "onnx"' in optimize
            ),
            "overwrites_existing_outputs": (
                "dst.unlink()" in optimize
                and "shutil.rmtree" in optimize
            ),
            "execution_ready": False,
        },
        "dependency_audit": {
            "python_declared": ">=3.10",
            "transformers_pep723": transformers,
            "requirements_conflict": requirements_conflict,
            "declared": dependencies,
            "unlocked": unlocked,
            "fully_locked": not unlocked and not requirements_conflict,
            "uv_available": bool(host.get("uv_available")),
        },
        "quantization": {
            "rtn": {
                "implemented": rtn_implemented,
                "bits": 4,
                "block_size": 32,
                "symmetric": False,
                "scope": "weight_only_matmul_and_gather",
            },
            "codec_and_speaker_encoder_policy": "fp32_only",
            "fixed_source_fp32_generated": False,
            "fixed_source_int4_generated": False,
            "fp32_int4_parity_verified": False,
        },
        "existing_artifacts": variants,
        "artifact_size_evidence": {
            "cpu_fp32_declared_payload_bytes": fp32_bytes,
            "cpu_int4_declared_payload_bytes": int4_bytes,
            "fp32_to_int4_compression_ratio": compression_ratio,
            "fp32_to_int4_reduction_fraction": reduction_fraction,
            "quality_or_parity_inferred_from_size": False,
        },
        "mi50": {
            "present": bool(host.get("mi50_present")),
            "arch": host.get("mi50_arch"),
            "legacy_rocm_lane_image_present": bool(
                host.get("rocm_container_image_present")
            ),
            "cuda_manifest_counts_as_rocm_evidence": False,
            "execution_verified": False,
        },
        "arrowquant_image": {
            **arrowquant_image,
            "admitted_for_tts": not arrow_reasons,
            "reasons": arrow_reasons,
        },
        "decision": {
            "selected_quantizer": (
                "olive_onnx_blockwise_rtn_int4_after_fp32_reference"
            ),
            "generation_lane": "isolated_cpu_fp32_then_cpu_int4",
            "mi50_lane": "separate_legacy_rocm_inference_only",
            "quark_status": "watch_not_selected",
            "next_gate": (
                "pin_complete_offline_environment_and_isolated_workspace"
            ),
        },
        "blockers": blockers,
        "runtime_effects": {
            "started_container": False,
            "installed_packages": False,
            "downloaded_files": False,
            "loaded_source_model": False,
            "executed_converter": False,
            "executed_quantizer": False,
            "created_onnx": False,
            "used_gpu": False,
            "played_audio": False,
        },
    }


def _docker_image_facts(image: str) -> dict[str, Any]:
    try:
        raw = subprocess.run(
            ["docker", "image", "inspect", image],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        inspected = json.loads(raw)[0]
        history = subprocess.run(
            ["docker", "history", "--no-trunc", "--format", "{{.CreatedBy}}", image],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {
            "present": False,
            "repo_digests": [],
            "default_command_uses_apt": False,
            "contains_cloudflare_warp": False,
            "transformers_version": None,
            "olive_version": None,
            "onnxruntime_version": None,
        }
    command = " ".join(
        inspected.get("Config", {}).get("Cmd") or []
    )
    transformer_match = re.search(
        r'transformers==([0-9.]+)', history
    )
    return {
        "present": True,
        "repo_digests": inspected.get("RepoDigests") or [],
        "default_command_uses_apt": "apt-get" in command,
        "contains_cloudflare_warp": "cloudflare-warp" in history,
        "transformers_version": (
            transformer_match.group(1) if transformer_match else None
        ),
        "olive_version": None,
        "onnxruntime_version": None,
    }


def _host_facts() -> dict[str, Any]:
    try:
        pci = subprocess.run(
            ["lspci", "-nn"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pci = ""
    return {
        "uv_available": shutil.which("uv") is not None,
        "mi50_present": "1002:66a1" in pci,
        "mi50_arch": "gfx906" if "1002:66a1" in pci else None,
        "rocm_container_image_present": (
            subprocess.run(
                ["docker", "image", "inspect", "rocm/dev-ubuntu-22.04:5.7"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Statically audit Qwen TTS conversion and quantization"
    )
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = audit_toolchain(
        args.snapshot,
        host=_host_facts(),
        arrowquant_image=_docker_image_facts("arrowquant-rocm:5.7"),
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
