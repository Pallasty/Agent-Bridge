#!/usr/bin/env python3
"""Source-pinned, diagnostic-only D K655360/C37 q76 screen.

The exact q74 screen is the immediate same-byte private execution parent.  It
still owns a fresh checkpoint-one replay through its exact q72 parent; this
screen changes only the diagnostic horizon from 74 to 76.  Both older
canonical loaders and both older relabellers are suppressed during execution.
The q74 canonical is loaded only after replay as exact q1--74 prefix evidence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
import types
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple


SELF_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k655360_c37_l1048576_d1048576_q76_screen.py"
)
EXECUTION_PARENT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k655360_c37_l1048576_d1048576_q74_screen.py"
)
NESTED_Q72_PARENT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k655360_c37_l1048576_d1048576_q72_screen.py"
)
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k655360_c37_l1048576_d1048576_q74_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k655360_c37_l1048576_d1048576_q76_transcript.json"
)

EXPECTED_EXECUTION_PARENT_SHA256 = (
    "5e2e077a9cab2a2b83f9830d755bafb7cc6dfa1d1c8a1ffade840d09e5016376"
)
EXPECTED_EXECUTION_PARENT_FILE_SIZE = 117_108
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "4421f5973253968167b1c8bd77e024b18450325ea9581ed39dbe975ec8163ec9"
)
EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE = 773_489
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "f765797dad4f6892524fc651a259786dff9c10187a6c634fc088fd3508c1e89f"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "d521cdf189b54254cf3ca3d0e9033b52c90ea6ec91dc571d95a605e520972ff8"
)
EXPECTED_ROUTE_PREDECESSOR_ROWS_SHA256 = (
    "0188a245385cd11ad15972881fefd916061dd4eb73f413c8fa1acc2e47bac8d3"
)
EXPECTED_ROUTE_PREDECESSOR_Q74_RECORD_SHA256 = (
    "e9c61283eb88cf956cf53f29697a3296dafe9195113684d7ad6144fb8661f9ed"
)
EXPECTED_ROUTE_PREDECESSOR_Q74_ROWS_SHA256 = (
    "9f3984d041510c48064c611a36d43423fe80c2eeeb2e08abe23a7ad077327ce1"
)
EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256 = (
    "3f40762d324339d3d377f5c311ad8cfe43b4511feef4a04b3e472794a0dfc7d3"
)
EXPECTED_ROUTE_PREDECESSOR_CUSTODY_SHA256 = (
    "258df717b7a66b3e215a8e2691351ab79055b73390787f603c432ccb458547a0"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "6fea7915627245dc6318107f929ba0efc1596d8ecbba039d9312bf82a20ea080"
)
EXPECTED_Q74_RETAINED_COUNT = 655_360
EXPECTED_Q74_RETAINED_EXPANSION_SHA256 = (
    "99fb342059ee6627a8b51b4230945237bdfdcaa7f65a20dab6898e8af0ed48eb"
)
EXPECTED_Q74_E_AFTER_TICKS = "2289190807152394"
BOUNDARY_INPUT_NAME = (
    "hubbard_l8_interval_checkpoints/double_occupancy_boundary_002.b85"
)
EXPECTED_BOUNDARY_INPUT_ROLE = "double_occupancy_encoded_input_boundary"
EXPECTED_BOUNDARY_INPUT_FILE_SIZE = 841_495
EXPECTED_BOUNDARY_INPUT_SHA256 = (
    "f92d5eadc01e1d9ebef86328b9eed92d867a2dd79b8bb2ba0baa821fe3b037ab"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_ROUTE_TRANSCRIPT_BYTES = 1_048_576
MAX_BOUNDARY_INPUT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

MODE = "double_occupancy"
BASE_PARENT_HORIZON = 74
EXTENDED_HORIZON = 76
K655360 = 655_360
EXPECTED_Q75_PREFIX_CAP_TICKS = "2289337503783615"
EXPECTED_Q76_PREFIX_CAP_TICKS = "2289420005773549"
EXPECTED_EXTENSION_CHECKPOINT_ANCHORS = {
    75: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 18,
        "gate_batch_sha256": (
            "d2bc2f79ddb0b0f03897e0e8705e4d2bcc63c7653b04988c17f54a4fbd95e70f"
        ),
    },
    76: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 19,
        "gate_batch_sha256": (
            "7ed21993d3a203f135c12b0b7f658c6a966c7aa62cd98f276559dce4213bfc63"
        ),
    },
}
EXPECTED_Q72_EXCLUDED_K638976_EVIDENCE = {
    "configured_K": 638_976,
    "minimum_effective_K_to_meet_prefix": 642_206,
    "shortfall": 3_230,
    "evidence_scope": "fixed_four_gate_q72_predecessor_state_prefix_only",
    "execution_candidate": False,
    "candidate_row_constructed": False,
    "exact_drop_ticks_asserted": False,
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


def exact_value_equal(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def bounded_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as handle:
        payload = handle.read(maximum + 1)
    if len(payload) > maximum:
        raise RuntimeError(f"byte cap exceeded: {path.name}")
    return payload


def checked_repo_file(repo: Path, relative_path: str) -> Path:
    if type(relative_path) is not str or not relative_path:
        raise RuntimeError("invalid relative path")
    repo = repo.resolve()
    unresolved = repo / relative_path
    path = unresolved.resolve()
    try:
        path.relative_to(repo)
    except ValueError as exc:
        raise RuntimeError(f"repository path escapes root: {relative_path}") from exc
    if not path.is_file() or unresolved.is_symlink():
        raise RuntimeError(f"unsafe repository file: {relative_path}")
    return path


def compile_isolated(name: str, path: Path, payload: bytes) -> Any:
    if type(payload) is not bytes:
        raise RuntimeError("isolated module payload must be exact bytes")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, str(path), "exec"), module.__dict__)
    return module


def require_exact_keys(value: Any, expected: Any, label: str) -> None:
    if type(value) is not dict or frozenset(value) != frozenset(expected):
        raise RuntimeError(f"{label} key drift")


def validate_local_configuration(parent: Any | None = None) -> None:
    if BASE_PARENT_HORIZON != 74 or EXTENDED_HORIZON != 76:
        raise RuntimeError("D q76 horizon contract drift")
    expected_caps = {
        "self": 131_072,
        "pinned": 262_144,
        "route": 1_048_576,
        "boundary": 1_048_576,
        "output": 4_194_304,
    }
    if {
        "self": MAX_SELF_SOURCE_BYTES,
        "pinned": MAX_PINNED_SOURCE_BYTES,
        "route": MAX_ROUTE_TRANSCRIPT_BYTES,
        "boundary": MAX_BOUNDARY_INPUT_BYTES,
        "output": MAX_OUTPUT_BYTES,
    } != expected_caps:
        raise RuntimeError("D q76 source/output cap drift")
    if EXPECTED_EXTENSION_CHECKPOINT_ANCHORS != {
        75: {
            "stage_index": 2,
            "stage_group": "HU",
            "batch_in_stage": 18,
            "gate_batch_sha256": (
                "d2bc2f79ddb0b0f03897e0e8705e4d2bcc63c7653b04988c17f54a4fbd95e70f"
            ),
        },
        76: {
            "stage_index": 2,
            "stage_group": "HU",
            "batch_in_stage": 19,
            "gate_batch_sha256": (
                "7ed21993d3a203f135c12b0b7f658c6a966c7aa62cd98f276559dce4213bfc63"
            ),
        },
    }:
        raise RuntimeError("D q76 checkpoint anchor drift")
    E_input = 2_283_149_854_538_588
    maximum = (1 << 64) // 4000
    denominator = 98 * 288
    if str(E_input + 75 * (maximum - E_input) // denominator) != (
        EXPECTED_Q75_PREFIX_CAP_TICKS
    ):
        raise RuntimeError("D q75 prefix cap derivation drift")
    if str(E_input + 76 * (maximum - E_input) // denominator) != (
        EXPECTED_Q76_PREFIX_CAP_TICKS
    ):
        raise RuntimeError("D q76 prefix cap derivation drift")
    if parent is not None:
        if (
            parent.EXTENDED_HORIZON != BASE_PARENT_HORIZON
            or tuple(parent.D_CANDIDATES)[-1] != K655360
            or len(parent.D_CANDIDATES) != 37
            or 638_976 in parent.D_CANDIDATES
        ):
            raise RuntimeError("D q76 immediate-parent contract drift")
        schema_sizes = {
            "raw": len(parent.EXPECTED_PARENT_RESULT_KEYS),
            "final": len(parent.EXPECTED_RELABELLED_RESULT_KEYS),
            "success": len(parent.SUCCESS_RECORD_KEYS),
            "failure": len(parent.FAILURE_RECORD_KEYS),
            "row": len(parent.CANDIDATE_RECORD_KEYS),
            "abort": len(parent.RESOURCE_POLICY_ABORT_KEYS),
        }
        if schema_sizes != {
            "raw": 67,
            "final": 96,
            "success": 38,
            "failure": 32,
            "row": 7,
            "abort": 50,
        }:
            raise RuntimeError("D q76 inherited schema cardinality drift")


def load_execution_parent(repo: Path) -> Any:
    path = checked_repo_file(repo, EXECUTION_PARENT_NAME)
    payload = bounded_bytes(path, MAX_PINNED_SOURCE_BYTES)
    if len(payload) != EXPECTED_EXECUTION_PARENT_FILE_SIZE:
        raise RuntimeError("D q74 execution-parent source size drift")
    if sha256(payload) != EXPECTED_EXECUTION_PARENT_SHA256:
        raise RuntimeError("D q74 execution-parent source pin drift")
    parent = compile_isolated(
        "pinned_d_k655360_c37_q74_parent_for_q76",
        path,
        payload,
    )
    validate_local_configuration(parent)
    if (
        type(getattr(parent, "_run_verified", None)) is not types.FunctionType
        or parent._run_verified.__globals__ is not parent.__dict__
        or parent._run_verified.__code__.co_filename != parent.__file__
    ):
        raise RuntimeError("D q76 immediate-parent private entrypoint drift")
    return parent


def _derived_q75_q76_abort_builder(parent: Any) -> Any:
    """Derive the q75/q76 builder by a closed constant-only code transform."""

    original = parent.build_resource_abort_parent_result
    constants = list(original.__code__.co_consts)
    if constants.count((73, 74)) != 1:
        raise RuntimeError("D q76 abort-builder checkpoint tuple drift")
    constants[constants.index((73, 74))] = (75, 76)
    transformed = []
    for value in constants:
        if type(value) is str:
            value = value.replace("q73/q74", "q75/q76")
            value = value.replace("D q74", "D q76")
            value = value.replace(
                "D_k655360_c37_l1048576_d1048576_q74_policy_resource_abort_v1",
                "D_k655360_c37_l1048576_d1048576_q76_policy_resource_abort_v1",
            )
        transformed.append(value)
    if (
        "D_k655360_c37_l1048576_d1048576_q76_policy_resource_abort_v1"
        not in transformed
    ):
        raise RuntimeError("D q76 abort-builder id transform drift")
    derived_globals = dict(parent.__dict__)
    derived_globals.update({
        "EXTENDED_HORIZON": EXTENDED_HORIZON,
        "EXPECTED_EXTENSION_CHECKPOINT_ANCHORS": (
            EXPECTED_EXTENSION_CHECKPOINT_ANCHORS
        ),
    })
    code = original.__code__.replace(co_consts=tuple(transformed))
    return types.FunctionType(
        code,
        derived_globals,
        "build_q75_q76_resource_abort_parent_result",
    )


def _abort_checkpoint(parent: Any, control_parent: Any, exception: Any) -> int:
    expected_run = parent._require_abort_parent_authority(control_parent)
    run_items = [
        item
        for item in parent._traceback_items(exception)
        if item.tb_frame.f_code is expected_run.__code__
    ]
    if len(run_items) != 1:
        raise RuntimeError("D q76 abort dispatcher parent-frame drift")
    checkpoint = run_items[0].tb_frame.f_locals.get("checkpoint_number")
    if type(checkpoint) is not int:
        raise RuntimeError("D q76 abort dispatcher checkpoint drift")
    return checkpoint


def execute_parent_replay(parent: Any, repo: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Call the q74 private parent with six closed, temporary patches."""

    if type(parent) is not types.ModuleType:
        raise RuntimeError("D q76 execution parent is not isolated")
    validate_local_configuration(parent)
    names = (
        "EXTENDED_HORIZON",
        "validate_local_configuration",
        "execute_parent_replay",
        "load_route_reference",
        "validate_and_relabel",
        "build_resource_abort_parent_result",
    )
    originals = {name: getattr(parent, name) for name in names}
    context: Dict[str, Any] = {
        "execution_parent_private_entrypoint_called": False,
        "q74_replay_completed_before_reference": False,
        "q74_canonical_loaded_before_replay": False,
        "q74_route_loader_suppressed": False,
        "q74_relabel_suppressed": False,
        "q75_q76_abort_adapter_installed": False,
        "q72_inner_eight_attributes_restored": False,
    }
    derived_builder = _derived_q75_q76_abort_builder(parent)

    def capture_replay(q72_parent, source_repo):
        inner_names = (
            "EXTENDED_HORIZON",
            "validate_local_configuration",
            "load_configured_v6_baseline",
            "load_kernel_wrapper",
            "load_route_reference",
            "configure_parent_execution",
            "execute_parent_fail_closed",
            "validate_and_relabel",
        )
        inner_originals = {
            name: getattr(q72_parent, name) for name in inner_names
        }
        context["q72_parent"] = q72_parent
        try:
            result, replay_context = originals["execute_parent_replay"](
                q72_parent,
                source_repo,
            )
        finally:
            restored = all(
                getattr(q72_parent, name) is value
                for name, value in inner_originals.items()
            )
            context["q72_inner_eight_attributes_restored"] = restored
            if not restored:
                raise RuntimeError("D q76 q72 inner adapter restoration drift")
        context["q74_replay_context"] = replay_context
        context["q74_replay_completed_before_reference"] = True
        return result, replay_context

    def no_q74_reference(_source_repo):
        if context["q74_replay_completed_before_reference"] is not True:
            raise RuntimeError("D q76 q74 reference suppression order drift")
        context["q74_route_loader_suppressed"] = True
        context["q74_canonical_loaded_before_replay"] = False
        return {}, {}

    def return_raw(result, _predecessor, _reference, q72_parent, inner):
        if context["q74_route_loader_suppressed"] is not True:
            raise RuntimeError("D q76 q74 relabel preceded loader suppression")
        if q72_parent is not context.get("q72_parent"):
            raise RuntimeError("D q76 q72 parent identity drift")
        if inner is not context.get("q74_replay_context"):
            raise RuntimeError("D q76 q74 replay context identity drift")
        context["q74_relabel_suppressed"] = True
        return result

    def dispatch_abort(execution_parent, control_parent, kernel, exception):
        checkpoint = _abort_checkpoint(parent, control_parent, exception)
        if checkpoint in (73, 74):
            return originals["build_resource_abort_parent_result"](
                execution_parent,
                control_parent,
                kernel,
                exception,
            )
        if checkpoint in (75, 76):
            return derived_builder(
                execution_parent,
                control_parent,
                kernel,
                exception,
            )
        raise RuntimeError("D q76 resource abort outside q73-q76")

    failure = None
    result = None
    try:
        parent.EXTENDED_HORIZON = EXTENDED_HORIZON
        parent.validate_local_configuration = lambda: None
        parent.execute_parent_replay = capture_replay
        parent.load_route_reference = no_q74_reference
        parent.validate_and_relabel = return_raw
        parent.build_resource_abort_parent_result = dispatch_abort
        context["q75_q76_abort_adapter_installed"] = True
        context["execution_parent_private_entrypoint_called"] = True
        result = parent._run_verified(repo.resolve())
    except BaseException as exception:
        failure = exception
    finally:
        for name, value in originals.items():
            setattr(parent, name, value)
        if not all(getattr(parent, name) is value for name, value in originals.items()):
            raise RuntimeError("D q76 outer six-attribute restoration drift")
    if failure is not None:
        raise failure
    if type(result) is not dict:
        raise RuntimeError("D q76 immediate parent returned non-dict")
    required = {
        "q74_replay_context",
        "q72_parent",
        "q74_replay_completed_before_reference",
        "q74_route_loader_suppressed",
        "q74_relabel_suppressed",
        "q75_q76_abort_adapter_installed",
        "q72_inner_eight_attributes_restored",
    }
    if not required <= context.keys() or not all(
        context[key] is True
        for key in (
            "q74_replay_completed_before_reference",
            "q74_route_loader_suppressed",
            "q74_relabel_suppressed",
            "q75_q76_abort_adapter_installed",
            "q72_inner_eight_attributes_restored",
        )
    ):
        raise RuntimeError("D q76 parent adapter evidence did not close")
    inner = context["q74_replay_context"]
    if (
        inner.get("execution_parent_route_loader_suppressed") is not True
        or inner.get("execution_parent_abort_adapter_installed") is not True
    ):
        raise RuntimeError("D q76 q72 loader/relabel suppression drift")
    return result, context


