#!/usr/bin/env python3
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];SOURCE='scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_reviewer_independence_synthetic_exact_t17_receipt_track_and_validator_build_config_binding_verifier_isolated_lab_v1.py';T17='scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_custody_chain_synthetic_exact_t16_receipt_track_and_six_segment_identity_verifier_isolated_lab_v1_pack.py';AUTH='scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_review_independence_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json';DOMAIN='AB_TRACK_B_T18_REVIEW_INDEPENDENCE_PACK_V1'
def mod(x,n):
 p=ROOT/x;s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);added=str(p.parent)not in sys.path
 if added:sys.path.insert(0,str(p.parent))
 try:sys.modules[n]=m;s.loader.exec_module(m);return m
 finally:
  if added:sys.path.remove(str(p.parent))
def cb(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def evaluate():
 s=mod(SOURCE,'_t18');c=mod(T17,'_t17c');base,profiles=c.vectors(s.predecessor);vs=[(*v,s.policy_bytes(),s.request_bytes(p['track_id']))for v,p in zip(base,profiles,strict=True)];rs=[]
 for v,p in zip(vs,profiles,strict=True):
  r=s.review_independence(*v);assert r['track_id']==p['track_id']and r['public_input_count']==30 and r['predecessor_review_count']==1 and r['isolated_lab_candidate_surface_component_total']==16 and r['t18_review_independence_implemented']is True and r['t19_authorized']is False; x=dict(r);h=x.pop('content_sha256');assert h==hashlib.sha256(s.DOMAIN.encode()+b'\0'+cb(x)).hexdigest();rs.append(r)
 n=0
 def reject(v,code):
  nonlocal n
  try:s.review_independence(*v)
  except s.ReviewIndependenceError as e:assert e.code==code;n+=1;return
  raise AssertionError('accepted')
 for i,fn,code in [(28,lambda x:x.update(schema='x'),'E_REVIEW_INDEPENDENCE_POLICY_REJECTED'),(28,lambda x:x['profiles'].reverse(),'E_REVIEW_INDEPENDENCE_POLICY_REJECTED'),(28,lambda x:x.update(reject_on_zero_matches=False),'E_REVIEW_INDEPENDENCE_POLICY_REJECTED'),(29,lambda x:x.pop('reviewer_identity_sha256'),'E_PRODUCTION_INDEPENDENT_REVIEW_FAILED'),(29,lambda x:x.update(reviewer_identity_sha256='0'*64),'E_PRODUCTION_INDEPENDENT_REVIEW_FAILED'),(29,lambda x:x.update(validator_build_sha256='0'*64),'E_PRODUCTION_INDEPENDENT_REVIEW_FAILED'),(29,lambda x:x.update(validator_config_sha256='0'*64),'E_PRODUCTION_INDEPENDENT_REVIEW_FAILED'),(29,lambda x:x.update(reviewer_identity_sha256=x['validator_build_sha256']),'E_PRODUCTION_INDEPENDENT_REVIEW_FAILED')]:v=list(vs[0]);x=json.loads(v[i]);fn(x);v[i]=cb(x);reject(v,code)
 for i,raw,code in [(28,b'{}','E_REVIEW_INDEPENDENCE_POLICY_REJECTED'),(29,b'{}','E_PRODUCTION_INDEPENDENT_REVIEW_FAILED'),(29,vs[0][29]+b' ','E_PRODUCTION_INDEPENDENT_REVIEW_FAILED')]:v=list(vs[0]);v[i]=raw;reject(v,code)
 original=s.predecessor.review_custody_chain;calls=0
 def wrapped(*a,**k):
  nonlocal calls;calls+=1;return original(*a,**k)
 s.predecessor.review_custody_chain=wrapped
 try:s.review_independence(*vs[0])
 finally:s.predecessor.review_custody_chain=original
 assert calls==1;n+=1
 owner=json.loads((ROOT/AUTH).read_text());assert owner['authority']['consumed']is False and owner['boundary']['t18_implemented']is False
 r={'schema':'agent_bridge.biocortex.t18_review_independence_pack.receipt.v0','status':'APPROVE_T18_REVIEW_INDEPENDENCE_SYNTHETIC_VERIFIER','valid_case_count':2,'directed_negative_test_count':n,'public_input_count':30,'profile_count':2,'request_field_count':3,'policy_match_dimension_count':5,'predecessor_review_count_per_case':1,'isolated_lab_candidate_surface_component_total':16,'runtime_authority':False,'provider_authority':False,'t18_implemented':True,'t19_authorized':False,'managed_receipt_content_sha256':rs[0]['content_sha256'],'self_hosted_receipt_content_sha256':rs[1]['content_sha256'],'authority_raw_sha256':hashlib.sha256((ROOT/AUTH).read_bytes()).hexdigest(),'source_raw_sha256':hashlib.sha256((ROOT/SOURCE).read_bytes()).hexdigest(),'content_sha256':'0'*64};x=dict(r);del x['content_sha256'];r['content_sha256']=hashlib.sha256(DOMAIN.encode()+b'\0'+cb(x)).hexdigest();return ''.join(f"{k}\t{str(v).lower()if type(v)is bool else v}\n"for k,v in r.items())
def main():
 a=argparse.ArgumentParser();a.add_argument('--self-test',action='store_true');x=a.parse_args()
 try:o=evaluate();sys.stdout.write('self_test_contract\tpass\nself_test_mutations\tpass\nself_test_boundary\tpass\n'if x.self_test else o);return 0
 except Exception as e:print(f'check_error\t{e}',file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
