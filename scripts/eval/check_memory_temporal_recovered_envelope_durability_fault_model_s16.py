#!/usr/bin/env python3
"""Independent fail-closed oracle for the private S16 durability fault model.

The oracle reconstructs the frozen S14 record with the predecessor Python
reference, then independently builds every S16 receipt, witness, replica view,
5639-row commitment, and the full catalog commitment.  It never consumes Rust
output as an oracle.  A passing receipt remains synthetic historical evidence;
it is not external durability, currentness, authorization, admission, or
deployment evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable


sys.dont_write_bytecode = True

STATUS = (
    "RECOVERED_ENVELOPE_DURABILITY_FAULT_MODEL_PREREGISTERED_SYNTHETIC_"
    "DETERMINISTIC_5639_ROWS_HISTORICAL_ONLY_ZERO_EXTERNAL_DURABILITY_"
    "OBSERVATIONS_NO_PRODUCTION_OR_PROVIDER_TRANSPORT_NO_DURABILITY_PROOF_"
    "NO_CURRENTNESS_NO_ADMISSION"
)
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s16-recovered-envelope-durability-fault-model-synthetic"
S15_FEATURE = "temporal-evidence-s15-recovered-envelope-bounded-runtime-adapter-synthetic"
POLICY = b"agent-bridge/track-b/recovered-envelope-durability-fault-model/v1"
PROFILE = b"DETERMINISTIC_SYNTHETIC_OBJECT_RECEIPT_WITNESS_FAULT_MODEL_HISTORICAL_ONLY"
S15_CONTRACT_SHA256 = bytes.fromhex(
    "07d7ae5e7345bb5052aa130349af2e90bae853e5c74560346a4178b2b0397cc7"
)
LOOKUP_SHA256 = bytes.fromhex(
    "866e016ce631433e3e272d0858906f3c76c67204cd74b73ab11b7353e57eae00"
)
BASE_RECORD_SHA256 = bytes.fromhex(
    "a788ec43fefa76e393d77c86bbfabeef7d2ae8c5499bb834c1945af5cbb1b3cd"
)
BASE_RECORD_LEN = 5_494
ROW_COUNT = 5_639
CATALOG_MESSAGE_LEN = 225_852
CATALOG_SHA256 = bytes.fromhex(
    "c09cdc640957594cc7acc2eeea39cb4e59993631ef04a1fa1e26a69c285af853"
)

CONTRACT_PATH = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-recovered-envelope-durability-fault-model-s16-v0.json"
)
SUCCESSOR_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s16-v0.json"
)
S14_CHECKER_PATH = "scripts/eval/check_memory_temporal_recovered_envelope_source_s14.py"
S14_CHECKER_SHA256 = "3d89b9f4a44bb8dd978b538cf72e2c94f2ed2d8c461c7d85e604e82326381abe"
STORE_CARGO_PATH = "crates/store/Cargo.toml"
S15_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "recovered_s9_decision_reverification/recovered_envelope_delivery/"
    "recovered_envelope_source/bounded_runtime_adapter.rs"
)
S16_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "recovered_s9_decision_reverification/recovered_envelope_delivery/"
    "recovered_envelope_source/bounded_runtime_adapter/durability_fault_model.rs"
)
S15_SOURCE_SHA256_WITHOUT_S16_GLUE = (
    "be722ae5d61cf2d120c9d30685ab90d453c2e713ca08edfc0754621e8dabee3a"
)
S16_CHILD_GLUE = f'#[cfg(feature = "{FEATURE}")]\nmod durability_fault_model;\n\n'

RECEIPT_DOMAIN = b"agent-bridge/track-b/recovered-envelope-durability-fault-model/receipt/v1"
WITNESS_DOMAIN = b"agent-bridge/track-b/recovered-envelope-durability-fault-model/witness/v1"
VIEW_DOMAIN = b"agent-bridge/track-b/recovered-envelope-durability-fault-model/replica-view/v1"
ABSENT_DOMAIN = b"agent-bridge/track-b/recovered-envelope-durability-fault-model/absent/v1"
ROW_DOMAIN = b"agent-bridge/track-b/recovered-envelope-durability-fault-model/row/v1"
CATALOG_DOMAIN = b"agent-bridge/track-b/recovered-envelope-durability-fault-model/catalog/v1"
RECEIPT_SCHEMA = b"agent-bridge/track-b/recovered-envelope-durability-receipt/v1"
WITNESS_SCHEMA = b"agent-bridge/track-b/recovered-envelope-durability-witness/v1"
VIEW_SCHEMA = b"agent-bridge/track-b/recovered-envelope-replica-view/v1"
ROW_SCHEMA = b"agent-bridge/track-b/recovered-envelope-durability-fault-row/v1"

SOURCE_INCARNATION = bytes([0x81]) * 32
SOURCE_GENERATION = bytes([0x82]) * 32
OBJECT_ID = bytes([0x83]) * 32
PREVIOUS_RECEIPT = bytes([0x91]) * 32
WITNESS_SCOPE = bytes([0x92]) * 32
WITNESS_INCARNATION = bytes([0x93]) * 32
WITNESS_GENERATION = bytes([0x94]) * 32
PREVIOUS_WITNESS = bytes([0x95]) * 32
SELECTED_REPLICA = bytes([0x96]) * 32
COMPETING_REPLICA = bytes([0x97]) * 32

FAMILY_COUNTS = {
    "D00_CLEAN_COMMITTED_HEAD": 1,
    "D01_TORN_OR_PARTIAL_OBJECT": 5_493,
    "D02_ACK_BEFORE_DURABLE_COMMIT": 4,
    "D03_DURABLE_HEAD_ACK_LOST": 1,
    "D04_PUBLISH_CRASH_RESTART_CUTS": 6,
    "D05_S15_READ_CRASH_RESTART_CUTS": 106,
    "D06_OBJECT_PRESENT_RECEIPT_ABSENT": 1,
    "D07_RECEIPT_PRESENT_OBJECT_ABSENT": 1,
    "D08_RECEIPT_OBJECT_BINDING_MISMATCH": 5,
    "D09_OLD_GENERATION_SNAPSHOT": 1,
    "D10_SAME_GENERATION_LOWER_REVISION": 1,
    "D11_SAME_REVISION_EQUIVOCATION": 2,
    "D12_SELECTED_STALE_REPLICA": 1,
    "D13_DIVERGENT_AUTHORITATIVE_VIEWS": 3,
    "D14_WITNESS_FAILURES": 4,
    "D15_POST_PERSISTENCE_CORRUPTION": 9,
}

OPERATIONAL_GAPS = (
    "RECOVERED_S9_DECISION_EXTERNAL_RUNTIME_CARRIER_UNIMPLEMENTED",
    "RECOVERED_S9_DECISION_BYTES_AVAILABILITY_UNATTESTED",
    "RECOVERED_S9_RAW_DECISION_EXTERNAL_DURABILITY_UNATTESTED",
    "RECOVERED_ENVELOPE_EXTERNAL_DURABLE_SOURCE_RUNTIME_UNIMPLEMENTED",
    "RECOVERED_ENVELOPE_CONCRETE_RUNTIME_TRANSPORT_UNIMPLEMENTED",
    "RECOVERED_ENVELOPE_CAPTURE_PROVENANCE_RUNTIME_UNATTESTED",
    "RECOVERED_ENVELOPE_CAPTURE_SIGNER_CUSTODY_UNATTESTED",
    "RECOVERED_ENVELOPE_CAPTURE_SIGNER_ROLE_SEPARATION_UNATTESTED",
    "RECOVERED_ENVELOPE_EXACT_LOOKUP_OWNER_AUTHORIZATION_UNATTESTED",
    "RECOVERED_ENVELOPE_SOURCE_ROLLBACK_AND_EQUIVOCATION_UNATTESTED",
    "RECOVERED_S10_RAW_EVIDENCE_RUNTIME_DELIVERY_UNIMPLEMENTED",
    "RECOVERED_HANDOFF_PROCESS_RESTART_UNAVAILABLE",
    "RECOVERED_HANDOFF_NOT_GLOBAL_REPLAY_FENCE",
    "RECOVERED_S9_DECISION_HISTORICAL_ONLY_NOT_CURRENT_AT_USE",
    "OWNER_PINNED_TRUST_ANCHOR_UNAVAILABLE",
    "PROVIDER_LINEARIZABILITY_UNATTESTED",
    "PROVIDER_SPLIT_BRAIN_FENCING_UNATTESTED",
    "PROVIDER_STATE_ROLLBACK_UNATTESTED",
    "ATOMIC_AUTHORITY_OPERATION_EXTERNAL_DATABASE_UNIMPLEMENTED",
    "DATABASE_KMS_CROSS_SERVICE_ATOMICITY_UNATTESTED",
    "CURRENTNESS_AT_DOWNSTREAM_USE_UNATTESTED",
)
REMAINING_GAPS = (
    "AUTHORITY_POLICY_CUSTODY_UNRESOLVED",
    "CAPTURE_PROVENANCE_UNATTESTED",
    "CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED",
    "PHYSICAL_PRIVACY_DELETION_UNRESOLVED",
    "PRODUCTION_PRODUCER_PROFILE_UNADMITTED",
)

TEST_NAMES = (
    "s16_known_answer_receipt_witness_row_and_full_historical_chain_are_stable",
    "s16_legal_publish_transition_order_is_closed_and_wrong_order_rejects",
    "s16_case_catalog_is_closed_unique_and_5639_row_commitments_are_deterministic",
    "s16_every_partial_object_prefix_fails_closed_without_open",
    "s16_premature_ack_variants_are_ambiguous_and_indeterminate",
    "s16_durable_triple_with_lost_ack_uses_fresh_exact_read",
    "s16_every_publish_crash_cut_restarts_from_modeled_persisted_image_only",
    "s16_every_s15_read_crash_cut_discards_partial_state_and_uses_fresh_adapter",
    "s16_object_present_receipt_absent_is_pending_without_open",
    "s16_receipt_present_object_absent_is_integrity_conflict",
    "s16_each_receipt_object_binding_mismatch_is_integrity_conflict",
    "s16_old_generation_snapshot_is_rollback_without_generation_ordering",
    "s16_same_generation_lower_revision_is_rollback",
    "s16_same_revision_divergent_head_is_equivocation_conflict",
    "s16_selected_stale_replica_is_stale_without_replica_switch",
    "s16_divergent_authoritative_views_are_split_brain_conflict",
    "s16_witness_missing_unavailable_corrupt_and_forked_map_exactly",
    "s16_post_persistence_object_receipt_and_witness_corruption_is_malformed",
    "s16_all_rows_are_simulated_with_zero_external_evidence_and_no_side_effects",
    "s16_private_surface_has_no_production_transport_persistence_runtime_or_admission_wiring",
)

ROW_FIELDS = (
    ("row_domain", "bytes"),
    ("policy", "bytes"),
    ("profile", "bytes"),
    ("row_schema", "bytes"),
    ("s15_contract_sha256", "bytes"),
    ("lookup_commitment_sha256", "bytes"),
    ("case_id", "ascii"),
    ("variant_id", "ascii"),
    ("variant_index", "u64"),
    ("evidence_origin", "ascii"),
    ("publisher_phase", "ascii"),
    ("object_persistence", "ascii"),
    ("object_len", "u64"),
    ("observed_object_sha256", "bytes"),
    ("receipt_state", "ascii"),
    ("computed_receipt_sha256", "bytes"),
    ("stored_receipt_sha256", "bytes"),
    ("witness_state", "ascii"),
    ("computed_witness_sha256", "bytes"),
    ("stored_witness_sha256", "bytes"),
    ("selected_view_sha256", "bytes"),
    ("competing_view_sha256", "bytes"),
    ("ack_state", "ascii"),
    ("crash_cut", "ascii"),
    ("crash_cut_index", "u64"),
    ("adapter_pre_state", "ascii"),
    ("adapter_post_state", "ascii"),
    ("disposition", "ascii"),
    ("reason", "ascii"),
    ("s15_execution_result", "ascii"),
    ("mapped_s15_failure", "ascii"),
    ("external_durability_observation_count", "u64"),
    ("provider_durability_observation_count", "u64"),
    ("owned_lab_durability_observation_count", "u64"),
    ("side_effects_unlocked", "ascii"),
)


class CheckFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_bytes(repo: Path, relative: str) -> bytes:
    path = repo / relative
    require(path.is_file() and not path.is_symlink(), f"missing/non-regular artifact: {relative}")
    return path.read_bytes()


def read_text(repo: Path, relative: str) -> str:
    try:
        return read_bytes(repo, relative).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckFailure(f"non-UTF-8 artifact: {relative}") from exc


def artifact_sha256(repo: Path, relative: str) -> str:
    return hashlib.sha256(read_bytes(repo, relative)).hexdigest()


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in output, f"duplicate JSON key: {key}")
        output[key] = value
    return output


def load_json(repo: Path, relative: str) -> dict[str, Any]:
    try:
        value = json.loads(read_text(repo, relative), object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise CheckFailure(f"invalid JSON {relative}: {exc}") from exc
    require(type(value) is dict, f"top-level JSON object required: {relative}")
    return value


def strict_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            strict_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            strict_equal(left, right) for left, right in zip(actual, expected)
        )
    return bool(actual == expected)


def require_exact(actual: Any, expected: Any, message: str) -> None:
    require(strict_equal(actual, expected), message)


def import_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frame(value: bytes) -> bytes:
    return len(value).to_bytes(8, "big") + value


def framed_message(fields: Iterable[bytes]) -> bytes:
    return b"".join(frame(field) for field in fields)


def u64(value: int) -> bytes:
    require(type(value) is int and 0 <= value < 1 << 64, "u64 value out of range")
    return value.to_bytes(8, "big")


def flip_byte(value: bytes, index: int) -> bytes:
    require(0 <= index < len(value), "bit-flip index out of range")
    return value[:index] + bytes([value[index] ^ 0x01]) + value[index + 1 :]


def independent_record(repo: Path) -> bytes:
    require(
        artifact_sha256(repo, S14_CHECKER_PATH) == S14_CHECKER_SHA256,
        "frozen independent S14 checker digest drift",
    )
    module = import_module(repo / S14_CHECKER_PATH, "s14_reference_for_s16")
    vectors = module.independent_vectors(repo)
    record = bytes(vectors["record"])
    require(len(record) == BASE_RECORD_LEN, "independent S14 record length drift")
    require(hashlib.sha256(record).digest() == BASE_RECORD_SHA256, "independent S14 record hash drift")
    require(
        bytes(vectors["historical_chain_sha256"]).hex()
        == "afb8aa4945f0e491937f75233c621d52f1bcc1307e6d497352fd9d0fc79b7204",
        "independent S9-S12 historical chain drift",
    )
    require(
        bytes(vectors["historical_source_chain_sha256"]).hex()
        == "d29da2a081b09b2b124298eae40b15ada555196cc5e3fd52d8e4dfadf3f2149b",
        "independent S14 historical source chain drift",
    )
    return record


def absent_digest(kind: str) -> bytes:
    require(kind in {"OBJECT", "RECEIPT", "WITNESS", "REPLICA_VIEW"}, "unknown absent kind")
    return hashlib.sha256(framed_message((ABSENT_DOMAIN, kind.encode("ascii")))).digest()


def receipt_message(
    *,
    source_generation: bytes = SOURCE_GENERATION,
    object_id: bytes = OBJECT_ID,
    revision: int = 17,
    record_len: int = BASE_RECORD_LEN,
    record_sha256: bytes = BASE_RECORD_SHA256,
    previous_receipt: bytes = PREVIOUS_RECEIPT,
) -> bytes:
    return framed_message(
        (
            RECEIPT_DOMAIN,
            POLICY,
            PROFILE,
            RECEIPT_SCHEMA,
            S15_CONTRACT_SHA256,
            LOOKUP_SHA256,
            SOURCE_INCARNATION,
            source_generation,
            object_id,
            u64(revision),
            u64(record_len),
            record_sha256,
            u64(23),
            previous_receipt,
        )
    )


def witness_message(
    receipt_sha256: bytes,
    *,
    source_generation: bytes = SOURCE_GENERATION,
    object_id: bytes = OBJECT_ID,
    revision: int = 17,
    record_sha256: bytes = BASE_RECORD_SHA256,
    previous_witness: bytes = PREVIOUS_WITNESS,
) -> bytes:
    return framed_message(
        (
            WITNESS_DOMAIN,
            POLICY,
            PROFILE,
            WITNESS_SCHEMA,
            S15_CONTRACT_SHA256,
            WITNESS_SCOPE,
            WITNESS_INCARNATION,
            WITNESS_GENERATION,
            u64(31),
            LOOKUP_SHA256,
            SOURCE_INCARNATION,
            source_generation,
            object_id,
            u64(revision),
            record_sha256,
            receipt_sha256,
            previous_witness,
        )
    )


def view_message(
    receipt_sha256: bytes,
    *,
    replica_id: bytes = SELECTED_REPLICA,
    authority: str = "CLAIMS_AUTHORITATIVE",
    source_generation: bytes = SOURCE_GENERATION,
    object_id: bytes = OBJECT_ID,
    revision: int = 17,
    record_len: int = BASE_RECORD_LEN,
    record_sha256: bytes = BASE_RECORD_SHA256,
) -> bytes:
    return framed_message(
        (
            VIEW_DOMAIN,
            POLICY,
            PROFILE,
            VIEW_SCHEMA,
            S15_CONTRACT_SHA256,
            LOOKUP_SHA256,
            replica_id,
            authority.encode("ascii"),
            SOURCE_INCARNATION,
            source_generation,
            object_id,
            u64(revision),
            u64(record_len),
            record_sha256,
            receipt_sha256,
        )
    )


def digest(message: bytes) -> bytes:
    return hashlib.sha256(message).digest()


def image_absent() -> dict[str, Any]:
    return {
        "object_persistence": "ABSENT",
        "object_len": 0,
        "observed_object_sha256": absent_digest("OBJECT"),
        "receipt_state": "ABSENT",
        "computed_receipt_sha256": absent_digest("RECEIPT"),
        "stored_receipt_sha256": absent_digest("RECEIPT"),
        "witness_state": "ABSENT",
        "computed_witness_sha256": absent_digest("WITNESS"),
        "stored_witness_sha256": absent_digest("WITNESS"),
        "selected_view_sha256": absent_digest("REPLICA_VIEW"),
    }


def image_prefix(record: bytes, prefix_len: int) -> dict[str, Any]:
    image = image_absent()
    image.update(
        object_persistence="PARTIAL",
        object_len=prefix_len,
        observed_object_sha256=hashlib.sha256(record[:prefix_len]).digest(),
    )
    return image


def image_object(record: bytes) -> dict[str, Any]:
    image = image_absent()
    image.update(
        object_persistence="COMMITTED",
        object_len=len(record),
        observed_object_sha256=hashlib.sha256(record).digest(),
    )
    return image


def image_object_receipt(record: bytes, receipt_sha256: bytes) -> dict[str, Any]:
    image = image_object(record)
    image.update(
        receipt_state="COMMITTED",
        computed_receipt_sha256=receipt_sha256,
        stored_receipt_sha256=receipt_sha256,
    )
    return image


def image_triple(
    record: bytes,
    receipt_sha256: bytes,
    witness_sha256: bytes,
    selected_view_sha256: bytes,
) -> dict[str, Any]:
    image = image_object_receipt(record, receipt_sha256)
    image.update(
        witness_state="PRESENT",
        computed_witness_sha256=witness_sha256,
        stored_witness_sha256=witness_sha256,
        selected_view_sha256=selected_view_sha256,
    )
    return image


def logical_base(record: bytes) -> dict[str, Any]:
    receipt_sha = digest(receipt_message())
    witness_sha = digest(witness_message(receipt_sha))
    selected_sha = digest(view_message(receipt_sha))
    row: dict[str, Any] = {
        "row_domain": ROW_DOMAIN,
        "policy": POLICY,
        "profile": PROFILE,
        "row_schema": ROW_SCHEMA,
        "s15_contract_sha256": S15_CONTRACT_SHA256,
        "lookup_commitment_sha256": LOOKUP_SHA256,
        "case_id": "D00_CLEAN_COMMITTED_HEAD",
        "variant_id": "CLEAN",
        "variant_index": 0,
        "evidence_origin": "SIMULATED_MODEL",
        "publisher_phase": "ACKED",
        **image_triple(record, receipt_sha, witness_sha, selected_sha),
        "competing_view_sha256": absent_digest("REPLICA_VIEW"),
        "ack_state": "OBSERVED",
        "crash_cut": "NONE",
        "crash_cut_index": 0,
        "adapter_pre_state": "FRESH",
        "adapter_post_state": "COMPLETED",
        "disposition": "MODEL_EXACT_HISTORICAL_READ_ELIGIBLE",
        "reason": "EXACT_MODELED_HEAD",
        "s15_execution_result": "STREAM_EXACT",
        "mapped_s15_failure": "NONE",
        "external_durability_observation_count": 0,
        "provider_durability_observation_count": 0,
        "owned_lab_durability_observation_count": 0,
        "side_effects_unlocked": "NONE",
    }
    require(set(row) == {name for name, _ in ROW_FIELDS}, "D00 logical base is not closed")
    return row


def derived_row(
    base: dict[str, Any],
    *,
    case_id: str,
    variant_id: str,
    variant_index: int,
    disposition: str,
    reason: str,
    execution: str,
    failure: str,
    publisher_phase: str,
    image: dict[str, Any],
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = dict(base)
    row.update(
        case_id=case_id,
        variant_id=variant_id,
        variant_index=variant_index,
        evidence_origin="SIMULATED_MODEL",
        competing_view_sha256=absent_digest("REPLICA_VIEW"),
        ack_state="NOT_OBSERVED",
        crash_cut="NONE",
        crash_cut_index=0,
        adapter_pre_state="FRESH",
        adapter_post_state=(
            "COMPLETED"
            if disposition == "MODEL_EXACT_HISTORICAL_READ_ELIGIBLE"
            else "FRESH"
        ),
        disposition=disposition,
        reason=reason,
        s15_execution_result=execution,
        mapped_s15_failure=failure,
        external_durability_observation_count=0,
        provider_durability_observation_count=0,
        owned_lab_durability_observation_count=0,
        side_effects_unlocked="NONE",
        publisher_phase=publisher_phase,
    )
    row.update(image)
    if overrides:
        row.update(overrides)
    require(set(row) == {name for name, _ in ROW_FIELDS}, f"row shape drift: {case_id}/{variant_id}")
    return row


def generate_rows(record: bytes) -> list[dict[str, Any]]:
    base = logical_base(record)
    rows = [base]
    add = rows.append
    base_receipt = base["computed_receipt_sha256"]
    base_witness = base["computed_witness_sha256"]
    base_view = base["selected_view_sha256"]
    absent = image_absent()
    obj = image_object(record)
    obj_receipt = image_object_receipt(record, base_receipt)
    triple = image_triple(record, base_receipt, base_witness, base_view)

    for prefix_len in range(1, BASE_RECORD_LEN):
        add(derived_row(
            base,
            case_id="D01_TORN_OR_PARTIAL_OBJECT",
            variant_id=f"PREFIX_CUT_{prefix_len:04d}",
            variant_index=prefix_len - 1,
            disposition="MODEL_INCOMPLETE_FAIL_CLOSED",
            reason="PARTIAL_OBJECT_NOT_COMMITTED",
            execution="NOT_INVOKED",
            failure="MALFORMED",
            publisher_phase="OBJECT_PREFIX",
            image=image_prefix(record, prefix_len),
            overrides={"crash_cut": "PUBLISH_AFTER_OBJECT_PREFIX", "crash_cut_index": prefix_len},
        ))

    d02 = (
        ("ACK_AT_EMPTY", absent),
        ("ACK_AT_OBJECT_PARTIAL", image_prefix(record, 2_747)),
        ("ACK_AT_OBJECT_COMMITTED", obj),
        ("ACK_AT_RECEIPT_COMMITTED", obj_receipt),
    )
    for index, (variant, image) in enumerate(d02):
        add(derived_row(
            base,
            case_id="D02_ACK_BEFORE_DURABLE_COMMIT",
            variant_id=variant,
            variant_index=index,
            disposition="MODEL_AMBIGUOUS_QUARANTINED",
            reason="ACK_OUTRAN_MODELED_DURABILITY",
            execution="NOT_INVOKED",
            failure="INDETERMINATE",
            publisher_phase="ACKED",
            image=image,
            overrides={"ack_state": "OBSERVED"},
        ))

    add(derived_row(
        base,
        case_id="D03_DURABLE_HEAD_ACK_LOST",
        variant_id="ACK_NOT_OBSERVED_AFTER_WITNESS",
        variant_index=0,
        disposition="MODEL_EXACT_HISTORICAL_READ_ELIGIBLE",
        reason="MODELED_DURABLE_TRIPLE_ACK_LOST",
        execution="STREAM_EXACT",
        failure="NONE",
        publisher_phase="WITNESS_COMMITTED",
        image=triple,
    ))

    d04 = (
        ("CRASH_AT_EMPTY_RESTART", "EMPTY", absent, "NONE", 0, "MODEL_INCOMPLETE_FAIL_CLOSED", "NO_DURABLE_OBJECT_AFTER_RESTART", "NOT_INVOKED", "NOT_FOUND"),
        ("CRASH_AFTER_OBJECT_PREFIX_RESTART", "OBJECT_PREFIX", image_prefix(record, 2_747), "PUBLISH_AFTER_OBJECT_PREFIX", 2_747, "MODEL_INCOMPLETE_FAIL_CLOSED", "PARTIAL_OBJECT_AFTER_RESTART", "NOT_INVOKED", "MALFORMED"),
        ("CRASH_AFTER_OBJECT_COMMIT_RESTART", "OBJECT_COMMITTED", obj, "PUBLISH_AFTER_OBJECT_COMMIT", 0, "MODEL_INCOMPLETE_FAIL_CLOSED", "RECEIPT_MISSING_AFTER_RESTART", "NOT_INVOKED", "PENDING"),
        ("CRASH_AFTER_RECEIPT_COMMIT_RESTART", "RECEIPT_COMMITTED", obj_receipt, "PUBLISH_AFTER_RECEIPT_COMMIT", 0, "MODEL_INCOMPLETE_FAIL_CLOSED", "WITNESS_MISSING_AFTER_RESTART", "NOT_INVOKED", "PENDING"),
        ("CRASH_AFTER_WITNESS_COMMIT_RESTART", "WITNESS_COMMITTED", triple, "PUBLISH_AFTER_WITNESS_COMMIT", 0, "MODEL_EXACT_HISTORICAL_READ_ELIGIBLE", "MODELED_DURABLE_TRIPLE_RECOVERED", "STREAM_EXACT", "NONE"),
        ("CRASH_AFTER_ACK_RESTART", "ACKED", triple, "PUBLISH_AFTER_ACK", 0, "MODEL_EXACT_HISTORICAL_READ_ELIGIBLE", "MODELED_DURABLE_TRIPLE_RECOVERED", "STREAM_EXACT", "NONE"),
    )
    for index, values in enumerate(d04):
        variant, phase, image, cut, cut_index, disposition, reason, execution, failure = values
        add(derived_row(
            base,
            case_id="D04_PUBLISH_CRASH_RESTART_CUTS",
            variant_id=variant,
            variant_index=index,
            disposition=disposition,
            reason=reason,
            execution=execution,
            failure=failure,
            publisher_phase=phase,
            image=image,
            overrides={"crash_cut": cut, "crash_cut_index": cut_index},
        ))

    cuts: list[tuple[str, str, int]] = [
        ("BEFORE_OPEN", "READ_BEFORE_OPEN", 0),
        ("AFTER_OPEN", "READ_AFTER_OPEN", 0),
    ]
    cuts.extend((f"AFTER_DATA_{index:04d}", "READ_AFTER_DATA", index) for index in range(1, 50))
    cuts.extend((
        ("AFTER_COMPLETE_BEFORE_S14", "READ_AFTER_COMPLETE_BEFORE_S14", 0),
        ("AFTER_HISTORICAL", "READ_AFTER_HISTORICAL", 0),
    ))
    require(len(cuts) == 53, "D05 cut cardinality drift")
    for cut_ordinal, (cut_id, crash_cut, crash_index) in enumerate(cuts):
        if cut_id == "BEFORE_OPEN":
            first = ("FRESH", "FRESH", "MODEL_AMBIGUOUS_QUARANTINED", "CRASH_BEFORE_OPEN_RESULT_UNKNOWN", "NOT_INVOKED", "INDETERMINATE")
        elif cut_id in {"AFTER_OPEN"} or cut_id.startswith("AFTER_DATA_"):
            first = ("STREAMING", "TERMINAL_FAILED", "MODEL_AMBIGUOUS_QUARANTINED", "CRASH_DURING_STREAM_DISCARDED_PARTIAL_STATE", "FAIL_INDETERMINATE", "INDETERMINATE")
        elif cut_id == "AFTER_COMPLETE_BEFORE_S14":
            first = ("STREAMING", "COMPLETED", "MODEL_AMBIGUOUS_QUARANTINED", "ADAPTER_COMPLETED_S14_RESULT_NOT_OBSERVED", "STREAM_EXACT", "NONE")
        else:
            first = ("COMPLETED", "COMPLETED", "MODEL_EXACT_HISTORICAL_READ_ELIGIBLE", "HISTORICAL_RESULT_OBSERVED_BEFORE_CRASH", "STREAM_EXACT", "NONE")
        for phase_ordinal, attempt in enumerate(("FIRST_ATTEMPT", "RESTART")):
            if attempt == "FIRST_ATTEMPT":
                pre, post, disposition, reason, execution, failure = first
            else:
                pre, post = "FRESH", "COMPLETED"
                disposition = "MODEL_EXACT_HISTORICAL_READ_ELIGIBLE"
                reason = (
                    "REPEATED_HISTORICAL_REVERIFY_NO_REPLAY_FENCE"
                    if cut_id == "AFTER_HISTORICAL"
                    else "FRESH_ADAPTER_EXACT_REREAD"
                )
                execution, failure = "STREAM_EXACT", "NONE"
            add(derived_row(
                base,
                case_id="D05_S15_READ_CRASH_RESTART_CUTS",
                variant_id=f"{cut_id}_{attempt}",
                variant_index=2 * cut_ordinal + phase_ordinal,
                disposition=disposition,
                reason=reason,
                execution=execution,
                failure=failure,
                publisher_phase="ACKED",
                image=triple,
                overrides={
                    "crash_cut": crash_cut,
                    "crash_cut_index": crash_index,
                    "adapter_pre_state": pre,
                    "adapter_post_state": post,
                },
            ))

    add(derived_row(base, case_id="D06_OBJECT_PRESENT_RECEIPT_ABSENT", variant_id="COMMITTED_OBJECT_NO_RECEIPT", variant_index=0, disposition="MODEL_INCOMPLETE_FAIL_CLOSED", reason="RECEIPT_MISSING", execution="NOT_INVOKED", failure="PENDING", publisher_phase="OBJECT_COMMITTED", image=obj))

    receipt_without_object = image_absent()
    receipt_without_object.update(receipt_state="COMMITTED", computed_receipt_sha256=base_receipt, stored_receipt_sha256=base_receipt)
    add(derived_row(base, case_id="D07_RECEIPT_PRESENT_OBJECT_ABSENT", variant_id="COMMITTED_RECEIPT_NO_OBJECT", variant_index=0, disposition="MODEL_INTEGRITY_INCIDENT_QUARANTINED", reason="RECEIPT_WITHOUT_OBJECT", execution="NOT_INVOKED", failure="CONFLICT", publisher_phase="RECEIPT_COMMITTED", image=receipt_without_object))

    flipped_first_record_hash = flip_byte(BASE_RECORD_SHA256, 0)
    d08 = (
        ("LENGTH", "RECEIPT_LENGTH_MISMATCH", {"record_len": 5_495}),
        ("HASH", "RECEIPT_RECORD_HASH_MISMATCH", {"record_sha256": flipped_first_record_hash}),
        ("GENERATION", "RECEIPT_SOURCE_GENERATION_MISMATCH", {"source_generation": bytes([0xA2]) * 32}),
        ("OBJECT_ID", "RECEIPT_OBJECT_ID_MISMATCH", {"object_id": bytes([0xA3]) * 32}),
        ("REVISION", "RECEIPT_OBJECT_REVISION_MISMATCH", {"revision": 18}),
    )
    for index, (variant, reason, mutation) in enumerate(d08):
        receipt_sha = digest(receipt_message(**mutation))
        witness_kwargs = {key: mutation[key] for key in ("source_generation", "object_id", "revision", "record_sha256") if key in mutation}
        view_kwargs = dict(mutation)
        witness_sha = digest(witness_message(receipt_sha, **witness_kwargs))
        selected_sha = digest(view_message(receipt_sha, **view_kwargs))
        mutated_image = image_triple(record, receipt_sha, witness_sha, selected_sha)
        add(derived_row(base, case_id="D08_RECEIPT_OBJECT_BINDING_MISMATCH", variant_id=variant, variant_index=index, disposition="MODEL_INTEGRITY_INCIDENT_QUARANTINED", reason=reason, execution="NOT_INVOKED", failure="CONFLICT", publisher_phase="WITNESS_COMMITTED", image=mutated_image))

    old_generation = bytes([0x80]) * 32
    old_receipt = digest(receipt_message(source_generation=old_generation))
    old_view = digest(view_message(old_receipt, source_generation=old_generation))
    d09_image = image_triple(record, old_receipt, base_witness, old_view)
    add(derived_row(base, case_id="D09_OLD_GENERATION_SNAPSHOT", variant_id="OLD_GENERATION_EXACT_OBJECT", variant_index=0, disposition="MODEL_INTEGRITY_INCIDENT_QUARANTINED", reason="WITNESS_HEAD_GENERATION_MISMATCH", execution="NOT_INVOKED", failure="ROLLBACK", publisher_phase="WITNESS_COMMITTED", image=d09_image))

    lower_receipt = digest(receipt_message(revision=16))
    lower_view = digest(view_message(lower_receipt, revision=16))
    d10_image = image_triple(record, lower_receipt, base_witness, lower_view)
    add(derived_row(base, case_id="D10_SAME_GENERATION_LOWER_REVISION", variant_id="LOWER_REVISION_EXACT_OBJECT", variant_index=0, disposition="MODEL_INTEGRITY_INCIDENT_QUARANTINED", reason="WITNESS_HEAD_REVISION_ROLLBACK", execution="NOT_INVOKED", failure="ROLLBACK", publisher_phase="WITNESS_COMMITTED", image=d10_image))

    d11_receipt_record = digest(receipt_message(record_sha256=flipped_first_record_hash))
    d11_competing_record = digest(view_message(d11_receipt_record, replica_id=COMPETING_REPLICA, record_sha256=flipped_first_record_hash))
    d11_receipt_previous = digest(receipt_message(previous_receipt=bytes([0x99]) * 32))
    d11_competing_receipt = digest(view_message(d11_receipt_previous, replica_id=COMPETING_REPLICA))
    for index, (variant, competing) in enumerate((
        ("DIVERGENT_RECORD_HASH", d11_competing_record),
        ("DIVERGENT_RECEIPT_HASH", d11_competing_receipt),
    )):
        add(derived_row(base, case_id="D11_SAME_REVISION_EQUIVOCATION", variant_id=variant, variant_index=index, disposition="MODEL_INTEGRITY_INCIDENT_QUARANTINED", reason="SAME_REVISION_EQUIVOCATION", execution="NOT_INVOKED", failure="CONFLICT", publisher_phase="WITNESS_COMMITTED", image=triple, overrides={"competing_view_sha256": competing}))

    stale_selected = digest(view_message(lower_receipt, authority="NON_AUTHORITATIVE_STALE", revision=16))
    stale_image = dict(triple)
    stale_image["selected_view_sha256"] = stale_selected
    add(derived_row(base, case_id="D12_SELECTED_STALE_REPLICA", variant_id="NON_AUTHORITATIVE_STALE_VIEW", variant_index=0, disposition="MODEL_INTEGRITY_INCIDENT_QUARANTINED", reason="SELECTED_REPLICA_STALE", execution="NOT_INVOKED", failure="STALE", publisher_phase="WITNESS_COMMITTED", image=stale_image))

    middle_record_hash = flip_byte(BASE_RECORD_SHA256, 16)
    d13_mutations = (
        ("DIVERGENT_GENERATION", {"source_generation": bytes([0xA2]) * 32}),
        ("DIVERGENT_REVISION", {"revision": 18}),
        ("DIVERGENT_RECORD", {"revision": 18, "record_sha256": middle_record_hash}),
    )
    for index, (variant, mutation) in enumerate(d13_mutations):
        receipt_sha = digest(receipt_message(**mutation))
        competing = digest(view_message(receipt_sha, replica_id=COMPETING_REPLICA, **mutation))
        add(derived_row(base, case_id="D13_DIVERGENT_AUTHORITATIVE_VIEWS", variant_id=variant, variant_index=index, disposition="MODEL_INTEGRITY_INCIDENT_QUARANTINED", reason="DIVERGENT_AUTHORITATIVE_VIEWS", execution="NOT_INVOKED", failure="CONFLICT", publisher_phase="WITNESS_COMMITTED", image=triple, overrides={"competing_view_sha256": competing}))

    fork_witness = digest(witness_message(base_receipt, previous_witness=bytes([0x9A]) * 32))
    d14 = (
        ("MISSING", "MODEL_INCOMPLETE_FAIL_CLOSED", "WITNESS_MISSING", "PENDING", "ABSENT", absent_digest("WITNESS"), absent_digest("WITNESS")),
        ("UNAVAILABLE", "MODEL_INCOMPLETE_FAIL_CLOSED", "WITNESS_UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", absent_digest("WITNESS"), absent_digest("WITNESS")),
        ("CORRUPT_STORED_HASH", "MODEL_INTEGRITY_INCIDENT_QUARANTINED", "WITNESS_STORED_HASH_CORRUPT", "MALFORMED", "PRESENT", base_witness, flip_byte(base_witness, 7)),
        ("FORKED_SAME_SEQUENCE", "MODEL_INTEGRITY_INCIDENT_QUARANTINED", "WITNESS_FORKED_SAME_SEQUENCE", "CONFLICT", "FORKED", base_witness, fork_witness),
    )
    for index, (variant, disposition, reason, failure, state, computed, stored) in enumerate(d14):
        image = dict(triple)
        image.update(witness_state=state, computed_witness_sha256=computed, stored_witness_sha256=stored)
        add(derived_row(base, case_id="D14_WITNESS_FAILURES", variant_id=variant, variant_index=index, disposition=disposition, reason=reason, execution="NOT_INVOKED", failure=failure, publisher_phase="WITNESS_COMMITTED", image=image))

    positions = (("FIRST", 0), ("MIDDLE", 16), ("LAST", 31))
    object_positions = {"FIRST": 0, "MIDDLE": 2_747, "LAST": 5_493}
    for component_ordinal, component in enumerate(("OBJECT", "RECEIPT_STORED_HASH", "WITNESS_STORED_HASH")):
        for position_ordinal, (position, digest_index) in enumerate(positions):
            image = dict(triple)
            if component == "OBJECT":
                image["observed_object_sha256"] = hashlib.sha256(flip_byte(record, object_positions[position])).digest()
                reason = "POST_PERSISTENCE_OBJECT_CORRUPTION"
            elif component == "RECEIPT_STORED_HASH":
                image["stored_receipt_sha256"] = flip_byte(base_receipt, digest_index)
                reason = "POST_PERSISTENCE_RECEIPT_STORED_HASH_CORRUPTION"
            else:
                image["stored_witness_sha256"] = flip_byte(base_witness, digest_index)
                reason = "POST_PERSISTENCE_WITNESS_STORED_HASH_CORRUPTION"
            add(derived_row(base, case_id="D15_POST_PERSISTENCE_CORRUPTION", variant_id=f"{component}_BIT_{position}", variant_index=3 * component_ordinal + position_ordinal, disposition="MODEL_INTEGRITY_INCIDENT_QUARANTINED", reason=reason, execution="NOT_INVOKED", failure="MALFORMED", publisher_phase="WITNESS_COMMITTED", image=image))

    rows.sort(key=lambda row: (row["case_id"].encode("ascii"), row["variant_index"]))
    require(len(rows) == ROW_COUNT, "row catalog cardinality drift")
    require(len({(row["case_id"], row["variant_index"]) for row in rows}) == ROW_COUNT, "duplicate row key")
    require(Counter(row["case_id"] for row in rows) == Counter(FAMILY_COUNTS), "family row counts drift")
    return rows


def encode_field(value: Any, kind: str) -> bytes:
    if kind == "bytes":
        require(type(value) is bytes, "raw row field is not bytes")
        if len(value) == 0:
            raise CheckFailure("empty raw row field")
        return value
    if kind == "ascii":
        require(type(value) is str and value and value.isascii(), "invalid ASCII row field")
        return value.encode("ascii")
    require(kind == "u64", "unknown row field encoder")
    return u64(value)


def row_message(row: dict[str, Any]) -> bytes:
    return framed_message(encode_field(row[name], kind) for name, kind in ROW_FIELDS)


def catalog_oracle(record: bytes) -> dict[str, Any]:
    rows = generate_rows(record)
    row_messages = [row_message(row) for row in rows]
    row_digests = [digest(message) for message in row_messages]
    require(len(set(row_digests)) == ROW_COUNT, "duplicate row commitment")
    catalog = framed_message(
        (CATALOG_DOMAIN, POLICY, PROFILE, S15_CONTRACT_SHA256, u64(ROW_COUNT), *row_digests)
    )
    require(len(catalog) == CATALOG_MESSAGE_LEN, "catalog message length KAT drift")
    require(digest(catalog) == CATALOG_SHA256, "catalog commitment KAT drift")
    base_receipt_message = receipt_message()
    base_receipt = digest(base_receipt_message)
    base_witness_message = witness_message(base_receipt)
    base_witness = digest(base_witness_message)
    base_view_message = view_message(base_receipt)
    return {
        "rows": rows,
        "row_messages": row_messages,
        "row_digests": row_digests,
        "catalog_message": catalog,
        "catalog_sha256": digest(catalog),
        "receipt_message": base_receipt_message,
        "receipt_sha256": base_receipt,
        "witness_message": base_witness_message,
        "witness_sha256": base_witness,
        "selected_view_message": base_view_message,
        "selected_view_sha256": digest(base_view_message),
    }


def check_contract(repo: Path, oracle: dict[str, Any]) -> dict[str, Any]:
    contract = load_json(repo, CONTRACT_PATH)
    require_exact(
        set(contract),
        {
            "boundary", "catalog", "decision", "dependency", "encoding", "evaluator",
            "execution_boundary", "fault_families", "fixed_fixture", "known_answers",
            "mutation_rules", "operational_gap_codes", "policy", "profile",
            "publisher_model", "remaining_gap_codes", "row_generation", "row_model",
            "schema", "state_recipes", "status", "test_matrix",
        },
        "contract root is not closed",
    )
    require_exact(contract["schema"], "agent_bridge.memory_temporal_recovered_envelope_durability_fault_model_s16.v0", "contract schema drift")
    require_exact(contract["status"], STATUS, "contract status drift")
    require_exact(contract["decision"], DECISION, "contract decision drift")
    require_exact(contract["policy"], POLICY.decode("ascii"), "contract policy drift")
    require_exact(contract["profile"], PROFILE.decode("ascii"), "contract profile drift")
    require_exact(
        contract["execution_boundary"],
        {
            "d05_modeled_cut_position_count": 53,
            "d05_modeled_row_count": 106,
            "d05_model_only_cut_position_count": 3,
            "d05_model_only_cuts": [
                "BEFORE_OPEN", "AFTER_COMPLETE_BEFORE_S14", "AFTER_HISTORICAL",
            ],
            "d05_model_only_row_count": 6,
            "d05_test_only_fresh_instance_reread_count": 50,
            "d05_test_only_injected_failure_attempt_count": 50,
            "external_durable_restart_execution_count": 0,
            "os_process_crash_execution_count": 0,
            "test_only_transport_is_external_durability_evidence": False,
        },
        "execution boundary drift",
    )
    require_exact(
        contract["catalog"],
        {
            "catalog_commitment_is_derived_not_trusted_input": True,
            "catalog_frame_count": 5_644,
            "catalog_frame_order": ["catalog_domain", "policy", "profile", "s15_contract_sha256_raw", "row_count_u64be", "ordered_row_commitment_sha256_raw_repeated"],
            "duplicate_case_variant_or_commitment_allowed": False,
            "family_counts": FAMILY_COUNTS,
            "ordering": "ASCII_CASE_ID_THEN_NUMERIC_VARIANT_INDEX",
            "row_count": ROW_COUNT,
            "row_frame_count": 35,
            "row_key": ["case_id", "variant_index"],
        },
        "catalog contract drift",
    )
    dependency = contract["dependency"]
    require_exact(dependency["feature"], FEATURE, "feature drift")
    require_exact(dependency["requires_feature"], S15_FEATURE, "S15 dependency drift")
    require_exact(dependency["feature_default_enabled"], False, "S16 feature became default")
    require_exact(dependency["frozen_s15_contract_sha256"], S15_CONTRACT_SHA256.hex(), "S15 contract pin drift")
    require_exact(dependency["only_allowed_s15_source_seam"], "CFG_FEATURE_GATED_PRIVATE_CHILD_MODULE_DECLARATION", "S15 seam drift")
    require_exact(dependency["s15_test_fixture_seam_allowed"], False, "S15 fixture seam enabled")

    enc = contract["encoding"]
    require_exact(enc["canonicalization"], "EXACT_ORDERED_U64BE_LENGTH_PREFIXED_BYTE_FRAMES", "canonicalization drift")
    require_exact(enc["frame"], "U64BE_BYTE_LENGTH_THEN_EXACT_BYTES", "frame encoding drift")
    require_exact(enc["digest_field_encoding"], "RAW_32_BYTES", "digest encoding drift")
    require_exact(enc["u64_field_encoding"], "RAW_8_BYTE_BIG_ENDIAN", "u64 encoding drift")
    require_exact(enc["empty_or_default_frame_allowed"], False, "empty frames enabled")
    require_exact(enc["unknown_frame_or_enum_is_fail_closed"], True, "unknown frame fail-closed drift")
    require_exact(enc["domains"], {"absent": ABSENT_DOMAIN.decode(), "catalog": CATALOG_DOMAIN.decode(), "receipt": RECEIPT_DOMAIN.decode(), "replica_view": VIEW_DOMAIN.decode(), "row": ROW_DOMAIN.decode(), "witness": WITNESS_DOMAIN.decode()}, "domain drift")
    require_exact(enc["schemas"], {"receipt": RECEIPT_SCHEMA.decode(), "replica_view": VIEW_SCHEMA.decode(), "row": ROW_SCHEMA.decode(), "witness": WITNESS_SCHEMA.decode()}, "schema-domain drift")
    require(len(enc["receipt_frame_order"]) == 14, "receipt frame cardinality drift")
    require(len(enc["witness_frame_order"]) == 17, "witness frame cardinality drift")
    require(len(enc["replica_view_frame_order"]) == 15, "view frame cardinality drift")
    encoded_row_names = [
        name.removesuffix("_ascii").removesuffix("_raw").removesuffix("_u64be")
        for name in enc["row_frame_order"]
    ]
    encoded_row_names[21] = encoded_row_names[21].removesuffix("_or_absent")
    require(
        [name for name, _ in ROW_FIELDS] == encoded_row_names,
        "row frame order drift",
    )

    known = contract["known_answers"]
    require_exact(known["catalog_message_len"], len(oracle["catalog_message"]), "catalog KAT length drift")
    require_exact(known["catalog_sha256"], oracle["catalog_sha256"].hex(), "catalog KAT drift")
    require_exact(known["receipt_message_len"], len(oracle["receipt_message"]), "receipt KAT length drift")
    require_exact(known["receipt_sha256"], oracle["receipt_sha256"].hex(), "receipt KAT drift")
    require_exact(known["witness_message_len"], len(oracle["witness_message"]), "witness KAT length drift")
    require_exact(known["witness_sha256"], oracle["witness_sha256"].hex(), "witness KAT drift")
    require_exact(known["selected_replica_view_message_len"], len(oracle["selected_view_message"]), "view KAT length drift")
    require_exact(known["selected_replica_view_sha256"], oracle["selected_view_sha256"].hex(), "view KAT drift")
    require_exact(known["absent_replica_view_message_len"], len(framed_message((ABSENT_DOMAIN, b"REPLICA_VIEW"))), "absent view length drift")
    require_exact(known["absent_replica_view_sha256"], absent_digest("REPLICA_VIEW").hex(), "absent view KAT drift")
    require_exact(known["clean_d00_row_message_len"], len(oracle["row_messages"][0]), "D00 row KAT length drift")
    require_exact(known["clean_d00_row_sha256"], oracle["row_digests"][0].hex(), "D00 row KAT drift")

    fixture = contract["fixed_fixture"]
    require_exact(fixture["base_record_len"], BASE_RECORD_LEN, "base record length drift")
    require_exact(fixture["base_record_sha256"], BASE_RECORD_SHA256.hex(), "base record hash drift")
    require_exact(fixture["s15_contract_sha256_raw"], S15_CONTRACT_SHA256.hex(), "fixture S15 pin drift")
    require_exact(fixture["lookup_commitment_sha256"], LOOKUP_SHA256.hex(), "fixture lookup drift")
    require_exact(fixture["representative_prefix_len"], 2_747, "representative prefix drift")
    require_exact(fixture["base_object_revision"], 17, "base revision drift")
    require_exact(fixture["lower_revision"], 16, "lower revision drift")
    require_exact(fixture["higher_revision"], 18, "higher revision drift")

    require_exact(contract["test_matrix"], {"nonignored_rust_test_count": 20, "test_names": list(TEST_NAMES)}, "test matrix drift")
    require_exact(contract["operational_gap_codes"], list(OPERATIONAL_GAPS), "operational gap drift")
    require_exact(contract["remaining_gap_codes"], list(REMAINING_GAPS), "remaining gap drift")
    require_exact(
        contract["publisher_model"],
        {
            "ack_is_durability_evidence": False,
            "legal_phase_transitions": [
                "EMPTY_TO_OBJECT_PREFIX",
                "OBJECT_PREFIX_TO_OBJECT_COMMITTED",
                "OBJECT_COMMITTED_TO_RECEIPT_COMMITTED",
                "RECEIPT_COMMITTED_TO_WITNESS_COMMITTED",
                "WITNESS_COMMITTED_TO_ACKED",
            ],
            "phases": [
                "EMPTY", "OBJECT_PREFIX", "OBJECT_COMMITTED", "RECEIPT_COMMITTED",
                "WITNESS_COMMITTED", "ACKED",
            ],
            "restart_discards_all_volatile_bytes_hashes_sink_and_adapter_state": True,
            "restart_resumes_partial_s15_adapter": False,
            "restart_uses_modeled_durable_image_only": True,
            "response_loss_can_trigger_blind_republish_or_retry": False,
        },
        "publisher model drift",
    )
    require_exact(
        contract["row_model"],
        {
            "ack_states": ["NOT_OBSERVED", "OBSERVED"],
            "adapter_states": ["FRESH", "STREAMING", "COMPLETED", "TERMINAL_FAILED"],
            "authority_states": ["CLAIMS_AUTHORITATIVE", "NON_AUTHORITATIVE_STALE"],
            "crash_cuts": [
                "NONE", "PUBLISH_AFTER_OBJECT_PREFIX", "PUBLISH_AFTER_OBJECT_COMMIT",
                "PUBLISH_AFTER_RECEIPT_COMMIT", "PUBLISH_AFTER_WITNESS_COMMIT",
                "PUBLISH_AFTER_ACK", "READ_BEFORE_OPEN", "READ_AFTER_OPEN",
                "READ_AFTER_DATA", "READ_AFTER_COMPLETE_BEFORE_S14",
                "READ_AFTER_HISTORICAL",
            ],
            "dispositions": [
                "MODEL_EXACT_HISTORICAL_READ_ELIGIBLE", "MODEL_INCOMPLETE_FAIL_CLOSED",
                "MODEL_AMBIGUOUS_QUARANTINED", "MODEL_INTEGRITY_INCIDENT_QUARANTINED",
            ],
            "evidence_origins": ["SIMULATED_MODEL"],
            "mapped_s15_failures": [
                "NONE", "NOT_FOUND", "PENDING", "CONFLICT", "STALE", "ROLLBACK",
                "UNAVAILABLE", "UNAUTHENTICATED", "MALFORMED", "INDETERMINATE",
            ],
            "object_persistence_states": ["ABSENT", "PARTIAL", "COMMITTED"],
            "publisher_phases": [
                "EMPTY", "OBJECT_PREFIX", "OBJECT_COMMITTED", "RECEIPT_COMMITTED",
                "WITNESS_COMMITTED", "ACKED",
            ],
            "receipt_states": ["ABSENT", "COMMITTED"],
            "s15_execution_results": ["NOT_INVOKED", "STREAM_EXACT", "FAIL_INDETERMINATE"],
            "side_effect_values": ["NONE"],
            "unauthenticated_failure_is_reachable": False,
            "witness_states": ["ABSENT", "PRESENT", "UNAVAILABLE", "FORKED"],
        },
        "row-model enum drift",
    )
    require_exact([family["case_id"] for family in contract["fault_families"]], list(FAMILY_COUNTS), "fault family order drift")
    require_exact({family["case_id"]: family["row_count"] for family in contract["fault_families"]}, FAMILY_COUNTS, "fault family counts drift")
    d05 = contract["fault_families"][5]["cut_generator"]
    require_exact(d05["after_data_range"], {"start_inclusive": 1, "end_inclusive": 49, "expanded_count": 49, "format": "AFTER_DATA_%04d"}, "D05 data cut generator drift")
    require_exact(d05["expanded_cut_count"], 53, "D05 cut count drift")
    require_exact(d05["expanded_row_count"], 106, "D05 row count drift")
    d13 = contract["fault_families"][13]["variants"][2]
    require_exact(d13, {"competing_mutation": "OBJECT_REVISION_17_TO_18_AND_RECORD_SHA256_XOR_MIDDLE_BYTE_01_WITH_RECOMPUTED_RECEIPT", "variant_id": "DIVERGENT_RECORD"}, "D13 record mutation drift")

    row_generation = contract["row_generation"]
    require_exact(set(row_generation), {"application_order", "digest_tokens", "family_state_rules", "image_templates", "row_defaults", "unresolved_token_or_rule_is_fail_closed"}, "row generation root drift")
    require_exact(
        row_generation["application_order"],
        [
            "ROW_DEFAULTS", "IMAGE_TEMPLATE", "FAMILY_STATE_RULE",
            "VARIANT_STATE_RULE", "D05_RAW_LIFECYCLE_STATE",
            "RAW_STATE_EVALUATOR_OUTCOME", "ENCODE_EXACT_35_FRAMES",
        ],
        "raw-state evaluator application order drift",
    )
    require_exact(row_generation["unresolved_token_or_rule_is_fail_closed"], True, "unresolved row token became allowed")
    require_exact(row_generation["row_defaults"], {"ack_state": "NOT_OBSERVED", "adapter_post_state": "FRESH", "adapter_pre_state": "FRESH", "competing_view_sha256": "ABSENT_REPLICA_VIEW", "crash_cut": "NONE", "crash_cut_index": 0, "evidence_origin": "SIMULATED_MODEL", "external_durability_observation_count": 0, "owned_lab_durability_observation_count": 0, "provider_durability_observation_count": 0, "side_effects_unlocked": "NONE"}, "row defaults drift")
    require_exact(set(row_generation["family_state_rules"]), set(FAMILY_COUNTS), "row generation family closure drift")
    require_exact(row_generation["family_state_rules"]["D12_SELECTED_STALE_REPLICA"]["mutation_application"], "KEEP_BASE_DURABLE_RECEIPT_AND_WITNESS_REPLACE_ONLY_SELECTED_VIEW_WITH_REPLICA_96_NON_AUTHORITATIVE_STALE_REVISION_16_VIEW_AND_RECOMPUTED_REVISION_16_RECEIPT_HASH", "D12 exact stale mutation drift")
    require_exact(row_generation["family_state_rules"]["D13_DIVERGENT_AUTHORITATIVE_VIEWS"]["mutation_application"], "ADD_CLAIMS_AUTHORITATIVE_REPLICA_97_COMPETING_VIEW_USING_EXACT_VARIANT_MUTATION", "D13 competing-view mutation drift")

    boundary = contract["boundary"]
    require_exact(
        boundary,
        {
            "bridge_or_state_store_caller": False,
            "currentness_or_admission_issued": False,
            "external_durability_observation_count": 0,
            "filesystem_network_database_or_provider_wiring": False,
            "modeled_durable_state_is_external_durability_evidence": False,
            "modeled_witness_is_independently_operated": False,
            "owned_lab_durability_observation_count": 0,
            "owner_authorized_object_selection_available": False,
            "production_or_provider_concrete_runtime_transport_present": False,
            "provider_durability_observation_count": 0,
            "s15_adapter_logic_and_s14_verifier_unchanged": True,
            "side_effects_unlocked": "NONE",
            "test_only_synthetic_transport_present": True,
        },
        "contract boundary drift",
    )
    require_exact(contract["row_model"]["unauthenticated_failure_is_reachable"], False, "UNAUTHENTICATED became reachable")
    require("UNAUTHENTICATED" in contract["row_model"]["mapped_s15_failures"], "UNAUTHENTICATED enum removed")

    evaluator = contract["evaluator"]
    require_exact(
        set(evaluator),
        {
            "catalog_builder_sets_outcome_fields", "pre_open_failure_never_invokes_s15",
            "precedence", "raw_evaluator_is_single", "raw_input_contains_outcome_fields",
            "raw_durable_lifecycle_pair_is_exactly_validated",
            "raw_lifecycle_tuple_is_exactly_validated",
            "receipt_or_view_metadata_can_replace_frozen_lookup",
            "replica_switch_latest_list_range_retry_cache_or_repair_allowed",
            "unknown_combination_disposition", "unknown_combination_mapped_s15_failure",
        },
        "evaluator contract root drift",
    )
    require_exact(evaluator["catalog_builder_sets_outcome_fields"], False, "catalog builder regained outcome authority")
    require_exact(evaluator["raw_evaluator_is_single"], True, "canonical raw evaluator multiplicity drift")
    require_exact(evaluator["raw_input_contains_outcome_fields"], False, "raw input regained outcome fields")
    require_exact(evaluator["raw_durable_lifecycle_pair_is_exactly_validated"], True, "raw durable/lifecycle pairing drift")
    require_exact(evaluator["raw_lifecycle_tuple_is_exactly_validated"], True, "raw lifecycle validation drift")
    require_exact(evaluator["pre_open_failure_never_invokes_s15"], True, "pre-open S15 boundary drift")
    require_exact(evaluator["receipt_or_view_metadata_can_replace_frozen_lookup"], False, "lookup replacement became allowed")
    require_exact(evaluator["replica_switch_latest_list_range_retry_cache_or_repair_allowed"], False, "replica repair became allowed")
    require_exact(evaluator["unknown_combination_disposition"], "MODEL_AMBIGUOUS_QUARANTINED", "unknown disposition stopped failing closed")
    require_exact(evaluator["unknown_combination_mapped_s15_failure"], "INDETERMINATE", "unknown failure mapping drift")
    require_exact(
        evaluator["precedence"],
        [
            "REJECT_UNKNOWN_SCHEMA_ENUM_FRAME_ROW_SHAPE_OR_LIFECYCLE_TUPLE_AS_INDETERMINATE",
            "REJECT_NONZERO_EXTERNAL_PROVIDER_OR_OWNED_LAB_COUNT_OR_NON_NONE_SIDE_EFFECT",
            "IF_SELECTED_AND_COMPETING_VIEWS_BOTH_CLAIM_AUTHORITY_SAME_GENERATION_AND_REVISION_DIVERGENCE_IS_EQUIVOCATION_OTHER_DIVERGENCE_IS_SPLIT_BRAIN",
            "ACK_BEFORE_WITNESS_COMMIT_IS_AMBIGUOUS_INDETERMINATE",
            "RECEIPT_PRESENT_WITH_OBJECT_ABSENT_IS_INTEGRITY_CONFLICT",
            "OBJECT_ABSENT_OR_PARTIAL_IS_CLASSIFIED_FROM_RAW_PERSISTENCE_BYTES_AND_LIFECYCLE_WITHOUT_S15_OPEN",
            "COMPUTED_VERSUS_STORED_RECEIPT_OR_WITNESS_HASH_MISMATCH_IS_MALFORMED_UNLESS_WITNESS_FORK_IS_WELL_FORMED",
            "RECEIPT_TO_OBJECT_LOOKUP_INCARNATION_ID_OR_CHAIN_BINDING_MISMATCH_IS_CONFLICT_BEFORE_ROLLBACK",
            "MISSING_WITNESS_IS_PENDING_AND_UNAVAILABLE_WITNESS_IS_UNAVAILABLE",
            "ONLY_EXACT_CANONICAL_WITNESS_HEAD_AND_RECEIPT_BOUND_SELECTED_VIEW_CAN_PROVE_OLD_GENERATION_OR_LOWER_REVISION_ROLLBACK_WITHOUT_GENERATION_ORDERING",
            "NON_AUTHORITATIVE_STALE_SELECTED_VIEW_IS_STALE_WITHOUT_REPLICA_SWITCH",
            "ONLY_EXACT_OBJECT_RECEIPT_WITNESS_AND_SELECTED_VIEW_CAN_STREAM_TO_S15",
            "ANY_UNCLASSIFIED_COMBINATION_IS_INDETERMINATE",
        ],
        "canonical raw evaluator precedence drift",
    )

    for row in oracle["rows"]:
        require(row["evidence_origin"] == "SIMULATED_MODEL", "non-simulated row")
        require(row["external_durability_observation_count"] == 0, "nonzero external row count")
        require(row["provider_durability_observation_count"] == 0, "nonzero provider row count")
        require(row["owned_lab_durability_observation_count"] == 0, "nonzero owned-lab row count")
        require(row["side_effects_unlocked"] == "NONE", "row unlocked side effects")
        require(row["mapped_s15_failure"] != "UNAUTHENTICATED", "UNAUTHENTICATED row became reachable")
        if row["s15_execution_result"] == "NOT_INVOKED":
            require(row["adapter_pre_state"] == "FRESH", "pre-open row did not use a fresh adapter")
    return contract


def feature_is_reachable(features: dict[str, Any], roots: list[str], target: str) -> bool:
    pending = list(roots)
    seen: set[str] = set()
    while pending:
        feature = pending.pop()
        if feature in seen:
            continue
        seen.add(feature)
        if feature == target:
            return True
        edges = features.get(feature, [])
        require(type(edges) is list, f"Cargo feature is not a list: {feature}")
        for edge in edges:
            require(type(edge) is str, f"Cargo feature edge is not a string: {feature}")
            candidate = edge.split("/", 1)[0].removeprefix("dep:")
            if candidate in features:
                pending.append(candidate)
    return False


def check_glue(repo: Path) -> None:
    cargo = tomllib.loads(read_text(repo, STORE_CARGO_PATH))
    features = cargo.get("features")
    require(type(features) is dict, "Cargo features table missing")
    require_exact(features.get(FEATURE), [S15_FEATURE], "S16 feature dependency drift")
    defaults = features.get("default", [])
    require(type(defaults) is list, "Cargo default feature list missing")
    require(not feature_is_reachable(features, defaults, FEATURE), "S16 became default-reachable")

    parent = read_text(repo, S15_SOURCE_PATH)
    require(parent.count(S16_CHILD_GLUE) == 1, "S16 private child glue missing or duplicated")
    restored = parent.replace(S16_CHILD_GLUE, "", 1)
    require(
        hashlib.sha256(restored.encode("utf-8")).hexdigest()
        == S15_SOURCE_SHA256_WITHOUT_S16_GLUE,
        "S15 adapter logic changed beyond the unique S16 child glue",
    )
    for visibility in ("pub mod durability_fault_model", "pub(crate) mod durability_fault_model", "pub(super) mod durability_fault_model"):
        require(visibility not in parent, "S16 child module became visible")

    store_root = repo / "crates/store/src"
    occurrences = 0
    for path in store_root.rglob("*.rs"):
        occurrences += path.read_text(encoding="utf-8").count("mod durability_fault_model;")
    require(occurrences == 1, "S16 child module declaration is not unique")


def rust_test_names(source: str) -> tuple[str, ...]:
    pattern = re.compile(r"(?m)^\s*#\[test\]\s*\n\s*fn (s16_[a-z0-9_]+)\s*\(")
    names = tuple(pattern.findall(source))
    require(len(names) == len(set(names)), "duplicate S16 Rust test name")
    return names


def strip_rust_comments_and_literals(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", " ", source)
    source = re.sub(r'r#+".*?"#+', '""', source, flags=re.DOTALL)
    source = re.sub(r'"(?:\\.|[^"\\])*"', '""', source, flags=re.DOTALL)
    return source


def mask_rust_comments_and_literals(source: str) -> str:
    """Mask non-code while preserving offsets for small braced-item checks."""

    def mask(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    source = re.sub(r"/\*.*?\*/", mask, source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", mask, source)
    source = re.sub(r'r#+".*?"#+', mask, source, flags=re.DOTALL)
    source = re.sub(r'"(?:\\.|[^"\\])*"', mask, source, flags=re.DOTALL)
    return source


def rust_braced_item_region(source: str, declaration: str, label: str) -> tuple[str, str]:
    """Return one raw/masked Rust item region using balanced braces."""

    masked = mask_rust_comments_and_literals(source)
    matches = list(re.finditer(declaration, masked, flags=re.MULTILINE))
    require(len(matches) == 1, f"S16 Rust {label} is missing or duplicated")
    start = matches[0].start()
    opening = masked.find("{", matches[0].start())
    require(opening >= 0, f"S16 Rust {label} body is missing")
    depth = 0
    for index in range(opening, len(masked)):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1], masked[start : index + 1]
    raise CheckFailure(f"S16 Rust {label} body is unbalanced")


def rust_function_region(source: str, name: str) -> tuple[str, str]:
    return rust_braced_item_region(
        source,
        rf"^\s*fn\s+{re.escape(name)}\s*\(",
        f"function {name}",
    )


def rust_struct_region(source: str, name: str) -> tuple[str, str]:
    return rust_braced_item_region(
        source,
        rf"^\s*struct\s+{re.escape(name)}\s*\{{",
        f"struct {name}",
    )


def parse_rust_byte_array(source: str, name: str) -> bytes:
    match = re.search(
        rf"const\s+{re.escape(name)}:\s*\[u8;\s*32\]\s*=\s*\[(.*?)\];",
        source,
        flags=re.DOTALL,
    )
    require(match is not None, f"missing Rust byte-array constant: {name}")
    values = bytes(int(value, 16) for value in re.findall(r"0x([0-9a-fA-F]{2})", match.group(1)))
    require(len(values) == 32, f"Rust byte-array width drift: {name}")
    return values


def require_rust_string_constant(
    source: str,
    name: str,
    rust_type: str,
    value: str,
    *,
    byte_string: bool = False,
) -> None:
    literal_prefix = "b" if byte_string else ""
    pattern = (
        rf"const\s+{re.escape(name)}\s*:\s*{rust_type}\s*=\s*"
        rf'{literal_prefix}"{re.escape(value)}"\s*;'
    )
    require(
        re.search(pattern, source, flags=re.DOTALL) is not None,
        f"S16 Rust constant drift: {name}",
    )


def check_raw_evaluator_structure(production: str) -> None:
    """Keep raw modeled state, canonical evaluation, and row labels one-way."""

    evaluator_names = re.findall(
        r"(?m)^\s*fn\s+(evaluate_[a-z0-9_]+)\s*\(",
        strip_rust_comments_and_literals(production),
    )
    require_exact(
        evaluator_names,
        ["evaluate_raw_modeled_state_v1"],
        "S16 canonical raw evaluator is not unique",
    )

    raw_outcome_tokens = (
        "ModelDispositionV1", "ModeledS15ExecutionResultV1",
        "MappedS15FailureV1", "ModeledEvaluationV1", "ModeledFaultRowV1",
        "case_id", "variant_id", "variant_index", "reason",
    )
    for struct_name in ("ModeledDurableStateV1", "ModeledVolatileStateV1"):
        _raw, masked = rust_struct_region(production, struct_name)
        for token in raw_outcome_tokens:
            require(token not in masked, f"S16 raw input {struct_name} contains outcome token: {token}")

    image_raw, image_masked = rust_function_region(production, "row_image_from_raw_state_v1")
    for token in (
        "ModelDispositionV1", "ModeledS15ExecutionResultV1",
        "MappedS15FailureV1", "ModeledEvaluationV1", "ModeledFaultRowV1",
        "case_id", "variant_id", "variant_index", "reason",
    ):
        require(token not in image_masked, f"S16 raw-to-image materializer contains outcome token: {token}")
    require("&ModeledDurableStateV1" in image_raw, "S16 row image is not derived from raw durable state")

    evaluator_raw, evaluator_masked = rust_function_region(
        production, "evaluate_raw_modeled_state_v1"
    )
    for token in ("case_id", "variant_id", "variant_index", "ModeledFaultRowV1"):
        require(token not in evaluator_masked, f"S16 raw evaluator depends on catalog label token: {token}")
    require("&ModeledDurableStateV1" in evaluator_raw, "S16 evaluator lost raw durable state")
    require("&ModeledVolatileStateV1" in evaluator_raw, "S16 evaluator lost raw volatile state")
    require(
        re.search(r"unknown_modeled_evaluation_v1\s*\(\s*image\s*\)\s*\}\s*$", evaluator_masked)
        is not None,
        "S16 evaluator lost its terminal unknown fail-closed fallback",
    )

    unknown_raw, _unknown_masked = rust_function_region(
        production, "unknown_modeled_evaluation_v1"
    )
    for token in (
        "ModelDispositionV1::AmbiguousQuarantined",
        '"UNCLASSIFIED_MODELED_STATE"',
        "ModeledS15ExecutionResultV1::NotInvoked",
        "MappedS15FailureV1::Indeterminate",
    ):
        require(token in unknown_raw, f"S16 unknown fallback drift: {token}")
    for forbidden in (
        "ModelDispositionV1::ExactHistoricalReadEligible",
        "ModeledS15ExecutionResultV1::StreamExact",
        "MappedS15FailureV1::None",
    ):
        require(forbidden not in unknown_raw, f"S16 unknown fallback became eligible: {forbidden}")

    divergence_raw, _divergence_masked = rust_function_region(production, "views_diverge_v1")
    for field in (
        "source_incarnation", "source_generation_id", "object_id", "object_revision",
        "record_len", "record_sha256", "receipt_sha256",
    ):
        require(
            divergence_raw.count(field) >= 2,
            f"S16 authoritative divergence stopped comparing raw field: {field}",
        )
    identity_raw, _identity_masked = rust_function_region(
        production, "views_share_revision_identity_v1"
    )
    for field in ("source_incarnation", "source_generation_id", "object_id", "object_revision"):
        require(
            identity_raw.count(field) >= 2,
            f"S16 equivocation identity stopped comparing raw field: {field}",
        )

    lifecycle_raw, _lifecycle_masked = rust_function_region(
        production, "raw_lifecycle_tuple_is_known_v1"
    )
    for token in (
        "volatile.publisher_phase", "volatile.adapter_phase",
        "volatile.adapter_post_phase", "volatile.ack", "volatile.crash_cut",
        "volatile.crash_cut_index", "volatile.observed_data_steps",
        "volatile.observed_len", "volatile.restarted_after_crash",
        "observed_len_for_data_steps_v1", "DATA_STEP_COUNT",
        "ModeledCrashCutV1::PublishAfterObjectPrefix",
        "ModeledCrashCutV1::PublishAfterObjectCommit",
        "ModeledCrashCutV1::PublishAfterReceiptCommit",
        "ModeledCrashCutV1::PublishAfterWitnessCommit",
        "ModeledCrashCutV1::PublishAfterAck",
        "ModeledCrashCutV1::ReadBeforeOpen", "ModeledCrashCutV1::ReadAfterOpen",
        "ModeledCrashCutV1::ReadAfterData",
        "ModeledCrashCutV1::ReadAfterCompleteBeforeS14",
        "ModeledCrashCutV1::ReadAfterHistorical",
        '"OBJECT_PREFIX"', '"OBJECT_COMMITTED"', '"RECEIPT_COMMITTED"',
        '"WITNESS_COMMITTED"', '"ACKED"', '"NOT_OBSERVED"', '"OBSERVED"',
    ):
        require(token in lifecycle_raw, f"S16 raw lifecycle predicate missing token: {token}")

    lifecycle_start = evaluator_raw.find("!raw_lifecycle_tuple_is_known_v1(volatile)")
    evidence_start = evaluator_raw.find("volatile.external_durability_observation_count")
    authoritative_start = evaluator_raw.find("if let (Some(selected), Some(competing))")
    ack_start = evaluator_raw.find('"ACK_OUTRAN_MODELED_DURABILITY"')
    require(
        0 <= lifecycle_start < evidence_start < authoritative_start,
        "S16 lifecycle/evidence/view precedence drift",
    )
    require(
        evaluator_raw.count("raw_lifecycle_tuple_is_known_v1(volatile)") == 1,
        "S16 evaluator does not call the raw lifecycle predicate exactly once",
    )
    evidence_region = evaluator_raw[evidence_start:authoritative_start]
    for token in (
        "volatile.external_durability_observation_count",
        "volatile.provider_durability_observation_count",
        "volatile.owned_lab_durability_observation_count",
        "ModeledSideEffectV1::None",
        "unknown_modeled_evaluation_v1(image)",
    ):
        require(token in evidence_region, f"S16 evidence-boundary fail-closed token missing: {token}")
    require(
        0 <= authoritative_start < ack_start,
        "S16 authoritative-view precedence no longer precedes ack classification",
    )
    authoritative_region = evaluator_raw[authoritative_start:ack_start]
    for token in (
        "claims_authority_v1(selected)", "claims_authority_v1(competing)",
        "views_diverge_v1(selected, competing)",
        "views_share_revision_identity_v1(selected, competing)",
        '"SAME_REVISION_EQUIVOCATION"', '"DIVERGENT_AUTHORITATIVE_VIEWS"',
    ):
        require(token in authoritative_region, f"S16 D11/D13 raw precedence token missing: {token}")

    receipt_match = evaluator_raw.find("let receipt = match &durable.receipt")
    receipt_absent_start = evaluator_raw.find("ModeledReceiptSlotV1::Absent => {", receipt_match)
    receipt_committed_start = evaluator_raw.find(
        "ModeledReceiptSlotV1::Committed(receipt) => receipt", receipt_absent_start
    )
    require(
        0 <= receipt_match < receipt_absent_start < receipt_committed_start,
        "S16 receipt-slot evaluator structure drift",
    )
    receipt_absent_region = evaluator_raw[receipt_absent_start:receipt_committed_start]
    for token, expected_count in (
        ('"OBJECT_COMMITTED"', 2),
        ("ModeledCrashCutV1::PublishAfterObjectCommit", 1),
        ("ModeledCrashCutV1::None", 1),
    ):
        require_exact(
            receipt_absent_region.count(token),
            expected_count,
            f"S16 receipt-absent durable/lifecycle schedule drift: {token}",
        )
    receipt_schedule = receipt_absent_region.find("let schedule_is_known = if volatile.restarted_after_crash")
    receipt_schedule_failure = receipt_absent_region.find("if !schedule_is_known")
    receipt_unknown = receipt_absent_region.find(
        "return unknown_modeled_evaluation_v1(image)", receipt_schedule_failure
    )
    receipt_pending = receipt_absent_region.find("MappedS15FailureV1::Pending")
    require(
        0 <= receipt_schedule < receipt_schedule_failure < receipt_unknown < receipt_pending,
        "S16 receipt-absent schedule no longer fails closed before pending outcome",
    )

    witness_match = evaluator_raw.find("let witness = match &durable.witness")
    witness_absent_start = evaluator_raw.find("ModeledWitnessSlotV1::Absent => {", witness_match)
    witness_unavailable_start = evaluator_raw.find(
        "ModeledWitnessSlotV1::Unavailable => {", witness_absent_start
    )
    witness_present_start = evaluator_raw.find(
        "ModeledWitnessSlotV1::Present(witness) => witness", witness_unavailable_start
    )
    require(
        0 <= witness_match < witness_absent_start < witness_unavailable_start < witness_present_start,
        "S16 witness-slot evaluator structure drift",
    )
    witness_absent_region = evaluator_raw[witness_absent_start:witness_unavailable_start]
    for token, expected_count in (
        ('"RECEIPT_COMMITTED"', 1),
        ("ModeledCrashCutV1::PublishAfterReceiptCommit", 1),
        ('"WITNESS_COMMITTED"', 1),
        ("ModeledCrashCutV1::None", 1),
    ):
        require_exact(
            witness_absent_region.count(token),
            expected_count,
            f"S16 witness-absent durable/lifecycle schedule drift: {token}",
        )
    witness_schedule = witness_absent_region.find("let schedule_is_known = if volatile.restarted_after_crash")
    witness_schedule_failure = witness_absent_region.find("if !schedule_is_known")
    witness_unknown = witness_absent_region.find(
        "return unknown_modeled_evaluation_v1(image)", witness_schedule_failure
    )
    witness_pending = witness_absent_region.find("MappedS15FailureV1::Pending")
    require(
        0 <= witness_schedule < witness_schedule_failure < witness_unknown < witness_pending,
        "S16 witness-absent schedule no longer fails closed before pending outcome",
    )

    witness_unavailable_region = evaluator_raw[witness_unavailable_start:witness_present_start]
    for token, expected_count in (
        ("volatile.restarted_after_crash", 1),
        ('volatile.publisher_phase.as_str() != "WITNESS_COMMITTED"', 1),
        ("ModeledCrashCutV1::None", 1),
    ):
        require_exact(
            witness_unavailable_region.count(token),
            expected_count,
            f"S16 unavailable-witness durable/lifecycle schedule drift: {token}",
        )
    unavailable_schedule = witness_unavailable_region.find("if volatile.restarted_after_crash")
    unavailable_unknown = witness_unavailable_region.find("return unknown_modeled_evaluation_v1(image)")
    unavailable_outcome = witness_unavailable_region.find('"WITNESS_UNAVAILABLE"')
    unavailable_failure = witness_unavailable_region.find("MappedS15FailureV1::Unavailable")
    require(
        0 <= unavailable_schedule < unavailable_unknown < unavailable_outcome < unavailable_failure,
        "S16 unavailable-witness schedule no longer fails closed before unavailable outcome",
    )

    canonical_witness_raw, _canonical_witness_masked = rust_function_region(
        production, "exact_canonical_witness_head_v1"
    )
    for token in (
        "witness_scope_id", "witness_incarnation", "witness_generation_id",
        "witness_sequence", "lookup_commitment_sha256", "source_incarnation",
        "source_generation_id", "object_id", "object_revision", "record_sha256",
        "receipt_sha256", "previous_witness_sha256", "stored_witness_sha256",
        "computed_witness_sha256_v1(witness)", "base.receipt", "base.witness",
    ):
        require(token in canonical_witness_raw, f"S16 canonical witness gate missing token: {token}")

    nonversion_conflicts = [
        evaluator_raw.find(f'"{reason}"')
        for reason in (
            "RECEIPT_LENGTH_MISMATCH", "RECEIPT_RECORD_HASH_MISMATCH",
            "RECEIPT_LOOKUP_COMMITMENT_MISMATCH", "RECEIPT_SOURCE_INCARNATION_MISMATCH",
            "RECEIPT_OBJECT_ID_MISMATCH", "RECEIPT_CHAIN_BINDING_MISMATCH",
        )
    ]
    missing_witness = evaluator_raw.find('"WITNESS_MISSING"')
    unavailable_witness = evaluator_raw.find('"WITNESS_UNAVAILABLE"')
    rollback_gate = evaluator_raw.find("if exact_canonical_witness_head_v1(witness, base)")
    generic_generation_conflict = evaluator_raw.find('"RECEIPT_SOURCE_GENERATION_MISMATCH"')
    generic_revision_conflict = evaluator_raw.find('"RECEIPT_OBJECT_REVISION_MISMATCH"')
    require(
        all(position >= 0 for position in nonversion_conflicts)
        and max(nonversion_conflicts) < missing_witness < unavailable_witness < rollback_gate
        < generic_generation_conflict < generic_revision_conflict,
        "S16 canonical rollback gate precedence drift",
    )
    rollback_region = evaluator_raw[rollback_gate:generic_generation_conflict]
    for token in (
        "exact_canonical_witness_head_v1(witness, base)",
        "if let Some(selected) = &durable.selected_view",
        "exact_selected_view_binding_v1(selected, receipt, receipt_sha256)",
        "witness_proves_receipt_generation_rollback_v1(receipt, witness)",
        "witness_proves_receipt_revision_rollback_v1(receipt, witness)",
        '"WITNESS_HEAD_GENERATION_MISMATCH"',
        '"WITNESS_HEAD_REVISION_ROLLBACK"',
        "MappedS15FailureV1::Rollback",
    ):
        require(token in rollback_region, f"S16 canonical rollback proof token missing: {token}")
    rollback_outside = evaluator_raw[:rollback_gate] + evaluator_raw[generic_generation_conflict:]
    for token, expected_count in (
        ('"WITNESS_HEAD_GENERATION_MISMATCH"', 1),
        ('"WITNESS_HEAD_REVISION_ROLLBACK"', 1),
        ("MappedS15FailureV1::Rollback", 2),
    ):
        require_exact(
            rollback_region.count(token),
            expected_count,
            f"S16 canonical rollback region occurrence drift: {token}",
        )
        require(
            token not in rollback_outside,
            f"S16 rollback bypass exists outside the canonical proof region: {token}",
        )
        require_exact(
            evaluator_raw.count(token),
            expected_count,
            f"S16 evaluator rollback occurrence drift: {token}",
        )

    stale_authority = evaluator_raw.find("ModeledReplicaAuthorityV1::NonAuthoritativeStale")
    stale_reason = evaluator_raw.find('"SELECTED_REPLICA_STALE"')
    require(
        ack_start < stale_authority < stale_reason,
        "S16 D12 raw non-authoritative stale branch precedence drift",
    )
    stale_region = evaluator_raw[stale_authority:stale_reason]
    for token in (
        "selected.source_incarnation", "selected.source_generation_id",
        "selected.object_id", "selected.object_revision", "witness.object_revision",
    ):
        require(token in stale_region, f"S16 D12 raw stale predicate missing: {token}")
    for forbidden in ("view_for_v1(", ".or_else(", ".unwrap_or("):
        require(forbidden not in evaluator_masked, f"S16 evaluator gained replica substitution: {forbidden}")

    materializer_raw, materializer_masked = rust_function_region(
        production, "row_from_raw_state_v1"
    )
    header = materializer_masked[: materializer_masked.find("{")]
    for token in (
        "ModelDispositionV1", "ModeledS15ExecutionResultV1",
        "MappedS15FailureV1", "ModeledEvaluationV1", "reason",
    ):
        require(token not in header, f"S16 row materializer accepts caller-supplied outcome: {token}")
    require(
        materializer_masked.count("evaluate_raw_modeled_state_v1(") == 1,
        "S16 row materializer does not use exactly one canonical evaluator",
    )
    for token in (
        "let ModeledEvaluationV1", "disposition", "reason",
        "s15_execution_result", "mapped_s15_failure",
    ):
        require(token in materializer_raw, f"S16 evaluated row field flow missing: {token}")

    builder_raw, builder_masked = rust_function_region(production, "build_case_catalog_v1")
    for token in (
        "ModelDispositionV1::", "ModeledS15ExecutionResultV1::",
        "MappedS15FailureV1::", "ModeledEvaluationV1", "modeled_evaluation_v1(",
        "unknown_modeled_evaluation_v1(", "evaluate_raw_modeled_state_v1(",
        "ModeledFaultRowV1 {", ".disposition =", ".reason =",
        ".s15_execution_result =", ".mapped_s15_failure =",
    ):
        require(token not in builder_masked, f"S16 catalog builder hand-fills outcome token: {token}")
    require(
        builder_masked.count("row_from_raw_state_v1(") >= 16,
        "S16 closed catalog does not route every family through the raw-state row materializer",
    )
    require(
        strip_rust_comments_and_literals(production).count("evaluate_raw_modeled_state_v1(") == 2,
        "S16 canonical raw evaluator has an unexpected production call path",
    )


def check_rust(repo: Path, oracle: dict[str, Any]) -> int:
    source = read_text(repo, S16_SOURCE_PATH)
    require("#[cfg(test)]\nmod tests {" in source, "S16 test module boundary missing")
    production, _tests = source.split("#[cfg(test)]\nmod tests {", 1)
    lexical = strip_rust_comments_and_literals(production)
    require(re.search(r"\bpub(?:\([^)]*\))?\s", lexical) is None, "S16 production public surface detected")
    check_raw_evaluator_structure(production)

    for name, value in (
        ("POLICY_ID", POLICY.decode()),
        ("PROFILE", PROFILE.decode()),
        ("RECEIPT_SCHEMA_ID", RECEIPT_SCHEMA.decode()),
        ("WITNESS_SCHEMA_ID", WITNESS_SCHEMA.decode()),
        ("REPLICA_VIEW_SCHEMA_ID", VIEW_SCHEMA.decode()),
        ("ROW_SCHEMA_ID", ROW_SCHEMA.decode()),
    ):
        require_rust_string_constant(source, name, r"&str", value)
    for name, value in (
        ("RECEIPT_DOMAIN", RECEIPT_DOMAIN.decode()),
        ("WITNESS_DOMAIN", WITNESS_DOMAIN.decode()),
        ("REPLICA_VIEW_DOMAIN", VIEW_DOMAIN.decode()),
        ("ABSENT_DOMAIN", ABSENT_DOMAIN.decode()),
        ("ROW_DOMAIN", ROW_DOMAIN.decode()),
        ("CATALOG_DOMAIN", CATALOG_DOMAIN.decode()),
    ):
        require_rust_string_constant(source, name, r"&\[u8\]", value, byte_string=True)
    require(
        re.search(r"const\s+ROW_COUNT\s*:\s*usize\s*=\s*5_639\s*;", source) is not None,
        "S16 Rust constant drift: ROW_COUNT",
    )
    require(
        parse_rust_byte_array(source, "S15_CONTRACT_SHA256") == S15_CONTRACT_SHA256,
        "S16 Rust S15 contract pin drift",
    )

    for pattern, label in (
        (r"\bunsafe\b", "unsafe code"),
        (r"\bserde\b|\bSerialize\b|\bDeserialize\b", "serde surface"),
        (r"\bstd\s*::\s*(?:fs|net|process|thread)\b", "filesystem/network/process/thread runtime"),
        (r"\b(?:tokio|reqwest|hyper|ureq|sqlx|rusqlite|rocksdb|sled)\b", "network/database/provider dependency"),
        (r"\b(?:StateStore|ab_bridge|Bridge)\b", "Bridge or StateStore wiring"),
        (r"\b(?:SystemTime|Instant)\b", "clock/currentness source"),
        (r"\b(?:rand|random|getrandom)\b", "randomness source"),
        (r"impl\s+RuntimeExactRecoveredEnvelopeTransportV1\s+for", "concrete S15 transport implementation"),
        (r"recover_historical_from_external_source_v1\s*\(", "production S14 recovery caller"),
    ):
        require(re.search(pattern, lexical) is None, f"S16 production {label} detected")

    names = rust_test_names(source)
    require_exact(names, TEST_NAMES, "S16 Rust test inventory drift")
    require("#[ignore" not in source, "ignored S16 test forbidden")

    for name, expected in (
        ("RECEIPT_KAT_SHA256", oracle["receipt_sha256"]),
        ("WITNESS_KAT_SHA256", oracle["witness_sha256"]),
        ("SELECTED_VIEW_KAT_SHA256", oracle["selected_view_sha256"]),
        ("D00_ROW_KAT_SHA256", oracle["row_digests"][0]),
        ("CATALOG_KAT_SHA256", oracle["catalog_sha256"]),
    ):
        require(parse_rust_byte_array(source, name) == expected, f"S16 Rust KAT drift: {name}")
    require(
        re.search(r"const\s+CATALOG_MESSAGE_LEN\s*:\s*usize\s*=\s*225_852\s*;", source)
        is not None,
        "S16 Rust catalog message-length KAT drift",
    )

    bridge_root = repo / "crates/bridge"
    for path in bridge_root.rglob("*.rs"):
        text = path.read_text(encoding="utf-8")
        require(FEATURE not in text, f"S16 feature wired into Bridge: {path.relative_to(repo)}")
        require("durability_fault_model" not in text, f"S16 model wired into Bridge: {path.relative_to(repo)}")
    return len(names)


def check_successor(repo: Path, contract: dict[str, Any]) -> None:
    gate = load_json(repo, SUCCESSOR_PATH)
    require_exact(
        set(gate),
        {
            "admission", "authorization_semantics", "boundary", "decision",
            "local_preregistration", "next_evidence_stage", "operational_gap_codes",
            "remaining_gap_codes", "required_production_successor_identity", "schema", "status",
        },
        "successor gate root is not closed",
    )
    require_exact(gate["schema"], "agent_bridge.memory_temporal_successor_admission_gate_s16.v0", "successor schema drift")
    require_exact(gate["status"], STATUS, "successor status drift")
    require_exact(gate["decision"], DECISION, "successor decision drift")
    require_exact(gate["operational_gap_codes"], list(OPERATIONAL_GAPS), "successor operational gaps drift")
    require_exact(gate["remaining_gap_codes"], list(REMAINING_GAPS), "successor remaining gaps drift")
    require_exact(gate["operational_gap_codes"], contract["operational_gap_codes"], "contract/successor operational gaps disagree")
    require_exact(gate["remaining_gap_codes"], contract["remaining_gap_codes"], "contract/successor remaining gaps disagree")
    require_exact(gate["admission"], {"bridge_or_state_store_enabled": False, "currentness_token_issued": False, "owner_approval_receipt": None, "production_authorized": False, "successor_payload_admitted": False, "transport_enabled": False}, "successor admission drift")
    require_exact(gate["authorization_semantics"], {"catalog_row_is_external_durability_observation": False, "exact_lookup_is_owner_authorized_runtime_object_selection": False, "fault_model_pass_is_production_durability_evidence": False, "feature_flag_is_authorization": False, "historical_source_chain_is_admission_capability": False, "modeled_durable_state_is_external_durability": False, "modeled_witness_is_independently_operated_witness": False, "source_revision_is_currentness": False}, "successor authorization semantics drift")
    require_exact(gate["boundary"], {"capture_provenance_runtime_attested": False, "concrete_runtime_bounded_source_adapter_available": False, "currentness_and_consume_atomic": False, "deterministic_synthetic_fault_model_preregistered": True, "external_durable_source_runtime_available": False, "external_durability_observation_count": 0, "owned_lab_durability_observation_count": 0, "owner_pinned_production_source_permit_available": False, "provider_durability_observation_count": 0, "provider_rollback_and_split_brain_proved": False, "runtime_recovered_bytes_available": False, "runtime_s10_delivery_available": False, "side_effects_unlocked": "NONE"}, "successor boundary drift")
    require_exact(gate["local_preregistration"], {"catalog_row_count": ROW_COUNT, "crash_restart_open_data_complete_cuts_modeled": True, "deterministic_catalog_and_stable_order": True, "modeled_durable_and_volatile_state_separated": True, "object_receipt_and_witness_state_separated": True, "rollback_equivocation_split_brain_and_witness_faults_modeled": True, "s15_adapter_logic_and_s14_verifier_unchanged": True, "simulated_and_observed_ledgers_separated": True}, "successor local preregistration drift")
    require_exact(gate["next_evidence_stage"], {"admission_receipt": None, "external_observations_required": True, "identity": "SEPARATELY_AUTHORIZED_PROVIDER_OR_OWNED_LAB_DURABILITY_EVIDENCE_PLAN", "must_keep_simulated_and_observed_ledgers_disjoint": True, "must_map_observations_to_frozen_s16_taxonomy": True, "must_record_real_crash_restart_and_anti_rollback_evidence": True, "owned_lab_execution_authorized": False, "production_or_provider_execution_authorized": False}, "successor next-evidence stage drift")
    require_exact(gate["required_production_successor_identity"], {"admission_receipt": None, "crash_restart_external_durability_evidence": True, "currentness_and_consume_atomicity": True, "external_observed_ledger_nonempty": True, "owner_authorized_exact_object_selection": True, "owner_pinned_production_source_and_authority_permits": True, "provider_and_source_rollback_split_brain_evidence": True, "runtime_capture_attestation_and_signer_custody": True, "runtime_capture_signer_role_separation_evidence": True, "runtime_concrete_bounded_exact_source_adapter": True, "runtime_s10_delivery_and_local_reverification": True}, "successor production identity drift")


def receipt_tsv(repo: Path, oracle: dict[str, Any]) -> str:
    rows: list[tuple[str, str]] = [
        ("schema", "agent_bridge.memory_temporal_recovered_envelope_durability_fault_model_s16_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("feature", FEATURE),
        ("depends_on_feature", S15_FEATURE),
        ("feature_default_reachable", "false"),
        ("policy", POLICY.decode("ascii")),
        ("profile", PROFILE.decode("ascii")),
        ("row_count", str(ROW_COUNT)),
        ("catalog_frame_count", "5644"),
        ("catalog_message_len", str(CATALOG_MESSAGE_LEN)),
        ("catalog_sha256", oracle["catalog_sha256"].hex()),
        ("known_receipt_message_len", str(len(oracle["receipt_message"]))),
        ("known_receipt_sha256", oracle["receipt_sha256"].hex()),
        ("known_witness_message_len", str(len(oracle["witness_message"]))),
        ("known_witness_sha256", oracle["witness_sha256"].hex()),
        ("known_selected_view_message_len", str(len(oracle["selected_view_message"]))),
        ("known_selected_view_sha256", oracle["selected_view_sha256"].hex()),
        ("known_d00_row_message_len", str(len(oracle["row_messages"][0]))),
        ("known_d00_row_sha256", oracle["row_digests"][0].hex()),
        ("s16_nonignored_rust_tests", str(len(TEST_NAMES))),
        ("external_durability_observation_count", "0"),
        ("provider_durability_observation_count", "0"),
        ("owned_lab_durability_observation_count", "0"),
        ("test_only_synthetic_transport_present", "true"),
        ("production_or_provider_concrete_transport_present", "false"),
        ("test_only_transport_is_external_durability_evidence", "false"),
        ("d05_modeled_cut_position_count", "53"),
        ("d05_modeled_row_count", "106"),
        ("d05_test_only_injected_failure_attempt_count", "50"),
        ("d05_test_only_fresh_instance_reread_count", "50"),
        ("d05_model_only_cut_position_count", "3"),
        ("d05_model_only_row_count", "6"),
        ("os_process_crash_execution_count", "0"),
        ("external_durable_restart_execution_count", "0"),
        ("currentness_or_admission_issued", "false"),
        ("side_effects_unlocked", "NONE"),
        ("contract_sha256", artifact_sha256(repo, CONTRACT_PATH)),
        ("successor_gate_sha256", artifact_sha256(repo, SUCCESSOR_PATH)),
    ]
    for case_id, count in FAMILY_COUNTS.items():
        rows.append((f"rows_{case_id}", str(count)))
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--contract-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        record = independent_record(repo)
        oracle = catalog_oracle(record)
        contract = check_contract(repo, oracle)
        if not args.contract_only:
            check_glue(repo)
            check_successor(repo, contract)
            check_rust(repo, oracle)
        sys.stdout.write(receipt_tsv(repo, oracle))
    except (CheckFailure, OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        print(f"S16_CHECK_FAILED\t{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