def load_route_reference(repo: Path, parent: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    parent_raw = bounded_bytes(
        checked_repo_file(repo, EXECUTION_PARENT_NAME),
        MAX_PINNED_SOURCE_BYTES,
    )
    if (
        len(parent_raw) != EXPECTED_EXECUTION_PARENT_FILE_SIZE
        or sha256(parent_raw) != EXPECTED_EXECUTION_PARENT_SHA256
    ):
        raise RuntimeError("D q76 post-only parent source drift")
    raw = bounded_bytes(
        checked_repo_file(repo, ROUTE_PREDECESSOR_TRANSCRIPT_NAME),
        MAX_ROUTE_TRANSCRIPT_BYTES,
    )
    if len(raw) != EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE:
        raise RuntimeError("D q74 canonical file-size drift")
    if sha256(raw) != EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256:
        raise RuntimeError("D q74 canonical file pin drift")
    try:
        transcript = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("D q74 canonical is invalid JSON") from exc
    if type(transcript) is not dict or raw != canonical_bytes(transcript):
        raise RuntimeError("D q74 transcript is not canonical JSON")
    require_exact_keys(
        transcript,
        parent.EXPECTED_RELABELLED_RESULT_KEYS,
        "D q74 canonical",
    )
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k655360_c37_l1048576_d1048576_q74_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
        "screen_horizon_checkpoint_count": BASE_PARENT_HORIZON,
        "attempted_checkpoint_count": BASE_PARENT_HORIZON,
        "completed_checkpoint_count": BASE_PARENT_HORIZON,
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "resource_policy_abort": None,
        "resource_policy_abort_sha256": None,
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": True,
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        "screen_execution_components_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256
        ),
        "checkpoint_transform_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256
        ),
        "positive_artifact_generated": False,
        "child_boundary_committed": False,
    }
    for field, value in expected.items():
        if not exact_value_equal(transcript.get(field), value):
            raise RuntimeError(f"D q74 canonical drift: {field}")
    for value_field, digest_field in (
        ("records", "records_sha256"),
        ("selected_K_history", "selected_K_history_sha256"),
        ("screen_execution_components", "screen_execution_components_sha256"),
        ("configuration_reference", "configuration_reference_sha256"),
        ("configuration_override", "configuration_override_sha256"),
        ("kernel_capability_override", "kernel_capability_override_sha256"),
        ("parent_horizon_override", "parent_horizon_override_sha256"),
        ("route_predecessor_reference", "route_predecessor_reference_sha256"),
        ("predecessor_handoff_validation", "predecessor_handoff_validation_sha256"),
        ("checkpoint_transform", "checkpoint_transform_sha256"),
    ):
        if sha256(canonical_bytes(transcript[value_field])) != transcript[digest_field]:
            raise RuntimeError(f"D q74 nested digest drift: {value_field}")
    records = transcript.get("records")
    history = transcript.get("selected_K_history")
    if type(records) is not list or len(records) != 74:
        raise RuntimeError("D q74 record count drift")
    if type(history) is not list or len(history) != 74:
        raise RuntimeError("D q74 history count drift")
    if sha256(canonical_bytes(records)) != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256:
        raise RuntimeError("D q74 records digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256:
        raise RuntimeError("D q74 history digest drift")
    rows = [row for record in records for row in record["candidate_records"]]
    if len(rows) != 74 * 37 or sha256(canonical_bytes(rows)) != (
        EXPECTED_ROUTE_PREDECESSOR_ROWS_SHA256
    ):
        raise RuntimeError("D q74 all-row closure drift")
    q74 = records[-1]
    if sha256(canonical_bytes(q74)) != EXPECTED_ROUTE_PREDECESSOR_Q74_RECORD_SHA256:
        raise RuntimeError("D q74 terminal record drift")
    if sha256(canonical_bytes(q74["candidate_records"])) != (
        EXPECTED_ROUTE_PREDECESSOR_Q74_ROWS_SHA256
    ):
        raise RuntimeError("D q74 terminal rows drift")
    anchors = {
        "checkpoint_number_one_based": 74,
        "selected_K": K655360,
        "retained_expansion_count": EXPECTED_Q74_RETAINED_COUNT,
        "retained_expansion_sha256": EXPECTED_Q74_RETAINED_EXPANSION_SHA256,
        "E_after_ticks": EXPECTED_Q74_E_AFTER_TICKS,
    }
    for field, value in anchors.items():
        if not exact_value_equal(q74.get(field), value):
            raise RuntimeError(f"D q74 terminal anchor drift: {field}")
    evidence = transcript["configuration_override"][
        "execution_parent_configuration_override"
    ]["excluded_candidate_threshold_evidence"]
    if not exact_value_equal(evidence, EXPECTED_Q72_EXCLUDED_K638976_EVIDENCE):
        raise RuntimeError("D q74 historical K638976 evidence drift")
    components = transcript["screen_execution_components"]
    custody = transcript["source_custody"]
    if (
        len(components) != 11
        or len(custody) != 10
        or sha256(canonical_bytes(components))
        != EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256
        or sha256(canonical_bytes(custody))
        != EXPECTED_ROUTE_PREDECESSOR_CUSTODY_SHA256
    ):
        raise RuntimeError("D q74 source closure drift")
    expected_boundary_component = {
        "relative_path": BOUNDARY_INPUT_NAME,
        "role": EXPECTED_BOUNDARY_INPUT_ROLE,
        "sha256": EXPECTED_BOUNDARY_INPUT_SHA256,
    }
    boundary_components = [
        component for component in components
        if component.get("relative_path") == BOUNDARY_INPUT_NAME
        or component.get("role") == EXPECTED_BOUNDARY_INPUT_ROLE
    ]
    if not exact_value_equal(
        boundary_components,
        [expected_boundary_component],
    ):
        raise RuntimeError("D q74 encoded boundary component drift")
    for component in components:
        is_boundary = component["relative_path"] == BOUNDARY_INPUT_NAME
        component_cap = (
            MAX_BOUNDARY_INPUT_BYTES
            if is_boundary
            else MAX_PINNED_SOURCE_BYTES
        )
        payload = bounded_bytes(
            checked_repo_file(repo, component["relative_path"]),
            component_cap,
        )
        if is_boundary and len(payload) != EXPECTED_BOUNDARY_INPUT_FILE_SIZE:
            raise RuntimeError("D q74 encoded boundary size drift")
        if sha256(payload) != component["sha256"]:
            raise RuntimeError("D q74 component source drift")
    for relative_path, expected_sha in custody.items():
        payload = bounded_bytes(
            checked_repo_file(repo, relative_path),
            MAX_PINNED_SOURCE_BYTES,
        )
        if sha256(payload) != expected_sha:
            raise RuntimeError("D q74 custody source drift")
    reference = {
        "route_id": (
            "double_occupancy_k655360_c37_l1048576_d1048576_"
            "q74_to_q76_v1"
        ),
        "execution_parent_screen": {
            "relative_path": EXECUTION_PARENT_NAME,
            "source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
            "source_size_bytes": EXPECTED_EXECUTION_PARENT_FILE_SIZE,
            "compiled": True,
            "executed": True,
            "private_entrypoint_called": True,
            "execution_source_layer": True,
        },
        "canonical_transcript": {
            "relative_path": ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
            "file_size_bytes": EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE,
            "file_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
            "records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
            "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
            "q74_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q74_RECORD_SHA256,
            "q74_candidate_rows_sha256": EXPECTED_ROUTE_PREDECESSOR_Q74_ROWS_SHA256,
            "compiled": False,
            "executed": False,
            "loaded_before_replay": False,
            "loaded_after_full_replay_as_exact_reference": True,
            "used_only_for_post_replay_q1_q74_prefix_validation": True,
            "propagation_input": False,
            "checkpoint_74_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
        },
        "incremental_semantic_delta": {
            "candidate_K_values_changed": False,
            "policy_caps_changed": False,
            "kernel_capability_limits_changed": False,
            "horizon_checkpoint_count": {"before": 74, "after": 76},
        },
        "q72_excluded_K638976_evidence": copy.deepcopy(evidence),
        "q75_q76_K638976_threshold_or_drop_asserted": False,
    }
    return transcript, reference


def _mapped_validator(parent: Any, name: str) -> Any:
    globals_copy = dict(parent.__dict__)
    globals_copy.update({
        "EXPECTED_Q73_PREFIX_CAP_TICKS": EXPECTED_Q75_PREFIX_CAP_TICKS,
        "EXPECTED_Q74_PREFIX_CAP_TICKS": EXPECTED_Q76_PREFIX_CAP_TICKS,
        "EXPECTED_EXTENSION_CHECKPOINT_ANCHORS": {
            73: EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[75],
            74: EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[76],
        },
    })
    original = getattr(parent, name)
    return types.FunctionType(original.__code__, globals_copy, name)


def _map_checkpoint_fields(value: Dict[str, Any], checkpoint: int) -> Dict[str, Any]:
    mapped = checkpoint - 2
    output = copy.deepcopy(value)
    output["checkpoint_index_zero_based"] = mapped - 1
    output["checkpoint_number_one_based"] = mapped
    output["gate_occurrence_first_zero_based"] = 4 * (mapped - 1)
    output["gate_occurrence_last_zero_based"] = 4 * mapped - 1
    return output


def validate_extended_record(
    parent: Any,
    record: Dict[str, Any],
    previous: Dict[str, Any],
    checkpoint: int,
) -> int | None:
    if checkpoint not in (75, 76) or type(record) is not dict:
        raise RuntimeError("D q76 extended record checkpoint drift")
    expected = {
        "checkpoint_index_zero_based": checkpoint - 1,
        "checkpoint_number_one_based": checkpoint,
        "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
        "gate_occurrence_last_zero_based": 4 * checkpoint - 1,
        "budget_prefix_cap_ticks": (
            EXPECTED_Q75_PREFIX_CAP_TICKS
            if checkpoint == 75
            else EXPECTED_Q76_PREFIX_CAP_TICKS
        ),
        **EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint],
    }
    for field, value in expected.items():
        if not exact_value_equal(record.get(field), value):
            raise RuntimeError(f"D q{checkpoint} exact anchor drift: {field}")
    mapped = _map_checkpoint_fields(record, checkpoint)
    validator = _mapped_validator(parent, "validate_extended_record")
    return validator(mapped, previous, checkpoint - 2)


