#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any,Mapping
HERE=Path(__file__).resolve().parent; CONTRACT=HERE/"fh_l8_reopening_contract_d63.json"
class D63Error(RuntimeError):pass
def load(p:Path)->Mapping[str,Any]:
 x=json.loads(p.read_text());
 if not isinstance(x,Mapping):raise D63Error("object required")
 return x
def digest(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def verify()->dict[str,Any]:
 c=load(CONTRACT)
 if c.get("contract_id")!="FH-L8-REOPENING-CONTRACT-D63-V1":raise D63Error("id drift")
 for n,h in c["source_pins"].items():
  if digest(HERE/n)!=h:raise D63Error(f"pin drift: {n}")
 d62=load(HERE/"fh_l8_external_authorization_d62_contract.json")
 predicates=d62["required_closure_predicates"]
 if list(c["predicate_evidence"])!=predicates or c["reopening_order"]!=[*predicates,"D62_reverification"]:raise D63Error("predicate order drift")
 if any(len(v)!=2 for v in c["predicate_evidence"].values()) or len(c["rejection_conditions"])!=4:raise D63Error("evidence coverage drift")
 a=c["authority"]
 if any(a[k]!=0 for k in ("scientific_kernel_calls_executed","object_measurements_executed","timing_measurements_executed","packed_q3_reads")) or a["full53_execution_authorized"] is not False:raise D63Error("authority open")
 return {"status":c["status"],"predicate_count":len(predicates),"evidence_item_count":sum(map(len,c["predicate_evidence"].values())),"rejection_condition_count":4,**a,"next_gate":c["next_gate"]}
if __name__=="__main__":print(json.dumps(verify(),indent=2,sort_keys=True))
