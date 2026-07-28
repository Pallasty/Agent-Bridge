#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;P=H/"fh_l8_d60_runtime_environment_request_d69.json"
class D69Error(RuntimeError):pass
def verify():
 x=json.loads(P.read_text())
 if x["request_id"]!="FH-L8-D60-RUNTIME-ENVIRONMENT-REQUEST-D69-V1":raise D69Error("id")
 for n,v in x["source_pins"].items():
  if hashlib.sha256((H/n).read_bytes()).hexdigest()!=v:raise D69Error("pin")
 if any(len(v)<3 for v in x["request"].values()) or x["state"]!="UNSENT_EMPTY_REQUEST" or x["authority"]!={"external_request_sent":False,"timing_measurements_executed":0,"numeric_runtime_seconds_proven":False,"full53_execution_authorized":False}:raise D69Error("coverage")
 return {"status":"VERIFIED_D69_UNSENT_D60_RUNTIME_REQUEST","field_group_count":4,"timing_measurements_executed":0}
if __name__=="__main__":print(json.dumps(verify(),sort_keys=True))
