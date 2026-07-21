#!/usr/bin/env python3
"""Offline T20 verifier: every path returns a fail-closed rejection receipt."""
from __future__ import annotations
import hashlib,json
from typing import Any
import biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_identity_window_synthetic_exact_t18_receipt_track_and_owner_role_signature_same_set_revision_deadline_binding_verifier_isolated_lab_v1 as predecessor
FIELDS=('control_set_sha256','fifteen_evidence_set_sha256','decision_request_sha256','downstream_separation_sha256');TRACKS=('MANAGED_SPANNER_CLOUD_KMS','SELF_HOSTED_ETCD_OPENBAO');DOMAIN='AB_T20_PREMATURE_AUTHORITY_KAT_RECEIPT_V1'
class PrematureAuthorityError(ValueError):
 def __init__(self,c):super().__init__(c);self.code=c
def cb(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def req(x,c):
 if not x:raise PrematureAuthorityError(c)
def policy_bytes():return cb({'schema':'agent_bridge.biocortex.t20_premature_authority_policy.v1','schema_version':1,'default_disposition':'REJECTED_FAIL_CLOSED','positive_production_decision':False,'downstream_execution_authority':False})
def request_bytes(track):return cb({k:hashlib.sha256(b'AB_T20\0'+track.encode()+b'\0'+k.encode()).hexdigest()for k in FIELDS})
PROFILES={track:json.loads(request_bytes(track))for track in TRACKS}
def review_premature_authority(*inputs:Any):
 req(len(inputs)==34,'E_PREMATURE_AUTHORITY_PUBLIC_INPUT_COUNT')
 try:prior=predecessor.review_owner_identity_window(*inputs[:32])
 except predecessor.OwnerIdentityWindowError as e:raise PrematureAuthorityError('E_PREDECESSOR_OWNER_IDENTITY_REJECTED')from e
 try:
  pol=json.loads(inputs[32]);v=json.loads(inputs[33]);req(cb(pol)==inputs[32] and cb(v)==inputs[33],'E_PRODUCTION_DECISION_OR_DOWNSTREAM_SEPARATION_FAILED');req(pol==json.loads(policy_bytes()) and v==PROFILES.get(prior['track_id']) and prior['t19_owner_identity_window_implemented']is True and prior['t20_authorized']is False,'E_PRODUCTION_DECISION_OR_DOWNSTREAM_SEPARATION_FAILED')
 except PrematureAuthorityError:raise
 except Exception:raise PrematureAuthorityError('E_PRODUCTION_DECISION_OR_DOWNSTREAM_SEPARATION_FAILED')
 r={'schema':'agent_bridge.biocortex.t20_premature_authority.receipt.v0','status':'REJECTED_FAIL_CLOSED','reason_code':'E_PRODUCTION_DECISION_OR_DOWNSTREAM_SEPARATION_FAILED','content_sha256':'0'*64,'track_id':prior['track_id'],'public_input_count':34,'predecessor_review_count':1,'positive_production_decision':False,'downstream_execution_authority':False,'t20_premature_authority_implemented':True,'successor_authorized':False,'network_accessed':False,'runtime_authority':False,'provider_authority':False,'production_admissible':False,'side_effects_unlocked':'NONE'};x=dict(r);del x['content_sha256'];r['content_sha256']=hashlib.sha256(DOMAIN.encode()+b'\0'+cb(x)).hexdigest();return r
