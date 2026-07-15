#!/usr/bin/env python3
"""Deterministically validate the Track B local pre-output guard v1 pack.

The checker constructs two complete synthetic sampling worlds, stores their
terminal outcomes through the frozen crash-atomic custodian, and validates one
closed pre-output plan.  Directed negatives exercise exact joins, causal
boundaries, source identity, canonical JSON, roster/order semantics, and the
intentional absence of both authorizing consumption and output side effects.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import types
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable


BASELINE_COMMIT = "8daa44ee5406b700c59b57b0e44514421bc2f0ad"
PACK_DECISION = (
    "SOURCE_PROFILE_PASS_BLOCKED_FAIL_CLOSED_EXTERNAL_ATOMIC_AUTHORITY_"
    "AND_NON_BYPASSABLE_OUTPUT_PATH_UNBOUND"
)
PACK_STATUS = "LOCAL_PRE_OUTPUT_TUPLE_VALIDATION_ONLY_NO_LIVE_OUTPUT_PERMIT"
PACK_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_first_condition_output_guard_v1_pack_manifest.v0"
)
SYNTHETIC_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_first_condition_output_guard_v1_pack_synthetic.v0"
)
RESULT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_first_condition_output_guard_v1_pack_validation_result.v0"
)

GUARD_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_first_condition_output_guard_v1.py"
)
CUSTODIAN_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_sampling_attempt_custodian_v1.py"
)
CUSTODIAN_CHECKER_PATH = Path(
    "scripts/eval/check_biocortex_ab_track_b_sampling_attempt_custodian_v1_pack.py"
)
SUCCESSOR_CHECKER_PATH = Path(
    "scripts/eval/check_biocortex_ab_track_b_successor_admission_map_v1_pack.py"
)
PLAN_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-pre-output-generation-plan-schema-v1.json"
)
RECEIPT_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-local-guard-validation-receipt-schema-v1.json"
)
MANIFEST_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_first_condition_output_guard_v1_pack_v0.json"
)
EXPECTED_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_first_condition_output_guard_v1_pack.expected.v0.tsv"
)
SYNTHETIC_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_first_condition_output_guard_v1_pack_synthetic_v0.json"
)
CUSTODIAN_FIXTURE_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_sampling_attempt_custodian_v1_pack_synthetic_v0.json"
)
SUCCESSOR_FIXTURE_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_successor_admission_map_v1_pack_synthetic_v0.json"
)
ADMISSION_POLICY_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v1.json"
)
GRAPH_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
)
LEDGER_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
)
ADMISSION_V1_CHECKER_PATH = Path(
    "scripts/eval/check_biocortex_ab_track_b_admission_v1.py"
)

EXPECTED_PREDECESSOR_HASHES = {
    str(CUSTODIAN_PATH): "29c410adef0c5d2b9b312e6417d507395bcb6d808140e8502eeb63211078c71b",
    str(CUSTODIAN_CHECKER_PATH): "64ffc875a532a7ff0c76bfb5fbe947e3d6d8c7254f044793c9d5bfd0325f6848",
    str(SUCCESSOR_CHECKER_PATH): "8011699aac4c897095785330ececf0802b8ccadc9a4226ceb9770aa609e4bab2",
    str(CUSTODIAN_FIXTURE_PATH): "6dd66c46f60023b6b5bc301b800153c001503e2d6f449330d4a971da2bd78f29",
    str(SUCCESSOR_FIXTURE_PATH): "a95a0052a6abfa93ea58f7f913429b8aad4c368cb91a5a54ad98d36fc58470a8",
    str(ADMISSION_POLICY_PATH): "2847ebd368c4a0b557f95b2c91f72b69e31126cf3623ed29320b4154537e3dbe",
    str(GRAPH_PATH): "8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af",
    str(LEDGER_PATH): "764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341a",
    str(ADMISSION_V1_CHECKER_PATH): "8d493f3452589fe1cfd9ece27388c3222a28bac47ca6298cab66c6c3ed52db24",
}

PLAN_SCHEMA_SHA256 = "8b1f4889a4c8f56f2dca69e29e9220eea7b5e51ee6d3944d469bd52e1b5e2409"
RECEIPT_SCHEMA_SHA256 = "34826789b8dcc274d7c8591a64e622598f7f55d294f0e7e7946aa8698fc8c3da"
SYNTHETIC_FIXTURE_SHA256 = "35b382fe5227809c6c06c97a496d4b2664b5632cf230701a167e87ff410d7cb7"
GUARD_SOURCE_SHA256 = "6edf446550b4f10158f938aee6a4583ed0380a580a59c972c12d0fc18f131411"

_OWNED_MODULES: dict[str, Any] = {}


class PackError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise PackError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def canonical_bytes(value: Any) -> bytes:
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
        fail(f"cannot render canonical JSON: {exc}")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_object(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda token: fail(f"{label} has non-finite {token}"),
            object_pairs_hook=_reject_pairs,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"cannot load {label}: {exc}")
    require(type(value) is dict, f"{label} must be an object")
    require(canonical_bytes(value) == raw, f"{label} is not canonical JSON")
    return value, raw


def load_module(path: Path, name: str) -> Any:
    require(name not in sys.modules, f"module name is occupied: {name}")
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(name, None)
        fail(f"cannot execute {path}: {exc}")
    _OWNED_MODULES[name] = module
    return module


def cleanup_owned_modules() -> None:
    for name, module in tuple(_OWNED_MODULES.items()):
        if sys.modules.get(name) is module:
            sys.modules.pop(name, None)
    _OWNED_MODULES.clear()


def validate_source_hashes(root: Path) -> None:
    for relative, expected in EXPECTED_PREDECESSOR_HASHES.items():
        require(
            sha256_bytes((root / relative).read_bytes()) == expected,
            f"predecessor source hash drift: {relative}",
        )
    require(sha256_bytes((root / PLAN_SCHEMA_PATH).read_bytes()) == PLAN_SCHEMA_SHA256, "plan schema hash drift")
    require(sha256_bytes((root / RECEIPT_SCHEMA_PATH).read_bytes()) == RECEIPT_SCHEMA_SHA256, "receipt schema hash drift")
    require(sha256_bytes((root / SYNTHETIC_PATH).read_bytes()) == SYNTHETIC_FIXTURE_SHA256, "synthetic fixture hash drift")
    require(sha256_bytes((root / GUARD_PATH).read_bytes()) == GUARD_SOURCE_SHA256, "guard source hash drift")


def validate_schemas(root: Path, guard: Any) -> None:
    plan_schema, _ = load_canonical(root / PLAN_SCHEMA_PATH, "generation-plan schema")
    receipt_schema, _ = load_canonical(root / RECEIPT_SCHEMA_PATH, "local receipt schema")
    for schema in (plan_schema, receipt_schema):
        require(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", "JSON Schema draft drift")
        require(schema["type"] == "object", "schema root must be an object")
        require(schema["additionalProperties"] is False, "schema root is not closed")
        require(schema["required"] == sorted(schema["properties"]), "schema required/properties drift")
    require(plan_schema["properties"]["schema"]["const"] == guard.PLAN_SCHEMA, "plan instance schema drift")
    require(receipt_schema["properties"]["schema"]["const"] == guard.RECEIPT_SCHEMA, "receipt instance schema drift")
    require(receipt_schema["properties"]["decision"]["const"] == guard.DECISION, "receipt decision drift")
    require(receipt_schema["properties"]["status"]["const"] == guard.STATUS, "receipt status drift")
    for field in (
        "trusted_pre_output_order_verified",
        "caller_prior_output_absence_verified",
        "all_generator_paths_guarded",
        "external_owner_trust_verified",
        "external_authority_provider_present",
        "external_authority_linearizability_verified",
        "external_anti_rollback_anchor_present",
        "external_global_single_use_verified",
        "non_bypassable_output_path_verified",
        "authorizing_consumption_performed",
        "live_output_capability_emitted",
        "condition_output_authorized",
        "receipt_is_output_permit",
    ):
        require(receipt_schema["properties"][field]["const"] is False, f"receipt schema raises {field}")
    require(receipt_schema["properties"]["side_effects_unlocked"]["const"] == "NONE", "receipt schema unlocks a side effect")


def validate_manifest(root: Path, guard: Any) -> None:
    manifest, _ = load_canonical(root / MANIFEST_PATH, "guard pack manifest")
    require(manifest["schema"] == PACK_SCHEMA, "manifest schema drift")
    require(manifest["baseline_commit"] == BASELINE_COMMIT, "manifest baseline drift")
    require(manifest["decision"] == PACK_DECISION, "manifest decision drift")
    require(manifest["status"] == PACK_STATUS, "manifest status drift")
    boundary = manifest["boundary"]
    required_false = (
        "all_generator_paths_guarded",
        "authorizing_consumption_performed",
        "caller_prior_output_absence_verified",
        "condition_output_authorized",
        "external_anti_rollback_anchor_present",
        "external_authority_linearizability_verified",
        "external_authority_provider_present",
        "external_global_single_use_verified",
        "external_owner_trust_verified",
        "live_output_capability_emitted",
        "non_bypassable_output_path_verified",
        "receipt_is_output_permit",
        "real_run_admitted",
        "trusted_pre_output_order_verified",
    )
    for field in required_false:
        require(boundary[field] is False, f"manifest raises {field}")
    require(boundary["local_validation_receipt_replayable"] is True, "manifest hides replayability")
    require(boundary["live_binding_satisfied_count"] == 0, "manifest live binding drift")
    require(boundary["side_effects_unlocked"] == "NONE", "manifest unlocks a side effect")
    bindings = {row["repo_path"]: row["sha256"] for row in manifest["artifact_bindings"]}
    require(bindings[str(GUARD_PATH)] == GUARD_SOURCE_SHA256, "manifest guard source binding drift")
    require(bindings[str(PLAN_SCHEMA_PATH)] == PLAN_SCHEMA_SHA256, "manifest plan schema binding drift")
    require(bindings[str(RECEIPT_SCHEMA_PATH)] == RECEIPT_SCHEMA_SHA256, "manifest receipt schema binding drift")
    evidence = manifest["evidence_sha256"]
    require(len(evidence) == 19, "manifest evidence catalog length drift")
    for relative, expected_sha256 in evidence.items():
        require(type(relative) is str and not Path(relative).is_absolute(), "manifest evidence path is not repository-relative")
        require(
            expected_sha256 == sha256_bytes((root / relative).read_bytes()),
            f"manifest evidence hash drift: {relative}",
        )
    require(manifest["test_oracle"]["directed_mutation_count"] == 47, "manifest mutation count drift")
    require(manifest["test_oracle"]["replay_returns_identical_blocked_receipt"] is True, "manifest replay fact drift")


def build_context(
    root: Path,
    custodian_pack: Any,
    custodian: Any,
    successor: Any,
    custodian_fixture: dict[str, Any],
    successor_fixture: dict[str, Any],
) -> Any:
    policy_raw = (root / ADMISSION_POLICY_PATH).read_bytes()
    admission_sha256 = sha256_bytes(policy_raw)
    write_request, built, _seed = successor._sampling_request(
        root, successor_fixture, admission_sha256
    )
    trial_id = successor_fixture["trial_id"]
    require(custodian_fixture["trial_id"] == trial_id, "synthetic fixture trials differ")
    core_sha256 = sha256_object(write_request["contract_core"])
    frame_sha256 = sha256_object(write_request["eligible_frame_manifest"])
    allocation_sha256 = sha256_object(write_request["strata_allocation_manifest"])
    return custodian_pack.SyntheticContext(
        fixture=custodian_fixture,
        write_request=write_request,
        built_sampling_receipt=built,
        admission_policy_sha256=admission_sha256,
        contract_core_sha256=core_sha256,
        eligible_frame_manifest_sha256=frame_sha256,
        strata_allocation_manifest_sha256=allocation_sha256,
        sampling_attempt_namespace_sha256=custodian.derive_sampling_attempt_namespace(trial_id),
        sampling_event_sha256=custodian.derive_sampling_event(
            core_sha256, trial_id, frame_sha256, allocation_sha256
        ),
    )


def _unit_commitment(domain: str, trial_id: str, index: int, case_id: str, condition_id: str) -> str:
    return sha256_bytes(
        b"\0".join(
            (
                domain.encode("ascii"),
                trial_id.encode("utf-8"),
                str(index).encode("ascii"),
                case_id.encode("ascii"),
                condition_id.encode("ascii"),
            )
        )
    )


def build_plan_and_request(
    guard: Any,
    successor: Any,
    fixture: dict[str, Any],
    context: Any,
    success: dict[str, Any],
    successor_fixture: dict[str, Any],
) -> dict[str, Any]:
    policy_raw = Path(successor.__file__).resolve().parents[2].joinpath(ADMISSION_POLICY_PATH).read_bytes()
    map_request, _sampling_seed = successor.build_map_request(
        Path(successor.__file__).resolve().parents[2], successor_fixture, policy_raw
    )
    require(map_request["sampling_receipt_write_request"] == context.write_request, "map/custodian write-request drift")
    roster = map_request["condition_roster"]
    roster_raw = canonical_bytes(roster)
    seed = bytes.fromhex(successor_fixture["answer_blinding_seed_hex"])
    selected = context.write_request["selected_case_manifest"]
    ranked = sorted(
        (
            successor.map_v1.generation_rank(seed, fixture["trial_id"], row["case_id"], condition["condition_id"]),
            row["case_id"],
            condition["condition_id"],
        )
        for row in selected["cases"]
        for condition in roster["conditions"]
    )
    commitments = fixture["commitments"]
    units: list[dict[str, Any]] = []
    for index, (_rank, case_id, condition_id) in enumerate(ranked, 1):
        units.append(
            {
                "invocation_index": index,
                "case_id": case_id,
                "condition_id": condition_id,
                "prompt_context_sha256": _unit_commitment("agent-bridge/track-b/prompt-context/v1", fixture["trial_id"], index, case_id, condition_id),
                "generator_build_sha256": commitments["generator_build_sha256"],
                "model_snapshot_sha256": commitments["model_snapshot_sha256"],
                "tokenizer_sha256": commitments["tokenizer_sha256"],
                "decoding_profile_sha256": commitments["decoding_profile_sha256"],
                "output_sink_commitment_sha256": _unit_commitment("agent-bridge/track-b/output-sink-slot/v1", fixture["trial_id"], index, case_id, condition_id),
            }
        )
    outcome = success["outcome"]
    plan = {
        "schema": guard.PLAN_SCHEMA,
        "protocol_version": 1,
        "trial_id": fixture["trial_id"],
        "plan_created_at_utc": fixture["plan_created_at_utc"],
        "admission_policy_sha256": context.admission_policy_sha256,
        "contract_core_sha256": context.contract_core_sha256,
        "eligible_frame_manifest_sha256": context.eligible_frame_manifest_sha256,
        "strata_allocation_manifest_sha256": context.strata_allocation_manifest_sha256,
        "sampling_attempt_namespace_sha256": context.sampling_attempt_namespace_sha256,
        "sampling_event_sha256": context.sampling_event_sha256,
        "owner_trial_registration_receipt_sha256": success["registration"].receipt_sha256,
        "sampling_attempt_namespace_claim_receipt_sha256": success["claim"].receipt_sha256,
        "sampling_write_outcome_custodian_receipt_sha256": outcome.receipt_sha256,
        "sampling_write_request_sha256": sha256_object(context.write_request),
        "sampling_receipt_sha256": context.built_sampling_receipt.receipt_sha256,
        "selected_case_manifest_sha256": sha256_object(selected),
        "selection_commitment_sha256": context.built_sampling_receipt.receipt["selection_commitment_sha256"],
        "condition_roster_sha256": sha256_bytes(roster_raw),
        "answer_blinding_seed_sha256": sha256_bytes(seed),
        "generation_session_sha256": commitments["generation_session_sha256"],
        "units": units,
    }
    plan_raw = canonical_bytes(plan)
    request = {
        "schema": guard.REQUEST_SCHEMA,
        "protocol_version": 1,
        "trial_id": fixture["trial_id"],
        "evaluated_at_utc": fixture["evaluated_at_utc"],
        "sampling_attempt_namespace_sha256": context.sampling_attempt_namespace_sha256,
        "sampling_event_sha256": context.sampling_event_sha256,
        "sampling_write_outcome_custodian_receipt_sha256": outcome.receipt_sha256,
        "sampling_receipt_sha256": context.built_sampling_receipt.receipt_sha256,
        "generation_plan_sha256": sha256_bytes(plan_raw),
        "first_output_unit_sha256": sha256_object(units[0]),
        "requested_side_effect": "FIRST_CONDITION_OUTPUT",
        "external_authority_decision_receipt_sha256": None,
        "trusted_clock_receipt_sha256": None,
        "currentness_at_use_receipt_sha256": None,
        "non_bypassable_output_adapter_sha256": None,
    }
    return {
        "plan": plan,
        "plan_raw": plan_raw,
        "request": request,
        "request_raw": canonical_bytes(request),
        "roster": roster,
        "roster_raw": roster_raw,
        "seed": seed,
        "write_request_raw": canonical_bytes(context.write_request),
    }


def guard_binding(guard: Any, config: Any) -> Any:
    values = asdict(config)
    return guard.CustodianStoreBinding(**values)


def invoke(guard: Any, root: Path, world: dict[str, Any]) -> Any:
    artifacts = world["artifacts"]
    return guard.validate_local_first_condition_output_preflight(
        root,
        guard_binding(guard, world["success"]["config"]),
        artifacts["request_raw"],
        artifacts["plan_raw"],
        artifacts["roster_raw"],
        artifacts["seed"],
        artifacts["write_request_raw"],
    )


def expect_rejected(label: str, action: Callable[[], Any]) -> None:
    try:
        action()
    except Exception as exc:
        if exc.__class__.__name__ != "GuardError" or type(getattr(exc, "code", None)) is not str:
            fail(f"directed negative raised an unexpected exception for {label}: {exc}")
        return
    fail(f"directed negative was accepted: {label}")


def mutated_world(world: dict[str, Any]) -> dict[str, Any]:
    result = dict(world)
    result["artifacts"] = copy.deepcopy(world["artifacts"])
    return result


def refresh_plan_request(guard: Any, world: dict[str, Any]) -> None:
    artifacts = world["artifacts"]
    artifacts["plan_raw"] = canonical_bytes(artifacts["plan"])
    artifacts["request"]["generation_plan_sha256"] = sha256_bytes(artifacts["plan_raw"])
    artifacts["request"]["first_output_unit_sha256"] = sha256_object(artifacts["plan"]["units"][0])
    artifacts["request_raw"] = canonical_bytes(artifacts["request"])


def run_directed_mutations(guard: Any, root: Path, world_a: dict[str, Any], world_b: dict[str, Any]) -> dict[str, int]:
    counts = {
        "cross_world_tuple": 0,
        "plan_and_order": 0,
        "causal_authority": 0,
        "canonical_and_schema": 0,
        "artifact_bytes": 0,
    }

    plan_hash_fields = [
        "admission_policy_sha256",
        "answer_blinding_seed_sha256",
        "condition_roster_sha256",
        "contract_core_sha256",
        "eligible_frame_manifest_sha256",
        "owner_trial_registration_receipt_sha256",
        "sampling_attempt_namespace_claim_receipt_sha256",
        "sampling_attempt_namespace_sha256",
        "sampling_event_sha256",
        "sampling_receipt_sha256",
        "sampling_write_outcome_custodian_receipt_sha256",
        "sampling_write_request_sha256",
        "selected_case_manifest_sha256",
        "selection_commitment_sha256",
        "strata_allocation_manifest_sha256",
    ]
    for field in plan_hash_fields:
        candidate = mutated_world(world_a)
        replacement = world_b["artifacts"]["plan"][field]
        if replacement == world_a["artifacts"]["plan"][field]:
            replacement = sha256_bytes(f"directed-world-b/{field}".encode("ascii"))
        candidate["artifacts"]["plan"][field] = replacement
        refresh_plan_request(guard, candidate)
        expect_rejected(f"cross-world plan {field}", lambda c=candidate: invoke(guard, root, c))
        counts["cross_world_tuple"] += 1

    for field in (
        "trial_id",
        "sampling_attempt_namespace_sha256",
        "sampling_event_sha256",
        "sampling_receipt_sha256",
        "sampling_write_outcome_custodian_receipt_sha256",
    ):
        candidate = mutated_world(world_a)
        replacement = world_b["artifacts"]["request"][field]
        if replacement == world_a["artifacts"]["request"][field]:
            replacement = sha256_bytes(f"directed-world-b/request/{field}".encode("ascii"))
        candidate["artifacts"]["request"][field] = replacement
        candidate["artifacts"]["request_raw"] = canonical_bytes(candidate["artifacts"]["request"])
        expect_rejected(f"cross-world request {field}", lambda c=candidate: invoke(guard, root, c))
        counts["cross_world_tuple"] += 1

    unit_mutations: list[tuple[str, Any]] = [
        ("invocation_index", 2),
        ("case_id", world_b["artifacts"]["plan"]["units"][0]["case_id"]),
        ("condition_id", world_b["artifacts"]["plan"]["units"][0]["condition_id"]),
        ("output_sink_commitment_sha256", world_a["artifacts"]["plan"]["units"][1]["output_sink_commitment_sha256"]),
    ]
    for field, replacement in unit_mutations:
        candidate = mutated_world(world_a)
        candidate["artifacts"]["plan"]["units"][0][field] = replacement
        refresh_plan_request(guard, candidate)
        expect_rejected(f"plan unit {field}", lambda c=candidate: invoke(guard, root, c))
        counts["plan_and_order"] += 1

    for key in ("generation_sha256", "blind_packet_sha256", "blind_map_sha256", "answer_sha256", "capture_sha256"):
        candidate = mutated_world(world_a)
        candidate["artifacts"]["plan"][key] = "1" * 64
        refresh_plan_request(guard, candidate)
        expect_rejected(f"post-generation plan field {key}", lambda c=candidate: invoke(guard, root, c))
        counts["causal_authority"] += 1

    for field in (
        "external_authority_decision_receipt_sha256",
        "trusted_clock_receipt_sha256",
        "currentness_at_use_receipt_sha256",
        "non_bypassable_output_adapter_sha256",
    ):
        candidate = mutated_world(world_a)
        candidate["artifacts"]["request"][field] = "1" * 64
        candidate["artifacts"]["request_raw"] = canonical_bytes(candidate["artifacts"]["request"])
        expect_rejected(f"unbound evidence {field}", lambda c=candidate: invoke(guard, root, c))
        counts["causal_authority"] += 1

    for label, raw in (
        ("noncanonical request", json.dumps(world_a["artifacts"]["request"]).encode()),
        ("duplicate request key", world_a["artifacts"]["request_raw"].replace(b'{\n', b'{\n  "schema": "duplicate",\n', 1)),
        ("nonfinite request", world_a["artifacts"]["request_raw"].replace(b'"protocol_version": 1', b'"protocol_version": NaN', 1)),
    ):
        candidate = mutated_world(world_a)
        candidate["artifacts"]["request_raw"] = raw
        expect_rejected(label, lambda c=candidate: invoke(guard, root, c))
        counts["canonical_and_schema"] += 1

    for mutation in ("extra", "missing", "zero", "v0"):
        candidate = mutated_world(world_a)
        request = candidate["artifacts"]["request"]
        if mutation == "extra":
            request["condition_output_authorized"] = False
        elif mutation == "missing":
            request.pop("requested_side_effect")
        elif mutation == "zero":
            request["sampling_event_sha256"] = "0" * 64
        else:
            request["schema"] = request["schema"].replace(".v1", ".v0")
        candidate["artifacts"]["request_raw"] = canonical_bytes(request)
        expect_rejected(f"request {mutation}", lambda c=candidate: invoke(guard, root, c))
        counts["canonical_and_schema"] += 1

    artifact_mutations = (
        ("private seed", lambda c: c["artifacts"].__setitem__("seed", bytes(reversed(c["artifacts"]["seed"])))),
        ("roster", lambda c: c["artifacts"].__setitem__("roster_raw", world_b["artifacts"]["roster_raw"])),
        ("write request", lambda c: c["artifacts"].__setitem__("write_request_raw", world_b["artifacts"]["write_request_raw"])),
    )
    for label, mutation in artifact_mutations:
        candidate = mutated_world(world_a)
        mutation(candidate)
        expect_rejected(label, lambda c=candidate: invoke(guard, root, c))
        counts["artifact_bytes"] += 1

    candidate = mutated_world(world_a)
    candidate["artifacts"]["plan"]["units"] = candidate["artifacts"]["plan"]["units"][:-1]
    refresh_plan_request(guard, candidate)
    expect_rejected("incomplete plan", lambda: invoke(guard, root, candidate))
    counts["plan_and_order"] += 1

    candidate = mutated_world(world_a)
    candidate["artifacts"]["plan"]["units"][0], candidate["artifacts"]["plan"]["units"][1] = candidate["artifacts"]["plan"]["units"][1], candidate["artifacts"]["plan"]["units"][0]
    refresh_plan_request(guard, candidate)
    expect_rejected("plan order", lambda: invoke(guard, root, candidate))
    counts["plan_and_order"] += 1

    return counts


def validate_static_surface(root: Path) -> None:
    tree = ast.parse((root / GUARD_PATH).read_text(encoding="utf-8"))
    public_functions = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")}
    require("validate_local_first_condition_output_preflight" in public_functions, "validator API missing")
    forbidden_names = {"authorize_output", "issue_permit", "generate", "write_output", "publish_output", "consume_authority"}
    require(not public_functions & forbidden_names, "guard source exposes a live-output API")
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
    require(not imported & {"socket", "subprocess", "requests", "http", "urllib"}, "guard source imports an output/network path")


def _evaluate_once(root: Path) -> dict[str, Any]:
    root = root.resolve()
    validate_source_hashes(root)
    eval_dir = root / "scripts/eval"
    if str(eval_dir) not in sys.path:
        sys.path.insert(0, str(eval_dir))
    guard = load_module(root / GUARD_PATH, "_track_b_guard_v1_pack_subject")
    custodian = load_module(root / CUSTODIAN_PATH, "_track_b_guard_v1_pack_custodian")
    custodian_pack = load_module(root / CUSTODIAN_CHECKER_PATH, "_track_b_guard_v1_pack_custodian_checker")
    successor = load_module(root / SUCCESSOR_CHECKER_PATH, "_track_b_guard_v1_pack_successor")
    validate_schemas(root, guard)
    validate_manifest(root, guard)
    validate_static_surface(root)

    fixture, _fixture_raw = load_canonical(root / SYNTHETIC_PATH, "guard synthetic fixture")
    custodian_fixture, _ = load_canonical(root / CUSTODIAN_FIXTURE_PATH, "custodian synthetic fixture")
    successor_fixture, _ = load_canonical(root / SUCCESSOR_FIXTURE_PATH, "successor synthetic fixture")
    require(fixture["schema"] == SYNTHETIC_SCHEMA, "synthetic fixture schema drift")
    require(fixture["trial_id"] == custodian_fixture["trial_id"] == successor_fixture["trial_id"], "synthetic trial drift")

    with tempfile.TemporaryDirectory(prefix="track-b-guard-v1-") as temporary:
        base = Path(temporary)
        context_a = build_context(root, custodian_pack, custodian, successor, custodian_fixture, successor_fixture)
        success_a = custodian_pack.run_success_path(root, custodian, successor, context_a, base / "world-a")
        artifacts_a = build_plan_and_request(guard, successor, fixture, context_a, success_a, successor_fixture)
        world_a = {"context": context_a, "success": success_a, "artifacts": artifacts_a}

        fixture_b = copy.deepcopy(fixture)
        fixture_b["trial_id"] = "public_synthetic_track_b_guard_world_b"
        fixture_b["commitments"] = copy.deepcopy(fixture["commitments"])
        fixture_b["commitments"]["generation_session_sha256"] = sha256_bytes(b"agent-bridge/track-b/generation-session/world-b")
        custodian_b = copy.deepcopy(custodian_fixture)
        successor_b = copy.deepcopy(successor_fixture)
        custodian_b["trial_id"] = fixture_b["trial_id"]
        successor_b["trial_id"] = fixture_b["trial_id"]
        successor_b["answer_blinding_seed_hex"] = bytes(reversed(bytes.fromhex(successor_fixture["answer_blinding_seed_hex"]))).hex()
        context_b = build_context(root, custodian_pack, custodian, successor, custodian_b, successor_b)
        success_b = custodian_pack.run_success_path(root, custodian, successor, context_b, base / "world-b")
        artifacts_b = build_plan_and_request(guard, successor, fixture_b, context_b, success_b, successor_b)
        world_b = {"context": context_b, "success": success_b, "artifacts": artifacts_b}

        canary = base / "preexisting-output-canary.bin"
        canary.write_bytes(bytes.fromhex(fixture["preexisting_output_canary_content_hex"]))
        canary_before = canary.read_bytes()
        tree_before = sorted(str(path.relative_to(base)) for path in base.rglob("*") if path.is_file())
        fd_before = set(os.listdir("/proc/self/fd")) if Path("/proc/self/fd").is_dir() else set()
        receipt = invoke(guard, root, world_a)
        fd_after = set(os.listdir("/proc/self/fd")) if Path("/proc/self/fd").is_dir() else set()
        tree_after = sorted(str(path.relative_to(base)) for path in base.rglob("*") if path.is_file())
        require(canary.read_bytes() == canary_before, "preexisting canary changed")
        require(tree_after == tree_before, "guard created or removed an output artifact")
        require(fd_after == fd_before, "guard leaked a file descriptor")

        replay = invoke(guard, root, world_a)
        require(replay == receipt, "local validation receipt is not deterministically replayable")
        require(receipt.receipt["caller_prior_output_absence_verified"] is False, "canary presence was misreported as absence proof")
        require(receipt.receipt["authorizing_consumption_performed"] is False, "validator claims authorizing consumption")
        require(receipt.receipt["condition_output_authorized"] is False, "validator authorizes output")
        require(receipt.receipt["side_effects_unlocked"] == "NONE", "validator unlocks a side effect")
        require(set(receipt.receipt) == set(load_canonical(root / RECEIPT_SCHEMA_PATH, "receipt schema")[0]["required"]), "receipt/schema field set drift")

        for occupied_name in (
            "_biocortex_ab_track_b_bound_custodian_v1_guard",
            "_biocortex_ab_track_b_bound_map_v1_guard",
        ):
            sentinel = types.ModuleType(occupied_name)
            sys.modules[occupied_name] = sentinel
            try:
                expect_rejected(
                    f"preoccupied private module {occupied_name}",
                    lambda: invoke(guard, root, world_a),
                )
                require(
                    sys.modules.get(occupied_name) is sentinel,
                    "guard removed caller-owned module state",
                )
            finally:
                if sys.modules.get(occupied_name) is sentinel:
                    sys.modules.pop(occupied_name, None)

        abort_context = build_context(root, custodian_pack, custodian, successor, custodian_fixture, successor_fixture)
        abort = custodian_pack.run_abort_path(custodian, abort_context, base / "abort-world")
        abort_world = mutated_world(world_a)
        abort_world["success"] = {"config": abort["config"]}
        abort_world["artifacts"]["request"]["sampling_write_outcome_custodian_receipt_sha256"] = abort["outcome"].receipt_sha256
        abort_world["artifacts"]["request_raw"] = canonical_bytes(abort_world["artifacts"]["request"])
        expect_rejected("terminal abort", lambda: invoke(guard, root, abort_world))

        missing_world = mutated_world(world_a)
        missing_world["artifacts"]["request"]["sampling_attempt_namespace_sha256"] = "1" * 64
        missing_world["artifacts"]["request_raw"] = canonical_bytes(missing_world["artifacts"]["request"])
        expect_rejected("missing terminal outcome", lambda: invoke(guard, root, missing_world))

        mutation_counts = run_directed_mutations(guard, root, world_a, world_b)

    _graph, _ = load_canonical(root / GRAPH_PATH, "frozen dependency graph")
    ledger, _ = load_canonical(root / LEDGER_PATH, "frozen live-binding ledger")
    admission = load_module(root / ADMISSION_V1_CHECKER_PATH, "_track_b_guard_v1_pack_admission")
    policy, _ = load_canonical(root / ADMISSION_POLICY_PATH, "admission v1")
    admission.validate_policy(policy, root)
    live = {
        "satisfied": policy["live_binding"]["live_binding_satisfied_count"],
        "total": len(ledger["bindings"]),
    }
    require(live["satisfied"] == 0 and live["total"] == 91, "frozen live-binding count drift")

    directed_total = sum(mutation_counts.values()) + 2
    return {
        "schema": RESULT_SCHEMA,
        "decision": PACK_DECISION,
        "status": PACK_STATUS,
        "protocol_version": 1,
        "trial_id": fixture["trial_id"],
        "sampling_attempt_namespace_sha256": context_a.sampling_attempt_namespace_sha256,
        "sampling_event_sha256": context_a.sampling_event_sha256,
        "sampling_write_outcome_custodian_receipt_sha256": success_a["outcome"].receipt_sha256,
        "sampling_receipt_sha256": context_a.built_sampling_receipt.receipt_sha256,
        "generation_plan_sha256": sha256_bytes(artifacts_a["plan_raw"]),
        "first_output_unit_sha256": sha256_object(artifacts_a["plan"]["units"][0]),
        "local_guard_validation_receipt_sha256": receipt.receipt_sha256,
        "generation_unit_count": len(artifacts_a["plan"]["units"]),
        "directed_mutation_count": directed_total,
        "cross_world_tuple_mutation_count": mutation_counts["cross_world_tuple"],
        "plan_and_order_mutation_count": mutation_counts["plan_and_order"],
        "causal_authority_mutation_count": mutation_counts["causal_authority"],
        "canonical_and_schema_mutation_count": mutation_counts["canonical_and_schema"],
        "artifact_bytes_mutation_count": mutation_counts["artifact_bytes"],
        "abort_and_missing_outcome_mutation_count": 2,
        "preexisting_output_canary_preserved": True,
        "preoccupied_module_state_preserved": True,
        "caller_prior_output_absence_verified": False,
        "local_validation_receipt_replayable": True,
        "authorizing_consumption_performed": False,
        "external_owner_trust_verified": False,
        "external_authority_provider_present": False,
        "external_authority_linearizability_verified": False,
        "external_anti_rollback_anchor_present": False,
        "external_global_single_use_verified": False,
        "all_generator_paths_guarded": False,
        "non_bypassable_output_path_verified": False,
        "live_output_capability_emitted": False,
        "condition_output_authorized": False,
        "live_binding_satisfied_count": live["satisfied"],
        "live_binding_required_count": live["total"],
        "side_effects_unlocked": "NONE",
    }


def evaluate(root: Path) -> dict[str, Any]:
    original_sys_path = list(sys.path)
    try:
        return _evaluate_once(root)
    finally:
        cleanup_owned_modules()
        sys.path[:] = original_sys_path


def render(result: dict[str, Any]) -> str:
    rows: list[str] = []
    for key, value in result.items():
        if type(value) is bool:
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        rows.append(f"{key}\t{rendered}")
    return "\n".join(rows) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--self-test", action="store_true", help="run the same closed directed oracle")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = evaluate(args.root)
        if args.self_test:
            repeated = evaluate(args.root)
            require(repeated == result, "same-process repeated evaluation drifted")
        rendered = render(result)
        expected = (args.root.resolve() / EXPECTED_PATH).read_bytes()
        require(rendered.encode("utf-8") == expected, "rendered result differs from the frozen expected TSV")
    except Exception as exc:
        print(f"Track B first-condition-output guard v1 pack failed: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
