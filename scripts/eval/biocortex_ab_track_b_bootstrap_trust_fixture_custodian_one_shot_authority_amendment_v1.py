#!/usr/bin/env python3
"""Pure review surface for the one-shot bootstrap-trust fixture amendment.

This module records no consumption event and performs no generation.  It only
reviews a bounded owner-decision record and emits a deterministic public receipt.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.biocortex_ab_track_b.bootstrap_trust_fixture_custodian_one_shot_authority_amendment.v1"
DECISION = "AUTHORIZE_EXACT_ONE_SHOT_OFFLINE_NONPRODUCTION_FIXTURE_CUSTODIAN_PUBLIC_ONLY_BOOTSTRAP_TRUST_VECTOR_GENERATION_AMENDMENT"
PENDING_STATE = "AUTHORIZED_PENDING_INTEGRATED_FULL_GATE"
NEXT_UNIT = "BOOTSTRAP_TRUST_PUBLIC_ONLY_VECTOR_SUPPLY_AND_GENERATION_PROVENANCE_RECEIPT_FREEZE"
GENERIC_ROLE = "SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY"
EXPECTED_RECORD_RAW_SHA256 = "d913fa29cdef6d9ebf7ffa3a07c5cd687eaf26cd57611d255776016b8683076f"
EXPECTED_RECORD_CANONICAL_SHA256 = "ee0c4ab2f12d3c540a72c2e8af37e4d9705ac4861c4368834e2bdb518356f21b"
MAX_RECORD_BYTES = 65536
MAX_DEPTH = 32
MAX_NODES = 4096
MAX_OBJECT_MEMBERS = 256
MAX_ARRAY_ITEMS = 64


class AmendmentRejected(ValueError):
    """Fail-closed decision-review rejection."""


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _bounded_walk(value: Any, depth: int = 0, counter: list[int] | None = None) -> None:
    if counter is None:
        counter = [0]
    if depth > MAX_DEPTH:
        raise AmendmentRejected("JSON_DEPTH_LIMIT")
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise AmendmentRejected("JSON_NODE_LIMIT")
    if isinstance(value, dict):
        if len(value) > MAX_OBJECT_MEMBERS:
            raise AmendmentRejected("JSON_OBJECT_MEMBER_LIMIT")
        for key, child in value.items():
            if not isinstance(key, str):
                raise AmendmentRejected("NONSTRING_OBJECT_KEY")
            _bounded_walk(child, depth + 1, counter)
    elif isinstance(value, list):
        if len(value) > MAX_ARRAY_ITEMS:
            raise AmendmentRejected("JSON_ARRAY_ITEM_LIMIT")
        for child in value:
            _bounded_walk(child, depth + 1, counter)
    elif value is not None and not isinstance(value, (str, int, bool)):
        raise AmendmentRejected("UNSUPPORTED_JSON_SCALAR")


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise AmendmentRejected(reason)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AmendmentRejected("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _validate_tracks(tracks: Any, role_map: Any) -> None:
    expected = [
        {
            "track_id": "MANAGED_SPANNER_CLOUD_KMS",
            "vector_set_id": "KAT_MANAGED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1",
            "domain_ascii": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_MANAGED_KAT_SIGNATURE_V1",
            "domain_bytes": 79,
            "canonical_frame_bytes": 659,
            "canonical_frame_sha256": "e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295",
            "constructed_message_bytes": 754,
            "constructed_message_sha256": "a52aa400add05bb7b545c9eddbf1f48e55befd393f07c5c6ba6baaefd4f5343b",
            "role": "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER",
        },
        {
            "track_id": "SELF_HOSTED_ETCD_OPENBAO",
            "vector_set_id": "KAT_SELF_HOSTED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1",
            "domain_ascii": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_SELF_HOSTED_KAT_SIGNATURE_V1",
            "domain_bytes": 83,
            "canonical_frame_bytes": 658,
            "canonical_frame_sha256": "da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e",
            "constructed_message_bytes": 757,
            "constructed_message_sha256": "2eb3584afe6c8f18281224785ec083e531da37eed71524f2eedbf3a8225055ac",
            "role": "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER",
        },
    ]
    _require(isinstance(tracks, list) and len(tracks) == 2, "TRACK_CARDINALITY")
    _require(isinstance(role_map, dict), "TRACK_ROLE_MAP")
    for actual, frozen in zip(tracks, expected, strict=True):
        _require(isinstance(actual, dict), "TRACK_OBJECT")
        for key, value in frozen.items():
            if key == "role":
                _require(role_map.get(frozen["track_id"]) == value, "TRACK_ROLE_MAPPING")
            else:
                _require(actual.get(key) == value, "TRACK_" + key.upper())
        _require(actual.get("revoked_leaf_key_generation_authorized") is False, "REVOKED_LEAF_KEYGEN")
def review_amendment(record_bytes: bytes) -> dict[str, str]:
    _require(isinstance(record_bytes, bytes), "INPUT_TYPE")
    _require(0 < len(record_bytes) <= MAX_RECORD_BYTES, "INPUT_SIZE")
    try:
        record = json.loads(record_bytes.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AmendmentRejected("INVALID_JSON") from exc
    _require(isinstance(record, dict), "TOP_LEVEL_OBJECT")
    _bounded_walk(record)
    _require(hashlib.sha256(record_bytes).hexdigest() == EXPECTED_RECORD_RAW_SHA256, "RECORD_RAW_ORACLE")
    _require(_canonical_sha256(record) == EXPECTED_RECORD_CANONICAL_SHA256, "RECORD_CANONICAL_ORACLE")
    expected_top = {
        "boundary", "date", "decision", "decision_provenance",
        "fixture_custodian_authority", "next_unit", "nonclaims",
        "output_contract", "predecessor", "rollback", "schema",
        "schema_version", "semantic_amendment", "separation_of_duties",
        "state_machine", "status", "synthetic_vector_contract",
    }
    _require(set(record) == expected_top, "TOP_LEVEL_KEYS")
    _require(record["schema"] == SCHEMA and type(record["schema_version"]) is int and record["schema_version"] == 1, "SCHEMA")
    _require(record["date"] == "2026-07-17", "DATE")
    _require(record["decision"] == DECISION, "DECISION")
    _require(record["next_unit"] == NEXT_UNIT, "NEXT_UNIT")
    provenance = record["decision_provenance"]
    _require(provenance.get("directive_observed_in_owner_session") is True, "OWNER_DIRECTIVE")
    _require(provenance.get("explicit_fixture_generation_authority_observed") is True, "OWNER_AUTHORITY")
    _require(provenance.get("explicit_production_authority_observed") is False, "PRODUCTION_AUTHORITY")

    predecessor = record["predecessor"]
    _require(predecessor.get("authority_integration_commit") == "a18f0af7b4cbaa971143c71080a2b49786a7f7a3", "PREDECESSOR_COMMIT")
    _require(predecessor.get("authority_integration_tree") == "8afca41122ee482493afec9c2c4aa32d600c175e", "PREDECESSOR_TREE")
    _require(predecessor.get("authority_effective") is True, "PREDECESSOR_EFFECTIVE")
    _require(predecessor.get("authority_single_use_consumed") is False, "PREDECESSOR_CONSUMPTION")
    _require(len(predecessor.get("authority_artifact_raw_sha256", {})) == 7, "PREDECESSOR_ARTIFACT_COUNT")

    semantic = record["semantic_amendment"]
    chain = semantic["trust_chain_semantics"]
    _require(chain.get("exact_chain_entry_count") == 3, "CHAIN_COUNT")
    _require(chain.get("certificate_link_signature_count") == 0, "CHAIN_LINK_SIGNATURE_COUNT")
    _require(chain.get("cryptographic_verification_count_on_positive_path") == 1, "VERIFY_COUNT")
    _require(chain.get("pki_path_validation_claimed") is False, "PKI_CLAIM")
    role = semantic["declared_role_mapping"]
    _require(role.get("generic_declared_role_class") == GENERIC_ROLE, "GENERIC_ROLE")
    _require(role.get("mapping_is_role_scope_authorization") is False, "ROLE_AUTHORIZATION")

    authority = record["fixture_custodian_authority"]
    exact_authority = {
        "authority_effective_only_after_integrated_full_gate": True,
        "authority_single_use_consumed": False,
        "consumption_event": "FIXTURE_CUSTODIAN_PROCESS_STARTED_BEFORE_RANDOMNESS_OR_KEYGEN",
        "exact_keypair_generation_count": 6,
        "exact_signature_generation_count": 2,
        "revoked_leaf_keypair_generation_count": 0,
        "revoked_leaf_signature_generation_count": 0,
        "network_allowed": False,
        "credential_authority": False,
        "provider_authority": False,
        "production_root_or_key_material_allowed": False,
        "retry_authorized": False,
        "effective_external_paid_spend_cap": 0,
        "generator_source_or_executable_may_be_committed": False,
        "ephemeral_generator_executable_mode": "0700",
        "local_os_csprng_allowed": True,
        "private_memory_zeroization_proved": False,
        "swap_exclusion_proved": False,
        "max_parallel_workers": 1,
        "max_private_scratch_bytes": 67108864,
        "scratch_directory_mode": "0700",
        "scratch_non_executable_file_mode": "0600",
    }
    for key, value in exact_authority.items():
        actual = authority.get(key)
        _require(type(actual) is type(value) and actual == value, "AUTHORITY_" + key.upper())
    dependency = authority.get("allowed_dependency")
    _require(dependency == {
        "cargo_net_offline_required": True,
        "crate": "ring",
        "repository_cargo_files_may_change": False,
        "version": "0.17.14",
    }, "DEPENDENCY")

    output = record["output_contract"]
    _require(type(output.get("public_key_count")) is int and output.get("public_key_count") == 6, "OUTPUT_PUBLIC_KEYS")
    _require(type(output.get("signature_count")) is int and output.get("signature_count") == 2, "OUTPUT_SIGNATURES")
    _require(type(output.get("vector_bundle_track_count")) is int and output.get("vector_bundle_track_count") == 2, "OUTPUT_TRACKS")
    receipt_fields = output.get("generation_receipt_required_fields", [])
    _require(isinstance(receipt_fields, list) and len(receipt_fields) == 24 and len(set(receipt_fields)) == 24, "RECEIPT_FIELDS")
    _require(output.get("generation_receipt_serialization") == "SORTED_KEYS_COMPACT_UTF8_SINGLE_TRAILING_LF", "RECEIPT_SERIALIZATION")
    serialization = output.get("vector_bundle_serialization")
    _require(isinstance(serialization, dict), "VECTOR_SERIALIZATION")
    _require(serialization.get("canonical_json_profile") == "SORTED_KEYS_COMPACT_UTF8_SINGLE_TRAILING_LF", "VECTOR_CANONICAL_JSON")
    _require(serialization.get("public_key_hex_pattern") == "^[0-9a-f]{64}$", "PUBLIC_KEY_HEX")
    _require(serialization.get("signature_hex_pattern") == "^[0-9a-f]{128}$", "SIGNATURE_HEX")
    separation = record["separation_of_duties"]
    _require(separation.get("minimum_distinct_semantic_actor_count") == 4, "ACTOR_COUNT")
    _require(separation.get("pairwise_distinct_required") is True, "ACTOR_DISTINCTNESS")

    _validate_tracks(record["synthetic_vector_contract"].get("tracks"), role.get("track_role_map"))
    vector = record["synthetic_vector_contract"]
    _require(vector.get("algorithm") == "ED25519", "ALGORITHM")
    _require(vector.get("signature_scheme") == "ED25519_PURE_RFC8032_NO_CONTEXT_NO_PREHASH", "SIGNATURE_SCHEME")

    state = record["state_machine"]
    _require(state.get("current_state") == PENDING_STATE, "STATE")
    _require(state.get("states") == [
        "UNRECORDED_NO_AUTHORITY",
        "AUTHORIZED_PENDING_INTEGRATED_FULL_GATE",
        "AUTHORIZED_ONE_SHOT_FIXTURE_CUSTODIAN_PENDING_PROCESS_START",
        "CONSUMED_PROCESS_STARTED_OUTPUT_PENDING",
        "CONSUMED_SCOPE_COMPLETE_PUBLIC_OUTPUT_AVAILABLE",
        "CONSUMED_FAILED_NO_RETRY_REQUIRES_NEW_OWNER_DECISION",
        "INVALIDATED_REQUIRES_NEW_DECISION",
    ], "STATE_CATALOG")
    events = [item.get("event") for item in state.get("transitions", []) if isinstance(item, dict)]
    _require(events.count("FIXTURE_CUSTODIAN_PROCESS_STARTED_BEFORE_RANDOMNESS_OR_KEYGEN") == 1, "CONSUMPTION_TRANSITION")
    _require("PROCESS_FAILURE_OR_CONTRACT_DRIFT_AFTER_MAIN_ENTRY" in events, "FAILURE_TRANSITION")
    _require(record["nonclaims"].get("global_single_use_proved") is False, "GLOBAL_SINGLE_USE_CLAIM")
    _require(record["boundary"].get("bootstrap_trust_verifier_implementation_authority_single_use_consumed") is False, "IMPLEMENTATION_CONSUMPTION")

    contract_sections = {
        "authority": authority,
        "semantic_amendment": semantic,
        "output_contract": output,
        "separation_of_duties": separation,
        "synthetic_vector_contract": vector,
    }
    return {
        "schema": SCHEMA,
        "decision": DECISION,
        "owner_authorization_explicit": "true",
        "predecessor_authority_effective": "true",
        "predecessor_implementation_authority_single_use_consumed": "false",
        "structural_policy_chain_entry_count": "3",
        "certificate_link_signature_count": "0",
        "positive_path_active_leaf_signature_verification_count": "1",
        "generic_role_mapping_frozen": "true",
        "role_scope_authorization_implemented": "false",
        "fixture_generation_authority_state": PENDING_STATE,
        "fixture_generation_authority_single_use_consumed": "false",
        "generation_consumption_event": "FIXTURE_CUSTODIAN_PROCESS_STARTED_BEFORE_RANDOMNESS_OR_KEYGEN",
        "keypair_generation_count_authorized": "6",
        "signature_generation_count_authorized": "2",
        "retry_authorized": "false",
        "network_provider_credential_authority": "false",
        "production_runtime_authority": "false",
        "minimum_distinct_semantic_actor_count": "4",
        "record_sha256": hashlib.sha256(record_bytes).hexdigest(),
        "contract_sha256": _canonical_sha256(contract_sections),
        "next_unit": NEXT_UNIT,
        "status": "PASS",
    }


def _render(receipt: dict[str, str]) -> str:
    return "".join(f"{key}\t{value}\n" for key, value in receipt.items())


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} OWNER_DECISION.json", file=sys.stderr)
        return 2
    try:
        receipt = review_amendment(Path(argv[1]).read_bytes())
    except (OSError, AmendmentRejected) as exc:
        print(f"amendment review failed: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(_render(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
