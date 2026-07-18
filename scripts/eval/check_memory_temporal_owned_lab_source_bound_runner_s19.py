#!/usr/bin/env python3
"""Independent S19 non-live runner, manifest, CAS, and release-packet checker."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import types
from pathlib import Path
from typing import Any, Callable

sys.dont_write_bytecode = True


BASELINE_COMMIT = "85f686dde161f25166b8f38c38b9a05bd7957bfd"
FEATURE = "temporal-evidence-s19-owned-lab-source-bound-runner-synthetic"
BASELINE_CARGO_SHA256 = "6b993a079c541d95485c908863da5aa427e4cebffd1cd3fd274105a477d5a2c6"
BASELINE_S18_RUST_SHA256 = "17af73a6c7793f53372ec15713afa7e329ce8cb001e4b9570bdbb1f0e982c2f6"
S18_CHECKER_SHA256 = "05aff9ae7c22d653486de9d47e99f5ab6d7837919d17fb1735bd436f20514aea"
S18_GATE_SHA256 = "af37e50736e0869b081a11ffeb204cc2aa42defdf0a826e067ae480a573fe61b"
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
SQLITE_PROFILE_SHA256 = "6a51b825e83935fa638cc051a8086ff07fc2821bfa90b14bc2363ffa42ac9ac8"
SQLITE_SCHEMA_CATALOG_SHA256 = "32559198f29827fc9f7a37d100520d7a5685ff99b3d9d40ac91baf9eba965110"

CARGO_PATH = "crates/store/Cargo.toml"
S18_RUST_PATH = (
    "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/"
    "recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/"
    "durability_fault_model/owned_lab_owner_resource_authorization.rs"
)
RUST_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/"
    "recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/"
    "durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner.rs"
)
DESIGN_PATH = "docs/design/MEMORY_TEMPORAL_OWNED_LAB_SOURCE_BOUND_RUNNER_S19_2026_07_17.md"
CONTRACT_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-source-bound-runner-contract-s19-v0.json"
STATUS_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-source-bound-runner-status-s19-v0.json"
MANIFEST_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-subject-manifest-schema-s19-v0.json"
PREFLIGHT_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-preflight-receipt-schema-s19-v0.json"
CONTROL_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-control-snapshot-schema-s19-v0.json"
CLAIM_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-authority-control-claim-schema-s19-v0.json"
POST_RUN_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-post-run-receipt-bundle-schema-s19-v0.json"
SUCCESSOR_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s19-v0.json"
SYNTHETIC_PATH = "docs/design/fixtures/biocortex-ab-track-b-owned-lab-subject-manifest-synthetic-s19-v0.json"
REPORT_PATH = "docs/reports/goal-c-u/2026-07-17-biocortex-ab-track-b-owned-lab-source-bound-runner-s19.md"
CHECKER_PATH = "scripts/eval/check_memory_temporal_owned_lab_source_bound_runner_s19.py"
EXPECTED_PATH = "scripts/eval/fixtures/memory_temporal_owned_lab_source_bound_runner_s19.expected.v0.tsv"
GATE_PATH = "scripts/check-memory-temporal-owned-lab-source-bound-runner-s19.sh"

S18_CHECKER_PATH = "scripts/eval/check_memory_temporal_owned_lab_authorization_envelope_verifier_s18.py"
S18_GATE_PATH = "scripts/check-memory-temporal-owned-lab-authorization-envelope-verifier-s18.sh"
SCHEMA_IDS = {
    MANIFEST_SCHEMA_PATH: "agent_bridge.memory_temporal_owned_lab_subject_manifest_s19.v0",
    PREFLIGHT_SCHEMA_PATH: "agent_bridge.memory_temporal_owned_lab_preflight_receipt_s19.v0",
    CONTROL_SCHEMA_PATH: "agent_bridge.memory_temporal_owned_lab_control_snapshot_s19.v0",
    CLAIM_SCHEMA_PATH: "agent_bridge.memory_temporal_owned_lab_authority_control_claim_s19.v0",
    POST_RUN_SCHEMA_PATH: "agent_bridge.memory_temporal_owned_lab_post_run_receipt_bundle_s19.v0",
}
CONTRACT_SCHEMA_BINDINGS = {
    "subject_manifest_schema_sha256": MANIFEST_SCHEMA_PATH,
    "preflight_receipt_schema_sha256": PREFLIGHT_SCHEMA_PATH,
    "control_snapshot_schema_sha256": CONTROL_SCHEMA_PATH,
    "authority_control_claim_schema_sha256": CLAIM_SCHEMA_PATH,
    "post_run_receipt_bundle_schema_sha256": POST_RUN_SCHEMA_PATH,
}
MANIFEST_KEYS = (
    "artifact_bindings",
    "build_identity",
    "canonicalization",
    "claim_protocol",
    "control_protocol",
    "experiment_scope",
    "lab_environment",
    "manifest_state",
    "nonclaims",
    "packet_kind",
    "receipt_bindings",
    "safety_policy",
    "schema",
    "test_only",
    "validators",
)
CONTRACT_KEYS = (
    "current_authority_and_execution",
    "decision",
    "execution_permit",
    "external_control",
    "implementation",
    "implementation_mode",
    "independent_registration",
    "post_run_evidence",
    "predecessor",
    "preflight",
    "schema",
    "schema_artifacts",
    "single_use_claim",
    "status",
    "subject_manifest",
    "successor_boundary",
)
STATUS_KEYS = (
    "actual_execution",
    "current_authority",
    "decision",
    "implementation_mode",
    "implemented",
    "next_stage",
    "nonclaims",
    "not_implemented_or_not_present",
    "schema",
    "status",
)
SUCCESSOR_KEYS = (
    "completed_boundary",
    "current_execution",
    "decision",
    "next_stage",
    "nonclaims",
    "s20_fail_closed_conditions",
    "schema",
    "status",
)
CAS_WHERE_BINDINGS = (
    "authorization_id_sha256",
    "signed_payload_sha256",
    "subject_manifest_sha256",
    "resource_scope_sha256",
    "signed_revocation_epoch",
    "claim_namespace_sha256",
    "claim_key_sha256",
    "revision",
    "run_id_sha256",
    "controller_binary_sha256",
    "runner_binary_sha256",
    "capability_nonce_sha256",
    "preflight_receipt_sha256",
    "control_snapshot_sha256",
    "stop_revision",
    "revocation_revision",
)
FROZEN_S18_ARTIFACTS = {
    "docs/design/MEMORY_TEMPORAL_OWNED_LAB_AUTHORIZATION_ENVELOPE_VERIFIER_S18_2026_07_17.md":
        "df4787947a6d284153cf98842bbc01b963e9876739edc3da386d6a924cdbe8af",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-authorization-validator-contract-s18-v0.json":
        "034918f67efea4487dfc28bff7830251dff71e6218317157efae106d07aa8f56",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-authorization-validator-status-s18-v0.json":
        "f9ca95332e061fc619f2a9f50c2ef9d7eee6607617da7c1051c5fdd5416e57a0",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-authorization-envelope-schema-s18-v0.json":
        "cb31843865d12c183b37c65d9d5ffae39a7f42bb8a7f4be2fd4f90c099548e6b",
    "docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-trust-anchor-schema-s18-v0.json":
        "648d7f09dc430675707583e5be85adeb95209f8e26bbae7aad4fad08fbf7350b",
    "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s18-v0.json":
        "3a2c446f3dfa4bad343c9ed582712a7c72135860d0a9eda2d4e64a1886e2f675",
    "docs/reports/goal-c-u/2026-07-17-biocortex-ab-track-b-owned-lab-authorization-envelope-verifier-s18.md":
        "f95296730770f0f874f6b956282d4f173aae6cb131c0a596a27970ce748fbf64",
    S18_CHECKER_PATH: S18_CHECKER_SHA256,
    S18_GATE_PATH: S18_GATE_SHA256,
    "scripts/eval/fixtures/memory_temporal_owned_lab_authorization_envelope_verifier_s18.expected.v0.tsv":
        "ce5919f5ad7b60bd0836e94158d30d4c59bcb28628931049f5046a0f38b2300e",
    (
        "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/"
        "recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/"
        "durability_fault_model.rs"
    ): "aa94d1e8223fbc55e0cbbfb423a979f351704203a847bb252d513a3bef345a91",
}

S19_ARTIFACT_ROWS = (
    ("cargo_manifest_sha256", CARGO_PATH),
    ("s18_parent_verifier_sha256", S18_RUST_PATH),
    ("rust_s19_source_sha256", RUST_SOURCE_PATH),
    ("design_sha256", DESIGN_PATH),
    ("contract_sha256", CONTRACT_PATH),
    ("status_fixture_sha256", STATUS_PATH),
    ("manifest_schema_sha256", MANIFEST_SCHEMA_PATH),
    ("preflight_schema_sha256", PREFLIGHT_SCHEMA_PATH),
    ("control_snapshot_schema_sha256", CONTROL_SCHEMA_PATH),
    ("authority_claim_schema_sha256", CLAIM_SCHEMA_PATH),
    ("post_run_schema_sha256", POST_RUN_SCHEMA_PATH),
    ("successor_gate_sha256", SUCCESSOR_PATH),
    ("synthetic_manifest_sha256", SYNTHETIC_PATH),
    ("checker_sha256", CHECKER_PATH),
    ("source_gate_sha256", GATE_PATH),
)


class CheckFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def canonical_path(repo: Path, relative: str) -> Path:
    path = repo / relative
    require(
        path.is_file() and not path.is_symlink() and path.resolve() == path,
        f"artifact is not one canonical regular file: {relative}",
    )
    return path


def read_bytes(repo: Path, relative: str) -> bytes:
    path = canonical_path(repo, relative)
    size = path.stat().st_size
    require(0 < size <= MAX_ARTIFACT_BYTES, f"artifact size outside bounded profile: {relative}")
    raw = path.read_bytes()
    require(len(raw) == size, f"artifact changed while being read: {relative}")
    return raw


def read_text(repo: Path, relative: str) -> str:
    raw = read_bytes(repo, relative)
    require(not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {relative}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckFailure(f"artifact is not UTF-8: {relative}") from exc


def artifact_sha256(repo: Path, relative: str) -> str:
    return hashlib.sha256(read_bytes(repo, relative)).hexdigest()


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


def parse_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, CheckFailure) as exc:
        raise CheckFailure(f"invalid {label}: {exc}") from exc
    require(isinstance(value, dict), f"{label} root must be an object")
    return value


def load_json(repo: Path, relative: str) -> dict[str, Any]:
    return parse_json_bytes(read_bytes(repo, relative), relative)


def canonical_structure_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_structure_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_structure_bytes(value)).hexdigest()


def load_frozen_module(repo: Path, relative: str, digest: str, name: str) -> Any:
    raw = read_bytes(repo, relative)
    require(hashlib.sha256(raw).hexdigest() == digest, f"frozen module drift: {relative}")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckFailure(f"frozen module is not UTF-8: {relative}") from exc
    module = types.ModuleType(name)
    module.__file__ = str(repo / relative)
    module.__package__ = ""
    code = compile(source, module.__file__, "exec", dont_inherit=True, optimize=0)
    exec(code, module.__dict__)
    return module


def validate_predecessor(repo: Path) -> tuple[Any, Any]:
    for path, digest in FROZEN_S18_ARTIFACTS.items():
        require(artifact_sha256(repo, path) == digest, f"frozen S18 artifact drift: {path}")
    s18 = load_frozen_module(
        repo,
        S18_CHECKER_PATH,
        S18_CHECKER_SHA256,
        "agent_bridge_frozen_s18_checker_for_s19",
    )
    s17 = s18.load_frozen_module(
        repo,
        s18.S17_CHECKER_PATH,
        s18.FROZEN_S17_ARTIFACTS[s18.S17_CHECKER_PATH],
        "agent_bridge_frozen_s17_checker_for_s19",
    )
    s18.validate_s17(repo, s17)
    return s18, s17


def validate_closed_schema_graph(schema: dict[str, Any], label: str) -> None:
    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            declared_type = node.get("type")
            if declared_type == "object" or (
                isinstance(declared_type, list) and "object" in declared_type
            ):
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


def validate_schema_evaluator_coverage(schema: dict[str, Any], label: str) -> None:
    """Reject valid-but-unsupported keywords before using the frozen evaluator."""
    supported = {
        "$defs",
        "$id",
        "$ref",
        "$schema",
        "additionalProperties",
        "allOf",
        "const",
        "description",
        "else",
        "enum",
        "if",
        "items",
        "maxItems",
        "maxLength",
        "maximum",
        "minItems",
        "minLength",
        "minimum",
        "oneOf",
        "pattern",
        "prefixItems",
        "properties",
        "required",
        "then",
        "title",
        "type",
    }

    def walk(node: Any, path: str) -> None:
        require(isinstance(node, dict), f"{label} schema node is not an object: {path}")
        unknown = set(node).difference(supported)
        require(not unknown, f"{label} unsupported evaluator keyword at {path}: {sorted(unknown)}")
        for container in ("$defs", "properties"):
            children = node.get(container, {})
            if isinstance(children, dict):
                for name, child in children.items():
                    walk(child, f"{path}/{container}/{name}")
        for container in ("allOf", "oneOf", "prefixItems"):
            children = node.get(container, [])
            if isinstance(children, list):
                for index, child in enumerate(children):
                    walk(child, f"{path}/{container}/{index}")
        for key in ("if", "then", "else", "items", "additionalProperties"):
            child = node.get(key)
            if isinstance(child, dict):
                walk(child, f"{path}/{key}")

    walk(schema, "#")


def normalize_union_types_for_frozen_evaluator(value: Any) -> Any:
    """Translate Draft 2020-12 type arrays into the frozen evaluator's oneOf subset."""
    if isinstance(value, list):
        return [normalize_union_types_for_frozen_evaluator(item) for item in value]
    if not isinstance(value, dict):
        return copy.deepcopy(value)
    output = {
        key: normalize_union_types_for_frozen_evaluator(item)
        for key, item in value.items()
        if key != "type" or not isinstance(item, list)
    }
    type_value = value.get("type")
    if isinstance(type_value, list):
        require(
            type_value
            and len(type_value) == len(set(type_value))
            and all(item in {"object", "array", "string", "integer", "boolean", "null"} for item in type_value),
            "unsupported or duplicate union type",
        )
        require("oneOf" not in value, "type-array and oneOf composition is unsupported")
        output["oneOf"] = [{"type": item} for item in type_value]
    return output


