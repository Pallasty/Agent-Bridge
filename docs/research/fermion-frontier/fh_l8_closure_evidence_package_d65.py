#!/usr/bin/env python3
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE/"fh_l8_closure_evidence_package_d65.json"
class D65Error(RuntimeError):pass
def verify():
 x=json.loads(P.read_text())
 if x.get("package_id")!="FH-L8-CLOSURE-EVIDENCE-PACKAGE-D65-V1" or x.get("state")!="EMPTY_NO_EVIDENCE_ACCEPTED":raise D65Error("state")
 if set(x.get("slots",{}))!={"D58","D59","D60","D23"} or any(len(v.get("required",[]))!=4 or v.get("evidence") is not None for v in x["slots"].values()):raise D65Error("slot")
 if any(x.get("authority",{}).values()):raise D65Error("authority")
 return {"status":"VERIFIED_D65_EMPTY_FOUR_PATH_EVIDENCE_PACKAGE","slot_count":4,"evidence_accepted":False}
if __name__=="__main__":print(json.dumps(verify(),sort_keys=True))
