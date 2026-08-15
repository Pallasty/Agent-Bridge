#!/usr/bin/env python3
"""Build a bounded, read-only activation-hook plan from a Q0 static report."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.activation_probe_plan.v1"
ALLOWED_FAMILIES = {"attention", "feed_forward_or_projection"}
TALKER_LAYER = re.compile(r"^talker\.model\.layers\.(\d+)\.")
ROLE_ORDER = (
    "down_proj",
    "gate_proj",
    "up_proj",
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def module_name(tensor_name: str) -> str:
    return tensor_name[:-7] if tensor_name.endswith(".weight") else tensor_name


def stratified_selection(candidates: list[dict], max_modules: int) -> list[dict]:
    by_layer_role = {}
    for row in candidates:
        match = TALKER_LAYER.match(row["module"])
        role = row["module"].rsplit(".", 1)[-1]
        if match and role in ROLE_ORDER:
            by_layer_role[(int(match.group(1)), role)] = row
    layers = sorted({layer for layer, _ in by_layer_role})
    selected = []
    selected_names = set()
    for round_index in range(len(ROLE_ORDER)):
        for layer_index, layer in enumerate(layers):
            role = ROLE_ORDER[(layer_index + round_index) % len(ROLE_ORDER)]
            row = by_layer_role.get((layer, role))
            if row is not None and row["module"] not in selected_names:
                selected.append(row)
                selected_names.add(row["module"])
                if len(selected) == max_modules:
                    return selected
    remaining = sorted(
        (row for row in candidates if row["module"] not in selected_names),
        key=lambda row: (-row["elements"], row["module"]),
    )
    return [*selected, *remaining[: max_modules - len(selected)]]


def build_plan(report: dict, source_hash: str, max_modules: int) -> dict:
    candidates = []
    for file_report in report.get("files", []):
        if file_report.get("partition") != "talker":
            continue
        for tensor in file_report.get("tensors", []):
            if tensor.get("family") not in ALLOWED_FAMILIES:
                continue
            if not tensor.get("name", "").startswith("talker.model.layers."):
                continue
            shape = tensor.get("shape", [])
            diagnostics = tensor.get("diagnostics") or {}
            if len(shape) != 2 or not diagnostics:
                continue
            candidates.append({
                "module": module_name(tensor["name"]),
                "tensor": tensor["name"],
                "family": tensor["family"],
                "source_dtype": tensor["dtype"],
                "shape": shape,
                "elements": tensor["element_count"],
                "static_q8_nrmse": diagnostics.get("groupwise_q8_nrmse", {}).get("128"),
                "static_entropy_256": diagnostics.get("normalized_entropy", {}).get("256"),
            })
    selected = stratified_selection(candidates, max_modules)
    selected_layers = sorted(
        {
            int(match.group(1))
            for row in selected
            if (match := TALKER_LAYER.match(row["module"]))
        }
    )
    selected_roles = {}
    for row in selected:
        role = row["module"].rsplit(".", 1)[-1]
        selected_roles[role] = selected_roles.get(role, 0) + 1
    return {
        "schema": SCHEMA,
        "status": "PLAN_ONLY_DEFAULT_OFF",
        "static_report_sha256": source_hash,
        "selection": {
            "eligible_families": sorted(ALLOWED_FAMILIES),
            "excluded": ["speech_tokenizer_codec", "text_embedding", "all_code_predictor", "norm_scale_or_bias"],
            "eligible_count": len(candidates),
            "selected_count": len(selected),
            "max_modules": max_modules,
            "algorithm": "layer_role_rotating_stratified_v1",
            "selected_layers": selected_layers,
            "selected_role_counts": dict(sorted(selected_roles.items())),
        },
        "source_assets": [
            {
                "partition": file_report.get("partition"),
                "bytes": file_report.get("bytes"),
                "sha256": file_report.get("sha256"),
            }
            for file_report in report.get("files", [])
        ],
        "capture_budget": {
            "values_per_module_max": 4096,
            "histogram_bins": [64, 256],
            "global_host_bytes_max": 268435456,
            "retain_full_activations": False,
            "detach_to_cpu_float32": True,
            "statistics": ["count", "sample_min", "sample_max", "mean", "rms", "variance", "kurtosis", "zero_ratio", "outlier_ratio", "sample_normalized_entropy"],
        },
        "execution_boundary": {
            "loads_separate_offline_model": True,
            "modifies_worker_v1": False,
            "quantizes_or_mutates_weights": False,
            "writes_audio": False,
            "allows_candidate_or_promotion": False,
        },
        "modules": selected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-modules", type=int, default=96)
    args = parser.parse_args()
    if not args.static_report.is_file():
        parser.error("static report not found")
    if args.output.exists():
        parser.error("refusing to overwrite output")
    if not 1 <= args.max_modules <= 512:
        parser.error("--max-modules must be between 1 and 512")
    report = json.loads(args.static_report.read_text(encoding="utf-8"))
    if report.get("schema") != "agent_bridge.qwen3_tts.quant_static_report.v0":
        parser.error("unexpected static report schema")
    plan = build_plan(report, sha256(args.static_report), args.max_modules)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": plan["status"], **plan["selection"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