def validate_resource_policy_abort(
    parent: Any,
    result: Dict[str, Any],
    previous: Dict[str, Any],
    checkpoint: int,
) -> Dict[str, Any] | None:
    abort = result.get("resource_policy_abort")
    abort_sha = result.get("resource_policy_abort_sha256")
    if abort is None:
        if abort_sha is not None:
            raise RuntimeError("D q76 null resource abort has digest")
        return None
    if checkpoint not in (75, 76):
        raise RuntimeError("D q76 resource abort checkpoint drift")
    require_exact_keys(abort, parent.RESOURCE_POLICY_ABORT_KEYS, "D q76 abort")
    if sha256(canonical_bytes(abort)) != abort_sha:
        raise RuntimeError("D q76 resource abort digest drift")
    expected = {
        "abort_id": (
            "D_k655360_c37_l1048576_d1048576_q76_policy_resource_abort_v1"
        ),
        "checkpoint_index_zero_based": checkpoint - 1,
        "checkpoint_number_one_based": checkpoint,
        "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
        "gate_occurrence_last_zero_based": 4 * checkpoint - 1,
        **EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint],
    }
    for field, value in expected.items():
        if not exact_value_equal(abort.get(field), value):
            raise RuntimeError(f"D q{checkpoint} abort anchor drift: {field}")
    mapped_result = copy.deepcopy(result)
    mapped_abort = _map_checkpoint_fields(abort, checkpoint)
    mapped_abort["abort_id"] = (
        "D_k655360_c37_l1048576_d1048576_q74_policy_resource_abort_v1"
    )
    mapped_result["resource_policy_abort"] = mapped_abort
    mapped_result["resource_policy_abort_sha256"] = sha256(
        canonical_bytes(mapped_abort)
    )
    validator = _mapped_validator(parent, "validate_resource_policy_abort")
    observed = validator(mapped_result, previous, checkpoint - 2)
    if observed is None:
        raise RuntimeError("D q76 mapped abort unexpectedly vanished")
    return abort


