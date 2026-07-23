#!/usr/bin/env python3
"""Frozen full-53-shard consumer plan; action is impossible before D21 authorization."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
SOURCE=HERE/"fh_l8_packed_q3_checkpoint_d11_bundle/checkpoint.bin"
SOURCE_SHA="db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231"
class ConsumerError(ValueError):pass
def _json(p):return json.loads(p.read_text(encoding="utf-8"))
def _sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build_plan(contract):
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D20":raise ConsumerError("identity drift")
 if _sha(Path(__file__))!=contract.get("runner_self_sha256"):raise ConsumerError("runner self pin drift")
 if _sha(SOURCE)!=contract["source"]["sha256"]:raise ConsumerError("packed q3 drift")
 source=contract["source"]
 if source!={"records":213099,"record_bytes":32,"sha256":SOURCE_SHA,"shard_size":4096,"shard_count":53,"last_shard_records":107}:raise ConsumerError("source plan drift")
 protocol=contract["full_protocol"]
 expected={"fresh_exclusive_scratch_required":True,"shared_append_spool_forbidden":True,"source_rehash_before_and_after_action":True,"partition_count":256,"partition_selector":"SHA256(target_u128_be)[0]","spill_record_bytes":32,"scaled_denominator":8,"exact_53_shard_frontier_required":True,"resume_requires_all_manifest_hashes":True,"resume_forbids_gap_overlap_or_orphan_bytes":True,"manifest_only_merge":True,"merge_partition_order":"000_to_255","merge_maximum_fan_in":32,"atomic_no_replace_target_publication":True,"terminal_execution_and_resource_receipt_required":True}
 if protocol!=expected:raise ConsumerError("full protocol drift")
 authorization=contract["execution_authorization"]
 if authorization!={"full_53_shard_execution_authorized":False,"q3_rows_authorized":0,"kernel_evaluations_authorized":0}:raise ConsumerError("authorization drift")
 return {"contract_id":contract["contract_id"],"status":"VERIFIED_D20_FULL_53_CONSUMER_IMPLEMENTATION_FROZEN_NO_EXECUTION","verified":True,"source_shards":53,"partitions":256,"execution_authorized":False,"action_entrypoint":"REJECTED_BEFORE_HAMILTONIAN_ACTION","next_gate":"FULL_53_SHARD_RESOURCE_PREFLIGHT_AND_AUTHORIZATION","authority_exclusions":contract["authority_exclusions"]}
def run(contract):
 build_plan(contract)
 raise ConsumerError("D20 full action is not authorized")
def main(argv=None):
 try:
  c=_json(HERE/"fh_l8_full_consumer_d20_contract.json");e=build_plan(c)
  if "--attempt-action" in list(sys.argv[1:] if argv is None else argv):run(c)
 except (OSError,json.JSONDecodeError,ConsumerError,KeyError,TypeError) as x:print(json.dumps({"status":"D20_CONSUMER_REJECTED","verified":False,"error":str(x)},sort_keys=True));return 1
 print(json.dumps(e,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
