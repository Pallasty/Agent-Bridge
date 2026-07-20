#!/usr/bin/env python3
"""Pure offline T18 synthetic reviewer-independence binding verifier."""
from __future__ import annotations
import hashlib,json
from typing import Any,NoReturn
import biocortex_ab_track_b_reference_provider_fault_injection_runner_custody_chain_synthetic_exact_t16_receipt_track_and_six_segment_identity_verifier_isolated_lab_v1 as predecessor
POLICY_SCHEMA="agent_bridge.biocortex.t18_review_independence_synthetic_policy.v1";RECEIPT_SCHEMA="agent_bridge.biocortex.t18_reviewer_independence_synthetic_exact_t17_receipt_track_and_validator_build_config_binding_verifier_isolated_lab_v1.receipt.v0";DOMAIN="AB_T18_REVIEW_INDEPENDENCE_KAT_RECEIPT_V1";UNIT="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_REVIEWER_INDEPENDENCE_SYNTHETIC_EXACT_T17_RECEIPT_TRACK_AND_VALIDATOR_BUILD_CONFIG_BINDING_VERIFIER_ISOLATED_LAB_IMPLEMENTATION";FIELDS=("reviewer_identity_sha256","validator_build_sha256","validator_config_sha256");MATCH=("t17_receipt_content_sha256","track_id",*FIELDS);TRACKS=("MANAGED_SPANNER_CLOUD_KMS","SELF_HOSTED_ETCD_OPENBAO");RECEIPTS=("ee548c1748b5a5e27f8211c0821c349c8c9cea5622fead8934dd876cbe413692","154dcf486788cff28c3e9eefa9cd0848494425ca40b6bb0fa2453a195f416d6c");IDS=(("c8c5b8b24bc0edc1929f0051c7f726e544fbc900235f691255feec4fbbdb01b0","4885d2dc26724cfebcfc601bd3cd27fab29a9f9a176304109fbe8c07f4d033a7","7b67da428f3996041664702099dbc530e9a026bff1844c524b3ebcb21c9e630b"),("1a6a005ae1aedf81e105f88c5b4c92f3582584e13eb10e6f7508781af7519ea1","1cb4eefce65b98a4bdaec7ff9167722fca344a90b7cfdea2500e330902b83edb","c3e9ae65b66d4c2de0c16bae86c82d711d30213b11739f570fed99b4d537ee30"));PROFILES=tuple(dict(zip(MATCH,(h,t,*i),strict=True))for t,h,i in zip(TRACKS,RECEIPTS,IDS,strict=True))
class ReviewIndependenceError(ValueError):
 def __init__(self,c,d,detail_code=None):super().__init__(f"{c}: {d}");self.code=c;self.detail=d;self.detail_code=detail_code
def fail(c,d)->NoReturn:raise ReviewIndependenceError(c,d)
def req(x,c,d):
 if not x:fail(c,d)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def pairs(xs):
 d={}
 for k,v in xs:req(type(k)is str and k not in d,"E_JSON_DUPLICATE_KEY","duplicate");d[k]=v
 return d
def decode(raw,limit,label):
 req(type(raw)is bytes and 0<len(raw)<=limit,f"E_{label}_SIZE","bytes/bound")
 try:
  text=raw.decode();v,end=json.JSONDecoder(object_pairs_hook=pairs,parse_int=int,parse_float=lambda x:fail("E_JSON_NON_INTEGER_NUMBER",x),parse_constant=lambda x:fail("E_JSON_NON_INTEGER_NUMBER",x),strict=True).raw_decode(text)
 except ReviewIndependenceError:raise
 except Exception as e:fail(f"E_{label}_JSON",str(e))
 req(type(v)is dict and end==len(text) and canonical(v)==raw,f"E_{label}_NONCANONICAL","closed");return v
