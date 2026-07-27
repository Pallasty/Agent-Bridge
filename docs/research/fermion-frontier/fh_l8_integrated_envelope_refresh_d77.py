#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent; C=HERE/"fh_l8_integrated_envelope_refresh_d77_contract.json"; R=HERE/"fh_l8_integrated_envelope_refresh_d77_result.json"
class D77Error(RuntimeError): pass
def verify()->dict[str,Any]:
 c=json.loads(C.read_text())
 for n,h in c["source_pins"].items():
  if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h: raise D77Error("pin mismatch")
 d76=json.loads((HERE/"fh_l8_owner_local_capacity_admission_d76_result.json").read_text())
 if d76["owner_local_capacity_admitted"] is not True: raise D77Error("D23 not admitted")
 unresolved=[g for g,f in {"D58": "fh_l8_allocator_numeric_proof_d58_result.json", "D59": "fh_l8_page_cache_numeric_proof_d59_result.json", "D60": "fh_l8_runtime_numeric_proof_d60_result.json"}.items() if not any(json.loads((HERE/f).read_text()).get(k) is True for k in (["numeric_peak_memory_proven"] if g=="D58" else ["numeric_peak_memory_proven"] if g=="D59" else ["numeric_runtime_seconds_proven"]))]
 result={"status":"VERIFIED_D77_INTEGRATED_ENVELOPE_REFRESH","decision":"NO_GO_D77_D58_D59_D60_REMAIN_UNRESOLVED","required_gate_count":4,"unresolved_gate_count":len(unresolved)+1,"unresolved_gates":["D23_external_reservation"]+unresolved,"owner_local_capacity_admitted":True,"external_resource_reservation_admitted":False,"full53_execution_authorized":False}
 if json.loads(R.read_text())!=result: raise D77Error("result drift")
 return result
if __name__=="__main__": print(json.dumps(verify(),indent=2,sort_keys=True))
