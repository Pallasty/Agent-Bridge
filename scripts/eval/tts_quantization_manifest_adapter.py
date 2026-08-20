#!/usr/bin/env python3
"""Adapt frozen native Qwen or OmniVoice reports into the unified gate manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "agent_bridge.tts_quantization_candidate.v1"
QWEN_WAVEFORM_SCHEMA = "agent_bridge.qwen3_tts.codec_linear_perchannel_q8_scope3_expansion_evidence.v1"
QWEN_LISTENING_SCHEMA = "agent_bridge.qwen3_tts.codec_linear_scope3_blind_ab_owner_review.v1"
QWEN_RUNTIME_SCHEMA = "agent_bridge.qwen3_tts.codec_scope3_e2e_reduction.v1"
OMNI_SUMMARY_SCHEMA = "agent_bridge.omnivoice_static_int8_summary.v0"
OMNI_TRAJECTORY_SCHEMA = "agent_bridge.omnivoice.autoregressive_trajectory_reduction.v1"


class AdapterError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AdapterError(message)


def load(path: Path) -> tuple[dict[str, Any], str]:
    require(path.is_file() and not path.is_symlink(), f"input_not_regular_file:{path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdapterError(f"invalid_json:{path}") from error
    require(isinstance(value, dict), f"expected_object:{path}")
    return value, hashlib.sha256(raw).hexdigest()


def finite(value: Any, name: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{name}:number")
    result = float(value)
    require(math.isfinite(result), f"{name}:nonfinite")
    return result


def object_value(value: Any, name: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{name}:object")
    return value


def relative_path(target: Path, output: Path) -> str:
    return os.path.relpath(target.resolve(), output.parent.resolve())


def evidence(kind: str, path: Path, digest: str, status: str, cases: list[str], metrics: dict) -> dict:
    return {"kind": kind, "path": str(path), "sha256": digest, "status": status,
            "case_ids": cases, "metrics": metrics}


def corpus_identity(path: Path, output: Path, case_ids: list[str]) -> dict:
    document, digest = load(path)
    if "case_ids" in document:
        observed = document["case_ids"]
        require(isinstance(observed, list) and all(isinstance(item, str) for item in observed),
                "corpus.case_ids:strings")
    elif "cases" in document:
        rows = document["cases"]
        require(isinstance(rows, list), "corpus.cases:array")
        observed = []
        for index, row in enumerate(rows):
            require(isinstance(row, dict), f"corpus.cases[{index}]:object")
            value = row.get("case_id")
            require(isinstance(value, str) and value, f"corpus.cases[{index}].case_id")
            observed.append(value)
    elif "results" in document:
        rows = document["results"]
        require(isinstance(rows, list), "corpus.results:array")
        observed = []
        for index, row in enumerate(rows):
            require(isinstance(row, dict), f"corpus.results[{index}]:object")
            value = row.get("prompt")
            require(isinstance(value, str) and value, f"corpus.results[{index}].prompt")
            observed.append(value)
    else:
        raise AdapterError("corpus:case_identity_missing")
    require(observed == case_ids, "corpus:case_order_mismatch")
    return {"id": path.stem, "path": relative_path(path, output), "sha256": digest,
            "case_ids": case_ids}


def unique_case_ids(rows: Any, name: str) -> list[str]:
    require(isinstance(rows, list) and rows, f"{name}:empty")
    result = []
    for index, row in enumerate(rows):
        require(isinstance(row, dict), f"{name}[{index}]:object")
        case_id = row.get("case_id")
        require(isinstance(case_id, str) and case_id, f"{name}[{index}].case_id")
        result.append(case_id)
    require(len(result) == len(set(result)), f"{name}:duplicate_case")
    return result


def adapt_qwen(args: argparse.Namespace) -> dict:
    waveform, waveform_sha = load(args.waveform)
    listening, listening_sha = load(args.listening)
    runtime, runtime_sha = load(args.runtime)
    require(waveform.get("schema") == QWEN_WAVEFORM_SCHEMA, "qwen:waveform_schema")
    require(listening.get("schema") == QWEN_LISTENING_SCHEMA, "qwen:listening_schema")
    require(runtime.get("schema") == QWEN_RUNTIME_SCHEMA, "qwen:runtime_schema")

    waveform_rows = waveform.get("prompt_results")
    cases = unique_case_ids(waveform_rows, "qwen.waveform.prompt_results")
    summary = object_value(waveform.get("summary"), "qwen.waveform.summary")
    waveform_pass = (
        waveform.get("status") == "PERCHANNEL_Q8_SCOPE3_BLIND_AB_PLAN_AUTHORIZED"
        and all(row.get("passed") is True for row in waveform_rows)
        and summary.get("prompts") == len(cases)
        and summary.get("passed") == len(cases)
    )

    review_rows = listening.get("reviews")
    review_cases = unique_case_ids(review_rows, "qwen.listening.reviews")
    require(review_cases == cases, "qwen:listening_case_order_mismatch")
    acceptable_artifacts = {"none", "no_obvious_defect"}
    listening_pass = (
        listening.get("status") == "OWNER_REVIEW_COMPLETE_BLINDED_RESPONSES_SEALED"
        and listening.get("blinding_intact") is True
        and listening.get("completed_cases") == len(cases)
        and listening.get("total_cases") == len(cases)
        and all(row.get("arm_identity_known") is False for row in review_rows)
        and all(row.get("artifacts_or_noise") in acceptable_artifacts for row in review_rows)
    )

    runtime_rows = runtime.get("cases")
    runtime_cases = unique_case_ids(runtime_rows, "qwen.runtime.cases")
    require(set(runtime_cases).issubset(set(cases)), "qwen:runtime_unknown_case")
    ratios = [finite(row.get("q8_to_fp16_ratio"), "qwen.runtime.q8_to_fp16_ratio")
              for row in runtime_rows]
    memory = object_value(runtime.get("memory"), "qwen.runtime.memory")
    memory_delta = finite(memory.get("q8_minus_fp16_bytes"), "qwen.runtime.q8_minus_fp16_bytes")
    gates = object_value(runtime.get("gates"), "qwen.runtime.gates")
    runtime_pass = (
        runtime.get("status") != "SCOPE3_RUNTIME_INTEGRATION_REJECTED_NO_END_TO_END_BENEFIT"
        and gates.get("latency_must_not_regress") is True
        and gates.get("runtime_memory_must_decrease") is True
        and len(runtime_cases) == len(cases)
    )
    sidecar = object_value(waveform.get("sidecar"), "qwen.waveform.sidecar")
    baseline_bytes = sidecar.get("source_fp32_bytes")
    candidate_bytes = sidecar.get("bytes")
    require(isinstance(baseline_bytes, int) and baseline_bytes > 0, "qwen:source_fp32_bytes")
    require(isinstance(candidate_bytes, int) and candidate_bytes > 0, "qwen:sidecar_bytes")

    return {
        "schema": MANIFEST_SCHEMA,
        "candidate": {"id": "qwen3-tts-codec-scope3-native-perchannel-q8",
                      "model": "Qwen3-TTS-12Hz-1.7B-CustomVoice",
                      "quantization": "three-codec-linear-per-output-channel-int8",
                      "artifact": {"baseline_bytes": baseline_bytes, "candidate_bytes": candidate_bytes}},
        "corpus": corpus_identity(args.corpus, args.output, cases),
        "components": [{"name": "speech_tokenizer.decoder.scope3", "boundary": "codec"}],
        "evidence": [
            evidence("waveform_numeric", Path(relative_path(args.waveform, args.output)), waveform_sha,
                     "PASS" if waveform_pass else "FAIL", cases, {}),
            evidence("blind_listening", Path(relative_path(args.listening, args.output)), listening_sha,
                     "PASS" if listening_pass else "FAIL", review_cases, {}),
            evidence("runtime_benchmark", Path(relative_path(args.runtime, args.output)), runtime_sha,
                     "PASS" if runtime_pass else "FAIL", runtime_cases,
                     {"max_latency_ratio": max(ratios), "runtime_memory_delta_bytes": memory_delta}),
        ],
    }


def adapt_omnivoice(args: argparse.Namespace) -> dict:
    summary, summary_sha = load(args.summary)
    require(summary.get("schema") == OMNI_SUMMARY_SCHEMA, "omnivoice:summary_schema")
    rows = summary.get("results")
    require(isinstance(rows, list) and rows, "omnivoice:results_empty")
    cases = []
    for index, row in enumerate(rows):
        require(isinstance(row, dict), f"omnivoice.results[{index}]:object")
        prompt = row.get("prompt")
        require(isinstance(prompt, str) and prompt, f"omnivoice.results[{index}].prompt")
        cases.append(prompt)
        finite(row.get("guided_top1"), f"omnivoice.results[{index}].guided_top1")
        finite(row.get("guided_cosine"), f"omnivoice.results[{index}].guided_cosine")
    require(len(cases) == len(set(cases)), "omnivoice:duplicate_prompt")
    gate = object_value(summary.get("gate"), "omnivoice.gate")
    top1_min = finite(gate.get("guided_top1_min"), "omnivoice.gate.guided_top1_min")
    cosine_min = finite(gate.get("guided_cosine_min"), "omnivoice.gate.guided_cosine_min")
    numeric_pass = (
        summary.get("decision") != "reject_static_int8_candidate"
        and all(row["guided_top1"] >= top1_min and row["guided_cosine"] >= cosine_min for row in rows)
    )
    candidate = object_value(summary.get("candidate"), "omnivoice.candidate")
    baseline_bytes = candidate.get("source_bytes")
    candidate_bytes = candidate.get("bytes")
    require(isinstance(baseline_bytes, int) and baseline_bytes > 0, "omnivoice:source_bytes")
    require(isinstance(candidate_bytes, int) and candidate_bytes > 0, "omnivoice:candidate_bytes")
    evidence_rows = [
        evidence("tensor_numeric", Path(relative_path(args.summary, args.output)), summary_sha,
                 "PASS" if numeric_pass else "FAIL", cases,
                 {"min_guided_top1": min(row["guided_top1"] for row in rows),
                  "min_guided_cosine": min(row["guided_cosine"] for row in rows)}),
    ]
    if getattr(args, "trajectory", None) is not None:
        reduction, reduction_sha = load(args.trajectory)
        require(reduction.get("schema") == OMNI_TRAJECTORY_SCHEMA, "omnivoice:trajectory_schema")
        trajectory_rows = reduction.get("cases")
        trajectory_cases = unique_case_ids(trajectory_rows, "omnivoice.trajectory.cases")
        require(set(trajectory_cases).issubset(set(cases)), "omnivoice:trajectory_unknown_case")
        trajectory_pass = reduction.get("status") == "PASS" and all(
            row.get("status") == "PASS" and row.get("control_exact") is True
            for row in trajectory_rows
        )
        agreements = [finite(row.get("final_token_agreement"),
                             "omnivoice.trajectory.final_token_agreement") for row in trajectory_rows]
        evidence_rows.append(evidence(
            "autoregressive_trajectory", Path(relative_path(args.trajectory, args.output)), reduction_sha,
            "PASS" if trajectory_pass else "FAIL", trajectory_cases,
            {"minimum_final_token_agreement": min(agreements)},
        ))
    return {
        "schema": MANIFEST_SCHEMA,
        "candidate": {"id": "omnivoice-llm-static-int8", "model": "OmniVoice",
                      "quantization": str(candidate.get("method", "static-int8")),
                      "artifact": {"baseline_bytes": baseline_bytes, "candidate_bytes": candidate_bytes}},
        "corpus": corpus_identity(args.summary, args.output, cases),
        "components": [{"name": "omnivoice.llm", "boundary": "autoregressive"}],
        "evidence": evidence_rows,
    }


def write_exclusive(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="adapter", required=True)
    qwen = subparsers.add_parser("qwen-codec-scope3")
    qwen.add_argument("--waveform", required=True, type=Path)
    qwen.add_argument("--listening", required=True, type=Path)
    qwen.add_argument("--runtime", required=True, type=Path)
    qwen.add_argument("--corpus", required=True, type=Path)
    qwen.add_argument("--output", required=True, type=Path)
    omni = subparsers.add_parser("omnivoice-static-int8")
    omni.add_argument("--summary", required=True, type=Path)
    omni.add_argument("--trajectory", type=Path,
                      help="optional full 32-step trajectory reduction")
    omni.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = adapt_qwen(args) if args.adapter == "qwen-codec-scope3" else adapt_omnivoice(args)
        write_exclusive(args.output, value)
    except (AdapterError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({"adapter": args.adapter, "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
