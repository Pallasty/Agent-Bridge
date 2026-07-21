#!/usr/bin/env python3
"""Policy-only D K622592/C36 q72 diagnostic screen.

The frozen K622592/C36 q72 screen is compiled from exact pinned bytes and used
only as a code provider.  Its private entrypoint and relabeller are never
called.  After its old contract has been validated, this screen changes only
``max_single_expansion_terms`` and ``max_digest_terms`` on that isolated
module, then calls its exact lower-level load/configure/execute functions.

The frozen q72 resource-abort transcript is not read until the fresh replay
has returned.  It is post-replay evidence only: it is never an expansion,
checkpoint state, resume input, execution component, or custody source.
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
    "k622592_c36_l1048576_d1048576_q72_screen.py"
)
CODE_PROVIDER_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_q72_screen.py"
)
CONTROL_FLOW_ROOT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k622592_c36.py"
FROZEN_ABORT_TRANSCRIPT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_q72_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_l1048576_d1048576_q72_transcript.json"
)

EXPECTED_CODE_PROVIDER_SHA256 = (
    "2e22e1918fbc10cd696d700dbf05e8d99d0c333a1428e9473de6ebbc563488e1"
)
EXPECTED_CONTROL_FLOW_ROOT_SHA256 = (
    "b483d9555a24dd07ea96292ed0a7ed51587259a79a2c5d69e3a8bf1408b4a614"
)
EXPECTED_V6_BASELINE_CONFIGURATION_SHA256 = (
    "3e7f9ff0546addfaa23f351f3569b102d0c3ebb578dbc4873b042bac21070af2"
)
EXPECTED_V2_ARITHMETIC_SHA256 = (
    "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998"
)
EXPECTED_KERNEL_WRAPPER_SHA256 = (
    "7ac6c87f3d789ad62540cbc96e81f0a092594b0524eec3f9b05e7ffec2124838"
)
EXPECTED_FROZEN_ABORT_TRANSCRIPT_SHA256 = (
    "e7ae9abb11a4cc116778c8c373ff1c93131db9c9d36ba886ff6ef2d7b53bd09f"
)
EXPECTED_FROZEN_ABORT_TRANSCRIPT_SIZE = 726_293
EXPECTED_FROZEN_RECORDS_SHA256 = (
    "6bd9a1a5e6599efd78dda59025281af2d8a030beb02c3f145d9f3e055ed18d22"
)
EXPECTED_FROZEN_HISTORY_SHA256 = (
    "18e76e6b8a2eb970bf5930c79901f97d24e9e5cfed865d5a8c8e27bee5bec807"
)
EXPECTED_FROZEN_Q71_RECORD_SHA256 = (
    "bb5fffe2871aefed25755423d43b0689d48df7e954bb524e3041268a9fc22ad2"
)
EXPECTED_FROZEN_ABORT_SHA256 = (
    "a88ad538886ad3309b6a54679169a9f74ff66630cda5245b5149ca8070005f27"
)
EXPECTED_FROZEN_CONFIGURATION_REFERENCE_SHA256 = (
    "d8ac3bc5a105560dedd41442b14168d3e477e21e0193b96354fd7068d1fd5ab1"
)
EXPECTED_FROZEN_CONFIGURATION_OVERRIDE_SHA256 = (
    "f47b061f413264fca5c6eb2324356bd3ee2305f175392e22c327c7240bea1cf7"
)
EXPECTED_FROZEN_KERNEL_OVERRIDE_SHA256 = (
    "6fb7b9a56abe958e63d3c0368e72d5e93ab0251e7b0b8d98db8b75b214b337c8"
)
EXPECTED_FROZEN_HORIZON_OVERRIDE_SHA256 = (
    "6260d69cff7e23c4f725e81f1db2d2edd057a2a2b73bbf2b5fc99382003db6b7"
)
EXPECTED_FROZEN_TRANSFORM_SHA256 = (
    "b22eb3ad898890066fb79b946f14301be564be08639ae9e6b2543c42c79d177c"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_FROZEN_TRANSCRIPT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

MODE = "double_occupancy"
HORIZON = 72
K622592 = 622_592
LIVE_AND_DIGEST_CAP = 1_048_576

OLD_POLICY_CAPS_BASE = {
    "max_candidate_K": K622592,
    "max_output_terms_if_successful": K622592,
    "max_single_expansion_terms": 786_432,
    "max_digest_terms": 786_432,
    "max_term_gate_visits": 536_870_912,
    "max_expansion_coefficient_tick_bits": 192,
    "max_trigonometric_tick_bits": 66,
    "max_product_bits": 384,
    "max_suffix_accumulator_bits": 224,
}
POLICY_CAPS_BASE = {
    **OLD_POLICY_CAPS_BASE,
    "max_single_expansion_terms": LIVE_AND_DIGEST_CAP,
    "max_digest_terms": LIVE_AND_DIGEST_CAP,
}
POLICY_CHANGED_FIELDS = frozenset({
    "max_single_expansion_terms",
    "max_digest_terms",
})
EXPECTED_POLICY_CAPS_SHA256 = (
    "df050df416ef67c66bbcbe5aaa7c7b200149cff822208c1f1758baf276df9741"
)
EXPECTED_TRANSCRIPT_POLICY_CAPS_SHA256 = (
    "aff89906ad9bc847b85021dff29187bba02b4d3171a55437f5827fde2e4fd631"
)
EXPECTED_CANDIDATE_SHA256 = (
    "5ab222cdcd073227d6d5e23f881ce94511dab86c35b6aab53c72de9f403367fc"
)
EXPECTED_WRAPPED_KERNEL_LIMITS = {
    "max_candidate_count": 36,
    "max_digest_terms": LIVE_AND_DIGEST_CAP,
    "max_expansion_coefficient_tick_bits": 192,
    "max_product_bits": 384,
    "max_retained_K": K622592,
    "max_single_expansion_terms": LIVE_AND_DIGEST_CAP,
    "max_source_bytes": 196_608,
    "max_suffix_accumulator_bits": 224,
    "max_term_gate_visits": 1_000_000_000,
    "max_trigonometric_tick_bits": 66,
}

Q72_PROPAGATION_FIELDS = (
    "checkpoint_index_zero_based",
    "checkpoint_number_one_based",
    "stage_index",
    "stage_group",
    "batch_in_stage",
    "gate_occurrence_first_zero_based",
    "gate_occurrence_last_zero_based",
    "gate_batch_sha256",
    "input_expansion_count",
    "input_expansion_sha256",
    "pretruncation_expansion_count",
    "peak_live_terms_this_checkpoint",
    "peak_live_terms_cumulative",
    "term_gate_visits_increment",
    "term_gate_visits_cumulative",
    "rounding_increment_scaled_ticks_squared",
    "rounding_cumulative_scaled_ticks_squared",
    "maximum_expansion_coefficient_tick_bits",
    "maximum_product_bits",
)


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


def exact_value_equal(observed: Any, expected: Any) -> bool:
    if type(observed) is not type(expected):
        return False
    if type(expected) is dict:
        return (
            observed.keys() == expected.keys()
            and all(
                exact_value_equal(observed[key], expected[key])
                for key in expected
            )
        )
    if type(expected) in (list, tuple):
        return (
            len(observed) == len(expected)
            and all(
                exact_value_equal(left, right)
                for left, right in zip(observed, expected)
            )
        )
    return observed == expected


def changed_keys(before: Mapping[str, Any], after: Mapping[str, Any]) -> set[str]:
    return {
        key for key in set(before) | set(after)
        if not exact_value_equal(before.get(key), after.get(key))
    }


def require_exact_keys(value: Any, expected: frozenset[str], label: str) -> None:
    if type(value) is not dict:
        raise RuntimeError(f"{label} is not an exact dict")
    observed = frozenset(value)
    if observed != expected:
        raise RuntimeError(
            f"{label} exact key-set drift: "
            f"missing={sorted(expected - observed)}, "
            f"extra={sorted(observed - expected)}"
        )


def is_canonical_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


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


def validate_local_configuration() -> None:
    if changed_keys(OLD_POLICY_CAPS_BASE, POLICY_CAPS_BASE) != POLICY_CHANGED_FIELDS:
        raise RuntimeError("policy-only route changed outside live/digest caps")
    for field in POLICY_CHANGED_FIELDS:
        if OLD_POLICY_CAPS_BASE[field] != 786_432:
            raise RuntimeError(f"old policy cap drift: {field}")
        if POLICY_CAPS_BASE[field] != LIVE_AND_DIGEST_CAP:
            raise RuntimeError(f"new policy cap drift: {field}")
        kernel_field = field
        if POLICY_CAPS_BASE[field] != EXPECTED_WRAPPED_KERNEL_LIMITS[kernel_field]:
            raise RuntimeError(f"policy/kernel limit mismatch: {field}")
    if sha256(canonical_bytes(POLICY_CAPS_BASE)) != EXPECTED_POLICY_CAPS_SHA256:
        raise RuntimeError("policy-only cap digest drift")
    transcript_caps = {**POLICY_CAPS_BASE, "max_candidate_count": 36}
    if sha256(canonical_bytes(transcript_caps)) != (
        EXPECTED_TRANSCRIPT_POLICY_CAPS_SHA256
    ):
        raise RuntimeError("transcript policy-cap digest drift")
    if HORIZON != 72 or K622592 != 622_592:
        raise RuntimeError("policy-only K/horizon drift")


def load_code_provider(repo: Path) -> Any:
    path = checked_repo_file(repo, CODE_PROVIDER_NAME)
    payload = bounded_bytes(path, MAX_PINNED_SOURCE_BYTES)
    if sha256(payload) != EXPECTED_CODE_PROVIDER_SHA256:
        raise RuntimeError("D q72 code-provider source pin drift")
    provider = compile_isolated(
        "pinned_d_k622592_c36_q72_code_provider_for_policy_route",
        path,
        payload,
    )
    expected = {
        "SELF_NAME": CODE_PROVIDER_NAME,
        "CONTROL_FLOW_PARENT_NAME": CONTROL_FLOW_ROOT_NAME,
        "EXPECTED_CONTROL_FLOW_PARENT_SHA256": EXPECTED_CONTROL_FLOW_ROOT_SHA256,
        "V6_BASELINE_CONFIGURATION_NAME": V6_BASELINE_CONFIGURATION_NAME,
        "EXPECTED_V6_BASELINE_CONFIGURATION_SHA256": (
            EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
        ),
        "V2_ARITHMETIC_NAME": V2_ARITHMETIC_NAME,
        "EXPECTED_V2_ARITHMETIC_SHA256": EXPECTED_V2_ARITHMETIC_SHA256,
        "KERNEL_WRAPPER_NAME": KERNEL_WRAPPER_NAME,
        "EXPECTED_KERNEL_WRAPPER_SHA256": EXPECTED_KERNEL_WRAPPER_SHA256,
        "MODE": MODE,
        "EXTENDED_HORIZON": HORIZON,
        "K622592": K622592,
        "POLICY_CAPS_BASE": OLD_POLICY_CAPS_BASE,
        "EXPECTED_WRAPPED_KERNEL_LIMITS": EXPECTED_WRAPPED_KERNEL_LIMITS,
    }
    for field, value in expected.items():
        if not exact_value_equal(getattr(provider, field, None), value):
            raise RuntimeError(f"D q72 code-provider contract drift: {field}")
    if sha256(canonical_bytes(list(provider.D_CANDIDATES))) != (
        EXPECTED_CANDIDATE_SHA256
    ):
        raise RuntimeError("D q72 code-provider candidate digest drift")
    if len(provider.EXPECTED_PARENT_RESULT_KEYS) != 67:
        raise RuntimeError("D q72 code-provider raw schema drift")
    if len(provider.EXPECTED_RELABELLED_RESULT_KEYS) != 96:
        raise RuntimeError("D q72 code-provider final schema drift")
    provider.validate_local_configuration()
    required_functions = (
        "load_control_flow_parent",
        "load_configured_v6_baseline",
        "load_kernel_wrapper",
        "configure_parent_execution",
        "execute_parent_with_structured_abort",
        "load_route_reference",
        "validate_replay_handoff",
    )
    for name in required_functions:
        function = getattr(provider, name, None)
        if (
            type(function) is not types.FunctionType
            or function.__globals__ is not provider.__dict__
            or function.__module__ != provider.__name__
            or function.__code__.co_filename != provider.__file__
        ):
            raise RuntimeError(f"D q72 code-provider function authority drift: {name}")
    return provider


def execute_fresh_replay(
    provider: Any,
    repo: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Run the exact lower-level sequence with only two policy fields changed."""

    if type(provider) is not types.ModuleType:
        raise RuntimeError("policy route code provider is not isolated")
    provider.validate_local_configuration()
    old_caps = copy.deepcopy(provider.POLICY_CAPS_BASE)
    if not exact_value_equal(old_caps, OLD_POLICY_CAPS_BASE):
        raise RuntimeError("policy route did not begin from the frozen caps")
    if changed_keys(old_caps, POLICY_CAPS_BASE) != POLICY_CHANGED_FIELDS:
        raise RuntimeError("policy adapter delta is not exactly two fields")
    context: Dict[str, Any] = {
        "code_provider_private_entrypoint_called": False,
        "code_provider_relabeller_called": False,
        "frozen_abort_loaded_before_replay": False,
        "changed_policy_fields": sorted(POLICY_CHANGED_FIELDS),
        "policy_caps_before": old_caps,
        "policy_caps_after": copy.deepcopy(POLICY_CAPS_BASE),
    }
    try:
        provider.POLICY_CAPS_BASE = copy.deepcopy(POLICY_CAPS_BASE)
        if changed_keys(old_caps, provider.POLICY_CAPS_BASE) != POLICY_CHANGED_FIELDS:
            raise RuntimeError("isolated provider policy mutation drift")

        control_parent = provider.load_control_flow_parent(repo)
        configuration, baseline_d = provider.load_configured_v6_baseline(repo)
        if not exact_value_equal(configuration.POLICY_CAPS_BASE, POLICY_CAPS_BASE):
            raise RuntimeError("effective v6 policy adapter drift")
        if tuple(configuration.MODE_CONFIG[MODE]["candidates"]) != tuple(
            provider.D_CANDIDATES
        ):
            raise RuntimeError("policy adapter changed the D candidate ladder")
        wrapper, wrapper_sha, manifest = provider.load_kernel_wrapper(repo)
        if wrapper_sha != EXPECTED_KERNEL_WRAPPER_SHA256:
            raise RuntimeError("policy adapter wrapper pin drift")
        horizon_override = provider.configure_parent_execution(
            control_parent,
            configuration,
            wrapper,
        )
        result = provider.execute_parent_with_structured_abort(
            control_parent,
            repo,
        )
        context.update({
            "baseline_d": tuple(baseline_d),
            "wrapper_sha": wrapper_sha,
            "wrapper_manifest": copy.deepcopy(manifest),
            "raw_control_flow_horizon_override": copy.deepcopy(
                horizon_override
            ),
            "exact_lower_level_sequence_called": [
                "load_control_flow_parent",
                "load_configured_v6_baseline",
                "load_kernel_wrapper",
                "configure_parent_execution",
                "execute_parent_with_structured_abort",
            ],
        })
    finally:
        provider.POLICY_CAPS_BASE = old_caps
    if type(result) is not dict:
        raise RuntimeError("policy route replay returned a non-dict result")
    if not exact_value_equal(provider.POLICY_CAPS_BASE, OLD_POLICY_CAPS_BASE):
        raise RuntimeError("policy adapter did not restore provider globals")
    required_context = {
        "baseline_d",
        "wrapper_sha",
        "wrapper_manifest",
        "raw_control_flow_horizon_override",
        "exact_lower_level_sequence_called",
    }
    if not required_context <= context.keys():
        raise RuntimeError("policy route execution context is incomplete")
    return result, context


