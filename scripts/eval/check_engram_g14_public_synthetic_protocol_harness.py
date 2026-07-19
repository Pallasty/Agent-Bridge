#!/usr/bin/env python3
"""Adversarial checks for the public-synthetic G1.4 protocol harness."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
IMPLEMENTATION_PATH = SCRIPT_DIR / "engram_g14_public_synthetic_protocol_harness.py"
CONTRACT_PATH = (
    SCRIPT_DIR
    / "fixtures/engram_g14_public_synthetic_protocol_harness_contract_v0.json"
)
FIXTURE_PATH = (
    SCRIPT_DIR / "fixtures/engram_g14_public_synthetic_protocol_harness_fixture_v0.json"
)

sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location(
    "engram_g14_protocol_harness", IMPLEMENTATION_PATH
)
assert SPEC is not None and SPEC.loader is not None
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


CONTRACT = load_json(CONTRACT_PATH)
FIXTURE = load_json(FIXTURE_PATH)

CHECKER_CONTRACT_SCHEMA = (
    "agent_bridge.engram_g1_4_public_synthetic_protocol_harness_contract.v0"
)
CHECKER_FIXTURE_SCHEMA = (
    "agent_bridge.engram_g1_4_public_synthetic_protocol_harness_fixture.v0"
)
CHECKER_MODE = "PUBLIC_SYNTHETIC_PROTOCOL_KAT"
CHECKER_PHASES = (
    "development_lock",
    "development_feedback",
    "final_lock",
    "blinded_run_plan",
    "sandbox_attestation",
    "qualification",
    "synthetic_run",
    "decision",
    "mapping_reveal",
)
CHECKER_OPAQUE_ARMS = ("arm_0", "arm_1", "arm_2", "arm_3", "arm_4")
CHECKER_ARM_MAPPING = {
    "arm_0": "stable_control",
    "arm_1": "density_only",
    "arm_2": "clustered_reorganization",
    "arm_3": "mechanism_off",
    "arm_4": "cluster_shuffled",
}
CHECKER_CANARIES = (
    "candidate_code_read",
    "dependency_read",
    "ephemeral_scratch_write",
    "repository_metadata_read",
    "private_manifest_read",
    "live_store_read",
    "network_connect",
    "subprocess_spawn",
    "dynamic_plugin_load",
    "non_scratch_write",
    "wall_clock_read",
    "external_entropy_read",
    "extra_inherited_fd_use",
    "free_form_output",
)
CHECKER_COMPARATORS = ("stable_control", "density_only")
CHECKER_FALSIFIERS = ("mechanism_off", "cluster_shuffled")
SHA256_CHARS = frozenset("0123456789abcdef")


def checker_canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def checker_sha256(value: Any) -> str:
    return hashlib.sha256(checker_canonical_bytes(value)).hexdigest()


def is_sha256(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and set(value).issubset(SHA256_CHARS)


def assert_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    assert type(value) is dict, label
    assert set(value) == expected, (label, set(value), expected)
    return value


def assert_independent_contract_schema() -> None:
    contract = assert_exact_keys(
        CONTRACT,
        {
            "schema",
            "contract_id",
            "stage",
            "predecessor_preregistration",
            "registered_fixture",
            "scope",
            "protocol_state_machine",
            "candidate_artifact_lock_model",
            "access_and_blinding_model",
            "sandbox_attestation_model",
            "determinism_and_state_isolation_model",
            "run_lifecycle_model",
            "decision_rule_model",
            "receipt_model",
            "human_audit_policy",
            "state_machine",
            "boundaries",
        },
        "contract",
    )
    assert contract["schema"] == CHECKER_CONTRACT_SCHEMA
    assert contract["stage"] == (
        "g1_4_public_synthetic_protocol_harness_implementation_gate_only"
    )
    assert contract["registered_fixture"]["fixture_sha256"] == digest(FIXTURE_PATH)
    assert contract["protocol_state_machine"]["required_phases_in_order"] == list(
        CHECKER_PHASES
    )
    scope = contract["scope"]
    assert scope["enabled_by_default"] is False
    assert scope["explicit_boolean_enable_required"] is True
    for field in (
        "production_admissible",
        "production_mode_representable",
        "accepts_real_candidate_source_or_configuration",
        "accepts_real_fit_development_or_sealed_material",
        "accepts_real_freeze_capability",
        "launches_candidate_or_untrusted_process",
        "applies_native_sandbox_policy",
        "observes_native_sandbox_enforcement",
        "registers_mcp_or_runtime_surface",
        "touches_live_store_or_retrieval",
        "opens_candidate_implementation",
        "opens_private_data_access",
        "opens_g1_4_execution",
    ):
        assert scope[field] is False, field
    access = contract["access_and_blinding_model"]
    assert access["synthetic_predecision_and_postdecision_material_split_required"]
    assert access["synthetic_decision_input_custodian_split_required"]
    assert access["scorer_view_contains_mapping_before_decision"] is False
    lifecycle = contract["run_lifecycle_model"]
    assert lifecycle["run_id_consumed_before_attempt_specific_validation"] is True
    assert lifecycle["selective_retry_or_partial_rerun_forbidden"] is True
    receipts = contract["receipt_model"]
    assert receipts["payload_embedded_and_commitment_recomputed_on_verify"] is True
    assert receipts["predecision_scoring_chain_head_frozen_before_scorer"] is True
    audit = contract["human_audit_policy"]
    assert audit["rollback_failure_path_exercised_by_harness"] is True
    assert len(audit["manual_safety_audit_required_for"]) == 8
    assert len(set(audit["manual_safety_audit_required_for"])) == 8
    boundaries = contract["boundaries"]
    positive = {
        "g1_4_design_preregistration_bound",
        "public_synthetic_protocol_harness_implemented",
    }
    for field, value in boundaries.items():
        assert value is (field in positive), (field, value)


def assert_independent_fixture_schema() -> None:
    fixture = assert_exact_keys(
        FIXTURE,
        {
            "schema",
            "fixture_id",
            "mode",
            "public_synthetic_fixture",
            "production_admissible",
            "candidate_artifact",
            "blinding",
            "sandbox_attestation",
            "qualification",
            "synthetic_run",
            "decision_input",
            "expected",
        },
        "fixture",
    )
    assert fixture["schema"] == CHECKER_FIXTURE_SCHEMA
    assert fixture["mode"] == CHECKER_MODE
    assert fixture["public_synthetic_fixture"] is True
    assert fixture["production_admissible"] is False
    blinding = assert_exact_keys(
        fixture["blinding"],
        {"predecision", "postdecision_reveal"},
        "fixture.blinding",
    )
    predecision = assert_exact_keys(
        blinding["predecision"],
        {
            "arm_mapping_commitment_sha256",
            "opaque_arm_ids_in_execution_order",
            "scorer_visible_arm_ids",
            "mapping_reveal_available_to_scorer_before_decision",
        },
        "fixture.blinding.predecision",
    )
    assert predecision["opaque_arm_ids_in_execution_order"] == list(CHECKER_OPAQUE_ARMS)
    assert predecision["scorer_visible_arm_ids"] == list(CHECKER_OPAQUE_ARMS)
    assert predecision["mapping_reveal_available_to_scorer_before_decision"] is False
    assert blinding["postdecision_reveal"] == CHECKER_ARM_MAPPING
    assert (
        checker_sha256(blinding["postdecision_reveal"])
        == predecision["arm_mapping_commitment_sha256"]
    )
    canaries = fixture["sandbox_attestation"]["canaries"]
    assert [row["name"] for row in canaries] == list(CHECKER_CANARIES)
    for index, row in enumerate(canaries):
        expected = "allow" if index < 3 else "deny"
        assert row == {
            "name": CHECKER_CANARIES[index],
            "expected": expected,
            "observed": expected,
        }
    invocations = fixture["synthetic_run"]["invocations"]
    assert [row["opaque_arm_id"] for row in invocations] == list(CHECKER_OPAQUE_ARMS)
    assert [row["ordinal"] for row in invocations] == [1, 2, 3, 4, 5]
    all_ids = [
        invocation_id
        for replay in fixture["qualification"]["replays"]
        for invocation_id in replay["invocation_ids"]
    ] + [row["invocation_id"] for row in invocations]
    assert all(is_sha256(value) for value in all_ids)
    assert len(all_ids) == len(set(all_ids))
    decision = fixture["decision_input"]
    assert [row["comparator"] for row in decision["candidate_comparisons"]] == list(
        CHECKER_COMPARATORS
    )
    assert [row["falsifier"] for row in decision["falsifier_comparisons"]] == list(
        CHECKER_FALSIFIERS
    )


def independent_decision(value: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    candidate_repairs: dict[str, int] = {}
    for row in value["candidate_comparisons"]:
        comparator = row["comparator"]
        candidate_repairs[comparator] = row["candidate_primary_repairs"]
        if row["candidate_primary_repairs"] < 2:
            reasons.append(f"candidate_repairs_below_two_vs_{comparator}")
        for field in (
            "new_exact_misses",
            "new_related_misses",
            "no_relevant_gap_regressions",
            "per_mode_unrelated_intrusion_increases",
        ):
            if row[field] != 0:
                reasons.append(f"{field}_nonzero_vs_{comparator}")
        if Decimal(row["exact_mrr_absolute_loss"]) > Decimal("0.05"):
            reasons.append(f"exact_mrr_loss_exceeded_vs_{comparator}")
        if Decimal(row["related_mrr_absolute_loss"]) > Decimal("0.05"):
            reasons.append(f"related_mrr_loss_exceeded_vs_{comparator}")
    for row in value["falsifier_comparisons"]:
        falsifier = row["falsifier"]
        for comparator in CHECKER_COMPARATORS:
            repairs = row[f"repairs_vs_{comparator}"]
            if repairs > 1:
                reasons.append(f"{falsifier}_repairs_above_one_vs_{comparator}")
            if candidate_repairs[comparator] <= repairs:
                reasons.append(f"candidate_not_above_{falsifier}_vs_{comparator}")
    if reasons:
        return "SYNTHETIC_CANDIDATE_RULE_FAIL_NO_EXPERIMENT_AUTHORITY", reasons
    return "SYNTHETIC_CANDIDATE_RULE_PASS_NO_EXPERIMENT_AUTHORITY", []


def expected_receipt_payloads(
    fixture: dict[str, Any],
) -> list[tuple[str, str, dict[str, Any]]]:
    artifact = fixture["candidate_artifact"]
    development_digest = checker_sha256(artifact["development_lock"])
    final_digest = checker_sha256(artifact["final_lock"])
    sandbox = fixture["sandbox_attestation"]
    run = fixture["synthetic_run"]
    predecision = fixture["blinding"]["predecision"]
    decision, reasons = independent_decision(fixture["decision_input"])
    rows: list[tuple[str, str, dict[str, Any]]] = [
        (
            "agent_bridge.engram_g1_4_synthetic_candidate_lock_receipt.v0",
            "development_lock",
            {
                "lock_sha256": development_digest,
                "lock_kind": "development",
                "contract_sha256": digest(CONTRACT_PATH),
                "fixture_sha256": digest(FIXTURE_PATH),
                "implementation_sha256": digest(IMPLEMENTATION_PATH),
                "predecessor_commit": CONTRACT["predecessor_preregistration"]["commit"],
                "predecessor_contract_sha256": CONTRACT["predecessor_preregistration"][
                    "contract_sha256"
                ],
            },
        )
    ]
    for feedback in artifact["development_feedback_rounds"]:
        rows.append(
            (
                "agent_bridge.engram_g1_4_synthetic_candidate_lock_receipt.v0",
                "development_feedback",
                {
                    "round": feedback["round"],
                    "aggregate_receipt_sha256": feedback["aggregate_receipt_sha256"],
                },
            )
        )
    rows.extend(
        [
            (
                "agent_bridge.engram_g1_4_synthetic_candidate_lock_receipt.v0",
                "final_lock",
                {
                    "lock_sha256": final_digest,
                    "development_lock_sha256": development_digest,
                    "feedback_round_count": len(
                        artifact["development_feedback_rounds"]
                    ),
                },
            ),
            (
                "agent_bridge.engram_g1_4_synthetic_blinded_run_plan_receipt.v0",
                "blinded_run_plan",
                {
                    "arm_mapping_commitment_sha256": predecision[
                        "arm_mapping_commitment_sha256"
                    ],
                    "opaque_arm_count": len(CHECKER_OPAQUE_ARMS),
                    "final_lock_sha256": final_digest,
                    "synthetic_capability_sha256": run["synthetic_capability_sha256"],
                    "runner_sha256": sandbox["runner_sha256"],
                    "mapping_present": False,
                },
            ),
            (
                "agent_bridge.engram_g1_4_synthetic_sandbox_attestation_receipt.v0",
                "sandbox_attestation",
                {
                    "profile": sandbox["profile"],
                    "evidence_kind": sandbox["evidence_kind"],
                    "canary_count": len(CHECKER_CANARIES),
                    "all_canaries_match": True,
                    "native_enforcement_verified": False,
                    "resource_budget_sha256": sandbox["resource_budget_sha256"],
                    "mount_set_sha256": sandbox["mount_set_sha256"],
                    "environment_allowlist_sha256": sandbox[
                        "environment_allowlist_sha256"
                    ],
                    "output_schema_sha256": sandbox["output_schema_sha256"],
                    "runner_sha256": sandbox["runner_sha256"],
                },
            ),
            (
                "agent_bridge.engram_g1_4_synthetic_qualification_receipt.v0",
                "qualification",
                {
                    "replay_count": 2,
                    "outputs_identical": True,
                    "seed_schedule_commitment_sha256": fixture["qualification"][
                        "seed_schedule_commitment_sha256"
                    ],
                },
            ),
        ]
    )
    for invocation in run["invocations"]:
        rows.append(
            (
                "agent_bridge.engram_g1_4_synthetic_invocation_receipt.v0",
                "synthetic_run",
                {
                    "ordinal": invocation["ordinal"],
                    "opaque_arm_id": invocation["opaque_arm_id"],
                    "invocation_commitment_sha256": checker_sha256(invocation),
                    "status": "ok",
                    "scratch_destroyed": True,
                },
            )
        )
    rows.extend(
        [
            (
                "agent_bridge.engram_g1_4_synthetic_decision_receipt.v0",
                "decision",
                {
                    "decision": decision,
                    "reason_count": len(reasons),
                    "decision_frozen": True,
                    "mapping_present": False,
                },
            ),
            (
                "agent_bridge.engram_g1_4_synthetic_mapping_reveal_receipt.v0",
                "mapping_reveal",
                {
                    "arm_mapping_commitment_sha256": predecision[
                        "arm_mapping_commitment_sha256"
                    ],
                    "revealed_after_decision": True,
                    "public_receipt_contains_mapping": False,
                },
            ),
        ]
    )
    return rows


def build_expected_receipts(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    previous = "0" * 64
    for sequence, (schema, phase, payload) in enumerate(
        expected_receipt_payloads(fixture), start=1
    ):
        body = {
            "schema": schema,
            "sequence": sequence,
            "previous_sha256": previous,
            "phase": phase,
            "payload": copy.deepcopy(payload),
            "payload_sha256": checker_sha256(payload),
            "synthetic_only": True,
            "production_admissible": False,
        }
        event = {**body, "event_sha256": checker_sha256(body)}
        events.append(event)
        previous = event["event_sha256"]
    return events


def independent_verify_receipts(events: list[dict[str, Any]]) -> str:
    previous = "0" * 64
    expected_keys = {
        "schema",
        "sequence",
        "previous_sha256",
        "phase",
        "payload",
        "payload_sha256",
        "synthetic_only",
        "production_admissible",
        "event_sha256",
    }
    for sequence, event in enumerate(events, start=1):
        assert_exact_keys(event, expected_keys, f"receipt[{sequence - 1}]")
        assert event["sequence"] == sequence
        assert event["previous_sha256"] == previous
        assert type(event["payload"]) is dict
        assert event["payload_sha256"] == checker_sha256(event["payload"])
        assert event["synthetic_only"] is True
        assert event["production_admissible"] is False
        body = {key: value for key, value in event.items() if key != "event_sha256"}
        assert event["event_sha256"] == checker_sha256(body)
        previous = event["event_sha256"]
    return previous


def expect_error(code: str, action: Callable[[], Any]) -> HARNESS.HarnessError:
    try:
        action()
    except HARNESS.HarnessError as exc:
        assert exc.code == code, (code, exc.code, str(exc))
        return exc
    raise AssertionError(f"expected {code}")


def clone_with(path: tuple[Any, ...], replacement: Any) -> dict[str, Any]:
    value = copy.deepcopy(FIXTURE)
    cursor: Any = value
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = replacement
    return value


def walk(value: Any, path: tuple[Any, ...] = ()):
    yield path, value
    if type(value) is dict:
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))


def replace_at(value: Any, path: tuple[Any, ...], replacement: Any) -> Any:
    if not path:
        return replacement
    cursor = value
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = replacement
    return value


def assert_contract_and_raw_pins() -> int:
    assert digest(CONTRACT_PATH) == HARNESS.CONTRACT_SHA256
    assert digest(FIXTURE_PATH) == HARNESS.FIXTURE_SHA256
    assert digest(IMPLEMENTATION_PATH) == HARNESS.implementation_sha256()
    assert CONTRACT["registered_fixture"]["fixture_sha256"] == digest(FIXTURE_PATH)
    assert_independent_contract_schema()
    assert_independent_fixture_schema()
    HARNESS.validate_contract_semantics(copy.deepcopy(CONTRACT))
    HARNESS.validate_fixture_semantics(copy.deepcopy(FIXTURE))
    HARNESS.validate_predecessor_artifacts(REPO_ROOT)

    mutation_count = 0
    for path, current in list(walk(CONTRACT)):
        replacements: list[Any] = []
        if type(current) is dict:
            added = copy.deepcopy(current)
            added["unexpected_field"] = False
            replacements.append(added)
            if current:
                removed = copy.deepcopy(current)
                removed.pop(next(iter(removed)))
                replacements.append(removed)
            if path:
                replacements.append([])
        elif type(current) is list:
            replacements.extend(({}, current[:-1] if current else ["unexpected"]))
            if len(current) > 1 and list(reversed(current)) != current:
                replacements.append(list(reversed(current)))
        elif type(current) is bool:
            replacements.extend((not current, int(current)))
        elif type(current) is int:
            replacements.extend((current + 1, str(current)))
        elif type(current) is str:
            replacements.extend((current + "_mutated", False))
        else:
            raise AssertionError((path, type(current)))
        for replacement in replacements:
            candidate = replace_at(copy.deepcopy(CONTRACT), path, replacement)
            _expect_any_harness_error(
                lambda candidate=candidate: HARNESS.validate_contract_semantics(
                    candidate
                )
            )
            mutation_count += 1

    with tempfile.TemporaryDirectory(prefix="ab-g14-harness-check-") as raw_dir:
        scratch = Path(raw_dir)
        drift = scratch / "contract-byte-drift.json"
        drift.write_bytes(CONTRACT_PATH.read_bytes() + b"\n")
        expect_error(
            "E_RAW_PIN",
            lambda: HARNESS._read_pinned_json(
                drift, HARNESS.CONTRACT_SHA256, "contract"
            ),
        )
        fixture_drift = scratch / "fixture-byte-drift.json"
        fixture_drift.write_bytes(FIXTURE_PATH.read_bytes() + b"\n")
        expect_error(
            "E_RAW_PIN",
            lambda: HARNESS._read_pinned_json(
                fixture_drift, HARNESS.FIXTURE_SHA256, "fixture"
            ),
        )

    expect_error(
        "E_DUPLICATE_JSON_KEY",
        lambda: HARNESS.decode_closed_json(b'{"x":1,"x":2}', "duplicate"),
    )
    expect_error(
        "E_JSON_NUMBER",
        lambda: HARNESS.decode_closed_json(b'{"x":1.5}', "float"),
    )
    expect_error(
        "E_JSON_NUMBER",
        lambda: HARNESS.decode_closed_json(b'{"x":NaN}', "nan"),
    )
    expect_error("E_SCHEMA", lambda: HARNESS.decode_closed_json(b"[]", "root"))
    expect_error("E_JSON", lambda: HARNESS.decode_closed_json(b"\xff", "utf8"))
    assert mutation_count >= 250, mutation_count
    return mutation_count


def _expect_any_harness_error(action: Callable[[], Any]) -> HARNESS.HarnessError:
    try:
        action()
    except HARNESS.HarnessError as exc:
        return exc
    raise AssertionError("semantic mutation was accepted")


def assert_fixture_static_boundaries() -> None:
    static_mutations = (
        (("public_synthetic_fixture",), False),
        (("production_admissible",), True),
        (("synthetic_run", "real_freeze_capability_present"), True),
        (
            (
                "blinding",
                "predecision",
                "mapping_reveal_available_to_scorer_before_decision",
            ),
            True,
        ),
        (("sandbox_attestation", "canaries", 0, "name"), "private_read"),
        (("sandbox_attestation", "canaries", 0, "expected"), "deny"),
        (("sandbox_attestation", "resource_ceilings", "cpu_millis"), 0),
        (("sandbox_attestation", "native_enforcement_observed"), "yes"),
        (("synthetic_run", "invocations", 0, "status"), "retry"),
        (("synthetic_run", "invocations", 0, "scratch_destroyed"), 1),
    )
    for path, replacement in static_mutations:
        _expect_any_harness_error(
            lambda path=path, replacement=replacement: HARNESS.validate_fixture_semantics(
                clone_with(path, replacement)
            )
        )

    extra = copy.deepcopy(FIXTURE)
    extra["unexpected"] = False
    expect_error("E_SCHEMA", lambda: HARNESS.validate_fixture_semantics(extra))


def assert_lock_and_phase_state_machine() -> None:
    development_lock = FIXTURE["candidate_artifact"]["development_lock"]
    final_lock = FIXTURE["candidate_artifact"]["final_lock"]
    feedback = FIXTURE["candidate_artifact"]["development_feedback_rounds"]

    state = HARNESS.CandidateArtifactState()
    expect_error("E_PHASE", lambda: state.record_feedback(feedback[0]))
    expect_error("E_PHASE", lambda: state.register_final_lock(final_lock))
    state.register_development_lock(development_lock)
    expect_error(
        "E_LOCK_REPLAY", lambda: state.register_development_lock(development_lock)
    )
    state.record_feedback(feedback[0])
    state.record_feedback(feedback[1])
    expect_error(
        "E_FEEDBACK_BUDGET",
        lambda: state.record_feedback({"round": 3}),
    )
    state.register_final_lock(final_lock)
    expect_error("E_FINAL_LOCK", lambda: state.record_feedback(feedback[0]))
    expect_error("E_LOCK_REPLAY", lambda: state.register_final_lock(final_lock))
    drifted = copy.deepcopy(final_lock)
    drifted["source_tree_sha256"] = "0" * 64
    expect_error("E_FINAL_LOCK_DRIFT", lambda: state.assert_unchanged(drifted))

    phase = HARNESS.SyntheticProtocolHarness(enabled=True)
    expect_error("E_POLICY", lambda: phase._advance("mapping_reveal"))
    for expected in HARNESS.PHASES:
        phase._advance(expected)
    expect_error("E_PHASE", lambda: phase._advance("mapping_reveal"))


def dynamic_fault(
    path: tuple[Any, ...],
    replacement: Any,
    expected_code: str,
    *,
    rollback_succeeds: bool = True,
) -> None:
    candidate = clone_with(path, replacement)
    HARNESS.validate_fixture_semantics(copy.deepcopy(candidate))
    registry = HARNESS.SyntheticRunRegistry()
    harness = HARNESS.SyntheticProtocolHarness(
        enabled=True,
        registry=registry,
        rollback_succeeds=rollback_succeeds,
    )
    expect_error(expected_code, lambda: harness.exercise(candidate))
    run_id = FIXTURE["synthetic_run"]["run_id"]
    assert registry.states[run_id] == "INVALIDATED_NO_RETRY"
    assert harness.state == "INVALIDATED_NO_RETRY"
    if rollback_succeeds:
        assert registry.synthetic_lessons == []
    else:
        assert len(registry.synthetic_lessons) == 1
        assert registry.synthetic_lessons[0]["reason_code"] == expected_code
    retry = HARNESS.SyntheticProtocolHarness(enabled=True, registry=registry)
    expect_error("E_RUN_REPLAY", lambda: retry.exercise(copy.deepcopy(FIXTURE)))


def assert_sandbox_determinism_and_fault_invalidation() -> int:
    cases = [
        (("sandbox_attestation", "support_reported"), False, "E_SANDBOX_UNAVAILABLE"),
        (
            ("sandbox_attestation", "policy_apply_reported"),
            False,
            "E_SANDBOX_UNAVAILABLE",
        ),
        (("sandbox_attestation", "active_reported"), False, "E_SANDBOX_UNAVAILABLE"),
        (
            ("sandbox_attestation", "native_enforcement_observed"),
            True,
            "E_NATIVE_SANDBOX_CLAIM",
        ),
        (
            ("sandbox_attestation", "canaries", 0, "observed"),
            "deny",
            "E_SANDBOX_CANARY",
        ),
        (
            (
                "qualification",
                "replays",
                1,
                "ranked_output_commitments_by_opaque_arm",
                "arm_0",
                0,
            ),
            "f" * 64,
            "E_DETERMINISM",
        ),
        (
            ("qualification", "replays", 1, "invocation_ids", 0),
            FIXTURE["qualification"]["replays"][0]["invocation_ids"][0],
            "E_STATE_REUSE",
        ),
        (
            ("synthetic_run", "invocations", 1, "invocation_id"),
            FIXTURE["synthetic_run"]["invocations"][0]["invocation_id"],
            "E_STATE_REUSE",
        ),
        (
            ("synthetic_run", "invocations", 0, "invocation_id"),
            FIXTURE["qualification"]["replays"][0]["invocation_ids"][0],
            "E_STATE_REUSE",
        ),
        (("synthetic_run", "invocations", 0, "status"), "timeout", "E_INVOCATION"),
        (
            ("synthetic_run", "invocations", 0, "output_schema_valid"),
            False,
            "E_OUTPUT_SCHEMA",
        ),
        (
            ("synthetic_run", "invocations", 0, "scratch_destroyed"),
            False,
            "E_STATE_REUSE",
        ),
        (
            ("synthetic_run", "invocations", 0, "resource_budget_match"),
            False,
            "E_RESOURCE",
        ),
        (
            ("blinding", "predecision", "arm_mapping_commitment_sha256"),
            "0" * 64,
            "E_ARM_MAPPING_COMMITMENT",
        ),
    ]
    for index, (path, replacement, code) in enumerate(cases):
        dynamic_fault(
            path,
            replacement,
            code,
            rollback_succeeds=index != 0,
        )
    return len(cases)


def assert_decision_rule() -> int:
    decision = copy.deepcopy(FIXTURE["decision_input"])
    verdict, reasons = HARNESS.evaluate_decision(decision)
    assert (verdict, reasons) == independent_decision(decision)

    failures = 0

    def rejected(mutator: Callable[[dict[str, Any]], None], needle: str) -> None:
        nonlocal failures
        candidate = copy.deepcopy(decision)
        mutator(candidate)
        result, result_reasons = HARNESS.evaluate_decision(candidate)
        assert (result, result_reasons) == independent_decision(candidate)
        assert result == "SYNTHETIC_CANDIDATE_RULE_FAIL_NO_EXPERIMENT_AUTHORITY"
        assert any(needle in reason for reason in result_reasons), result_reasons
        failures += 1

    rejected(
        lambda value: value["candidate_comparisons"][0].update(
            candidate_primary_repairs=1
        ),
        "candidate_repairs_below_two",
    )
    for field in (
        "new_exact_misses",
        "new_related_misses",
        "no_relevant_gap_regressions",
        "per_mode_unrelated_intrusion_increases",
    ):
        rejected(
            lambda value, field=field: value["candidate_comparisons"][0].update(
                {field: 1}
            ),
            field,
        )
    for field, needle in (
        ("exact_mrr_absolute_loss", "exact_mrr_loss_exceeded"),
        ("related_mrr_absolute_loss", "related_mrr_loss_exceeded"),
    ):
        rejected(
            lambda value, field=field: value["candidate_comparisons"][0].update(
                {field: "0.051"}
            ),
            needle,
        )
    rejected(
        lambda value: value["falsifier_comparisons"][0].update(
            repairs_vs_stable_control=2
        ),
        "repairs_above_one",
    )

    boundary = copy.deepcopy(decision)
    boundary["candidate_comparisons"][0]["exact_mrr_absolute_loss"] = "0.05"
    boundary["candidate_comparisons"][0]["related_mrr_absolute_loss"] = "0.05"
    boundary_verdict, boundary_reasons = HARNESS.evaluate_decision(boundary)
    assert (boundary_verdict, boundary_reasons) == independent_decision(boundary)
    assert boundary_verdict.endswith("PASS_NO_EXPERIMENT_AUTHORITY")
    assert boundary_reasons == []

    for field, replacement in (
        ("paired_by_episode_group", False),
        ("sealed_shape_is_decisive", False),
        ("fit_or_development_used_for_final_verdict", True),
    ):
        malformed = copy.deepcopy(decision)
        malformed[field] = replacement
        expect_error(
            "E_POLICY", lambda malformed=malformed: HARNESS.evaluate_decision(malformed)
        )
    return failures


def assert_scorer_custody_split() -> None:
    captured: dict[str, Any] = {}
    original = HARNESS.SyntheticProtocolHarness._exercise_predecision

    def capture_view(instance: Any, scorer_view: dict[str, Any]) -> None:
        captured["scorer_view"] = copy.deepcopy(scorer_view)
        original(instance, scorer_view)

    HARNESS.SyntheticProtocolHarness._exercise_predecision = capture_view
    try:
        harness = HARNESS.SyntheticProtocolHarness(enabled=True)
        harness.exercise(copy.deepcopy(FIXTURE))
    finally:
        HARNESS.SyntheticProtocolHarness._exercise_predecision = original

    scorer_view = captured["scorer_view"]
    assert "decision_input" not in scorer_view
    assert "expected" not in scorer_view
    assert set(scorer_view["blinding"]) == {
        "arm_mapping_commitment_sha256",
        "opaque_arm_ids_in_execution_order",
        "scorer_visible_arm_ids",
        "mapping_reveal_available_to_scorer_before_decision",
    }
    scorer_bytes = checker_canonical_bytes(scorer_view)
    for semantic_arm in CHECKER_ARM_MAPPING.values():
        assert semantic_arm.encode("utf-8") not in scorer_bytes

    expected_events = build_expected_receipts(FIXTURE)
    expected_scoring_head = independent_verify_receipts(expected_events[:12])
    custodian = HARNESS.SyntheticProtocolCustodian(
        CHECKER_ARM_MAPPING,
        checker_sha256(CHECKER_ARM_MAPPING),
        FIXTURE["decision_input"],
        expected_scoring_head,
    )
    custodian.validate_precommitment()
    expect_error("E_PHASE", lambda: custodian.decide_after_scoring([]))
    expect_error("E_DECISION_STATE", lambda: custodian.reveal_after_decision([]))
    forged_decision_only = HARNESS.ReceiptChain()
    forged_decision_only.append(
        "agent_bridge.engram_g1_4_synthetic_decision_receipt.v0",
        "decision",
        {
            "decision": "SYNTHETIC_CANDIDATE_RULE_PASS_NO_EXPERIMENT_AUTHORITY",
            "reason_count": 0,
            "decision_frozen": True,
            "mapping_present": False,
        },
    )
    expect_error(
        "E_DECISION_STATE",
        lambda: custodian.reveal_after_decision(forged_decision_only.events),
    )

    decision, reasons = custodian.decide_after_scoring(expected_events[:12])
    assert (decision, reasons) == independent_decision(FIXTURE["decision_input"])
    expect_error(
        "E_DECISION_REPLAY",
        lambda: custodian.decide_after_scoring(expected_events[:12]),
    )
    assert custodian.reveal_after_decision(expected_events[:13]) == CHECKER_ARM_MAPPING
    expect_error(
        "E_REVEAL_REPLAY",
        lambda: custodian.reveal_after_decision(expected_events[:13]),
    )

    fully_rehashed_forgery = copy.deepcopy(expected_events[:12])
    fully_rehashed_forgery[0]["payload"]["lock_kind"] = "forged"
    previous = "0" * 64
    for event in fully_rehashed_forgery:
        event["previous_sha256"] = previous
        event["payload_sha256"] = checker_sha256(event["payload"])
        body = {key: value for key, value in event.items() if key != "event_sha256"}
        event["event_sha256"] = checker_sha256(body)
        previous = event["event_sha256"]
    assert independent_verify_receipts(fully_rehashed_forgery) == previous
    assert previous != expected_scoring_head
    forged_custodian = HARNESS.SyntheticProtocolCustodian(
        CHECKER_ARM_MAPPING,
        checker_sha256(CHECKER_ARM_MAPPING),
        FIXTURE["decision_input"],
        expected_scoring_head,
    )
    forged_custodian.validate_precommitment()
    expect_error(
        "E_RECEIPT_ANCHOR",
        lambda: forged_custodian.decide_after_scoring(fully_rehashed_forgery),
    )


def assert_receipts_one_shot_and_lessons() -> None:
    first_registry = HARNESS.SyntheticRunRegistry()
    first = HARNESS.SyntheticProtocolHarness(enabled=True, registry=first_registry)
    first_result = first.exercise(copy.deepcopy(FIXTURE))
    second = HARNESS.SyntheticProtocolHarness(enabled=True)
    second_result = second.exercise(copy.deepcopy(FIXTURE))
    expected_events = build_expected_receipts(FIXTURE)
    assert first.receipts.events == second.receipts.events == expected_events
    expected_head = independent_verify_receipts(expected_events)
    assert (
        first_result["receipt_chain_head_sha256"]
        == second_result["receipt_chain_head_sha256"]
        == expected_head
    )
    assert (
        HARNESS.ReceiptChain.verify(first.receipts.events)
        == first_result["receipt_chain_head_sha256"]
    )
    assert len(first.receipts.events) == 14
    assert all(event["synthetic_only"] is True for event in first.receipts.events)
    assert all(
        event["production_admissible"] is False for event in first.receipts.events
    )
    phases = [event["phase"] for event in first.receipts.events]
    assert phases.index("decision") < phases.index("mapping_reveal")
    serialized = json.dumps(first.receipts.events, sort_keys=True)
    for real_arm_name in CHECKER_ARM_MAPPING.values():
        assert real_arm_name not in serialized

    reordered = copy.deepcopy(first.receipts.events)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    _expect_any_harness_error(lambda: HARNESS.ReceiptChain.verify(reordered))
    tampered = copy.deepcopy(first.receipts.events)
    tampered[3]["phase"] = "synthetic_run"
    _expect_any_harness_error(lambda: HARNESS.ReceiptChain.verify(tampered))
    payload_tampered = copy.deepcopy(first.receipts.events)
    payload_tampered[0]["payload"]["lock_kind"] = "forged"
    _expect_any_harness_error(lambda: HARNESS.ReceiptChain.verify(payload_tampered))

    forged = copy.deepcopy(expected_events)
    forged[0]["payload"]["lock_kind"] = "forged"
    previous = "0" * 64
    for event in forged:
        event["previous_sha256"] = previous
        event["payload_sha256"] = checker_sha256(event["payload"])
        body = {key: value for key, value in event.items() if key != "event_sha256"}
        event["event_sha256"] = checker_sha256(body)
        previous = event["event_sha256"]
    assert independent_verify_receipts(forged) == previous
    assert forged != expected_events
    assert previous != expected_head

    run_id = FIXTURE["synthetic_run"]["run_id"]
    assert first_registry.states[run_id] == "COMPLETED_SYNTHETIC_NO_AUTHORITY"
    retry = HARNESS.SyntheticProtocolHarness(enabled=True, registry=first_registry)
    expect_error("E_RUN_REPLAY", lambda: retry.exercise(copy.deepcopy(FIXTURE)))

    no_lesson = HARNESS.SyntheticRunRegistry()
    no_lesson.claim("synthetic-rollback-ok")
    no_lesson.invalidate("synthetic-rollback-ok", "E_TEST")
    assert no_lesson.synthetic_lessons == []

    lesson_registry = HARNESS.SyntheticRunRegistry()
    lesson_registry.claim("synthetic-rollback-failed")
    lesson_registry.invalidate(
        "synthetic-rollback-failed", "E_ROLLBACK", rollback_succeeded=False
    )
    assert lesson_registry.states["synthetic-rollback-failed"] == (
        "INVALIDATED_NO_RETRY"
    )
    assert len(lesson_registry.synthetic_lessons) == 1
    lesson = lesson_registry.synthetic_lessons[0]
    assert set(lesson) == {
        "schema",
        "run_commitment_sha256",
        "reason_code",
        "synthetic_only",
        "durable_in_real_implementation_required",
        "production_admissible",
    }
    assert lesson["reason_code"] == "E_ROLLBACK"
    assert lesson["synthetic_only"] is True
    assert lesson["durable_in_real_implementation_required"] is True
    assert lesson["production_admissible"] is False
    assert "synthetic-rollback-failed" not in json.dumps(lesson, sort_keys=True)


def assert_cli_and_zero_authority() -> None:
    disabled = subprocess.run(
        [sys.executable, str(IMPLEMENTATION_PATH), "exercise"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert disabled.returncode == 2
    assert "E_DEFAULT_OFF" in disabled.stderr

    commands = [
        sys.executable,
        str(IMPLEMENTATION_PATH),
        "exercise",
        "--enable-public-synthetic",
    ]
    first = subprocess.run(commands, text=True, capture_output=True, check=False)
    second = subprocess.run(commands, text=True, capture_output=True, check=False)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    receipt = json.loads(first.stdout)
    assert receipt["verdict"] == "PASS_PUBLIC_SYNTHETIC_PROTOCOL_HARNESS_NO_AUTHORITY"
    assert receipt["receipt_count"] == 14
    assert receipt["only_permitted_successor"] == HARNESS.ONLY_PERMITTED_SUCCESSOR
    assert receipt["public_synthetic_protocol_harness_implemented"] is True
    for field, value in receipt.items():
        if field == "public_synthetic_protocol_harness_implemented":
            continue
        if (
            field.endswith("_authority")
            or field.endswith("_verified")
            or field.endswith("_present")
            or field.endswith("_executed")
            or field.endswith("_open")
            or field
            in {
                "native_sandbox_enforcement_implemented",
                "production_admissible",
                "private_corpus_accessed",
                "real_freeze_capability_consumed",
            }
        ):
            assert value is False, (field, value)

    contract_result = subprocess.run(
        [sys.executable, str(IMPLEMENTATION_PATH), "validate-contract"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert contract_result.returncode == 0
    contract_receipt = json.loads(contract_result.stdout)
    assert contract_receipt["production_admissible"] is False
    assert contract_receipt["g1_4_execution_open"] is False


def assert_static_no_runtime_or_native_sandbox_surface() -> None:
    source = IMPLEMENTATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned_import_roots = {
        "ctypes",
        "http",
        "multiprocessing",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
        "urllib",
    }
    banned_calls = {
        "exec",
        "eval",
        "fork",
        "open_connection",
        "Popen",
        "run",
        "system",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in banned_import_roots
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".", 1)[0] not in banned_import_roots
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in banned_calls
            elif isinstance(node.func, ast.Attribute):
                assert node.func.attr not in banned_calls

    help_result = subprocess.run(
        [sys.executable, str(IMPLEMENTATION_PATH), "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert help_result.returncode == 0
    for forbidden_option in (
        "--candidate",
        "--contract",
        "--fixture",
        "--freeze",
        "--key",
        "--manifest",
        "--private",
    ):
        assert forbidden_option not in help_result.stdout
    assert "sandbox-exec" not in source
    assert "landlock_restrict_self" not in source
    assert "seatbelt_apply" not in source

    runtime_matches = []
    for path in (REPO_ROOT / "crates").rglob("*"):
        if path.is_file() and path.suffix in {".rs", ".toml"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if (
                "engram_g14_public_synthetic_protocol_harness" in text
                or "PUBLIC_SYNTHETIC_PROTOCOL_KAT" in text
            ):
                runtime_matches.append(str(path.relative_to(REPO_ROOT)))
    assert runtime_matches == [], runtime_matches


def main() -> int:
    mutation_count = assert_contract_and_raw_pins()
    assert_fixture_static_boundaries()
    assert_lock_and_phase_state_machine()
    fault_count = assert_sandbox_determinism_and_fault_invalidation()
    decision_failure_count = assert_decision_rule()
    assert_scorer_custody_split()
    assert_receipts_one_shot_and_lessons()
    assert_cli_and_zero_authority()
    assert_static_no_runtime_or_native_sandbox_surface()
    print(
        "engram G1.4 public synthetic protocol harness adversarial checks: PASS "
        f"(contract_mutations={mutation_count}, fault_cases={fault_count}, "
        f"decision_guards={decision_failure_count})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