def validate_replay_handoff(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
    parent: Any,
) -> Dict[str, Any]:
    require_exact_keys(
        result,
        parent.EXPECTED_PARENT_RESULT_KEYS,
        "D q76 raw parent result",
    )
    if result.get("status") != "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS":
        raise RuntimeError("D q76 raw status drift")
    if result.get("screen_horizon_checkpoint_count") != EXTENDED_HORIZON:
        raise RuntimeError("D q76 raw horizon drift")
    if (
        result.get("candidate_K_values") != list(parent.D_CANDIDATES)
        or result.get("kernel_capability_limits")
        != parent.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        or result.get("proposed_policy_caps")
        != {**parent.POLICY_CAPS_BASE, "max_candidate_count": 37}
    ):
        raise RuntimeError("D q76 same-cap policy drift")
    dynamic = {
        "transcript_fingerprint", "screen_terminal_condition",
        "screen_source_sha256", "control_flow_owned_by_screen",
        "screen_execution_components", "screen_execution_components_sha256",
        "configuration_reference", "configuration_reference_sha256",
        "checkpoint_transform", "checkpoint_transform_sha256", "source_custody",
        "screen_horizon_checkpoint_count", "horizon_checkpoint_attempted",
        "horizon_reached_with_committed_checkpoint", "attempted_checkpoint_count",
        "completed_checkpoint_count", "failure_checkpoint_included",
        "selected_K_history", "selected_K_history_sha256", "records",
        "records_sha256", "failure_record_sha256",
        "last_committed_cumulative_drop_ticks",
        "observed_peak_single_expansion_terms",
        "observed_term_gate_visits_including_terminal_attempt",
        "observed_maximum_expansion_coefficient_tick_bits",
        "observed_maximum_product_bits",
        "observed_rounding_cumulative_scaled_ticks_squared",
        "resource_policy_abort", "resource_policy_abort_sha256",
    }
    for field in parent.EXPECTED_PARENT_RESULT_KEYS - dynamic:
        if not exact_value_equal(result.get(field), predecessor.get(field)):
            raise RuntimeError(f"D q76 invariant top-level drift: {field}")
    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or len(records) not in (74, 75, 76):
        raise RuntimeError("D q76 record count drift")
    if type(history) is not list or len(history) not in (74, 75, 76):
        raise RuntimeError("D q76 history count drift")
    old_records = predecessor["records"]
    old_history = predecessor["selected_K_history"]
    if not exact_value_equal(records[:74], old_records):
        raise RuntimeError("D q76 changed exact q1-q74 records")
    if not exact_value_equal(history[:74], old_history):
        raise RuntimeError("D q76 changed exact q1-q74 history")
    if sha256(canonical_bytes(records[:74])) != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256:
        raise RuntimeError("D q76 q1-q74 records digest drift")
    if sha256(canonical_bytes(history[:74])) != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256:
        raise RuntimeError("D q76 q1-q74 history digest drift")
    prefix_rows = [row for record in records[:74] for row in record["candidate_records"]]
    if (
        len(prefix_rows) != 74 * 37
        or sha256(canonical_bytes(prefix_rows))
        != EXPECTED_ROUTE_PREDECESSOR_ROWS_SHA256
    ):
        raise RuntimeError("D q76 q1-q74 row prefix drift")
    q74 = records[73]
    if (
        sha256(canonical_bytes(q74))
        != EXPECTED_ROUTE_PREDECESSOR_Q74_RECORD_SHA256
        or q74.get("retained_expansion_count") != EXPECTED_Q74_RETAINED_COUNT
        or q74.get("retained_expansion_sha256")
        != EXPECTED_Q74_RETAINED_EXPANSION_SHA256
        or q74.get("E_after_ticks") != EXPECTED_Q74_E_AFTER_TICKS
    ):
        raise RuntimeError("D q76 q74 terminal anchor drift")

    extension_history = []
    abort = None
    if len(records) == 74:
        abort = validate_resource_policy_abort(parent, result, q74, 75)
        if abort is None or len(history) != 74:
            raise RuntimeError("D q75 abort ledger drift")
        branch = "Q75_RESOURCE_ABORT_Q76_NOT_ATTEMPTED"
        expected_summary = {
            "attempted_checkpoint_count": 75,
            "completed_checkpoint_count": 74,
            "horizon_checkpoint_attempted": False,
            "horizon_reached_with_committed_checkpoint": False,
            "screen_terminal_condition": "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
            "failure_checkpoint_included": False,
            "last_committed_cumulative_drop_ticks": EXPECTED_Q74_E_AFTER_TICKS,
        }
    else:
        q75 = records[74]
        selected_q75 = validate_extended_record(parent, q75, q74, 75)
        if selected_q75 is None:
            if len(records) != 75 or len(history) != 74:
                raise RuntimeError("D q75 failure ledger drift")
            if validate_resource_policy_abort(parent, result, q74, 75) is not None:
                raise RuntimeError("D q75 failure carried abort")
            branch = "Q75_FAILURE_Q76_NOT_ATTEMPTED"
            expected_summary = {
                "attempted_checkpoint_count": 75,
                "completed_checkpoint_count": 74,
                "horizon_checkpoint_attempted": False,
                "horizon_reached_with_committed_checkpoint": False,
                "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                "failure_checkpoint_included": True,
                "last_committed_cumulative_drop_ticks": EXPECTED_Q74_E_AFTER_TICKS,
            }
        else:
            extension_history.append(selected_q75)
            if len(records) == 75:
                abort = validate_resource_policy_abort(parent, result, q75, 76)
                if abort is None or len(history) != 75:
                    raise RuntimeError("D q76 abort ledger drift")
                branch = "Q75_SUCCESS_Q76_RESOURCE_ABORT"
                expected_summary = {
                    "attempted_checkpoint_count": 76,
                    "completed_checkpoint_count": 75,
                    "horizon_checkpoint_attempted": True,
                    "horizon_reached_with_committed_checkpoint": False,
                    "screen_terminal_condition": "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
                    "failure_checkpoint_included": False,
                    "last_committed_cumulative_drop_ticks": q75["E_after_ticks"],
                }
            else:
                if validate_resource_policy_abort(parent, result, q75, 76) is not None:
                    raise RuntimeError("D q76 record carried abort")
                q76 = records[75]
                selected_q76 = validate_extended_record(parent, q76, q75, 76)
                if selected_q76 is None:
                    if len(history) != 75:
                        raise RuntimeError("D q76 failure history drift")
                    branch = "Q75_SUCCESS_Q76_FAILURE"
                    expected_summary = {
                        "attempted_checkpoint_count": 76,
                        "completed_checkpoint_count": 75,
                        "horizon_checkpoint_attempted": True,
                        "horizon_reached_with_committed_checkpoint": False,
                        "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                        "failure_checkpoint_included": True,
                        "last_committed_cumulative_drop_ticks": q75["E_after_ticks"],
                    }
                else:
                    extension_history.append(selected_q76)
                    if len(history) != 76:
                        raise RuntimeError("D q76 success history drift")
                    branch = "Q75_AND_Q76_SUCCESS_HORIZON_REACHED"
                    expected_summary = {
                        "attempted_checkpoint_count": 76,
                        "completed_checkpoint_count": 76,
                        "horizon_checkpoint_attempted": True,
                        "horizon_reached_with_committed_checkpoint": True,
                        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
                        "failure_checkpoint_included": False,
                        "last_committed_cumulative_drop_ticks": q76["E_after_ticks"],
                    }
    if history != list(old_history) + extension_history:
        raise RuntimeError("D q76 selected history is not exact replay ledger")
    for field, value in expected_summary.items():
        if not exact_value_equal(result.get(field), value):
            raise RuntimeError(f"D q76 terminal summary drift: {field}")
    final = records[-1]
    failed = abort is None and final["status"] == (
        "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
    )
    expected_failure_sha = sha256(canonical_bytes(final)) if failed else None
    if result.get("failure_record_sha256") != expected_failure_sha:
        raise RuntimeError("D q76 failure digest drift")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("D q76 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(canonical_bytes(history)):
        raise RuntimeError("D q76 history digest drift")
    resource = abort if abort is not None else final
    resources = {
        "observed_peak_single_expansion_terms": resource["peak_live_terms_cumulative"],
        "observed_term_gate_visits_including_terminal_attempt": resource[
            "term_gate_visits_cumulative"
        ],
        "observed_maximum_expansion_coefficient_tick_bits": resource[
            "maximum_expansion_coefficient_tick_bits"
        ],
        "observed_maximum_product_bits": resource["maximum_product_bits"],
        "observed_rounding_cumulative_scaled_ticks_squared": resource[
            "rounding_cumulative_scaled_ticks_squared"
        ],
    }
    for field, value in resources.items():
        if not exact_value_equal(result.get(field), value):
            raise RuntimeError(f"D q76 observed resource drift: {field}")
    expected_rows = {74: 2738, 75: 2775, 76: 2812}[len(records)]
    actual_rows = sum(len(record["candidate_records"]) for record in records)
    if actual_rows != expected_rows:
        raise RuntimeError("D q76 terminal row count drift")
    return {
        "validation_id": "D_k655360_c37_l1048576_d1048576_q76_same_cap_handoff_v1",
        "q1_through_q74_records_exact": True,
        "q1_through_q74_all_37_candidate_rows_exact": True,
        "q1_through_q74_selected_history_exact": True,
        "q74_records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        "q74_selected_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        "q74_terminal_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q74_RECORD_SHA256,
        "q74_terminal_candidate_rows_sha256": EXPECTED_ROUTE_PREDECESSOR_Q74_ROWS_SHA256,
        "q72_excluded_K638976_evidence_historical_only": True,
        "q75_q76_K638976_threshold_or_drop_asserted": False,
        "q75_input_retained_count": EXPECTED_Q74_RETAINED_COUNT,
        "q75_input_retained_sha256": EXPECTED_Q74_RETAINED_EXPANSION_SHA256,
        "q75_input_E_before_ticks": EXPECTED_Q74_E_AFTER_TICKS,
        "q75_prefix_cap_ticks": EXPECTED_Q75_PREFIX_CAP_TICKS,
        "q76_prefix_cap_ticks_if_attempted": EXPECTED_Q76_PREFIX_CAP_TICKS,
        "legal_terminal_branches": [
            "Q75_FAILURE_Q76_NOT_ATTEMPTED",
            "Q75_RESOURCE_ABORT_Q76_NOT_ATTEMPTED",
            "Q75_SUCCESS_Q76_FAILURE",
            "Q75_SUCCESS_Q76_RESOURCE_ABORT",
            "Q75_AND_Q76_SUCCESS_HORIZON_REACHED",
        ],
        "terminal_branch": branch,
        "resource_policy_abort_structured": abort is not None,
        "resource_policy_abort_checkpoint": (
            abort["checkpoint_number_one_based"] if abort is not None else None
        ),
        "resource_policy_abort_kind": (
            abort["abort_kind"] if abort is not None else None
        ),
        "resource_policy_abort_sha256": result["resource_policy_abort_sha256"],
        "q76_checkpoint_record_constructed": len(records) == 76,
        "q75_and_q76_outcomes_precommitted": False,
    }


def _flatten_components(
    predecessor: Mapping[str, Any],
    self_sha: str,
) -> list[Dict[str, Any]]:
    old = predecessor["screen_execution_components"]
    paths = [item["relative_path"] for item in old]
    if (
        len(old) != 11
        or paths[:2] != [EXECUTION_PARENT_NAME, NESTED_Q72_PARENT_NAME]
    ):
        raise RuntimeError("D q76 predecessor component topology drift")
    immediate = dict(old[0])
    immediate["role"] = (
        "D_k655360_c37_l1048576_d1048576_q74_same_byte_private_execution_parent"
    )
    components = [
        {
            "relative_path": SELF_NAME,
            "role": "D_k655360_c37_l1048576_d1048576_q76_fresh_same_byte_screen",
            "sha256": self_sha,
        },
        immediate,
        *[copy.deepcopy(item) for item in old[2:]],
    ]
    final_paths = [item["relative_path"] for item in components]
    if (
        len(components) != 11
        or len(final_paths) != len(set(final_paths))
        or NESTED_Q72_PARENT_NAME in final_paths
        or ROUTE_PREDECESSOR_TRANSCRIPT_NAME in final_paths
    ):
        raise RuntimeError("D q76 flattened component closure drift")
    return components


def _flatten_custody(
    predecessor: Mapping[str, Any],
    self_sha: str,
) -> Dict[str, str]:
    old = predecessor["source_custody"]
    if len(old) != 10 or old.get(EXECUTION_PARENT_NAME) != (
        EXPECTED_EXECUTION_PARENT_SHA256
    ):
        raise RuntimeError("D q76 predecessor custody topology drift")
    custody = {
        SELF_NAME: self_sha,
        **{
            path: digest
            for path, digest in old.items()
            if path != NESTED_Q72_PARENT_NAME
        },
    }
    if (
        len(custody) != 10
        or NESTED_Q72_PARENT_NAME in custody
        or ROUTE_PREDECESSOR_TRANSCRIPT_NAME in custody
    ):
        raise RuntimeError("D q76 flattened custody closure drift")
    return custody


def validate_and_relabel(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
    route_reference: Mapping[str, Any],
    parent: Any,
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("D q76 relabel requires same-byte self execution")
    handoff = validate_replay_handoff(result, predecessor, parent)
    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = _flatten_components(predecessor, self_sha)
    custody = _flatten_custody(predecessor, self_sha)
    configuration_reference = copy.deepcopy(predecessor["configuration_reference"])
    parent_config = copy.deepcopy(predecessor["configuration_override"])
    config = {
        "override_id": (
            "double_occupancy_k655360_c37_l1048576_d1048576_q76_"
            "configuration_override_v1"
        ),
        "execution_parent_configuration_override": parent_config,
        "execution_parent_configuration_override_sha256": sha256(
            canonical_bytes(parent_config)
        ),
        "incremental_route_override_from_k655360_c37_l1048576_d1048576_q74": {
            "candidate_K_values_sha256": parent.EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 37, "after": 37},
            "candidate_ladder_added": [],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {},
            "predecessor_configuration_override_sha256": predecessor[
                "configuration_override_sha256"
            ],
        },
        "effective_candidate_K_values": list(parent.D_CANDIDATES),
        "effective_policy_caps": {
            **parent.POLICY_CAPS_BASE,
            "max_candidate_count": 37,
        },
        "candidate_policy_and_kernel_capability_unchanged_on_route": True,
        "overridden_fields_on_incremental_route": [
            "screen_horizon_checkpoint_count"
        ],
    }
    parent_capability = copy.deepcopy(predecessor["kernel_capability_override"])
    capability = {
        "relative_path": parent.KERNEL_WRAPPER_NAME,
        "source_sha256": parent.EXPECTED_KERNEL_WRAPPER_SHA256,
        "role": "unchanged_k655360_c37_capability_override_provider",
        "execution_parent_kernel_capability_override": parent_capability,
        "execution_parent_kernel_capability_override_sha256": sha256(
            canonical_bytes(parent_capability)
        ),
        "effective_kernel_capability_limits": (
            parent.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        ),
        "incremental_route_changes_from_k655360_c37_l1048576_d1048576_q74": {},
        "execution_source_layers": [
            parent.KERNEL_WRAPPER_NAME,
            parent.V2_ARITHMETIC_NAME,
        ],
        "q74_canonical_is_execution_source": False,
        "v2_arithmetic_module_mutated_by_screen": False,
    }
    raw_horizon = context["q74_replay_context"].get(
        "raw_control_flow_horizon_override"
    )
    if (
        type(raw_horizon) is not dict
        or raw_horizon.get("changed_fields") != [
            "MODE_CONFIG.double_occupancy.horizon_checkpoint_count"
        ]
        or raw_horizon.get("semantic_delta", {}).get(
            "MODE_CONFIG.double_occupancy.horizon_checkpoint_count"
        ) != {"before": 66, "after": 76}
    ):
        raise RuntimeError("D q76 raw horizon evidence drift")
    horizon = {
        "override_id": "double_occupancy_q74_parent_to_q76_horizon_override_v1",
        "parent_relative_path": EXECUTION_PARENT_NAME,
        "parent_source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
        "parent_module_isolated": True,
        "parent_source_bytes_changed": False,
        "changed_fields": ["screen_horizon_checkpoint_count"],
        "semantic_delta": {
            "screen_horizon_checkpoint_count": {"before": 74, "after": 76}
        },
        "nested_raw_control_flow_horizon_override": copy.deepcopy(raw_horizon),
        "candidate_K_values_changed": False,
        "policy_caps_changed": False,
        "kernel_capability_limits_changed": False,
        "execution_parent_private_entrypoint_called": context[
            "execution_parent_private_entrypoint_called"
        ],
        "q74_canonical_loaded_before_replay": context[
            "q74_canonical_loaded_before_replay"
        ],
        "q74_route_loader_suppressed": context["q74_route_loader_suppressed"],
        "q74_relabel_suppressed": context["q74_relabel_suppressed"],
        "q72_inner_eight_attributes_restored": context[
            "q72_inner_eight_attributes_restored"
        ],
        "q75_q76_abort_adapter_installed": context[
            "q75_q76_abort_adapter_installed"
        ],
    }
    parent_transform = copy.deepcopy(predecessor["checkpoint_transform"])
    transform = {
        "transform_id": (
            "double_occupancy_four_gate_k655360_c37_l1048576_d1048576_q76_v1"
        ),
        "execution_parent_q74_transform": parent_transform,
        "execution_parent_q74_transform_sha256": sha256(
            canonical_bytes(parent_transform)
        ),
        "q74_execution_parent_replaces_nested_q72_at_outer_boundary": True,
        "nested_q72_and_physical_b483_provenance_retained_in_q74_transform": True,
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "q75_q76_resource_abort_builder_derived_from_verified_q74_code": True,
        "resource_abort_builder_transform_changes_constants_only": True,
        "q75_and_q76_outcomes_precommitted": False,
        "incremental_route_semantic_delta": {
            "candidate_K_values_changed": False,
            "policy_caps_changed": False,
            "kernel_capability_limits_changed": False,
            "horizon_checkpoint_count": {"before": 74, "after": 76},
        },
        "overridden_semantics": ["double_occupancy_horizon_checkpoint_count"],
    }
    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k655360_c37_l1048576_d1048576_q76_screen_v1"
        ),
        "screen_source_sha256": self_sha,
        "same_byte_self_execution": True,
        "control_flow_owned_by_screen": False,
        "control_flow_owned_by_verified_parent": True,
        "control_flow_parent_relative_path": EXECUTION_PARENT_NAME,
        "control_flow_parent_source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
        "control_flow_parent_compiled_from_verified_bytes": True,
        "control_flow_parent_module_isolated": True,
        "control_flow_parent_same_byte_execution": True,
        "control_flow_parent_private_entrypoint_called": True,
        "control_flow_parent_runtime_horizon_override_applied": True,
        "v6_configuration_source_used_as_baseline_only": True,
        "v6_runtime_configuration_override_applied": True,
        "v2_arithmetic_source_sha256": parent.EXPECTED_V2_ARITHMETIC_SHA256,
        "v2_arithmetic_compiled_from_verified_bytes": True,
        "arithmetic_kernel_commit_role": (
            "base_v2_arithmetic_implementation_commit_before_capability_override"
        ),
        "kernel_capability_wrapper_relative_path": parent.KERNEL_WRAPPER_NAME,
        "kernel_capability_wrapper_source_sha256": parent.EXPECTED_KERNEL_WRAPPER_SHA256,
        "kernel_capability_wrapper_compiled_from_verified_bytes": True,
        "kernel_capability_wrapper_module_isolated": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(canonical_bytes(components)),
        "configuration_reference": configuration_reference,
        "configuration_reference_sha256": sha256(
            canonical_bytes(configuration_reference)
        ),
        "configuration_override": config,
        "configuration_override_sha256": sha256(canonical_bytes(config)),
        "kernel_capability_override": capability,
        "kernel_capability_override_sha256": sha256(canonical_bytes(capability)),
        "parent_horizon_override": horizon,
        "parent_horizon_override_sha256": sha256(canonical_bytes(horizon)),
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
        parent.EXPECTED_RELABELLED_RESULT_KEYS,
        "D q76 relabelled result",
    )
    if len(components) != 11 or len(custody) != 10:
        raise RuntimeError("D q76 final source closure cardinality drift")
    for value_key, digest_key in (
        ("screen_execution_components", "screen_execution_components_sha256"),
        ("configuration_reference", "configuration_reference_sha256"),
        ("configuration_override", "configuration_override_sha256"),
        ("kernel_capability_override", "kernel_capability_override_sha256"),
        ("parent_horizon_override", "parent_horizon_override_sha256"),
        ("route_predecessor_reference", "route_predecessor_reference_sha256"),
        ("predecessor_handoff_validation", "predecessor_handoff_validation_sha256"),
        ("checkpoint_transform", "checkpoint_transform_sha256"),
        ("resource_policy_abort", "resource_policy_abort_sha256"),
    ):
        value = result[value_key]
        digest = result[digest_key]
        if value is None:
            if digest is not None:
                raise RuntimeError(f"D q76 null nested digest drift: {value_key}")
        elif digest != sha256(canonical_bytes(value)):
            raise RuntimeError(f"D q76 nested digest drift: {value_key}")
    return result


