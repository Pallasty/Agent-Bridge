#!/usr/bin/env python3
"""Validate the source-only Track B real-run admission policy v1.

This is a closed-world successor policy validator.  It does not create a
runtime admission state, read private trial artifacts, or unlock any side
effect.  Historical v0 replay and new-trial v1 validation remain separate
explicit routes.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable


POLICY_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v1.json"
)
SCHEMA = "agent_bridge.biocortex_ab_track_b_real_run_admission_policy.v1"
STATUS = "BLOCKED_FAIL_CLOSED_SOURCE_COMPATIBILITY_ONLY"
DECISION = "SUCCESSOR_V1_SOURCE_INTERFACE_AVAILABLE_REAL_RUN_NOT_ADMITTED"
BASELINE_COMMIT = "2e828d7b86444770c3ef3cd40ac17f26cac6fb0e"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")

RECEIPT_REQUIRED = [
    "anti_shopping_order_verified",
    "case_inclusion_probabilities",
    "case_sampling_weights",
    "condition_output_authorized",
    "contract_digest_profile_sha256",
    "contract_sha256",
    "created_at_utc",
    "eligible_frame_manifest_sha256",
    "external_entropy_sha256",
    "frame_o_excl_receipt_sha256",
    "pre_output_timing_verified",
    "receipt_precedes_first_condition_output",
    "receipt_schema_sha256",
    "receipt_writer_sha256",
    "reserve_manifest_sha256",
    "sampling_seed_sha256",
    "sampling_selection_algorithm_sha256",
    "sampling_selection_domain",
    "sampling_selection_message",
    "schema",
    "seed_derivation_domain",
    "seed_derivation_message_profile",
    "seed_derivation_sha256",
    "seed_entropy_receipt_sha256",
    "selected_case_manifest_sha256",
    "selection_commitment_sha256",
    "strata_allocation_manifest_sha256",
    "trial_id",
]

EXPECTED_BLOCKERS = [
    "ADMISSION_POLICY_NOT_LIVE_BOUND",
    "CONTRACT_CORE_INSTANCE_NOT_FROZEN",
    "FRAME_STRATA_AND_ENTROPY_CUSTODY_UNATTESTED",
    "SAMPLING_ATTEMPT_NAMESPACE_GLOBAL_SINGLE_USE_UNENFORCED",
    "SAMPLING_WRITE_OUTCOME_CUSTODIAN_RECEIPT_UNBOUND",
    "TRUSTED_CLOCK_AND_PRE_OUTPUT_ORDER_UNATTESTED",
    "ANTI_SHOPPING_ORDER_UNATTESTED",
    "FIRST_CONDITION_OUTPUT_GUARD_UNBOUND",
    "MAP_V1_NOT_LIVE_BOUND",
    "MAP_CONSUMPTION_SINGLE_USE_UNENFORCED",
    "RUNTIME_SOURCE_AND_BINARY_PROVENANCE_UNBOUND",
    "OWNER_POLICY_BINDINGS_UNSET",
    "FROZEN_GRAPH_LEDGER_AND_ADMISSION_V0_REMAIN_NON_ADMITTING",
]

SOURCE_HASHES = {
    "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json":
        "ad40df50eec68fa192c79e6699a8d2da2a9c3925a387eaa7427f7e19f996d783",
    "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v1.json":
        "475f5c518df83049808e0a118f50ef83026b8c8202bebfd4439dfb9c416fd724",
    "docs/design/fixtures/biocortex-ab-track-b-sampling-contract-digest-profile-v0.json":
        "a8972ad5e75b30634931fee84f08226e2660413b45cf9dfea948089d61160243",
    "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json":
        "9e73afee2f6366a241b155680b4f77341adeb7c4e341ab91b8d4b1499b5aacbd",
    "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v1.json":
        "e418b58246eaf183b5624c7eb12299caeea933c83a07584faa915651b3cd48d4",
    "scripts/eval/biocortex_ab_track_b_map_bijection_v0.py":
        "45f55cea933ee12df402fbb55d27ea7c6cd08ba8eef9d9868e4e491dd62a2cd2",
    "scripts/eval/biocortex_ab_track_b_map_bijection_v1.py":
        "92926f3e01910501e20a7d5f8f9b0cab79e28ca38ae2717966b8b6977fa89e58",
    "scripts/eval/biocortex_ab_track_b_sampling_receipt_writer_v0.py":
        "a8642d2b524183e060eb2f2c16d3a4bba4bca43c8e18b8524bc14738d4f6d975",
    "scripts/eval/check_biocortex_ab_track_b_admission.py":
        "b09b10243f195299dc226b5d8d2b484ec74f5eecd49bb487296c391f6f193b13",
    "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json":
        "8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af",
    "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json":
        "764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341a",
    "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json":
        "1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e",
}


class AdmissionV1Error(RuntimeError):
    pass


def fail(message: str) -> None:
    raise AdmissionV1Error(message)


def reject_constant(value: str) -> Any:
    fail(f"non-finite JSON constant {value!r}")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


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


def load_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read {label}: {exc}")
    if type(value) is not dict or canonical_bytes(value) != raw:
        fail(f"{label} is not a canonical object")
    return value, raw


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        fail(f"{label} field set drift")
    return value


def require(value: bool, message: str) -> None:
    if not value:
        fail(message)


def require_sha(value: Any, label: str) -> str:
    if type(value) is not str or SHA_RE.fullmatch(value) is None:
        fail(f"{label} is not lowercase SHA-256")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_sources(root: Path, policy: dict[str, Any]) -> None:
    for relative, expected in SOURCE_HASHES.items():
        path = root / relative
        require(path.is_file() and not path.is_symlink(), f"source missing: {relative}")
        require(sha256_file(path) == expected, f"source hash drift: {relative}")
    require(
        policy["map_interface"]["checker_sha256"]
        == SOURCE_HASHES["scripts/eval/biocortex_ab_track_b_map_bijection_v1.py"],
        "policy map checker binding drift",
    )


def validate_policy(policy: dict[str, Any], root: Path | None = None) -> None:
    exact_keys(
        policy,
        {
            "authority",
            "baseline_commit",
            "blockers",
            "contract_id",
            "contract_identity",
            "data_quality",
            "date",
            "decision",
            "dynamic_state",
            "live_binding",
            "map_interface",
            "protocol_migration",
            "sampling_interface",
            "sampling_single_use",
            "schema",
            "stages",
            "status",
        },
        "policy",
    )
    require(policy["schema"] == SCHEMA, "policy schema drift")
    require(policy["status"] == STATUS, "policy status drift")
    require(policy["decision"] == DECISION, "policy decision drift")
    require(policy["baseline_commit"] == BASELINE_COMMIT, "baseline commit drift")
    require(policy["date"] == "2026-07-14", "policy date drift")
    require(
        policy["contract_id"]
        == "biocortex_ab_track_b_real_run_admission_policy_20260714_v1",
        "contract id drift",
    )
    require(policy["blockers"] == EXPECTED_BLOCKERS, "blocker catalog drift")

    authority = exact_keys(
        policy["authority"],
        {
            "capture",
            "condition_output",
            "generation",
            "real_run",
            "review",
            "scoring",
            "scientific_claim",
            "unblinding",
        },
        "authority",
    )
    require(all(value is False for value in authority.values()), "authority raised")

    identity = exact_keys(
        policy["contract_identity"],
        {
            "admission_policy_sha256_binding_required",
            "contract_core_schema",
            "contract_digest_profile_path",
            "contract_digest_profile_sha256",
            "contract_sha256_semantics",
            "dynamic_runtime_state_inside_contract_core",
            "policy_to_core_binding_direction",
            "transitive_policy_cycle_check_required_before_live_binding",
        },
        "contract_identity",
    )
    require(identity == {
        "admission_policy_sha256_binding_required": True,
        "contract_core_schema": "agent_bridge.biocortex_ab_track_b_sampling_contract_core.v0",
        "contract_digest_profile_path": "docs/design/fixtures/biocortex-ab-track-b-sampling-contract-digest-profile-v0.json",
        "contract_digest_profile_sha256": "a8972ad5e75b30634931fee84f08226e2660413b45cf9dfea948089d61160243",
        "contract_sha256_semantics": "SHA256_OF_EXACT_CANONICAL_SAMPLING_CONTRACT_CORE_BYTES_NOT_ADMISSION_PACKET_BYTES",
        "dynamic_runtime_state_inside_contract_core": False,
        "policy_to_core_binding_direction": "CONTRACT_CORE_ADMISSION_POLICY_SHA256_EQUALS_EXACT_POLICY_BYTES",
        "transitive_policy_cycle_check_required_before_live_binding": True,
    }, "contract identity semantics drift")

    migration = exact_keys(
        policy["protocol_migration"],
        {
            "automatic_upcast_or_downcast",
            "cross_version_artifact_join_allowed",
            "cross_version_trial_identity_reuse_allowed",
            "current_protocol_version",
            "default_protocol_when_missing",
            "historical_v0",
            "new_trials_require_v1",
            "routing_key",
            "validation_failure_fallback_allowed",
        },
        "protocol_migration",
    )
    require(migration["current_protocol_version"] == 1, "protocol version drift")
    require(migration["default_protocol_when_missing"] is None, "default protocol exists")
    for field in (
        "automatic_upcast_or_downcast",
        "cross_version_artifact_join_allowed",
        "cross_version_trial_identity_reuse_allowed",
        "validation_failure_fallback_allowed",
    ):
        require(migration[field] is False, f"migration {field} raised")
    require(migration["new_trials_require_v1"] is True, "new trials do not require v1")
    require(
        migration["routing_key"]
        == "EXACT_REQUEST_SCHEMA_THEN_EXACT_ARTIFACT_VERSION_TUPLE_NO_ALIAS",
        "version routing drift",
    )
    historical = exact_keys(
        migration["historical_v0"],
        {
            "admission_checker_path",
            "admission_checker_sha256",
            "admission_contract_path",
            "admission_contract_sha256",
            "blind_map_schema_sha256",
            "frozen_replay_commit",
            "historical_validation_only",
            "map_checker_sha256",
            "receipt_schema_sha256",
            "side_effects_unlocked",
        },
        "historical_v0",
    )
    require(historical == {
        "admission_checker_path": "scripts/eval/check_biocortex_ab_track_b_admission.py",
        "admission_checker_sha256": SOURCE_HASHES["scripts/eval/check_biocortex_ab_track_b_admission.py"],
        "admission_contract_path": "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json",
        "admission_contract_sha256": SOURCE_HASHES["scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"],
        "blind_map_schema_sha256": SOURCE_HASHES["docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json"],
        "frozen_replay_commit": "59869af57f2a0b24647f3b47d7bea93839bfbefe",
        "historical_validation_only": True,
        "map_checker_sha256": SOURCE_HASHES["scripts/eval/biocortex_ab_track_b_map_bijection_v0.py"],
        "receipt_schema_sha256": SOURCE_HASHES["docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json"],
        "side_effects_unlocked": "NONE",
    }, "historical v0 boundary drift")

    sampling = exact_keys(
        policy["sampling_interface"],
        {
            "anti_shopping_order_verified",
            "condition_output_authorized",
            "contract_digest_profile_sha256",
            "pre_output_timing_verified",
            "receipt_instance_schema",
            "receipt_schema_path",
            "receipt_schema_sha256",
            "receipt_writer_path",
            "receipt_writer_sha256",
            "required_receipt_bindings",
            "sampling_seed_derivation_sha256",
            "sampling_selection_algorithm_sha256",
            "selected_manifest_schema",
        },
        "sampling_interface",
    )
    for field in (
        "anti_shopping_order_verified",
        "condition_output_authorized",
        "pre_output_timing_verified",
    ):
        require(sampling[field] is False, f"sampling {field} raised")
    require(sampling["required_receipt_bindings"] == RECEIPT_REQUIRED, "receipt fields drift")
    require(sampling["receipt_instance_schema"] == "agent_bridge.biocortex_ab_track_b_sampling_receipt.v1", "receipt instance drift")
    require(sampling["receipt_schema_path"] == "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v1.json", "receipt schema path drift")
    require(sampling["receipt_writer_path"] == "scripts/eval/biocortex_ab_track_b_sampling_receipt_writer_v0.py", "receipt writer path drift")
    require(sampling["receipt_schema_sha256"] == SOURCE_HASHES["docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v1.json"], "receipt schema binding drift")
    require(sampling["receipt_writer_sha256"] == SOURCE_HASHES["scripts/eval/biocortex_ab_track_b_sampling_receipt_writer_v0.py"], "receipt writer binding drift")
    require(sampling["contract_digest_profile_sha256"] == SOURCE_HASHES["docs/design/fixtures/biocortex-ab-track-b-sampling-contract-digest-profile-v0.json"], "digest profile binding drift")
    require(sampling["sampling_seed_derivation_sha256"] == "4f51781ff707e89b4c09adffeafbdaacd75c7e1571d1a86e45d336aace888a3f", "seed source binding drift")
    require(sampling["sampling_selection_algorithm_sha256"] == "e327faf2ad73718dc33f68fdb66a89abf0ac84fbbf8d828ff79fa0e8b75772ec", "selection source binding drift")
    require(sampling["selected_manifest_schema"] == "agent_bridge.biocortex_ab_track_b_selected_case_manifest_source_profile.v0", "selected schema drift")

    map_interface = exact_keys(
        policy["map_interface"],
        {
            "accepted_blind_map_schema",
            "accepted_receipt_schema",
            "accepted_selected_manifest_schema",
            "blind_map_schema_path",
            "blind_map_schema_sha256",
            "checker_path",
            "checker_sha256",
            "condition_output_authority_from_map_validation",
            "cross_version_fallback_allowed",
            "identity_derivation_domain",
            "request_schema",
            "result_schema",
            "v0_map_or_receipt_accepted",
        },
        "map_interface",
    )
    require(map_interface["accepted_blind_map_schema"] == "agent_bridge.biocortex_ab_track_b_blind_map.v1", "map schema tuple drift")
    require(map_interface["accepted_receipt_schema"] == "agent_bridge.biocortex_ab_track_b_sampling_receipt.v1", "map receipt tuple drift")
    require(map_interface["accepted_selected_manifest_schema"] == sampling["selected_manifest_schema"], "map selected tuple drift")
    require(map_interface["blind_map_schema_path"] == "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v1.json", "map schema path drift")
    require(map_interface["checker_path"] == "scripts/eval/biocortex_ab_track_b_map_bijection_v1.py", "map checker path drift")
    require(map_interface["blind_map_schema_sha256"] == SOURCE_HASHES["docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v1.json"], "map schema hash drift")
    require(map_interface["checker_sha256"] == SOURCE_HASHES["scripts/eval/biocortex_ab_track_b_map_bijection_v1.py"], "map checker hash drift")
    require(map_interface["identity_derivation_domain"] == "agent-bridge/track-b/blind-map/v2", "identity domain drift")
    require(map_interface["request_schema"] == "agent_bridge.biocortex_ab_track_b_map_bijection_request.v1", "map request schema drift")
    require(map_interface["result_schema"] == "agent_bridge.biocortex_ab_track_b_map_bijection_validation_result.v1", "map result schema drift")
    for field in (
        "condition_output_authority_from_map_validation",
        "cross_version_fallback_allowed",
        "v0_map_or_receipt_accepted",
    ):
        require(map_interface[field] is False, f"map boundary {field} raised")

    single_use = exact_keys(
        policy["sampling_single_use"],
        {
            "abort_is_terminal_for_same_attempt_namespace",
            "attempt_namespace_excludes_contract_core_frame_allocation_and_external_entropy",
            "contract_core_frame_or_allocation_change_within_attempt_namespace_forbidden",
            "event_identity_excludes_external_entropy",
            "global_single_use_verified",
            "new_attempt_requires_new_trial_and_owner_refreeze",
            "one_exact_policy_contract_core_frame_allocation_and_event_per_attempt_namespace_required",
            "owner_issued_globally_unique_trial_id_required_before_claim",
            "sampling_attempt_namespace_domain",
            "sampling_attempt_namespace_message",
            "sampling_event_domain",
            "sampling_event_message",
        },
        "sampling_single_use",
    )
    require(single_use == {
        "abort_is_terminal_for_same_attempt_namespace": True,
        "attempt_namespace_excludes_contract_core_frame_allocation_and_external_entropy": True,
        "contract_core_frame_or_allocation_change_within_attempt_namespace_forbidden": True,
        "event_identity_excludes_external_entropy": True,
        "global_single_use_verified": False,
        "new_attempt_requires_new_trial_and_owner_refreeze": True,
        "one_exact_policy_contract_core_frame_allocation_and_event_per_attempt_namespace_required": True,
        "owner_issued_globally_unique_trial_id_required_before_claim": True,
        "sampling_attempt_namespace_domain": "agent-bridge/track-b/sampling-attempt-namespace/v1",
        "sampling_attempt_namespace_message": "domain_utf8_NUL_trial_id_utf8",
        "sampling_event_domain": "agent-bridge/track-b/sampling-event/v1",
        "sampling_event_message": "domain_utf8_NUL_contract_core_sha256_ascii_NUL_trial_id_utf8_NUL_eligible_frame_sha256_ascii_NUL_strata_allocation_sha256_ascii",
    }, "sampling single-use policy drift")

    live = exact_keys(
        policy["live_binding"],
        {
            "active_v0_admission_mutated",
            "condition_output_authorized",
            "frozen_graph_mutated",
            "frozen_ledger_mutated",
            "graph_source_candidate_count",
            "graph_source_candidate_total",
            "live_binding_satisfied_count",
            "new_graph_binding_path_count",
            "real_run_admitted",
            "side_effects_unlocked",
        },
        "live_binding",
    )
    require(live == {
        "active_v0_admission_mutated": False,
        "condition_output_authorized": False,
        "frozen_graph_mutated": False,
        "frozen_ledger_mutated": False,
        "graph_source_candidate_count": 13,
        "graph_source_candidate_total": 13,
        "live_binding_satisfied_count": 0,
        "new_graph_binding_path_count": 0,
        "real_run_admitted": False,
        "side_effects_unlocked": "NONE",
    }, "live-binding boundary drift")

    state = exact_keys(
        policy["dynamic_state"],
        {
            "admission_attempt_id",
            "condition_output_guard_receipt_sha256",
            "contract_core_sha256",
            "map_bijection_receipt_sha256",
            "map_consumption_receipt_sha256",
            "owner_trial_registration_receipt_sha256",
            "sampling_attempt_namespace_claim_receipt_sha256",
            "sampling_receipt_sha256",
            "sampling_write_outcome_custodian_receipt_sha256",
            "schema",
            "status",
            "trusted_clock_receipt_sha256",
        },
        "dynamic_state",
    )
    require(state["schema"] == "agent_bridge.biocortex_ab_track_b_real_run_admission_state.v1", "state schema drift")
    require(state["status"] == "NO_RUNTIME_INSTANCE_SOURCE_TEMPLATE_ONLY", "state status drift")
    require(all(value is None for key, value in state.items() if key not in {"schema", "status"}), "runtime state populated")

    stages = exact_keys(policy["stages"], {"post_generation_map_validation", "pre_output_admission", "pre_review"}, "stages")
    require(stages["post_generation_map_validation"] == {
        "side_effects_unlocked": "NONE",
        "status": "SOURCE_VALIDATOR_AVAILABLE_NOT_LIVE_BOUND",
    }, "map stage drift")
    require(stages["pre_output_admission"] == {
        "required_missing_evidence": [
            "owner_trial_registration_receipt_sha256",
            "sampling_attempt_namespace_claim_receipt_sha256",
            "sampling_write_outcome_custodian_receipt_sha256",
            "trusted_clock_receipt_sha256",
            "condition_output_guard_receipt_sha256",
        ],
        "side_effects_unlocked": "NONE",
        "status": "BLOCKED_FAIL_CLOSED",
    }, "pre-output stage drift")
    require(stages["pre_review"] == {
        "required_missing_evidence": [
            "map_bijection_receipt_sha256",
            "map_consumption_receipt_sha256",
        ],
        "side_effects_unlocked": "NONE",
        "status": "BLOCKED_FAIL_CLOSED",
    }, "pre-review stage drift")

    quality = exact_keys(policy["data_quality"], {"exact_grains", "join_rules"}, "data_quality")
    require(quality == {
        "exact_grains": {
            "blind_map_assignment": "protocol_version_x_trial_id_x_case_id_x_opaque_answer_id",
            "contract_core": "protocol_version_x_trial_id",
            "owner_trial_registration": "global_track_b_trial_registry_x_trial_id",
            "sampling_attempt_namespace": "protocol_version_x_trial_id",
            "sampling_event": "protocol_version_x_trial_id_x_contract_core_sha256_x_eligible_frame_manifest_sha256_x_strata_allocation_manifest_sha256",
            "selected_case": "protocol_version_x_trial_id_x_case_id",
        },
        "join_rules": [
            "CONTRACT_CORE_SHA256_ONE_TO_ONE_ACROSS_RECEIPT_SELECTED_MAP_AND_DOWNSTREAM_ARTIFACTS",
            "SELECTED_PROBABILITY_WEIGHT_ROWS_EXACT_ORDERED_ONE_TO_ONE_BY_CASE_ID",
            "SELECTED_CASE_STRATUM_EQUALS_ELIGIBLE_FRAME_STRATUM",
            "SAMPLING_SEED_AND_SELECTION_COMMITMENT_EQUAL_ACROSS_RECEIPT_SELECTED_AND_MAP",
            "OWNER_GLOBAL_TRIAL_REGISTRATION_ONE_TO_ONE_WITH_PROTOCOL_ATTEMPT_NAMESPACE",
            "SAMPLING_ATTEMPT_NAMESPACE_ONE_TO_ONE_WITH_EXACT_POLICY_CONTRACT_CORE_FRAME_ALLOCATION_AND_EVENT",
            "NO_MANY_TO_MANY_OR_CROSS_VERSION_JOIN",
            "MISSING_EXTRA_DUPLICATE_OR_ALIAS_KEYS_FAIL_CLOSED",
        ],
    }, "data-quality contract drift")

    if root is not None:
        validate_sources(root, policy)
        receipt_schema, _ = load_canonical(
            root / "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v1.json",
            "sampling receipt schema v1",
        )
        require(receipt_schema.get("required") == RECEIPT_REQUIRED, "policy/schema receipt field mismatch")


def set_path(value: dict[str, Any], path: tuple[str, ...], replacement: Any) -> None:
    cursor: Any = value
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = replacement


def run_self_test(policy: dict[str, Any]) -> int:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("schema", lambda x: set_path(x, ("schema",), "agent_bridge.biocortex_ab_track_b_real_run_admission_policy.v0")),
        ("authority", lambda x: set_path(x, ("authority", "condition_output"), True)),
        ("status", lambda x: set_path(x, ("status",), "READY")),
        ("decision", lambda x: set_path(x, ("decision",), "REAL_RUN_ADMITTED")),
        ("blocker", lambda x: x["blockers"].pop()),
        ("default", lambda x: set_path(x, ("protocol_migration", "default_protocol_when_missing"), 0)),
        ("fallback", lambda x: set_path(x, ("protocol_migration", "validation_failure_fallback_allowed"), True)),
        ("upcast", lambda x: set_path(x, ("protocol_migration", "automatic_upcast_or_downcast"), True)),
        ("cross-version-join", lambda x: set_path(x, ("protocol_migration", "cross_version_artifact_join_allowed"), True)),
        ("v0-live", lambda x: set_path(x, ("protocol_migration", "historical_v0", "historical_validation_only"), False)),
        ("contract-alias", lambda x: set_path(x, ("contract_identity", "contract_sha256_semantics"), "ADMISSION_PACKET_SHA256")),
        ("dynamic-core", lambda x: set_path(x, ("contract_identity", "dynamic_runtime_state_inside_contract_core"), True)),
        ("receipt-v0", lambda x: set_path(x, ("sampling_interface", "receipt_instance_schema"), "agent_bridge.biocortex_ab_track_b_sampling_receipt.v0")),
        ("receipt-field", lambda x: x["sampling_interface"]["required_receipt_bindings"].pop()),
        ("receipt-authority", lambda x: set_path(x, ("sampling_interface", "condition_output_authorized"), True)),
        ("anti-shopping", lambda x: set_path(x, ("sampling_interface", "anti_shopping_order_verified"), True)),
        ("timing", lambda x: set_path(x, ("sampling_interface", "pre_output_timing_verified"), True)),
        ("map-v0", lambda x: set_path(x, ("map_interface", "request_schema"), "agent_bridge.biocortex_ab_track_b_map_bijection_request.v0")),
        ("map-fallback", lambda x: set_path(x, ("map_interface", "cross_version_fallback_allowed"), True)),
        ("map-authority", lambda x: set_path(x, ("map_interface", "condition_output_authority_from_map_validation"), True)),
        ("entropy-event", lambda x: set_path(x, ("sampling_single_use", "event_identity_excludes_external_entropy"), False)),
        ("attempt-scope", lambda x: set_path(x, ("sampling_single_use", "attempt_namespace_excludes_contract_core_frame_allocation_and_external_entropy"), False)),
        ("attempt-one-event", lambda x: set_path(x, ("sampling_single_use", "one_exact_policy_contract_core_frame_allocation_and_event_per_attempt_namespace_required"), False)),
        ("attempt-input-change", lambda x: set_path(x, ("sampling_single_use", "contract_core_frame_or_allocation_change_within_attempt_namespace_forbidden"), False)),
        ("owner-trial", lambda x: set_path(x, ("sampling_single_use", "owner_issued_globally_unique_trial_id_required_before_claim"), False)),
        ("single-use", lambda x: set_path(x, ("sampling_single_use", "global_single_use_verified"), True)),
        ("live", lambda x: set_path(x, ("live_binding", "live_binding_satisfied_count"), 1)),
        ("admitted", lambda x: set_path(x, ("live_binding", "real_run_admitted"), True)),
        ("side-effect", lambda x: set_path(x, ("live_binding", "side_effects_unlocked"), "GENERATION")),
        ("runtime-state", lambda x: set_path(x, ("dynamic_state", "sampling_receipt_sha256"), "0" * 64)),
        ("stage", lambda x: set_path(x, ("stages", "pre_output_admission", "status"), "READY")),
        ("unknown", lambda x: x.update({"private_runtime": {}})),
    ]
    rejected = 0
    for label, mutate in mutations:
        candidate = copy.deepcopy(policy)
        mutate(candidate)
        try:
            validate_policy(candidate, None)
        except AdmissionV1Error:
            rejected += 1
        else:
            fail(f"self-test mutation accepted: {label}")
    return rejected


RESULT_ORDER = (
    "schema",
    "policy_sha256",
    "status",
    "decision",
    "protocol_version",
    "historical_v0_validation_only",
    "v1_new_trials_required",
    "cross_version_fallback_allowed",
    "contract_sha256_semantics",
    "receipt_schema_sha256",
    "receipt_writer_sha256",
    "map_schema_sha256",
    "map_checker_sha256",
    "live_binding_satisfied_count",
    "real_run_admitted",
    "condition_output_authorized",
    "global_sampling_single_use_verified",
    "runtime_state_populated_count",
    "blocker_count",
    "side_effects_unlocked",
)


def render_result(policy: dict[str, Any], raw: bytes) -> str:
    state = policy["dynamic_state"]
    rows = {
        "schema": SCHEMA,
        "policy_sha256": hashlib.sha256(raw).hexdigest(),
        "status": policy["status"],
        "decision": policy["decision"],
        "protocol_version": policy["protocol_migration"]["current_protocol_version"],
        "historical_v0_validation_only": policy["protocol_migration"]["historical_v0"]["historical_validation_only"],
        "v1_new_trials_required": policy["protocol_migration"]["new_trials_require_v1"],
        "cross_version_fallback_allowed": policy["protocol_migration"]["validation_failure_fallback_allowed"],
        "contract_sha256_semantics": policy["contract_identity"]["contract_sha256_semantics"],
        "receipt_schema_sha256": policy["sampling_interface"]["receipt_schema_sha256"],
        "receipt_writer_sha256": policy["sampling_interface"]["receipt_writer_sha256"],
        "map_schema_sha256": policy["map_interface"]["blind_map_schema_sha256"],
        "map_checker_sha256": policy["map_interface"]["checker_sha256"],
        "live_binding_satisfied_count": policy["live_binding"]["live_binding_satisfied_count"],
        "real_run_admitted": policy["live_binding"]["real_run_admitted"],
        "condition_output_authorized": policy["live_binding"]["condition_output_authorized"],
        "global_sampling_single_use_verified": policy["sampling_single_use"]["global_single_use_verified"],
        "runtime_state_populated_count": sum(value is not None for key, value in state.items() if key not in {"schema", "status"}),
        "blocker_count": len(policy["blockers"]),
        "side_effects_unlocked": policy["live_binding"]["side_effects_unlocked"],
    }
    return "".join(
        f"{key}\t{str(rows[key]).lower() if type(rows[key]) is bool else rows[key]}\n"
        for key in RESULT_ORDER
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        policy, raw = load_canonical(root / POLICY_PATH, "admission policy v1")
        validate_policy(policy, root)
        if args.self_test:
            print(f"SELF_TEST_OK\tmutations_rejected={run_self_test(policy)}")
        else:
            sys.stdout.write(render_result(policy, raw))
        return 0
    except AdmissionV1Error as exc:
        print(f"Track B admission v1 check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
