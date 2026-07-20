#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OWNER="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_concurrent_replay_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json";SEMANTIC="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json";T13="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_synthetic_exact_t12_receipt_track_reserved_issuer_nonce_sequence_and_packet_identity_submitted_issuer_nonce_sequence_and_packet_identity_verifier_isolated_lab_v1_pack_v0.json";DOMAIN="AB_T14_CONCURRENT_REPLAY_AUTHORITY_V1"
UNIT="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CONCURRENT_REPLAY_SYNTHETIC_EXACT_T13_RECEIPT_TRACK_RESERVATION_KEY_CONTENDER_A_AND_B_OBSERVED_GENERATION_AND_CAS_RESULT_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
REQ=("reservation_key_sha256","contender_a_observed_generation","contender_b_observed_generation","contender_a_cas_result","contender_b_cas_result");MATCH=("t13_receipt_content_sha256","track_id",*REQ);ORDER=("MANAGED_SPANNER_CLOUD_KMS","SELF_HOSTED_ETCD_OPENBAO");RECEIPTS=("5f42f7ee62ddfb470113726fd1ced0e0cbaa0be2162f8665027692690626154a","ecc9d3f5ca738f3bfc199c35dde7f178657865aee2e05f3561a0ee11c39848ae")
def path(x):
 p=ROOT.joinpath(*x.split('/'));r=p.resolve(strict=True);assert ROOT in r.parents and p.is_file()and not p.is_symlink();return p
def load(x):return json.loads(path(x).read_text())
def sha(x):return hashlib.sha256(path(x).read_bytes()).hexdigest()
def validate(o,s,m):
 assert o["decision"]=="AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_T14_CONCURRENT_REPLAY_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED" and o["next_unit"]==UNIT
 assert o["actor"]=={"class":"PROJECT_OWNER","id":"pallasting","directive":"CONTINUE_NEXT_STEP_USING_AGENT_RECOMMENDED_ORDER"}
 assert o["predecessor"]=={"exact_release_commit":"375aae7772c39e12fbb2511e849a8dc810276866","t13_implemented":True,"authority_consumed":True}
 c=o["contract"];assert c["public_input_count"]==22 and tuple(c["request_fields"])==REQ and tuple(c["match_fields"])==MATCH and tuple(c["profile_order"])==ORDER and len(c["profiles"])==2
 assert c["review_order"]==["MODE_FIRST","T13_EXACTLY_ONCE","POLICY_NEXT","REQUEST_LAST","EXACT_PROFILE_MATCH","SAME_GENERATION","EXACTLY_ONE_CAS_WINNER"]
 for p,t,h in zip(c["profiles"],ORDER,RECEIPTS,strict=True):
  assert set(p)==set(MATCH) and p["track_id"]==t and p["t13_receipt_content_sha256"]==h and len(p["reservation_key_sha256"])==64
  assert type(p["contender_a_observed_generation"])is int and type(p["contender_b_observed_generation"])is int and 0<=p["contender_a_observed_generation"]<=2**63-1 and p["contender_a_observed_generation"]==p["contender_b_observed_generation"]
  assert type(p["contender_a_cas_result"])is bool and type(p["contender_b_cas_result"])is bool and (p["contender_a_cas_result"]^p["contender_b_cas_result"])
 assert o["authority"]=={"state":"AUTHORIZED_T14_CONCURRENT_REPLAY_ISOLATED_LAB_EXACT_UNIT","non_transitive":True,"consumed":False,"forbidden":["CLAIM_REAL_CONCURRENCY_OR_LINEARIZABILITY","ACCESS_OR_MUTATE_ATOMIC_OR_DURABLE_REPLAY_STATE","PERFORM_NETWORK_PROVIDER_RUNTIME_OR_PRODUCTION_ACTION"]}
 assert o["boundary"]=={"current_component_total":11,"future_component_total":12,"decision_implements_components":0,"t14_implemented":False,"t15_authorized":False,"runtime_authority":False,"provider_authority":False}
 assert o["resources"]=={"network":False,"spend":0,"workers":1,"predecessor_calls":1,"scratch_bytes":67108864,"policy_bytes":65536,"request_bytes":16384} and o["state_machine"]=={"decision_consumes_authority":False,"future_integrated_full_consumes_authority":True}
 assert m["boundary"]["t13_replay_implemented_after_integrated_full"]is True and m["boundary"]["component_total_after_integrated_full"]==11 and m["authority"]["implementation_consumes_authority_after_integrated_full"]is True
 t=next(x for x in s["threat_cases"]if x["case_id"]=="T14");assert t=={"case_id":"T14","expected_disposition":"REJECTED_FAIL_CLOSED","expected_reason_code":"E_PRODUCTION_REPLAY_REJECTED","mutation":"Concurrent submissions race a non-atomic replay check","threat_class":"CONCURRENT_REPLAY"}
 r={"schema":"agent_bridge.biocortex.concurrent_replay_authority.receipt.v0","status":"APPROVE_T14_CONCURRENT_REPLAY_AUTHORITY_DECISION","authorized_unit":UNIT,"public_input_count":22,"profile_count":2,"request_field_count":5,"match_dimension_count":7,"t13_implemented":True,"t14_implemented":False,"authority_consumed":False,"future_component_total":12,"runtime_authority":False,"provider_authority":False,"owner_raw_sha256":sha(OWNER),"semantic_raw_sha256":sha(SEMANTIC),"t13_manifest_raw_sha256":sha(T13),"content_sha256":"0"*64};x=dict(r);del x["content_sha256"];r["content_sha256"]=hashlib.sha256(DOMAIN.encode()+b"\0"+json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest();return r
def main():
 try:
  for k,v in validate(load(OWNER),load(SEMANTIC),load(T13)).items():print(f"{k}\t{str(v).lower()if type(v)is bool else v}")
  return 0
 except Exception as e:print(f"review_error\t{e}",file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
