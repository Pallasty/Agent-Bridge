#!/usr/bin/env python3
"""Validate the Track B sampling-attempt custodian v1 source pack.

The positive path uses only public synthetic inputs.  It provisions one local
reference ledger, registers and claims one exact tuple, runs the frozen
sampling-receipt writer, and commits one terminal success.  Independent
negative paths cover abort, concurrency, crash boundaries, joins, filesystem
identity, and the deliberately unresolved old-snapshot rollback boundary.

Nothing in this checker creates a real owner registration, proves external
global single use, or authorizes a condition output.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import importlib.util
import json
import multiprocessing
import os
import re
import shutil
import signal
import sqlite3
import stat
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any, Callable


BASELINE_COMMIT = "c3a4ddce9ede20acf0cc90ef5d8c7e9c343d2245"
PACK_DECISION = (
    "LOCAL_CRASH_ATOMIC_CUSTODIAN_SOURCE_PROFILE_PASS_"
    "EXTERNAL_GLOBAL_SINGLE_USE_NOT_ADMITTED"
)
PACK_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_sampling_attempt_custodian_v1_pack_manifest.v0"
)
SYNTHETIC_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_sampling_attempt_custodian_v1_pack_synthetic.v0"
)

CUSTODIAN_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_sampling_attempt_custodian_v1.py"
)
PURPOSE_PATH = Path(
    "scripts/eval/check_biocortex_ab_track_b_sampling_attempt_custodian_v1_pack.py"
)
SYNTHETIC_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_sampling_attempt_custodian_v1_pack_synthetic_v0.json"
)
MANIFEST_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_sampling_attempt_custodian_v1_pack_v0.json"
)
EXPECTED_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_sampling_attempt_custodian_v1_pack.expected.v0.tsv"
)
REPORT_PATH = Path(
    "docs/reports/goal-c-u/2026-07-14-biocortex-track-b-sampling-attempt-custodian-v1-pack.md"
)
GATE_PATH = Path(
    "scripts/check-biocortex-ab-track-b-sampling-attempt-custodian-v1-pack.sh"
)
SUCCESSOR_FIXTURE_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_successor_admission_map_v1_pack_synthetic_v0.json"
)
SUCCESSOR_CHECKER_PATH = Path(
    "scripts/eval/check_biocortex_ab_track_b_successor_admission_map_v1_pack.py"
)
ADMISSION_POLICY_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v1.json"
)
REGISTRATION_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-owner-trial-registration-receipt-schema-v1.json"
)
CLAIM_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-sampling-attempt-claim-receipt-schema-v1.json"
)
OUTCOME_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-sampling-write-outcome-custodian-receipt-schema-v1.json"
)

EXPECTED_EVIDENCE_PATHS = frozenset(
    {
        "crates/store/src/temporal_replay_transport/durable_replay_registry.rs",
        "crates/store/src/temporal_replay_transport/external_restore_authority.rs",
        "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json",
        "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v1.json",
        "docs/design/fixtures/biocortex-ab-track-b-durable-replay-contract-s7-v0.json",
        "docs/design/fixtures/biocortex-ab-track-b-external-authority-provider-s9-v0.json",
        "docs/design/fixtures/biocortex-ab-track-b-owner-trial-registration-receipt-schema-v1.json",
        "docs/design/fixtures/biocortex-ab-track-b-sampling-attempt-claim-receipt-schema-v1.json",
        "docs/design/fixtures/biocortex-ab-track-b-sampling-contract-digest-profile-v0.json",
        "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json",
        "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v1.json",
        "docs/design/fixtures/biocortex-ab-track-b-sampling-write-outcome-custodian-receipt-schema-v1.json",
        "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-durable-replay-s7.md",
        "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-external-authority-provider-s9.md",
        "docs/reports/goal-c-u/2026-07-14-biocortex-track-b-successor-admission-map-v1-pack.md",
        "scripts/check-biocortex-ab-track-b-sampling-receipt-writer-pack.sh",
        "scripts/check-biocortex-ab-track-b-successor-admission-map-v1-pack.sh",
        "scripts/eval/biocortex_ab_track_b_map_bijection_v0.py",
        "scripts/eval/biocortex_ab_track_b_map_bijection_v1.py",
        "scripts/eval/biocortex_ab_track_b_sampling_attempt_custodian_v1.py",
        "scripts/eval/biocortex_ab_track_b_sampling_receipt_writer_v0.py",
        "scripts/eval/biocortex_ab_track_b_sampling_seed_derivation_v0.py",
        "scripts/eval/biocortex_ab_track_b_sampling_selection_v0.py",
        "scripts/eval/check_biocortex_ab_track_b_admission.py",
        "scripts/eval/check_biocortex_ab_track_b_admission_v1.py",
        "scripts/eval/check_biocortex_ab_track_b_sampling_attempt_custodian_v1_pack.py",
        "scripts/eval/check_biocortex_ab_track_b_successor_admission_map_v1_pack.py",
        "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json",
        "scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_synthetic_v0.json",
        "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json",
        "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json",
        "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v1.json",
        "scripts/eval/fixtures/biocortex_ab_track_b_sampling_attempt_custodian_v1_pack_synthetic_v0.json",
        "scripts/eval/fixtures/biocortex_ab_track_b_sampling_receipt_writer_pack_synthetic_v0.json",
        "scripts/eval/fixtures/biocortex_ab_track_b_successor_admission_map_v1_pack.expected.v0.tsv",
        "scripts/eval/fixtures/biocortex_ab_track_b_successor_admission_map_v1_pack_synthetic_v0.json",
        "scripts/eval/fixtures/biocortex_ab_track_b_successor_admission_map_v1_pack_v0.json",
    }
)

CANONICAL_PROFILE = (
    "UTF8_SORTED_KEYS_INDENT_2_LF_FINAL_NEWLINE_NO_NAN_DUPLICATE_KEYS_REJECTED"
)
SHA_RE_TEXT = "^[0-9a-f]{64}$"
SELF_TEST_EXPECTED_SHA256 = (
    "cfc787d3d40c12826a5b103316bfa96eff2e5f523fc1435dab2647aec0435165"
)


class PackError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise PackError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def reject_constant(value: str) -> Any:
    fail(f"non-finite JSON constant {value!r}")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


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
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        fail(f"cannot render canonical JSON: {exc}")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_object(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def load_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read {label}: {exc}")
    require(type(value) is dict, f"{label} root is not an object")
    require(canonical_bytes(value) == raw, f"{label} is not canonical JSON")
    return value, raw


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(name, None)
        fail(f"cannot execute {path}: {exc}")
    return module


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    require(type(value) is dict and set(value) == expected, f"{label} field set drift")
    return value


def validate_receipt_schema(
    schema: dict[str, Any],
    *,
    expected_id: str,
    expected_instance_schema: str,
    expected_fields: set[str],
) -> None:
    require(
        set(schema)
        == {
            "$id",
            "$schema",
            "additionalProperties",
            "properties",
            "required",
            "title",
            "type",
        }
        or set(schema)
        == {
            "$id",
            "$schema",
            "additionalProperties",
            "oneOf",
            "properties",
            "required",
            "title",
            "type",
        },
        "receipt schema top-level field set drift",
    )
    require(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", "JSON Schema draft drift")
    require(schema["$id"] == expected_id, "receipt schema id drift")
    require(schema["type"] == "object" and schema["additionalProperties"] is False, "receipt schema is not closed")
    require(set(schema["properties"]) == expected_fields, "receipt schema properties drift")
    require(schema["required"] == sorted(expected_fields), "receipt schema required list drift")
    require(schema["properties"]["schema"]["const"] == expected_instance_schema, "instance schema const drift")
    for field in expected_fields:
        if field.endswith("_sha256") and field not in {
            "external_entropy_sha256",
            "failure_evidence_sha256",
            "sampling_receipt_sha256",
            "sampling_write_observation_sha256",
            "sampling_write_request_sha256",
        }:
            require(schema["properties"][field].get("pattern") == SHA_RE_TEXT, f"{field} SHA profile drift")
    require(
        schema["properties"]["condition_output_authorized"].get("const") is False,
        "receipt schema raises output authority",
    )
    if "external_global_single_use_verified" in expected_fields:
        require(
            schema["properties"]["external_global_single_use_verified"].get("const") is False,
            "receipt schema invents external global single use",
        )


def validate_schemas(root: Path, custodian: Any) -> dict[str, str]:
    rows = (
        (
            REGISTRATION_SCHEMA_PATH,
            "urn:agent-bridge:biocortex-ab:track-b:owner-trial-registration-receipt:v1",
            custodian.REGISTRATION_RECEIPT_SCHEMA,
            set(custodian.REGISTRATION_RECEIPT_FIELDS),
        ),
        (
            CLAIM_SCHEMA_PATH,
            "urn:agent-bridge:biocortex-ab:track-b:sampling-attempt-claim-receipt:v1",
            custodian.CLAIM_RECEIPT_SCHEMA,
            set(custodian.CLAIM_RECEIPT_FIELDS),
        ),
        (
            OUTCOME_SCHEMA_PATH,
            "urn:agent-bridge:biocortex-ab:track-b:sampling-write-outcome-custodian-receipt:v1",
            custodian.OUTCOME_RECEIPT_SCHEMA,
            set(custodian.OUTCOME_RECEIPT_FIELDS),
        ),
    )
    hashes: dict[str, str] = {}
    for path, expected_id, expected_instance, fields in rows:
        schema, raw = load_canonical(root / path, str(path))
        validate_receipt_schema(
            schema,
            expected_id=expected_id,
            expected_instance_schema=expected_instance,
            expected_fields=fields,
        )
        hashes[str(path)] = sha256_bytes(raw)
    require(
        hashes[str(REGISTRATION_SCHEMA_PATH)] == custodian.REGISTRATION_SCHEMA_SHA256,
        "registration schema source hash drift",
    )
    require(
        hashes[str(CLAIM_SCHEMA_PATH)] == custodian.CLAIM_SCHEMA_SHA256,
        "claim schema source hash drift",
    )
    require(
        hashes[str(OUTCOME_SCHEMA_PATH)] == custodian.OUTCOME_SCHEMA_SHA256,
        "outcome schema source hash drift",
    )
    return hashes


@dataclasses.dataclass(frozen=True)
class SyntheticContext:
    fixture: dict[str, Any]
    write_request: dict[str, Any]
    built_sampling_receipt: Any
    admission_policy_sha256: str
    contract_core_sha256: str
    eligible_frame_manifest_sha256: str
    strata_allocation_manifest_sha256: str
    sampling_attempt_namespace_sha256: str
    sampling_event_sha256: str


def build_synthetic_context(
    root: Path,
    fixture: dict[str, Any],
    custodian: Any,
    successor: Any,
) -> SyntheticContext:
    successor_fixture, successor_raw = load_canonical(
        root / SUCCESSOR_FIXTURE_PATH, "successor synthetic fixture"
    )
    require(
        sha256_bytes(successor_raw) == fixture["source_successor_fixture_sha256"],
        "successor synthetic fixture hash drift",
    )
    require(
        fixture["source_successor_fixture_path"] == str(SUCCESSOR_FIXTURE_PATH),
        "successor fixture path drift",
    )
    policy_raw = (root / ADMISSION_POLICY_PATH).read_bytes()
    admission_sha256 = sha256_bytes(policy_raw)
    require(
        admission_sha256 == fixture["custodian_config"]["admission_policy_sha256"],
        "synthetic admission policy binding drift",
    )
    write_request, built, _seed = successor._sampling_request(
        root, successor_fixture, admission_sha256
    )
    require(write_request["contract_core"]["trial_id"] == fixture["trial_id"], "trial join drift")
    core_sha = sha256_object(write_request["contract_core"])
    frame_sha = sha256_object(write_request["eligible_frame_manifest"])
    allocation_sha = sha256_object(write_request["strata_allocation_manifest"])
    namespace = custodian.derive_sampling_attempt_namespace(fixture["trial_id"])
    event = custodian.derive_sampling_event(
        core_sha,
        fixture["trial_id"],
        frame_sha,
        allocation_sha,
    )
    return SyntheticContext(
        fixture=fixture,
        write_request=write_request,
        built_sampling_receipt=built,
        admission_policy_sha256=admission_sha256,
        contract_core_sha256=core_sha,
        eligible_frame_manifest_sha256=frame_sha,
        strata_allocation_manifest_sha256=allocation_sha,
        sampling_attempt_namespace_sha256=namespace,
        sampling_event_sha256=event,
    )


def make_config(custodian: Any, context: SyntheticContext, store_path: Path) -> Any:
    values = context.fixture["custodian_config"]
    return custodian.CustodianConfig(store_path=store_path, **values)


def registration_request(custodian: Any, context: SyntheticContext) -> dict[str, Any]:
    fixture = context.fixture
    owner = fixture["owner_registration"]
    return {
        "schema": custodian.REGISTRATION_REQUEST_SCHEMA,
        "protocol_version": 1,
        "trial_id": fixture["trial_id"],
        "registered_at_utc": owner["registered_at_utc"],
        "admission_policy_sha256": context.admission_policy_sha256,
        "contract_core_sha256": context.contract_core_sha256,
        "eligible_frame_manifest_sha256": context.eligible_frame_manifest_sha256,
        "strata_allocation_manifest_sha256": context.strata_allocation_manifest_sha256,
        "sampling_attempt_namespace_sha256": context.sampling_attempt_namespace_sha256,
        "sampling_event_sha256": context.sampling_event_sha256,
        "owner_authorization_receipt_sha256": owner[
            "owner_authorization_receipt_sha256"
        ],
        "owner_freeze_receipt_sha256": owner["owner_freeze_receipt_sha256"],
        "owner_trust_policy_sha256": fixture["custodian_config"][
            "owner_trust_policy_sha256"
        ],
    }


def claim_request(
    custodian: Any,
    context: SyntheticContext,
    registration_sha256: str,
    config: Any,
) -> dict[str, Any]:
    return {
        "schema": custodian.CLAIM_REQUEST_SCHEMA,
        "protocol_version": 1,
        "trial_id": context.fixture["trial_id"],
        "claimed_at_utc": context.fixture["claim"]["claimed_at_utc"],
        "owner_trial_registration_receipt_sha256": registration_sha256,
        "admission_policy_sha256": context.admission_policy_sha256,
        "contract_core_sha256": context.contract_core_sha256,
        "eligible_frame_manifest_sha256": context.eligible_frame_manifest_sha256,
        "strata_allocation_manifest_sha256": context.strata_allocation_manifest_sha256,
        "sampling_attempt_namespace_sha256": context.sampling_attempt_namespace_sha256,
        "sampling_event_sha256": context.sampling_event_sha256,
        "custody_target_sha256": custodian.derive_custody_target(
            config.custodian_instance_sha256,
            context.sampling_attempt_namespace_sha256,
        ),
    }


def outcome_request(
    custodian: Any,
    context: SyntheticContext,
    registration_sha256: str,
    claim_sha256: str,
    config: Any,
    *,
    outcome: str,
) -> dict[str, Any]:
    base = {
        "schema": custodian.OUTCOME_REQUEST_SCHEMA,
        "protocol_version": 1,
        "trial_id": context.fixture["trial_id"],
        "finalized_at_utc": context.fixture[
            "success" if outcome == "SUCCESS" else "abort"
        ]["finalized_at_utc"],
        "owner_trial_registration_receipt_sha256": registration_sha256,
        "sampling_attempt_namespace_claim_receipt_sha256": claim_sha256,
        "admission_policy_sha256": context.admission_policy_sha256,
        "contract_core_sha256": context.contract_core_sha256,
        "eligible_frame_manifest_sha256": context.eligible_frame_manifest_sha256,
        "strata_allocation_manifest_sha256": context.strata_allocation_manifest_sha256,
        "sampling_attempt_namespace_sha256": context.sampling_attempt_namespace_sha256,
        "sampling_event_sha256": context.sampling_event_sha256,
        "custody_target_sha256": custodian.derive_custody_target(
            config.custodian_instance_sha256,
            context.sampling_attempt_namespace_sha256,
        ),
        "outcome": outcome,
    }
    if outcome == "SUCCESS":
        base.update(
            {
                "write_state": "COMPLETE_DURABLE_OBSERVED",
                "external_entropy_sha256": context.write_request[
                    "external_entropy_sha256"
                ],
                "sampling_write_request_sha256": sha256_object(context.write_request),
                "abort_reason_code": None,
                "failure_evidence_sha256": None,
            }
        )
    else:
        abort = context.fixture["abort"]
        base.update(
            {
                "write_state": abort["write_state"],
                "external_entropy_sha256": None,
                "sampling_write_request_sha256": None,
                "abort_reason_code": abort["abort_reason_code"],
                "failure_evidence_sha256": abort["failure_evidence_sha256"],
            }
        )
    return base


def initialize_store(custodian: Any, config: Any) -> None:
    config.store_path.parent.mkdir(mode=0o700, parents=True, exist_ok=False)
    custodian.initialize_custodian(
        config,
        created_at_utc="2026-07-14T11:59:50Z",
    )


def write_sampling_receipt(
    successor: Any,
    context: SyntheticContext,
    receipt_directory: Path,
) -> Path:
    receipt_directory.mkdir(mode=0o700)
    directory_fd = os.open(
        receipt_directory,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        successor.writer.write_sampling_receipt_o_excl(
            directory_fd,
            context.built_sampling_receipt,
        )
    finally:
        os.close(directory_fd)
    return receipt_directory


def record_success_outcome(
    custodian: Any,
    config: Any,
    outcome_bytes: bytes,
    context: SyntheticContext,
    receipt_directory: Path,
    *,
    sampling_write_request_bytes: bytes | None = None,
) -> Any:
    directory_fd = os.open(
        receipt_directory,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        return custodian.record_sampling_outcome(
            config,
            outcome_bytes,
            sampling_write_request_bytes=(
                canonical_bytes(context.write_request)
                if sampling_write_request_bytes is None
                else sampling_write_request_bytes
            ),
            sampling_receipt_directory_fd=directory_fd,
        )
    finally:
        os.close(directory_fd)


def run_success_path(
    root: Path,
    custodian: Any,
    successor: Any,
    context: SyntheticContext,
    base: Path,
) -> dict[str, Any]:
    config = make_config(custodian, context, base / "ledger" / custodian.STORE_BASENAME)
    initialize_store(custodian, config)
    registration_raw = canonical_bytes(registration_request(custodian, context))
    registration = custodian.register_owner_trial(config, registration_raw)
    claim_raw = canonical_bytes(
        claim_request(custodian, context, registration.receipt_sha256, config)
    )
    claim = custodian.claim_sampling_attempt(config, claim_raw)
    receipt_directory = write_sampling_receipt(
        successor, context, base / "sampling-receipt-private"
    )
    outcome_raw = canonical_bytes(
        outcome_request(
            custodian,
            context,
            registration.receipt_sha256,
            claim.receipt_sha256,
            config,
            outcome="SUCCESS",
        )
    )
    outcome = record_success_outcome(
        custodian,
        config,
        outcome_raw,
        context,
        receipt_directory,
    )
    require(
        custodian.query_owner_trial(config, context.fixture["trial_id"])
        == registration,
        "registration query does not return exact stored receipt",
    )
    require(
        custodian.query_sampling_attempt_claim(
            config, context.sampling_attempt_namespace_sha256
        )
        == claim,
        "claim query does not return exact stored receipt",
    )
    require(
        custodian.query_sampling_outcome(
            config, context.sampling_attempt_namespace_sha256
        )
        == outcome,
        "outcome query does not return exact stored receipt",
    )
    for stored in (registration, claim, outcome):
        require(
            custodian.query_exact_receipt(config, stored.receipt_sha256) == stored,
            "exact receipt lookup drift",
        )
        require(stored.receipt["condition_output_authorized"] is False, "receipt raises output authority")
        require(stored.receipt["external_global_single_use_verified"] is False, "receipt invents global single use")
    return {
        "config": config,
        "registration": registration,
        "claim": claim,
        "outcome": outcome,
        "receipt_directory": receipt_directory,
    }


def run_abort_path(
    custodian: Any,
    context: SyntheticContext,
    base: Path,
) -> dict[str, Any]:
    config = make_config(custodian, context, base / "ledger" / custodian.STORE_BASENAME)
    initialize_store(custodian, config)
    registration = custodian.register_owner_trial(
        config, canonical_bytes(registration_request(custodian, context))
    )
    claim = custodian.claim_sampling_attempt(
        config,
        canonical_bytes(
            claim_request(custodian, context, registration.receipt_sha256, config)
        ),
    )
    outcome = custodian.record_sampling_outcome(
        config,
        canonical_bytes(
            outcome_request(
                custodian,
                context,
                registration.receipt_sha256,
                claim.receipt_sha256,
                config,
                outcome="TERMINAL_ABORT",
            )
        ),
    )
    require(outcome.receipt["outcome"] == "TERMINAL_ABORT", "abort outcome drift")
    require(outcome.receipt["sampling_receipt_sha256"] is None, "abort invented sampling receipt")
    return {"config": config, "registration": registration, "claim": claim, "outcome": outcome}


def validate_synthetic_fixture(fixture: dict[str, Any], raw: bytes) -> None:
    exact_keys(
        fixture,
        {
            "abort",
            "boundary",
            "claim",
            "custodian_config",
            "expected",
            "owner_registration",
            "schema",
            "source_successor_fixture_path",
            "source_successor_fixture_sha256",
            "success",
            "synthetic_only",
            "trial_id",
        },
        "synthetic fixture",
    )
    require(fixture["schema"] == SYNTHETIC_SCHEMA, "synthetic schema drift")
    require(fixture["synthetic_only"] is True, "synthetic fixture loses synthetic label")
    require(
        fixture["boundary"]
        == {
            "condition_output_authorized": False,
            "external_anti_rollback_anchor_present": False,
            "external_global_single_use_verified": False,
            "external_owner_trust_verified": False,
            "fixture_only": True,
            "live_binding_satisfied_count": 0,
            "real_run_admitted": False,
            "side_effects_unlocked": "NONE",
        },
        "synthetic authority boundary drift",
    )
    require(len(raw) < 64 * 1024, "synthetic fixture exceeds bounded profile")


def validate_manifest(
    manifest: dict[str, Any],
    raw: bytes,
    root: Path,
    synthetic_raw: bytes,
    schema_hashes: dict[str, str],
    custodian: Any,
) -> None:
    exact_keys(
        manifest,
        {
            "artifact_bindings",
            "baseline_commit",
            "boundary",
            "canonical_serialization",
            "data_quality_contract",
            "date",
            "decision",
            "evidence_sha256",
            "known_limitation",
            "next_unit",
            "predecessor",
            "schema",
            "self_test_expected_sha256",
            "sqlite_profile",
            "state_machine",
            "synthetic_fixture_path",
            "synthetic_fixture_sha256",
        },
        "pack manifest",
    )
    require(manifest["schema"] == PACK_SCHEMA, "manifest schema drift")
    require(manifest["baseline_commit"] == BASELINE_COMMIT, "manifest baseline drift")
    require(manifest["decision"] == PACK_DECISION, "manifest decision drift")
    require(manifest["date"] == "2026-07-14", "manifest date drift")
    require(
        type(manifest["self_test_expected_sha256"]) is str
        and re.fullmatch(SHA_RE_TEXT, manifest["self_test_expected_sha256"]) is not None,
        "manifest self-test output hash drift",
    )
    require(
        manifest["self_test_expected_sha256"] == SELF_TEST_EXPECTED_SHA256,
        "manifest self-test oracle hash drift",
    )
    require(manifest["canonical_serialization"] == CANONICAL_PROFILE, "canonical profile drift")
    require(manifest["synthetic_fixture_path"] == str(SYNTHETIC_PATH), "manifest fixture path drift")
    require(manifest["synthetic_fixture_sha256"] == sha256_bytes(synthetic_raw), "manifest fixture hash drift")
    expected_artifacts = [
        (REGISTRATION_SCHEMA_PATH, "owner_trial_registration_receipt_schema"),
        (CLAIM_SCHEMA_PATH, "sampling_attempt_claim_receipt_schema"),
        (OUTCOME_SCHEMA_PATH, "sampling_write_outcome_receipt_schema"),
        (CUSTODIAN_PATH, "sampling_attempt_custodian_source"),
    ]
    bindings = manifest["artifact_bindings"]
    require(type(bindings) is list and len(bindings) == 4, "artifact binding count drift")
    for row, (path, kind) in zip(bindings, expected_artifacts, strict=True):
        exact_keys(row, {"artifact_kind", "repo_path", "sha256", "status"}, "artifact binding")
        require(row["repo_path"] == str(path) and row["artifact_kind"] == kind, "artifact binding identity drift")
        require(row["sha256"] == sha256_bytes((root / path).read_bytes()), "artifact binding hash drift")
        require("NOT_LIVE" in row["status"] or "LOCAL_REFERENCE" in row["status"], "artifact status overclaims")
    require(
        manifest["boundary"]
        == {
            "condition_output_authorized": False,
            "external_anti_rollback_anchor_present": False,
            "external_global_single_use_verified": False,
            "external_owner_trust_verified": False,
            "frozen_admission_v1_mutated": False,
            "frozen_graph_mutated": False,
            "frozen_ledger_mutated": False,
            "live_binding_satisfied_count": 0,
            "real_owner_registration_created": False,
            "real_run_admitted": False,
            "side_effects_unlocked": "NONE",
            "synthetic_fixture_only": True,
        },
        "manifest boundary drift",
    )
    require(
        manifest["state_machine"]
        == {
            "states": [
                "ABSENT",
                "REGISTERED",
                "CLAIMED",
                "TERMINAL_SUCCESS",
                "TERMINAL_ABORT",
            ],
            "claim_is_required_before_terminal_outcome": True,
            "claim_precedes_external_entropy_and_sampling_write_attested": False,
            "claimed_namespace_released_on_failure": False,
            "exactly_one_terminal_outcome_per_claim": True,
            "retry_after_terminal_abort_allowed": False,
            "updates_deletes_expiry_and_gc_allowed": False,
        },
        "manifest state machine drift",
    )
    require(
        manifest["sqlite_profile"]
        == {
            "application_id": custodian.APPLICATION_ID,
            "foreign_keys": True,
            "journal_mode": "DELETE",
            "locking_mode": "NORMAL",
            "pathname_rebinding_rejected_before_return": True,
            "read_uncommitted": False,
            "runtime_create_allowed": False,
            "sqlite_connection_inode_binding_verified": True,
            "synchronous": "EXTRA",
            "trusted_schema": False,
            "user_version": custodian.USER_VERSION,
        },
        "manifest SQLite profile drift",
    )
    require(
        manifest["data_quality_contract"]
        == {
            "grains": {
                "attempt_claim": "local_custodian_instance_x_sampling_attempt_namespace",
                "ledger_event": "local_custodian_instance_x_monotonic_sequence",
                "owner_trial_registration": "local_registry_generation_x_trial_id",
                "terminal_outcome": "local_custodian_instance_x_sampling_attempt_namespace",
            },
            "join_rules": [
                "REGISTRATION_BINDS_EXACT_POLICY_CORE_FRAME_ALLOCATION_NAMESPACE_AND_EVENT",
                "CLAIM_EXACTLY_CONSUMES_ONE_REGISTRATION_AND_THE_SAME_FULL_TUPLE",
                "OUTCOME_EXACTLY_CONSUMES_ONE_CLAIM_AND_THE_SAME_FULL_TUPLE",
                "TRIAL_ID_PRIMARY_KEY_IS_NOT_PROTOCOL_SCOPED_WITHIN_THE_LOCAL_STORE",
                "EXTERNAL_GLOBAL_TRIAL_UNIQUENESS_IS_NOT_VERIFIED",
                "ONE_CLAIM_AND_ONE_TERMINAL_OUTCOME_PER_ATTEMPT_NAMESPACE",
                "SUCCESS_WRITE_REQUEST_REPLAY_RECEIPT_REREAD_AND_OBSERVATION_HASH_ARE_CUSTODIAN_DERIVED",
                "NO_UPDATE_DELETE_EXPIRY_GC_ALIAS_OR_MANY_TO_MANY_JOIN",
            ],
        },
        "manifest data quality contract drift",
    )
    require(
        manifest["known_limitation"]
        == {
            "dedicated_custodian_euid_required": True,
            "local_snapshot_rollback_attack_expected_to_reproduce": True,
            "local_sqlite_is_external_linearizable_custodian": False,
            "on_disk_source_hash_is_not_loaded_code_attestation": True,
            "old_snapshot_restore_detected_without_external_anchor": False,
            "production_claim_requires_external_owner_trust_and_anti_rollback": True,
            "same_euid_untrusted_processes_excluded_from_local_profile": True,
        },
        "manifest known limitation drift",
    )
    require(
        manifest["next_unit"]
        == "FIRST_CONDITION_OUTPUT_GUARD_V1_SOURCE_PACK_WITH_EXTERNAL_AUTHORITY_STILL_REQUIRED",
        "manifest next unit drift",
    )
    require(sha256_bytes(raw) == sha256_object(manifest), "manifest canonical hash drift")
    evidence = manifest["evidence_sha256"]
    require(type(evidence) is dict and evidence == {key: evidence[key] for key in sorted(evidence)}, "manifest evidence order drift")
    require(set(evidence) == EXPECTED_EVIDENCE_PATHS, "manifest evidence path set drift")
    for path, expected in evidence.items():
        parsed_path = PurePosixPath(path)
        require(
            type(path) is str
            and path == parsed_path.as_posix()
            and not parsed_path.is_absolute()
            and path not in {"", "."}
            and ".." not in parsed_path.parts,
            f"manifest evidence path is not normalized repo-relative POSIX: {path}",
        )
        require(sha256_bytes((root / path).read_bytes()) == expected, f"manifest evidence hash drift: {path}")
    for path, expected in schema_hashes.items():
        require(evidence.get(path) == expected, f"schema missing from evidence ledger: {path}")


def validate_report(
    root: Path,
    manifest: dict[str, Any],
    manifest_raw: bytes,
    synthetic_raw: bytes,
    schema_hashes: dict[str, str],
) -> None:
    try:
        raw = (root / REPORT_PATH).read_bytes()
        report = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        fail(f"cannot read technical report: {exc}")
    require(1 <= len(raw) <= 262_144 and not raw.startswith(b"\xef\xbb\xbf"), "technical report byte profile drift")
    expected_raw = (root / EXPECTED_PATH).read_bytes()
    identities = {
        "Owner-trial registration receipt schema v1": schema_hashes[
            str(REGISTRATION_SCHEMA_PATH)
        ],
        "Sampling-attempt claim receipt schema v1": schema_hashes[
            str(CLAIM_SCHEMA_PATH)
        ],
        "Sampling-write outcome receipt schema v1": schema_hashes[
            str(OUTCOME_SCHEMA_PATH)
        ],
        "Custodian source": sha256_bytes((root / CUSTODIAN_PATH).read_bytes()),
        "Purpose checker": sha256_bytes((root / PURPOSE_PATH).read_bytes()),
        "Synthetic fixture": sha256_bytes(synthetic_raw),
        "Expected normal TSV": sha256_bytes(expected_raw),
        "Pack manifest": sha256_bytes(manifest_raw),
        "Self-test output": manifest["self_test_expected_sha256"],
        "Source-bound Git gate": sha256_bytes((root / GATE_PATH).read_bytes()),
    }
    required_fragments = [
        f"Decision: `{PACK_DECISION}`",
        "| Directed mutations rejected | 67 |",
        "| `SIGKILL` transaction boundaries checked | 6 |",
        "| Filesystem/schema attacks rejected | 13 |",
        "| Unexpected-exception cleanup checks | 1 |",
        "| Whole-store old-snapshot attack reproduced | Yes |",
        "cannot attest that an untrusted caller",
        "requires a dedicated custodian euid",
        "not an external custody attestation",
    ]
    for fragment in required_fragments:
        require(fragment in report, f"technical report fact drift: {fragment}")
    concurrency_rows = [
        "| Concurrent claim winners | 1 |",
        "| Concurrent claim losers | 5 |",
        "| Concurrent terminal-outcome winners | 1 |",
        "| Concurrent terminal-outcome losers | 1 |",
    ]
    for row in concurrency_rows:
        require(report.count(row) == 1, f"technical report metric cardinality drift: {row}")
    for label, digest in identities.items():
        row = f"| {label} | `{digest}` |"
        require(report.count(row) == 1, f"technical report identity drift: {label}")


RESULT_ORDER = (
    "schema",
    "decision",
    "protocol_version",
    "trial_id",
    "sampling_attempt_namespace_sha256",
    "sampling_event_sha256",
    "custody_target_sha256",
    "registration_receipt_sha256",
    "claim_receipt_sha256",
    "success_outcome_receipt_sha256",
    "abort_outcome_receipt_sha256",
    "custodian_source_sha256",
    "custodian_store_schema_sha256",
    "registration_receipt_schema_sha256",
    "claim_receipt_schema_sha256",
    "outcome_receipt_schema_sha256",
    "success_terminal_outcome",
    "success_ledger_event_count",
    "owner_registration_count",
    "claim_count",
    "success_terminal_count",
    "abort_terminal_count",
    "sqlite_journal_mode",
    "sqlite_synchronous",
    "sqlite_foreign_keys",
    "sqlite_trusted_schema",
    "sqlite_read_uncommitted",
    "sqlite_locking_mode",
    "external_owner_trust_verified",
    "external_anti_rollback_anchor_present",
    "external_global_single_use_verified",
    "known_local_snapshot_rollback_attack_reproduced",
    "condition_output_authorized",
    "live_binding_satisfied_count",
    "side_effects_unlocked",
)


def render_result(rows: dict[str, Any]) -> str:
    require(set(rows) == set(RESULT_ORDER), "result field set drift")
    return "".join(
        f"{key}\t{str(rows[key]).lower() if type(rows[key]) is bool else rows[key]}\n"
        for key in RESULT_ORDER
    )


def _config_kwargs(config: Any) -> dict[str, Any]:
    values = dataclasses.asdict(config)
    values["store_path"] = str(values["store_path"])
    return values


def _load_worker_module(path: str, suffix: str) -> Any:
    module_path = Path(path)
    spec = importlib.util.spec_from_file_location(
        f"_track_b_custodian_worker_{suffix}_{os.getpid()}", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load custodian worker module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _claim_worker(
    source_path: str,
    config_values: dict[str, Any],
    request_bytes: bytes,
    result_path: str,
) -> None:
    try:
        module = _load_worker_module(source_path, "claim")
        values = dict(config_values)
        values["store_path"] = Path(values["store_path"])
        config = module.CustodianConfig(**values)
        stored = module.claim_sampling_attempt(config, request_bytes)
        Path(result_path).write_text(
            f"ok\t{stored.receipt_sha256}\n", encoding="utf-8"
        )
    except Exception as exc:
        code = getattr(exc, "code", type(exc).__name__)
        Path(result_path).write_text(f"error\t{code}\n", encoding="utf-8")


def _outcome_worker(
    source_path: str,
    config_values: dict[str, Any],
    request_bytes: bytes,
    result_path: str,
    sampling_write_request_bytes: bytes | None = None,
    sampling_receipt_directory_fd: int | None = None,
) -> None:
    try:
        module = _load_worker_module(source_path, "outcome")
        values = dict(config_values)
        values["store_path"] = Path(values["store_path"])
        config = module.CustodianConfig(**values)
        stored = module.record_sampling_outcome(
            config,
            request_bytes,
            sampling_write_request_bytes=sampling_write_request_bytes,
            sampling_receipt_directory_fd=sampling_receipt_directory_fd,
        )
        Path(result_path).write_text(
            f"ok\t{stored.receipt_sha256}\n", encoding="utf-8"
        )
    except Exception as exc:
        code = getattr(exc, "code", type(exc).__name__)
        Path(result_path).write_text(f"error\t{code}\n", encoding="utf-8")


def _paused_worker(
    source_path: str,
    operation: str,
    config_values: dict[str, Any],
    request_bytes: bytes,
    pause_stage: str,
    marker_path: str,
) -> None:
    module = _load_worker_module(source_path, f"pause_{operation}")
    values = dict(config_values)
    values["store_path"] = Path(values["store_path"])
    config = module.CustodianConfig(**values)

    def hook(stage: str) -> None:
        if stage != pause_stage:
            return
        marker = Path(marker_path)
        marker.write_text(stage + "\n", encoding="utf-8")
        while True:
            signal.pause()

    target = {
        "claim": module.claim_sampling_attempt,
        "outcome": module.record_sampling_outcome,
    }[operation]
    target(config, request_bytes, _fault_hook=hook)


def _wait_for_marker(path: Path, process: multiprocessing.Process) -> None:
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if path.is_file():
            return
        if not process.is_alive():
            fail(f"fault worker exited before marker: exit={process.exitcode}")
        time.sleep(0.01)
    fail("fault worker did not reach marker")


def _kill_at_stage(
    source_path: Path,
    operation: str,
    config: Any,
    request_bytes: bytes,
    stage: str,
    base: Path,
) -> None:
    marker = base / f"{operation}-{stage}.marker"
    ctx = multiprocessing.get_context("fork")
    process = ctx.Process(
        target=_paused_worker,
        args=(
            str(source_path),
            operation,
            _config_kwargs(config),
            request_bytes,
            stage,
            str(marker),
        ),
    )
    process.start()
    _wait_for_marker(marker, process)
    os.kill(process.pid, signal.SIGKILL)
    process.join(10)
    require(process.exitcode == -signal.SIGKILL, "fault worker was not SIGKILLed")


def _expect_rejected(custodian: Any, label: str, call: Callable[[], Any]) -> None:
    try:
        call()
    except custodian.CustodianError:
        return
    fail(f"directed negative accepted: {label}")


def _set_path(value: dict[str, Any], path: tuple[str, ...], replacement: Any) -> None:
    cursor: Any = value
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = replacement


def _mutated_bytes(
    source: dict[str, Any],
    mutate: Callable[[dict[str, Any]], None],
) -> bytes:
    candidate = copy.deepcopy(source)
    mutate(candidate)
    return canonical_bytes(candidate)


def _new_prepared_store(
    custodian: Any,
    context: SyntheticContext,
    base: Path,
    label: str,
    *,
    claim: bool,
) -> tuple[Any, Any, Any | None]:
    config = make_config(
        custodian,
        context,
        base / label / "ledger" / custodian.STORE_BASENAME,
    )
    initialize_store(custodian, config)
    registration = custodian.register_owner_trial(
        config, canonical_bytes(registration_request(custodian, context))
    )
    claimed = None
    if claim:
        claimed = custodian.claim_sampling_attempt(
            config,
            canonical_bytes(
                claim_request(
                    custodian,
                    context,
                    registration.receipt_sha256,
                    config,
                )
            ),
        )
    return config, registration, claimed


def run_directed_mutations(
    custodian: Any,
    context: SyntheticContext,
    receipt_directory: Path,
    base: Path,
) -> int:
    rejected = 0
    counter = 0

    registration_base = registration_request(custodian, context)
    registration_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("registration-schema", lambda x: _set_path(x, ("schema",), "wrong")),
        ("registration-protocol", lambda x: _set_path(x, ("protocol_version",), 2)),
        ("registration-trial", lambda x: _set_path(x, ("trial_id",), "different_trial")),
        ("registration-time", lambda x: _set_path(x, ("registered_at_utc",), "not-a-time")),
        ("registration-policy", lambda x: _set_path(x, ("admission_policy_sha256",), "0" * 64)),
        ("registration-core", lambda x: _set_path(x, ("contract_core_sha256",), "0" * 64)),
        ("registration-frame", lambda x: _set_path(x, ("eligible_frame_manifest_sha256",), "0" * 64)),
        ("registration-allocation", lambda x: _set_path(x, ("strata_allocation_manifest_sha256",), "0" * 64)),
        ("registration-namespace", lambda x: _set_path(x, ("sampling_attempt_namespace_sha256",), "0" * 64)),
        ("registration-event", lambda x: _set_path(x, ("sampling_event_sha256",), "0" * 64)),
        ("registration-owner-auth", lambda x: _set_path(x, ("owner_authorization_receipt_sha256",), "0" * 64)),
        ("registration-owner-freeze", lambda x: _set_path(x, ("owner_freeze_receipt_sha256",), None)),
        ("registration-owner-trust", lambda x: _set_path(x, ("owner_trust_policy_sha256",), "0" * 64)),
        ("registration-missing", lambda x: x.pop("sampling_event_sha256")),
        ("registration-extra", lambda x: x.update({"external_entropy_sha256": "0" * 64})),
    ]
    for label, mutate in registration_mutations:
        config = make_config(
            custodian,
            context,
            base / f"mutation-{counter}" / "ledger" / custodian.STORE_BASENAME,
        )
        counter += 1
        initialize_store(custodian, config)
        _expect_rejected(
            custodian,
            label,
            lambda c=config, b=_mutated_bytes(registration_base, mutate): custodian.register_owner_trial(c, b),
        )
        rejected += 1

    config = make_config(
        custodian,
        context,
        base / f"mutation-{counter}" / "ledger" / custodian.STORE_BASENAME,
    )
    counter += 1
    initialize_store(custodian, config)
    noncanonical = json.dumps(registration_base, sort_keys=True).encode("utf-8")
    _expect_rejected(
        custodian,
        "registration-noncanonical",
        lambda: custodian.register_owner_trial(config, noncanonical),
    )
    rejected += 1

    config, registration, _ = _new_prepared_store(
        custodian, context, base, f"mutation-{counter}", claim=False
    )
    counter += 1
    claim_base = claim_request(
        custodian, context, registration.receipt_sha256, config
    )
    claim_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("claim-schema", lambda x: _set_path(x, ("schema",), "wrong")),
        ("claim-protocol", lambda x: _set_path(x, ("protocol_version",), 0)),
        ("claim-trial", lambda x: _set_path(x, ("trial_id",), "different_trial")),
        ("claim-time-order", lambda x: _set_path(x, ("claimed_at_utc",), context.fixture["owner_registration"]["registered_at_utc"])),
        ("claim-registration", lambda x: _set_path(x, ("owner_trial_registration_receipt_sha256",), "0" * 64)),
        ("claim-policy", lambda x: _set_path(x, ("admission_policy_sha256",), "0" * 64)),
        ("claim-core", lambda x: _set_path(x, ("contract_core_sha256",), "0" * 64)),
        ("claim-frame", lambda x: _set_path(x, ("eligible_frame_manifest_sha256",), "0" * 64)),
        ("claim-allocation", lambda x: _set_path(x, ("strata_allocation_manifest_sha256",), "0" * 64)),
        ("claim-namespace", lambda x: _set_path(x, ("sampling_attempt_namespace_sha256",), "0" * 64)),
        ("claim-event", lambda x: _set_path(x, ("sampling_event_sha256",), "0" * 64)),
        ("claim-custody", lambda x: _set_path(x, ("custody_target_sha256",), "0" * 64)),
        ("claim-missing", lambda x: x.pop("sampling_event_sha256")),
        ("claim-extra-entropy", lambda x: x.update({"external_entropy_sha256": "0" * 64})),
    ]
    for label, mutate in claim_mutations:
        _expect_rejected(
            custodian,
            label,
            lambda b=_mutated_bytes(claim_base, mutate): custodian.claim_sampling_attempt(config, b),
        )
        rejected += 1
    claim = custodian.claim_sampling_attempt(config, canonical_bytes(claim_base))
    _expect_rejected(
        custodian,
        "claim-exact-retry",
        lambda: custodian.claim_sampling_attempt(config, canonical_bytes(claim_base)),
    )
    rejected += 1
    require(
        custodian.query_sampling_attempt_claim(
            config, context.sampling_attempt_namespace_sha256
        )
        == claim,
        "claim retry changed winner",
    )

    config, registration, claim = _new_prepared_store(
        custodian, context, base, f"mutation-{counter}", claim=True
    )
    counter += 1
    assert claim is not None
    outcome_base = outcome_request(
        custodian,
        context,
        registration.receipt_sha256,
        claim.receipt_sha256,
        config,
        outcome="SUCCESS",
    )
    outcome_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("outcome-schema", lambda x: _set_path(x, ("schema",), "wrong")),
        ("outcome-protocol", lambda x: _set_path(x, ("protocol_version",), 2)),
        ("outcome-trial", lambda x: _set_path(x, ("trial_id",), "different_trial")),
        ("outcome-time-order", lambda x: _set_path(x, ("finalized_at_utc",), context.fixture["claim"]["claimed_at_utc"])),
        ("outcome-registration", lambda x: _set_path(x, ("owner_trial_registration_receipt_sha256",), "0" * 64)),
        ("outcome-claim", lambda x: _set_path(x, ("sampling_attempt_namespace_claim_receipt_sha256",), "0" * 64)),
        ("outcome-policy", lambda x: _set_path(x, ("admission_policy_sha256",), "0" * 64)),
        ("outcome-core", lambda x: _set_path(x, ("contract_core_sha256",), "0" * 64)),
        ("outcome-frame", lambda x: _set_path(x, ("eligible_frame_manifest_sha256",), "0" * 64)),
        ("outcome-allocation", lambda x: _set_path(x, ("strata_allocation_manifest_sha256",), "0" * 64)),
        ("outcome-namespace", lambda x: _set_path(x, ("sampling_attempt_namespace_sha256",), "0" * 64)),
        ("outcome-event", lambda x: _set_path(x, ("sampling_event_sha256",), "0" * 64)),
        ("outcome-custody", lambda x: _set_path(x, ("custody_target_sha256",), "0" * 64)),
        ("outcome-tag", lambda x: _set_path(x, ("outcome",), "PENDING")),
        ("outcome-write-state", lambda x: _set_path(x, ("write_state",), "PARTIAL_OR_AMBIGUOUS")),
        ("outcome-entropy", lambda x: _set_path(x, ("external_entropy_sha256",), "0" * 64)),
        ("outcome-write-request", lambda x: _set_path(x, ("sampling_write_request_sha256",), "0" * 64)),
        ("outcome-caller-receipt-object", lambda x: x.update({"sampling_receipt": context.built_sampling_receipt.receipt})),
        ("outcome-caller-observation-object", lambda x: x.update({"sampling_write_observation": {"parent_directory_fsync_completed": True}})),
        ("outcome-abort-reason", lambda x: _set_path(x, ("abort_reason_code",), "NOT_NULL")),
        ("outcome-failure", lambda x: _set_path(x, ("failure_evidence_sha256",), "0" * 64)),
        ("outcome-missing", lambda x: x.pop("sampling_event_sha256")),
        ("outcome-extra", lambda x: x.update({"condition_output_authorized": True})),
    ]
    for label, mutate in outcome_mutations:
        _expect_rejected(
            custodian,
            label,
            lambda b=_mutated_bytes(outcome_base, mutate): record_success_outcome(
                custodian,
                config,
                b,
                context,
                receipt_directory,
            ),
        )
        rejected += 1
    _expect_rejected(
        custodian,
        "outcome-missing-success-evidence",
        lambda: custodian.record_sampling_outcome(
            config,
            canonical_bytes(outcome_base),
        ),
    )
    rejected += 1
    _expect_rejected(
        custodian,
        "outcome-missing-receipt-directory",
        lambda: custodian.record_sampling_outcome(
            config,
            canonical_bytes(outcome_base),
            sampling_write_request_bytes=canonical_bytes(context.write_request),
        ),
    )
    rejected += 1
    directory_only_fd = os.open(
        receipt_directory,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        _expect_rejected(
            custodian,
            "outcome-missing-write-request-bytes",
            lambda: custodian.record_sampling_outcome(
                config,
                canonical_bytes(outcome_base),
                sampling_receipt_directory_fd=directory_only_fd,
            ),
        )
        rejected += 1
    finally:
        os.close(directory_only_fd)
    mismatched_write_request = copy.deepcopy(context.write_request)
    mismatched_write_request["external_entropy_sha256"] = "f" * 64
    _expect_rejected(
        custodian,
        "outcome-write-request-bytes",
        lambda: record_success_outcome(
            custodian,
            config,
            canonical_bytes(outcome_base),
            context,
            receipt_directory,
            sampling_write_request_bytes=canonical_bytes(mismatched_write_request),
        ),
    )
    rejected += 1

    receipt_path = receipt_directory / "sampling-receipt.json"
    original_receipt_bytes = receipt_path.read_bytes()
    forged_receipt = json.loads(original_receipt_bytes.decode("utf-8"))
    forged_receipt["selection_commitment_sha256"] = "f" * 64
    os.chmod(receipt_path, 0o600)
    receipt_path.write_bytes(canonical_bytes(forged_receipt))
    os.chmod(receipt_path, 0o400)
    try:
        _expect_rejected(
            custodian,
            "outcome-forged-sealed-receipt",
            lambda: record_success_outcome(
                custodian,
                config,
                canonical_bytes(outcome_base),
                context,
                receipt_directory,
            ),
        )
        rejected += 1
    finally:
        os.chmod(receipt_path, 0o600)
        receipt_path.write_bytes(original_receipt_bytes)
        os.chmod(receipt_path, 0o400)

    unexpected = receipt_directory / "unexpected-entry"
    unexpected.write_text("unexpected\n", encoding="utf-8")
    try:
        _expect_rejected(
            custodian,
            "outcome-receipt-directory-extra-entry",
            lambda: record_success_outcome(
                custodian,
                config,
                canonical_bytes(outcome_base),
                context,
                receipt_directory,
            ),
        )
        rejected += 1
    finally:
        unexpected.unlink()

    outcome = record_success_outcome(
        custodian,
        config,
        canonical_bytes(outcome_base),
        context,
        receipt_directory,
    )
    _expect_rejected(
        custodian,
        "outcome-exact-retry",
        lambda: record_success_outcome(
            custodian,
            config,
            canonical_bytes(outcome_base),
            context,
            receipt_directory,
        ),
    )
    rejected += 1
    require(
        custodian.query_sampling_outcome(
            config, context.sampling_attempt_namespace_sha256
        )
        == outcome,
        "outcome retry changed winner",
    )

    config, registration, claim = _new_prepared_store(
        custodian, context, base, f"mutation-{counter}", claim=True
    )
    assert claim is not None
    abort_base = outcome_request(
        custodian,
        context,
        registration.receipt_sha256,
        claim.receipt_sha256,
        config,
        outcome="TERMINAL_ABORT",
    )
    abort_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("abort-complete-state", lambda x: _set_path(x, ("write_state",), "COMPLETE_DURABLE_OBSERVED")),
        ("abort-missing-reason", lambda x: _set_path(x, ("abort_reason_code",), None)),
        ("abort-missing-evidence", lambda x: _set_path(x, ("failure_evidence_sha256",), None)),
        ("abort-receipt-object", lambda x: x.update({"sampling_receipt": context.built_sampling_receipt.receipt})),
        ("abort-observation-object", lambda x: x.update({"sampling_write_observation": {"parent_directory_fsync_completed": True}})),
    ]
    for label, mutate in abort_mutations:
        _expect_rejected(
            custodian,
            label,
            lambda b=_mutated_bytes(abort_base, mutate): custodian.record_sampling_outcome(config, b),
        )
        rejected += 1
    abort_evidence_fd = os.open(
        receipt_directory,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        _expect_rejected(
            custodian,
            "abort-success-only-file-evidence",
            lambda: custodian.record_sampling_outcome(
                config,
                canonical_bytes(abort_base),
                sampling_write_request_bytes=canonical_bytes(context.write_request),
                sampling_receipt_directory_fd=abort_evidence_fd,
            ),
        )
        rejected += 1
    finally:
        os.close(abort_evidence_fd)
    return rejected


def run_concurrency_tests(
    root: Path,
    custodian: Any,
    context: SyntheticContext,
    receipt_directory: Path,
    base: Path,
) -> dict[str, int]:
    source_path = root / CUSTODIAN_PATH
    config, registration, _ = _new_prepared_store(
        custodian, context, base, "concurrent-claim", claim=False
    )
    request_raw = canonical_bytes(
        claim_request(custodian, context, registration.receipt_sha256, config)
    )
    result_dir = base / "concurrent-claim-results"
    result_dir.mkdir(mode=0o700)
    ctx = multiprocessing.get_context("fork")
    processes: list[multiprocessing.Process] = []
    for index in range(6):
        process = ctx.Process(
            target=_claim_worker,
            args=(
                str(source_path),
                _config_kwargs(config),
                request_raw,
                str(result_dir / f"result-{index}.txt"),
            ),
        )
        processes.append(process)
        process.start()
    for process in processes:
        process.join(20)
        require(process.exitcode == 0, f"concurrent claim worker failed: {process.exitcode}")
    results = [
        (result_dir / f"result-{index}.txt").read_text(encoding="utf-8").strip()
        for index in range(6)
    ]
    winners = [row for row in results if row.startswith("ok\t")]
    losers = [row for row in results if row.startswith("error\t")]
    require(len(winners) == 1 and len(losers) == 5, "concurrent claim is not one-winner")
    winner = custodian.query_sampling_attempt_claim(
        config, context.sampling_attempt_namespace_sha256
    )
    require(winner is not None and winners[0] == f"ok\t{winner.receipt_sha256}", "concurrent winner receipt drift")
    custodian.record_sampling_outcome(
        config,
        canonical_bytes(
            outcome_request(
                custodian,
                context,
                registration.receipt_sha256,
                winner.receipt_sha256,
                config,
                outcome="TERMINAL_ABORT",
            )
        ),
    )

    config, registration, claim = _new_prepared_store(
        custodian, context, base, "concurrent-outcome", claim=True
    )
    assert claim is not None
    success_raw = canonical_bytes(
        outcome_request(
            custodian,
            context,
            registration.receipt_sha256,
        claim.receipt_sha256,
        config,
        outcome="SUCCESS",
    )
    )
    abort_raw = canonical_bytes(
        outcome_request(
            custodian,
            context,
            registration.receipt_sha256,
            claim.receipt_sha256,
            config,
            outcome="TERMINAL_ABORT",
        )
    )
    outcome_dir = base / "concurrent-outcome-results"
    outcome_dir.mkdir(mode=0o700)
    receipt_directory_fd = os.open(
        receipt_directory,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        outcome_processes = [
            ctx.Process(
                target=_outcome_worker,
                args=(
                    str(source_path),
                    _config_kwargs(config),
                    raw,
                    str(outcome_dir / f"result-{index}.txt"),
                    canonical_bytes(context.write_request) if index == 0 else None,
                    receipt_directory_fd if index == 0 else None,
                ),
            )
            for index, raw in enumerate((success_raw, abort_raw))
        ]
        for process in outcome_processes:
            process.start()
        for process in outcome_processes:
            process.join(20)
            require(process.exitcode == 0, f"concurrent outcome worker failed: {process.exitcode}")
    finally:
        os.close(receipt_directory_fd)
    outcome_results = [
        (outcome_dir / f"result-{index}.txt").read_text(encoding="utf-8").strip()
        for index in range(2)
    ]
    require(
        sum(row.startswith("ok\t") for row in outcome_results) == 1
        and sum(row.startswith("error\t") for row in outcome_results) == 1,
        "success/abort race did not preserve one terminal winner",
    )
    terminal = custodian.query_sampling_outcome(
        config, context.sampling_attempt_namespace_sha256
    )
    require(terminal is not None, "concurrent outcome winner missing")
    return {
        "claim_winners": len(winners),
        "claim_losers": len(losers),
        "outcome_winners": 1,
        "outcome_losers": 1,
    }


def run_crash_tests(
    root: Path,
    custodian: Any,
    context: SyntheticContext,
    base: Path,
) -> int:
    source_path = root / CUSTODIAN_PATH
    boundaries = 0

    config, registration, _ = _new_prepared_store(
        custodian, context, base, "claim-precommit-kill", claim=False
    )
    raw = canonical_bytes(
        claim_request(custodian, context, registration.receipt_sha256, config)
    )
    _kill_at_stage(
        source_path, "claim", config, raw, "claim_before_commit", base
    )
    require(
        custodian.query_sampling_attempt_claim(
            config, context.sampling_attempt_namespace_sha256
        )
        is None,
        "pre-commit killed claim became visible",
    )
    claim = custodian.claim_sampling_attempt(config, raw)
    custodian.record_sampling_outcome(
        config,
        canonical_bytes(
            outcome_request(
                custodian,
                context,
                registration.receipt_sha256,
                claim.receipt_sha256,
                config,
                outcome="TERMINAL_ABORT",
            )
        ),
    )
    boundaries += 1

    config, registration, _ = _new_prepared_store(
        custodian, context, base, "claim-commit-pre-fsync-kill", claim=False
    )
    raw = canonical_bytes(
        claim_request(custodian, context, registration.receipt_sha256, config)
    )
    _kill_at_stage(
        source_path,
        "claim",
        config,
        raw,
        "claim_after_commit_before_explicit_fsync",
        base,
    )
    claim = custodian.query_sampling_attempt_claim(
        config, context.sampling_attempt_namespace_sha256
    )
    require(claim is not None, "post-commit killed claim was lost")
    _expect_rejected(
        custodian,
        "post-commit-claim-retry",
        lambda: custodian.claim_sampling_attempt(config, raw),
    )
    custodian.record_sampling_outcome(
        config,
        canonical_bytes(
            outcome_request(
                custodian,
                context,
                registration.receipt_sha256,
                claim.receipt_sha256,
                config,
                outcome="TERMINAL_ABORT",
            )
        ),
    )
    boundaries += 1

    config, registration, _ = _new_prepared_store(
        custodian, context, base, "claim-post-fsync-kill", claim=False
    )
    raw = canonical_bytes(
        claim_request(custodian, context, registration.receipt_sha256, config)
    )
    _kill_at_stage(
        source_path, "claim", config, raw, "claim_after_durable_fsync", base
    )
    claim = custodian.query_sampling_attempt_claim(
        config, context.sampling_attempt_namespace_sha256
    )
    require(claim is not None, "post-fsync killed claim was lost")
    _expect_rejected(
        custodian,
        "post-fsync-claim-retry",
        lambda: custodian.claim_sampling_attempt(config, raw),
    )
    custodian.record_sampling_outcome(
        config,
        canonical_bytes(
            outcome_request(
                custodian,
                context,
                registration.receipt_sha256,
                claim.receipt_sha256,
                config,
                outcome="TERMINAL_ABORT",
            )
        ),
    )
    boundaries += 1

    config, registration, claim = _new_prepared_store(
        custodian, context, base, "outcome-precommit-kill", claim=True
    )
    assert claim is not None
    raw = canonical_bytes(
        outcome_request(
            custodian,
            context,
            registration.receipt_sha256,
            claim.receipt_sha256,
            config,
            outcome="TERMINAL_ABORT",
        )
    )
    _kill_at_stage(
        source_path, "outcome", config, raw, "outcome_before_commit", base
    )
    require(
        custodian.query_sampling_outcome(
            config, context.sampling_attempt_namespace_sha256
        )
        is None,
        "pre-commit killed outcome became visible",
    )
    custodian.record_sampling_outcome(config, raw)
    boundaries += 1

    config, registration, claim = _new_prepared_store(
        custodian, context, base, "outcome-commit-pre-fsync-kill", claim=True
    )
    assert claim is not None
    raw = canonical_bytes(
        outcome_request(
            custodian,
            context,
            registration.receipt_sha256,
            claim.receipt_sha256,
            config,
            outcome="TERMINAL_ABORT",
        )
    )
    _kill_at_stage(
        source_path,
        "outcome",
        config,
        raw,
        "outcome_after_commit_before_explicit_fsync",
        base,
    )
    require(
        custodian.query_sampling_outcome(
            config, context.sampling_attempt_namespace_sha256
        )
        is not None,
        "post-commit killed outcome was lost",
    )
    _expect_rejected(
        custodian,
        "post-commit-outcome-retry",
        lambda: custodian.record_sampling_outcome(config, raw),
    )
    boundaries += 1

    config, registration, claim = _new_prepared_store(
        custodian, context, base, "outcome-post-fsync-kill", claim=True
    )
    assert claim is not None
    raw = canonical_bytes(
        outcome_request(
            custodian,
            context,
            registration.receipt_sha256,
            claim.receipt_sha256,
            config,
            outcome="TERMINAL_ABORT",
        )
    )
    _kill_at_stage(
        source_path, "outcome", config, raw, "outcome_after_durable_fsync", base
    )
    require(
        custodian.query_sampling_outcome(
            config, context.sampling_attempt_namespace_sha256
        )
        is not None,
        "post-fsync killed outcome was lost",
    )
    _expect_rejected(
        custodian,
        "post-fsync-outcome-retry",
        lambda: custodian.record_sampling_outcome(config, raw),
    )
    boundaries += 1
    return boundaries


def reproduce_local_snapshot_rollback(
    custodian: Any,
    context: SyntheticContext,
    base: Path,
) -> bool:
    config, registration, _ = _new_prepared_store(
        custodian, context, base, "snapshot-rollback", claim=False
    )
    snapshot = base / "pre-claim-old-snapshot.sqlite3"
    shutil.copy2(config.store_path, snapshot)
    claim_raw = canonical_bytes(
        claim_request(custodian, context, registration.receipt_sha256, config)
    )
    claim = custodian.claim_sampling_attempt(config, claim_raw)
    outcome = custodian.record_sampling_outcome(
        config,
        canonical_bytes(
            outcome_request(
                custodian,
                context,
                registration.receipt_sha256,
                claim.receipt_sha256,
                config,
                outcome="TERMINAL_ABORT",
            )
        ),
    )
    require(outcome.receipt["terminal"] is True, "snapshot setup did not terminalize")
    os.replace(snapshot, config.store_path)
    os.chmod(config.store_path, 0o600)
    second = custodian.claim_sampling_attempt(config, claim_raw)
    return second.receipt_sha256 == claim.receipt_sha256


def run_filesystem_and_schema_tests(
    custodian: Any,
    context: SyntheticContext,
    base: Path,
) -> int:
    rejected = 0

    missing_parent = base / "missing-runtime" / "ledger"
    missing_parent.mkdir(mode=0o700, parents=True)
    missing_config = make_config(
        custodian, context, missing_parent / custodian.STORE_BASENAME
    )
    _expect_rejected(
        custodian,
        "runtime-missing-no-create",
        lambda: custodian.query_owner_trial(missing_config, context.fixture["trial_id"]),
    )
    require(not missing_config.store_path.exists(), "runtime query created missing ledger")
    rejected += 1

    for attack in ("symlink", "fifo", "hardlink"):
        parent = base / f"path-{attack}"
        parent.mkdir(mode=0o700)
        config = make_config(custodian, context, parent / custodian.STORE_BASENAME)
        target = base / f"path-{attack}-target"
        target.write_bytes(b"not-a-ledger")
        os.chmod(target, 0o600)
        if attack == "symlink":
            config.store_path.symlink_to(target)
        elif attack == "fifo":
            config.store_path.unlink(missing_ok=True)
            os.mkfifo(config.store_path, 0o600)
        else:
            os.link(target, config.store_path)
        _expect_rejected(
            custodian,
            f"path-{attack}",
            lambda c=config: custodian.initialize_custodian(
                c, created_at_utc="2026-07-14T11:59:50Z"
            ),
        )
        rejected += 1

    config = make_config(
        custodian,
        context,
        base / "wrong-db-mode" / "ledger" / custodian.STORE_BASENAME,
    )
    initialize_store(custodian, config)
    os.chmod(config.store_path, 0o644)
    _expect_rejected(
        custodian,
        "wrong-db-mode",
        lambda: custodian.query_owner_trial(config, context.fixture["trial_id"]),
    )
    rejected += 1

    config = make_config(
        custodian,
        context,
        base / "wrong-parent-mode" / "ledger" / custodian.STORE_BASENAME,
    )
    initialize_store(custodian, config)
    os.chmod(config.store_path.parent, 0o755)
    _expect_rejected(
        custodian,
        "wrong-parent-mode",
        lambda: custodian.query_owner_trial(config, context.fixture["trial_id"]),
    )
    rejected += 1

    config = make_config(
        custodian,
        context,
        base / "application-drift" / "ledger" / custodian.STORE_BASENAME,
    )
    initialize_store(custodian, config)
    connection = sqlite3.connect(config.store_path)
    try:
        connection.execute("PRAGMA application_id=1")
        connection.commit()
    finally:
        connection.close()
    _expect_rejected(
        custodian,
        "application-id-drift",
        lambda: custodian.query_owner_trial(config, context.fixture["trial_id"]),
    )
    rejected += 1

    config = make_config(
        custodian,
        context,
        base / "schema-drift" / "ledger" / custodian.STORE_BASENAME,
    )
    initialize_store(custodian, config)
    connection = sqlite3.connect(config.store_path)
    try:
        connection.execute("CREATE TABLE injected_table(value TEXT)")
        connection.commit()
    finally:
        connection.close()
    _expect_rejected(
        custodian,
        "schema-drift",
        lambda: custodian.query_owner_trial(config, context.fixture["trial_id"]),
    )
    rejected += 1

    sidecar_parent = base / "unsafe-initialize-sidecar" / "ledger"
    sidecar_parent.mkdir(mode=0o700, parents=True)
    config = make_config(
        custodian,
        context,
        sidecar_parent / custodian.STORE_BASENAME,
    )
    sidecar_target = base / "unsafe-initialize-sidecar-target"
    sidecar_target.write_text("not-a-journal\n", encoding="utf-8")
    Path(str(config.store_path) + "-journal").symlink_to(sidecar_target)
    _expect_rejected(
        custodian,
        "unsafe-initialize-sidecar",
        lambda: custodian.initialize_custodian(
            config,
            created_at_utc="2026-07-14T11:59:50Z",
        ),
    )
    rejected += 1

    config = make_config(
        custodian,
        context,
        base / "unsafe-runtime-sidecar" / "ledger" / custodian.STORE_BASENAME,
    )
    initialize_store(custodian, config)
    runtime_sidecar_target = base / "unsafe-runtime-sidecar-target"
    runtime_sidecar_target.write_text("not-a-journal\n", encoding="utf-8")
    Path(str(config.store_path) + "-journal").symlink_to(runtime_sidecar_target)
    _expect_rejected(
        custodian,
        "unsafe-runtime-sidecar",
        lambda: custodian.query_owner_trial(config, context.fixture["trial_id"]),
    )
    rejected += 1

    config, registration, _ = _new_prepared_store(
        custodian,
        context,
        base,
        "post-open-path-replacement",
        claim=False,
    )
    claim_raw = canonical_bytes(
        claim_request(custodian, context, registration.receipt_sha256, config)
    )
    moved_store = config.store_path.with_name("moved-original.sqlite3")

    def replace_after_commit(stage: str) -> None:
        if stage != "claim_after_commit_before_explicit_fsync":
            return
        os.replace(config.store_path, moved_store)
        shutil.copy2(moved_store, config.store_path)
        os.chmod(config.store_path, 0o600)

    _expect_rejected(
        custodian,
        "post-open-path-replacement",
        lambda: custodian.claim_sampling_attempt(
            config,
            claim_raw,
            _fault_hook=replace_after_commit,
        ),
    )
    rejected += 1

    real_parent = base / "ancestor-symlink-real"
    real_parent.mkdir(mode=0o700)
    alias_parent = base / "ancestor-symlink-alias"
    alias_parent.symlink_to(real_parent, target_is_directory=True)
    config = make_config(
        custodian,
        context,
        alias_parent / custodian.STORE_BASENAME,
    )
    _expect_rejected(
        custodian,
        "ancestor-symlink",
        lambda: custodian.initialize_custodian(
            config,
            created_at_utc="2026-07-14T11:59:50Z",
        ),
    )
    rejected += 1

    config = make_config(
        custodian,
        context,
        base / "sqlite-new-fd-binding" / "ledger" / custodian.STORE_BASENAME,
    )
    initialize_store(custodian, config)
    decoy = base / "sqlite-new-fd-binding-decoy.sqlite3"
    decoy.write_bytes(b"decoy")
    os.chmod(decoy, 0o600)
    sentinel_fd = os.open(decoy, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    extra_preexisting_fd = os.open(
        decoy,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        decoy_identity = os.fstat(sentinel_fd)
        _expect_rejected(
            custodian,
            "sqlite-new-fd-binding",
            lambda: custodian._connect_existing_inode(
                config,
                decoy_identity,
                sentinel_fd,
            ),
        )
        rejected += 1
    finally:
        os.close(extra_preexisting_fd)
        os.close(sentinel_fd)
    return rejected


def run_unexpected_exception_cleanup_test(
    custodian: Any,
    context: SyntheticContext,
    base: Path,
) -> int:
    config, registration, _ = _new_prepared_store(
        custodian,
        context,
        base,
        "unexpected-exception-cleanup",
        claim=False,
    )
    raw = canonical_bytes(
        claim_request(custodian, context, registration.receipt_sha256, config)
    )
    before_fds = custodian._process_fd_set()

    def raise_runtime(stage: str) -> None:
        if stage == "claim_before_commit":
            raise RuntimeError("synthetic unexpected exception")

    try:
        custodian.claim_sampling_attempt(config, raw, _fault_hook=raise_runtime)
    except RuntimeError as exc:
        require(str(exc) == "synthetic unexpected exception", "unexpected exception drift")
    else:
        fail("unexpected exception hook did not escape")
    after_fds = custodian._process_fd_set()
    require(after_fds == before_fds, "unexpected exception leaked process descriptors")
    claim = custodian.claim_sampling_attempt(config, raw)
    require(claim.receipt["local_namespace_claim_committed"] is True, "cleanup left claim locked")
    custodian.record_sampling_outcome(
        config,
        canonical_bytes(
            outcome_request(
                custodian,
                context,
                registration.receipt_sha256,
                claim.receipt_sha256,
                config,
                outcome="TERMINAL_ABORT",
            )
        ),
    )
    return 1


def run_normal(
    root: Path,
    custodian: Any,
    successor: Any,
    context: SyntheticContext,
) -> str:
    with tempfile.TemporaryDirectory(prefix="track-b-custodian-v1-normal-") as raw:
        base = Path(raw)
        success = run_success_path(
            root, custodian, successor, context, base / "success"
        )
        abort = run_abort_path(custodian, context, base / "abort")
        rollback_reproduced = reproduce_local_snapshot_rollback(
            custodian, context, base / "rollback"
        )
        counts = custodian.inspect_counts(success["config"])
        expected = context.fixture["expected"]
        require(
            counts
            == {
                "ledger_event_count": expected["ledger_event_count_after_success"],
                "owner_registration_count": expected["owner_registration_count"],
                "sampling_attempt_claim_count": 1,
                "terminal_abort_count": 0,
                "terminal_outcome_count": expected["success_terminal_count"],
                "terminal_success_count": expected["success_terminal_count"],
            },
            "positive store count profile drift",
        )
        require(
            abort["outcome"].receipt["outcome"] == "TERMINAL_ABORT",
            "abort terminal tag drift",
        )
        require(
            rollback_reproduced
            is expected["known_local_snapshot_rollback_attack_reproduced"],
            "known rollback boundary changed",
        )
        registration_receipt = success["registration"].receipt
        claim_receipt = success["claim"].receipt
        outcome_receipt = success["outcome"].receipt
        rows = {
            "schema": "agent_bridge.biocortex_ab_track_b_sampling_attempt_custodian_v1_pack_validation_result.v0",
            "decision": PACK_DECISION,
            "protocol_version": expected["protocol_version"],
            "trial_id": context.fixture["trial_id"],
            "sampling_attempt_namespace_sha256": context.sampling_attempt_namespace_sha256,
            "sampling_event_sha256": context.sampling_event_sha256,
            "custody_target_sha256": claim_receipt["custody_target_sha256"],
            "registration_receipt_sha256": success["registration"].receipt_sha256,
            "claim_receipt_sha256": success["claim"].receipt_sha256,
            "success_outcome_receipt_sha256": success["outcome"].receipt_sha256,
            "abort_outcome_receipt_sha256": abort["outcome"].receipt_sha256,
            "custodian_source_sha256": registration_receipt[
                "custodian_source_sha256"
            ],
            "custodian_store_schema_sha256": registration_receipt[
                "custodian_store_schema_sha256"
            ],
            "registration_receipt_schema_sha256": registration_receipt[
                "receipt_schema_sha256"
            ],
            "claim_receipt_schema_sha256": claim_receipt[
                "receipt_schema_sha256"
            ],
            "outcome_receipt_schema_sha256": outcome_receipt[
                "receipt_schema_sha256"
            ],
            "success_terminal_outcome": outcome_receipt["outcome"],
            "success_ledger_event_count": counts["ledger_event_count"],
            "owner_registration_count": counts["owner_registration_count"],
            "claim_count": counts["sampling_attempt_claim_count"],
            "success_terminal_count": counts["terminal_success_count"],
            "abort_terminal_count": expected["abort_terminal_count"],
            "sqlite_journal_mode": "DELETE",
            "sqlite_synchronous": "EXTRA",
            "sqlite_foreign_keys": True,
            "sqlite_trusted_schema": False,
            "sqlite_read_uncommitted": False,
            "sqlite_locking_mode": "NORMAL",
            "external_owner_trust_verified": registration_receipt[
                "external_owner_trust_verified"
            ],
            "external_anti_rollback_anchor_present": context.fixture["boundary"][
                "external_anti_rollback_anchor_present"
            ],
            "external_global_single_use_verified": outcome_receipt[
                "external_global_single_use_verified"
            ],
            "known_local_snapshot_rollback_attack_reproduced": rollback_reproduced,
            "condition_output_authorized": outcome_receipt[
                "condition_output_authorized"
            ],
            "live_binding_satisfied_count": context.fixture["boundary"][
                "live_binding_satisfied_count"
            ],
            "side_effects_unlocked": context.fixture["boundary"][
                "side_effects_unlocked"
            ],
        }
        return render_result(rows)


def run_self_test(
    root: Path,
    custodian: Any,
    successor: Any,
    context: SyntheticContext,
) -> str:
    with tempfile.TemporaryDirectory(prefix="track-b-custodian-v1-self-") as raw:
        base = Path(raw)
        receipt_directory = write_sampling_receipt(
            successor, context, base / "shared-sampling-observation"
        )
        mutation_count = run_directed_mutations(
            custodian, context, receipt_directory, base / "mutations"
        )
        concurrency = run_concurrency_tests(
            root, custodian, context, receipt_directory, base / "concurrency"
        )
        crash_boundaries = run_crash_tests(
            root, custodian, context, base / "crash"
        )
        path_rejections = run_filesystem_and_schema_tests(
            custodian, context, base / "path-schema"
        )
        exception_cleanups = run_unexpected_exception_cleanup_test(
            custodian,
            context,
            base / "exception-cleanup",
        )
        rollback_reproduced = reproduce_local_snapshot_rollback(
            custodian, context, base / "rollback"
        )
        expected = context.fixture["expected"]
        require(
            mutation_count >= expected["minimum_directed_mutations_rejected"],
            "directed mutation count below frozen minimum",
        )
        require(
            concurrency["claim_winners"]
            == expected["concurrent_claim_winner_count"]
            and concurrency["claim_losers"]
            == expected["concurrent_claim_loser_count"],
            "concurrent claim expected counts drift",
        )
        require(
            crash_boundaries == expected["crash_boundary_count"],
            "crash boundary count drift",
        )
        require(
            path_rejections == expected["filesystem_schema_rejection_count"],
            "filesystem/schema rejection count drift",
        )
        require(
            exception_cleanups == expected["unexpected_exception_cleanup_count"],
            "unexpected exception cleanup count drift",
        )
        require(rollback_reproduced is True, "old snapshot attack stopped reproducing")
        return (
            "SELF_TEST_OK"
            f"\tdirected_mutations_rejected={mutation_count}"
            f"\tclaim_winners={concurrency['claim_winners']}"
            f"\tclaim_losers={concurrency['claim_losers']}"
            f"\toutcome_winners={concurrency['outcome_winners']}"
            f"\toutcome_losers={concurrency['outcome_losers']}"
            f"\tcrash_boundaries={crash_boundaries}"
            f"\tfilesystem_schema_rejections={path_rejections}"
            f"\tunexpected_exception_cleanups={exception_cleanups}"
            "\tlocal_snapshot_rollback_attack_reproduced=true\n"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        fixture, synthetic_raw = load_canonical(
            root / SYNTHETIC_PATH, "custodian synthetic fixture"
        )
        validate_synthetic_fixture(fixture, synthetic_raw)
        custodian = load_module(
            root / CUSTODIAN_PATH,
            "_agent_bridge_track_b_sampling_attempt_custodian_v1",
        )
        successor = load_module(
            root / SUCCESSOR_CHECKER_PATH,
            "_agent_bridge_track_b_successor_pack_for_custodian",
        )
        schema_hashes = validate_schemas(root, custodian)
        manifest, manifest_raw = load_canonical(
            root / MANIFEST_PATH, "custodian pack manifest"
        )
        validate_manifest(
            manifest,
            manifest_raw,
            root,
            synthetic_raw,
            schema_hashes,
            custodian,
        )
        validate_report(
            root,
            manifest,
            manifest_raw,
            synthetic_raw,
            schema_hashes,
        )
        context = build_synthetic_context(
            root, fixture, custodian, successor
        )
        if args.self_test:
            sys.stdout.write(run_self_test(root, custodian, successor, context))
        else:
            sys.stdout.write(run_normal(root, custodian, successor, context))
        return 0
    except PackError as exc:
        print(f"Track B custodian v1 pack check failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"Track B custodian v1 pack check failed closed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
