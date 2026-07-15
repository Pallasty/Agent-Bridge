#!/usr/bin/env python3
"""Validate the source-only Track B context/sampling determinism pack.

The checker binds three independent source algorithms to the frozen public
dependency graph and executes only public synthetic known-answer vectors.  It
does not read a real memory store or frame, obtain entropy, create a receipt,
produce reviewer packets, authorize condition output, score, or unblind.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import re
import sys
import types
from pathlib import Path
from typing import Any, Callable


PACK_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_context_sampling_determinism_pack.v0"
)
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_context_sampling_determinism_pack_synthetic.v0"
)
BASELINE_COMMIT = "d4e4093d9b273bc36ed2fb4c373e15dcd8467a55"
GRAPH_SOURCE_COMMIT = "ba4dbae629398ec16e4f22f4b0ac7f2ce372541f"
PREDECESSOR_SOURCE_COMMIT = "78c72f3af29c6043afdc92e15a71d2b6b36d0205"
DECISION = "SOURCE_CONTEXT_AND_SAMPLING_DETERMINISM_IMPLEMENTED_NOT_LIVE_BOUND"
CANONICAL_SERIALIZATION = (
    "UTF8_SORTED_KEYS_INDENT_2_LF_FINAL_NEWLINE_NO_NAN_DUPLICATE_KEYS_REJECTED"
)

MANIFEST_PATH = (
    "scripts/eval/fixtures/"
    "biocortex_ab_track_b_context_sampling_determinism_pack_v0.json"
)
FIXTURE_PATH = (
    "scripts/eval/fixtures/"
    "biocortex_ab_track_b_context_sampling_determinism_pack_synthetic_v0.json"
)
REFERENCE_PATH = "scripts/eval/biocortex_ab_track_b_reference_context_builder_v0.py"
SEED_PATH = "scripts/eval/biocortex_ab_track_b_sampling_seed_derivation_v0.py"
SELECTION_PATH = "scripts/eval/biocortex_ab_track_b_sampling_selection_v0.py"
GRAPH_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
LEDGER_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
ADMISSION_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
STRICT_PACK_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_strict_review_pack_v0.json"
SAMPLING_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json"
)
S0_SOURCE_PATH = "crates/store/examples/memory_reference_admission_fixture.rs"
S0_LIB_PATH = "crates/store/src/lib.rs"
S0_FIXTURE_PATH = "scripts/eval/fixtures/biocortex_ab_reference_admission_v1.json"
S0_EXPECTED_PATH = (
    "scripts/eval/fixtures/biocortex_ab_reference_admission.expected.v1.tsv"
)

GRAPH_SHA256 = "8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af"
LEDGER_SHA256 = "764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341a"
ADMISSION_SHA256 = "1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e"
STRICT_PACK_SHA256 = "24abcd9eb33eb9f999df2a0f791ea3c6167f766c95268f4f5f29497b771bfc61"
SAMPLING_SCHEMA_SHA256 = (
    "9e73afee2f6366a241b155680b4f77341adeb7c4e341ab91b8d4b1499b5aacbd"
)
S0_SOURCE_SHA256 = "3ed5c67ca5e4673c9afdf5639a95115399d4e7ce3c6d5774f6513dac76adc016"
S0_LIB_SHA256 = "4e357d77d35d82c7fe6ac8de5b1870af7296cf10c72cf57ff684e49625a0638b"
S0_FIXTURE_SHA256 = "a2d8718e5982b030659f20c69a893ec4d1e39f3b10b01fdd960df0ac55f9af4d"
S0_EXPECTED_SHA256 = "04bfaf10a8bf343ff133b46388ea798ee81e6fd605198d6a48f84ea9236cc32c"
REFERENCE_SHA256 = "c37ac35cb349170b6830fb900de642bfc9572111b351bb031244c0485e282227"
SEED_SHA256 = "4f51781ff707e89b4c09adffeafbdaacd75c7e1571d1a86e45d336aace888a3f"
SELECTION_SHA256 = "e327faf2ad73718dc33f68fdb66a89abf0ac84fbbf8d828ff79fa0e8b75772ec"
FIXTURE_SHA256 = "5d31766048a9d5c6f61ee60c79dd00fba3ca9993017eb5c5fedb7d6bd31cb3ca"

MAX_SINGLE_ARTIFACT_BYTES = 33_554_432
MAX_TOTAL_INPUT_BYTES = 67_108_864
MAX_OUTPUT_BYTES = 33_554_432

EXPECTED_EVIDENCE = {
    S0_SOURCE_PATH: S0_SOURCE_SHA256,
    S0_LIB_PATH: S0_LIB_SHA256,
    SAMPLING_SCHEMA_PATH: SAMPLING_SCHEMA_SHA256,
    S0_EXPECTED_PATH: S0_EXPECTED_SHA256,
    S0_FIXTURE_PATH: S0_FIXTURE_SHA256,
    GRAPH_PATH: GRAPH_SHA256,
    LEDGER_PATH: LEDGER_SHA256,
    ADMISSION_PATH: ADMISSION_SHA256,
    STRICT_PACK_PATH: STRICT_PACK_SHA256,
}

ARTIFACT_BINDINGS = [
    {
        "artifact_kind": "reference_context_builder",
        "binding_path": "reference_condition.context_builder_sha256",
        "local_dependencies": [],
        "provider_neutral": True,
        "repo_path": REFERENCE_PATH,
        "schema_id": None,
        "sha256": REFERENCE_SHA256,
        "source_status": "SOURCE_ARTIFACT_IMPLEMENTED_NOT_LIVE_BOUND",
        "unlocks_side_effect": False,
    },
    {
        "artifact_kind": "sampling_seed_derivation_algorithm",
        "binding_path": "sampling.sampling_seed_derivation_sha256",
        "local_dependencies": [],
        "provider_neutral": True,
        "repo_path": SEED_PATH,
        "schema_id": None,
        "sha256": SEED_SHA256,
        "source_status": "SOURCE_ARTIFACT_IMPLEMENTED_NOT_LIVE_BOUND",
        "unlocks_side_effect": False,
    },
    {
        "artifact_kind": "stratified_hmac_selection_algorithm",
        "binding_path": "sampling.sampling_selection_algorithm_sha256",
        "local_dependencies": [],
        "provider_neutral": True,
        "repo_path": SELECTION_PATH,
        "schema_id": None,
        "sha256": SELECTION_SHA256,
        "source_status": "SOURCE_ARTIFACT_IMPLEMENTED_NOT_LIVE_BOUND",
        "unlocks_side_effect": False,
    },
]

PREVIOUS_COMPLETED = (
    "review_and_blinding.map_bijection_checker_sha256",
    "review_and_blinding.map_schema_sha256",
    "review_and_blinding.review_command_schema_sha256",
    "review_and_blinding.review_receipt_schema_sha256",
    "review_and_blinding.review_schema_sha256",
    "sampling.sampling_receipt_schema_sha256",
    "truth_inputs.referent_schema_sha256",
    "truth_inputs.strict_case_algorithm_sha256",
    "truth_inputs.truth_manifest_schema_sha256",
)
TARGET_BINDINGS = (
    "reference_condition.context_builder_sha256",
    "sampling.sampling_seed_derivation_sha256",
    "sampling.sampling_selection_algorithm_sha256",
)
COMPLETED_PUBLIC_BINDINGS = tuple(sorted((*PREVIOUS_COMPLETED, *TARGET_BINDINGS)))
NEXT_PUBLIC_FRONTIER = ("sampling.sampling_receipt_writer_sha256",)

BOUNDARY = {
    "anti_shopping_order_verified": False,
    "condition_ids_or_mapping_emitted": False,
    "context_and_result_builder_bound": False,
    "eligible_frame_bytes_verified": False,
    "entropy_custody_verified": False,
    "frame_o_excl_receipt_created": False,
    "graph_packet_mutated": False,
    "live_binding_satisfied_count": 0,
    "opaque_answer_ids_emitted": False,
    "private_runtime_artifact_emitted": False,
    "real_run_admitted": False,
    "reviewer_packet_created": False,
    "reviewer_visible_sampling_weights_emitted": False,
    "runtime_context_receipt_created": False,
    "runtime_instance_validated": False,
    "sampling_receipt_created": False,
    "sampling_seed_secrecy_claimed": False,
    "scoring_authorized": False,
    "side_effects_unlocked": "NONE",
    "source_artifact_count": 3,
    "unblinding_authorized": False,
}

RESOURCE_CAPS = {
    "max_cases": 4096,
    "max_context_bytes": 16_777_216,
    "max_metadata_items_per_hit": 1024,
    "max_output_bytes": MAX_OUTPUT_BYTES,
    "max_reference_hits": 40,
    "max_reference_input_utf8_bytes": 33_554_432,
    "max_single_artifact_bytes": MAX_SINGLE_ARTIFACT_BYTES,
    "max_strata": 256,
    "max_total_input_bytes": MAX_TOTAL_INPUT_BYTES,
}

ADMISSION_BLOCKERS = (
    "REFERENCE_FROZEN_CLOCK_UNAVAILABLE",
    "REFERENCE_CLEAN_ENV_HARNESS_UNIMPLEMENTED",
    "REFERENCE_DETERMINISTIC_TIE_BREAK_UNPROVED",
    "REFERENCE_HARD_CONTEXT_BUDGET_UNSET",
    "REFERENCE_RUNTIME_BINARY_AND_SNAPSHOT_UNSET",
    "CANDIDATE_STORE_ADAPTER_BLOCKED_DATA_MODEL",
    "PREVALENCE_FRAME_SAMPLING_AND_POWER_UNSET",
    "TRUTH_AS_OF_AND_AUTHORITY_MANIFEST_UNSET",
    "FRESH_REVIEWER_AND_BLIND_MAP_BINDINGS_UNSET",
    "LATENCY_HARDWARE_TOKENIZER_AND_ORDER_UNSET",
    "CANONICAL_SOURCE_AND_STORAGE_MANIFEST_UNSET",
    "POST_FIX_CAPTURE_DATE_NOT_REACHED_IN_THIS_PREREG",
)

STRUCTURAL_BLOCKERS = (
    "DETERMINISTIC_TRUTH_GATE_PRODUCER_AND_PROVENANCE_UNBOUND",
    "ELIGIBLE_FRAME_AND_STRATA_MANIFEST_SCHEMAS_UNBOUND",
    "EXTERNAL_ENTROPY_CUSTODY_AND_ANTI_SHOPPING_ORDER_UNBOUND",
    "NON_CIRCULAR_CONTRACT_DIGEST_PROFILE_UNBOUND",
    "REFERENCE_RUNTIME_CONFIG_SNAPSHOT_CLOCK_AND_BUDGET_UNBOUND",
    "REVIEW_PROVENANCE_CHECKER_UNBOUND",
    "REVIEW_RAW_RESPONSE_SCHEMA_UNBOUND",
    "REVIEWER_ROSTER_INSTRUCTION_AND_CONFLICT_MANIFEST_UNBOUND",
    "SAMPLING_RECEIPT_OMITS_SAMPLING_SEED_COMMITMENT",
    "SAMPLING_RECEIPT_WRITER_UNBOUND",
    "SOURCE_ARTIFACTS_ARE_NOT_RUNTIME_INSTANCES",
)

SEMANTICS = {
    "context_budget_rule": "COMPLETE_PAGE_OR_TERMINAL_ERROR_NEVER_TRUNCATE",
    "context_grain": "ONE_CASE_X_COMPLETE_RANKED_REFERENCE_PAGE",
    "context_projection": (
        "RUST_S0_ACCEPTED_DOMAIN_FIELD_ORDER_COMPACT_UTF8_SORT_AND_DEDUP_"
        "TAGS_AND_RELATED_KEYS"
    ),
    "context_runtime_config": "LATER_HASH_BOUND_INPUT_NOT_SELECTED_BY_SOURCE_ALGORITHM",
    "context_telemetry": (
        "ACCESS_COUNT_LAST_ACCESSED_IMPORTANCE_SCORE_AND_COSINE_FORBIDDEN"
    ),
    "seed_anti_shopping": (
        "NOT_PROVEN_BY_PURE_ALGORITHM_REQUIRES_FRAME_O_EXCL_AND_EXTERNAL_"
        "ENTROPY_CUSTODY_RECEIPTS"
    ),
    "seed_derivation": "SHA256_EXACT_FIVE_PART_NUL_SEPARATED_MESSAGE",
    "seed_domain": "agent-bridge/track-b/sample/v1",
    "seed_public_output": (
        "PUBLICLY_RECOMPUTABLE_FROM_FROZEN_COMMITMENTS_NO_SECRECY_CLAIM_"
        "DIRECT_BYTES_NOT_SERIALIZED"
    ),
    "seed_selection_separation": (
        "DISTINCT_PRIMITIVE_AND_MESSAGE_ARITY_SHARED_PUBLIC_SAMPLING_DOMAIN"
    ),
    "selection_collision_rule": "FULL_WIDTH_HMAC_COLLISION_IS_TERMINAL",
    "selection_commitment": (
        "COMPLETE_RESULT_ENVELOPE_EXCEPT_SELF_CANONICAL_PRETTY_SHA256"
    ),
    "selection_order": "PER_STRATUM_HMAC_SHA256_ASCENDING_NO_MODULO_REDUCTION",
    "selection_projection": (
        "SELECTED_CASE_ID_ORDER_RESERVE_STRATUM_THEN_HMAC_RANK_ORDER"
    ),
    "selection_weight": (
        "REDUCED_N_H_DIV_n_h_REPORTED_NOT_APPLIED_APPLY_EXACTLY_ONCE_AT_CASE_GRAIN"
    ),
    "synthetic_fixture_authority": (
        "KNOWN_ANSWER_VALIDATION_ONLY_NOT_REAL_FRAME_ENTROPY_CONTEXT_OR_RECEIPT"
    ),
}

FIXTURE_BOUNDARY = {
    "condition_output_authorized": False,
    "contains_private_blind_map": False,
    "contains_real_entropy": False,
    "contains_real_frame": False,
    "live_binding_satisfied": False,
    "runtime_context_authorized": False,
    "sampling_receipt_created": False,
    "side_effects_unlocked": "NONE",
}


class PackError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise PackError(code, message)


def reject_constant(value: str) -> Any:
    fail("JSON_CONSTANT", f"non-finite JSON constant {value!r}")


def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("JSON_DUPLICATE_KEY", f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def canonical_pretty_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                indent=2,
                separators=(",", ": "),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail("JSON_CANONICAL", f"cannot serialize canonical JSON: {exc}")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_canonical_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("JSON_UTF8", f"{label} is not UTF-8: {exc}")
    try:
        value = json.loads(
            text,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate_pairs,
        )
    except json.JSONDecodeError as exc:
        fail("JSON_PARSE", f"{label} is malformed: {exc}")
    if type(value) is not dict:
        fail("JSON_ROOT", f"{label} must be an object")
    if canonical_pretty_bytes(value) != raw:
        fail("JSON_CANONICAL", f"{label} bytes are not canonical pretty JSON")
    return value


def read_bytes(root: Path, path: str, maximum: int = MAX_SINGLE_ARTIFACT_BYTES) -> bytes:
    target = root / path
    try:
        size = target.stat().st_size
        if size < 0 or size > maximum:
            fail("FILE_SIZE", f"{path} exceeds its byte cap")
        raw = target.read_bytes()
    except OSError as exc:
        fail("FILE_READ", f"cannot read {path}: {exc}")
    if len(raw) != size:
        fail("FILE_RACE", f"{path} changed during read")
    return raw


def exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        fail("OBJECT_KEYS", f"{label} field set differs from the frozen contract")


def load_module(root: Path, name: str, path: str, expected_sha256: str) -> types.ModuleType:
    raw = read_bytes(root, path)
    if sha256_bytes(raw) != expected_sha256:
        fail("ALGORITHM_HASH", f"{path} byte hash drift")
    spec = importlib.util.spec_from_file_location(name, root / path)
    if spec is None or spec.loader is None:
        fail("ALGORITHM_IMPORT", f"cannot create import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        fail("ALGORITHM_IMPORT", f"cannot import {path}: {exc}")
    return module


def derive_frontier(graph: dict[str, Any], completed: set[str]) -> tuple[str, ...]:
    result: list[str] = []
    for raw in graph["nodes"]:
        node = raw if type(raw) is dict else {}
        path = node.get("artifact_binding_path")
        if path in completed or node.get("primary_readiness_class") != "INDEPENDENT_PUBLIC":
            continue
        dependencies = node.get("local_dependencies")
        if type(dependencies) is list and set(dependencies).issubset(completed):
            result.append(path)
    return tuple(sorted(result))


def validate_graph_and_ledger(graph: dict[str, Any], ledger: dict[str, Any]) -> None:
    nodes = graph.get("nodes")
    bindings = ledger.get("bindings")
    if type(nodes) is not list or type(bindings) is not list:
        fail("GRAPH_SHAPE", "graph nodes or ledger bindings missing")
    by_path = {row.get("artifact_binding_path"): row for row in nodes if type(row) is dict}
    ledger_by_path = {row.get("binding_path"): row for row in bindings if type(row) is dict}
    if len(by_path) != len(nodes) or len(ledger_by_path) != len(bindings):
        fail("GRAPH_DUPLICATE", "graph or ledger repeats a binding path")
    for binding in ARTIFACT_BINDINGS:
        path = binding["binding_path"]
        node = by_path.get(path)
        row = ledger_by_path.get(path)
        if node is None or row is None:
            fail("GRAPH_COVERAGE", f"graph/ledger lacks {path}")
        expected_node = {
            "artifact_kind": binding["artifact_kind"],
            "binding_evidence": None,
            "binding_satisfied": False,
            "blocked_upstream_dependencies": [],
            "committed_artifact_blob_oid": None,
            "committed_artifact_repo_path": None,
            "committed_artifact_sha256": None,
            "external_dependencies": [],
            "implementation_status": "PLANNED_NOT_IMPLEMENTED_OR_BOUND",
            "local_dependencies": [],
            "primary_readiness_class": "INDEPENDENT_PUBLIC",
            "public_authoring_eligible": True,
            "required_stage": "PRE_OUTPUT_ADMISSION",
            "unlocks_side_effect": False,
            "unrepresented_upstream_dependencies": [],
        }
        for key, expected in expected_node.items():
            if node.get(key) != expected:
                fail("GRAPH_TARGET", f"graph target {path}.{key} drift")
        expected_ledger = {
            "binding_evidence": None,
            "binding_path": path,
            "binding_satisfied": False,
            "local_fill_rule": "EXACT_COMMITTED_ARTIFACT_ONLY",
            "owner_class": "local_deterministic",
            "required_stage": "PRE_OUTPUT_ADMISSION",
            "unlocks_side_effect": False,
            "value_kind": "sha256",
        }
        if row != expected_ledger:
            fail("LEDGER_TARGET", f"ledger target drift: {path}")
    if derive_frontier(graph, set(COMPLETED_PUBLIC_BINDINGS)) != NEXT_PUBLIC_FRONTIER:
        fail("GRAPH_FRONTIER", "completed bindings do not derive the one-node frontier")


def validate_frozen_contracts(
    admission: dict[str, Any],
    strict_pack: dict[str, Any],
    sampling_schema: dict[str, Any],
) -> None:
    if tuple(strict_pack.get("completed_public_bindings", [])) != PREVIOUS_COMPLETED:
        fail("PREDECESSOR_COMPLETED", "strict-review completed set drift")
    if tuple(strict_pack.get("next_public_frontier", [])) != TARGET_BINDINGS:
        fail("PREDECESSOR_FRONTIER", "strict-review frontier drift")
    if strict_pack.get("retained_stage_obligations") is None:
        fail("PREDECESSOR_OBLIGATIONS", "strict-review stage obligations missing")
    if tuple(admission.get("blockers", [])) != ADMISSION_BLOCKERS:
        fail("ADMISSION_BLOCKERS", "real-run admission blockers drift")

    reference = admission.get("reference_condition")
    sampling = admission.get("sampling")
    if type(reference) is not dict or type(sampling) is not dict:
        fail("ADMISSION_SHAPE", "reference or sampling contract missing")
    if (
        reference.get("context_builder_sha256") != "UNSET_BLOCKS_REAL_RUN"
        or reference.get("status") != "NO_GO_EXACT_REFERENCE_BINDING"
        or reference.get("request", {}).get("exclude_kinds") != ["skill"]
        or reference.get("request", {}).get("limit") != 10
        or reference.get("request", {}).get("mode") != "hybrid"
    ):
        fail("REFERENCE_CONTRACT", "frozen reference contract drift")
    expected_sampling = {
        "primary_selection": "STRATIFIED_SRSWOR_BY_HMAC_SHA256_ASCENDING",
        "sample_weight": "N_h_DIV_n_h_APPLIED_ONCE_AT_CASE_GRAIN",
        "sampling_seed_derivation_message": (
            "domain_utf8_NUL_contract_sha256_ascii_NUL_trial_id_utf8_NUL_"
            "eligible_frame_sha256_ascii_NUL_external_entropy_sha256_ascii"
        ),
        "sampling_selection_domain": "agent-bridge/track-b/sample/v1",
        "sampling_selection_message": (
            "domain_utf8_NUL_frame_sha256_ascii_NUL_stratum_utf8_NUL_case_id_utf8"
        ),
        "reserve_replacement_after_condition_output_allowed": False,
        "sampling_receipt_must_precede_condition_output": True,
    }
    for key, expected in expected_sampling.items():
        if sampling.get(key) != expected:
            fail("SAMPLING_CONTRACT", f"sampling.{key} drift")
    for key in (
        "sampling_seed_derivation_sha256",
        "sampling_selection_algorithm_sha256",
        "sampling_receipt_writer_sha256",
    ):
        if sampling.get(key) != "UNSET_BLOCKS_REAL_RUN":
            fail("SAMPLING_LIVE_BINDING", f"sampling.{key} unexpectedly bound")

    properties = sampling_schema.get("properties")
    required = sampling_schema.get("required")
    if type(properties) is not dict or type(required) is not list:
        fail("SAMPLING_SCHEMA", "sampling receipt schema shape drift")
    if "sampling_seed_sha256" in properties or "sampling_seed_sha256" in required:
        fail("SAMPLING_SCHEMA_GAP", "seed commitment gap unexpectedly disappeared")
    if (
        properties.get("sampling_selection_domain", {}).get("const")
        != "agent-bridge/track-b/sample/v1"
        or properties.get("sampling_selection_message", {}).get("const")
        != "domain_utf8_NUL_frame_sha256_ascii_NUL_stratum_utf8_NUL_case_id_utf8"
        or properties.get("receipt_precedes_first_condition_output", {}).get("const")
        is not True
    ):
        fail("SAMPLING_SCHEMA", "sampling receipt frozen constants drift")


def validate_manifest_value(
    root: Path,
    manifest: dict[str, Any],
    fixture_raw: bytes,
    graph: dict[str, Any],
    ledger: dict[str, Any],
    admission: dict[str, Any],
    strict_pack: dict[str, Any],
) -> None:
    exact_keys(
        manifest,
        {
            "artifact_bindings",
            "baseline_commit",
            "boundary",
            "canonical_serialization",
            "completed_public_bindings",
            "date",
            "decision",
            "evidence_sha256",
            "graph_sha256",
            "graph_source_commit",
            "next_public_frontier",
            "predecessor_strict_review_pack_sha256",
            "predecessor_strict_review_source_commit",
            "resource_caps",
            "retained_admission_blockers",
            "retained_stage_obligations",
            "schema",
            "semantics",
            "structural_blockers",
            "synthetic_fixture_path",
            "synthetic_fixture_sha256",
        },
        "pack manifest",
    )
    scalars = {
        "baseline_commit": BASELINE_COMMIT,
        "canonical_serialization": CANONICAL_SERIALIZATION,
        "date": "2026-07-14",
        "decision": DECISION,
        "graph_sha256": GRAPH_SHA256,
        "graph_source_commit": GRAPH_SOURCE_COMMIT,
        "predecessor_strict_review_pack_sha256": STRICT_PACK_SHA256,
        "predecessor_strict_review_source_commit": PREDECESSOR_SOURCE_COMMIT,
        "schema": PACK_SCHEMA,
        "synthetic_fixture_path": FIXTURE_PATH,
        "synthetic_fixture_sha256": FIXTURE_SHA256,
    }
    for key, expected in scalars.items():
        if manifest.get(key) != expected:
            fail("MANIFEST_SCALAR", f"manifest {key} drift")
    if sha256_bytes(fixture_raw) != FIXTURE_SHA256:
        fail("FIXTURE_HASH", "synthetic fixture byte hash drift")
    structures = {
        "artifact_bindings": ARTIFACT_BINDINGS,
        "boundary": BOUNDARY,
        "completed_public_bindings": list(COMPLETED_PUBLIC_BINDINGS),
        "evidence_sha256": EXPECTED_EVIDENCE,
        "next_public_frontier": list(NEXT_PUBLIC_FRONTIER),
        "resource_caps": RESOURCE_CAPS,
        "retained_admission_blockers": list(ADMISSION_BLOCKERS),
        "retained_stage_obligations": strict_pack["retained_stage_obligations"],
        "semantics": SEMANTICS,
        "structural_blockers": list(STRUCTURAL_BLOCKERS),
    }
    for key, expected in structures.items():
        if manifest.get(key) != expected:
            fail(f"MANIFEST_{key.upper()}", f"manifest {key} drift")
    for path, expected in EXPECTED_EVIDENCE.items():
        if sha256_bytes(read_bytes(root, path)) != expected:
            fail("EVIDENCE_HASH", f"evidence byte hash drift: {path}")
    for binding in ARTIFACT_BINDINGS:
        if sha256_bytes(read_bytes(root, binding["repo_path"])) != binding["sha256"]:
            fail("ARTIFACT_HASH", f"artifact byte hash drift: {binding['repo_path']}")
    validate_graph_and_ledger(graph, ledger)
    if tuple(admission.get("blockers", [])) != tuple(manifest["retained_admission_blockers"]):
        fail("ADMISSION_JOIN", "manifest admission blockers do not join admission")


def evaluate_fixture(
    fixture: Any,
    reference_module: types.ModuleType,
    seed_module: types.ModuleType,
    selection_module: types.ModuleType,
) -> dict[str, Any]:
    if type(fixture) is not dict:
        fail("FIXTURE_TYPE", "synthetic fixture must be an object")
    exact_keys(
        fixture,
        {
            "boundary",
            "fixture_only",
            "real_runtime_authorized",
            "reference",
            "schema",
            "seed",
            "selection",
        },
        "synthetic fixture",
    )
    if fixture["schema"] != FIXTURE_SCHEMA:
        fail("FIXTURE_SCHEMA", "synthetic fixture schema drift")
    if fixture["fixture_only"] is not True or fixture["real_runtime_authorized"] is not False:
        fail("FIXTURE_BOUNDARY", "synthetic-only fixture boundary drift")
    if fixture["boundary"] != FIXTURE_BOUNDARY:
        fail("FIXTURE_BOUNDARY", "synthetic fixture authority boundary drift")

    reference = fixture["reference"]
    seed = fixture["seed"]
    selection = fixture["selection"]
    if type(reference) is not dict or type(seed) is not dict or type(selection) is not dict:
        fail("FIXTURE_SECTION", "fixture algorithm sections must be objects")
    exact_keys(reference, {"case_id", "expected", "hits", "max_context_bytes"}, "reference")
    exact_keys(
        seed,
        {
            "expected_public_result",
            "expected_seed_hex",
            "request",
            "synthetic_seed_disclosure_allowed",
        },
        "seed",
    )
    exact_keys(selection, {"expected_result", "request"}, "selection")
    if seed["synthetic_seed_disclosure_allowed"] is not True:
        fail("FIXTURE_SEED_BOUNDARY", "synthetic seed disclosure marker must be true")

    try:
        reference_result = reference_module.build_reference_context(
            reference["case_id"], reference["hits"], reference["max_context_bytes"]
        )
    except Exception as exc:
        fail("REFERENCE_VECTOR", f"reference vector rejected: {exc}")
    expected_reference = reference["expected"]
    for key in (
        "context_bytes",
        "context_json",
        "context_sha256",
        "hit_count",
        "input_utf8_bytes",
    ):
        if reference_result.get(key) != expected_reference.get(key):
            fail("REFERENCE_EXPECTED", f"reference expected {key} drift")
    projected = json.loads(reference_result["context_json"])
    if [row["key"] for row in projected] != expected_reference["ordered_keys"]:
        fail("REFERENCE_ORDER", "reference projected key order drift")
    reference_reversed = reference_module.build_reference_context(
        reference["case_id"], list(reversed(reference["hits"])), reference["max_context_bytes"]
    )
    if reference_reversed != reference_result:
        fail("REFERENCE_INVARIANCE", "reference input list order changes output")
    if (
        reference_result["mutable_access_telemetry_included"] is not False
        or reference_result["truncation_applied"] is not False
        or reference_result["runtime_configuration_verified"] is not False
        or reference_result["runtime_context_receipt_created"] is not False
        or reference_result["context_json_public_diagnostic_allowed"] is not False
    ):
        fail("REFERENCE_AUTHORITY", "reference result overclaims authority")

    try:
        seed_result = seed_module.derive_sampling_seed(seed["request"])
    except Exception as exc:
        fail("SEED_VECTOR", f"seed vector rejected: {exc}")
    if seed_result.seed_bytes.hex() != seed["expected_seed_hex"]:
        fail("SEED_EXPECTED", "derived synthetic seed drift")
    if seed_result.public_result != seed["expected_public_result"]:
        fail("SEED_EXPECTED", "public seed derivation result drift")
    if (
        seed_result.public_result["derived_seed_directly_serialized"] is not False
        or seed_result.public_result["derived_seed_publicly_recomputable"] is not True
        or seed_result.public_result["seed_secrecy_claimed"] is not False
    ):
        fail("SEED_AUTHORITY", "public seed reproducibility boundary drift")
    public_derivation_message = b"\0".join(
        (
            seed_result.public_result["seed_derivation_domain"].encode("utf-8"),
            seed_result.public_result["contract_sha256"].encode("ascii"),
            seed_result.public_result["trial_id"].encode("utf-8"),
            seed_result.public_result["eligible_frame_manifest_sha256"].encode(
                "ascii"
            ),
            seed_result.public_result["external_entropy_sha256"].encode("ascii"),
        )
    )
    publicly_recomputed_seed = hashlib.sha256(public_derivation_message).digest()
    if publicly_recomputed_seed != seed_result.seed_bytes:
        fail("SEED_PUBLIC_RECOMPUTE", "public bindings do not reproduce the seed")
    if (
        hashlib.sha256(publicly_recomputed_seed).hexdigest()
        != seed_result.public_result["sampling_seed_sha256"]
    ):
        fail("SEED_COMMITMENT", "publicly recomputed seed does not match commitment")
    public_seed_bytes = canonical_pretty_bytes(seed_result.public_result)
    if seed["expected_seed_hex"].encode("ascii") in public_seed_bytes:
        fail("SEED_DIRECT_SERIALIZATION", "public result directly serializes seed bytes")
    if seed["expected_seed_hex"] in repr(seed_result):
        fail("SEED_REPR_SERIALIZATION", "seed dataclass repr directly serializes seed")

    try:
        selection_result = selection_module.select_stratified_cases(
            selection["request"], seed_result.seed_bytes
        )
    except Exception as exc:
        fail("SELECTION_VECTOR", f"selection vector rejected: {exc}")
    if selection_result != selection["expected_result"]:
        fail("SELECTION_EXPECTED", "selection known-answer result drift")
    committed_selection = copy.deepcopy(selection_result)
    selection_commitment = committed_selection.pop("selection_commitment_sha256")
    if hashlib.sha256(canonical_pretty_bytes(committed_selection)).hexdigest() != selection_commitment:
        fail("SELECTION_COMMITMENT", "selection commitment omits result-envelope fields")
    permuted_request = copy.deepcopy(selection["request"])
    permuted_request["cases"].reverse()
    permuted_request["strata_allocations"].reverse()
    if (
        selection_module.select_stratified_cases(permuted_request, seed_result.seed_bytes)
        != selection_result
    ):
        fail("SELECTION_INVARIANCE", "selection input order changes output")
    selected_ids = [row["case_id"] for row in selection_result["selected_cases"]]
    reserve_ids = [row["case_id"] for row in selection_result["reserve_cases"]]
    frame_ids = [row["case_id"] for row in selection["request"]["cases"]]
    if set(selected_ids) & set(reserve_ids) or set(selected_ids) | set(reserve_ids) != set(frame_ids):
        fail("SELECTION_PARTITION", "selected and reserve do not partition the frame")
    if [row["case_id"] for row in selection_result["case_inclusion_probabilities"]] != selected_ids:
        fail("SELECTION_JOIN", "probability rows do not exactly join selected cases")
    if [row["case_id"] for row in selection_result["case_sampling_weights"]] != selected_ids:
        fail("SELECTION_JOIN", "weight rows do not exactly join selected cases")
    for probability, weight in zip(
        selection_result["case_inclusion_probabilities"],
        selection_result["case_sampling_weights"],
        strict=True,
    ):
        if (
            math.gcd(probability["numerator"], probability["denominator"]) != 1
            or math.gcd(weight["numerator"], weight["denominator"]) != 1
            or probability["numerator"] * weight["numerator"]
            != probability["denominator"] * weight["denominator"]
        ):
            fail("SELECTION_RATIONAL", "probability/weight rows are not reduced reciprocals")
    if (
        selection_result["weights_applied"] is not False
        or selection_result["sampling_receipt_created"] is not False
        or selection_result["condition_output_authorized"] is not False
        or selection_result["eligible_frame_bytes_verified"] is not False
        or selection_result["modulo_reduction_used"] is not False
    ):
        fail("SELECTION_AUTHORITY", "selection result overclaims authority")

    # Independent public known-answer controls, separate from the fixture's
    # a/b/c bindings.
    empty = reference_module.build_reference_context(
        "case_ffffffffffffffffffffffffffffffff", [], 2
    )
    if (
        empty["context_json"] != "[]"
        or empty["context_bytes"] != 2
        or empty["context_sha256"]
        != "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
    ):
        fail("REFERENCE_EMPTY_KAT", "empty-context known answer drift")
    independent_seed = seed_module.derive_sampling_seed(
        {
            "schema": seed_module.REQUEST_SCHEMA,
            "contract_sha256": "00" * 32,
            "trial_id": "trial_v0",
            "eligible_frame_manifest_sha256": "11" * 32,
            "external_entropy_sha256": "22" * 32,
        }
    )
    if (
        independent_seed.seed_bytes.hex()
        != "687970671f77da52f4ebd4a23f4b4a1bc8805a39df666d784f514ee0c7104870"
        or independent_seed.public_result["sampling_seed_sha256"]
        != "400cadc7bd5b802c1762f55a04f69622dee191bc65f7018aef0b03e938570d1d"
    ):
        fail("SEED_INDEPENDENT_KAT", "independent seed known answer drift")

    return {
        "reference": reference_result,
        "seed_public": seed_result.public_result,
        "seed_bytes": seed_result.seed_bytes,
        "selection": selection_result,
        "selected_count": len(selected_ids),
        "reserve_count": len(reserve_ids),
        "stratum_count": len(selection_result["strata"]),
    }


def load_inputs(root: Path) -> dict[str, Any]:
    paths = [
        MANIFEST_PATH,
        FIXTURE_PATH,
        *EXPECTED_EVIDENCE,
        REFERENCE_PATH,
        SEED_PATH,
        SELECTION_PATH,
    ]
    total = 0
    raw_by_path: dict[str, bytes] = {}
    for path in paths:
        raw = read_bytes(root, path)
        total += len(raw)
        if total > MAX_TOTAL_INPUT_BYTES:
            fail("TOTAL_INPUT_SIZE", "pack validation input exceeds 64 MiB")
        raw_by_path[path] = raw
    manifest = parse_canonical_json(raw_by_path[MANIFEST_PATH], MANIFEST_PATH)
    fixture = parse_canonical_json(raw_by_path[FIXTURE_PATH], FIXTURE_PATH)
    parsed = {
        path: parse_canonical_json(raw_by_path[path], path)
        for path in (GRAPH_PATH, LEDGER_PATH, ADMISSION_PATH, STRICT_PACK_PATH, SAMPLING_SCHEMA_PATH)
    }
    modules = {
        "reference": load_module(root, "track_b_reference_context_v0", REFERENCE_PATH, REFERENCE_SHA256),
        "seed": load_module(root, "track_b_sampling_seed_v0", SEED_PATH, SEED_SHA256),
        "selection": load_module(root, "track_b_sampling_selection_v0", SELECTION_PATH, SELECTION_SHA256),
    }
    validate_frozen_contracts(
        parsed[ADMISSION_PATH], parsed[STRICT_PACK_PATH], parsed[SAMPLING_SCHEMA_PATH]
    )
    validate_manifest_value(
        root,
        manifest,
        raw_by_path[FIXTURE_PATH],
        parsed[GRAPH_PATH],
        parsed[LEDGER_PATH],
        parsed[ADMISSION_PATH],
        parsed[STRICT_PACK_PATH],
    )
    metrics = evaluate_fixture(
        fixture, modules["reference"], modules["seed"], modules["selection"]
    )
    return {
        "manifest": manifest,
        "manifest_raw": raw_by_path[MANIFEST_PATH],
        "fixture": fixture,
        "fixture_raw": raw_by_path[FIXTURE_PATH],
        "parsed": parsed,
        "modules": modules,
        "metrics": metrics,
        "total_input_bytes": total,
    }


def receipt_rows(inputs: dict[str, Any]) -> list[tuple[str, Any]]:
    metrics = inputs["metrics"]
    reference = metrics["reference"]
    seed = metrics["seed_public"]
    selection = metrics["selection"]
    return [
        ("schema", PACK_SCHEMA),
        ("decision", DECISION),
        ("baseline_commit", BASELINE_COMMIT),
        ("manifest_sha256", sha256_bytes(inputs["manifest_raw"])),
        ("synthetic_fixture_sha256", FIXTURE_SHA256),
        ("graph_sha256", GRAPH_SHA256),
        ("live_ledger_sha256", LEDGER_SHA256),
        ("real_run_admission_sha256", ADMISSION_SHA256),
        ("predecessor_strict_review_pack_sha256", STRICT_PACK_SHA256),
        ("sampling_receipt_schema_sha256", SAMPLING_SCHEMA_SHA256),
        ("rust_s0_library_sha256", S0_LIB_SHA256),
        ("reference_context_builder_sha256", REFERENCE_SHA256),
        ("sampling_seed_derivation_sha256", SEED_SHA256),
        ("sampling_selection_algorithm_sha256", SELECTION_SHA256),
        ("synthetic_total_input_bytes", inputs["total_input_bytes"]),
        ("reference_status", reference["status"]),
        ("reference_case_id", reference["case_id"]),
        ("reference_context_sha256", reference["context_sha256"]),
        ("reference_context_bytes", reference["context_bytes"]),
        ("reference_hit_count", reference["hit_count"]),
        ("reference_input_utf8_bytes", reference["input_utf8_bytes"]),
        ("reference_input_order_invariant", reference["input_order_invariant"]),
        ("reference_mutable_access_telemetry_included", False),
        ("reference_truncation_applied", False),
        ("reference_runtime_configuration_verified", False),
        ("reference_runtime_context_receipt_created", False),
        ("seed_status", seed["status"]),
        ("seed_derivation_domain", seed["seed_derivation_domain"]),
        ("seed_derivation_message_profile", seed["seed_derivation_message_profile"]),
        ("synthetic_sampling_seed_sha256", seed["sampling_seed_sha256"]),
        ("seed_derived_seed_directly_serialized", seed["derived_seed_directly_serialized"]),
        ("seed_publicly_recomputable", seed["derived_seed_publicly_recomputable"]),
        ("seed_secrecy_claimed", seed["seed_secrecy_claimed"]),
        ("seed_raw_entropy_consumed", False),
        ("seed_anti_shopping_order_verified", False),
        ("seed_entropy_custody_verified", False),
        ("seed_o_excl_sampling_receipt_created", False),
        ("selection_status", selection["status"]),
        ("selection_domain", selection["sampling_selection_domain"]),
        ("selection_message", selection["sampling_selection_message"]),
        ("selection_commitment_sha256", selection["selection_commitment_sha256"]),
        ("selection_selected_case_count", metrics["selected_count"]),
        ("selection_reserve_case_count", metrics["reserve_count"]),
        ("selection_stratum_count", metrics["stratum_count"]),
        ("selection_input_order_invariant", True),
        ("selection_full_width_hmac_ordering", True),
        ("selection_modulo_reduction_used", False),
        ("selection_weights_applied", False),
        ("selection_eligible_frame_bytes_verified", False),
        ("selection_sampling_receipt_created", False),
        ("selection_condition_output_authorized", False),
        ("completed_public_binding_count", len(COMPLETED_PUBLIC_BINDINGS)),
        ("next_public_frontier_count", len(NEXT_PUBLIC_FRONTIER)),
        ("next_public_frontier", NEXT_PUBLIC_FRONTIER[0]),
        ("retained_stage_obligation_count", len(inputs["manifest"]["retained_stage_obligations"])),
        ("retained_admission_blocker_count", len(ADMISSION_BLOCKERS)),
        ("structural_blocker_count", len(STRUCTURAL_BLOCKERS)),
        ("source_artifact_count", 3),
        ("condition_ids_or_mapping_emitted", False),
        ("opaque_answer_ids_emitted", False),
        ("reviewer_visible_sampling_weights_emitted", False),
        ("reviewer_packet_created", False),
        ("runtime_instance_validated", False),
        ("live_binding_satisfied_count", 0),
        ("real_run_admitted", False),
        ("scoring_authorized", False),
        ("unblinding_authorized", False),
        ("side_effects_unlocked", "NONE"),
    ]


def render_receipt(inputs: dict[str, Any]) -> str:
    def scalar(value: Any) -> str:
        if value is True:
            return "true"
        if value is False:
            return "false"
        return str(value)

    raw = "".join(f"{key}\t{scalar(value)}\n" for key, value in receipt_rows(inputs))
    encoded = raw.encode("utf-8")
    if len(encoded) > MAX_OUTPUT_BYTES:
        fail("OUTPUT_SIZE", "public diagnostic exceeds its byte cap")
    forbidden = [
        inputs["fixture"]["seed"]["expected_seed_hex"],
        "memory_alpha",
        "第一条：确定性上下文",
        "case_00000000000000000000000000000002",
        "case_00000000000000000000000000000003",
        "case_00000000000000000000000000000001",
        "case_00000000000000000000000000000004",
        "case_00000000000000000000000000000005",
        "case_00000000000000000000000000000006",
        "ans_",
        "cond_",
    ]
    for token in forbidden:
        if token in raw:
            fail("PUBLIC_DIAGNOSTIC_LEAK", f"public diagnostic exposes forbidden token {token!r}")
    return raw


def expect_code(
    name: str,
    callback: Callable[[], Any],
    error_type: type[BaseException],
    expected_code: str,
) -> None:
    try:
        callback()
    except error_type as exc:
        if getattr(exc, "code", None) != expected_code:
            fail(
                "SELF_TEST_WRONG_ERROR",
                f"{name} expected {expected_code}, got {getattr(exc, 'code', None)}",
            )
        return
    except Exception as exc:
        fail("SELF_TEST_EXCEPTION", f"{name} raised uncontrolled {type(exc).__name__}: {exc}")
    fail("SELF_TEST_ACCEPTED", f"{name} mutation was accepted")


def run_self_test(inputs: dict[str, Any]) -> str:
    fixture = inputs["fixture"]
    manifest = inputs["manifest"]
    modules = inputs["modules"]
    reference = modules["reference"]
    seed = modules["seed"]
    selection = modules["selection"]
    counts = {
        "json_mutations_rejected": 0,
        "context_mutations_rejected": 0,
        "seed_mutations_rejected": 0,
        "selection_mutations_rejected": 0,
        "fixture_mutations_rejected": 0,
        "manifest_mutations_rejected": 0,
        "positive_controls_accepted": 0,
    }

    json_cases = [
        ("duplicate", b'{"schema":"x","schema":"x"}\n', "JSON_DUPLICATE_KEY"),
        ("nan", b'{"value":NaN}\n', "JSON_CONSTANT"),
        ("bom", b'\xef\xbb\xbf{"value":1}\n', "JSON_PARSE"),
        ("invalid-utf8", b'{"value":"\xff"}\n', "JSON_UTF8"),
        ("compact", b'{"value":1}\n', "JSON_CANONICAL"),
        ("root", b'[]\n', "JSON_ROOT"),
    ]
    for name, raw, code in json_cases:
        expect_code(name, lambda raw=raw: parse_canonical_json(raw, name), PackError, code)
        counts["json_mutations_rejected"] += 1

    base_hits = fixture["reference"]["hits"]
    case_id = fixture["reference"]["case_id"]
    budget = fixture["reference"]["max_context_bytes"]

    def context_case(name: str, mutate: Callable[[list[Any]], None], code: str) -> None:
        rows = copy.deepcopy(base_hits)
        mutate(rows)
        expect_code(
            name,
            lambda: reference.build_reference_context(case_id, rows, budget),
            reference.ReferenceContextError,
            code,
        )
        counts["context_mutations_rejected"] += 1

    context_case("telemetry-extra", lambda x: x[0].__setitem__("score", 1.0), "OBJECT_KEYS")
    context_case("rank-duplicate", lambda x: x[0].__setitem__("rank", 1), "RANK_DUPLICATE")
    context_case("rank-bool", lambda x: x[0].__setitem__("rank", True), "RANK")
    context_case("rank-gap", lambda x: x[0].__setitem__("rank", 3), "RANK_CONTIGUITY")
    context_case("key-duplicate", lambda x: x[0].__setitem__("key", x[1]["key"]), "KEY_DUPLICATE")
    context_case("skill", lambda x: x[0].__setitem__("kind", "skill"), "KIND_EXCLUDED")
    context_case("archived", lambda x: x[0].__setitem__("status", "archived"), "STATUS")
    context_case("timestamp-bool", lambda x: x[0].__setitem__("created_at", True), "TIMESTAMP")
    context_case("too-many-tags", lambda x: x[0].__setitem__("tags", ["x"] * 1025), "ARRAY_BOUND")
    context_case(
        "unpaired-surrogate",
        lambda x: x[0].__setitem__("content", "\ud800"),
        "STRING_UTF8",
    )
    expect_code(
        "bad-case",
        lambda: reference.build_reference_context("case_bad", base_hits, budget),
        reference.ReferenceContextError,
        "CASE_ID",
    )
    counts["context_mutations_rejected"] += 1
    expect_code(
        "bad-budget",
        lambda: reference.build_reference_context(case_id, base_hits, 1),
        reference.ReferenceContextError,
        "CONTEXT_BUDGET",
    )
    counts["context_mutations_rejected"] += 1
    expect_code(
        "complete-page-over-budget",
        lambda: reference.build_reference_context(case_id, base_hits, 549),
        reference.ReferenceContextError,
        "CONTEXT_BUDGET_EXCEEDED",
    )
    counts["context_mutations_rejected"] += 1
    expansion_rows = [copy.deepcopy(base_hits[1])]
    expansion_rows[0]["content"] = "\0" * reference.MAX_CONTENT_BYTES
    original_compact_json = reference._compact_json
    try:
        reference._compact_json = lambda _value: (_ for _ in ()).throw(
            AssertionError("serializer called before escaped-size rejection")
        )
        expect_code(
            "escaped-output-preflight",
            lambda: reference.build_reference_context(
                case_id, expansion_rows, reference.MAX_CONTEXT_BYTES
            ),
            reference.ReferenceContextError,
            "CONTEXT_BUDGET_EXCEEDED",
        )
        counts["context_mutations_rejected"] += 1
    finally:
        reference._compact_json = original_compact_json
    oversized_rows = []
    shared_content = "x" * reference.MAX_CONTENT_BYTES
    for index in range(9):
        row = copy.deepcopy(base_hits[1])
        row["rank"] = index + 1
        row["key"] = f"memory_{index}"
        row["content"] = shared_content
        oversized_rows.append(row)
    expect_code(
        "input-preflight",
        lambda: reference.build_reference_context(case_id, oversized_rows, reference.MAX_CONTEXT_BYTES),
        reference.ReferenceContextError,
        "INPUT_BYTES",
    )
    counts["context_mutations_rejected"] += 1
    forty_one = []
    for index in range(41):
        row = copy.deepcopy(base_hits[1])
        row["rank"] = min(index + 1, 40)
        row["key"] = f"memory_{index}"
        forty_one.append(row)
    expect_code(
        "hit-cap",
        lambda: reference.build_reference_context(case_id, forty_one, budget),
        reference.ReferenceContextError,
        "HIT_COUNT",
    )
    counts["context_mutations_rejected"] += 1

    seed_request = fixture["seed"]["request"]

    def seed_case(name: str, mutate: Callable[[dict[str, Any]], None], code: str) -> None:
        request = copy.deepcopy(seed_request)
        mutate(request)
        expect_code(
            name,
            lambda: seed.derive_sampling_seed(request),
            seed.SamplingSeedError,
            code,
        )
        counts["seed_mutations_rejected"] += 1

    seed_case("seed-extra", lambda x: x.__setitem__("condition_id", "cond_x"), "REQUEST_KEYS")
    seed_case("seed-schema", lambda x: x.__setitem__("schema", "wrong"), "REQUEST_SCHEMA")
    seed_case("seed-contract-case", lambda x: x.__setitem__("contract_sha256", "A" * 64), "SHA256")
    seed_case("seed-frame-short", lambda x: x.__setitem__("eligible_frame_manifest_sha256", "b" * 63), "SHA256")
    seed_case("seed-trial-nul", lambda x: x.__setitem__("trial_id", "trial\x00x"), "LABEL")
    seed_case("seed-entropy", lambda x: x.__setitem__("external_entropy_sha256", "z" * 64), "SHA256")

    seed_base = seed.derive_sampling_seed(seed_request).seed_bytes
    for field in (
        "contract_sha256",
        "eligible_frame_manifest_sha256",
        "external_entropy_sha256",
        "trial_id",
    ):
        changed = copy.deepcopy(seed_request)
        if field == "trial_id":
            changed[field] = "public_synthetic_track_b_context_sampling_v1"
        else:
            changed[field] = ("d" if changed[field][0] != "d" else "e") * 64
        if seed.derive_sampling_seed(changed).seed_bytes == seed_base:
            fail("SEED_SENSITIVITY", f"seed does not bind {field}")
        counts["positive_controls_accepted"] += 1

    selection_request = fixture["selection"]["request"]

    def selection_case(
        name: str,
        mutate: Callable[[dict[str, Any]], None],
        code: str,
        key: bytes = seed_base,
    ) -> None:
        request = copy.deepcopy(selection_request)
        mutate(request)
        expect_code(
            name,
            lambda: selection.select_stratified_cases(request, key),
            selection.SamplingSelectionError,
            code,
        )
        counts["selection_mutations_rejected"] += 1

    selection_case("selection-extra", lambda x: x.__setitem__("condition_map", {}), "REQUEST_KEYS")
    selection_case("selection-schema", lambda x: x.__setitem__("schema", "wrong"), "REQUEST_SCHEMA")
    selection_case("selection-frame", lambda x: x.__setitem__("eligible_frame_manifest_sha256", "B" * 64), "IDENTIFIER")
    selection_case("selection-case-duplicate", lambda x: x["cases"].append(copy.deepcopy(x["cases"][0])), "CASE_DUPLICATE")
    selection_case("selection-case-id", lambda x: x["cases"][0].__setitem__("case_id", "case_bad"), "IDENTIFIER")
    selection_case("selection-allocation-missing", lambda x: x["strata_allocations"].pop(), "STRATUM_COVERAGE")
    selection_case("selection-allocation-duplicate", lambda x: x["strata_allocations"].append(copy.deepcopy(x["strata_allocations"][0])), "ALLOCATION_DUPLICATE")
    selection_case("selection-zero", lambda x: x["strata_allocations"][0].__setitem__("sample_size", 0), "SAMPLE_SIZE")
    selection_case("selection-bool", lambda x: x["strata_allocations"][0].__setitem__("sample_size", True), "SAMPLE_SIZE")
    selection_case("selection-over", lambda x: x["strata_allocations"][0].__setitem__("sample_size", 4), "SAMPLE_SIZE")
    selection_case("selection-empty", lambda x: x.__setitem__("cases", []), "CASE_COUNT")
    expect_code(
        "selection-seed-length",
        lambda: selection.select_stratified_cases(selection_request, b"x" * 31),
        selection.SamplingSelectionError,
        "SEED",
    )
    counts["selection_mutations_rejected"] += 1
    expect_code(
        "selection-seed-type",
        lambda: selection.select_stratified_cases(selection_request, bytearray(seed_base)),
        selection.SamplingSelectionError,
        "SEED",
    )
    counts["selection_mutations_rejected"] += 1
    original_key = selection._selection_key
    try:
        selection._selection_key = lambda *_args: b"\x00" * 32
        expect_code(
            "selection-collision",
            lambda: selection.select_stratified_cases(selection_request, seed_base),
            selection.SamplingSelectionError,
            "HMAC_COLLISION",
        )
        counts["selection_mutations_rejected"] += 1
    finally:
        selection._selection_key = original_key

    base_selection = selection.select_stratified_cases(selection_request, seed_base)
    different_seed = bytes([seed_base[0] ^ 1]) + seed_base[1:]
    alternate_selection = selection.select_stratified_cases(selection_request, different_seed)
    if (
        base_selection["sampling_seed_sha256"] == alternate_selection["sampling_seed_sha256"]
        or base_selection["selection_commitment_sha256"]
        == alternate_selection["selection_commitment_sha256"]
    ):
        fail("SELECTION_SEED_BINDING", "selection invocation commitment omits seed")
    counts["positive_controls_accepted"] += 1

    def fixture_case(name: str, mutate: Callable[[dict[str, Any]], None], code: str) -> None:
        value = copy.deepcopy(fixture)
        mutate(value)
        expect_code(
            name,
            lambda: evaluate_fixture(value, reference, seed, selection),
            PackError,
            code,
        )
        counts["fixture_mutations_rejected"] += 1

    fixture_case("fixture-schema", lambda x: x.__setitem__("schema", "wrong"), "FIXTURE_SCHEMA")
    fixture_case("fixture-real", lambda x: x.__setitem__("real_runtime_authorized", True), "FIXTURE_BOUNDARY")
    fixture_case("fixture-boundary", lambda x: x["boundary"].__setitem__("live_binding_satisfied", True), "FIXTURE_BOUNDARY")
    fixture_case("fixture-context", lambda x: x["reference"]["expected"].__setitem__("context_sha256", "0" * 64), "REFERENCE_EXPECTED")
    fixture_case("fixture-seed", lambda x: x["seed"].__setitem__("expected_seed_hex", "0" * 64), "SEED_EXPECTED")
    fixture_case("fixture-seed-public", lambda x: x["seed"]["expected_public_result"].__setitem__("condition_output_authorized", True), "SEED_EXPECTED")
    fixture_case("fixture-selection", lambda x: x["selection"]["expected_result"].__setitem__("weights_applied", True), "SELECTION_EXPECTED")

    # Manifest cases use explicit callbacks below because their stable codes
    # are intentionally grouped by structural field.
    manifest_specs: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
        ("baseline", lambda x: x.__setitem__("baseline_commit", "0" * 40), "MANIFEST_SCALAR"),
        ("artifact", lambda x: x["artifact_bindings"].pop(), "MANIFEST_ARTIFACT_BINDINGS"),
        ("boundary", lambda x: x["boundary"].__setitem__("real_run_admitted", True), "MANIFEST_BOUNDARY"),
        ("completed", lambda x: x["completed_public_bindings"].pop(), "MANIFEST_COMPLETED_PUBLIC_BINDINGS"),
        ("evidence", lambda x: x["evidence_sha256"].pop(S0_SOURCE_PATH), "MANIFEST_EVIDENCE_SHA256"),
        ("evidence-lib", lambda x: x["evidence_sha256"].pop(S0_LIB_PATH), "MANIFEST_EVIDENCE_SHA256"),
        ("frontier", lambda x: x["next_public_frontier"].append("x"), "MANIFEST_NEXT_PUBLIC_FRONTIER"),
        ("resource", lambda x: x["resource_caps"].__setitem__("max_cases", 1), "MANIFEST_RESOURCE_CAPS"),
        ("admission", lambda x: x["retained_admission_blockers"].pop(), "MANIFEST_RETAINED_ADMISSION_BLOCKERS"),
        ("obligation", lambda x: x["retained_stage_obligations"].pop(), "MANIFEST_RETAINED_STAGE_OBLIGATIONS"),
        ("semantics", lambda x: x["semantics"].__setitem__("selection_order", "wrong"), "MANIFEST_SEMANTICS"),
        ("blockers", lambda x: x["structural_blockers"].pop(), "MANIFEST_STRUCTURAL_BLOCKERS"),
        ("fixture-hash", lambda x: x.__setitem__("synthetic_fixture_sha256", "0" * 64), "MANIFEST_SCALAR"),
    ]
    for name, mutate, code in manifest_specs:
        value = copy.deepcopy(manifest)
        mutate(value)
        expect_code(
            f"manifest-{name}",
            lambda value=value: validate_manifest_value(
                Path(inputs["root"]),
                value,
                inputs["fixture_raw"],
                inputs["parsed"][GRAPH_PATH],
                inputs["parsed"][LEDGER_PATH],
                inputs["parsed"][ADMISSION_PATH],
                inputs["parsed"][STRICT_PACK_PATH],
            ),
            PackError,
            code,
        )
        counts["manifest_mutations_rejected"] += 1

    # Canonicalization-equivalence positive control: duplicate and permuted
    # tags/related keys intentionally normalize to the same Rust S0 bytes.
    normalized_a = reference.build_reference_context(case_id, base_hits, budget)
    normalized_b_hits = copy.deepcopy(base_hits)
    normalized_b_hits[0]["tags"] = ["alpha", "zeta", "zeta", "alpha"]
    normalized_b_hits[0]["related_keys"] = ["memory_a", "memory_z", "memory_z"]
    normalized_b = reference.build_reference_context(case_id, normalized_b_hits, budget)
    if normalized_a["context_json"] != normalized_b["context_json"]:
        fail("REFERENCE_NORMALIZATION", "normalization equivalence control drift")
    counts["positive_controls_accepted"] += 1

    rust_domain_hits = [copy.deepcopy(base_hits[1])]
    rust_domain_hits[0].update(
        {
            "created_at": reference.MIN_TIMESTAMP,
            "related_keys": [""],
            "scope": "",
            "superseded_by": "",
            "tags": ["", "z"],
            "trigger_pattern": "",
            "updated_at": reference.MAX_TIMESTAMP,
        }
    )
    rust_domain = reference.build_reference_context(case_id, rust_domain_hits, budget)
    if (
        '"tags":["","z"]' not in rust_domain["context_json"]
        or f'"created_at":{reference.MIN_TIMESTAMP}' not in rust_domain["context_json"]
        or '"scope":""' not in rust_domain["context_json"]
    ):
        fail("REFERENCE_RUST_DOMAIN", "accepted Rust S0 scalar domain drift")
    counts["positive_controls_accepted"] += 1

    total_rejected = sum(value for key, value in counts.items() if key.endswith("_rejected"))
    ordered = [
        "json_mutations_rejected",
        "context_mutations_rejected",
        "seed_mutations_rejected",
        "selection_mutations_rejected",
        "fixture_mutations_rejected",
        "manifest_mutations_rejected",
        "positive_controls_accepted",
    ]
    return (
        "SELF_TEST_OK\t"
        + "\t".join(f"{key}={counts[key]}" for key in ordered)
        + f"\ttotal_mutations_rejected={total_rejected}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    inputs = load_inputs(root)
    inputs["root"] = str(root)
    if args.self_test:
        sys.stdout.write(run_self_test(inputs))
    else:
        sys.stdout.write(render_receipt(inputs))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PackError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
