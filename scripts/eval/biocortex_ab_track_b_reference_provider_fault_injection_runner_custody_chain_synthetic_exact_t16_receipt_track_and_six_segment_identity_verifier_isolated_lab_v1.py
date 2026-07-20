#!/usr/bin/env python3
"""Pure, offline T17 synthetic custody-chain identity verifier.

This module never reads custody state.  Its six values are detached SHA-256
identities supplied in a canonical JSON request and are accepted only when
they exactly match the frozen synthetic profile for the T16 receipt track.
"""
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from typing import Any,Mapping,NoReturn
import biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_set_synthetic_exact_t15_receipt_track_and_ordered_owner_entry_t01_through_t15_verifier_isolated_lab_v1 as predecessor

POLICY_SCHEMA="agent_bridge.biocortex.t17_custody_chain_synthetic_policy.v1"; RECEIPT_SCHEMA="agent_bridge.biocortex.t17_custody_chain_synthetic_exact_t16_receipt_track_and_six_segment_identity_verifier_isolated_lab_v1.receipt.v0"
AUTHORIZED_UNIT="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CUSTODY_CHAIN_SYNTHETIC_EXACT_T16_RECEIPT_TRACK_AND_SIX_SEGMENT_IDENTITY_CHAIN_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
STATUS="REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CUSTODY_CHAIN_SYNTHETIC_EXACT_T16_RECEIPT_TRACK_AND_SIX_SEGMENT_IDENTITY_CHAIN_VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
RECEIPT_DOMAIN="AB_TRACK_B_T17_CUSTODY_CHAIN_ISOLATED_LAB_KAT_RECEIPT_V1"; CHAIN_DOMAIN="AB_T17_CUSTODY_CHAIN_SYNTHETIC_IDENTITY_V1"; SEGMENTS=("raw_sha256","canonical_sha256","validation_sha256","retention_sha256","cleanup_sha256","tombstone_sha256")
TRACKS=("MANAGED_SPANNER_CLOUD_KMS","SELF_HOSTED_ETCD_OPENBAO"); T16_RECEIPTS=("bf5dea31300989c7550bf3f92705df9a8f81fa8f2c14d30e211ad783a0369742","ec8814b7ced178ff5a4e719943fdd4860a2faff89cf44f162d1af7984b9c46cb")
DEFAULT_DISPOSITION="REJECTED_FAIL_CLOSED"; MAX_POLICY_BYTES=65536; MAX_REQUEST_BYTES=32768; REQUEST_FIELDS=SEGMENTS; MATCH_FIELDS=("t16_receipt_content_sha256","track_id","chain_domain","segment_count")
@dataclass(frozen=True)
class Profile:t16_receipt_content_sha256:str;track_id:str;chain_domain:str;segment_count:int;segments:tuple[str,...]
def segment(track:str,name:str)->str:return hashlib.sha256(CHAIN_DOMAIN.encode()+b"\0"+track.encode()+b"\0"+name.encode()).hexdigest()
PROFILES=tuple(Profile(h,t,CHAIN_DOMAIN,6,tuple(segment(t,n)for n in SEGMENTS))for t,h in zip(TRACKS,T16_RECEIPTS,strict=True))
class CustodyChainReviewError(ValueError):
 def __init__(self,code:str,detail:str,*,detail_code:str|None=None):super().__init__(f"{code}: {detail}");self.code=code;self.detail=detail;self.detail_code=detail_code
def fail(c:str,d:str)->NoReturn:raise CustodyChainReviewError(c,d)
def req(x:bool,c:str,d:str)->None:
 if not x:fail(c,d)
def pairs(items:list[tuple[str,Any]])->dict[str,Any]:
 d={}
 for k,v in items:req(type(k)is str and k not in d,"E_JSON_DUPLICATE_KEY","duplicate");d[k]=v
 return d
def no_num(v:str)->NoReturn:fail("E_JSON_NON_INTEGER_NUMBER",v)
def parse_int(v:str)->int:
 x=int(v);req(-(2**63)<=x<=2**63-1,"E_JSON_INT_RANGE",v);return x
