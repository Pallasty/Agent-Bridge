#!/usr/bin/env python3
"""Independent checker for the T13 replay isolated-lab verifier."""
from __future__ import annotations
import argparse,ast,copy,hashlib,importlib.util,json,sys
from pathlib import Path
from typing import Any,Callable
ROOT=Path(__file__).resolve().parents[2]
SOURCE="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_synthetic_exact_t12_receipt_track_reserved_issuer_nonce_sequence_and_packet_identity_submitted_issuer_nonce_sequence_and_packet_identity_verifier_isolated_lab_v1.py"
T12_CHECKER="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_synthetic_exact_t11_receipt_track_validation_owner_epoch_and_decision_recheck_owner_epoch_verifier_isolated_lab_v1_pack.py"
OWNER="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
SEMANTIC="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
DOMAIN="AB_TRACK_B_T13_REPLAY_ISOLATED_LAB_PACK_RECEIPT_V1"
def require(ok:bool,detail:str)->None:
 if not ok:raise ValueError(detail)
def path(rel:str)->Path:
 p=ROOT.joinpath(*rel.split('/'));r=p.resolve(strict=True);require(ROOT in r.parents and p.is_file()and not p.is_symlink(),rel);return p
def sha(rel:str)->str:return hashlib.sha256(path(rel).read_bytes()).hexdigest()
def cb(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def module(rel:str,name:str):
 p=path(rel);spec=importlib.util.spec_from_file_location(name,p);require(spec is not None and spec.loader is not None,"import");inserted=str(p.parent)not in sys.path
 if inserted:sys.path.insert(0,str(p.parent))
 try:m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
 finally:
  if inserted:sys.path.remove(str(p.parent))
def vectors(subject:Any):
 c=module(T12_CHECKER,"_t12_checker_t13");base,profiles=c.vectors(subject.predecessor);require(len(base)==2,"vectors");policy=subject.known_answer_replay_policy_bytes();out=[]
 for v,p in zip(base,profiles,strict=True):require(len(v)==18 and v[-1]=="SYNTHETIC_KAT","T12 topology");out.append((*v[:-1],policy,subject.known_answer_replay_request_bytes(p["track_id"]),"SYNTHETIC_KAT"))
 return out,profiles
def mutate(raw:bytes,op:Callable[[dict[str,Any]],None])->bytes:v=json.loads(raw);op(v);return cb(v)
def reject(subject:Any,v:tuple[Any,...],outer:str,detail:str|None=None)->None:
 try:subject.review_replay(*v)
 except subject.ReplayReviewError as e:require(e.code==outer,f"{e.code}!={outer}");require(detail is None or e.detail_code==detail,f"{e.detail_code}!={detail}");return
 raise ValueError("mutation accepted")
def validate(subject:Any,r:dict[str,Any],track:str)->None:
 expected={"MANAGED_SPANNER_CLOUD_KMS":"ddb58a2e4db7c74aedbf2504dcf38bde8419722429aeb3dba9cd61273ba3177d","SELF_HOSTED_ETCD_OPENBAO":"d51f20f0c0b6ba03cb8fcc8b561c671d38b59fdc80a6fe35beafa0ae9d2f5eee"}[track];require(r["track_id"]==track and r["predecessor_receipt_content_sha256"]==expected,"binding");require(r["public_input_count"]==20 and r["binding_policy_match_dimension_count"]==5 and r["binding_request_field_count"]==3,"topology");require(r["isolated_lab_candidate_surface_component_total"]==11 and r["t13_replay_implemented"]is True and r["t14_authorized"]is False,"boundary");require(r["implementation_authority_single_use_consumed"]is True and r["runtime_authority"]is False and r["provider_authority"]is False and r["production_admissible"]is False,"authority");require(r["submitted_issuer_nonce"]!=r["reserved_issuer_nonce"]and r["submitted_sequence"]!=r["reserved_sequence"]and r["submitted_packet_identity_sha256"]!=r["reserved_packet_identity_sha256"],"fresh");x=dict(r);observed=x.pop("content_sha256");require(observed==hashlib.sha256(subject.RECEIPT_DOMAIN.encode()+b"\0"+cb(x)).hexdigest(),"hash")
def directed(subject:Any,valid:tuple[Any,...])->int:
 n=0
 def check(v:tuple[Any,...],outer:str,detail:str|None=None)->None:
  nonlocal n;reject(subject,v,outer,detail);n+=1
 for mode,code in (("PRODUCTION","E_REPLAY_PRODUCTION_MODE_NOT_AUTHORIZED"),("UNKNOWN","E_REPLAY_MODE_UNKNOWN"),(True,"E_REPLAY_MODE_UNKNOWN")):
  v=list(valid);v[-1]=mode;check(tuple(v),code)
 original=subject.predecessor.review_owner_toctou;calls=0
 def forbidden(*a:Any,**k:Any):
  nonlocal calls;calls+=1;raise AssertionError
 subject.predecessor.review_owner_toctou=forbidden
 try:check(tuple([object()for _ in valid[:-1]]+["PRODUCTION"]),"E_REPLAY_PRODUCTION_MODE_NOT_AUTHORIZED")
 finally:subject.predecessor.review_owner_toctou=original
 require(calls==0,"mode ordering")
 pi,ri=-3,-2
 mutations=[(pi,lambda x:x.update(schema="x"),"E_REPLAY_POLICY_REJECTED","E_REPLAY_POLICY_SCHEMA"),(pi,lambda x:x["profiles"].reverse(),"E_REPLAY_POLICY_REJECTED","E_REPLAY_PROFILE_EXACT"),(pi,lambda x:x.update(reject_on_zero_matches=False),"E_REPLAY_POLICY_REJECTED","E_REPLAY_POLICY_AMBIGUITY"),(pi,lambda x:x["profiles"][0].update(submitted_sequence=4102),"E_REPLAY_POLICY_REJECTED","E_REPLAY_PROFILE_EXACT"),(pi,lambda x:x["profiles"][0].update(extra=1),"E_REPLAY_POLICY_REJECTED","E_REPLAY_PROFILE_FIELDS"),(ri,lambda x:x.update(submitted_sequence=-1),subject.TARGET_PRODUCTION_FAILURE_CODE,"E_SUBMITTED_SEQUENCE"),(ri,lambda x:x.update(submitted_sequence=True),subject.TARGET_PRODUCTION_FAILURE_CODE,"E_SUBMITTED_SEQUENCE"),(ri,lambda x:x.update(submitted_issuer_nonce="managed-reserved-0001"),subject.TARGET_PRODUCTION_FAILURE_CODE,"E_REPLAY_EXACT_MATCH"),(ri,lambda x:x.update(submitted_sequence=4100),subject.TARGET_PRODUCTION_FAILURE_CODE,"E_REPLAY_EXACT_MATCH"),(ri,lambda x:x.update(submitted_packet_identity_sha256="fbce175924579ab998990a7438b611cfd419937903d180e930c11058999ccbdc"),subject.TARGET_PRODUCTION_FAILURE_CODE,"E_REPLAY_EXACT_MATCH"),(ri,lambda x:x.update(extra=1),subject.TARGET_PRODUCTION_FAILURE_CODE,"E_REPLAY_REQUEST_FIELDS")]
 for i,op,outer,detail in mutations:v=list(valid);v[i]=mutate(v[i],op);check(tuple(v),outer,detail)
 for i,raw,outer in ((pi,b"{}","E_REPLAY_POLICY_REJECTED"),(ri,b"{}",subject.TARGET_PRODUCTION_FAILURE_CODE),(ri,b'{"submitted_sequence":4101,"submitted_sequence":4101,"submitted_issuer_nonce":"x","submitted_packet_identity_sha256":"'+b'0'*64+b'"}',subject.TARGET_PRODUCTION_FAILURE_CODE),(ri,valid[ri]+b' ',subject.TARGET_PRODUCTION_FAILURE_CODE)):
  v=list(valid);v[i]=raw;check(tuple(v),outer)
 v=list(valid);v[pi]=b"{}";v[ri]=b"{}";check(tuple(v),"E_REPLAY_POLICY_REJECTED")
 calls=0
 def wrapped(*a:Any,**k:Any):
  nonlocal calls;calls+=1;return original(*a,**k)
 subject.predecessor.review_owner_toctou=wrapped
 try:subject.review_replay(*valid)
 finally:subject.predecessor.review_owner_toctou=original
 require(calls==1,"predecessor calls");return n+1
def guards()->int:
 tree=ast.parse(path(SOURCE).read_text());imports=set()
 for node in ast.walk(tree):
  if isinstance(node,ast.Import):imports.update(x.name.split('.')[0]for x in node.names)
  elif isinstance(node,ast.ImportFrom)and node.module:imports.add(node.module.split('.')[0])
 allowed={"__future__","hashlib","json","dataclasses","typing","biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_synthetic_exact_t11_receipt_track_validation_owner_epoch_and_decision_recheck_owner_epoch_verifier_isolated_lab_v1"};require(imports<=allowed,repr(imports-allowed));text=path(SOURCE).read_text()
 for token in ("socket","requests","urllib","subprocess","time.time","datetime","os.environ","open("):require(token not in text,token)
 return 8
def evaluate()->str:
 s=module(SOURCE,"_t13_subject");vs,ps=vectors(s);receipts=[]
 for v,p in zip(vs,ps,strict=True):r=s.review_replay(*v);validate(s,r,p["track_id"]);receipts.append(r)
 negatives=directed(s,vs[0]);owner=json.loads(path(OWNER).read_text());semantic=json.loads(path(SEMANTIC).read_text());require(owner["boundary"]["t13_implemented"]is False and owner["state_machine"]["future_successor_integrated_full_consumes_authority"]is True,"owner");t13=next(x for x in semantic["threat_cases"]if x["case_id"]=="T13");require(t13["expected_reason_code"]==s.TARGET_PRODUCTION_FAILURE_CODE,"semantic")
 pack={"schema":"agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.replay_isolated_lab_v1_pack.receipt.v0","status":"APPROVE_T13_REPLAY_SYNTHETIC_EXACT_VERIFIER","valid_case_count":2,"directed_negative_test_count":negatives,"source_ast_guard_count":guards(),"public_input_count":20,"profile_count":2,"request_field_count":3,"policy_match_dimension_count":5,"predecessor_review_count_per_case":1,"isolated_lab_candidate_surface_component_total":11,"production_ingestion_controls_implemented":0,"runtime_threats_exercised":0,"runtime_prerequisites_satisfied":0,"real_evidence_items_present":0,"runtime_authority":False,"provider_authority":False,"t13_implemented":True,"t14_authorized":False,"managed_receipt_content_sha256":receipts[0]["content_sha256"],"self_hosted_receipt_content_sha256":receipts[1]["content_sha256"],"owner_raw_sha256":sha(OWNER),"semantic_raw_sha256":sha(SEMANTIC),"source_raw_sha256":sha(SOURCE),"content_sha256":"0"*64};x=dict(pack);del x["content_sha256"];pack["content_sha256"]=hashlib.sha256(DOMAIN.encode()+b"\0"+cb(x)).hexdigest();return ''.join(f"{k}\t{str(v).lower()if type(v)is bool else v}\n"for k,v in pack.items())
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true");a=p.parse_args()
 try:o=evaluate();sys.stdout.write("self_test_contract\tpass\nself_test_mutations\tpass\nself_test_boundary\tpass\n"if a.self_test else o);return 0
 except Exception as e:print(f"check_error\t{e}",file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
