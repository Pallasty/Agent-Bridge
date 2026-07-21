#!/usr/bin/env python3
"""Read-only Git validator for P11-G11."""
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];CONTRACT=HERE/'majorana_certificate_p11_g11_post_source_inspection_governance_contract.json';RECORD=HERE/'majorana_certificate_p11_g11_post_source_inspection_governance_record.json';PARENT='7159b298811250e91a21a66d28a710dcebca4a65';REPORT='docs/research/fermion-frontier/majorana_certificate_p11e3_source_inspection_report.json'
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
 raw=git('show',f'{PARENT}:{REPORT}');cust=c['P11_E3_result_custody']
 if sha(raw)!=cust['report_raw_sha256']:raise ValueError('E3 report custody drift')
 e=json.loads(raw)
 if e['outcome']!=cust['expected_outcome'] or e['failure_class']!=cust['expected_failure_class'] or e['materialization_completed'] or e['source_text_read']:raise ValueError('E3 failure semantics drift')
 if len(c['findings'])!=5 or any(x['status']!='PASS' for x in c['findings']):raise ValueError('finding failure')
 d=c['decision']
 if d['retry_or_materialization_authorized'] or d['source_reading_authorized'] or d['external_evidence_mutation_authorized'] or d['build_execution_or_measurement_authorized'] or d['scientific_authority']!='NONE':raise ValueError('authority reopened')
 p=c['P11_E3R_required_policy']
 if not all(p.values()):raise ValueError('confined-link policy incomplete')
 if r['contract_raw_sha256']!=sha(CONTRACT.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('digest drift')
 return {'next_gate':d['only_allowed_next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
