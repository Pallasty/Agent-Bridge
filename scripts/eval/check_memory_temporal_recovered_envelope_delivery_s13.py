#!/usr/bin/env python3
"""Fail-closed checker for S13 local recovered-envelope delivery.

The checker validates the private/default-off Rust boundary, independently
rebuilds the owned-envelope known answer, and freezes negative authorization
claims.  Its receipt is structural historical evidence only; it is not a
runtime carrier, owner approval, currentness, replay consumption, or admission.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any


sys.dont_write_bytecode = True

STATUS = (
    "RECOVERED_S9_ENVELOPE_LOCAL_HANDOFF_PREREGISTERED_SYNTHETIC_OWNED_"
    "ONE_SHOT_IN_PROCESS_HISTORICAL_ONLY_NO_DURABLE_SOURCE_NO_RUNTIME_"
    "TRANSPORT_NO_CURRENTNESS_NO_ADMISSION"
)
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s13-recovered-envelope-delivery-synthetic"
S12_FEATURE = "temporal-evidence-s12-recovered-s9-decision-reverification-synthetic"

CONTRACT_PATH = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-recovered-envelope-delivery-s13-v0.json"
)
GATE_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s13-v0.json"
DESIGN_PATH = "docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_DELIVERY_S13_2026_07_15.md"
STORE_CARGO_PATH = "crates/store/Cargo.toml"
S12_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "recovered_s9_decision_reverification.rs"
)
DELIVERY_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "recovered_s9_decision_reverification/recovered_envelope_delivery.rs"
)
S10_SOURCE_PATH = "crates/store/src/temporal_replay_transport/external_operation_recovery.rs"
S11_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "external_authority_operation_state_machine.rs"
)
S12_CHECKER_PATH = "scripts/eval/check_memory_temporal_recovered_s9_decision_reverification_s12.py"

POLICY = b"agent-bridge/track-b/recovered-envelope-delivery/v1"
PROFILE = (
    b"OWNED_EXACT_S9_ENVELOPE_PLUS_LEXICAL_VERIFIED_S10_PROJECTION_"
    b"HISTORICAL_ONLY"
)
SCHEMA = b"agent-bridge/track-b/recovered-s9-envelope/v1"
ENVELOPE_DOMAIN = b"agent-bridge/track-b/recovered-envelope-delivery/envelope-digest/v1"
S12_CONTRACT_SHA256 = "4efa9dc533cfca6c98473ae20cf8fc983292362e92b669575a81e80e189b1303"
MAX_MESSAGE_BYTES = 65_536
MAX_ENVELOPE_BYTES = 131_072
SIGNATURE_BYTES = 64

OPERATIONAL_GAPS = (
    "RECOVERED_S9_DECISION_EXTERNAL_CARRIER_UNIMPLEMENTED",
    "RECOVERED_S9_DECISION_BYTES_AVAILABILITY_UNATTESTED",
    "RECOVERED_S9_RAW_DECISION_EXTERNAL_DURABILITY_UNATTESTED",
    "RECOVERED_S9_BYTE_ONLY_DECODER_UNIMPLEMENTED",
    "RECOVERED_ENVELOPE_CAPTURE_PROVENANCE_UNATTESTED",
    "RECOVERED_S10_VERIFIED_PROJECTION_RUNTIME_DELIVERY_UNIMPLEMENTED",
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
    return read_bytes(repo, relative).decode("utf-8")


def sha256(repo: Path, relative: str) -> str:
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
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckFailure(f"invalid JSON {relative}: {exc}") from exc
    require(isinstance(value, dict), f"top-level JSON object required: {relative}")
    return value


def import_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def envelope_vector(repo: Path) -> tuple[dict[str, str | int], str]:
    s12 = import_module(repo / S12_CHECKER_PATH, "s12_reference_for_s13")
    vectors = s12.independent_vectors(repo)
    ref = s12.import_s9_reference(repo)
    framed_message = ref.framed_message
    framed_digest = ref.framed_digest
    repeated = lambda value: bytes([value]) * 32
    u64 = lambda value: value.to_bytes(8, "big")

    provider_profile = b"owner-selected-provider-v1"
    namespace = b"agent-bridge-research-prod"
    tenant = b"agent-bridge"
    audience = b"ab-store-restore-admission"
    cluster = b"authority-cluster-a"
    incarnation = repeated(0x61)
    operation = repeated(0x21)
    challenge = repeated(0x31)
    epoch_record = repeated(0x41)
    generation = repeated(0x42)
    trust_policy = repeated(0x71)

    def opaque_key_ref(key_id: bytes, version: int, role: bytes) -> bytes:
        return framed_digest(
            s12.S9_KEY_REF_DOMAIN,
            [
                s12.S9_POLICY,
                provider_profile,
                namespace,
                cluster,
                incarnation,
                key_id,
                u64(version),
                role,
                b"hmac-sha-256",
            ],
        )

    keyset = framed_digest(
        s12.S9_KEYSET_DOMAIN,
        [
            s12.S9_POLICY,
            opaque_key_ref(b"handle-key", 11, b"HANDLE"),
            opaque_key_ref(b"inner-key", 12, b"INNER_TRANSPORT"),
            opaque_key_ref(b"outer-key", 13, b"OUTER_CHANNEL"),
        ],
    )
    request_message = framed_message(
        s12.S9_REQUEST_DOMAIN,
        [
            s12.S9_POLICY,
            s12.ALGORITHM,
            s12.S9_LEASE,
            provider_profile,
            namespace,
            tenant,
            audience,
            operation,
            challenge,
            u64(2),
            epoch_record,
            generation,
            repeated(0x43),
            repeated(0x44),
            repeated(0x45),
            keyset,
            trust_policy,
        ],
    )
    request_sha256 = hashlib.sha256(request_message).digest()
    revocation = framed_digest(s12.S9_REVOCATION_DOMAIN, [request_sha256, u64(42)])
    custody = framed_digest(s12.S9_CUSTODY_DOMAIN, [keyset, u64(2), u64(42)])
    use_denied = framed_digest(s12.S9_USE_DENIED_DOMAIN, [epoch_record, u64(2), u64(42)])
    decision_id = framed_digest(s12.S9_DECISION_ID_DOMAIN, [operation, challenge, u64(42)])
    decision_message = framed_message(
        s12.S9_DECISION_DOMAIN,
        [
            s12.S9_POLICY,
            s12.ALGORITHM,
            s12.S9_LEASE,
            request_sha256,
            b"ACTIVE",
            cluster,
            incarnation,
            u64(7),
            u64(42),
            u64(1),
            u64(2),
            epoch_record,
            generation,
            keyset,
            revocation,
            u64(1),
            custody,
            use_denied,
            decision_id,
            b"currentness-signer-a",
            u64(3),
        ],
    )
    signature = bytes.fromhex(str(vectors["s9_ed25519_signature"]))
    require(len(signature) == SIGNATURE_BYTES, "S9 signature length drift")
    require(hashlib.sha256(request_message).hexdigest() == vectors["s9_request_sha256"], "request KAT drift")
    require(
        hashlib.sha256(decision_message).hexdigest() == vectors["s9_decision_message_sha256"],
        "decision KAT drift",
    )

    envelope_sha256 = framed_digest(
        ENVELOPE_DOMAIN,
        [
            POLICY,
            PROFILE,
            SCHEMA,
            bytes.fromhex(s12.S9_CONTRACT_SHA256),
            bytes.fromhex(s12.S10_CONTRACT_SHA256),
            bytes.fromhex(s12.S11_CONTRACT_SHA256),
            bytes.fromhex(S12_CONTRACT_SHA256),
            request_message,
            decision_message,
            signature,
        ],
    ).hex()
    return vectors, envelope_sha256


def struct_body(source: str, name: str) -> str:
    match = re.search(rf"struct\s+{re.escape(name)}\s*\{{(?P<body>.*?)\n\}}", source, re.S)
    require(match is not None, f"missing Rust struct: {name}")
    return match.group("body")


def function_body(source: str, name: str) -> str:
    match = re.search(rf"fn\s+{re.escape(name)}\s*\([^)]*\).*?\{{(?P<body>.*?)\n    \}}", source, re.S)
    require(match is not None, f"missing Rust function: {name}")
    return match.group("body")


def check_contract(repo: Path, vectors: dict[str, str | int], envelope_sha256: str) -> None:
    contract = load_json(repo, CONTRACT_PATH)
    require(
        set(contract)
        == {
            "boundary",
            "carrier",
            "decision",
            "dependency",
            "envelope_digest",
            "framing_hardening",
            "handoff",
            "known_vector",
            "negative_evidence",
            "operational_gap_codes",
            "policy",
            "profile",
            "remaining_gap_codes",
            "schema",
            "status",
            "test_matrix",
        },
        "contract top-level keys drift",
    )
    require(contract["status"] == STATUS and contract["decision"] == DECISION, "contract decision drift")
    require(contract["policy"] == POLICY.decode() and contract["profile"] == PROFILE.decode(), "policy/profile drift")
    require(contract["dependency"]["feature"] == FEATURE, "feature drift")
    require(contract["dependency"]["requires_feature"] == S12_FEATURE, "feature dependency drift")
    carrier = contract["carrier"]
    require(carrier["max_request_message_bytes"] == MAX_MESSAGE_BYTES, "request bound drift")
    require(carrier["max_decision_message_bytes"] == MAX_MESSAGE_BYTES, "decision bound drift")
    require(carrier["max_combined_bytes"] == MAX_ENVELOPE_BYTES, "aggregate bound drift")
    require(carrier["canonical_signature_bytes_required"] == SIGNATURE_BYTES, "signature bound drift")
    require(carrier["cloneable"] is False and carrier["serializable"] is False, "carrier capability drift")
    require(contract["envelope_digest"]["domain"] == ENVELOPE_DOMAIN.decode(), "envelope domain drift")
    require(contract["envelope_digest"]["known_sha256"] == envelope_sha256, "envelope KAT drift")
    require(
        set(contract["handoff"])
        == {
            "consumes_self",
            "cross_process_capability",
            "global_exactly_once",
            "owns_typed_signed_s10_material",
            "projection_reconstructible_from_scalars",
            "projection_serialized_or_persisted",
            "reverification_of_same_typed_signed_input_possible",
            "s10_projection_lexical_only",
            "s10_reverified_locally",
        },
        "handoff contract keys drift",
    )
    require(contract["handoff"]["consumes_self"] is True, "handoff consumption drift")
    require(contract["handoff"]["owns_typed_signed_s10_material"] is True, "S10 ownership drift")
    require(contract["handoff"]["s10_projection_lexical_only"] is True, "projection lifetime drift")
    for key in (
        "cross_process_capability",
        "global_exactly_once",
        "projection_reconstructible_from_scalars",
        "projection_serialized_or_persisted",
    ):
        require(contract["handoff"][key] is False, f"handoff overclaim: {key}")
    require(
        contract["known_vector"]["historical_chain_sha256"] == vectors["historical_chain_sha256"],
        "historical chain drift",
    )
    require(list(contract["operational_gap_codes"]) == list(OPERATIONAL_GAPS), "operational gaps drift")
    require(list(contract["remaining_gap_codes"]) == list(REMAINING_GAPS), "remaining gaps drift")
    require(all(contract["test_matrix"].values()), "contract test matrix must be complete")


def check_gate(repo: Path) -> None:
    gate = load_json(repo, GATE_PATH)
    require(
        set(gate)
        == {
            "admission",
            "authorization_semantics",
            "boundary",
            "decision",
            "local_preregistration",
            "operational_gap_codes",
            "remaining_gap_codes",
            "required_successor_identity",
            "schema",
            "status",
        },
        "gate top-level keys drift",
    )
    require(gate["status"] == STATUS and gate["decision"] == DECISION, "gate decision drift")
    require(list(gate["operational_gap_codes"]) == list(OPERATIONAL_GAPS), "gate operational gaps drift")
    require(list(gate["remaining_gap_codes"]) == list(REMAINING_GAPS), "gate remaining gaps drift")
    for key, value in gate["admission"].items():
        if key == "owner_approval_receipt":
            require(value is None, "owner receipt must remain absent")
        else:
            require(value is False, f"admission must remain false: {key}")
    require(all(value is False for value in gate["authorization_semantics"].values()), "authorization overclaim")
    require(all(value is False for value in gate["boundary"].values()), "runtime boundary overclaim")
    require(all(value is True for value in gate["local_preregistration"].values()), "local boundary incomplete")


def check_source(repo: Path) -> tuple[int, int, int, int]:
    cargo = tomllib.loads(read_text(repo, STORE_CARGO_PATH))
    features = cargo["features"]
    require(features.get(FEATURE) == [S12_FEATURE], "S13 feature dependency drift")
    require(FEATURE not in features.get("default", []), "S13 feature became default")

    s12 = read_text(repo, S12_SOURCE_PATH)
    delivery = read_text(repo, DELIVERY_SOURCE_PATH)
    s10 = read_text(repo, S10_SOURCE_PATH)
    s11 = read_text(repo, S11_SOURCE_PATH)
    require(
        f'#[cfg(feature = "{FEATURE}")]\nmod recovered_envelope_delivery;' in s12,
        "S13 child module wiring drift",
    )
    require(re.search(r"\nfn verify_recovered_s9_decision_v1\s*\(", s12) is not None, "S12 verifier visibility widened")
    require("pub(super) fn verify_recovered_s9_decision_v1" not in s12, "S12 verifier became sibling-visible")

    envelope = struct_body(delivery, "RecoveredS9EnvelopeV1")
    handoff = struct_body(delivery, "RecoveredEvidenceHandoffV1")
    for field in (
        "request: ExternalCurrentnessRequestV1",
        "canonical_request_bytes: Box<[u8]>",
        "decision: SignedExternalCurrentnessDecisionV1",
        "canonical_decision_message_bytes: Box<[u8]>",
        "canonical_signature_bytes: Box<[u8]>",
        "envelope_sha256: [u8; 32]",
    ):
        require(field in envelope, f"owned envelope field drift: {field}")
    require("s10_query" not in envelope and "s10_observation" not in envelope, "S10 material leaked into S9 envelope")
    require("envelope: RecoveredS9EnvelopeV1" in handoff, "handoff envelope ownership drift")
    require("s10_query: ExternalOperationRecoveryQueryV1" in handoff, "handoff query ownership drift")
    require(
        "s10_observation: SignedExternalOperationRecoveryObservationV1" in handoff,
        "handoff observation ownership drift",
    )
    require(re.search(r"fn consume\s*\(\s*self,", delivery, re.S) is not None, "handoff must consume self")
    require("verify_external_operation_recovery_observation_v1(" in delivery, "local S10 re-verification missing")
    require("verify_recovered_s9_decision_v1(" in delivery, "S12 handoff missing")
    require("canonical_signature_bytes.len() != ED25519_SIGNATURE_BYTES" in delivery, "signature bound missing")
    require("checked_add(canonical_decision_message_bytes.len())" in delivery, "checked aggregate bound missing")

    production = delivery.split("#[cfg(test)]", 1)[0]
    for forbidden in (
        "serde::",
        "Serialize",
        "Deserialize",
        "#[derive(Clone",
        "#[derive(Copy",
        "pub(crate)",
        "pub(super)",
        "StateStore",
        "std::fs",
        "std::net",
        ".lookup_operation(",
        ".request_currentness(",
    ):
        require(forbidden not in production, f"forbidden S13 production surface: {forbidden}")

    require(re.search(r"\nfn observation_message\s*\(", s10) is not None, "S10 raw framer not private")
    require(
        re.search(r"pub\(super\)\s+fn\s+observation_message\s*\(", s10) is None,
        "S10 raw framer remains shared",
    )
    require("pub(super) fn validated_observation_message" in s10, "S10 validated framer missing")
    s10_validated = function_body(s10, "validated_observation_message")
    require(
        s10_validated.find("validate_observation_labels") < s10_validated.find("observation_message"),
        "S10 validation must precede framing",
    )

    require(re.search(r"\nfn decision_message\s*\(", s11) is not None, "S11 raw decision framer not private")
    require(
        re.search(r"pub\(super\)\s+fn\s+decision_message\s*\(", s11) is None,
        "S11 raw decision framer remains shared",
    )
    require(re.search(r"\nfn sign_job_id\s*\(", s11) is not None, "S11 raw sign-job framer not private")
    require(
        re.search(r"pub\(super\)\s+fn\s+sign_job_id\s*\(", s11) is None,
        "S11 raw sign-job framer remains shared",
    )
    require("pub(super) fn validated_decision_message" in s11, "S11 validated decision framer missing")
    require("pub(super) fn validated_sign_job_id" in s11, "S11 validated sign-job framer missing")
    s11_decision = function_body(s11, "validated_decision_message")
    require(s11_decision.find("validate_request") < s11_decision.find("decision_message"), "S11 request validation ordering drift")
    s11_job = function_body(s11, "validated_sign_job_id")
    require("!valid_label(signer_key_id)" in s11_job and "signer_key_version == 0" in s11_job, "S11 signer validation drift")

    bridge_root = repo / "crates/bridge"
    for path in bridge_root.rglob("*.rs"):
        require(FEATURE not in path.read_text(encoding="utf-8"), "S13 feature wired into Bridge")

    s13_tests = len(re.findall(r"#\[test\]\s*fn\s+s13_", delivery))
    s12_tests = len(re.findall(r"#\[test\]\s*fn\s+s12_", s12))
    s10_tests = len(re.findall(r"#\[test\]\s*fn\s+s10_", s10))
    s11_tests = len(re.findall(r"#\[test\]\s*fn\s+s11_", s11))
    require(s13_tests >= 15, "S13 negative matrix is incomplete")
    require(s12_tests == 32, "S12 regression count drift")
    require(s10_tests >= 15, "S10 hardening regression missing")
    require(s11_tests >= 30, "S11 hardening regression missing")
    return s13_tests, s12_tests, s10_tests, s11_tests


def receipt(
    repo: Path,
    vectors: dict[str, str | int],
    envelope_sha256: str,
    test_counts: tuple[int, int, int, int],
) -> str:
    s13_tests, s12_tests, s10_tests, s11_tests = test_counts
    rows: list[tuple[str, str]] = [
        ("schema", "agent_bridge.memory_temporal_recovered_envelope_delivery_s13_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("feature", FEATURE),
        ("depends_on_feature", S12_FEATURE),
        ("feature_default_enabled", "false"),
        ("policy", POLICY.decode()),
        ("profile", PROFILE.decode()),
        ("envelope_schema", SCHEMA.decode()),
        ("envelope_digest_domain", ENVELOPE_DOMAIN.decode()),
        ("max_request_message_bytes", str(MAX_MESSAGE_BYTES)),
        ("max_decision_message_bytes", str(MAX_MESSAGE_BYTES)),
        ("max_combined_bytes", str(MAX_ENVELOPE_BYTES)),
        ("signature_bytes", str(SIGNATURE_BYTES)),
        ("known_envelope_sha256", envelope_sha256),
        ("known_s9_request_sha256", str(vectors["s9_request_sha256"])),
        ("known_s9_decision_message_sha256", str(vectors["s9_decision_message_sha256"])),
        ("known_s9_signature", str(vectors["s9_ed25519_signature"])),
        ("known_s10_observation_sha256", str(vectors["s10_observation_sha256"])),
        ("known_historical_chain_sha256", str(vectors["historical_chain_sha256"])),
        ("s13_nonignored_rust_tests", str(s13_tests)),
        ("s12_retained_rust_tests", str(s12_tests)),
        ("s10_rust_tests_with_hardening", str(s10_tests)),
        ("s11_rust_tests_with_hardening", str(s11_tests)),
        ("owned_exact_s9_structural_carrier", "true"),
        ("handoff_consumes_self", "true"),
        ("s10_projection_lexical_only", "true"),
        ("s10_typed_signed_evidence_reverified_locally", "true"),
        ("s10_projection_serializable", "false"),
        ("carrier_cloneable", "false"),
        ("byte_only_decoder_present", "false"),
        ("external_durable_source_present", "false"),
        ("runtime_adapter_present", "false"),
        ("global_exactly_once_or_replay_fence", "false"),
        ("currentness_or_admission_issued", "false"),
        ("bridge_or_state_store_caller", "false"),
        ("side_effects_unlocked", "NONE"),
        ("remaining_gaps", ",".join(REMAINING_GAPS)),
        ("operational_gaps", ",".join(OPERATIONAL_GAPS)),
    ]
    for label, path in (
        ("contract_sha256", CONTRACT_PATH),
        ("successor_gate_sha256", GATE_PATH),
        ("design_sha256", DESIGN_PATH),
        ("store_cargo_sha256", STORE_CARGO_PATH),
        ("s12_source_sha256", S12_SOURCE_PATH),
        ("delivery_source_sha256", DELIVERY_SOURCE_PATH),
        ("s10_source_sha256", S10_SOURCE_PATH),
        ("s11_source_sha256", S11_SOURCE_PATH),
    ):
        rows.append((label, sha256(repo, path)))
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        vectors, envelope_sha256 = envelope_vector(repo)
        check_contract(repo, vectors, envelope_sha256)
        check_gate(repo)
        counts = check_source(repo)
        sys.stdout.write(receipt(repo, vectors, envelope_sha256, counts))
    except (CheckFailure, OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        print(f"S13_CHECK_FAILED\t{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
