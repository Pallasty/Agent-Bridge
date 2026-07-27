#!/usr/bin/env python3
"""Verify D62 denies reservation and full-53 authorization until all gates close."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any,Mapping
HERE=Path(__file__).resolve().parent; CONTRACT=HERE/"fh_l8_external_authorization_d62_contract.json"; RESULT=HERE/"fh_l8_external_authorization_d62_result.json"
class D62Error(RuntimeError): pass
def load(p:Path)->Mapping[str,Any]:
 x=json.loads(p.read_text(encoding="utf-8"));
 if not isinstance(x,Mapping): raise D62Error("object required")
 return x
def digest(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(c:Mapping[str,Any])->dict[str,Any]:
 if c.get("contract_id")!="FH-L8-EXTERNAL-AUTHORIZATION-DECISION-D62-V1":raise D62Error("id drift")
 if len(c.get("source_pins",{}))!=7:raise D62Error("source pins drift")
 for n,h in c["source_pins"].items():
  if digest(HERE/n)!=h:raise D62Error(f"pin drift: {n}")
 d56=load(HERE/"fh_l8_resource_closure_plan_d56_contract.json"); d23=load(HERE/"fh_l8_full_resource_envelope_d23_result.json"); d58=load(HERE/"fh_l8_live_allocation_bound_d58_result.json"); d59=load(HERE/"fh_l8_production_io_page_cache_d59_result.json"); d60=load(HERE/"fh_l8_runtime_rule_d60_result.json"); d61=load(HERE/"fh_l8_integrated_resource_envelope_d61_result.json")
 if d56["work_packages"][5]["gate"]!="D62_EXTERNAL_RESERVATION_AND_FULL53_AUTHORIZATION_DECISION":raise D62Error("D56 handoff drift")
 names=["D58_numeric_peak_memory_proven","D59_page_cache_environment_bound","D60_runtime_rule_precommitted_and_environment_fixed","D23_registered_scratch_meets_design_requirement","D61_integrated_envelope_GO"]
 if c.get("required_closure_predicates")!=names or c.get("observed_predicate_values")!={n:False for n in names}:raise D62Error("predicate inventory drift")
 if d58["numeric_peak_memory_proven"] is not False or d59["decision"]!="NO_GO_D59_PAGE_CACHE_BOUND_MISSING_ENVIRONMENT_CONTRACT" or d60["decision"]!="NO_GO_D60_RUNTIME_RULE_ENVIRONMENT_AND_MARGIN_NOT_PRECOMMITTED" or d23["status"]!="NO_GO_D23_FULL_53_RESOURCE_ENVELOPE_INCOMPLETE" or d61["decision"]!="NO_GO_D61_INTEGRATED_RESOURCE_ENVELOPE_INCOMPLETE":raise D62Error("source disposition drift")
 a=c.get("authority",{}); zero=("scientific_kernel_calls_executed","object_measurements_executed","timing_measurements_executed","packed_q3_reads")
 closed=("external_resource_reservation_attempted","external_resource_reservation_admitted","production_io_executed","numeric_peak_memory_proven","numeric_runtime_seconds_proven","full53_execution_authorized","full53_execution_performed")
 if any(a.get(k)!=0 for k in zero) or any(a.get(k) is not False for k in closed):raise D62Error("authority open")
 if c.get("decision")!="NO_GO_D62_CLOSURE_PREDICATES_UNSATISFIED_NO_EXTERNAL_RESERVATION_OR_FULL53_AUTHORIZATION":raise D62Error("decision drift")
 return {"status":"VERIFIED_D62_FAIL_CLOSED_AUTHORIZATION_DENIAL","unsatisfied_predicate_count":5,**a,"decision":c["decision"],"reopen_condition":c["reopen_condition"]}
def verify()->dict[str,Any]:
 x=validate(load(CONTRACT));
 if load(RESULT)!=x:raise D62Error("result drift")
 return x
if __name__=="__main__":print(json.dumps(verify(),indent=2,sort_keys=True))
