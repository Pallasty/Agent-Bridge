#!/usr/bin/env python3
"""Validate the fail-closed P11-E4 operation record."""
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
R=HERE/'majorana_certificate_p11e4_source_evidence_analysis_result.json'
C=HERE/'majorana_certificate_p11e4_version_bound_source_evidence_analysis_contract.json'
G=HERE/'majorana_certificate_p11_g14_source_evidence_analysis_authorization_record.json'
M=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e3r-source-inspection/receipts/gcc-15.tree.json')
P='7b2aa7fe1f54a3beaaadf7c68f481292185febc0'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def verify():
 r=json.loads(R.read_bytes())
 if R.read_bytes().rstrip(b'\n')!=canon(r):raise ValueError('record is not canonical JSON')
 if subprocess.run(['git','rev-parse','HEAD'],cwd=REPO,check=True,capture_output=True,text=True).stdout.strip()!=P:raise ValueError('lifecycle drift')
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['g14_authorization_record_raw_sha256']!=sha(G.read_bytes()) or r['tree_manifest_raw_sha256']!=sha(M.read_bytes()):raise ValueError('custody digest drift')
 rows=json.loads(M.read_bytes())
 if any(x.get('relative_path')=='gcc/gcc.cc' and x.get('type')=='file' for x in rows):raise ValueError('recorded absence contradicted')
 if not any(x.get('relative_path')=='gcc-15.2.0.tar.xz' and x.get('type')=='file' for x in rows):raise ValueError('nested archive evidence missing')
 if r['disposition']!='STOPPED_FAIL_CLOSED_BEFORE_SOURCE_TEXT_READ' or r['source_text_read'] or r['excerpt_count']!=0:raise ValueError('failure boundary drift')
 if r['scientific_authority']!='NONE' or r['next_gate']!='P11-G15-POST-SOURCE-EVIDENCE-ANALYSIS-GOVERNANCE-V1':raise ValueError('authority drift')
 return {'excerpt_count':0,'next_gate':r['next_gate'],'source_text_read':False,'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
