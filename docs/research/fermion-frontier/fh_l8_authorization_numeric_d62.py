#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent; C=HERE/"fh_l8_authorization_numeric_d62_contract.json"; R=HERE/"fh_l8_authorization_numeric_d62_result.json"
class D62NumericProofError(RuntimeError): pass
def verify()->dict[str,Any]:
 c=json.loads(C.read_text(encoding="utf-8"))
 if c.get("contract_id")!="FH-L8-AUTHORIZATION-NUMERIC-D62-V1": raise D62NumericProofError("id")
 if any(v=="TO_BE_FILLED" for v in c["source_pins"].values()): raise D62NumericProofError("unsealed source pin")
 for n,h in c["source_pins"].items():
  if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h: raise D62NumericProofError("pin mismatch")
 predicates=c["predicate_values"]; missing=[p for p in c["required_predicates"] if predicates.get(p) is not True]
 authorized=not missing
 result={"status":"VERIFIED_D62_AUTHORIZATION_FAIL_CLOSED" if missing else "VERIFIED_D62_AUTHORIZATION_GRANTED","decision":"NO_GO_D62_CLOSURE_PREDICATES_UNSATISFIED" if missing else "GO_D62_AUTHORIZATION_PREDICATES_SATISFIED","predicate_count":len(predicates),"unsatisfied_predicate_count":len(missing),"unsatisfied_predicates":missing,"external_resource_reservation_admitted":False,"full53_execution_authorized":authorized,"full53_execution_performed":False}
 if json.loads(R.read_text(encoding="utf-8"))!=result: raise D62NumericProofError("result drift")
 return result
if __name__=="__main__": print(json.dumps(verify(),indent=2,sort_keys=True))
