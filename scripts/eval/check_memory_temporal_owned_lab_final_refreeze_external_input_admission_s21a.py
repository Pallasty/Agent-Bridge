#!/usr/bin/env python3
"""Independent S21A closed-world refreeze and external-input checker.

This checker deliberately treats every repository fixture as a synthetic public
KAT.  Candidate-carried match booleans, keys, digests, registration state, or
checkpoint assertions never become an independent trust source.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

sys.dont_write_bytecode = True


BASELINE_COMMIT = "33c2c4df78ef302fd0538986b95fa40a3711ba86"
BASELINE_TREE = "6f92c687b61e1433e693ca6cd1bc6390dda97f29"
S20B_SOURCE_COMMIT = "a1948daaf466563358fcbf054b2bebef8e966777"
S20B_SOURCE_TREE = "eca0de065221621fcc70941adaefac1f4315bd3e"
S20B_INTEGRATED_ARCHIVE_SHA256 = (
    "cde7d7e71591265cc26f57e378448fa066b0083ef4b32cbebd3ec8ca27a8b43e"
)
S20B_CATALOG_SHA256 = "44d9f48318e221d961819f9f189c2b355a4fce42351844d7cd5b4a84e72b1f0d"
S20B_VALIDATOR_RULESET_SHA256 = (
    "84b374eaadc65610fbfc660b5fe69f840229a03c39b196414b7300ec045b705d"
)
# This is only the SHA-256 fingerprint of the prohibited RFC 8032 test seed;
# the private seed bytes themselves must not be reintroduced here or in Rust.
FORBIDDEN_RFC8032_TEST_SEED_SHA256 = (
    "644d50ab64864c20a12b3c4656d46b4a48f69ef7c47ecdc8415cd28316b22ef5"
)
STATUS = "S21A_NON_LIVE_REFREEZE_AND_EXTERNAL_INPUT_ADMISSION_TOOLING_COMPLETE"
DECISION = (
    "S21B_BLOCKED_PENDING_POST_INTEGRATION_UNSIGNED_FINAL_SUBJECT_NEW_OWNER_SIGNATURE_"
    "INSTALLED_TRUST_ANCHOR_AND_INDEPENDENT_LIVE_INPUTS"
)
MODE = "PRIVATE_DEFAULT_OFF_SYNTHETIC_NON_LIVE_REFREEZE_AND_ADMISSION_VALIDATION_ONLY"
FEATURE = "temporal-evidence-s21a-owned-lab-final-refreeze-admission-synthetic"
CANONICALIZATION = (
    "AB_RESTRICTED_CANONICAL_JSON_S21A_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT"
)
FRAMING = (
    "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_CANONICAL_PAYLOAD_LENGTH_CANONICAL_PAYLOAD"
)
SIGNED_PAYLOAD_DOMAIN = (
    "agent-bridge/biocortex/owned-lab/s21a/owner-authorization-signed-payload/v1"
)
AUTHORIZATION_ID_DOMAIN = (
    "agent-bridge/biocortex/owned-lab/s21a/owner-authorization-id/v1"
)
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
MAX_CANONICAL_JSON_BYTES = 64 * 1024
MAX_CANONICAL_JSON_DEPTH = 16

PREFIX = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-"
CARGO_PATH = "crates/store/Cargo.toml"
S20_RUST_PATH = (
    "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/"
    "recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/"
    "durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner/"
    "trusted_controller_orchestration.rs"
)
S21A_RUST_PATH = S20_RUST_PATH[:-3] + "/final_refreeze_admission.rs"
DESIGN_PATH = (
    "docs/design/MEMORY_TEMPORAL_OWNED_LAB_FINAL_REFREEZE_EXTERNAL_INPUT_ADMISSION_"
    "S21A_2026_07_18.md"
)
CONTRACT_PATH = PREFIX + "final-refreeze-external-input-admission-contract-s21a-v0.json"
STATUS_PATH = PREFIX + "final-refreeze-external-input-admission-status-s21a-v0.json"
SUCCESSOR_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s21a-v0.json"
REPORT_PATH = (
    "docs/reports/goal-c-u/2026-07-18-biocortex-ab-track-b-owned-lab-"
    "final-refreeze-external-input-admission-s21a.md"
)
CHECKER_PATH = (
    "scripts/eval/check_memory_temporal_owned_lab_final_refreeze_external_input_"
    "admission_s21a.py"
)
EXPECTED_PATH = (
    "scripts/eval/fixtures/memory_temporal_owned_lab_final_refreeze_external_input_"
    "admission_s21a.expected.v0.tsv"
)
GATE_PATH = (
    "scripts/check-memory-temporal-owned-lab-final-refreeze-external-input-"
    "admission-s21a.sh"
)
S20B_CHECKER_PATH = (
    "scripts/eval/check_memory_temporal_owned_lab_rich_packet_schema_replacements_s20b.py"
)
S20B_GATE_PATH = "scripts/check-memory-temporal-owned-lab-rich-packet-schema-replacements-s20b.sh"
S20B_REPORT_PATH = (
    "docs/reports/goal-c-u/2026-07-18-biocortex-ab-track-b-owned-lab-"
    "rich-packet-schema-replacements-s20b.md"
)
S20B_SUCCESSOR_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s20b-v0.json"


@dataclass(frozen=True)
class PacketSpec:
    slug: str
    schema_id: str
    packet_kind: str
    state_key: str
    state_value: str
    self_hash_field: str
    domain: str

    @property
    def schema_path(self) -> str:
        return PREFIX + self.slug + "-schema-s21a-v0.json"

    @property
    def fixture_path(self) -> str:
        return PREFIX + self.slug + "-synthetic-s21a-v0.json"


PACKETS = (
    PacketSpec(
        "final-refreeze-subject",
        "agent_bridge.memory_temporal_owned_lab_final_refreeze_subject_s21a.v0",
        "S21A_FINAL_REFREEZE_SUBJECT",
        "subject_state",
        "SYNTHETIC_KAT_NON_LIVE_UNSIGNED_NOT_FINAL",
        "subject_sha256",
        "agent-bridge/biocortex/owned-lab/s21a/final-refreeze-subject/v1",
    ),
    PacketSpec(
        "owner-trust-anchor",
        "agent_bridge.memory_temporal_owned_lab_owner_trust_anchor_s21a.v0",
        "S21A_OWNER_TRUST_ANCHOR",
        "anchor_state",
        "SYNTHETIC_PUBLIC_KAT_NOT_INSTALLED",
        "anchor_document_sha256",
        "agent-bridge/biocortex/owned-lab/s21a/owner-trust-anchor-document/v1",
    ),
    PacketSpec(
        "owner-authorization-envelope",
        "agent_bridge.memory_temporal_owned_lab_owner_authorization_envelope_s21a.v0",
        "S21A_OWNER_AUTHORIZATION_ENVELOPE",
        "envelope_state",
        "SYNTHETIC_KAT_NON_LIVE",
        "owner_envelope_sha256",
        "agent-bridge/biocortex/owned-lab/s21a/owner-authorization-envelope/v1",
    ),
    PacketSpec(
        "external-input-admission",
        "agent_bridge.memory_temporal_owned_lab_external_input_admission_s21a.v0",
        "S21A_EXTERNAL_INPUT_ADMISSION_RESULT",
        "admission_state",
        "SYNTHETIC_KAT_BLOCKED_NON_LIVE",
        "admission_packet_sha256",
        "agent-bridge/biocortex/owned-lab/s21a/external-input-admission/v1",
    ),
)

ARTIFACT_ROWS = (
    ("cargo_manifest_sha256", CARGO_PATH),
    ("s20b_parent_rust_sha256", S20_RUST_PATH),
    ("s21a_rust_sha256", S21A_RUST_PATH),
    ("design_sha256", DESIGN_PATH),
    ("contract_sha256", CONTRACT_PATH),
    ("status_fixture_sha256", STATUS_PATH),
    ("successor_gate_sha256", SUCCESSOR_PATH),
    ("checker_sha256", CHECKER_PATH),
    ("source_gate_sha256", GATE_PATH),
)


class CheckFailure(RuntimeError):
    """Expected validation failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_path(repo: Path, relative: str) -> Path:
    path = repo / relative
    require(path.is_file(), f"missing regular artifact: {relative}")
    require(not path.is_symlink(), f"symlink artifact forbidden: {relative}")
    require(path.resolve() == path, f"non-canonical artifact path: {relative}")
    return path


def read_bytes(
    repo: Path, relative: str, overrides: Mapping[str, bytes] | None = None
) -> bytes:
    if overrides and relative in overrides:
        return overrides[relative]
    path = canonical_path(repo, relative)
    size = path.stat().st_size
    require(0 < size <= MAX_ARTIFACT_BYTES, f"artifact size outside bound: {relative}")
    raw = path.read_bytes()
    require(len(raw) == size, f"artifact changed while reading: {relative}")
    return raw


def read_text(
    repo: Path, relative: str, overrides: Mapping[str, bytes] | None = None
) -> str:
    raw = read_bytes(repo, relative, overrides)
    require(not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {relative}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckFailure(f"non-UTF-8 artifact: {relative}") from exc


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in output, f"duplicate JSON key: {key}")
        output[key] = value
    return output


def reject_float(value: str) -> None:
    raise CheckFailure(f"floating-point JSON forbidden: {value}")


def reject_constant(value: str) -> None:
    raise CheckFailure(f"non-finite JSON forbidden: {value}")


def validate_restricted_json_value(value: Any, depth: int = 0) -> None:
    require(depth <= MAX_CANONICAL_JSON_DEPTH, "restricted JSON nesting depth exceeded")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        require(0 <= value <= 2**64 - 1, "nonnegative u64 integer required")
        return
    if isinstance(value, str):
        require(value.isascii(), "non-ASCII string value forbidden")
        return
    if isinstance(value, list):
        for child in value:
            validate_restricted_json_value(child, depth + 1)
        return
    require(isinstance(value, dict), "unsupported restricted JSON value")
    for key, child in value.items():
        require(isinstance(key, str) and key.isascii(), "non-ASCII object key forbidden")
        validate_restricted_json_value(child, depth + 1)


def parse_json(raw: bytes, label: str) -> dict[str, Any]:
    require(len(raw) <= MAX_CANONICAL_JSON_BYTES,
            f"restricted JSON exceeds 64 KiB ({label})")
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=reject_duplicates,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, CheckFailure) as exc:
        raise CheckFailure(f"invalid restricted JSON ({label}): {exc}") from exc
    require(isinstance(value, dict), f"JSON root must be an object: {label}")
    validate_restricted_json_value(value)
    return value


