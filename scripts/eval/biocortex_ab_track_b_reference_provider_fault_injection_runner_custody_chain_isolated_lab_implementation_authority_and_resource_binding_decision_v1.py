#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OWNER="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_custody_chain_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json";SEMANTIC="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json";T16="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_set_synthetic_exact_t15_receipt_track_and_ordered_owner_entry_t01_through_t15_verifier_isolated_lab_v1_pack_v0.json";DOMAIN="AB_T17_CUSTODY_AUTHORITY_V1";UNIT="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CUSTODY_CHAIN_SYNTHETIC_EXACT_T16_RECEIPT_TRACK_AND_SIX_SEGMENT_IDENTITY_CHAIN_VERIFIER_ISOLATED_LAB_IMPLEMENTATION";ORDER=("MANAGED_SPANNER_CLOUD_KMS","SELF_HOSTED_ETCD_OPENBAO");RECEIPTS=("bf5dea31300989c7550bf3f92705df9a8f81fa8f2c14d30e211ad783a0369742","ec8814b7ced178ff5a4e719943fdd4860a2faff89cf44f162d1af7984b9c46cb")
def path(x):
 p=ROOT.joinpath(*x.split('/'));r=p.resolve(strict=True);assert ROOT in r.parents and p.is_file()and not p.is_symlink();return p
def load(x):return json.loads(path(x).read_text())
def sha(x):return hashlib.sha256(path(x).read_bytes()).hexdigest()
def validate(o,s,m):
 assert o['decision']=="AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_T17_CUSTODY_CHAIN_ISOLATED_LAB_COMPONENT_IMPLEMENTATION_ONLY_FAIL_CLOSED" and o['next_unit']==UNIT and o['predecessor']=={'exact_release_commit':'b09914b21c9253c12d3fd503e2c4006149d3b080','t16_implemented':True,'authority_consumed':True}
 c=o['contract'];assert c['public_input_count']==28 and tuple(c['request_fields'])==('raw_sha256','canonical_sha256','validation_sha256','retention_sha256','cleanup_sha256','tombstone_sha256') and tuple(c['match_fields'])==('t16_receipt_content_sha256','track_id','chain_domain','segment_count') and tuple(c['profile_order'])==ORDER
 for p,t,h in zip(c['profiles'],ORDER,RECEIPTS,strict=True):assert p=={'t16_receipt_content_sha256':h,'track_id':t,'chain_domain':'AB_T17_CUSTODY_CHAIN_SYNTHETIC_IDENTITY_V1','segment_count':6}
 assert o['authority']=={'state':'AUTHORIZED_T17_CUSTODY_CHAIN_ISOLATED_LAB_EXACT_UNIT','non_transitive':True,'consumed':False,'forbidden':['ACCESS_OR_MUTATE_REAL_CUSTODY_RETENTION_CLEANUP_OR_TOMBSTONE_STATE','CLAIM_REAL_EVIDENCE_CUSTODY_OR_RETENTION','PERFORM_NETWORK_PROVIDER_RUNTIME_OR_PRODUCTION_ACTION']}
 assert o['boundary']=={'current_component_total':14,'future_component_total':15,'decision_implements_components':0,'t17_implemented':False,'t18_authorized':False,'runtime_authority':False,'provider_authority':False}
 assert o['resources']=={'network':False,'spend':0,'workers':1,'predecessor_calls':1,'scratch_bytes':67108864,'policy_bytes':65536,'request_bytes':32768} and o['state_machine']=={'decision_consumes_authority':False,'future_integrated_full_consumes_authority':True}
 assert m['boundary']['t16_implemented_after_integrated_full']is True and m['boundary']['component_total_after_integrated_full']==14
 t=next(x for x in s['threat_cases']if x['case_id']=='T17');assert t=={'case_id':'T17','expected_disposition':'REJECTED_FAIL_CLOSED','expected_reason_code':'E_PRODUCTION_CUSTODY_FAILED','mutation':'Raw, canonical, validation, retention, cleanup, or tombstone chain diverges','threat_class':'CUSTODY'}
 r={'schema':'agent_bridge.biocortex.custody_authority.receipt.v0','status':'APPROVE_T17_CUSTODY_CHAIN_AUTHORITY_DECISION','authorized_unit':UNIT,'public_input_count':28,'profile_count':2,'custody_segment_count':6,'match_dimension_count':4,'t16_implemented':True,'t17_implemented':False,'authority_consumed':False,'future_component_total':15,'runtime_authority':False,'provider_authority':False,'owner_raw_sha256':sha(OWNER),'semantic_raw_sha256':sha(SEMANTIC),'t16_manifest_raw_sha256':sha(T16),'content_sha256':'0'*64};x=dict(r);del x['content_sha256'];r['content_sha256']=hashlib.sha256(DOMAIN.encode()+b'\0'+json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest();return r
def main():
 try:
  for k,v in validate(load(OWNER),load(SEMANTIC),load(T16)).items():print(f"{k}\t{str(v).lower()if type(v)is bool else v}")
  return 0
 except Exception as e:print(f"review_error\t{e}",file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
