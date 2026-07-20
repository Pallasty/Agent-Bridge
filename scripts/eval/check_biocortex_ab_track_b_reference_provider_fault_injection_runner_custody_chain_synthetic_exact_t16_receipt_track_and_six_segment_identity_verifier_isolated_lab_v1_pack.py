#!/usr/bin/env python3
from __future__ import annotations
import argparse,ast,hashlib,importlib.util,json,sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2];SOURCE="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_custody_chain_synthetic_exact_t16_receipt_track_and_six_segment_identity_verifier_isolated_lab_v1.py";T16_CHECKER="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_set_synthetic_exact_t15_receipt_track_and_ordered_owner_entry_t01_through_t15_verifier_isolated_lab_v1_pack.py";AUTHORITY="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_custody_chain_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json";DOMAIN="AB_TRACK_B_T17_CUSTODY_CHAIN_PACK_V1"
def req(x:bool,d:str)->None:
 if not x:raise ValueError(d)
def path(x:str)->Path:
 p=ROOT.joinpath(*x.split('/'));r=p.resolve(strict=True);req(ROOT in r.parents and p.is_file()and not p.is_symlink(),x);return p
def mod(x:str,n:str):
 p=path(x);s=importlib.util.spec_from_file_location(n,p);req(s and s.loader,'import');a=str(p.parent)not in sys.path
 if a:sys.path.insert(0,str(p.parent))
 try:m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
 finally:
  if a:sys.path.remove(str(p.parent))
def cb(x:Any)->bytes:return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha(x:str)->str:return hashlib.sha256(path(x).read_bytes()).hexdigest()
def vectors(s:Any):
 c=mod(T16_CHECKER,"_t16c");base,profiles=c.vectors(s.predecessor);policy=s.known_answer_custody_chain_policy_bytes();return [(*v,policy,s.known_answer_custody_chain_request(p["track_id"]))for v,p in zip(base,profiles,strict=True)],profiles
def reject(s:Any,v:list[Any],code:str)->None:
 try:s.review_custody_chain(*v)
 except s.CustodyChainReviewError as e:req(e.code==code,e.code);return
 raise ValueError("accepted")
