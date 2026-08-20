from __future__ import annotations

import importlib.util
import json
from argparse import Namespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


adapter = module("tts_quantization_manifest_adapter", "scripts/eval/tts_quantization_manifest_adapter.py")
gate = module("tts_quantization_gate_for_adapter", "scripts/eval/tts_quantization_gate.py")
POLICY = ROOT / "scripts/eval/fixtures/tts_quantization_gate_policy_v1.json"
FROZEN = ROOT / "tests/fixtures/tts_quantization"
CASES = ["case-a", "case-b", "case-c", "case-d"]


def dump(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return path


def qwen_inputs(tmp_path: Path) -> Namespace:
    waveform = dump(tmp_path / "waveform.json", {
        "schema": adapter.QWEN_WAVEFORM_SCHEMA,
        "status": "PERCHANNEL_Q8_SCOPE3_BLIND_AB_PLAN_AUTHORIZED",
        "prompt_results": [{"case_id": case, "passed": True} for case in CASES],
        "summary": {"prompts": 4, "passed": 4},
        "sidecar": {"source_fp32_bytes": 4000, "bytes": 1000},
    })
    listening = dump(tmp_path / "listening.json", {
        "schema": adapter.QWEN_LISTENING_SCHEMA,
        "status": "OWNER_REVIEW_COMPLETE_BLINDED_RESPONSES_SEALED",
        "completed_cases": 4,
        "total_cases": 4,
        "blinding_intact": True,
        "reviews": [{"case_id": case, "arm_identity_known": False,
                     "artifacts_or_noise": "none"} for case in CASES],
    })
    runtime = dump(tmp_path / "runtime.json", {
        "schema": adapter.QWEN_RUNTIME_SCHEMA,
        "status": "SCOPE3_RUNTIME_INTEGRATION_ACCEPTED",
        "cases": [{"case_id": case, "q8_to_fp16_ratio": 1.01} for case in CASES],
        "memory": {"q8_minus_fp16_bytes": -1000},
        "gates": {"latency_must_not_regress": True, "runtime_memory_must_decrease": True},
    })
    corpus = dump(tmp_path / "corpus.json", {"case_ids": CASES})
    return Namespace(waveform=waveform, listening=listening, runtime=runtime, corpus=corpus,
                     output=tmp_path / "manifest.json")


def test_qwen_adapter_maps_complete_native_chain_to_pass(tmp_path: Path) -> None:
    args = qwen_inputs(tmp_path)
    value = adapter.adapt_qwen(args)
    adapter.write_exclusive(args.output, value)
    receipt = gate.build_receipt(args.output, POLICY)
    assert receipt["decision"] == "pass"
    assert [item["kind"] for item in value["evidence"]] == [
        "waveform_numeric", "blind_listening", "runtime_benchmark"
    ]


def test_qwen_adapter_preserves_native_runtime_rejection(tmp_path: Path) -> None:
    args = qwen_inputs(tmp_path)
    runtime = json.loads(args.runtime.read_text())
    runtime["status"] = "SCOPE3_RUNTIME_INTEGRATION_REJECTED_NO_END_TO_END_BENEFIT"
    runtime["memory"]["q8_minus_fp16_bytes"] = 1000
    dump(args.runtime, runtime)
    value = adapter.adapt_qwen(args)
    adapter.write_exclusive(args.output, value)
    receipt = gate.build_receipt(args.output, POLICY)
    assert receipt["decision"] == "reject"
    assert "evidence_failed:runtime_benchmark" in receipt["rejection_reasons"]


def test_qwen_adapter_rejects_schema_drift(tmp_path: Path) -> None:
    args = qwen_inputs(tmp_path)
    waveform = json.loads(args.waveform.read_text())
    waveform["schema"] = "drifted"
    dump(args.waveform, waveform)
    with pytest.raises(adapter.AdapterError, match="waveform_schema"):
        adapter.adapt_qwen(args)


def test_qwen_adapter_rejects_corpus_case_identity_drift(tmp_path: Path) -> None:
    args = qwen_inputs(tmp_path)
    dump(args.corpus, {"case_ids": [*CASES[:-1], "different-case"]})
    with pytest.raises(adapter.AdapterError, match="corpus:case_order_mismatch"):
        adapter.adapt_qwen(args)


def test_qwen_adapter_rejects_malformed_nested_contract(tmp_path: Path) -> None:
    args = qwen_inputs(tmp_path)
    waveform = json.loads(args.waveform.read_text())
    waveform["summary"] = []
    dump(args.waveform, waveform)
    with pytest.raises(adapter.AdapterError, match="qwen.waveform.summary:object"):
        adapter.adapt_qwen(args)


def omni_args(tmp_path: Path, decision: str = "reject_static_int8_candidate") -> Namespace:
    summary = dump(tmp_path / "summary.json", {
        "schema": adapter.OMNI_SUMMARY_SCHEMA,
        "decision": decision,
        "candidate": {"method": "static QDQ int8", "source_bytes": 4000, "bytes": 1000},
        "gate": {"guided_top1_min": 0.999, "guided_cosine_min": 0.9999},
        "results": [
            {"prompt": "en94", "guided_top1": 0.2, "guided_cosine": 0.99},
            {"prompt": "zh57", "guided_top1": 0.3, "guided_cosine": 0.98},
            {"prompt": "clone50", "guided_top1": 0.1, "guided_cosine": 0.95},
        ],
    })
    return Namespace(summary=summary, trajectory=None, output=tmp_path / "manifest.json")


def test_omnivoice_one_step_report_is_not_mislabeled_as_trajectory_or_runtime(tmp_path: Path) -> None:
    args = omni_args(tmp_path)
    value = adapter.adapt_omnivoice(args)
    assert [item["kind"] for item in value["evidence"]] == ["tensor_numeric"]
    assert value["evidence"][0]["status"] == "FAIL"
    adapter.write_exclusive(args.output, value)
    receipt = gate.build_receipt(args.output, POLICY)
    assert receipt["decision"] == "reject"
    assert "evidence_failed:tensor_numeric" in receipt["rejection_reasons"]
    assert "evidence_missing:autoregressive_trajectory" in receipt["missing_evidence"]
    assert "evidence_missing:runtime_benchmark" in receipt["missing_evidence"]


def test_omnivoice_thresholds_override_optimistic_decision_text(tmp_path: Path) -> None:
    args = omni_args(tmp_path, decision="pass_static_int8_candidate")
    value = adapter.adapt_omnivoice(args)
    assert value["evidence"][0]["status"] == "FAIL"


def test_omnivoice_adapter_accepts_only_frozen_full_trajectory_schema(tmp_path: Path) -> None:
    args = omni_args(tmp_path)
    args.trajectory = dump(tmp_path / "trajectory.json", {
        "schema": adapter.OMNI_TRAJECTORY_SCHEMA,
        "status": "FAIL",
        "cases": [{"case_id": "en94", "status": "FAIL", "control_exact": True,
                   "final_token_agreement": 0.2}],
    })
    value = adapter.adapt_omnivoice(args)
    assert [item["kind"] for item in value["evidence"]] == [
        "tensor_numeric", "autoregressive_trajectory"
    ]
    assert value["evidence"][1]["status"] == "FAIL"
    changed = json.loads(args.trajectory.read_text())
    changed["schema"] = "drifted"
    dump(args.trajectory, changed)
    with pytest.raises(adapter.AdapterError, match="trajectory_schema"):
        adapter.adapt_omnivoice(args)


def test_adapter_exclusive_output_refuses_overwrite(tmp_path: Path) -> None:
    args = qwen_inputs(tmp_path)
    value = adapter.adapt_qwen(args)
    adapter.write_exclusive(args.output, value)
    original = args.output.read_bytes()
    with pytest.raises(FileExistsError):
        adapter.write_exclusive(args.output, value)
    assert args.output.read_bytes() == original


def test_frozen_qwen_native_evidence_preserves_runtime_rejection(tmp_path: Path) -> None:
    args = Namespace(
        waveform=FROZEN / "qwen_waveform.json",
        listening=FROZEN / "qwen_listening.json",
        runtime=FROZEN / "qwen_runtime_rejected.json",
        corpus=FROZEN / "qwen_corpus.json",
        output=tmp_path / "qwen-manifest.json",
    )
    adapter.write_exclusive(args.output, adapter.adapt_qwen(args))
    receipt = gate.build_receipt(args.output, POLICY)
    assert receipt["decision"] == "reject"
    assert "evidence_failed:runtime_benchmark" in receipt["rejection_reasons"]
    assert "resource_limit:runtime_memory_increased" in receipt["rejection_reasons"]
    assert "evidence_case_coverage:runtime_benchmark" in receipt["missing_evidence"]


def test_frozen_omnivoice_native_evidence_preserves_quality_rejection(tmp_path: Path) -> None:
    args = Namespace(
        summary=FROZEN / "omnivoice_static_rejected.json",
        trajectory=FROZEN / "omnivoice_trajectory_rejected.json",
        output=tmp_path / "omnivoice-manifest.json",
    )
    adapter.write_exclusive(args.output, adapter.adapt_omnivoice(args))
    receipt = gate.build_receipt(args.output, POLICY)
    assert receipt["decision"] == "reject"
    assert "evidence_failed:tensor_numeric" in receipt["rejection_reasons"]
    assert "evidence_failed:autoregressive_trajectory" in receipt["rejection_reasons"]
    assert "evidence_missing:runtime_benchmark" in receipt["missing_evidence"]
