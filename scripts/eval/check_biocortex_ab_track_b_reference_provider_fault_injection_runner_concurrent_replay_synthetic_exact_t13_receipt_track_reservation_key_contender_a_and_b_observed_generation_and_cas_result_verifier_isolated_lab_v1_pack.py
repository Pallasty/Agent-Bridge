#!/usr/bin/env python3
from __future__ import annotations
import argparse,ast,hashlib,importlib.util,json,sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2];SOURCE="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_concurrent_replay_synthetic_exact_t13_receipt_track_reservation_key_contender_a_and_b_observed_generation_and_cas_result_verifier_isolated_lab_v1.py";T13_CHECKER="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_synthetic_exact_t12_receipt_track_reserved_issuer_nonce_sequence_and_packet_identity_submitted_issuer_nonce_sequence_and_packet_identity_verifier_isolated_lab_v1_pack.py";OWNER="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_concurrent_replay_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json";SEMANTIC="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json";DOMAIN="AB_TRACK_B_T14_CONCURRENT_REPLAY_PACK_V1"
def req(x:bool,d:str)->None:
 if not x:raise ValueError(d)
def path(x:str)->Path:p=ROOT.joinpath(*x.split('/'));r=p.resolve(strict=True);req(ROOT in r.parents and p.is_file()and not p.is_symlink(),x);return p
def sha(x:str)->str:return hashlib.sha256(path(x).read_bytes()).hexdigest()
def cb(x:Any)->bytes:return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def mod(x:str,n:str):
 p=path(x);s=importlib.util.spec_from_file_location(n,p);req(s is not None and s.loader is not None,'import');added=str(p.parent)not in sys.path
 if added:sys.path.insert(0,str(p.parent))
 try:m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
 finally:
  if added:sys.path.remove(str(p.parent))
def vectors(s:Any):
 c=mod(T13_CHECKER,'_t13c');base,profiles=c.vectors(s.predecessor);req(len(base)==2,'vectors');policy=s.known_answer_concurrent_replay_policy_bytes();return [(*v[:-1],policy,s.known_answer_concurrent_replay_request_bytes(p['track_id']),'SYNTHETIC_KAT')for v,p in zip(base,profiles,strict=True)],profiles
def reject(s:Any,v:list[Any],outer:str)->None:
 try:s.review_concurrent_replay(*v)
 except s.ConcurrentReplayReviewError as e:req(e.code==outer,e.code);return
 raise ValueError('accepted')