def evaluate()->str:
 s=mod(SOURCE,"_t17");vs,profiles=vectors(s);receipts=[]
 for v,p in zip(vs,profiles,strict=True):
  r=s.review_custody_chain(*v);req(r["track_id"]==p["track_id"] and r["public_input_count"]==28 and r["predecessor_review_count"]==1 and r["custody_segment_count"]==6 and r["isolated_lab_candidate_surface_component_total"]==15 and r["t17_custody_chain_implemented"]is True and r["t18_authorized"]is False and r["production_admissible"]is False,"receipt");x=dict(r);h=x.pop("content_sha256");req(h==hashlib.sha256(s.RECEIPT_DOMAIN.encode()+b"\0"+cb(x)).hexdigest(),"hash");receipts.append(r)
 n=0
 for mode,code in [("PRODUCTION","E_PREDECESSOR_OWNER_SET_REJECTED"),("UNKNOWN","E_PREDECESSOR_OWNER_SET_REJECTED"),(True,"E_PREDECESSOR_OWNER_SET_REJECTED")]:v=list(vs[0]);v[25]=mode;reject(s,v,code);n+=1
 def mutate(i:int,fn,code:str):
  nonlocal n;v=list(vs[0]);x=json.loads(v[i]);fn(x);v[i]=cb(x);reject(s,v,code);n+=1
 pi,ri=26,27
 for f in [lambda x:x.update(schema="x"),lambda x:x["profiles"].reverse(),lambda x:x.update(reject_on_zero_matches=False),lambda x:x["profiles"][0].update(extra=1),lambda x:x["profiles"][0]["segment_identities"].pop("raw_sha256"),lambda x:x["profiles"][0]["segment_identities"].update(raw_sha256="0"*64)]:mutate(pi,f,"E_CUSTODY_CHAIN_POLICY_REJECTED")
 for f in [lambda x:x.pop("raw_sha256"),lambda x:x.update(extra=1),lambda x:x.update(raw_sha256="x"),lambda x:x.update(raw_sha256=x["canonical_sha256"]),lambda x:x.update(raw_sha256="0"*64),lambda x:x.__setitem__("retention_sha256",x["cleanup_sha256"]),lambda x:x.__setitem__("tombstone_sha256",x["validation_sha256"])]:mutate(ri,f,"E_PRODUCTION_CUSTODY_FAILED")
 cross=json.loads(vs[1][ri])["raw_sha256"];mutate(ri,lambda x:x.update(raw_sha256=cross),"E_PRODUCTION_CUSTODY_FAILED")
 for i,raw,code in [(pi,b"{}","E_CUSTODY_CHAIN_POLICY_REJECTED"),(ri,b"{}","E_PRODUCTION_CUSTODY_FAILED"),(ri,vs[0][ri]+b" ","E_PRODUCTION_CUSTODY_FAILED")]:v=list(vs[0]);v[i]=raw;reject(s,v,code);n+=1
 original=s.predecessor.review_owner_set;calls=0
 def wrapped(*a,**k):
  nonlocal calls;calls+=1;return original(*a,**k)
 s.predecessor.review_owner_set=wrapped
 try:s.review_custody_chain(*vs[0])
 finally:s.predecessor.review_owner_set=original
 req(calls==1,"calls");n+=1
 tree=ast.parse(path(SOURCE).read_text());imports=set()
 for x in ast.walk(tree):
  if isinstance(x,ast.Import):imports.update(a.name.split(".")[0]for a in x.names)
  elif isinstance(x,ast.ImportFrom)and x.module:imports.add(x.module.split(".")[0])
 req(imports<={"__future__","hashlib","json","dataclasses","typing","biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_set_synthetic_exact_t15_receipt_track_and_ordered_owner_entry_t01_through_t15_verifier_isolated_lab_v1"},"imports")
 authority=json.loads(path(AUTHORITY).read_text());req(authority["authority"]["consumed"]is False and authority["boundary"]["t17_implemented"]is False and authority["contract"]["public_input_count"]==28,"authority")
 r={"schema":"agent_bridge.biocortex.t17_custody_chain_pack.receipt.v0","status":"APPROVE_T17_CUSTODY_CHAIN_SYNTHETIC_EXACT_VERIFIER","valid_case_count":2,"directed_negative_test_count":n,"source_ast_guard_count":7,"public_input_count":28,"profile_count":2,"custody_segment_count":6,"request_field_count":6,"policy_match_dimension_count":4,"predecessor_review_count_per_case":1,"isolated_lab_candidate_surface_component_total":15,"production_ingestion_controls_implemented":0,"runtime_threats_exercised":0,"runtime_prerequisites_satisfied":0,"real_evidence_items_present":0,"runtime_authority":False,"provider_authority":False,"t17_implemented":True,"t18_authorized":False,"managed_receipt_content_sha256":receipts[0]["content_sha256"],"self_hosted_receipt_content_sha256":receipts[1]["content_sha256"],"authority_raw_sha256":sha(AUTHORITY),"source_raw_sha256":sha(SOURCE),"content_sha256":"0"*64};x=dict(r);del x["content_sha256"];r["content_sha256"]=hashlib.sha256(DOMAIN.encode()+b"\0"+cb(x)).hexdigest();return "".join(f"{k}\t{str(v).lower()if type(v)is bool else v}\n"for k,v in r.items())
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true");a=p.parse_args()
 try:o=evaluate();sys.stdout.write("self_test_contract\tpass\nself_test_mutations\tpass\nself_test_boundary\tpass\n"if a.self_test else o);return 0
 except Exception as e:print(f"check_error\t{e}",file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