def load_json(
    repo: Path, relative: str, overrides: Mapping[str, bytes] | None = None
) -> tuple[bytes, dict[str, Any]]:
    raw = read_bytes(repo, relative, overrides)
    return raw, parse_json(raw, relative)


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    except (TypeError, UnicodeEncodeError) as exc:
        raise CheckFailure(f"value is not restricted canonical JSON: {exc}") from exc


def require_canonical_repository_json(raw: bytes, value: dict[str, Any], label: str) -> None:
    require(raw.endswith(b"\n") and not raw.endswith(b"\n\n"),
            f"repository JSON terminal LF drift: {label}")
    require(b"\n" not in raw[:-1], f"repository JSON is not compact: {label}")
    require(raw == canonical_bytes(value) + b"\n",
            f"repository JSON is not restricted canonical JSON: {label}")


def framed_digest(domain: str, payload: bytes) -> str:
    domain_raw = domain.encode("ascii")
    return sha256(
        len(domain_raw).to_bytes(4, "big")
        + domain_raw
        + len(payload).to_bytes(8, "big")
        + payload
    )


def framed_raw_digest_sequence(domain: str, digests: tuple[str, ...]) -> str:
    domain_raw = domain.encode("ascii")
    message = len(domain_raw).to_bytes(4, "big") + domain_raw
    for digest in digests:
        require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
                "raw digest sequence contains invalid digest")
        raw = bytes.fromhex(digest)
        message += len(raw).to_bytes(8, "big") + raw
    return sha256(message)


def validate_schema_node(value: Any, label: str) -> None:
    if isinstance(value, list):
        for index, child in enumerate(value):
            validate_schema_node(child, f"{label}/{index}")
        return
    if not isinstance(value, dict):
        return
    ref = value.get("$ref")
    if ref is not None:
        require(isinstance(ref, str) and ref.startswith("#/"), f"external schema ref: {label}")
    if value.get("type") == "object":
        require(value.get("additionalProperties") is False, f"open object schema: {label}")
        properties = value.get("properties")
        required = value.get("required")
        require(isinstance(properties, dict), f"object schema lacks properties: {label}")
        require(isinstance(required, list), f"object schema lacks required list: {label}")
        require(len(required) == len(set(required)), f"duplicate required key: {label}")
        require(set(required) == set(properties), f"required/properties mismatch: {label}")
    for key, child in value.items():
        validate_schema_node(child, f"{label}/{key}")


def all_named_values(value: Any, key_name: str) -> list[Any]:
    matches: list[Any] = []
    if isinstance(value, list):
        for child in value:
            matches.extend(all_named_values(child, key_name))
    elif isinstance(value, dict):
        for key, child in value.items():
            if key == key_name:
                matches.append(child)
            matches.extend(all_named_values(child, key_name))
    return matches


def require_named_value(
    value: Any, key: str, expected: Any, label: str, *, minimum_count: int = 1
) -> None:
    matches = all_named_values(value, key)
    require(len(matches) >= minimum_count, f"required semantic field absent: {label}.{key}")
    require(all(item == expected for item in matches), f"semantic field drift: {label}.{key}")


def all_fail_closed_fields(value: Any, label: str) -> None:
    if isinstance(value, list):
        for index, child in enumerate(value):
            all_fail_closed_fields(child, f"{label}[{index}]")
        return
    if not isinstance(value, dict):
        return
    false_fields = {
        "automatic_retry_allowed",
        "automatic_or_implicit_retry_allowed",
        "retry_or_implicit_rerun_allowed",
        "runner_created_registration_allowed",
        "registration_created_by_runner",
        "registration_may_be_created_by_runner",
        "checkpoint_same_failure_domain_allowed",
        "checkpoint_candidate_self_assertion_authoritative",
        "self_asserted_key_is_owner_authentication",
        "self_asserted_signature_valid",
        "public_key_carried_by_envelope",
        "anchor_installed",
        "synthetic_anchor_installed",
        "out_of_band_installed",
        "out_of_band_pinned",
        "installed_out_of_band",
        "pinned_by_independent_caller",
        "anchor_installed_out_of_band",
        "anchor_pinned_by_independent_caller",
        "candidate_carried_key_used",
        "candidate_carried_key_is_trusted",
        "candidate_supplied_expected_digest_used",
        "private_key_present_in_repository",
        "legacy_s19_key_reuse_allowed",
        "legacy_s19_signature_or_envelope_reuse_allowed",
        "existing_s19_signature_authorizes_s21a",
        "old_s19_signature_authorizes_s21a",
        "generated_outside_repository_after_s21a_integration",
        "signature_verified",
        "owner_authority_established",
        "checkpoint_present",
        "checkpoint_validated",
        "checkpoint_current",
        "checkpoint_independent",
        "registration_present",
        "registration_validated",
        "registration_current",
        "registration_independent",
        "observer_present",
        "observer_validated",
        "observer_current",
        "observer_independent",
        "runner_present",
        "runner_validated",
        "runner_current",
        "runner_independent",
        "created_by_runner",
        "same_failure_domain_as_database",
        "new_owner_signature_valid",
        "trust_anchor_installed_and_pinned",
        "all_external_inputs_validated",
        "exact_canary_inputs_present_and_bound",
        "exact_environment_present_and_bound",
        "fresh_observer_present_and_bound",
        "real_runner_present_and_bound",
        "stop_and_revocation_fresh_and_exact",
        "exact_s21a_commit_tree_and_build_bound",
        "final_post_integration_subject_validated",
        "registered_by_external_control_plane",
        "live_execution_authorized",
        "execution_start_permitted",
        "single_use_execution_capability_issued",
        "provider_or_production_authority",
        "provider_access_allowed",
        "production_access_allowed",
        "credential_access_allowed",
        "network_allowed",
        "paid_resource_allowed",
        "may_execute_live",
        "live_execution_may_begin",
        "future_s21b_preapproved",
        "schema_conformance_alone_authorizes_execution",
        "owner_envelope_is_bearer_capability",
        "synthetic_envelope_is_owner_authority",
        "admission_packet_is_owner_authority",
        "subject_is_owner_authority",
    }
    for key, child in value.items():
        if key == "side_effects_unlocked":
            require(child == "NONE", f"side effects unlocked: {label}.{key}")
        elif (
            (
                key.startswith("real_")
                and key
                != "real_anchor_repository_public_kat_key_id_and_material_denylist_enforced"
                and "current_missing_external_inputs" not in label
            )
            or key.startswith("actual_live_")
            or key in false_fields
        ):
            require(child is False, f"fail-closed field became true: {label}.{key}")
        all_fail_closed_fields(child, f"{label}.{key}")


NULLABLE_SYNTHETIC_DIGEST_PATHS = {
    "checkpoint_input.previous_checkpoint_sha256",
    "checkpoint_input.previous_checkpoint_head_sha256",
    "external_registration.claimed_run_id_sha256",
    "owner_identity.owner_identity_verification_receipt_sha256",
    "trust_policy.installation_receipt_sha256",
}


def validate_nonzero_digest_fields(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, list):
        for index, child in enumerate(value):
            validate_nonzero_digest_fields(child, path + (str(index),))
        return
    if not isinstance(value, dict):
        return
    for key, child in value.items():
        child_path = path + (key,)
        if key.endswith("sha256"):
            dotted = ".".join(child_path)
            if child is None:
                require(dotted in NULLABLE_SYNTHETIC_DIGEST_PATHS,
                        f"unexpected null SHA-256 field: {dotted}")
            else:
                require(
                    isinstance(child, str)
                    and re.fullmatch(r"[0-9a-f]{64}", child) is not None
                    and child != "0" * 64,
                    f"invalid or zero SHA-256 field: {dotted}",
                )
        validate_nonzero_digest_fields(child, child_path)


def verify_hashing_contract(fixture: dict[str, Any], spec: PacketSpec) -> str:
    contract = fixture.get("hashing_contract")
    require(isinstance(contract, dict), f"hashing contract absent: {spec.fixture_path}")
    expected = {
        "canonicalization": CANONICALIZATION,
        "digest_domain": spec.domain,
        "digest_framing": FRAMING,
        "hash_algorithm": "SHA-256",
        "self_hash_field": spec.self_hash_field,
        "self_hash_field_excluded": True,
        "repository_framing_lf_excluded": True,
        "candidate_reported_matches_authoritative": False,
        "cross_field_semantic_validation_required": True,
    }
    for key, wanted in expected.items():
        require(contract.get(key) == wanted, f"hashing contract drift: {spec.slug}.{key}")
    scope = contract.get("hash_scope")
    require(
        isinstance(scope, str)
        and "EXCEPT" in scope
        and spec.self_hash_field.upper() in scope,
        f"non-explicit self-hash scope: {spec.slug}",
    )
    declared = fixture.get(spec.self_hash_field)
    require(
        isinstance(declared, str) and re.fullmatch(r"[0-9a-f]{64}", declared) is not None,
        f"invalid declared self digest: {spec.fixture_path}",
    )
    payload = copy.deepcopy(fixture)
    require(payload.pop(spec.self_hash_field, None) == declared, "self digest removal mismatch")
    computed = framed_digest(spec.domain, canonical_bytes(payload))
    require(computed == declared, f"self digest mismatch: {spec.fixture_path}")
    return computed


def reseal_fixture(fixture: dict[str, Any], spec: PacketSpec) -> bytes:
    value = copy.deepcopy(fixture)
    value.pop(spec.self_hash_field, None)
    value[spec.self_hash_field] = framed_digest(spec.domain, canonical_bytes(value))
    return canonical_bytes(value) + b"\n"