def validate_schemas(
    s17: Any,
    schemas: dict[str, dict[str, Any]],
    synthetic: dict[str, Any],
) -> None:
    for path, schema in schemas.items():
        require(schema.get("$id") == SCHEMA_IDS[path], f"schema ID drift: {path}")
        require(
            schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
            f"schema draft drift: {path}",
        )
        validate_schema_evaluator_coverage(schema, path)
        validate_closed_schema_graph(schema, path)
        evaluator_schema = normalize_union_types_for_frozen_evaluator(schema)
        s17.validate_schema_keywords(evaluator_schema, path)
        s17.validate_local_refs(schema, path)
        if path != MANIFEST_SCHEMA_PATH:
            require(
                b"S20_TARGET_SCHEMA_ONLY_NOT_EMITTED_OR_VALIDATED_BY_S19_RUST"
                in canonical_structure_bytes(schema),
                f"rich packet schema overclaims S19 runtime implementation: {path}",
            )
    manifest_schema = schemas[MANIFEST_SCHEMA_PATH]
    errors = s17.schema_instance_errors(manifest_schema, synthetic, manifest_schema)
    require(not errors, f"synthetic manifest rejected: {errors[:3]}")
    require(synthetic.get("test_only") is True, "synthetic manifest is not test-only")
    mutated = copy.deepcopy(synthetic)
    mutated["unexpected"] = False
    require(
        bool(s17.schema_instance_errors(manifest_schema, mutated, manifest_schema)),
        "manifest schema accepted an unknown field",
    )


