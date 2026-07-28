#!/usr/bin/env python3
"""Validate D59 I/O lifetime coverage and its fail-closed page-cache disposition."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any, Mapping
HERE=Path(__file__).resolve().parent; CONTRACT=HERE/"fh_l8_production_io_page_cache_d59_contract.json"; RESULT=HERE/"fh_l8_production_io_page_cache_d59_result.json"
class D59Error(RuntimeError): pass
def load(p:Path)->Mapping[str,Any]:
 v=json.loads(p.read_text());
 if not isinstance(v,Mapping): raise D59Error("object required")
 return v
def digest(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(c:Mapping[str,Any])->dict[str,Any]:
 if c.get("contract_id")!="FH-L8-PRODUCTION-IO-PAGE-CACHE-D59-V1":raise D59Error("id drift")
 for n,h in c["source_pins"].items():
  if digest(HERE/n)!=h:raise D59Error(f"pin drift: {n}")
 d51=load(HERE/"fh_l8_full53_streaming_lifetime_d51_contract.json"); d56=load(HERE/"fh_l8_resource_closure_plan_d56_contract.json")
 if d56["work_packages"][2]["gate"]!="D59_PRODUCTION_IO_PAGE_CACHE_BOUND":raise D59Error("handoff drift")
 rows=c.get("io_lifetimes"); phases=[x["phase"] for x in d51["lifetime_phases"]]
 if not isinstance(rows,list) or [x.get("phase") for x in rows]!=phases:raise D59Error("phase coverage drift")
 policy=c.get("fixed_policy")
 if policy.get("partition_count")!=256 or policy.get("maximum_merge_fan_in")!=32 or policy.get("simultaneous_spill_generations")!=2:raise D59Error("I/O shape drift")
 if policy.get("writeback_and_fsync_policy")!="UNSPECIFIED_BLOCKING" or policy.get("page_cache_environment_contract")!="MISSING":raise D59Error("page cache disposition drift")
 if len(c.get("required_to_close",[]))!=5 or len(c.get("forbidden_claims",[]))!=4:raise D59Error("closure boundary drift")
 a=c["authority"]
 if any(a.get(k) is not False for k in ("production_io_executed","numeric_peak_memory_proven","numeric_runtime_seconds_proven","external_resource_reservation_admitted","full53_execution_authorized")):raise D59Error("authority open")
 if a.get("scientific_kernel_calls_executed")!=0 or a.get("packed_q3_reads")!=0:raise D59Error("execution drift")
 return {"status":"VERIFIED_D59_PRODUCTION_IO_LIFETIME_PAGE_CACHE_BOUND_INCOMPLETE","fixed_io_lifetime_count":len(rows),"required_closure_item_count":len(c["required_to_close"]),**a,"decision":c["decision"],"next_gate":c["next_gate"]}
def verify()->dict[str,Any]:
 x=validate(load(CONTRACT));
 if load(RESULT)!=x:raise D59Error("result drift")
 return x
if __name__=="__main__":print(json.dumps(verify(),indent=2,sort_keys=True))
