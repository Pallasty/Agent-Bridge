#!/usr/bin/env python3
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "fh_l8_public_network_deep_audit_contract.json").read_text())
RESULT = json.loads((HERE / "fh_l8_public_network_deep_audit_result.json").read_text())


def verify():
    if RESULT["contract_id"] != CONTRACT["contract_id"]:
        raise ValueError("contract identity")
    if RESULT["workload_fingerprint"] != CONTRACT["workload_fingerprint"]:
        raise ValueError("workload identity")
    if RESULT["search_coverage"] != {name: True for name in CONTRACT["required_search_classes"]}:
        raise ValueError("search coverage")
    if list(RESULT["route_results"]) != CONTRACT["required_routes"]:
        raise ValueError("route coverage")
    if any(item["status"] != "UNRESOLVED_EXTERNAL_EXPORT_REQUIRED" for item in RESULT["route_results"].values()):
        raise ValueError("route status")
    if RESULT["admitted_exports"] or RESULT["third_party_code_executed"] or RESULT["paper_or_figure_sequence_reconstructed"]:
        raise ValueError("evidence boundary")
    if any(CONTRACT["admission_boundary"][key] for key in (
        "third_party_code_executed", "third_party_package_installed",
        "paper_or_figure_sequence_reconstructed", "method_code_equated_with_target_export",
    )):
        raise ValueError("contract prohibition")
    decisions = {item["decision"] for item in RESULT["candidate_register"]}
    if decisions != {"REJECT_AS_TARGET_EXPORT", "REJECT_AS_NATIVE_TARGET_EXPORT", "CONTEXT_ONLY"}:
        raise ValueError("candidate decisions")
    if RESULT["audit_disposition"] != CONTRACT["expected_disposition"]:
        raise ValueError("audit disposition")
    if RESULT["next_state"] != CONTRACT["expected_next_state"]:
        raise ValueError("next state")
    if RESULT["scientific_authority"] != "NONE_FOR_FH_L8_CROSS_ROUTE_EXPORT_COMPARISON":
        raise ValueError("scientific authority")
    return {"status": "PASS", "next_state": RESULT["next_state"]}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True, separators=(",", ":")))
