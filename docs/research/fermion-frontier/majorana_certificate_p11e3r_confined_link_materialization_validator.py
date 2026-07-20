#!/usr/bin/env python3
"""Git custody plus synthetic confined-symlink policy validator for P11-E3R."""
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path,PurePosixPath
from typing import Any
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];CONTRACT=HERE/'majorana_certificate_p11e3r_confined_link_materialization_contract.json';RECORD=HERE/'majorana_certificate_p11e3r_confined_link_materialization_record.json';PARENT='29ecb3500b76210eb0666f022b737ae9b42a6b96';G11='docs/research/fermion-frontier/majorana_certificate_p11_g11_post_source_inspection_governance_record.json'
def canon(x:Any)->bytes:return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def load(p:Path,strict=False):
 b=p.read_bytes();v=json.loads(b)
 if strict and b!=canon(v):raise ValueError('noncanonical record')
 return v
def git(*a:str)->bytes:return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def normalize(parts):
 out=[]
 for part in parts:
  if part in ('','.'):continue
  if part=='..':
   if not out:raise ValueError('root escape')
   out.pop()
  else:out.append(part)
 return PurePosixPath(*out)
def confined_target(link_path:str,target:str)->str:
 lp=PurePosixPath(link_path);tp=PurePosixPath(target)
 if lp.is_absolute() or tp.is_absolute() or not target or '\x00' in target or any(ord(c)<32 for c in target):raise ValueError('unsafe link')
 resolved=normalize((*lp.parent.parts,*tp.parts))
 root=normalize((lp.parts[0],))
 if not resolved.parts or resolved.parts[0]!=root.parts[0]:raise ValueError('cross-root link')
 return str(resolved)
def verify_graph(entries:set[str],links:dict[str,str])->None:
 for link,target in links.items():
  seen={link};cur=confined_target(link,target)
  while cur in links:
   if cur in seen:raise ValueError('link cycle')
   seen.add(cur);cur=confined_target(cur,links[cur])
  if cur not in entries:raise ValueError('dangling link')
def verify():
 c=load(CONTRACT);r=load(RECORD,True)
 if git('rev-parse','HEAD').decode().strip()!=PARENT or r['parent_commit']!=PARENT:raise ValueError('parent drift')
 raw=git('show',f'{PARENT}:{G11}');cust=c['P11_G11_custody']
 if sha(raw)!=cust['record_raw_sha256']:raise ValueError('G11 custody drift')
 g=json.loads(raw)
 if g['disposition']!=cust['expected_disposition'] or g['next_gate']!=cust['expected_next_gate']:raise ValueError('G11 semantics drift')
 a=c['current_authority']
 if any(a[k] for k in a if k.endswith('authorized')) or a['scientific_authority']!='NONE':raise ValueError('authority reopened')
 verify_graph({'pkg/Documentation/Changes'}, {'pkg/Changes':'Documentation/Changes'})
 if r['contract_raw_sha256']!=sha(CONTRACT.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('digest drift')
 return {'next_gate':c['only_allowed_next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