def sha(v):return type(v)is str and len(v)==64 and all(c in '0123456789abcdef'for c in v)
def policy_bytes():return canonical({"schema":POLICY_SCHEMA,"schema_version":1,"default_disposition":"REJECTED_FAIL_CLOSED","profiles":PROFILES,"reject_on_zero_matches":True,"reject_on_multiple_matches":True})
def request_bytes(track):
 for p in PROFILES:
  if p['track_id']==track:return canonical({k:p[k]for k in FIELDS})
 fail("E_REVIEW_INDEPENDENCE_TRACK_UNKNOWN",track)
def validate_policy(v):
 req(set(v)=={"schema","schema_version","default_disposition","profiles","reject_on_zero_matches","reject_on_multiple_matches"},"E_REVIEW_INDEPENDENCE_POLICY_FIELDS","fields");req(v["schema"]==POLICY_SCHEMA and v["schema_version"]==1 and v["default_disposition"]=="REJECTED_FAIL_CLOSED" and v["reject_on_zero_matches"]is True and v["reject_on_multiple_matches"]is True and v["profiles"]==list(PROFILES),"E_REVIEW_INDEPENDENCE_POLICY_EXACT","frozen")
def validate_request(v):req(set(v)==set(FIELDS) and all(sha(v[k])for k in FIELDS) and len(set(v.values()))==3,"E_REVIEW_INDEPENDENCE_REQUEST","exact");return v
def review_independence(*inputs:Any):
 req(len(inputs)==30,"E_REVIEW_INDEPENDENCE_PUBLIC_INPUT_COUNT","thirty")
 try:prior=predecessor.review_custody_chain(*inputs[:28])
 except predecessor.CustodyChainReviewError as e:raise ReviewIndependenceError("E_PREDECESSOR_CUSTODY_REJECTED",e.code,e.code)from e
 try:validate_policy(decode(inputs[28],65536,"REVIEW_INDEPENDENCE_POLICY"))
 except ReviewIndependenceError as e:raise ReviewIndependenceError("E_REVIEW_INDEPENDENCE_POLICY_REJECTED",e.code,e.code)from e
 try:
  values=validate_request(decode(inputs[29],32768,"REVIEW_INDEPENDENCE_REQUEST"));match={"t17_receipt_content_sha256":prior["content_sha256"],"track_id":prior["track_id"],**values};req(sum(p==match for p in PROFILES)==1,"E_REVIEW_INDEPENDENCE_EXACT_MATCH","one");req(prior["t17_custody_chain_implemented"]is True and prior["t18_authorized"]is False and prior["isolated_lab_candidate_surface_component_total"]==15,"E_T17_RECEIPT_TRUTH","T17")
 except ReviewIndependenceError as e:raise ReviewIndependenceError("E_PRODUCTION_INDEPENDENT_REVIEW_FAILED",e.code,e.code)from e
 r={"schema":RECEIPT_SCHEMA,"status":"APPROVE_T18_REVIEW_INDEPENDENCE_SYNTHETIC_VERIFIER","content_sha256":"0"*64,"authorized_unit":UNIT,"execution_mode":"SYNTHETIC_KAT","synthetic_fixture":True,"predecessor_receipt_content_sha256":prior["content_sha256"],"predecessor_review_count":1,"track_id":prior["track_id"],"public_input_count":30,"binding_profile_count":2,"binding_match_dimension_count":5,"binding_request_field_count":3,"implementation_authority_single_use_consumed":True,"isolated_lab_candidate_surface_component_total":16,"t17_custody_chain_implemented":True,"t18_review_independence_implemented":True,"t19_authorized":False,"network_accessed":False,"runtime_authority":False,"provider_authority":False,"production_admissible":False,"real_evidence_items_present":0,"side_effects_unlocked":"NONE"};x=dict(r);del x['content_sha256'];r['content_sha256']=hashlib.sha256(DOMAIN.encode()+b'\0'+canonical(x)).hexdigest();return r
