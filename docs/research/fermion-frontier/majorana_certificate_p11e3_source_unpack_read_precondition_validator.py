#!/usr/bin/env python3
"""Read-only Git validator for P11-E3 pre-read design."""
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];CONTRACT=HERE/'majorana_certificate_p11e3_source_unpack_read_precondition_contract.json';RECORD=HERE/'majorana_certificate_p11e3_source_unpack_read_precondition_record.json';PARENT='768928a53af9174fa30e39e80884fa0afdd500f6';G9='docs/research/fermion-frontier/majorana_certificate_p11_g9_post_remedial_custody_governance_record.json'
def canon(x:Any)->bytes:return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def load(p:Path,strict=False):
 b=p.read_bytes();v=json.loads(b)
 if strict and b!=canon(v):raise ValueError('noncanonical record')
 return v
def git(*a:str)->bytes:return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def verify():
 c=load(CONTRACT);r=load(RECORD,True)
 if git('rev-parse','HEAD').decode().strip()!=PARENT or r['parent_commit']!=PARENT:raise ValueError('parent drift')
 raw=git('show',f'{PARENT}:{G9}');cust=c['P11_G9_custody']
 if sha(raw)!=cust['record_raw_sha256']:raise ValueError('G9 custody drift')
 g=json.loads(raw)
 if g['disposition']!=cust['expected_disposition'] or g['next_gate']!=cust['expected_next_gate']:raise ValueError('G9 semantics drift')
 a=c['current_authority'];bools=[k for k in a if k.endswith('authorized')]
 if any(a[k] for k in bools) or a['scientific_authority']!='NONE':raise ValueError('authority reopened')
 safe=c['future_safe_materialization_contract']
 if not safe['reject_filesystem_escape_before_and_after_extraction'] or not safe['record_sorted_final_tree_path_type_mode_size_and_sha256_manifest']:raise ValueError('safe materialization drift')
 if not c['future_operation_requires_independent_authorization']:raise ValueError('G10 bypass')
 if r['contract_raw_sha256']!=sha(CONTRACT.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('contract digest drift')
 return {'next_gate':c['only_allowed_next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