def evaluate()->str:
 s=mod(SOURCE,'_t14');vs,ps=vectors(s);receipts=[]
 for v,p in zip(vs,ps,strict=True):
  r=s.review_concurrent_replay(*v);req(r['track_id']==p['track_id']and r['public_input_count']==22 and r['predecessor_review_count']==1 and r['isolated_lab_candidate_surface_component_total']==12 and r['t14_concurrent_replay_implemented']is True and r['t15_authorized']is False,'receipt');x=dict(r);h=x.pop('content_sha256');req(h==hashlib.sha256(s.RECEIPT_DOMAIN.encode()+b'\0'+cb(x)).hexdigest(),'hash');receipts.append(r)
 negatives=0
 for mode,code in [('PRODUCTION','E_CONCURRENT_REPLAY_PRODUCTION_MODE_NOT_AUTHORIZED'),('UNKNOWN','E_CONCURRENT_REPLAY_MODE_UNKNOWN'),(True,'E_CONCURRENT_REPLAY_MODE_UNKNOWN')]:v=list(vs[0]);v[-1]=mode;reject(s,v,code);negatives+=1
 pi,ri=-3,-2
 def mutate(index:int,fn,outer:str):
  nonlocal negatives;v=list(vs[0]);x=json.loads(v[index]);fn(x);v[index]=cb(x);reject(s,v,outer);negatives+=1
 for fn in [lambda x:x.update(schema='x'),lambda x:x['profiles'].reverse(),lambda x:x.update(reject_on_zero_matches=False),lambda x:x['profiles'][0].update(extra=1),lambda x:x['profiles'][0].update(contender_a_cas_result=False)]:mutate(pi,fn,'E_CONCURRENT_REPLAY_POLICY_REJECTED')
 for fn in [lambda x:x.update(contender_a_observed_generation=-1),lambda x:x.update(contender_a_observed_generation=True),lambda x:x.update(contender_b_observed_generation=102),lambda x:x.update(contender_a_cas_result=True,contender_b_cas_result=True),lambda x:x.update(contender_a_cas_result=False,contender_b_cas_result=False),lambda x:x.update(contender_a_cas_result=1),lambda x:x.update(reservation_key_sha256='x'),lambda x:x.update(extra=1)]:mutate(ri,fn,s.TARGET_PRODUCTION_FAILURE_CODE)
 for i,raw,outer in [(pi,b'{}','E_CONCURRENT_REPLAY_POLICY_REJECTED'),(ri,b'{}',s.TARGET_PRODUCTION_FAILURE_CODE),(ri,vs[0][ri]+b' ',s.TARGET_PRODUCTION_FAILURE_CODE)]:v=list(vs[0]);v[i]=raw;reject(s,v,outer);negatives+=1
 original=s.predecessor.review_replay;calls=0
 def wrapped(*a,**k):
  nonlocal calls;calls+=1;return original(*a,**k)
 s.predecessor.review_replay=wrapped
 try:s.review_concurrent_replay(*vs[0])
 finally:s.predecessor.review_replay=original
 req(calls==1,'calls');negatives+=1
 tree=ast.parse(path(SOURCE).read_text());imports=set()
 for n in ast.walk(tree):
  if isinstance(n,ast.Import):imports.update(a.name.split('.')[0]for a in n.names)
  elif isinstance(n,ast.ImportFrom)and n.module:imports.add(n.module.split('.')[0])
 allowed={'__future__','hashlib','json','dataclasses','typing','biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_synthetic_exact_t12_receipt_track_reserved_issuer_nonce_sequence_and_packet_identity_submitted_issuer_nonce_sequence_and_packet_identity_verifier_isolated_lab_v1'};req(imports<=allowed,'imports')
 owner=json.loads(path(OWNER).read_text());sem=json.loads(path(SEMANTIC).read_text());req(owner['boundary']['t14_implemented']is False and next(x for x in sem['threat_cases']if x['case_id']=='T14')['expected_reason_code']==s.TARGET_PRODUCTION_FAILURE_CODE,'authority')
 r={'schema':'agent_bridge.biocortex.concurrent_replay_isolated_lab_v1_pack.receipt.v0','status':'APPROVE_T14_CONCURRENT_REPLAY_SYNTHETIC_EXACT_VERIFIER','valid_case_count':2,'directed_negative_test_count':negatives,'source_ast_guard_count':8,'public_input_count':22,'profile_count':2,'request_field_count':5,'policy_match_dimension_count':7,'predecessor_review_count_per_case':1,'isolated_lab_candidate_surface_component_total':12,'production_ingestion_controls_implemented':0,'runtime_threats_exercised':0,'runtime_prerequisites_satisfied':0,'real_evidence_items_present':0,'runtime_authority':False,'provider_authority':False,'t14_implemented':True,'t15_authorized':False,'managed_receipt_content_sha256':receipts[0]['content_sha256'],'self_hosted_receipt_content_sha256':receipts[1]['content_sha256'],'owner_raw_sha256':sha(OWNER),'semantic_raw_sha256':sha(SEMANTIC),'source_raw_sha256':sha(SOURCE),'content_sha256':'0'*64};x=dict(r);del x['content_sha256'];r['content_sha256']=hashlib.sha256(DOMAIN.encode()+b'\0'+cb(x)).hexdigest();return ''.join(f"{k}\t{str(v).lower()if type(v)is bool else v}\n"for k,v in r.items())
def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');a=p.parse_args()
 try:o=evaluate();sys.stdout.write('self_test_contract\tpass\nself_test_mutations\tpass\nself_test_boundary\tpass\n'if a.self_test else o);return 0
 except Exception as e:print(f'check_error\t{e}',file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
