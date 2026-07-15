#!/usr/bin/env python3
"""Fail-closed Track B sampling-receipt v1 builder and O_EXCL writer.

This source recomputes the public seed and deterministic selection from exact
canonical inputs, validates every case-grain join, and writes one private
receipt without overwrite.  Its successful return is a same-process
observation, not an independent custody, clock, entropy, or output-admission
attestation.  In particular, this module never authorizes condition output.
"""

from __future__ import annotations

import __future__ as _future
import builtins as _builtins
import hashlib
import json
import math
import os
import re
import stat
import sys
import types
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REQUEST_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_receipt_write_request.v0"
RECEIPT_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_receipt.v1"
CONTRACT_CORE_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_contract_core.v0"
FRAME_SCHEMA = "agent_bridge.biocortex_ab_track_b_eligible_frame_source_profile.v0"
ALLOCATION_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_strata_allocation_source_profile.v0"
)
SELECTED_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_selected_case_manifest_source_profile.v0"
)
RESERVE_SCHEMA = "agent_bridge.biocortex_ab_track_b_reserve_manifest_source_profile.v0"
SEED_REQUEST_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_seed_request.v0"
SEED_DOMAIN = "agent-bridge/track-b/sample/v1"
SEED_MESSAGE_PROFILE = (
    "domain_utf8_NUL_contract_sha256_ascii_NUL_trial_id_utf8_NUL_"
    "eligible_frame_sha256_ascii_NUL_external_entropy_sha256_ascii"
)
SELECTION_REQUEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_sampling_selection_request.v0"
)
SELECTION_DOMAIN = "agent-bridge/track-b/sample/v1"
SELECTION_MESSAGE_PROFILE = (
    "domain_utf8_NUL_frame_sha256_ascii_NUL_stratum_utf8_NUL_case_id_utf8"
)

CANONICAL_SERIALIZATION = (
    "UTF8_SORTED_KEYS_INDENT_2_LF_FINAL_NEWLINE_NO_NAN_DUPLICATE_KEYS_REJECTED"
)
WRITE_EVIDENCE_SCOPE = "SAME_PROCESS_OBSERVATION_NOT_INDEPENDENT_CUSTODY_ATTESTATION"
RECEIPT_BASENAME = "sampling-receipt.json"
WRITE_FLAGS_PROFILE = "O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC"

PROFILE_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-sampling-contract-digest-profile-v0.json"
)
RECEIPT_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v1.json"
)
SEED_SOURCE_PATH = "scripts/eval/biocortex_ab_track_b_sampling_seed_derivation_v0.py"
SELECTION_SOURCE_PATH = "scripts/eval/biocortex_ab_track_b_sampling_selection_v0.py"

EXPECTED_PROFILE_SHA256 = "a8972ad5e75b30634931fee84f08226e2660413b45cf9dfea948089d61160243"
EXPECTED_RECEIPT_SCHEMA_SHA256 = (
    "e418b58246eaf183b5624c7eb12299caeea933c83a07584faa915651b3cd48d4"
)
EXPECTED_SEED_SOURCE_SHA256 = (
    "4f51781ff707e89b4c09adffeafbdaacd75c7e1571d1a86e45d336aace888a3f"
)
EXPECTED_SELECTION_SOURCE_SHA256 = (
    "e327faf2ad73718dc33f68fdb66a89abf0ac84fbbf8d828ff79fa0e8b75772ec"
)

MAX_CASES = 4096
MAX_STRATA = 256
MAX_JSON_DEPTH = 32
MAX_CONTRACT_CORE_BYTES = 1_048_576
MAX_SINGLE_ARTIFACT_BYTES = 8_388_608
MAX_TOTAL_INPUT_BYTES = 16_777_216
MAX_RECEIPT_BYTES = 8_388_608
MAX_SAFE_INTEGER = 9_007_199_254_740_991
HMAC_SHA256_BLOCK_BYTES = 64

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
CASE_RE = re.compile(r"^case_[0-9a-f]{32}$")
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

