#!/usr/bin/env python3
"""Static D19 decision gate after externally verified D18-C bounded evidence."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
STATUS="NO_GO_D19_FULL_53_SHARD_REQUIRES_NEW_IMPLEMENTATION_AND_AUTHORIZATION"
class VerificationError(ValueError):pass
def _json(path):return json.loads(path.read_text(encoding="utf-8"))
def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def recompute(contract):
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D19":raise VerificationError("identity drift")
 if _sha(Path(__file__))!=contract.get("checker_self_sha256"):raise VerificationError("checker self pin drift")
 for pin in contract["source_pins"]:
  if _sha(HERE/pin["path"])!=pin["sha256"]:raise VerificationError("source pin drift")
 d18=_json(HERE/"fh_l8_fresh_consumer_d18c_result.json")
 if d18.get("status")!="VERIFIED_D18C_FRESH_EXCLUSIVE_PACKED_Q3_BOUNDED_4096_PREFLIGHT":raise VerificationError("D18-C status drift")
 if d18["authority"].get("bounded_4096_preflight_executed") is not True or d18["authority"].get("full_53_shard_authorization_granted") is not False:raise VerificationError("D18-C authority drift")
 review=contract["bounded_preflight_review"]
 expected_review={"external_checker_status":"VERIFIED_D18C_RESULT_AND_EXTERNAL_TERMINAL_EVIDENCE","external_scratch_verified":True,"source_rows":4096,"kernel_evaluations":8192,"spill_records":868786,"target_records":424682,"target_sha256":"8b43b76f1e7a45f12e220905bcba41dc7cfef9fce66f0257cb3c9dff9623fa5f","global_semantic_sha256":"da049d945738630c66b8118ec58627a09910887e7263f91e4b08417ef7bafb34","memory_peak_bytes":224747520,"memory_max_bytes":536870912,"memory_swap_max_bytes":0,"memory_events_clean":True}
 if review!=expected_review:raise VerificationError("bounded review drift")
 decision=contract["full_execution_decision"]
 expected_decision={"full_53_shard_execution_authorized":False,"reason":"bounded_runner_and_contract_do_not_authorize_full_53_shard_execution","separate_full_implementation_required":True,"separate_full_contract_freeze_required":True,"fresh_full_resource_envelope_required":True,"partial_target_forbidden_as_full_q4_operand":True}
 if decision!=expected_decision:raise VerificationError("full decision drift")
 exclusions=contract["authority_exclusions"]
 if any(exclusions.values()):raise VerificationError("forbidden authority granted")
 return {"contract_id":contract["contract_id"],"status":STATUS,"verified":True,"bounded_preflight_externally_verified":True,"full_53_shard_execution_authorized":False,"next_gate":"FULL_53_SHARD_CONSUMER_IMPLEMENTATION_AND_CONTRACT_FREEZE","authority_exclusions":exclusions,"limitations":["Bounded evidence does not authorize a full 53-shard action.","The bounded partial target remains forbidden as a full-q4 or contraction operand.","No q5, remainder, cumulative, R100, physical-reference, or READY authority."]}
def verify(c,r):
 e=recompute(c)
 if e!=r:raise VerificationError("result does not equal recomputed evidence")
 return e
def main(argv=None):
 try:
  c=_json(HERE/"fh_l8_full_run_decision_d19_contract.json");e=recompute(c)
  if "--evidence" not in list(sys.argv[1:] if argv is None else argv):e=verify(c,_json(HERE/"fh_l8_full_run_decision_d19_result.json"))
 except (OSError,json.JSONDecodeError,VerificationError,KeyError,TypeError) as x:print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(x)},sort_keys=True));return 1
 print(json.dumps(e,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
