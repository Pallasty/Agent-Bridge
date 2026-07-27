#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any,Mapping
HERE=Path(__file__).resolve().parent; CONTRACT=HERE/"fh_l8_runtime_rule_d60_contract.json"; RESULT=HERE/"fh_l8_runtime_rule_d60_result.json"
class D60Error(RuntimeError):pass
def load(p:Path)->Mapping[str,Any]:
 x=json.loads(p.read_text());
 if not isinstance(x,Mapping):raise D60Error("object required")
 return x
def digest(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(c:Mapping[str,Any])->dict[str,Any]:
 if c.get("contract_id")!="FH-L8-RUNTIME-RULE-D60-V1":raise D60Error("id drift")
 for n,h in c["source_pins"].items():
  if digest(HERE/n)!=h:raise D60Error(f"pin drift: {n}")
 d51=load(HERE/"fh_l8_full53_streaming_lifetime_d51_contract.json"); d56=load(HERE/"fh_l8_resource_closure_plan_d56_contract.json")
 if d56["work_packages"][3]["gate"]!="D60_RUNTIME_BOUND_OR_PRECOMMITTED_MARGIN_RULE":raise D60Error("handoff drift")
 expected={k:v for k,v in d51["runtime_work_units"].items() if k!="host_seconds_bound_proven"}
 if c["operation_population"]!=expected:raise D60Error("population drift")
 env=c["environment_definition"]
 if len(env)!=5 or any(value is not False for key,value in env.items() if key!="adapter_source_pin_required") or env.get("adapter_source_pin_required") is not True:raise D60Error("environment disposition drift")
 if len(c["admissible_runtime_rule_forms"])!=2 or len(c["required_before_measurement"])!=4 or len(c["forbidden_margin_sources"])!=3:raise D60Error("rule boundary drift")
 a=c["authority"]
 if any(a.get(k)!=0 for k in ("timing_measurements_executed","scientific_kernel_calls_executed","packed_q3_reads")):raise D60Error("execution drift")
 if any(a.get(k)is not False for k in ("numeric_runtime_seconds_proven","numeric_peak_memory_proven","external_resource_reservation_admitted","full53_execution_authorized")):raise D60Error("authority open")
 return {"status":"VERIFIED_D60_PREMEASUREMENT_RUNTIME_RULE_ENVIRONMENT_AND_MARGIN_PENDING","admissible_runtime_rule_form_count":2,"environment_field_count":len(env),"required_before_measurement_count":4,"forbidden_margin_source_count":3,**a,"decision":c["decision"],"next_gate":c["next_gate"]}
def verify()->dict[str,Any]:
 x=validate(load(CONTRACT));
 if load(RESULT)!=x:raise D60Error("result drift")
 return x
if __name__=="__main__":print(json.dumps(verify(),indent=2,sort_keys=True))