def validate_packet_semantics(spec: PacketSpec, fixture: dict[str, Any]) -> None:
    require(fixture.get("schema") == spec.schema_id, f"fixture schema drift: {spec.slug}")
    require(fixture.get("packet_kind") == spec.packet_kind, f"packet kind drift: {spec.slug}")
    require(fixture.get(spec.state_key) == spec.state_value, f"packet state drift: {spec.slug}")
    require(fixture.get("canonicalization") == CANONICALIZATION, "canonicalization drift")
    require(fixture.get("test_only") is True, f"fixture is not test-only: {spec.slug}")
    require(fixture.get("synthetic") is True, f"fixture is not synthetic: {spec.slug}")
    all_fail_closed_fields(fixture, spec.fixture_path)
    validate_nonzero_digest_fields(fixture)
    audience_matches = all_named_values(fixture, "audience")
    if audience_matches:
        require(
            all(
                value
                == "agent-bridge/biocortex/owned-lab/s21a/final-refreeze-owner-review/v1"
                for value in audience_matches
            ),
            f"semantic field drift: {spec.slug}.audience",
        )
    if spec.slug == "final-refreeze-subject":
        require_named_value(
            fixture,
            "generated_outside_repository_after_s21a_integration",
            False,
            spec.slug,
        )
        for key in (
            "s21a_source_commit",
            "s21a_source_tree",
            "s21a_integration_commit",
            "s21a_integration_tree",
        ):
            require_named_value(fixture, key, None, spec.slug)
    elif spec.slug == "owner-trust-anchor":
        require_named_value(fixture, "algorithm", "Ed25519", spec.slug)
        require_named_value(
            fixture,
            "public_key_hex",
            "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
            spec.slug,
        )
        require_named_value(fixture, "key_id", "s21a-synthetic-public-kat-v1", spec.slug)
        require_named_value(fixture, "key_version", 1, spec.slug)
        require_named_value(fixture, "installed_out_of_band", False, spec.slug)
        require_named_value(fixture, "pinned_by_independent_caller", False, spec.slug)
        require_named_value(fixture, "candidate_carried_key_is_trusted", False, spec.slug)
        require_named_value(fixture, "public_kat_is_installed_anchor", False, spec.slug)
        require_named_value(fixture, "identity_verified_out_of_band", False, spec.slug)
        require_named_value(
            fixture, "owner_identity_verification_receipt_sha256", None, spec.slug
        )
        require_named_value(fixture, "legacy_s19_key_reuse_allowed", False, spec.slug)
    elif spec.slug == "owner-authorization-envelope":
        require_named_value(fixture, "algorithm", "Ed25519", spec.slug)
        require_named_value(
            fixture,
            "signature_domain",
            "agent-bridge/biocortex/owned-lab/s21a/owner-authorization-signature/v1",
            spec.slug,
        )
        require_named_value(fixture, "signed_payload_digest_domain", SIGNED_PAYLOAD_DOMAIN,
                            spec.slug)
        require_named_value(fixture, "signed_payload_digest_framing", FRAMING, spec.slug)
        require_named_value(
            fixture,
            "message_framing",
            "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_32_RAW_SIGNED_PAYLOAD_SHA256",
            spec.slug,
        )
        require_named_value(
            fixture,
            "detached_signature_digest_profile",
            "SHA256_RAW_64_BYTE_ED25519_SIGNATURE",
            spec.slug,
        )
        require_named_value(fixture, "authorization_id_domain", AUTHORIZATION_ID_DOMAIN,
                            spec.slug)
        require_named_value(
            fixture,
            "authorization_id_framing",
            "U32BE_DOMAIN_LENGTH_DOMAIN_THREE_U64BE_32_RAW_SHA256",
            spec.slug,
        )
        require_named_value(fixture, "candidate_carried_key_used", False, spec.slug)
        require_named_value(fixture, "anchor_installed_out_of_band", False, spec.slug)
        require_named_value(fixture, "anchor_pinned_by_independent_caller", False, spec.slug)
        require_named_value(fixture, "signature_verified", False, spec.slug)
        require_named_value(fixture, "owner_authority_established", False, spec.slug)
        require_named_value(
            fixture, "legacy_s19_signature_or_envelope_reuse_allowed", False, spec.slug
        )
        require_named_value(fixture, "automatic_retry_allowed", False, spec.slug)
        require_named_value(fixture, "single_use", True, spec.slug)
    else:
        require_named_value(fixture, "may_execute_live", False, spec.slug)
        require_named_value(fixture, "automatic_or_implicit_retry_allowed", False, spec.slug)
        require_named_value(fixture, "created_by_runner", False, spec.slug)
        require_named_value(fixture, "same_failure_domain_as_database", False, spec.slug)
        require_named_value(fixture, "checkpoint_state", "MISSING", spec.slug)
        require_named_value(fixture, "registration_state", "MISSING", spec.slug)
        require_named_value(fixture, "registered_by_external_control_plane", False, spec.slug)
        require_named_value(fixture, "monotonic_counter", 1, spec.slug)
        require_named_value(fixture, "previous_checkpoint_sha256", None, spec.slug)
        require_named_value(fixture, "expected_unclaimed_revision", 1, spec.slug)
        require_named_value(fixture, "registration_revision", 1, spec.slug)
        require_named_value(fixture, "previous_revision", 0, spec.slug)
        require_named_value(fixture, "successful_claim_count", 0, spec.slug)
        require_named_value(fixture, "claimed_run_id_sha256", None, spec.slug)
        require_named_value(fixture, "observed_revocation_epoch", 1, spec.slug)
        require_named_value(fixture, "current_revocation_epoch", 1, spec.slug)
        require_named_value(fixture, "terminal_hard_lock", True, spec.slug)


