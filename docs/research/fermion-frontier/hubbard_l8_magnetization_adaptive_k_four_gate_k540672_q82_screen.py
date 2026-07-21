#!/usr/bin/env python3
"""Source-pinned, diagnostic-only M q82 horizon extension.

The pinned K=540672 screen remains the private execution parent.  This outer
wrapper changes only the magnetization horizon from 80 to 82 inside one isolated
copy of that parent.  Candidate ladders, policy caps, kernel capabilities,
physical gates and all double-occupancy configuration remain unchanged.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
import types
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple


SELF_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k540672_q82_screen.py"
)
BASE_SCREEN_NAME = "hubbard_l8_adaptive_k_four_gate_k540672_screen.py"
BASE_TRANSCRIPT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k540672_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k540672_q82_transcript.json"
)

EXPECTED_BASE_SCREEN_SHA256 = (
    "81ac62fa093c48d57667cb56958ad58a8ed26e8ff81abd7c35365e01fb981d6f"
)
EXPECTED_BASE_TRANSCRIPT_SHA256 = (
    "d4a0f952a3d4a93bd78d370fae50c5c043e33caa4d1452e841987976e43354a5"
)
EXPECTED_BASE_RECORDS_SHA256 = (
    "c433c9c1231c9ec464b669b545efb3c18d5aefa4be48d780642994219b34dd91"
)
EXPECTED_BASE_HISTORY_SHA256 = (
    "43dabd7d34c8de39a91388080dac5e941c162867771fe39fe8a216f7ad00dcc9"
)
EXPECTED_CANDIDATE_SHA256 = (
    "9baadb7bea90ac503ec3f68cd05fa01d967376fedff59aaedcbf2d009c46fb95"
)
EXPECTED_KERNEL_WRAPPER_SHA256 = (
    "327837e4646cb79cb237611ab49e645b51a47a36a97006e94838d1f5fa05af60"
)
EXPECTED_KERNEL_MANIFEST_SHA256 = (
    "d51151fc1d6c73c33f1b50da0a09de4d3346212599716feaba578839dde37526"
)

MODE = "magnetization"
BASE_HORIZON = 80
EXTENDED_HORIZON = 82
MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 131_072
MAX_BASE_TRANSCRIPT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")


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


def bounded_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as handle:
        payload = handle.read(maximum + 1)
    if len(payload) > maximum:
        raise RuntimeError(f"byte cap exceeded: {path.name}")
    return payload


def checked_repo_file(repo: Path, relative_path: str) -> Path:
    if type(relative_path) is not str or not relative_path:
        raise RuntimeError("relative path is not a nonempty string")
    repo = repo.resolve()
    path = (repo / relative_path).resolve()
    try:
        path.relative_to(repo)
    except ValueError as exc:
        raise RuntimeError("path escapes the repository") from exc
    return path


def compile_isolated(name: str, path: Path, payload: bytes) -> Any:
    if type(payload) is not bytes:
        raise RuntimeError("isolated module payload must be exact bytes")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def load_base_screen(repo: Path) -> Tuple[Any, bytes]:
    path = checked_repo_file(repo, BASE_SCREEN_NAME)
    payload = bounded_bytes(path, MAX_PINNED_SOURCE_BYTES)
    observed = sha256(payload)
    if observed != EXPECTED_BASE_SCREEN_SHA256:
        raise RuntimeError(f"base K=540672 screen source pin drift: {observed}")
    base = compile_isolated(
        "pinned_k540672_screen_for_magnetization_q82",
        path,
        payload,
    )
    base.validate_local_configuration()
    if base.SELF_NAME != BASE_SCREEN_NAME:
        raise RuntimeError("base K=540672 screen filename contract drift")
    if base.MODE_CONFIG[MODE]["horizon_checkpoint_count"] != BASE_HORIZON:
        raise RuntimeError("base magnetization horizon drift")
    if base.MODE_CONFIG["double_occupancy"]["horizon_checkpoint_count"] != 66:
        raise RuntimeError("base double-occupancy horizon drift")
    if base.EXPECTED_CANDIDATE_SHA256[MODE] != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("base magnetization candidate digest drift")
    if base.EXPECTED_KERNEL_WRAPPER_SHA256 != EXPECTED_KERNEL_WRAPPER_SHA256:
        raise RuntimeError("base kernel wrapper pin drift")
    if base.EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256 != (
        EXPECTED_KERNEL_MANIFEST_SHA256
    ):
        raise RuntimeError("base kernel manifest pin drift")
    return base, payload


def load_base_transcript(repo: Path, base: Any) -> Dict[str, Any]:
    path = checked_repo_file(repo, BASE_TRANSCRIPT_NAME)
    raw = bounded_bytes(path, MAX_BASE_TRANSCRIPT_BYTES)
    observed = sha256(raw)
    if observed != EXPECTED_BASE_TRANSCRIPT_SHA256:
        raise RuntimeError(f"base M canonical transcript pin drift: {observed}")
    try:
        transcript = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("base M canonical transcript is invalid JSON") from exc
    if type(transcript) is not dict or raw != canonical_bytes(transcript):
        raise RuntimeError("base M transcript is not canonical exact JSON")
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_k540672_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_BASE_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "attempted_checkpoint_count": BASE_HORIZON,
        "completed_checkpoint_count": BASE_HORIZON,
        "failure_checkpoint_included": False,
        "horizon_reached_with_committed_checkpoint": True,
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "records_sha256": EXPECTED_BASE_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_BASE_HISTORY_SHA256,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, value in expected.items():
        if transcript.get(key) != value:
            raise RuntimeError(f"base M canonical transcript drift: {key}")
    if transcript.get("candidate_K_values") != list(base.M_CANDIDATES):
        raise RuntimeError("base M canonical candidate ladder drift")
    if len(transcript.get("records", ())) != BASE_HORIZON:
        raise RuntimeError("base M canonical record count drift")
    if len(transcript.get("selected_K_history", ())) != BASE_HORIZON:
        raise RuntimeError("base M canonical history count drift")
    if sha256(canonical_bytes(transcript["records"])) != (
        EXPECTED_BASE_RECORDS_SHA256
    ):
        raise RuntimeError("base M canonical records digest drift")
    if sha256(canonical_bytes(transcript["selected_K_history"])) != (
        EXPECTED_BASE_HISTORY_SHA256
    ):
        raise RuntimeError("base M canonical history digest drift")
    return transcript


def adapter_manifest(base: Any) -> Dict[str, Any]:
    return {
        "adapter_id": "magnetization_k540672_q82_runtime_horizon_adapter_v1",
        "mode": MODE,
        "semantic_delta": {
            "MODE_CONFIG.magnetization.horizon_checkpoint_count": {
                "before": BASE_HORIZON,
                "after": EXTENDED_HORIZON,
            },
        },
        "changed_semantic_fields": [
            "MODE_CONFIG.magnetization.horizon_checkpoint_count",
        ],
        "unchanged_candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "unchanged_policy_caps": dict(base.POLICY_CAPS_BASE),
        "unchanged_kernel_capability_limits": dict(
            base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        ),
        "unchanged_kernel_wrapper_source_sha256": (
            EXPECTED_KERNEL_WRAPPER_SHA256
        ),
        "unchanged_kernel_manifest_sha256": EXPECTED_KERNEL_MANIFEST_SHA256,
        "double_occupancy_configuration_unchanged": True,
        "runtime_adapter_functions": [
            "base_screen.validate_local_configuration",
            "base_screen.load_control_flow_parent",
            "returned_parent.MODE_CONFIG.magnetization.horizon_checkpoint_count",
        ],
        "original_validator_called_in_exact_baseline_state": True,
        "original_parent_loader_called_in_exact_baseline_state": True,
        "temporary_baseline_state_restored_with_try_finally": True,
        "base_screen_private_entrypoint_called": True,
        "base_screen_public_entrypoint_called": False,
        "full_replay_from_checkpoint_one": True,
        "checkpoint_80_state_loaded_from_transcript": False,
    }


def install_horizon_adapter(base: Any) -> Dict[str, Any]:
    """Install one explicit 80->82 adapter in an isolated K540 screen."""

    base.validate_local_configuration()
    baseline_config = copy.deepcopy(base.MODE_CONFIG)
    original_validator = base.validate_local_configuration
    original_parent_loader = base.load_control_flow_parent
    effective_config = copy.deepcopy(baseline_config)
    effective_config[MODE]["horizon_checkpoint_count"] = EXTENDED_HORIZON

    def validate_q82_configuration() -> None:
        active = base.MODE_CONFIG
        try:
            base.MODE_CONFIG = copy.deepcopy(baseline_config)
            original_validator()
        finally:
            base.MODE_CONFIG = active
        if base.MODE_CONFIG != effective_config:
            raise RuntimeError("q82 runtime configuration changed outside horizon")
        if base.MODE_CONFIG[MODE]["horizon_checkpoint_count"] != EXTENDED_HORIZON:
            raise RuntimeError("q82 magnetization horizon adapter drift")

    def load_q82_control_flow_parent(repo: Path) -> Any:
        active = base.MODE_CONFIG
        try:
            base.MODE_CONFIG = copy.deepcopy(baseline_config)
            parent = original_parent_loader(repo)
        finally:
            base.MODE_CONFIG = active
        if parent.MODE_CONFIG[MODE]["horizon_checkpoint_count"] != BASE_HORIZON:
            raise RuntimeError("returned parent magnetization horizon drift")
        parent_baseline = copy.deepcopy(parent.MODE_CONFIG)
        parent_config = copy.deepcopy(parent.MODE_CONFIG)
        parent_config[MODE]["horizon_checkpoint_count"] = EXTENDED_HORIZON
        parent.MODE_CONFIG = parent_config
        if parent.MODE_CONFIG["double_occupancy"] != (
            parent_baseline["double_occupancy"]
        ):
            raise RuntimeError("q82 adapter changed parent double occupancy")
        return parent

    base.MODE_CONFIG = effective_config
    base.validate_local_configuration = validate_q82_configuration
    base.load_control_flow_parent = load_q82_control_flow_parent
    validate_q82_configuration()
    return adapter_manifest(base)


def validate_base_result(
    result: Dict[str, Any],
    base: Any,
    anchor: Mapping[str, Any],
) -> None:
    if type(result) is not dict:
        raise RuntimeError("base q82 result is not an exact dict")
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_k540672_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_BASE_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "same_byte_self_execution": True,
        "screen_horizon_checkpoint_count": EXTENDED_HORIZON,
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "candidate_policy_precommitted_at_probe_time": False,
        "control_flow_owned_by_screen": False,
        "control_flow_owned_by_verified_parent": True,
        "control_flow_parent_private_entrypoint_called": True,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise RuntimeError(f"base q82 result drift: {key}")
    if result.get("candidate_K_values") != list(base.M_CANDIDATES):
        raise RuntimeError("q82 candidate ladder drift")
    expected_caps = {
        **base.POLICY_CAPS_BASE,
        "max_candidate_count": len(base.M_CANDIDATES),
    }
    if result.get("proposed_policy_caps") != expected_caps:
        raise RuntimeError("q82 proposed policy caps drift")
    if result.get("kernel_capability_limits") != (
        base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
    ):
        raise RuntimeError("q82 kernel capability limits drift")
    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or not (BASE_HORIZON < len(records) <= EXTENDED_HORIZON):
        raise RuntimeError("q82 result did not attempt beyond checkpoint 80")
    if records[:BASE_HORIZON] != anchor["records"]:
        raise RuntimeError("q82 result changed the exact q1-80 record prefix")
    if history[:BASE_HORIZON] != anchor["selected_K_history"]:
        raise RuntimeError("q82 result changed the exact q1-80 history prefix")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("q82 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(
        canonical_bytes(history)
    ):
        raise RuntimeError("q82 history digest drift")


def relabel_outer_result(
    result: Dict[str, Any],
    base: Any,
    anchor: Mapping[str, Any],
    adapter: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("q82 relabel requires fresh same-byte self execution")
    validate_base_result(result, base, anchor)
    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)

    base_components = result["screen_execution_components"]
    base_components_sha = result["screen_execution_components_sha256"]
    if base_components_sha != sha256(canonical_bytes(base_components)):
        raise RuntimeError("base q82 component digest drift")
    components = [{
        "relative_path": SELF_NAME,
        "role": "magnetization_q82_fresh_same_byte_horizon_wrapper",
        "sha256": self_sha,
    }]
    saw_base = False
    for original in base_components:
        item = dict(original)
        if item.get("relative_path") == BASE_SCREEN_NAME:
            if item.get("sha256") != EXPECTED_BASE_SCREEN_SHA256:
                raise RuntimeError("base screen component pin drift")
            item["role"] = "k540672_private_execution_parent_for_q82"
            saw_base = True
        components.append(item)
    if not saw_base:
        raise RuntimeError("base screen component missing from q82 result")

    old_transform = result["checkpoint_transform"]
    old_transform_sha = result["checkpoint_transform_sha256"]
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("base q82 transform digest drift")
    horizon_override = {
        **dict(adapter),
        "base_screen_source_sha256": EXPECTED_BASE_SCREEN_SHA256,
        "base_canonical_transcript_anchor": {
            "relative_path": BASE_TRANSCRIPT_NAME,
            "file_sha256": EXPECTED_BASE_TRANSCRIPT_SHA256,
            "records_sha256": EXPECTED_BASE_RECORDS_SHA256,
            "selected_K_history_sha256": EXPECTED_BASE_HISTORY_SHA256,
            "attempted_checkpoint_count": BASE_HORIZON,
            "completed_checkpoint_count": BASE_HORIZON,
        },
    }
    transform = {
        "transform_id": "magnetization_four_gate_k540672_q82_horizon_v1",
        "base_k540672_checkpoint_transform": old_transform,
        "base_k540672_checkpoint_transform_sha256": old_transform_sha,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "candidate_ladder_changed": False,
        "policy_caps_changed": False,
        "kernel_capabilities_changed": False,
        "horizon_checkpoint_count": {
            "before": BASE_HORIZON,
            "after": EXTENDED_HORIZON,
        },
    }
    custody = dict(result["source_custody"])
    if SELF_NAME in custody:
        raise RuntimeError("unexpected preexisting q82 source custody")
    custody[SELF_NAME] = self_sha

    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k540672_q82_screen_v1"
        ),
        "screen_source_sha256": self_sha,
        "same_byte_self_execution": True,
        "horizon_extension_orchestration_owned_by_outer_screen": True,
        "physical_checkpoint_loop_owned_by_verified_four_gate_parent": True,
        "horizon_extension_parent_relative_path": BASE_SCREEN_NAME,
        "horizon_extension_parent_source_sha256": EXPECTED_BASE_SCREEN_SHA256,
        "horizon_extension_parent_compiled_from_verified_bytes": True,
        "horizon_extension_parent_module_isolated": True,
        "horizon_extension_parent_private_entrypoint_called": True,
        "horizon_extension_parent_public_entrypoint_called": False,
        "base_screen_execution_components_sha256_before_outer_relabel": (
            base_components_sha
        ),
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(canonical_bytes(components)),
        "horizon_extension_override": horizon_override,
        "horizon_extension_override_sha256": sha256(
            canonical_bytes(horizon_override)
        ),
        "checkpoint_transform": transform,
        "checkpoint_transform_sha256": sha256(canonical_bytes(transform)),
        "base_canonical_reference_artifact": {
            "relative_path": BASE_TRANSCRIPT_NAME,
            "file_sha256": EXPECTED_BASE_TRANSCRIPT_SHA256,
            "post_replay_prefix_validation_input": True,
            "propagation_input": False,
            "checkpoint_80_state_loaded": False,
            "state_resume_input": False,
        },
        "source_custody": custody,
        "diagnostic_horizon_precommitted_before_replay": True,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    })
    return result


def _run_verified(repo: Path) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("q82 screen requires fresh same-byte self execution")
    repo = repo.resolve()
    base, _payload = load_base_screen(repo)
    anchor = load_base_transcript(repo, base)
    adapter = install_horizon_adapter(base)
    result = base._run_verified(repo, MODE)
    return relabel_outer_result(result, base, anchor, adapter)


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_magnetization_k540672_q82_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("q82 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("q82 transcript exceeds output byte cap")
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
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp"))
    args = parser.parse_args()
    result = run(args.repo)
    raw = canonical_bytes(result)
    output = args.output_dir / OUTPUT_NAME
    write_atomic_bounded(output, raw)
    final_record = result["records"][-1]
    print(json.dumps({
        "output": output.name,
        "semantic_and_file_sha256": sha256(raw),
        "records_sha256": result["records_sha256"],
        "screen_terminal_condition": result["screen_terminal_condition"],
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "attempted_checkpoint_count": result["attempted_checkpoint_count"],
        "final_status": final_record["status"],
        "final_checkpoint": final_record["checkpoint_number_one_based"],
        "last_committed_cumulative_drop_ticks": (
            result["last_committed_cumulative_drop_ticks"]
        ),
        "peak": result["observed_peak_single_expansion_terms"],
        "visits": result["observed_term_gate_visits_including_terminal_attempt"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
