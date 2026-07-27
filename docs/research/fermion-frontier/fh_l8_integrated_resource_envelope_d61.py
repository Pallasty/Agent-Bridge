#!/usr/bin/env python3
"""Verify the D61 fail-closed resource-envelope reconciliation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

HERE=Path(__file__).resolve().parent
CONTRACT=HERE/"fh_l8_integrated_resource_envelope_d61_contract.json"
RESULT=HERE/"fh_l8_integrated_resource_envelope_d61_result.json"
class D61Error(RuntimeError): pass
def load(path: Path)->Mapping[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,Mapping): raise D61Error("object required")
    return value
def digest(path: Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def validate(c: Mapping[str,Any])->dict[str,Any]:
    if c.get("contract_id")!="FH-L8-INTEGRATED-RESOURCE-ENVELOPE-D61-V1": raise D61Error("id drift")
    pins=c.get("source_pins")
    if not isinstance(pins,Mapping) or len(pins)!=11: raise D61Error("source pin coverage drift")
    for name, expected in pins.items():
        if digest(HERE/name)!=expected: raise D61Error(f"pin drift: {name}")
    d56=load(HERE/"fh_l8_resource_closure_plan_d56_contract.json")
    d51=load(HERE/"fh_l8_full53_streaming_lifetime_d51_contract.json")
    d58=load(HERE/"fh_l8_live_allocation_bound_d58_contract.json")
    d59=load(HERE/"fh_l8_production_io_page_cache_d59_contract.json")
    if d56["work_packages"][4]["gate"]!="D61_INTEGRATED_RESOURCE_ENVELOPE_RECONCILIATION": raise D61Error("D56 handoff drift")
    phases=[row["phase"] for row in d51["lifetime_phases"]]
    envelope=c.get("phase_resource_envelope")
    if not isinstance(envelope,Mapping) or list(envelope)!=phases: raise D61Error("phase envelope drift")
    if [envelope[p]["allocation_expression"] for p in phases] != [d58["phase_expressions"][p] for p in phases]: raise D61Error("D58 allocation expression drift")
    if any(envelope[p]["runtime"]!="no_per_operation_rule" for p in phases): raise D61Error("D60 runtime disposition drift")
    if d59["decision"]!="NO_GO_D59_PAGE_CACHE_BOUND_MISSING_ENVIRONMENT_CONTRACT" or any("unbounded_without" not in envelope[p]["page_cache"] for p in phases): raise D61Error("D59 page-cache disposition drift")
    scratch=c.get("scratch_reconciliation")
    expected={"design_required_scratch_bytes":3110572064,"d23_registered_scratch_bytes":2750812950,"shortfall_bytes":359759114,"registered_meets_design_requirement":False}
    if scratch!=expected or scratch["design_required_scratch_bytes"]-scratch["d23_registered_scratch_bytes"]!=scratch["shortfall_bytes"]: raise D61Error("scratch reconciliation drift")
    expected_closures=["D58_independent_allocator_and_object_size_bounds","D59_filesystem_page_cache_environment_and_writeback_bound","D60_precommitted_runtime_rule_and_fixed_environment","D23_scratch_capacity_shortfall"]
    if c.get("unresolved_closures")!=expected_closures: raise D61Error("closure set drift")
    a=c.get("authority")
    zero=("scientific_kernel_calls_executed","object_measurements_executed","timing_measurements_executed","packed_q3_reads")
    closed=("production_io_executed","numeric_peak_memory_proven","numeric_runtime_seconds_proven","external_resource_reservation_admitted","full53_execution_authorized")
    if not isinstance(a,Mapping) or any(a[k]!=0 for k in zero) or any(a[k] is not False for k in closed): raise D61Error("authority open")
    if c.get("decision")!="NO_GO_D61_INTEGRATED_RESOURCE_ENVELOPE_INCOMPLETE": raise D61Error("decision drift")
    return {"status":"VERIFIED_D61_INTEGRATED_RESOURCE_ENVELOPE_INCOMPLETE","phase_count":4,"unresolved_closure_count":4,"scratch_shortfall_bytes":359759114,**a,"decision":c["decision"],"next_gate":c["next_gate"]}
def verify()->dict[str,Any]:
    expected=validate(load(CONTRACT))
    if load(RESULT)!=expected: raise D61Error("result drift")
    return expected
if __name__=="__main__": print(json.dumps(verify(),indent=2,sort_keys=True))