def validate_schema_fixtures(
    repo: Path, overrides: Mapping[str, bytes] | None
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    fixtures: dict[str, dict[str, Any]] = {}
    receipts: dict[str, str] = {}
    for spec in PACKETS:
        schema_raw, schema = load_json(repo, spec.schema_path, overrides)
        require(
            schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
            f"schema draft drift: {spec.schema_path}",
        )
        require(schema.get("$id") == spec.schema_id, f"schema id drift: {spec.schema_path}")
        validate_schema_node(schema, spec.schema_path)
        definitions = schema.get("$defs")
        require(isinstance(definitions, dict), f"schema definitions absent: {spec.schema_path}")
        require(
            definitions.get("sha256", {}).get("pattern")
            == r"^(?!0{64}$)[0-9a-f]{64}$",
            f"schema permits all-zero SHA-256: {spec.schema_path}",
        )
        if spec.slug == "final-refreeze-subject":
            require(
                definitions.get("git_oid", {}).get("pattern")
                == r"^(?!0{40}$)[0-9a-f]{40}$",
                "subject schema permits all-zero Git object identity",
            )
        elif spec.slug == "owner-trust-anchor":
            key_properties = definitions.get("key_binding", {}).get("properties", {})
            require(
                key_properties.get("public_key_hex", {}).get("pattern")
                == r"^(?!0{64}$)[0-9a-f]{64}$",
                "anchor schema permits all-zero Ed25519 public key",
            )
            require(
                key_properties.get("key_id", {}).get("pattern")
                == r"^[A-Za-z0-9._-]{1,96}$"
                and key_properties.get("key_version", {}).get("minimum") == 1
                and key_properties.get("key_version", {}).get("maximum") == 4_294_967_295,
                "anchor schema key label/version bounds drift",
            )
        elif spec.slug == "owner-authorization-envelope":
            signature_properties = definitions.get("signature_binding", {}).get("properties", {})
            require(
                signature_properties.get("signature_hex", {}).get("pattern")
                == r"^(?!0{128}$)[0-9a-f]{128}$",
                "envelope schema permits all-zero Ed25519 signature",
            )
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise CheckFailure(f"Draft202012 schema invalid: {spec.schema_path}: {exc.message}") from exc
        fixture_raw, fixture = load_json(repo, spec.fixture_path, overrides)
        require_canonical_repository_json(fixture_raw, fixture, spec.fixture_path)
        errors = list(Draft202012Validator(schema).iter_errors(fixture))
        require(not errors, f"schema rejected fixture: {spec.fixture_path}: {[e.message for e in errors[:2]]}")
        probe_fixture = fixture
        if overrides is not None and spec.fixture_path in overrides:
            # Schema capability probes must stay independent from a fixture
            # mutation under test.  Otherwise an intentionally unsafe fixture
            # can make the complete safe projection fail before the semantic
            # validator observes the mutation itself.
            _, probe_fixture = load_json(repo, spec.fixture_path)
        if spec.slug == "owner-trust-anchor":
            installed = copy.deepcopy(probe_fixture)
            installed["test_only"] = False
            installed["synthetic"] = False
            installed["anchor_state"] = "INSTALLED_OUT_OF_BAND_CALLER_PINNED"
            installed["key_binding"]["key_id"] = "s21a-independent-owner-key-v1"
            installed["key_binding"]["public_key_hex"] = "e" * 64
            installed["owner_identity"]["identity_verified_out_of_band"] = True
            installed["owner_identity"]["owner_identity_verification_receipt_sha256"] = "f" * 64
            installed["trust_policy"]["installed_out_of_band"] = True
            installed["trust_policy"]["pinned_by_independent_caller"] = True
            installed["trust_policy"]["installation_receipt_sha256"] = "e" * 64
            installed = parse_json(reseal_fixture(installed, spec), "installed-anchor-schema-probe")
            installed_errors = list(Draft202012Validator(schema).iter_errors(installed))
            require(not installed_errors, "anchor schema rejects complete installed projection")
            missing_identity_receipt = copy.deepcopy(installed)
            missing_identity_receipt["owner_identity"][
                "owner_identity_verification_receipt_sha256"
            ] = None
            require(
                bool(list(Draft202012Validator(schema).iter_errors(missing_identity_receipt))),
                "anchor schema accepts installed identity without verification receipt",
            )
            repository_kat_id = copy.deepcopy(installed)
            repository_kat_id["key_binding"]["key_id"] = "s21a-synthetic-public-kat-v1"
            require(
                bool(list(Draft202012Validator(schema).iter_errors(repository_kat_id))),
                "anchor schema accepts real repository public KAT key id",
            )
            repository_kat_material = copy.deepcopy(installed)
            repository_kat_material["key_binding"]["public_key_hex"] = (
                "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
            )
            require(
                bool(list(Draft202012Validator(schema).iter_errors(repository_kat_material))),
                "anchor schema accepts real repository public KAT key material",
            )
        if spec.slug == "external-input-admission":
            complete = copy.deepcopy(probe_fixture)
            complete["test_only"] = False
            complete["synthetic"] = False
            complete["admission_state"] = (
                "INPUTS_COMPLETE_PENDING_SEPARATE_REVIEW_NON_EXECUTING"
            )
            complete["subject_binding"]["final_post_integration_subject_validated"] = True
            complete["subject_binding"]["exact_s21a_commit_tree_and_build_bound"] = True
            complete["owner_binding"]["new_owner_signature_valid"] = True
            complete["owner_binding"]["trust_anchor_installed_and_pinned"] = True
            complete["checkpoint_input"]["checkpoint_state"] = "COMMITTED_CURRENT"
            complete["checkpoint_input"]["provider_present"] = True
            complete["checkpoint_input"]["independent_failure_domain_proved"] = True
            complete["checkpoint_input"]["acknowledgement_semantics_validated"] = True
            complete["external_registration"]["registration_state"] = (
                "AUTHORIZED_UNCLAIMED_PRESENT"
            )
            complete["external_registration"]["binding_validated"] = True
            complete["external_registration"]["registered_by_external_control_plane"] = True
            for key in (
                "fresh_observer_present_and_bound",
                "real_runner_present_and_bound",
                "exact_environment_present_and_bound",
                "exact_canary_inputs_present_and_bound",
                "stop_and_revocation_fresh_and_exact",
            ):
                complete["runtime_inputs"][key] = True
            complete["result"]["all_external_inputs_validated"] = True
            complete["result"]["terminal_hard_lock"] = False
            complete = parse_json(reseal_fixture(complete, spec),
                                  "complete-external-admission-schema-probe")
            require(
                not list(Draft202012Validator(schema).iter_errors(complete)),
                "external-admission schema rejects complete non-executing projection",
            )
            for section, key, bad_value in (
                ("checkpoint_input", "same_failure_domain_as_database", True),
                ("external_registration", "created_by_runner", True),
                ("external_registration", "registered_by_external_control_plane", False),
            ):
                unsafe_complete = copy.deepcopy(complete)
                unsafe_complete[section][key] = bad_value
                require(
                    bool(list(Draft202012Validator(schema).iter_errors(unsafe_complete))),
                    f"external-admission complete schema accepts unsafe {key}",
                )
            later_checkpoint = copy.deepcopy(complete)
            later_checkpoint["checkpoint_input"]["monotonic_counter"] = 2
            later_checkpoint["checkpoint_input"]["previous_checkpoint_sha256"] = "e" * 64
            require(
                not list(Draft202012Validator(schema).iter_errors(later_checkpoint)),
                "checkpoint schema rejects exact predecessor for generation greater than one",
            )
            later_checkpoint["checkpoint_input"]["previous_checkpoint_sha256"] = None
            require(
                bool(list(Draft202012Validator(schema).iter_errors(later_checkpoint))),
                "checkpoint schema accepts missing predecessor after generation one",
            )
        validate_packet_semantics(spec, fixture)
        self_hash = verify_hashing_contract(fixture, spec)
        key = spec.slug.replace("-", "_")
        receipts[f"{key}_self_hash"] = self_hash
        receipts[f"{key}_schema_sha256"] = sha256(schema_raw)
        receipts[f"{key}_fixture_sha256"] = sha256(fixture_raw)
        fixtures[spec.slug] = fixture
    return fixtures, receipts


def validate_cross_bindings(
    repo: Path,
    fixtures: dict[str, dict[str, Any]],
    overrides: Mapping[str, bytes] | None,
) -> int:
    subject = fixtures["final-refreeze-subject"]
    anchor = fixtures["owner-trust-anchor"]
    envelope = fixtures["owner-authorization-envelope"]
    admission = fixtures["external-input-admission"]
    subject_sha = subject[PACKETS[0].self_hash_field]
    anchor_sha = anchor[PACKETS[1].self_hash_field]
    envelope_sha = envelope[PACKETS[2].self_hash_field]
    matches = all_named_values(envelope, "anchor_document_sha256")
    require(len(matches) == 2, "envelope trust-anchor binding cardinality drift")
    require(all(value == anchor_sha for value in matches), "envelope trust-anchor binding mismatch")
    subject_matches = all_named_values(envelope, "final_refreeze_subject_sha256")
    require(len(subject_matches) == 1, "envelope subject binding cardinality drift")
    require(subject_matches[0] == subject_sha, "envelope subject binding mismatch")
    signed_payload = envelope.get("signed_payload")
    signature = envelope.get("signature_binding")
    owner_decision = envelope.get("owner_decision")
    require(isinstance(signed_payload, dict), "signed payload absent")
    require(isinstance(signature, dict), "signature binding absent")
    require(isinstance(owner_decision, dict), "owner decision absent")
    computed_payload_sha = framed_digest(SIGNED_PAYLOAD_DOMAIN, canonical_bytes(signed_payload))
    require(signature.get("signed_payload_sha256") == computed_payload_sha,
            "signed payload digest mismatch")
    signature_hex = signature.get("signature_hex")
    require(isinstance(signature_hex, str) and re.fullmatch(r"[0-9a-f]{128}", signature_hex),
            "detached signature encoding invalid")
    computed_signature_sha = sha256(bytes.fromhex(signature_hex))
    require(signature.get("detached_signature_sha256") == computed_signature_sha,
            "detached signature digest mismatch")
    computed_authorization_id = framed_raw_digest_sequence(
        AUTHORIZATION_ID_DOMAIN,
        (computed_payload_sha, computed_signature_sha, anchor_sha),
    )
    require(owner_decision.get("authorization_id_sha256") == computed_authorization_id,
            "authorization id digest mismatch")
    admission_subject = all_named_values(admission, "final_refreeze_subject_sha256")
    require(len(admission_subject) == 3 and all(value == subject_sha for value in admission_subject),
            "admission subject binding mismatch")
    admission_anchor = all_named_values(admission, "anchor_document_sha256")
    require(len(admission_anchor) == 1 and admission_anchor[0] == anchor_sha,
            "admission anchor binding mismatch")
    admission_envelope = all_named_values(admission, "owner_envelope_sha256")
    require(len(admission_envelope) == 3 and all(value == envelope_sha for value in admission_envelope),
            "admission envelope binding mismatch")
    admission_authorization_ids = all_named_values(admission, "authorization_id_sha256")
    require(
        len(admission_authorization_ids) == 2
        and all(value == computed_authorization_id for value in admission_authorization_ids),
        "admission authorization-id binding mismatch",
    )
    capability_nonce = signed_payload.get("capability_nonce_sha256")
    registration_nonces = all_named_values(admission.get("external_registration", {}),
                                           "capability_nonce_sha256")
    require(len(registration_nonces) == 1 and registration_nonces[0] == capability_nonce,
            "registration capability-nonce binding mismatch")

    subject_build = subject.get("build_bindings")
    runtime_inputs = admission.get("runtime_inputs")
    checkpoint_input = admission.get("checkpoint_input")
    registration = admission.get("external_registration")
    policy_bindings = admission.get("policy_bindings")
    require(isinstance(subject_build, dict), "subject build bindings absent")
    require(isinstance(runtime_inputs, dict), "admission runtime inputs absent")
    require(isinstance(checkpoint_input, dict), "admission checkpoint input absent")
    require(isinstance(registration, dict), "admission registration absent")
    require(isinstance(policy_bindings, dict), "admission policy bindings absent")
    require(checkpoint_input.get("monotonic_counter") == 1
            and checkpoint_input.get("previous_checkpoint_sha256") is None,
            "checkpoint predecessor relation mismatch")
    require(registration.get("expected_unclaimed_revision") == 1
            and registration.get("registration_revision") == 1,
            "registration revision binding mismatch")
    external_digest_fields = (
        (checkpoint_input, "provider_identity_sha256"),
        (checkpoint_input, "provider_trust_anchor_sha256"),
        (checkpoint_input, "provider_policy_sha256"),
        (checkpoint_input, "provider_failure_domain_sha256"),
        (checkpoint_input, "database_failure_domain_sha256"),
        (checkpoint_input, "checkpoint_receipt_sha256"),
        (checkpoint_input, "checkpoint_head_sha256"),
        (checkpoint_input, "committed_content_root_sha256"),
        (registration, "registration_receipt_sha256"),
        (registration, "registrar_identity_sha256"),
        (registration, "external_control_plane_identity_sha256"),
        (registration, "provenance_receipt_sha256"),
        (registration, "creator_binary_sha256"),
        (runtime_inputs, "controller_binary_sha256"),
        (runtime_inputs, "observer_source_sha256"),
        (runtime_inputs, "observer_binary_sha256"),
        (runtime_inputs, "observer_toolchain_sha256"),
        (runtime_inputs, "observer_measurement_receipt_sha256"),
        (runtime_inputs, "runner_source_sha256"),
        (runtime_inputs, "runner_binary_sha256"),
        (runtime_inputs, "runner_toolchain_sha256"),
        (runtime_inputs, "runner_operation_manifest_sha256"),
        (runtime_inputs, "environment_observation_receipt_sha256"),
        (runtime_inputs, "canary_input_pack_sha256"),
        (runtime_inputs, "stop_snapshot_sha256"),
        (runtime_inputs, "revocation_snapshot_sha256"),
        (policy_bindings, "lab_environment_sha256"),
        (policy_bindings, "stop_policy_sha256"),
        (policy_bindings, "revocation_policy_sha256"),
        (policy_bindings, "retention_policy_sha256"),
        (policy_bindings, "cleanup_policy_sha256"),
        (policy_bindings, "custody_policy_sha256"),
        (policy_bindings, "review_policy_sha256"),
        (policy_bindings, "independent_review_receipt_sha256"),
    )
    for container, key in external_digest_fields:
        digest = container.get(key)
        require(
            isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            and digest != "0" * 64,
            f"external input digest absent or zero: {key}",
        )
    for key in ("controller_binary_sha256", "observer_binary_sha256", "runner_binary_sha256"):
        require(subject_build.get(key) == runtime_inputs.get(key),
                f"subject/admission runtime digest mismatch: {key}")
    require(
        checkpoint_input.get("provider_failure_domain_sha256")
        != checkpoint_input.get("database_failure_domain_sha256"),
        "checkpoint provider/database failure-domain collision",
    )
    require(
        registration.get("creator_binary_sha256")
        != runtime_inputs.get("runner_binary_sha256"),
        "registration creator is the runner binary",
    )
    signed_revocation_epoch = signed_payload.get("revocation_epoch")
    require(
        checkpoint_input.get("observed_revocation_epoch") == signed_revocation_epoch
        and policy_bindings.get("current_revocation_epoch") == signed_revocation_epoch,
        "external revocation epoch binding mismatch",
    )
    require(
        registration.get("previous_revision") == 0
        and registration.get("registration_revision") == 1
        and registration.get("previous_revision") + 1
        == registration.get("registration_revision"),
        "registration predecessor revision relation mismatch",
    )
    require(
        registration.get("successful_claim_count") == 0
        and registration.get("claimed_run_id_sha256") is None,
        "synthetic registration is already claimed",
    )
    for key, expected in (
        ("s20b_integration_commit", BASELINE_COMMIT),
        ("s20b_integration_tree", BASELINE_TREE),
        ("s20b_source_commit", S20B_SOURCE_COMMIT),
        ("s20b_source_tree", S20B_SOURCE_TREE),
        ("s20b_integrated_archive_sha256", S20B_INTEGRATED_ARCHIVE_SHA256),
    ):
        require_named_value(subject, key, expected, "final-refreeze-subject")
    artifact_bindings = subject.get("artifact_bindings")
    require(isinstance(artifact_bindings, dict), "subject artifact bindings absent")
    for key, expected in (
        ("assignment_set_sha256", "b3a7025a488e9aefc6724869f75ab76a482002224bee90c075e9379101ee7264"),
        ("schedule_sha256", "8c0129d150d918523c122dbf3afb4e7c6abb3ce7ca957204252c115a7f1def15"),
        ("assignment_record_set_sha256", "7a927eba7eb691990b32c7987bea5c0fdce15c51d37792f8ca45c3bddb556bc6"),
        ("operation_descriptor_set_sha256", "a00feb5745c83fc20d5ad84f66877289c9108b29371697ceb8cf13e3fb142db0"),
        ("catalog_row_count", 5639),
        ("catalog_sha256", S20B_CATALOG_SHA256),
        ("target_phase_count", 113),
        ("validator_rule_count", 32),
        ("validator_ruleset_sha256", S20B_VALIDATOR_RULESET_SHA256),
        ("s20b_source_delta_file_count", 23),
    ):
        require_named_value(subject, key, expected, "final-refreeze-subject")
    for key, path in (
        ("s20b_checker_sha256", S20B_CHECKER_PATH),
        ("s20b_gate_sha256", S20B_GATE_PATH),
        ("s20b_report_sha256", S20B_REPORT_PATH),
        ("s20b_successor_gate_sha256", S20B_SUCCESSOR_PATH),
    ):
        require_named_value(subject, key, sha256(read_bytes(repo, path, overrides)),
                            "final-refreeze-subject")
    return 83


RUST_MARKERS = (
    "S21A_FINAL_REFREEZE_SUBJECT_BUILDER_PARSER_VALIDATOR_IMPLEMENTED: bool = true",
    "S21A_NEW_OWNER_SIGNATURE_VERIFIER_IMPLEMENTED: bool = true",
    "S21A_OPAQUE_EXTERNAL_INPUT_ADMISSION_IMPLEMENTED: bool = true",
    "S21A_EXTERNAL_INPUT_DIGEST_CROSS_BINDING_IMPLEMENTED: bool = true",
    "S21A_TYPED_EXTERNAL_INPUT_PACKET_VALIDATOR_IMPLEMENTED: bool = true",
    "S21A_REAL_EXTERNAL_FACT_CONSTRUCTOR_PRESENT: bool = false",
    "S21A_LIVE_BACKEND_PRESENT: bool = false",
    'S21A_SIDE_EFFECTS_UNLOCKED: &str = "NONE"',
)

EXPECTED_RUST_TESTS = {
    "s21a_final_subject_roundtrip_freezes_exact_predecessor_and_lf_contract",
    "s21a_subject_noncanonical_duplicate_self_and_independent_build_drift_reject",
    "s21a_repository_synthetic_subject_cannot_be_owner_authorized",
    "s21a_new_domain_detached_owner_signature_accepts_only_nonexecuting_review",
    "s21a_old_s19_signature_domain_and_legacy_reuse_reject",
    "s21a_self_authenticated_or_uninstalled_anchor_rejects",
    "s21a_repository_public_kat_key_rejects_even_if_pinned",
    "s21a_owner_identity_receipt_build_and_retry_drift_reject",
    "s21a_external_exact_digest_cross_bind_returns_nonpermit_readiness",
    "s21a_same_failure_domain_checkpoint_rejects",
    "s21a_stale_forked_prepared_and_unknown_checkpoint_reject",
    "s21a_runner_created_or_consumed_registration_rejects",
    "s21a_observer_runner_build_and_environment_drift_reject",
    "s21a_retry_stop_revocation_and_side_effect_inputs_reject",
    "s21a_subject_catalog_and_validator_ruleset_are_exactly_pinned",
    "s21a_owner_key_id_and_u32_revision_boundaries_are_exact",
    "s21a_typed_admission_parser_and_exact_rebuild_reject_resealed_drift",
    "s21a_typed_synthetic_packet_requires_all_fail_closed_booleans",
    "s21a_repository_synthetic_admission_kat_parses_and_roundtrips_exactly",
    "s21a_checkpoint_counter_and_optional_predecessor_are_exact",
    "s21a_policy_bindings_and_matching_all_zero_digests_reject",
    "s21a_registration_revision_provenance_control_plane_and_claims_reject",
    "s21a_no_real_external_constructor_live_backend_or_public_permit_exists",
}


def production_rust_source(source: str) -> str:
    marker = re.search(r"(?m)^#\[cfg\(test\)\]\s*\nmod tests\s*\{", source)
    return source if marker is None else source[: marker.start()]


def validate_rfc8032_private_seed_absent(source: str) -> None:
    require("RFC8032_SEED" not in source, "RFC8032 private test seed symbol present")
    require("from_seed" not in source, "seed-based Ed25519 key construction present")
    candidates: list[bytes] = []
    byte_literals = re.findall(r"(?i)0x([0-9a-f]{2})(?![0-9a-f])", source)
    for start in range(0, max(0, len(byte_literals) - 31)):
        candidates.append(bytes(int(value, 16) for value in byte_literals[start : start + 32]))
    for value in re.findall(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", source):
        candidates.append(bytes.fromhex(value))
    for value in re.findall(r"(?i)(?:\\x[0-9a-f]{2}){32}", source):
        candidates.append(bytes.fromhex(value.replace("\\x", "")))
    require(
        all(sha256(candidate) != FORBIDDEN_RFC8032_TEST_SEED_SHA256 for candidate in candidates),
        "RFC8032 private test seed bytes present",
    )


def validate_rust(repo: Path, overrides: Mapping[str, bytes] | None) -> int:
    cargo = read_text(repo, CARGO_PATH, overrides)
    require(
        f'{FEATURE} = ["temporal-evidence-s20b-owned-lab-rich-packet-validators-synthetic"]'
        in cargo,
        "exact private default-off S21A Cargo feature absent",
    )
    require('default = ["onnx-embed"]' in cargo,
            "Cargo default feature set drifted or may include S21A")
    parent = read_text(repo, S20_RUST_PATH, overrides)
    require(
        f'#[cfg(feature = "{FEATURE}")]\nmod final_refreeze_admission;' in parent,
        "exact S21A child-module stanza absent",
    )
    source = read_text(repo, S21A_RUST_PATH, overrides)
    for marker in RUST_MARKERS:
        require(marker in source, f"S21A Rust implementation marker absent: {marker}")
    for token in (
        "IndependentS21RefreezeInputsV1",
        "S21RefreezeSubjectV1",
        "PinnedS21OwnerTrustExpectationsV1",
        "VerifiedS21OwnerBoundSubjectV1",
        "PinnedExternalAdmissionExpectationsV1",
        "ExternalAdmissionFactsV1",
        "S21ExternalInputAdmissionV1",
        "CanonicalBuiltS21ExternalInputAdmissionV1",
        "ValidatedS21ExternalInputReadinessV1",
        SIGNED_PAYLOAD_DOMAIN,
        AUTHORIZATION_ID_DOMAIN,
        BASELINE_COMMIT,
        BASELINE_TREE,
        S20B_SOURCE_COMMIT,
        S20B_SOURCE_TREE,
        S20B_CATALOG_SHA256,
        S20B_VALIDATOR_RULESET_SHA256,
        "registration_provenance_receipt_sha256",
        "external_control_plane_identity_sha256",
        "registration_creator_binary_sha256",
        "previous_checkpoint_head_sha256",
        "expected_checkpoint_counter",
        "independent_review_receipt_sha256",
        "security_digests_nonzero",
        "checkpoint_predecessor_valid",
        "provenance_receipt_sha256: String",
        "creator_binary_sha256: String",
        "expected_unclaimed_revision: u64",
        "registration_revision: u64",
        "previous_revision: u64",
        'S21A_REPOSITORY_PUBLIC_KAT_KEY_ID: &str = "s21a-synthetic-public-kat-v1"',
        'S21A_REPOSITORY_PUBLIC_KAT_KEY_HEX: &str =',
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
    ):
        require(token in source, f"S21A Rust semantic token absent: {token}")
    for pattern in (
        r"struct\s+S21ExternalInputAdmissionV1\s*\{",
        r"#\[must_use\]\s*\nstruct\s+CanonicalBuiltS21ExternalInputAdmissionV1\s*\{",
        r"fn\s+parse_s21_external_input_admission_v1\s*\(",
        r"fn\s+build_s21_external_input_admission_v1\s*\(",
        r"fn\s+verify_s21_external_input_admission_v1\s*\(",
        r"fn\s+valid_s21_owner_key_id\s*\(",
        r"value\.len\(\)\s*<=\s*96",
        r"anchor\.key_binding\.key_id\s*==\s*S21A_REPOSITORY_PUBLIC_KAT_KEY_ID",
        r"public_key\s*==\s*repository_public_kat_key",
        r"previous_revision\.checked_add\(1\)\s*==\s*Some\(facts\.registration\.revision\)",
        r"creator_binary_sha256\s*!=\s*facts\.runtime\.runner_binary_sha256",
        r"\(1,\s*None\)\s*=>\s*true",
        r"Some\(previous\)\)\s+if\s+counter\s*>\s*1",
        r"previous\s*!=\s*\*checkpoint_head_sha256",
        r"monotonic_counter\s*==\s*expected\.expected_checkpoint_counter",
        r"!facts\.registration\.created_by_runner",
        r"!facts\.control\.automatic_retry_allowed",
        r"facts\.control\.live_side_effect_count\s*==\s*0",
        r"\|\|\s*!security_digests_valid",
    ):
        require(re.search(pattern, source) is not None,
                f"S21A Rust fail-closed relation absent: {pattern}")
    require(
        len(re.findall(r"key_version\s*>\s*u64::from\(u32::MAX\)", source)) == 2,
        "S21A Rust owner key-version u32 bounds drift",
    )
    production = production_rust_source(source)
    validate_rfc8032_private_seed_absent(source)
    test_source = source[len(production) :]
    for token in (
        "use ring::rand::SystemRandom;",
        "Ed25519KeyPair::generate_pkcs8(&SystemRandom::new())",
        "Ed25519KeyPair::from_pkcs8(pkcs8.as_ref())",
    ):
        require(token in test_source, f"ephemeral test key generation absent: {token}")
        require(token not in production, f"test key generation escaped cfg(test): {token}")
    forbidden = (
        r"\bstd::process::Command\b",
        r"\bTcp(?:Stream|Listener)\b",
        r"\bUdpSocket\b",
        r"\bunsafe\s*\{",
        r"\blibc::(?:kill|mount|umount)",
        r"\bnix::[^\n]*(?:kill|mount)",
        r"\bimpl\s+SyntheticCheckpointPortV1\s+for\b",
        r"\bimpl\s+SyntheticActionStarterV1\s+for\b",
        r"\bpub(?:\(crate\))?\s+fn\s+(?:open|spawn|execute|start)_live\b",
    )
    for pattern in forbidden:
        require(re.search(pattern, production) is None, f"live/unsafe Rust surface present: {pattern}")
    require("side_effects_unlocked" in source or "SIDE_EFFECTS_UNLOCKED" in source,
            "S21A side-effect marker absent")
    require("NONE" in source, "S21A side effects are not explicitly NONE")
    tests = re.findall(r"(?m)^\s*#\[test\]\s*\n\s*fn\s+(s21a_[a-z0-9_]+)\s*\(", source)
    require(len(tests) == len(set(tests)), "duplicate S21A Rust test name")
    require(set(tests) == EXPECTED_RUST_TESTS, "S21A directed Rust KAT catalog drift")
    return len(tests)


def validate_control_documents(repo: Path, overrides: Mapping[str, bytes] | None) -> None:
    loaded: dict[str, dict[str, Any]] = {}
    for label, path in (
        ("contract", CONTRACT_PATH),
        ("status", STATUS_PATH),
        ("successor", SUCCESSOR_PATH),
    ):
        _, value = load_json(repo, path, overrides)
        require(value.get("status") == STATUS, f"status drift: {label}")
        require(value.get("decision") == DECISION, f"decision drift: {label}")
        all_fail_closed_fields(value, label)
        loaded[label] = value
    contract = loaded["contract"]
    status = loaded["status"]
    successor = loaded["successor"]
    require(contract.get("implementation_mode") == MODE, "implementation mode drift")
    require_named_value(contract, "side_effects_unlocked", "NONE", "contract")
    require_named_value(contract, "independently_installed_trust_anchor_present", False, "contract")
    require_named_value(contract, "external_authorized_unclaimed_registration_present", False, "contract")
    require_named_value(contract, "real_independent_checkpoint_provider_present", False, "contract")
    require_named_value(contract, "live_execution_authorized", False, "contract")
    require_named_value(
        contract, "repository_public_kat_key_id_denied_for_real_anchor", True, "contract"
    )
    require_named_value(
        contract, "repository_public_kat_public_key_denied_for_real_anchor", True, "contract"
    )
    require_named_value(
        contract, "repository_public_kat_can_be_promoted_to_real_anchor", False, "contract"
    )
    require_named_value(contract, "schema_count", 4, "contract")
    require_named_value(contract, "synthetic_fixture_count", 4, "contract")
    require_named_value(contract, "audience",
                        "agent-bridge/biocortex/owned-lab/s21a/final-refreeze-owner-review/v1",
                        "contract")
    require_named_value(contract, "signed_payload_digest_domain", SIGNED_PAYLOAD_DOMAIN, "contract")
    require_named_value(contract, "signature_domain",
                        "agent-bridge/biocortex/owned-lab/s21a/owner-authorization-signature/v1",
                        "contract")
    require_named_value(contract, "authorization_id_domain", AUTHORIZATION_ID_DOMAIN, "contract")
    require_named_value(status, "implementation_mode", MODE, "status")
    require_named_value(status, "closed_schema_count", 4, "status")
    require_named_value(status, "live_canary_run", False, "status")
    require_named_value(
        status,
        "real_anchor_repository_public_kat_key_id_and_material_denylist_enforced",
        True,
        "status",
    )
    require_named_value(successor, "candidate_supplied_expected_values_authoritative", False,
                        "successor")
    require_named_value(successor, "live_execution_may_begin", False, "successor")
    require_named_value(
        successor,
        "repository_public_kat_key_id_and_material_denied_for_real_anchor",
        True,
        "successor",
    )
    require_named_value(
        successor,
        "forbids_repository_public_kat_key_id_or_material_as_real_owner_anchor",
        True,
        "successor",
    )
    require_named_value(
        successor, "repository_public_kat_is_s21_authority", False, "successor"
    )
    conditions = successor.get("fail_closed_conditions")
    require(isinstance(conditions, list) and len(conditions) == 11,
            "successor fail-closed condition catalog drift")
    condition_text = "\n".join(str(item) for item in conditions)
    for token in (
        "STALE",
        "FORKED",
        "UNKNOWN",
        "CREATED_BY_RUNNER",
        "LEGACY_S19",
        "AUTOMATIC",
        "REPOSITORY_PUBLIC_KAT_KEY_ID_OR_KEY_MATERIAL",
    ):
        require(token in condition_text, f"successor fail-closed token absent: {token}")


def validate_docs(repo: Path, overrides: Mapping[str, bytes] | None) -> None:
    design = read_text(repo, DESIGN_PATH, overrides)
    report = read_text(repo, REPORT_PATH, overrides)
    for token in (
        STATUS,
        DECISION,
        BASELINE_COMMIT,
        BASELINE_TREE,
        S20B_SOURCE_COMMIT,
        S20B_SOURCE_TREE,
        "NON_LIVE",
        "side_effects_unlocked=NONE",
    ):
        require(token in design or token in report, f"design/report token absent: {token}")


def validate_source_gate(repo: Path, overrides: Mapping[str, bytes] | None) -> None:
    gate = read_text(repo, GATE_PATH, overrides)
    for token in (
        "#!/usr/bin/env -S -i /usr/bin/bash",
        "set -euo pipefail",
        "--unshare-net",
        '--ro-bind / / --bind "$tmp" "$tmp" --dev /dev',
        "CARGO_BUILD_JOBS=1",
        "CARGO_NET_OFFLINE=true",
        "--locked --offline",
        '--no-default-features --features "$feature" -j1',
        "s21a_ -- --test-threads=1",
        "live_canary\\tNOT_RUN",
        "side_effects_unlocked\\tNONE",
    ):
        require(token in gate, f"S21A source gate safety token absent: {token}")
    require("--bind / /" not in gate, "S21A source gate root is writable")
    if overrides is None or GATE_PATH not in overrides:
        require(
            canonical_path(repo, GATE_PATH).stat().st_mode & 0o777 == 0o755,
            "S21A source gate mode is not 0755",
        )


def mutate_first_named(value: Any, key_name: str, replacement: Any) -> bool:
    if isinstance(value, list):
        for child in value:
            if mutate_first_named(child, key_name, replacement):
                return True
    elif isinstance(value, dict):
        for key, child in value.items():
            if key == key_name:
                value[key] = replacement
                return True
            if mutate_first_named(child, key_name, replacement):
                return True
    return False


def mutation_cases(repo: Path) -> list[tuple[str, bytes, str]]:
    cases: list[tuple[str, bytes, str]] = []
    loaded: dict[str, tuple[PacketSpec, dict[str, Any], dict[str, Any]]] = {}
    for spec in PACKETS:
        _, schema = load_json(repo, spec.schema_path)
        _, fixture = load_json(repo, spec.fixture_path)
        loaded[spec.slug] = (spec, schema, fixture)
        raw = read_bytes(repo, spec.fixture_path)
        cases.append((spec.fixture_path, raw.replace(b"{", b'{"schema":"duplicate",', 1), "duplicate JSON key"))
        cases.append((spec.fixture_path, raw.replace(b"{", b'{"unexpected_float":1.5,', 1), "floating-point JSON forbidden"))
        cases.append((spec.fixture_path, raw.replace(b"{", b'{"unexpected_non_ascii":"\xc3\xa9",', 1), "invalid restricted JSON"))
        cases.append((spec.fixture_path, raw.replace(b"{", b'{"unexpected_escaped_non_ascii":"\\u00e9",', 1), "non-ASCII string value forbidden"))
        cases.append((spec.fixture_path, raw.replace(b"{", b'{"unexpected_negative":-1,', 1), "nonnegative u64 integer required"))
        cases.append((spec.fixture_path, raw.replace(b"{", b'{"unexpected_u64_overflow":18446744073709551616,', 1), "nonnegative u64 integer required"))
        cases.append((spec.fixture_path, b" " + raw,
                      "repository JSON is not restricted canonical JSON"))
        extra = copy.deepcopy(fixture)
        extra["unexpected_open_world_field"] = False
        cases.append((spec.fixture_path, canonical_bytes(extra) + b"\n", "schema rejected fixture"))
        for required in schema.get("required", []):
            missing = copy.deepcopy(fixture)
            missing.pop(required, None)
            cases.append((spec.fixture_path, canonical_bytes(missing) + b"\n", "schema rejected fixture"))
        bad_hash = copy.deepcopy(fixture)
        bad_hash[spec.self_hash_field] = "0" * 64
        cases.append((spec.fixture_path, canonical_bytes(bad_hash) + b"\n",
                      "self digest mismatch|schema rejected fixture"))
        schema_extra = copy.deepcopy(schema)
        schema_extra["properties"]["open"] = {"type": "boolean"}
        cases.append((spec.schema_path, canonical_bytes(schema_extra) + b"\n", "required/properties mismatch"))
        schema_external = copy.deepcopy(schema)
        replaced = False

        def replace_first_ref(value: Any) -> None:
            nonlocal replaced
            if replaced:
                return
            if isinstance(value, list):
                for child in value:
                    replace_first_ref(child)
            elif isinstance(value, dict):
                for key, child in value.items():
                    if key == "$ref" and isinstance(child, str) and child.startswith("#/"):
                        value[key] = "https://invalid.example/s21a-open-schema"
                        replaced = True
                        return
                    replace_first_ref(child)

        replace_first_ref(schema_external)
        require(replaced, f"schema has no internal ref KAT: {spec.schema_path}")
        cases.append((spec.schema_path, canonical_bytes(schema_external) + b"\n", "external schema ref"))

    subject_spec, _, subject = loaded["final-refreeze-subject"]
    anchor_spec, _, anchor = loaded["owner-trust-anchor"]
    envelope_spec, _, envelope = loaded["owner-authorization-envelope"]
    admission_spec, _, admission = loaded["external-input-admission"]
    semantic_mutations = (
        (subject_spec, subject, "generated_outside_repository_after_s21a_integration", True, "fail-closed field became true"),
        (subject_spec, subject, "candidate_supplied_expected_digest_used", True, "fail-closed field became true"),
        (anchor_spec, anchor, "installed_out_of_band", True, "fail-closed field became true"),
        (anchor_spec, anchor, "pinned_by_independent_caller", True, "fail-closed field became true"),
        (anchor_spec, anchor, "private_key_present_in_repository", True, "fail-closed field became true"),
        (anchor_spec, anchor, "candidate_carried_key_is_trusted", True, "fail-closed field became true"),
        (anchor_spec, anchor, "owner_identity_verification_receipt_sha256", "f" * 64, "semantic field drift"),
        (anchor_spec, anchor, "public_key_hex", "0" * 64, "semantic field drift"),
        (anchor_spec, anchor, "key_version", 2, "semantic field drift"),
        (anchor_spec, anchor, "legacy_s19_key_reuse_allowed", True, "fail-closed field became true"),
        (anchor_spec, anchor, "audience", "AGENT_BRIDGE_S19_OWNED_LAB_L1_ONLY", "semantic field drift"),
        (envelope_spec, envelope, "signature_domain", "agent-bridge/biocortex/owned-lab/owner-authorization/s19/v1", "semantic field drift"),
        (envelope_spec, envelope, "audience", "AGENT_BRIDGE_S19_OWNED_LAB_L1_ONLY", "semantic field drift"),
        (envelope_spec, envelope, "candidate_carried_key_used", True, "fail-closed field became true"),
        (envelope_spec, envelope, "anchor_installed_out_of_band", True, "fail-closed field became true"),
        (envelope_spec, envelope, "anchor_pinned_by_independent_caller", True, "fail-closed field became true"),
        (envelope_spec, envelope, "signature_verified", True, "fail-closed field became true"),
        (envelope_spec, envelope, "owner_authority_established", True, "fail-closed field became true"),
        (envelope_spec, envelope, "synthetic_envelope_is_owner_authority", True, "fail-closed field became true"),
        (envelope_spec, envelope, "legacy_s19_signature_or_envelope_reuse_allowed", True, "fail-closed field became true"),
        (admission_spec, admission, "same_failure_domain_as_database", True, "fail-closed field became true"),
        (admission_spec, admission, "created_by_runner", True, "fail-closed field became true"),
        (admission_spec, admission, "automatic_or_implicit_retry_allowed", True, "fail-closed field became true"),
        (admission_spec, admission, "may_execute_live", True, "fail-closed field became true"),
        (admission_spec, admission, "admission_packet_is_owner_authority", True, "fail-closed field became true"),
        (admission_spec, admission, "side_effects_unlocked", "LIVE",
         "side effects unlocked|schema rejected fixture"),
        (subject_spec, subject, "s20b_integration_commit", "0" * 40, "semantic field drift"),
        (subject_spec, subject, "s20b_integration_tree", "0" * 40, "semantic field drift"),
        (subject_spec, subject, "s20b_source_commit", "f" * 40, "semantic field drift"),
        (subject_spec, subject, "s20b_source_tree", "f" * 40, "semantic field drift"),
        (subject_spec, subject, "s20b_integrated_archive_sha256", "f" * 64, "semantic field drift"),
    )
    for spec, original, key, replacement, expected in semantic_mutations:
        mutated = copy.deepcopy(original)
        require(mutate_first_named(mutated, key, replacement), f"semantic KAT field absent: {key}")
        cases.append((spec.fixture_path, reseal_fixture(mutated, spec), expected))

    altered_payload = copy.deepcopy(envelope)
    require(mutate_first_named(altered_payload, "challenge_nonce_sha256", "e" * 64),
            "signed-payload digest KAT field absent")
    cases.append((envelope_spec.fixture_path, reseal_fixture(altered_payload, envelope_spec),
                  "signed payload digest mismatch"))
    altered_signature = copy.deepcopy(envelope)
    require(mutate_first_named(altered_signature, "signature_hex", "01" * 64),
            "signature digest KAT field absent")
    cases.append((envelope_spec.fixture_path, reseal_fixture(altered_signature, envelope_spec),
                  "detached signature digest mismatch"))
    altered_authorization_id = copy.deepcopy(envelope)
    require(mutate_first_named(altered_authorization_id, "authorization_id_sha256", "e" * 64),
            "authorization-id KAT field absent")
    cases.append((envelope_spec.fixture_path, reseal_fixture(altered_authorization_id, envelope_spec),
                  "authorization id digest mismatch"))

    for checkpoint_state in ("STALE", "FORKED", "ACKNOWLEDGEMENT_UNKNOWN"):
        altered_checkpoint = copy.deepcopy(admission)
        require(mutate_first_named(altered_checkpoint, "checkpoint_state", checkpoint_state),
                "checkpoint-state KAT field absent")
        cases.append((admission_spec.fixture_path, reseal_fixture(altered_checkpoint, admission_spec),
                      "semantic field drift"))
    altered_registration = copy.deepcopy(admission)
    require(mutate_first_named(altered_registration, "registration_state", "UNKNOWN"),
            "registration-state KAT field absent")
    cases.append((admission_spec.fixture_path, reseal_fixture(altered_registration, admission_spec),
                  "semantic field drift"))
    altered_runtime = copy.deepcopy(admission)
    require(mutate_first_named(altered_runtime, "observer_binary_sha256", "f" * 64),
            "runtime cross-binding KAT field absent")
    cases.append((admission_spec.fixture_path, reseal_fixture(altered_runtime, admission_spec),
                  "subject/admission runtime digest mismatch"))
    zero_checkpoint = copy.deepcopy(admission)
    require(mutate_first_named(zero_checkpoint, "checkpoint_receipt_sha256", "0" * 64),
            "checkpoint receipt KAT field absent")
    cases.append((admission_spec.fixture_path, reseal_fixture(zero_checkpoint, admission_spec),
                  "external input digest absent or zero|invalid or zero SHA-256 field|schema rejected fixture"))
    registration_auth_drift = copy.deepcopy(admission)
    registration_auth_drift["external_registration"]["authorization_id_sha256"] = "e" * 64
    cases.append((admission_spec.fixture_path,
                  reseal_fixture(registration_auth_drift, admission_spec),
                  "admission authorization-id binding mismatch"))
    checkpoint_subject_drift = copy.deepcopy(admission)
    checkpoint_subject_drift["checkpoint_input"]["final_refreeze_subject_sha256"] = "e" * 64
    cases.append((admission_spec.fixture_path,
                  reseal_fixture(checkpoint_subject_drift, admission_spec),
                  "admission subject binding mismatch"))
    checkpoint_predecessor_drift = copy.deepcopy(admission)
    checkpoint_predecessor_drift["checkpoint_input"]["previous_checkpoint_sha256"] = "e" * 64
    cases.append((admission_spec.fixture_path,
                  reseal_fixture(checkpoint_predecessor_drift, admission_spec),
                  "checkpoint predecessor relation mismatch|schema rejected fixture"))
    registration_nonce_drift = copy.deepcopy(admission)
    registration_nonce_drift["external_registration"]["capability_nonce_sha256"] = "e" * 64
    cases.append((admission_spec.fixture_path,
                  reseal_fixture(registration_nonce_drift, admission_spec),
                  "registration capability-nonce binding mismatch"))
    registration_revision_drift = copy.deepcopy(admission)
    registration_revision_drift["external_registration"]["registration_revision"] = 2
    cases.append((admission_spec.fixture_path,
                  reseal_fixture(registration_revision_drift, admission_spec),
                  "semantic field drift|registration revision binding mismatch"))
    zero_policy = copy.deepcopy(admission)
    zero_policy["policy_bindings"]["review_policy_sha256"] = "0" * 64
    cases.append((admission_spec.fixture_path, reseal_fixture(zero_policy, admission_spec),
                  "invalid or zero SHA-256 field|schema rejected fixture"))
    same_failure_domain = copy.deepcopy(admission)
    same_failure_domain["checkpoint_input"]["provider_failure_domain_sha256"] = (
        same_failure_domain["checkpoint_input"]["database_failure_domain_sha256"]
    )
    cases.append((admission_spec.fixture_path, reseal_fixture(same_failure_domain, admission_spec),
                  "checkpoint provider/database failure-domain collision"))
    runner_created_registration = copy.deepcopy(admission)
    runner_created_registration["external_registration"]["creator_binary_sha256"] = (
        runner_created_registration["runtime_inputs"]["runner_binary_sha256"]
    )
    cases.append((admission_spec.fixture_path,
                  reseal_fixture(runner_created_registration, admission_spec),
                  "registration creator is the runner binary"))
    previous_revision_drift = copy.deepcopy(admission)
    previous_revision_drift["external_registration"]["previous_revision"] = 1
    cases.append((admission_spec.fixture_path,
                  reseal_fixture(previous_revision_drift, admission_spec),
                  "semantic field drift|registration predecessor revision relation mismatch"))
    claimed_registration = copy.deepcopy(admission)
    claimed_registration["external_registration"]["successful_claim_count"] = 1
    cases.append((admission_spec.fixture_path, reseal_fixture(claimed_registration, admission_spec),
                  "semantic field drift|synthetic registration is already claimed"))
    claimed_run = copy.deepcopy(admission)
    claimed_run["external_registration"]["claimed_run_id_sha256"] = "e" * 64
    cases.append((admission_spec.fixture_path, reseal_fixture(claimed_run, admission_spec),
                  "semantic field drift|synthetic registration is already claimed|schema rejected fixture"))
    revocation_drift = copy.deepcopy(admission)
    revocation_drift["checkpoint_input"]["observed_revocation_epoch"] = 2
    cases.append((admission_spec.fixture_path, reseal_fixture(revocation_drift, admission_spec),
                  "semantic field drift|external revocation epoch binding mismatch"))
    zero_checkpoint_head = copy.deepcopy(admission)
    zero_checkpoint_head["checkpoint_input"]["checkpoint_head_sha256"] = "0" * 64
    cases.append((admission_spec.fixture_path,
                  reseal_fixture(zero_checkpoint_head, admission_spec),
                  "invalid or zero SHA-256 field|schema rejected fixture"))
    zero_registration_provenance = copy.deepcopy(admission)
    zero_registration_provenance["external_registration"]["provenance_receipt_sha256"] = "0" * 64
    cases.append((admission_spec.fixture_path,
                  reseal_fixture(zero_registration_provenance, admission_spec),
                  "invalid or zero SHA-256 field|schema rejected fixture"))

    for path, key in (
        (CONTRACT_PATH, "live_execution_authorized"),
        (CONTRACT_PATH, "existing_s19_signature_authorizes_s21a"),
        (STATUS_PATH, "real_live_adapter_present"),
        (SUCCESSOR_PATH, "candidate_supplied_expected_values_authoritative"),
        (SUCCESSOR_PATH, "live_execution_may_begin"),
        (SUCCESSOR_PATH, "provider_or_production_authority"),
    ):
        _, document = load_json(repo, path)
        mutated_document = copy.deepcopy(document)
        require(mutate_first_named(mutated_document, key, True),
                f"control-document KAT field absent: {key}")
        cases.append((path, canonical_bytes(mutated_document) + b"\n",
                      "fail-closed field became true|semantic field drift"))

    for path, key in (
        (CONTRACT_PATH, "repository_public_kat_key_id_denied_for_real_anchor"),
        (CONTRACT_PATH, "repository_public_kat_public_key_denied_for_real_anchor"),
        (STATUS_PATH, "real_anchor_repository_public_kat_key_id_and_material_denylist_enforced"),
        (SUCCESSOR_PATH, "repository_public_kat_key_id_and_material_denied_for_real_anchor"),
        (SUCCESSOR_PATH, "forbids_repository_public_kat_key_id_or_material_as_real_owner_anchor"),
    ):
        _, document = load_json(repo, path)
        mutated_document = copy.deepcopy(document)
        require(mutate_first_named(mutated_document, key, False),
                f"denylist KAT field absent: {key}")
        cases.append((path, canonical_bytes(mutated_document) + b"\n", "semantic field drift"))

    anchor_schema_for_denylist = copy.deepcopy(loaded["owner-trust-anchor"][1])
    anchor_schema_for_denylist["allOf"][0]["else"]["properties"]["key_binding"].pop("not")
    cases.append(
        (
            anchor_spec.schema_path,
            canonical_bytes(anchor_schema_for_denylist) + b"\n",
            "anchor schema accepts real repository public KAT key id",
        )
    )
    wrong_anchor = copy.deepcopy(envelope)
    require(mutate_first_named(wrong_anchor, "anchor_document_sha256", "f" * 64),
            "trust-anchor binding KAT field absent")
    cases.append((envelope_spec.fixture_path, reseal_fixture(wrong_anchor, envelope_spec), "trust-anchor binding mismatch"))

    rust = read_bytes(repo, S21A_RUST_PATH)
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(
                b'S21A_SIDE_EFFECTS_UNLOCKED: &str = "NONE"',
                b'S21A_SIDE_EFFECTS_UNLOCKED: &str = "LIVE"',
                1,
            ),
            "Rust implementation marker absent",
        )
    )
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(
                b"S21A_EXTERNAL_INPUT_DIGEST_CROSS_BINDING_IMPLEMENTED: bool = true",
                b"S21A_EXTERNAL_INPUT_DIGEST_CROSS_BINDING_IMPLEMENTED: bool = false",
                1,
            ),
            "Rust implementation marker absent",
        )
    )
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(b"previous_revision.checked_add(1)",
                         b"previous_revision.checked_add(2)", 1),
            "Rust fail-closed relation absent",
        )
    )
    for function_name in (
        b"parse_s21_external_input_admission_v1",
        b"build_s21_external_input_admission_v1",
        b"verify_s21_external_input_admission_v1",
    ):
        cases.append(
            (
                S21A_RUST_PATH,
                rust.replace(b"fn " + function_name, b"fn disabled_" + function_name, 1),
                "Rust fail-closed relation absent",
            )
        )
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(b"value.len() <= 96", b"value.len() <= 97", 1),
            "Rust fail-closed relation absent",
        )
    )
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(
                b"key_version > u64::from(u32::MAX)",
                b"key_version > u64::MAX",
                1,
            ),
            "Rust owner key-version u32 bounds drift",
        )
    )
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(
                b"fn s21a_repository_synthetic_admission_kat_parses_and_roundtrips_exactly",
                b"fn s21a_repository_synthetic_admission_kat_was_removed",
                1,
            ),
            "S21A directed Rust KAT catalog drift",
        )
    )
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(
                b"anchor.key_binding.key_id == S21A_REPOSITORY_PUBLIC_KAT_KEY_ID",
                b"anchor.key_binding.key_id != S21A_REPOSITORY_PUBLIC_KAT_KEY_ID",
                1,
            ),
            "Rust fail-closed relation absent",
        )
    )
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(
                b"public_key == repository_public_kat_key",
                b"public_key != repository_public_kat_key",
                1,
            ),
            "Rust fail-closed relation absent",
        )
    )
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(
                b"Ed25519KeyPair::generate_pkcs8(&SystemRandom::new())",
                b"Ed25519KeyPair::disabled_ephemeral_generation(&SystemRandom::new())",
                1,
            ),
            "ephemeral test key generation absent",
        )
    )
    cases.append(
        (
            S21A_RUST_PATH,
            rust + b"\nconst RFC8032_SEED: () = ();\n",
            "RFC8032 private test seed symbol present",
        )
    )
    gate = read_bytes(repo, GATE_PATH)
    cases.append(
        (
            GATE_PATH,
            gate.replace(b"--ro-bind / /", b"--bind / /", 1),
            "S21A source gate safety token absent|S21A source gate root is writable",
        )
    )
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(b"(1, None) => true", b"(1, None) => false", 1),
            "Rust fail-closed relation absent",
        )
    )
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(b"|| !security_digests_valid", b"|| false", 1),
            "Rust fail-closed relation absent",
        )
    )
    cases.append(
        (
            S21A_RUST_PATH,
            rust.replace(
                b"creator_binary_sha256 != facts.runtime.runner_binary_sha256",
                b"creator_binary_sha256 == facts.runtime.runner_binary_sha256",
                1,
            ),
            "Rust fail-closed relation absent",
        )
    )
    require(all(read_bytes(repo, path) != mutated for path, mutated, _ in cases),
            "one or more mutation cases are no-ops")
    return cases


