#!/usr/bin/env python3
"""Read-only Git validator for P11-G9 custody governance."""
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];CONTRACT=HERE/'majorana_certificate_p11_g9_post_remedial_custody_governance_contract.json';RECORD=HERE/'majorana_certificate_p11_g9_post_remedial_custody_governance_record.json';PARENT='f0f2baf26da0582854987717ba5bda2ca2134cc5';REPORT='docs/research/fermion-frontier/majorana_certificate_p11e2r_remedial_source_archive_custody_report.json'
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
 raw=git('show',f'{PARENT}:{REPORT}');cust=c['E2R_custody']
 if sha(raw)!=cust['report_raw_sha256']:raise ValueError('E2R report custody drift')
 e=json.loads(raw)
 if e['outcome']!=cust['expected_outcome'] or not e['complete_set_custody_established'] or not e['final_path_receipts_rehashed'] or e['host_apt_warning_detected'] or e['old_p11e1_evidence_used']:raise ValueError('E2R semantics drift')
 if len(c['findings'])!=5 or any(x['status']!='PASS' for x in c['findings']):raise ValueError('finding failure')
 d=c['decision']
 if any(d[x] for x in ('network_or_archive_acquisition_authorized','external_evidence_mutation_authorized','archive_unpack_or_source_reading_authorized','candidate_implementation_or_execution_authorized','kernel_accounting_bound_design_authorized')) or d['scientific_authority']!='NONE':raise ValueError('authority reopened')
 if r['contract_raw_sha256']!=sha(CONTRACT.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('contract digest drift')
 return {'next_gate':d['only_allowed_next_gate'],'finding_pass_count':5,'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
