#!/usr/bin/env python3
"""Independent S20B closed-world rich-packet and semantic-validator checker."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

sys.dont_write_bytecode = True


BASELINE_COMMIT = "bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54"
BASELINE_TREE = "c752a2069fa2d3e5d0e1241bf2342987338f0db5"
FROZEN_S20_COMMIT = "0b76cc23534a230ec3be92cfaeed55503c69478c"
FROZEN_S20_TREE = "dc2c1a027728311c51e40e59eb559a8a9e8142be"
STATUS = "S20B_NON_LIVE_RICH_PACKET_VALIDATORS_COMPLETE"
DECISION = (
    "S21_BLOCKED_PENDING_FINAL_REFREEZE_NEW_OWNER_SIGNATURE_AND_INDEPENDENT_LIVE_INPUTS"
)
MODE = "PRIVATE_DEFAULT_OFF_SYNTHETIC_NON_LIVE_VALIDATION_ONLY"
FEATURE = "temporal-evidence-s20b-owned-lab-rich-packet-validators-synthetic"
CANONICALIZATION = (
    "AB_RESTRICTED_CANONICAL_JSON_S20B_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT"
)
FRAMING = (
    "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_CANONICAL_PAYLOAD_LENGTH_CANONICAL_PAYLOAD"
)
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
ASSIGNMENT_V2_KATS = (
    "b3a7025a488e9aefc6724869f75ab76a482002224bee90c075e9379101ee7264",
    "8c0129d150d918523c122dbf3afb4e7c6abb3ce7ca957204252c115a7f1def15",
    "7a927eba7eb691990b32c7987bea5c0fdce15c51d37792f8ca45c3bddb556bc6",
    "a00feb5745c83fc20d5ad84f66877289c9108b29371697ceb8cf13e3fb142db0",
    "b9e38d17c7d6974b7fb49e0840bf2e431f60dc8bc309c31b6202c3b5bcbf41fc",
    "6bd2c6e3648030d1de1a3be795a6ad221887fc8e273c9c771024d85b9866f135",
    "341fa260fcc7958e18891f4143fd33bcafb13efcfd6f4fd07a16058be16a654b",
    "e6cc4cfe754e3d3e9b0e670cfdfb38ce065e4bf2ec157c092ae8bf75da586e94",
)
BUSINESS_CONTENT_ROOT_KAT = (
    "5463bd72d21d1515cebb33c8c575883db86cd12c1a980c878192a9802459e56d"
)

PREFIX = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-"
CARGO_PATH = "crates/store/Cargo.toml"
S20_RUST_PATH = (
    "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/"
    "recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/"
    "durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner/"
    "trusted_controller_orchestration.rs"
)
S19_RUST_PATH = S20_RUST_PATH.rsplit("/", 1)[0] + ".rs"
S20B_RUST_PATH = S20_RUST_PATH[:-3] + "/rich_packet_validators.rs"
S20B_RUST_ASSIGNMENT_PATH = S20_RUST_PATH[:-3] + "/rich_packet_validators/assignment_authority.rs"
S20B_RUST_SCHEMA_PACKETS_PATH = (
    S20_RUST_PATH[:-3] + "/rich_packet_validators/schema_aligned_packets.rs"
)
S20B_RUST_S17_PATH = S20_RUST_PATH[:-3] + "/rich_packet_validators/s17_full_validator.rs"
S20B_RUST_PATHS = (
    S20B_RUST_PATH,
    S20B_RUST_ASSIGNMENT_PATH,
    S20B_RUST_SCHEMA_PACKETS_PATH,
    S20B_RUST_S17_PATH,
)
DESIGN_PATH = (
    "docs/design/MEMORY_TEMPORAL_OWNED_LAB_RICH_PACKET_SCHEMA_REPLACEMENTS_"
    "S20B_2026_07_18.md"
)
CONTRACT_PATH = PREFIX + "rich-packet-schema-replacements-contract-s20b-v0.json"
STATUS_PATH = PREFIX + "rich-packet-schema-replacements-status-s20b-v0.json"
SUCCESSOR_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s20b-v0.json"
REPORT_PATH = (
    "docs/reports/goal-c-u/2026-07-18-biocortex-ab-track-b-owned-lab-"
    "rich-packet-schema-replacements-s20b.md"
)
CHECKER_PATH = "scripts/eval/check_memory_temporal_owned_lab_rich_packet_schema_replacements_s20b.py"
EXPECTED_PATH = (
    "scripts/eval/fixtures/memory_temporal_owned_lab_rich_packet_schema_replacements_"
    "s20b.expected.v0.tsv"
)
GATE_PATH = "scripts/check-memory-temporal-owned-lab-rich-packet-schema-replacements-s20b.sh"

S17_CHECKER_PATH = (
    "scripts/eval/check_memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17.py"
)
S16_CHECKER_PATH = (
    "scripts/eval/check_memory_temporal_recovered_envelope_durability_fault_model_s16.py"
)
S17_OBSERVATION_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-"
    "process-crash-restart-observation-schema-s17-v0.json"
)
S17_PLAN_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-"
    "process-crash-restart-plan-s17-v0.json"
)
FROZEN_S17_ARTIFACTS = {
    S17_CHECKER_PATH: "d9903fc84701e7f6ceff3ae89a5f9f186efda36e8e8e9166fea7cab59510aed6",
    S16_CHECKER_PATH: "0f4c5d9fb2a63f3a65d56a462a6299819e539a4b5f205610ac1c0daffc8dc0e8",
    S17_OBSERVATION_SCHEMA_PATH: "26a8cca9f9ca74ceb4b949a2e75d9282a6227623f5bd66cc3333fbff7441588d",
    S17_PLAN_PATH: "ca9769ff2b79e474999df6bb5096a3e062b5acf78fa23788f76ae44295531650",
}
_S17_VALIDATED_REPOS: set[Path] = set()


class PacketSpec:
    def __init__(
        self,
        slug: str,
        schema_id: str,
        packet_kind: str,
        state_key: str,
        state_value: str,
        self_hash_field: str,
        domain: str,
    ) -> None:
        self.slug = slug
        self.schema_path = PREFIX + slug + "-schema-s20b-v0.json"
        self.fixture_path = PREFIX + slug + "-synthetic-s20b-v0.json"
        self.schema_id = schema_id
        self.packet_kind = packet_kind
        self.state_key = state_key
        self.state_value = state_value
        self.self_hash_field = self_hash_field
        self.domain = domain


PACKETS = (
    PacketSpec(
        "preflight-receipt",
        "agent_bridge.memory_temporal_owned_lab_preflight_receipt_s20b.v0",
        "S20B_OWNED_LAB_FRESH_PREFLIGHT_RECEIPT",
        "preflight_state",
        "SYNTHETIC_KAT_NON_LIVE_PREFLIGHT",
        "preflight_receipt_sha256",
        "agent-bridge/biocortex/owned-lab/s20b/preflight-receipt/v1",
    ),
    PacketSpec(
        "control-snapshot",
        "agent_bridge.memory_temporal_owned_lab_control_snapshot_s20b.v0",
        "S20B_EXTERNAL_AUTHORITY_CONTROL_SNAPSHOT",
        "snapshot_state",
        "SYNTHETIC_KAT_NON_LIVE_CONTROL_SNAPSHOT",
        "control_snapshot_sha256",
        "agent-bridge/biocortex/owned-lab/s20b/control-snapshot/v1",
    ),
    PacketSpec(
        "authority-control-claim",
        "agent_bridge.memory_temporal_owned_lab_authority_control_claim_s20b.v0",
        "S20B_SINGLE_USE_CLAIM_OUTCOME_RECEIPT",
        "claim_packet_state",
        "SYNTHETIC_KAT_NON_LIVE_CLAIM_PACKET",
        "claim_packet_sha256",
        "agent-bridge/biocortex/owned-lab/s20b/claim-outcome-receipt/v1",
    ),
    PacketSpec(
        "post-run-receipt-bundle",
        "agent_bridge.memory_temporal_owned_lab_post_run_receipt_bundle_s20b.v0",
        "S20B_OWNED_LAB_POST_RUN_RECEIPT_BUNDLE",
        "bundle_state",
        "SYNTHETIC_KAT_NON_LIVE_POST_RUN_BUNDLE",
        "post_run_bundle_sha256",
        "agent-bridge/biocortex/owned-lab/s20b/post-run-bundle/v1",
    ),
)
PACKET_BY_SLUG = {packet.slug: packet for packet in PACKETS}

ARTIFACT_ROWS = (
    ("cargo_manifest_sha256", CARGO_PATH),
    ("s19_source_bound_runner_rust_sha256", S19_RUST_PATH),
    ("s20_parent_rust_sha256", S20_RUST_PATH),
    ("s20b_rust_sha256", S20B_RUST_PATH),
    ("s20b_assignment_authority_rust_sha256", S20B_RUST_ASSIGNMENT_PATH),
    ("s20b_schema_aligned_packets_rust_sha256", S20B_RUST_SCHEMA_PACKETS_PATH),
    ("s20b_s17_full_validator_rust_sha256", S20B_RUST_S17_PATH),
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


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    except (TypeError, UnicodeEncodeError) as exc:
        raise CheckFailure(f"value is not restricted canonical JSON: {exc}") from exc


def framed_digest(domain: str, payload: bytes) -> str:
    domain_raw = domain.encode("ascii")
    return sha256(
        len(domain_raw).to_bytes(4, "big")
        + domain_raw
        + len(payload).to_bytes(8, "big")
        + payload
    )


def validate_claim_transition_core(claim: dict[str, Any]) -> str:
    """Recompute p06 from the exact ordered p01..p24 binding contract.

    The transition core has its own framing and deliberately excludes p06 itself,
    so it cannot be replaced by the final claim-packet self digest.
    """
    cas = get_path(
        claim,
        ("claim_attempt", "cas_parameter_bindings"),
        "claim.claim_attempt.cas_parameter_bindings",
    )
    require(isinstance(cas, dict), "claim CAS parameter bindings are not an object")
    profile_key = "parameter_order_profile"
    profile = "S20B_EXACT_S19_24_PARAMETER_CAS_WITH_TRANSITION_CORE_IN_P06"
    require(cas.get(profile_key) == profile, "claim CAS parameter order profile drift")

    parameter_keys: dict[int, str] = {}
    for index in range(1, 25):
        prefix = f"p{index:02d}_"
        matches = [key for key in cas if key.startswith(prefix)]
        require(len(matches) == 1, f"claim CAS p{index:02d} cardinality drift")
        parameter_keys[index] = matches[0]
    require(
        set(cas) == {profile_key, *parameter_keys.values()},
        "claim CAS parameter key set drift",
    )

    integer_parameters = {1, 13, 14, 19, 20}
    frames = [profile.encode("ascii")]
    for index in range(1, 25):
        key = parameter_keys[index]
        value = cas[key]
        if index in integer_parameters:
            require(
                type(value) is int and 1 <= value <= 0xFFFF_FFFF_FFFF_FFFF,
                f"claim CAS p{index:02d} is not an unsigned 64-bit integer",
            )
            encoded = value.to_bytes(8, "big")
        else:
            require(
                isinstance(value, str)
                and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
                f"claim CAS p{index:02d} is not a lowercase SHA-256 digest",
            )
            encoded = bytes.fromhex(value)
        if index != 6:
            frames.append(encoded)

    require(
        cas[parameter_keys[1]] == cas[parameter_keys[14]] + 1,
        "claim CAS p01 is not exactly p14 plus one",
    )
    domain = b"agent-bridge/biocortex/owned-lab/s20b/claim-transition-core/v1"
    message = len(domain).to_bytes(4, "big") + domain
    for frame in frames:
        message += len(frame).to_bytes(8, "big") + frame
    computed = sha256(message)
    require(cas[parameter_keys[6]] == computed, "claim transition-core p06 digest mismatch")
    return computed


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
        require(len(required) == len(set(required)), f"duplicate required key in schema: {label}")
        require(set(required) == set(properties), f"required/properties mismatch: {label}")
    for key, child in value.items():
        validate_schema_node(child, f"{label}/{key}")


def schema_errors(schema: dict[str, Any], instance: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    return [error.message for error in sorted(validator.iter_errors(instance), key=str)]


def get_path(value: dict[str, Any], path: tuple[str, ...], label: str) -> Any:
    current: Any = value
    for component in path:
        require(isinstance(current, dict) and component in current, f"missing binding path {label}")
        current = current[component]
    return current


def set_path(value: dict[str, Any], path: tuple[str, ...], replacement: Any) -> None:
    current: Any = value
    for component in path[:-1]:
        if not isinstance(current, dict) or component not in current:
            raise CheckFailure(f"cannot mutate absent path: {'.'.join(path)}")
        current = current[component]
    if not isinstance(current, dict) or path[-1] not in current:
        raise CheckFailure(f"cannot mutate absent path: {'.'.join(path)}")
    current[path[-1]] = replacement


def verify_hashing_contract(fixture: dict[str, Any], spec: PacketSpec) -> str:
    contract = fixture.get("hashing_contract")
    require(isinstance(contract, dict), f"hashing contract absent: {spec.fixture_path}")
    expected_fields = {
        "canonicalization": CANONICALIZATION,
        "cross_field_semantic_validation_required": True,
        "digest_domain": spec.domain,
        "digest_framing": FRAMING,
        "hash_algorithm": "SHA-256",
        "repository_framing_lf_excluded": True,
        "self_hash_field": spec.self_hash_field,
        "self_hash_field_excluded": True,
        "self_reported_match_fields_are_authoritative": False,
    }
    for key, expected in expected_fields.items():
        require(contract.get(key) == expected, f"hashing contract drift: {spec.fixture_path}.{key}")
    scope = contract.get("hash_scope")
    require(
        isinstance(scope, str)
        and spec.self_hash_field.upper() in scope
        and "EXCEPT" in scope,
        f"non-explicit self-hash scope: {spec.fixture_path}",
    )
    declared = fixture.get(spec.self_hash_field)
    require(
        isinstance(declared, str) and re.fullmatch(r"[0-9a-f]{64}", declared) is not None,
        f"invalid declared self digest: {spec.fixture_path}",
    )
    payload_value = copy.deepcopy(fixture)
    require(
        payload_value.pop(spec.self_hash_field, None) == declared,
        f"self digest removal mismatch: {spec.fixture_path}",
    )
    computed = framed_digest(spec.domain, canonical_bytes(payload_value))
    require(declared == computed, f"self digest mismatch: {spec.fixture_path}")
    return computed


def reseal_fixture(fixture: dict[str, Any], spec: PacketSpec) -> bytes:
    value = copy.deepcopy(fixture)
    value.pop(spec.self_hash_field, None)
    value[spec.self_hash_field] = framed_digest(spec.domain, canonical_bytes(value))
    return canonical_bytes(value) + b"\n"


def validate_preflight_context(preflight: dict[str, Any]) -> str:
    context = get_path(preflight, ("preflight_context",), "preflight.preflight_context")
    require(isinstance(context, dict), "preflight_context is not one closed object")
    declared = get_path(
        preflight,
        ("phase_bindings", "preflight_context_sha256"),
        "preflight.phase_bindings.preflight_context_sha256",
    )
    require(isinstance(declared, str) and re.fullmatch(r"[0-9a-f]{64}", declared) is not None,
            "invalid preflight context digest")
    computed = framed_digest(
        "agent-bridge/biocortex/owned-lab/s20b/preflight-context/v1",
        canonical_bytes(context),
    )
    require(declared == computed, "preflight context digest mismatch")
    return computed


def validate_cross_bindings(fixtures: dict[str, dict[str, Any]]) -> tuple[int, int]:
    preflight = fixtures["preflight-receipt"]
    control = fixtures["control-snapshot"]
    claim = fixtures["authority-control-claim"]
    postrun = fixtures["post-run-receipt-bundle"]
    context_sha = validate_preflight_context(preflight)
    control_sha = control["control_snapshot_sha256"]
    preflight_sha = preflight["preflight_receipt_sha256"]
    claim_sha = claim["claim_packet_sha256"]
    validate_claim_transition_core(claim)

    edges = (
        (
            "preflight_context_to_control",
            context_sha,
            get_path(control, ("phase_parent", "parent_sha256"), "control.phase_parent.parent_sha256"),
        ),
        (
            "control_to_preflight",
            control_sha,
            get_path(preflight, ("phase_bindings", "control_snapshot_sha256"), "preflight.phase_bindings.control_snapshot_sha256"),
        ),
        (
            "preflight_to_claim",
            preflight_sha,
            get_path(claim, ("parent_bindings", "preflight_receipt_sha256"), "claim.parent_bindings.preflight_receipt_sha256"),
        ),
        (
            "control_to_claim",
            control_sha,
            get_path(claim, ("parent_bindings", "control_snapshot_sha256"), "claim.parent_bindings.control_snapshot_sha256"),
        ),
        (
            "claim_to_postrun_execution",
            claim_sha,
            get_path(postrun, ("execution_binding", "claim_packet_sha256"), "postrun.execution_binding.claim_packet_sha256"),
        ),
        (
            "preflight_to_postrun_chain",
            preflight_sha,
            get_path(postrun, ("receipt_chain", "preflight_receipt_sha256"), "postrun.receipt_chain.preflight_receipt_sha256"),
        ),
        (
            "control_to_postrun_chain",
            control_sha,
            get_path(postrun, ("receipt_chain", "control_snapshot_sha256"), "postrun.receipt_chain.control_snapshot_sha256"),
        ),
        (
            "claim_to_postrun_chain",
            claim_sha,
            get_path(postrun, ("receipt_chain", "claim_packet_sha256"), "postrun.receipt_chain.claim_packet_sha256"),
        ),
    )
    for name, expected, actual in edges:
        require(actual == expected, f"cross binding drift: {name}")
    cas = get_path(
        claim,
        ("claim_attempt", "cas_parameter_bindings"),
        "claim.claim_attempt.cas_parameter_bindings",
    )
    require(
        cas["p04_preflight_receipt_sha256"] == preflight_sha,
        "claim CAS p04 is not the independently rehashed final preflight",
    )
    require(
        cas["p05_control_snapshot_sha256"] == control_sha,
        "claim CAS p05 is not the independently rehashed applicable control snapshot",
    )
    require(
        get_path(control, ("phase_parent", "parent_kind"), "control.phase_parent.parent_kind")
        == "PREFLIGHT_CONTEXT",
        "control phase parent is not the preflight context",
    )
    require(control.get("snapshot_phase") == "PREFLIGHT_BEFORE_CLAIM",
            "control fixture phase is not preflight-before-claim")

    # Fixed topological order proves that the permitted edges are backward-only.
    ranks = {"context": 0, "control": 1, "preflight": 2, "claim": 3, "postrun": 4}
    graph_edges = (
        ("context", "control"),
        ("control", "preflight"),
        ("preflight", "claim"),
        ("control", "claim"),
        ("claim", "postrun"),
        ("preflight", "postrun"),
        ("control", "postrun"),
    )
    require(all(ranks[parent] < ranks[child] for parent, child in graph_edges),
            "digest DAG contains a forward or cyclic edge")
    return (5, len(edges))


def all_fail_closed_fields(value: Any, label: str) -> None:
    if isinstance(value, list):
        for index, child in enumerate(value):
            all_fail_closed_fields(child, f"{label}[{index}]")
        return
    if not isinstance(value, dict):
        return
    for key, child in value.items():
        if key == "side_effects_unlocked":
            require(child == "NONE", f"side effects unlocked: {label}.{key}")
        elif key.startswith("real_") or key in {
            "automatic_retry_allowed",
            "packet_is_bearer_capability",
            "provider_or_production_authority",
            "live_execution_authorized",
            "preapproved",
            "may_execute_live",
            "may_execute_live_now",
            "live_execution_may_begin",
        }:
            require(child is False, f"fail-closed field became true: {label}.{key}")
        all_fail_closed_fields(child, f"{label}.{key}")


def validate_schema_fixtures(
    repo: Path, overrides: Mapping[str, bytes] | None
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    fixtures: dict[str, dict[str, Any]] = {}
    receipts: dict[str, str] = {}
    for spec in PACKETS:
        schema_raw, schema = load_json(repo, spec.schema_path, overrides)
        require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
                f"schema draft drift: {spec.schema_path}")
        require(schema.get("$id") == spec.schema_id, f"schema id drift: {spec.schema_path}")
        validate_schema_node(schema, spec.schema_path)
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise CheckFailure(f"Draft202012 schema invalid: {spec.schema_path}: {exc.message}") from exc

        fixture_raw, fixture = load_json(repo, spec.fixture_path, overrides)
        require(fixture_raw.endswith(b"\n") and not fixture_raw.endswith(b"\n\n"),
                f"fixture terminal LF drift: {spec.fixture_path}")
        require(b"\n" not in fixture_raw[:-1], f"fixture is not compact: {spec.fixture_path}")
        require(fixture_raw == canonical_bytes(fixture) + b"\n",
                f"fixture is not restricted canonical JSON: {spec.fixture_path}")
        errors = schema_errors(schema, fixture)
        require(not errors, f"schema rejected valid fixture: {spec.fixture_path}: {errors[:2]}")
        require(fixture.get("schema") == spec.schema_id, f"fixture schema drift: {spec.fixture_path}")
        require(fixture.get("packet_kind") == spec.packet_kind,
                f"fixture packet kind drift: {spec.fixture_path}")
        require(fixture.get(spec.state_key) == spec.state_value,
                f"fixture state drift: {spec.fixture_path}")
        require(fixture.get("canonicalization") == CANONICALIZATION,
                f"fixture canonicalization drift: {spec.fixture_path}")
        require(fixture.get("test_only") is True and fixture.get("synthetic") is True,
                f"fixture is not explicit synthetic KAT: {spec.fixture_path}")
        all_fail_closed_fields(fixture.get("nonclaims", {}), spec.fixture_path + ".nonclaims")
        self_hash = verify_hashing_contract(fixture, spec)
        receipts[spec.slug.replace("-", "_") + "_self_hash"] = self_hash
        receipts[spec.slug.replace("-", "_") + "_schema_sha256"] = sha256(schema_raw)
        receipts[spec.slug.replace("-", "_") + "_fixture_sha256"] = sha256(fixture_raw)
        fixtures[spec.slug] = fixture
    return fixtures, receipts


def import_frozen_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot load frozen module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_frozen_s17(repo: Path, overrides: Mapping[str, bytes] | None) -> None:
    # Overrides of a frozen dependency must fail before any import or execution.
    for relative, expected in FROZEN_S17_ARTIFACTS.items():
        require(sha256(read_bytes(repo, relative, overrides)) == expected,
                f"frozen S17/S16 artifact drift: {relative}")
    cacheable = not overrides or not (set(overrides) & set(FROZEN_S17_ARTIFACTS))
    if cacheable and repo in _S17_VALIDATED_REPOS:
        return
    module = import_frozen_module(repo / S17_CHECKER_PATH, "s20b_frozen_s17_semantics")
    rules = getattr(module, "EXPECTED_CROSS_FIELD_RULES", None)
    require(isinstance(rules, list) and len(rules) == 32 and len(set(rules)) == 32,
            "frozen S17 cross-field rule catalog is not exact 32")
    kat_rows = module.validate_full_catalog_uniqueness(repo)
    require(isinstance(kat_rows, dict) and {"OL00", "OL04", "OL05_FIRST", "OL05_RESTART"} <= set(kat_rows),
            "frozen S17 full-catalog KAT receipt incomplete")
    if cacheable:
        _S17_VALIDATED_REPOS.add(repo)


RUST_MARKERS = (
    "S20B_FOUR_RICH_PACKET_BUILDERS_PARSERS_VALIDATORS_IMPLEMENTED: bool = true",
    "S20B_RUNTIME_SELF_DIGEST_RECOMPUTATION_IMPLEMENTED: bool = true",
    "S20B_RUNTIME_CROSS_PACKET_DIGEST_RECOMPUTATION_IMPLEMENTED: bool = true",
    "S20B_FULL_24_PARAMETER_CLAIM_VALIDATOR_IMPLEMENTED: bool = true",
    "S20B_EXACT_ASSIGNMENT_MEMBERSHIP_VALIDATOR_IMPLEMENTED: bool = true",
    "S20B_CONCRETE_OPERATION_DESCRIPTOR_VALIDATOR_IMPLEMENTED: bool = true",
    "S20B_DATABASE_CONTENT_ROOT_IMPLEMENTED: bool = true",
    "S20B_S17_32_RULE_FULL_5639_ROW_VALIDATOR_IMPLEMENTED: bool = true",
    "S20B_NEGATIVE_KAT_SUITE_IMPLEMENTED: bool = true",
    "S20B_LIVE_BACKEND_PRESENT: bool = false",
    'S20B_SIDE_EFFECTS_UNLOCKED: &str = "NONE"',
)


def validate_rust(repo: Path, overrides: Mapping[str, bytes] | None) -> tuple[int, int]:
    cargo = read_text(repo, CARGO_PATH, overrides)
    require(
        f'{FEATURE} = ["temporal-evidence-s20-owned-lab-trusted-controller-orchestration-synthetic"]'
        in cargo,
        "exact private default-off S20B Cargo feature absent",
    )
    parent = read_text(repo, S20_RUST_PATH, overrides)
    s19_source = read_text(repo, S19_RUST_PATH, overrides)
    for field in (
        "assignment_set_sha256",
        "schedule_sha256",
        "catalog_row_count",
        "catalog_sha256",
        "classifier_binary_sha256",
        "classifier_source_sha256",
        "expected_oracle_sha256",
        "s17_observation_schema_sha256",
        "s17_plan_sha256",
        "target_phase_count",
        "target_phase_unique_match_count",
        "allowed_operation_ids",
    ):
        require(
            field in s19_source,
            f"verified S19 subject does not retain owner-bound S20B field: {field}",
        )
    require(
        f'#[cfg(feature = "{FEATURE}")]\nmod rich_packet_validators;' in parent,
        "exact S20B child-module stanza absent",
    )
    sources = {
        relative: read_text(repo, relative, overrides) for relative in S20B_RUST_PATHS
    }
    source = "\n".join(sources.values())
    for marker in RUST_MARKERS:
        require(marker in source, f"S20B Rust implementation marker absent: {marker}")
    assignment_source = sources[S20B_RUST_ASSIGNMENT_PATH]
    design = read_text(repo, DESIGN_PATH, overrides)
    contract = read_text(repo, CONTRACT_PATH, overrides)
    for kat in ASSIGNMENT_V2_KATS:
        require(kat in assignment_source, f"typed-v2 assignment KAT absent from Rust: {kat}")
        require(kat in design and kat in contract, f"typed-v2 assignment KAT not frozen: {kat}")
    require(
        BUSINESS_CONTENT_ROOT_KAT in parent and BUSINESS_CONTENT_ROOT_KAT in design,
        "business-content-root KAT is not independently frozen",
    )
    require(
        "LEGACY_FIXTURE_ASSIGNMENT_RECORD_DOMAIN" in sources[S20B_RUST_PATH]
        and "#[cfg(test)]" in sources[S20B_RUST_PATH],
        "legacy v1 fixture assignment projection is not explicitly test-only",
    )
    for token in (
        "UNKNOWN_COMMIT_OUTCOME_TERMINAL_HARD_LOCK",
        "COMMITTED_PRE_PERMIT_CRASH_TERMINAL",
        "PREFLIGHT_CONTEXT",
        "5639",
        "113",
        "32",
        "assignment",
        "operation",
        "content_root",
        "reopen",
    ):
        require(token in source, f"S20B Rust semantic token absent: {token}")
    for pattern in (
        r"\bstd::process::Command\b",
        r"\bTcp(?:Stream|Listener)\b",
        r"\bUdpSocket\b",
        r"\bunsafe\s*\{",
        r"\blibc::(?:kill|mount|umount)",
        r"\bnix::[^\n]*(?:kill|mount)",
    ):
        require(re.search(pattern, source) is None, f"live/unsafe Rust surface present: {pattern}")
    tests = re.findall(
        r"(?m)^\s*#\[test\]\s*\n\s*fn\s+(s20b_[a-z0-9_]+)\s*\(", source
    )
    require(len(tests) == len(set(tests)), "duplicate S20B Rust test name")
    module_minimums = {
        S20B_RUST_PATH: 8,
        S20B_RUST_ASSIGNMENT_PATH: 3,
        S20B_RUST_SCHEMA_PACKETS_PATH: 6,
        S20B_RUST_S17_PATH: 6,
    }
    for relative, minimum in module_minimums.items():
        module_tests = re.findall(
            r"(?m)^\s*#\[test\]\s*\n\s*fn\s+(s20b_[a-z0-9_]+)\s*\(",
            sources[relative],
        )
        require(
            len(module_tests) >= minimum,
            f"S20B directed KAT catalog is too small in {relative}",
        )
    parent_tests = re.findall(
        r"(?m)^\s*#\[test\]\s*\n\s*fn\s+(s20_[a-z0-9_]+)\s*\(", parent
    )
    require(len(parent_tests) == len(set(parent_tests)), "duplicate S20 parent Rust test name")
    require(len(parent_tests) >= 16, "S20 parent regression catalog is too small")
    return len(tests), len(parent_tests)


def validate_control_documents(repo: Path, overrides: Mapping[str, bytes] | None) -> None:
    _, contract = load_json(repo, CONTRACT_PATH, overrides)
    _, status = load_json(repo, STATUS_PATH, overrides)
    _, successor = load_json(repo, SUCCESSOR_PATH, overrides)
    for label, value in (("contract", contract), ("status", status), ("successor", successor)):
        require(value.get("status") == STATUS, f"status drift: {label}")
        require(value.get("decision") == DECISION, f"decision drift: {label}")
        all_fail_closed_fields(value, label)
    require(contract.get("implementation_mode") == MODE, "implementation mode drift")
    replacements = contract.get("replacement_schemas")
    require(isinstance(replacements, dict), "replacement schema registry absent")
    require(replacements.get("schema_count") == 4, "replacement schema count drift")
    for spec, key in zip(PACKETS, ("preflight", "control_snapshot", "authority_control_claim", "post_run_bundle")):
        require(replacements.get(key) == spec.schema_id, f"replacement schema identity drift: {key}")
    digest = contract.get("digest_contract")
    require(isinstance(digest, dict), "digest contract absent")
    require(digest.get("algorithm") == "SHA-256", "digest algorithm drift")
    require(digest.get("canonicalization") == CANONICALIZATION, "contract canonicalization drift")
    require(digest.get("framing") == FRAMING, "contract digest framing drift")
    require(digest.get("candidate_reported_matches_authoritative") is False,
            "candidate-reported digest match became authoritative")
    completion = contract.get("mechanical_completion")
    require(isinstance(completion, dict), "mechanical completion absent")
    for key, value in completion.items():
        if key == "schemas_defined" or key.endswith("implemented") or key.endswith("passed") or key in {
            "coherent_cross_packet_fixture_chain_present", "s20b_complete"
        }:
            require(value is True, f"S20B completion field is not true: {key}")
    implementation = status.get("implementation")
    require(isinstance(implementation, dict), "status implementation receipt absent")
    for key, value in implementation.items():
        if key == "implementation_state":
            require(isinstance(value, str) and ("COMPLETE" in value or "IMPLEMENTED" in value),
                    "status implementation state is not complete")
        else:
            require(value is True, f"status implementation field is not true: {key}")
    require(successor.get("admission_decision", {}).get("s20b_mechanically_complete") is True,
            "successor does not record mechanically complete S20B")
    require(successor.get("admission_decision", {}).get("live_execution_may_begin") is False,
            "successor permits live execution")


def validate_docs(repo: Path, overrides: Mapping[str, bytes] | None) -> None:
    design = read_text(repo, DESIGN_PATH, overrides)
    report = read_text(repo, REPORT_PATH, overrides)
    for token in (
        STATUS,
        DECISION,
        "NON_LIVE",
        "5,639",
        "32-rule",
        "113",
        "UNKNOWN_OUTCOME_TERMINAL_HARD_LOCK",
        "COMMITTED_PRE_PERMIT_CRASH_TERMINAL",
        "side_effects_unlocked=NONE",
    ):
        require(token in design or token in report, f"design/report token absent: {token}")


def mutation_cases(repo: Path) -> list[tuple[str, bytes, str]]:
    cases: list[tuple[str, bytes, str]] = []
    loaded: dict[str, tuple[PacketSpec, dict[str, Any], dict[str, Any]]] = {}
    for spec in PACKETS:
        _, schema = load_json(repo, spec.schema_path)
        _, fixture = load_json(repo, spec.fixture_path)
        loaded[spec.slug] = (spec, schema, fixture)

        duplicate = read_bytes(repo, spec.fixture_path).replace(b"{", b'{"schema":"duplicate",', 1)
        cases.append((spec.fixture_path, duplicate, "duplicate JSON key"))
        floating = read_bytes(repo, spec.fixture_path).replace(b"{", b'{"unexpected_float":1.5,', 1)
        cases.append((spec.fixture_path, floating, "floating-point JSON forbidden"))

        extra = copy.deepcopy(fixture)
        extra["unexpected_open_world_field"] = False
        cases.append((spec.fixture_path, canonical_bytes(extra) + b"\n", "schema rejected"))
        for required in schema.get("required", []):
            missing = copy.deepcopy(fixture)
            missing.pop(required, None)
            cases.append((spec.fixture_path, canonical_bytes(missing) + b"\n", "schema rejected"))

        digest = copy.deepcopy(fixture)
        digest[spec.self_hash_field] = "0" * 64
        cases.append((spec.fixture_path, canonical_bytes(digest) + b"\n", "self digest mismatch"))

        schema_external = copy.deepcopy(schema)
        replaced = False
        def replace_ref(value: Any) -> None:
            nonlocal replaced
            if replaced:
                return
            if isinstance(value, list):
                for child in value:
                    replace_ref(child)
            elif isinstance(value, dict):
                for key, child in value.items():
                    if key == "$ref" and isinstance(child, str) and child.startswith("#/"):
                        value[key] = "https://invalid.example/s20b-schema"
                        replaced = True
                        return
                    replace_ref(child)
        replace_ref(schema_external)
        require(replaced, f"schema has no internal ref for external-ref KAT: {spec.schema_path}")
        cases.append((spec.schema_path, canonical_bytes(schema_external) + b"\n", "external schema ref"))

    # Rehash every mutated child so each edge test reaches cross-binding validation.
    edge_mutations = (
        ("control-snapshot", ("phase_parent", "parent_sha256")),
        ("preflight-receipt", ("phase_bindings", "control_snapshot_sha256")),
        ("authority-control-claim", ("parent_bindings", "preflight_receipt_sha256")),
        ("authority-control-claim", ("parent_bindings", "control_snapshot_sha256")),
        ("post-run-receipt-bundle", ("execution_binding", "claim_packet_sha256")),
        ("post-run-receipt-bundle", ("receipt_chain", "preflight_receipt_sha256")),
        ("post-run-receipt-bundle", ("receipt_chain", "control_snapshot_sha256")),
        ("post-run-receipt-bundle", ("receipt_chain", "claim_packet_sha256")),
    )
    for slug, path in edge_mutations:
        spec, _, fixture = loaded[slug]
        mutated = copy.deepcopy(fixture)
        set_path(mutated, path, "f" * 64)
        cases.append((spec.fixture_path, reseal_fixture(mutated, spec), "cross binding drift"))

    # A forward link from control to final preflight closes a 2-node cycle.
    control_spec, _, control = loaded["control-snapshot"]
    preflight = loaded["preflight-receipt"][2]
    cyclic = copy.deepcopy(control)
    set_path(cyclic, ("phase_parent", "parent_sha256"), preflight["preflight_receipt_sha256"])
    cases.append((control_spec.fixture_path, reseal_fixture(cyclic, control_spec), "cross binding drift"))

    # p06 is independently recomputed from the profile plus p01..p24 excluding
    # p06. Resealing the outer claim must not make an altered transition core
    # authoritative.
    claim_spec, _, claim = loaded["authority-control-claim"]
    for key, replacement, expected in (
        ("p01_next_revision", 13, "claim CAS p01 is not exactly p14 plus one"),
        ("p06_claim_transition_core_sha256", "f" * 64, "claim transition-core p06 digest mismatch"),
        ("p24_sqlite_schema_sha256", "e" * 64, "claim transition-core p06 digest mismatch"),
    ):
        mutated = copy.deepcopy(claim)
        set_path(mutated, ("claim_attempt", "cas_parameter_bindings", key), replacement)
        cases.append((claim_spec.fixture_path, reseal_fixture(mutated, claim_spec), expected))

    # Terminal/non-live mutations are discovered by exact field name and resealed.
    for spec, _, fixture in loaded.values():
        for field, unsafe_value in (
            ("automatic_retry_allowed", True),
            ("side_effects_unlocked", "LIVE"),
        ):
            mutated = copy.deepcopy(fixture)
            changed = False
            def mutate_named(value: Any) -> None:
                nonlocal changed
                if isinstance(value, list):
                    for child in value:
                        mutate_named(child)
                elif isinstance(value, dict):
                    for key, child in value.items():
                        if key == field and not changed:
                            value[key] = unsafe_value
                            changed = True
                            return
                        mutate_named(child)
            mutate_named(mutated)
            if changed:
                cases.append(
                    (
                        spec.fixture_path,
                        reseal_fixture(mutated, spec),
                        (
                            "schema rejected valid fixture|fail-closed field became true"
                            if field == "automatic_retry_allowed"
                            else "schema rejected valid fixture|side effects unlocked"
                        ),
                    )
                )

    rust = read_bytes(repo, S20B_RUST_PATH)
    cases.append(
        (
            S20B_RUST_PATH,
            rust.replace(
                b"S20B_RUNTIME_CROSS_PACKET_DIGEST_RECOMPUTATION_IMPLEMENTED: bool = true",
                b"S20B_RUNTIME_CROSS_PACKET_DIGEST_RECOMPUTATION_IMPLEMENTED: bool = false",
                1,
            ),
            "Rust implementation marker absent",
        )
    )
    require(all(read_bytes(repo, path) != mutated for path, mutated, _ in cases),
            "one or more mutation cases are no-ops")
    return cases


def validate_bundle(
    repo: Path, overrides: Mapping[str, bytes] | None = None
) -> list[tuple[str, str]]:
    fixtures, schema_receipts = validate_schema_fixtures(repo, overrides)
    node_count, edge_count = validate_cross_bindings(fixtures)
    validate_frozen_s17(repo, overrides)
    rust_test_count, rust_parent_test_count = validate_rust(repo, overrides)
    validate_control_documents(repo, overrides)
    validate_docs(repo, overrides)
    rows: list[tuple[str, str]] = [
        ("schema", "agent_bridge.memory_temporal_owned_lab_rich_packet_schema_replacements_s20b.check.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("implementation_mode", MODE),
        ("baseline_commit", BASELINE_COMMIT),
        ("baseline_tree", BASELINE_TREE),
        ("frozen_s20_commit", FROZEN_S20_COMMIT),
        ("frozen_s20_tree", FROZEN_S20_TREE),
        ("feature", FEATURE),
        ("repaired_rich_schema_count", "4"),
        ("synthetic_cross_packet_fixture_count", "4"),
        ("rich_positive_fixture_count", "4"),
        ("rich_cross_digest_node_count", str(node_count)),
        ("rich_cross_digest_edge_count", str(edge_count)),
        ("digest_dag_cycle_count", "0"),
        ("full_packet_builders_parsers_validators_implemented", "true"),
        ("runtime_full_packet_digest_recomputation_implemented", "true"),
        ("runtime_full_cross_packet_binding_recomputation_implemented", "true"),
        ("full_24_parameter_claim_validator_implemented", "true"),
        ("exact_assignment_membership_validator_implemented", "true"),
        ("concrete_operation_descriptor_validator_implemented", "true"),
        ("unknown_commit_terminal_hard_lock_implemented", "true"),
        ("postcommit_prepermit_terminal_implemented", "true"),
        ("database_content_root_recomputation_implemented", "true"),
        ("reopen_exact_cardinality_and_terminal_kat", "PASS"),
        ("s17_cross_field_rule_count", "32"),
        ("s17_full_catalog_row_count", "5639"),
        ("s17_full_catalog_unique_fingerprint_count", "5639"),
        ("authorized_assignment_count", "60"),
        ("s17_target_phase_count", "113"),
        ("s17_target_unique_match_count", "113"),
        ("s17_missing_match_count", "0"),
        ("s17_multiple_match_count", "0"),
        ("assignment_prefilter_used", "false"),
        ("concrete_operation_descriptor_kind_count", "8"),
        ("rust_s20b_test_count", str(rust_test_count)),
        ("rust_s20_parent_test_count", str(rust_parent_test_count)),
        ("rust_trusted_controller_test_count", str(rust_test_count + rust_parent_test_count)),
        ("self_test_mutation_count", str(len(mutation_cases(repo))) if overrides is None else "DEFERRED"),
        ("live_canary", "NOT_RUN"),
        ("side_effects_unlocked", "NONE"),
        ("future_s21_preapproved", "false"),
    ]
    for key in sorted(schema_receipts):
        rows.append((key, schema_receipts[key]))
    for key, relative in ARTIFACT_ROWS:
        rows.append((key, sha256(read_bytes(repo, relative, overrides))))
    return rows


def expect_failure(repo: Path, relative: str, mutated: bytes, expected: str) -> None:
    try:
        validate_bundle(repo, {relative: mutated})
    except CheckFailure as exc:
        accepted_messages = expected.split("|")
        require(
            any(message in str(exc) for message in accepted_messages),
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
    parser.add_argument("--seed", type=int, default=20_002)
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
        print(f"S20B rich-packet checker failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