def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def decode(raw:bytes,limit:int,label:str)->dict[str,Any]:
 req(type(raw)is bytes,f"E_{label}_TYPE","bytes");req(0<len(raw)<=limit,f"E_{label}_SIZE","bound")
 try:
  text=raw.decode("utf-8","strict");d=json.JSONDecoder(object_pairs_hook=pairs,parse_int=parse_int,parse_float=no_num,parse_constant=no_num,strict=True);v,end=d.raw_decode(text)
 except CustodyChainReviewError:raise
 except Exception as e:fail(f"E_{label}_JSON",str(e))
 req(end==len(text)and type(v)is dict,f"E_{label}_ROOT_OR_TRAILING","closed");req(canonical(v)==raw,f"E_{label}_NONCANONICAL","canonical");return v
def exact(v:Mapping[str,Any],fields:tuple[str,...],code:str)->None:req(type(v)is dict and set(v)==set(fields),code,"fields")
def sha(v:Any)->bool:return type(v)is str and len(v)==64 and all(c in "0123456789abcdef"for c in v)
def profile_dict(p:Profile)->dict[str,Any]:return {"t16_receipt_content_sha256":p.t16_receipt_content_sha256,"track_id":p.track_id,"chain_domain":p.chain_domain,"segment_count":p.segment_count,"segment_identities":dict(zip(SEGMENTS,p.segments,strict=True))}
def known_answer_custody_chain_policy()->dict[str,Any]:return {"default_disposition":DEFAULT_DISPOSITION,"profiles":[profile_dict(p)for p in PROFILES],"reject_on_multiple_matches":True,"reject_on_zero_matches":True,"schema":POLICY_SCHEMA,"schema_version":1}
def known_answer_custody_chain_policy_bytes()->bytes:return canonical(known_answer_custody_chain_policy())
def known_answer_custody_chain_request(track:str)->bytes:
 for p in PROFILES:
  if p.track_id==track:return canonical(dict(zip(SEGMENTS,p.segments,strict=True)))
 fail("E_CUSTODY_CHAIN_TRACK_UNKNOWN",track)
def validate_policy(v:Mapping[str,Any])->tuple[Mapping[str,Any],...]:
 exact(v,("default_disposition","profiles","reject_on_multiple_matches","reject_on_zero_matches","schema","schema_version"),"E_CUSTODY_CHAIN_POLICY_FIELDS");req(v["schema"]==POLICY_SCHEMA and v["schema_version"]==1,"E_CUSTODY_CHAIN_POLICY_SCHEMA","schema");req(v["default_disposition"]==DEFAULT_DISPOSITION and v["reject_on_zero_matches"]is True and v["reject_on_multiple_matches"]is True,"E_CUSTODY_CHAIN_POLICY_DENY","deny");ps=v["profiles"];req(type(ps)is list and len(ps)==2,"E_CUSTODY_CHAIN_POLICY_PROFILES","two")
 for candidate,frozen in zip(ps,PROFILES,strict=True):
  exact(candidate,("t16_receipt_content_sha256","track_id","chain_domain","segment_count","segment_identities"),"E_CUSTODY_CHAIN_PROFILE_FIELDS");exact(candidate["segment_identities"],SEGMENTS,"E_CUSTODY_CHAIN_SEGMENT_FIELDS");req(all(sha(x)for x in candidate["segment_identities"].values()),"E_CUSTODY_CHAIN_SEGMENT_HASH","sha256");req(candidate==profile_dict(frozen),"E_CUSTODY_CHAIN_PROFILE_EXACT","frozen")
 return tuple(ps)
def validate_request(v:Mapping[str,Any])->dict[str,str]:
 exact(v,REQUEST_FIELDS,"E_CUSTODY_CHAIN_REQUEST_FIELDS");req(all(sha(v[x])for x in SEGMENTS),"E_CUSTODY_CHAIN_SEGMENT_HASH","sha256");req(len(set(v.values()))==6,"E_CUSTODY_CHAIN_SEGMENT_DUPLICATE","unique");return dict(v)
