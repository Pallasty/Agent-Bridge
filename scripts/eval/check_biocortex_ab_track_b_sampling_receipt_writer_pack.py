#!/usr/bin/env python3
"""Purpose checker for the Track B sampling-receipt-writer source packet."""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import json
import os
import stat
import sys
import tempfile
import threading
import types
from pathlib import Path
from typing import Any, Callable


EVAL_DIR = Path(__file__).absolute().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import biocortex_ab_track_b_sampling_receipt_writer_v0 as writer
from biocortex_ab_track_b_sampling_seed_derivation_v0 import (
    REQUEST_SCHEMA as SEED_REQUEST_SCHEMA,
    derive_sampling_seed,
)
from biocortex_ab_track_b_sampling_selection_v0 import (
    REQUEST_SCHEMA as SELECTION_REQUEST_SCHEMA,
    select_stratified_cases,
)


BASELINE_COMMIT = "7819e61f5468bb84061e6cbe111c327f63dc63bf"
PREDECESSOR_SOURCE_COMMIT = "753c32c223ba04cc1b19fdf244a7036e8cfac3bf"
PREDECESSOR_MANIFEST_SHA256 = (
    "06f54d4079e09d7728effd242d9dbf0e35f4d050e0d7a9f6a5fc9a8202b9445f"
)
V0_SCHEMA_SHA256 = "9e73afee2f6366a241b155680b4f77341adeb7c4e341ab91b8d4b1499b5aacbd"
PROFILE_SHA256 = "a8972ad5e75b30634931fee84f08226e2660413b45cf9dfea948089d61160243"
V1_SCHEMA_SHA256 = "e418b58246eaf183b5624c7eb12299caeea933c83a07584faa915651b3cd48d4"
WRITER_SHA256 = "a8642d2b524183e060eb2f2c16d3a4bba4bca43c8e18b8524bc14738d4f6d975"
FIXTURE_SHA256 = "79bdb87f5fdaeb72423ff12002f4cf9a0deca2e9cd9b86e820321357a0641b8a"
MAP_SOURCE_SHA256 = "45f55cea933ee12df402fbb55d27ea7c6cd08ba8eef9d9868e4e491dd62a2cd2"
BLIND_MAP_SCHEMA_SHA256 = "ad40df50eec68fa192c79e6699a8d2da2a9c3925a387eaa7427f7e19f996d783"
ADMISSION_CHECKER_SHA256 = "b09b10243f195299dc226b5d8d2b484ec74f5eecd49bb487296c391f6f193b13"
FOUNDATIONAL_MANIFEST_SHA256 = "fbfbf5738dd81e0afe8dbc45b1e91a35e92382a1913006a9b2e5ded67c077f36"
IDENTITY_MANIFEST_SHA256 = "c1a6c5a6c83d61f92d35948432b139749d19d5828f68a7fc2473859bba21a7e9"
GRAPH_SHA256 = "8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af"
LEDGER_SHA256 = "764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341a"
ADMISSION_SHA256 = "1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e"
SEED_SHA256 = "4f51781ff707e89b4c09adffeafbdaacd75c7e1571d1a86e45d336aace888a3f"
SELECTION_SHA256 = "e327faf2ad73718dc33f68fdb66a89abf0ac84fbbf8d828ff79fa0e8b75772ec"

PROFILE_PATH = "docs/design/fixtures/biocortex-ab-track-b-sampling-contract-digest-profile-v0.json"
V1_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v1.json"
WRITER_PATH = "scripts/eval/biocortex_ab_track_b_sampling_receipt_writer_v0.py"
FIXTURE_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_sampling_receipt_writer_pack_synthetic_v0.json"
MANIFEST_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_sampling_receipt_writer_pack_v0.json"
V0_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json"
GRAPH_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
LEDGER_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
ADMISSION_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
PREDECESSOR_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_context_sampling_determinism_pack_v0.json"
SEED_PATH = "scripts/eval/biocortex_ab_track_b_sampling_seed_derivation_v0.py"
SELECTION_PATH = "scripts/eval/biocortex_ab_track_b_sampling_selection_v0.py"
MAP_SOURCE_PATH = "scripts/eval/biocortex_ab_track_b_map_bijection_v0.py"
BLIND_MAP_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json"
ADMISSION_CHECKER_PATH = "scripts/eval/check_biocortex_ab_track_b_admission.py"
FOUNDATIONAL_MANIFEST_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_foundational_schema_pack_v0.json"
IDENTITY_MANIFEST_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_v0.json"

EXPECTED_HASHES = {
    PROFILE_PATH: PROFILE_SHA256,
    V1_SCHEMA_PATH: V1_SCHEMA_SHA256,
    WRITER_PATH: WRITER_SHA256,
    FIXTURE_PATH: FIXTURE_SHA256,
    V0_SCHEMA_PATH: V0_SCHEMA_SHA256,
    GRAPH_PATH: GRAPH_SHA256,
    LEDGER_PATH: LEDGER_SHA256,
    ADMISSION_PATH: ADMISSION_SHA256,
    PREDECESSOR_PATH: PREDECESSOR_MANIFEST_SHA256,
    SEED_PATH: SEED_SHA256,
    SELECTION_PATH: SELECTION_SHA256,
    MAP_SOURCE_PATH: MAP_SOURCE_SHA256,
    BLIND_MAP_SCHEMA_PATH: BLIND_MAP_SCHEMA_SHA256,
    ADMISSION_CHECKER_PATH: ADMISSION_CHECKER_SHA256,
    FOUNDATIONAL_MANIFEST_PATH: FOUNDATIONAL_MANIFEST_SHA256,
    IDENTITY_MANIFEST_PATH: IDENTITY_MANIFEST_SHA256,
}

NEW_RECEIPT_BINDINGS = {
    "anti_shopping_order_verified",
    "condition_output_authorized",
    "contract_digest_profile_sha256",
    "external_entropy_sha256",
    "pre_output_timing_verified",
    "sampling_seed_sha256",
    "seed_derivation_domain",
    "seed_derivation_message_profile",
    "selection_commitment_sha256",
}
EXPECTED_WRITER_DEPENDENCIES = {
    "sampling.sampling_receipt_schema_sha256",
    "sampling.sampling_seed_derivation_sha256",
    "sampling.sampling_selection_algorithm_sha256",
}
EXPECTED_BLOCKERS = {
    "ACTIVE_ADMISSION_STILL_PINS_RECEIPT_V0",
    "FRAME_AND_ENTROPY_CUSTODY_SCHEMAS_UNBOUND",
    "MAP_BIJECTION_STILL_PINS_RECEIPT_V0",
    "OUTPUT_ADMISSION_GUARD_UNBOUND",
    "PYTHON_RUNTIME_AND_STDLIB_BINARY_PROVENANCE_UNBOUND",
    "SOURCE_WRITER_NOT_RUNTIME_PROVENANCE",
    "STRATA_ALLOCATION_PRE_ENTROPY_CUSTODY_UNBOUND",
}


