#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent; C=HERE/"fh_l8_integrated_envelope_numeric_d61_contract.json"; R=HERE/"fh_l8_integrated_envelope_numeric_d61_result.json"
class D61NumericProofError(RuntimeError): pass
def verify()->dict[str,Any]:
 c=json.loads(C.read_text(encoding="utf-8"))
 if c.get("contract_id")!="FH-L8-INTEGRATED-ENVELOPE-NUMERIC-D61-V1": raise D61NumericProofError("id")
 if any(v=="TO_BE_FILLED" for v in c["source_pins"].values()): raise D61NumericProofError("unsealed source pin")
 for n,h in c["source_pins"].items():
  if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h: raise D61NumericProofError("pin mismatch")
 s=c["scratch"]; shortfall=s["design_required_bytes"]-s["registered_bytes"]
 if shortfall<0: raise D61NumericProofError("negative shortfall")
 statuses={"D58":json.loads((HERE/"fh_l8_allocator_numeric_proof_d58_result.json").read_text())["numeric_peak_memory_proven"],"D59":json.loads((HERE/"fh_l8_page_cache_numeric_proof_d59_result.json").read_text())["numeric_peak_memory_proven"],"D60":json.loads((HERE/"fh_l8_runtime_numeric_proof_d60_result.json").read_text())["numeric_runtime_seconds_proven"],"D23":False}
 unresolved=[k for k,v in statuses.items() if not v or (k=="D23" and shortfall>0)]
 result={"status":"VERIFIED_D61_INTEGRATED_ENVELOPE_FAIL_CLOSED","decision":"NO_GO_D61_INTEGRATED_ENVELOPE_INPUTS_INCOMPLETE","phase_count":4,"unresolved_closure_count":len(unresolved),"unresolved_closures":unresolved,"scratch_shortfall_bytes":shortfall,"numeric_peak_memory_proven":False,"numeric_runtime_seconds_proven":False,"full53_execution_authorized":False}
 if json.loads(R.read_text(encoding="utf-8"))!=result: raise D61NumericProofError("result drift")
 return result
if __name__=="__main__": print(json.dumps(verify(),indent=2,sort_keys=True))
