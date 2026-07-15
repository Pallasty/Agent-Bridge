#!/usr/bin/env python3
"""Fail-closed local pre-output tuple validator for BioCortex Track B.

This source profile validates a terminal-success sampling tuple and a complete
pre-output generation plan.  Its result is deliberately replayable and is not
an output permit.  It performs no authorizing consumption, calls no generator,
opens no output sink, and emits no live capability.  A future trusted boundary
must add an external atomic authority and make every generator/output path
non-bypassable before any condition output can be authorized.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import types
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = 1

REQUEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_first_condition_output_guard_request.v1"
)
PLAN_SCHEMA = "agent_bridge.biocortex_ab_track_b_pre_output_generation_plan.v1"
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_local_guard_validation_receipt.v1"
)

DECISION = (
    "SOURCE_PROFILE_PASS_BLOCKED_FAIL_CLOSED_EXTERNAL_ATOMIC_AUTHORITY_"
    "AND_NON_BYPASSABLE_OUTPUT_PATH_UNBOUND"
)
STATUS = "LOCAL_PRE_OUTPUT_TUPLE_VALIDATION_ONLY_NO_LIVE_OUTPUT_PERMIT"
AUTHORITY_SCOPE = "LOCAL_VALIDATION_ONLY_NOT_OUTPUT_AUTHORITY"

SOURCE_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_first_condition_output_guard_v1.py"
)
PLAN_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-pre-output-generation-plan-schema-v1.json"
)
RECEIPT_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-local-guard-validation-receipt-schema-v1.json"
)
CUSTODIAN_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_sampling_attempt_custodian_v1.py"
)
MAP_VALIDATOR_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_map_bijection_v1.py"
)

PLAN_SCHEMA_SHA256 = (
    "8b1f4889a4c8f56f2dca69e29e9220eea7b5e51ee6d3944d469bd52e1b5e2409"
)
RECEIPT_SCHEMA_SHA256 = (
    "34826789b8dcc274d7c8591a64e622598f7f55d294f0e7e7946aa8698fc8c3da"
)
CUSTODIAN_SHA256 = (
    "29c410adef0c5d2b9b312e6417d507395bcb6d808140e8502eeb63211078c71b"
)
MAP_VALIDATOR_SHA256 = (
    "92926f3e01910501e20a7d5f8f9b0cab79e28ca38ae2717966b8b6977fa89e58"
)

MAX_INPUT_BYTES = 33_554_432
MAX_TOTAL_INPUT_BYTES = 67_108_864
MAX_JSON_DEPTH = 40
MAX_UNITS = 262_144
MAX_SAFE_INTEGER = 9_007_199_254_740_991

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
CASE_RE = re.compile(r"^case_[0-9a-f]{32}$")
CONDITION_RE = re.compile(r"^cond_[0-9a-f]{32}$")
UTC_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
ZERO_SHA256 = "0" * 64

REQUEST_FIELDS = {
    "currentness_at_use_receipt_sha256",
    "evaluated_at_utc",
    "external_authority_decision_receipt_sha256",
    "first_output_unit_sha256",
    "generation_plan_sha256",
    "non_bypassable_output_adapter_sha256",
    "protocol_version",
    "requested_side_effect",
    "sampling_attempt_namespace_sha256",
    "sampling_event_sha256",
    "sampling_receipt_sha256",
    "sampling_write_outcome_custodian_receipt_sha256",
    "schema",
    "trial_id",
    "trusted_clock_receipt_sha256",
}

PLAN_FIELDS = {
    "admission_policy_sha256",
    "answer_blinding_seed_sha256",
    "condition_roster_sha256",
    "contract_core_sha256",
    "eligible_frame_manifest_sha256",
    "generation_session_sha256",
    "owner_trial_registration_receipt_sha256",
    "plan_created_at_utc",
    "protocol_version",
    "sampling_attempt_namespace_claim_receipt_sha256",
    "sampling_attempt_namespace_sha256",
    "sampling_event_sha256",
    "sampling_receipt_sha256",
    "sampling_write_outcome_custodian_receipt_sha256",
    "sampling_write_request_sha256",
    "schema",
    "selected_case_manifest_sha256",
    "selection_commitment_sha256",
    "strata_allocation_manifest_sha256",
    "trial_id",
    "units",
}

UNIT_FIELDS = {
    "case_id",
    "condition_id",
    "decoding_profile_sha256",
    "generator_build_sha256",
    "invocation_index",
    "model_snapshot_sha256",
    "output_sink_commitment_sha256",
    "prompt_context_sha256",
    "tokenizer_sha256",
}

BLOCKERS = (
    "CALLER_PRIOR_OUTPUT_ABSENCE_UNVERIFIED",
    "EXTERNAL_ANTI_ROLLBACK_ANCHOR_UNBOUND",
    "EXTERNAL_ATOMIC_AUTHORITY_PROVIDER_UNBOUND",
    "EXTERNAL_GLOBAL_SINGLE_USE_UNVERIFIED",
    "EXTERNAL_OWNER_TRUST_UNVERIFIED",
    "NON_BYPASSABLE_GENERATOR_AND_OUTPUT_PATH_UNBOUND",
    "TRUSTED_PRE_OUTPUT_ORDER_UNVERIFIED",
)


class GuardError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise GuardError(code, message)


@dataclass(frozen=True)
class CustodianStoreBinding:
    store_path: Path
    custodian_id: str
    custodian_authority_sha256: str
    custodian_instance_sha256: str
    registry_generation_sha256: str
    owner_trust_policy_sha256: str
    admission_policy_sha256: str
    sampling_receipt_schema_sha256: str
    sampling_receipt_writer_sha256: str
    busy_timeout_ms: int = 5000


@dataclass(frozen=True)
class LocalGuardValidationReceipt:
    receipt_sha256: str
    canonical_bytes: bytes
    receipt: dict[str, Any]


def canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                indent=2,
                separators=(",", ": "),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail("JSON_CANONICAL", f"value cannot be serialized canonically: {exc}")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_object(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _reject_constant(value: str) -> Any:
    fail("JSON_CONSTANT", f"non-finite JSON constant {value!r}")


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("JSON_DUPLICATE_KEY", f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _check_shape(value: Any, depth: int = 1) -> None:
    if depth > MAX_JSON_DEPTH:
        fail("JSON_DEPTH", "JSON nesting exceeds the source profile")
    if value is None or type(value) in {bool, int, str}:
        if type(value) is int and not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            fail("JSON_INTEGER", "integer exceeds the interoperable range")
        return
    if type(value) is list:
        for item in value:
            _check_shape(item, depth + 1)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                fail("JSON_KEY", "JSON object key is not a string")
            _check_shape(item, depth + 1)
        return
    fail("JSON_TYPE", "unsupported JSON value type")


def parse_canonical(raw: Any, expected_fields: set[str], schema: str, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_INPUT_BYTES:
        fail("INPUT_BYTES", f"{label} must be bounded exact bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("JSON_PARSE", f"{label} is not canonical JSON: {exc}")
    if type(value) is not dict:
        fail("OBJECT_TYPE", f"{label} must be an object")
    _check_shape(value)
    if canonical_bytes(value) != raw:
        fail("JSON_CANONICAL", f"{label} bytes are not canonical pretty JSON")
    if set(value) != expected_fields:
        fail("OBJECT_FIELDS", f"{label} field set is not closed")
    if value.get("schema") != schema:
        fail("SCHEMA", f"{label} schema is not the frozen v1 value")
    return value


def require_sha(value: Any, label: str) -> str:
    if type(value) is not str or SHA_RE.fullmatch(value) is None or value == ZERO_SHA256:
        fail("SHA256", f"{label} is not a nonzero lowercase SHA-256")
    return value


def require_label(value: Any, label: str) -> str:
    if type(value) is not str or LABEL_RE.fullmatch(value) is None:
        fail("LABEL", f"{label} is not a canonical label")
    return value


def require_utc(value: Any, label: str) -> datetime:
    if type(value) is not str or UTC_RE.fullmatch(value) is None:
        fail("UTC", f"{label} is not canonical second-resolution UTC")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        fail("UTC", f"{label} is not a real UTC instant: {exc}")


def _read_pinned_file(path: Path, expected_sha256: str | None, label: str) -> tuple[bytes, str]:
    try:
        before = os.lstat(path)
    except OSError as exc:
        fail("SOURCE_IDENTITY", f"cannot stat {label}: {exc}")
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or before.st_nlink != 1
        or before.st_size < 1
        or before.st_size > 8_388_608
    ):
        fail("SOURCE_IDENTITY", f"{label} is not one bounded unaliased regular file")
    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    if any(not hasattr(os, name) for name in required):
        fail("PLATFORM", "source validation needs nofollow/cloexec/nonblock")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            fail("SOURCE_RACE", f"{label} changed while opening")
        chunks: list[bytes] = []
        remaining = 8_388_609
        while remaining:
            chunk = os.read(fd, min(1_048_576, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        if (
            len(raw) > 8_388_608
            or after.st_size != len(raw)
            or (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            fail("SOURCE_RACE", f"{label} size or identity changed while reading")
    finally:
        os.close(fd)
    digest = sha256_bytes(raw)
    if expected_sha256 is not None and digest != expected_sha256:
        fail("SOURCE_HASH", f"{label} byte hash drift")
    return raw, digest


def _load_bound_module(root: Path, relative: Path, expected: str, module_name: str) -> types.ModuleType:
    path = (root / relative).resolve()
    if path != root / relative:
        fail("SOURCE_PATH", f"{relative} does not resolve to the exact repository path")
    raw, _ = _read_pinned_file(path, expected, str(relative))
    if module_name in sys.modules:
        fail("MODULE_STATE", f"private module name is already occupied: {module_name}")
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = None
    sys.modules[module_name] = module
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _unload_bound_module(name: str, module: types.ModuleType | None) -> None:
    if module is not None and sys.modules.get(name) is module:
        sys.modules.pop(name, None)


def _validate_sources(root: Path) -> str:
    if not isinstance(root, Path) or not root.is_absolute() or root.resolve() != root:
        fail("ROOT_PATH", "repository root must be an absolute resolved Path")
    for relative, expected, label in (
        (PLAN_SCHEMA_PATH, PLAN_SCHEMA_SHA256, "pre-output plan schema"),
        (RECEIPT_SCHEMA_PATH, RECEIPT_SCHEMA_SHA256, "local validation receipt schema"),
    ):
        raw, _ = _read_pinned_file(root / relative, expected, label)
        try:
            parsed = json.loads(raw, object_pairs_hook=_reject_pairs, parse_constant=_reject_constant)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            fail("SCHEMA_SOURCE", f"{label} is malformed: {exc}")
        if canonical_bytes(parsed) != raw:
            fail("SCHEMA_SOURCE", f"{label} is not canonical JSON")
    source_path = Path(__file__).absolute()
    if source_path.resolve() != root / SOURCE_PATH:
        fail("SOURCE_PATH", "loaded guard source path differs from the repository binding")
    _, source_sha256 = _read_pinned_file(source_path, None, "local guard source")
    return source_sha256


def _validate_plan(plan: dict[str, Any]) -> None:
    if plan["protocol_version"] != PROTOCOL_VERSION:
        fail("PROTOCOL_VERSION", "generation plan is not protocol v1")
    require_label(plan["trial_id"], "plan.trial_id")
    require_utc(plan["plan_created_at_utc"], "plan.plan_created_at_utc")
    for field in PLAN_FIELDS - {"schema", "protocol_version", "trial_id", "plan_created_at_utc", "units"}:
        require_sha(plan[field], f"plan.{field}")
    units = plan["units"]
    if type(units) is not list or not 1 <= len(units) <= MAX_UNITS:
        fail("PLAN_UNITS", "generation plan units are outside the bounded nonempty profile")
    sink_commitments: set[str] = set()
    for index, unit in enumerate(units, 1):
        if type(unit) is not dict or set(unit) != UNIT_FIELDS:
            fail("PLAN_UNIT_FIELDS", "generation plan unit field set is not closed")
        if unit["invocation_index"] != index or type(unit["invocation_index"]) is not int:
            fail("PLAN_INVOCATION_INDEX", "invocation indices must be contiguous from one")
        if type(unit["case_id"]) is not str or CASE_RE.fullmatch(unit["case_id"]) is None:
            fail("PLAN_CASE_ID", "plan unit case id is not canonical")
        if type(unit["condition_id"]) is not str or CONDITION_RE.fullmatch(unit["condition_id"]) is None:
            fail("PLAN_CONDITION_ID", "plan unit condition id is not opaque canonical v1")
        for field in UNIT_FIELDS - {"invocation_index", "case_id", "condition_id"}:
            require_sha(unit[field], f"plan.units[{index - 1}].{field}")
        sink = unit["output_sink_commitment_sha256"]
        if sink in sink_commitments:
            fail("PLAN_SINK_DUPLICATE", "output sink commitment repeats across units")
        sink_commitments.add(sink)


def _exact_equal(left: Any, right: Any, code: str, message: str) -> None:
    if left != right:
        fail(code, message)


def validate_local_first_condition_output_preflight(
    root: Path,
    custodian_binding: CustodianStoreBinding,
    request_bytes: bytes,
    generation_plan_bytes: bytes,
    condition_roster_bytes: bytes,
    answer_blinding_seed_bytes: bytes,
    sampling_write_request_bytes: bytes,
) -> LocalGuardValidationReceipt:
    """Validate one source-only pre-output tuple and return a blocked receipt."""

    inputs = (
        request_bytes,
        generation_plan_bytes,
        condition_roster_bytes,
        answer_blinding_seed_bytes,
        sampling_write_request_bytes,
    )
    if any(type(value) is not bytes for value in inputs):
        fail("INPUT_TYPE", "all artifact inputs must be exact bytes")
    if sum(len(value) for value in inputs) > MAX_TOTAL_INPUT_BYTES:
        fail("INPUT_BUDGET", "combined input bytes exceed the source profile")
    if type(answer_blinding_seed_bytes) is not bytes or len(answer_blinding_seed_bytes) != 32:
        fail("ANSWER_SEED", "answer-blinding seed must be exactly 32 private bytes")
    if type(custodian_binding) is not CustodianStoreBinding:
        fail("CUSTODIAN_BINDING", "custodian binding must be the exact local type")

    source_sha256 = _validate_sources(root)
    request = parse_canonical(request_bytes, REQUEST_FIELDS, REQUEST_SCHEMA, "guard request")
    plan = parse_canonical(generation_plan_bytes, PLAN_FIELDS, PLAN_SCHEMA, "generation plan")
    _validate_plan(plan)

    if request["protocol_version"] != PROTOCOL_VERSION:
        fail("PROTOCOL_VERSION", "guard request is not protocol v1")
    require_label(request["trial_id"], "request.trial_id")
    evaluated_at = require_utc(request["evaluated_at_utc"], "request.evaluated_at_utc")
    for field in (
        "sampling_attempt_namespace_sha256",
        "sampling_event_sha256",
        "sampling_write_outcome_custodian_receipt_sha256",
        "sampling_receipt_sha256",
        "generation_plan_sha256",
        "first_output_unit_sha256",
    ):
        require_sha(request[field], f"request.{field}")
    if request["requested_side_effect"] != "FIRST_CONDITION_OUTPUT":
        fail("REQUESTED_SIDE_EFFECT", "request does not name the closed blocked side effect")
    for field in (
        "external_authority_decision_receipt_sha256",
        "trusted_clock_receipt_sha256",
        "currentness_at_use_receipt_sha256",
        "non_bypassable_output_adapter_sha256",
    ):
        if request[field] is not None:
            fail("UNBOUND_EVIDENCE", f"source profile requires {field} to remain null")

    generation_plan_sha256 = sha256_bytes(generation_plan_bytes)
    _exact_equal(
        request["generation_plan_sha256"], generation_plan_sha256,
        "PLAN_HASH_JOIN", "request does not bind the exact generation-plan bytes",
    )
    _exact_equal(request["trial_id"], plan["trial_id"], "TRIAL_JOIN", "request and plan trial differ")
    for field in ("sampling_attempt_namespace_sha256", "sampling_event_sha256", "sampling_receipt_sha256", "sampling_write_outcome_custodian_receipt_sha256"):
        _exact_equal(request[field], plan[field], "REQUEST_PLAN_JOIN", f"request and plan {field} differ")

    custodian_name = "_biocortex_ab_track_b_bound_custodian_v1_guard"
    map_name = "_biocortex_ab_track_b_bound_map_v1_guard"
    custodian: types.ModuleType | None = None
    map_v1: types.ModuleType | None = None
    try:
        custodian = _load_bound_module(
            root, CUSTODIAN_PATH, CUSTODIAN_SHA256, custodian_name
        )
        map_v1 = _load_bound_module(
            root, MAP_VALIDATOR_PATH, MAP_VALIDATOR_SHA256, map_name
        )
        try:
            bound_config = custodian.CustodianConfig(
                store_path=custodian_binding.store_path,
                custodian_id=custodian_binding.custodian_id,
                custodian_authority_sha256=custodian_binding.custodian_authority_sha256,
                custodian_instance_sha256=custodian_binding.custodian_instance_sha256,
                registry_generation_sha256=custodian_binding.registry_generation_sha256,
                owner_trust_policy_sha256=custodian_binding.owner_trust_policy_sha256,
                admission_policy_sha256=custodian_binding.admission_policy_sha256,
                sampling_receipt_schema_sha256=custodian_binding.sampling_receipt_schema_sha256,
                sampling_receipt_writer_sha256=custodian_binding.sampling_receipt_writer_sha256,
                busy_timeout_ms=custodian_binding.busy_timeout_ms,
            )
            outcome_stored = custodian.query_sampling_outcome(
                bound_config, request["sampling_attempt_namespace_sha256"]
            )
            if outcome_stored is None:
                fail("OUTCOME_MISSING", "custodian has no terminal outcome for the namespace")
            _exact_equal(
                outcome_stored.receipt_sha256,
                request["sampling_write_outcome_custodian_receipt_sha256"],
                "OUTCOME_RECEIPT_JOIN",
                "request does not bind the exact custodian outcome receipt",
            )
            outcome = outcome_stored.receipt
            expected_terminal = (
                outcome["outcome"] == "SUCCESS"
                and outcome["write_state"] == "COMPLETE_DURABLE_OBSERVED"
                and outcome["terminal"] is True
                and outcome["first_condition_output_guard_required"] is True
                and outcome["condition_output_authorized"] is False
                and outcome["external_global_single_use_verified"] is False
            )
            if not expected_terminal:
                fail("OUTCOME_NOT_SUCCESS", "custodian outcome is not a blocked terminal success")

            registration = custodian.query_exact_receipt(
                bound_config, outcome["owner_trial_registration_receipt_sha256"]
            )
            claim = custodian.query_exact_receipt(
                bound_config, outcome["sampling_attempt_namespace_claim_receipt_sha256"]
            )
            if registration is None or claim is None:
                fail("CUSTODIAN_CHAIN", "custodian registration or claim receipt is absent")
            if registration.receipt.get("condition_output_authorized") is not False:
                fail("CUSTODIAN_CHAIN", "registration unexpectedly authorizes output")
            if claim.receipt.get("condition_output_authorized") is not False:
                fail("CUSTODIAN_CHAIN", "claim unexpectedly authorizes output")

            write_request, rebuilt_receipt_bytes, rebuilt_receipt_sha256 = map_v1.rebuild_sampling_receipt(
                root, sampling_write_request_bytes
            )
            sampling_receipt = map_v1.parse_canonical_bytes(
                rebuilt_receipt_bytes, "rebuilt sampling receipt"
            )
            map_v1.validate_schema_sources(root)
            core_info = map_v1.validate_contract_core(root, write_request["contract_core"])
            frame_info = map_v1.validate_eligible_frame(write_request["eligible_frame_manifest"])
            sampling_info = map_v1.validate_sampling(sampling_receipt)
            selected_info = map_v1.validate_selected(write_request["selected_case_manifest"])
            roster = map_v1.parse_canonical_bytes(condition_roster_bytes, "condition roster")
            roster_info = map_v1.validate_roster(roster, answer_blinding_seed_bytes, plan["trial_id"])
        except GuardError:
            raise
        except Exception as exc:
            fail("PREDECESSOR_VALIDATION", f"frozen predecessor validation failed: {exc}")

        core_sha256 = sha256_object(write_request["contract_core"])
        frame_sha256 = sha256_object(write_request["eligible_frame_manifest"])
        allocation_sha256 = sha256_object(write_request["strata_allocation_manifest"])
        selected_sha256 = sha256_object(write_request["selected_case_manifest"])
        roster_sha256 = sha256_bytes(condition_roster_bytes)
        write_request_sha256 = sha256_bytes(sampling_write_request_bytes)
        answer_seed_sha256 = sha256_bytes(answer_blinding_seed_bytes)

        joins = {
            "trial_id": plan["trial_id"],
            "admission_policy_sha256": plan["admission_policy_sha256"],
            "contract_core_sha256": plan["contract_core_sha256"],
            "eligible_frame_manifest_sha256": plan["eligible_frame_manifest_sha256"],
            "strata_allocation_manifest_sha256": plan["strata_allocation_manifest_sha256"],
            "sampling_attempt_namespace_sha256": plan["sampling_attempt_namespace_sha256"],
            "sampling_event_sha256": plan["sampling_event_sha256"],
            "owner_trial_registration_receipt_sha256": plan["owner_trial_registration_receipt_sha256"],
            "sampling_attempt_namespace_claim_receipt_sha256": plan["sampling_attempt_namespace_claim_receipt_sha256"],
            "sampling_write_outcome_custodian_receipt_sha256": plan["sampling_write_outcome_custodian_receipt_sha256"],
            "sampling_write_request_sha256": plan["sampling_write_request_sha256"],
            "sampling_receipt_sha256": plan["sampling_receipt_sha256"],
            "selected_case_manifest_sha256": plan["selected_case_manifest_sha256"],
            "selection_commitment_sha256": plan["selection_commitment_sha256"],
        }
        expected_joins = {
            "trial_id": outcome["trial_id"],
            "admission_policy_sha256": outcome["admission_policy_sha256"],
            "contract_core_sha256": core_sha256,
            "eligible_frame_manifest_sha256": frame_sha256,
            "strata_allocation_manifest_sha256": allocation_sha256,
            "sampling_attempt_namespace_sha256": outcome["sampling_attempt_namespace_sha256"],
            "sampling_event_sha256": outcome["sampling_event_sha256"],
            "owner_trial_registration_receipt_sha256": outcome["owner_trial_registration_receipt_sha256"],
            "sampling_attempt_namespace_claim_receipt_sha256": outcome["sampling_attempt_namespace_claim_receipt_sha256"],
            "sampling_write_outcome_custodian_receipt_sha256": outcome_stored.receipt_sha256,
            "sampling_write_request_sha256": write_request_sha256,
            "sampling_receipt_sha256": rebuilt_receipt_sha256,
            "selected_case_manifest_sha256": selected_sha256,
            "selection_commitment_sha256": sampling_receipt["selection_commitment_sha256"],
        }
        if joins != expected_joins:
            fail("EXACT_TUPLE_JOIN", "generation plan differs from the stored sampling tuple")
        if request["sampling_receipt_sha256"] != rebuilt_receipt_sha256:
            fail("SAMPLING_RECEIPT_JOIN", "request sampling receipt hash differs from replay")
        if outcome["sampling_receipt_sha256"] != rebuilt_receipt_sha256:
            fail("SAMPLING_RECEIPT_JOIN", "custodian outcome sampling receipt differs from replay")
        if outcome["sampling_write_request_sha256"] != write_request_sha256:
            fail("SAMPLING_WRITE_REQUEST_JOIN", "custodian outcome write request differs")

        if not (
            core_info["trial_id"] == frame_info["trial_id"] == sampling_info["trial_id"]
            == selected_info["trial_id"] == roster_info["trial_id"] == plan["trial_id"]
        ):
            fail("TRIAL_JOIN", "predecessor artifact trials differ")
        if not (
            sampling_info["contract_sha256"] == selected_info["contract_sha256"]
            == roster_info["contract_sha256"] == core_sha256
        ):
            fail("CONTRACT_JOIN", "predecessor artifact contract bindings differ")
        if sampling_info["eligible_frame_manifest_sha256"] != frame_sha256:
            fail("FRAME_JOIN", "sampling receipt frame binding differs")
        if selected_info["eligible_frame_manifest_sha256"] != frame_sha256:
            fail("FRAME_JOIN", "selected manifest frame binding differs")
        if sampling_info["selected_case_manifest_sha256"] != selected_sha256:
            fail("SELECTED_JOIN", "sampling receipt selected-manifest binding differs")
        if sampling_info["case_ids"] != selected_info["case_ids"]:
            fail("SELECTED_GRAIN", "sampling probability grain differs from selected cases")
        if sampling_info["selection_commitment_sha256"] != selected_info["selection_commitment_sha256"]:
            fail("SELECTION_JOIN", "selection commitments differ")
        if plan["condition_roster_sha256"] != roster_sha256:
            fail("ROSTER_HASH_JOIN", "plan does not bind the exact roster bytes")
        if plan["answer_blinding_seed_sha256"] != answer_seed_sha256:
            fail("ANSWER_SEED_JOIN", "plan does not bind the exact private seed")
        if answer_seed_sha256 == sampling_info["sampling_seed_sha256"]:
            fail("SEED_DOMAIN_SEPARATION", "answer-blinding seed equals the sampling seed")

        ranked: list[tuple[str, str, str]] = []
        for case_id in selected_info["case_ids"]:
            for _condition_key, condition_id in roster_info["conditions"]:
                ranked.append(
                    (
                        map_v1.generation_rank(
                            answer_blinding_seed_bytes,
                            plan["trial_id"],
                            case_id,
                            condition_id,
                        ),
                        case_id,
                        condition_id,
                    )
                )
        if len({row[0] for row in ranked}) != len(ranked):
            fail("GENERATION_RANK_COLLISION", "generation rank collision is fail closed")
        ranked.sort()
        units = plan["units"]
        if len(units) != len(ranked):
            fail("PLAN_COVERAGE", "generation plan is not selected-cases by roster complete")
        for index, ((_, case_id, condition_id), unit) in enumerate(zip(ranked, units, strict=True), 1):
            if (
                unit["invocation_index"] != index
                or unit["case_id"] != case_id
                or unit["condition_id"] != condition_id
            ):
                fail("PLAN_ORDER", "generation plan does not follow the seed-derived global order")

        first_output_unit_sha256 = sha256_object(units[0])
        if request["first_output_unit_sha256"] != first_output_unit_sha256:
            fail("FIRST_OUTPUT_SLOT_JOIN", "request does not bind the exact first plan unit")

        sampling_created = sampling_info["created_at"]
        outcome_finalized = require_utc(outcome["finalized_at_utc"], "outcome.finalized_at_utc")
        plan_created = require_utc(plan["plan_created_at_utc"], "plan.plan_created_at_utc")
        if not sampling_created < outcome_finalized < plan_created < evaluated_at:
            fail("LOCAL_TIME_ORDER", "local artifact timestamps are equal or reversed")

        receipt = {
            "schema": RECEIPT_SCHEMA,
            "decision": DECISION,
            "status": STATUS,
            "authority_scope": AUTHORITY_SCOPE,
            "protocol_version": PROTOCOL_VERSION,
            "trial_id": plan["trial_id"],
            "evaluated_at_utc": request["evaluated_at_utc"],
            "admission_policy_sha256": plan["admission_policy_sha256"],
            "contract_core_sha256": core_sha256,
            "eligible_frame_manifest_sha256": frame_sha256,
            "strata_allocation_manifest_sha256": allocation_sha256,
            "sampling_attempt_namespace_sha256": plan["sampling_attempt_namespace_sha256"],
            "sampling_event_sha256": plan["sampling_event_sha256"],
            "owner_trial_registration_receipt_sha256": plan["owner_trial_registration_receipt_sha256"],
            "sampling_attempt_namespace_claim_receipt_sha256": plan["sampling_attempt_namespace_claim_receipt_sha256"],
            "sampling_write_outcome_custodian_receipt_sha256": outcome_stored.receipt_sha256,
            "sampling_write_request_sha256": write_request_sha256,
            "sampling_receipt_sha256": rebuilt_receipt_sha256,
            "selected_case_manifest_sha256": selected_sha256,
            "selection_commitment_sha256": sampling_info["selection_commitment_sha256"],
            "condition_roster_sha256": roster_sha256,
            "answer_blinding_seed_sha256": answer_seed_sha256,
            "generation_session_sha256": plan["generation_session_sha256"],
            "generation_plan_sha256": generation_plan_sha256,
            "first_output_unit_sha256": first_output_unit_sha256,
            "local_guard_source_sha256": source_sha256,
            "pre_output_generation_plan_schema_sha256": PLAN_SCHEMA_SHA256,
            "local_guard_validation_receipt_schema_sha256": RECEIPT_SCHEMA_SHA256,
            "local_custodian_terminal_success_verified": True,
            "sampling_receipt_replay_verified": True,
            "local_generation_plan_verified": True,
            "first_output_slot_bound": True,
            "post_generation_map_intentionally_absent": True,
            "local_time_order_consistent": True,
            "source_identity_verified": True,
            "trusted_pre_output_order_verified": False,
            "caller_prior_output_absence_verified": False,
            "all_generator_paths_guarded": False,
            "external_owner_trust_verified": False,
            "external_authority_provider_present": False,
            "external_authority_linearizability_verified": False,
            "external_anti_rollback_anchor_present": False,
            "external_global_single_use_verified": False,
            "non_bypassable_output_path_verified": False,
            "authorizing_consumption_performed": False,
            "local_validation_receipt_replayable": True,
            "live_output_capability_emitted": False,
            "condition_output_authorized": False,
            "receipt_is_output_permit": False,
            "side_effects_unlocked": "NONE",
            "blockers": list(BLOCKERS),
        }
        rendered = canonical_bytes(receipt)
        return LocalGuardValidationReceipt(
            receipt_sha256=sha256_bytes(rendered),
            canonical_bytes=rendered,
            receipt=receipt,
        )
    finally:
        _unload_bound_module(map_name, map_v1)
        _unload_bound_module(custodian_name, custodian)


__all__ = [
    "CustodianStoreBinding",
    "GuardError",
    "LocalGuardValidationReceipt",
    "canonical_bytes",
    "sha256_bytes",
    "sha256_object",
    "validate_local_first_condition_output_preflight",
]