class CheckError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def canonical_bytes(value: Any) -> bytes:
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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def protected_bytes(root: Path, relative: str) -> bytes:
    require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, f"unsafe path: {relative}")
    cursor = root
    for part in Path(relative).parts:
        cursor = cursor / part
        require(not cursor.is_symlink(), f"protected path contains symlink: {relative}")
    info = os.lstat(cursor)
    require(stat.S_ISREG(info.st_mode), f"protected path is not regular: {relative}")
    require(info.st_nlink == 1, f"protected path is hard-linked: {relative}")
    data = cursor.read_bytes()
    require(len(data) == info.st_size, f"protected path size changed: {relative}")
    return data


def canonical_json(root: Path, relative: str) -> dict[str, Any]:
    raw = protected_bytes(root, relative)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckError(f"invalid JSON {relative}: {exc}") from exc
    require(type(value) is dict, f"JSON root must be object: {relative}")
    require(canonical_bytes(value) == raw, f"JSON is not canonical pretty form: {relative}")
    return value


def verify_bound_files(root: Path) -> None:
    for path, expected in EXPECTED_HASHES.items():
        actual = sha256_bytes(protected_bytes(root, path))
        require(actual == expected, f"frozen file hash drift: {path}")


def validate_profile_and_schema(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    profile = canonical_json(root, PROFILE_PATH)
    v0 = canonical_json(root, V0_SCHEMA_PATH)
    v1 = canonical_json(root, V1_SCHEMA_PATH)
    require(profile["schema"] == "agent_bridge.biocortex_ab_track_b_sampling_contract_digest_profile.v0", "contract profile schema drift")
    require(profile["contract_core_schema"] == writer.CONTRACT_CORE_SCHEMA, "contract core schema drift")
    require(set(profile["required_fields"]) == writer.CONTRACT_CORE_FIELDS, "contract profile exact field set drift")
    require(set(profile["sha256_fields"]) == writer.CONTRACT_SHA_FIELDS, "contract profile SHA field set drift")
    require(profile["canonical_serialization"] == writer.CANONICAL_SERIALIZATION, "contract canonical profile drift")
    require(profile["limits"]["max_total_input_bytes"] == writer.MAX_TOTAL_INPUT_BYTES, "profile total-input cap drift")
    require(profile["limits"]["max_single_artifact_bytes"] == writer.MAX_SINGLE_ARTIFACT_BYTES, "profile artifact cap drift")
    require(profile["limits"]["max_receipt_bytes"] == writer.MAX_RECEIPT_BYTES, "profile receipt cap drift")
    require(profile["source_only_boundary"]["real_run_authorized"] is False, "profile authorizes real run")
    require(profile["source_only_boundary"]["policy_artifact_transitive_cycle_verified"] is False, "profile overclaims transitive cycle validation")
    require(profile["source_only_boundary"]["strata_allocation_pre_entropy_verified"] is False, "profile overclaims allocation timing")
    order = profile["dependency_order"]
    require(order.index("STRATA_ALLOCATION_MANIFEST_FROZEN") < order.index("EXTERNAL_ENTROPY_AND_CUSTODY_RECEIPT"), "allocation is not ordered before entropy")
    forbidden = set(profile["forbidden_dynamic_fields"])
    require({
        "case_inclusion_probabilities",
        "case_sampling_weights",
        "condition_output_authorized",
        "contract_sha256",
        "external_entropy_sha256",
        "reserve_cases",
        "sampling_receipt_sha256",
        "sampling_seed_entropy_receipt_sha256",
        "sampling_seed_sha256",
        "selected_cases",
        "selection_commitment_sha256",
        "strata",
    } <= forbidden, "contract dynamic-field denylist incomplete")

    v0_properties = set(v0["properties"])
    v1_properties = set(v1["properties"])
    require(v0["additionalProperties"] is False and v0["unevaluatedProperties"] is False, "v0 closed-world schema drift")
    require(not (NEW_RECEIPT_BINDINGS & v0_properties), "frozen v0 unexpectedly contains successor fields")
    require(v1["$id"] == "urn:agent-bridge:biocortex-ab:track-b:sampling-receipt:v1", "v1 schema id drift")
    require(v1["properties"]["schema"]["const"] == writer.RECEIPT_SCHEMA, "v1 instance schema drift")
    require(v1["additionalProperties"] is False and v1["unevaluatedProperties"] is False, "v1 is not closed world")
    require(set(v1["required"]) == v1_properties == writer.RECEIPT_FIELDS, "v1 required/property/writer fields differ")
    require(NEW_RECEIPT_BINDINGS <= v1_properties, "v1 successor binding set incomplete")
    require(v1["properties"]["condition_output_authorized"]["const"] is False, "v1 authorizes output")
    require(v1["properties"]["anti_shopping_order_verified"]["const"] is False, "v1 overclaims anti-shopping")
    require(v1["properties"]["pre_output_timing_verified"]["const"] is False, "v1 overclaims timing")
    for field, expected in (
        ("sampling_selection_domain", writer.SELECTION_DOMAIN),
        ("sampling_selection_message", writer.SELECTION_MESSAGE_PROFILE),
        ("seed_derivation_domain", writer.SEED_DOMAIN),
        ("seed_derivation_message_profile", writer.SEED_MESSAGE_PROFILE),
    ):
        require(v1["properties"][field]["const"] == expected, f"v1 const drift: {field}")
    require(v1["$defs"]["sha256"]["pattern"] == "^[0-9a-f]{64}$", "v1 SHA profile drift")
    require(v1["$defs"]["positiveInteger"]["maximum"] == writer.MAX_SAFE_INTEGER, "v1 integer cap drift")
    return profile, v0, v1


def validate_receipt_instance(receipt: Any, schema: dict[str, Any]) -> None:
    require(type(receipt) is dict and set(receipt) == set(schema["required"]), "receipt/schema field set mismatch")
    properties = schema["properties"]
    for field, definition in properties.items():
        if "const" in definition:
            require(receipt[field] == definition["const"], f"receipt const mismatch: {field}")
        if definition.get("$ref") == "#/$defs/sha256":
            require(type(receipt[field]) is str and writer.SHA_RE.fullmatch(receipt[field]) is not None, f"receipt SHA mismatch: {field}")
    require(type(receipt["trial_id"]) is str and writer.LABEL_RE.fullmatch(receipt["trial_id"]) is not None, "receipt trial label mismatch")
    require(type(receipt["created_at_utc"]) is str and writer.UTC_RE.fullmatch(receipt["created_at_utc"]) is not None, "receipt UTC shape mismatch")
    for field in ("case_inclusion_probabilities", "case_sampling_weights"):
        rows = receipt[field]
        require(type(rows) is list and 1 <= len(rows) <= writer.MAX_CASES, f"receipt row count mismatch: {field}")
        require(len({canonical_bytes(row) for row in rows}) == len(rows), f"receipt schema uniqueItems mismatch: {field}")
        for row in rows:
            require(type(row) is dict and set(row) == {"case_id", "denominator", "numerator"}, f"receipt rational row shape mismatch: {field}")
            require(type(row["case_id"]) is str and writer.CASE_RE.fullmatch(row["case_id"]) is not None, f"receipt case ID mismatch: {field}")
            for number in ("denominator", "numerator"):
                require(type(row[number]) is int and 1 <= row[number] <= writer.MAX_SAFE_INTEGER, f"receipt rational value mismatch: {field}.{number}")


def validate_graph_ledger_and_active_contract(
    root: Path,
) -> tuple[set[str], dict[str, dict[str, Any]], int, int]:
    graph = canonical_json(root, GRAPH_PATH)
    ledger = canonical_json(root, LEDGER_PATH)
    admission = canonical_json(root, ADMISSION_PATH)
    predecessor = canonical_json(root, PREDECESSOR_PATH)
    nodes = graph["nodes"]
    graph_by_path = {row["artifact_binding_path"]: row for row in nodes}
    require(len(graph_by_path) == len(nodes), "graph binding paths are not unique")
    writer_nodes = [row for row in nodes if row["artifact_binding_path"] == "sampling.sampling_receipt_writer_sha256"]
    require(len(writer_nodes) == 1, "writer graph node cardinality drift")
    node = writer_nodes[0]
    require(node["primary_readiness_class"] == "INDEPENDENT_PUBLIC", "writer readiness class drift")
    require(node["public_authoring_eligible"] is True and node["unlocks_side_effect"] is False, "writer graph authority drift")
    require(set(node["local_dependencies"]) == EXPECTED_WRITER_DEPENDENCIES, "writer graph dependencies drift")
    independent = {
        row["artifact_binding_path"]
        for row in nodes
        if row["primary_readiness_class"] == "INDEPENDENT_PUBLIC"
    }
    require(len(independent) == 13, "independent-public graph cardinality drift")
    require(len(predecessor["completed_public_bindings"]) == 12, "predecessor completed count drift")
    require(predecessor["next_public_frontier"] == ["sampling.sampling_receipt_writer_sha256"], "predecessor frontier drift")

    ledger_rows = ledger["bindings"]
    ledger_by_path = {row["binding_path"]: row for row in ledger_rows}
    require(len(ledger_by_path) == len(ledger_rows), "ledger binding paths are not unique")
    live_binding_count = sum(row["binding_satisfied"] is True for row in ledger_rows)
    require(live_binding_count == 0, "frozen ledger contains a live binding")
    for binding in (
        "sampling.sampling_receipt_schema_sha256",
        "sampling.sampling_receipt_writer_sha256",
        "sampling.sampling_seed_derivation_sha256",
        "sampling.sampling_selection_algorithm_sha256",
    ):
        row = ledger_by_path[binding]
        require(row["owner_class"] == "local_deterministic", f"ledger owner drift: {binding}")
        require(row["local_fill_rule"] == "EXACT_COMMITTED_ARTIFACT_ONLY", f"ledger fill rule drift: {binding}")
        require(row["binding_satisfied"] is False, f"source work falsely live-binds: {binding}")
    for binding in ("sampling.sampling_seed_sha256", "sampling.sampling_receipt_sha256"):
        row = ledger_by_path[binding]
        require(row["owner_class"] == "custodian_private", f"private owner drift: {binding}")
        require(row["local_fill_rule"] == "PROHIBITED_LOCAL_SYNTHESIS", f"private synthesis rule drift: {binding}")

    active = admission["sampling"]
    require(active["sampling_receipt_schema_sha256"] == "UNSET_BLOCKS_REAL_RUN", "active schema unexpectedly bound")
    required = set(active["sampling_receipt_required_bindings"])
    require("sampling_seed_sha256" not in required and "selection_commitment_sha256" not in required, "active v0 interface silently changed")
    require(admission["admission"]["real_run_admitted"] is False, "active contract admits a real run")
    map_source = protected_bytes(root, MAP_SOURCE_PATH).decode("utf-8")
    require(f'SAMPLING_SCHEMA_SHA256 = "{V0_SCHEMA_SHA256}"' in map_source, "map no longer pins exact v0 hash")
    require('SAMPLING_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_receipt.v0"' in map_source, "map no longer pins v0 instance schema")
    return independent, graph_by_path, len(ledger_by_path), live_binding_count


def request_bytes(request: dict[str, Any]) -> bytes:
    return canonical_bytes(request)


def validate_fixture(root: Path) -> tuple[dict[str, Any], writer.BuiltSamplingReceipt, writer.ReceiptWriteObservation]:
    fixture = canonical_json(root, FIXTURE_PATH)
    receipt_schema = canonical_json(root, V1_SCHEMA_PATH)
    require(fixture["schema"] == "agent_bridge.biocortex_ab_track_b_sampling_receipt_writer_pack_synthetic.v0", "fixture schema drift")
    require(fixture["fixture_only"] is True, "fixture-only marker missing")
    for key, value in fixture["boundary"].items():
        if key != "fixture_only":
            require(value is False, f"synthetic boundary overclaim: {key}")
    require(fixture["boundary"]["fixture_only"] is True, "fixture boundary marker drift")
    raw = request_bytes(fixture["request"])
    require(sha256_bytes(raw) == fixture["request_sha256"], "fixture request hash drift")
    require(fixture["source_hashes"] == {
        "contract_digest_profile_sha256": PROFILE_SHA256,
        "sampling_receipt_schema_sha256": V1_SCHEMA_SHA256,
        "sampling_receipt_writer_sha256": WRITER_SHA256,
        "sampling_seed_derivation_sha256": SEED_SHA256,
        "sampling_selection_algorithm_sha256": SELECTION_SHA256,
    }, "fixture source-hash set drift")
    built = writer.build_sampling_receipt(raw)
    expected = fixture["expected"]
    validate_receipt_instance(built.receipt, receipt_schema)
    require(built.receipt == expected["receipt"], "fixture receipt object drift")
    require(built.receipt_sha256 == expected["receipt_sha256"], "fixture receipt hash drift")
    require(len(built.canonical_bytes) == expected["receipt_bytes"], "fixture receipt byte count drift")
    require(built.selected_case_count == expected["selected_case_count"], "fixture selected count drift")
    require(built.reserve_case_count == expected["reserve_case_count"], "fixture reserve count drift")
    require(built.receipt["sampling_seed_sha256"] == expected["sampling_seed_sha256"], "fixture seed join drift")
    require(built.receipt["selection_commitment_sha256"] == expected["selection_commitment_sha256"], "fixture selection join drift")
    for expected_field, receipt_field in (
        ("contract_sha256", "contract_sha256"),
        ("eligible_frame_manifest_sha256", "eligible_frame_manifest_sha256"),
        ("strata_allocation_manifest_sha256", "strata_allocation_manifest_sha256"),
        ("sampling_seed_sha256", "sampling_seed_sha256"),
        ("selection_commitment_sha256", "selection_commitment_sha256"),
        ("selected_case_manifest_sha256", "selected_case_manifest_sha256"),
        ("reserve_manifest_sha256", "reserve_manifest_sha256"),
    ):
        require(expected[expected_field] == built.receipt[receipt_field], f"fixture top-level join drift: {expected_field}")

    with tempfile.TemporaryDirectory(prefix="track-b-receipt-positive-") as temp:
        os.chmod(temp, 0o700)
        directory_fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            observation = writer.write_sampling_receipt_o_excl(directory_fd, built)
            stored_path = Path(temp, writer.RECEIPT_BASENAME)
            stored = stored_path.read_bytes()
            require(stored == built.canonical_bytes, "stored receipt bytes drift")
            require(stat.S_IMODE(stored_path.stat().st_mode) == 0o400, "stored receipt final mode drift")
            try:
                writer.write_sampling_receipt_o_excl(directory_fd, built)
            except writer.SamplingReceiptError as exc:
                require(exc.code == "RECEIPT_EXISTS", "second write failed for wrong reason")
            else:
                raise CheckError("second write overwrote the sampling receipt")
        finally:
            os.close(directory_fd)
    observed = dataclasses.asdict(observation)
    for key, value in expected["write_observation"].items():
        require(observed[key] == value, f"write observation drift: {key}")
    require(observation.receipt_sha256 == built.receipt_sha256, "write observation hash drift")
    return fixture, built, observation


def validate_manifest(
    root: Path,
    fixture: dict[str, Any],
    independent: set[str],
    graph_by_path: dict[str, dict[str, Any]],
    live_binding_count: int,
) -> dict[str, Any]:
    manifest = canonical_json(root, MANIFEST_PATH)
    require(manifest["schema"] == "agent_bridge.biocortex_ab_track_b_sampling_receipt_writer_pack.v0", "manifest schema drift")
    require(manifest["baseline_commit"] == BASELINE_COMMIT, "manifest baseline drift")
    require(manifest["predecessor_context_sampling_source_commit"] == PREDECESSOR_SOURCE_COMMIT, "manifest predecessor source drift")
    require(manifest["predecessor_context_sampling_pack_sha256"] == PREDECESSOR_MANIFEST_SHA256, "manifest predecessor hash drift")
    require(manifest["decision"] == "SOURCE_SAMPLING_RECEIPT_WRITER_IMPLEMENTED_NOT_LIVE_BOUND", "manifest decision drift")
    completed_rows = manifest["completed_public_bindings"]
    completed = set(completed_rows)
    require(len(completed_rows) == len(completed), "manifest completed-public bindings repeat")
    require(completed == independent and len(independent) == 13, "manifest completed-public exact set drift")
    derived_frontier = sorted(
        path
        for path in independent - completed
        if set(graph_by_path[path]["local_dependencies"]) <= completed
    )
    require(manifest["next_public_frontier"] == derived_frontier == [], "manifest frontier is not graph-derived")
    require(set(manifest["retained_blockers"]) >= EXPECTED_BLOCKERS, "manifest retained blocker set incomplete")
    require(manifest["boundary"]["live_binding_satisfied_count"] == live_binding_count == 0, "manifest live-binding count differs from ledger")
    require(manifest["boundary"]["condition_output_authorized"] is False, "manifest authorizes output")
    require(manifest["boundary"]["pre_output_timing_verified"] is False, "manifest overclaims output timing")
    require(manifest["boundary"]["strata_allocation_pre_entropy_verified"] is False, "manifest overclaims allocation timing")
    require(manifest["boundary"]["real_run_admitted"] is False, "manifest admits real run")
    require(manifest["schema_revision"]["predecessor_sha256"] == V0_SCHEMA_SHA256, "manifest v0 revision hash drift")
    require(manifest["schema_revision"]["successor_sha256"] == V1_SCHEMA_SHA256, "manifest v1 revision hash drift")
    require(manifest["schema_revision"]["compatibility"] == "V0_REJECTED_BY_WRITER_V0", "manifest compatibility drift")
    require(manifest["synthetic_fixture_sha256"] == FIXTURE_SHA256, "manifest fixture hash drift")
    require(manifest["synthetic_fixture_sha256"] == sha256_bytes(canonical_bytes(fixture)), "manifest fixture bytes drift")
    artifacts = {row["binding_path"]: row for row in manifest["artifact_bindings"]}
    require(artifacts["sampling.sampling_receipt_schema_sha256"]["sha256"] == V1_SCHEMA_SHA256, "manifest v1 binding drift")
    require(artifacts["sampling.sampling_receipt_writer_sha256"]["sha256"] == WRITER_SHA256, "manifest writer binding drift")
    require(manifest["supporting_artifacts"][0]["sha256"] == PROFILE_SHA256, "manifest contract profile hash drift")
    require(manifest["resource_caps"]["max_total_input_bytes"] == writer.MAX_TOTAL_INPUT_BYTES, "manifest total-input cap drift")
    require(manifest["resource_caps"]["max_single_artifact_bytes"] == writer.MAX_SINGLE_ARTIFACT_BYTES, "manifest artifact cap drift")
    require(manifest["resource_caps"]["max_receipt_bytes"] == writer.MAX_RECEIPT_BYTES, "manifest receipt cap drift")
    receipt_grains = [row for row in manifest["data_quality_contract"]["grains"] if row["surface"] == "sampling_receipt"]
    require(len(receipt_grains) == 1 and receipt_grains[0]["grain"] == "ONE_EXCLUSIVE_CREATE_PER_CUSTODY_DIRECTORY_AND_SAMPLING_EVENT", "manifest receipt grain drift")
    return manifest


def normal_rows(root: Path) -> list[tuple[str, str]]:
    verify_bound_files(root)
    validate_profile_and_schema(root)
    independent, graph_by_path, ledger_binding_count, live_binding_count = validate_graph_ledger_and_active_contract(root)
    fixture, built, observation = validate_fixture(root)
    manifest = validate_manifest(root, fixture, independent, graph_by_path, live_binding_count)
    rows = [
        ("decision", manifest["decision"]),
        ("baseline_commit", BASELINE_COMMIT),
        ("predecessor_context_sampling_source_commit", PREDECESSOR_SOURCE_COMMIT),
        ("predecessor_context_sampling_pack_sha256", PREDECESSOR_MANIFEST_SHA256),
        ("contract_digest_profile_sha256", PROFILE_SHA256),
        ("sampling_receipt_schema_v0_sha256", V0_SCHEMA_SHA256),
        ("sampling_receipt_schema_v1_sha256", V1_SCHEMA_SHA256),
        ("sampling_receipt_writer_sha256", WRITER_SHA256),
        ("sampling_seed_derivation_sha256", SEED_SHA256),
        ("sampling_selection_algorithm_sha256", SELECTION_SHA256),
        ("artifact_dependency_graph_sha256", GRAPH_SHA256),
        ("live_binding_ledger_sha256", LEDGER_SHA256),
        ("real_run_admission_sha256", ADMISSION_SHA256),
        ("map_bijection_v0_source_sha256", MAP_SOURCE_SHA256),
        ("synthetic_fixture_sha256", FIXTURE_SHA256),
        ("synthetic_request_sha256", fixture["request_sha256"]),
        ("synthetic_contract_sha256", fixture["expected"]["contract_sha256"]),
        ("synthetic_frame_sha256", fixture["expected"]["eligible_frame_manifest_sha256"]),
        ("synthetic_allocation_sha256", fixture["expected"]["strata_allocation_manifest_sha256"]),
        ("synthetic_sampling_seed_sha256", fixture["expected"]["sampling_seed_sha256"]),
        ("synthetic_selection_commitment_sha256", fixture["expected"]["selection_commitment_sha256"]),
        ("synthetic_selected_manifest_sha256", fixture["expected"]["selected_case_manifest_sha256"]),
        ("synthetic_reserve_manifest_sha256", fixture["expected"]["reserve_manifest_sha256"]),
        ("synthetic_receipt_sha256", built.receipt_sha256),
        ("synthetic_receipt_bytes", str(len(built.canonical_bytes))),
        ("synthetic_selected_count", str(built.selected_case_count)),
        ("synthetic_reserve_count", str(built.reserve_case_count)),
        ("receipt_write_flags", observation.write_flags_profile),
        ("receipt_create_file_mode", observation.create_file_mode_octal),
        ("receipt_final_file_mode", observation.final_file_mode_octal),
        ("receipt_content_fsync", str(observation.content_fsync_completed).lower()),
        ("receipt_read_only_seal_fsync", str(observation.read_only_seal_fsync_completed).lower()),
        ("receipt_directory_fsync", str(observation.parent_directory_fsync_completed).lower()),
        ("receipt_reread_verified", str(observation.reread_identity_and_bytes_verified).lower()),
        ("write_evidence_scope", observation.evidence_scope),
        ("condition_output_authorized", "false"),
        ("pre_output_timing_verified", "false"),
        ("trusted_clock_verified", "false"),
        ("independent_public_binding_count", str(len(independent))),
        ("completed_public_binding_count", str(len(manifest["completed_public_bindings"]))),
        ("next_public_frontier", "NONE"),
        ("live_binding_satisfied_count", "0"),
        ("ledger_binding_count", str(ledger_binding_count)),
        ("retained_blocker_count", str(len(manifest["retained_blockers"]))),
        ("active_admission_schema_compatibility", "V0_ONLY_FAIL_CLOSED_FOR_V1"),
        ("map_bijection_schema_compatibility", "V0_ONLY_FAIL_CLOSED_FOR_V1"),
        ("anti_shopping_verified", "false"),
        ("strata_allocation_pre_entropy_verified", "false"),
        ("external_custody_verified", "false"),
        ("source_writer_runtime_provenance_verified", "false"),
        ("real_run_admitted", "false"),
        ("side_effects_unlocked", "NONE"),
    ]
    require(all("case_" not in key and "case_" not in value for key, value in rows), "public diagnostic leaks case IDs")
    return rows


def error_code(call: Callable[[], Any]) -> str:
    try:
        call()
    except writer.SamplingReceiptError as exc:
        return exc.code
    raise CheckError("expected SamplingReceiptError was not raised")


def recompute_manifests(request: dict[str, Any]) -> dict[str, Any]:
    core = request["contract_core"]
    contract_sha256 = sha256_bytes(canonical_bytes(core))
    frame = request["eligible_frame_manifest"]
    frame_sha256 = sha256_bytes(canonical_bytes(frame))
    request["strata_allocation_manifest"]["eligible_frame_manifest_sha256"] = frame_sha256
    seed = derive_sampling_seed(
        {
            "schema": SEED_REQUEST_SCHEMA,
            "contract_sha256": contract_sha256,
            "trial_id": core["trial_id"],
            "eligible_frame_manifest_sha256": frame_sha256,
            "external_entropy_sha256": request["external_entropy_sha256"],
        }
    )
    selection = select_stratified_cases(
        {
            "schema": SELECTION_REQUEST_SCHEMA,
            "eligible_frame_manifest_sha256": frame_sha256,
            "cases": frame["cases"],
            "strata_allocations": request["strata_allocation_manifest"]["strata_allocations"],
        },
        seed.seed_bytes,
    )
    common = {
        "trial_id": core["trial_id"],
        "contract_sha256": contract_sha256,
        "eligible_frame_manifest_sha256": frame_sha256,
        "sampling_seed_sha256": selection["sampling_seed_sha256"],
        "selection_commitment_sha256": selection["selection_commitment_sha256"],
    }
    request["selected_case_manifest"] = {
        "schema": writer.SELECTED_SCHEMA,
        **common,
        "cases": selection["selected_cases"],
    }
    request["reserve_manifest"] = {
        "schema": writer.RESERVE_SCHEMA,
        **common,
        "cases": selection["reserve_cases"],
    }
    return selection


def run_self_test(root: Path) -> list[str]:
    verify_bound_files(root)
    validate_profile_and_schema(root)
    fixture = canonical_json(root, FIXTURE_PATH)
    original = fixture["request"]
    tests: list[str] = []

    def expect_raw(name: str, raw: bytes, expected: str) -> None:
        require(error_code(lambda: writer.parse_canonical_request_bytes(raw)) == expected, f"{name} error drift")
        tests.append(name)

    def expect_mutation(name: str, mutate: Callable[[dict[str, Any]], None], expected: str) -> None:
        value = copy.deepcopy(original)
        mutate(value)
        require(error_code(lambda: writer.build_sampling_receipt(request_bytes(value))) == expected, f"{name} error drift")
        tests.append(name)

    expect_raw("canonical-empty", b"", "REQUEST_SIZE")
    expect_raw("canonical-bom", b"\xef\xbb\xbf{}\n", "JSON_BOM")
    expect_raw("canonical-invalid-utf8", b"{\xff}\n", "JSON_UTF8")
    expect_raw("canonical-duplicate-key", b'{"schema":1,"schema":2}\n', "JSON_DUPLICATE_KEY")
    expect_raw("canonical-nan", b'{"x":NaN}\n', "JSON_NONFINITE")
    expect_raw("canonical-whitespace", b'{}', "REQUEST_CANONICAL")
    expect_raw("canonical-root-array", b'[]\n', "REQUEST_ROOT")
    expect_raw("canonical-float", b'{"x":1.5}\n', "JSON_SCALAR")
    expect_raw("canonical-unsafe-int", b'{"x":9007199254740992}\n', "JSON_INTEGER")
    expect_raw("canonical-total-input-cap", b"x" * (writer.MAX_TOTAL_INPUT_BYTES + 1), "REQUEST_SIZE")
    deep: Any = 0
    for _ in range(writer.MAX_JSON_DEPTH + 1):
        deep = [deep]
    expect_raw("canonical-depth", canonical_bytes({"x": deep}), "JSON_DEPTH")

    expect_mutation("request-extra", lambda x: x.__setitem__("extra", 1), "OBJECT_KEYS")
    expect_mutation("request-missing", lambda x: x.pop("created_at_utc"), "OBJECT_KEYS")
    expect_mutation("request-schema", lambda x: x.__setitem__("schema", "wrong"), "REQUEST_SCHEMA")
    expect_mutation("contract-extra", lambda x: x["contract_core"].__setitem__("extra", "0" * 64), "OBJECT_KEYS")
    expect_mutation("contract-missing", lambda x: x["contract_core"].pop("review_policy_sha256"), "OBJECT_KEYS")
    expect_mutation("contract-schema", lambda x: x["contract_core"].__setitem__("schema", "wrong"), "CONTRACT_SCHEMA")
    expect_mutation("contract-trial", lambda x: x["contract_core"].__setitem__("trial_id", "BAD"), "LABEL")
    for name, field in (
        ("contract-profile-hash", "contract_digest_profile_sha256"),
        ("contract-receipt-schema-hash", "sampling_receipt_schema_sha256"),
        ("contract-writer-hash", "sampling_receipt_writer_sha256"),
        ("contract-seed-source-hash", "sampling_seed_derivation_sha256"),
        ("contract-selection-source-hash", "sampling_selection_algorithm_sha256"),
    ):
        expect_mutation(name, lambda x, f=field: x["contract_core"].__setitem__(f, "0" * 64), "CONTRACT_SOURCE_JOIN")
    expect_mutation("contract-policy-shape", lambda x: x["contract_core"].__setitem__("review_policy_sha256", "bad"), "SHA256")

    expect_mutation("frame-extra", lambda x: x["eligible_frame_manifest"].__setitem__("extra", 1), "OBJECT_KEYS")
    expect_mutation("frame-trial", lambda x: x["eligible_frame_manifest"].__setitem__("trial_id", "other"), "FRAME_IDENTITY")
    expect_mutation("frame-policy", lambda x: x["eligible_frame_manifest"].__setitem__("frame_builder_sha256", "0" * 64), "FRAME_POLICY_JOIN")
    expect_mutation("frame-duplicate-case", lambda x: x["eligible_frame_manifest"]["cases"].__setitem__(1, copy.deepcopy(x["eligible_frame_manifest"]["cases"][0])), "CASE_DUPLICATE")
    expect_mutation("frame-order", lambda x: x["eligible_frame_manifest"]["cases"].reverse(), "FRAME_ORDER")
    expect_mutation("frame-case-id", lambda x: x["eligible_frame_manifest"]["cases"][0].__setitem__("case_id", "bad"), "CASE_ID")
    expect_mutation("frame-stratum", lambda x: x["eligible_frame_manifest"]["cases"][0].__setitem__("stratum", "BAD"), "LABEL")
    expect_mutation("frame-empty", lambda x: x["eligible_frame_manifest"].__setitem__("cases", []), "FRAME_CASE_COUNT")

    expect_mutation("allocation-extra", lambda x: x["strata_allocation_manifest"].__setitem__("extra", 1), "OBJECT_KEYS")
    expect_mutation("allocation-trial", lambda x: x["strata_allocation_manifest"].__setitem__("trial_id", "other"), "ALLOCATION_IDENTITY")
    expect_mutation("allocation-frame", lambda x: x["strata_allocation_manifest"].__setitem__("eligible_frame_manifest_sha256", "0" * 64), "ALLOCATION_FRAME_JOIN")
    expect_mutation("allocation-policy", lambda x: x["strata_allocation_manifest"].__setitem__("strata_allocation_policy_sha256", "0" * 64), "ALLOCATION_POLICY_JOIN")
    expect_mutation("allocation-order", lambda x: x["strata_allocation_manifest"]["strata_allocations"].reverse(), "ALLOCATION_ORDER")
    expect_mutation("allocation-missing-stratum", lambda x: x["strata_allocation_manifest"]["strata_allocations"].pop(), "STRATUM_COVERAGE")
    expect_mutation("allocation-duplicate-stratum", lambda x: x["strata_allocation_manifest"]["strata_allocations"].insert(1, copy.deepcopy(x["strata_allocation_manifest"]["strata_allocations"][0])), "ALLOCATION_DUPLICATE")
    expect_mutation("allocation-zero", lambda x: x["strata_allocation_manifest"]["strata_allocations"][0].__setitem__("sample_size", 0), "SAMPLE_SIZE")
    expect_mutation("allocation-bool", lambda x: x["strata_allocation_manifest"]["strata_allocations"][0].__setitem__("sample_size", True), "SAMPLE_SIZE")
    expect_mutation("allocation-over", lambda x: x["strata_allocation_manifest"]["strata_allocations"][0].__setitem__("sample_size", 4), "SAMPLE_SIZE")

    expect_mutation("selected-extra", lambda x: x["selected_case_manifest"].__setitem__("extra", 1), "OBJECT_KEYS")
    expect_mutation("selected-missing-case", lambda x: x["selected_case_manifest"]["cases"].pop(), "SELECTION_MANIFEST_JOIN")
    expect_mutation("selected-duplicate-case", lambda x: x["selected_case_manifest"]["cases"].__setitem__(1, copy.deepcopy(x["selected_case_manifest"]["cases"][0])), "SELECTION_MANIFEST_JOIN")
    expect_mutation("selected-stratum", lambda x: x["selected_case_manifest"]["cases"][0].__setitem__("stratum", "wrong"), "SELECTION_MANIFEST_JOIN")
    expect_mutation("selected-seed", lambda x: x["selected_case_manifest"].__setitem__("sampling_seed_sha256", "0" * 64), "SELECTION_MANIFEST_JOIN")
    expect_mutation("selected-commitment", lambda x: x["selected_case_manifest"].__setitem__("selection_commitment_sha256", "0" * 64), "SELECTION_MANIFEST_JOIN")
    expect_mutation("reserve-missing", lambda x: x["reserve_manifest"]["cases"].pop(), "SELECTION_MANIFEST_JOIN")
    expect_mutation("reserve-overlap", lambda x: x["reserve_manifest"]["cases"][0].__setitem__("case_id", x["selected_case_manifest"]["cases"][0]["case_id"]), "SELECTION_MANIFEST_JOIN")
    expect_mutation("reserve-rank", lambda x: x["reserve_manifest"]["cases"][0].__setitem__("reserve_rank", 9), "SELECTION_MANIFEST_JOIN")
    expect_mutation("reserve-order", lambda x: x["reserve_manifest"]["cases"].reverse(), "SELECTION_MANIFEST_JOIN")

    expect_mutation("entropy-sha", lambda x: x.__setitem__("external_entropy_sha256", "bad"), "SHA256")
    expect_mutation("frame-receipt-sha", lambda x: x.__setitem__("frame_o_excl_receipt_sha256", "bad"), "SHA256")
    expect_mutation("entropy-receipt-sha", lambda x: x.__setitem__("seed_entropy_receipt_sha256", "bad"), "SHA256")
    expect_mutation("clock-shape", lambda x: x.__setitem__("created_at_utc", "2026-7-14"), "UTC")
    expect_mutation("clock-calendar", lambda x: x.__setitem__("created_at_utc", "2026-02-30T00:00:00Z"), "UTC")

    selection = recompute_manifests(copy.deepcopy(original))
    broken = copy.deepcopy(selection)
    broken["selection_commitment_sha256"] = "0" * 64
    require(error_code(lambda: writer._verify_selection_commitment(broken)) == "SELECTION_COMMITMENT", "selection commitment mutation drift")
    tests.append("selection-commitment")
    broken = copy.deepcopy(selection)
    broken["case_inclusion_probabilities"][0]["numerator"] = 1
    require(error_code(lambda: writer._verify_case_grain(broken, original["eligible_frame_manifest"])) == "PROBABILITY", "probability mutation drift")
    tests.append("probability-exact")
    broken = copy.deepcopy(selection)
    broken["case_sampling_weights"][0]["numerator"] = 4
    require(error_code(lambda: writer._verify_case_grain(broken, original["eligible_frame_manifest"])) == "WEIGHT", "weight mutation drift")
    tests.append("weight-exact")
    broken = copy.deepcopy(selection)
    broken["case_inclusion_probabilities"][0]["case_id"] = broken["case_inclusion_probabilities"][1]["case_id"]
    require(error_code(lambda: writer._verify_case_grain(broken, original["eligible_frame_manifest"])) == "CASE_GRAIN_JOIN", "case-grain join mutation drift")
    tests.append("case-grain-join")
    broken = copy.deepcopy(selection)
    broken["reserve_cases"][0]["case_id"] = broken["selected_cases"][0]["case_id"]
    require(error_code(lambda: writer._verify_case_grain(broken, original["eligible_frame_manifest"])) == "CASE_PARTITION", "partition overlap mutation drift")
    tests.append("partition-overlap")
    broken = copy.deepcopy(selection)
    broken["reserve_cases"].pop()
    require(error_code(lambda: writer._verify_case_grain(broken, original["eligible_frame_manifest"])) == "CASE_PARTITION", "partition gap mutation drift")
    tests.append("partition-gap")
    broken = copy.deepcopy(selection)
    broken["reserve_cases"][0]["stratum"] = "wrong"
    require(error_code(lambda: writer._verify_case_grain(broken, original["eligible_frame_manifest"])) == "CASE_STRATUM_JOIN", "stratum join mutation drift")
    tests.append("stratum-join")
    broken = copy.deepcopy(selection)
    broken["reserve_cases"][0]["reserve_rank"] = 2
    require(error_code(lambda: writer._verify_case_grain(broken, original["eligible_frame_manifest"])) == "RESERVE_RANK", "reserve rank mutation drift")
    tests.append("reserve-rank-contiguous")

    built = writer.build_sampling_receipt(request_bytes(original))
    require(
        writer._bound_hmac_sha256_new(
            bytes.fromhex("0b" * 20),
            b"Hi There",
            writer._CAPTURED_SHA256,
        ).digest().hex()
        == "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7",
        "controlled HMAC-SHA-256 RFC 4231 vector drift",
    )
    tests.append("controlled-hmac-rfc4231")
    seed_module, selection_module = writer._load_bound_dependencies()
    require(seed_module.__name__.startswith("_agent_bridge_bound_sampling_seed_derivation_"), "seed dependency was not privately loaded")
    require(selection_module.__name__.startswith("_agent_bridge_bound_sampling_selection_"), "selection dependency was not privately loaded")
    require(seed_module.derive_sampling_seed.__module__ == seed_module.__name__, "seed function provenance drift")
    require(selection_module.select_stratified_cases.__module__ == selection_module.__name__, "selection function provenance drift")
    tests.append("bound-dependency-execution")
    real_hmac_module = sys.modules.get("hmac")
    fake_hmac_module = types.ModuleType("hmac")
    fake_hmac_module.new = lambda *_args, **_kwargs: types.SimpleNamespace(
        digest=lambda: b"\0" * 32
    )
    sys.modules["hmac"] = fake_hmac_module
    try:
        _shadow_seed, shadow_selection = writer._load_bound_dependencies()
        require(shadow_selection.hmac is not fake_hmac_module, "selection dependency accepted ambient hmac shadow")
        shadow_built = writer.build_sampling_receipt(request_bytes(original))
        require(shadow_built.canonical_bytes == built.canonical_bytes, "ambient hmac shadow changed receipt bytes")
    finally:
        if real_hmac_module is None:
            sys.modules.pop("hmac", None)
        else:
            sys.modules["hmac"] = real_hmac_module
    tests.append("transitive-hmac-shadow-isolated")
    tampered_receipt = copy.deepcopy(built.receipt)
    tampered_receipt["condition_output_authorized"] = True
    tampered = dataclasses.replace(built, receipt=tampered_receipt)
    with tempfile.TemporaryDirectory(prefix="track-b-built-object-") as temp:
        os.chmod(temp, 0o700)
        fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            require(error_code(lambda: writer.write_sampling_receipt_o_excl(fd, tampered)) == "BUILT_RECOMPUTE", "built object mutation drift")
        finally:
            os.close(fd)
    tests.append("built-object")
    tampered = dataclasses.replace(built, canonical_bytes=built.canonical_bytes + b" ")
    with tempfile.TemporaryDirectory(prefix="track-b-built-bytes-") as temp:
        os.chmod(temp, 0o700)
        fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            require(error_code(lambda: writer.write_sampling_receipt_o_excl(fd, tampered)) == "BUILT_RECOMPUTE", "built bytes mutation drift")
        finally:
            os.close(fd)
    tests.append("built-bytes")
    tampered = dataclasses.replace(built, receipt_sha256="0" * 64)
    with tempfile.TemporaryDirectory(prefix="track-b-built-hash-") as temp:
        os.chmod(temp, 0o700)
        fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            require(error_code(lambda: writer.write_sampling_receipt_o_excl(fd, tampered)) == "BUILT_RECOMPUTE", "built hash mutation drift")
        finally:
            os.close(fd)
    tests.append("built-hash")

    forged_receipt = {"attacker": True, "condition_output_authorized": True}
    forged_bytes = canonical_bytes(forged_receipt)
    forged = writer.BuiltSamplingReceipt(
        receipt=forged_receipt,
        canonical_bytes=forged_bytes,
        canonical_request_bytes=built.canonical_request_bytes,
        receipt_sha256=sha256_bytes(forged_bytes),
        selected_case_count=0,
        reserve_case_count=0,
    )
    with tempfile.TemporaryDirectory(prefix="track-b-built-forgery-") as temp:
        os.chmod(temp, 0o700)
        fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            require(error_code(lambda: writer.write_sampling_receipt_o_excl(fd, forged)) == "BUILT_RECOMPUTE", "self-consistent arbitrary built forgery drift")
        finally:
            os.close(fd)
    tests.append("built-self-consistent-arbitrary-forgery")

    schema_valid_forgery_receipt = copy.deepcopy(built.receipt)
    schema_valid_forgery_receipt["sampling_seed_sha256"] = "0" * 64
    schema_valid_forgery_receipt["selection_commitment_sha256"] = "1" * 64
    schema_valid_forgery_receipt["case_inclusion_probabilities"][0]["numerator"] = 1
    forged_bytes = canonical_bytes(schema_valid_forgery_receipt)
    schema_valid_forgery = dataclasses.replace(
        built,
        receipt=schema_valid_forgery_receipt,
        canonical_bytes=forged_bytes,
        receipt_sha256=sha256_bytes(forged_bytes),
    )
    with tempfile.TemporaryDirectory(prefix="track-b-schema-valid-forgery-") as temp:
        os.chmod(temp, 0o700)
        fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            require(error_code(lambda: writer.write_sampling_receipt_o_excl(fd, schema_valid_forgery)) == "BUILT_RECOMPUTE", "schema-valid derived forgery drift")
        finally:
            os.close(fd)
    tests.append("built-schema-valid-derived-forgery")

    require(error_code(lambda: writer.write_sampling_receipt_o_excl(-1, built)) == "DIRECTORY_FD", "negative fd mutation drift")
    tests.append("directory-negative-fd")
    with tempfile.NamedTemporaryFile() as ordinary:
        require(error_code(lambda: writer.write_sampling_receipt_o_excl(ordinary.fileno(), built)) == "DIRECTORY_TYPE", "file fd mutation drift")
    tests.append("directory-file-fd")
    with tempfile.TemporaryDirectory(prefix="track-b-mode-") as temp:
        os.chmod(temp, 0o755)
        fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            require(error_code(lambda: writer.write_sampling_receipt_o_excl(fd, built)) == "DIRECTORY_MODE", "directory mode mutation drift")
        finally:
            os.close(fd)
    tests.append("directory-mode")

    def existing_leaf(kind: str) -> None:
        with tempfile.TemporaryDirectory(prefix=f"track-b-existing-{kind}-") as temp:
            os.chmod(temp, 0o700)
            leaf = Path(temp, writer.RECEIPT_BASENAME)
            if kind == "regular":
                leaf.write_bytes(b"sentinel")
            elif kind == "symlink":
                leaf.symlink_to("target")
            elif kind == "dangling":
                leaf.symlink_to("missing")
            elif kind == "fifo":
                os.mkfifo(leaf, 0o600)
            fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                require(error_code(lambda: writer.write_sampling_receipt_o_excl(fd, built)) == "RECEIPT_EXISTS", f"existing {kind} mutation drift")
                if kind == "regular":
                    require(leaf.read_bytes() == b"sentinel", "existing regular bytes changed")
            finally:
                os.close(fd)
        tests.append(f"existing-{kind}")

    for leaf_kind in ("regular", "symlink", "dangling", "fifo"):
        existing_leaf(leaf_kind)

    with tempfile.TemporaryDirectory(prefix="track-b-concurrent-") as temp:
        os.chmod(temp, 0o700)
        fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        barrier = threading.Barrier(2)
        results: list[str] = []
        def concurrent_write() -> None:
            barrier.wait()
            try:
                writer.write_sampling_receipt_o_excl(fd, built)
                results.append("OK")
            except writer.SamplingReceiptError as exc:
                results.append(exc.code)
        threads = [threading.Thread(target=concurrent_write) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        os.close(fd)
        require(sorted(results) == ["OK", "RECEIPT_EXISTS"], "concurrent writer uniqueness drift")
    tests.append("concurrent-single-winner")

    real_write = writer.os.write
    with tempfile.TemporaryDirectory(prefix="track-b-short-write-") as temp:
        os.chmod(temp, 0o700)
        fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            writer.os.write = lambda _fd, _view: 0
            require(error_code(lambda: writer.write_sampling_receipt_o_excl(fd, built)) == "RECEIPT_SHORT_WRITE", "short-write mutation drift")
            writer.os.write = real_write
            require(error_code(lambda: writer.write_sampling_receipt_o_excl(fd, built)) == "RECEIPT_EXISTS", "short-write tombstone retry drift")
        finally:
            writer.os.write = real_write
            os.close(fd)
    tests.append("short-write-tombstone")

    real_fsync = writer.os.fsync
    for name, fail_directory in (("file-fsync-tombstone", False), ("directory-fsync-tombstone", True)):
        with tempfile.TemporaryDirectory(prefix=f"track-b-{name}-") as temp:
            os.chmod(temp, 0o700)
            fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            def failing_fsync(target_fd: int, directory: bool = fail_directory) -> None:
                is_directory = stat.S_ISDIR(os.fstat(target_fd).st_mode)
                if is_directory == directory:
                    raise OSError("synthetic fsync failure")
                real_fsync(target_fd)
            try:
                writer.os.fsync = failing_fsync
                require(error_code(lambda: writer.write_sampling_receipt_o_excl(fd, built)) == "RECEIPT_IO", f"{name} error drift")
                writer.os.fsync = real_fsync
                require(error_code(lambda: writer.write_sampling_receipt_o_excl(fd, built)) == "RECEIPT_EXISTS", f"{name} retry drift")
            finally:
                writer.os.fsync = real_fsync
                os.close(fd)
        tests.append(name)

    entropy_variant = copy.deepcopy(original)
    entropy_variant["external_entropy_sha256"] = hashlib.sha256(b"alternate synthetic entropy").hexdigest()
    variant_selection = recompute_manifests(entropy_variant)
    variant = writer.build_sampling_receipt(request_bytes(entropy_variant))
    require(variant.receipt["sampling_seed_sha256"] != built.receipt["sampling_seed_sha256"], "entropy variant seed did not change")
    require(variant.receipt["selection_commitment_sha256"] != built.receipt["selection_commitment_sha256"], "entropy variant commitment did not change")
    tests.append("entropy-variant")
    census = copy.deepcopy(original)
    for row in census["strata_allocation_manifest"]["strata_allocations"]:
        row["sample_size"] = 3
    recompute_manifests(census)
    census_built = writer.build_sampling_receipt(request_bytes(census))
    require(census_built.selected_case_count == 6 and census_built.reserve_case_count == 0, "full census positive control drift")
    tests.append("full-census")

    require(len(tests) >= 75, "mutation matrix unexpectedly small")
    return tests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).absolute()
    require(root.is_dir() and not root.is_symlink(), "root must be a real directory")
    if args.self_test:
        tests = run_self_test(root)
        digest = sha256_bytes(canonical_bytes(tests))
        print(f"SELF_TEST_OK\t{len(tests)}\t{digest}")
        return 0
    for key, value in normal_rows(root):
        print(f"{key}\t{value}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CheckError, writer.SamplingReceiptError) as exc:
        print(f"sampling-receipt-writer purpose check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