def independently_rebuild_manifest(
    independent_source: dict[str, Any],
    manifest_schema: dict[str, Any],
) -> dict[str, Any]:
    """Rebuild only from the separately loaded manifest source, never a candidate envelope."""
    required = manifest_schema.get("required")
    properties = manifest_schema.get("properties")
    require(isinstance(required, list) and isinstance(properties, dict), "manifest schema shape")
    require(set(independent_source) == set(required) == set(properties), "manifest exact key drift")
    require(
        not {"candidate", "candidate_envelope", "authentication", "payload"}.intersection(
            independent_source
        ),
        "independent manifest source contains candidate-envelope material",
    )
    require(tuple(sorted(required)) == tuple(sorted(MANIFEST_KEYS)), "manifest key catalog drift")
    # Deliberately spell every field out.  No candidate envelope or candidate
    # payload is accepted by this function or used to derive expected values.
    return {
        "artifact_bindings": copy.deepcopy(independent_source["artifact_bindings"]),
        "build_identity": copy.deepcopy(independent_source["build_identity"]),
        "canonicalization": independent_source["canonicalization"],
        "claim_protocol": copy.deepcopy(independent_source["claim_protocol"]),
        "control_protocol": copy.deepcopy(independent_source["control_protocol"]),
        "experiment_scope": copy.deepcopy(independent_source["experiment_scope"]),
        "lab_environment": copy.deepcopy(independent_source["lab_environment"]),
        "manifest_state": independent_source["manifest_state"],
        "nonclaims": copy.deepcopy(independent_source["nonclaims"]),
        "packet_kind": independent_source["packet_kind"],
        "receipt_bindings": copy.deepcopy(independent_source["receipt_bindings"]),
        "safety_policy": copy.deepcopy(independent_source["safety_policy"]),
        "schema": independent_source["schema"],
        "test_only": independent_source["test_only"],
        "validators": copy.deepcopy(independent_source["validators"]),
    }


