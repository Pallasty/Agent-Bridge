from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "scripts" / "story_voice_quantization_toolchain_audit.py"
)
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_quantization_toolchain_audit.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_quantization_toolchain_audit", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_converter(root: Path) -> Path:
    snapshot = root / "community"
    snapshot.mkdir()
    (snapshot / "optimize.py").write_text(
        """# /// script
# dependencies = [
#   "transformers==4.57.3",
#   "torch",
#   "olive-ai",
#   "onnx",
#   "onnxruntime>=1.20",
# ]
# ///
PROVIDER = {"cpu": "CPUExecutionProvider", "cuda": "CUDAExecutionProvider"}
passes["q"] = {"type": "OnnxBlockwiseRtnQuantization", "bits": 4,
               "block_size": 32, "is_symmetric": False}
def output_root(device, precision):
    return HERE / "onnx" / f"{device}_{precision}"
snapshot_download(repo_id=model, local_dir=str(dst))
if args.skip_download:
    cmd.append("--skip-download")
dst.unlink()
shutil.rmtree(tmp)
"""
    )
    (snapshot / "user_script.py").write_text(
        "Qwen3TTSForConditionalGeneration.from_pretrained(model_path)\n"
    )
    (snapshot / "requirements.txt").write_text(
        "olive-ai\nonnxruntime>=1.20\ntorch\ntransformers>=5.10\n"
    )
    for variant in ("cpu_fp32", "cpu_int4", "cuda_int4"):
        directory = snapshot / variant
        directory.mkdir()
        payload = b"x" * (100 if variant == "cpu_fp32" else 25)
        (directory / "component.onnx").write_bytes(payload)
        (directory / "manifest.json").write_text(
            json.dumps(
                {
                    "precision": variant.split("_")[1],
                    "sub_models": {
                        "component": {"filename": "component.onnx"}
                    },
                }
            )
        )
    return snapshot


def image_facts() -> dict:
    return {
        "present": True,
        "repo_digests": [],
        "default_command_uses_apt": True,
        "contains_cloudflare_warp": True,
        "transformers_version": "4.44.2",
        "olive_version": None,
        "onnxruntime_version": None,
    }


def host_facts() -> dict:
    return {
        "uv_available": False,
        "mi50_present": True,
        "mi50_arch": "gfx906",
        "rocm_container_image_present": True,
    }


def test_audit_selects_rtn_only_after_fp32_reference(tmp_path: Path) -> None:
    audit = load_module().audit_toolchain(
        make_converter(tmp_path),
        host=host_facts(),
        arrowquant_image=image_facts(),
    )

    assert audit["status"] == "audited_lock_and_execution_blocked"
    assert audit["decision"]["selected_quantizer"] == (
        "olive_onnx_blockwise_rtn_int4_after_fp32_reference"
    )
    assert audit["quantization"]["rtn"] == {
        "implemented": True,
        "bits": 4,
        "block_size": 32,
        "symmetric": False,
        "scope": "weight_only_matmul_and_gather",
    }
    assert audit["quantization"]["fixed_source_int4_generated"] is False


def test_floating_dependencies_and_transformers_conflict_block_lock(
    tmp_path: Path,
) -> None:
    audit = load_module().audit_toolchain(
        make_converter(tmp_path),
        host=host_facts(),
        arrowquant_image=image_facts(),
    )

    assert audit["dependency_audit"]["transformers_pep723"] == "4.57.3"
    assert audit["dependency_audit"]["requirements_conflict"] is True
    assert "olive-ai" in audit["dependency_audit"]["unlocked"]
    assert "build_dependencies_not_fully_locked" in audit["blockers"]


def test_in_snapshot_output_and_network_fallback_are_rejected(
    tmp_path: Path,
) -> None:
    audit = load_module().audit_toolchain(
        make_converter(tmp_path),
        host=host_facts(),
        arrowquant_image=image_facts(),
    )

    assert audit["converter"]["output_root_inside_source_snapshot"] is True
    assert audit["converter"]["can_download_without_skip_download"] is True
    assert "converter_output_root_inside_community_snapshot" in audit["blockers"]


def test_cuda_artifact_is_not_mi50_evidence(tmp_path: Path) -> None:
    audit = load_module().audit_toolchain(
        make_converter(tmp_path),
        host=host_facts(),
        arrowquant_image=image_facts(),
    )

    assert audit["existing_artifacts"]["cuda_int4"] is True
    assert audit["mi50"]["execution_verified"] is False
    assert audit["mi50"]["cuda_manifest_counts_as_rocm_evidence"] is False


def test_size_claim_uses_manifest_declared_payload_only(
    tmp_path: Path,
) -> None:
    audit = load_module().audit_toolchain(
        make_converter(tmp_path),
        host=host_facts(),
        arrowquant_image=image_facts(),
    )

    assert audit["artifact_size_evidence"] == {
        "cpu_fp32_declared_payload_bytes": 100,
        "cpu_int4_declared_payload_bytes": 25,
        "fp32_to_int4_compression_ratio": 4.0,
        "fp32_to_int4_reduction_fraction": 0.75,
        "quality_or_parity_inferred_from_size": False,
    }


def test_arrowquant_image_is_not_admitted_for_tts(tmp_path: Path) -> None:
    audit = load_module().audit_toolchain(
        make_converter(tmp_path),
        host=host_facts(),
        arrowquant_image=image_facts(),
    )

    assert audit["arrowquant_image"]["admitted_for_tts"] is False
    assert audit["arrowquant_image"]["reasons"] == [
        "image_has_no_repo_digest",
        "default_command_mutates_packages",
        "build_history_contains_network_tunnel",
        "tts_toolchain_versions_not_present",
    ]


def test_audit_has_no_execution_or_model_effects(tmp_path: Path) -> None:
    audit = load_module().audit_toolchain(
        make_converter(tmp_path),
        host=host_facts(),
        arrowquant_image=image_facts(),
    )

    assert audit["runtime_effects"] == {
        "started_container": False,
        "installed_packages": False,
        "downloaded_files": False,
        "loaded_source_model": False,
        "executed_converter": False,
        "executed_quantizer": False,
        "created_onnx": False,
        "used_gpu": False,
        "played_audio": False,
    }


def test_repository_shape_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = __import__("jsonschema")
    audit = load_module().audit_toolchain(
        make_converter(tmp_path),
        host=host_facts(),
        arrowquant_image=image_facts(),
    )

    jsonschema.validate(audit, json.loads(SCHEMA_PATH.read_text()))
