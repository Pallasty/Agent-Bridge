#!/usr/bin/env python3
"""Static D13 selector: q5 redesign without a commutation shortcut."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
STATUS="VERIFIED_D13_OBSERVABLE_ADJOINT_CONTRACTION_DESIGN_REQUIRED"
class VerificationError(ValueError):pass
def _json(path):return json.loads(path.read_text(encoding="utf-8"))
def recompute(contract):
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D13":raise VerificationError("identity drift")
 if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=contract.get("checker_self_sha256"):raise VerificationError("checker self pin drift")
 for pin in contract["source_pins"]:
  if hashlib.sha256((HERE/pin["path"]).read_bytes()).hexdigest()!=pin["sha256"]:raise VerificationError("source pin drift")
 d12=_json(HERE/"fh_l8_q4_to_q5_cost_d12_result.json")
 if d12.get("status")!="NO_GO_D12_Q4_TO_Q5_CURRENT_D10_ENVELOPE" or d12.get("q5_executed") is not False:raise VerificationError("D12 boundary drift")
 costs=d12["costs"]
 if costs["primary_spill_bytes_upper_bound"]!=77655924000 or costs["total_group_image_upper_bound"]!=19500265360:raise VerificationError("D12 cost drift")
 routes=contract["routes"]
 if routes["full_q5_materialization"]["current_d10_eligible"] or routes["resource_expansion"]["authorized"] or routes["commutation_shortcut"]["valid_for_staggered_magnetization"] or routes["commutation_shortcut"]["valid_for_double_occupancy"]:raise VerificationError("route authority drift")
 if routes["observable_adjoint_contraction"]["preconditions_certified"] or routes["observable_adjoint_contraction"]["executed"]:raise VerificationError("adjoint route prematurely authorized")
 return {"contract_id":contract["contract_id"],"status":STATUS,"verified":True,"D12_costs":costs,"route_decisions":{"full_q5_materialization":"NO_GO_CURRENT_D10_ENVELOPE","resource_expansion":"NOT_AUTHORIZED","commutation_shortcut":"SEMANTICALLY_INVALID_NO_OBSERVABLE_COMMUTES_WITH_HOPPING_H","observable_adjoint_contraction":"DESIGN_ONLY_NEXT"},"q5_executed":False,"next_gate":"OBSERVABLE_SPECIFIC_ADJOINT_CONTRACTION_CONTRACT_DESIGN","degree6_remainder_bounded":False,"two_step_cumulative_error_bounded":False,"full_R100_error_bounded":False,"physical_reference_qualified":False,"ready_gate_eligible":False,"limitations":["No equality replacing O H^5 by H^5 O is available for either observable.","The adjoint contraction route has no certified identity, resource bound, or execution authority yet.","No q5, D6 remainder, cumulative, R100, physical reference, or READY authority."]}
def verify(contract,result):
 evidence=recompute(contract)
 if evidence!=result:raise VerificationError("result does not equal recomputed evidence")
 return evidence
def main(argv=None):
 try:
  c=_json(HERE/"fh_l8_q5_redesign_d13_contract.json");e=recompute(c)
  if "--evidence" not in list(sys.argv[1:] if argv is None else argv):e=verify(c,_json(HERE/"fh_l8_q5_redesign_d13_result.json"))
 except (OSError,json.JSONDecodeError,VerificationError,KeyError,TypeError) as exc:print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(exc)},sort_keys=True));return 1
 print(json.dumps(e,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
