#!/usr/bin/env python3
"""Static protocol gate for a future FH-L8 packed depth-3 quotient checkpoint."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
STATUS="VERIFIED_D8_PACKED_DEPTH3_QUOTIENT_CHECKPOINT_PROTOCOL_NO_MATERIALIZATION"
class VerificationError(ValueError): pass
def _json(path):
 value=json.loads(path.read_text(encoding="utf-8"))
 if not isinstance(value,dict): raise VerificationError("JSON root must be object")
 return value
def _canonical(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")).hexdigest()
def recompute(contract):
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D8": raise VerificationError("identity drift")
 if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=contract.get("checker_self_sha256"): raise VerificationError("checker self pin drift")
 parent=contract.get("parent_d7",{});checker=HERE/parent.get("checker_path","");source=HERE/parent.get("contract_path","")
 if not checker.is_file() or not source.is_file(): raise VerificationError("D7 source missing")
 if hashlib.sha256(checker.read_bytes()).hexdigest()!=parent.get("checker_sha256") or hashlib.sha256(source.read_bytes()).hexdigest()!=parent.get("contract_sha256"): raise VerificationError("D7 source pin drift")
 d7=_json(source)
 if d7.get("contract_id")!="FH-L8-QUOTIENT-H-D3-TO-D4-DESIGN-GATE-V1" or d7.get("authority",{}).get("next_packed_source_checkpoint_protocol_design_eligible") is not True: raise VerificationError("D7 prerequisite drift")
 layout=contract.get("record_layout",{});fields=layout.get("fields")
 expected=[{"name":"representative_u128_be","offset":0,"bytes":16},{"name":"amplitude_i64_le","offset":16,"bytes":8},{"name":"orbit_size_u8","offset":24,"bytes":1},{"name":"reserved_zero","offset":25,"bytes":7}]
 if fields!=expected or layout.get("record_bytes")!=32 or sum(item["bytes"] for item in fields)!=32: raise VerificationError("record layout drift")
 source_spec=contract.get("source",{});schedule=contract.get("schedule",{});count=source_spec.get("record_count");size=schedule.get("shard_size")
 if (count,size)!=(213099,4096): raise VerificationError("source schedule drift")
 shards=(count+size-1)//size
 if schedule.get("shard_count")!=shards or schedule.get("last_shard_records")!=count-size*(shards-1): raise VerificationError("shard arithmetic drift")
 if source_spec.get("maximum_payload_bytes")!=count*32 or source_spec.get("maximum_payload_bytes")!=6819168: raise VerificationError("payload arithmetic drift")
 manifest=contract.get("manifest",{});required=["protocol_contract_sha256","d7_contract_sha256","source_full_vector_sha256","source_quotient_sha256","record_count","record_bytes","shard_count","shards","payload_sha256"]
 if manifest.get("required_fields")!=required or manifest.get("payload_sha256_before_materialization")!="UNSET": raise VerificationError("manifest schema drift")
 authority=contract.get("authority",{})
 for key in ("checkpoint_materialized","source_vector_materialized","depth3_to_depth4_action_authorized","depth3_to_depth4_action_executed","target_vector_materialized","runtime_feasibility_certified","memory_feasibility_certified","degree6_remainder_bounded","ready_gate_eligible"):
  if authority.get(key) is not False: raise VerificationError(f"authority drift: {key}")
 return {"contract_id":contract["contract_id"],"status":STATUS,"verified":True,"record_layout_verified":True,"payload_bytes":6819168,"shard_schedule":{"count":53,"full_shards":52,"last_shard_records":107},"manifest_hash_binding_required":True,"checkpoint_materialized":False,"depth3_to_depth4_action_authorized":False,"depth3_to_depth4_action_executed":False,"next_gate":"BOUNDED_PACKED_CHECKPOINT_PREFLIGHT_PROTOCOL","limitations":["This unit defines no checkpoint payload and executes no scientific state iteration.","A future materialization requires a new bounded preflight and separate execution authority.","No fourth Krylov action, remainder, cumulative, R100, physical reference, or READY authority."]}
def verify(contract,result):
 evidence=recompute(contract)
 if evidence!=result: raise VerificationError("result does not equal recomputed evidence")
 return evidence
def main(argv=None):
 try:
  contract=_json(HERE/"fh_l8_packed_depth3_checkpoint_d8_contract.json");evidence=recompute(contract)
  if "--evidence" not in list(sys.argv[1:] if argv is None else argv): evidence=verify(contract,_json(HERE/"fh_l8_packed_depth3_checkpoint_d8_result.json"))
 except (OSError,json.JSONDecodeError,VerificationError,TypeError,KeyError) as exc:
  print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(exc)},sort_keys=True));return 1
 print(json.dumps(evidence,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