def review_custody_chain(*public_inputs:Any)->dict[str,Any]:
 req(len(public_inputs)==28,"E_CUSTODY_CHAIN_PUBLIC_INPUT_COUNT","twenty-eight");t16_inputs=public_inputs[:26];policy_raw,request_raw=public_inputs[26:]
 try:prior=predecessor.review_owner_set(*t16_inputs)
 except predecessor.OwnerSetReviewError as e:raise CustodyChainReviewError("E_PREDECESSOR_OWNER_SET_REJECTED",f"{e.code}: {e.detail}",detail_code=e.code)from e
 try:profiles=validate_policy(decode(policy_raw,MAX_POLICY_BYTES,"CUSTODY_CHAIN_POLICY"))
 except CustodyChainReviewError as e:raise CustodyChainReviewError("E_CUSTODY_CHAIN_POLICY_REJECTED",f"{e.code}: {e.detail}",detail_code=e.code)from e
 try:
  values=validate_request(decode(request_raw,MAX_REQUEST_BYTES,"CUSTODY_CHAIN_REQUEST"));match={"t16_receipt_content_sha256":prior.get("content_sha256"),"track_id":prior.get("track_id"),"chain_domain":CHAIN_DOMAIN,"segment_count":6};hits=[p for p in profiles if all(p[k]==match[k]for k in MATCH_FIELDS)and p["segment_identities"]==values];req(len(hits)==1,"E_CUSTODY_CHAIN_EXACT_MATCH","one");req(prior.get("schema")==predecessor.RECEIPT_SCHEMA and prior.get("t16_owner_set_implemented")is True and prior.get("t17_authorized")is False and prior.get("isolated_lab_candidate_surface_component_total")==14,"E_T16_RECEIPT_TRUTH","T16")
 except CustodyChainReviewError as e:raise CustodyChainReviewError("E_PRODUCTION_CUSTODY_FAILED",f"{e.code}: {e.detail}",detail_code=e.code)from e
 chain_hash=hashlib.sha256(CHAIN_DOMAIN.encode()+b"\0"+canonical(values)).hexdigest();r={"schema":RECEIPT_SCHEMA,"schema_version":1,"status":STATUS,"authorized_unit":AUTHORIZED_UNIT,"content_sha256":"0"*64,"execution_mode":"SYNTHETIC_KAT","synthetic_fixture":True,"predecessor_receipt_schema":predecessor.RECEIPT_SCHEMA,"predecessor_receipt_content_sha256":prior["content_sha256"],"predecessor_review_count":1,"track_id":prior["track_id"],"custody_chain_identity_sha256":chain_hash,"custody_segment_count":6,"public_input_count":28,"binding_match_count":1,"binding_policy_match_dimension_count":4,"binding_profile_count":2,"binding_request_field_count":6,"implementation_authority_single_use_consumed":True,"isolated_lab_candidate_surface_component_total":15,"isolated_lab_candidate_surface_components_implemented":15,"local_threat_specifications_covered":17,"t16_owner_set_implemented":True,"t17_custody_chain_implemented":True,"t18_authorized":False,"network_accessed":False,"runtime_authority":False,"provider_authority":False,"production_admissible":False,"real_evidence_items_present":0,"production_ingestion_controls_implemented":0,"production_threat_specifications_runtime_exercised":0,"runtime_prerequisites_satisfied":0,"side_effects_unlocked":"NONE"};x=dict(r);del x["content_sha256"];r["content_sha256"]=hashlib.sha256(RECEIPT_DOMAIN.encode()+b"\0"+canonical(x)).hexdigest();return r
__all__=["CustodyChainReviewError","PROFILES","RECEIPT_DOMAIN","RECEIPT_SCHEMA","SEGMENTS","known_answer_custody_chain_policy_bytes","known_answer_custody_chain_request","review_custody_chain"]
