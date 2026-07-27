#!/usr/bin/env python3
import hashlib, json
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent; C=HERE/"fh_l8_page_cache_numeric_proof_d59_contract.json"; R=HERE/"fh_l8_page_cache_numeric_proof_d59_result.json"
class D59NumericProofError(RuntimeError): pass
def verify()->dict[str,Any]:
 c=json.loads(C.read_text(encoding="utf-8"))
 if c.get("contract_id")!="FH-L8-PAGE-CACHE-NUMERIC-PROOF-D59-V1": raise D59NumericProofError("id")
 if any(v=="TO_BE_FILLED" for v in c["source_pins"].values()): raise D59NumericProofError("unsealed source pin")
 for n,h in c["source_pins"].items():
  if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h: raise D59NumericProofError(f"pin mismatch: {n}")
 if list(c["proof_inputs"])!=c["phases"]: raise D59NumericProofError("phase coverage")
 missing=[]; peak=0
 for phase in c["phases"]:
  row=c["proof_inputs"][phase]
  if any(row.get(k) is None for k in c["required_fields_per_phase"]): missing.append(phase); continue
  if row["writeback_multiplier"]<1 or any(not isinstance(row[k],int) or row[k]<0 for k in c["required_fields_per_phase"]): raise D59NumericProofError("invalid numeric input")
  peak=max(peak,row["base_file_bytes"]*row["writeback_multiplier"])
 if missing:
  result={"status":"VERIFIED_D59_PAGE_CACHE_PROOF_FAIL_CLOSED","decision":"NO_GO_D59_PAGE_CACHE_INPUTS_INCOMPLETE","phase_count":4,"missing_phase_count":len(missing),"missing_phases":missing,"recomputed_peak_bytes":None,"numeric_peak_memory_proven":False,"production_io_executed":False,"full53_execution_authorized":False}
 else:
  result={"status":"VERIFIED_D59_PAGE_CACHE_PROOF_RECOMPUTED","decision":"GO_D59_PAGE_CACHE_PROOF_RECOMPUTED","phase_count":4,"missing_phase_count":0,"missing_phases":[],"recomputed_peak_bytes":peak,"numeric_peak_memory_proven":True,"production_io_executed":False,"full53_execution_authorized":False}
 if json.loads(R.read_text(encoding="utf-8"))!=result: raise D59NumericProofError("result drift")
 return result
if __name__=="__main__": print(json.dumps(verify(),indent=2,sort_keys=True))