def validate_bundle(
    repo: Path, overrides: Mapping[str, bytes] | None = None
) -> list[tuple[str, str]]:
    fixtures, receipts = validate_schema_fixtures(repo, overrides)
    cross_binding_count = validate_cross_bindings(repo, fixtures, overrides)
    rust_test_count = validate_rust(repo, overrides)
    validate_control_documents(repo, overrides)
    validate_docs(repo, overrides)
    validate_source_gate(repo, overrides)
    rows: list[tuple[str, str]] = [
        ("schema", "agent_bridge.memory_temporal_owned_lab_final_refreeze_external_input_admission_s21a.check.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("implementation_mode", MODE),
        ("baseline_commit", BASELINE_COMMIT),
        ("baseline_tree", BASELINE_TREE),
        ("s20b_source_commit", S20B_SOURCE_COMMIT),
        ("s20b_source_tree", S20B_SOURCE_TREE),
        ("s20b_integrated_archive_sha256", S20B_INTEGRATED_ARCHIVE_SHA256),
        ("feature", FEATURE),
        ("closed_schema_count", "4"),
        ("synthetic_fixture_count", "4"),
        ("independent_refreeze_binding_count", str(cross_binding_count)),
        ("old_s19_signature_domain_accepted", "false"),
        ("candidate_self_authenticated_anchor_accepted", "false"),
        ("same_failure_domain_checkpoint_accepted", "false"),
        ("stale_checkpoint_accepted", "false"),
        ("forked_checkpoint_accepted", "false"),
        ("unknown_checkpoint_accepted", "false"),
        ("runner_created_registration_accepted", "false"),
        ("retry_or_implicit_rerun_allowed", "false"),
        ("repository_public_kat_key_id_accepted_as_real_anchor", "false"),
        ("repository_public_kat_public_key_accepted_as_real_anchor", "false"),
        ("committed_rfc8032_private_seed_present", "false"),
        ("s21a_rust_test_count", str(rust_test_count)),
        ("self_test_mutation_count", str(len(mutation_cases(repo))) if overrides is None else "DEFERRED"),
        ("live_canary", "NOT_RUN"),
        ("side_effects_unlocked", "NONE"),
        ("future_s21b_preapproved", "false"),
    ]
    for key in sorted(receipts):
        rows.append((key, receipts[key]))
    for key, relative in ARTIFACT_ROWS:
        rows.append((key, sha256(read_bytes(repo, relative, overrides))))
    return rows


def expect_failure(repo: Path, relative: str, mutated: bytes, expected: str) -> None:
    try:
        validate_bundle(repo, {relative: mutated})
    except CheckFailure as exc:
        accepted = expected.split("|")
        if expected in {"fail-closed field became true", "semantic field drift"}:
            accepted.append("schema rejected fixture")
        require(
            any(message in str(exc) for message in accepted),
            f"mutation failed for wrong reason ({relative}): {exc}",
        )
        return
    raise CheckFailure(f"self-test mutation was accepted: {relative}")


def run_self_test(repo: Path, seed: int) -> None:
    validate_bundle(repo)
    cases = mutation_cases(repo)
    random.Random(seed).shuffle(cases)
    for relative, mutated, expected in cases:
        expect_failure(repo, relative, mutated, expected)


def render(rows: list[tuple[str, str]]) -> str:
    require(len(rows) == len({key for key, _ in rows}), "duplicate receipt key")
    for key, value in rows:
        require("\t" not in key + value and "\n" not in key + value, "invalid receipt field")
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--seed", type=int, default=21_001)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    require(repo.is_dir() and not repo.is_symlink(), "repository root is not canonical")
    if args.self_test:
        run_self_test(repo, args.seed)
    sys.stdout.write(render(validate_bundle(repo)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print(f"S21A final-refreeze checker failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
