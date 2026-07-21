#!/usr/bin/env python3
"""Read-only Git validator for P11-G10 authorization."""
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];CONTRACT=HERE/'majorana_certificate_p11_g10_source_materialization_read_authorization_contract.json';RECORD=HERE/'majorana_certificate_p11_g10_source_materialization_read_authorization_record.json';PARENT='a86583e3597bce8afc569da9dca2c24976a9111b';E3='docs/research/fermion-frontier/majorana_certificate_p11e3_source_unpack_read_precondition_record.json'
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
 raw=git('show',f'{PARENT}:{E3}');cust=c['P11_E3_custody']
 if sha(raw)!=cust['record_raw_sha256']:raise ValueError('E3 custody drift')
 e=json.loads(raw)
 if e['disposition']!=cust['expected_disposition'] or e['next_gate']!=cust['expected_next_gate']:raise ValueError('E3 semantics drift')
 if len(c['readiness_review'])!=6 or any(x['status']!='PASS' for x in c['readiness_review']):raise ValueError('readiness failure')
 d=c['decision']
 if not d['authenticated_source_materialization_authorized'] or not d['bounded_text_search_and_excerpt_hashing_authorized']:raise ValueError('bounded operation missing')
 if d['network_or_package_mutation_authorized'] or d['E2R_custody_root_mutation_authorized'] or d['source_patch_build_configure_compile_link_execute_or_measure_authorized'] or d['candidate_or_kernel_bound_derivation_authorized'] or d['scientific_authority']!='NONE':raise ValueError('authority too broad')
 if r['contract_raw_sha256']!=sha(CONTRACT.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('digest drift')
 return {'next_gate':d['post_run_gate'],'readiness_pass_count':6,'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
