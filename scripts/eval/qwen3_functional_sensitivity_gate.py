#!/usr/bin/env python3
"""Authorize one exact, non-writing Qwen3-TTS fake-Q8 sensitivity smoke."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.functional_sensitivity_gate.v0"
POLICY_SCHEMA = "agent_bridge.qwen3_tts.functional_sensitivity_policy.v0"
PLAN_SCHEMA = "agent_bridge.qwen3_tts.activation_probe_plan.v1"
ACTIVATION_GATE_SCHEMA = "agent_bridge.qwen3_tts.activation_calibration_gate.v0"
SCOPE_SCHEMA = "agent_bridge.qwen3_tts.q8_perturbation_scope_plan.v0"
PROBE_SCHEMA = "agent_bridge.qwen3_tts.token_boundary_probe.v0"
MANIFEST_SCHEMA = "agent_bridge.qwen3_tts.inference_critical_manifest.v0"
CORPUS_SCHEMA = "agent_bridge.qwen3_tts.quantization_corpus.v0"
THRESHOLDS_SCHEMA = "agent_bridge.qwen3_tts.quantization_thresholds.v0"
READY = "READY_FOR_ONE_MODULE_FAKE_Q8_SMOKE"
BLOCKED = "BLOCKED_FUNCTIONAL_SENSITIVITY_PREREQUISITES"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exclusive_write_json(path: Path, report: dict) -> None:
    if not path.parent.is_dir():
        raise ValueError("output parent directory must already exist")
    payload = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def evaluate(
    policy: dict,
    plan: dict,
    activation_gate: dict,
    scope: dict,
    probe: dict,
    manifest: dict,
    corpus: dict,
    thresholds: dict,
    hashes: dict[str, str],
) -> dict:
    failures: list[str] = []

    def require(condition: bool, code: str) -> None:
        if not condition:
            failures.append(code)

    inputs = policy.get("inputs", {})
    require(policy.get("schema") == POLICY_SCHEMA, "policy_schema_mismatch")
    require(
        policy.get("status") == "FROZEN_ONE_MODULE_ONE_CASE_SMOKE_ONLY",
        "policy_not_frozen",
    )
    require(plan.get("schema") == PLAN_SCHEMA, "plan_schema_mismatch")
    require(
        activation_gate.get("schema") == ACTIVATION_GATE_SCHEMA
        and activation_gate.get("status") == "READY_FOR_FUNCTIONAL_SENSITIVITY_DESIGN",
        "activation_gate_not_ready",
    )
    require(scope.get("schema") == SCOPE_SCHEMA, "scope_schema_mismatch")
    require(
        scope.get("status") == "Q8_PERTURBATION_SCOPE_PLANNED_DEFAULT_OFF",
        "scope_not_default_off",
    )
    require(
        probe.get("schema") == PROBE_SCHEMA
        and probe.get("status") == "TOKEN_CODE_BOUNDARY_OBSERVED_READ_ONLY",
        "token_boundary_not_observed",
    )
    require(manifest.get("schema") == MANIFEST_SCHEMA, "manifest_schema_mismatch")
    require(corpus.get("schema") == CORPUS_SCHEMA, "corpus_schema_mismatch")
    require(thresholds.get("schema") == THRESHOLDS_SCHEMA, "thresholds_schema_mismatch")

    expected_hash_fields = {
        "activation_plan_sha256": "plan",
        "activation_gate_sha256": "activation_gate",
        "activation_capture_sha256": "activation_capture",
        "perturbation_scope_sha256": "scope",
        "token_boundary_probe_sha256": "probe",
        "runtime_manifest_sha256": "manifest",
        "corpus_sha256": "corpus",
        "thresholds_sha256": "thresholds",
    }
    for policy_field, hash_field in expected_hash_fields.items():
        require(
            inputs.get(policy_field) == hashes.get(hash_field),
            f"frozen_hash_mismatch:{policy_field}",
        )

    require(
        activation_gate.get("activation_plan_sha256") == hashes.get("plan"),
        "activation_gate_plan_mismatch",
    )
    require(
        activation_gate.get("activation_capture_sha256")
        == hashes.get("activation_capture"),
        "activation_gate_capture_mismatch",
    )
    require(
        activation_gate.get("corpus_sha256") == hashes.get("corpus"),
        "activation_gate_corpus_mismatch",
    )
    require(
        scope.get("activation_plan_sha256") == hashes.get("plan"),
        "scope_plan_mismatch",
    )
    require(
        scope.get("activation_capture_sha256") == hashes.get("activation_capture"),
        "scope_capture_mismatch",
    )
    require(
        scope.get("activation_gate_sha256") == hashes.get("activation_gate"),
        "scope_gate_mismatch",
    )
    require(
        probe.get("activation_plan_sha256") == hashes.get("plan"),
        "probe_plan_mismatch",
    )
    require(
        probe.get("activation_gate_sha256") == hashes.get("activation_gate"),
        "probe_gate_mismatch",
    )
    require(
        probe.get("runtime_manifest_sha256") == hashes.get("manifest"),
        "probe_manifest_mismatch",
    )
    require(
        probe.get("corpus_sha256") == hashes.get("corpus"),
        "probe_corpus_mismatch",
    )
    policy_assets = {
        row.get("partition"): (row.get("bytes"), row.get("sha256"))
        for row in policy.get("source_assets", [])
    }
    probe_assets = {
        row.get("partition"): (row.get("bytes"), row.get("sha256"))
        for row in probe.get("model_assets", [])
    }
    require(policy_assets == probe_assets, "policy_probe_asset_mismatch")
    functional_source_pins = policy.get("functional_runtime_source_pins", [])
    expected_functional_sources = {
        ("qwen_tts", "__init__.py"),
        ("transformers", "__init__.py"),
        ("transformers", "generation/utils.py"),
        ("safetensors", "__init__.py"),
        ("safetensors", "torch.py"),
        ("safetensors", "_safetensors_rust.abi3.so"),
    }
    require(
        {
            (row.get("package"), row.get("relative_path"))
            for row in functional_source_pins
        }
        == expected_functional_sources
        and all(
            isinstance(row.get("bytes"), int)
            and row.get("bytes", 0) > 0
            and len(row.get("sha256", "")) == 64
            for row in functional_source_pins
        ),
        "functional_runtime_source_pin_invalid",
    )

    target = policy.get("target", {})
    plan_rows = [row for row in plan.get("modules", []) if row.get("module") == target.get("module")]
    scope_rows = [
        row for row in scope.get("modules", []) if row.get("module") == target.get("module")
    ]
    require(len(plan_rows) == 1, "target_not_unique_in_plan")
    require(len(scope_rows) == 1, "target_not_unique_in_scope")
    if plan_rows:
        planned = plan_rows[0]
        for field in ("module", "tensor", "family", "shape", "elements", "source_dtype"):
            require(
                planned.get(field) == target.get(field),
                f"target_plan_mismatch:{field}",
            )
    if scope_rows:
        scoped = scope_rows[0]
        require(
            scoped.get("eligible_for_future_perturbation_design") is True,
            "target_not_scope_eligible",
        )
        require(
            scoped.get("proposed_mode_if_separately_authorized")
            == "ONE_MODULE_AT_A_TIME_FAKE_Q8_GROUPWISE_SYMMETRIC",
            "target_scope_mode_mismatch",
        )
        require(
            scoped.get("joint_risk_score") == target.get("joint_risk_score"),
            "target_scope_risk_mismatch",
        )

    case_policy = policy.get("case", {})
    frozen_cases = [case for case in corpus.get("cases", []) if case.get("id") == case_policy.get("id")]
    require(len(frozen_cases) == 1, "target_case_not_unique")
    require(probe.get("case") == (frozen_cases[0] if frozen_cases else None), "probe_case_mismatch")
    if frozen_cases:
        require(
            case_policy.get("speaker") == frozen_cases[0].get("speaker"),
            "policy_case_speaker_mismatch",
        )
    require(case_policy.get("language") == "Chinese", "policy_case_language_mismatch")
    boundary = probe.get("boundary", {})
    generated = boundary.get("generated_codes", [])
    require(boundary.get("exact_generate_to_decode_match") is True, "probe_code_handoff_mismatch")
    require(boundary.get("decode_was_intercepted") is True, "probe_decode_not_intercepted")
    require(boundary.get("returned_wave_samples") == [0], "probe_returned_audio")
    require(
        len(generated) == 1
        and generated[0].get("time_steps", 0) > 0
        and generated[0].get("codebooks") == 16,
        "probe_code_matrix_invalid",
    )

    for source in (activation_gate, probe):
        for field in (
            "allows_quantized_weight_writing",
            "allows_runtime_candidate_generation",
            "allows_runtime_wiring_or_promotion",
        ):
            require(source.get(field) is False, f"prerequisite_authority:{field}")
    require(scope.get("allows_fake_quant_execution") is False, "scope_fake_execution_true")
    require(probe.get("allows_fake_quant_execution") is False, "probe_fake_execution_true")
    require(scope.get("writes_quantized_weights") is False, "scope_writes_weights")
    require(scope.get("creates_runtime_candidate") is False, "scope_creates_candidate")
    require(probe.get("mutates_weights") is False, "probe_mutates_weights")
    require(probe.get("decodes_audio") is False, "probe_decodes_audio")
    require(probe.get("writes_audio") is False, "probe_writes_audio")

    execution = policy.get("execution", {})
    quantizer = policy.get("quantizer", {})
    authorization = policy.get("authorization", {})
    require(
        execution.get("processes") == execution.get("modules") == execution.get("cases")
        == execution.get("fake_trials")
        == 1,
        "execution_not_single_trial",
    )
    trial_id = execution.get("trial_id", "")
    expected_trial_root = (
        Path.home()
        / ".local"
        / "state"
        / "agent-bridge"
        / "qwen3-evaluation-ledger"
    )
    require(
        trial_id
        == "qwen3-tts-q2-fs-v0-l6-gate-proj-zh-short-neutral-serena-001",
        "trial_id_mismatch",
    )
    require(
        execution.get("claim_path")
        == str(expected_trial_root / f"{trial_id}.claim.json"),
        "claim_path_mismatch",
    )
    require(
        execution.get("result_path")
        == str(expected_trial_root / f"{trial_id}.result.json"),
        "result_path_mismatch",
    )
    require(
        execution.get("one_shot_claim_o_excl") is True
        and execution.get("claim_is_never_automatically_deleted") is True,
        "one_shot_claim_contract_missing",
    )
    require(
        execution.get("claim_and_result_parent_directory_fsync") is True,
        "claim_directory_fsync_missing",
    )
    require(
        len(execution.get("gate_evaluator_sha256", "")) == 64,
        "gate_evaluator_sha256_invalid",
    )
    require(execution.get("do_sample") is False, "talker_sampling_enabled")
    require(execution.get("subtalker_dosample") is False, "subtalker_sampling_enabled")
    require(quantizer.get("group_size") == 128, "quantizer_group_size_mismatch")
    require(quantizer.get("qmin") == -127 and quantizer.get("qmax") == 127, "qrange_mismatch")
    require(
        quantizer.get("rounding") == "half_away_from_zero",
        "quantizer_rounding_mismatch",
    )
    require(
        authorization.get("allows_exactly_one_module_one_case_fake_q8_smoke") is True,
        "one_trial_not_authorized",
    )
    for field in (
        "allows_additional_module_or_case",
        "allows_weight_mutation",
        "allows_quantized_weight_writing",
        "allows_packing_or_scale_storage_claim",
        "allows_runtime_candidate_generation",
        "allows_worker_socket_use",
        "allows_audio_decode_write_or_playback",
        "allows_runtime_wiring_fallback_deployment_or_promotion",
    ):
        require(authorization.get(field) is False, f"forbidden_authority:{field}")

    failures = sorted(set(failures))
    ready = not failures
    return {
        "schema": SCHEMA,
        "status": READY if ready else BLOCKED,
        "policy_sha256": hashes.get("policy"),
        "activation_plan_sha256": hashes.get("plan"),
        "activation_gate_sha256": hashes.get("activation_gate"),
        "activation_capture_sha256": hashes.get("activation_capture"),
        "perturbation_scope_sha256": hashes.get("scope"),
        "token_boundary_probe_sha256": hashes.get("probe"),
        "runtime_manifest_sha256": hashes.get("manifest"),
        "corpus_sha256": hashes.get("corpus"),
        "thresholds_sha256": hashes.get("thresholds"),
        "target": target,
        "case": case_policy,
        "trial": {
            "trial_id": trial_id,
            "claim_path": execution.get("claim_path"),
            "result_path": execution.get("result_path"),
            "one_shot_claim_o_excl": execution.get("one_shot_claim_o_excl"),
            "claim_is_never_automatically_deleted": execution.get(
                "claim_is_never_automatically_deleted"
            ),
            "claim_and_result_parent_directory_fsync": execution.get(
                "claim_and_result_parent_directory_fsync"
            ),
            "gate_evaluator_sha256": execution.get("gate_evaluator_sha256"),
        },
        "functional_runtime_source_pins": functional_source_pins,
        "failures": failures,
        "allows_exactly_one_module_one_case_fake_q8_smoke": ready,
        "allows_weight_mutation": False,
        "allows_quantized_weight_writing": False,
        "allows_runtime_candidate_generation": False,
        "allows_worker_socket_use": False,
        "allows_audio_decode_write_or_playback": False,
        "allows_runtime_wiring_fallback_deployment_or_promotion": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--activation-gate", required=True, type=Path)
    parser.add_argument("--activation-capture", required=True, type=Path)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--token-boundary-probe", required=True, type=Path)
    parser.add_argument("--runtime-manifest", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--thresholds", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    input_paths = {
        "policy": args.policy,
        "plan": args.plan,
        "activation_gate": args.activation_gate,
        "activation_capture": args.activation_capture,
        "scope": args.scope,
        "probe": args.token_boundary_probe,
        "manifest": args.runtime_manifest,
        "corpus": args.corpus,
        "thresholds": args.thresholds,
    }
    if not all(path.is_file() for path in input_paths.values()):
        parser.error("all frozen prerequisite files must exist")
    if args.output.exists() or args.output.is_symlink():
        parser.error("refusing to overwrite or follow output")
    documents = {
        key: json.loads(path.read_text(encoding="utf-8"))
        for key, path in input_paths.items()
        if key != "activation_capture"
    }
    hashes = {key: sha256(path) for key, path in input_paths.items()}
    report = evaluate(
        documents["policy"],
        documents["plan"],
        documents["activation_gate"],
        documents["scope"],
        documents["probe"],
        documents["manifest"],
        documents["corpus"],
        documents["thresholds"],
        hashes,
    )
    try:
        exclusive_write_json(args.output, report)
    except (FileExistsError, OSError, ValueError) as error:
        parser.error(f"exclusive gate receipt write failed: {error}")
    print(
        json.dumps(
            {
                "status": report["status"],
                "failure_count": len(report["failures"]),
                "target_module": report["target"].get("module"),
                "case_id": report["case"].get("id"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == READY else 2


if __name__ == "__main__":
    raise SystemExit(main())
