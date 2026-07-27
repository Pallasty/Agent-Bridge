#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any,Mapping
HERE=Path(__file__).resolve().parent; CONTRACT=HERE/"fh_l8_closure_evidence_intake_d63_contract.json"; RESULT=HERE/"fh_l8_closure_evidence_intake_d63_result.json"
class D63Error(RuntimeError):pass
def load(p:Path)->Mapping[str,Any]:
 x=json.loads(p.read_text());
 if not isinstance(x,Mapping):raise D63Error("object required")
 return x
def validate(c:Mapping[str,Any])->dict[str,Any]:
 if c.get("contract_id")!="FH-L8-CLOSURE-EVIDENCE-INTAKE-D63-V1":raise D63Error("id drift")
 for n,h in c["source_pins"].items():
  if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h:raise D63Error("pin drift")
 slots=c.get("evidence_slots",[])
 if len(slots)!=4 or len({x.get("predicate") for x in slots})!=4 or any(len(x.get("required_identity",[]))<3 or len(x.get("reject_if",[]))<3 for x in slots):raise D63Error("slot coverage drift")
 if c.get("intake_state")!="EMPTY_NO_EVIDENCE_ACCEPTED" or c.get("decision")!="NO_GO_D63_EVIDENCE_INTAKE_EMPTY":raise D63Error("intake state drift")
 if any(c["authority"].values()):raise D63Error("authority open")
 return {"status":"VERIFIED_D63_EMPTY_CLOSURE_EVIDENCE_INTAKE","evidence_slot_count":4,"evidence_accepted":False,"decision":c["decision"]}
def verify()->dict[str,Any]:
 x=validate(load(CONTRACT));
 if load(RESULT)!=x:raise D63Error("result drift")
 return x
if __name__=="__main__":print(json.dumps(verify(),sort_keys=True))
