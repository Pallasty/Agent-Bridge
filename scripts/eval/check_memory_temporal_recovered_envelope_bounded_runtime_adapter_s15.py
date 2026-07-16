#!/usr/bin/env python3
"""Fail-closed checker for the private S15 bounded runtime-adapter kernel.

This checker is intentionally independent of the Rust test implementation.  It
freezes the exact Cargo feature edge, the only two changes allowed in the S14
source, the private S15 module surface, closed JSON contracts, frozen S14 known
record receipt, and negative production/runtime claims.  A passing receipt is
synthetic preregistration evidence only; it is not durability, currentness,
object-selection authorization, admission, or deployment evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

STATUS = (
    "RECOVERED_ENVELOPE_BOUNDED_RUNTIME_ADAPTER_KERNEL_PREREGISTERED_"
    "SYNTHETIC_ONE_SHOT_EXACT_READ_FIXED_BUFFER_HISTORICAL_ONLY_NO_"
    "CONCRETE_TRANSPORT_NO_DURABILITY_PROOF_NO_CURRENTNESS_NO_ADMISSION"
)
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s15-recovered-envelope-bounded-runtime-adapter-synthetic"
S14_FEATURE = "temporal-evidence-s14-recovered-envelope-source-synthetic"
S13_FEATURE = "temporal-evidence-s13-recovered-envelope-delivery-synthetic"
S14_SOURCE_COMMIT = "cc8143e5ef2cc8cf00da0627f7321f714369ebb9"
S14_INTEGRATION_COMMIT = "b2dd4706bd34155a1edd6d6472ee0b32a3bb232b"
S14_SOURCE_SHA256 = "751b746180a8bd03e4f714527a703d4aa81ee6ccc861d65ecd02921972933255"
S14_CONTRACT_SHA256 = "ba10e9f433294e8d9f50f3342f04ec140ff2f7fce8e3f2c02130a5a0b4f92899"
S14_EXPECTED_SHA256 = "1105dbb42cc0f24578a526a039dd31363a92874f8c9e188b7c1aaddcc84ae4b4"

POLICY = "agent-bridge/track-b/recovered-envelope-bounded-runtime-adapter/v1"
PROFILE = "PRIVATE_ONE_SHOT_EXACT_OPEN_FIXED_BUFFER_RAW_BYTES_UNTRUSTED_COMPLETION_HISTORICAL_ONLY"
FIXED_BUFFER_BYTES = 16_384
MAX_DATA_STEPS = 1_024
MAX_TRANSPORT_READ_CALLS = 1_025
LOOKUP_COMMITMENT_DOMAIN = (
    b"agent-bridge/track-b/recovered-envelope-bounded-runtime-adapter/exact-lookup/v1"
)

STORE_CARGO_PATH = "crates/store/Cargo.toml"
S14_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "recovered_s9_decision_reverification/recovered_envelope_delivery/"
    "recovered_envelope_source.rs"
)
S15_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "recovered_s9_decision_reverification/recovered_envelope_delivery/"
    "recovered_envelope_source/bounded_runtime_adapter.rs"
)
CONTRACT_PATH = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-recovered-envelope-bounded-runtime-adapter-s15-v0.json"
)
GATE_PATH = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-successor-admission-gate-s15-v0.json"
)
DESIGN_PATH = (
    "docs/design/"
    "MEMORY_TEMPORAL_RECOVERED_ENVELOPE_BOUNDED_RUNTIME_ADAPTER_S15_2026_07_15.md"
)
S14_CONTRACT_PATH = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-recovered-envelope-source-s14-v0.json"
)
S14_EXPECTED_PATH = (
    "scripts/eval/fixtures/"
    "memory_temporal_recovered_envelope_source_s14.expected.v0.tsv"
)

KNOWN_VECTOR = {
    "exact_lookup_commitment_sha256": "866e016ce631433e3e272d0858906f3c76c67204cd74b73ab11b7353e57eae00",
    "historical_chain_sha256": "afb8aa4945f0e491937f75233c621d52f1bcc1307e6d497352fd9d0fc79b7204",
    "historical_source_chain_sha256": "d29da2a081b09b2b124298eae40b15ada555196cc5e3fd52d8e4dfadf3f2149b",
    "record_len": 5_494,
    "record_sha256": "a788ec43fefa76e393d77c86bbfabeef7d2ae8c5499bb834c1945af5cbb1b3cd",
    "s13_envelope_sha256": "5d74c7a300abe503b9a79c796394faa23de0c64f22fb80902294fa0654ee15d9",
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

# Filled only with exact, non-ignored Rust test names.  The architecture module
# is frozen against this tuple after its implementation lands.
TEST_NAMES: tuple[str, ...] = (
    "s15_lookup_commitment_and_full_historical_chain_are_stable",
    "s15_every_two_chunk_cut_preserves_exact_bytes",
    "s15_every_partial_cut_failure_is_terminal_without_retry",
    "s15_second_read_and_opening_reentry_are_terminal_without_second_open",
    "s15_real_open_or_read_callback_reentry_cannot_restore_outer_success",
    "s15_open_and_read_failure_matrix_never_retries",
    "s15_zero_progress_oversize_and_empty_completion_fail",
    "s15_1024_data_steps_then_completion_passes_and_1025th_data_fails",
    "s15_total_cap_exact_passes_and_cap_plus_one_fails_before_completion",
    "s15_each_completion_binding_mismatch_fails_closed",
    "s15_tampered_or_mixed_bytes_fail_even_with_locally_matching_completion",
    "s15_valid_completion_cannot_bypass_unchanged_s14_record_verification",
    "s15_debug_redacts_transport_completion_and_adapter_state",
)

S15_CHILD_GLUE = (
    '#[cfg(feature = "temporal-evidence-s15-recovered-envelope-bounded-runtime-adapter-synthetic")]\n'
    "mod bounded_runtime_adapter;\n\n"
)
S15_TEST_GLUE = (
    '    #[cfg(feature = "temporal-evidence-s15-recovered-envelope-bounded-runtime-adapter-synthetic")]\n'
    "    pub(super) fn s15_fixture_parts() -> (\n"
    "        Vec<u8>,\n"
    "        ExactRecoveredEnvelopeLookupV1,\n"
    "        ExternalRecoveredEnvelopeSourceTrustPermitV1,\n"
    "        Fixture,\n"
    "        ExternalOperationRecoveryTrustPermitV1,\n"
    "    ) {\n"
    "        let fixture = source_fixture();\n"
    "        let (record, _, _) = fixture.record.materialize();\n"
    "        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&record));\n"
    "        let permit = source_permit_for(&fixture.record.claim);\n"
    "        (record, lookup, permit, fixture.base, fixture.s10_permit)\n"
    "    }\n\n"
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


def parse_frozen_s14_receipt(repo: Path) -> dict[str, str]:
    require(
        artifact_sha256(repo, S14_EXPECTED_PATH) == S14_EXPECTED_SHA256,
        "frozen S14 expected receipt digest drift",
    )
    rows: dict[str, str] = {}
    text = read_text(repo, S14_EXPECTED_PATH)
    require(text.endswith("\n"), "frozen S14 receipt missing final newline")
    for line in text.splitlines():
        parts = line.split("\t")
        require(len(parts) == 2 and all(parts), "malformed frozen S14 TSV row")
        key, value = parts
        require(key not in rows, f"duplicate frozen S14 TSV key: {key}")
        rows[key] = value
    for key, expected in (
        ("known_record_len", str(KNOWN_VECTOR["record_len"])),
        ("known_record_sha256", str(KNOWN_VECTOR["record_sha256"])),
        ("known_s13_envelope_sha256", str(KNOWN_VECTOR["s13_envelope_sha256"])),
        ("known_historical_chain_sha256", str(KNOWN_VECTOR["historical_chain_sha256"])),
        (
            "known_historical_source_chain_sha256",
            str(KNOWN_VECTOR["historical_source_chain_sha256"]),
        ),
    ):
        require(rows.get(key) == expected, f"frozen S14 known answer drift: {key}")
    return rows


def frame(value: bytes) -> bytes:
    return len(value).to_bytes(8, "big") + value


def independent_lookup_commitment() -> bytes:
    fields = (
        LOOKUP_COMMITMENT_DOMAIN,
        POLICY.encode("ascii"),
        PROFILE.encode("ascii"),
        bytes.fromhex(S14_CONTRACT_SHA256),
        b"durable-source-profile-a",
        b"durable-source-namespace-a",
        b"agent-bridge",
        b"ab-store-restore-admission",
        b"durable-source-cluster-a",
        bytes([0x81]) * 32,
        bytes([0x82]) * 32,
        bytes([0x83]) * 32,
        (17).to_bytes(8, "big"),
        bytes.fromhex(str(KNOWN_VECTOR["record_sha256"])),
    )
    require(len(fields) == 14, "lookup commitment field cardinality drift")
    return hashlib.sha256(b"".join(frame(field) for field in fields)).digest()


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
        values = features.get(feature, [])
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            candidate = value.split("/", 1)[0].removeprefix("dep:")
            if candidate in features:
                pending.append(candidate)
    return False


def remove_exact_once(text: str, snippet: str, label: str) -> str:
    require(text.count(snippet) == 1, f"{label} is missing or duplicated")
    return text.replace(snippet, "", 1)


def check_glue(repo: Path) -> None:
    cargo = tomllib.loads(read_text(repo, STORE_CARGO_PATH))
    features = cargo.get("features")
    require(type(features) is dict, "Cargo features table missing")
    require_exact(features.get(FEATURE), [S14_FEATURE], "S15 feature dependency drift")
    require_exact(features.get(S14_FEATURE), [S13_FEATURE], "S14 feature dependency drift")
    defaults = features.get("default", [])
    require(type(defaults) is list, "Cargo default feature list missing")
    require(not feature_is_reachable(features, defaults, FEATURE), "S15 became default-reachable")
    require(not feature_is_reachable(features, defaults, S14_FEATURE), "S14 became default-reachable")

    source = read_text(repo, S14_SOURCE_PATH)
    restored = remove_exact_once(source, S15_CHILD_GLUE, "S15 private child glue")
    restored = remove_exact_once(restored, S15_TEST_GLUE, "S15 cfg-test fixture glue")
    require(
        hashlib.sha256(restored.encode("utf-8")).hexdigest() == S14_SOURCE_SHA256,
        "S14 source changed beyond exact S15 child/test glue",
    )
    require("pub mod bounded_runtime_adapter" not in source, "S15 child module became public")
    require("pub(crate) mod bounded_runtime_adapter" not in source, "S15 child module became crate-public")
    require("pub(super) mod bounded_runtime_adapter" not in source, "S15 child module became parent-public")


def check_contract(repo: Path) -> None:
    contract = load_json(repo, CONTRACT_PATH)
    require_exact(
        set(contract),
        {
            "adapter_kernel", "boundary", "completion_receipt", "decision",
            "dependency", "known_vector", "negative_evidence", "operational_gap_codes",
            "policy", "profile", "remaining_gap_codes", "schema", "state_machine",
            "status", "test_matrix",
        },
        "contract root is not closed",
    )
    require_exact(contract["schema"], "agent_bridge.memory_temporal_recovered_envelope_bounded_runtime_adapter_s15.v0", "contract schema drift")
    require_exact(contract["status"], STATUS, "contract status drift")
    require_exact(contract["decision"], DECISION, "contract decision drift")
    require_exact(contract["policy"], POLICY, "contract policy drift")
    require_exact(contract["profile"], PROFILE, "contract profile drift")
    require_exact(
        contract["dependency"],
        {
            "feature": FEATURE,
            "feature_default_enabled": False,
            "frozen_s14_contract_sha256": S14_CONTRACT_SHA256,
            "frozen_s14_integration_commit": S14_INTEGRATION_COMMIT,
            "frozen_s14_source_commit": S14_SOURCE_COMMIT,
            "requires_feature": S14_FEATURE,
            "s14_current_gate_claimed_pass_at_s15_head": False,
            "s14_frozen_integrated_gate_replayed": True,
            "s14_source_change_is_exact_production_child_and_test_fixture_glue_only": True,
        },
        "contract dependency drift",
    )
    require_exact(
        contract["adapter_kernel"],
        {
            "backend_can_replace_or_generate_lookup": False,
            "backend_returns_preallocated_vec_or_box": False,
            "caller_owned_fixed_buffer": True,
            "concrete_transport_implementation_present": False,
            "exact_open_count_per_adapter": 1,
            "fixed_buffer_bytes": FIXED_BUFFER_BYTES,
            "max_data_steps": MAX_DATA_STEPS,
            "max_transport_read_calls": MAX_TRANSPORT_READ_CALLS,
            "partial_bytes_can_produce_historical_result": False,
            "private_sealed_transport": True,
            "raw_bytes_forwarded_without_normalization_or_reframing": True,
            "retry_cache_fallback_list_latest_range_write_or_delete_available": False,
            "runtime_shaped_adapter_kernel_preregistered": True,
            "second_read_or_reentry_available": False,
            "terminal_completion_call_counted_as_data_step": False,
        },
        "adapter-kernel contract drift",
    )
    require_exact(
        contract["boundary"],
        {
            "bridge_or_state_store_caller": False,
            "concrete_runtime_bounded_source_adapter_available": False,
            "currentness_or_admission_issued": False,
            "external_durable_source_runtime_available": False,
            "owner_authorized_runtime_object_selection_available": False,
            "production_transport_constructor_present": False,
            "runtime_shaped_adapter_kernel_preregistered": True,
            "side_effects_unlocked": "NONE",
        },
        "contract boundary drift",
    )
    require_exact(
        contract["completion_receipt"],
        {
            "authenticated_or_owner_authorized": False,
            "binds_domain_separated_exact_lookup_commitment": True,
            "binds_exact_object_revision": True,
            "binds_locally_computed_length_and_sha256": True,
            "durability_or_currentness_proof": False,
            "lookup_commitment_domain": LOOKUP_COMMITMENT_DOMAIN.decode("ascii"),
            "lookup_commitment_encoding": "u64be_length_prefixed_exact_field_order",
            "lookup_commitment_fields": [
                "domain", "policy", "profile", "s14_contract_sha256_raw",
                "source_profile_id", "source_namespace_id", "tenant_id", "audience",
                "source_cluster_id", "source_incarnation", "source_generation_id",
                "object_id", "object_revision_u64be", "expected_record_sha256",
            ],
            "request_lookup_frozen_before_open": True,
            "response_metadata_compared_but_never_adopted": True,
            "untrusted_consistency_metadata_only": True,
        },
        "completion receipt drift",
    )
    require_exact(contract["known_vector"], KNOWN_VECTOR, "known R/chain vector drift")
    require(
        independent_lookup_commitment().hex() == KNOWN_VECTOR["exact_lookup_commitment_sha256"],
        "independent exact-lookup KAT drift",
    )
    require_exact(
        contract["negative_evidence"],
        {
            "adapter_instance_one_shot_is_global_replay_fence": False,
            "completion_receipt_proves_backend_followed_exact_lookup": False,
            "completion_receipt_proves_external_durability": False,
            "completion_receipt_proves_provider_memory_or_liveness_bounds": False,
            "exact_valid_read_is_current_chain_head": False,
            "feature_flag_is_authorization": False,
            "fixed_ingress_buffer_is_backend_allocation_bound": False,
            "historical_source_chain_is_admission": False,
            "source_signer_key_independence_enforced_or_attested": False,
            "step_budget_is_wall_clock_timeout": False,
        },
        "negative-evidence drift",
    )
    require_exact(
        contract["state_machine"],
        {
            "failure_is_terminal": True,
            "states": ["FRESH", "OPENING", "STREAMING", "COMPLETED", "TERMINAL_FAILED"],
            "terminal_failures": [
                "REENTRY_OR_SECOND_READ", "OPEN_FAILURE", "READ_FAILURE", "ZERO_PROGRESS",
                "REPORTED_LENGTH_EXCEEDS_BUFFER", "CHECKED_LENGTH_OR_SINK_BOUND_FAILURE",
                "STEP_BUDGET_EXHAUSTED", "EMPTY_COMPLETION", "LOOKUP_COMMITMENT_MISMATCH",
                "OBJECT_REVISION_MISMATCH", "LOCAL_LENGTH_MISMATCH", "LOCAL_DIGEST_MISMATCH",
                "EXPECTED_RECORD_DIGEST_MISMATCH",
            ],
        },
        "state-machine contract drift",
    )
    require_exact(contract["operational_gap_codes"], list(OPERATIONAL_GAPS), "contract operational gaps drift")
    require_exact(contract["remaining_gap_codes"], list(REMAINING_GAPS), "contract remaining gaps drift")
    require_exact(
        contract["test_matrix"],
        {
            "all_chunk_cuts_and_partial_failures_no_retry": True,
            "backend_metadata_cannot_replace_request_lookup": True,
            "completion_lookup_revision_length_and_digest_mismatch_reject": True,
            "debug_redacted_move_only_no_serde": True,
            "empty_zero_progress_oversize_and_step_budget_reject": True,
            "exactly_one_open_and_completion": True,
            "fixed_buffer_and_total_cap_boundaries": True,
            "known_s14_record_and_historical_chain_unchanged": True,
            "mixed_snapshot_and_forged_completion_reject": True,
            "original_s14_s13_s12_regressions_unchanged": True,
            "second_read_and_reentry_terminal": True,
            "static_no_runtime_or_admission_wiring": True,
        },
        "contract test matrix drift",
    )


def check_successor_gate(repo: Path) -> None:
    gate = load_json(repo, GATE_PATH)
    require_exact(
        set(gate),
        {
            "admission", "authorization_semantics", "boundary", "decision",
            "local_preregistration", "next_preregistered_stage", "operational_gap_codes",
            "remaining_gap_codes", "required_production_successor_identity", "schema", "status",
        },
        "successor gate root is not closed",
    )
    require_exact(gate["schema"], "agent_bridge.memory_temporal_successor_admission_gate_s15.v0", "successor schema drift")
    require_exact(gate["status"], STATUS, "successor status drift")
    require_exact(gate["decision"], DECISION, "successor decision drift")
    require_exact(gate["operational_gap_codes"], list(OPERATIONAL_GAPS), "successor operational gaps drift")
    require_exact(gate["remaining_gap_codes"], list(REMAINING_GAPS), "successor remaining gaps drift")
    require_exact(
        gate["admission"],
        {
            "bridge_or_state_store_enabled": False, "currentness_token_issued": False,
            "owner_approval_receipt": None, "production_authorized": False,
            "successor_payload_admitted": False, "transport_enabled": False,
        },
        "successor admission drift",
    )
    require_exact(
        gate["authorization_semantics"],
        {
            "completion_receipt_is_authenticated_durability_evidence": False,
            "exact_lookup_is_owner_authorized_runtime_object_selection": False,
            "feature_flag_is_authorization": False,
            "historical_source_chain_is_admission_capability": False,
            "one_shot_adapter_is_global_replay_fence": False,
            "runtime_shaped_kernel_is_concrete_runtime_deployment": False,
            "source_signer_key_independence_enforced_or_attested": False,
            "source_revision_is_currentness": False,
        },
        "successor authorization semantics drift",
    )
    require_exact(
        gate["boundary"],
        {
            "capture_provenance_runtime_attested": False,
            "concrete_runtime_bounded_source_adapter_available": False,
            "currentness_and_consume_atomic": False,
            "external_durable_source_runtime_available": False,
            "owner_pinned_production_source_permit_available": False,
            "provider_rollback_and_split_brain_proved": False,
            "runtime_recovered_bytes_available": False,
            "runtime_s10_delivery_available": False,
            "runtime_shaped_bounded_adapter_kernel_preregistered": True,
        },
        "successor boundary drift",
    )
    require_exact(
        gate["local_preregistration"],
        {
            "exact_request_frozen_before_open": True,
            "fixed_buffer_and_step_budget": True,
            "private_sealed_one_shot_transport": True,
            "raw_bytes_only_into_unchanged_s14_sink": True,
            "s14_strict_decode_and_local_reverification_unchanged": True,
            "untrusted_completion_cross_checks_local_length_and_digest": True,
        },
        "successor local preregistration drift",
    )
    require_exact(
        gate["next_preregistered_stage"],
        {
            "external_provider_observations_count_as_zero": True,
            "identity": "S16_DURABILITY_FAULT_MODEL_AGAINST_FROZEN_S15_STATE_SURFACE",
            "must_cover_ack_and_commit_uncertainty": True,
            "must_cover_crash_restart_each_state_cut": True,
            "must_cover_partial_torn_and_manifest_ordering": True,
            "must_cover_rollback_equivocation_split_brain_and_witness_loss": True,
            "simulated_rows_are_not_durability_evidence": True,
        },
        "successor S16 preregistration drift",
    )
    require_exact(
        gate["required_production_successor_identity"],
        {
            "admission_receipt": None,
            "crash_restart_external_durability_evidence": True,
            "currentness_and_consume_atomicity": True,
            "owner_authorized_exact_object_selection": True,
            "owner_pinned_production_source_and_authority_permits": True,
            "provider_and_source_rollback_split_brain_evidence": True,
            "runtime_capture_attestation_and_signer_custody": True,
            "runtime_capture_signer_role_separation_evidence": True,
            "runtime_concrete_bounded_exact_source_adapter": True,
            "runtime_s10_delivery_and_local_reverification": True,
        },
        "successor production identity drift",
    )


def rust_test_names(source: str) -> tuple[str, ...]:
    pattern = re.compile(r"(?m)^\s*#\[test\]\s*\n\s*fn (s15_[a-z0-9_]+)\s*\(")
    names = tuple(pattern.findall(source))
    require(len(names) == len(set(names)), "duplicate S15 Rust test name")
    return names


def strip_rust_comments_and_literals(source: str) -> str:
    # This is a conservative lexical screen, not a Rust parser.  Exact module
    # hashing and Cargo compilation in the outer gate provide the authoritative
    # syntax check; this removes prose so forbidden production API names cannot
    # be satisfied merely by comments or strings.
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", " ", source)
    source = re.sub(r'r#+".*?"#+', '""', source, flags=re.DOTALL)
    source = re.sub(r'"(?:\\.|[^"\\])*"', '""', source, flags=re.DOTALL)
    return source


def require_move_only_type(production: str, type_name: str) -> None:
    declaration = re.search(
        rf"((?:#\[[^\]]+\]\s*)*)struct\s+{re.escape(type_name)}(?:<[^>]+>)?\b",
        production,
    )
    require(declaration is not None, f"missing move-only type: {type_name}")
    require(
        "Clone" not in declaration.group(1) and "Copy" not in declaration.group(1),
        f"{type_name} became Clone/Copy",
    )
    clone_impl = re.search(
        rf"impl(?:<[^>]+>)?\s+(?:Clone|Copy)\s+for\s+{re.escape(type_name)}\b",
        production,
    )
    require(clone_impl is None, f"{type_name} gained a Clone/Copy implementation")


def check_rust(repo: Path) -> int:
    source = read_text(repo, S15_SOURCE_PATH)
    require("#[cfg(test)]\nmod tests {" in source, "S15 test module boundary missing")
    production, _tests = source.split("#[cfg(test)]\nmod tests {", 1)
    lexical = strip_rust_comments_and_literals(production)
    require_move_only_type(production, "RuntimeExactReadCompletionV1")
    require_move_only_type(production, "BoundedRuntimeRecoveredEnvelopeAdapterV1")
    constructor = "    #[cfg(test)]\n    fn new(transport: T) -> Self {"
    require(source.count(constructor) == 1, "S15 test-only adapter constructor cfg drift")
    require(source.count("fn new(transport: T) -> Self") == 1, "unexpected S15 adapter constructor")
    public_surface = re.findall(r"\bpub(?:\([^)]*\))?\s[^\n]*", lexical)
    require_exact(public_surface, ["pub(super) trait Sealed {}"], "S15 production visibility drift")
    for pattern, label in (
        (r"\bStateStore\b", "StateStore"),
        (r"\bab_bridge\b", "Bridge crate"),
        (r"\bstd\s*::\s*fs\b", "filesystem"),
        (r"\bstd\s*::\s*net\b", "network"),
        (r"\btokio\b|\breqwest\b|\bhyper\b", "network/async runtime"),
        (r"\bsqlx\b|\brusqlite\b|\brocksdb\b|\bsled\b", "database"),
        (r"\b(?:list|latest|retry|fallback|cache|write|delete|range)[A-Za-z0-9_]*\s*\(", "forbidden transport operation"),
    ):
        require(re.search(pattern, lexical, flags=re.IGNORECASE) is None, f"S15 production {label} wiring detected")
    for pattern, label in (
        (r"\bunsafe\b", "unsafe code"),
        (r"\bstd\s*::\s*thread\b|\bthread\s*::", "thread runtime"),
        (r"\bSystemTime\b|\bInstant\b", "clock/currentness source"),
        (r"\bserde\b|\bSerialize\b|\bDeserialize\b", "serde surface"),
        (
            r"impl\s+RuntimeExactRecoveredEnvelopeTransportV1\s+for",
            "concrete production transport implementation",
        ),
        (
            r"recover_historical_from_external_source_v1\s*\(",
            "production recovery caller",
        ),
    ):
        require(re.search(pattern, lexical) is None, f"S15 production {label} detected")
    for token in (
        "const MAX_RUNTIME_READ_BUFFER_BYTES: usize = 16 * 1024;",
        "const MAX_RUNTIME_DATA_STEPS: usize = 1024;",
        "trait RuntimeExactRecoveredEnvelopeTransportV1",
        "enum AdapterStateV1",
        "TerminalFailed",
        "read_into",
        "complete",
        "recover_historical_from_external_source_v1",
    ):
        require(token in source, f"S15 Rust contract token drift: {token}")
    kat_match = re.search(
        r"const LOOKUP_KAT: \[u8; 32\] = \[(.*?)\];",
        source,
        flags=re.DOTALL,
    )
    require(kat_match is not None, "S15 Rust lookup KAT missing")
    kat_bytes = bytes(int(value, 16) for value in re.findall(r"0x([0-9a-f]{2})", kat_match.group(1)))
    require(len(kat_bytes) == 32, "S15 Rust lookup KAT width drift")
    require(kat_bytes == independent_lookup_commitment(), "S15 Rust lookup KAT differs from independent reconstruction")
    names = rust_test_names(source)
    require(TEST_NAMES, "S15 Rust test-name freeze not initialized")
    require_exact(names, TEST_NAMES, "S15 Rust test inventory drift")
    require("#[ignore" not in source, "ignored S15 test forbidden")

    bridge_root = repo / "crates/bridge"
    for path in bridge_root.rglob("*.rs"):
        text = path.read_text(encoding="utf-8")
        require(FEATURE not in text, f"S15 feature wired into Bridge: {path.relative_to(repo)}")
        require("bounded_runtime_adapter" not in text, f"S15 adapter wired into Bridge: {path.relative_to(repo)}")
    return len(names)


def check_design(repo: Path) -> None:
    design = read_text(repo, DESIGN_PATH)
    for required in (
        "Decision: `BLOCKED_FAIL_CLOSED`",
        "It is not itself\ndurability evidence.",
        "does **not** claim that the current HEAD passes the S14\nhistorical-descendant gate",
        "test-only fixture seam independently,\nreplays the frozen S14 integrated gate",
        "no filesystem, network, database, provider SDK, credential",
        "NOT durability - NOT currentness - NOT admission",
        "The one-shot adapter instance is only a local misuse guard; it is not a\nglobal replay fence.",
        "simulated ledger and count as zero external durability\nobservations",
        "adapter and completion value are private, non-`Clone`, non-serde values; their\n`Debug` output is redacted",
    ):
        require(required in design, f"design negative claim drift: {required}")


def receipt(repo: Path, s15_tests: int) -> str:
    rows: list[tuple[str, str]] = [
        ("schema", "agent_bridge.memory_temporal_recovered_envelope_bounded_runtime_adapter_s15_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("feature", FEATURE),
        ("depends_on_feature", S14_FEATURE),
        ("feature_default_reachable", "false"),
        ("policy", POLICY),
        ("profile", PROFILE),
        ("fixed_buffer_bytes", str(FIXED_BUFFER_BYTES)),
        ("max_data_steps", str(MAX_DATA_STEPS)),
        ("max_transport_read_calls", str(MAX_TRANSPORT_READ_CALLS)),
        ("known_exact_lookup_commitment_sha256", str(KNOWN_VECTOR["exact_lookup_commitment_sha256"])),
        ("known_record_len", str(KNOWN_VECTOR["record_len"])),
        ("known_record_sha256", str(KNOWN_VECTOR["record_sha256"])),
        ("known_s13_envelope_sha256", str(KNOWN_VECTOR["s13_envelope_sha256"])),
        ("known_historical_chain_sha256", str(KNOWN_VECTOR["historical_chain_sha256"])),
        ("known_historical_source_chain_sha256", str(KNOWN_VECTOR["historical_source_chain_sha256"])),
        ("s15_nonignored_rust_tests", str(s15_tests)),
        ("private_sealed_transport", "true"),
        ("one_exact_open_per_adapter", "true"),
        ("caller_owned_fixed_buffer", "true"),
        ("raw_bytes_forwarded_without_reframing", "true"),
        ("untrusted_completion_metadata", "true"),
        ("failure_terminal_no_retry_or_fallback", "true"),
        ("s14_source_exact_child_and_test_glue_only", "true"),
        ("current_s14_gate_claimed_pass", "false"),
        ("frozen_s14_integrated_gate_required", "true"),
        ("concrete_transport_present", "false"),
        ("bridge_or_state_store_caller", "false"),
        ("filesystem_network_or_database_wiring", "false"),
        ("external_durability_proved", "false"),
        ("currentness_or_admission_issued", "false"),
        ("side_effects_unlocked", "NONE"),
        ("operational_gaps", ",".join(OPERATIONAL_GAPS)),
        ("remaining_gaps", ",".join(REMAINING_GAPS)),
    ]
    for label, path in (
        ("contract_sha256", CONTRACT_PATH),
        ("successor_gate_sha256", GATE_PATH),
        ("design_sha256", DESIGN_PATH),
        ("store_cargo_sha256", STORE_CARGO_PATH),
        ("s14_source_with_s15_glue_sha256", S14_SOURCE_PATH),
        ("s15_source_sha256", S15_SOURCE_PATH),
        ("frozen_s14_contract_sha256", S14_CONTRACT_PATH),
        ("frozen_s14_expected_sha256", S14_EXPECTED_PATH),
    ):
        rows.append((label, artifact_sha256(repo, path)))
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--glue-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        check_glue(repo)
        if args.glue_only:
            sys.stdout.write("glue_check\tPASS\n")
            return 0
        require(artifact_sha256(repo, S14_CONTRACT_PATH) == S14_CONTRACT_SHA256, "frozen S14 contract digest drift")
        parse_frozen_s14_receipt(repo)
        check_contract(repo)
        check_successor_gate(repo)
        s15_tests = check_rust(repo)
        check_design(repo)
        sys.stdout.write(receipt(repo, s15_tests))
    except (CheckFailure, OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        print(f"S15_CHECK_FAILED\t{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
