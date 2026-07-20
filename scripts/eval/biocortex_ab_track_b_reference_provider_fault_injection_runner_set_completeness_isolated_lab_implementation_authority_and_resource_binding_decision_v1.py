#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OWNER="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_set_completeness_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json";SEMANTIC="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json";T14="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_concurrent_replay_synthetic_exact_t13_receipt_track_reservation_key_contender_a_and_b_observed_generation_and_cas_result_verifier_isolated_lab_v1_pack_v0.json";DOMAIN="AB_T15_SET_COMPLETENESS_AUTHORITY_V1"
UNIT="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_SET_COMPLETENESS_SYNTHETIC_EXACT_T14_RECEIPT_TRACK_AND_ORDERED_VALIDATED_ENTRY_T01_THROUGH_T14_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
REQ=("ordered_validated_entries",);ENTRY=("ordinal","case_id","validated_receipt_content_sha256");MATCH=("t14_receipt_content_sha256","track_id",*REQ);ORDER=("MANAGED_SPANNER_CLOUD_KMS","SELF_HOSTED_ETCD_OPENBAO");RECEIPTS=("fe47c0c4140933ceac18c9c24be2d5e02b6483816efa2979be9d04c2816feee8","cf93c5be80036290873f1cd370a0b7b38cf5568d0feed25e0e849955ec116b23")
def path(x):
 p=ROOT.joinpath(*x.split('/'));r=p.resolve(strict=True);assert ROOT in r.parents and p.is_file()and not p.is_symlink();return p
def load(x):return json.loads(path(x).read_text())
def sha(x):return hashlib.sha256(path(x).read_bytes()).hexdigest()
def validate(o,s,m):
 assert o["decision"]=="AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_T15_SET_COMPLETENESS_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED" and o["next_unit"]==UNIT
 assert o["actor"]=={"class":"PROJECT_OWNER","id":"pallasting","directive":"CONTINUE_NEXT_STEP_USING_AGENT_RECOMMENDED_ORDER"}
 assert o["predecessor"]=={"exact_release_commit":"df4d6b75e6dae64c152138397c26571e2f61f469","t14_implemented":True,"authority_consumed":True}
 c=o["contract"];assert c["public_input_count"]==24 and tuple(c["request_fields"])==REQ and tuple(c["entry_fields"])==ENTRY and tuple(c["match_fields"])==MATCH and tuple(c["profile_order"])==ORDER and len(c["profiles"])==2
 assert c["review_order"]==["MODE_FIRST","T14_EXACTLY_ONCE","POLICY_NEXT","REQUEST_LAST","EXACT_PROFILE_MATCH","EXACT_ORDERED_T01_THROUGH_T14_SET"]
 seen=set()
 for p,t,h in zip(c["profiles"],ORDER,RECEIPTS,strict=True):
  assert set(p)==set(MATCH) and p["track_id"]==t and p["t14_receipt_content_sha256"]==h
  e=p["ordered_validated_entries"];assert type(e)is list and len(e)==14 and len(set(e))==14 and all(type(x)is str and len(x)==64 and set(x)<=set("0123456789abcdef")for x in e)
  expected=[hashlib.sha256(b"AB_T15_SET_COMPLETENESS_SYNTHETIC_ENTRY_V1\0"+t.encode()+b"\0"+f"T{i:02d}".encode()).hexdigest()for i in range(1,15)];assert e==expected and not(seen&set(e));seen|=set(e)
 assert o["authority"]=={"state":"AUTHORIZED_T15_SET_COMPLETENESS_ISOLATED_LAB_EXACT_UNIT","non_transitive":True,"consumed":False,"forbidden":["CLAIM_INDEPENDENT_REVIEW_OR_REVIEWER_IDENTITY","USE_SYNTHETIC_SET_AS_PRODUCTION_REVIEW_SUBJECT","PERFORM_NETWORK_PROVIDER_RUNTIME_OR_PRODUCTION_ACTION"]}
 assert o["boundary"]=={"current_component_total":12,"future_component_total":13,"decision_implements_components":0,"t15_implemented":False,"t16_authorized":False,"runtime_authority":False,"provider_authority":False}
 assert o["resources"]=={"network":False,"spend":0,"workers":1,"predecessor_calls":1,"scratch_bytes":67108864,"policy_bytes":131072,"request_bytes":65536} and o["state_machine"]=={"decision_consumes_authority":False,"future_integrated_full_consumes_authority":True}
 assert m["boundary"]["t14_implemented_after_integrated_full"]is True and m["boundary"]["component_total_after_integrated_full"]==12 and m["authority"]["implementation_consumes_authority_after_integrated_full"]is True
 t=next(x for x in s["threat_cases"]if x["case_id"]=="T15");assert t=={"case_id":"T15","expected_disposition":"REJECTED_FAIL_CLOSED","expected_reason_code":"E_PRODUCTION_INDEPENDENT_REVIEW_FAILED","mutation":"Missing, duplicated, reordered, or substituted validated entry 1-14","threat_class":"SET_COMPLETENESS"}
 td=next(x for x in s["trust_domains"]if x["domain_id"]=="AB_TRACK_B_RUNTIME_PREREQUISITE_PRODUCTION_REVIEW_SUBJECT_SET_V1");assert td["offline_usable"]is False and td["production_implemented"]is False and td["cross_domain_substitution_allowed"]is False
 r={"schema":"agent_bridge.biocortex.set_completeness_authority.receipt.v0","status":"APPROVE_T15_SET_COMPLETENESS_AUTHORITY_DECISION","authorized_unit":UNIT,"public_input_count":24,"profile_count":2,"ordered_entry_count":14,"entry_field_count":3,"match_dimension_count":3,"t14_implemented":True,"t15_implemented":False,"authority_consumed":False,"future_component_total":13,"runtime_authority":False,"provider_authority":False,"owner_raw_sha256":sha(OWNER),"semantic_raw_sha256":sha(SEMANTIC),"t14_manifest_raw_sha256":sha(T14),"content_sha256":"0"*64};x=dict(r);del x["content_sha256"];r["content_sha256"]=hashlib.sha256(DOMAIN.encode()+b"\0"+json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest();return r
def main():
 try:
  for k,v in validate(load(OWNER),load(SEMANTIC),load(T14)).items():print(f"{k}\t{str(v).lower()if type(v)is bool else v}")
  return 0
 except Exception as e:print(f"review_error\t{e}",file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
