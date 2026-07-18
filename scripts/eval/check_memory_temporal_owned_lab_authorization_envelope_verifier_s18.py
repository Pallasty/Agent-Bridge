#!/usr/bin/env python3
"""Independent S18 contract, schema, canonicalization, and source checker."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import types
from pathlib import Path
from typing import Any, Callable, Iterable


STATUS = (
    "S18_POSITIVE_OWNER_SCHEMA_AND_OFFLINE_SEMANTIC_SIGNATURE_VERIFIER_"
    "IMPLEMENTED_REAL_OWNER_AND_EXECUTION_STILL_BLOCKED"
)
DECISION = (
    "BLOCKED_PENDING_SOURCE_BOUND_RUNNER_REAL_OUT_OF_BAND_TRUST_ANCHOR_"
    "AND_OWNER_SIGNED_UNCLAIMED_ENVELOPE"
)
CANONICAL_PROFILE = (
    "AB_RESTRICTED_CANONICAL_JSON_S18_V1_COMPACT_SORTED_KEYS_"
    "ASCII_VALUES_NO_FLOAT"
)
MESSAGE_DOMAIN = b"agent-bridge/biocortex/owned-lab/owner-authorization/s18/v1"
MESSAGE_PROFILE = "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_32_RAW_PAYLOAD_SHA256"
AUTHORIZATION_ID_DOMAIN = b"agent-bridge/biocortex/owned-lab/owner-authorization-id/s18/v1"
AUTHORIZATION_ID_FORMULA = (
    "SHA256(U32BE(LEN(ID_DOMAIN)) || ID_DOMAIN || U64BE(32) || "
    "SHA256(CANONICAL_PAYLOAD_WITHOUT_AUTHORIZATION_ID_SHA256))"
)
FEATURE = "temporal-evidence-s18-owned-lab-authorization-verifier-synthetic"
BASELINE_CARGO_SHA256 = "26c850a68efcbb9f68c9f457251750cae4aaeaa7ae7c0bcdb068790bc808c04a"
BASELINE_PARENT_MODULE_SHA256 = "b10984e6336c436a0b84548d0f8c9f7ad4537df7b491d4863e1b6545f517f2d1"
EXPECTED_ANCHOR_SCHEMA_CANONICAL_SHA256 = "561bc4f5cedae09dd5c81c17f6f0d249a7b12810f3ef2ec43dc6c8ecd956878e"
EXPECTED_ENVELOPE_SCHEMA_CANONICAL_SHA256 = "036341378d0184d7b06c6a675970e4c501ccfe3709eb548fa43971606a1c86b5"
S19_MANIFEST_BINDINGS = (
    "FINAL_S19_SOURCE_AND_INTEGRATION_COMMITS",
    "RUNNER_SOURCE_BINARY_AND_TOOLCHAIN",
    "OWNER_AUTHORIZATION_VALIDATOR_SOURCE_BINARY_TOOLCHAIN_AND_RULESET",
    "LIVE_OBSERVATION_VALIDATOR_SOURCE_BINARY_TOOLCHAIN_AND_RULESET",
    "INDEPENDENT_EXPECTED_BINDING_BUILDER_SOURCE_BINARY_TOOLCHAIN_AND_RULESET",
    "CAS_LEDGER_SCHEMA_SOURCE_BINARY_AND_TOOLCHAIN",
    "PREFLIGHT_SCHEMA_SOURCE_BINARY_TOOLCHAIN_AND_POLICY",
    "ABSORBING_STOP_LEDGER_SCHEMA_SOURCE_BINARY_TOOLCHAIN_AND_POLICY",
    "POST_RUN_RETENTION_SEMANTIC_BATCH_STOP_CLEANUP_AND_CUSTODY_RECEIPT_SCHEMAS",
    "RECEIPT_VALIDATOR_SOURCE_BINARY_TOOLCHAIN_AND_RULESET",
    "SCHEDULE_ASSIGNMENT_CONTROL_SQLITE_CLASSIFIER_AND_ORACLE",
    "EXACT_F2FS_RESOURCE_SCOPE_DEADLINES_AND_FORBIDDEN_OPERATIONS",
    "CURRENT_REVOCATION_AND_STOP_READ_PROTOCOL",
)

DESIGN_PATH = "docs/design/MEMORY_TEMPORAL_OWNED_LAB_AUTHORIZATION_ENVELOPE_VERIFIER_S18_2026_07_17.md"
CONTRACT_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-authorization-validator-contract-s18-v0.json"
STATUS_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-authorization-validator-status-s18-v0.json"
ANCHOR_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-trust-anchor-schema-s18-v0.json"
ENVELOPE_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-authorization-envelope-schema-s18-v0.json"
SUCCESSOR_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s18-v0.json"
REPORT_PATH = "docs/reports/goal-c-u/2026-07-17-biocortex-ab-track-b-owned-lab-authorization-envelope-verifier-s18.md"
CHECKER_PATH = "scripts/eval/check_memory_temporal_owned_lab_authorization_envelope_verifier_s18.py"
EXPECTED_PATH = "scripts/eval/fixtures/memory_temporal_owned_lab_authorization_envelope_verifier_s18.expected.v0.tsv"
GATE_PATH = "scripts/check-memory-temporal-owned-lab-authorization-envelope-verifier-s18.sh"
CARGO_PATH = "crates/store/Cargo.toml"
PARENT_MODULE_PATH = (
    "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/"
    "recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/"
    "durability_fault_model.rs"
)
RUST_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/"
    "recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/"
    "durability_fault_model/owned_lab_owner_resource_authorization.rs"
)
S17_CHECKER_PATH = "scripts/eval/check_memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17.py"

FROZEN_S17_ARTIFACTS = {
    "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-process-crash-restart-plan-s17-v0.json": "ca9769ff2b79e474999df6bb5096a3e062b5acf78fa23788f76ae44295531650",
    "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-process-crash-restart-observation-schema-s17-v0.json": "26a8cca9f9ca74ceb4b949a2e75d9282a6227623f5bd66cc3333fbff7441588d",
    "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-owner-resource-decision-schema-s17-v0.json": "41426b240443672d7e83fc0a8781ddb79acd9beaab1c7f6e9eaf9270c1bdf608",
    "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s17-v0.json": "6c35fc3684f7262a7eca2b8405e2c3a21b5ce2f7d282731824ceb67b0ea7163e",
    "scripts/eval/check_memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17.py": "d9903fc84701e7f6ceff3ae89a5f9f186efda36e8e8e9166fea7cab59510aed6",
    "scripts/check-memory-temporal-recovered-envelope-owned-lab-process-crash-restart-s17.sh": "00b93ec57bbb60695061caf31152d97454936aa1ee7100cff0e6aa6a2f469687",
}
FROZEN_PYTHON_MODULES = {
    S17_CHECKER_PATH: FROZEN_S17_ARTIFACTS[S17_CHECKER_PATH],
    "scripts/eval/check_memory_temporal_recovered_envelope_durability_fault_model_s16.py": "0f4c5d9fb2a63f3a65d56a462a6299819e539a4b5f205610ac1c0daffc8dc0e8",
    "scripts/eval/check_memory_temporal_recovered_envelope_source_s14.py": "3d89b9f4a44bb8dd978b538cf72e2c94f2ed2d8c461c7d85e604e82326381abe",
    "scripts/eval/check_memory_temporal_recovered_s9_decision_reverification_s12.py": "d580feaad194579961b380dcbea5aca4eb95101b3ce76beac793a248b3ea4dd2",
    "scripts/eval/check_memory_temporal_external_authority_provider_s9.py": "ad7e373f539b780dd71af7f226464412442e3274ce98b0246329c0401a42995f",
}


class CheckFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def artifact_sha256(repo: Path, relative: str) -> str:
    return hashlib.sha256((repo / relative).read_bytes()).hexdigest()


def read_text(repo: Path, relative: str) -> str:
    return (repo / relative).read_text(encoding="utf-8")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise CheckFailure(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def reject_float(value: str) -> None:
    raise CheckFailure(f"floating-point JSON is forbidden: {value}")


def reject_constant(value: str) -> None:
    raise CheckFailure(f"non-finite JSON is forbidden: {value}")


def parse_json_text(text: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, UnicodeDecodeError, CheckFailure) as exc:
        raise CheckFailure(f"invalid {label}: {exc}") from exc
    require(isinstance(value, dict), f"{label} root must be an object")
    return value


def load_json(repo: Path, relative: str) -> dict[str, Any]:
    return parse_json_text(read_text(repo, relative), relative)


def validate_restricted_value(value: Any, depth: int = 0) -> None:
    require(depth <= 16, "restricted canonical JSON exceeds depth 16")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        require(0 <= value <= 18446744073709551615, "integer is outside u64")
        return
    if isinstance(value, float):
        raise CheckFailure("float is forbidden in restricted canonical JSON")
    if isinstance(value, str):
        require(value.isascii(), "non-ASCII string is forbidden")
        return
    if isinstance(value, list):
        for item in value:
            validate_restricted_value(item, depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            require(isinstance(key, str) and key.isascii(), "non-ASCII object key")
            validate_restricted_value(item, depth + 1)
        return
    raise CheckFailure(f"unsupported restricted JSON type: {type(value).__name__}")


def restricted_canonical_bytes(value: Any) -> bytes:
    validate_restricted_value(value)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    require(len(raw) <= 65536, "restricted canonical document exceeds 65536 bytes")
    return raw


def canonical_structure_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def parse_restricted_canonical(raw: bytes, label: str) -> dict[str, Any]:
    require(len(raw) <= 65536, f"{label} exceeds 65536 bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckFailure(f"{label} is not UTF-8: {exc}") from exc
    value = parse_json_text(text, label)
    require(restricted_canonical_bytes(value) == raw, f"{label} is not exact canonical bytes")
    return value


def signed_message(payload_sha256: bytes) -> bytes:
    require(len(payload_sha256) == 32, "payload digest must be 32 raw bytes")
    return (
        len(MESSAGE_DOMAIN).to_bytes(4, "big")
        + MESSAGE_DOMAIN
        + (32).to_bytes(8, "big")
        + payload_sha256
    )


def authorization_id(payload: dict[str, Any]) -> tuple[bytes, bytes, bytes]:
    without_id = copy.deepcopy(payload)
    require(
        isinstance(without_id.pop("authorization_id_sha256", None), str),
        "authorization-ID KAT self field missing",
    )
    canonical_without_id = restricted_canonical_bytes(without_id)
    digest = hashlib.sha256(canonical_without_id).digest()
    message = (
        len(AUTHORIZATION_ID_DOMAIN).to_bytes(4, "big")
        + AUTHORIZATION_ID_DOMAIN
        + len(digest).to_bytes(8, "big")
        + digest
    )
    return canonical_without_id, message, hashlib.sha256(message).digest()


def load_frozen_module(repo: Path, relative: str, expected_sha256: str, name: str) -> Any:
    path = repo / relative
    require(
        path.is_file() and not path.is_symlink() and path.resolve() == path,
        f"frozen module is not one canonical regular file: {relative}",
    )
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, f"frozen module drift before execution: {relative}")
    require(not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {relative}")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckFailure(f"frozen module is not UTF-8: {relative}") from exc
    code = compile(source, str(path), "exec", dont_inherit=True, optimize=0)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    exec(code, module.__dict__)

    def safe_path_loader(candidate: Path, child_name: str) -> Any:
        candidate = Path(candidate)
        try:
            child_relative = candidate.relative_to(repo).as_posix()
        except ValueError as exc:
            raise CheckFailure(f"frozen child module escapes repository: {candidate}") from exc
        child_expected = FROZEN_PYTHON_MODULES.get(child_relative)
        require(child_expected is not None, f"unregistered frozen child module: {child_relative}")
        return load_frozen_module(repo, child_relative, child_expected, child_name)

    if "import_module" in module.__dict__:
        module.__dict__["import_module"] = safe_path_loader
    if "import_frozen_module" in module.__dict__:
        module.__dict__["import_frozen_module"] = safe_path_loader
    if relative.endswith("check_memory_temporal_recovered_s9_decision_reverification_s12.py"):
        def safe_s9_reference(candidate_repo: Path) -> Any:
            require(Path(candidate_repo).resolve() == repo, "S12 repository root drift")
            child = safe_path_loader(
                repo / "scripts/eval/check_memory_temporal_external_authority_provider_s9.py",
                "s12_pinned_s9_ed25519_reference",
            )
            for required in (
                "framed_message",
                "framed_digest",
                "ed25519_public_key",
                "ed25519_sign",
                "ed25519_verify",
            ):
                require(callable(getattr(child, required, None)), f"pinned S9 reference missing: {required}")
            return child

        module.__dict__["import_s9_reference"] = safe_s9_reference
    return module


def resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    require(ref.startswith("#/$defs/"), f"non-local ref: {ref}")
    name = ref.removeprefix("#/$defs/")
    target = root.get("$defs", {}).get(name)
    require(isinstance(target, dict), f"missing ref target: {ref}")
    return target


def schema_sample(schema: dict[str, Any], root: dict[str, Any], field: str = "") -> Any:
    if "$ref" in schema:
        return schema_sample(resolve_ref(root, schema["$ref"]), root, field)
    if "const" in schema:
        return copy.deepcopy(schema["const"])
    if "enum" in schema:
        return copy.deepcopy(schema["enum"][0])
    expected_type = schema.get("type")
    if expected_type == "object":
        return {
            key: schema_sample(schema["properties"][key], root, key)
            for key in schema.get("required", [])
        }
    if expected_type == "array":
        return []
    if expected_type == "integer":
        return schema.get("minimum", 0)
    if expected_type == "boolean":
        return False
    if expected_type == "null":
        return None
    if expected_type == "string":
        pattern = schema.get("pattern", "")
        if "{128}" in pattern:
            return "33" * 64
        if "{64}" in pattern:
            return "11" * 32
        if "{40}" in pattern:
            return "22" * 20
        if field.endswith("utc_audit_only"):
            return "2026-07-17T00:00:00Z"
        return "owner-key-v1"
    raise CheckFailure(f"cannot synthesize schema field: {field}")


def validate_closed_schema_graph(schema: dict[str, Any], label: str) -> None:
    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                properties = node.get("properties")
                required = node.get("required")
                require(isinstance(properties, dict), f"{label} {path} lacks properties")
                require(node.get("additionalProperties") is False, f"{label} {path} is open")
                require(isinstance(required, list), f"{label} {path} lacks required")
                require(set(required) == set(properties), f"{label} {path} required/property drift")
                require(len(required) == len(set(required)), f"{label} {path} duplicate required")
            for key, value in node.items():
                walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}/{index}")

    walk(schema, "#")


def schema_accepts(s17: Any, schema: dict[str, Any], instance: dict[str, Any]) -> bool:
    return not s17.schema_instance_errors(schema, instance, schema)


def validate_schemas(s17: Any, anchor: dict[str, Any], envelope: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    require(anchor.get("$id") == "agent_bridge.memory_temporal_owned_lab_owner_trust_anchor_s18.v0", "anchor schema id")
    require(envelope.get("$id") == "agent_bridge.memory_temporal_owned_lab_owner_authorization_envelope_s18.v0", "envelope schema id")
    require(canonical_structure_sha256(anchor) == EXPECTED_ANCHOR_SCHEMA_CANONICAL_SHA256, "anchor schema structure drift")
    require(canonical_structure_sha256(envelope) == EXPECTED_ENVELOPE_SCHEMA_CANONICAL_SHA256, "envelope schema structure drift")
    for label, schema in (("anchor", anchor), ("envelope", envelope)):
        require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{label} draft")
        validate_closed_schema_graph(schema, label)
        s17.validate_schema_keywords(schema, label)
        s17.validate_local_refs(schema, label)

    anchor_sample = schema_sample(anchor, anchor)
    envelope_sample = schema_sample(envelope, envelope)
    require(schema_accepts(s17, anchor, anchor_sample), "positive anchor sample rejected")
    require(schema_accepts(s17, envelope, envelope_sample), "authorized-unclaimed sample rejected")
    payload = envelope_sample["payload"]
    require(payload["owner_scope_authorized"] is True, "positive schema does not admit owner scope")
    for key in (
        "owned_lab_execution_authorized",
        "single_use_execution_capability_issued",
        "execution_start_permitted",
    ):
        require(payload[key] is False, f"positive schema enables {key}")
    for key in (
        "trusted_time_receipt_sha256",
        "cas_claim_receipt_sha256",
        "claimed_run_id_sha256",
        "execution_capability_sha256",
        "post_run_cleanup_receipt_sha256",
        "post_run_custody_receipt_sha256",
    ):
        require(payload[key] is None, f"positive schema pre-fills lifecycle receipt: {key}")
    require(payload["stop_state_at_signing_audit_only"] is False, "signed STOP audit state drift")
    require(
        payload["use_time_external_absorbing_stop_check_required"] is True
        and payload["use_time_current_revocation_epoch_check_required"] is True,
        "use-time external STOP/revocation checks are not mandatory",
    )
    for key in (
        "s19_integration_commit",
        "s19_subject_manifest_schema_sha256",
        "s19_subject_manifest_sha256",
    ):
        require(isinstance(payload[key], str) and payload[key], f"S19 owner binding missing: {key}")
    return anchor_sample, envelope_sample


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract["status"] == STATUS and contract["decision"] == DECISION, "contract state drift")
    canonical = contract["canonicalization"]
    require(canonical["profile"] == CANONICAL_PROFILE, "canonical profile drift")
    require(canonical["maximum_document_bytes"] == 65536, "document bound drift")
    require(canonical["maximum_nesting_depth"] == 16, "depth bound drift")
    for key in ("duplicate_keys_allowed", "unknown_fields_allowed", "floating_point_allowed", "nonfinite_number_allowed", "noncanonical_input_allowed"):
        require(canonical[key] is False, f"canonical prohibition weakened: {key}")
    signature = contract["signature"]
    require(signature["algorithm"] == "Ed25519", "signature algorithm drift")
    require(signature["message_domain"].encode() == MESSAGE_DOMAIN, "message domain drift")
    require(signature["message_profile"] == MESSAGE_PROFILE, "message profile drift")
    require(signature["public_key_source"] == "INDEPENDENT_OUT_OF_BAND_OWNER_TRUST_ANCHOR_ONLY", "trust source drift")
    require(signature["envelope_key_is_trust_anchor"] is False, "envelope key became anchor")
    authorization = contract["authorization_id"]
    require(
        authorization["domain"].encode() == AUTHORIZATION_ID_DOMAIN,
        "authorization-ID domain drift",
    )
    require(authorization["formula"] == AUTHORIZATION_ID_FORMULA, "authorization-ID formula drift")
    require(
        authorization["self_field_excluded"] == "authorization_id_sha256",
        "authorization-ID self-field exclusion drift",
    )
    lifecycle = contract["authorization_lifecycle"]
    require(lifecycle["owner_envelope_state"].startswith("AUTHORIZED_UNCLAIMED_"), "lifecycle state drift")
    require(lifecycle["future_atomic_transition"] == "UNCLAIMED_TO_CONSUMED_FOR_EXACT_RUN", "CAS transition drift")
    require(lifecycle["future_successful_claim_limit"] == 1, "claim limit drift")
    for key in (
        "owner_envelope_is_execution_capability",
        "owner_envelope_may_create_lab_root",
        "owner_envelope_may_start_runner",
        "failed_claim_grants_execution",
        "failed_claim_mutates_unclaimed_state",
        "failed_claim_allows_automatic_retry",
        "successful_claim_then_crash_allows_retry",
        "signed_stop_state_is_use_time_stop_proof",
    ):
        require(lifecycle[key] is False, f"lifecycle authority widened: {key}")
    require(
        lifecycle["use_time_stop_and_revocation_must_be_read_from_external_ledgers"] is True,
        "external use-time STOP/revocation read was weakened",
    )
    scope = contract["exact_canary_scope"]
    require(scope["claim_level"] == "L1_PROCESS_CRASH_FRESH_PROCESS_RESTART_ONLY", "claim level drift")
    require(scope["family_ids"] == ["OL00", "OL04", "OL05"], "family order drift")
    require(scope["family_scenario_counts"] == {"OL00": 1, "OL04": 6, "OL05": 53}, "family counts drift")
    require(scope["canary_batch_count"] == 1, "canary batch count drift")
    require(scope["retry_or_implicit_rerun_allowed"] is False, "canary retry enabled")
    require((scope["assigned_attempt_count"], scope["planned_pidfd_sigkill_attempt_count"], scope["planned_distinct_fresh_exec_read_count"], scope["planned_total_s16_mapping_phase_record_count"]) == (60, 59, 59, 113), "canary counts drift")
    implementation = contract["implementation"]
    for key in ("positive_owner_schema_available", "out_of_band_trust_anchor_schema_available", "restricted_canonical_json_parser_implemented", "owner_cross_field_semantic_validator_implemented", "active_ed25519_signature_verifier_implemented"):
        require(implementation[key] is True, f"implementation missing: {key}")
    for key in ("rfc8032_test_key_is_real_owner_authority", "generic_external_cli_implemented", "source_bound_runner_implemented", "single_use_cas_ledger_implemented", "execution_capability_type_implemented", "live_observation_runtime_validator_implemented"):
        require(implementation[key] is False, f"implementation overclaims: {key}")
    current = contract["current_authority_and_execution"]
    for key, value in current.items():
        if key == "side_effects_unlocked":
            require(value == "NONE", "side effects unlocked")
        elif isinstance(value, bool):
            require(value is False, f"real authority became true: {key}")
        elif isinstance(value, int):
            require(value == 0, f"actual count became nonzero: {key}")


def validate_status_and_successor(status: dict[str, Any], successor: dict[str, Any]) -> None:
    require(status["status"] == STATUS and status["decision"] == DECISION, "status fixture drift")
    for section_name in ("real_authority", "actual_execution", "nonclaims"):
        for key, value in status[section_name].items():
            if key == "side_effects_unlocked":
                require(value == "NONE", f"status side effects drift: {section_name}")
            elif isinstance(value, bool):
                require(value is False, f"status authority became true: {section_name}.{key}")
            elif isinstance(value, int):
                require(value == 0, f"status actual count became nonzero: {section_name}.{key}")
    implementation = status["implementation"]
    for key in (
        "positive_owner_schema_available",
        "out_of_band_trust_anchor_schema_available",
        "restricted_canonical_json_parser_implemented",
        "owner_cross_field_semantic_validator_implemented",
        "active_ed25519_signature_verifier_implemented",
        "rfc8032_test_only_known_answer_present",
    ):
        require(implementation[key] is True, f"status implementation missing: {key}")
    for key in (
        "rfc8032_test_key_is_real_owner_authority",
        "source_bound_runner_implemented",
        "single_use_cas_ledger_implemented",
        "execution_capability_type_implemented",
        "live_observation_runtime_validator_implemented",
    ):
        require(implementation[key] is False, f"status implementation overclaims: {key}")
    lifecycle = status["lifecycle"]
    require(
        lifecycle["owner_envelope_state_if_future_valid"]
        == "AUTHORIZED_UNCLAIMED_OWNED_LAB_L1_OL00_OL04_OL05_CANARY",
        "status owner-envelope state drift",
    )
    require(lifecycle["owner_envelope_is_bearer_capability"] is False, "status envelope became bearer")
    require(
        lifecycle["future_atomic_transition"] == "UNCLAIMED_TO_CONSUMED_FOR_EXACT_RUN"
        and lifecycle["future_successful_claim_limit"] == 1,
        "status claim transition drift",
    )
    for key in (
        "future_failed_claim_grants_execution",
        "future_failed_claim_mutates_unclaimed_state",
        "future_failed_claim_allows_automatic_retry",
        "future_successful_claim_then_crash_allows_retry",
    ):
        require(lifecycle[key] is False, f"status lifecycle widened: {key}")
    require(
        lifecycle["signed_stop_state_is_audit_only"] is True
        and lifecycle["use_time_stop_and_revocation_require_external_ledger_reads"] is True,
        "status use-time STOP/revocation boundary drift",
    )
    require(
        lifecycle["preflight_cas_and_post_run_receipts_are_separate"] is True
        and lifecycle["timestamps_are_audit_metadata_only"] is True,
        "status lifecycle separation drift",
    )
    require(successor["status"] == STATUS and successor["decision"] == DECISION, "successor state drift")
    completed = successor["completed_boundary"]
    for key in (
        "positive_owner_schema_available",
        "out_of_band_trust_anchor_schema_available",
        "restricted_canonical_parser_available",
        "owner_cross_field_semantic_kernel_available",
        "active_ed25519_verification_available",
    ):
        require(completed[key] is True, f"completed implementation missing: {key}")
    for key in (
        "owner_envelope_is_execution_capability",
        "source_bound_runner_available",
        "real_owner_envelope_present",
    ):
        require(completed[key] is False, f"completed boundary widened: {key}")
    require(
        completed["owner_envelope_output_state"]
        == "AUTHORIZED_UNCLAIMED_OWNED_LAB_L1_OL00_OL04_OL05_CANARY",
        "completed owner-envelope state drift",
    )
    require(completed["side_effects_unlocked"] == "NONE", "completed boundary side effects")
    next_stage = successor["next_stage"]
    require(next_stage["identity"] == "S19_SOURCE_BOUND_OWNED_LAB_RUNNER_PREFLIGHT_AND_SINGLE_USE_CAS_IMPLEMENTATION_NON_LIVE", "next stage drift")
    require(next_stage["may_execute_live_canary"] is False, "S19 may execute live")
    for key, value in next_stage.items():
        if key.startswith("requires_"):
            require(value is True, f"successor requirement weakened: {key}")
    require(
        next_stage["requires_expected_binding_from_independent_closed_typed_manifest_builder"] is True
        and next_stage["requires_expected_binding_not_derived_from_candidate_envelope"] is True,
        "successor expected binding may be self-derived",
    )
    manifest = successor["s19_subject_manifest_contract"]
    require(manifest["manifest_is_closed_typed_and_canonical"] is True, "S19 manifest is not closed")
    require(
        manifest["manifest_sha256_and_schema_sha256_are_owner_signed"] is True,
        "S19 manifest/schema digests are not owner-signed",
    )
    require(tuple(manifest["required_bindings"]) == S19_MANIFEST_BINDINGS, "S19 manifest binding set drift")
    future = successor["future_real_owner_step_after_s19"]
    require(
        future["identity"] == "S20_REAL_OWNER_ENVELOPE_SINGLE_USE_CAS_AND_LIVE_CANARY",
        "S20 identity drift",
    )
    for key in (
        "trust_anchor_must_be_installed_out_of_band",
        "owner_must_sign_exact_final_s19_subject",
        "single_use_cas_revocation_and_stop_remain_required",
        "may_execute_exact_live_canary_only_after_all_prerequisites",
    ):
        require(future[key] is True, f"S20 prerequisite weakened: {key}")
    for key in (
        "repository_may_generate_or_store_owner_private_key",
        "envelope_carried_key_may_authenticate_owner",
        "trusted_wall_clock_required_for_this_lab_authorization",
    ):
        require(future[key] is False, f"S20 authority boundary widened: {key}")
    for section_name in ("current_execution", "nonclaims"):
        for key, value in successor[section_name].items():
            if key == "side_effects_unlocked":
                require(value == "NONE", f"successor side effects drift: {section_name}")
            elif isinstance(value, bool):
                require(value is False, f"successor authority became true: {section_name}.{key}")
            elif isinstance(value, int):
                require(value == 0, f"successor actual count became nonzero: {section_name}.{key}")


def validate_sources(repo: Path) -> int:
    cargo = read_text(repo, CARGO_PATH)
    parent = read_text(repo, PARENT_MODULE_PATH)
    source = read_text(repo, RUST_SOURCE_PATH)
    cargo_addition = (
        f'{FEATURE} = ["temporal-evidence-s16-recovered-envelope-durability-fault-model-synthetic"]\n'
    )
    require(cargo.count(cargo_addition) == 1, "S18 feature dependency drift")
    require(
        hashlib.sha256(cargo.replace(cargo_addition, "", 1).encode()).hexdigest()
        == BASELINE_CARGO_SHA256,
        "Cargo manifest contains changes beyond the exact S18 feature",
    )
    parent_addition = (
        f'#[cfg(feature = "{FEATURE}")]\n'
        "mod owned_lab_owner_resource_authorization;\n\n"
    )
    require(parent.count(parent_addition) == 1, "private child module missing")
    require(
        hashlib.sha256(parent.replace(parent_addition, "", 1).encode()).hexdigest()
        == BASELINE_PARENT_MODULE_SHA256,
        "parent module contains changes beyond the exact private S18 child",
    )
    require(FEATURE in parent and "owned_lab_owner_resource_authorization" in parent, "private child module missing")
    required_tokens = (
        "UnparsedPublicKey",
        "ED25519",
        "verify(",
        "AUTHORIZED_UNCLAIMED_OWNED_LAB_L1_OL00_OL04_OL05_CANARY",
        "UNCLAIMED",
        "CONSUMED_FOR_EXACT_RUN",
        "AB_RESTRICTED_CANONICAL_JSON_S18_V1",
        "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_32_RAW_PAYLOAD_SHA256",
        "owner-authorization-id/s18/v1",
        "sort_keys()",
        "VerifiedUnclaimed",
        "RFC8032",
    )
    for token in required_tokens:
        require(token in source, f"Rust verifier token missing: {token}")
    forbidden_tokens = (
        "std::process::Command",
        "std::fs::",
        "rusqlite",
        "tokio::",
        "TcpStream",
        "UnixStream",
        "unsafe {",
        "StateStore",
        "Bridge",
    )
    for token in forbidden_tokens:
        require(token not in source, f"Rust verifier gained forbidden surface: {token}")
    tests = re.findall(r"fn (s18_[a-z0-9_]+)\s*\(", source)
    require(len(tests) == len(set(tests)) and len(tests) >= 8, "insufficient or duplicate S18 Rust KATs")
    return len(tests)


def validate_docs(design: str, report: str) -> None:
    required = (
        "AUTHORIZED_UNCLAIMED_OWNED_LAB_L1_OL00_OL04_OL05_CANARY",
        "UNCLAIMED_TO_CONSUMED_FOR_EXACT_RUN",
        "side_effects_unlocked=NONE",
        "no real trust anchor",
        "not an execution capability",
        "S19",
    )
    combined = (design + "\n" + report).lower()
    for token in required:
        require(token.lower() in combined, f"documentation token missing: {token}")


def validate_s17(repo: Path, s17: Any) -> None:
    for path, digest in FROZEN_S17_ARTIFACTS.items():
        require(artifact_sha256(repo, path) == digest, f"frozen S17 artifact drift: {path}")
    for path, digest in s17.FROZEN_PREDECESSOR_ARTIFACTS.items():
        if path == PARENT_MODULE_PATH:
            continue
        require(artifact_sha256(repo, path) == digest, f"frozen S17 predecessor drift: {path}")
    kat_rows = s17.validate_full_catalog_uniqueness(repo)
    bundle = {
        "plan": s17.load_json(repo, s17.PLAN_PATH),
        "observation": s17.load_json(repo, s17.OBSERVATION_SCHEMA_PATH),
        "owner": s17.load_json(repo, s17.OWNER_SCHEMA_PATH),
        "successor": s17.load_json(repo, s17.SUCCESSOR_PATH),
        "synthetic": s17.load_json(repo, s17.SYNTHETIC_PATH),
    }
    s17.validate_bundle(
        bundle,
        s17.read_text(repo, s17.DESIGN_PATH),
        s17.read_text(repo, s17.REPORT_PATH),
        kat_rows,
    )


def expect_failure(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except (CheckFailure, ValueError, TypeError):
        return
    raise CheckFailure(f"negative mutation accepted: {label}")


def self_test(s17: Any, anchor_schema: dict[str, Any], envelope_schema: dict[str, Any], anchor_sample: dict[str, Any], envelope_sample: dict[str, Any]) -> None:
    def rejected(schema: dict[str, Any], sample: dict[str, Any], mutate: Callable[[dict[str, Any]], None], label: str) -> None:
        candidate = copy.deepcopy(sample)
        mutate(candidate)
        require(not schema_accepts(s17, schema, candidate), f"schema mutation accepted: {label}")

    rejected(anchor_schema, anchor_sample, lambda v: v.__setitem__("private_key_present", True), "private key")
    rejected(anchor_schema, anchor_sample, lambda v: v.__setitem__("self_asserted_key_is_owner_authentication", True), "self anchor")
    rejected(anchor_schema, anchor_sample, lambda v: v.__setitem__("unexpected", False), "anchor unknown")
    rejected(envelope_schema, envelope_sample, lambda v: v["payload"].__setitem__("owned_lab_execution_authorized", True), "execution true")
    rejected(envelope_schema, envelope_sample, lambda v: v["payload"].__setitem__("cas_claim_receipt_sha256", "11" * 32), "prefilled CAS")
    rejected(envelope_schema, envelope_sample, lambda v: v["payload"].__setitem__("post_run_cleanup_receipt_sha256", "11" * 32), "prefilled cleanup")
    rejected(envelope_schema, envelope_sample, lambda v: v["payload"].__setitem__("retry_or_implicit_rerun_allowed", True), "retry")
    rejected(envelope_schema, envelope_sample, lambda v: v["payload"].__setitem__("network_allowed", True), "network")
    rejected(envelope_schema, envelope_sample, lambda v: v["payload"].__setitem__("stop_state_at_signing_audit_only", True), "signed STOP audit")
    rejected(envelope_schema, envelope_sample, lambda v: v["payload"].__setitem__("use_time_external_absorbing_stop_check_required", False), "external STOP check")
    rejected(envelope_schema, envelope_sample, lambda v: v["payload"].__setitem__("use_time_current_revocation_epoch_check_required", False), "current revocation check")
    rejected(envelope_schema, envelope_sample, lambda v: v["authentication"].__setitem__("detached_signature_hex", "00"), "short signature")
    rejected(envelope_schema, envelope_sample, lambda v: v.__setitem__("unexpected", False), "envelope unknown")

    canonical = restricted_canonical_bytes(envelope_sample)
    require(parse_restricted_canonical(canonical, "canonical-self-test") == envelope_sample, "canonical round trip")
    expect_failure("whitespace", lambda: parse_restricted_canonical(canonical + b"\n", "whitespace"))
    expect_failure("duplicate", lambda: parse_restricted_canonical(b'{"a":1,"a":1}', "duplicate"))
    expect_failure("out-of-order", lambda: parse_restricted_canonical(b'{"b":1,"a":2}', "out-of-order"))
    expect_failure("float", lambda: parse_restricted_canonical(b'{"a":1.5}', "float"))
    expect_failure("negative", lambda: restricted_canonical_bytes({"a": -1}))
    expect_failure("non-ascii", lambda: restricted_canonical_bytes({"a": "\u03bb"}))
    too_deep: Any = None
    for _ in range(18):
        too_deep = [too_deep]
    expect_failure("depth", lambda: restricted_canonical_bytes(too_deep))
    expect_failure("size", lambda: restricted_canonical_bytes({"a": "a" * 65536}))


def receipt_rows(repo: Path, rust_test_count: int, envelope_sample: dict[str, Any]) -> list[tuple[str, str]]:
    payload_bytes = restricted_canonical_bytes(envelope_sample["payload"])
    payload_sha = hashlib.sha256(payload_bytes).digest()
    message = signed_message(payload_sha)
    id_payload = {
        "audience": "kat",
        "authorization_id_sha256": "0" * 64,
        "revision": 7,
    }
    id_input, id_message, id_digest = authorization_id(id_payload)
    rows = [
        ("schema", "agent_bridge.memory_temporal_owned_lab_authorization_validator_s18_validation_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("positive_owner_schema_available", "true"),
        ("positive_owner_state", "AUTHORIZED_UNCLAIMED_OWNED_LAB_L1_OL00_OL04_OL05_CANARY"),
        ("owner_envelope_is_execution_capability", "false"),
        ("out_of_band_trust_anchor_required", "true"),
        ("signature_algorithm", "Ed25519"),
        ("signature_message_profile", MESSAGE_PROFILE),
        ("restricted_canonical_profile", CANONICAL_PROFILE),
        ("maximum_document_bytes", "65536"),
        ("maximum_nesting_depth", "16"),
        ("structural_kat_payload_len", str(len(payload_bytes))),
        ("structural_kat_payload_sha256", payload_sha.hex()),
        ("structural_kat_message_len", str(len(message))),
        ("structural_kat_message_sha256", hashlib.sha256(message).hexdigest()),
        ("authorization_id_domain", AUTHORIZATION_ID_DOMAIN.decode()),
        ("authorization_id_kat_input_len", str(len(id_input))),
        ("authorization_id_kat_input_sha256", hashlib.sha256(id_input).hexdigest()),
        ("authorization_id_kat_message_len", str(len(id_message))),
        ("authorization_id_kat_sha256", id_digest.hex()),
        ("rust_s18_test_count", str(rust_test_count)),
        ("full_catalog_augmented_fingerprint_count", "5639"),
        ("target_phase_unique_match_count", "113"),
        ("actual_owner_trust_anchor_count", "0"),
        ("actual_owner_signature_count", "0"),
        ("actual_cas_claim_count", "0"),
        ("actual_execution_capability_count", "0"),
        ("actual_assigned_attempt_count", "0"),
        ("actual_sigkill_attempt_count", "0"),
        ("actual_fresh_process_read_count", "0"),
        ("actual_observation_count", "0"),
        ("runner_implemented", "false"),
        ("side_effects_unlocked", "NONE"),
    ]
    for label, path in (
        ("cargo_manifest_sha256", CARGO_PATH),
        ("parent_module_sha256", PARENT_MODULE_PATH),
        ("design_sha256", DESIGN_PATH),
        ("contract_sha256", CONTRACT_PATH),
        ("status_fixture_sha256", STATUS_PATH),
        ("trust_anchor_schema_sha256", ANCHOR_SCHEMA_PATH),
        ("positive_owner_schema_sha256", ENVELOPE_SCHEMA_PATH),
        ("successor_gate_sha256", SUCCESSOR_PATH),
        ("rust_validator_source_sha256", RUST_SOURCE_PATH),
        ("checker_sha256", CHECKER_PATH),
        ("source_gate_sha256", GATE_PATH),
    ):
        rows.append((label, artifact_sha256(repo, path)))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]

    s17 = load_frozen_module(
        repo,
        S17_CHECKER_PATH,
        FROZEN_S17_ARTIFACTS[S17_CHECKER_PATH],
        "agent_bridge_frozen_s17_checker_for_s18",
    )
    validate_s17(repo, s17)
    anchor_schema = load_json(repo, ANCHOR_SCHEMA_PATH)
    envelope_schema = load_json(repo, ENVELOPE_SCHEMA_PATH)
    contract = load_json(repo, CONTRACT_PATH)
    status = load_json(repo, STATUS_PATH)
    successor = load_json(repo, SUCCESSOR_PATH)
    anchor_sample, envelope_sample = validate_schemas(s17, anchor_schema, envelope_schema)
    validate_contract(contract)
    validate_status_and_successor(status, successor)
    rust_test_count = validate_sources(repo)
    validate_docs(read_text(repo, DESIGN_PATH), read_text(repo, REPORT_PATH))
    if args.self_test:
        self_test(s17, anchor_schema, envelope_schema, anchor_sample, envelope_sample)
    for key, value in receipt_rows(repo, rust_test_count, envelope_sample):
        print(f"{key}\t{value}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print(f"S18 authorization verifier check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
