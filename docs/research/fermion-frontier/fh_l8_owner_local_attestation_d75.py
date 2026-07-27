#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent; C=HERE/"fh_l8_owner_local_attestation_d75_contract.json"; R=HERE/"fh_l8_owner_local_attestation_d75_result.json"; RES=Path("/Data/CascadeProjects/.ab-reservations/fh-l8-d23-capacity-reservation-v1.bin")
class D75Error(RuntimeError): pass
def verify()->dict[str,Any]:
 c=json.loads(C.read_text(encoding="utf-8"))
 for n,h in c["source_pins"].items():
  if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h: raise D75Error("source pin mismatch")
 a=c["owner_attestation"]; r=c["reservation"]
 if a["owner_identity"]!="pallasting" or a["owner_confirmation"] is not True: raise D75Error("owner confirmation")
 if not RES.is_file() or RES.stat().st_size!=r["logical_bytes"] or hashlib.sha256(RES.read_bytes()).hexdigest()!=r["sha256"]: raise D75Error("reservation mismatch")
 result={"status":"VERIFIED_D75_OWNER_LOCAL_ATTESTATION","owner_attestation_accepted":True,"logical_bytes":r["logical_bytes"],"allocated_blocks_512":r["allocated_blocks_512"],"capacity_attestation_admitted":False,"external_resource_reservation_admitted":False,"full53_execution_authorized":False,"decision":c["decision"]}
 if json.loads(R.read_text(encoding="utf-8"))!=result: raise D75Error("result drift")
 return result
if __name__=="__main__": print(json.dumps(verify(),indent=2,sort_keys=True))
