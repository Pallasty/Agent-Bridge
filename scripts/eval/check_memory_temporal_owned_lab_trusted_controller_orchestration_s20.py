#!/usr/bin/env python3
"""Independent S20 closed-world, non-live orchestration packet checker."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Mapping

sys.dont_write_bytecode = True


BASELINE_COMMIT = "b90740ebd44632ae4ad88995938890e682d58b18"
BASELINE_TREE = "2d3c7c7ae486fd63777a83880c3337462bd9c39f"
S19_SOURCE_COMMIT = "1c0f8c77eb730b530d2e026f46c7ba22ffcebd97"
S19_SOURCE_TREE = "826db40e5f499c845b544cc87e6d55ccb85ef3ae"
FEATURE = "temporal-evidence-s20-owned-lab-trusted-controller-orchestration-synthetic"
STATUS = "S20A_NON_LIVE_TRUSTED_CONTROLLER_SECURITY_CORE_SYNTHETIC_ONLY"
DECISION = (
    "BLOCKED_PENDING_S20B_NON_CYCLIC_RICH_PACKET_CONTRACTS_AND_FULL_BUILDERS_"
    "BEFORE_ANY_S21_OWNER_BOUND_LIVE_STAGE"
)
MODE = "NON_LIVE_PRIVATE_DEFAULT_OFF_SYNTHETIC_KAT_ONLY"
S20B_IDENTITY = "S20B_NON_CYCLIC_RICH_PACKET_SCHEMA_REPLACEMENTS_AND_FULL_VALIDATORS"
FINAL_IMPLEMENTATION_STATE = (
    "IMPLEMENTED_S20A_SECURITY_CORE_SYNTHETIC_KAT_PASS_RICH_PACKET_LAYER_BLOCKED"
)
CANONICALIZATION = (
    "AB_RESTRICTED_CANONICAL_JSON_S20_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT"
)
MAX_ARTIFACT_BYTES = 3 * 1024 * 1024

CARGO_PATH = "crates/store/Cargo.toml"
S18_RUST_PATH = (
    "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/"
    "recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/"
    "durability_fault_model/owned_lab_owner_resource_authorization.rs"
)
S19_RUST_PATH = S18_RUST_PATH[:-3] + "/source_bound_runner.rs"
S20_RUST_PATH = S19_RUST_PATH[:-3] + "/trusted_controller_orchestration.rs"
DESIGN_PATH = (
    "docs/design/MEMORY_TEMPORAL_OWNED_LAB_TRUSTED_CONTROLLER_ORCHESTRATION_"
    "S20_2026_07_18.md"
)
FIXTURE_PREFIX = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-"
CONTRACT_PATH = FIXTURE_PREFIX + "trusted-controller-orchestration-contract-s20-v0.json"
STATUS_PATH = FIXTURE_PREFIX + "trusted-controller-orchestration-status-s20-v0.json"
CHECKPOINT_SCHEMA_PATH = FIXTURE_PREFIX + "external-anti-rollback-checkpoint-schema-s20-v0.json"
CHECKPOINT_FIXTURE_PATH = FIXTURE_PREFIX + "external-anti-rollback-checkpoint-synthetic-s20-v0.json"
ATTEMPT_SCHEMA_PATH = FIXTURE_PREFIX + "one-shot-attempt-tombstone-schema-s20-v0.json"
ATTEMPT_FIXTURE_PATH = FIXTURE_PREFIX + "one-shot-attempt-tombstone-synthetic-s20-v0.json"
ACTION_SCHEMA_PATH = FIXTURE_PREFIX + "action-start-linearization-receipt-schema-s20-v0.json"
ACTION_FIXTURE_PATH = FIXTURE_PREFIX + "action-start-linearization-receipt-synthetic-s20-v0.json"
INDEX_SCHEMA_PATH = FIXTURE_PREFIX + "exact-canary-run-index-schema-s20-v0.json"
INDEX_FIXTURE_PATH = FIXTURE_PREFIX + "exact-canary-run-index-synthetic-s20-v0.json"
SUCCESSOR_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s20-v0.json"
REPORT_PATH = (
    "docs/reports/goal-c-u/2026-07-18-biocortex-ab-track-b-owned-lab-"
    "trusted-controller-orchestration-s20.md"
)
CHECKER_PATH = "scripts/eval/check_memory_temporal_owned_lab_trusted_controller_orchestration_s20.py"
EXPECTED_PATH = (
    "scripts/eval/fixtures/memory_temporal_owned_lab_trusted_controller_"
    "orchestration_s20.expected.v0.tsv"
)
GATE_PATH = "scripts/check-memory-temporal-owned-lab-trusted-controller-orchestration-s20.sh"

SCHEMA_FIXTURES = (
    (
        CHECKPOINT_SCHEMA_PATH,
        CHECKPOINT_FIXTURE_PATH,
        "agent_bridge.memory_temporal_owned_lab_external_anti_rollback_checkpoint_s20.v0",
        "S20_EXTERNAL_ANTI_ROLLBACK_CHECKPOINT_RECEIPT",
        "checkpoint_state",
        "checkpoint_receipt_sha256",
        "agent-bridge/biocortex/owned-lab/s20/external-checkpoint-receipt/v1",
    ),
    (
        ATTEMPT_SCHEMA_PATH,
        ATTEMPT_FIXTURE_PATH,
        "agent_bridge.memory_temporal_owned_lab_one_shot_attempt_tombstone_s20.v0",
        "S20_ONE_SHOT_ATTEMPT_TOMBSTONE",
        "tombstone_state",
        "tombstone_receipt_sha256",
        "agent-bridge/biocortex/owned-lab/s20/one-shot-attempt-tombstone/v1",
    ),
    (
        ACTION_SCHEMA_PATH,
        ACTION_FIXTURE_PATH,
        "agent_bridge.memory_temporal_owned_lab_action_start_linearization_receipt_s20.v0",
        "S20_ACTION_START_LINEARIZATION_RECEIPT",
        "action_start_state",
        "action_start_receipt_sha256",
        "agent-bridge/biocortex/owned-lab/s20/action-start-linearization-receipt/v1",
    ),
    (
        INDEX_SCHEMA_PATH,
        INDEX_FIXTURE_PATH,
        "agent_bridge.memory_temporal_owned_lab_exact_canary_run_index_s20.v0",
        "S20_EXACT_CANARY_RUN_INDEX",
        "index_state",
        "run_index_sha256",
        "agent-bridge/biocortex/owned-lab/s20/exact-canary-run-index/v1",
    ),
)

FROZEN_S19_ARTIFACTS = {
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-subject-manifest-schema-s19-v0.json":
        "e8c75dc6fc15d8ca745ff3c27dc3ab7306036429517de9bcfc06cbc063b22495",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-preflight-receipt-schema-s19-v0.json":
        "989091d08d3ffa48b97df8a85ef239846d5cee5581d398bcd0a22eee4dfb2aef",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-control-snapshot-schema-s19-v0.json":
        "fcfa9fb441385b30209af48ca130dc93362a98dd5f966c9516b1c8d512774481",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-authority-control-claim-schema-s19-v0.json":
        "723627a925c5d876bc210d0ce478a44a439ed7129a7f2f05620a0e63aba038fd",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-post-run-receipt-bundle-schema-s19-v0.json":
        "f3ecbf2a03ba2c9def0e0d06c0fd2371aede65c79c09fe7f5cc7b907874de491",
    "scripts/check-memory-temporal-owned-lab-source-bound-runner-s19.sh":
        "1b33ee073bb6fbf4446a4f92e4dfc195f32b54b0cdfb48311ab79cf171a02b8f",
    "scripts/eval/check_memory_temporal_owned_lab_source_bound_runner_s19.py":
        "294c9fc3b9ecd12276959a498ff827a1b12df1d00c12f9595ddc73dc2d0771fa",
    "scripts/eval/fixtures/memory_temporal_owned_lab_source_bound_runner_s19.expected.v0.tsv":
        "5468d235a8f9eebffad298b854152e7261d4436a79fa0846081470bc18e7f9d0",
    "docs/reports/goal-c-u/2026-07-17-biocortex-ab-track-b-owned-lab-source-bound-runner-s19.md":
        "58073a661281448798291b585606df6e0ef85f098506f1832052e2de8eadba9e",
}

BASELINE_SHA256 = {
    CARGO_PATH: "5826f3e800b2337713499612317c158a8348bdc12e1e1420ea028019aa0cf66a",
    S18_RUST_PATH: "59e03d3523ffe8fdcad5bdfb5032a4e02ab574d05b6240a5039ebd3188679eb2",
    S19_RUST_PATH: "be93a0956540a20280ad4a6725dffb3a1c1f63d824ad7414fe912ae84b642945",
}

ADDITIONS = {
    CARGO_PATH: (
        b'temporal-evidence-s20-owned-lab-trusted-controller-orchestration-synthetic = '
        b'["temporal-evidence-s19-owned-lab-source-bound-runner-synthetic"]\n'
    ),
    S18_RUST_PATH: (
        b"    owner_envelope_sha256: [u8; 32],\n"
        b"    trust_anchor_document_sha256: [u8; 32],\n"
        b"    owner_identity_sha256: [u8; 32],\n"
        b"    owner_key_id: String,\n"
        b"    owner_key_version: u64,\n"
    ),
    S19_RUST_PATH: (
        b'#[cfg(feature = "temporal-evidence-s20-owned-lab-trusted-controller-'
        b'orchestration-synthetic")]\n'
        b"mod trusted_controller_orchestration;\n\n"
    ),
}

S18_ASSIGNMENT_ADDITION = (
    b"        owner_envelope_sha256: sha256_bytes(envelope_raw),\n"
    b"        trust_anchor_document_sha256: anchor.document_sha256,\n"
    b"        owner_identity_sha256: anchor.owner_identity_sha256,\n"
    b"        owner_key_id: anchor.owner_key_id,\n"
    b"        owner_key_version: anchor.owner_key_version,\n"
)

S18_S20_PROJECTION_TEST_ADDITION = b'''    #[test]
    fn s20_opaque_authorization_projection_is_derived_by_the_s18_verifier() {
        let (anchor, envelope, expected) = fixture();
        let anchor_value: Value = serde_json::from_slice(&anchor).unwrap();
        let verified = verify_unclaimed_owner_authorization_v1(&anchor, &envelope, &expected)
            .expect("synthetic authenticated-unclaimed fixture");
        assert_eq!(verified.owner_envelope_sha256, sha256_bytes(&envelope));
        assert_eq!(verified.trust_anchor_document_sha256, sha256_bytes(&anchor));
        assert_eq!(
            hex(&verified.owner_identity_sha256),
            anchor_value["owner_identity_sha256"].as_str().unwrap()
        );
        assert_eq!(
            verified.owner_key_id,
            anchor_value["owner_key_id"].as_str().unwrap()
        );
        assert_eq!(
            verified.owner_key_version,
            anchor_value["owner_key_version"].as_u64().unwrap()
        );
    }

'''

ARTIFACT_ROWS = (
    ("cargo_manifest_sha256", CARGO_PATH),
    ("s18_parent_verifier_sha256", S18_RUST_PATH),
    ("s19_parent_runner_sha256", S19_RUST_PATH),
    ("rust_s20_source_sha256", S20_RUST_PATH),
    ("design_sha256", DESIGN_PATH),
    ("contract_sha256", CONTRACT_PATH),
    ("status_fixture_sha256", STATUS_PATH),
    ("checkpoint_schema_sha256", CHECKPOINT_SCHEMA_PATH),
    ("checkpoint_fixture_sha256", CHECKPOINT_FIXTURE_PATH),
    ("attempt_schema_sha256", ATTEMPT_SCHEMA_PATH),
    ("attempt_fixture_sha256", ATTEMPT_FIXTURE_PATH),
    ("action_schema_sha256", ACTION_SCHEMA_PATH),
    ("action_fixture_sha256", ACTION_FIXTURE_PATH),
    ("index_schema_sha256", INDEX_SCHEMA_PATH),
    ("index_fixture_sha256", INDEX_FIXTURE_PATH),
    ("successor_gate_sha256", SUCCESSOR_PATH),
    ("checker_sha256", CHECKER_PATH),
    ("source_gate_sha256", GATE_PATH),
)


class CheckFailure(RuntimeError):
    """Expected validation failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def canonical_path(repo: Path, relative: str) -> Path:
    path = repo / relative
    require(path.is_file(), f"missing regular artifact: {relative}")
    require(not path.is_symlink(), f"symlink artifact forbidden: {relative}")
    require(path.resolve() == path, f"non-canonical artifact path: {relative}")
    return path