def _run_verified(repo: Path) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("D q76 requires fresh same-byte self execution")
    if len(_VERIFIED_SELF_SOURCE_BYTES) > MAX_SELF_SOURCE_BYTES:
        raise RuntimeError("D q76 self source byte cap exceeded")
    repo = repo.resolve()
    parent = load_execution_parent(repo)
    result, context = execute_parent_replay(parent, repo)
    predecessor, route_reference = load_route_reference(repo, parent)
    return validate_and_relabel(
        result,
        predecessor,
        route_reference,
        parent,
        context,
    )


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    return compile_isolated(
        "verified_d_k655360_c37_l1048576_d1048576_q76_screen",
        path,
        payload,
    )


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("D q76 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("D q76 transcript exceeds output byte cap")
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output.resolve().parent,
            prefix=f".{output.name}.",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(raw)
            handle.flush()
        Path(temporary_name).replace(output.resolve())
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / OUTPUT_NAME,
    )
    args = parser.parse_args()
    result = run(Path(__file__).resolve().parent)
    raw = canonical_bytes(result)
    write_atomic_bounded(args.output, raw)
    print(json.dumps({
        "output": str(args.output),
        "file_size_bytes": len(raw),
        "file_sha256": sha256(raw),
        "status": result["status"],
        "terminal": result["screen_terminal_condition"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