REQUEST_FIELDS = {
    "contract_core",
    "created_at_utc",
    "eligible_frame_manifest",
    "external_entropy_sha256",
    "frame_o_excl_receipt_sha256",
    "reserve_manifest",
    "schema",
    "seed_entropy_receipt_sha256",
    "selected_case_manifest",
    "strata_allocation_manifest",
}
CONTRACT_CORE_FIELDS = {
    "admission_policy_sha256",
    "candidate_condition_policy_sha256",
    "clock_policy_sha256",
    "condition_roster_policy_sha256",
    "context_result_policy_sha256",
    "contract_digest_profile_sha256",
    "estimator_policy_sha256",
    "external_entropy_policy_sha256",
    "frame_builder_sha256",
    "generation_policy_sha256",
    "inclusion_exclusion_rules_sha256",
    "latency_policy_sha256",
    "reference_condition_policy_sha256",
    "resource_caps_policy_sha256",
    "review_policy_sha256",
    "sampling_receipt_schema_sha256",
    "sampling_receipt_writer_sha256",
    "sampling_seed_derivation_sha256",
    "sampling_selection_algorithm_sha256",
    "schema",
    "seed_separation_policy_sha256",
    "strata_allocation_policy_sha256",
    "target_population_definition_sha256",
    "trial_id",
    "truth_policy_sha256",
}
CONTRACT_SHA_FIELDS = CONTRACT_CORE_FIELDS - {"schema", "trial_id"}
FRAME_FIELDS = {
    "cases",
    "frame_builder_sha256",
    "inclusion_exclusion_rules_sha256",
    "schema",
    "target_population_definition_sha256",
    "trial_id",
}
ALLOCATION_FIELDS = {
    "eligible_frame_manifest_sha256",
    "schema",
    "strata_allocation_policy_sha256",
    "strata_allocations",
    "trial_id",
}
SELECTION_MANIFEST_FIELDS = {
    "cases",
    "contract_sha256",
    "eligible_frame_manifest_sha256",
    "sampling_seed_sha256",
    "schema",
    "selection_commitment_sha256",
    "trial_id",
}
RECEIPT_FIELDS = {
    "anti_shopping_order_verified",
    "case_inclusion_probabilities",
    "case_sampling_weights",
    "condition_output_authorized",
    "contract_digest_profile_sha256",
    "contract_sha256",
    "created_at_utc",
    "eligible_frame_manifest_sha256",
    "external_entropy_sha256",
    "frame_o_excl_receipt_sha256",
    "pre_output_timing_verified",
    "receipt_precedes_first_condition_output",
    "receipt_schema_sha256",
    "receipt_writer_sha256",
    "reserve_manifest_sha256",
    "sampling_seed_sha256",
    "sampling_selection_algorithm_sha256",
    "sampling_selection_domain",
    "sampling_selection_message",
    "schema",
    "seed_derivation_domain",
    "seed_derivation_message_profile",
    "seed_derivation_sha256",
    "seed_entropy_receipt_sha256",
    "selected_case_manifest_sha256",
    "selection_commitment_sha256",
    "strata_allocation_manifest_sha256",
    "trial_id",
}


class SamplingReceiptError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise SamplingReceiptError(code, message)


_CAPTURED_SHA256 = hashlib.sha256
_CAPTURED_JSON_DUMPS = json.dumps
_CAPTURED_MATH_GCD = math.gcd
_CAPTURED_RE_COMPILE = re.compile


class _BoundModuleProxy:
    """Read-only export surface for exact-source dependency execution."""

    __slots__ = ("_exports",)

    def __init__(self, **exports: Any) -> None:
        object.__setattr__(self, "_exports", types.MappingProxyType(dict(exports)))

    def __getattr__(self, name: str) -> Any:
        try:
            return self._exports[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, _name: str, _value: Any) -> None:
        raise AttributeError("bound dependency module proxy is read-only")


class _BoundHmacDigest:
    __slots__ = ("_digest",)

    def __init__(self, digest: bytes) -> None:
        self._digest = digest

    def digest(self) -> bytes:
        return self._digest


def _bound_hmac_sha256_new(
    key: Any,
    msg: Any = None,
    digestmod: Any = None,
) -> _BoundHmacDigest:
    """One-shot HMAC-SHA-256 primitive for the frozen selection source."""

    if digestmod is not _CAPTURED_SHA256:
        raise ValueError("controlled selection execution permits only SHA-256 HMAC")
    if type(key) is not bytes or (msg is not None and type(msg) is not bytes):
        raise TypeError("controlled HMAC key and message must be exact bytes")
    message = b"" if msg is None else msg
    normalized = key
    if len(normalized) > HMAC_SHA256_BLOCK_BYTES:
        normalized = _CAPTURED_SHA256(normalized).digest()
    normalized += b"\0" * (HMAC_SHA256_BLOCK_BYTES - len(normalized))
    inner_pad = bytes(byte ^ 0x36 for byte in normalized)
    outer_pad = bytes(byte ^ 0x5C for byte in normalized)
    inner = _CAPTURED_SHA256(inner_pad + message).digest()
    return _BoundHmacDigest(_CAPTURED_SHA256(outer_pad + inner).digest())


_BOUND_IMPORTS = types.MappingProxyType(
    {
        "__future__": _BoundModuleProxy(annotations=_future.annotations),
        "dataclasses": _BoundModuleProxy(dataclass=dataclass, field=field),
        "hashlib": _BoundModuleProxy(sha256=_CAPTURED_SHA256),
        "hmac": _BoundModuleProxy(new=_bound_hmac_sha256_new),
        "json": _BoundModuleProxy(dumps=_CAPTURED_JSON_DUMPS),
        "math": _BoundModuleProxy(gcd=_CAPTURED_MATH_GCD),
        "re": _BoundModuleProxy(compile=_CAPTURED_RE_COMPILE),
        "typing": _BoundModuleProxy(Any=Any),
    }
)


def _bound_dependency_import(
    name: str,
    _globals: Any = None,
    _locals: Any = None,
    _fromlist: Any = (),
    level: int = 0,
) -> Any:
    if level != 0 or name not in _BOUND_IMPORTS:
        raise ImportError(f"dependency import outside exact allowlist: {name}")
    return _BOUND_IMPORTS[name]


def _bound_dependency_builtins() -> dict[str, Any]:
    controlled = dict(vars(_builtins))
    controlled["__import__"] = _bound_dependency_import
    return controlled


