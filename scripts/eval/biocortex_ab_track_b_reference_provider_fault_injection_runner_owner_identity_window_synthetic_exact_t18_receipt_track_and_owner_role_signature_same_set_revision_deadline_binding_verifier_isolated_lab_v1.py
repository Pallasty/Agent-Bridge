#!/usr/bin/env python3
"""Pure offline T19 owner-identity/window synthetic verifier."""
from __future__ import annotations
import hashlib,json
from typing import Any
import biocortex_ab_track_b_reference_provider_fault_injection_runner_reviewer_independence_synthetic_exact_t17_receipt_track_and_validator_build_config_binding_verifier_isolated_lab_v1 as predecessor
FIELDS=('owner_identity_sha256','role_sha256','signature_sha256','same_set_hash_sha256','revision_sha256','deadline_sha256');TRACKS=('MANAGED_SPANNER_CLOUD_KMS','SELF_HOSTED_ETCD_OPENBAO');RECEIPTS=('4c5f7fe84905786aee65000a3257234cdd0361ad3c9fd98a81d05c20dc954678','20f140c8aa884b2eababb31686eae4748336a6b633a19ab7cc534f7548eb4277');IDS=(('2744fc5ad91a31f457324d77b9cf2740c9a43f9074b08f854eee31fcadf44d92','e6e8f7f6eee40b37a13e881849f19b9fc220b745695c4eb827cf5350768da568','3d597fa227ce96de7a9f985d8dde64932c792b8a7afb902a744bfdc2974c9645','e7b826dc96ea92eb775b3ca036183be91eb307023de9bcf0f9ca2fdb9a15b236','5401b58dc8162cca22689cabf9d8b2e7846dca6e234f90d353d32b87fc9b3561','f98f2a248d594f6dec50148c2785b7e088b18c15874be224eb843c56c37be4b8'),('1ef2ff476289b7d0c5f08fe7d0a88769dae427d471ef32f50ef8193de1e416d8','4cf496d36b2384adf20c5a429719c45e51173bea868ff6259b166c240ff8025f','14e9dec6d6d8ea2377d702fa4937079ee7887160de549cde7217db4d7a8ff1dc','53cb612e98d685d92b2611d39884194f7c58550ffa8522c98f49a6ed63d2857d','df13a485b123dc18376353931b11165f8d567253eda39aa78e0dc7760798ce89','1e9a45dfa811da92b841e134cf088d08841ac35d101a332c4104f340584d9b6e'))
PROFILES=tuple({'t18_receipt_content_sha256':h,'track_id':t,**dict(zip(FIELDS,v))}for t,h,v in zip(TRACKS,RECEIPTS,IDS,strict=True));DOMAIN='AB_T19_OWNER_IDENTITY_WINDOW_KAT_RECEIPT_V1'
class OwnerIdentityWindowError(ValueError):
 def __init__(self,c,d):super().__init__(f'{c}: {d}');self.code=c
def cb(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def req(x,c):
 if not x:raise OwnerIdentityWindowError(c,c)
def policy_bytes():return cb({'schema':'agent_bridge.biocortex.t19_owner_identity_window_policy.v1','schema_version':1,'default_disposition':'REJECTED_FAIL_CLOSED','profiles':PROFILES,'reject_on_zero_matches':True,'reject_on_multiple_matches':True})
def request_bytes(track):
 for p in PROFILES:
  if p['track_id']==track:return cb({k:p[k]for k in FIELDS})
 raise OwnerIdentityWindowError('E_OWNER_IDENTITY_TRACK_UNKNOWN',track)
def decode(raw,label):
 try:v=json.loads(raw);req(cb(v)==raw,f'E_{label}_NONCANONICAL');return v
 except OwnerIdentityWindowError:raise
 except Exception:raise OwnerIdentityWindowError(f'E_{label}_JSON','json')
def review_owner_identity_window(*inputs:Any):
 req(len(inputs)==32,'E_OWNER_IDENTITY_PUBLIC_INPUT_COUNT')
 try:prior=predecessor.review_independence(*inputs[:30])
 except predecessor.ReviewIndependenceError as e:raise OwnerIdentityWindowError('E_PREDECESSOR_REVIEW_INDEPENDENCE_REJECTED',e.code)
 try:
  pol=decode(inputs[30],'OWNER_IDENTITY_POLICY');req(pol==json.loads(policy_bytes()),'E_OWNER_IDENTITY_POLICY_REJECTED')
 except OwnerIdentityWindowError:raise
 try:
  v=decode(inputs[31],'OWNER_IDENTITY_REQUEST');req(set(v)==set(FIELDS)and all(type(v[k])is str and len(v[k])==64 for k in FIELDS),'E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED');m={'t18_receipt_content_sha256':prior['content_sha256'],'track_id':prior['track_id'],**v};req(sum(p==m for p in PROFILES)==1,'E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED');req(prior['t18_review_independence_implemented']is True and prior['t19_authorized']is False,'E_T18_RECEIPT_TRUTH')
 except OwnerIdentityWindowError as e:raise OwnerIdentityWindowError('E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED',e.code)
 r={'schema':'agent_bridge.biocortex.t19_owner_identity_window.receipt.v0','status':'APPROVE_T19_OWNER_IDENTITY_WINDOW_SYNTHETIC_VERIFIER','content_sha256':'0'*64,'track_id':prior['track_id'],'public_input_count':32,'predecessor_review_count':1,'binding_profile_count':2,'binding_match_dimension_count':8,'binding_request_field_count':6,'implementation_authority_single_use_consumed':True,'isolated_lab_candidate_surface_component_total':17,'t19_owner_identity_window_implemented':True,'t20_authorized':False,'network_accessed':False,'runtime_authority':False,'provider_authority':False,'production_admissible':False,'real_evidence_items_present':0,'side_effects_unlocked':'NONE'};x=dict(r);del x['content_sha256'];r['content_sha256']=hashlib.sha256(DOMAIN.encode()+b'\0'+cb(x)).hexdigest();return r
