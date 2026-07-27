#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;P=H/"fh_l8_evidence_request_handoff_d71.json"
class D71Error(RuntimeError):pass
def verify():
 x=json.loads(P.read_text())
 if x["bundle_id"]!="FH-L8-EVIDENCE-REQUEST-HANDOFF-D71-V1":raise D71Error("id")
 for n,v in x["source_pins"].items():
  if hashlib.sha256((H/n).read_bytes()).hexdigest()!=v:raise D71Error("pin")
 if [r["gate"] for r in x["handoffs"]]!=["D23","D59","D60","D58"] or x["state"]!="LOCAL_UNSENT_HANDOFF_BUNDLE" or x["authority"]!={"external_messages_sent":0,"evidence_accepted":False,"full53_execution_authorized":False}:raise D71Error("state")
 return {"status":"VERIFIED_D71_LOCAL_UNSENT_EVIDENCE_HANDOFF","handoff_count":4,"external_messages_sent":0}
if __name__=="__main__":print(json.dumps(verify(),sort_keys=True))