def load_frozen_abort_evidence(
    repo: Path,
    provider: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Load the old q72 abort only after replay as exact comparison evidence."""

    provider_bytes = bounded_bytes(
        checked_repo_file(repo, CODE_PROVIDER_NAME),
        MAX_PINNED_SOURCE_BYTES,
    )
    if sha256(provider_bytes) != EXPECTED_CODE_PROVIDER_SHA256:
        raise RuntimeError("frozen q72 screen pin drift at evidence boundary")
    raw = bounded_bytes(
        checked_repo_file(repo, FROZEN_ABORT_TRANSCRIPT_NAME),
        MAX_FROZEN_TRANSCRIPT_BYTES,
    )
    if len(raw) != EXPECTED_FROZEN_ABORT_TRANSCRIPT_SIZE:
        raise RuntimeError("frozen q72 abort file-size drift")
    if sha256(raw) != EXPECTED_FROZEN_ABORT_TRANSCRIPT_SHA256:
        raise RuntimeError("frozen q72 abort file pin drift")
    try:
        transcript = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("frozen q72 abort is invalid JSON") from exc
    if type(transcript) is not dict or raw != canonical_bytes(transcript):
        raise RuntimeError("frozen q72 abort is not canonical JSON")
    require_exact_keys(
        transcript,
        frozenset(provider.EXPECTED_RELABELLED_RESULT_KEYS),
        "frozen q72 abort transcript",
    )
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k622592_c36_q72_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_CODE_PROVIDER_SHA256,
        "screen_terminal_condition": "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
        "attempted_checkpoint_count": 72,
        "completed_checkpoint_count": 71,
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": False,
        "screen_horizon_checkpoint_count": HORIZON,
        "candidate_K_values": list(provider.D_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **OLD_POLICY_CAPS_BASE,
            "max_candidate_count": len(provider.D_CANDIDATES),
        },
        "kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_LIMITS,
        "records_sha256": EXPECTED_FROZEN_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_FROZEN_HISTORY_SHA256,
        "resource_policy_abort_sha256": EXPECTED_FROZEN_ABORT_SHA256,
        "configuration_reference_sha256": (
            EXPECTED_FROZEN_CONFIGURATION_REFERENCE_SHA256
        ),
        "configuration_override_sha256": (
            EXPECTED_FROZEN_CONFIGURATION_OVERRIDE_SHA256
        ),
        "kernel_capability_override_sha256": (
            EXPECTED_FROZEN_KERNEL_OVERRIDE_SHA256
        ),
        "parent_horizon_override_sha256": (
            EXPECTED_FROZEN_HORIZON_OVERRIDE_SHA256
        ),
        "checkpoint_transform_sha256": EXPECTED_FROZEN_TRANSFORM_SHA256,
    }
    for field, value in expected.items():
        if not exact_value_equal(transcript.get(field), value):
            raise RuntimeError(f"frozen q72 abort evidence drift: {field}")
    records = transcript.get("records")
    history = transcript.get("selected_K_history")
    if type(records) is not list or len(records) != 71:
        raise RuntimeError("frozen q72 abort record count drift")
    if type(history) is not list or len(history) != 71:
        raise RuntimeError("frozen q72 abort history count drift")
    if sha256(canonical_bytes(records)) != EXPECTED_FROZEN_RECORDS_SHA256:
        raise RuntimeError("frozen q72 abort record digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_FROZEN_HISTORY_SHA256:
        raise RuntimeError("frozen q72 abort history digest drift")
    q71 = records[-1]
    if sha256(canonical_bytes(q71)) != EXPECTED_FROZEN_Q71_RECORD_SHA256:
        raise RuntimeError("frozen q71 record digest drift")
    if q71.get("checkpoint_number_one_based") != 71:
        raise RuntimeError("frozen q71 checkpoint drift")
    if q71.get("status") != "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
        raise RuntimeError("frozen q71 status drift")
    if q71.get("selected_K") != K622592:
        raise RuntimeError("frozen q71 selected K drift")
    abort = transcript.get("resource_policy_abort")
    if sha256(canonical_bytes(abort)) != EXPECTED_FROZEN_ABORT_SHA256:
        raise RuntimeError("frozen q72 nested abort digest drift")
    provider.validate_resource_policy_abort(transcript, q71)
    if abort.get("max_single_expansion_terms") != 786_432:
        raise RuntimeError("frozen q72 abort cap drift")
    if abort.get("pretruncation_expansion_count") != 799_279:
        raise RuntimeError("frozen q72 pretruncation evidence drift")
    if abort["pretruncation_expansion_count"] > LIVE_AND_DIGEST_CAP:
        raise RuntimeError("frozen q72 obstruction was not removed by new cap")

    reference = {
        "route_id": (
            "double_occupancy_k622592_c36_q72_abort_to_"
            "l1048576_d1048576_q72_policy_only_v1"
        ),
        "code_provider_screen": {
            "relative_path": CODE_PROVIDER_NAME,
            "source_sha256": EXPECTED_CODE_PROVIDER_SHA256,
            "compiled_from_verified_bytes": True,
            "private_entrypoint_called": False,
            "relabeller_called": False,
            "exact_lower_level_functions_called": True,
            "execution_source_layer": True,
        },
        "frozen_abort_transcript": {
            "relative_path": FROZEN_ABORT_TRANSCRIPT_NAME,
            "file_size_bytes": EXPECTED_FROZEN_ABORT_TRANSCRIPT_SIZE,
            "file_sha256": EXPECTED_FROZEN_ABORT_TRANSCRIPT_SHA256,
            "records_sha256": EXPECTED_FROZEN_RECORDS_SHA256,
            "selected_K_history_sha256": EXPECTED_FROZEN_HISTORY_SHA256,
            "q71_record_sha256": EXPECTED_FROZEN_Q71_RECORD_SHA256,
            "old_resource_abort_sha256": EXPECTED_FROZEN_ABORT_SHA256,
            "compiled": False,
            "executed": False,
            "loaded_before_replay": False,
            "loaded_after_fresh_replay_as_exact_evidence": True,
            "used_only_for_post_replay_q1_through_q71_and_q72_propagation_validation": True,
            "propagation_input": False,
            "checkpoint_71_state_loaded": False,
            "checkpoint_72_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
            "source_custody_layer": False,
        },
        "secondary_provider_route_validation_reference": {
            "screen_relative_path": provider.ROUTE_PREDECESSOR_SCREEN_NAME,
            "screen_source_sha256": (
                provider.EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256
            ),
            "transcript_relative_path": (
                provider.ROUTE_PREDECESSOR_TRANSCRIPT_NAME
            ),
            "transcript_file_sha256": (
                provider.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256
            ),
            "loaded_before_replay": False,
            "loaded_after_fresh_replay_inside_validate_raw_replay": True,
            "used_only_by_verified_provider_validate_replay_handoff": True,
            "propagation_input": False,
            "state_resume_input": False,
            "execution_source_layer": False,
            "source_custody_layer": False,
        },
        "incremental_semantic_delta_from_frozen_q72": {
            "candidate_K_values_changed": False,
            "horizon_checkpoint_count_changed": False,
            "kernel_capability_limits_changed": False,
            "policy_cap_changes": {
                "max_digest_terms": {
                    "before": 786_432,
                    "after": LIVE_AND_DIGEST_CAP,
                },
                "max_single_expansion_terms": {
                    "before": 786_432,
                    "after": LIVE_AND_DIGEST_CAP,
                },
            },
        },
        "terminal_contract": {
            "artifact_branches": [
                "Q72_POLICY_FAILURE",
                "Q72_SUCCESS_HORIZON_REACHED",
            ],
            "resource_policy_abort_pair_null_on_every_artifact": True,
            "kernel_SchemaError_and_unhandled_resource_exceptions_rethrown": True,
            "structured_resource_results_rejected_before_artifact": True,
            "resource_exception_artifact_generated": False,
        },
    }
    return transcript, reference


def validate_raw_replay(
    result: Dict[str, Any],
    provider: Any,
    repo: Path,
    frozen: Mapping[str, Any],
) -> Dict[str, Any]:
    require_exact_keys(
        result,
        frozenset(provider.EXPECTED_PARENT_RESULT_KEYS),
        "policy-only raw replay",
    )
    expected_caps = {**POLICY_CAPS_BASE, "max_candidate_count": 36}
    if not exact_value_equal(result.get("proposed_policy_caps"), expected_caps):
        raise RuntimeError("policy-only replay caps drift")
    if sha256(canonical_bytes(result["proposed_policy_caps"])) != (
        EXPECTED_TRANSCRIPT_POLICY_CAPS_SHA256
    ):
        raise RuntimeError("policy-only replay cap digest drift")
    fixed = {
        "candidate_K_values": list(provider.D_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "screen_horizon_checkpoint_count": HORIZON,
        "kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_LIMITS,
        "screen_source_sha256": EXPECTED_CONTROL_FLOW_ROOT_SHA256,
    }
    for field, value in fixed.items():
        if not exact_value_equal(result.get(field), value):
            raise RuntimeError(f"policy-only replay invariant drift: {field}")
    records = result.get("records")
    history = result.get("selected_K_history")
    frozen_records = frozen.get("records")
    frozen_history = frozen.get("selected_K_history")
    if type(records) is not list or len(records) not in (71, 72):
        raise RuntimeError("policy-only replay record count drift")
    if type(history) is not list or len(history) not in (71, 72):
        raise RuntimeError("policy-only replay history count drift")
    if not exact_value_equal(records[:71], frozen_records):
        raise RuntimeError("policy-only replay changed exact q1-q71 records")
    if not exact_value_equal(history[:71], frozen_history):
        raise RuntimeError("policy-only replay changed exact q1-q71 history")
    if sha256(canonical_bytes(records[:71])) != EXPECTED_FROZEN_RECORDS_SHA256:
        raise RuntimeError("policy-only q1-q71 record digest drift")
    if sha256(canonical_bytes(history[:71])) != EXPECTED_FROZEN_HISTORY_SHA256:
        raise RuntimeError("policy-only q1-q71 history digest drift")

    abort = result.get("resource_policy_abort")
    if abort is not None:
        if result.get("resource_policy_abort_sha256") != sha256(
            canonical_bytes(abort)
        ):
            raise RuntimeError("policy-only resource abort digest drift")
        if abort.get("max_single_expansion_terms") == 786_432:
            raise RuntimeError("old 786432 q72 abort is illegal on policy route")
        raise RuntimeError(
            "policy-only resource exception must fail closed without artifact"
        )
    else:
        if result.get("resource_policy_abort_sha256") is not None:
            raise RuntimeError("null policy-only abort carries a digest")
        if len(records) != 72:
            raise RuntimeError("policy-only normal terminal lacks q72 record")
        q72 = records[71]
        frozen_abort = frozen["resource_policy_abort"]
        for field in Q72_PROPAGATION_FIELDS:
            if not exact_value_equal(q72.get(field), frozen_abort.get(field)):
                raise RuntimeError(
                    f"policy-only q72 propagation evidence drift: {field}"
                )
        q72_propagation_matches_frozen_evidence = True
        if q72.get("status") == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
            terminal_branch = "Q72_SUCCESS_HORIZON_REACHED"
        elif q72.get("status") == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE":
            terminal_branch = "Q72_POLICY_FAILURE"
        else:
            raise RuntimeError("policy-only q72 terminal status drift")

    # The provider's older D35 canonical is loaded only here, after the fresh
    # replay and the frozen q72 evidence load, as a secondary validation input.
    predecessor, _reference = provider.load_route_reference(repo)
    old_caps = provider.POLICY_CAPS_BASE
    try:
        provider.POLICY_CAPS_BASE = copy.deepcopy(POLICY_CAPS_BASE)
        parent_handoff = provider.validate_replay_handoff(result, predecessor)
    finally:
        provider.POLICY_CAPS_BASE = old_caps

    allowed_parent_branches = {
        "Q72_SUCCESS_HORIZON_REACHED": "Q71_AND_Q72_SUCCESS_HORIZON_REACHED",
        "Q72_POLICY_FAILURE": "Q71_SUCCESS_Q72_FAILURE",
    }
    if parent_handoff.get("terminal_branch") != allowed_parent_branches[
        terminal_branch
    ]:
        raise RuntimeError("policy-only parent terminal-branch drift")
    return {
        "validation_id": (
            "D_k622592_c36_l1048576_d1048576_q72_policy_handoff_v1"
        ),
        "execution_provider_handoff_validation": parent_handoff,
        "execution_provider_handoff_validation_sha256": sha256(
            canonical_bytes(parent_handoff)
        ),
        "q1_through_q71_records_exact_to_post_replay_frozen_evidence": True,
        "q1_through_q71_selected_history_exact_to_post_replay_frozen_evidence": True,
        "q1_through_q71_records_sha256": EXPECTED_FROZEN_RECORDS_SHA256,
        "q1_through_q71_selected_history_sha256": EXPECTED_FROZEN_HISTORY_SHA256,
        "q72_old_abort_loaded_before_replay": False,
        "q72_old_abort_used_as_state_or_resume_input": False,
        "secondary_D35_reference_loaded_only_post_replay_for_provider_handoff_validation": True,
        "q72_old_786432_abort_illegal_on_policy_route": True,
        "resource_exceptions_fail_closed_without_artifact": True,
        "q72_propagation_matches_post_replay_frozen_evidence": (
            q72_propagation_matches_frozen_evidence
        ),
        "terminal_branch": terminal_branch,
        "candidate_K_values_changed": False,
        "horizon_checkpoint_count_changed": False,
        "kernel_capability_limits_changed": False,
        "incremental_policy_changed_fields": sorted(POLICY_CHANGED_FIELDS),
    }


def execution_components(
    provider: Any,
    parent_components: Any,
    self_sha: str,
) -> list[Dict[str, Any]]:
    if not exact_value_equal(
        parent_components,
        list(provider.EXPECTED_PARENT_EXECUTION_COMPONENTS),
    ):
        raise RuntimeError("policy-only raw execution components drift")
    components = [
        {
            "relative_path": SELF_NAME,
            "role": "D_policy_only_fresh_same_byte_screen",
            "sha256": self_sha,
        },
        {
            "relative_path": CODE_PROVIDER_NAME,
            "role": "verified_lower_level_execution_code_provider",
            "sha256": EXPECTED_CODE_PROVIDER_SHA256,
        },
    ]
    for original in parent_components:
        item = dict(original)
        path = item.get("relative_path")
        if path == CONTROL_FLOW_ROOT_NAME:
            item["role"] = "fresh_four_gate_control_flow_private_entrypoint"
        elif path == V6_BASELINE_CONFIGURATION_NAME:
            item["role"] = "v6_baseline_before_declared_policy_and_route_override"
        elif path == V2_ARITHMETIC_NAME:
            item["role"] = "v2_arithmetic_bytes_beneath_unchanged_wrapper"
        components.append(item)
        if path == V2_ARITHMETIC_NAME:
            components.append({
                "relative_path": KERNEL_WRAPPER_NAME,
                "role": "unchanged_k622592_c36_capability_provider",
                "sha256": EXPECTED_KERNEL_WRAPPER_SHA256,
            })
    if len(components) != 12:
        raise RuntimeError("policy-only execution component cardinality drift")
    paths = [item["relative_path"] for item in components]
    if len(paths) != len(set(paths)):
        raise RuntimeError("policy-only execution components contain duplicates")
    if FROZEN_ABORT_TRANSCRIPT_NAME in paths:
        raise RuntimeError("frozen abort became an execution component")
    return components


def configuration_override(
    provider: Any,
    baseline_d: Tuple[int, ...],
) -> Dict[str, Any]:
    parent_override = provider.configuration_override(baseline_d)
    if sha256(canonical_bytes(parent_override)) != (
        EXPECTED_FROZEN_CONFIGURATION_OVERRIDE_SHA256
    ):
        raise RuntimeError("frozen provider configuration override drift")
    return {
        "override_id": (
            "double_occupancy_k622592_c36_l1048576_d1048576_"
            "q72_policy_override_v1"
        ),
        "execution_provider_configuration_override": parent_override,
        "execution_provider_configuration_override_sha256": sha256(
            canonical_bytes(parent_override)
        ),
        "incremental_route_from_frozen_k622592_c36_q72": {
            "candidate_K_values_changed": False,
            "horizon_checkpoint_count_changed": False,
            "kernel_capability_limits_changed": False,
            "policy_cap_changes": {
                "max_digest_terms": {
                    "before": 786_432,
                    "after": LIVE_AND_DIGEST_CAP,
                },
                "max_single_expansion_terms": {
                    "before": 786_432,
                    "after": LIVE_AND_DIGEST_CAP,
                },
            },
            "changed_fields": [
                "POLICY_CAPS_BASE.max_digest_terms",
                "POLICY_CAPS_BASE.max_single_expansion_terms",
            ],
        },
        "direct_v6_delta_includes_inherited_candidate_K_and_horizon_overrides": True,
        "only_two_fields_claim_applies_only_to_incremental_frozen_q72_route": True,
        "effective_candidate_K_values": list(provider.D_CANDIDATES),
        "effective_policy_caps": {
            **POLICY_CAPS_BASE,
            "max_candidate_count": len(provider.D_CANDIDATES),
        },
    }


def expected_final_source_custody(
    provider: Any,
    raw_custody: Any,
    self_sha: str,
) -> Dict[str, str]:
    parent_custody = provider.validate_parent_source_custody(raw_custody)
    custody = {
        **parent_custody,
        SELF_NAME: self_sha,
        CODE_PROVIDER_NAME: EXPECTED_CODE_PROVIDER_SHA256,
        CONTROL_FLOW_ROOT_NAME: EXPECTED_CONTROL_FLOW_ROOT_SHA256,
        KERNEL_WRAPPER_NAME: EXPECTED_KERNEL_WRAPPER_SHA256,
    }
    if len(custody) != 11:
        raise RuntimeError("policy-only source custody cardinality drift")
    if FROZEN_ABORT_TRANSCRIPT_NAME in custody:
        raise RuntimeError("frozen abort became a custody source")
    return custody


def validate_and_relabel(
    result: Dict[str, Any],
    provider: Any,
    repo: Path,
    frozen: Mapping[str, Any],
    route_reference: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("policy-only relabel requires fresh same-byte self execution")
    handoff = validate_raw_replay(result, provider, repo, frozen)
    old_components = result.get("screen_execution_components")
    old_transform = result.get("checkpoint_transform")
    old_transform_sha = result.get("checkpoint_transform_sha256")
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("policy-only raw transform digest drift")
    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = execution_components(provider, old_components, self_sha)
    reference = provider.configuration_reference()
    if sha256(canonical_bytes(reference)) != (
        EXPECTED_FROZEN_CONFIGURATION_REFERENCE_SHA256
    ):
        raise RuntimeError("policy-only configuration reference drift")
    config = configuration_override(provider, tuple(context["baseline_d"]))
    parent_kernel = provider.kernel_capability_override(
        context["wrapper_sha"],
        context["wrapper_manifest"],
    )
    if sha256(canonical_bytes(parent_kernel)) != EXPECTED_FROZEN_KERNEL_OVERRIDE_SHA256:
        raise RuntimeError("policy-only inherited kernel override drift")
    kernel_override = {
        "override_id": "D_k622592_c36_policy_route_unchanged_kernel_v1",
        "execution_provider_kernel_capability_override": parent_kernel,
        "execution_provider_kernel_capability_override_sha256": sha256(
            canonical_bytes(parent_kernel)
        ),
        "effective_kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_LIMITS,
        "incremental_route_kernel_changes": {},
        "wrapper_source_bytes_changed": False,
    }
    raw_horizon = copy.deepcopy(context["raw_control_flow_horizon_override"])
    if sha256(canonical_bytes(raw_horizon)) != EXPECTED_FROZEN_HORIZON_OVERRIDE_SHA256:
        raise RuntimeError("policy-only inherited horizon override drift")
    parent_horizon = {
        "override_id": "D_k622592_c36_policy_route_unchanged_horizon_v1",
        "execution_provider_horizon_override": raw_horizon,
        "execution_provider_horizon_override_sha256": sha256(
            canonical_bytes(raw_horizon)
        ),
        "incremental_route_horizon_changes": {},
        "effective_horizon_checkpoint_count": HORIZON,
    }
    transform = {
        "transform_id": (
            "double_occupancy_four_gate_k622592_c36_"
            "l1048576_d1048576_q72_policy_only_v1"
        ),
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": (
            old_transform_sha
        ),
        "frozen_q72_outer_transform_sha256": EXPECTED_FROZEN_TRANSFORM_SHA256,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "candidate_K_values_changed": False,
        "kernel_capability_limits_changed": False,
        "horizon_checkpoint_count_changed": False,
        "incremental_policy_changed_fields": sorted(POLICY_CHANGED_FIELDS),
        "q72_outcome_precommitted": False,
    }
    custody = expected_final_source_custody(
        provider,
        result.get("source_custody"),
        self_sha,
    )
    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k622592_c36_l1048576_d1048576_q72_screen_v1"
        ),
        "screen_source_sha256": self_sha,
        "same_byte_self_execution": True,
        "control_flow_owned_by_screen": False,
        "control_flow_owned_by_verified_parent": True,
        "control_flow_parent_relative_path": CONTROL_FLOW_ROOT_NAME,
        "control_flow_parent_source_sha256": EXPECTED_CONTROL_FLOW_ROOT_SHA256,
        "control_flow_parent_compiled_from_verified_bytes": True,
        "control_flow_parent_module_isolated": True,
        "control_flow_parent_same_byte_execution": True,
        "control_flow_parent_private_entrypoint_called": True,
        "control_flow_parent_runtime_horizon_override_applied": True,
        "v6_configuration_source_used_as_baseline_only": True,
        "v6_runtime_configuration_override_applied": True,
        "v2_arithmetic_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "v2_arithmetic_compiled_from_verified_bytes": True,
        "arithmetic_kernel_commit_role": (
            "base_v2_arithmetic_implementation_commit_before_unchanged_"
            "k622592_c36_capability_wrapper"
        ),
        "kernel_capability_wrapper_relative_path": KERNEL_WRAPPER_NAME,
        "kernel_capability_wrapper_source_sha256": EXPECTED_KERNEL_WRAPPER_SHA256,
        "kernel_capability_wrapper_compiled_from_verified_bytes": True,
        "kernel_capability_wrapper_module_isolated": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(canonical_bytes(components)),
        "configuration_reference": reference,
        "configuration_reference_sha256": sha256(canonical_bytes(reference)),
        "configuration_override": config,
        "configuration_override_sha256": sha256(canonical_bytes(config)),
        "kernel_capability_override": kernel_override,
        "kernel_capability_override_sha256": sha256(
            canonical_bytes(kernel_override)
        ),
        "parent_horizon_override": parent_horizon,
        "parent_horizon_override_sha256": sha256(canonical_bytes(parent_horizon)),
        "route_predecessor_reference": dict(route_reference),
        "route_predecessor_reference_sha256": sha256(
            canonical_bytes(route_reference)
        ),
        "predecessor_handoff_validation": handoff,
        "predecessor_handoff_validation_sha256": sha256(canonical_bytes(handoff)),
        "checkpoint_transform": transform,
        "checkpoint_transform_sha256": sha256(canonical_bytes(transform)),
        "source_custody": custody,
        "diagnostic_candidate_ladder_precommitted_before_replay": True,
        "diagnostic_horizon_precommitted_before_replay": True,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    })
    require_exact_keys(
        result,
        frozenset(provider.EXPECTED_RELABELLED_RESULT_KEYS),
        "policy-only relabelled result",
    )
    return result


def _run_verified(repo: Path) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("policy-only screen requires fresh same-byte execution")
    validate_local_configuration()
    repo = repo.resolve()
    provider = load_code_provider(repo)
    result, context = execute_fresh_replay(provider, repo)
    frozen, route_reference = load_frozen_abort_evidence(repo, provider)
    return validate_and_relabel(
        result,
        provider,
        repo,
        frozen,
        route_reference,
        context,
    )


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType(
        "verified_d_k622592_c36_l1048576_d1048576_q72_screen"
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
        raise RuntimeError("policy-only transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("policy-only transcript exceeds output byte cap")
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
    print(json.dumps({
        "output": output.name,
        "semantic_and_file_sha256": sha256(raw),
        "records_sha256": result["records_sha256"],
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "attempted_checkpoint_count": result["attempted_checkpoint_count"],
        "screen_terminal_condition": result["screen_terminal_condition"],
        "policy_terminal_branch": result[
            "predecessor_handoff_validation"
        ]["terminal_branch"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
