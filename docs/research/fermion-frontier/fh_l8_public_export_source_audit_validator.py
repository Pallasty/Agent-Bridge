#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_public_export_source_audit_contract.json"
RESULT = HERE / "fh_l8_public_export_source_audit_result.json"


def verify():
    contract = json.loads(CONTRACT.read_text())
    result = json.loads(RESULT.read_text())
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=HERE.parents[2], check=True,
        capture_output=True, text=True
    ).stdout.strip()
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", contract["required_ancestor_commit"], head],
        cwd=HERE.parents[2], check=True, capture_output=True
    )
    if result["contract_id"] != contract["contract_id"]:
        raise ValueError("contract identity")
    if result["working_tree_commit"] != contract["required_ancestor_commit"]:
        raise ValueError("audit lifecycle")
    if contract["audit_boundaries"] != {
        "network_download_or_execution_performed": False,
        "third_party_package_installation_performed": False,
        "manual_or_figure_reconstruction_admissible": False,
        "absence_claim_scope": "only_the_named_public_sources_and_searches_on_audit_date",
    }:
        raise ValueError("audit boundary")
    if result["audit_disposition"] != contract["expected_disposition"] or result["admitted_exports"]:
        raise ValueError("admission disposition")
    if result["synthetic_or_figure_reconstructed_sequence_accepted"]:
        raise ValueError("synthetic sequence")
    if list(result["route_disposition"]) != contract["required_routes"]:
        raise ValueError("route coverage")
    if set(result["route_disposition"].values()) != {"UNRESOLVED_EXTERNAL_EXPORT_REQUIRED"}:
        raise ValueError("route closure")
    for source in result["sources"]:
        if not source["url"].startswith("https://") or source["public_machine_readable_target_export_identified"]:
            raise ValueError("source record")
    request = result["minimum_external_acquisition_request"]
    if len(request["per_required_route"]) != 5 or not request["acceptance_rule"].startswith("admit only"):
        raise ValueError("acquisition request")
    return {"status": "PASS", "next_state": result["next_state"]}


if __name__ == "__main__":
    try:
        print(json.dumps(verify(), sort_keys=True, separators=(",", ":")))
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
