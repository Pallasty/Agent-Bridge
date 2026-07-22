#!/usr/bin/env python3
"""Reconcile the historical D5A-derived byte-table D6 with D5 R1 lanes."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "fh_l8_d5_d6_descendant_reconciliation.json"
R1_CHECKER = HERE / "fh_l8_d5_dual_track_reconciliation_checker.py"
STATUS = "VERIFIED_D5_D6_DESCENDANT_SCOPE_RECONCILIATION"
R1_ID = "FH-L8-D5-DUAL-TRACK-R1"
R2_ID = "FH-L8-D5-D6-DESCENDANT-R2"
PREFIX_ALIAS = "FH-L8-D5-EVIDENCE-SIGNED-D4-PREFIX-V1"
FULL_ALIAS = "FH-L8-D5-EVIDENCE-SYMMETRY-ORBIT-QUOTIENT-V1"
D6_ALIAS = "FH-L8-D6-EVIDENCE-BYTE-TABLE-SUPPORT-ORBIT-V1"
LEGACY_D5_ID = "FH-L8-INDEPENDENT-REFERENCE-D5"
LEGACY_D6_ID = "FH-L8-INDEPENDENT-REFERENCE-D6"
R1_COMMIT = "cbd5668e42c6a73237a31a07112466dfc8a80739"
REPOSITORY_INTEGRATION_COMMIT = "7a1d02e8e910f1b25547c68b795cf7f4e404a0f0"
D6_OUTCOME_COMMIT = "e45b5b9f68520289d3396c0af071019856afe56e"
D6_INTEGRATION_COMMIT = "77475550b96dee1a862e9f11046de8b097d9d063"
SHA_RE = re.compile(r"[0-9a-f]{40}")
CURRENT_AUTHORITY = {
    "byte_table_support_orbit_canonicalization_executed": True,
    "full_depth3_support_orbit_count_verified": True,
    "depth0_to_depth3_quotient_transitions_executed_and_verified": True,
    "future_quotient_hamiltonian_design_eligible": True,
    "depth3_to_depth4_quotient_hamiltonian_action_executed": False,
    "depth3_to_depth4_execution_authorized": False,
    "fourth_hamiltonian_action_executed": False,
    "degree6_remainder_bounded": False,
    "two_step_cumulative_error_bounded": False,
    "full_R100_error_bounded": False,
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}


class VerificationError(ValueError):
    pass


def _load_json_bytes(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise VerificationError("JSON root must be an object")
    return value


def _git(*args: str) -> bytes:
    root = subprocess.check_output(
        ["git", "-C", str(HERE), "rev-parse", "--show-toplevel"],
        stderr=subprocess.DEVNULL,
    ).decode("ascii").strip()
    return subprocess.check_output(["git", "-C", root, *args], stderr=subprocess.DEVNULL)


def _verify_commit(record: Mapping[str, Any], expected_parents: list[str]) -> None:
    if set(record) != {"commit", "tree", "parents"}:
        raise VerificationError("commit record schema drift")
    commit = record["commit"]
    if not isinstance(commit, str) or SHA_RE.fullmatch(commit) is None:
        raise VerificationError("full commit id required")
    if _git("rev-parse", f"{commit}^{{commit}}").decode("ascii").strip() != commit:
        raise VerificationError("commit id is not exact")
    if _git("rev-parse", f"{commit}^{{tree}}").decode("ascii").strip() != record["tree"]:
        raise VerificationError("commit tree drift")
    parents = _git("rev-list", "--parents", "-n", "1", commit).decode("ascii").split()[1:]
    if parents != expected_parents or record["parents"] != expected_parents:
        raise VerificationError("commit parent drift")


def _verify_artifacts(
    commit: str,
    artifacts: list[Mapping[str, Any]],
    expected_paths: set[str],
) -> dict[str, bytes]:
    if not isinstance(artifacts, list) or len(artifacts) != len(expected_paths):
        raise VerificationError("artifact count drift")
    if {item.get("path") for item in artifacts} != expected_paths:
        raise VerificationError("artifact family drift")
    loaded: dict[str, bytes] = {}
    for artifact in artifacts:
        if set(artifact) != {"path", "mode", "blob", "bytes", "sha256"}:
            raise VerificationError("artifact schema drift")
        path = artifact["path"]
        relative = f"docs/research/fermion-frontier/{path}"
        raw = _git("show", f"{commit}:{relative}")
        mode = _git("ls-tree", commit, relative).decode("ascii").split()[0]
        blob = _git("rev-parse", f"{commit}:{relative}").decode("ascii").strip()
        if mode != artifact["mode"] or blob != artifact["blob"]:
            raise VerificationError(f"Git identity drift: {path}")
        if len(raw) != artifact["bytes"] or hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
            raise VerificationError(f"raw identity drift: {path}")
        if (HERE / path).read_bytes() != raw:
            raise VerificationError(f"working artifact drift: {path}")
        loaded[path] = raw
    return loaded


def _load_r1(manifest: Mapping[str, Any]) -> dict[str, Any]:
    record = manifest["r1_snapshot"]
    if set(record) != {"reconciliation_id", "commit_record", "artifacts"}:
        raise VerificationError("R1 snapshot schema drift")
    if record["reconciliation_id"] != R1_ID:
        raise VerificationError("R1 identity drift")
    commit_record = record["commit_record"]
    _verify_commit(commit_record, [REPOSITORY_INTEGRATION_COMMIT])
    if commit_record["commit"] != R1_COMMIT:
        raise VerificationError("R1 commit drift")
    loaded = _verify_artifacts(
        R1_COMMIT,
        record["artifacts"],
        {
            "fh_l8_d5_dual_track_reconciliation_checker.py",
            "fh_l8_d5_dual_track_reconciliation.json",
            "FH_L8_D5_DUAL_TRACK_RECONCILIATION_ZH.md",
        },
    )
    r1_manifest = _load_json_bytes(loaded["fh_l8_d5_dual_track_reconciliation.json"])
    spec = importlib.util.spec_from_file_location("fh_l8_d5_r1", R1_CHECKER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    evidence = module.recompute(r1_manifest)
    if evidence.get("status") != module.STATUS or evidence.get("verified") is not True:
        raise VerificationError("R1 checker evidence drift")
    return r1_manifest


def _verify_d6_descendant(
    record: Mapping[str, Any], r1_manifest: Mapping[str, Any]
) -> dict[str, Any]:
    if set(record) != {
        "route_alias",
        "original_contract_id",
        "historical_parent_contract_id",
        "resolved_parent_evidence_lane_alias",
        "scope",
        "preregistration_evidence",
        "outcome",
        "integration",
        "artifacts",
        "result_status",
        "performance_record",
        "selected_as_complementary_support_orbit_input",
    }:
        raise VerificationError("D6 descendant schema drift")
    if (
        record["route_alias"] != D6_ALIAS
        or record["original_contract_id"] != LEGACY_D6_ID
        or record["historical_parent_contract_id"] != LEGACY_D5_ID
        or record["resolved_parent_evidence_lane_alias"] != PREFIX_ALIAS
    ):
        raise VerificationError("D6 route identity drift")
    if record["preregistration_evidence"] is not False:
        raise VerificationError("D6 preregistration must remain unestablished")
    outcome = record["outcome"]
    integration = record["integration"]
    _verify_commit(outcome, ["64438c47be710835626dea0ceb2521b6634951dc"])
    _verify_commit(
        integration,
        ["ec5777e284585377896e7e50503a54dcd95a9b82", D6_OUTCOME_COMMIT],
    )
    if outcome["commit"] != D6_OUTCOME_COMMIT or integration["commit"] != D6_INTEGRATION_COMMIT:
        raise VerificationError("D6 topology identity drift")
    for path in (
        "fh_l8_byte_table_orbit_d6_checker.py",
        "fh_l8_byte_table_orbit_d6_contract.json",
        "fh_l8_byte_table_orbit_d6_result.json",
    ):
        relative = f"docs/research/fermion-frontier/{path}"
        try:
            _git("cat-file", "-e", f"64438c47be710835626dea0ceb2521b6634951dc:{relative}")
        except subprocess.CalledProcessError:
            pass
        else:
            raise VerificationError("D6 triplet existed in its parent commit")
    loaded = _verify_artifacts(
        D6_OUTCOME_COMMIT,
        record["artifacts"],
        {
            "fh_l8_byte_table_orbit_d6_checker.py",
            "fh_l8_byte_table_orbit_d6_contract.json",
            "fh_l8_byte_table_orbit_d6_result.json",
        },
    )
    contract = _load_json_bytes(loaded["fh_l8_byte_table_orbit_d6_contract.json"])
    result = _load_json_bytes(loaded["fh_l8_byte_table_orbit_d6_result.json"])
    if (
        contract.get("contract_id") != LEGACY_D6_ID
        or contract.get("parent_contract_id") != LEGACY_D5_ID
        or result.get("contract_id") != LEGACY_D6_ID
    ):
        raise VerificationError("D6 embedded ids drift")
    prefix = r1_manifest["routes"][0]
    expected_pins = [
        {"path": item["path"], "sha256": item["sha256"]}
        for item in prefix["artifacts"]
    ]
    if contract.get("source_pins") != expected_pins:
        raise VerificationError("D6 parent pins do not resolve uniquely to D5A")
    if result.get("status") != "VERIFIED_D6_BYTE_TABLE_SIGNED_D4_DEPTH3_ORBITS":
        raise VerificationError("D6 result status drift")
    if record["result_status"] != result["status"]:
        raise VerificationError("D6 manifest/result status mismatch")
    if result.get("depth3_orbit") != {
        "digest": "7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26",
        "orbits": 213099,
        "states": 1704285,
    }:
        raise VerificationError("D6 full support-orbit record drift")
    if (
        result.get("signed_support_equivalence_samples") != 4096
        or result.get("canonicalization_within_seconds_cap") is not True
        or result.get("fourth_layer_feasibility") != "NOT_EXECUTED_OR_CERTIFIED"
    ):
        raise VerificationError("D6 scope boundary drift")
    for claim in (
        "degree6_remainder_bounded",
        "two_step_cumulative_error_bounded",
        "full_R100_error_bounded",
        "physical_reference_qualified",
        "ready_gate_eligible",
    ):
        if result.get(claim) is not False:
            raise VerificationError("D6 authority uplift")
    if record["performance_record"] != {
        "maximum_seconds": 240,
        "within_cap": True,
        "exact_elapsed_seconds_retained_in_result": False,
    }:
        raise VerificationError("D6 performance custody drift")
    if "canonicalization_seconds" in result or "canonicalization_seconds_rounded" in result:
        raise VerificationError("unexpected exact elapsed time in D6 result")
    if (
        record["scope"] != "full_depth3_signed_support_orbit_enumeration_only"
        or record["selected_as_complementary_support_orbit_input"] is not True
    ):
        raise VerificationError("D6 scope selection drift")
    full_result = json.loads(
        (HERE / "fh_l8_symmetry_orbit_quotient_d5_result.json").read_text(encoding="utf-8")
    )
    full_depth3 = full_result["krylov_prefix"]["depth_records"][3]
    if (full_depth3["full_state_count"], full_depth3["orbit_representative_count"]) != (
        result["depth3_orbit"]["states"],
        result["depth3_orbit"]["orbits"],
    ):
        raise VerificationError("D6 support orbit count does not match full D5B quotient")
    return result


def recompute(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if set(manifest) != {
        "schema_version",
        "reconciliation_id",
        "status",
        "checker_self_sha256",
        "repository_integration",
        "r1_snapshot",
        "known_descendant",
        "selection",
        "authority",
        "limitations",
    }:
        raise VerificationError("R2 manifest schema drift")
    if manifest.get("schema_version") != 1 or manifest.get("reconciliation_id") != R2_ID:
        raise VerificationError("R2 identity drift")
    if manifest.get("status") != STATUS:
        raise VerificationError("R2 status drift")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != manifest["checker_self_sha256"]:
        raise VerificationError("R2 checker self pin drift")
    repository = manifest["repository_integration"]
    _verify_commit(
        repository,
        [
            "85dcc018fd18c6af5bd58fb930bd2e261ddf0c9e",
            "17ff4b2677254f1895075d9fcdc69ef400ad601c",
        ],
    )
    if repository["commit"] != REPOSITORY_INTEGRATION_COMMIT:
        raise VerificationError("repository integration identity drift")
    r1_manifest = _load_r1(manifest)
    _verify_d6_descendant(manifest["known_descendant"], r1_manifest)
    root = _git("rev-parse", "--show-toplevel").decode("ascii").strip()
    for ancestor in (
        R1_COMMIT,
        D6_OUTCOME_COMMIT,
        D6_INTEGRATION_COMMIT,
        "2f9556a986c50a42ff3096ded45b75e39c5a61a9",
    ):
        subprocess.check_call(
            ["git", "-C", root, "merge-base", "--is-ancestor", ancestor, "HEAD"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    subprocess.check_call(
        [
            "git",
            "-C",
            root,
            "merge-base",
            "--is-ancestor",
            D6_INTEGRATION_COMMIT,
            REPOSITORY_INTEGRATION_COMMIT,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    selection = manifest["selection"]
    expected_selection = {
        "required_full_quotient_semantics_route_alias": FULL_ALIAS,
        "complementary_support_orbit_route_alias": D6_ALIAS,
        "future_contract_id_policy": "new_globally_unique_route_specific_id_required",
        "occupied_legacy_contract_ids": [LEGACY_D5_ID, LEGACY_D6_ID],
        "authority_ceiling": "FUTURE_QUOTIENT_HAMILTONIAN_DESIGN_ONLY",
        "evidence_is_additive": False,
        "relation": "D6_parallel_shared_D4_support_orbit_count_matches_D5B_without_quotient_H_execution",
    }
    if selection != expected_selection:
        raise VerificationError("R2 selection drift")
    if manifest["authority"] != CURRENT_AUTHORITY:
        raise VerificationError("R2 authority drift")
    if manifest["limitations"] != [
        "The D5A-derived D6 checker, contract, and result first appear together; preregistration is unestablished.",
        "The exact 14.856-second console observation is not retained in the D6 result and is not certified.",
        "The byte-table result certifies support-orbit canonicalization, not quotient Hamiltonian amplitudes or a fourth H action.",
        "The full D5B and D6 support-orbit records agree on counts but are complementary, not additive evidence.",
        "No remainder, cumulative, R100, physical-reference, hardware, quantum-advantage, or READY claim is certified.",
    ]:
        raise VerificationError("R2 limitations drift")
    return {
        "reconciliation_id": R2_ID,
        "status": STATUS,
        "verified": True,
        "d5_r1_status": r1_manifest["status"],
        "known_descendant_route_alias": D6_ALIAS,
        "required_full_quotient_semantics_route_alias": FULL_ALIAS,
        "authority": dict(CURRENT_AUTHORITY),
    }


def main() -> int:
    try:
        evidence = recompute(_load_json_bytes(MANIFEST.read_bytes()))
    except (
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        VerificationError,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        print(json.dumps({"status": "VERIFICATION_FAILED", "verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
