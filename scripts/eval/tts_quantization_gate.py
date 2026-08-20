#!/usr/bin/env python3
"""Evaluate a normalized TTS quantization evidence bundle without mutating it."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "agent_bridge.tts_quantization_candidate.v1"
POLICY_SCHEMA = "agent_bridge.tts_quantization_gate_policy.v1"
RECEIPT_SCHEMA = "agent_bridge.tts_quantization_gate_receipt.v1"
BOUNDARY_REQUIREMENT = {
    "autoregressive": "autoregressive_trajectory",
    "codec": "waveform_numeric",
    "feedforward": "tensor_numeric",
}
KNOWN_EVIDENCE = {
    "static_shadow",
    "tensor_numeric",
    "autoregressive_trajectory",
    "waveform_numeric",
    "blind_listening",
    "runtime_benchmark",
}
AUTHORIZATION = {
    "allows_weight_writing": False,
    "allows_checkpoint_rewrite": False,
    "allows_audio_generation_or_playback": False,
    "allows_runtime_wiring": False,
    "allows_deployment": False,
    "allows_promotion": False,
}


class ContractError(ValueError):
    """Raised when an input is not a valid, closed-world gate contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def require_dict(value: Any, name: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{name}:expected_object")
    return value


def require_list(value: Any, name: str) -> list[Any]:
    require(isinstance(value, list), f"{name}:expected_array")
    return value


def exact_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    observed = set(value)
    require(observed == expected, f"{name}:keys:{sorted(observed ^ expected)}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    require(path.is_file() and not path.is_symlink(), f"input_not_regular_file:{path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError(f"invalid_json:{path}") from error
    return require_dict(value, str(path)), raw


def finite_number(value: Any, name: str, *, minimum: float | None = None) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{name}:expected_number")
    number = float(value)
    require(math.isfinite(number), f"{name}:nonfinite")
    if minimum is not None:
        require(number >= minimum, f"{name}:below_minimum")
    return number


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    exact_keys(
        policy,
        {"schema", "required_case_count", "require_blind_listening_for_codec", "resource_limits", "authorization"},
        "policy",
    )
    require(policy["schema"] == POLICY_SCHEMA, "policy:schema")
    required_cases = policy["required_case_count"]
    require(isinstance(required_cases, int) and not isinstance(required_cases, bool) and required_cases > 0,
            "policy:required_case_count")
    require(isinstance(policy["require_blind_listening_for_codec"], bool),
            "policy:require_blind_listening_for_codec")
    limits = require_dict(policy["resource_limits"], "policy.resource_limits")
    exact_keys(limits, {"max_latency_ratio", "require_artifact_smaller", "require_runtime_memory_nonincrease"},
               "policy.resource_limits")
    max_latency = finite_number(limits["max_latency_ratio"], "policy.resource_limits.max_latency_ratio", minimum=0.0)
    require(max_latency > 0.0, "policy.resource_limits.max_latency_ratio:must_be_positive")
    for key in ("require_artifact_smaller", "require_runtime_memory_nonincrease"):
        require(isinstance(limits[key], bool), f"policy.resource_limits.{key}")
    authorization = require_dict(policy["authorization"], "policy.authorization")
    exact_keys(authorization, set(AUTHORIZATION), "policy.authorization")
    require(authorization == AUTHORIZATION, "policy:contains_operational_authority")
    return policy


def validate_manifest(manifest: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    exact_keys(manifest, {"schema", "candidate", "corpus", "components", "evidence"}, "manifest")
    require(manifest["schema"] == MANIFEST_SCHEMA, "manifest:schema")

    candidate = require_dict(manifest["candidate"], "manifest.candidate")
    exact_keys(candidate, {"id", "model", "quantization", "artifact"}, "manifest.candidate")
    for key in ("id", "model", "quantization"):
        require(isinstance(candidate[key], str) and candidate[key], f"manifest.candidate.{key}")
    artifact = require_dict(candidate["artifact"], "manifest.candidate.artifact")
    exact_keys(artifact, {"baseline_bytes", "candidate_bytes"}, "manifest.candidate.artifact")
    for key in artifact:
        require(isinstance(artifact[key], int) and not isinstance(artifact[key], bool) and artifact[key] > 0,
                f"manifest.candidate.artifact.{key}")

    corpus = require_dict(manifest["corpus"], "manifest.corpus")
    exact_keys(corpus, {"id", "path", "sha256", "case_ids"}, "manifest.corpus")
    require(isinstance(corpus["id"], str) and corpus["id"], "manifest.corpus.id")
    require(isinstance(corpus["sha256"], str) and len(corpus["sha256"]) == 64,
            "manifest.corpus.sha256")
    corpus_path = Path(corpus["path"])
    if not corpus_path.is_absolute():
        corpus_path = manifest_dir / corpus_path
    corpus_document, corpus_raw = load_json(corpus_path)
    del corpus_document
    require(sha256_bytes(corpus_raw) == corpus["sha256"], "manifest.corpus:sha256_mismatch")
    case_ids = require_list(corpus["case_ids"], "manifest.corpus.case_ids")
    require(case_ids and all(isinstance(item, str) and item for item in case_ids), "manifest.corpus.case_ids")
    require(len(case_ids) == len(set(case_ids)), "manifest.corpus.case_ids:duplicates")

    components = require_list(manifest["components"], "manifest.components")
    require(components, "manifest.components:empty")
    component_names: set[str] = set()
    for index, component_value in enumerate(components):
        component = require_dict(component_value, f"manifest.components[{index}]")
        exact_keys(component, {"name", "boundary"}, f"manifest.components[{index}]")
        require(isinstance(component["name"], str) and component["name"], f"manifest.components[{index}].name")
        require(component["name"] not in component_names, "manifest.components:duplicate_name")
        component_names.add(component["name"])
        require(component["boundary"] in BOUNDARY_REQUIREMENT, f"manifest.components[{index}].boundary")

    evidence = require_list(manifest["evidence"], "manifest.evidence")
    seen_kinds: set[str] = set()
    normalized = []
    for index, item_value in enumerate(evidence):
        item = require_dict(item_value, f"manifest.evidence[{index}]")
        exact_keys(item, {"kind", "path", "sha256", "status", "case_ids", "metrics"},
                   f"manifest.evidence[{index}]")
        kind = item["kind"]
        require(kind in KNOWN_EVIDENCE, f"manifest.evidence[{index}].kind")
        require(kind not in seen_kinds, f"manifest.evidence:duplicate_kind:{kind}")
        seen_kinds.add(kind)
        require(item["status"] in {"PASS", "FAIL"}, f"manifest.evidence[{index}].status")
        evidence_cases = require_list(item["case_ids"], f"manifest.evidence[{index}].case_ids")
        require(all(isinstance(case, str) and case for case in evidence_cases),
                f"manifest.evidence[{index}].case_ids")
        require(len(evidence_cases) == len(set(evidence_cases)),
                f"manifest.evidence[{index}].case_ids:duplicates")
        metrics = require_dict(item["metrics"], f"manifest.evidence[{index}].metrics")
        evidence_path = Path(item["path"])
        if not evidence_path.is_absolute():
            evidence_path = manifest_dir / evidence_path
        document, raw = load_json(evidence_path)
        del document  # Contents remain producer-owned; this gate binds the exact bytes.
        observed_sha = sha256_bytes(raw)
        require(item["sha256"] == observed_sha, f"manifest.evidence[{index}]:sha256_mismatch")
        normalized.append({**item, "observed_sha256": observed_sha})
    return {**manifest, "corpus": {**corpus, "observed_sha256": sha256_bytes(corpus_raw)},
            "evidence": normalized}


def evaluate(manifest: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    corpus_cases = set(manifest["corpus"]["case_ids"])
    required_count = policy["required_case_count"]
    missing: list[str] = []
    rejected: list[str] = []
    evidence_by_kind = {item["kind"]: item for item in manifest["evidence"]}

    for kind, item in sorted(evidence_by_kind.items()):
        if kind != "static_shadow" and item["status"] == "FAIL":
            rejected.append(f"evidence_failed:{kind}")

    if len(corpus_cases) < required_count:
        missing.append(f"corpus_cases:{required_count}_required_{len(corpus_cases)}_observed")

    required_kinds = {BOUNDARY_REQUIREMENT[item["boundary"]] for item in manifest["components"]}
    if any(item["boundary"] == "codec" for item in manifest["components"]):
        if policy["require_blind_listening_for_codec"]:
            required_kinds.add("blind_listening")
    required_kinds.add("runtime_benchmark")

    for kind in sorted(required_kinds):
        item = evidence_by_kind.get(kind)
        if item is None:
            missing.append(f"evidence_missing:{kind}")
            continue
        observed_cases = set(item["case_ids"])
        if not corpus_cases.issubset(observed_cases):
            missing.append(f"evidence_case_coverage:{kind}")
    runtime = evidence_by_kind.get("runtime_benchmark")
    if runtime is not None:
        metrics = runtime["metrics"]
        expected_keys = {"max_latency_ratio", "runtime_memory_delta_bytes"}
        require(set(metrics) == expected_keys, "runtime_benchmark.metrics:keys")
        latency = finite_number(metrics["max_latency_ratio"], "runtime_benchmark.max_latency_ratio", minimum=0.0)
        memory_value = metrics["runtime_memory_delta_bytes"]
        memory_delta = None if memory_value is None else finite_number(
            memory_value, "runtime_benchmark.runtime_memory_delta_bytes"
        )
        if latency > policy["resource_limits"]["max_latency_ratio"]:
            rejected.append("resource_limit:max_latency_ratio")
        if policy["resource_limits"]["require_runtime_memory_nonincrease"]:
            if memory_delta is None:
                missing.append("resource_metric:runtime_memory_delta_bytes")
            elif memory_delta > 0:
                rejected.append("resource_limit:runtime_memory_increased")

    artifact = manifest["candidate"]["artifact"]
    if policy["resource_limits"]["require_artifact_smaller"]:
        if artifact["candidate_bytes"] >= artifact["baseline_bytes"]:
            rejected.append("resource_limit:artifact_not_smaller")

    if rejected:
        decision = "reject"
    elif missing:
        decision = "insufficient_evidence"
    else:
        decision = "pass"
    return {
        "decision": decision,
        "missing_evidence": sorted(set(missing)),
        "rejection_reasons": sorted(set(rejected)),
        "required_evidence_kinds": sorted(required_kinds),
        "shadow_evidence_observed": "static_shadow" in evidence_by_kind,
    }


def build_receipt(manifest_path: Path, policy_path: Path) -> dict[str, Any]:
    manifest_document, manifest_raw = load_json(manifest_path)
    policy_document, policy_raw = load_json(policy_path)
    policy = validate_policy(policy_document)
    manifest = validate_manifest(manifest_document, manifest_path.parent)
    result = evaluate(manifest, policy)
    return {
        "schema": RECEIPT_SCHEMA,
        "decision": result["decision"],
        "candidate_id": manifest["candidate"]["id"],
        "model": manifest["candidate"]["model"],
        "manifest_sha256": sha256_bytes(manifest_raw),
        "policy_sha256": sha256_bytes(policy_raw),
        "corpus": {
            "id": manifest["corpus"]["id"],
            "sha256": manifest["corpus"]["observed_sha256"],
            "case_ids": manifest["corpus"]["case_ids"],
        },
        "components": manifest["components"],
        "evidence": [
            {
                "kind": item["kind"],
                "sha256": item["observed_sha256"],
                "status": item["status"],
                "case_count": len(item["case_ids"]),
            }
            for item in manifest["evidence"]
        ],
        "required_evidence_kinds": result["required_evidence_kinds"],
        "shadow_evidence_observed": result["shadow_evidence_observed"],
        "missing_evidence": result["missing_evidence"],
        "rejection_reasons": result["rejection_reasons"],
        "authorization": dict(AUTHORIZATION),
    }


def write_exclusive_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = build_receipt(args.manifest, args.policy)
        write_exclusive_json(args.output, receipt)
    except (ContractError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({"decision": receipt["decision"], "output": str(args.output)}, sort_keys=True))
    return 0 if receipt["decision"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
