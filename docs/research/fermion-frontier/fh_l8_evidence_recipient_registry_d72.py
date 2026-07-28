#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;P=H/"fh_l8_evidence_recipient_registry_d72.json"
class D72Error(RuntimeError):pass
def verify():
 x=json.loads(P.read_text())
 if x["registry_id"]!="FH-L8-EVIDENCE-RECIPIENT-REGISTRY-D72-V1":raise D72Error("id")
 for n,v in x["source_pins"].items():
  if hashlib.sha256((H/n).read_bytes()).hexdigest()!=v:raise D72Error("pin")
 if [r["gate"] for r in x["channels"]]!=["D23","D59","D60","D58"] or any(len(r["required"])!=4 or r["assignment"] is not None for r in x["channels"]) or x["state"]!="UNASSIGNED_LOCAL_TEMPLATE" or any(x["authority"].values()):raise D72Error("state")
 return {"status":"VERIFIED_D72_UNASSIGNED_RECIPIENT_TEMPLATE","channel_count":4,"external_contact_attempted":False}
if __name__=="__main__":print(json.dumps(verify(),sort_keys=True))
