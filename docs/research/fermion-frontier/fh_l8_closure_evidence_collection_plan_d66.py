#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;P=H/"fh_l8_closure_evidence_collection_plan_d66.json"
class D66Error(RuntimeError):pass
def verify():
 x=json.loads(P.read_text())
 if x["plan_id"]!="FH-L8-CLOSURE-EVIDENCE-COLLECTION-D66-V1":raise D66Error("id")
 for n,v in x["source_pins"].items():
  if hashlib.sha256((H/n).read_bytes()).hexdigest()!=v:raise D66Error("pin")
 rows=x["collection_order"]
 if [r["gate"] for r in rows]!=["D23","D59","D60","D58"] or any(len(r["packet"])<4 for r in rows):raise D66Error("order")
 if any(x["authority"].values()):raise D66Error("authority")
 return {"status":"VERIFIED_D66_CLOSURE_EVIDENCE_COLLECTION_PLAN","collection_step_count":4,"evidence_accepted":False,"decision":x["decision"]}
if __name__=="__main__":print(json.dumps(verify(),sort_keys=True))
