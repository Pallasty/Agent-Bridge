#!/usr/bin/env python3
"""Source-pinned, diagnostic-only D K=573440/C=33 q70 extension.

The exact q68 screen remains the private execution parent.  This fresh
same-byte outer wrapper changes only that isolated parent's declared horizon
from 68 to 70.  The q68 private entrypoint still constructs and owns the full
checkpoint-one replay; the canonical q68 transcript is used only afterwards
to validate the exact q1--68 records and selected-K history.
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
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k573440_c33_q70_screen.py"
)
BASE_SCREEN_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k573440_c33_q68_screen.py"
)
BASE_TRANSCRIPT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k573440_c33_q68_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k573440_c33_q70_transcript.json"
)

EXPECTED_BASE_SCREEN_SHA256 = (
    "3c4dfb8aca29b6a5903d2aedd52f85409941d1c16050760f6b24453d9585d67b"
)
EXPECTED_BASE_TRANSCRIPT_SHA256 = (
    "b1f072c84cc676151fe3cddbb8a0db445df946f299dbb81f41e34f765d30dfc8"
)
EXPECTED_BASE_RECORDS_SHA256 = (
    "e26a869b24da95eb586604a36dadc23371f82961a9b5f76723bdbf6377891d3f"
)
EXPECTED_BASE_HISTORY_SHA256 = (
    "e2d036fab34ed4a6d1b9e09309a2a83c8a9e69afaff2ca9add92505b72557607"
)
EXPECTED_CANDIDATE_SHA256 = (
    "461517a4e7d5f6ffbb610b53240f01071cc7f7a9ac1b2dfdbc6e4b0addd59a27"
)
EXPECTED_KERNEL_WRAPPER_SHA256 = (
    "811a16b6a47bca60281fb4afe8280783146e6f4ee28955dde7907b47fc65bb49"
)
EXPECTED_KERNEL_MANIFEST_SHA256 = (
    "c2787b105553b80ee9a1e5e1d925d6cac2ab819b0cdfab305484bf89bbba32c5"
)

MODE = "double_occupancy"
BASE_HORIZON = 68
EXTENDED_HORIZON = 70
MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
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
        raise RuntimeError(f"base D q68 screen source pin drift: {observed}")
    base = compile_isolated(
        "pinned_double_occupancy_k573440_c33_q68_for_q70",
        path,
        payload,
    )
    base.validate_local_configuration()
    expected = {
        "SELF_NAME": BASE_SCREEN_NAME,
        "MODE": MODE,
        "BASE_PARENT_HORIZON": 66,
        "EXTENDED_HORIZON": BASE_HORIZON,
        "EXPECTED_CANDIDATE_SHA256": EXPECTED_CANDIDATE_SHA256,
        "EXPECTED_KERNEL_WRAPPER_SHA256": EXPECTED_KERNEL_WRAPPER_SHA256,
        "EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256": (
            EXPECTED_KERNEL_MANIFEST_SHA256
        ),
    }
    for key, value in expected.items():
        if getattr(base, key, None) != value:
            raise RuntimeError(f"base D q68 screen contract drift: {key}")
    if len(base.D_CANDIDATES) != 33 or base.D_CANDIDATES[-1] != 573_440:
        raise RuntimeError("base D q68 candidate ladder drift")
    if sha256(canonical_bytes(list(base.D_CANDIDATES))) != (
        EXPECTED_CANDIDATE_SHA256
    ):
        raise RuntimeError("base D q68 candidate digest drift")
    if not callable(getattr(base, "_run_verified", None)):
        raise RuntimeError("base D q68 private entrypoint missing")
    return base, payload


def load_base_transcript(repo: Path, base: Any) -> Dict[str, Any]:
    path = checked_repo_file(repo, BASE_TRANSCRIPT_NAME)
    raw = bounded_bytes(path, MAX_BASE_TRANSCRIPT_BYTES)
    observed = sha256(raw)
    if observed != EXPECTED_BASE_TRANSCRIPT_SHA256:
        raise RuntimeError(f"base D q68 canonical transcript pin drift: {observed}")
    try:
        transcript = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("base D q68 canonical transcript is invalid JSON") from exc
    if type(transcript) is not dict or raw != canonical_bytes(transcript):
        raise RuntimeError("base D q68 transcript is not canonical exact JSON")
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k573440_c33_q68_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_BASE_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_horizon_checkpoint_count": BASE_HORIZON,
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "attempted_checkpoint_count": BASE_HORIZON,
        "completed_checkpoint_count": BASE_HORIZON,
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "horizon_reached_with_committed_checkpoint": True,
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "records_sha256": EXPECTED_BASE_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_BASE_HISTORY_SHA256,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, value in expected.items():
        if transcript.get(key) != value:
            raise RuntimeError(f"base D q68 canonical transcript drift: {key}")
    if transcript.get("candidate_K_values") != list(base.D_CANDIDATES):
        raise RuntimeError("base D q68 canonical candidate ladder drift")
    expected_caps = {
        **base.POLICY_CAPS_BASE,
        "max_candidate_count": len(base.D_CANDIDATES),
    }
    if transcript.get("proposed_policy_caps") != expected_caps:
        raise RuntimeError("base D q68 canonical policy caps drift")
    if transcript.get("kernel_capability_limits") != (
        base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
    ):
        raise RuntimeError("base D q68 canonical kernel limits drift")
    records = transcript.get("records")
    history = transcript.get("selected_K_history")
    if type(records) is not list or len(records) != BASE_HORIZON:
        raise RuntimeError("base D q68 canonical record count drift")
    if type(history) is not list or len(history) != BASE_HORIZON:
        raise RuntimeError("base D q68 canonical history count drift")
    if sha256(canonical_bytes(records)) != EXPECTED_BASE_RECORDS_SHA256:
        raise RuntimeError("base D q68 canonical records digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_BASE_HISTORY_SHA256:
        raise RuntimeError("base D q68 canonical history digest drift")
    return transcript


def adapter_manifest(base: Any) -> Dict[str, Any]:
    return {
        "adapter_id": "double_occupancy_k573440_c33_q70_runtime_adapter_v1",
        "mode": MODE,
        "semantic_delta": {
            "EXTENDED_HORIZON": {
                "before": BASE_HORIZON,
                "after": EXTENDED_HORIZON,
            },
        },
        "changed_semantic_fields": ["EXTENDED_HORIZON"],
        "unchanged_candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "unchanged_policy_caps": dict(base.POLICY_CAPS_BASE),
        "unchanged_kernel_capability_limits": dict(
            base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        ),
        "unchanged_kernel_wrapper_source_sha256": (
            EXPECTED_KERNEL_WRAPPER_SHA256
        ),
        "unchanged_kernel_manifest_sha256": EXPECTED_KERNEL_MANIFEST_SHA256,
        "magnetization_configuration_unchanged": True,
        "physical_gate_sequence_unchanged": True,
        "runtime_adapter_functions": [
            "base_q68.validate_local_configuration",
            "base_q68.load_control_flow_parent",
        ],
        "original_validator_called_in_exact_q68_baseline_state": True,
        "original_parent_loader_called_in_exact_q68_baseline_state": True,
        "temporary_q68_baseline_restored_with_try_finally": True,
        "returned_parent_mode_config_mutated_by_outer_adapter": False,
        "base_q68_private_entrypoint_called": True,
        "base_q68_public_entrypoint_called": False,
        "base_q68_runtime_configurer_applies_parent_horizon": True,
        "full_replay_from_checkpoint_one": True,
        "checkpoint_68_state_loaded_from_transcript": False,
    }


def install_horizon_adapter(base: Any) -> Dict[str, Any]:
    """Install one explicit 68->70 adapter in an isolated q68 screen."""

    base.validate_local_configuration()
    if base.EXTENDED_HORIZON != BASE_HORIZON:
        raise RuntimeError("base D q68 horizon baseline drift")
    baseline_candidates = tuple(base.D_CANDIDATES)
    baseline_caps = copy.deepcopy(base.POLICY_CAPS_BASE)
    baseline_limits = copy.deepcopy(
        base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
    )
    original_validator = base.validate_local_configuration
    original_parent_loader = base.load_control_flow_parent

    def validate_q70_configuration() -> None:
        active = base.EXTENDED_HORIZON
        try:
            base.EXTENDED_HORIZON = BASE_HORIZON
            original_validator()
        finally:
            base.EXTENDED_HORIZON = active
        if base.EXTENDED_HORIZON != EXTENDED_HORIZON:
            raise RuntimeError("q70 runtime horizon adapter drift")
        if tuple(base.D_CANDIDATES) != baseline_candidates:
            raise RuntimeError("q70 adapter changed the D candidate ladder")
        if base.POLICY_CAPS_BASE != baseline_caps:
            raise RuntimeError("q70 adapter changed policy caps")
        if base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS != baseline_limits:
            raise RuntimeError("q70 adapter changed kernel capability limits")

    def load_q70_control_flow_parent(repo: Path) -> Any:
        active = base.EXTENDED_HORIZON
        try:
            base.EXTENDED_HORIZON = BASE_HORIZON
            parent = original_parent_loader(repo)
        finally:
            base.EXTENDED_HORIZON = active
        expected_horizons = {"magnetization": 80, MODE: 66}
        observed_horizons = {
            mode: config["horizon_checkpoint_count"]
            for mode, config in parent.MODE_CONFIG.items()
        }
        if observed_horizons != expected_horizons:
            raise RuntimeError("returned q68 control-flow parent horizon drift")
        return parent

    base.EXTENDED_HORIZON = EXTENDED_HORIZON
    base.validate_local_configuration = validate_q70_configuration
    base.load_control_flow_parent = load_q70_control_flow_parent
    validate_q70_configuration()
    return adapter_manifest(base)


def expected_q70_parent_horizon_override(
    anchor: Mapping[str, Any],
) -> Dict[str, Any]:
    expected = copy.deepcopy(anchor["parent_horizon_override"])
    field = "MODE_CONFIG.double_occupancy.horizon_checkpoint_count"
    expected["semantic_delta"][field]["after"] = EXTENDED_HORIZON
    expected["parent_mode_config_after"][MODE][
        "horizon_checkpoint_count"
    ] = EXTENDED_HORIZON
    expected["parent_mode_config_after_sha256"] = sha256(
        canonical_bytes(expected["parent_mode_config_after"])
    )
    return expected


def validate_base_result(
    result: Dict[str, Any],
    base: Any,
    anchor: Mapping[str, Any],
) -> None:
    if type(result) is not dict:
        raise RuntimeError("base q70 result is not an exact dict")
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k573440_c33_q68_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_BASE_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "same_byte_self_execution": True,
        "screen_horizon_checkpoint_count": EXTENDED_HORIZON,
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "control_flow_owned_by_screen": False,
        "control_flow_owned_by_verified_parent": True,
        "control_flow_parent_private_entrypoint_called": True,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise RuntimeError(f"base q70 result drift: {key}")
    unchanged_fields = (
        "candidate_K_values",
        "proposed_policy_caps",
        "kernel_capability_limits",
        "sequence",
        "screen_execution_components",
        "screen_execution_components_sha256",
        "configuration_reference",
        "configuration_reference_sha256",
        "configuration_override",
        "configuration_override_sha256",
        "kernel_capability_override",
        "kernel_capability_override_sha256",
        "route_predecessor_reference",
        "route_predecessor_reference_sha256",
        "predecessor_handoff_validation",
        "predecessor_handoff_validation_sha256",
        "checkpoint_transform",
        "checkpoint_transform_sha256",
        "source_custody",
    )
    for field in unchanged_fields:
        if result.get(field) != anchor.get(field):
            raise RuntimeError(f"q70 changed q68 invariant field: {field}")
    if result.get("candidate_K_values") != list(base.D_CANDIDATES):
        raise RuntimeError("q70 candidate ladder drift")
    expected_caps = {
        **base.POLICY_CAPS_BASE,
        "max_candidate_count": len(base.D_CANDIDATES),
    }
    if result.get("proposed_policy_caps") != expected_caps:
        raise RuntimeError("q70 proposed policy caps drift")
    if result.get("kernel_capability_limits") != (
        base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
    ):
        raise RuntimeError("q70 kernel capability limits drift")

    expected_parent_override = expected_q70_parent_horizon_override(anchor)
    if result.get("parent_horizon_override") != expected_parent_override:
        raise RuntimeError("q70 base parent horizon override drift")
    if result.get("parent_horizon_override_sha256") != sha256(
        canonical_bytes(expected_parent_override)
    ):
        raise RuntimeError("q70 base parent horizon override digest drift")

    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or not (
        BASE_HORIZON < len(records) <= EXTENDED_HORIZON
    ):
        raise RuntimeError("q70 result did not attempt beyond checkpoint 68")
    if type(history) is not list or not (
        BASE_HORIZON <= len(history) <= EXTENDED_HORIZON
    ):
        raise RuntimeError("q70 selected-K history count drift")
    if records[:BASE_HORIZON] != anchor["records"]:
        raise RuntimeError("q70 result changed the exact q1-68 record prefix")
    if history[:BASE_HORIZON] != anchor["selected_K_history"]:
        raise RuntimeError("q70 result changed the exact q1-68 history prefix")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("q70 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(
        canonical_bytes(history)
    ):
        raise RuntimeError("q70 selected-K history digest drift")
    if result.get("attempted_checkpoint_count") != len(records):
        raise RuntimeError("q70 attempted checkpoint count drift")
    if result.get("completed_checkpoint_count") != len(history):
        raise RuntimeError("q70 completed checkpoint count drift")

    final = records[-1]
    failed = final.get("status") == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
    if failed:
        if len(history) != len(records) - 1:
            raise RuntimeError("q70 failure/history count drift")
        if result.get("screen_terminal_condition") != (
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        ):
            raise RuntimeError("q70 failure terminal label drift")
        if result.get("failure_checkpoint_included") is not True:
            raise RuntimeError("q70 failure inclusion flag drift")
        if result.get("failure_record_sha256") != sha256(
            canonical_bytes(final)
        ):
            raise RuntimeError("q70 failure record digest drift")
        if result.get("horizon_reached_with_committed_checkpoint") is not False:
            raise RuntimeError("q70 failure horizon flag drift")
    else:
        if len(records) != EXTENDED_HORIZON or len(history) != EXTENDED_HORIZON:
            raise RuntimeError("q70 non-failure did not commit the horizon")
        if result.get("screen_terminal_condition") != "DIAGNOSTIC_HORIZON_REACHED":
            raise RuntimeError("q70 horizon terminal label drift")
        if result.get("failure_checkpoint_included") is not False:
            raise RuntimeError("q70 non-failure inclusion flag drift")
        if result.get("failure_record_sha256") is not None:
            raise RuntimeError("q70 non-failure record digest drift")
        if result.get("horizon_reached_with_committed_checkpoint") is not True:
            raise RuntimeError("q70 committed horizon flag drift")


def relabel_outer_result(
    result: Dict[str, Any],
    base: Any,
    anchor: Mapping[str, Any],
    adapter: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("D q70 relabel requires fresh same-byte self execution")
    validate_base_result(result, base, anchor)
    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)

    base_components = result["screen_execution_components"]
    base_components_sha = result["screen_execution_components_sha256"]
    if base_components_sha != sha256(canonical_bytes(base_components)):
        raise RuntimeError("base q70 component digest drift")
    components = [{
        "relative_path": SELF_NAME,
        "role": "D_k573440_c33_q70_fresh_same_byte_horizon_wrapper",
        "sha256": self_sha,
    }]
    saw_base = False
    for original in base_components:
        item = dict(original)
        if item.get("relative_path") == BASE_SCREEN_NAME:
            if item.get("sha256") != EXPECTED_BASE_SCREEN_SHA256:
                raise RuntimeError("base q68 screen component pin drift")
            item["role"] = "D_k573440_c33_q68_private_execution_parent_for_q70"
            saw_base = True
        components.append(item)
    if not saw_base:
        raise RuntimeError("base q68 screen component missing from q70 result")

    old_transform = result["checkpoint_transform"]
    old_transform_sha = result["checkpoint_transform_sha256"]
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("base q70 transform digest drift")
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
            "used_only_after_full_replay_for_exact_prefix_validation": True,
            "propagation_input": False,
            "checkpoint_68_state_loaded": False,
            "state_resume_input": False,
        },
    }
    transform = {
        "transform_id": "double_occupancy_k573440_c33_q70_horizon_v1",
        "base_q68_checkpoint_transform": old_transform,
        "base_q68_checkpoint_transform_sha256": old_transform_sha,
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
        raise RuntimeError("unexpected preexisting q70 source custody")
    custody[SELF_NAME] = self_sha

    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k573440_c33_q70_screen_v1"
        ),
        "screen_source_sha256": self_sha,
        "same_byte_self_execution": True,
        "horizon_extension_orchestration_owned_by_outer_screen": True,
        "q68_private_entrypoint_owns_full_replay_execution": True,
        "physical_checkpoint_loop_ownership_preserved_from_q68_result": True,
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
            "records_sha256": EXPECTED_BASE_RECORDS_SHA256,
            "selected_K_history_sha256": EXPECTED_BASE_HISTORY_SHA256,
            "loaded_before_replay_as_exact_reference": True,
            "used_only_after_replay_for_result_prefix_validation": True,
            "post_replay_prefix_validation_input": True,
            "propagation_input": False,
            "checkpoint_68_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
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
        raise RuntimeError("D q70 screen requires fresh same-byte self execution")
    repo = repo.resolve()
    base, _payload = load_base_screen(repo)
    anchor = load_base_transcript(repo, base)
    adapter = install_horizon_adapter(base)
    result = base._run_verified(repo)
    return relabel_outer_result(result, base, anchor, adapter)


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType(
        "verified_double_occupancy_k573440_c33_q70_screen"
    )
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("D q70 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("D q70 transcript exceeds output byte cap")
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
