#!/usr/bin/env python3
import argparse,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];SOURCE='scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_identity_window_synthetic_exact_t18_receipt_track_and_owner_role_signature_same_set_revision_deadline_binding_verifier_isolated_lab_v1.py';T17='scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_custody_chain_synthetic_exact_t16_receipt_track_and_six_segment_identity_verifier_isolated_lab_v1_pack.py'
def mod(x,n):
 p=ROOT/x;s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);added=str(p.parent)not in sys.path
 if added:sys.path.insert(0,str(p.parent))
 try:sys.modules[n]=m;s.loader.exec_module(m);return m
 finally:
  if added:sys.path.remove(str(p.parent))
def evaluate():
 s=mod(SOURCE,'_t19');c=mod(T17,'_t17c');base,ps=c.vectors(s.predecessor.predecessor);t18=[(*v,s.predecessor.policy_bytes(),s.predecessor.request_bytes(p['track_id']))for v,p in zip(base,ps,strict=True)];vs=[(*v,s.policy_bytes(),s.request_bytes(p['track_id']))for v,p in zip(t18,ps,strict=True)];out=[]
 for v,p in zip(vs,ps,strict=True):
  r=s.review_owner_identity_window(*v);assert r['track_id']==p['track_id']and r['public_input_count']==32 and r['predecessor_review_count']==1 and r['isolated_lab_candidate_surface_component_total']==17 and r['t19_owner_identity_window_implemented']is True and r['t20_authorized']is False;out.append(r)
 n=0
 def reject(v,code):
  nonlocal n
  try:s.review_owner_identity_window(*v)
  except s.OwnerIdentityWindowError as e:assert e.code==code;n+=1;return
  raise AssertionError('accepted')
 for i,fn,code in [(30,lambda x:x.update(schema='x'),'E_OWNER_IDENTITY_POLICY_REJECTED'),(30,lambda x:x['profiles'].reverse(),'E_OWNER_IDENTITY_POLICY_REJECTED'),(31,lambda x:x.pop('owner_identity_sha256'),'E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED'),*[ (31,lambda x,k=k:x.update({k:'0'*64}),'E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED') for k in s.FIELDS]]:
  v=list(vs[0]);x=json.loads(v[i]);fn(x);v[i]=s.cb(x);reject(v,code)
 for i,raw,code in [(30,b'{}','E_OWNER_IDENTITY_POLICY_REJECTED'),(31,b'{}','E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED'),(31,vs[0][31]+b' ','E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED')]:v=list(vs[0]);v[i]=raw;reject(v,code)
 original=s.predecessor.review_independence;calls=0
 def wrapped(*a,**k):
  nonlocal calls;calls+=1;return original(*a,**k)
 s.predecessor.review_independence=wrapped
 try:s.review_owner_identity_window(*vs[0])
 finally:s.predecessor.review_independence=original
 assert calls==1;n+=1
 return {'valid_case_count':2,'directed_negative_test_count':n,'public_input_count':32,'profile_count':2,'request_field_count':6,'match_dimension_count':8,'predecessor_review_count_per_case':1,'isolated_lab_candidate_surface_component_total':17,'t19_implemented':True,'t20_authorized':False}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--self-test',action='store_true');x=a.parse_args();r=evaluate();print('self_test_boundary\tpass'if x.self_test else ''.join(f'{k}\t{str(v).lower()if type(v)is bool else v}\n'for k,v in r.items()),end='')
