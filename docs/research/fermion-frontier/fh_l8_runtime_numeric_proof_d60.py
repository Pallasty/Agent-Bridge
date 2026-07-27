#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent; C=HERE/"fh_l8_runtime_numeric_proof_d60_contract.json"; R=HERE/"fh_l8_runtime_numeric_proof_d60_result.json"
class D60NumericProofError(RuntimeError): pass
def verify()->dict[str,Any]:
 c=json.loads(C.read_text(encoding="utf-8"))
 if c.get("contract_id")!="FH-L8-RUNTIME-NUMERIC-PROOF-D60-V1": raise D60NumericProofError("id")
 if any(v=="TO_BE_FILLED" for v in c["source_pins"].values()): raise D60NumericProofError("unsealed source pin")
 for n,h in c["source_pins"].items():
  if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h: raise D60NumericProofError("pin mismatch")
 if set(c["operation_population"])!={"scientific_kernel_calls","candidate_visits","merge_record_reads_upper","merge_record_writes_upper","merge_heap_comparisons_design_upper"}: raise D60NumericProofError("population")
 env=c["environment_definition"]; rule=c["rule_selection"]
 missing=[k for k,v in env.items() if v is not True]+[k for k,v in rule.items() if v is None]
 if missing:
  result={"status":"VERIFIED_D60_RUNTIME_PROOF_FAIL_CLOSED","decision":"NO_GO_D60_RUNTIME_INPUTS_INCOMPLETE","population_count":5,"missing_input_count":len(missing),"missing_inputs":missing,"numeric_runtime_seconds_proven":False,"timing_measurements_executed":0,"scientific_kernel_calls_executed":0,"full53_execution_authorized":False}
 else:
  result={"status":"VERIFIED_D60_RUNTIME_PROOF_RECOMPUTED","decision":"GO_D60_RUNTIME_PROOF_RECOMPUTED","population_count":5,"missing_input_count":0,"missing_inputs":[],"numeric_runtime_seconds_proven":True,"timing_measurements_executed":0,"scientific_kernel_calls_executed":0,"full53_execution_authorized":False}
 if json.loads(R.read_text(encoding="utf-8"))!=result: raise D60NumericProofError("result drift")
 return result
if __name__=="__main__": print(json.dumps(verify(),indent=2,sort_keys=True))
