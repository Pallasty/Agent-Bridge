#!/usr/bin/env python3
"""Offline E3R result validator."""
import hashlib,json,os,sys
from pathlib import Path
ROOT=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e3r-source-inspection');HERE=Path(__file__).resolve().parent;M=HERE/'majorana_certificate_p11e3r_source_inspection_manifest.json';R=HERE/'majorana_certificate_p11e3r_source_inspection_report.json'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def load(p):
 b=p.read_bytes();v=json.loads(b)
 if b!=canon(v):raise ValueError('noncanonical JSON')
 return v
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
 m,r,s=load(M),load(R),load(ROOT/'receipts/state.json')
 if s['outcome']!='SOURCE_MATERIALIZATION_AND_BOUNDED_READ_COMPLETED' or len(s['packages'])!=4 or len(s['commands'])!=4:raise ValueError('state drift')
 if sha(ROOT/'receipts/state.json')!=m['state_sha256'] or not r['pre_post_link_policy_passed']:raise ValueError('manifest drift')
 for p in s['packages']:
  tree=load(ROOT/'receipts'/f"{p['source_package']}.tree.json")
  if len(tree)!=p['tree_entry_count'] or hashlib.sha256(canon(tree)).hexdigest()!=p['tree_manifest_sha256']:raise ValueError('tree manifest drift')
  root=ROOT/'trees'/f"{p['source_package']}={p['source_version']}";resolved=root.resolve()
  for q in root.rglob('*'):
   if q.is_symlink():
    target=q.resolve(strict=True)
    if resolved not in (target,*target.parents):raise ValueError('link escape')
 if r['candidate_or_kernel_bound_derived'] or r['scientific_claim_established']:raise ValueError('claim boundary drift')
 return {'package_count':4,'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
