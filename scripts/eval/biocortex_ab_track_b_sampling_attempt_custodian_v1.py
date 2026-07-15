#!/usr/bin/env python3
"""Local crash-atomic Track B sampling-attempt custodian reference profile.

This module provides an executable append-only SQLite state machine for public
synthetic validation.  It is deliberately not a production custodian: a local
database can be restored from an old snapshot, so the returned receipts always
say that external owner trust and global single use are unverified.  No API in
this module authorizes condition output.  The local profile requires a
dedicated effective user and does not treat same-euid callers as an isolation
boundary.

Normal mutation calls never create a missing store.  Explicit initialization
is separate, create-new only, and pins one custodian generation and policy
configuration.  Registration, claim, and terminal outcome are immutable rows
in one transactionally consistent ledger.

Terminal success requires exact write-request bytes and a private receipt
directory descriptor.  The custodian replays the hash-pinned writer, rereads
and fsyncs the sealed receipt, and derives the local observation itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
import threading
import types
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


PROTOCOL_VERSION = 1
APPLICATION_ID = 0x4142_4331  # ASCII "ABC1"
USER_VERSION = 1
STORE_BASENAME = "track-b-sampling-attempt-custodian-v1.sqlite3"

REGISTRATION_REQUEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_owner_trial_registration_request.v1"
)
CLAIM_REQUEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_sampling_attempt_namespace_claim_request.v1"
)
OUTCOME_REQUEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_sampling_write_outcome_request.v1"
)
REGISTRATION_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_owner_trial_registration_receipt.v1"
)
CLAIM_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_sampling_attempt_namespace_claim_receipt.v1"
)
OUTCOME_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_sampling_write_outcome_custodian_receipt.v1"
)
SAMPLING_RECEIPT_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_receipt.v1"

GLOBAL_TRIAL_KEY_DOMAIN = "agent-bridge/track-b/global-trial-key/v1"
SAMPLING_ATTEMPT_NAMESPACE_DOMAIN = (
    "agent-bridge/track-b/sampling-attempt-namespace/v1"
)
SAMPLING_EVENT_DOMAIN = "agent-bridge/track-b/sampling-event/v1"
CUSTODY_TARGET_DOMAIN = "agent-bridge/track-b/custody-target/v1"
GLOBAL_TRIAL_KEY_MESSAGE = "domain_utf8_NUL_trial_id_utf8"
SAMPLING_ATTEMPT_NAMESPACE_MESSAGE = "domain_utf8_NUL_trial_id_utf8"
SAMPLING_EVENT_MESSAGE = (
    "domain_utf8_NUL_contract_core_sha256_ascii_NUL_trial_id_utf8_NUL_"
    "eligible_frame_sha256_ascii_NUL_strata_allocation_sha256_ascii"
)
CUSTODY_TARGET_MESSAGE = (
    "domain_utf8_NUL_custodian_instance_sha256_ascii_NUL_"
    "sampling_attempt_namespace_sha256_ascii"
)

REGISTRATION_SCHEMA_SHA256 = (
    "98f6e2c539758c147d9c0d5050c88123f38e975539914e7e926421df10ac9eea"
)
CLAIM_SCHEMA_SHA256 = (
    "baa08930421ca6c5a1e1e4835ad95e027b147592d3765371d0028956b96d1eb4"
)
OUTCOME_SCHEMA_SHA256 = (
    "93d9b7ebda7f0fd6c24b1a1d0823866128db4885afe7f507b1ae8f6da7e4cb7d"
)

MAX_REQUEST_BYTES = 16_777_216
MAX_RECEIPT_BYTES = 16_777_216
MAX_JSON_DEPTH = 40
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_BUSY_TIMEOUT_MS = 60_000

_SQLITE_CONNECT_LOCK = threading.Lock()

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
ABORT_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

REGISTRATION_REQUEST_FIELDS = {
    "admission_policy_sha256",
    "contract_core_sha256",
    "eligible_frame_manifest_sha256",
    "owner_authorization_receipt_sha256",
    "owner_freeze_receipt_sha256",
    "owner_trust_policy_sha256",
    "protocol_version",
    "registered_at_utc",
    "sampling_attempt_namespace_sha256",
    "sampling_event_sha256",
    "schema",
    "strata_allocation_manifest_sha256",
    "trial_id",
}
CLAIM_REQUEST_FIELDS = {
    "admission_policy_sha256",
    "claimed_at_utc",
    "contract_core_sha256",
    "custody_target_sha256",
    "eligible_frame_manifest_sha256",
    "owner_trial_registration_receipt_sha256",
    "protocol_version",
    "sampling_attempt_namespace_sha256",
    "sampling_event_sha256",
    "schema",
    "strata_allocation_manifest_sha256",
    "trial_id",
}
OUTCOME_REQUEST_FIELDS = {
    "abort_reason_code",
    "admission_policy_sha256",
    "contract_core_sha256",
    "custody_target_sha256",
    "eligible_frame_manifest_sha256",
    "external_entropy_sha256",
    "failure_evidence_sha256",
    "finalized_at_utc",
    "outcome",
    "owner_trial_registration_receipt_sha256",
    "protocol_version",
    "sampling_attempt_namespace_claim_receipt_sha256",
    "sampling_attempt_namespace_sha256",
    "sampling_event_sha256",
    "sampling_write_request_sha256",
    "schema",
    "strata_allocation_manifest_sha256",
    "trial_id",
    "write_state",
}

REGISTRATION_RECEIPT_FIELDS = {
    "admission_policy_sha256",
    "authority_scope",
    "condition_output_authorized",
    "contract_core_sha256",
    "cross_protocol_trial_id_reuse_forbidden",
    "custodian_authority_sha256",
    "custodian_id",
    "custodian_instance_sha256",
    "custodian_sequence",
    "custodian_source_sha256",
    "custodian_store_schema_sha256",
    "eligible_frame_manifest_sha256",
    "external_global_single_use_verified",
    "external_owner_trust_verified",
    "global_trial_key_sha256",
    "local_registry_trial_id_consumed",
    "owner_authorization_receipt_sha256",
    "owner_freeze_receipt_sha256",
    "owner_trust_policy_sha256",
    "protocol_version",
    "receipt_schema_sha256",
    "registered_at_utc",
    "sampling_attempt_namespace_sha256",
    "sampling_event_sha256",
    "schema",
    "strata_allocation_manifest_sha256",
    "trial_id",
}
CLAIM_RECEIPT_FIELDS = {
    "admission_policy_sha256",
    "authority_scope",
    "claimed_at_utc",
    "condition_output_authorized",
    "contract_core_sha256",
    "custodian_authority_sha256",
    "custodian_id",
    "custodian_instance_sha256",
    "custodian_sequence",
    "custodian_source_sha256",
    "custodian_store_schema_sha256",
    "custody_target_sha256",
    "eligible_frame_manifest_sha256",
    "external_entropy_bound",
    "external_global_single_use_verified",
    "first_condition_output_guard_required",
    "live_sampling_write_authorized",
    "local_namespace_claim_committed",
    "owner_trial_registration_receipt_sha256",
    "protocol_version",
    "receipt_schema_sha256",
    "same_namespace_sampling_retry_forbidden",
    "sampling_attempt_namespace_sha256",
    "sampling_event_sha256",
    "sampling_write_outcome_status",
    "schema",
    "strata_allocation_manifest_sha256",
    "trial_id",
}
OUTCOME_RECEIPT_FIELDS = {
    "abort_reason_code",
    "admission_policy_sha256",
    "authority_scope",
    "condition_output_authorized",
    "contract_core_sha256",
    "custodian_authority_sha256",
    "custodian_id",
    "custodian_instance_sha256",
    "custodian_sequence",
    "custodian_source_sha256",
    "custodian_store_schema_sha256",
    "custody_target_sha256",
    "eligible_frame_manifest_sha256",
    "external_entropy_sha256",
    "external_global_single_use_verified",
    "failure_evidence_sha256",
    "finalized_at_utc",
    "first_condition_output_guard_required",
    "outcome",
    "owner_trial_registration_receipt_sha256",
    "protocol_version",
    "receipt_schema_sha256",
    "same_namespace_sampling_retry_forbidden",
    "sampling_attempt_namespace_claim_receipt_sha256",
    "sampling_attempt_namespace_sha256",
    "sampling_event_sha256",
    "sampling_receipt_sha256",
    "sampling_write_observation_sha256",
    "sampling_write_request_sha256",
    "schema",
    "strata_allocation_manifest_sha256",
    "terminal",
    "trial_id",
    "write_state",
}

SAMPLING_RECEIPT_FIELDS = {
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
WRITE_OBSERVATION_FIELDS = {
    "anti_shopping_order_verified",
    "condition_output_authorized",
    "evidence_scope",
    "parent_directory_fsync_completed_by_custodian",
    "pre_output_timing_verified",
    "receipt_basename",
    "receipt_directory_entry_set_verified",
    "receipt_directory_mode_octal",
    "receipt_directory_owner_euid_verified",
    "receipt_file_fsync_completed_by_custodian",
    "receipt_file_mode_octal",
    "receipt_file_owner_euid_verified",
    "receipt_file_single_link_verified",
    "receipt_sha256",
    "receipt_size_bytes",
    "reserve_case_count",
    "reread_identity_and_bytes_verified_by_custodian",
    "sampling_receipt_writer_replay_verified",
    "sampling_write_request_sha256",
    "selected_case_count",
    "trusted_clock_verified",
}


SCHEMA_SQL = r"""
CREATE TABLE custodian_meta_v1 (
    singleton INTEGER NOT NULL PRIMARY KEY CHECK (singleton = 1),
    registry_generation_sha256 TEXT NOT NULL CHECK (length(registry_generation_sha256) = 64),
    custodian_id TEXT NOT NULL,
    custodian_authority_sha256 TEXT NOT NULL CHECK (length(custodian_authority_sha256) = 64),
    custodian_instance_sha256 TEXT NOT NULL CHECK (length(custodian_instance_sha256) = 64),
    owner_trust_policy_sha256 TEXT NOT NULL CHECK (length(owner_trust_policy_sha256) = 64),
    admission_policy_sha256 TEXT NOT NULL CHECK (length(admission_policy_sha256) = 64),
    sampling_receipt_schema_sha256 TEXT NOT NULL CHECK (length(sampling_receipt_schema_sha256) = 64),
    sampling_receipt_writer_sha256 TEXT NOT NULL CHECK (length(sampling_receipt_writer_sha256) = 64),
    initialized_at_utc TEXT NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE custodian_ledger_events_v1 (
    custodian_sequence INTEGER NOT NULL PRIMARY KEY CHECK (custodian_sequence >= 1),
    event_type TEXT NOT NULL CHECK (event_type IN ('REGISTRATION', 'CLAIM', 'OUTCOME')),
    trial_id TEXT NOT NULL,
    sampling_attempt_namespace_sha256 TEXT NOT NULL CHECK (length(sampling_attempt_namespace_sha256) = 64),
    request_sha256 TEXT NOT NULL UNIQUE CHECK (length(request_sha256) = 64),
    receipt_sha256 TEXT NOT NULL UNIQUE CHECK (length(receipt_sha256) = 64)
) STRICT, WITHOUT ROWID;

CREATE TABLE owner_trial_registrations_v1 (
    trial_id TEXT NOT NULL PRIMARY KEY,
    protocol_version INTEGER NOT NULL CHECK (protocol_version = 1),
    global_trial_key_sha256 TEXT NOT NULL UNIQUE CHECK (length(global_trial_key_sha256) = 64),
    sampling_attempt_namespace_sha256 TEXT NOT NULL UNIQUE CHECK (length(sampling_attempt_namespace_sha256) = 64),
    admission_policy_sha256 TEXT NOT NULL CHECK (length(admission_policy_sha256) = 64),
    contract_core_sha256 TEXT NOT NULL CHECK (length(contract_core_sha256) = 64),
    eligible_frame_manifest_sha256 TEXT NOT NULL CHECK (length(eligible_frame_manifest_sha256) = 64),
    strata_allocation_manifest_sha256 TEXT NOT NULL CHECK (length(strata_allocation_manifest_sha256) = 64),
    sampling_event_sha256 TEXT NOT NULL UNIQUE CHECK (length(sampling_event_sha256) = 64),
    owner_authorization_receipt_sha256 TEXT NOT NULL UNIQUE CHECK (length(owner_authorization_receipt_sha256) = 64),
    owner_freeze_receipt_sha256 TEXT NOT NULL UNIQUE CHECK (length(owner_freeze_receipt_sha256) = 64),
    owner_trust_policy_sha256 TEXT NOT NULL CHECK (length(owner_trust_policy_sha256) = 64),
    registered_at_utc TEXT NOT NULL,
    custodian_sequence INTEGER NOT NULL UNIQUE REFERENCES custodian_ledger_events_v1(custodian_sequence),
    request_sha256 TEXT NOT NULL UNIQUE CHECK (length(request_sha256) = 64),
    request_bytes BLOB NOT NULL,
    receipt_sha256 TEXT NOT NULL UNIQUE CHECK (length(receipt_sha256) = 64),
    receipt_bytes BLOB NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE sampling_attempt_claims_v1 (
    sampling_attempt_namespace_sha256 TEXT NOT NULL PRIMARY KEY CHECK (length(sampling_attempt_namespace_sha256) = 64),
    trial_id TEXT NOT NULL UNIQUE REFERENCES owner_trial_registrations_v1(trial_id),
    protocol_version INTEGER NOT NULL CHECK (protocol_version = 1),
    owner_trial_registration_receipt_sha256 TEXT NOT NULL UNIQUE CHECK (length(owner_trial_registration_receipt_sha256) = 64),
    admission_policy_sha256 TEXT NOT NULL CHECK (length(admission_policy_sha256) = 64),
    contract_core_sha256 TEXT NOT NULL CHECK (length(contract_core_sha256) = 64),
    eligible_frame_manifest_sha256 TEXT NOT NULL CHECK (length(eligible_frame_manifest_sha256) = 64),
    strata_allocation_manifest_sha256 TEXT NOT NULL CHECK (length(strata_allocation_manifest_sha256) = 64),
    sampling_event_sha256 TEXT NOT NULL UNIQUE CHECK (length(sampling_event_sha256) = 64),
    custody_target_sha256 TEXT NOT NULL UNIQUE CHECK (length(custody_target_sha256) = 64),
    claimed_at_utc TEXT NOT NULL,
    custodian_sequence INTEGER NOT NULL UNIQUE REFERENCES custodian_ledger_events_v1(custodian_sequence),
    request_sha256 TEXT NOT NULL UNIQUE CHECK (length(request_sha256) = 64),
    request_bytes BLOB NOT NULL,
    receipt_sha256 TEXT NOT NULL UNIQUE CHECK (length(receipt_sha256) = 64),
    receipt_bytes BLOB NOT NULL
) STRICT, WITHOUT ROWID;

CREATE TABLE sampling_attempt_outcomes_v1 (
    sampling_attempt_namespace_sha256 TEXT NOT NULL PRIMARY KEY REFERENCES sampling_attempt_claims_v1(sampling_attempt_namespace_sha256),
    trial_id TEXT NOT NULL UNIQUE,
    protocol_version INTEGER NOT NULL CHECK (protocol_version = 1),
    owner_trial_registration_receipt_sha256 TEXT NOT NULL UNIQUE CHECK (length(owner_trial_registration_receipt_sha256) = 64),
    sampling_attempt_namespace_claim_receipt_sha256 TEXT NOT NULL UNIQUE CHECK (length(sampling_attempt_namespace_claim_receipt_sha256) = 64),
    admission_policy_sha256 TEXT NOT NULL CHECK (length(admission_policy_sha256) = 64),
    contract_core_sha256 TEXT NOT NULL CHECK (length(contract_core_sha256) = 64),
    eligible_frame_manifest_sha256 TEXT NOT NULL CHECK (length(eligible_frame_manifest_sha256) = 64),
    strata_allocation_manifest_sha256 TEXT NOT NULL CHECK (length(strata_allocation_manifest_sha256) = 64),
    sampling_event_sha256 TEXT NOT NULL UNIQUE CHECK (length(sampling_event_sha256) = 64),
    custody_target_sha256 TEXT NOT NULL UNIQUE CHECK (length(custody_target_sha256) = 64),
    outcome TEXT NOT NULL CHECK (outcome IN ('SUCCESS', 'TERMINAL_ABORT')),
    write_state TEXT NOT NULL CHECK (write_state IN ('COMPLETE_DURABLE_OBSERVED', 'NOT_STARTED', 'PARTIAL_OR_AMBIGUOUS', 'PROCESS_DEATH_RECONCILIATION', 'TIMEOUT_WORKER_FENCED')),
    external_entropy_sha256 TEXT CHECK (external_entropy_sha256 IS NULL OR length(external_entropy_sha256) = 64),
    sampling_write_request_sha256 TEXT CHECK (sampling_write_request_sha256 IS NULL OR length(sampling_write_request_sha256) = 64),
    sampling_receipt_sha256 TEXT CHECK (sampling_receipt_sha256 IS NULL OR length(sampling_receipt_sha256) = 64),
    sampling_receipt_bytes BLOB,
    sampling_write_observation_sha256 TEXT CHECK (sampling_write_observation_sha256 IS NULL OR length(sampling_write_observation_sha256) = 64),
    sampling_write_observation_bytes BLOB,
    abort_reason_code TEXT,
    failure_evidence_sha256 TEXT CHECK (failure_evidence_sha256 IS NULL OR length(failure_evidence_sha256) = 64),
    finalized_at_utc TEXT NOT NULL,
    custodian_sequence INTEGER NOT NULL UNIQUE REFERENCES custodian_ledger_events_v1(custodian_sequence),
    request_sha256 TEXT NOT NULL UNIQUE CHECK (length(request_sha256) = 64),
    request_bytes BLOB NOT NULL,
    receipt_sha256 TEXT NOT NULL UNIQUE CHECK (length(receipt_sha256) = 64),
    receipt_bytes BLOB NOT NULL,
    CHECK (
      (outcome = 'SUCCESS'
       AND write_state = 'COMPLETE_DURABLE_OBSERVED'
       AND external_entropy_sha256 IS NOT NULL
       AND sampling_write_request_sha256 IS NOT NULL
       AND sampling_receipt_sha256 IS NOT NULL
       AND sampling_receipt_bytes IS NOT NULL
       AND sampling_write_observation_sha256 IS NOT NULL
       AND sampling_write_observation_bytes IS NOT NULL
       AND abort_reason_code IS NULL
       AND failure_evidence_sha256 IS NULL)
      OR
      (outcome = 'TERMINAL_ABORT'
       AND write_state != 'COMPLETE_DURABLE_OBSERVED'
       AND sampling_receipt_sha256 IS NULL
       AND sampling_receipt_bytes IS NULL
       AND sampling_write_observation_sha256 IS NULL
       AND sampling_write_observation_bytes IS NULL
       AND abort_reason_code IS NOT NULL
       AND failure_evidence_sha256 IS NOT NULL)
    )
) STRICT, WITHOUT ROWID;

CREATE TRIGGER custodian_meta_v1_no_insert BEFORE INSERT ON custodian_meta_v1
WHEN EXISTS (SELECT 1 FROM custodian_meta_v1)
BEGIN SELECT RAISE(ABORT, 'custodian metadata is immutable'); END;
CREATE TRIGGER custodian_meta_v1_no_update BEFORE UPDATE ON custodian_meta_v1
BEGIN SELECT RAISE(ABORT, 'custodian metadata is immutable'); END;
CREATE TRIGGER custodian_meta_v1_no_delete BEFORE DELETE ON custodian_meta_v1
BEGIN SELECT RAISE(ABORT, 'custodian metadata is permanent'); END;
CREATE TRIGGER custodian_ledger_events_v1_no_update BEFORE UPDATE ON custodian_ledger_events_v1
BEGIN SELECT RAISE(ABORT, 'custodian ledger events are immutable'); END;
CREATE TRIGGER custodian_ledger_events_v1_no_delete BEFORE DELETE ON custodian_ledger_events_v1
BEGIN SELECT RAISE(ABORT, 'custodian ledger events are permanent'); END;
CREATE TRIGGER owner_trial_registrations_v1_no_update BEFORE UPDATE ON owner_trial_registrations_v1
BEGIN SELECT RAISE(ABORT, 'owner trial registrations are immutable'); END;
CREATE TRIGGER owner_trial_registrations_v1_no_delete BEFORE DELETE ON owner_trial_registrations_v1
BEGIN SELECT RAISE(ABORT, 'owner trial registrations are permanent'); END;
CREATE TRIGGER sampling_attempt_claims_v1_no_update BEFORE UPDATE ON sampling_attempt_claims_v1
BEGIN SELECT RAISE(ABORT, 'sampling attempt claims are immutable'); END;
CREATE TRIGGER sampling_attempt_claims_v1_no_delete BEFORE DELETE ON sampling_attempt_claims_v1
BEGIN SELECT RAISE(ABORT, 'sampling attempt claims are permanent'); END;
CREATE TRIGGER sampling_attempt_outcomes_v1_no_update BEFORE UPDATE ON sampling_attempt_outcomes_v1
BEGIN SELECT RAISE(ABORT, 'sampling attempt outcomes are immutable'); END;
CREATE TRIGGER sampling_attempt_outcomes_v1_no_delete BEFORE DELETE ON sampling_attempt_outcomes_v1
BEGIN SELECT RAISE(ABORT, 'sampling attempt outcomes are permanent'); END;
"""


class CustodianError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise CustodianError(code, message)


@dataclass(frozen=True)
class CustodianConfig:
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
class StoredReceipt:
    receipt_sha256: str
    canonical_bytes: bytes
    receipt: dict[str, Any]


FaultHook = Callable[[str], None] | None


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
        fail("JSON_CANONICAL", f"{label} cannot be serialized: {exc}")


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("JSON_DUPLICATE_KEY", f"duplicate key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    fail("JSON_NONFINITE", f"non-finite number {value!r}")


def _check_shape(value: Any, depth: int = 1) -> None:
    if depth > MAX_JSON_DEPTH:
        fail("JSON_DEPTH", "JSON depth exceeds the frozen cap")
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            fail("JSON_KEY", "JSON object key is not a string")
        for item in value.values():
            _check_shape(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _check_shape(item, depth + 1)
    elif value is None or type(value) in {str, bool}:
        return
    elif type(value) is int:
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            fail("JSON_INTEGER", "integer exceeds interoperable safe range")
    else:
        fail("JSON_SCALAR", f"unsupported JSON scalar {type(value).__name__}")


def _parse_canonical(raw: Any, fields: set[str], schema: str, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_REQUEST_BYTES:
        fail("REQUEST_BYTES", f"{label} must be bounded exact bytes")
    if raw.startswith(b"\xef\xbb\xbf"):
        fail("JSON_BOM", f"{label} has a forbidden UTF-8 BOM")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_pairs,
            parse_constant=_reject_constant,
        )
    except CustodianError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        fail("JSON_PARSE", f"cannot parse {label}: {exc}")
    if type(value) is not dict or set(value) != fields:
        fail("REQUEST_FIELDS", f"{label} field set drift")
    _check_shape(value)
    if _canonical_bytes(value, label) != raw:
        fail("REQUEST_CANONICAL", f"{label} is not canonical JSON")
    if value["schema"] != schema:
        fail("REQUEST_SCHEMA", f"{label} schema drift")
    return value


def _require_sha(value: Any, label: str) -> str:
    if (
        type(value) is not str
        or SHA_RE.fullmatch(value) is None
        or value == "0" * 64
    ):
        fail("SHA256", f"{label} is not lowercase SHA-256")
    return value


def _require_label(value: Any, label: str) -> str:
    if type(value) is not str or LABEL_RE.fullmatch(value) is None:
        fail("LABEL", f"{label} is outside the frozen label profile")
    if len(value.encode("utf-8")) > 128:
        fail("LABEL", f"{label} exceeds 128 UTF-8 bytes")
    return value


def _require_utc(value: Any, label: str) -> datetime:
    if type(value) is not str or UTC_RE.fullmatch(value) is None:
        fail("UTC", f"{label} is not whole-second UTC")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        fail("UTC", f"{label} is not a real instant: {exc}")
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        fail("UTC", f"{label} is not canonical")
    return parsed


def _framed_sha256(domain: str, *fields: str) -> str:
    parts = [domain, *fields]
    try:
        message = b"\0".join(part.encode("utf-8", errors="strict") for part in parts)
    except UnicodeEncodeError as exc:
        fail("IDENTITY_UTF8", f"identity input is not UTF-8: {exc}")
    return hashlib.sha256(message).hexdigest()


def derive_global_trial_key(trial_id: str) -> str:
    return _framed_sha256(GLOBAL_TRIAL_KEY_DOMAIN, _require_label(trial_id, "trial_id"))


def derive_sampling_attempt_namespace(trial_id: str) -> str:
    return _framed_sha256(
        SAMPLING_ATTEMPT_NAMESPACE_DOMAIN,
        _require_label(trial_id, "trial_id"),
    )


def derive_sampling_event(
    contract_core_sha256: str,
    trial_id: str,
    eligible_frame_manifest_sha256: str,
    strata_allocation_manifest_sha256: str,
) -> str:
    return _framed_sha256(
        SAMPLING_EVENT_DOMAIN,
        _require_sha(contract_core_sha256, "contract_core_sha256"),
        _require_label(trial_id, "trial_id"),
        _require_sha(eligible_frame_manifest_sha256, "eligible_frame_manifest_sha256"),
        _require_sha(
            strata_allocation_manifest_sha256,
            "strata_allocation_manifest_sha256",
        ),
    )


def derive_custody_target(
    custodian_instance_sha256: str,
    sampling_attempt_namespace_sha256: str,
) -> str:
    return _framed_sha256(
        CUSTODY_TARGET_DOMAIN,
        _require_sha(custodian_instance_sha256, "custodian_instance_sha256"),
        _require_sha(
            sampling_attempt_namespace_sha256,
            "sampling_attempt_namespace_sha256",
        ),
    )


def _schema_rows(connection: sqlite3.Connection) -> list[tuple[str, str, str]]:
    rows = connection.execute(
        "SELECT type, name, sql FROM main.sqlite_schema "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    if any(
        type(kind) is not str or type(name) is not str or type(sql) is not str
        for kind, name, sql in rows
    ):
        fail("STORE_SCHEMA", "persistent schema row has an invalid type")
    return rows


def _schema_digest(rows: list[tuple[str, str, str]]) -> str:
    digest = hashlib.sha256()
    for kind, name, sql in rows:
        for field in (kind.encode("utf-8"), name.encode("utf-8"), sql.encode("utf-8")):
            digest.update(len(field).to_bytes(8, "big"))
            digest.update(field)
    return digest.hexdigest()


def _expected_schema_profile() -> tuple[str, tuple[tuple[str, str], ...]]:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        connection.executescript(SCHEMA_SQL)
        rows = _schema_rows(connection)
        objects = tuple((kind, name) for kind, name, _sql in rows)
        return _schema_digest(rows), objects
    finally:
        connection.close()


STORE_SCHEMA_SHA256, EXPECTED_SCHEMA_OBJECTS = _expected_schema_profile()


def _source_sha256() -> str:
    path = Path(__file__).absolute()
    try:
        before = os.lstat(path)
    except OSError as exc:
        fail("SOURCE_IDENTITY", f"cannot stat custodian source: {exc}")
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or before.st_nlink != 1
        or before.st_size > 4_194_304
    ):
        fail("SOURCE_IDENTITY", "custodian source is not one bounded unaliased regular file")
    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    if any(not hasattr(os, name) for name in required):
        fail("PLATFORM", "source verification requires nofollow/cloexec/nonblock")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            fail("SOURCE_RACE", "custodian source changed while opening")
        remaining = 4_194_305
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(fd, min(1_048_576, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        if (
            len(raw) > 4_194_304
            or after.st_size != len(raw)
            or (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            fail("SOURCE_RACE", "custodian source size or identity changed")
        return hashlib.sha256(raw).hexdigest()
    finally:
        os.close(fd)


def _validate_config(config: Any) -> CustodianConfig:
    if type(config) is not CustodianConfig:
        fail("CONFIG_TYPE", "config must be an exact CustodianConfig")
    if not isinstance(config.store_path, Path) or not config.store_path.is_absolute():
        fail("STORE_PATH", "store path must be an absolute Path")
    if config.store_path.name != STORE_BASENAME:
        fail("STORE_PATH", "store basename differs from the frozen profile")
    _require_label(config.custodian_id, "custodian_id")
    for label in (
        "custodian_authority_sha256",
        "custodian_instance_sha256",
        "registry_generation_sha256",
        "owner_trust_policy_sha256",
        "admission_policy_sha256",
        "sampling_receipt_schema_sha256",
        "sampling_receipt_writer_sha256",
    ):
        _require_sha(getattr(config, label), label)
    if config.sampling_receipt_schema_sha256 != "e418b58246eaf183b5624c7eb12299caeea933c83a07584faa915651b3cd48d4":
        fail("CONFIG_SAMPLING_SCHEMA", "sampling receipt schema is not frozen v1")
    if config.sampling_receipt_writer_sha256 != "a8642d2b524183e060eb2f2c16d3a4bba4bca43c8e18b8524bc14738d4f6d975":
        fail("CONFIG_WRITER", "sampling receipt writer is not the frozen writer")
    if (
        type(config.busy_timeout_ms) is not int
        or not 1 <= config.busy_timeout_ms <= MAX_BUSY_TIMEOUT_MS
    ):
        fail("CONFIG_TIMEOUT", "busy timeout is outside 1..=60000 ms")
    return config


def _reject_symlinked_ancestors(path: Path) -> None:
    cursor = Path(path.anchor)
    for component in path.parts[1:]:
        cursor /= component
        try:
            info = os.lstat(cursor)
        except OSError as exc:
            fail("STORE_PARENT", f"cannot stat store ancestor {cursor}: {exc}")
        if stat.S_ISLNK(info.st_mode):
            fail("STORE_PARENT", f"store ancestor is a symlink: {cursor}")


def _open_parent(config: CustodianConfig) -> tuple[int, os.stat_result]:
    parent = config.store_path.parent
    _reject_symlinked_ancestors(parent)
    try:
        before = os.lstat(parent)
    except OSError as exc:
        fail("STORE_PARENT", f"cannot stat store parent: {exc}")
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
        fail("STORE_PARENT", "store parent is not a direct directory")
    if before.st_uid != os.geteuid() or stat.S_IMODE(before.st_mode) != 0o700:
        fail("STORE_PARENT", "store parent must be owned by euid with exact mode 0700")
    required = ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    if any(not hasattr(os, name) for name in required):
        fail("PLATFORM", "store profile requires directory/nofollow/cloexec/nonblock")
    fd = os.open(
        parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
    )
    try:
        opened = os.fstat(fd)
    except BaseException:
        os.close(fd)
        raise
    if (
        (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
        or opened.st_uid != os.geteuid()
        or stat.S_IMODE(opened.st_mode) != 0o700
    ):
        os.close(fd)
        fail("STORE_PARENT_RACE", "store parent identity changed while opening")
    return fd, opened


def _validate_sidecars(config: CustodianConfig, parent_fd: int) -> None:
    for suffix in ("-journal", "-wal", "-shm"):
        try:
            info = os.stat(
                STORE_BASENAME + suffix,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            continue
        except OSError as exc:
            fail("STORE_SIDECAR", f"cannot stat SQLite sidecar {suffix}: {exc}")
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            fail("STORE_SIDECAR", f"SQLite sidecar {suffix} has an unsafe identity")


def _process_fd_set() -> set[int]:
    directory_fd: int | None = None
    try:
        directory_fd = os.open(
            "/proc/self/fd",
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        names = os.listdir(directory_fd)
    except OSError as exc:
        fail("PLATFORM", f"cannot enumerate process descriptors: {exc}")
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
    result = {int(name) for name in names if name.isdigit()}
    result.discard(directory_fd)
    return result


def _connect_existing_inode(
    config: CustodianConfig,
    expected_identity: os.stat_result,
    sentinel_fd: int,
) -> sqlite3.Connection:
    connection: sqlite3.Connection | None = None
    try:
        with _SQLITE_CONNECT_LOCK:
            before_fds = _process_fd_set()
            connection = sqlite3.connect(
                config.store_path.as_uri() + "?mode=rw",
                uri=True,
                timeout=config.busy_timeout_ms / 1000,
                isolation_level=None,
            )
            new_fds = _process_fd_set() - before_fds
            matching = 0
            for fd in new_fds:
                if fd == sentinel_fd:
                    continue
                try:
                    info = os.fstat(fd)
                except OSError:
                    continue
                if (
                    stat.S_ISREG(info.st_mode)
                    and (info.st_dev, info.st_ino)
                    == (expected_identity.st_dev, expected_identity.st_ino)
                ):
                    matching += 1
            if matching < 1:
                fail(
                    "STORE_SQLITE_IDENTITY",
                    "new SQLite connection fd is not bound to the pinned store inode",
                )
        return connection
    except BaseException:
        if connection is not None:
            connection.close()
        raise


def _validate_bound_paths(
    config: CustodianConfig,
    parent_fd: int,
    parent_identity: os.stat_result,
    store_identity: os.stat_result,
) -> None:
    try:
        parent = os.lstat(config.store_path.parent)
        direct = os.lstat(config.store_path)
        relative = os.stat(
            STORE_BASENAME,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except OSError as exc:
        fail("STORE_RACE", f"cannot revalidate configured store paths: {exc}")
    expected_parent = (parent_identity.st_dev, parent_identity.st_ino)
    expected_store = (store_identity.st_dev, store_identity.st_ino)
    if (
        not stat.S_ISDIR(parent.st_mode)
        or stat.S_ISLNK(parent.st_mode)
        or (parent.st_dev, parent.st_ino) != expected_parent
        or parent.st_uid != os.geteuid()
        or stat.S_IMODE(parent.st_mode) != 0o700
        or not stat.S_ISREG(direct.st_mode)
        or stat.S_ISLNK(direct.st_mode)
        or (direct.st_dev, direct.st_ino) != expected_store
        or direct.st_uid != os.geteuid()
        or direct.st_nlink != 1
        or stat.S_IMODE(direct.st_mode) != 0o600
        or not stat.S_ISREG(relative.st_mode)
        or (relative.st_dev, relative.st_ino) != expected_store
        or relative.st_uid != os.geteuid()
        or relative.st_nlink != 1
        or stat.S_IMODE(relative.st_mode) != 0o600
    ):
        fail("STORE_RACE", "configured store or parent path identity changed")


def _open_store_sentinel(
    config: CustodianConfig,
    parent_fd: int,
) -> tuple[int, os.stat_result]:
    try:
        before = os.lstat(config.store_path)
    except FileNotFoundError:
        fail("STORE_MISSING", "runtime operation refuses to create a missing custodian store")
    except OSError as exc:
        fail("STORE_IDENTITY", f"cannot stat custodian store: {exc}")
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.geteuid()
        or before.st_nlink != 1
        or stat.S_IMODE(before.st_mode) != 0o600
    ):
        fail("STORE_IDENTITY", "custodian store must be one euid-owned 0600 regular file")
    fd = os.open(
        STORE_BASENAME,
        os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
        dir_fd=parent_fd,
    )
    try:
        opened = os.fstat(fd)
    except BaseException:
        os.close(fd)
        raise
    if (
        (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
        or not stat.S_ISREG(opened.st_mode)
        or opened.st_uid != os.geteuid()
        or opened.st_nlink != 1
        or stat.S_IMODE(opened.st_mode) != 0o600
    ):
        os.close(fd)
        fail("STORE_IDENTITY", "custodian store identity changed while opening")
    return fd, opened


def _configure_connection(connection: sqlite3.Connection, config: CustodianConfig) -> None:
    connection.execute(f"PRAGMA busy_timeout={config.busy_timeout_ms}")
    connection.execute("PRAGMA synchronous=EXTRA")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA read_uncommitted=OFF")
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("PRAGMA locking_mode=NORMAL")
    if hasattr(connection, "enable_load_extension"):
        connection.enable_load_extension(False)
    journal = connection.execute("PRAGMA journal_mode").fetchone()
    synchronous = connection.execute("PRAGMA synchronous").fetchone()
    foreign = connection.execute("PRAGMA foreign_keys").fetchone()
    uncommitted = connection.execute("PRAGMA read_uncommitted").fetchone()
    trusted = connection.execute("PRAGMA trusted_schema").fetchone()
    locking = connection.execute("PRAGMA locking_mode").fetchone()
    if (
        journal is None
        or str(journal[0]).lower() != "delete"
        or synchronous != (3,)
        or foreign != (1,)
        or uncommitted != (0,)
        or trusted != (0,)
        or locking is None
        or str(locking[0]).lower() != "normal"
    ):
        fail("STORE_PRAGMA", "SQLite connection did not retain the closed profile")


def _meta_values(config: CustodianConfig) -> tuple[Any, ...]:
    return (
        config.registry_generation_sha256,
        config.custodian_id,
        config.custodian_authority_sha256,
        config.custodian_instance_sha256,
        config.owner_trust_policy_sha256,
        config.admission_policy_sha256,
        config.sampling_receipt_schema_sha256,
        config.sampling_receipt_writer_sha256,
    )


def _validate_store(connection: sqlite3.Connection, config: CustodianConfig) -> None:
    app_id = connection.execute("PRAGMA application_id").fetchone()
    user_version = connection.execute("PRAGMA user_version").fetchone()
    if app_id != (APPLICATION_ID,) or user_version != (USER_VERSION,):
        fail("STORE_VERSION", "custodian application or user version drift")
    rows = _schema_rows(connection)
    if tuple((kind, name) for kind, name, _sql in rows) != EXPECTED_SCHEMA_OBJECTS:
        fail("STORE_SCHEMA", "custodian schema object catalog drift")
    if _schema_digest(rows) != STORE_SCHEMA_SHA256:
        fail("STORE_SCHEMA", "custodian schema SQL digest drift")
    if connection.execute("SELECT COUNT(*) FROM temp.sqlite_schema").fetchone() != (0,):
        fail("STORE_SCHEMA", "temporary schema objects are forbidden")
    meta = connection.execute(
        "SELECT registry_generation_sha256, custodian_id, custodian_authority_sha256, "
        "custodian_instance_sha256, owner_trust_policy_sha256, admission_policy_sha256, "
        "sampling_receipt_schema_sha256, sampling_receipt_writer_sha256 "
        "FROM custodian_meta_v1 WHERE singleton=1"
    ).fetchone()
    if meta != _meta_values(config):
        fail("STORE_GENERATION", "custodian store identity/configuration drift")
    quick = connection.execute("PRAGMA quick_check(1)").fetchone()
    foreign = connection.execute("PRAGMA foreign_key_check").fetchall()
    if quick != ("ok",) or foreign:
        fail("STORE_INTEGRITY", "custodian store integrity check failed")


@dataclass
class _OpenStore:
    config: CustodianConfig
    connection: sqlite3.Connection
    parent_fd: int
    parent_identity: os.stat_result
    sentinel_fd: int
    store_identity: os.stat_result


def _open_existing(config: Any) -> _OpenStore:
    config = _validate_config(config)
    parent_fd, parent_identity = _open_parent(config)
    try:
        _validate_sidecars(config, parent_fd)
        sentinel_fd, store_identity = _open_store_sentinel(config, parent_fd)
    except BaseException:
        os.close(parent_fd)
        raise
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect_existing_inode(config, store_identity, sentinel_fd)
        _configure_connection(connection, config)
        _validate_store(connection, config)
        _validate_bound_paths(
            config,
            parent_fd,
            parent_identity,
            store_identity,
        )
        return _OpenStore(
            config=config,
            connection=connection,
            parent_fd=parent_fd,
            parent_identity=parent_identity,
            sentinel_fd=sentinel_fd,
            store_identity=store_identity,
        )
    except BaseException:
        if connection is not None:
            try:
                connection.close()
            except BaseException:
                pass
        os.close(sentinel_fd)
        os.close(parent_fd)
        raise


def _close_store(store: _OpenStore, *, durable: bool) -> None:
    error: BaseException | None = None
    connection_closed = False
    try:
        _validate_bound_paths(
            store.config,
            store.parent_fd,
            store.parent_identity,
            store.store_identity,
        )
        store.connection.close()
        connection_closed = True
        if durable:
            os.fsync(store.sentinel_fd)
            os.fsync(store.parent_fd)
        opened = os.fstat(store.sentinel_fd)
        parent = os.fstat(store.parent_fd)
        if (
            (opened.st_dev, opened.st_ino)
            != (store.store_identity.st_dev, store.store_identity.st_ino)
            or opened.st_uid != os.geteuid()
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != 0o600
            or (parent.st_dev, parent.st_ino)
            != (store.parent_identity.st_dev, store.parent_identity.st_ino)
            or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) != 0o700
        ):
            fail("STORE_RACE", "store or parent identity changed during operation")
        _validate_bound_paths(
            store.config,
            store.parent_fd,
            store.parent_identity,
            store.store_identity,
        )
        _validate_sidecars(store.config, store.parent_fd)
    except BaseException as exc:
        error = exc
    finally:
        if not connection_closed:
            try:
                store.connection.close()
            except BaseException as exc:
                if error is None:
                    error = exc
        os.close(store.sentinel_fd)
        os.close(store.parent_fd)
    if error is not None:
        if isinstance(error, CustodianError):
            raise error
        if not isinstance(error, Exception):
            raise error
        fail("STORE_CLOSE", f"cannot durably close custodian store: {error}")


def initialize_custodian(
    config: Any,
    *,
    created_at_utc: str,
    _fault_hook: FaultHook = None,
) -> None:
    config = _validate_config(config)
    _require_utc(created_at_utc, "created_at_utc")
    parent_fd, parent_identity = _open_parent(config)
    fd: int | None = None
    created = False
    connection: sqlite3.Connection | None = None
    try:
        try:
            fd = os.open(
                STORE_BASENAME,
                os.O_RDWR
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | os.O_CLOEXEC
                | os.O_NONBLOCK,
                0o600,
                dir_fd=parent_fd,
            )
            created = True
        except FileExistsError:
            fail("STORE_EXISTS", "explicit initialization refuses an existing store")
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            fail("STORE_IDENTITY", "new store file has an unsafe identity")
        os.fsync(fd)
        os.fsync(parent_fd)
        _validate_sidecars(config, parent_fd)
        connection = _connect_existing_inode(config, info, fd)
        mode = connection.execute("PRAGMA journal_mode=DELETE").fetchone()
        if mode is None or str(mode[0]).lower() != "delete":
            fail("STORE_PRAGMA", "cannot establish DELETE journal mode")
        _configure_connection(connection, config)
        connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version={USER_VERSION}")
        connection.executescript("BEGIN EXCLUSIVE;\n" + SCHEMA_SQL)
        connection.execute(
            "INSERT INTO custodian_meta_v1 "
            "(singleton, registry_generation_sha256, custodian_id, "
            "custodian_authority_sha256, custodian_instance_sha256, "
            "owner_trust_policy_sha256, admission_policy_sha256, "
            "sampling_receipt_schema_sha256, sampling_receipt_writer_sha256, "
            "initialized_at_utc) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*_meta_values(config), created_at_utc),
        )
        _validate_store(connection, config)
        if _fault_hook is not None:
            _fault_hook("initialize_before_commit")
        connection.commit()
        _validate_bound_paths(config, parent_fd, parent_identity, info)
        os.fsync(fd)
        os.fsync(parent_fd)
        if _fault_hook is not None:
            _fault_hook("initialize_after_commit")
        connection.close()
        connection = None
        _validate_bound_paths(config, parent_fd, parent_identity, info)
        _validate_sidecars(config, parent_fd)
    except CustodianError:
        raise
    except (OSError, sqlite3.Error) as exc:
        suffix = "partial store retained" if created else "store not created"
        fail("STORE_INITIALIZE", f"cannot initialize custodian ({suffix}): {exc}")
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        if fd is not None:
            os.close(fd)
        os.close(parent_fd)


def _require_protocol(value: Any) -> int:
    if type(value) is not int or value != PROTOCOL_VERSION:
        fail("PROTOCOL_VERSION", "request protocol version is not exact v1")
    return value


def _validate_exact_tuple(request: dict[str, Any], config: CustodianConfig) -> None:
    _require_protocol(request["protocol_version"])
    trial_id = _require_label(request["trial_id"], "trial_id")
    admission = _require_sha(request["admission_policy_sha256"], "admission_policy_sha256")
    core = _require_sha(request["contract_core_sha256"], "contract_core_sha256")
    frame = _require_sha(
        request["eligible_frame_manifest_sha256"],
        "eligible_frame_manifest_sha256",
    )
    allocation = _require_sha(
        request["strata_allocation_manifest_sha256"],
        "strata_allocation_manifest_sha256",
    )
    namespace = _require_sha(
        request["sampling_attempt_namespace_sha256"],
        "sampling_attempt_namespace_sha256",
    )
    event = _require_sha(request["sampling_event_sha256"], "sampling_event_sha256")
    if admission != config.admission_policy_sha256:
        fail("ADMISSION_POLICY_BINDING", "request admission policy differs from store pin")
    if namespace != derive_sampling_attempt_namespace(trial_id):
        fail("ATTEMPT_NAMESPACE", "request attempt namespace derivation drift")
    if event != derive_sampling_event(core, trial_id, frame, allocation):
        fail("SAMPLING_EVENT", "request sampling event derivation drift")


def _next_sequence(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(custodian_sequence), 0) + 1 "
        "FROM custodian_ledger_events_v1"
    ).fetchone()
    if row is None or type(row[0]) is not int or row[0] < 1:
        fail("STORE_SEQUENCE", "cannot derive next custodian sequence")
    return row[0]


def _stored_receipt(receipt: dict[str, Any], expected_fields: set[str]) -> StoredReceipt:
    if set(receipt) != expected_fields:
        fail("INTERNAL_RECEIPT_FIELDS", "constructed receipt field set drift")
    raw = _canonical_bytes(receipt, "receipt")
    if not 1 <= len(raw) <= MAX_RECEIPT_BYTES:
        fail("RECEIPT_SIZE", "receipt exceeds frozen size cap")
    return StoredReceipt(
        receipt_sha256=hashlib.sha256(raw).hexdigest(),
        canonical_bytes=raw,
        receipt=receipt,
    )


def _insert_ledger_event(
    connection: sqlite3.Connection,
    *,
    sequence: int,
    event_type: str,
    trial_id: str,
    namespace: str,
    request_sha256: str,
    receipt_sha256: str,
) -> None:
    connection.execute(
        "INSERT INTO custodian_ledger_events_v1 "
        "(custodian_sequence, event_type, trial_id, "
        "sampling_attempt_namespace_sha256, request_sha256, receipt_sha256) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            sequence,
            event_type,
            trial_id,
            namespace,
            request_sha256,
            receipt_sha256,
        ),
    )


def _rollback_and_close(store: _OpenStore) -> None:
    try:
        if store.connection.in_transaction:
            store.connection.rollback()
    finally:
        _close_store(store, durable=False)


def register_owner_trial(
    config: Any,
    request_bytes: Any,
    *,
    _fault_hook: FaultHook = None,
) -> StoredReceipt:
    config = _validate_config(config)
    request = _parse_canonical(
        request_bytes,
        REGISTRATION_REQUEST_FIELDS,
        REGISTRATION_REQUEST_SCHEMA,
        "owner trial registration request",
    )
    _validate_exact_tuple(request, config)
    registered_at = _require_utc(request["registered_at_utc"], "registered_at_utc")
    del registered_at
    owner_auth = _require_sha(
        request["owner_authorization_receipt_sha256"],
        "owner_authorization_receipt_sha256",
    )
    owner_freeze = _require_sha(
        request["owner_freeze_receipt_sha256"],
        "owner_freeze_receipt_sha256",
    )
    owner_trust = _require_sha(
        request["owner_trust_policy_sha256"],
        "owner_trust_policy_sha256",
    )
    if owner_trust != config.owner_trust_policy_sha256:
        fail("OWNER_TRUST_POLICY", "registration owner trust policy differs from store pin")
    trial_id = request["trial_id"]
    namespace = request["sampling_attempt_namespace_sha256"]
    request_sha256 = hashlib.sha256(request_bytes).hexdigest()
    source_sha256 = _source_sha256()

    store = _open_existing(config)
    committed = False
    try:
        connection = store.connection
        connection.execute("BEGIN IMMEDIATE")
        _validate_store(connection, config)
        if connection.execute(
            "SELECT 1 FROM owner_trial_registrations_v1 WHERE trial_id=?",
            (trial_id,),
        ).fetchone() is not None:
            fail("TRIAL_ALREADY_REGISTERED", "global trial_id is already registered")
        sequence = _next_sequence(connection)
        receipt = _stored_receipt(
            {
                "schema": REGISTRATION_RECEIPT_SCHEMA,
                "protocol_version": PROTOCOL_VERSION,
                "trial_id": trial_id,
                "registered_at_utc": request["registered_at_utc"],
                "global_trial_key_sha256": derive_global_trial_key(trial_id),
                "sampling_attempt_namespace_sha256": namespace,
                "sampling_event_sha256": request["sampling_event_sha256"],
                "admission_policy_sha256": request["admission_policy_sha256"],
                "contract_core_sha256": request["contract_core_sha256"],
                "eligible_frame_manifest_sha256": request[
                    "eligible_frame_manifest_sha256"
                ],
                "strata_allocation_manifest_sha256": request[
                    "strata_allocation_manifest_sha256"
                ],
                "owner_authorization_receipt_sha256": owner_auth,
                "owner_freeze_receipt_sha256": owner_freeze,
                "owner_trust_policy_sha256": owner_trust,
                "custodian_id": config.custodian_id,
                "custodian_authority_sha256": config.custodian_authority_sha256,
                "custodian_instance_sha256": config.custodian_instance_sha256,
                "custodian_sequence": sequence,
                "custodian_source_sha256": source_sha256,
                "custodian_store_schema_sha256": STORE_SCHEMA_SHA256,
                "receipt_schema_sha256": REGISTRATION_SCHEMA_SHA256,
                "local_registry_trial_id_consumed": True,
                "cross_protocol_trial_id_reuse_forbidden": True,
                "external_owner_trust_verified": False,
                "external_global_single_use_verified": False,
                "condition_output_authorized": False,
                "authority_scope": "LOCAL_CRASH_ATOMIC_REGISTRATION_ONLY_NOT_EXTERNAL_GLOBAL_ANTI_ROLLBACK",
            },
            REGISTRATION_RECEIPT_FIELDS,
        )
        _insert_ledger_event(
            connection,
            sequence=sequence,
            event_type="REGISTRATION",
            trial_id=trial_id,
            namespace=namespace,
            request_sha256=request_sha256,
            receipt_sha256=receipt.receipt_sha256,
        )
        connection.execute(
            "INSERT INTO owner_trial_registrations_v1 "
            "(trial_id, protocol_version, global_trial_key_sha256, "
            "sampling_attempt_namespace_sha256, admission_policy_sha256, "
            "contract_core_sha256, eligible_frame_manifest_sha256, "
            "strata_allocation_manifest_sha256, sampling_event_sha256, "
            "owner_authorization_receipt_sha256, owner_freeze_receipt_sha256, "
            "owner_trust_policy_sha256, registered_at_utc, custodian_sequence, "
            "request_sha256, request_bytes, receipt_sha256, receipt_bytes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trial_id,
                PROTOCOL_VERSION,
                derive_global_trial_key(trial_id),
                namespace,
                request["admission_policy_sha256"],
                request["contract_core_sha256"],
                request["eligible_frame_manifest_sha256"],
                request["strata_allocation_manifest_sha256"],
                request["sampling_event_sha256"],
                owner_auth,
                owner_freeze,
                owner_trust,
                request["registered_at_utc"],
                sequence,
                request_sha256,
                request_bytes,
                receipt.receipt_sha256,
                receipt.canonical_bytes,
            ),
        )
        if _fault_hook is not None:
            _fault_hook("registration_before_commit")
        connection.commit()
        committed = True
        os.fsync(store.sentinel_fd)
        os.fsync(store.parent_fd)
        if _fault_hook is not None:
            _fault_hook("registration_after_commit")
        _validate_store(connection, config)
    except CustodianError:
        if not committed:
            _rollback_and_close(store)
        else:
            _close_store(store, durable=True)
        raise
    except (OSError, sqlite3.Error) as exc:
        if not committed:
            _rollback_and_close(store)
        else:
            _close_store(store, durable=True)
        fail("REGISTRATION_INDETERMINATE", f"registration result is indeterminate: {exc}")
    except BaseException:
        if not committed:
            _rollback_and_close(store)
        else:
            _close_store(store, durable=True)
        raise
    else:
        _close_store(store, durable=True)
    return receipt


def _registration_row(
    connection: sqlite3.Connection,
    trial_id: str,
) -> tuple[Any, ...]:
    row = connection.execute(
        "SELECT protocol_version, sampling_attempt_namespace_sha256, "
        "admission_policy_sha256, contract_core_sha256, "
        "eligible_frame_manifest_sha256, strata_allocation_manifest_sha256, "
        "sampling_event_sha256, registered_at_utc, receipt_sha256 "
        "FROM owner_trial_registrations_v1 WHERE trial_id=?",
        (trial_id,),
    ).fetchone()
    if row is None:
        fail("REGISTRATION_MISSING", "trial has no owner registration")
    return row


def claim_sampling_attempt(
    config: Any,
    request_bytes: Any,
    *,
    _fault_hook: FaultHook = None,
) -> StoredReceipt:
    config = _validate_config(config)
    request = _parse_canonical(
        request_bytes,
        CLAIM_REQUEST_FIELDS,
        CLAIM_REQUEST_SCHEMA,
        "sampling attempt claim request",
    )
    _validate_exact_tuple(request, config)
    claimed_at = _require_utc(request["claimed_at_utc"], "claimed_at_utc")
    registration_receipt_sha256 = _require_sha(
        request["owner_trial_registration_receipt_sha256"],
        "owner_trial_registration_receipt_sha256",
    )
    custody_target = _require_sha(
        request["custody_target_sha256"], "custody_target_sha256"
    )
    expected_target = derive_custody_target(
        config.custodian_instance_sha256,
        request["sampling_attempt_namespace_sha256"],
    )
    if custody_target != expected_target:
        fail("CUSTODY_TARGET", "claim custody target derivation drift")
    trial_id = request["trial_id"]
    namespace = request["sampling_attempt_namespace_sha256"]
    request_sha256 = hashlib.sha256(request_bytes).hexdigest()
    source_sha256 = _source_sha256()

    store = _open_existing(config)
    committed = False
    try:
        connection = store.connection
        connection.execute("BEGIN IMMEDIATE")
        _validate_store(connection, config)
        registration = _registration_row(connection, trial_id)
        expected_registration = (
            PROTOCOL_VERSION,
            namespace,
            request["admission_policy_sha256"],
            request["contract_core_sha256"],
            request["eligible_frame_manifest_sha256"],
            request["strata_allocation_manifest_sha256"],
            request["sampling_event_sha256"],
        )
        if registration[:7] != expected_registration:
            fail("REGISTRATION_JOIN", "claim tuple differs from owner registration")
        if registration[8] != registration_receipt_sha256:
            fail("REGISTRATION_RECEIPT_JOIN", "claim registration receipt hash drift")
        registered_at = _require_utc(registration[7], "stored registered_at_utc")
        if claimed_at <= registered_at:
            fail("CLAIM_TIME_ORDER", "claim must be strictly later than registration")
        if connection.execute(
            "SELECT 1 FROM sampling_attempt_claims_v1 "
            "WHERE sampling_attempt_namespace_sha256=?",
            (namespace,),
        ).fetchone() is not None:
            fail("ATTEMPT_ALREADY_CLAIMED", "sampling attempt namespace is permanently claimed")
        sequence = _next_sequence(connection)
        receipt = _stored_receipt(
            {
                "schema": CLAIM_RECEIPT_SCHEMA,
                "protocol_version": PROTOCOL_VERSION,
                "trial_id": trial_id,
                "claimed_at_utc": request["claimed_at_utc"],
                "owner_trial_registration_receipt_sha256": registration_receipt_sha256,
                "sampling_attempt_namespace_sha256": namespace,
                "sampling_event_sha256": request["sampling_event_sha256"],
                "admission_policy_sha256": request["admission_policy_sha256"],
                "contract_core_sha256": request["contract_core_sha256"],
                "eligible_frame_manifest_sha256": request[
                    "eligible_frame_manifest_sha256"
                ],
                "strata_allocation_manifest_sha256": request[
                    "strata_allocation_manifest_sha256"
                ],
                "custody_target_sha256": custody_target,
                "custodian_id": config.custodian_id,
                "custodian_authority_sha256": config.custodian_authority_sha256,
                "custodian_instance_sha256": config.custodian_instance_sha256,
                "custodian_sequence": sequence,
                "custodian_source_sha256": source_sha256,
                "custodian_store_schema_sha256": STORE_SCHEMA_SHA256,
                "receipt_schema_sha256": CLAIM_SCHEMA_SHA256,
                "local_namespace_claim_committed": True,
                "same_namespace_sampling_retry_forbidden": True,
                "external_entropy_bound": False,
                "sampling_write_outcome_status": "PENDING",
                "live_sampling_write_authorized": False,
                "external_global_single_use_verified": False,
                "first_condition_output_guard_required": True,
                "condition_output_authorized": False,
                "authority_scope": "LOCAL_CRASH_ATOMIC_CLAIM_ONLY_NOT_EXTERNAL_GLOBAL_ANTI_ROLLBACK",
            },
            CLAIM_RECEIPT_FIELDS,
        )
        _insert_ledger_event(
            connection,
            sequence=sequence,
            event_type="CLAIM",
            trial_id=trial_id,
            namespace=namespace,
            request_sha256=request_sha256,
            receipt_sha256=receipt.receipt_sha256,
        )
        connection.execute(
            "INSERT INTO sampling_attempt_claims_v1 "
            "(sampling_attempt_namespace_sha256, trial_id, protocol_version, "
            "owner_trial_registration_receipt_sha256, admission_policy_sha256, "
            "contract_core_sha256, eligible_frame_manifest_sha256, "
            "strata_allocation_manifest_sha256, sampling_event_sha256, "
            "custody_target_sha256, claimed_at_utc, custodian_sequence, "
            "request_sha256, request_bytes, receipt_sha256, receipt_bytes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                namespace,
                trial_id,
                PROTOCOL_VERSION,
                registration_receipt_sha256,
                request["admission_policy_sha256"],
                request["contract_core_sha256"],
                request["eligible_frame_manifest_sha256"],
                request["strata_allocation_manifest_sha256"],
                request["sampling_event_sha256"],
                custody_target,
                request["claimed_at_utc"],
                sequence,
                request_sha256,
                request_bytes,
                receipt.receipt_sha256,
                receipt.canonical_bytes,
            ),
        )
        if _fault_hook is not None:
            _fault_hook("claim_before_commit")
        connection.commit()
        committed = True
        if _fault_hook is not None:
            _fault_hook("claim_after_commit_before_explicit_fsync")
        os.fsync(store.sentinel_fd)
        os.fsync(store.parent_fd)
        if _fault_hook is not None:
            _fault_hook("claim_after_durable_fsync")
        _validate_store(connection, config)
    except CustodianError:
        if not committed:
            _rollback_and_close(store)
        else:
            _close_store(store, durable=True)
        raise
    except (OSError, sqlite3.Error) as exc:
        if not committed:
            _rollback_and_close(store)
        else:
            _close_store(store, durable=True)
        fail("CLAIM_INDETERMINATE", f"claim result is indeterminate: {exc}")
    except BaseException:
        if not committed:
            _rollback_and_close(store)
        else:
            _close_store(store, durable=True)
        raise
    else:
        _close_store(store, durable=True)
    return receipt


def _claim_row(
    connection: sqlite3.Connection,
    namespace: str,
) -> tuple[Any, ...]:
    row = connection.execute(
        "SELECT trial_id, protocol_version, owner_trial_registration_receipt_sha256, "
        "admission_policy_sha256, contract_core_sha256, eligible_frame_manifest_sha256, "
        "strata_allocation_manifest_sha256, sampling_event_sha256, custody_target_sha256, "
        "claimed_at_utc, receipt_sha256 FROM sampling_attempt_claims_v1 "
        "WHERE sampling_attempt_namespace_sha256=?",
        (namespace,),
    ).fetchone()
    if row is None:
        fail("CLAIM_MISSING", "sampling attempt namespace has no committed claim")
    return row


def _validate_probability_weight_grain(receipt: dict[str, Any]) -> None:
    probabilities = receipt["case_inclusion_probabilities"]
    weights = receipt["case_sampling_weights"]
    if type(probabilities) is not list or type(weights) is not list:
        fail("SAMPLING_CASE_GRAIN", "probability or weight surface is not a list")
    if not probabilities or len(probabilities) != len(weights):
        fail("SAMPLING_CASE_GRAIN", "probability and weight cardinality differs")
    seen: set[str] = set()
    for index, (probability, weight) in enumerate(zip(probabilities, weights, strict=True)):
        if (
            type(probability) is not dict
            or set(probability) != {"case_id", "denominator", "numerator"}
            or type(weight) is not dict
            or set(weight) != {"case_id", "denominator", "numerator"}
        ):
            fail("SAMPLING_CASE_GRAIN", f"case evidence row {index} field drift")
        case_id = probability["case_id"]
        if type(case_id) is not str or not case_id.startswith("case_"):
            fail("SAMPLING_CASE_GRAIN", "case ID is outside the receipt profile")
        if case_id in seen or weight["case_id"] != case_id:
            fail("SAMPLING_CASE_GRAIN", "probability/weight case join is not one-to-one")
        seen.add(case_id)
        values = (
            probability["numerator"],
            probability["denominator"],
            weight["numerator"],
            weight["denominator"],
        )
        if any(type(item) is not int or item <= 0 for item in values):
            fail("SAMPLING_CASE_GRAIN", "probability/weight is not positive exact integer")
        if (
            probability["numerator"] != weight["denominator"]
            or probability["denominator"] != weight["numerator"]
            or probability["numerator"] > probability["denominator"]
        ):
            fail("SAMPLING_CASE_GRAIN", "sampling weight is not reciprocal probability")


def _execute_frozen_sampling_writer(config: CustodianConfig) -> types.ModuleType:
    path = Path(__file__).absolute().with_name(
        "biocortex_ab_track_b_sampling_receipt_writer_v0.py"
    )
    try:
        before = os.lstat(path)
    except OSError as exc:
        fail("SAMPLING_WRITER_SOURCE", f"cannot stat frozen writer: {exc}")
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or before.st_nlink != 1
        or not 1 <= before.st_size <= 4_194_304
    ):
        fail("SAMPLING_WRITER_SOURCE", "frozen writer has an unsafe file identity")
    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    if any(not hasattr(os, name) for name in required):
        fail("PLATFORM", "writer replay requires nofollow/cloexec/nonblock")
    try:
        fd = os.open(
            path,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
        )
    except OSError as exc:
        fail("SAMPLING_WRITER_SOURCE", f"cannot open frozen writer: {exc}")
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            fail("SAMPLING_WRITER_SOURCE", "frozen writer changed while opening")
        chunks: list[bytes] = []
        remaining = 4_194_305
        while remaining:
            chunk = os.read(fd, min(1_048_576, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        source = b"".join(chunks)
        after = os.fstat(fd)
        if (
            not 1 <= len(source) <= 4_194_304
            or after.st_size != len(source)
            or (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
            or hashlib.sha256(source).hexdigest()
            != config.sampling_receipt_writer_sha256
        ):
            fail("SAMPLING_WRITER_SOURCE", "frozen writer bytes or identity drifted")
    finally:
        os.close(fd)
    module_name = (
        f"_agent_bridge_custodian_bound_sampling_writer_{os.getpid()}_{id(source)}"
    )
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = ""
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        code = compile(source, str(path), "exec", dont_inherit=True, optimize=0)
        exec(code, module.__dict__)
    except Exception as exc:
        fail("SAMPLING_WRITER_EXECUTION", f"cannot execute frozen writer: {exc}")
    finally:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
    if (
        getattr(module, "RECEIPT_SCHEMA", None) != SAMPLING_RECEIPT_SCHEMA
        or not callable(getattr(module, "build_sampling_receipt", None))
    ):
        fail("SAMPLING_WRITER_INTERFACE", "frozen writer interface drifted")
    return module


def _read_frozen_sampling_receipt(
    directory_fd: Any,
    expected_bytes: bytes,
    expected_sha256: str,
    *,
    selected_case_count: int,
    reserve_case_count: int,
    sampling_write_request_sha256: str,
) -> tuple[bytes, str, bytes]:
    if type(directory_fd) is not int or directory_fd < 0:
        fail("RECEIPT_DIRECTORY_FD", "success requires an open receipt directory fd")
    try:
        directory_before = os.fstat(directory_fd)
    except OSError as exc:
        fail("RECEIPT_DIRECTORY_FD", f"cannot stat receipt directory fd: {exc}")
    if (
        not stat.S_ISDIR(directory_before.st_mode)
        or directory_before.st_uid != os.geteuid()
        or stat.S_IMODE(directory_before.st_mode) != 0o700
    ):
        fail("RECEIPT_DIRECTORY_IDENTITY", "receipt directory is not euid-owned 0700")
    try:
        entries_before = sorted(os.listdir(directory_fd))
    except OSError as exc:
        fail("RECEIPT_DIRECTORY_IDENTITY", f"cannot enumerate receipt directory: {exc}")
    if entries_before != ["sampling-receipt.json"]:
        fail("RECEIPT_DIRECTORY_ENTRIES", "receipt directory entry set is not exact")
    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    if any(not hasattr(os, name) for name in required) or os.open not in os.supports_dir_fd:
        fail("PLATFORM", "receipt reread requires openat nofollow/cloexec/nonblock")
    try:
        receipt_fd = os.open(
            "sampling-receipt.json",
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            dir_fd=directory_fd,
        )
    except OSError as exc:
        fail("SAMPLING_RECEIPT_FILE", f"cannot open frozen sampling receipt: {exc}")
    try:
        opened = os.fstat(receipt_fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != os.geteuid()
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != 0o400
            or opened.st_size != len(expected_bytes)
        ):
            fail("SAMPLING_RECEIPT_FILE", "sampling receipt file profile drifted")
        chunks: list[bytes] = []
        remaining = MAX_RECEIPT_BYTES + 1
        while remaining:
            chunk = os.read(receipt_fd, min(1_048_576, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if raw != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_sha256:
            fail("SAMPLING_RECEIPT_REPLAY", "sealed receipt differs from writer replay")
        os.fsync(receipt_fd)
        os.lseek(receipt_fd, 0, os.SEEK_SET)
        reread_chunks: list[bytes] = []
        remaining = len(expected_bytes) + 1
        while remaining:
            chunk = os.read(receipt_fd, min(1_048_576, remaining))
            if not chunk:
                break
            reread_chunks.append(chunk)
            remaining -= len(chunk)
        reread = b"".join(reread_chunks)
        after = os.fstat(receipt_fd)
        relative = os.stat(
            "sampling-receipt.json",
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if (
            reread != raw
            or (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
            or (relative.st_dev, relative.st_ino) != (opened.st_dev, opened.st_ino)
            or after.st_size != len(raw)
            or after.st_uid != os.geteuid()
            or after.st_nlink != 1
            or stat.S_IMODE(after.st_mode) != 0o400
        ):
            fail("SAMPLING_RECEIPT_REREAD", "sealed receipt identity changed on reread")
    finally:
        os.close(receipt_fd)
    try:
        os.fsync(directory_fd)
        directory_after = os.fstat(directory_fd)
        entries_after = sorted(os.listdir(directory_fd))
    except OSError as exc:
        fail("RECEIPT_DIRECTORY_FSYNC", f"cannot durably revalidate receipt directory: {exc}")
    if (
        (directory_after.st_dev, directory_after.st_ino)
        != (directory_before.st_dev, directory_before.st_ino)
        or directory_after.st_uid != os.geteuid()
        or stat.S_IMODE(directory_after.st_mode) != 0o700
        or entries_after != entries_before
    ):
        fail("RECEIPT_DIRECTORY_RACE", "receipt directory identity changed")
    observation = {
        "anti_shopping_order_verified": False,
        "condition_output_authorized": False,
        "evidence_scope": (
            "LOCAL_CUSTODIAN_WRITER_REPLAY_REREAD_AND_FSYNC_"
            "NOT_EXTERNAL_CUSTODY_ATTESTATION"
        ),
        "parent_directory_fsync_completed_by_custodian": True,
        "pre_output_timing_verified": False,
        "receipt_basename": "sampling-receipt.json",
        "receipt_directory_entry_set_verified": True,
        "receipt_directory_mode_octal": "0700",
        "receipt_directory_owner_euid_verified": True,
        "receipt_file_fsync_completed_by_custodian": True,
        "receipt_file_mode_octal": "0400",
        "receipt_file_owner_euid_verified": True,
        "receipt_file_single_link_verified": True,
        "receipt_sha256": expected_sha256,
        "receipt_size_bytes": len(expected_bytes),
        "reserve_case_count": reserve_case_count,
        "reread_identity_and_bytes_verified_by_custodian": True,
        "sampling_receipt_writer_replay_verified": True,
        "sampling_write_request_sha256": sampling_write_request_sha256,
        "selected_case_count": selected_case_count,
        "trusted_clock_verified": False,
    }
    if set(observation) != WRITE_OBSERVATION_FIELDS:
        fail("WRITE_OBSERVATION_FIELDS", "derived write observation field set drift")
    observation_bytes = _canonical_bytes(observation, "sampling write observation")
    return raw, hashlib.sha256(observation_bytes).hexdigest(), observation_bytes


def _validate_success_evidence(
    request: dict[str, Any],
    config: CustodianConfig,
    sampling_write_request_bytes: Any,
    sampling_receipt_directory_fd: Any,
) -> tuple[str, bytes, str, bytes]:
    if (
        type(sampling_write_request_bytes) is not bytes
        or not 1 <= len(sampling_write_request_bytes) <= MAX_REQUEST_BYTES
    ):
        fail(
            "SAMPLING_WRITE_REQUEST_BYTES",
            "success requires bounded exact write-request bytes",
        )
    write_request_sha256 = hashlib.sha256(sampling_write_request_bytes).hexdigest()
    if write_request_sha256 != request["sampling_write_request_sha256"]:
        fail("SAMPLING_WRITE_REQUEST_JOIN", "write-request bytes differ from committed digest")
    writer = _execute_frozen_sampling_writer(config)
    try:
        built = writer.build_sampling_receipt(sampling_write_request_bytes)
    except Exception as exc:
        fail("SAMPLING_WRITER_REPLAY", f"frozen writer rejected success request: {exc}")
    receipt = getattr(built, "receipt", None)
    receipt_bytes = getattr(built, "canonical_bytes", None)
    receipt_sha256 = getattr(built, "receipt_sha256", None)
    selected_case_count = getattr(built, "selected_case_count", None)
    reserve_case_count = getattr(built, "reserve_case_count", None)
    if (
        type(receipt) is not dict
        or set(receipt) != SAMPLING_RECEIPT_FIELDS
        or type(receipt_bytes) is not bytes
        or type(receipt_sha256) is not str
        or type(selected_case_count) is not int
        or selected_case_count < 1
        or type(reserve_case_count) is not int
        or reserve_case_count < 0
    ):
        fail("SAMPLING_WRITER_REPLAY", "frozen writer returned an invalid receipt object")
    _check_shape(receipt)
    if (
        len(receipt_bytes) > MAX_RECEIPT_BYTES
        or _canonical_bytes(receipt, "sampling receipt") != receipt_bytes
        or hashlib.sha256(receipt_bytes).hexdigest() != receipt_sha256
    ):
        fail("SUCCESS_EVIDENCE_SIZE", "replayed receipt bytes exceed or violate the profile")
    expected_receipt = (
        receipt["schema"] == SAMPLING_RECEIPT_SCHEMA
        and receipt["trial_id"] == request["trial_id"]
        and receipt["contract_sha256"] == request["contract_core_sha256"]
        and receipt["eligible_frame_manifest_sha256"]
        == request["eligible_frame_manifest_sha256"]
        and receipt["strata_allocation_manifest_sha256"]
        == request["strata_allocation_manifest_sha256"]
        and receipt["external_entropy_sha256"] == request["external_entropy_sha256"]
        and receipt["receipt_schema_sha256"]
        == config.sampling_receipt_schema_sha256
        and receipt["receipt_writer_sha256"]
        == config.sampling_receipt_writer_sha256
        and receipt["condition_output_authorized"] is False
        and receipt["anti_shopping_order_verified"] is False
        and receipt["pre_output_timing_verified"] is False
        and receipt["receipt_precedes_first_condition_output"] is True
    )
    if not expected_receipt:
        fail("SAMPLING_RECEIPT_JOIN", "success receipt does not bind the exact claim tuple")
    for field in SAMPLING_RECEIPT_FIELDS:
        if field.endswith("_sha256"):
            _require_sha(receipt[field], f"sampling_receipt.{field}")
    _validate_probability_weight_grain(receipt)
    selected_count = len(receipt["case_inclusion_probabilities"])
    if selected_case_count != selected_count:
        fail("WRITE_OBSERVATION_JOIN", "writer selected-case count drifted")
    (
        disk_bytes,
        observation_sha256,
        observation_bytes,
    ) = _read_frozen_sampling_receipt(
        sampling_receipt_directory_fd,
        receipt_bytes,
        receipt_sha256,
        selected_case_count=selected_case_count,
        reserve_case_count=reserve_case_count,
        sampling_write_request_sha256=write_request_sha256,
    )
    return receipt_sha256, disk_bytes, observation_sha256, observation_bytes


def record_sampling_outcome(
    config: Any,
    request_bytes: Any,
    *,
    sampling_write_request_bytes: Any = None,
    sampling_receipt_directory_fd: Any = None,
    _fault_hook: FaultHook = None,
) -> StoredReceipt:
    config = _validate_config(config)
    request = _parse_canonical(
        request_bytes,
        OUTCOME_REQUEST_FIELDS,
        OUTCOME_REQUEST_SCHEMA,
        "sampling write outcome request",
    )
    _validate_exact_tuple(request, config)
    finalized_at = _require_utc(request["finalized_at_utc"], "finalized_at_utc")
    registration_receipt_sha256 = _require_sha(
        request["owner_trial_registration_receipt_sha256"],
        "owner_trial_registration_receipt_sha256",
    )
    claim_receipt_sha256 = _require_sha(
        request["sampling_attempt_namespace_claim_receipt_sha256"],
        "sampling_attempt_namespace_claim_receipt_sha256",
    )
    custody_target = _require_sha(
        request["custody_target_sha256"], "custody_target_sha256"
    )
    if custody_target != derive_custody_target(
        config.custodian_instance_sha256,
        request["sampling_attempt_namespace_sha256"],
    ):
        fail("CUSTODY_TARGET", "outcome custody target derivation drift")
    outcome = request["outcome"]
    if outcome not in {"SUCCESS", "TERMINAL_ABORT"}:
        fail("OUTCOME_TAG", "outcome is not a closed terminal tag")

    sampling_receipt_sha256: str | None
    sampling_receipt_bytes: bytes | None
    observation_sha256: str | None
    observation_bytes: bytes | None
    if outcome == "SUCCESS":
        if (
            request["write_state"] != "COMPLETE_DURABLE_OBSERVED"
            or request["abort_reason_code"] is not None
            or request["failure_evidence_sha256"] is not None
        ):
            fail("OUTCOME_UNION", "success branch has abort state")
        _require_sha(request["external_entropy_sha256"], "external_entropy_sha256")
        _require_sha(
            request["sampling_write_request_sha256"],
            "sampling_write_request_sha256",
        )
        (
            sampling_receipt_sha256,
            sampling_receipt_bytes,
            observation_sha256,
            observation_bytes,
        ) = _validate_success_evidence(
            request,
            config,
            sampling_write_request_bytes,
            sampling_receipt_directory_fd,
        )
        abort_reason: str | None = None
        failure_evidence: str | None = None
    else:
        if (
            sampling_write_request_bytes is not None
            or sampling_receipt_directory_fd is not None
        ):
            fail(
                "OUTCOME_EVIDENCE_UNEXPECTED",
                "terminal abort cannot carry success-only file evidence",
            )
        if request["write_state"] not in {
            "NOT_STARTED",
            "PARTIAL_OR_AMBIGUOUS",
            "PROCESS_DEATH_RECONCILIATION",
            "TIMEOUT_WORKER_FENCED",
        }:
            fail("OUTCOME_UNION", "terminal abort has an invalid write state")
        abort_reason = request["abort_reason_code"]
        if type(abort_reason) is not str or ABORT_CODE_RE.fullmatch(abort_reason) is None:
            fail("ABORT_REASON", "terminal abort reason code is not canonical")
        failure_evidence = _require_sha(
            request["failure_evidence_sha256"], "failure_evidence_sha256"
        )
        for label in ("external_entropy_sha256", "sampling_write_request_sha256"):
            value = request[label]
            if value is not None:
                _require_sha(value, label)
        sampling_receipt_sha256 = None
        sampling_receipt_bytes = None
        observation_sha256 = None
        observation_bytes = None

    trial_id = request["trial_id"]
    namespace = request["sampling_attempt_namespace_sha256"]
    request_sha256 = hashlib.sha256(request_bytes).hexdigest()
    source_sha256 = _source_sha256()
    store = _open_existing(config)
    committed = False
    try:
        connection = store.connection
        connection.execute("BEGIN IMMEDIATE")
        _validate_store(connection, config)
        claim = _claim_row(connection, namespace)
        expected_claim = (
            trial_id,
            PROTOCOL_VERSION,
            registration_receipt_sha256,
            request["admission_policy_sha256"],
            request["contract_core_sha256"],
            request["eligible_frame_manifest_sha256"],
            request["strata_allocation_manifest_sha256"],
            request["sampling_event_sha256"],
            custody_target,
        )
        if claim[:9] != expected_claim:
            fail("CLAIM_JOIN", "outcome tuple differs from committed claim")
        if claim[10] != claim_receipt_sha256:
            fail("CLAIM_RECEIPT_JOIN", "outcome claim receipt hash drift")
        claimed_at = _require_utc(claim[9], "stored claimed_at_utc")
        if finalized_at <= claimed_at:
            fail("OUTCOME_TIME_ORDER", "terminal outcome must be strictly later than claim")
        if connection.execute(
            "SELECT 1 FROM sampling_attempt_outcomes_v1 "
            "WHERE sampling_attempt_namespace_sha256=?",
            (namespace,),
        ).fetchone() is not None:
            fail("ATTEMPT_ALREADY_TERMINAL", "sampling attempt already has a terminal outcome")
        sequence = _next_sequence(connection)
        receipt = _stored_receipt(
            {
                "schema": OUTCOME_RECEIPT_SCHEMA,
                "protocol_version": PROTOCOL_VERSION,
                "trial_id": trial_id,
                "finalized_at_utc": request["finalized_at_utc"],
                "owner_trial_registration_receipt_sha256": registration_receipt_sha256,
                "sampling_attempt_namespace_claim_receipt_sha256": claim_receipt_sha256,
                "sampling_attempt_namespace_sha256": namespace,
                "sampling_event_sha256": request["sampling_event_sha256"],
                "admission_policy_sha256": request["admission_policy_sha256"],
                "contract_core_sha256": request["contract_core_sha256"],
                "eligible_frame_manifest_sha256": request[
                    "eligible_frame_manifest_sha256"
                ],
                "strata_allocation_manifest_sha256": request[
                    "strata_allocation_manifest_sha256"
                ],
                "custody_target_sha256": custody_target,
                "outcome": outcome,
                "write_state": request["write_state"],
                "external_entropy_sha256": request["external_entropy_sha256"],
                "sampling_write_request_sha256": request[
                    "sampling_write_request_sha256"
                ],
                "sampling_receipt_sha256": sampling_receipt_sha256,
                "sampling_write_observation_sha256": observation_sha256,
                "abort_reason_code": abort_reason,
                "failure_evidence_sha256": failure_evidence,
                "custodian_id": config.custodian_id,
                "custodian_authority_sha256": config.custodian_authority_sha256,
                "custodian_instance_sha256": config.custodian_instance_sha256,
                "custodian_sequence": sequence,
                "custodian_source_sha256": source_sha256,
                "custodian_store_schema_sha256": STORE_SCHEMA_SHA256,
                "receipt_schema_sha256": OUTCOME_SCHEMA_SHA256,
                "terminal": True,
                "same_namespace_sampling_retry_forbidden": True,
                "external_global_single_use_verified": False,
                "first_condition_output_guard_required": True,
                "condition_output_authorized": False,
                "authority_scope": "LOCAL_CRASH_ATOMIC_TERMINAL_OUTCOME_ONLY_NOT_OUTPUT_AUTHORITY",
            },
            OUTCOME_RECEIPT_FIELDS,
        )
        _insert_ledger_event(
            connection,
            sequence=sequence,
            event_type="OUTCOME",
            trial_id=trial_id,
            namespace=namespace,
            request_sha256=request_sha256,
            receipt_sha256=receipt.receipt_sha256,
        )
        connection.execute(
            "INSERT INTO sampling_attempt_outcomes_v1 "
            "(sampling_attempt_namespace_sha256, trial_id, protocol_version, "
            "owner_trial_registration_receipt_sha256, "
            "sampling_attempt_namespace_claim_receipt_sha256, "
            "admission_policy_sha256, contract_core_sha256, "
            "eligible_frame_manifest_sha256, strata_allocation_manifest_sha256, "
            "sampling_event_sha256, custody_target_sha256, outcome, write_state, "
            "external_entropy_sha256, sampling_write_request_sha256, "
            "sampling_receipt_sha256, sampling_receipt_bytes, "
            "sampling_write_observation_sha256, sampling_write_observation_bytes, "
            "abort_reason_code, failure_evidence_sha256, finalized_at_utc, "
            "custodian_sequence, request_sha256, request_bytes, receipt_sha256, "
            "receipt_bytes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                namespace,
                trial_id,
                PROTOCOL_VERSION,
                registration_receipt_sha256,
                claim_receipt_sha256,
                request["admission_policy_sha256"],
                request["contract_core_sha256"],
                request["eligible_frame_manifest_sha256"],
                request["strata_allocation_manifest_sha256"],
                request["sampling_event_sha256"],
                custody_target,
                outcome,
                request["write_state"],
                request["external_entropy_sha256"],
                request["sampling_write_request_sha256"],
                sampling_receipt_sha256,
                sampling_receipt_bytes,
                observation_sha256,
                observation_bytes,
                abort_reason,
                failure_evidence,
                request["finalized_at_utc"],
                sequence,
                request_sha256,
                request_bytes,
                receipt.receipt_sha256,
                receipt.canonical_bytes,
            ),
        )
        if _fault_hook is not None:
            _fault_hook("outcome_before_commit")
        connection.commit()
        committed = True
        if _fault_hook is not None:
            _fault_hook("outcome_after_commit_before_explicit_fsync")
        os.fsync(store.sentinel_fd)
        os.fsync(store.parent_fd)
        if _fault_hook is not None:
            _fault_hook("outcome_after_durable_fsync")
        _validate_store(connection, config)
    except CustodianError:
        if not committed:
            _rollback_and_close(store)
        else:
            _close_store(store, durable=True)
        raise
    except (OSError, sqlite3.Error) as exc:
        if not committed:
            _rollback_and_close(store)
        else:
            _close_store(store, durable=True)
        fail("OUTCOME_INDETERMINATE", f"terminal outcome result is indeterminate: {exc}")
    except BaseException:
        if not committed:
            _rollback_and_close(store)
        else:
            _close_store(store, durable=True)
        raise
    else:
        _close_store(store, durable=True)
    return receipt


def _decode_stored_receipt(raw: Any, digest: Any) -> StoredReceipt:
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_RECEIPT_BYTES:
        fail("STORED_RECEIPT", "stored receipt bytes are invalid")
    expected = _require_sha(digest, "stored receipt_sha256")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_pairs,
            parse_constant=_reject_constant,
        )
    except CustodianError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        fail("STORED_RECEIPT", f"cannot parse stored receipt: {exc}")
    if type(value) is not dict or _canonical_bytes(value, "stored receipt") != raw:
        fail("STORED_RECEIPT", "stored receipt is not a canonical object")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        fail("STORED_RECEIPT", "stored receipt digest differs from bytes")
    return StoredReceipt(expected, raw, value)


def _query_receipt(
    config: Any,
    sql: str,
    parameters: tuple[Any, ...],
) -> StoredReceipt | None:
    store = _open_existing(config)
    try:
        row = store.connection.execute(sql, parameters).fetchone()
        if row is None:
            result = None
        else:
            if len(row) != 2:
                fail("STORED_RECEIPT", "stored receipt query shape drift")
            result = _decode_stored_receipt(row[1], row[0])
    except CustodianError:
        _close_store(store, durable=False)
        raise
    except sqlite3.Error as exc:
        _close_store(store, durable=False)
        fail("STORE_QUERY", f"cannot query stored receipt: {exc}")
    except BaseException:
        _close_store(store, durable=False)
        raise
    else:
        _close_store(store, durable=False)
    return result


def query_owner_trial(config: Any, trial_id: Any) -> StoredReceipt | None:
    trial = _require_label(trial_id, "trial_id")
    return _query_receipt(
        config,
        "SELECT receipt_sha256, receipt_bytes FROM owner_trial_registrations_v1 "
        "WHERE trial_id=?",
        (trial,),
    )


def query_sampling_attempt_claim(
    config: Any,
    sampling_attempt_namespace_sha256: Any,
) -> StoredReceipt | None:
    namespace = _require_sha(
        sampling_attempt_namespace_sha256,
        "sampling_attempt_namespace_sha256",
    )
    return _query_receipt(
        config,
        "SELECT receipt_sha256, receipt_bytes FROM sampling_attempt_claims_v1 "
        "WHERE sampling_attempt_namespace_sha256=?",
        (namespace,),
    )


def query_sampling_outcome(
    config: Any,
    sampling_attempt_namespace_sha256: Any,
) -> StoredReceipt | None:
    namespace = _require_sha(
        sampling_attempt_namespace_sha256,
        "sampling_attempt_namespace_sha256",
    )
    return _query_receipt(
        config,
        "SELECT receipt_sha256, receipt_bytes FROM sampling_attempt_outcomes_v1 "
        "WHERE sampling_attempt_namespace_sha256=?",
        (namespace,),
    )


def query_exact_receipt(config: Any, receipt_sha256: Any) -> StoredReceipt | None:
    digest = _require_sha(receipt_sha256, "receipt_sha256")
    store = _open_existing(config)
    try:
        event = store.connection.execute(
            "SELECT event_type FROM custodian_ledger_events_v1 WHERE receipt_sha256=?",
            (digest,),
        ).fetchone()
        if event is None:
            result = None
        else:
            table = {
                "REGISTRATION": "owner_trial_registrations_v1",
                "CLAIM": "sampling_attempt_claims_v1",
                "OUTCOME": "sampling_attempt_outcomes_v1",
            }.get(event[0])
            if table is None:
                fail("STORE_EVENT", "ledger event type has no receipt table")
            row = store.connection.execute(
                f"SELECT receipt_sha256, receipt_bytes FROM {table} WHERE receipt_sha256=?",
                (digest,),
            ).fetchone()
            if row is None:
                fail("STORE_EVENT", "ledger receipt has no immutable evidence row")
            result = _decode_stored_receipt(row[1], row[0])
    except CustodianError:
        _close_store(store, durable=False)
        raise
    except sqlite3.Error as exc:
        _close_store(store, durable=False)
        fail("STORE_QUERY", f"cannot query exact receipt: {exc}")
    except BaseException:
        _close_store(store, durable=False)
        raise
    else:
        _close_store(store, durable=False)
    return result


def inspect_counts(config: Any) -> dict[str, int]:
    store = _open_existing(config)
    try:
        connection = store.connection
        counts = {
            "ledger_event_count": connection.execute(
                "SELECT COUNT(*) FROM custodian_ledger_events_v1"
            ).fetchone()[0],
            "owner_registration_count": connection.execute(
                "SELECT COUNT(*) FROM owner_trial_registrations_v1"
            ).fetchone()[0],
            "sampling_attempt_claim_count": connection.execute(
                "SELECT COUNT(*) FROM sampling_attempt_claims_v1"
            ).fetchone()[0],
            "terminal_outcome_count": connection.execute(
                "SELECT COUNT(*) FROM sampling_attempt_outcomes_v1"
            ).fetchone()[0],
            "terminal_success_count": connection.execute(
                "SELECT COUNT(*) FROM sampling_attempt_outcomes_v1 WHERE outcome='SUCCESS'"
            ).fetchone()[0],
            "terminal_abort_count": connection.execute(
                "SELECT COUNT(*) FROM sampling_attempt_outcomes_v1 WHERE outcome='TERMINAL_ABORT'"
            ).fetchone()[0],
        }
        if any(type(value) is not int or value < 0 for value in counts.values()):
            fail("STORE_COUNTS", "custodian count query returned an invalid value")
    except CustodianError:
        _close_store(store, durable=False)
        raise
    except sqlite3.Error as exc:
        _close_store(store, durable=False)
        fail("STORE_QUERY", f"cannot inspect custodian counts: {exc}")
    except BaseException:
        _close_store(store, durable=False)
        raise
    else:
        _close_store(store, durable=False)
    return counts