def validate_manifest_semantics(manifest: dict[str, Any]) -> None:
    require(set(manifest) == set(MANIFEST_KEYS), "manifest top-level key drift")
    require(manifest["schema"] == SCHEMA_IDS[MANIFEST_SCHEMA_PATH], "manifest schema")
    require(
        manifest["packet_kind"] == "S19_OWNER_REVIEW_SUBJECT_MANIFEST",
        "manifest packet kind",
    )
    require(
        manifest["canonicalization"]
        == "AB_RESTRICTED_CANONICAL_JSON_S19_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT",
        "manifest canonical profile",
    )
    require(
        manifest["manifest_state"] == "SYNTHETIC_KAT_NON_LIVE_SUBJECT"
        and manifest["test_only"] is True,
        "manifest test-only state",
    )

    build = manifest["build_identity"]
    require(build["s18_integration_commit"] == BASELINE_COMMIT, "S18 integration binding")
    synthetic_oids = {
        "runner_source_commit": "11" * 20,
        "s19_integration_commit": "22" * 20,
        "s19_integration_tree": "23" * 20,
        "s19_source_commit": "24" * 20,
        "s19_source_tree": "25" * 20,
    }
    for key, expected in synthetic_oids.items():
        require(build[key] == expected, f"synthetic build identity drift: {key}")

    artifacts = manifest["artifact_bindings"]
    require(artifacts["catalog_row_count"] == 5639, "catalog count drift")
    require(
        artifacts["target_phase_count"] == 113
        and artifacts["target_phase_unique_match_count"] == 113,
        "target phase count drift",
    )
    require(
        artifacts["sqlite_application_id"] == 1094865689
        and artifacts["sqlite_user_version"] == 19
        and artifacts["sqlite_profile_sha256"] == SQLITE_PROFILE_SHA256
        and artifacts["sqlite_schema_sha256"] == SQLITE_SCHEMA_CATALOG_SHA256,
        "SQLite artifact binding drift",
    )
    frozen_bindings = {
        "s17_plan_sha256": "ca9769ff2b79e474999df6bb5096a3e062b5acf78fa23788f76ae44295531650",
        "s17_observation_schema_sha256": "26a8cca9f9ca74ceb4b949a2e75d9282a6227623f5bd66cc3333fbff7441588d",
        "positive_owner_schema_sha256": "cb31843865d12c183b37c65d9d5ffae39a7f42bb8a7f4be2fd4f90c099548e6b",
        "s18_contract_sha256": "034918f67efea4487dfc28bff7830251dff71e6218317157efae106d07aa8f56",
        "s18_owner_trust_anchor_schema_sha256": "648d7f09dc430675707583e5be85adeb95209f8e26bbae7aad4fad08fbf7350b",
        "s18_owner_verifier_source_sha256": BASELINE_S18_RUST_SHA256,
        "s18_successor_gate_sha256": "3a2c446f3dfa4bad343c9ed582712a7c72135860d0a9eda2d4e64a1886e2f675",
    }
    for key, expected in frozen_bindings.items():
        require(artifacts[key] == expected, f"predecessor manifest binding drift: {key}")

    scope = manifest["experiment_scope"]
    require(scope["authorized_family_ids"] == ["OL00", "OL04", "OL05"], "family order")
    require(
        scope["authorized_family_scenario_counts"] == {"OL00": 1, "OL04": 6, "OL05": 53},
        "family counts",
    )
    require(
        (
            scope["canary_batch_count"],
            scope["repetition_count"],
            scope["assigned_attempt_count"],
            scope["planned_pidfd_sigkill_attempt_count"],
            scope["planned_distinct_fresh_exec_read_count"],
            scope["planned_total_s16_mapping_phase_record_count"],
        )
        == (1, 1, 60, 59, 59, 113),
        "exact canary counts",
    )
    require(
        scope["claim_level"] == "L1_PROCESS_CRASH_FRESH_PROCESS_RESTART_ONLY"
        and scope["family_id_namespace"] == "OL00_OL04_OL05_FIRST_BATCH",
        "experiment claim namespace drift",
    )
    require(
        scope["retry_or_implicit_rerun_allowed"] is False
        and scope["rerun_requires_new_assignment_and_owner_decision"] is True,
        "retry/rerun policy",
    )

    claim = manifest["claim_protocol"]
    require(tuple(claim["cas_where_required_bindings"]) == CAS_WHERE_BINDINGS, "CAS binding set")
    require(
        claim["cas_sql_where_profile"] == "EXACT_ALL_BINDINGS_AND_CONTROLS_SINGLE_UPDATE"
        and claim["claim_key_derivation_profile"]
        == "SHA256_NAMESPACE_AUTHORIZATION_MANIFEST_RUN",
        "CAS or claim-key profile drift",
    )
    for key in (
        "authorization_registration_required",
        "claim_receipt_same_transaction",
        "consumed_tombstone_absorbing",
        "durable_commit_required_before_permit",
        "permit_binds_capability_nonce",
        "permit_binds_controller_runner_and_run",
        "single_use_claim_required",
    ):
        require(claim[key] is True, f"claim requirement weakened: {key}")
    for key in (
        "affine_permit_cloneable",
        "affine_permit_serializable",
        "cas_failure_allows_automatic_retry",
        "cas_failure_grants_execution",
        "cas_failure_mutates_unclaimed",
        "consumed_tombstone_deletable",
        "missing_row_may_be_created_by_claim",
        "successful_claim_then_crash_allows_retry",
        "upsert_or_replace_allowed",
    ):
        require(claim[key] is False, f"claim prohibition weakened: {key}")
    require(
        claim["transition"] == "UNCLAIMED_TO_CONSUMED_FOR_EXACT_RUN"
        and claim["unclaimed_state"] == "AUTHORIZED_UNCLAIMED"
        and claim["claimed_state"] == "CONSUMED_FOR_EXACT_RUN",
        "claim state machine",
    )
    require(
        (
            claim["failed_cas_expected_affected_rows"],
            claim["successful_cas_expected_affected_rows"],
            claim["maximum_successful_claims"],
        )
        == (0, 1, 1),
        "CAS cardinality",
    )
    require(claim["expected_unclaimed_revision"] == 41, "unclaimed revision drift")

    control = manifest["control_protocol"]
    for key in (
        "cas_and_control_reads_same_sqlite_transaction",
        "external_state_is_outside_owner_envelope",
        "missing_or_unknown_control_state_fails_closed",
        "post_claim_pre_start_recheck_required",
        "revocation_epoch_monotonic",
        "revocation_ledger_revision_monotonic",
        "revocation_policy_identity_required",
        "runtime_action_boundary_recheck_required",
        "stop_ledger_revision_monotonic",
        "stop_policy_identity_required",
        "stop_triggered_is_absorbing",
    ):
        require(control[key] is True, f"control requirement weakened: {key}")
    require(control["trusted_wall_clock_is_freshness"] is False, "wall-clock freshness")
    require(
        control["revocation_epoch_comparison"]
        == "ANCHOR_FLOOR_LE_EXTERNAL_EQ_SIGNED",
        "revocation equality semantics",
    )
    require(
        control["absorbing_stop_clear_state"] == "CLEAR"
        and control["absorbing_stop_triggered_state"] == "TRIGGERED"
        and control["current_epoch_source_profile"]
        == "EXTERNAL_AUTHORITY_CONTROL_LEDGER_EXACT_CURRENT_EPOCH"
        and control["stop_transition"] == "CLEAR_TO_TRIGGERED_ABSORBING"
        and control["same_transaction_required_table_ids"]
        == ["authority_control", "claim_ledger", "claim_receipts"],
        "STOP/control transaction semantics",
    )

    environment = manifest["lab_environment"]
    require(
        (
            environment["sqlite_journal_mode"],
            environment["sqlite_synchronous"],
            environment["sqlite_setup_mode"],
            environment["sqlite_reopen_mode"],
        )
        == (
            "DELETE",
            "EXTRA",
            "CREATE_NEW_ONLY_DURING_SETUP",
            "READ_WRITE_EXISTING_WITHOUT_CREATE",
        ),
        "SQLite profile drift",
    )
    require(
        environment["build_jobs"] == 1
        and environment["nested_cargo_allowed"] is False
        and environment["run_root_must_not_preexist"] is True,
        "resource/setup policy",
    )
    require(
        environment["run_root_create_mode"] == "CREATE_NEW_MODE_0700"
        and environment["run_root_derivation_profile"]
        == "S19_SOURCE_COMMIT_CONTROLLER_PID_MONOTONIC_COUNTER_RANDOM_NONCE_SHA256",
        "run-root derivation profile drift",
    )

    safety = manifest["safety_policy"]
    for key in (
        "agent_bridge_application_side_effect_allowed",
        "block_device_write_allowed",
        "credential_access_allowed",
        "drop_caches_allowed",
        "mount_or_unmount_allowed",
        "named_ipc_or_network_control_allowed",
        "network_allowed",
        "numeric_pid_signal_fallback_allowed",
        "paid_resource_allowed",
        "production_access_allowed",
        "provider_access_allowed",
        "reboot_kernel_crash_or_power_fault_allowed",
        "root_or_privilege_escalation_allowed",
    ):
        require(safety[key] is False, f"safety boundary widened: {key}")
    require(
        safety["allowed_operation_ids"]
        == [
            "CREATE_EXACT_RUN_ROOT",
            "SQLITE_EXACT_PROFILE_SETUP",
            "SPAWN_ONE_ASSIGNED_CHILD",
            "PIDFD_OPEN_ASSIGNED_CHILD",
            "PIDFD_SEND_SIGNAL_SIGKILL",
            "FRESH_EXEC_REOPEN",
            "WRITE_BOUND_RECEIPTS",
            "CLEANUP_EXACT_RUN_ROOT",
        ],
        "allowed operation catalog drift",
    )

    receipts = manifest["receipt_bindings"]
    for key in (
        "claim_receipt_is_owner_envelope",
        "cleanup_or_custody_receipt_is_owner_envelope",
        "post_run_receipts_grant_authority",
        "preflight_receipt_is_owner_envelope",
    ):
        require(receipts[key] is False, f"receipt became authority: {key}")
    require(
        receipts["receipt_hash_domain_profile"] == "DOMAIN_SEPARATED_PARENT_SHA256_CHAIN"
        and receipts["receipt_parent_chain"]
        == [
            "PREFLIGHT",
            "CONTROL_SNAPSHOT",
            "CLAIM",
            "RAW_OBSERVATIONS",
            "RETENTION",
            "SEMANTIC",
            "BATCH_RESULT",
            "OPTIONAL_STOP",
            "CLEANUP",
            "CUSTODY",
        ]
        and receipts["stop_receipt_required_if_triggered"] is True,
        "receipt evidence chain drift",
    )

    nonclaims = manifest["nonclaims"]
    for key, value in nonclaims.items():
        if key == "side_effects_unlocked":
            require(value == "NONE", "manifest side effects unlocked")
        elif isinstance(value, bool):
            require(value is False, f"manifest nonclaim became true: {key}")
        elif isinstance(value, int):
            require(value == 0, f"manifest actual count became nonzero: {key}")

    for path, value in all_scalar_items(manifest):
        leaf = path.split(".")[-1]
        if isinstance(value, str):
            require(
                value.isascii() and all(0x20 <= ord(character) <= 0x7E for character in value),
                f"manifest string is outside printable ASCII: {path}",
            )
        if leaf.endswith("_sha256"):
            require(
                isinstance(value, str)
                and re.fullmatch(r"[0-9a-f]{64}", value) is not None
                and value != "0" * 64,
                f"manifest digest malformed or zero: {path}",
            )


