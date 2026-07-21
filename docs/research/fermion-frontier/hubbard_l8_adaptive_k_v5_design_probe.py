#!/usr/bin/env python3
"""Deterministic, non-authoritative kernel-edge K design probe for L8 v5."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
import types
from pathlib import Path
from typing import Any, Dict


SELF_NAME = "hubbard_l8_adaptive_k_v5_design_probe.py"
BASE_PROBE_NAME = "hubbard_l8_adaptive_k_v4_design_probe.py"
EXPECTED_BASE_PROBE_SHA256 = (
    "9067055bb4134d43001d5a2f05ff40c668a9d880ab11e6052193cccf80b5ca30"
)
EXPECTED_GRANDPARENT_V3_PROBE_SHA256 = (
    "cf0c1a6cc64011bb98f07a0dc97495e4c3278e89773e4b94764483e8a387d066"
)
EXPECTED_IMPLEMENTATION_V2_PROBE_SHA256 = (
    "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3"
)
EXPECTED_V4_SOURCE_CHAIN_SHA256 = (
    "88fbf351a9e8996247f562f80ec945130436548335e2396b0774496d4e8c9be4"
)
MAX_SELF_SOURCE_BYTES = 65_536
MAX_BASE_SOURCE_BYTES = 65_536
MAX_OUTPUT_BYTES = 1_048_576
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

EXTENSION = (475_136, 491_520, 507_904)
M_CANDIDATES = tuple(range(65_536, 507_904 + 1, 16_384))
D_CANDIDATES = (
    65_536, 73_728, 81_920, 90_112, 98_304, 106_496,
    114_688, 122_880, 131_072,
    147_456, 163_840, 180_224, 196_608, 212_992, 229_376,
    245_760, 262_144, 278_528, 294_912, 311_296, 327_680,
    344_064, 360_448, 376_832, 393_216,
    409_600, 425_984, 442_368, 458_752,
    475_136, 491_520, 507_904,
)

POLICY_CAPS_BASE = {
    "max_candidate_K": 507_904,
    "max_output_terms_if_successful": 507_904,
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
        "output_name": "hubbard_l8_magnetization_adaptive_k_v5_design_transcript.json",
    },
    "double_occupancy": {
        "candidates": D_CANDIDATES,
        "output_name": "hubbard_l8_double_occupancy_adaptive_k_v5_design_transcript.json",
    },
}

CANONICAL_V4_MODE = {
    "magnetization": {
        "candidate_K_values_sha256": (
            "dca926aa22de4a5a040cafe30007b74f07bef131ecb97a3b247cdb3adb17071a"
        ),
        "configuration_override_sha256": (
            "595cde3aac5071c475fb7737eb1d08844f36bd229a2f6db6f993dda18705f294"
        ),
        "output_name": "hubbard_l8_magnetization_adaptive_k_v4_design_transcript.json",
    },
    "double_occupancy": {
        "candidate_K_values_sha256": (
            "1e96d6a8a0be0b27baf12d866fd0aafce4966a1f51bb4f881898f4d1eec0734a"
        ),
        "configuration_override_sha256": (
            "6176e7d026af1255b21a092b66dfbb3c7b5904741b7a5793fc7702059c8de425"
        ),
        "output_name": "hubbard_l8_double_occupancy_adaptive_k_v4_design_transcript.json",
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
    """Compile the exact committed v4 probe and preserve its execution bytes."""

    path = repo.resolve() / BASE_PROBE_NAME
    payload = bounded_source_bytes(path, MAX_BASE_SOURCE_BYTES)
    observed = sha256(payload)
    if observed != EXPECTED_BASE_PROBE_SHA256:
        raise RuntimeError(f"base design probe pin drift: {observed}")
    module = types.ModuleType("pinned_hubbard_l8_adaptive_k_v4_design_probe_for_v5")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def configured_base(repo: Path, mode: str) -> Any:
    """Return an isolated verified v4 module configured only for v5 diagnosis."""

    if mode not in MODE_CONFIG:
        raise RuntimeError(f"unknown mode: {mode}")
    base = load_verified_base(repo)
    config = copy.deepcopy(base.MODE_CONFIG)
    for configured_mode, extension in MODE_CONFIG.items():
        config[configured_mode]["candidates"] = tuple(extension["candidates"])
        config[configured_mode]["output_name"] = extension["output_name"]
    base.MODE_CONFIG = config
    base.POLICY_CAPS_BASE = dict(POLICY_CAPS_BASE)
    return base


def parent_effective_override(mode: str, candidate_sha: str) -> Dict[str, Any]:
    return {
        "candidate_K_values_sha256": candidate_sha,
        "max_candidate_K": POLICY_CAPS_BASE["max_candidate_K"],
        "max_output_terms_if_successful": (
            POLICY_CAPS_BASE["max_output_terms_if_successful"]
        ),
        "output_name": MODE_CONFIG[mode]["output_name"],
        "overridden_fields": [
            "MODE_CONFIG.candidates",
            "MODE_CONFIG.output_name",
            "POLICY_CAPS_BASE.max_candidate_K",
            "POLICY_CAPS_BASE.max_output_terms_if_successful",
        ],
    }


def direct_v5_override(mode: str, candidate_sha: str) -> Dict[str, Any]:
    return {
        "base_configuration_override_sha256": (
            CANONICAL_V4_MODE[mode]["configuration_override_sha256"]
        ),
        "base_candidate_K_values_sha256": (
            CANONICAL_V4_MODE[mode]["candidate_K_values_sha256"]
        ),
        "candidate_K_values_sha256": candidate_sha,
        "candidate_ladder_extension": list(EXTENSION),
        "max_candidate_K": POLICY_CAPS_BASE["max_candidate_K"],
        "max_output_terms_if_successful": (
            POLICY_CAPS_BASE["max_output_terms_if_successful"]
        ),
        "output_name_before": CANONICAL_V4_MODE[mode]["output_name"],
        "output_name_after": MODE_CONFIG[mode]["output_name"],
        "overridden_fields": [
            "MODE_CONFIG.candidates",
            "MODE_CONFIG.output_name",
            "POLICY_CAPS_BASE.max_candidate_K",
            "POLICY_CAPS_BASE.max_output_terms_if_successful",
        ],
    }


def validate_and_relabel(result: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """Validate the exact v4 result identity before adding v5 provenance."""

    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("v5 relabel requires fresh same-byte self execution")
    if mode not in MODE_CONFIG:
        raise RuntimeError(f"unknown mode: {mode}")
    if result["schema_version"] != 1:
        raise RuntimeError("base v4 schema version drift")
    if result["design_probe_source_sha256"] != EXPECTED_BASE_PROBE_SHA256:
        raise RuntimeError("base v4 probe identity drift")
    if result["transcript_fingerprint"] != (
        "hubbard_l8_adaptive_k_v4_higher_K_deterministic_design_probe_v1"
    ):
        raise RuntimeError("base v4 fingerprint drift")
    if result["probe_generation"] != "v4_higher_K_458752":
        raise RuntimeError("base v4 generation drift")
    if (
        result["implementation_parent_probe_source_sha256"]
        != EXPECTED_GRANDPARENT_V3_PROBE_SHA256
    ):
        raise RuntimeError("grandparent v3 probe identity drift")
    if result["implementation_parent_probe_relative_path"] != (
        "hubbard_l8_adaptive_k_v3_design_probe.py"
    ):
        raise RuntimeError("grandparent v3 probe path drift")
    if result["implementation_parent_original_fingerprint"] != (
        "hubbard_l8_adaptive_k_v3_extended_K_deterministic_design_probe_v1"
    ):
        raise RuntimeError("grandparent v3 fingerprint drift")
    if result["implementation_parent_original_generation"] != (
        "v3_extended_K_393216"
    ):
        raise RuntimeError("grandparent v3 generation drift")
    if (
        result["implementation_base_source_sha256"]
        != EXPECTED_IMPLEMENTATION_V2_PROBE_SHA256
    ):
        raise RuntimeError("implementation v2 probe identity drift")
    if result["implementation_source_chain_sha256"] != EXPECTED_V4_SOURCE_CHAIN_SHA256:
        raise RuntimeError("base v4 source chain drift")
    candidates = list(MODE_CONFIG[mode]["candidates"])
    candidate_sha = sha256(canonical_bytes(candidates))
    if result["candidate_K_values"] != candidates:
        raise RuntimeError("configured candidate ladder was not used")
    if result["candidate_K_values_sha256"] != candidate_sha:
        raise RuntimeError("configured candidate ladder digest drift")
    if result["proposed_policy_caps"] != {
        **POLICY_CAPS_BASE,
        "max_candidate_count": len(candidates),
    }:
        raise RuntimeError("configured resource envelope was not used")
    expected_effective = parent_effective_override(mode, candidate_sha)
    if result["configuration_override"] != expected_effective:
        raise RuntimeError("parent effective configuration override drift")
    if result["configuration_override_sha256"] != sha256(
        canonical_bytes(expected_effective)
    ):
        raise RuntimeError("parent effective configuration digest drift")
    if result["status"] != "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS":
        raise RuntimeError("base v4 diagnostic status drift")
    if result["candidate_policy_precommitted_at_probe_time"] is not False:
        raise RuntimeError("design probe unexpectedly claims a precommitted policy")
    if result["child_boundary_committed"] or result["positive_artifact_generated"]:
        raise RuntimeError("design probe unexpectedly claims positive authority")
    if not result["root_globals_unchanged"]:
        raise RuntimeError("base v4 reports changed root globals")
    if result["root_globals_before"] != result["root_globals_after"]:
        raise RuntimeError("base v4 root-global snapshots differ")
    for key in (
        "implementation_parent_compiled_from_verified_bytes",
        "implementation_parent_module_isolated",
        "implementation_base_compiled_from_verified_bytes",
        "implementation_base_module_isolated",
    ):
        if result.get(key) is not True:
            raise RuntimeError(f"base v4 provenance flag drift: {key}")

    source_custody = dict(result["source_custody"])
    if (
        source_custody.get("hubbard_l8_adaptive_k_v3_design_probe.py")
        != EXPECTED_GRANDPARENT_V3_PROBE_SHA256
    ):
        raise RuntimeError("grandparent v3 source custody drift")
    if (
        source_custody.get("hubbard_l8_adaptive_k_v2_design_probe.py")
        != EXPECTED_IMPLEMENTATION_V2_PROBE_SHA256
    ):
        raise RuntimeError("implementation v2 source custody drift")
    source_custody[BASE_PROBE_NAME] = EXPECTED_BASE_PROBE_SHA256

    effective_override = dict(result["configuration_override"])
    effective_override_sha = result["configuration_override_sha256"]
    override = direct_v5_override(mode, candidate_sha)
    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    layers = [
        {"relative_path": SELF_NAME, "role": "v5_design_probe", "sha256": self_sha},
        {
            "relative_path": BASE_PROBE_NAME,
            "role": "v4_parent_probe",
            "sha256": EXPECTED_BASE_PROBE_SHA256,
        },
        {
            "relative_path": "hubbard_l8_adaptive_k_v3_design_probe.py",
            "role": "v3_grandparent_probe",
            "sha256": EXPECTED_GRANDPARENT_V3_PROBE_SHA256,
        },
        {
            "relative_path": "hubbard_l8_adaptive_k_v2_design_probe.py",
            "role": "v2_implementation_probe",
            "sha256": EXPECTED_IMPLEMENTATION_V2_PROBE_SHA256,
        },
    ]
    chain_sha = sha256(canonical_bytes([item["sha256"] for item in layers]))
    result.update({
        "schema_version": 1,
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_v5_kernel_edge_K_deterministic_design_probe_v1"
        ),
        "probe_generation": "v5_kernel_edge_K_507904",
        "design_probe_source_sha256": self_sha,
        "implementation_parent_probe_relative_path": BASE_PROBE_NAME,
        "implementation_parent_probe_source_sha256": EXPECTED_BASE_PROBE_SHA256,
        "implementation_parent_compiled_from_verified_bytes": True,
        "implementation_parent_module_isolated": True,
        "implementation_parent_original_fingerprint": (
            "hubbard_l8_adaptive_k_v4_higher_K_deterministic_design_probe_v1"
        ),
        "implementation_parent_original_generation": "v4_higher_K_458752",
        "implementation_parent_original_source_chain_sha256": (
            EXPECTED_V4_SOURCE_CHAIN_SHA256
        ),
        "implementation_parent_effective_configuration_override": effective_override,
        "implementation_parent_effective_configuration_override_sha256": (
            effective_override_sha
        ),
        "implementation_grandparent_probe_relative_path": (
            "hubbard_l8_adaptive_k_v3_design_probe.py"
        ),
        "implementation_grandparent_probe_source_sha256": (
            EXPECTED_GRANDPARENT_V3_PROBE_SHA256
        ),
        "implementation_grandparent_compiled_from_verified_bytes": True,
        "implementation_grandparent_module_isolated": True,
        "implementation_grandparent_original_fingerprint": (
            "hubbard_l8_adaptive_k_v3_extended_K_deterministic_design_probe_v1"
        ),
        "implementation_grandparent_original_generation": "v3_extended_K_393216",
        "implementation_source_layers": layers,
        "implementation_source_layers_sha256": sha256(canonical_bytes(layers)),
        "implementation_source_chain_sha256": chain_sha,
        "configuration_override": override,
        "configuration_override_sha256": sha256(canonical_bytes(override)),
        "source_custody": source_custody,
    })
    return result


def _run_verified(repo: Path, mode: str) -> Dict[str, Any]:
    """Replay one kernel-edge K ladder and relabel it as v5 diagnostic evidence."""

    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("v5 run requires fresh same-byte self execution")
    if mode not in MODE_CONFIG:
        raise RuntimeError(f"unknown mode: {mode}")
    repo = repo.resolve()
    base = configured_base(repo, mode)
    result = base._run_verified(repo, mode)
    return validate_and_relabel(result, mode)


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_source_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_hubbard_l8_adaptive_k_v5_design_probe")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path, mode: str) -> Dict[str, Any]:
    """Public same-byte entry point for one v5 diagnostic replay."""

    return fresh_self_module()._run_verified(repo, mode)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("design transcript exceeds output byte cap")
    output = output.resolve()
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output.parent,
            prefix=output.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=tuple(MODE_CONFIG))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp"))
    args = parser.parse_args()
    result = run(args.repo, args.mode)
    raw = canonical_bytes(result)
    output = args.output_dir / MODE_CONFIG[args.mode]["output_name"]
    write_atomic_bounded(output, raw)
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
