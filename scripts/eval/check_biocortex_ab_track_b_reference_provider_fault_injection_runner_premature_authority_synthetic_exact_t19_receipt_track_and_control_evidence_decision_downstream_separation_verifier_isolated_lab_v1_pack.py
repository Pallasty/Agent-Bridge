#!/usr/bin/env python3
import argparse,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];SOURCE='scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_premature_authority_synthetic_exact_t19_receipt_track_and_control_evidence_decision_downstream_separation_verifier_isolated_lab_v1.py';T17='scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_custody_chain_synthetic_exact_t16_receipt_track_and_six_segment_identity_verifier_isolated_lab_v1_pack.py'
def mod(x,n):
 p=ROOT/x;s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);added=str(p.parent)not in sys.path
 if added:sys.path.insert(0,str(p.parent))
 try:sys.modules[n]=m;s.loader.exec_module(m);return m
 finally:
  if added:sys.path.remove(str(p.parent))
def evaluate():
 s=mod(SOURCE,'_t20');c=mod(T17,'_t17c');t19=s.predecessor;t18=t19.predecessor;base,ps=c.vectors(t18.predecessor);v18=[(*v,t18.policy_bytes(),t18.request_bytes(p['track_id']))for v,p in zip(base,ps,strict=True)];v19=[(*v,t19.policy_bytes(),t19.request_bytes(p['track_id']))for v,p in zip(v18,ps,strict=True)];vs=[(*v,s.policy_bytes(),s.request_bytes(p['track_id']))for v,p in zip(v19,ps,strict=True)]
 rs=[]
 for v in vs:
  r=s.review_premature_authority(*v);assert r['status']=='REJECTED_FAIL_CLOSED' and r['reason_code']=='E_PRODUCTION_DECISION_OR_DOWNSTREAM_SEPARATION_FAILED' and r['positive_production_decision']is False and r['downstream_execution_authority']is False and r['successor_authorized']is False;rs.append(r)
 n=0
 def reject(v,code):
  nonlocal n
  try:s.review_premature_authority(*v)
  except s.PrematureAuthorityError as e:assert e.code==code;n+=1;return
  raise AssertionError('accepted')
 for i,raw,code in [(32,b'{}','E_PRODUCTION_DECISION_OR_DOWNSTREAM_SEPARATION_FAILED'),(33,b'{}','E_PRODUCTION_DECISION_OR_DOWNSTREAM_SEPARATION_FAILED'),(33,vs[0][33]+b' ','E_PRODUCTION_DECISION_OR_DOWNSTREAM_SEPARATION_FAILED')]:v=list(vs[0]);v[i]=raw;reject(v,code)
 for k in s.FIELDS:v=list(vs[0]);x=json.loads(v[33]);x[k]='0'*64;v[33]=s.cb(x);reject(v,'E_PRODUCTION_DECISION_OR_DOWNSTREAM_SEPARATION_FAILED')
 original=s.predecessor.review_owner_identity_window;calls=0
 def wrapped(*a,**k):
  nonlocal calls;calls+=1;return original(*a,**k)
 s.predecessor.review_owner_identity_window=wrapped
 try:s.review_premature_authority(*vs[0])
 finally:s.predecessor.review_owner_identity_window=original
 assert calls==1;n+=1
 return {'valid_case_count':2,'directed_negative_test_count':n,'public_input_count':34,'profile_count':2,'request_field_count':4,'match_dimension_count':6,'predecessor_review_count_per_case':1,'status':'REJECTED_FAIL_CLOSED','positive_production_decision':False,'downstream_execution_authority':False,'successor_authorized':False}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--self-test',action='store_true');x=a.parse_args();r=evaluate();print('self_test_boundary\tpass'if x.self_test else ''.join(f'{k}\t{str(v).lower()if type(v)is bool else v}\n'for k,v in r.items()),end='')
