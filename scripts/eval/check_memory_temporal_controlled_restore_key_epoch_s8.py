#!/usr/bin/env python3
"""Fail-closed checker for the S8 controlled-restore key-epoch contract."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


STATUS = (
    "SYNTHETIC_CONTROLLED_RESTORE_KEY_EPOCH_ADMISSION_IMPLEMENTED_"
    "ONLINE_AUTHORITY_SIMULATED_SAME_EPOCH_ROLLBACK_UNRESOLVED_"
    "NOT_AUTHORIZED_NOT_TRANSPORT"
)
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s8-restore-bound-key-epoch-synthetic"
S7_FEATURE = "temporal-evidence-s7-durable-replay-synthetic"
BASE_COMMIT = "7819e61f5468bb84061e6cbe111c327f63dc63bf"
S7_FEATURE_COMMIT = "21d16c64c00ca1ba66b6833cc018e2796e76b5ef"
S7_CONTRACT_SHA256 = "8e4f895089f3085725988b50001ab77ec909b86b1dd203e304cc6b4a143a4c8c"
S7_GATE_SHA256 = "dec28c4a79e7573f0a296af43e5c03a68f61b8c13ddaef4384e19aa441500546"
S7_SCHEMA_SHA256 = "686c22c3f4f3f696113a88a6d72bb292635a55020e00144ea2ef02f7eae35466"
CONTEXT_PACK_SHA256 = "06f54d4079e09d7728effd242d9dbf0e35f4d050e0d7a9f6a5fc9a8202b9445f"
CONTRACT_PATH = "docs/design/fixtures/biocortex-ab-track-b-controlled-restore-key-epoch-s8-v0.json"
GATE_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s8-v0.json"
CONTRACT_SHA256 = "039ec8237afa9b2ea3340918a2924f78f89223abbd4034d41c6d82a2e1519573"
GATE_SHA256 = "c01e686d104392269d57c39a9a240b203016639c65f379f992e74d30248c5817"
SOURCE_PATH = "crates/store/src/temporal_replay_transport/restore_bound_key_epoch.rs"
SOURCE_SHA256 = "a252459ec21df5f2c4ecb251e61433017d5a2a44e9f14b1b886452da485f43b4"
POLICY = b"agent-bridge/track-b/controlled-restore-key-epoch/v1"
RECORD_DOMAIN = b"agent-bridge/track-b/controlled-restore-key-epoch/record/v1"
CURRENTNESS_DOMAIN = b"agent-bridge/track-b/controlled-restore-key-epoch/currentness/v1"
OUTER_DOMAIN = b"agent-bridge/track-b/controlled-restore-key-epoch/packet/v1"
REMAINING_GAPS = (
    "AUTHORITY_POLICY_CUSTODY_UNRESOLVED",
    "CAPTURE_PROVENANCE_UNATTESTED",
    "CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED",
    "PHYSICAL_PRIVACY_DELETION_UNRESOLVED",
    "PRODUCTION_PRODUCER_PROFILE_UNADMITTED",
)
OPERATIONAL_GAPS = (
    "CURRENTNESS_CHALLENGE_UNIQUENESS_UNATTESTED",
    "EXPECTED_EPOCH_CURRENTNESS_EXTERNAL_CUSTODY_UNATTESTED",
    "INSTANT_REVOCATION_UNAVAILABLE_WITH_LOCAL_CONSUME",
    "OLD_EPOCH_KEY_DESTRUCTION_UNATTESTED",
    "SAME_EPOCH_RESTORE_DETECTION_UNAVAILABLE",
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
        if key in output:
            raise CheckFailure(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def load_json(repo: Path, relative: str) -> dict[str, Any]:
    try:
        value = json.loads(read_text(repo, relative), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckFailure(f"invalid JSON {relative}: {exc}") from exc
    require(isinstance(value, dict), f"top-level JSON object required: {relative}")
    return value


def frame(value: bytes) -> bytes:
    return len(value).to_bytes(8, "big") + value


def framed_digest(domain: bytes, fields: list[bytes]) -> bytes:
    return hashlib.sha256(frame(domain) + b"".join(frame(field) for field in fields)).digest()


def independent_vectors() -> dict[str, str]:
    handle_key = bytes([0x11]) * 32
    inner_key = bytes([0x31]) * 32
    outer_key = bytes([0x51]) * 32
    policy_sha256 = hashlib.sha256(POLICY).digest()
    epoch = (1).to_bytes(8, "big")
    predecessor = bytes(32)
    generation = bytes([0x71]) * 32
    restore_event = bytes([0x91]) * 32
    receiver = bytes([0x81]) * 32
    build = bytes([0x82]) * 32
    allowlist = bytes([0x83]) * 32
    revocation = bytes([0x92]) * 32
    handle_fingerprint = hashlib.sha256(handle_key).digest()
    inner_fingerprint = hashlib.sha256(inner_key).digest()
    outer_fingerprint = hashlib.sha256(outer_key).digest()
    record_fields = [
        POLICY,
        S7_CONTRACT_SHA256.encode(),
        S7_SCHEMA_SHA256.encode(),
        epoch,
        predecessor,
        generation,
        restore_event,
        receiver,
        build,
        allowlist,
        revocation,
        policy_sha256,
        b"handle-key-s8-e1",
        handle_fingerprint,
        b"inner-key-s8-e1",
        inner_fingerprint,
        b"outer-key-s8-e1",
        outer_fingerprint,
    ]
    record_sha256 = framed_digest(RECORD_DOMAIN, record_fields)
    exact_payload = b'{"synthetic":"s8-known-vector"}'
    outer_fields = [
        epoch,
        record_sha256,
        predecessor,
        generation,
        restore_event,
        receiver,
        build,
        allowlist,
        revocation,
        policy_sha256,
        b"handle-key-s8-e1",
        handle_fingerprint,
        b"inner-key-s8-e1",
        inner_fingerprint,
        b"outer-key-s8-e1",
        outer_fingerprint,
    ]
    outer_message = frame(OUTER_DOMAIN) + b"".join(frame(field) for field in outer_fields)
    outer_message += frame(exact_payload)
    challenge = bytes([0xC1]) * 32
    currentness_message = (
        frame(CURRENTNESS_DOMAIN)
        + frame(challenge)
        + frame((1).to_bytes(8, "big"))
        + frame(b"ACTIVE")
        + frame(record_sha256)
    )
    return {
        "policy_sha256": policy_sha256.hex(),
        "epoch_record_sha256": record_sha256.hex(),
        "payload_sha256": hashlib.sha256(exact_payload).hexdigest(),
        "outer_hmac_sha256": hmac.new(outer_key, outer_message, hashlib.sha256).hexdigest(),
        "currentness_hmac_sha256": hmac.new(
            bytes([0xA8]) * 32, currentness_message, hashlib.sha256
        ).hexdigest(),
    }


def check_predecessors(repo: Path) -> None:
    require(
        sha256(repo, "docs/design/fixtures/biocortex-ab-track-b-durable-replay-contract-s7-v0.json")
        == S7_CONTRACT_SHA256,
        "S7 durable contract drift",
    )
    require(
        sha256(repo, "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s7-v0.json")
        == S7_GATE_SHA256,
        "S7 successor gate drift",
    )
    require(
        sha256(repo, "scripts/eval/fixtures/biocortex_ab_track_b_context_sampling_determinism_pack_v0.json")
        == CONTEXT_PACK_SHA256,
        "context-sampling compatibility pack drift",
    )


def check_contracts(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    require(sha256(repo, CONTRACT_PATH) == CONTRACT_SHA256, "S8 contract digest drift")
    require(sha256(repo, GATE_PATH) == GATE_SHA256, "S8 successor gate digest drift")
    contract = load_json(repo, CONTRACT_PATH)
    gate = load_json(repo, GATE_PATH)
    require(
        contract["schema"]
        == "agent_bridge.memory_temporal_controlled_restore_key_epoch_contract_s8.v0",
        "S8 contract schema drift",
    )
    require(contract["status"] == STATUS and contract["decision"] == DECISION, "S8 outcome drift")
    require(contract["feature"] == FEATURE, "S8 feature identity drift")
    require(contract["known_vector"] == {
        "authority_key_hex_profile": "a8_repeated_32_bytes",
        "currentness_challenge_hex_profile": "c1_repeated_32_bytes",
        "currentness_hmac_sha256": independent_vectors()["currentness_hmac_sha256"],
        "epoch_record_sha256": independent_vectors()["epoch_record_sha256"],
        "exact_payload_utf8": '{"synthetic":"s8-known-vector"}',
        "outer_hmac_sha256": independent_vectors()["outer_hmac_sha256"],
        "payload_sha256": independent_vectors()["payload_sha256"],
    }, "S8 known vector drift")
    require(
        contract["key_epoch_record"]["policy_sha256"] == independent_vectors()["policy_sha256"],
        "policy digest drift",
    )
    require(all(contract["test_matrix"].values()), "S8 test matrix contains an unclaimed case")
    negative = contract["negative_evidence"]
    require(
        negative["authority_restart_preserves_burn_history"] is False,
        "synthetic in-memory burn history falsely made durable",
    )
    require(
        negative["challenge_reuse_can_replay_stale_currentness"] is True,
        "challenge-reuse negative evidence missing",
    )
    require(negative["same_epoch_restore_detection"] is False, "same-epoch rollback falsely closed")
    require(
        negative["same_epoch_replay_tombstone_rollback_demonstrated"] is True,
        "same-epoch negative evidence missing",
    )
    require(
        negative["revocation_after_currentness_race_demonstrated"] is True,
        "revocation race negative evidence missing",
    )
    require(negative["external_monotonicity_proved"] is False, "external monotonicity invented")
    require(
        contract["key_epoch_record"]["reuse_enforcement_scope"]
        == "ONE_SYNTHETIC_AUTHORITY_INSTANCE_ONLY",
        "synthetic reuse scope drift",
    )
    require(
        contract["authentication_profile"]
        ["synthetic_authority_key_must_be_distinct_from_three_role_keys"]
        is True,
        "authority/data-role key separation missing",
    )
    boundary = contract["boundary"]
    require(boundary["controlled_restore_fencing"] == "SYNTHETIC_PROTOCOL_ONLY", "fencing scope drift")
    require(
        all(value is False for value in boundary.values() if isinstance(value, bool)),
        "S8 boundary silently opened",
    )
    require(contract["operational_gap_codes"] == list(OPERATIONAL_GAPS), "operational gaps drift")

    require(
        gate["schema"] == "agent_bridge.memory_temporal_successor_admission_gate_s8.v0",
        "S8 successor gate schema drift",
    )
    require(gate["status"] == "NOT_ADMITTED" and gate["decision"] == DECISION, "gate opened")
    require(gate["admission"]["admitted"] is False, "successor payload silently admitted")
    receipt_values = [
        value
        for key, value in gate["admission"].items()
        if key not in {"admitted", "admission_artifact_must_be_external_to_packet"}
    ]
    require(all(value is None for value in receipt_values), "invented admission receipt")
    require(gate["remaining_gap_codes"] == list(REMAINING_GAPS), "remaining gaps drift")
    require(gate["operational_gap_codes"] == list(OPERATIONAL_GAPS), "gate operational gaps drift")
    require(gate["predecessor"]["base_commit"] == BASE_COMMIT, "base commit drift")
    require(gate["predecessor"]["s7_feature_commit"] == S7_FEATURE_COMMIT, "S7 feature drift")
    require(
        gate["controlled_restore_preregistration"]["contract_sha256"] == CONTRACT_SHA256,
        "gate does not bind S8 contract",
    )
    require(
        all(value is False for value in gate["boundary"].values() if isinstance(value, bool)),
        "successor boundary opened",
    )
    require(gate["boundary"]["side_effects_unlocked"] == "NONE", "side effects unlocked")
    return contract, gate


def check_source(repo: Path) -> int:
    require(sha256(repo, SOURCE_PATH) == SOURCE_SHA256, "S8 Rust source digest drift")
    cargo = tomllib.loads(read_text(repo, "crates/store/Cargo.toml"))
    features = cargo.get("features", {})
    require(features.get(FEATURE) == [S7_FEATURE], "S8 feature dependency drift")
    require(FEATURE not in features.get("default", []), "S8 feature became default")
    parent = read_text(repo, "crates/store/src/temporal_replay_transport.rs")
    source = read_text(repo, SOURCE_PATH)
    durable = read_text(
        repo, "crates/store/src/temporal_replay_transport/durable_replay_registry.rs"
    )
    library = read_text(repo, "crates/store/src/lib.rs")
    bridge_cargo = read_text(repo, "crates/bridge/Cargo.toml")
    bridge_library = read_text(repo, "crates/bridge/src/lib.rs")
    require(
        f'#[cfg(feature = "{FEATURE}")]\nmod restore_bound_key_epoch;' in parent,
        "private S8 module gate missing",
    )
    require("pub mod restore_bound_key_epoch" not in parent, "S8 module became public")
    require(FEATURE not in library + bridge_cargo + bridge_library, "S8 leaked to public/Bridge surface")
    require("pub use restore_bound_key_epoch" not in parent + library, "S8 re-export forbidden")
    require("pub(crate)" not in source and "pub fn" not in source, "S8 capability became crate-public")
    require(
        "#[cfg(test)]\nstruct SyntheticOnlineRestoreEpochAuthorityV1" in source,
        "synthetic authority is not test-only",
    )
    require(
        "#[cfg(test)]\nfn synthetic_epoch_permit_for_test" in source,
        "synthetic epoch permit constructor is not test-only",
    )
    require("request_currentness" in source, "online currentness call missing")
    require("local fallback is forbidden" in source, "explicit no-fallback result missing")
    require("checked_add(1)" in source, "checked epoch/authority sequence missing")
    require("used_key_ids" in source and "used_key_fingerprints" in source, "reuse ledger missing")
    require("outer_authentication_message" in source, "outer exact-byte binding missing")
    require("verify_synthetic_detached_candidate_durable_v1" in source, "S7 durable wrapper missing")
    require("generation_id_for_restore_epoch" in durable + source, "S7 generation binding missing")
    require("SystemTime" not in source.split("#[cfg(test)]\nmod tests", 1)[0], "wall clock entered currentness")
    require("StateStore" not in source, "S8 entered StateStore")
    require("std::net" not in source and "tokio::net" not in source, "S8 implemented transport I/O")
    test_count = len(re.findall(r"(?m)^    fn s8_[a-z0-9_]+\(\)", source))
    require(test_count == 14, f"S8 Rust test count drift: {test_count}")
    require(
        "UNRESOLVED: same-epoch rollback can erase a local tombstone" in source,
        "same-epoch negative evidence assertion missing",
    )
    return test_count


def receipt(test_count: int, vectors: dict[str, str]) -> str:
    rows = [
        ("schema", "agent_bridge.memory_temporal_controlled_restore_key_epoch_s8_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("base_commit", BASE_COMMIT),
        ("s7_feature_commit", S7_FEATURE_COMMIT),
        ("s7_contract_sha256", S7_CONTRACT_SHA256),
        ("s7_successor_gate_sha256", S7_GATE_SHA256),
        ("context_sampling_pack_sha256", CONTEXT_PACK_SHA256),
        ("s8_contract_sha256", CONTRACT_SHA256),
        ("s8_successor_gate_sha256", GATE_SHA256),
        ("s8_source_sha256", SOURCE_SHA256),
        ("policy_sha256", vectors["policy_sha256"]),
        ("known_epoch_record_sha256", vectors["epoch_record_sha256"]),
        ("known_outer_hmac_sha256", vectors["outer_hmac_sha256"]),
        ("known_currentness_hmac_sha256", vectors["currentness_hmac_sha256"]),
        ("s8_nonignored_rust_tests", str(test_count)),
        ("controlled_restore_fencing", "SYNTHETIC_PROTOCOL_ONLY"),
        ("online_authority_runtime_present", "false"),
        ("external_key_custody_attested", "false"),
        ("old_epoch_rejection", "CONDITIONAL"),
        ("same_epoch_restore_detection", "false"),
        ("same_epoch_negative_evidence", "true"),
        ("instant_revocation_guaranteed", "false"),
        ("revocation_race_negative_evidence", "true"),
        ("challenge_uniqueness_enforced", "false"),
        ("challenge_reuse_negative_evidence", "true"),
        ("dual_store_atomicity_claimed", "false"),
        ("successor_payload_admitted", "false"),
        ("cross_repository_transport_authorized", "false"),
        ("bridge_runtime_caller_present", "false"),
        ("biocortex_runtime_influence", "false"),
        ("remaining_gaps", ",".join(REMAINING_GAPS)),
        ("operational_gaps", ",".join(OPERATIONAL_GAPS)),
        ("side_effects_unlocked", "NONE"),
    ]
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        check_predecessors(repo)
        check_contracts(repo)
        test_count = check_source(repo)
        vectors = independent_vectors()
    except (CheckFailure, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"S8_CHECK_FAILED\t{exc}", file=sys.stderr)
        return 1
    sys.stdout.write(receipt(test_count, vectors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
