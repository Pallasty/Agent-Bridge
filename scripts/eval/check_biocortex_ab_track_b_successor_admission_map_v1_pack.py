#!/usr/bin/env python3
"""Validate the source-only Track B successor admission/map v1 pack."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import biocortex_ab_track_b_map_bijection_v0 as map_v0
import biocortex_ab_track_b_map_bijection_v1 as map_v1
import biocortex_ab_track_b_sampling_receipt_writer_v0 as writer
import biocortex_ab_track_b_sampling_seed_derivation_v0 as seed_derivation
import biocortex_ab_track_b_sampling_selection_v0 as selection
import check_biocortex_ab_track_b_admission_v1 as admission_v1


BASELINE_COMMIT = "2e828d7b86444770c3ef3cd40ac17f26cac6fb0e"
PACK_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_successor_admission_map_v1_pack.v0"
)
PACK_DECISION = "SUCCESSOR_V1_SOURCE_COMPATIBILITY_PASS_REAL_RUN_NOT_ADMITTED"
SYNTHETIC_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_successor_admission_map_v1_pack_synthetic_v0.json"
)
MANIFEST_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_successor_admission_map_v1_pack_v0.json"
)
POLICY_PATH = admission_v1.POLICY_PATH
WRITER_FIXTURE_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_sampling_receipt_writer_pack_synthetic_v0.json"
)
IDENTITY_FIXTURE_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_synthetic_v0.json"
)
GRAPH_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
)
LEDGER_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
)
V0_ADMISSION_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
)

EXPECTED_HASHES = {
    str(WRITER_FIXTURE_PATH): "79bdb87f5fdaeb72423ff12002f4cf9a0deca2e9cd9b86e820321357a0641b8a",
    str(IDENTITY_FIXTURE_PATH): "094a7343543be2a9b32fc996dc3e7006bc9d02f87f8cc9bdd269ef9fb61a341a",
    str(GRAPH_PATH): "8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af",
    str(LEDGER_PATH): "764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341a",
    str(V0_ADMISSION_PATH): "1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e",
    "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json": "ad40df50eec68fa192c79e6699a8d2da2a9c3925a387eaa7427f7e19f996d783",
    "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json": "9e73afee2f6366a241b155680b4f77341adeb7c4e341ab91b8d4b1499b5aacbd",
    "scripts/eval/biocortex_ab_track_b_map_bijection_v0.py": "45f55cea933ee12df402fbb55d27ea7c6cd08ba8eef9d9868e4e491dd62a2cd2",
    "scripts/eval/biocortex_ab_track_b_sampling_seed_derivation_v0.py": "4f51781ff707e89b4c09adffeafbdaacd75c7e1571d1a86e45d336aace888a3f",
    "scripts/eval/biocortex_ab_track_b_sampling_selection_v0.py": "e327faf2ad73718dc33f68fdb66a89abf0ac84fbbf8d828ff79fa0e8b75772ec",
    "scripts/check-biocortex-ab-track-b-sampling-receipt-writer-pack.sh": "62006c057f8304733227402d105d8b37d033ad7253e7c4433fa58433196992d3",
}


class PackError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise PackError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def canonical_bytes(value: Any) -> bytes:
    return map_v1.canonical_pretty_bytes(value)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_object(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def load_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda token: fail(f"{label} non-finite constant {token}"),
            object_pairs_hook=_reject_duplicates,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read {label}: {exc}")
    require(type(value) is dict, f"{label} must be an object")
    require(canonical_bytes(value) == raw, f"{label} is not canonical JSON")
    return value, raw


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def validate_source_hashes(root: Path) -> None:
    for relative, expected in EXPECTED_HASHES.items():
        path = root / relative
        require(path.is_file() and not path.is_symlink(), f"source missing: {relative}")
        require(sha256_bytes(path.read_bytes()) == expected, f"source hash drift: {relative}")


def validate_synthetic_config(
    config: dict[str, Any], raw: bytes, root: Path
) -> None:
    expected_keys = {
        "answer_blinding_seed_hex",
        "boundary",
        "condition_keys",
        "expected",
        "map_created_at_utc",
        "schema",
        "source_writer_fixture_path",
        "source_writer_fixture_sha256",
        "synthetic_only",
        "trial_id",
    }
    require(set(config) == expected_keys, "synthetic config field set drift")
    require(
        config["schema"]
        == "agent_bridge.biocortex_ab_track_b_successor_admission_map_v1_pack_synthetic.v0",
        "synthetic config schema drift",
    )
    require(config["synthetic_only"] is True, "synthetic fence missing")
    require(
        config["boundary"]
        == {
            "anti_shopping_order_verified": False,
            "condition_output_authorized": False,
            "contains_private_runtime_material": False,
            "fixture_only": True,
            "live_binding_satisfied": False,
            "pre_output_timing_verified": False,
            "real_run_authorized": False,
            "replay_consumption_verified": False,
            "side_effects_unlocked": "NONE",
        },
        "synthetic boundary drift",
    )
    require(config["condition_keys"] == ["candidate", "reference"], "condition catalog drift")
    require(
        config["source_writer_fixture_path"] == str(WRITER_FIXTURE_PATH),
        "writer fixture path drift",
    )
    require(
        config["source_writer_fixture_sha256"] == EXPECTED_HASHES[str(WRITER_FIXTURE_PATH)],
        "writer fixture hash binding drift",
    )
    require(
        sha256_bytes((root / WRITER_FIXTURE_PATH).read_bytes())
        == config["source_writer_fixture_sha256"],
        "writer fixture byte hash drift",
    )
    require(1 <= len(raw) <= 65536, "synthetic config size outside source cap")


def validate_manifest(
    manifest: dict[str, Any], root: Path, synthetic_raw: bytes
) -> None:
    require(
        set(manifest)
        == {
            "artifact_bindings",
            "baseline_commit",
            "boundary",
            "canonical_serialization",
            "data_quality_contract",
            "date",
            "decision",
            "evidence_sha256",
            "next_unit",
            "predecessor",
            "retained_blockers",
            "schema",
            "synthetic_fixture_path",
            "synthetic_fixture_sha256",
            "version_tuple",
        },
        "manifest field set drift",
    )
    require(
        manifest["schema"]
        == "agent_bridge.biocortex_ab_track_b_successor_admission_map_v1_pack_manifest.v0",
        "manifest schema drift",
    )
    require(manifest["baseline_commit"] == BASELINE_COMMIT, "manifest baseline drift")
    require(manifest["decision"] == PACK_DECISION, "manifest decision drift")
    require(manifest["date"] == "2026-07-14", "manifest date drift")
    require(
        manifest["canonical_serialization"]
        == "UTF8_SORTED_KEYS_INDENT_2_LF_FINAL_NEWLINE_NO_NAN_DUPLICATE_KEYS_REJECTED",
        "manifest canonical profile drift",
    )
    require(
        manifest["synthetic_fixture_path"] == str(SYNTHETIC_PATH)
        and manifest["synthetic_fixture_sha256"] == sha256_bytes(synthetic_raw),
        "manifest synthetic binding drift",
    )
    expected_artifacts = {
        "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v1.json": (
            "successor_real_run_admission_policy",
            None,
            admission_v1.SCHEMA,
        ),
        "scripts/eval/check_biocortex_ab_track_b_admission_v1.py": (
            "successor_admission_policy_checker",
            None,
            None,
        ),
        "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v1.json": (
            "blind_map_schema_successor",
            "review_and_blinding.map_schema_sha256",
            "urn:agent-bridge:biocortex-ab:track-b:blind-map:v1",
        ),
        "scripts/eval/biocortex_ab_track_b_map_bijection_v1.py": (
            "map_bijection_checker_successor",
            "review_and_blinding.map_bijection_checker_sha256",
            map_v1.RESULT_SCHEMA,
        ),
    }
    bindings = manifest["artifact_bindings"]
    require(type(bindings) is list and len(bindings) == 4, "manifest artifact count drift")
    require(
        [row.get("repo_path") for row in bindings] == list(expected_artifacts),
        "manifest artifact order drift",
    )
    for row in bindings:
        require(
            set(row)
            == {
                "artifact_kind",
                "graph_binding_path",
                "repo_path",
                "schema_id",
                "sha256",
                "status",
            },
            "manifest artifact field set drift",
        )
        expected_kind, expected_path, expected_schema = expected_artifacts[
            row["repo_path"]
        ]
        require(row["artifact_kind"] == expected_kind, "manifest artifact kind drift")
        require(row["graph_binding_path"] == expected_path, "manifest graph path drift")
        require(row["schema_id"] == expected_schema, "manifest schema id drift")
        require(
            row["sha256"] == sha256_bytes((root / row["repo_path"]).read_bytes()),
            "manifest artifact byte binding drift",
        )
        require("NOT_LIVE_BOUND" in row["status"] or "NOT_RUNTIME_PROVENANCE" in row["status"], "manifest source status overclaims")
    manifest_evidence = {
        **EXPECTED_HASHES,
        "docs/design/fixtures/biocortex-ab-track-b-sampling-contract-digest-profile-v0.json": map_v1.CONTRACT_DIGEST_PROFILE_SHA256,
        "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v1.json": map_v1.SAMPLING_SCHEMA_SHA256,
        "scripts/eval/biocortex_ab_track_b_sampling_receipt_writer_v0.py": map_v1.SAMPLING_WRITER_SHA256,
        "scripts/eval/check_biocortex_ab_track_b_admission.py": "b09b10243f195299dc226b5d8d2b484ec74f5eecd49bb487296c391f6f193b13",
    }
    require(
        manifest["evidence_sha256"]
        == {relative: manifest_evidence[relative] for relative in sorted(manifest_evidence)},
        "manifest evidence catalog drift",
    )
    require(manifest["predecessor"] == {
        "integrated_commit": "be106a88688dd2df5257b4692a41c908988cdad8",
        "manifest_path": "scripts/eval/fixtures/biocortex_ab_track_b_sampling_receipt_writer_pack_v0.json",
        "manifest_sha256": "3fb4e59754c9c52b6c0ebb642dccdd6ccb7f9282fca6bfb83a4fd001e76437e9",
        "source_commit": "d72dcbba17a6744c6a8784c83e88fef6d74399cc",
    }, "manifest predecessor drift")
    require(manifest["boundary"] == {
        "anti_shopping_order_verified": False,
        "capture_allowed": False,
        "condition_output_authorized": False,
        "frozen_graph_mutated": False,
        "frozen_ledger_mutated": False,
        "historical_v0_bytes_mutated": False,
        "live_binding_satisfied_count": 0,
        "new_graph_binding_path_count": 0,
        "pre_output_timing_verified": False,
        "private_runtime_artifact_emitted": False,
        "real_run_admitted": False,
        "replay_consumption_verified": False,
        "review_authorized": False,
        "scoring_authorized": False,
        "side_effects_unlocked": "NONE",
        "synthetic_fixture_only": True,
        "unblinding_authorized": False,
    }, "manifest boundary drift")
    require(manifest["version_tuple"] == {
        "blind_map_instance_schema": map_v1.MAP_INSTANCE_SCHEMA,
        "contract_core_schema": "agent_bridge.biocortex_ab_track_b_sampling_contract_core.v0",
        "identity_derivation_domain": map_v1.IDENTITY_DERIVATION_DOMAIN,
        "map_request_schema": map_v1.REQUEST_SCHEMA,
        "map_result_schema": map_v1.RESULT_SCHEMA,
        "receipt_instance_schema": map_v1.SAMPLING_INSTANCE_SCHEMA,
        "sampling_attempt_namespace_domain": map_v1.SAMPLING_ATTEMPT_NAMESPACE_DOMAIN,
        "selected_manifest_schema": map_v1.SELECTED_INSTANCE_SCHEMA,
        "v0_fallback_allowed": False,
    }, "manifest version tuple drift")
    require(manifest["data_quality_contract"] == {
        "grains": {
            "blind_map_assignment": "protocol_version_x_trial_id_x_case_id_x_opaque_answer_id",
            "contract_core": "protocol_version_x_trial_id",
            "owner_trial_registration": "global_track_b_trial_registry_x_trial_id",
            "sampling_attempt_namespace": "protocol_version_x_trial_id",
            "sampling_event": "protocol_version_x_trial_id_x_contract_core_sha256_x_eligible_frame_manifest_sha256_x_strata_allocation_manifest_sha256",
            "selected_case": "protocol_version_x_trial_id_x_case_id",
        },
        "join_rules": [
            "EXACT_ORDERED_SELECTED_PROBABILITY_WEIGHT_CASE_ID_EQUALITY",
            "EXACT_SELECTED_TO_FRAME_CASE_AND_STRATUM_EQUALITY",
            "EXACT_RECEIPT_SELECTED_MAP_SEED_AND_SELECTION_COMMITMENT_EQUALITY",
            "EXACT_CONTRACT_CORE_SHA256_NO_ADMISSION_PACKET_ALIAS",
            "EXACT_OWNER_GLOBAL_TRIAL_REGISTRATION_TO_PROTOCOL_ATTEMPT_NAMESPACE",
            "EXACT_SAMPLING_ATTEMPT_NAMESPACE_TO_ONE_POLICY_CONTRACT_CORE_FRAME_ALLOCATION_AND_EVENT",
            "NO_CROSS_VERSION_FALLBACK_ALIAS_OR_MANY_TO_MANY_JOIN",
        ],
    }, "manifest data-quality contract drift")
    require(manifest["retained_blockers"] == admission_v1.EXPECTED_BLOCKERS[:-1], "manifest retained blocker catalog drift")
    require(
        manifest["next_unit"]
        == "INDEPENDENT_CUSTODIAN_SAMPLING_ATTEMPT_CLAIM_AND_WRITE_OUTCOME_RECEIPT",
        "manifest next unit drift",
    )


def _sampling_request(
    root: Path,
    config: dict[str, Any],
    admission_policy_sha256: str,
) -> tuple[dict[str, Any], Any, bytes]:
    writer_fixture, _ = load_canonical(root / WRITER_FIXTURE_PATH, "writer fixture")
    request = copy.deepcopy(writer_fixture["request"])
    trial_id = config["trial_id"]
    for value in (
        request["contract_core"],
        request["eligible_frame_manifest"],
        request["strata_allocation_manifest"],
    ):
        value["trial_id"] = trial_id
    request["contract_core"]["admission_policy_sha256"] = admission_policy_sha256
    contract_sha256 = sha256_object(request["contract_core"])
    frame_sha256 = sha256_object(request["eligible_frame_manifest"])
    request["strata_allocation_manifest"][
        "eligible_frame_manifest_sha256"
    ] = frame_sha256
    derived = seed_derivation.derive_sampling_seed(
        {
            "schema": seed_derivation.REQUEST_SCHEMA,
            "contract_sha256": contract_sha256,
            "trial_id": trial_id,
            "eligible_frame_manifest_sha256": frame_sha256,
            "external_entropy_sha256": request["external_entropy_sha256"],
        }
    )
    selected = selection.select_stratified_cases(
        {
            "schema": selection.REQUEST_SCHEMA,
            "eligible_frame_manifest_sha256": frame_sha256,
            "cases": request["eligible_frame_manifest"]["cases"],
            "strata_allocations": request["strata_allocation_manifest"][
                "strata_allocations"
            ],
        },
        derived.seed_bytes,
    )
    common = {
        "trial_id": trial_id,
        "contract_sha256": contract_sha256,
        "eligible_frame_manifest_sha256": frame_sha256,
        "sampling_seed_sha256": selected["sampling_seed_sha256"],
        "selection_commitment_sha256": selected[
            "selection_commitment_sha256"
        ],
    }
    request["selected_case_manifest"] = {
        "schema": writer.SELECTED_SCHEMA,
        **common,
        "cases": selected["selected_cases"],
    }
    request["reserve_manifest"] = {
        "schema": writer.RESERVE_SCHEMA,
        **common,
        "cases": selected["reserve_cases"],
    }
    request_raw = canonical_bytes(request)
    built = writer.build_sampling_receipt(request_raw)
    return request, built, derived.seed_bytes


def build_map_request(
    root: Path,
    config: dict[str, Any],
    policy_raw: bytes,
    *,
    answer_seed: bytes | None = None,
) -> tuple[dict[str, Any], bytes]:
    write_request, built, sampling_seed = _sampling_request(
        root, config, sha256_bytes(policy_raw)
    )
    receipt = built.receipt
    contract_core = write_request["contract_core"]
    frame = write_request["eligible_frame_manifest"]
    selected_manifest = write_request["selected_case_manifest"]
    trial_id = config["trial_id"]
    contract_sha256 = sha256_object(contract_core)
    frame_sha256 = sha256_object(frame)
    selected_sha256 = sha256_object(selected_manifest)
    write_request_raw = canonical_bytes(write_request)
    seed = answer_seed or bytes.fromhex(config["answer_blinding_seed_hex"])

    conditions = [
        {
            "condition_id": map_v1.derive_condition_id(seed, trial_id, key),
            "condition_key": key,
        }
        for key in config["condition_keys"]
    ]
    roster = {
        "schema": map_v1.ROSTER_INSTANCE_SCHEMA,
        "trial_id": trial_id,
        "contract_sha256": contract_sha256,
        "conditions": conditions,
    }
    case_count = len(selected_manifest["cases"])
    capture = {
        "schema": "agent_bridge.biocortex_ab_track_b_capture_synthetic.v1",
        "trial_id": trial_id,
        "synthetic_only": True,
        "captured_cells": case_count * len(conditions),
    }
    capture_sha256 = sha256_object(capture)
    ranked = sorted(
        (
            map_v1.generation_rank(
                seed, trial_id, row["case_id"], condition["condition_id"]
            ),
            row["case_id"],
            condition["condition_key"],
        )
        for row in selected_manifest["cases"]
        for condition in conditions
    )
    invocation_index = {
        (case_id, condition_key): index
        for index, (_, case_id, condition_key) in enumerate(ranked, 1)
    }
    generated_by_case: dict[str, dict[str, dict[str, Any]]] = {}
    generation_cases: list[dict[str, Any]] = []
    for selected_row in selected_manifest["cases"]:
        case_id = selected_row["case_id"]
        ordered_keys = sorted(
            config["condition_keys"],
            key=lambda key: invocation_index[(case_id, key)],
        )
        answers: list[dict[str, Any]] = []
        generated_by_case[case_id] = {}
        for condition_key in ordered_keys:
            index = invocation_index[(case_id, condition_key)]
            text = f"Synthetic response {index} for {case_id}."
            answer = {
                "answer_markdown": text,
                "answer_sha256": sha256_bytes(text.encode("utf-8")),
                "condition_key": condition_key,
                "invocation_index": index,
            }
            answers.append(answer)
            generated_by_case[case_id][condition_key] = answer
        generation_cases.append({"answers": answers, "case_id": case_id})
    generation = {
        "capture_sha256": capture_sha256,
        "cases": generation_cases,
        "contract_sha256": contract_sha256,
        "first_condition_output_at_utc": "2026-07-14T12:00:30Z",
        "schema": map_v1.GENERATION_INSTANCE_SCHEMA,
        "trial_id": trial_id,
    }
    generation_sha256 = sha256_object(generation)

    blind_cases: list[dict[str, Any]] = []
    map_cases: list[dict[str, Any]] = []
    for selected_row in selected_manifest["cases"]:
        case_id = selected_row["case_id"]
        ordered_conditions = [
            condition
            for _, condition in sorted(
                (
                    map_v1.blind_rank(
                        seed, trial_id, case_id, condition["condition_id"]
                    ),
                    condition,
                )
                for condition in conditions
            )
        ]
        blind_answers: list[dict[str, Any]] = []
        assignments: list[dict[str, Any]] = []
        for condition in ordered_conditions:
            answer_id = map_v1.derive_answer_id(
                seed, trial_id, case_id, condition["condition_id"]
            )
            generated = generated_by_case[case_id][condition["condition_key"]]
            blind_answers.append(
                {
                    "answer_id": answer_id,
                    "answer_markdown": generated["answer_markdown"],
                    "answer_sha256": generated["answer_sha256"],
                }
            )
            assignments.append(
                {"answer_id": answer_id, "condition_id": condition["condition_id"]}
            )
        blind_cases.append({"answers": blind_answers, "case_id": case_id})
        map_cases.append({"assignments": assignments, "case_id": case_id})
    blind_packet = {
        "capture_sha256": capture_sha256,
        "cases": blind_cases,
        "contract_sha256": contract_sha256,
        "generation_sha256": generation_sha256,
        "schema": map_v1.BLIND_INSTANCE_SCHEMA,
        "trial_id": trial_id,
    }
    blind_packet_sha256 = sha256_object(blind_packet)
    sampling_attempt_namespace_sha256 = (
        map_v1.derive_sampling_attempt_namespace_sha256(
            trial_id,
        )
    )
    sampling_event_sha256 = map_v1.derive_sampling_event_sha256(
        contract_sha256,
        trial_id,
        frame_sha256,
        receipt["strata_allocation_manifest_sha256"],
    )
    blind_map = {
        "answer_blinding_seed_sha256": sha256_bytes(seed),
        "blind_packet_sha256": blind_packet_sha256,
        "boundary": {
            "condition_output_authorized": False,
            "cross_version_identity_reuse_allowed": False,
            "mapping_private": True,
            "reviewer_must_not_read_before_review": True,
            "single_use_trial_specific": True,
            "unblinding_allowed": False,
        },
        "capture_sha256": capture_sha256,
        "cases": map_cases,
        "condition_roster_sha256": sha256_object(roster),
        "contract_digest_profile_sha256": map_v1.CONTRACT_DIGEST_PROFILE_SHA256,
        "contract_sha256": contract_sha256,
        "created_at_utc": config["map_created_at_utc"],
        "eligible_frame_manifest_sha256": frame_sha256,
        "generation_sha256": generation_sha256,
        "identity_derivation_domain": map_v1.IDENTITY_DERIVATION_DOMAIN,
        "sampling_attempt_namespace_sha256": sampling_attempt_namespace_sha256,
        "sampling_event_sha256": sampling_event_sha256,
        "sampling_receipt_schema_sha256": map_v1.SAMPLING_SCHEMA_SHA256,
        "sampling_receipt_sha256": built.receipt_sha256,
        "sampling_receipt_writer_sha256": map_v1.SAMPLING_WRITER_SHA256,
        "sampling_receipt_write_request_sha256": sha256_bytes(write_request_raw),
        "sampling_seed_sha256": receipt["sampling_seed_sha256"],
        "schema": map_v1.MAP_INSTANCE_SCHEMA,
        "selected_case_manifest_sha256": selected_sha256,
        "selection_commitment_sha256": receipt["selection_commitment_sha256"],
        "trial_id": trial_id,
    }
    request = {
        "answer_blinding_seed_hex": seed.hex(),
        "blind_map": blind_map,
        "blind_packet": blind_packet,
        "capture": capture,
        "condition_roster": roster,
        "contract_core": contract_core,
        "eligible_frame_manifest": frame,
        "generation_manifest": generation,
        "sampling_receipt": receipt,
        "sampling_receipt_write_request": write_request,
        "schema": map_v1.REQUEST_SCHEMA,
        "selected_case_manifest": selected_manifest,
    }
    return request, sampling_seed


def _set_path(value: dict[str, Any], path: tuple[Any, ...], replacement: Any) -> None:
    cursor: Any = value
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = replacement


def run_map_mutations(root: Path, request: dict[str, Any]) -> int:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("request-schema-v0", lambda x: _set_path(x, ("schema",), map_v0.REQUEST_SCHEMA)),
        ("request-missing", lambda x: x.pop("sampling_receipt_write_request")),
        ("request-extra", lambda x: x.update({"fallback_version": 0})),
        ("map-schema-v0", lambda x: _set_path(x, ("blind_map", "schema"), map_v0.MAP_INSTANCE_SCHEMA)),
        ("map-authority", lambda x: _set_path(x, ("blind_map", "boundary", "condition_output_authorized"), True)),
        ("map-cross-version", lambda x: _set_path(x, ("blind_map", "boundary", "cross_version_identity_reuse_allowed"), True)),
        ("map-domain", lambda x: _set_path(x, ("blind_map", "identity_derivation_domain"), "agent-bridge/track-b/blind-map/v1")),
        ("map-receipt-schema", lambda x: _set_path(x, ("blind_map", "sampling_receipt_schema_sha256"), map_v0.SAMPLING_SCHEMA_SHA256)),
        ("map-writer", lambda x: _set_path(x, ("blind_map", "sampling_receipt_writer_sha256"), "0" * 64)),
        ("map-profile", lambda x: _set_path(x, ("blind_map", "contract_digest_profile_sha256"), "0" * 64)),
        ("map-write-request", lambda x: _set_path(x, ("blind_map", "sampling_receipt_write_request_sha256"), "0" * 64)),
        ("map-attempt-namespace", lambda x: _set_path(x, ("blind_map", "sampling_attempt_namespace_sha256"), "0" * 64)),
        ("map-event", lambda x: _set_path(x, ("blind_map", "sampling_event_sha256"), "0" * 64)),
        ("map-seed", lambda x: _set_path(x, ("blind_map", "sampling_seed_sha256"), "0" * 64)),
        ("map-selection", lambda x: _set_path(x, ("blind_map", "selection_commitment_sha256"), "0" * 64)),
        ("receipt-schema-v0", lambda x: _set_path(x, ("sampling_receipt", "schema"), map_v0.SAMPLING_INSTANCE_SCHEMA)),
        ("receipt-schema-hash", lambda x: _set_path(x, ("sampling_receipt", "receipt_schema_sha256"), map_v0.SAMPLING_SCHEMA_SHA256)),
        ("receipt-writer", lambda x: _set_path(x, ("sampling_receipt", "receipt_writer_sha256"), "0" * 64)),
        ("receipt-profile", lambda x: _set_path(x, ("sampling_receipt", "contract_digest_profile_sha256"), "0" * 64)),
        ("receipt-seed-source", lambda x: _set_path(x, ("sampling_receipt", "seed_derivation_sha256"), "0" * 64)),
        ("receipt-selection-source", lambda x: _set_path(x, ("sampling_receipt", "sampling_selection_algorithm_sha256"), "0" * 64)),
        ("receipt-authority", lambda x: _set_path(x, ("sampling_receipt", "condition_output_authorized"), True)),
        ("receipt-anti-shopping", lambda x: _set_path(x, ("sampling_receipt", "anti_shopping_order_verified"), True)),
        ("receipt-timing", lambda x: _set_path(x, ("sampling_receipt", "pre_output_timing_verified"), True)),
        ("receipt-assertion", lambda x: _set_path(x, ("sampling_receipt", "receipt_precedes_first_condition_output"), False)),
        ("selected-schema-v0", lambda x: _set_path(x, ("selected_case_manifest", "schema"), map_v0.SELECTED_INSTANCE_SCHEMA)),
        ("selected-extra", lambda x: x["selected_case_manifest"]["cases"].append(copy.deepcopy(x["selected_case_manifest"]["cases"][0]))),
        ("selected-stratum", lambda x: _set_path(x, ("selected_case_manifest", "cases", 0, "stratum"), "wrong")),
        ("selected-seed", lambda x: _set_path(x, ("selected_case_manifest", "sampling_seed_sha256"), "0" * 64)),
        ("selected-selection", lambda x: _set_path(x, ("selected_case_manifest", "selection_commitment_sha256"), "0" * 64)),
        ("frame-stratum", lambda x: _set_path(x, ("eligible_frame_manifest", "cases", 0, "stratum"), "wrong")),
        ("contract-alias", lambda x: _set_path(x, ("contract_core", "schema"), admission_v1.SCHEMA)),
        ("writer-request-contract", lambda x: _set_path(x, ("sampling_receipt_write_request", "contract_core", "admission_policy_sha256"), "0" * 64)),
        ("writer-request-entropy", lambda x: _set_path(x, ("sampling_receipt_write_request", "external_entropy_sha256"), "0" * 64)),
        ("time-equal", lambda x: _set_path(x, ("generation_manifest", "first_condition_output_at_utc"), x["sampling_receipt"]["created_at_utc"])),
        ("time-late-map", lambda x: _set_path(x, ("generation_manifest", "first_condition_output_at_utc"), "2026-07-14T12:02:00Z")),
        ("roster-trial", lambda x: _set_path(x, ("condition_roster", "trial_id"), "other_trial")),
        ("roster-duplicate", lambda x: x["condition_roster"]["conditions"].append(copy.deepcopy(x["condition_roster"]["conditions"][0]))),
        ("map-answer-duplicate", lambda x: _set_path(x, ("blind_map", "cases", 0, "assignments", 1, "answer_id"), x["blind_map"]["cases"][0]["assignments"][0]["answer_id"])),
        ("blind-private-leak", lambda x: _set_path(x, ("blind_packet", "cases", 0, "answers", 0, "answer_markdown"), "candidate")),
        ("seed-length", lambda x: _set_path(x, ("answer_blinding_seed_hex",), "00")),
    ]
    rejected = 0
    for label, mutate in mutations:
        candidate = copy.deepcopy(request)
        mutate(candidate)
        try:
            map_v1.validate_request_object(root, candidate)
        except map_v1.BijectionError:
            rejected += 1
        else:
            fail(f"map mutation accepted: {label}")
    with tempfile.TemporaryDirectory(prefix="track-b-map-budget-") as tmp:
        tmp_root = Path(tmp)
        raw_paths: dict[str, Path] = {}
        for key in map_v1.RAW_ARGUMENTS:
            path = tmp_root / key
            path.write_bytes(b"\0" * (32 if key == "seed_file" else 4))
            raw_paths[key] = path
        try:
            map_v1.read_raw_file_set(
                raw_paths,
                total_limit=64,
                artifact_limit=64,
            )
        except map_v1.BijectionError as exc:
            require(exc.code == "INPUT_RESOURCE", "raw cumulative limit hit wrong gate")
            rejected += 1
        else:
            fail("raw cumulative input-byte overflow was accepted")
        regular = tmp_root / "regular"
        regular.write_bytes(b"ok")
        symlink = tmp_root / "symlink"
        symlink.symlink_to(regular)
        fifo = tmp_root / "fifo"
        os.mkfifo(fifo)
        hardlink = tmp_root / "hardlink"
        os.link(regular, hardlink)
        for label, path, code in (
            ("raw-symlink", symlink, "FILE_TYPE"),
            ("raw-fifo", fifo, "FILE_TYPE"),
            ("raw-hardlink", hardlink, "FILE_LINK"),
        ):
            try:
                map_v1.read_bytes(path, label, maximum=64)
            except map_v1.BijectionError as exc:
                require(exc.code == code, f"{label} hit wrong gate")
                rejected += 1
            else:
                fail(f"{label} was accepted")
    return rejected


def validate_version_routes(root: Path, v1_request: dict[str, Any]) -> dict[str, bool]:
    identity_fixture, _ = load_canonical(root / IDENTITY_FIXTURE_PATH, "identity fixture")
    v0_request = map_v0.extract_synthetic_map_request(identity_fixture)
    map_v0.validate_request_object(root, v0_request, input_mode="synthetic_fixture")
    v1_rejects_v0 = False
    try:
        map_v1.validate_request_object(root, v0_request)
    except map_v1.BijectionError:
        v1_rejects_v0 = True
    v0_rejects_v1 = False
    try:
        map_v0.validate_request_object(root, v1_request)
    except map_v0.BijectionError:
        v0_rejects_v1 = True
    require(v1_rejects_v0 and v0_rejects_v1, "version routes are not fail closed")
    return {
        "v0_map_fixture_replay_pass": True,
        "v0_map_accepts_v1_map": False,
        "v1_map_accepts_v0_map": False,
    }


def validate_frozen_boundary(root: Path) -> tuple[int, int, int]:
    graph, _ = load_canonical(root / GRAPH_PATH, "dependency graph")
    ledger, _ = load_canonical(root / LEDGER_PATH, "live-binding ledger")
    require(graph["summary"]["independent_public_count"] == 13, "graph public count drift")
    require(graph["summary"]["implementation_ready_count"] == 0, "graph implementation readiness raised")
    require(graph["summary"]["live_binding_ready_count"] == 0, "graph live readiness raised")
    require(graph["admission"]["real_run_admitted"] is False, "graph admission raised")
    satisfied = sum(row["binding_satisfied"] is True for row in ledger["bindings"])
    require(satisfied == 0, "ledger contains a satisfied live binding")
    require(ledger["coverage"]["real_binding_evidence_count"] == 0, "ledger contains real evidence")
    require(ledger["admission"]["real_run_admitted"] is False, "ledger admission raised")
    return len(graph["nodes"]), len(ledger["bindings"]), satisfied


def validate_data_quality(request: dict[str, Any]) -> dict[str, Any]:
    receipt = request["sampling_receipt"]
    selected = request["selected_case_manifest"]
    frame = request["eligible_frame_manifest"]
    probability_ids = [row["case_id"] for row in receipt["case_inclusion_probabilities"]]
    weight_ids = [row["case_id"] for row in receipt["case_sampling_weights"]]
    selected_ids = [row["case_id"] for row in selected["cases"]]
    require(probability_ids == weight_ids == selected_ids, "selected/probability/weight join drift")
    require(len(selected_ids) == len(set(selected_ids)), "selected case duplicates")
    frame_strata = {row["case_id"]: row["stratum"] for row in frame["cases"]}
    require(
        all(frame_strata[row["case_id"]] == row["stratum"] for row in selected["cases"]),
        "selected/frame stratum join drift",
    )
    require(selected["sampling_seed_sha256"] == receipt["sampling_seed_sha256"], "selected seed join drift")
    require(selected["selection_commitment_sha256"] == receipt["selection_commitment_sha256"], "selected selection join drift")
    contract_core_sha256 = sha256_object(request["contract_core"])
    frame_sha256 = sha256_object(frame)
    trial_id = request["contract_core"]["trial_id"]
    attempt_namespace = map_v1.derive_sampling_attempt_namespace_sha256(
        trial_id,
    )
    require(
        attempt_namespace
        == request["blind_map"]["sampling_attempt_namespace_sha256"],
        "sampling-attempt namespace join drift",
    )
    original_allocation = receipt["strata_allocation_manifest_sha256"]
    alternate_contract = "0" * 64 if contract_core_sha256 != "0" * 64 else "1" * 64
    alternate_frame = "0" * 64 if frame_sha256 != "0" * 64 else "1" * 64
    alternate_allocation = "0" * 64 if original_allocation != "0" * 64 else "1" * 64
    original_event = map_v1.derive_sampling_event_sha256(
        contract_core_sha256,
        trial_id,
        frame_sha256,
        original_allocation,
    )
    alternate_event = map_v1.derive_sampling_event_sha256(
        contract_core_sha256,
        trial_id,
        frame_sha256,
        alternate_allocation,
    )
    require(
        original_event == request["blind_map"]["sampling_event_sha256"],
        "sampling-event join drift",
    )
    require(original_event != alternate_event, "allocation does not distinguish event")
    require(
        original_event
        != map_v1.derive_sampling_event_sha256(
            alternate_contract,
            trial_id,
            frame_sha256,
            original_allocation,
        ),
        "contract core does not distinguish event",
    )
    require(
        original_event
        != map_v1.derive_sampling_event_sha256(
            contract_core_sha256,
            trial_id,
            alternate_frame,
            original_allocation,
        ),
        "eligible frame does not distinguish event",
    )
    return {
        "same_trial_input_shopping_namespace_guard_pass": True,
        "selected_probability_weight_join_pass": True,
        "selected_frame_stratum_join_pass": True,
        "selected_seed_selection_join_pass": True,
    }


RESULT_ORDER = (
    "schema",
    "decision",
    "baseline_commit",
    "manifest_sha256",
    "admission_policy_sha256",
    "map_checker_sha256",
    "map_schema_sha256",
    "sampling_receipt_schema_sha256",
    "sampling_receipt_writer_sha256",
    "sampling_attempt_namespace_sha256",
    "sampling_event_sha256",
    "contract_core_sha256",
    "selected_case_manifest_sha256",
    "selection_commitment_sha256",
    "case_count",
    "condition_count",
    "answer_count",
    "identity_binding_count",
    "map_mutations_rejected",
    "admission_mutations_rejected",
    "v0_map_fixture_replay_pass",
    "v0_map_accepts_v1_map",
    "v1_map_accepts_v0_map",
    "receipt_rebuild_pass",
    "contract_policy_join_pass",
    "same_trial_input_shopping_namespace_guard_pass",
    "selected_probability_weight_join_pass",
    "selected_frame_stratum_join_pass",
    "selected_seed_selection_join_pass",
    "protocol_time_order_consistent",
    "answer_sampling_seed_separation_pass",
    "graph_node_count",
    "ledger_binding_count",
    "live_binding_satisfied_count",
    "condition_output_authorized",
    "anti_shopping_order_verified",
    "pre_output_timing_verified",
    "replay_consumption_verified",
    "real_run_admitted",
    "capture_allowed",
    "review_authorized",
    "scoring_authorized",
    "unblinding_authorized",
    "private_runtime_artifact_emitted",
    "side_effects_unlocked",
    "next_unit",
)


def evaluate(root: Path, self_test: bool) -> dict[str, Any]:
    validate_source_hashes(root)
    policy, policy_raw = load_canonical(root / POLICY_PATH, "admission policy v1")
    admission_v1.validate_policy(policy, root)
    config, config_raw = load_canonical(root / SYNTHETIC_PATH, "synthetic config")
    validate_synthetic_config(config, config_raw, root)
    manifest, manifest_raw = load_canonical(root / MANIFEST_PATH, "pack manifest")
    validate_manifest(manifest, root, config_raw)
    request, sampling_seed = build_map_request(root, config, policy_raw)
    result = map_v1.validate_request_object(root, request)
    expected = config["expected"]
    for field in ("case_count", "condition_count", "answer_count", "identity_binding_count", "protocol_time_order_consistent"):
        require(result[field] == expected[field], f"map result {field} drift")
    quality = validate_data_quality(request)
    routes = validate_version_routes(root, request)
    graph_count, ledger_count, live_count = validate_frozen_boundary(root)
    map_rejected = run_map_mutations(root, request) if self_test else 0
    if self_test:
        require(map_rejected >= expected["minimum_map_mutations_rejected"], "map mutation coverage below floor")
        separation_request, _ = build_map_request(
            root, config, policy_raw, answer_seed=sampling_seed
        )
        try:
            map_v1.validate_request_object(root, separation_request)
        except map_v1.BijectionError as exc:
            require(exc.code == "SEED_SEPARATION", "seed-separation negative hit wrong gate")
            map_rejected += 1
        else:
            fail("answer/sampling seed collision was accepted")
    admission_rejected = admission_v1.run_self_test(policy) if self_test else 0
    return {
        "schema": PACK_SCHEMA,
        "decision": PACK_DECISION,
        "baseline_commit": BASELINE_COMMIT,
        "manifest_sha256": sha256_bytes(manifest_raw),
        "admission_policy_sha256": sha256_bytes(policy_raw),
        "map_checker_sha256": result["checker_sha256"],
        "map_schema_sha256": result["map_schema_sha256"],
        "sampling_receipt_schema_sha256": result["sampling_schema_sha256"],
        "sampling_receipt_writer_sha256": result["sampling_receipt_writer_sha256"],
        "sampling_attempt_namespace_sha256": result[
            "sampling_attempt_namespace_sha256"
        ],
        "sampling_event_sha256": result["sampling_event_sha256"],
        "contract_core_sha256": result["contract_core_sha256"],
        "selected_case_manifest_sha256": result["selected_case_manifest_sha256"],
        "selection_commitment_sha256": result["selection_commitment_sha256"],
        "case_count": result["case_count"],
        "condition_count": result["condition_count"],
        "answer_count": result["answer_count"],
        "identity_binding_count": result["identity_binding_count"],
        "map_mutations_rejected": map_rejected,
        "admission_mutations_rejected": admission_rejected,
        **routes,
        "receipt_rebuild_pass": True,
        "contract_policy_join_pass": request["contract_core"]["admission_policy_sha256"] == sha256_bytes(policy_raw),
        **quality,
        "protocol_time_order_consistent": result["protocol_time_order_consistent"],
        "answer_sampling_seed_separation_pass": True,
        "graph_node_count": graph_count,
        "ledger_binding_count": ledger_count,
        "live_binding_satisfied_count": live_count,
        "condition_output_authorized": False,
        "anti_shopping_order_verified": False,
        "pre_output_timing_verified": False,
        "replay_consumption_verified": False,
        "real_run_admitted": False,
        "capture_allowed": False,
        "review_authorized": False,
        "scoring_authorized": False,
        "unblinding_authorized": False,
        "private_runtime_artifact_emitted": False,
        "side_effects_unlocked": "NONE",
        "next_unit": "INDEPENDENT_CUSTODIAN_SAMPLING_ATTEMPT_CLAIM_AND_WRITE_OUTCOME_RECEIPT",
    }


def render(result: dict[str, Any]) -> str:
    require(set(result) == set(RESULT_ORDER), "pack result field set drift")
    return "".join(
        f"{key}\t{str(result[key]).lower() if type(result[key]) is bool else result[key]}\n"
        for key in RESULT_ORDER
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = evaluate(args.root.resolve(), args.self_test)
        if args.self_test:
            print(
                "SELF_TEST_OK"
                f"\tmap_mutations_rejected={result['map_mutations_rejected']}"
                f"\tadmission_mutations_rejected={result['admission_mutations_rejected']}"
                f"\ttotal_mutations_rejected={result['map_mutations_rejected'] + result['admission_mutations_rejected']}"
            )
        else:
            sys.stdout.write(render(result))
        return 0
    except (PackError, map_v1.BijectionError, map_v0.BijectionError, admission_v1.AdmissionV1Error) as exc:
        print(f"Track B successor admission/map v1 pack check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
