#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent; C=HERE/"fh_l8_owner_allocator_proof_d78_contract.json"; R=HERE/"fh_l8_owner_allocator_proof_d78_result.json"
class D78Error(RuntimeError): pass
def verify()->dict[str,Any]:
 c=json.loads(C.read_text())
 for n,h in c["source_pins"].items():
  if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h: raise D78Error("pin mismatch")
 missing=[v for v in c["variables"] if any(c["proof_inputs"][v][k] is None for k in c["required_fields"])]
 result={"status":"VERIFIED_D78_OWNER_ALLOCATOR_TEMPLATE_FAIL_CLOSED","decision":"NO_GO_D78_ALLOCATOR_NUMERIC_INPUTS_MISSING","variable_count":8,"missing_variable_count":len(missing),"missing_variables":missing,"owner_local_template_ready":True,"object_measurements_executed":0,"numeric_peak_memory_proven":False,"full53_execution_authorized":False}
 if json.loads(R.read_text())!=result: raise D78Error("result drift")
 return result
if __name__=="__main__": print(json.dumps(verify(),indent=2,sort_keys=True))
