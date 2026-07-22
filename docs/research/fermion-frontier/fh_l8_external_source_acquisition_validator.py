#!/usr/bin/env python3
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "fh_l8_external_source_acquisition_plan.json"
ROUTES = [
    "native_fermions", "dynamic_jw_local_grid_source_leading",
    "dynamic_jw_local_grid_figure_candidate_fit", "fsn_standard_figure_candidate_fit",
    "fsn_ladder_figure_candidate_fit",
]
CLASSES = {
    "PAPER_ONLY_EXTERNAL_EXPORT_REQUIRED",
    "PUBLIC_CODE_NO_FH_L8_TARGET_EXPORT",
    "PAPER_DATA_ONLY_EXTERNAL_EXPORT_REQUIRED",
}


def verify():
    plan = json.loads(PLAN.read_text())
    if plan["plan_id"] != "FH-L8-EXTERNAL-SOURCE-ACQUISITION-PLAN-V1":
        raise ValueError("plan identity")
    if plan["intake_contract_id"] != "FH-L8-EXTERNAL-EVIDENCE-INTAKE-V1":
        raise ValueError("intake binding")
    if plan["global_disposition"] != "NO_IMMEDIATE_ADMISSION_CANDIDATE; EXTERNAL_PRIMARY_EXPORTS_REQUIRED":
        raise ValueError("disposition")
    if any(plan["prohibitions"].values()):
        raise ValueError("prohibition inversion")
    requests = plan["route_requests"]
    if sorted(item["route"] for item in requests) != sorted(ROUTES):
        raise ValueError("route coverage")
    if any(item["classification"] not in CLASSES for item in requests):
        raise ValueError("unsupported classification")
    for item in requests:
        if item["priority"] not in (1, 2, 3) or not item["request"].strip():
            raise ValueError("request completeness")
        if not item["primary_sources"] or not all(url.startswith("https://") for url in item["primary_sources"]):
            raise ValueError("source custody")
    if len(plan["minimum_per_route_intake_payload"]) != 6:
        raise ValueError("intake payload")
    return {"status": "PASS", "next_state": "REQUEST_OR_LOCATE_VERSIONED_PRIMARY_EXPORTS"}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True, separators=(",", ":")))
