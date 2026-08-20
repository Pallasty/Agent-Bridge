from __future__ import annotations

import importlib.util
import json
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/eval/qwen3_codec_runtime_route_gate.py"
REAL_PACK = ROOT / "docs/reports/qwen3-tts-quantization/2026-08-20-codec-runtime-route-decision-v1"
SPEC = importlib.util.spec_from_file_location("qwen3_codec_runtime_route_gate", SCRIPT)
assert SPEC and SPEC.loader
route = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(route)


def dump(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value) + "\n")
    return path


def inputs(tmp_path: Path) -> Namespace:
    packed = dump(tmp_path / "packed.json", {"schema": route.SCHEMAS["packed"],
        "rows": [{"slowdown": 12.0}]})
    coreml = dump(tmp_path / "coreml.json", {"schema": route.SCHEMAS["coreml"],
        "latency_ms": {"fastest_coreml_q8_vs_mps_fake": 3.4},
        "numeric": {"coreml_q8_vs_frozen_fake_q8_nrmse": 0.003}})
    e2e = dump(tmp_path / "e2e.json", {"schema": route.SCHEMAS["e2e"],
        "cases": [{"q8_to_fp16_ratio": 1.02}], "memory": {
            "fp16_steady_bytes": 4_000_000_000,
            "original_fp16_scope_parameter_bytes_retained": 25_000_000,
            "sidecar_bytes": 12_500_000,
            "q8_minus_fp16_bytes": 12_500_000}})
    return Namespace(packed=packed, coreml=coreml, e2e=e2e)


def test_route_gate_rejects_current_routes_and_defers_tiny_rewrite(tmp_path: Path) -> None:
    decision, copied = route.build(inputs(tmp_path))
    assert decision["status"] == "PAUSE_CURRENT_CODEC_RUNTIME_ROUTES"
    assert [item["decision"] for item in decision["routes"]] == ["reject", "reject", "reject", "defer"]
    assert decision["routes"][3]["theoretical_model_memory_saving_fraction"] == 0.003125
    assert all(value is False for value in decision["authorization"].values())
    assert set(copied) == {"packed.json", "coreml.json", "e2e.json"}


def test_route_gate_rejects_wrong_schema(tmp_path: Path) -> None:
    args = inputs(tmp_path)
    args.packed.write_text('{"schema":"wrong","rows":[]}\n')
    try:
        route.build(args)
    except route.RouteError as error:
        assert "schema_mismatch" in str(error)
    else:
        raise AssertionError("schema drift accepted")


def test_route_gate_fails_closed_on_missing_nested_contract(tmp_path: Path) -> None:
    args = inputs(tmp_path)
    args.e2e.write_text(json.dumps({"schema": route.SCHEMAS["e2e"]}) + "\n")
    try:
        route.build(args)
    except route.RouteError as error:
        assert "e2e.cases:nonempty_array" in str(error)
    else:
        raise AssertionError("missing nested contract accepted")


def test_real_runtime_route_pack_reproduces_exact_decision() -> None:
    args = Namespace(
        packed=REAL_PACK / "inputs/packed.json",
        coreml=REAL_PACK / "inputs/coreml.json",
        e2e=REAL_PACK / "inputs/e2e.json",
    )
    reproduced, _ = route.build(args)
    frozen = json.loads((REAL_PACK / "decision.json").read_text())
    assert reproduced == frozen
    assert frozen["status"] == "PAUSE_CURRENT_CODEC_RUNTIME_ROUTES"
    assert all(value is False for value in frozen["authorization"].values())
