#!/usr/bin/env python3
"""Fail-closed D17 vector-custody disposition after the D16-F forensic gate."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
STATUS="NO_GO_D17_Q0_TO_Q4_DUAL_VECTOR_CUSTODY_INCOMPLETE"
class VerificationError(ValueError):pass
def _json(p):return json.loads(p.read_text(encoding="utf-8"))
def _sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def recompute(contract):
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D17":raise VerificationError("identity drift")
 if _sha(Path(__file__))!=contract.get("checker_self_sha256"):raise VerificationError("checker self pin drift")
 for pin in contract["source_pins"]:
  if _sha(HERE/pin["path"])!=pin["sha256"]:raise VerificationError("source pin drift")
 d16f=_json(HERE/"fh_l8_packed_consumer_forensic_d16_result.json")
 authority=d16f.get("authority",{})
 if d16f.get("status")!="NO_GO_D16_LEGACY_TARGET_CUSTODY_BROKEN_ASSOCIATED_SPOOL_DUPLICATED_TARGET_QUARANTINED":raise VerificationError("D16-F status drift")
 if authority.get("packed_q3_source_admissible") is not True or authority.get("legacy_full_action_target_scientifically_admitted") is not False:raise VerificationError("D16-F custody authority drift")
 custody=contract["vector_custody"]
 expected_custody={"q0_standalone_packed_payload_admitted":False,"q1_standalone_packed_payload_admitted":False,"q2_standalone_packed_payload_admitted":False,"q3_packed_payload_admitted":True,"q3_records":213099,"q3_bytes":6819168,"q3_sha256":"db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231","q4_payload_admitted":False,"q4_legacy_target_quarantined":True,"complete_q0_to_q4_custody":False}
 if custody!=expected_custody:raise VerificationError("vector custody drift")
 protocol=contract["fresh_successor_protocol"]
 expected_protocol={"fresh_exclusive_scratch_root_required":True,"committed_packed_q3_hash_verified_before_consume":True,"shared_append_spool_forbidden":True,"manifest_only_merge_and_fail_closed_recovery_required":True,"bounded_source_records":4096,"bounded_preflight_execution_authorized":False,"full_53_shard_execution_authorized":False,"dual_vector_contraction_authorized":False}
 if protocol!=expected_protocol:raise VerificationError("successor protocol drift")
 exclusions=contract["authority_exclusions"]
 if any(exclusions.values()):raise VerificationError("forbidden authority granted")
 return {"contract_id":contract["contract_id"],"status":STATUS,"verified":True,"q3_source_admissible":True,"q4_vector_admissible":False,"dual_vector_contraction_protocol_materializable":False,"fresh_bounded_4096_preflight_design_eligible":True,"fresh_bounded_4096_preflight_execution_authorized":False,"next_gate":"FRESH_EXCLUSIVE_PACKED_Q3_CONSUMER_IMPLEMENTATION_AND_BOUNDED_4096_PREFLIGHT_AUTHORIZATION","authority_exclusions":exclusions,"limitations":["The legacy q4 target is quarantined by D16-F and cannot supply a contraction operand.","No standalone committed q0, q1, or q2 packed payload is admitted by this gate.","No contraction, q5, D6 remainder, cumulative, R100, physical-reference, or READY authority."]}
def verify(c,r):
 e=recompute(c)
 if e!=r:raise VerificationError("result does not equal recomputed evidence")
 return e
def main(argv=None):
 try:
  c=_json(HERE/"fh_l8_vector_custody_d17_contract.json");e=recompute(c)
  if "--evidence" not in list(sys.argv[1:] if argv is None else argv):e=verify(c,_json(HERE/"fh_l8_vector_custody_d17_result.json"))
 except (OSError,json.JSONDecodeError,VerificationError,KeyError,TypeError) as x:print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(x)},sort_keys=True));return 1
 print(json.dumps(e,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