@dataclass(frozen=True)
class BuiltSamplingReceipt:
    receipt: dict[str, Any] = field(repr=False)
    canonical_bytes: bytes = field(repr=False)
    canonical_request_bytes: bytes = field(repr=False)
    receipt_sha256: str
    selected_case_count: int
    reserve_case_count: int


@dataclass(frozen=True)
class ReceiptWriteObservation:
    receipt_sha256: str
    receipt_size_bytes: int
    selected_case_count: int
    reserve_case_count: int
    receipt_basename: str
    write_flags_profile: str
    create_file_mode_octal: str
    final_file_mode_octal: str
    content_fsync_completed: bool
    read_only_seal_fsync_completed: bool
    parent_directory_fsync_completed: bool
    reread_identity_and_bytes_verified: bool
    condition_output_authorized: bool
    anti_shopping_order_verified: bool
    pre_output_timing_verified: bool
    trusted_clock_verified: bool
    evidence_scope: str


def _canonical_bytes(value: Any, label: str = "value") -> bytes:
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
        ) + "\n"
        return rendered.encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        fail("JSON_CANONICAL", f"{label} cannot be canonically serialized: {exc}")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            fail("JSON_DUPLICATE_KEY", f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    fail("JSON_NONFINITE", f"non-finite JSON number is forbidden: {value}")


def _depth_and_scalar_profile(value: Any, depth: int = 1) -> int:
    if depth > MAX_JSON_DEPTH:
        fail("JSON_DEPTH", f"JSON nesting exceeds {MAX_JSON_DEPTH}")
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            fail("JSON_KEY", "all JSON object keys must be strings")
        return max(
            [depth]
            + [_depth_and_scalar_profile(item, depth + 1) for item in value.values()]
        )
    if type(value) is list:
        return max(
            [depth] + [_depth_and_scalar_profile(item, depth + 1) for item in value]
        )
    if value is None or type(value) in {str, int, bool}:
        if type(value) is int and not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            fail("JSON_INTEGER", "JSON integer exceeds the interoperable safe range")
        return depth
    fail("JSON_SCALAR", f"unsupported JSON scalar type: {type(value).__name__}")


def parse_canonical_request_bytes(raw: Any) -> dict[str, Any]:
    if type(raw) is not bytes:
        fail("REQUEST_BYTES", "request must be exact bytes")
    if not 1 <= len(raw) <= MAX_TOTAL_INPUT_BYTES:
        fail("REQUEST_SIZE", f"request must be 1..={MAX_TOTAL_INPUT_BYTES} bytes")
    if raw.startswith(b"\xef\xbb\xbf"):
        fail("JSON_BOM", "UTF-8 BOM is forbidden")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        fail("JSON_UTF8", f"request is not strict UTF-8: {exc}")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except SamplingReceiptError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        fail("JSON_PARSE", f"request is not valid JSON: {exc}")
    if type(value) is not dict:
        fail("REQUEST_ROOT", "request root must be an object")
    _depth_and_scalar_profile(value)
    if _canonical_bytes(value, "request") != raw:
        fail("REQUEST_CANONICAL", "request bytes differ from the frozen canonical profile")
    return value


def _require_exact_object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        fail("OBJECT_KEYS", f"{label} field set differs from the frozen profile")
    return value


def _require_sha(value: Any, label: str) -> str:
    if type(value) is not str or SHA_RE.fullmatch(value) is None:
        fail("SHA256", f"{label} must be 64 lowercase hexadecimal characters")
    return value


def _require_label(value: Any, label: str) -> str:
    if type(value) is not str or LABEL_RE.fullmatch(value) is None:
        fail("LABEL", f"{label} is outside the frozen label profile")
    if len(value.encode("utf-8")) > 128:
        fail("LABEL", f"{label} exceeds 128 UTF-8 bytes")
    return value


def _require_utc(value: Any) -> str:
    if type(value) is not str or UTC_RE.fullmatch(value) is None:
        fail("UTC", "created_at_utc must use exact whole-second UTC form")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        fail("UTC", f"created_at_utc is not a real calendar instant: {exc}")
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        fail("UTC", "created_at_utc is not canonical")
    return value


def _read_bound_source(path: Path, label: str) -> bytes:
    try:
        before = os.lstat(path)
    except OSError as exc:
        fail("SOURCE_FILE", f"cannot stat {label}: {exc}")
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        fail("SOURCE_FILE", f"{label} must be one unaliased regular file")
    if before.st_size > MAX_SINGLE_ARTIFACT_BYTES:
        fail("SOURCE_SIZE", f"{label} exceeds the single-artifact cap")
    required_flags = ("O_NOFOLLOW", "O_CLOEXEC")
    if any(not hasattr(os, name) for name in required_flags):
        fail("PLATFORM", "source verification requires O_NOFOLLOW and O_CLOEXEC")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        fail("SOURCE_OPEN", f"cannot open {label}: {exc}")
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            fail("SOURCE_RACE", f"{label} identity changed while opening")
        chunks: list[bytes] = []
        remaining = MAX_SINGLE_ARTIFACT_BYTES + 1
        while remaining:
            chunk = os.read(fd, min(1_048_576, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        after = os.fstat(fd)
        if len(data) > MAX_SINGLE_ARTIFACT_BYTES or after.st_size != len(data):
            fail("SOURCE_SIZE", f"{label} size changed or exceeds the cap")
        if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
            fail("SOURCE_RACE", f"{label} identity changed while reading")
        return data
    finally:
        os.close(fd)


def _execute_bound_dependency(
    path: Path,
    expected_sha256: str,
    label: str,
) -> types.ModuleType:
    """Execute the exact verified source bytes, never a shadow import."""

    data = _read_bound_source(path, label)
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        fail("SOURCE_HASH", f"{label} differs from the frozen dependency")
    module_name = f"_agent_bridge_bound_{label}_{digest[:16]}"
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["__builtins__"] = _bound_dependency_builtins()
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        code = compile(data, str(path), "exec", dont_inherit=True, optimize=0)
        exec(code, module.__dict__)
    except Exception as exc:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        fail("SOURCE_EXECUTION", f"cannot execute exact {label} bytes: {exc}")
    return module


def _load_bound_dependencies() -> tuple[types.ModuleType, types.ModuleType]:
    source_path = Path(__file__).absolute()
    repo_root = source_path.parent.parent.parent
    seed_module = _execute_bound_dependency(
        repo_root / SEED_SOURCE_PATH,
        EXPECTED_SEED_SOURCE_SHA256,
        "sampling_seed_derivation",
    )
    selection_module = _execute_bound_dependency(
        repo_root / SELECTION_SOURCE_PATH,
        EXPECTED_SELECTION_SOURCE_SHA256,
        "sampling_selection",
    )
    expected_constants = (
        (seed_module, "REQUEST_SCHEMA", SEED_REQUEST_SCHEMA),
        (seed_module, "SEED_DOMAIN", SEED_DOMAIN),
        (seed_module, "SEED_MESSAGE_PROFILE", SEED_MESSAGE_PROFILE),
        (selection_module, "REQUEST_SCHEMA", SELECTION_REQUEST_SCHEMA),
        (selection_module, "SELECTION_DOMAIN", SELECTION_DOMAIN),
        (selection_module, "SELECTION_MESSAGE_PROFILE", SELECTION_MESSAGE_PROFILE),
    )
    for module, name, expected in expected_constants:
        if getattr(module, name, None) != expected:
            fail("SOURCE_INTERFACE", f"bound dependency constant drift: {name}")
    if not callable(getattr(seed_module, "derive_sampling_seed", None)):
        fail("SOURCE_INTERFACE", "bound seed dependency lacks derive_sampling_seed")
    if not callable(getattr(selection_module, "select_stratified_cases", None)):
        fail("SOURCE_INTERFACE", "bound selection dependency lacks select_stratified_cases")
    return seed_module, selection_module


def _source_hashes() -> dict[str, str]:
    source_path = Path(__file__).absolute()
    repo_root = source_path.parent.parent.parent
    paths = {
        "contract_digest_profile_sha256": repo_root / PROFILE_PATH,
        "sampling_receipt_schema_sha256": repo_root / RECEIPT_SCHEMA_PATH,
        "sampling_receipt_writer_sha256": source_path,
        "sampling_seed_derivation_sha256": repo_root / SEED_SOURCE_PATH,
        "sampling_selection_algorithm_sha256": repo_root / SELECTION_SOURCE_PATH,
    }
    hashes = {
        label: hashlib.sha256(_read_bound_source(path, label)).hexdigest()
        for label, path in paths.items()
    }
    expected = {
        "contract_digest_profile_sha256": EXPECTED_PROFILE_SHA256,
        "sampling_receipt_schema_sha256": EXPECTED_RECEIPT_SCHEMA_SHA256,
        "sampling_seed_derivation_sha256": EXPECTED_SEED_SOURCE_SHA256,
        "sampling_selection_algorithm_sha256": EXPECTED_SELECTION_SOURCE_SHA256,
    }
    for label, digest in expected.items():
        if hashes[label] != digest:
            fail("SOURCE_HASH", f"{label} differs from the frozen dependency")
    return hashes


def _validate_contract_core(value: Any, source_hashes: dict[str, str]) -> tuple[dict[str, Any], str, str]:
    core = _require_exact_object(value, CONTRACT_CORE_FIELDS, "contract_core")
    if core["schema"] != CONTRACT_CORE_SCHEMA:
        fail("CONTRACT_SCHEMA", "contract_core schema drift")
    trial_id = _require_label(core["trial_id"], "contract_core.trial_id")
    for field in CONTRACT_SHA_FIELDS:
        _require_sha(core[field], f"contract_core.{field}")
    for field, digest in source_hashes.items():
        if core[field] != digest:
            fail("CONTRACT_SOURCE_JOIN", f"contract_core.{field} does not bind this source set")
    core_bytes = _canonical_bytes(core, "contract_core")
    if len(core_bytes) > MAX_CONTRACT_CORE_BYTES:
        fail("CONTRACT_SIZE", "contract_core exceeds the frozen byte cap")
    return core, trial_id, hashlib.sha256(core_bytes).hexdigest()


def _validate_frame(value: Any, core: dict[str, Any], trial_id: str) -> tuple[dict[str, Any], str]:
    frame = _require_exact_object(value, FRAME_FIELDS, "eligible_frame_manifest")
    if frame["schema"] != FRAME_SCHEMA or frame["trial_id"] != trial_id:
        fail("FRAME_IDENTITY", "eligible frame schema or trial_id drift")
    for field in (
        "frame_builder_sha256",
        "inclusion_exclusion_rules_sha256",
        "target_population_definition_sha256",
    ):
        _require_sha(frame[field], f"eligible_frame_manifest.{field}")
        if frame[field] != core[field]:
            fail("FRAME_POLICY_JOIN", f"eligible frame does not bind contract_core.{field}")
    cases = frame["cases"]
    if type(cases) is not list or not 1 <= len(cases) <= MAX_CASES:
        fail("FRAME_CASE_COUNT", f"eligible frame must contain 1..={MAX_CASES} cases")
    seen: set[str] = set()
    for index, row in enumerate(cases):
        _require_exact_object(row, {"case_id", "stratum"}, f"cases[{index}]")
        case_id = row["case_id"]
        if type(case_id) is not str or CASE_RE.fullmatch(case_id) is None:
            fail("CASE_ID", f"cases[{index}].case_id is outside the frozen profile")
        _require_label(row["stratum"], f"cases[{index}].stratum")
        if case_id in seen:
            fail("CASE_DUPLICATE", "eligible frame repeats a case_id")
        seen.add(case_id)
    canonical_rows = sorted(cases, key=lambda row: row["case_id"].encode("utf-8"))
    if cases != canonical_rows:
        fail("FRAME_ORDER", "eligible frame cases must be in UTF-8 case_id order")
    frame_bytes = _canonical_bytes(frame, "eligible_frame_manifest")
    if len(frame_bytes) > MAX_SINGLE_ARTIFACT_BYTES:
        fail("FRAME_SIZE", "eligible frame exceeds the single-artifact cap")
    return frame, hashlib.sha256(frame_bytes).hexdigest()


def _validate_allocations(
    value: Any,
    core: dict[str, Any],
    trial_id: str,
    frame_sha256: str,
) -> tuple[dict[str, Any], str]:
    allocation = _require_exact_object(
        value, ALLOCATION_FIELDS, "strata_allocation_manifest"
    )
    if allocation["schema"] != ALLOCATION_SCHEMA or allocation["trial_id"] != trial_id:
        fail("ALLOCATION_IDENTITY", "allocation schema or trial_id drift")
    if allocation["eligible_frame_manifest_sha256"] != frame_sha256:
        fail("ALLOCATION_FRAME_JOIN", "allocation does not bind the exact eligible frame")
    if allocation["strata_allocation_policy_sha256"] != core["strata_allocation_policy_sha256"]:
        fail("ALLOCATION_POLICY_JOIN", "allocation policy differs from contract core")
    rows = allocation["strata_allocations"]
    if type(rows) is not list or not 1 <= len(rows) <= MAX_STRATA:
        fail("ALLOCATION_COUNT", f"allocation must contain 1..={MAX_STRATA} rows")
    canonical_rows = sorted(rows, key=lambda row: str(row.get("stratum", "")).encode("utf-8") if type(row) is dict else b"")
    if rows != canonical_rows:
        fail("ALLOCATION_ORDER", "allocation rows must be in UTF-8 stratum order")
    allocation_bytes = _canonical_bytes(allocation, "strata_allocation_manifest")
    if len(allocation_bytes) > MAX_SINGLE_ARTIFACT_BYTES:
        fail("ALLOCATION_SIZE", "allocation manifest exceeds the single-artifact cap")
    return allocation, hashlib.sha256(allocation_bytes).hexdigest()


def _expected_selection_manifest(
    schema: str,
    trial_id: str,
    contract_sha256: str,
    frame_sha256: str,
    selection: dict[str, Any],
    rows_key: str,
) -> dict[str, Any]:
    return {
        "schema": schema,
        "trial_id": trial_id,
        "contract_sha256": contract_sha256,
        "eligible_frame_manifest_sha256": frame_sha256,
        "sampling_seed_sha256": selection["sampling_seed_sha256"],
        "selection_commitment_sha256": selection["selection_commitment_sha256"],
        "cases": selection[rows_key],
    }


def _validate_selection_manifest(
    supplied: Any,
    expected: dict[str, Any],
    label: str,
) -> str:
    manifest = _require_exact_object(supplied, SELECTION_MANIFEST_FIELDS, label)
    if manifest != expected:
        fail("SELECTION_MANIFEST_JOIN", f"{label} differs from recomputed selection")
    raw = _canonical_bytes(manifest, label)
    if len(raw) > MAX_SINGLE_ARTIFACT_BYTES:
        fail("SELECTION_MANIFEST_SIZE", f"{label} exceeds the single-artifact cap")
    return hashlib.sha256(raw).hexdigest()


def _verify_selection_commitment(selection: dict[str, Any]) -> None:
    without_commitment = dict(selection)
    commitment = without_commitment.pop("selection_commitment_sha256", None)
    expected = hashlib.sha256(
        _canonical_bytes(without_commitment, "selection result without commitment")
    ).hexdigest()
    if commitment != expected:
        fail("SELECTION_COMMITMENT", "selection commitment does not cover the full envelope")


def _verify_case_grain(selection: dict[str, Any], frame: dict[str, Any]) -> None:
    selected = selection["selected_cases"]
    reserve = selection["reserve_cases"]
    probabilities = selection["case_inclusion_probabilities"]
    weights = selection["case_sampling_weights"]
    selected_ids = [row["case_id"] for row in selected]
    probability_ids = [row["case_id"] for row in probabilities]
    weight_ids = [row["case_id"] for row in weights]
    if selected_ids != probability_ids or selected_ids != weight_ids:
        fail("CASE_GRAIN_JOIN", "selected, probability, and weight case order differs")
    if len(set(selected_ids)) != len(selected_ids):
        fail("CASE_GRAIN_DUPLICATE", "selected case grain is not unique")
    reserve_ids = [row["case_id"] for row in reserve]
    if set(selected_ids) & set(reserve_ids):
        fail("CASE_PARTITION", "selected and reserve cases overlap")
    frame_ids = [row["case_id"] for row in frame["cases"]]
    if set(selected_ids) | set(reserve_ids) != set(frame_ids):
        fail("CASE_PARTITION", "selected and reserve cases do not cover the frame")
    if len(selected_ids) + len(reserve_ids) != len(frame_ids):
        fail("CASE_PARTITION", "selected and reserve case counts differ from frame")
    selected_strata = {row["case_id"]: row["stratum"] for row in selected}
    reserve_strata = {row["case_id"]: row["stratum"] for row in reserve}
    frame_strata = {row["case_id"]: row["stratum"] for row in frame["cases"]}
    if {**selected_strata, **reserve_strata} != frame_strata:
        fail("CASE_STRATUM_JOIN", "selection changes a frame stratum")
    ranks: dict[str, list[int]] = {}
    for row in reserve:
        ranks.setdefault(row["stratum"], []).append(row["reserve_rank"])
    for stratum_name, values in ranks.items():
        if values != list(range(1, len(values) + 1)):
            fail("RESERVE_RANK", f"reserve ranks are not contiguous in {stratum_name}")
    strata = {row["stratum"]: row for row in selection["strata"]}
    for probability, weight in zip(probabilities, weights, strict=True):
        case_id = probability["case_id"]
        stratum_row = strata[selected_strata[case_id]]
        expected_probability = (
            stratum_row["sample_size"],
            stratum_row["population_size"],
        )
        divisor = math.gcd(*expected_probability)
        expected_probability = (
            expected_probability[0] // divisor,
            expected_probability[1] // divisor,
        )
        if (probability["numerator"], probability["denominator"]) != expected_probability:
            fail("PROBABILITY", "case probability differs from exact n_h/N_h")
        if (weight["numerator"], weight["denominator"]) != expected_probability[::-1]:
            fail("WEIGHT", "case weight differs from exact N_h/n_h")


def build_sampling_receipt(request_bytes: Any) -> BuiltSamplingReceipt:
    request = parse_canonical_request_bytes(request_bytes)
    _require_exact_object(request, REQUEST_FIELDS, "request")
    if request["schema"] != REQUEST_SCHEMA:
        fail("REQUEST_SCHEMA", "sampling receipt write request schema drift")
    source_hashes = _source_hashes()
    seed_module, selection_module = _load_bound_dependencies()
    core, trial_id, contract_sha256 = _validate_contract_core(
        request["contract_core"], source_hashes
    )
    created_at_utc = _require_utc(request["created_at_utc"])
    frame, frame_sha256 = _validate_frame(
        request["eligible_frame_manifest"], core, trial_id
    )
    allocation, allocation_sha256 = _validate_allocations(
        request["strata_allocation_manifest"], core, trial_id, frame_sha256
    )
    external_entropy_sha256 = _require_sha(
        request["external_entropy_sha256"], "external_entropy_sha256"
    )
    frame_receipt_sha256 = _require_sha(
        request["frame_o_excl_receipt_sha256"], "frame_o_excl_receipt_sha256"
    )
    entropy_receipt_sha256 = _require_sha(
        request["seed_entropy_receipt_sha256"], "seed_entropy_receipt_sha256"
    )

    try:
        seed = seed_module.derive_sampling_seed(
            {
                "schema": SEED_REQUEST_SCHEMA,
                "contract_sha256": contract_sha256,
                "trial_id": trial_id,
                "eligible_frame_manifest_sha256": frame_sha256,
                "external_entropy_sha256": external_entropy_sha256,
            }
        )
        selection = selection_module.select_stratified_cases(
            {
                "schema": SELECTION_REQUEST_SCHEMA,
                "eligible_frame_manifest_sha256": frame_sha256,
                "cases": frame["cases"],
                "strata_allocations": allocation["strata_allocations"],
            },
            seed.seed_bytes,
        )
    except (seed_module.SamplingSeedError, selection_module.SamplingSelectionError) as exc:
        fail(exc.code, f"bound seed/selection dependency rejected input: {exc}")
    if selection["sampling_seed_sha256"] != seed.public_result["sampling_seed_sha256"]:
        fail("SEED_SELECTION_JOIN", "seed derivation and selection seed commitments differ")
    if selection["eligible_frame_manifest_sha256"] != frame_sha256:
        fail("FRAME_SELECTION_JOIN", "selection frame differs from exact manifest")
    _verify_selection_commitment(selection)
    _verify_case_grain(selection, frame)

    expected_selected = _expected_selection_manifest(
        SELECTED_SCHEMA,
        trial_id,
        contract_sha256,
        frame_sha256,
        selection,
        "selected_cases",
    )
    expected_reserve = _expected_selection_manifest(
        RESERVE_SCHEMA,
        trial_id,
        contract_sha256,
        frame_sha256,
        selection,
        "reserve_cases",
    )
    selected_sha256 = _validate_selection_manifest(
        request["selected_case_manifest"], expected_selected, "selected_case_manifest"
    )
    reserve_sha256 = _validate_selection_manifest(
        request["reserve_manifest"], expected_reserve, "reserve_manifest"
    )

    receipt = {
        "anti_shopping_order_verified": False,
        "schema": RECEIPT_SCHEMA,
        "trial_id": trial_id,
        "contract_sha256": contract_sha256,
        "contract_digest_profile_sha256": source_hashes[
            "contract_digest_profile_sha256"
        ],
        "receipt_schema_sha256": source_hashes["sampling_receipt_schema_sha256"],
        "receipt_writer_sha256": source_hashes["sampling_receipt_writer_sha256"],
        "created_at_utc": created_at_utc,
        "frame_o_excl_receipt_sha256": frame_receipt_sha256,
        "pre_output_timing_verified": False,
        "seed_entropy_receipt_sha256": entropy_receipt_sha256,
        "external_entropy_sha256": external_entropy_sha256,
        "seed_derivation_sha256": source_hashes["sampling_seed_derivation_sha256"],
        "seed_derivation_domain": SEED_DOMAIN,
        "seed_derivation_message_profile": SEED_MESSAGE_PROFILE,
        "sampling_seed_sha256": seed.public_result["sampling_seed_sha256"],
        "sampling_selection_algorithm_sha256": source_hashes[
            "sampling_selection_algorithm_sha256"
        ],
        "sampling_selection_domain": SELECTION_DOMAIN,
        "sampling_selection_message": SELECTION_MESSAGE_PROFILE,
        "selection_commitment_sha256": selection["selection_commitment_sha256"],
        "eligible_frame_manifest_sha256": frame_sha256,
        "strata_allocation_manifest_sha256": allocation_sha256,
        "selected_case_manifest_sha256": selected_sha256,
        "reserve_manifest_sha256": reserve_sha256,
        "case_inclusion_probabilities": selection["case_inclusion_probabilities"],
        "case_sampling_weights": selection["case_sampling_weights"],
        "receipt_precedes_first_condition_output": True,
        "condition_output_authorized": False,
    }
    if set(receipt) != RECEIPT_FIELDS:
        fail("INTERNAL_RECEIPT_FIELDS", "constructed receipt field set drift")
    canonical = _canonical_bytes(receipt, "sampling receipt")
    if len(canonical) > MAX_RECEIPT_BYTES:
        fail("RECEIPT_SIZE", "sampling receipt exceeds the frozen output cap")
    return BuiltSamplingReceipt(
        receipt=receipt,
        canonical_bytes=canonical,
        canonical_request_bytes=request_bytes,
        receipt_sha256=hashlib.sha256(canonical).hexdigest(),
        selected_case_count=len(selection["selected_cases"]),
        reserve_case_count=len(selection["reserve_cases"]),
    )


def _verify_private_directory(directory_fd: Any) -> os.stat_result:
    if type(directory_fd) is not int or directory_fd < 0:
        fail("DIRECTORY_FD", "directory_fd must be an open nonnegative integer fd")
    required = ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC")
    if any(not hasattr(os, name) for name in required):
        fail("PLATFORM", "O_EXCL writer requires O_DIRECTORY, O_NOFOLLOW, and O_CLOEXEC")
    if os.open not in os.supports_dir_fd:
        fail("PLATFORM", "this platform does not support openat-style dir_fd")
    try:
        info = os.fstat(directory_fd)
    except OSError as exc:
        fail("DIRECTORY_FD", f"cannot stat directory fd: {exc}")
    if not stat.S_ISDIR(info.st_mode):
        fail("DIRECTORY_TYPE", "directory_fd does not reference a directory")
    if info.st_uid != os.geteuid():
        fail("DIRECTORY_OWNER", "private directory is not owned by current euid")
    if stat.S_IMODE(info.st_mode) != 0o700:
        fail("DIRECTORY_MODE", "private directory mode must be exactly 0700")
    return info


def write_sampling_receipt_o_excl(
    directory_fd: Any,
    built: Any,
) -> ReceiptWriteObservation:
    if type(built) is not BuiltSamplingReceipt:
        fail("BUILT_TYPE", "built must be an exact BuiltSamplingReceipt")
    recomputed = build_sampling_receipt(built.canonical_request_bytes)
    if (
        built.receipt != recomputed.receipt
        or built.canonical_bytes != recomputed.canonical_bytes
        or built.receipt_sha256 != recomputed.receipt_sha256
        or built.selected_case_count != recomputed.selected_case_count
        or built.reserve_case_count != recomputed.reserve_case_count
    ):
        fail("BUILT_RECOMPUTE", "built receipt differs from full request recomputation")
    canonical = recomputed.canonical_bytes
    receipt_sha256 = recomputed.receipt_sha256
    if (
        recomputed.receipt["condition_output_authorized"] is not False
        or recomputed.receipt["anti_shopping_order_verified"] is not False
        or recomputed.receipt["pre_output_timing_verified"] is not False
    ):
        fail("INTERNAL_AUTHORITY", "source-only receipt overstates runtime authority")
    directory_before = _verify_private_directory(directory_fd)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    fd: int | None = None
    created = False
    try:
        try:
            fd = os.open(RECEIPT_BASENAME, flags, 0o600, dir_fd=directory_fd)
            created = True
        except FileExistsError:
            fail("RECEIPT_EXISTS", "sampling receipt leaf already exists; retry is forbidden")
        except OSError as exc:
            fail("RECEIPT_CREATE", f"cannot create sampling receipt: {exc}")
        opened = os.fstat(fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_uid != os.geteuid()
            or opened.st_nlink != 1
        ):
            fail("RECEIPT_FILE_PROFILE", "new receipt file identity or mode is unsafe")
        view = memoryview(canonical)
        offset = 0
        while offset < len(view):
            written = os.write(fd, view[offset:])
            if written <= 0:
                fail("RECEIPT_SHORT_WRITE", "receipt write made no forward progress")
            offset += written
        after_write = os.fstat(fd)
        if (
            (after_write.st_dev, after_write.st_ino) != (opened.st_dev, opened.st_ino)
            or after_write.st_size != len(canonical)
            or after_write.st_nlink != 1
            or stat.S_IMODE(after_write.st_mode) != 0o600
        ):
            fail("RECEIPT_FILE_DRIFT", "receipt file changed during write")
        os.fsync(fd)
        os.fchmod(fd, 0o400)
        sealed = os.fstat(fd)
        if (
            (sealed.st_dev, sealed.st_ino) != (opened.st_dev, opened.st_ino)
            or sealed.st_size != len(canonical)
            or sealed.st_nlink != 1
            or stat.S_IMODE(sealed.st_mode) != 0o400
        ):
            fail("RECEIPT_SEAL", "receipt did not enter the final read-only mode")
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.fsync(directory_fd)

        read_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        read_fd = os.open(RECEIPT_BASENAME, read_flags, dir_fd=directory_fd)
        try:
            reread_info = os.fstat(read_fd)
            if (
                (reread_info.st_dev, reread_info.st_ino)
                != (opened.st_dev, opened.st_ino)
                or reread_info.st_size != len(canonical)
                or reread_info.st_nlink != 1
                or stat.S_IMODE(reread_info.st_mode) != 0o400
            ):
                fail("RECEIPT_REREAD_IDENTITY", "receipt identity changed after fsync")
            chunks: list[bytes] = []
            remaining = len(canonical) + 1
            while remaining:
                chunk = os.read(read_fd, min(1_048_576, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            reread = b"".join(chunks)
            if reread != canonical or hashlib.sha256(reread).hexdigest() != receipt_sha256:
                fail("RECEIPT_REREAD_BYTES", "receipt bytes differ after fsync")
        finally:
            os.close(read_fd)
        directory_after = _verify_private_directory(directory_fd)
        if (
            directory_after.st_dev,
            directory_after.st_ino,
            stat.S_IMODE(directory_after.st_mode),
        ) != (
            directory_before.st_dev,
            directory_before.st_ino,
            stat.S_IMODE(directory_before.st_mode),
        ):
            fail("DIRECTORY_DRIFT", "private directory identity changed during write")
    except SamplingReceiptError:
        raise
    except OSError as exc:
        suffix = "partial receipt retained; trial must abort" if created else "no receipt created"
        fail("RECEIPT_IO", f"receipt I/O failed ({suffix}): {exc}")
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

    return ReceiptWriteObservation(
        receipt_sha256=receipt_sha256,
        receipt_size_bytes=len(canonical),
        selected_case_count=recomputed.selected_case_count,
        reserve_case_count=recomputed.reserve_case_count,
        receipt_basename=RECEIPT_BASENAME,
        write_flags_profile=WRITE_FLAGS_PROFILE,
        create_file_mode_octal="0600",
        final_file_mode_octal="0400",
        content_fsync_completed=True,
        read_only_seal_fsync_completed=True,
        parent_directory_fsync_completed=True,
        reread_identity_and_bytes_verified=True,
        condition_output_authorized=False,
        anti_shopping_order_verified=False,
        pre_output_timing_verified=False,
        trusted_clock_verified=False,
        evidence_scope=WRITE_EVIDENCE_SCOPE,
    )


def build_and_write_sampling_receipt(
    request_bytes: Any,
    directory_fd: Any,
) -> ReceiptWriteObservation:
    return write_sampling_receipt_o_excl(
        directory_fd,
        build_sampling_receipt(request_bytes),
    )
