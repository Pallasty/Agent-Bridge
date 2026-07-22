#!/usr/bin/env python3
"""Fail-closed identity reconciliation for the two immutable FH-L8 D5 lanes."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "fh_l8_d5_dual_track_reconciliation.json"
STATUS = "VERIFIED_D5_DUAL_TRACK_IDENTITY_RECONCILIATION"
LEGACY_ID = "FH-L8-INDEPENDENT-REFERENCE-D5"
PREFIX_ALIAS = "FH-L8-D5-EVIDENCE-SIGNED-D4-PREFIX-V1"
FULL_ALIAS = "FH-L8-D5-EVIDENCE-SYMMETRY-ORBIT-QUOTIENT-V1"
COMMON_BASE_COMMIT = "ae3935774d80f37b10f8317d0e17d339f03436cc"
PREFIX_OUTCOME_COMMIT = "72fe3b79a79501d5d523dc959a6a98b36a470bd4"
PREFIX_INTEGRATION_COMMIT = "64438c47be710835626dea0ceb2521b6634951dc"
FULL_PROTOCOL_COMMIT = "6daf30daeeb375962b9986af5df91517d8a4a8ec"
FULL_OUTCOME_COMMIT = "2f9556a986c50a42ff3096ded45b75e39c5a61a9"
INTEGRATION_COMMIT = "17ff4b2677254f1895075d9fcdc69ef400ad601c"
RECONCILED_AUTHORITY = {
    "d6_design_eligible": True,
    "d6_execution_authorized": False,
    "fourth_hamiltonian_action_executed": False,
    "degree6_remainder_bounded": False,
    "two_step_cumulative_error_bounded": False,
    "full_R100_error_bounded": False,
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}
SHA_RE = re.compile(r"[0-9a-f]{40}")


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
    return subprocess.check_output(
        ["git", "-C", root, *args], stderr=subprocess.DEVNULL
    )


def _verify_commit(record: Mapping[str, Any], expected_parent_count: int) -> None:
    if set(record) != {"commit", "tree", "parents"}:
        raise VerificationError("commit record schema drift")
    commit = record["commit"]
    if not isinstance(commit, str) or SHA_RE.fullmatch(commit) is None:
        raise VerificationError("full commit id required")
    resolved = _git("rev-parse", f"{commit}^{{commit}}").decode("ascii").strip()
    if resolved != commit:
        raise VerificationError("commit id is not exact")
    tree = _git("rev-parse", f"{commit}^{{tree}}").decode("ascii").strip()
    if tree != record["tree"]:
        raise VerificationError("commit tree drift")
    actual = _git("rev-list", "--parents", "-n", "1", commit).decode("ascii").split()[1:]
    if len(actual) != expected_parent_count or actual != record["parents"]:
        raise VerificationError("commit parent drift")


def _verify_artifacts(commit: str, artifacts: list[Mapping[str, Any]]) -> dict[str, bytes]:
    if not isinstance(artifacts, list) or len(artifacts) != 3:
        raise VerificationError("exact checker/contract/result artifact triplet required")
    loaded: dict[str, bytes] = {}
    for artifact in artifacts:
        if set(artifact) != {"path", "mode", "blob", "bytes", "sha256"}:
            raise VerificationError("artifact schema drift")
        path = artifact["path"]
        if not isinstance(path, str) or "/" in path or not path.startswith("fh_l8_"):
            raise VerificationError("unsafe artifact path")
        relative = f"docs/research/fermion-frontier/{path}"
        raw = _git("show", f"{commit}:{relative}")
        blob = _git("rev-parse", f"{commit}:{relative}").decode("ascii").strip()
        mode = _git("ls-tree", commit, relative).decode("ascii").split()[0]
        if mode != artifact["mode"] or blob != artifact["blob"]:
            raise VerificationError(f"Git identity drift: {path}")
        if len(raw) != artifact["bytes"]:
            raise VerificationError(f"byte-size drift: {path}")
        if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
            raise VerificationError(f"SHA-256 drift: {path}")
        if (HERE / path).read_bytes() != raw:
            raise VerificationError(f"working artifact differs from immutable outcome: {path}")
        loaded[path] = raw
    return loaded


def _verify_prefix_lane(route: Mapping[str, Any], common_base: str) -> None:
    if set(route) != {
        "route_alias",
        "legacy_contract_id",
        "scope",
        "preregistration_evidence",
        "protocol_freeze",
        "outcome",
        "artifacts",
        "result_status",
        "authority_ceiling",
        "downstream_design_selected",
    }:
        raise VerificationError("prefix route schema drift")
    if route["route_alias"] != PREFIX_ALIAS:
        raise VerificationError("prefix route alias drift")
    if route["legacy_contract_id"] != LEGACY_ID:
        raise VerificationError("prefix legacy id drift")
    if route["preregistration_evidence"] is not False or route["protocol_freeze"] is not None:
        raise VerificationError("prefix preregistration must remain unestablished")
    outcome = route["outcome"]
    _verify_commit(outcome, 1)
    if outcome["commit"] != PREFIX_OUTCOME_COMMIT or outcome["parents"] != [common_base]:
        raise VerificationError("prefix lane is not a parallel child of the common base")
    if {artifact.get("path") for artifact in route["artifacts"]} != {
        "fh_l8_signed_d4_orbit_d5_checker.py",
        "fh_l8_signed_d4_orbit_d5_contract.json",
        "fh_l8_signed_d4_orbit_d5_result.json",
    }:
        raise VerificationError("prefix artifact family drift")
    loaded = _verify_artifacts(outcome["commit"], route["artifacts"])
    contract = _load_json_bytes(loaded["fh_l8_signed_d4_orbit_d5_contract.json"])
    result = _load_json_bytes(loaded["fh_l8_signed_d4_orbit_d5_result.json"])
    if contract.get("contract_id") != LEGACY_ID or result.get("contract_id") != LEGACY_ID:
        raise VerificationError("prefix embedded contract id drift")
    if result.get("status") != "VERIFIED_D5_SIGNED_D4_CUSTODY_AND_DEPTH3_ORBIT_PREFIX_BOUNDARY":
        raise VerificationError("prefix result status drift")
    if route["result_status"] != result["status"]:
        raise VerificationError("prefix manifest/result status mismatch")
    if result.get("depth3_full_orbit_count_certified") is not False:
        raise VerificationError("prefix lane cannot certify full depth 3")
    for claim in (
        "degree6_remainder_bounded",
        "two_step_cumulative_error_bounded",
        "full_R100_error_bounded",
        "physical_reference_qualified",
        "ready_gate_eligible",
    ):
        if result.get(claim) is not False:
            raise VerificationError("prefix authority uplift")
    depth3 = result["orbit_records"]["depth3"]["orbit_measurement"]
    if (depth3["processed"], depth3["orbits"]) != (100000, 71064):
        raise VerificationError("prefix boundary drift")
    if route["downstream_design_selected"] is not False:
        raise VerificationError("prefix lane cannot be selected as the full quotient design input")
    if (
        route["scope"] != "historical_signed_D4_custody_and_depth3_prefix_only"
        or route["authority_ceiling"] != "HISTORICAL_PARTIAL_PREFIX_AND_CUSTODY"
    ):
        raise VerificationError("prefix scope or authority drift")


def _verify_full_lane(route: Mapping[str, Any], common_base: str) -> None:
    if set(route) != {
        "route_alias",
        "legacy_contract_id",
        "scope",
        "preregistration_evidence",
        "protocol_freeze",
        "outcome",
        "artifacts",
        "result_status",
        "authority_ceiling",
        "downstream_design_selected",
    }:
        raise VerificationError("full route schema drift")
    if route["route_alias"] != FULL_ALIAS:
        raise VerificationError("full route alias drift")
    if route["legacy_contract_id"] != LEGACY_ID:
        raise VerificationError("full legacy id drift")
    if route["preregistration_evidence"] is not True:
        raise VerificationError("full lane preregistration drift")
    protocol = route["protocol_freeze"]
    outcome = route["outcome"]
    _verify_commit(protocol, 1)
    _verify_commit(outcome, 1)
    if (
        protocol["commit"] != FULL_PROTOCOL_COMMIT
        or outcome["commit"] != FULL_OUTCOME_COMMIT
        or protocol["parents"] != [common_base]
        or outcome["parents"] != [protocol["commit"]]
    ):
        raise VerificationError("full lane chronology drift")
    if {artifact.get("path") for artifact in route["artifacts"]} != {
        "fh_l8_symmetry_orbit_quotient_d5_checker.py",
        "fh_l8_symmetry_orbit_quotient_d5_contract.json",
        "fh_l8_symmetry_orbit_quotient_d5_result.json",
    }:
        raise VerificationError("full artifact family drift")
    loaded = _verify_artifacts(outcome["commit"], route["artifacts"])
    contract = _load_json_bytes(loaded["fh_l8_symmetry_orbit_quotient_d5_contract.json"])
    result = _load_json_bytes(loaded["fh_l8_symmetry_orbit_quotient_d5_result.json"])
    if contract.get("contract_id") != LEGACY_ID or result.get("contract_id") != LEGACY_ID:
        raise VerificationError("full embedded contract id drift")
    result_path = "docs/research/fermion-frontier/fh_l8_symmetry_orbit_quotient_d5_result.json"
    try:
        _git("cat-file", "-e", f"{protocol['commit']}:{result_path}")
    except subprocess.CalledProcessError:
        pass
    else:
        raise VerificationError("full result existed in protocol freeze")
    for name in (
        "fh_l8_symmetry_orbit_quotient_d5_checker.py",
        "fh_l8_symmetry_orbit_quotient_d5_contract.json",
    ):
        relative = f"docs/research/fermion-frontier/{name}"
        if _git("show", f"{protocol['commit']}:{relative}") != loaded[name]:
            raise VerificationError("full protocol bytes drift")
    if result.get("status") != "VERIFIED_D5_SYMMETRY_ORBIT_QUOTIENT_ADMISSIBLE_FOR_D6_DESIGN":
        raise VerificationError("full result status drift")
    if route["result_status"] != result["status"]:
        raise VerificationError("full manifest/result status mismatch")
    if result.get("authority") != RECONCILED_AUTHORITY:
        raise VerificationError("full result authority drift")
    depth = result["krylov_prefix"]["depth_records"]
    if [(item["full_state_count"], item["orbit_representative_count"]) for item in depth] != [
        (1, 1),
        (225, 29),
        (24421, 3116),
        (1704285, 213099),
    ]:
        raise VerificationError("full quotient counts drift")
    transitions = result["krylov_prefix"]["quotient_transition_records"]
    if [item["source_depth"] for item in transitions] != [0, 1, 2] or not all(
        item["matches_next_full_quotient"] is True for item in transitions
    ):
        raise VerificationError("full quotient transition evidence drift")
    if route["downstream_design_selected"] is not True:
        raise VerificationError("full lane must be the explicit downstream design input")
    if (
        route["scope"] != "full_depth3_symmetry_quotient_and_D6_design_gate"
        or route["authority_ceiling"] != "D6_DESIGN_ELIGIBLE_ONLY"
    ):
        raise VerificationError("full scope or authority drift")


def recompute(manifest: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "reconciliation_id",
        "status",
        "checker_self_sha256",
        "common_base",
        "integration",
        "identity_collision",
        "routes",
        "shared_consistency",
        "non_equivalences",
        "selection",
        "authority",
        "limitations",
    }
    if set(manifest) != required or manifest.get("schema_version") != 1:
        raise VerificationError("reconciliation manifest schema drift")
    if manifest.get("reconciliation_id") != "FH-L8-D5-DUAL-TRACK-R1":
        raise VerificationError("reconciliation id drift")
    if manifest.get("status") != STATUS:
        raise VerificationError("reconciliation status drift")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != manifest["checker_self_sha256"]:
        raise VerificationError("reconciliation checker self pin drift")

    common = manifest["common_base"]
    _verify_commit(common, 2)
    if common["commit"] != COMMON_BASE_COMMIT:
        raise VerificationError("common base identity drift")
    integration = manifest["integration"]
    _verify_commit(integration, 2)
    if integration["commit"] != INTEGRATION_COMMIT or integration["parents"] != [
        PREFIX_INTEGRATION_COMMIT,
        FULL_OUTCOME_COMMIT,
    ]:
        raise VerificationError("integration identity drift")
    routes = manifest["routes"]
    if not isinstance(routes, list) or len(routes) != 2:
        raise VerificationError("exactly two reconciled lanes required")
    aliases = [route.get("route_alias") for route in routes]
    if aliases != [PREFIX_ALIAS, FULL_ALIAS] or len(set(aliases)) != 2:
        raise VerificationError("route aliases drift")
    _verify_prefix_lane(routes[0], common["commit"])
    _verify_full_lane(routes[1], common["commit"])
    for route in routes:
        subprocess.check_call(
            ["git", "-C", _git("rev-parse", "--show-toplevel").decode("ascii").strip(),
             "merge-base", "--is-ancestor", route["outcome"]["commit"], integration["commit"]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    collision = manifest["identity_collision"]
    if collision != {
        "legacy_contract_id": LEGACY_ID,
        "route_count": 2,
        "bare_legacy_contract_id_forbidden": True,
        "required_lookup_identity": "route_alias+artifact_path+git_blob+raw_sha256+bytes+commit",
    }:
        raise VerificationError("legacy identity collision policy drift")
    shared = manifest["shared_consistency"]
    if shared != {
        "group_order": 8,
        "neel_characters": [1] * 8,
        "observable_invariance": True,
        "depth0_to_depth2_full_and_orbit_counts": [[1, 1], [225, 29], [24421, 3116]],
    }:
        raise VerificationError("shared-consistency record drift")
    selection = manifest["selection"]
    if selection != {
        "downstream_design_route_alias": FULL_ALIAS,
        "authority_ceiling": "D6_DESIGN_ELIGIBLE_ONLY",
        "evidence_is_additive": False,
        "relation": "full_lane_closes_unmeasured_full_depth3_and_quotient_transition_gaps_without_retroactive_prefix_validation",
    }:
        raise VerificationError("route selection policy drift")
    authority = manifest["authority"]
    expected_authority = dict(RECONCILED_AUTHORITY)
    if authority != expected_authority:
        raise VerificationError("reconciled authority drift")
    if manifest["non_equivalences"] != [
        "The prefix lane and full lane use different orbit digest serializations; digest equality is not claimed.",
        "The full lane did not replay or retroactively validate the prefix lane's deterministic 100000-state digest.",
        "The 71064 prefix representatives are not a permutation-independent bound or ratio for the 213099 full representatives.",
    ]:
        raise VerificationError("non-equivalence ledger drift")
    if manifest["limitations"] != [
        "The bare legacy contract id is ambiguous and cannot be used for lookup or authorization.",
        "The full lane closes gaps left unmeasured by the prefix lane but does not replace its provenance.",
        "No fourth Hamiltonian action or D6 execution is authorized.",
        "No remainder, cumulative, R100, physical-reference, hardware, quantum-advantage, or READY claim is certified.",
    ]:
        raise VerificationError("limitations ledger drift")
    return {
        "reconciliation_id": manifest["reconciliation_id"],
        "status": STATUS,
        "verified": True,
        "route_aliases": aliases,
        "legacy_contract_id": LEGACY_ID,
        "bare_legacy_contract_id_forbidden": True,
        "downstream_design_route_alias": FULL_ALIAS,
        "authority": expected_authority,
    }


def main() -> int:
    try:
        manifest = _load_json_bytes(MANIFEST.read_bytes())
        evidence = recompute(manifest)
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
