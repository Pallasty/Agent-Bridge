#!/usr/bin/env python3
"""Static fail-closed q4-to-q5 cost gate; never executes q5."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
STATUS="NO_GO_D12_Q4_TO_Q5_CURRENT_D10_ENVELOPE"
class VerificationError(ValueError):pass
def _json(path):
 value=json.loads(path.read_text(encoding="utf-8"))
 if not isinstance(value,dict):raise VerificationError("JSON root must be object")
 return value
def recompute(contract):
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D12":raise VerificationError("identity drift")
 if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=contract.get("checker_self_sha256"):raise VerificationError("checker self pin drift")
 for pin in contract["source_pins"]:
  raw=(HERE/pin["path"]).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=pin["sha256"]:raise VerificationError("D11 source pin drift")
 d11=_json(HERE/"fh_l8_d11_full_action_result.json")
 if d11.get("status")!="VERIFIED_D11_FULL_DEPTH3_TO_DEPTH4_SIGNED_QUOTIENT_ACTION" or not d11.get("fourth_action_executed"):raise VerificationError("D11 result drift")
 q4=d11["target_records"];row=contract["row_terms_per_source"];group=contract["signed_group_order"];record=contract["spill_record_bytes"];caps=contract["current_d10_caps"]
 raw=q4*row;images=raw*group;source_images=q4*group;total_images=images+source_images;spill=raw*record
 expected={"q4_sources":10785545,"raw_candidate_upper_bound":2426747625,"candidate_group_image_upper_bound":19413981000,"source_group_image_upper_bound":86284360,"total_group_image_upper_bound":19500265360,"primary_spill_bytes_upper_bound":77655924000}
 actual={"q4_sources":q4,"raw_candidate_upper_bound":raw,"candidate_group_image_upper_bound":images,"source_group_image_upper_bound":source_images,"total_group_image_upper_bound":total_images,"primary_spill_bytes_upper_bound":spill}
 if actual!=expected:raise VerificationError("cost arithmetic drift")
 no_go={"raw_candidate_cap":raw>caps["max_raw_candidate_actions"],"group_image_cap":total_images>caps["max_total_group_images"],"spill_cap":spill>caps["max_cumulative_spill_write_bytes"],"source_checkpoint_cap":d11["target_payload_bytes"]>caps["max_live_algorithm_buffer_bytes"]}
 if not all(no_go.values()):raise VerificationError("current-envelope no-go drift")
 return {"contract_id":contract["contract_id"],"status":STATUS,"verified":True,"D11_q4_target_sha256":d11["target_sha256"],"costs":actual,"current_d10_no_go":no_go,"q5_executed":False,"next_gate":"Q4_TO_Q5_ALGORITHM_OR_RESOURCE_ENVELOPE_REDESIGN","degree6_remainder_bounded":False,"two_step_cumulative_error_bounded":False,"full_R100_error_bounded":False,"physical_reference_qualified":False,"ready_gate_eligible":False,"limitations":["All counts are static upper bounds from the D11 q4 target cardinality and 225-term row contract.","No q5 action, target vector, D6 remainder, cumulative, R100, physical reference, or READY authority."]}
def verify(contract,result):
 evidence=recompute(contract)
 if evidence!=result:raise VerificationError("result does not equal recomputed evidence")
 return evidence
def main(argv=None):
 try:
  c=_json(HERE/"fh_l8_q4_to_q5_cost_d12_contract.json");e=recompute(c)
  if "--evidence" not in list(sys.argv[1:] if argv is None else argv):e=verify(c,_json(HERE/"fh_l8_q4_to_q5_cost_d12_result.json"))
 except (OSError,json.JSONDecodeError,VerificationError,KeyError,TypeError) as exc:print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(exc)},sort_keys=True));return 1
 print(json.dumps(e,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