def read_bytes(repo: Path, relative: str, overrides: Mapping[str, bytes] | None = None) -> bytes:
    if overrides and relative in overrides:
        return overrides[relative]
    path = canonical_path(repo, relative)
    size = path.stat().st_size
    require(0 < size <= MAX_ARTIFACT_BYTES, f"artifact size outside bound: {relative}")
    raw = path.read_bytes()
    require(len(raw) == size, f"artifact changed while reading: {relative}")
    return raw


def read_text(repo: Path, relative: str, overrides: Mapping[str, bytes] | None = None) -> str:
    raw = read_bytes(repo, relative, overrides)
    require(not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {relative}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckFailure(f"non-UTF-8 artifact: {relative}") from exc


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


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


def parse_json(raw: bytes, label: str) -> dict[str, Any]:
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
    return value


def load_json(
    repo: Path, relative: str, overrides: Mapping[str, bytes] | None = None
) -> tuple[bytes, dict[str, Any]]:
    raw = read_bytes(repo, relative, overrides)
    return raw, parse_json(raw, relative)


def require_exact_keys(value: dict[str, Any], keys: set[str], label: str) -> None:
    require(set(value) == keys, f"unexpected keys in {label}: {sorted(set(value) ^ keys)}")


def verify_frozen_s19(repo: Path, overrides: Mapping[str, bytes] | None) -> None:
    for relative, expected in FROZEN_S19_ARTIFACTS.items():
        actual = sha256(read_bytes(repo, relative, overrides))
        require(actual == expected, f"frozen S19 artifact drift: {relative}")


def verify_exact_parent_edits(repo: Path, overrides: Mapping[str, bytes] | None) -> None:
    cargo = read_bytes(repo, CARGO_PATH, overrides)
    require(cargo.count(ADDITIONS[CARGO_PATH]) == 1, "S20 Cargo feature must occur exactly once")
    require(
        sha256(cargo.replace(ADDITIONS[CARGO_PATH], b"", 1)) == BASELINE_SHA256[CARGO_PATH],
        "Cargo.toml contains changes outside the exact S20 feature line",
    )

    s18 = read_bytes(repo, S18_RUST_PATH, overrides)
    require(s18.count(ADDITIONS[S18_RUST_PATH]) == 1, "S18 field extension must occur exactly once")
    require(s18.count(S18_ASSIGNMENT_ADDITION) == 1, "S18 assignment extension must occur exactly once")
    require(s18.count(S18_S20_PROJECTION_TEST_ADDITION) == 1, "S18 projection derivation KAT must occur exactly once")
    stripped_s18 = s18.replace(ADDITIONS[S18_RUST_PATH], b"", 1).replace(
        S18_ASSIGNMENT_ADDITION, b"", 1
    ).replace(S18_S20_PROJECTION_TEST_ADDITION, b"", 1)
    require(
        sha256(stripped_s18) == BASELINE_SHA256[S18_RUST_PATH],
        "S18 verifier contains changes outside exact S20 binding exposure",
    )

    s19 = read_bytes(repo, S19_RUST_PATH, overrides)
    require(s19.count(ADDITIONS[S19_RUST_PATH]) == 1, "S19 child-module stanza must occur once")
    require(
        sha256(s19.replace(ADDITIONS[S19_RUST_PATH], b"", 1)) == BASELINE_SHA256[S19_RUST_PATH],
        "S19 runner contains changes outside exact S20 private-module stanza",
    )


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
        require(isinstance(properties, dict), f"object schema lacks properties: {label}")
        required = value.get("required")
        require(isinstance(required, list), f"object schema lacks required list: {label}")
        require(set(required) == set(properties), f"optional/unknown object fields in schema: {label}")
        require(len(required) == len(set(required)), f"duplicate required key in schema: {label}")
    for key, child in value.items():
        validate_schema_node(child, f"{label}/{key}")


def all_nonclaim_values_fail_closed(value: dict[str, Any], label: str) -> None:
    for key, child in value.items():
        if key == "side_effects_unlocked":
            require(child == "NONE", f"side effects unlocked in {label}")
        else:
            require(child is False, f"nonclaim must be false: {label}.{key}")


def verify_fixture_self_hash(
    fixture: dict[str, Any],
    fixture_path: str,
    self_hash_field: str,
    expected_domain: str,
) -> str:
    contract = fixture.get("hashing_contract")
    require(isinstance(contract, dict), f"fixture lacks hashing contract: {fixture_path}")
    expected_contract = {
        "canonicalization": CANONICALIZATION,
        "cross_field_semantic_validation_required": True,
        "digest_domain": expected_domain,
        "digest_framing": "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_CANONICAL_PAYLOAD_LENGTH_CANONICAL_PAYLOAD",
        "hash_algorithm": "SHA-256",
        "hash_scope": "ENTIRE_PACKET_EXCEPT_" + self_hash_field.upper(),
        "repository_framing_lf_excluded": True,
        "self_hash_field": self_hash_field,
        "self_hash_field_excluded": True,
        "self_reported_match_fields_are_authoritative": False,
    }
    require(contract == expected_contract, f"hashing contract drift: {fixture_path}")
    declared = fixture.get(self_hash_field)
    require(
        isinstance(declared, str) and re.fullmatch(r"[0-9a-f]{64}", declared) is not None,
        f"invalid declared self hash: {fixture_path}",
    )
    payload_value = copy.deepcopy(fixture)
    removed = payload_value.pop(self_hash_field, None)
    require(removed == declared, f"self-hash field removal mismatch: {fixture_path}")
    payload = json.dumps(
        payload_value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    domain = expected_domain.encode("ascii")
    framed = len(domain).to_bytes(4, "big") + domain + len(payload).to_bytes(8, "big") + payload
    computed = sha256(framed)
    require(declared == computed, f"fixture self hash is not independently recomputed value: {fixture_path}")
    return computed


def validate_schema_fixture_pairs(
    repo: Path, overrides: Mapping[str, bytes] | None
) -> dict[str, str]:
    receipt: dict[str, str] = {}
    for (
        schema_path,
        fixture_path,
        schema_id,
        packet_kind,
        state_key,
        self_hash_field,
        digest_domain,
    ) in SCHEMA_FIXTURES:
        schema_raw, schema = load_json(repo, schema_path, overrides)
        require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"draft drift: {schema_path}")
        require(schema.get("$id") == schema_id, f"schema id drift: {schema_path}")
        validate_schema_node(schema, schema_path)

        fixture_raw, fixture = load_json(repo, fixture_path, overrides)
        require(fixture_raw.endswith(b"\n"), f"fixture lacks one final LF: {fixture_path}")
        require(not fixture_raw.endswith(b"\n\n"), f"fixture has multiple final LF: {fixture_path}")
        require(b"\n" not in fixture_raw[:-1], f"fixture is not compact one-line JSON: {fixture_path}")
        canonical = json.dumps(
            fixture, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii") + b"\n"
        require(fixture_raw == canonical, f"fixture is not canonical restricted JSON: {fixture_path}")
        require(fixture.get("schema") == schema_id, f"fixture schema drift: {fixture_path}")
        require(fixture.get("packet_kind") == packet_kind, f"packet kind drift: {fixture_path}")
        require(fixture.get("canonicalization") == CANONICALIZATION, f"canonicalization drift: {fixture_path}")
        require(fixture.get("test_only") is True and fixture.get("synthetic") is True, f"fixture not synthetic-only: {fixture_path}")
        require(
            isinstance(fixture.get(state_key), str)
            and fixture[state_key].startswith("SYNTHETIC_KAT_NON_LIVE_"),
            f"fixture state is not explicitly non-live: {fixture_path}",
        )
        nonclaims = fixture.get("nonclaims")
        require(isinstance(nonclaims, dict), f"fixture lacks nonclaims: {fixture_path}")
        all_nonclaim_values_fail_closed(nonclaims, fixture_path)
        computed_self_hash = verify_fixture_self_hash(
            fixture, fixture_path, self_hash_field, digest_domain
        )
        receipt[Path(schema_path).stem + "_sha256"] = sha256(schema_raw)
        receipt[Path(fixture_path).stem + "_sha256"] = sha256(fixture_raw)
        receipt[Path(fixture_path).stem + "_self_hash"] = computed_self_hash

    _, index = load_json(repo, INDEX_FIXTURE_PATH, overrides)
    _, checkpoint = load_json(repo, CHECKPOINT_FIXTURE_PATH, overrides)
    require(
        checkpoint["checkpoint_binding"]["independent_failure_domain_proved"] is False,
        "synthetic checkpoint must not claim an independently proved failure domain",
    )
    denominator = index["assigned_denominator"]
    require(denominator["authorized_family_ids"] == ["OL00", "OL04", "OL05"], "canary family drift")
    require(denominator["authorized_family_scenario_counts"] == {"OL00": 1, "OL04": 6, "OL05": 53}, "canary scenario denominator drift")
    require(denominator["canary_batch_count"] == 1, "canary batch drift")
    require(denominator["assigned_attempt_count"] == 60, "assigned denominator drift")
    require(denominator["planned_pidfd_sigkill_attempt_count"] == 59, "pidfd denominator drift")
    require(denominator["planned_distinct_fresh_exec_read_count"] == 59, "fresh-exec denominator drift")
    require(denominator["planned_total_s16_mapping_phase_record_count"] == 113, "S16 phase denominator drift")
    require(denominator["retry_or_implicit_rerun_allowed"] is False, "canary retry must remain forbidden")
    require(all(value == 0 for value in index["observed_counts"].values()), "synthetic observed counts must be zero")
    require(index["evidence_outcome"]["execution_occurred"] is False, "synthetic fixture claims execution")
    require(index["evidence_outcome"]["live_action_count"] == 0, "synthetic fixture claims live action")
    return receipt


def assert_current_quiescent(value: dict[str, Any], label: str) -> None:
    for key, child in value.items():
        if key == "side_effects_unlocked":
            require(child == "NONE", f"side effects unlocked: {label}")
        elif key.startswith("actual_") or key.endswith("_count"):
            require(child == 0, f"nonzero current count: {label}.{key}")
        elif (
            key.startswith("real_")
            or key in {
                "owned_lab_execution_authorized",
                "single_use_execution_permit_issued",
                "execution_start_permitted",
                "runner_launched",
                "live_root_created",
                "provider_or_production_authority",
                "global_runtime_admission",
            }
        ):
            require(child is False, f"current real/live authority present: {label}.{key}")


def validate_control_documents(repo: Path, overrides: Mapping[str, bytes] | None) -> None:
    _, contract = load_json(repo, CONTRACT_PATH, overrides)
    _, status = load_json(repo, STATUS_PATH, overrides)
    _, successor = load_json(repo, SUCCESSOR_PATH, overrides)
    for label, value in (("contract", contract), ("status", status), ("successor", successor)):
        require(value.get("status") == STATUS, f"status drift: {label}")
        require(value.get("decision") == DECISION, f"decision drift: {label}")
    require_exact_keys(
        contract,
        {
            "schema", "status", "decision", "implementation_mode", "predecessor",
            "new_closed_packet_schemas", "s20a_security_core_target",
            "orchestration_invariants", "frozen_canary", "current_real_inputs",
            "current_execution", "s20b_successor_boundary", "future_s21_live_boundary",
            "nonclaims",
        },
        "contract",
    )
    require_exact_keys(
        status,
        {
            "schema", "status", "decision", "implementation_mode",
            "documentation_and_schema", "rust_and_kat", "current_authority",
            "current_execution", "next_stage", "future_live_stage",
            "mechanical_completion_fields", "nonclaims",
        },
        "status",
    )
    require_exact_keys(
        successor,
        {
            "schema", "status", "decision", "completed_document_boundary",
            "s20a_implementation", "s20_non_live_limits",
            "current_authority_and_execution", "next_stage",
            "future_s21_live_boundary", "future_s21_fail_closed_conditions", "nonclaims",
        },
        "successor",
    )
    require(contract.get("implementation_mode") == MODE, "contract implementation mode drift")
    require(successor["completed_document_boundary"]["implementation_mode"] == MODE, "successor implementation mode drift")
    predecessor = contract["predecessor"]
    require(predecessor["s19_integration_commit"] == BASELINE_COMMIT, "contract baseline commit drift")
    require(predecessor["s19_integration_tree"] == BASELINE_TREE, "contract baseline tree drift")
    require(predecessor["s19_source_commit"] == S19_SOURCE_COMMIT, "contract S19 source drift")
    require(predecessor["s19_source_tree"] == S19_SOURCE_TREE, "contract S19 source tree drift")
    require(predecessor["s19_schemas_modified_by_s20"] is False, "contract claims S19 schema modification")
    require(contract["new_closed_packet_schemas"]["canonicalization"] == CANONICALIZATION, "contract canonicalization drift")
    require(contract["new_closed_packet_schemas"]["external_schema_references_allowed"] is False, "external refs allowed")
    require(contract["new_closed_packet_schemas"]["floating_point_values_allowed"] is False, "floats allowed")
    require(contract["new_closed_packet_schemas"]["synthetic_fixture_count"] == 4, "fixture count drift")
    target = contract["s20a_security_core_target"]
    require_exact_keys(
        target,
        {
            "implementation_state", "post_kat_implementation_state",
            "private_default_off_kernel_required", "real_backend_allowed",
            "s19_preflight_rich_packet_full_builder_and_validator_implemented",
            "s19_control_snapshot_rich_packet_full_builder_and_validator_implemented",
            "s19_authority_control_claim_rich_packet_full_builder_and_validator_implemented",
            "s19_post_run_bundle_rich_packet_full_builder_and_validator_implemented",
            "non_cyclic_s19_rich_packet_contracts_available", "rich_packet_layer_blocked",
            "new_s20_fixture_self_digests_verified_by_independent_checker",
            "runtime_full_packet_builders_and_digest_recomputation_implemented",
            "runtime_full_cross_packet_binding_recomputation_implemented",
            "s17_32_rule_full_catalog_semantic_validator_implemented",
            "s17_32_rule_full_catalog_semantic_validator_deferred_to_s20b",
            "synthetic_manifest_run_binding_implemented",
            "exact_assignment_membership_validator_implemented",
            "full_database_content_authentication_implemented",
            "transaction_profile_readback_implemented",
            "prepared_checkpoint_full_token_binding_implemented",
            "reopen_exact_cardinality_and_pending_intent_rejection_implemented",
            "action_permit_consumed_by_value_on_all_outcomes_implemented",
            "action_journal_exact_started_prefix_enforced",
            "synthetic_postrun_terminal_transition_implemented",
            "rich_postrun_receipt_implemented",
            "real_parent_directory_durability_adapter_implemented",
            "typed_external_checkpoint_state_machine_required",
            "typed_one_shot_attempt_tombstone_required",
            "typed_action_start_linearization_required",
            "typed_exact_canary_run_index_required",
            "private_noncloneable_nonserializable_handles_required", "synthetic_kat_required",
        },
        "contract.s20a_security_core_target",
    )
    require(target["implementation_state"] == FINAL_IMPLEMENTATION_STATE, "contract implementation not mechanically complete")
    require(target["post_kat_implementation_state"] == FINAL_IMPLEMENTATION_STATE, "contract post-KAT state drift")
    require(target["real_backend_allowed"] is False, "contract permits real backend")
    for key in (
        "s19_preflight_rich_packet_full_builder_and_validator_implemented",
        "s19_control_snapshot_rich_packet_full_builder_and_validator_implemented",
        "s19_authority_control_claim_rich_packet_full_builder_and_validator_implemented",
        "s19_post_run_bundle_rich_packet_full_builder_and_validator_implemented",
        "non_cyclic_s19_rich_packet_contracts_available",
        "runtime_full_packet_builders_and_digest_recomputation_implemented",
        "runtime_full_cross_packet_binding_recomputation_implemented",
        "s17_32_rule_full_catalog_semantic_validator_implemented",
        "exact_assignment_membership_validator_implemented",
        "full_database_content_authentication_implemented",
        "rich_postrun_receipt_implemented",
        "real_parent_directory_durability_adapter_implemented",
    ):
        require(target[key] is False, f"contract misclaims blocked rich layer: {key}")
    require(target["rich_packet_layer_blocked"] is True, "contract does not expose S20B blocker")
    require(target["new_s20_fixture_self_digests_verified_by_independent_checker"] is True, "contract omits independent fixture digest verification")
    require(target["s17_32_rule_full_catalog_semantic_validator_deferred_to_s20b"] is True, "contract hides deferred 5,639-row validator")
    for key in (
        "private_default_off_kernel_required",
        "typed_external_checkpoint_state_machine_required",
        "typed_one_shot_attempt_tombstone_required",
        "typed_action_start_linearization_required",
        "typed_exact_canary_run_index_required",
        "private_noncloneable_nonserializable_handles_required",
        "synthetic_kat_required",
        "synthetic_manifest_run_binding_implemented",
        "transaction_profile_readback_implemented",
        "prepared_checkpoint_full_token_binding_implemented",
        "reopen_exact_cardinality_and_pending_intent_rejection_implemented",
        "action_permit_consumed_by_value_on_all_outcomes_implemented",
        "action_journal_exact_started_prefix_enforced",
        "synthetic_postrun_terminal_transition_implemented",
    ):
        require(target[key] is True, f"contract S20A core requirement is not true: {key}")
    s20b = contract["s20b_successor_boundary"]
    require(s20b["identity"] == S20B_IDENTITY, "contract does not bind exact S20B successor")
    require(s20b["preapproved"] is False, "contract preapproves S20B")
    require(s20b["may_execute_live"] is False, "contract lets S20B execute live")
    require(s20b["requires_exact_authorized_assignment_membership_and_operation_descriptors"] is True, "contract hides assignment-membership blocker")
    require(s20b["requires_authenticated_database_content_root_or_equivalent_closed_writer_proof"] is True, "contract hides database-content-authentication blocker")
    require(contract["future_s21_live_boundary"]["preapproved"] is False, "contract preapproves future S21")
    canary = contract["frozen_canary"]
    require(canary["authorized_family_ids"] == ["OL00", "OL04", "OL05"], "contract family drift")
    require(canary["authorized_family_scenario_counts"] == {"OL00": 1, "OL04": 6, "OL05": 53}, "contract denominator drift")
    require((canary["canary_batch_count"], canary["assigned_attempt_count"]) == (1, 60), "contract batch/attempt drift")
    require((canary["planned_pidfd_sigkill_attempt_count"], canary["planned_distinct_fresh_exec_read_count"], canary["planned_total_s16_mapping_phase_record_count"]) == (59, 59, 113), "contract planned counts drift")
    require(canary["retry_or_implicit_rerun_allowed"] is False, "contract permits retry")
    assert_current_quiescent(contract["current_real_inputs"], "contract.current_real_inputs")
    assert_current_quiescent(contract["current_execution"], "contract.current_execution")
    all_nonclaim_values_fail_closed(contract["nonclaims"], "contract.nonclaims")

    rust_and_kat = status["rust_and_kat"]
    require(rust_and_kat["implementation_state"] == FINAL_IMPLEMENTATION_STATE, "status implementation not mechanically complete")
    require(rust_and_kat["post_kat_implementation_state"] == FINAL_IMPLEMENTATION_STATE, "status post-KAT state drift")
    deferred_fields = {
        "s19_preflight_rich_packet_full_builder_and_validator_implemented",
        "s19_control_snapshot_rich_packet_full_builder_and_validator_implemented",
        "s19_authority_control_claim_rich_packet_full_builder_and_validator_implemented",
        "s19_post_run_bundle_rich_packet_full_builder_and_validator_implemented",
        "runtime_full_packet_digest_recomputation_implemented",
        "runtime_full_cross_packet_binding_recomputation_implemented",
        "s17_32_rule_full_5639_row_semantic_validator_implemented",
        "exact_assignment_membership_validator_implemented",
        "full_database_content_authentication_implemented",
        "rich_postrun_receipt_implemented",
        "real_parent_directory_durability_adapter_implemented",
    }
    core_fields = {
        "private_default_off_kernel_implemented",
        "external_checkpoint_state_machine_implemented",
        "attempt_tombstone_state_machine_implemented",
        "action_start_linearization_state_machine_implemented",
        "exact_canary_run_index_validator_implemented",
        "synthetic_kat_passed",
        "synthetic_manifest_run_binding_implemented",
        "transaction_profile_readback_implemented",
        "prepared_checkpoint_full_token_binding_implemented",
        "reopen_exact_cardinality_and_pending_intent_rejection_implemented",
        "action_permit_consumed_by_value_on_all_outcomes_implemented",
        "action_journal_exact_started_prefix_enforced",
        "synthetic_postrun_terminal_transition_implemented",
    }
    require(
        set(rust_and_kat)
        == {
            "implementation_state", "post_kat_implementation_state",
            "real_backend_implemented", "rich_packet_layer_blocked_pending_s20b",
        }
        | deferred_fields
        | core_fields,
        "status Rust/KAT field set drift",
    )
    for key in deferred_fields:
        require(rust_and_kat[key] is False, f"S20A deferred boundary misclaimed as implemented: {key}")
    for key in core_fields:
        require(rust_and_kat[key] is True, f"S20A core completion field not true: {key}")
    require(rust_and_kat["rich_packet_layer_blocked_pending_s20b"] is True, "status hides S20B blocker")
    require(rust_and_kat["real_backend_implemented"] is False, "status claims real backend")
    assert_current_quiescent(status["current_authority"], "status.current_authority")
    assert_current_quiescent(status["current_execution"], "status.current_execution")
    require(status["next_stage"]["preapproved"] is False, "S21 preapproved")
    require(status["next_stage"]["may_execute_live"] is False, "S21 live execution allowed")
    require(status["next_stage"]["identity"] == S20B_IDENTITY, "status does not bind exact S20B successor")
    require(status["next_stage"]["requires_exact_authorized_assignment_membership_and_operation_descriptors"] is True, "status hides assignment-membership blocker")
    require(status["next_stage"]["requires_authenticated_database_content_root_or_equivalent_closed_writer_proof"] is True, "status hides database-content-authentication blocker")
    require(status["future_live_stage"]["preapproved"] is False, "status preapproves future S21")
    require(status["future_live_stage"]["may_execute_live"] is False, "status permits future S21 live")
    require(
        status["mechanical_completion_fields"]
        == [
            "rust_and_kat.implementation_state",
            "rust_and_kat.private_default_off_kernel_implemented",
            "rust_and_kat.external_checkpoint_state_machine_implemented",
            "rust_and_kat.attempt_tombstone_state_machine_implemented",
            "rust_and_kat.action_start_linearization_state_machine_implemented",
            "rust_and_kat.exact_canary_run_index_validator_implemented",
            "rust_and_kat.synthetic_manifest_run_binding_implemented",
            "rust_and_kat.transaction_profile_readback_implemented",
            "rust_and_kat.prepared_checkpoint_full_token_binding_implemented",
            "rust_and_kat.reopen_exact_cardinality_and_pending_intent_rejection_implemented",
            "rust_and_kat.action_permit_consumed_by_value_on_all_outcomes_implemented",
            "rust_and_kat.action_journal_exact_started_prefix_enforced",
            "rust_and_kat.synthetic_postrun_terminal_transition_implemented",
            "rust_and_kat.synthetic_kat_passed",
        ],
        "status mechanical completion list drift or rich-layer overclaim",
    )
    all_nonclaim_values_fail_closed(status["nonclaims"], "status.nonclaims")

    completion = successor["s20a_implementation"]
    require_exact_keys(
        completion,
        {
            "implementation_state", "post_kat_implementation_state",
            "private_default_off_synthetic_kernel_implemented",
            "s19_preflight_rich_packet_full_builder_and_validator_implemented",
            "s19_control_snapshot_rich_packet_full_builder_and_validator_implemented",
            "s19_authority_control_claim_rich_packet_full_builder_and_validator_implemented",
            "s19_post_run_bundle_rich_packet_full_builder_and_validator_implemented",
            "rich_packet_layer_blocked_pending_s20b",
            "runtime_full_packet_digest_recomputation_implemented",
            "runtime_full_cross_packet_binding_recomputation_implemented",
            "s17_32_rule_full_5639_row_semantic_validator_implemented",
            "synthetic_manifest_run_binding_implemented",
            "exact_assignment_membership_validator_implemented",
            "full_database_content_authentication_implemented",
            "transaction_profile_readback_implemented",
            "prepared_checkpoint_full_token_binding_implemented",
            "reopen_exact_cardinality_and_pending_intent_rejection_implemented",
            "action_permit_consumed_by_value_on_all_outcomes_implemented",
            "action_journal_exact_started_prefix_enforced",
            "synthetic_postrun_terminal_transition_implemented",
            "rich_postrun_receipt_implemented",
            "real_parent_directory_durability_adapter_implemented",
            "external_checkpoint_state_machine_implemented",
            "attempt_tombstone_state_machine_implemented",
            "action_start_linearization_state_machine_implemented",
            "exact_canary_run_index_validator_implemented", "synthetic_kat_passed",
            "real_checkpoint_adapter_implemented", "real_preflight_observer_implemented",
            "real_runner_implemented",
        },
        "successor.s20a_implementation",
    )
    require(completion["implementation_state"] == FINAL_IMPLEMENTATION_STATE, "successor implementation not mechanically complete")
    require(completion["post_kat_implementation_state"] == FINAL_IMPLEMENTATION_STATE, "successor post-KAT state drift")
    for key in (
        "private_default_off_synthetic_kernel_implemented",
        "external_checkpoint_state_machine_implemented",
        "attempt_tombstone_state_machine_implemented",
        "action_start_linearization_state_machine_implemented",
        "exact_canary_run_index_validator_implemented",
        "synthetic_kat_passed",
        "synthetic_manifest_run_binding_implemented",
        "transaction_profile_readback_implemented",
        "prepared_checkpoint_full_token_binding_implemented",
        "reopen_exact_cardinality_and_pending_intent_rejection_implemented",
        "action_permit_consumed_by_value_on_all_outcomes_implemented",
        "action_journal_exact_started_prefix_enforced",
        "synthetic_postrun_terminal_transition_implemented",
    ):
        require(completion[key] is True, f"successor completion field not true: {key}")
    for key in (
        "s19_preflight_rich_packet_full_builder_and_validator_implemented",
        "s19_control_snapshot_rich_packet_full_builder_and_validator_implemented",
        "s19_authority_control_claim_rich_packet_full_builder_and_validator_implemented",
        "s19_post_run_bundle_rich_packet_full_builder_and_validator_implemented",
        "runtime_full_packet_digest_recomputation_implemented",
        "runtime_full_cross_packet_binding_recomputation_implemented",
        "s17_32_rule_full_5639_row_semantic_validator_implemented",
        "exact_assignment_membership_validator_implemented",
        "full_database_content_authentication_implemented",
        "rich_postrun_receipt_implemented",
        "real_parent_directory_durability_adapter_implemented",
    ):
        require(completion[key] is False, f"successor misclaims full S19 rich packet layer: {key}")
    require(completion["rich_packet_layer_blocked_pending_s20b"] is True, "successor hides S20B blocker")
    for key in (
        "real_checkpoint_adapter_implemented",
        "real_preflight_observer_implemented",
        "real_runner_implemented",
    ):
        require(completion[key] is False, f"successor claims real implementation: {key}")
    for key, child in successor["s20_non_live_limits"].items():
        if key == "side_effects_unlocked":
            require(child == "NONE", "successor unlocks side effects")
        else:
            require(child is False, f"successor non-live limit is not false: {key}")
    assert_current_quiescent(successor["current_authority_and_execution"], "successor.current")
    require(successor["next_stage"]["preapproved"] is False, "successor preapproves S21")
    require(successor["next_stage"]["identity"] == S20B_IDENTITY, "successor does not bind exact S20B stage")
    require(successor["next_stage"]["requires_exact_authorized_assignment_membership_and_operation_descriptors"] is True, "successor hides assignment-membership blocker")
    require(successor["next_stage"]["requires_authenticated_database_content_root_or_equivalent_closed_writer_proof"] is True, "successor hides database-content-authentication blocker")
    require(successor["future_s21_live_boundary"]["preapproved"] is False, "successor preapproves future S21")
    all_nonclaim_values_fail_closed(successor["nonclaims"], "successor.nonclaims")


def validate_rust(repo: Path, overrides: Mapping[str, bytes] | None) -> int:
    source = read_text(repo, S20_RUST_PATH, overrides)
    required_tokens = (
        "#![cfg_attr(not(test), allow(dead_code))]",
        'const S20_FOUR_RICH_SCHEMAS_FULLY_IMPLEMENTED: bool = false;',
        'const S20_REAL_INDEPENDENT_CHECKPOINT_ADAPTER_PRESENT: bool = false;',
        'const S20_LIVE_ACTION_ADAPTER_PRESENT: bool = false;',
        'const S20_NEW_KERNEL_OWNER_REVIEW_BINDING_PRESENT: bool = false;',
        'const S20_EXACT_ASSIGNMENT_MEMBERSHIP_VALIDATOR_IMPLEMENTED: bool = false;',
        'const S20_FULL_DATABASE_CONTENT_AUTHENTICATION_IMPLEMENTED: bool = false;',
        'const S20_REAL_PARENT_DIRECTORY_DURABILITY_ADAPTER_PRESENT: bool = false;',
        'const S20_RICH_POSTRUN_RECEIPT_IMPLEMENTED: bool = false;',
        'const S20_EXACT_CANARY_INDEX_VALIDATOR_IMPLEMENTED: bool = true;',
        "PARTIAL_PREFLIGHT_SECURITY_PROJECTION_ONLY_FOUR_FROZEN_RICH_SCHEMAS_NOT_IMPLEMENTED",
        "reserve_preflight_once_v1",
        "validate_preflight_once_v1",
        "burn_claim_attempt_once_v1",
        "execute_burned_claim_once_v1",
        "linearize_synthetic_action_start_v1",
        "validate_partial_rich_security_projection_v1",
        "validate_exact_canary_accounting_v1",
        "action_sequence_from_zero_based_index_v1",
        "SYNTHETIC_MANIFEST_RUN_BOUND_NOT_ASSIGNMENT_MEMBERSHIP_PROOF",
        "SYNTHETIC_MANIFEST_RUN_BOUND_SEQUENCE_NOT_ASSIGNMENT_MEMBERSHIP_PROOF",
        "ACTION_SEQUENCE_ONE_BASED",
        "fn verify_s20_profile",
        "let prepared_matches = self.prepared.as_ref().is_some_and(",
        "ledger singleton or exact authorization cardinality drifted",
        "incomplete prior-controller attempt or action intent is non-resumable",
        "AB_S20_TEST_SCRATCH",
    )
    for token in required_tokens:
        require(token in source, f"S20 Rust token absent: {token}")
    forbidden = (
        r"\bstd::process::Command\b",
        r"\bTcpStream\b",
        r"\bTcpListener\b",
        r"\bUdpSocket\b",
        r"\bunsafe\s*\{",
        r"\blibc::(?:kill|mount|umount)",
        r"\bnix::[^\n]*(?:kill|mount)",
    )
    for pattern in forbidden:
        require(re.search(pattern, source) is None, f"live/unsafe Rust surface present: {pattern}")
    require("enum RichPacketKindV1" not in source, "partial S20A source claims a full rich packet enum")
    require("validate_exact_rich_packet_v1" not in source, "partial S20A source claims a full rich validator")

    claim_start = source.find("fn execute_burned_claim_once_v1")
    claim_end = source.find("mod starter_seal", claim_start)
    require(claim_start >= 0 and claim_end > claim_start, "cannot isolate exact claim kernel")
    claim = re.sub(r"\s+", " ", source[claim_start:claim_end])
    cas_fragments = (
        "UPDATE claim_ledger SET state='CONSUMED_FOR_EXACT_RUN',revision=?1, successful_claim_count=1",
        "run_id_sha256=?2,controller_binary_sha256=?3",
        "preflight_receipt_sha256=?4,control_snapshot_sha256=?5, claim_receipt_sha256=?6",
        "authorization_id_sha256=?7 AND claim_namespace_sha256=?8",
        "claim_key_sha256=?9 AND signed_payload_sha256=?10",
        "subject_manifest_sha256=?11 AND resource_scope_sha256=?12",
        "signed_revocation_epoch=?13 AND state='AUTHORIZED_UNCLAIMED'",
        "revision=?14 AND successful_claim_count=0 AND run_id_sha256 IS NULL",
        "controller_binary_sha256 IS NULL AND preflight_receipt_sha256 IS NULL",
        "control_snapshot_sha256 IS NULL AND claim_receipt_sha256 IS NULL",
        "runner_binary_sha256=?15 AND capability_nonce_sha256=?16",
        "control_ledger_identity_sha256=?17",
        "anti_rollback_policy_sha256=?18",
        "stop_state='CLEAR' AND stop_revision=?19",
        "current_revocation_epoch=?13 AND revocation_revision=?20",
        "stop_policy_identity_sha256=?21",
        "revocation_policy_identity_sha256=?22",
        "sqlite_profile_sha256=?23 AND sqlite_schema_sha256=?24",
        "to_sql_integer(authorized.authorization.revocation_epoch)?",
        "to_sql_integer(authorized.subject.expected_unclaimed_revision)?",
        "&authorized.subject.runner_binary_sha256[..]",
        "&authorized.capability_nonce_sha256[..]",
        "&authorized.subject.control_ledger_identity_sha256[..]",
        "&authorized.subject.anti_rollback_policy_sha256[..]",
        "&authorized.subject.stop_control_policy_sha256[..]",
        "&authorized.revocation_policy_sha256[..]",
        "&authorized.subject.sqlite_profile_sha256[..]",
        "&authorized.subject.sqlite_schema_sha256[..]",
        "let success = changed == 1;",
        "FAILED_CAS_PREDICATE",
        "ATTEMPT_CLAIM_FAILED",
    )
    for fragment in cas_fragments:
        require(fragment in claim, f"full claim CAS/control predicate absent: {fragment}")

    action_start = source.find("fn action_sequence_from_zero_based_index_v1")
    action_end = source.find("enum PartialRichSecurityProjectionKindV1", action_start)
    require(action_start >= 0 and action_end > action_start, "cannot isolate action linearization kernel")
    action = re.sub(r"\s+", " ", source[action_start:action_end])
    action_fragments = (
        "action_index_zero_based >= S20_ACTION_COUNT",
        "checked_add(1)",
        "&permit.run_assignment_id_sha256",
        "&permit.run_id_sha256",
        "&action_sequence.to_be_bytes()",
        "&operation_id_sha256",
        "&permit.claim_receipt_sha256",
        "&permit.controller_start_token_sha256",
        "INSERT INTO action_journal(",
        "run_assignment_id_sha256,operation_id_sha256,intent_sha256,outcome",
        "INTENT_DURABLE_SYNTHETIC",
        "starter.start_once(expected_action_index, intent)",
        "journal_changed != 1",
        "ACTION_START_LINEARIZED",
        "mut permit: ClaimedRunPermitS20V1",
        "AuthorizationResult<(ClaimedRunPermitS20V1, [u8; 32])>",
        "action journal is not one complete STARTED prefix",
        "POSTRUN_TERMINAL",
    )
    for fragment in action_fragments:
        require(fragment in action, f"exact action/operation binding absent: {fragment}")
    require("permit: &mut ClaimedRunPermitS20V1" not in action, "action permit remains reusable by reference")
    permit_match = re.search(r"struct ClaimedRunPermitS20V1\s*\{(?P<body>.*?)\n\}", source, re.S)
    require(permit_match is not None, "affine claimed permit absent")
    permit_prefix = source[max(0, permit_match.start() - 80):permit_match.start()]
    require("derive(Clone" not in permit_prefix, "claimed permit is cloneable")
    require("Rc<()>" in permit_match.group("body"), "claimed permit lacks process-local affine marker")

    tests = re.findall(r"(?m)^\s*fn\s+(s20_[a-z0-9_]+)\s*\(", source)
    require(len(tests) == len(set(tests)), "duplicate S20 Rust test name")
    expected_tests = {
        "s20_external_authority_preregistration_allows_only_one_preflight_reservation",
        "s20_failed_preflight_is_absorbing_across_revalidation",
        "s20_failed_claim_leaves_s19_row_unclaimed_but_attempt_terminal_after_reopen",
        "s20_full_claim_predicate_runner_drift_is_zero_row_and_terminal",
        "s20_checkpoint_prepared_fork_and_old_file_replacement_fail_closed",
        "s20_unknown_checkpoint_commit_absorbs_without_returning_a_token",
        "s20_attempt_trigger_rejects_stage_binding_drift_and_delete",
        "s20_stop_and_action_start_have_one_writer_order_and_no_after_guard",
        "s20_stop_replay_zero_row_is_rejected",
        "s20_zero_based_action_index_projects_to_one_based_receipt_sequence",
        "s20_partial_rich_projection_rejects_canonical_and_cross_binding_drift",
        "s20_no_live_effect_or_authority_counts_exist",
        "s20_exact_canary_index_distinguishes_synthetic_zero_and_complete_exact",
    }
    require(set(tests) == expected_tests, f"S20 synthetic KAT catalog drift: {sorted(set(tests) ^ expected_tests)}")
    return len(tests) + 1


def validate_docs(repo: Path, overrides: Mapping[str, bytes] | None) -> None:
    design = read_text(repo, DESIGN_PATH, overrides)
    report = read_text(repo, REPORT_PATH, overrides)
    for token in (
        STATUS,
        DECISION,
        "NON_LIVE",
        "SYNTHETIC",
        "OL00",
        "OL04",
        "OL05",
        S20B_IDENTITY,
        "side_effects_unlocked=NONE",
    ):
        require(token in design or token in report, f"required design/report token absent: {token}")


def validate_bundle(
    repo: Path, overrides: Mapping[str, bytes] | None = None
) -> list[tuple[str, str]]:
    verify_frozen_s19(repo, overrides)
    verify_exact_parent_edits(repo, overrides)
    schema_receipts = validate_schema_fixture_pairs(repo, overrides)
    validate_control_documents(repo, overrides)
    rust_test_count = validate_rust(repo, overrides)
    validate_docs(repo, overrides)

    rows: list[tuple[str, str]] = [
        ("schema", "agent_bridge.memory_temporal_owned_lab_trusted_controller_orchestration_s20.check.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("implementation_mode", MODE),
        ("implementation_state", FINAL_IMPLEMENTATION_STATE),
        ("successor_identity", S20B_IDENTITY),
        ("baseline_commit", BASELINE_COMMIT),
        ("baseline_tree", BASELINE_TREE),
        ("s19_source_commit", S19_SOURCE_COMMIT),
        ("s19_source_tree", S19_SOURCE_TREE),
        ("feature", FEATURE),
        ("s19_frozen_schema_count", "5"),
        ("s20_closed_schema_count", "4"),
        ("s20_synthetic_fixture_count", "4"),
        ("rust_s20_test_count", str(rust_test_count)),
        ("canary_family_counts", "OL00=1,OL04=6,OL05=53"),
        ("canary_assigned_attempt_count", "60"),
        ("canary_pidfd_sigkill_attempt_count", "59"),
        ("canary_distinct_fresh_exec_read_count", "59"),
        ("canary_s16_mapping_phase_record_count", "113"),
        ("actual_authority_input_count", "0"),
        ("actual_live_action_count", "0"),
        ("live_canary", "NOT_RUN"),
        ("side_effects_unlocked", "NONE"),
        ("synthetic_manifest_run_binding_implemented", "true"),
        ("exact_assignment_membership_validator_implemented", "false"),
        ("full_database_content_authentication_implemented", "false"),
        ("action_permit_consumed_by_value_on_all_outcomes", "true"),
        ("rich_postrun_receipt_implemented", "false"),
        ("self_test_mutation_count", "8"),
    ]
    for key in sorted(schema_receipts):
        rows.append((key, schema_receipts[key]))
    for key, relative in ARTIFACT_ROWS:
        rows.append((key, sha256(read_bytes(repo, relative, overrides))))
    return rows


def expect_failure(repo: Path, relative: str, mutated: bytes, expected_message: str) -> None:
    try:
        validate_bundle(repo, {relative: mutated})
    except CheckFailure as exc:
        require(
            expected_message in str(exc),
            f"self-test mutation failed for the wrong reason ({relative}): {exc}",
        )
        return
    raise CheckFailure(f"self-test mutation was accepted: {relative}")


def run_self_test(repo: Path, seed: int) -> None:
    # Establish a valid control first so an unrelated baseline failure cannot
    # make every negative mutation look correctly rejected.
    validate_bundle(repo)
    mutations: list[tuple[str, bytes, str]] = []
    fixture = read_bytes(repo, CHECKPOINT_FIXTURE_PATH)
    mutations.append((CHECKPOINT_FIXTURE_PATH, fixture.replace(b"{", b'{"schema":"duplicate",', 1), "duplicate JSON key"))
    mutations.append((CHECKPOINT_FIXTURE_PATH, fixture.replace(b'"synthetic":true', b'"synthetic":1.5', 1), "floating-point JSON forbidden"))
    fixture_value = parse_json(fixture, CHECKPOINT_FIXTURE_PATH)
    fixture_value["checkpoint_receipt_sha256"] = "0" * 64
    digest_mutation = json.dumps(
        fixture_value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii") + b"\n"
    mutations.append((CHECKPOINT_FIXTURE_PATH, digest_mutation, "fixture self hash is not independently recomputed value"))
    false_independence = parse_json(fixture, CHECKPOINT_FIXTURE_PATH)
    false_independence["checkpoint_binding"]["independent_failure_domain_proved"] = True
    false_independence.pop("checkpoint_receipt_sha256")
    false_payload = json.dumps(
        false_independence, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    false_domain = false_independence["hashing_contract"]["digest_domain"].encode("ascii")
    false_independence["checkpoint_receipt_sha256"] = sha256(
        len(false_domain).to_bytes(4, "big")
        + false_domain
        + len(false_payload).to_bytes(8, "big")
        + false_payload
    )
    false_independence_mutation = json.dumps(
        false_independence, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii") + b"\n"
    mutations.append((CHECKPOINT_FIXTURE_PATH, false_independence_mutation, "synthetic checkpoint must not claim an independently proved failure domain"))
    schema = read_bytes(repo, CHECKPOINT_SCHEMA_PATH)
    mutations.append((CHECKPOINT_SCHEMA_PATH, schema.replace(b'"#/$defs/sha256"', b'"https://invalid.example/schema"', 1), "external schema ref"))
    status = read_bytes(repo, STATUS_PATH)
    mutations.append((STATUS_PATH, status.replace(b'"real_runner_present": false', b'"real_runner_present": true', 1), "current real/live authority present"))
    rust = read_bytes(repo, S20_RUST_PATH)
    mutations.append(
        (
            S20_RUST_PATH,
            rust.replace(
                b"runner_binary_sha256=?15 AND capability_nonce_sha256=?16",
                b"runner_binary_sha256=?15 AND capability_nonce_sha256=?99",
                1,
            ),
            "full claim CAS/control predicate absent",
        )
    )
    cargo = read_bytes(repo, CARGO_PATH)
    mutations.append((CARGO_PATH, cargo + b"# unauthorized mutation\n", "Cargo.toml contains changes outside"))
    require(all(original != mutated for (_, original), (_, mutated, _) in zip(
        [
            (CHECKPOINT_FIXTURE_PATH, fixture),
            (CHECKPOINT_FIXTURE_PATH, fixture),
            (CHECKPOINT_FIXTURE_PATH, fixture),
            (CHECKPOINT_FIXTURE_PATH, fixture),
            (CHECKPOINT_SCHEMA_PATH, schema),
            (STATUS_PATH, status),
            (S20_RUST_PATH, rust),
            (CARGO_PATH, cargo),
        ],
        mutations,
    )), "self-test mutation construction failed")
    random.Random(seed).shuffle(mutations)
    for relative, mutated, expected_message in mutations:
        expect_failure(repo, relative, mutated, expected_message)


def render(rows: list[tuple[str, str]]) -> str:
    require(len(rows) == len({key for key, _ in rows}), "duplicate receipt key")
    for key, value in rows:
        require("\t" not in key + value and "\n" not in key + value, "invalid receipt field")
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--seed", type=int, default=20)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    require(repo.is_dir() and not repo.is_symlink(), "repository root must be canonical directory")
    if args.self_test:
        run_self_test(repo, args.seed)
    sys.stdout.write(render(validate_bundle(repo)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print(f"S20 orchestration checker failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
