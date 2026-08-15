#!/usr/bin/env python3
"""Build a fail-closed, non-actuating bounded Story render contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


VOICE_EVIDENCE_ROOT = Path(
    "/Data/Models/agent-bridge/evidence/voice-scene"
).resolve()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required:{path}")
    return value


def _validate_preflight(preflight: dict[str, Any]) -> None:
    if (
        preflight.get("schema") != "agent_bridge.story_fixture_mcp_preflight.v1"
        or preflight.get("status") != "story_fixture_mcp_preflight_verified"
        or preflight.get("next_gate")
        != "story_fixture_bounded_render_authorization"
        or preflight.get("result", {}).get("execution_authorized") is not False
    ):
        raise ValueError("fixture preflight boundary invalid")
    effects = preflight.get("runtime_effects", {})
    for key in (
        "loaded_model",
        "executed_onnx",
        "rendered_audio",
        "played_audio",
        "wrote_memory",
        "wrote_cache",
    ):
        if effects.get(key) is not False:
            raise ValueError("fixture preflight runtime effects invalid")


def _validate_acceptance(
    acceptance: dict[str, Any], preflight: dict[str, Any]
) -> None:
    if (
        acceptance.get("schema")
        != "agent_bridge.story_fixture_bounded_render.v1"
        or acceptance.get("status")
        != "story_fixture_bounded_render_owner_accepted"
        or acceptance.get("next_gate")
        != "story_bounded_render_execution_contract"
        or acceptance.get("owner_feedback", {}).get("accepted") is not True
        or acceptance.get("claims", {}).get("machine_audio_gate_passed") is not True
        or acceptance.get("claims", {}).get("owner_acceptance_verified") is not True
        or acceptance.get("claims", {}).get(
            "story_command_render_executor_enabled"
        )
        is not False
    ):
        raise ValueError("bounded render acceptance invalid")
    preflight_result = preflight.get("result", {})
    acceptance_preflight = acceptance.get("preflight", {})
    if (
        acceptance_preflight.get("preflight_sha256")
        != preflight_result.get("preflight_sha256")
        or acceptance_preflight.get("source_sha256")
        != preflight.get("request", {}).get("source_sha256")
        or acceptance_preflight.get("chapter")
        != preflight.get("request", {}).get("start", {}).get("chapter")
        or acceptance_preflight.get("selected_segments")
        != preflight.get("selection", {}).get("selected_segments")
    ):
        raise ValueError("preflight provenance mismatch")
    segments = acceptance.get("segments", [])
    if len(segments) != preflight.get("selection", {}).get("selected_segments"):
        raise ValueError("accepted segment count mismatch")
    if acceptance.get("assembly", {}).get("gap_seconds") != preflight.get(
        "selection", {}
    ).get("assembly_gap_seconds"):
        raise ValueError("accepted assembly gap mismatch")
    allowed_speakers = {"Serena", "Vivian"}
    indices = {row.get("index") for row in segments}
    if (
        not 1 <= len(segments) <= 3
        or indices != set(range(len(segments)))
        or any(
            row.get("speaker") not in allowed_speakers
            or row.get("frame_cap") != 100
            or not 1 <= row.get("generated_codec_frames", 0) < 100
            or row.get("natural_eos") is not True
            or row.get("sample_rate_hz") != 24000
            or row.get("channels") != 1
            for row in segments
        )
    ):
        raise ValueError("accepted render exceeds execution bounds")
    assembly = acceptance.get("assembly", {})
    if (
        not 0 < assembly.get("duration_seconds", 0) <= 30.0
        or assembly.get("sample_rate_hz") != 24000
        or assembly.get("channels") != 1
        or assembly.get("sample_width_bytes") != 2
        or assembly.get("non_silent") is not True
    ):
        raise ValueError("accepted render exceeds execution bounds")
    model = acceptance.get("model", {})
    if (
        model.get("variant") != "community_cpu_int4_onnx"
        or model.get("provider_policy") != "cpu_only_gpu_hidden"
        or model.get("offline") is not True
        or len(model.get("inference_sha256", "")) != 64
    ):
        raise ValueError("accepted render model boundary invalid")


def _safe_output_root(output_root: Path) -> Path:
    resolved = output_root.resolve()
    if resolved == VOICE_EVIDENCE_ROOT:
        raise ValueError("dedicated output root required")
    if not resolved.is_relative_to(VOICE_EVIDENCE_ROOT):
        raise ValueError("output root outside voice evidence root")
    return resolved


def build_execution_contract(
    *,
    preflight_receipt_path: Path,
    accepted_render_receipt_path: Path,
    trusted_runner_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Bind evidence and authority gates without performing any runtime action."""

    preflight = _read_json(preflight_receipt_path)
    acceptance = _read_json(accepted_render_receipt_path)
    _validate_preflight(preflight)
    _validate_acceptance(acceptance, preflight)
    output_root = _safe_output_root(output_root)
    if not trusted_runner_path.is_file():
        raise ValueError("trusted runner missing")

    speakers = sorted({row["speaker"] for row in acceptance["segments"]})
    contract_builder_path = Path(__file__).resolve()
    evidence = {
        "contract_builder_path": str(contract_builder_path),
        "contract_builder_sha256": _sha256_file(contract_builder_path),
        "preflight_receipt_path": str(preflight_receipt_path.resolve()),
        "preflight_receipt_sha256": _sha256_file(preflight_receipt_path),
        "accepted_render_receipt_path": str(accepted_render_receipt_path.resolve()),
        "accepted_render_receipt_sha256": _sha256_file(
            accepted_render_receipt_path
        ),
        "trusted_runner_path": str(trusted_runner_path.resolve()),
        "trusted_runner_sha256": _sha256_file(trusted_runner_path),
        "preflight_sha256": preflight["result"]["preflight_sha256"],
        "source_sha256": preflight["request"]["source_sha256"],
        "model_inference_sha256": acceptance["model"]["inference_sha256"],
        "chapter": acceptance["preflight"]["chapter"],
        "selected_segments": len(acceptance["segments"]),
        "accepted_assembly_sha256": acceptance["assembly"]["audio_sha256"],
    }
    bounds = {
        "max_segments_per_grant": 3,
        "max_codec_frames_per_segment": 100,
        "max_assembled_duration_seconds": 30.0,
        "sample_rate_hz": 24000,
        "channels": 1,
        "allowed_speakers": speakers,
        "output_root": str(output_root),
        "existing_output_overwrite_allowed": False,
        "network_allowed": False,
        "gpu_allowed": False,
    }
    authority = {
        "render": {
            "grant_required": True,
            "grant_present": False,
            "single_use": True,
            "bound_fields": [
                "contract_sha256",
                "preflight_sha256",
                "output_directory",
            ],
        },
        "playback": {
            "grant_required": True,
            "grant_present": False,
            "single_use": True,
            "requires_machine_gate": True,
            "bound_fields": ["render_receipt_sha256", "audio_sha256"],
        },
        "record": {"supported": False, "grant_present": False},
        "memory_write": {"supported": False, "grant_present": False},
    }
    state_machine = [
        "preflight_reviewed",
        "render_grant_required",
        "bounded_render",
        "machine_audio_gate",
        "playback_grant_required",
        "single_playback",
        "owner_feedback",
    ]
    runtime_effects = {
        "created_output_directory": False,
        "loaded_model": False,
        "executed_onnx": False,
        "rendered_audio": False,
        "played_audio": False,
        "recorded_audio": False,
        "wrote_cache": False,
        "wrote_memory": False,
    }
    bound = {
        "evidence": evidence,
        "bounds": bounds,
        "authority": authority,
        "state_machine": state_machine,
        "execution_authorized": False,
        "runtime_effects": runtime_effects,
    }
    return {
        "schema": "agent_bridge.story_bounded_render_execution_contract.v1",
        "status": "story_bounded_render_execution_contract_reviewable",
        **bound,
        "contract_sha256": _digest(bound),
        "claims": {
            "preflight_and_acceptance_hash_bound": True,
            "render_and_playback_authority_separated": True,
            "recording_unsupported": True,
            "memory_write_unsupported": True,
            "static_contract_ready": True,
            "executor_implemented": False,
            "runtime_execution_admitted": False,
        },
        "next_gate": "story_bounded_render_executor_implementation_review",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-receipt", type=Path, required=True)
    parser.add_argument("--accepted-render-receipt", type=Path, required=True)
    parser.add_argument("--trusted-runner", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = build_execution_contract(
        preflight_receipt_path=args.preflight_receipt,
        accepted_render_receipt_path=args.accepted_render_receipt,
        trusted_runner_path=args.trusted_runner,
        output_root=args.output_root,
    )
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
