#!/usr/bin/env python3
"""Fail-closed validator for the nonexecuting P9 post-D4 G0 closure.

This module reads committed Git objects and canonical JSON only.  It never
launches Julia or the P9 candidate.  G0 closes the diagnostic route because
the one D4 trace does not enter the only partition that could create a static
review target; it does not infer a host-failure cause or a resource no-go.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


sys.dont_write_bytecode = True

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[2]
CONTRACT_NAME = "majorana_certificate_p9_g0_post_d4_governance_closure_contract.json"
RECORD_NAME = "majorana_certificate_p9_g0_post_d4_governance_closure_record.json"
TEST_NAME = "test_majorana_certificate_p9_g0_post_d4_governance_closure.py"
D4_RUNNER_NAME = "majorana_certificate_p9_d4_segment_d_per_composite_probe.py"
D4_REPORT_REPO_PATH = (
    "docs/research/fermion-frontier/"
    "majorana_certificate_p9_d4_segment_d_per_composite_probe_report.json"
)
D4_B0 = "ed1955fbddde3f8d6edc6745293b47659f0dd615"
D4_B1 = "1bfdf15c553c6d4934ce4395114458dcda1be4f9"
D3_B1 = "e1f3d12bfaa51076ffea4ed43752c664970a4c92"
CONTRACT_ID = "MAJORANA-P9-POST-D4-G0-GOVERNANCE-CLOSURE-V1"
RECORD_ID = "MAJORANA-P9-POST-D4-G0-GOVERNANCE-CLOSURE-RECORD-V1"
DISPOSITION = "CLOSED_NO_POST_D4_REVIEW_TARGET"
NEXT_GATE_ID = "P10-A-STATIC-RESOURCE-ENVELOPE-PROOF-DESIGN-V1"
D4_EVENT_NAMES_CANONICAL_SHA256 = "c519018d38c67a0eeb5f431227571a950d29529a9d247e74276419525874952e"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_JSON_BYTES = 1_048_576

G0_REPO_PATHS = (
    "docs/research/fermion-frontier/ARTIFACTS.md",
    "docs/research/fermion-frontier/PROGRESS.md",
    f"docs/research/fermion-frontier/{CONTRACT_NAME}",
    f"docs/research/fermion-frontier/{RECORD_NAME}",
    "docs/research/fermion-frontier/majorana_certificate_p9_g0_post_d4_governance_closure_validator.py",
    f"docs/research/fermion-frontier/{TEST_NAME}",
)
G0_STAGED_STATUS = {
    G0_REPO_PATHS[0]: "M",
    G0_REPO_PATHS[1]: "M",
    G0_REPO_PATHS[2]: "A",
    G0_REPO_PATHS[3]: "A",
    G0_REPO_PATHS[4]: "A",
    G0_REPO_PATHS[5]: "A",
}

D4_SOURCE_PINS = (
    {
        "relative_path": "docs/research/fermion-frontier/majorana_certificate_p9_d4_segment_d_per_composite_probe.py",
        "size_bytes": 103885,
        "sha256": "a7a483d2b2258541e3e238839330060d8c3e59cccc18895e45fcf2505bd6f58d",
    },
    {
        "relative_path": "docs/research/fermion-frontier/majorana_certificate_p9_d4_segment_d_per_composite_probe/majorana_p9_bit_order_step3_segment_d_per_composite_probe.jl",
        "size_bytes": 89655,
        "sha256": "6a2ad035cbb777323594803f801b6a0fb394704b6159bd902de7339692ac9bf4",
    },
    {
        "relative_path": "docs/research/fermion-frontier/majorana_certificate_p9_d4_segment_d_per_composite_probe_fixture.json",
        "size_bytes": 18991,
        "sha256": "c5ca2f312163ae6e602f9946e9ccdd88ae24062f3be397995221c59b7fe3e32c",
    },
    {
        "relative_path": "docs/research/fermion-frontier/majorana_certificate_p9_d4_segment_d_per_composite_probe_policy.json",
        "size_bytes": 13768,
        "sha256": "1b0a2089c309609c7756ddec4cfe9ab85361fb84b71e76ca78e87791da5e9f1b",
    },
    {
        "relative_path": "docs/research/fermion-frontier/test_majorana_certificate_p9_d4_segment_d_per_composite_probe.py",
        "size_bytes": 30730,
        "sha256": "a2c1066e87b8c5e80ae87fdfa41458531fa17f279583c9b4a0c33874f3f22302",
    },
)

REVIEW_PREDICATES = (
    (
        "POST_D4_KAPPA_REVIEW_TARGET",
        "STEP3_SEGMENT_D_SUBGRID_ALPHA_REACHED",
        "STEP3_SEGMENT_D_COMPOSITE_KAPPA_REACHED",
        "SEGMENT_D_COMPOSITE_KAPPA_STATIC_INTERVAL",
    ),
    (
        "POST_D4_LAMBDA_REVIEW_TARGET",
        "STEP3_SEGMENT_D_COMPOSITE_KAPPA_REACHED",
        "STEP3_SEGMENT_D_COMPOSITE_LAMBDA_REACHED",
        "SEGMENT_D_COMPOSITE_LAMBDA_STATIC_INTERVAL",
    ),
    (
        "POST_D4_MU_REVIEW_TARGET",
        "STEP3_SEGMENT_D_COMPOSITE_LAMBDA_REACHED",
        "STEP3_SEGMENT_D_COMPOSITE_MU_REACHED",
        "SEGMENT_D_COMPOSITE_MU_STATIC_INTERVAL",
    ),
    (
        "POST_D4_NU_REVIEW_TARGET",
        "STEP3_SEGMENT_D_COMPOSITE_MU_REACHED",
        "STEP3_SEGMENT_D_COMPOSITE_NU_REACHED",
        "SEGMENT_D_COMPOSITE_NU_STATIC_INTERVAL",
    ),
)
OBLIGATION_IDS = (
    "LSB-01-SOURCE-TYPE-ALLOCATION-CLOSURE",
    "LSB-02-ALIAS-OWNERSHIP-LIFETIME-GRAPH",
    "LSB-03-EXACT-PAYLOAD-AND-CAPACITY-BYTES",
    "LSB-04-RUNTIME-OVERHEAD-ENVELOPE",
    "LSB-05-PEAK-COMPOSITION-AND-FIXED-CAP-COMPARISON",
    "LSB-06-INDEPENDENT-CHECKER-AND-ADVERSARIAL-MUTATIONS",
    "RSE-07-OPERATION-COST-CLOSURE",
)
CONTRACT_SECTION_SHA256 = {
    "decision_rules": "70fc3256632297b8a3d8da41a6e7d3323bb08e62128555890812431b35ddf348",
    "proof_obligation_ledger": "8542fb5fabec365c8a2efc7e8ee025c26ac64c5b584831087ab5e753fc9ac672",
    "next_gate_contract": "c8d63185396e2bfb63e7dbb7ec84dc7d823df22a348bcfe6422bcdefdc316599",
    "forbidden_actions": "8bc96b84c691f5c1f5ac90f3023740e5e52703037be832cb64819dd6d46ef3c3",
    "closure_lifecycle": "e0822e3e2ee10d1919d325b3b124e7d25cb09ae10b962228d909ca66b3eb5644",
}


class GovernanceError(ValueError):
    """Malformed evidence, source drift, or an invalid governance claim."""


def _strict_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            _strict_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _strict_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _exact_keys(value: Any, expected: Iterable[str], context: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise GovernanceError(f"{context} must be an exact object")
    expected_set = set(expected)
    if set(value) != expected_set:
        raise GovernanceError(f"{context} keys drift")
    return value


def _reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GovernanceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def canonical_payload(value: Any) -> bytes:
    try:
        return json.dumps(
            value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise GovernanceError("value is not canonical-JSON encodable") from exc


def canonical_bytes(value: Any) -> bytes:
    return canonical_payload(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_payload(value)).hexdigest()


def _read_regular(path: Path, context: str, maximum: int = MAX_JSON_BYTES) -> bytes:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise GovernanceError(f"missing {context}") from exc
    if not stat.S_ISREG(mode) or path.is_symlink():
        raise GovernanceError(f"{context} must be a regular non-symlink file")
    data = path.read_bytes()
    if len(data) > maximum:
        raise GovernanceError(f"{context} exceeds its byte cap")
    return data


def loads_strict(data: bytes, context: str) -> Any:
    try:
        text = data.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                GovernanceError(f"non-finite JSON token in {context}: {token}")
            ),
        )
    except GovernanceError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"malformed {context}") from exc


def load_json(path: Path, context: str, *, require_canonical: bool = False) -> tuple[Any, bytes]:
    data = _read_regular(path, context)
    value = loads_strict(data, context)
    if require_canonical and data != canonical_bytes(value):
        raise GovernanceError(f"{context} is not canonical JSON bytes")
    return value, data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str) -> str:
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", "replace").strip()
        raise GovernanceError(f"git {' '.join(args)} failed: {message}")
    return completed.stdout.decode("utf-8")


def _git_bytes(commit: str, repo_path: str) -> bytes:
    if not COMMIT_RE.fullmatch(commit):
        raise GovernanceError("malformed Git commit")
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", "show", f"{commit}:{repo_path}"], cwd=REPO_ROOT, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode != 0:
        raise GovernanceError(f"missing pinned Git blob: {commit}:{repo_path}")
    return completed.stdout


def _commit_parent(commit: str) -> str:
    fields = _git("rev-list", "--parents", "-n", "1", commit).strip().split()
    if len(fields) != 2 or fields[0] != commit:
        raise GovernanceError(f"{commit} must have exactly one parent")
    return fields[1]


def _changed_paths(commit: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    output = _git("diff-tree", "--no-commit-id", "--name-status", "-r", commit)
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] not in {"A", "M", "D"}:
            raise GovernanceError(f"unsupported changed-path row at {commit}")
        status_code, path = fields
        if path in rows:
            raise GovernanceError(f"duplicate changed path at {commit}")
        rows[path] = status_code
    return rows


def _load_d4_module() -> Any:
    path = BASE / D4_RUNNER_NAME
    spec = importlib.util.spec_from_file_location("_p9_d4_for_g0", path)
    if spec is None or spec.loader is None:
        raise GovernanceError("cannot load the frozen D4 validator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_contract(contract: Any) -> Mapping[str, Any]:
    contract = _exact_keys(contract, (
        "schema_version", "contract_id", "contract_role", "self_relative_path",
        "required_direct_parent_commit", "scientific_authority", "execution_authority",
        "candidate_selection_authority", "candidate_or_cap_change_authority",
        "resource_or_no_go_authority", "S0_authority",
        "certificate_eligible", "result_contract_eligible", "d4_result_custody",
        "allowed_D4_governance_projection", "review_target_predicates", "decision_rules",
        "proof_obligation_ledger", "next_gate_contract", "forbidden_actions",
        "closure_lifecycle",
    ), "G0 contract")
    expected_scalars = {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "contract_role": "result_informed_nonexecuting_post_D4_governance_closure_for_the_frozen_P9_step3_route",
        "self_relative_path": CONTRACT_NAME,
        "required_direct_parent_commit": D4_B1,
        "scientific_authority": "NONE",
        "execution_authority": False,
        "candidate_selection_authority": False,
        "candidate_or_cap_change_authority": False,
        "resource_or_no_go_authority": False,
        "S0_authority": False,
        "certificate_eligible": False,
        "result_contract_eligible": False,
    }
    for key, expected in expected_scalars.items():
        if not _strict_equal(contract[key], expected):
            raise GovernanceError(f"G0 contract scalar drift: {key}")
    for section, expected_sha256 in CONTRACT_SECTION_SHA256.items():
        if canonical_sha256(contract[section]) != expected_sha256:
            raise GovernanceError(f"G0 contract semantic section drift: {section}")

    custody = contract["d4_result_custody"]
    required_custody = {
        "result_commit_sha": D4_B1,
        "preprobe_commit_sha": D4_B0,
        "preprobe_changed_paths": [row["relative_path"] for row in D4_SOURCE_PINS],
        "preprobe_source_pins": list(D4_SOURCE_PINS),
        "report_relative_path": D4_REPORT_REPO_PATH,
        "report_size_bytes": 8283,
        "report_sha256": "46aa8ea40a96f84e091de039cbb7212e4d165ef1c3a36cee43038a59736c9142",
        "report_type": "majorana_p9_step3_e768_bitorder_segment_d_per_composite_report_d4_v1",
        "report_schema_version": 1,
        "policy_id": "MAJORANA-P9-STEP3-E768-BITORDER-D4-SEGMENT-D-PER-COMPOSITE-V1",
        "policy_sha256": "1b0a2089c309609c7756ddec4cfe9ab85361fb84b71e76ca78e87791da5e9f1b",
        "fixture_id": "MAJORANA-P9-STEP3-E768-BITORDER-D4-SEGMENT-D-PER-COMPOSITE-V1",
        "fixture_sha256": "c5ca2f312163ae6e602f9946e9ccdd88ae24062f3be397995221c59b7fe3e32c",
        "fixture_canonical_sha256": "c8f241e681bb34577b1fd338a5a1cad55899e76c418e724ba2046d24d301a606",
        "D3_B1_parent_commit_sha": D3_B1,
        "D3_B1_parent_report_sha256": "61cebcf8553333449927147640e5fed278e0156befa8d66c2cb68df13bf5f2ea",
        "D4_B1_changed_path_is_exactly_the_canonical_report": True,
        "report_Git_blob_and_clean_worktree_bytes_must_match": True,
        "report_must_pass_the_frozen_D4_validator_and_canonical_JSON_check": True,
    }
    if not _strict_equal(custody, required_custody):
        raise GovernanceError("D4 result custody drift")

    projection = _exact_keys(contract["allowed_D4_governance_projection"], (
        "projection_is_exhaustive_for_G0", "raw_report_bytes_do_not_cross_the_projection_after_validation",
        "full_phase_event_array_and_phase_digest_do_not_enter_any_future_runner",
        "report_identity", "observation", "marker_projection", "S0_admission",
    ), "allowed D4 projection")
    for key in (
        "projection_is_exhaustive_for_G0",
        "raw_report_bytes_do_not_cross_the_projection_after_validation",
        "full_phase_event_array_and_phase_digest_do_not_enter_any_future_runner",
    ):
        if projection[key] is not True:
            raise GovernanceError(f"D4 projection firewall drift: {key}")
    forbidden_observation_keys = {
        "outer_monotonic_elapsed_ns", "outer_timeout_triggered", "process_returncode",
        "stdout", "stdout_bytes", "stdout_sha256", "stderr", "stderr_bytes",
        "stderr_sha256", "RSS", "memory", "time_diagnostics", "host_failure_observed",
    }
    if forbidden_observation_keys & set(projection["observation"]):
        raise GovernanceError("forbidden host diagnostic entered the G0 projection")

    expected_predicates = [
        {
            "predicate_id": predicate_id,
            "last_reached_boundary": last,
            "required_absent_next_boundary": absent,
            "review_target": target,
            "same_single_D4_trace_required": True,
        }
        for predicate_id, last, absent, target in REVIEW_PREDICATES
    ]
    if not _strict_equal(contract["review_target_predicates"], expected_predicates):
        raise GovernanceError("review-target predicate drift")
    rules = contract["decision_rules"]
    if (
        rules.get("current_required_matched_target_count") != 0
        or rules.get("current_required_disposition") != DISPOSITION
        or rules.get("zero_matched_predicates_disposition") != DISPOSITION
        or rules.get("predicate_last_reached_and_required_absent_boundaries_must_come_from_the_same_D4_trace") is not True
        or rules.get("D3_marker_facts_must_not_be_spliced_with_D4_absence_facts") is not True
        or rules.get("more_than_one_matched_predicate_is_invalid") is not True
    ):
        raise GovernanceError("G0 decision rule drift")

    ledger = _exact_keys(contract["proof_obligation_ledger"], (
        "ledger_scope", "status", "execution_gate",
        "assessment_and_admission_are_distinct", "NOT_ESTABLISHED_never_unlocks_execution",
        "D4_host_timing_RSS_returncode_stderr_and_marker_reach_are_not_static_resource_envelope_proof",
        "obligations",
    ), "proof obligation ledger")
    if (
        ledger["ledger_scope"] != "proof_only_source_pinned_static_resource_envelope_design"
        or ledger["status"] != "OPEN_PROOF_ONLY_DESIGN_REQUIRED"
        or ledger["execution_gate"] != "CLOSED"
        or ledger["assessment_and_admission_are_distinct"] is not True
        or ledger["NOT_ESTABLISHED_never_unlocks_execution"] is not True
        or ledger["D4_host_timing_RSS_returncode_stderr_and_marker_reach_are_not_static_resource_envelope_proof"] is not True
    ):
        raise GovernanceError("proof ledger authority drift")
    obligations = ledger["obligations"]
    if type(obligations) is not list or [row.get("obligation_id") for row in obligations] != list(OBLIGATION_IDS):
        raise GovernanceError("proof obligation IDs drift")
    for row in obligations:
        _exact_keys(row, ("obligation_id", "required_evidence", "forbidden_substitute", "exit_condition"), "proof obligation")
        if not all(type(row[key]) is str and row[key] for key in row):
            raise GovernanceError("malformed proof obligation")

    next_gate = contract["next_gate_contract"]
    if (
        next_gate.get("only_allowed_next_gate") != NEXT_GATE_ID
        or next_gate.get("next_gate_is_a_design_proposal_not_an_execution") is not True
        or next_gate.get("next_gate_has_no_candidate_selection_resource_scientific_or_S0_authority") is not True
        or next_gate.get("next_gate_must_not_be_named_D5") is not True
        or next_gate.get("all_seven_obligations_must_be_positively_verified_before_future_execution_governance") is not True
        or next_gate.get("static_resource_envelope_must_be_established_with_peak_strictly_below_2147483648_bytes_before_future_execution_governance") is not True
        or next_gate.get("ASSESSED_NOT_ESTABLISHED_keeps_the_execution_gate_closed") is not True
        or next_gate.get("a_positive_static_envelope_still_does_not_authorize_execution_without_a_new_independent_governance_decision") is not True
        or next_gate.get("any_later_execution_requires_a_new_independent_governance_decision") is not True
    ):
        raise GovernanceError("next-gate contract drift")
    forbidden = contract["forbidden_actions"]
    if type(forbidden) is not list or len(forbidden) != len(set(forbidden)) or len(forbidden) < 10:
        raise GovernanceError("forbidden-action closure drift")
    required_forbidden_fragments = ("splice_D3", "rerun_or_repeat", "D5", "relax_or_change", "future_runner")
    joined = "\n".join(forbidden)
    if not all(fragment in joined for fragment in required_forbidden_fragments):
        raise GovernanceError("forbidden-action semantic closure drift")
    lifecycle = contract["closure_lifecycle"]
    if lifecycle.get("G0_exact_changed_paths") != list(G0_REPO_PATHS):
        raise GovernanceError("G0 exact changed paths drift")
    for key, value in lifecycle.items():
        if key != "G0_exact_changed_paths" and value is not True:
            raise GovernanceError(f"G0 lifecycle flag drift: {key}")
    return contract


def _validate_d4_topology_and_sources(contract: Mapping[str, Any]) -> None:
    if _commit_parent(D4_B0) != D3_B1:
        raise GovernanceError("D4 B0 parent drift")
    if _commit_parent(D4_B1) != D4_B0:
        raise GovernanceError("D4 B1 parent drift")
    expected_b0 = {row["relative_path"]: "A" for row in D4_SOURCE_PINS}
    if _changed_paths(D4_B0) != expected_b0:
        raise GovernanceError("D4 B0 changed-path set drift")
    if _changed_paths(D4_B1) != {D4_REPORT_REPO_PATH: "A"}:
        raise GovernanceError("D4 B1 must add only its canonical report")
    for pin in contract["d4_result_custody"]["preprobe_source_pins"]:
        path = REPO_ROOT / pin["relative_path"]
        current = _read_regular(path, f"D4 source {pin['relative_path']}")
        frozen = _git_bytes(D4_B0, pin["relative_path"])
        if current != frozen:
            raise GovernanceError(f"current D4 source differs from B0: {pin['relative_path']}")
        if len(current) != pin["size_bytes"] or _sha256(current) != pin["sha256"]:
            raise GovernanceError(f"D4 source pin drift: {pin['relative_path']}")


def _event_names(report: Mapping[str, Any]) -> list[str]:
    observation = report["observation"]
    events = observation["phase_events"]
    if type(events) is not list:
        raise GovernanceError("D4 phase events must be a list")
    names: list[str] = []
    for index, row in enumerate(events):
        if type(row) is not dict or row.get("sequence") != index or type(row.get("event")) is not str:
            raise GovernanceError("malformed D4 phase event")
        names.append(row["event"])
    if len(names) != observation["phase_event_count"]:
        raise GovernanceError("D4 phase event count drift")
    return names


def _marker_projection(names: Sequence[str]) -> dict[str, bool]:
    reached = set(names)
    return {
        "P6_prefix_resource_conformance_passed_marker_reached": "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED" in reached,
        "step3_engine_started_marker_reached": "STEP3_ENGINE_STARTED" in reached,
        "step3_state_initialized_marker_reached": "STEP3_STATE_INITIALIZED" in reached,
        "step3_schedule_entered_marker_reached": "STEP3_SCHEDULE_ENTERED" in reached,
        "segments_A_through_C_returned_markers_reached": all(
            f"STEP3_SEGMENT_{letter}_RETURNED" in reached for letter in "ABC"
        ),
        "segment_D_started_marker_reached": "STEP3_SEGMENT_D_STARTED" in reached,
        "segment_D_checkpoint_1_marker_reached": "STEP3_SEGMENT_D_CHECKPOINT_1_REACHED" in reached,
        "segment_D_subgrid_ALPHA_marker_reached": "STEP3_SEGMENT_D_SUBGRID_ALPHA_REACHED" in reached,
        "segment_D_composite_KAPPA_marker_reached": "STEP3_SEGMENT_D_COMPOSITE_KAPPA_REACHED" in reached,
        "segment_D_composite_LAMBDA_marker_reached": "STEP3_SEGMENT_D_COMPOSITE_LAMBDA_REACHED" in reached,
        "segment_D_composite_MU_marker_reached": "STEP3_SEGMENT_D_COMPOSITE_MU_REACHED" in reached,
        "segment_D_composite_NU_marker_reached": "STEP3_SEGMENT_D_COMPOSITE_NU_REACHED" in reached,
        "segment_D_subgrid_BETA_marker_reached": "STEP3_SEGMENT_D_SUBGRID_BETA_REACHED" in reached,
        "segment_D_subgrid_BETA_is_absent_from_the_D4_wire_vocabulary": True,
        "segment_D_subgrid_GAMMA_marker_reached": "STEP3_SEGMENT_D_SUBGRID_GAMMA_REACHED" in reached,
        "segment_D_checkpoint_2_marker_reached": "STEP3_SEGMENT_D_CHECKPOINT_2_REACHED" in reached,
        "segment_D_returned_marker_reached": "STEP3_SEGMENT_D_RETURNED" in reached,
        "later_schedule_markers_reached": any(
            any(name.startswith(f"STEP3_SEGMENT_{letter}_") for letter in "EFGHI")
            for name in names
        ),
        "step3_schedule_returned_marker_reached": "STEP3_SCHEDULE_RETURNED" in reached,
        "step3_engine_returned_marker_reached": "STEP3_ENGINE_RETURNED" in reached,
        "D4_diagnostic_completed_marker_reached": "D4_DIAGNOSTIC_COMPLETED" in reached,
    }


def validate_d4_evidence(contract: Mapping[str, Any]) -> tuple[Mapping[str, Any], list[str], dict[str, Any]]:
    _validate_d4_topology_and_sources(contract)
    custody = contract["d4_result_custody"]
    report_path = REPO_ROOT / custody["report_relative_path"]
    # D4 owns its canonical field order; validate those bytes with the frozen
    # D4 canonicalizer below rather than G0's sorted-key record canonicalizer.
    report, raw = load_json(report_path, "D4 report")
    if len(raw) != custody["report_size_bytes"] or _sha256(raw) != custody["report_sha256"]:
        raise GovernanceError("D4 report receipt drift")
    if _git_bytes(D4_B1, custody["report_relative_path"]) != raw:
        raise GovernanceError("D4 report differs from its B1 Git blob")
    d4 = _load_d4_module()
    try:
        validated = d4.validate_report(report)
    except Exception as exc:  # the frozen validator owns its detailed taxonomy
        raise GovernanceError("frozen D4 report validation failed") from exc
    if raw != d4.canonical_bytes(validated):
        raise GovernanceError("D4 frozen canonical-byte validation failed")
    names = _event_names(validated)
    projection = {
        "projection_is_exhaustive_for_G0": True,
        "raw_report_bytes_do_not_cross_the_projection_after_validation": True,
        "full_phase_event_array_and_phase_digest_do_not_enter_any_future_runner": True,
        "report_identity": {
            key: validated[key] for key in (
                "schema_version", "report_type", "policy_id", "fixture_id",
                "preprobe_commit_sha", "scientific_authority", "certificate_eligible",
                "result_contract_eligible",
            )
        },
        "observation": {
            key: validated["observation"][key] for key in (
                "status", "phase_trace_status", "phase_event_count", "last_phase_event",
                "diagnostic_terminal_branch", "resource_witness",
                "host_failure_has_no_mathematical_authority",
            )
        },
        "marker_projection": _marker_projection(names),
        "S0_admission": validated["S0_admission"],
    }
    if not _strict_equal(projection, contract["allowed_D4_governance_projection"]):
        raise GovernanceError("D4 minimal governance projection drift")
    return validated, names, projection


def evaluate_review_targets(names: Sequence[str], phase_trace_status: str) -> list[dict[str, Any]]:
    if phase_trace_status != "LEGAL_PREFIX_INTERRUPTED":
        raise GovernanceError("review predicates require one legal interrupted D4 trace")
    if canonical_sha256(list(names)) != D4_EVENT_NAMES_CANONICAL_SHA256:
        raise GovernanceError("review predicates require the validated D4 B1 event-name projection")
    reached = set(names)
    evaluations: list[dict[str, Any]] = []
    for predicate_id, last, absent, target in REVIEW_PREDICATES:
        if last not in reached:
            matched = False
            reason = f"required_last_boundary_{last}_is_absent_from_the_D4_trace"
        elif absent in reached:
            matched = False
            reason = f"required_absent_next_boundary_{absent}_is_present_in_the_D4_trace"
        else:
            matched = True
            reason = f"same_D4_trace_reached_{last}_without_reaching_{absent}"
        evaluations.append({
            "predicate_id": predicate_id,
            "review_target": target,
            "matched": matched,
            "reason": reason,
        })
    if sum(row["matched"] for row in evaluations) > 1:
        raise GovernanceError("more than one post-D4 target matched")
    return evaluations


def _record_minimal_projection(report: Mapping[str, Any], markers: Mapping[str, bool]) -> dict[str, Any]:
    observation = report["observation"]
    return {
        "scientific_authority": report["scientific_authority"],
        "certificate_eligible": report["certificate_eligible"],
        "result_contract_eligible": report["result_contract_eligible"],
        "observation_status": observation["status"],
        "phase_trace_status": observation["phase_trace_status"],
        "phase_event_count": observation["phase_event_count"],
        "last_phase_event": observation["last_phase_event"],
        "diagnostic_terminal_branch": observation["diagnostic_terminal_branch"],
        "resource_witness": observation["resource_witness"],
        "segments_A_through_C_returned_markers_reached": markers["segments_A_through_C_returned_markers_reached"],
        "segment_D_started_marker_reached": markers["segment_D_started_marker_reached"],
        "segment_D_checkpoint_1_marker_reached": markers["segment_D_checkpoint_1_marker_reached"],
        "segment_D_subgrid_ALPHA_marker_reached": markers["segment_D_subgrid_ALPHA_marker_reached"],
        "segment_D_composite_KAPPA_marker_reached": markers["segment_D_composite_KAPPA_marker_reached"],
        "segment_D_composite_LAMBDA_marker_reached": markers["segment_D_composite_LAMBDA_marker_reached"],
        "segment_D_composite_MU_marker_reached": markers["segment_D_composite_MU_marker_reached"],
        "segment_D_composite_NU_marker_reached": markers["segment_D_composite_NU_marker_reached"],
        "segment_D_subgrid_BETA_marker_reached": markers["segment_D_subgrid_BETA_marker_reached"],
        "segment_D_subgrid_GAMMA_marker_reached": markers["segment_D_subgrid_GAMMA_marker_reached"],
        "segment_D_checkpoint_2_marker_reached": markers["segment_D_checkpoint_2_marker_reached"],
        "segment_D_returned_marker_reached": markers["segment_D_returned_marker_reached"],
        "later_schedule_markers_reached": markers["later_schedule_markers_reached"],
        "step3_schedule_returned_marker_reached": markers["step3_schedule_returned_marker_reached"],
        "step3_engine_returned_marker_reached": markers["step3_engine_returned_marker_reached"],
        "D4_diagnostic_completed_marker_reached": markers["D4_diagnostic_completed_marker_reached"],
        "current_trace_is_outside_the_selected_ordinals_21_through_24_partition": not markers["segment_D_subgrid_ALPHA_marker_reached"],
    }


def validate_record(
    record: Any, contract: Mapping[str, Any], contract_raw: bytes,
    report: Mapping[str, Any], names: Sequence[str],
) -> Mapping[str, Any]:
    record = _exact_keys(record, (
        "schema_version", "record_type", "record_id", "contract_id",
        "required_direct_parent_commit", "contract_receipt", "D4_result_receipt",
        "D4_minimal_governance_projection", "review_predicate_evaluations",
        "matched_targets", "matched_target_count", "disposition", "disposition_reason",
        "cross_run_integrity", "scientific_authority", "execution_authority",
        "candidate_selection_authority", "candidate_or_cap_change_authority",
        "resource_or_no_go_authority", "S0_authority",
        "certificate_eligible", "result_contract_eligible", "S0_admission",
        "proof_obligation_ledger", "next_gate", "closure_assertions",
    ), "G0 record")
    scalars = {
        "schema_version": 1,
        "record_type": "majorana_p9_post_d4_g0_governance_closure_record_v1",
        "record_id": RECORD_ID,
        "contract_id": CONTRACT_ID,
        "required_direct_parent_commit": D4_B1,
        "disposition": DISPOSITION,
        "scientific_authority": "NONE",
        "execution_authority": False,
        "candidate_selection_authority": False,
        "candidate_or_cap_change_authority": False,
        "resource_or_no_go_authority": False,
        "S0_authority": False,
        "certificate_eligible": False,
        "result_contract_eligible": False,
    }
    for key, expected in scalars.items():
        if not _strict_equal(record[key], expected):
            raise GovernanceError(f"G0 record scalar drift: {key}")
    expected_contract_receipt = {
        "relative_path": CONTRACT_NAME,
        "size_bytes": len(contract_raw),
        "raw_sha256": _sha256(contract_raw),
        "canonical_sha256": canonical_sha256(contract),
        "raw_and_canonical_hashes_have_distinct_byte_domains": True,
    }
    if not _strict_equal(record["contract_receipt"], expected_contract_receipt):
        raise GovernanceError("G0 contract receipt drift")
    expected_d4_receipt = {
        "result_commit_sha": D4_B1,
        "preprobe_commit_sha": D4_B0,
        "report_relative_path": D4_REPORT_REPO_PATH,
        "report_size_bytes": 8283,
        "report_sha256": "46aa8ea40a96f84e091de039cbb7212e4d165ef1c3a36cee43038a59736c9142",
        "report_type": "majorana_p9_step3_e768_bitorder_segment_d_per_composite_report_d4_v1",
        "report_validator_status": "VERIFIED_P9_D4_SEGMENT_D_PER_COMPOSITE_REPORT",
        "report_is_canonical_JSON": True,
    }
    if not _strict_equal(record["D4_result_receipt"], expected_d4_receipt):
        raise GovernanceError("G0 D4 receipt drift")
    markers = _marker_projection(names)
    if not _strict_equal(record["D4_minimal_governance_projection"], _record_minimal_projection(report, markers)):
        raise GovernanceError("G0 record minimal projection drift")
    evaluations = evaluate_review_targets(names, report["observation"]["phase_trace_status"])
    if not _strict_equal(record["review_predicate_evaluations"], evaluations):
        raise GovernanceError("G0 review predicate evaluation drift")
    matched = [row["review_target"] for row in evaluations if row["matched"]]
    if record["matched_targets"] != matched or record["matched_target_count"] != len(matched):
        raise GovernanceError("G0 matched-target ledger drift")
    if matched or record["disposition"] != DISPOSITION:
        raise GovernanceError("current D4 trace must close with no review target")
    if record["disposition_reason"] != (
        "the_verified_D4_legal_interrupted_prefix_stops_at_segment_D_started_before_"
        "checkpoint_1_ALPHA_and_the_selected_ordinals_21_through_24_partition"
    ):
        raise GovernanceError("G0 disposition reason drift")
    expected_cross_run = {
        "same_single_D4_trace_was_used_for_every_predicate": True,
        "D3_ALPHA_reach_was_not_spliced_with_D4_KAPPA_absence": True,
        "cross_run_marker_progress_is_not_assumed_monotonic": True,
        "cross_run_splicing_would_invalidate_this_record": True,
    }
    if not _strict_equal(record["cross_run_integrity"], expected_cross_run):
        raise GovernanceError("cross-run firewall drift")
    expected_s0 = dict(report["S0_admission"])
    expected_s0["S0_status_unchanged_by_G0"] = True
    if not _strict_equal(record["S0_admission"], expected_s0):
        raise GovernanceError("G0 S0 non-authority drift")
    expected_ledger = {
        "ledger_scope": "proof_only_source_pinned_static_resource_envelope_design",
        "overall_status": "OPEN_PROOF_ONLY_DESIGN_REQUIRED",
        "execution_gate": "CLOSED",
        "assessment_status": "OPEN",
        "admission_status": "NOT_ESTABLISHED",
        "assessment_closed_does_not_imply_admission_passed": True,
        "static_resource_envelope_established": False,
        "obligations": [{"obligation_id": item, "status": "OPEN"} for item in OBLIGATION_IDS],
        "D4_host_or_marker_observation_was_not_used_as_static_resource_envelope_proof": True,
    }
    if not _strict_equal(record["proof_obligation_ledger"], expected_ledger):
        raise GovernanceError("G0 proof-obligation record drift")
    expected_next_gate = {
        "status": "PROOF_ONLY_DESIGN_PROPOSAL_REQUIRED",
        "allowed_proposal": NEXT_GATE_ID,
        "proposal_is_not_an_execution": True,
        "execution_authorized": False,
        "D5_authorized": False,
        "candidate_or_cap_change_authorized": False,
        "all_seven_obligations_positive_required_before_future_execution_governance": True,
        "static_resource_envelope_established_required_before_future_execution_governance": True,
        "peak_bound_strictly_below_2147483648_bytes_required_before_future_execution_governance": True,
        "ASSESSED_NOT_ESTABLISHED_keeps_execution_closed": True,
        "any_later_execution_requires_a_new_independent_governance_decision": True,
    }
    if not _strict_equal(record["next_gate"], expected_next_gate):
        raise GovernanceError("G0 next-gate record drift")
    expected_closure = {
        "D4_will_not_be_rerun_or_relaxed_in_place": True,
        "no_D5_or_finer_execution_is_authorized": True,
        "no_constituent_callback_selection_or_hot_loop_refinement_is_authorized": True,
        "the_D4_trace_will_not_enter_a_future_runner": True,
        "the_D4_host_failure_has_no_scientific_or_static_resource_envelope_authority": True,
        "the_frozen_D4_B1_commit_will_not_be_amended": True,
        "AB_memory_or_documentation_is_advisory_and_not_an_authority_source": True,
    }
    if not _strict_equal(record["closure_assertions"], expected_closure):
        raise GovernanceError("G0 closure assertion drift")
    return record


def validate_content() -> dict[str, Any]:
    contract, contract_raw = load_json(BASE / CONTRACT_NAME, "G0 contract")
    contract = validate_contract(contract)
    report, names, _projection = validate_d4_evidence(contract)
    record, _record_raw = load_json(BASE / RECORD_NAME, "G0 record", require_canonical=True)
    validate_record(record, contract, contract_raw, report, names)
    return {
        "contract_id": CONTRACT_ID,
        "disposition": DISPOSITION,
        "matched_target_count": 0,
        "record_sha256": _sha256(_record_raw),
        "status": "VERIFIED_P9_G0_POST_D4_GOVERNANCE_CLOSURE_CONTENT",
    }


def _parse_name_status(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2:
            raise GovernanceError("malformed Git name-status row")
        status_code, path = fields
        if status_code not in {"A", "M"} or path in result:
            raise GovernanceError("invalid Git name-status row")
        result[path] = status_code
    return result


def validate_lifecycle() -> str:
    head = _git("rev-parse", "HEAD").strip()
    if head == D4_B1:
        # No diff filter: an extra staged deletion must be visible and fail
        # closed instead of disappearing before the exact-six-path check.
        staged = _parse_name_status(_git("diff", "--cached", "--name-status", "--no-renames"))
        if staged != G0_STAGED_STATUS:
            raise GovernanceError("staged G0 changed-path set drift")
        if _git("diff", "--name-only").strip():
            raise GovernanceError("G0 has unstaged tracked changes")
        if _git("ls-files", "--others", "--exclude-standard").strip():
            raise GovernanceError("G0 has untracked files after staging")
        return "STAGED_DIRECT_CHILD"
    if _commit_parent(head) != D4_B1:
        raise GovernanceError("committed G0 is not a direct child of D4 B1")
    if _changed_paths(head) != G0_STAGED_STATUS:
        raise GovernanceError("committed G0 changed-path set drift")
    if _git("status", "--porcelain=v1").strip():
        raise GovernanceError("committed G0 worktree must be clean")
    for repo_path in G0_REPO_PATHS:
        current = _read_regular(REPO_ROOT / repo_path, f"current G0 path {repo_path}", 2_000_000)
        if current != _git_bytes(head, repo_path):
            raise GovernanceError(f"current G0 blob drift: {repo_path}")
    return "COMMITTED_DIRECT_CHILD"


def verify(*, include_lifecycle: bool = True) -> dict[str, Any]:
    result = validate_content()
    lifecycle = validate_lifecycle() if include_lifecycle else "NOT_REQUESTED"
    result = dict(result)
    result["lifecycle"] = lifecycle
    result["status"] = "VERIFIED_P9_G0_POST_D4_GOVERNANCE_CLOSURE"
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="verify content and staged/committed lifecycle")
    parser.add_argument("--verify-content", action="store_true", help="verify content without the G0 path gate")
    arguments = parser.parse_args(argv)
    if arguments.verify == arguments.verify_content:
        parser.error("select exactly one of --verify or --verify-content")
    try:
        result = verify(include_lifecycle=arguments.verify)
    except GovernanceError as exc:
        print(json.dumps({"error": str(exc), "status": "INVALID_P9_G0_GOVERNANCE_CLOSURE"}, sort_keys=True))
        return 1
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