def all_scalar_items(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    output: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else key
            output.extend(all_scalar_items(value[key], path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            output.extend(all_scalar_items(item, f"{prefix}[{index}]"))
    else:
        output.append((prefix, value))
    return output


def validate_zero_authority(value: dict[str, Any], label: str) -> None:
    for path, item in all_scalar_items(value):
        lower = path.lower()
        leaf = lower.split(".")[-1]
        if "side_effects_unlocked" in lower:
            require(item == "NONE", f"{label} side effects unlocked: {path}")
        if isinstance(item, bool) and (
            leaf.startswith("actual_")
            or leaf
            in {
                "real_owner_manifest_present",
                "real_owner_envelope_present",
                "real_owner_signature_present",
                "real_trust_anchor_present",
                "may_execute_live_canary",
                "live_canary_executed",
                "live_root_created",
                "runner_launched",
                "execution_authorized",
                "owned_lab_execution_authorized",
                "execution_started",
                "execution_start_permitted",
                "owner_signature_present",
                "owner_identity_bound",
                "provider_or_production_authority",
                "global_runtime_admission",
                "single_use_execution_permit_issued",
            }
        ):
            require(item is False, f"{label} real/live authority became true: {path}")
        if isinstance(item, int) and leaf.startswith("actual_"):
            require(item == 0, f"{label} actual count became nonzero: {path}")


def validate_contract_status_successor(
    repo: Path,
    contract: dict[str, Any],
    status: dict[str, Any],
    successor: dict[str, Any],
) -> tuple[str, str]:
    require(set(contract) == set(CONTRACT_KEYS), "contract top-level key drift")
    require(set(status) == set(STATUS_KEYS), "status top-level key drift")
    require(set(successor) == set(SUCCESSOR_KEYS), "successor top-level key drift")
    require(
        contract.get("schema")
        == "agent_bridge.memory_temporal_owned_lab_source_bound_runner_contract_s19.v0",
        "contract schema",
    )
    require(
        status.get("schema")
        == "agent_bridge.memory_temporal_owned_lab_source_bound_runner_status_s19.v0",
        "status schema",
    )
    require(
        successor.get("schema")
        == "agent_bridge.memory_temporal_successor_admission_gate_s19.v0",
        "successor schema",
    )
    status_text = contract.get("status")
    decision = contract.get("decision")
    require(isinstance(status_text, str) and "S19" in status_text, "contract status")
    require(isinstance(decision, str) and decision, "contract decision")
    require(status.get("status") == status_text and status.get("decision") == decision, "status drift")
    require(
        successor.get("status") == status_text and successor.get("decision") == decision,
        "successor drift",
    )
    implementation_mode = "NON_LIVE_PRIVATE_CHILD_DEFAULT_OFF_SYNTHETIC_KAT_ONLY"
    require(contract.get("implementation_mode") == implementation_mode, "contract mode")
    require(status.get("implementation_mode") == implementation_mode, "status mode")
    require(
        successor.get("completed_boundary", {}).get("implementation_mode")
        == implementation_mode,
        "successor mode",
    )
    require(
        contract.get("predecessor", {}).get("s18_integration_commit") == BASELINE_COMMIT,
        "contract predecessor binding",
    )
    schema_artifacts = contract.get("schema_artifacts", {})
    require(
        set(schema_artifacts) == set(CONTRACT_SCHEMA_BINDINGS),
        "contract schema artifact catalog drift",
    )
    for key, path in CONTRACT_SCHEMA_BINDINGS.items():
        require(
            schema_artifacts.get(key) == artifact_sha256(repo, path),
            f"contract schema artifact hash drift: {key}",
        )
    subject = contract.get("subject_manifest", {})
    require(subject.get("schema_id") == SCHEMA_IDS[MANIFEST_SCHEMA_PATH], "contract manifest schema")
    require(
        subject.get("canonicalization")
        == "AB_RESTRICTED_CANONICAL_JSON_S19_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT",
        "contract canonicalization",
    )
    require(
        subject.get("candidate_envelope_is_expected_builder_input") is False
        and subject.get("synthetic_fixture_is_owner_authority") is False,
        "candidate-derived or synthetic owner authority enabled",
    )
    preflight = contract.get("preflight", {})
    require(
        preflight.get("preflight_token_consumed_by_value_for_one_claim_api_call") is True
        and preflight.get("trusted_module_caller_can_revalidate_a_new_token") is True
        and preflight.get("rich_json_receipt_emitted_parsed_or_validated_by_s19_rust") is False
        and preflight.get("real_preflight_observer_present") is False,
        "preflight implementation boundary overclaim",
    )
    claim = contract.get("single_use_claim", {})
    require(
        claim.get("transaction_open") == "BEGIN_IMMEDIATE"
        and claim.get("cas_sql_where_profile")
        == "EXACT_ALL_BINDINGS_AND_CONTROLS_SINGLE_UPDATE"
        and tuple(claim.get("cas_where_required_bindings", ())) == CAS_WHERE_BINDINGS
        and claim.get("transition") == "UNCLAIMED_TO_CONSUMED_FOR_EXACT_RUN"
        and (
            claim.get("successful_affected_rows"),
            claim.get("failed_affected_rows"),
            claim.get("maximum_successful_claims"),
        )
        == (1, 0, 1),
        "contract CAS binding drift",
    )
    require(
        claim.get("manifest_failed_cas_policy") == "NO_AUTOMATIC_RETRY"
        and claim.get("failed_cas_mutates_unclaimed") is False
        and claim.get("failed_cas_grants_execution") is False
        and claim.get("failed_cas_allows_automatic_retry_by_policy") is False
        and claim.get("s19_claim_api_contains_internal_retry_loop") is False
        and claim.get("failed_attempt_ledger_tombstone_implemented") is False
        and claim.get("trusted_caller_revalidation_orchestration_blocked_by_s19") is False
        and claim.get("no_automatic_retry_controller_orchestration_is_s20_hard_obligation")
        is True,
        "failed-CAS enforcement boundary overclaim",
    )
    external = contract.get("external_control", {})
    require(
        external.get("sqlite_application_id") == 1094865689
        and external.get("sqlite_user_version") == 19
        and external.get("sqlite_profile_sha256") == SQLITE_PROFILE_SHA256
        and external.get("sqlite_schema_sha256") == SQLITE_SCHEMA_CATALOG_SHA256
        and external.get("required_tables_in_one_transaction")
        == ["authority_control", "claim_ledger", "claim_receipts"]
        and external.get("stop_transition") == "CLEAR_TO_TRIGGERED_ABSORBING"
        and external.get("revocation_epoch_comparison") == "ANCHOR_FLOOR_LE_EXTERNAL_EQ_SIGNED",
        "external control binding drift",
    )
    require(
        external.get("guarantee_scope") == "CURRENT_VERIFIED_SQLITE_DATABASE_INSTANCE_ONLY"
        and external.get("whole_file_rollback_resistance_implemented") is False
        and external.get("external_anti_rollback_checkpoint_implemented") is False
        and external.get("action_start_linearization_implemented") is False,
        "external control guarantee overclaim",
    )
    post_run = contract.get("post_run_evidence", {})
    require(
        post_run.get("shape_status")
        == "S20_TARGET_SCHEMA_ONLY_NOT_EMITTED_OR_VALIDATED_BY_S19_RUST"
        and post_run.get("rich_json_receipt_bundle_emitted_parsed_or_validated_by_s19_rust")
        is False,
        "post-run rich packet overclaim",
    )
    implementation = contract.get("implementation", {})
    false_implementation = {
        "rich_preflight_control_claim_or_post_run_json_packet_builders_available",
        "rich_preflight_control_claim_or_post_run_json_packet_validators_available",
        "real_runner_dispatch_available",
        "live_observation_execution_available",
    }
    require(
        all(isinstance(value, bool) for value in implementation.values())
        and {key for key, value in implementation.items() if value is False}
        == false_implementation,
        "contract implementation availability drift",
    )
    implemented = status.get("implemented", {})
    absent = status.get("not_implemented_or_not_present", {})
    require(
        implemented and all(value is True for value in implemented.values()),
        "status implemented catalog weakened",
    )
    require(absent and all(value is False for value in absent.values()), "status absent catalog drift")
    completed = successor.get("completed_boundary", {})
    require(
        completed.get("s19_claim_api_contains_internal_retry_loop") is False
        and completed.get("trusted_module_caller_can_revalidate_a_new_preflight_token") is True
        and completed.get("s19_rust_emits_or_validates_four_rich_target_packets") is False
        and completed.get("rich_post_run_receipt_chain_emitted_or_validated") is False,
        "successor completed-boundary overclaim",
    )
    successor_next = successor.get("next_stage", {})
    require(
        successor_next.get("preapproved") is False
        and all(
            value is True
            for key, value in successor_next.items()
            if key.startswith("requires_")
        ),
        "successor hard obligation drift",
    )
    require(
        contract.get("successor_boundary", {}).get("first_possible_live_stage")
        == status.get("next_stage", {}).get("identity")
        == successor.get("next_stage", {}).get("identity"),
        "S20 successor identity drift",
    )
    combined = canonical_structure_bytes([contract, status, successor]).decode("utf-8")
    for token in (
        "BEGIN_IMMEDIATE",
        "UNCLAIMED_TO_CONSUMED_FOR_EXACT_RUN",
        "NO_AUTOMATIC_RETRY",
        "ABSORBING_STOP",
        "CURRENT_REVOCATION",
        "NON_LIVE",
        "SIDE_EFFECTS_UNLOCKED",
        "FAILED_ATTEMPT_LEDGER_TOMBSTONE",
        "TRUSTED_MODULE_CALLER",
        "CONTROLLER_ORCHESTRATION",
        "S20",
    ):
        require(token in combined.upper(), f"contract/status/successor token missing: {token}")
    validate_zero_authority(contract, "contract")
    validate_zero_authority(status, "status")
    validate_zero_authority(successor, "successor")
    return status_text, decision


def validate_sources(repo: Path) -> int:
    cargo = read_text(repo, CARGO_PATH)
    s18_source = read_text(repo, S18_RUST_PATH)
    source = read_text(repo, RUST_SOURCE_PATH)
    cargo_addition = f'{FEATURE} = ["temporal-evidence-s18-owned-lab-authorization-verifier-synthetic"]\n'
    require(cargo.count(cargo_addition) == 1, "S19 feature dependency drift")
    require(
        hashlib.sha256(cargo.replace(cargo_addition, "", 1).encode()).hexdigest()
        == BASELINE_CARGO_SHA256,
        "Cargo contains changes beyond the exact S19 feature",
    )
    module_addition = (
        f'#[cfg(feature = "{FEATURE}")]\n'
        "mod source_bound_runner;\n\n"
    )
    require(s18_source.count(module_addition) == 1, "S19 private child module drift")
    require(
        hashlib.sha256(s18_source.replace(module_addition, "", 1).encode()).hexdigest()
        == BASELINE_S18_RUST_SHA256,
        "S18 verifier contains changes beyond the exact private S19 child",
    )
    required_tokens = (
        "TransactionBehavior::Immediate",
        "CONSUMED_FOR_EXACT_RUN",
        "UNCLAIMED",
        "expected_unclaimed_revision",
        "authorization_id",
        "subject_manifest",
        "revocation",
        "stop",
        "side_effects",
    )
    for token in required_tokens:
        require(token.lower() in source.lower(), f"Rust S19 token missing: {token}")
    test_module_offset = source.find("\n#[cfg(test)]\nmod tests")
    require(test_module_offset > 0, "Rust S19 test module boundary missing")
    implementation_source = source[:test_module_offset]
    forbidden_tokens = (
        "Command::new",
        "use std::process::Command",
        "libc::mount(",
        "TcpStream::",
        "UdpSocket::",
        "reqwest::",
        "Connection::open(",
        "SQLITE_OPEN_CREATE",
        "INSERT OR REPLACE",
        "INSERT OR IGNORE",
        "ON CONFLICT",
        "DELETE FROM",
        "DROP TABLE",
        "DROP TRIGGER",
        "PRAGMA writable_schema",
        "ATTACH DATABASE",
        "VACUUM INTO",
        "load_extension",
        "unsafe {",
    )
    for token in forbidden_tokens:
        require(
            token.lower() not in implementation_source.lower(),
            f"Rust S19 forbidden implementation surface: {token}",
        )
    permit_offset = source.find("struct ClaimedRunPermitV1")
    require(permit_offset >= 0, "opaque claimed-run permit missing")
    permit_prefix = source[max(0, permit_offset - 160):permit_offset]
    require(
        all(token not in permit_prefix for token in ("Serialize", "Clone", "Copy")),
        "claimed-run permit became serializable or cloneable",
    )
    require(
        "impl Serialize for ClaimedRunPermitV1" not in source
        and "impl Clone for ClaimedRunPermitV1" not in source,
        "claimed-run permit gained an authority-copy implementation",
    )
    require(
        "_affine_not_clone_or_serialize: Rc<()>" in source,
        "claimed-run permit lost its affine process-local marker",
    )
    for token in (
        "OpenFlags::SQLITE_OPEN_READ_WRITE",
        "OpenFlags::SQLITE_OPEN_NOFOLLOW",
        "PRAGMA quick_check(1)",
        "sqlite_schema_catalog_digest",
        "authority_control_transition_guard",
        "authority_control_delete_guard",
        "claim_ledger_transition_guard",
        "claim_ledger_delete_guard",
        "claim_receipts_update_guard",
        "claim_receipts_delete_guard",
        "controls_match_authorized_subject",
        "#[cfg(test)]\nfn initialize_new_synthetic_ledger_for_test",
    ):
        require(token in implementation_source, f"Rust S19 fail-closed kernel token missing: {token}")
    independent_start = source.find("struct IndependentSubjectInputsV1 {")
    require(independent_start >= 0, "independent manifest input type missing")
    independent_end = source.find("\n}", independent_start)
    require(independent_end > independent_start, "independent manifest input type malformed")
    independent_fields = source[independent_start:independent_end].lower()
    require(
        "candidate" not in independent_fields and "envelope" not in independent_fields,
        "independent manifest inputs gained candidate material",
    )
    builder_start = source.find("fn build_subject_manifest_v1(")
    builder_end = source.find("\nfn validate_closed_manifest_shape", builder_start)
    require(builder_start >= 0 and builder_end > builder_start, "typed manifest builder missing")
    builder = source[builder_start:builder_end]
    require(
        "inputs: &IndependentSubjectInputsV1" in builder
        and "candidate" not in builder.lower()
        and "envelope" not in builder.lower(),
        "typed expected manifest builder is not candidate-independent",
    )
    composition_start = source.find("fn verify_authorized_unclaimed_subject_v1(")
    composition_end = source.find("\n#[derive(Clone)]\nstruct ControlSnapshotV1", composition_start)
    require(
        composition_start >= 0 and composition_end > composition_start,
        "S18 opaque verifier composition missing",
    )
    composition = source[composition_start:composition_end]
    require(
        "let subject = verify_subject_manifest_v1(manifest_raw, independent_inputs)?;"
        in composition
        and "let payload = build_expected_s18_payload_v1(&subject, independent_inputs, signing)?;"
        in composition
        and "verify_unclaimed_owner_authorization_v1(anchor_raw, envelope_raw, &expected)?"
        in composition,
        "S18 composition is not independently expected and opaque",
    )
    claim_start = source.find("fn try_claim_once_v1(")
    claim_end = source.find("\nfn redeem_consumed_claim_after_fresh_controls_v1", claim_start)
    require(claim_start >= 0 and claim_end > claim_start, "single-invocation CAS function missing")
    claim_function = source[claim_start:claim_end]
    require(
        "preflight: ValidatedPreflightV1" in claim_function
        and "preflight: &ValidatedPreflightV1" not in claim_function
        and "loop {" not in claim_function
        and "while " not in claim_function
        and "return Ok(ClaimAttemptV1::FailedCas);" in claim_function,
        "CAS function does not consume one preflight token without an internal retry loop",
    )
    tests = re.findall(r"fn (s19_[a-z0-9_]+)\s*\(", source)
    required_tests = {
        "s19_typed_manifest_independent_expected_and_s18_opaque_composition_accept",
        "s19_candidate_manifest_cannot_redefine_independent_expected_binding",
        "s19_failed_cas_after_control_drift_leaves_unclaimed_and_never_retries",
        "s19_successful_claim_reopen_is_consumed_and_second_claim_fails",
        "s19_claim_then_stop_change_blocks_permit_but_remains_consumed",
        "s19_action_boundary_rechecks_absorbing_stop",
        "s19_stop_is_absorbing_and_revocation_is_monotonic",
        "s19_post_run_validator_keeps_receipts_separate_from_authority",
        "s19_missing_ledger_never_creates_on_reopen",
        "s19_current_stage_has_no_live_dispatch_or_real_side_effect_counter",
        "s19_committed_synthetic_manifest_frame_matches_typed_builder_exactly",
        "s19_preflight_rejects_manifest_bound_control_and_environment_drift",
        "s19_sqlite_schema_profile_is_frozen_and_reopen_verified",
    }
    require(
        len(tests) == len(set(tests))
        and len(tests) >= 13
        and required_tests.issubset(tests),
        "insufficient or duplicate S19 Rust KATs",
    )
    committed_fixture_literal = (
        '"/../../docs/design/fixtures/'
        'biocortex-ab-track-b-owned-lab-subject-manifest-synthetic-s19-v0.json"'
    )
    require(
        "include_bytes!(concat!(" in source
        and committed_fixture_literal in source
        and '.strip_suffix(b"\\n")' in source
        and "assert!(!canonical_payload.contains(&b'\\n'));" in source
        and "canonical_payload == fixture.manifest_raw" in source,
        "committed synthetic fixture exact-frame KAT drift",
    )
    return len(tests)


def validate_docs(design: str, report: str) -> None:
    combined = (design + "\n" + report).lower()
    for token in (
        "non-live",
        "candidate",
        "expected",
        "begin immediate",
        "failed cas",
        "no automatic retry",
        "consumed",
        "absorbing stop",
        "revocation",
        "side_effects_unlocked=none",
        "s20",
    ):
        require(token in combined, f"documentation token missing: {token}")


def expect_failure(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except (CheckFailure, KeyError, TypeError, ValueError):
        return
    raise CheckFailure(f"negative mutation accepted: {label}")


def self_test(
    repo: Path,
    s17: Any,
    schemas: dict[str, dict[str, Any]],
    synthetic: dict[str, Any],
    contract: dict[str, Any],
    status: dict[str, Any],
    successor: dict[str, Any],
) -> None:
    manifest_schema = schemas[MANIFEST_SCHEMA_PATH]
    for path, schema in schemas.items():
        unsupported = copy.deepcopy(schema)
        unsupported["not"] = {"type": "null"}
        expect_failure(
            f"unsupported schema keyword {path}",
            lambda value=unsupported, label=path: validate_schema_evaluator_coverage(value, label),
        )
        opened = copy.deepcopy(schema)

        def open_first_object(node: Any) -> bool:
            if isinstance(node, dict):
                declared_type = node.get("type")
                if declared_type == "object" or (
                    isinstance(declared_type, list) and "object" in declared_type
                ):
                    node["additionalProperties"] = True
                    return True
                return any(open_first_object(child) for child in node.values())
            if isinstance(node, list):
                return any(open_first_object(child) for child in node)
            return False

        require(open_first_object(opened), f"schema has no object to mutate: {path}")
        expect_failure(
            f"open object schema {path}",
            lambda value=opened, label=path: validate_closed_schema_graph(value, label),
        )
    unknown = copy.deepcopy(synthetic)
    unknown["candidate_envelope"] = copy.deepcopy(synthetic)
    expect_failure(
        "candidate-derived manifest",
        lambda: independently_rebuild_manifest(unknown, manifest_schema),
    )
    missing = copy.deepcopy(synthetic)
    missing.pop(next(iter(manifest_schema["required"])))
    expect_failure("missing manifest field", lambda: independently_rebuild_manifest(missing, manifest_schema))
    mutated_contract = copy.deepcopy(contract)
    mutated_contract["status"] = "S19_LIVE_SIDE_EFFECTS_UNLOCKED"
    expect_failure(
        "live contract",
        lambda: validate_contract_status_successor(repo, mutated_contract, status, successor),
    )
    mutated_status = copy.deepcopy(status)
    mutated_status["status"] = "DRIFT"
    expect_failure(
        "status mismatch",
        lambda: validate_contract_status_successor(repo, contract, mutated_status, successor),
    )
    nonzero_execution = copy.deepcopy(status)
    nonzero_execution["actual_execution"]["actual_observation_count"] = 1
    expect_failure(
        "nonzero actual execution",
        lambda: validate_contract_status_successor(
            repo, contract, nonzero_execution, successor
        ),
    )
    unknown_instance = copy.deepcopy(synthetic)
    unknown_instance["unexpected"] = False
    require(
        bool(s17.schema_instance_errors(manifest_schema, unknown_instance, manifest_schema)),
        "unknown-field schema self-test",
    )


def receipt_rows(
    repo: Path,
    status_text: str,
    decision: str,
    schemas: dict[str, dict[str, Any]],
    synthetic_artifact_raw: bytes,
    synthetic_canonical_payload: bytes,
    rebuilt: dict[str, Any],
    rust_test_count: int,
) -> list[tuple[str, str]]:
    rows = [
        ("schema", "agent_bridge.memory_temporal_owned_lab_source_bound_runner_s19_validation_receipt.v0"),
        ("status", status_text),
        ("decision", decision),
        ("baseline_commit", BASELINE_COMMIT),
        ("implementation_mode", "NON_LIVE_PRIVATE_CHILD_DEFAULT_OFF_SYNTHETIC_KAT_ONLY"),
        ("rich_s19_receipt_schema_runtime_validation_implemented", "false"),
        ("rich_s19_receipt_schemas_target_stage", "S20"),
        ("candidate_derived_expected_allowed", "false"),
        ("s18_to_s19_live_composition_claimed", "false"),
        ("single_use_cas_state", "UNCLAIMED_TO_CONSUMED_FOR_EXACT_RUN"),
        ("failed_cas_automatic_retry_allowed", "false"),
        ("failed_cas_affected_rows", "0"),
        ("failed_cas_mutates_authorized_unclaimed", "false"),
        ("failed_cas_issues_permit", "false"),
        ("s19_preflight_token_consumed_by_value", "true"),
        ("s19_failed_attempt_ledger_tombstone_implemented", "false"),
        ("s19_trusted_caller_revalidation_prevented", "false"),
        (
            "no_automatic_retry_enforcement_boundary",
            "S20_TRUSTED_CONTROLLER_ORCHESTRATION_HARD_OBLIGATION",
        ),
        ("successful_claim_then_crash_reuse_allowed", "false"),
        ("signed_stop_substitutes_for_use_time_external_read", "false"),
        ("real_side_effects_unlocked", "NONE"),
        ("full_catalog_augmented_fingerprint_count", "5639"),
        ("target_phase_unique_match_count", "113"),
        ("actual_owner_trust_anchor_count", "0"),
        ("actual_owner_signature_count", "0"),
        ("actual_live_cas_claim_count", "0"),
        ("actual_execution_capability_count", "0"),
        ("actual_runner_launch_count", "0"),
        ("actual_observation_count", "0"),
        ("synthetic_manifest_artifact_len", str(len(synthetic_artifact_raw))),
        (
            "synthetic_manifest_artifact_sha256",
            hashlib.sha256(synthetic_artifact_raw).hexdigest(),
        ),
        ("synthetic_manifest_canonical_payload_len", str(len(synthetic_canonical_payload))),
        (
            "synthetic_manifest_canonical_payload_sha256",
            hashlib.sha256(synthetic_canonical_payload).hexdigest(),
        ),
        ("rebuilt_manifest_sha256", canonical_structure_sha256(rebuilt)),
        ("rust_s19_test_count", str(rust_test_count)),
    ]
    for path in SCHEMA_IDS:
        rows.append((Path(path).stem + "_canonical_sha256", canonical_structure_sha256(schemas[path])))
    for label, path in S19_ARTIFACT_ROWS:
        rows.append((label, artifact_sha256(repo, path)))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]

    _s18, s17 = validate_predecessor(repo)
    schemas = {path: load_json(repo, path) for path in SCHEMA_IDS}
    contract = load_json(repo, CONTRACT_PATH)
    status = load_json(repo, STATUS_PATH)
    successor = load_json(repo, SUCCESSOR_PATH)
    synthetic_raw = read_bytes(repo, SYNTHETIC_PATH)
    require(synthetic_raw.isascii(), "synthetic manifest contains non-ASCII bytes")
    require(
        synthetic_raw.endswith(b"\n") and not synthetic_raw.endswith(b"\n\n"),
        "synthetic manifest repository framing must end in exactly one LF",
    )
    synthetic_payload = synthetic_raw[:-1]
    require(
        synthetic_payload
        and b"\n" not in synthetic_payload
        and not synthetic_payload.endswith((b" ", b"\t", b"\r")),
        "synthetic manifest canonical payload contains trailing or embedded whitespace",
    )
    synthetic = parse_json_bytes(synthetic_payload, SYNTHETIC_PATH)
    require(
        canonical_structure_bytes(synthetic) == synthetic_payload,
        "synthetic manifest payload is not exact compact sorted-key canonical bytes",
    )

    validate_schemas(s17, schemas, synthetic)
    validate_manifest_semantics(synthetic)
    rebuilt = independently_rebuild_manifest(synthetic, schemas[MANIFEST_SCHEMA_PATH])
    require(rebuilt == synthetic, "independent manifest reconstruction drift")
    status_text, decision = validate_contract_status_successor(repo, contract, status, successor)
    rust_test_count = validate_sources(repo)
    validate_docs(read_text(repo, DESIGN_PATH), read_text(repo, REPORT_PATH))
    if args.self_test:
        self_test(repo, s17, schemas, synthetic, contract, status, successor)

    for key, value in receipt_rows(
        repo,
        status_text,
        decision,
        schemas,
        synthetic_raw,
        synthetic_payload,
        rebuilt,
        rust_test_count,
    ):
        print(f"{key}\t{value}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print(f"S19 source-bound runner check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
