#!/usr/bin/env python3
"""Deterministic, non-authoritative extended-K design probe for L8 v3."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import types
from pathlib import Path
from typing import Any, Dict, Mapping


BASE_PROBE_NAME = "hubbard_l8_adaptive_k_v2_design_probe.py"
EXPECTED_BASE_PROBE_SHA256 = (
    "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3"
)
MAX_SELF_SOURCE_BYTES = 65_536
MAX_DEPENDENCY_SOURCE_BYTES = 262_144
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

M_CANDIDATES = tuple(range(65_536, 393_216 + 1, 16_384))
D_CANDIDATES = (
    65_536, 73_728, 81_920, 90_112, 98_304, 106_496,
    114_688, 122_880, 131_072,
    147_456, 163_840, 180_224, 196_608, 212_992, 229_376,
    245_760, 262_144, 278_528, 294_912, 311_296, 327_680,
    344_064, 360_448, 376_832, 393_216,
)

POLICY_CAPS_BASE = {
    "max_candidate_K": 393_216,
    "max_output_terms_if_successful": 393_216,
    "max_single_expansion_terms": 786_432,
    "max_digest_terms": 786_432,
    "max_term_gate_visits": 536_870_912,
    "max_expansion_coefficient_tick_bits": 192,
    "max_trigonometric_tick_bits": 66,
    "max_product_bits": 384,
    "max_suffix_accumulator_bits": 224,
}

MODE_CONFIG = {
    "magnetization": {
        "candidates": M_CANDIDATES,
        "output_name": "hubbard_l8_magnetization_adaptive_k_v3_design_transcript.json",
    },
    "double_occupancy": {
        "candidates": D_CANDIDATES,
        "output_name": "hubbard_l8_double_occupancy_adaptive_k_v3_design_transcript.json",
    },
}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def bounded_source_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as handle:
        payload = handle.read(maximum + 1)
    if len(payload) > maximum:
        raise RuntimeError(f"source byte cap exceeded: {path.name}")
    return payload


def load_verified_base(repo: Path) -> Any:
    """Compile the exact committed v2 probe into an isolated module."""

    path = repo / BASE_PROBE_NAME
    payload = bounded_source_bytes(path, MAX_DEPENDENCY_SOURCE_BYTES)
    observed = sha256(payload)
    if observed != EXPECTED_BASE_PROBE_SHA256:
        raise RuntimeError(f"base design probe pin drift: {observed}")
    module = types.ModuleType("pinned_hubbard_l8_adaptive_k_v2_design_probe_for_v3")
    module.__file__ = str(path)
    module.__package__ = ""
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def verified_dependency_payloads(repo: Path, base: Any, mode: str) -> Dict[str, bytes]:
    pins = {
        base.KERNEL_NAME: base.EXPECTED_KERNEL_SHA256,
        base.ROOT_NAME: base.EXPECTED_ROOT_SHA256,
        **base.CONFIG[mode]["parent_sources"],
    }
    payloads = {}
    for filename, expected in pins.items():
        payload = bounded_source_bytes(repo / filename, MAX_DEPENDENCY_SOURCE_BYTES)
        observed = sha256(payload)
        if observed != expected:
            raise RuntimeError(f"dependency source pin drift for {filename}: {observed}")
        payloads[filename] = payload
    return payloads


def install_verified_dependency_loader(
    repo: Path,
    base: Any,
    payloads: Mapping[str, bytes],
) -> None:
    repo = repo.resolve()
    pins = {name: sha256(payload) for name, payload in payloads.items()}

    def checked_name(path: Path) -> str:
        if not isinstance(path, Path):
            raise RuntimeError("verified dependency path must be a Path")
        resolved = path.resolve()
        if resolved.parent != repo or resolved.name not in payloads:
            raise RuntimeError("dependency path is outside the verified source set")
        return resolved.name

    def verify_source(path: Path, expected: str) -> bytes:
        name = checked_name(path)
        if expected != pins[name]:
            raise RuntimeError(f"dependency pin request drift for {name}")
        return payloads[name]

    def load_module(name: str, path: Path) -> Any:
        filename = checked_name(path)
        payload = payloads[filename]
        module = types.ModuleType(name)
        module.__file__ = str(repo / filename)
        module.__package__ = ""
        module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
        exec(compile(payload, module.__file__, "exec"), module.__dict__)
        return module

    base.verify_source = verify_source
    base.load_module = load_module


def configured_base(repo: Path, mode: str) -> Any:
    """Return a fresh v2 implementation instance configured only for v3 diagnosis."""

    if mode not in MODE_CONFIG:
        raise RuntimeError(f"unknown mode: {mode}")
    repo = repo.resolve()
    base = load_verified_base(repo)
    payloads = verified_dependency_payloads(repo, base, mode)
    install_verified_dependency_loader(repo, base, payloads)
    config = copy.deepcopy(base.CONFIG)
    for mode, extension in MODE_CONFIG.items():
        config[mode]["candidates"] = tuple(extension["candidates"])
        config[mode]["output_name"] = extension["output_name"]
    base.CONFIG = config
    base.POLICY_CAPS_BASE = dict(POLICY_CAPS_BASE)
    return base


def _run_verified(repo: Path, mode: str) -> Dict[str, Any]:
    """Replay one extended ladder and relabel the result as v3 diagnostic evidence."""

    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("v3 run requires fresh same-byte self execution")
    if mode not in MODE_CONFIG:
        raise RuntimeError(f"unknown mode: {mode}")
    repo = repo.resolve()
    base = configured_base(repo, mode)
    result = base.run(repo, mode)
    if result["design_probe_source_sha256"] != EXPECTED_BASE_PROBE_SHA256:
        raise RuntimeError("base probe changed during replay")
    candidates = list(MODE_CONFIG[mode]["candidates"])
    if result["candidate_K_values"] != candidates:
        raise RuntimeError("configured candidate ladder was not used")
    if result["proposed_policy_caps"]["max_candidate_K"] != candidates[-1]:
        raise RuntimeError("configured maximum K was not used")
    if result["candidate_policy_precommitted_at_probe_time"] is not False:
        raise RuntimeError("design probe unexpectedly claims a precommitted policy")
    if result["child_boundary_committed"] or result["positive_artifact_generated"]:
        raise RuntimeError("design probe unexpectedly claims positive authority")

    source_custody = dict(result["source_custody"])
    source_custody[BASE_PROBE_NAME] = EXPECTED_BASE_PROBE_SHA256
    result.update({
        "schema_version": 1,
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_v3_extended_K_deterministic_design_probe_v1"
        ),
        "probe_generation": "v3_extended_K_393216",
        "design_probe_source_sha256": sha256(_VERIFIED_SELF_SOURCE_BYTES),
        "implementation_base_source_sha256": EXPECTED_BASE_PROBE_SHA256,
        "implementation_base_compiled_from_verified_bytes": True,
        "implementation_base_module_isolated": True,
        "source_custody": source_custody,
    })
    return result


def fresh_self_module() -> Any:
    """Compile the current wrapper once and preserve those exact execution bytes."""

    path = Path(__file__).resolve()
    payload = bounded_source_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_hubbard_l8_adaptive_k_v3_design_probe")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path, mode: str) -> Dict[str, Any]:
    """Public same-byte entry point for one v3 diagnostic replay."""

    return fresh_self_module()._run_verified(repo, mode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=tuple(MODE_CONFIG))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp"))
    args = parser.parse_args()
    result = run(args.repo, args.mode)
    raw = canonical_bytes(result)
    output = args.output_dir / MODE_CONFIG[args.mode]["output_name"]
    output.write_bytes(raw)
    final_record = result["records"][-1] if result["records"] else None
    print(json.dumps({
        "output": output.name,
        "semantic_and_file_sha256": sha256(raw),
        "records_sha256": result["records_sha256"],
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "selected_K_history": result["selected_K_history"],
        "final_status": final_record["status"] if final_record else None,
        "failure_checkpoint": (
            final_record.get("checkpoint_number_one_based") if final_record else None
        ),
        "failure_minimum_effective_K": (
            final_record.get("minimum_effective_K_to_meet_prefix")
            if final_record else None
        ),
        "failure_required_K_excess": (
            final_record.get("required_K_excess_over_policy_maximum")
            if final_record else None
        ),
        "last_committed_cumulative_drop_ticks": (
            result["last_committed_cumulative_drop_ticks"]
        ),
        "peak": result["observed_peak_single_expansion_terms"],
        "visits": result["observed_term_gate_visits_including_failure"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
