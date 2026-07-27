#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;P=H/"fh_l8_d58_allocator_proof_request_d70.json"
class D70Error(RuntimeError):pass
def verify():
 x=json.loads(P.read_text())
 if x["request_id"]!="FH-L8-D58-ALLOCATOR-PROOF-REQUEST-D70-V1":raise D70Error("id")
 for n,v in x["source_pins"].items():
  if hashlib.sha256((H/n).read_bytes()).hexdigest()!=v:raise D70Error("pin")
 if any(len(v)<3 for v in x["request"].values()) or x["state"]!="UNSENT_EMPTY_REQUEST" or x["authority"]!={"external_request_sent":False,"object_measurements_executed":0,"numeric_peak_memory_proven":False,"full53_execution_authorized":False}:raise D70Error("coverage")
 return {"status":"VERIFIED_D70_UNSENT_D58_ALLOCATOR_PROOF_REQUEST","field_group_count":3,"object_measurements_executed":0}
if __name__=="__main__":print(json.dumps(verify(),sort_keys=True))
