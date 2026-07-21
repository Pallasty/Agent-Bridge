#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];C=HERE/'majorana_certificate_p11_g12_confined_link_authorization_contract.json';R=HERE/'majorana_certificate_p11_g12_confined_link_authorization_record.json';P='d2f7b99ebcb9f4a4cd34e9920c9ef3d671e8913a';E='docs/research/fermion-frontier/majorana_certificate_p11e3r_confined_link_materialization_record.json'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b)
 if b!=canon(r) or git('rev-parse','HEAD').decode().strip()!=P:raise ValueError('lifecycle drift')
 raw=git('show',f'{P}:{E}');e=json.loads(raw);x=c['E3R_custody']
 if sha(raw)!=x['record_raw_sha256'] or e['disposition']!=x['expected_disposition'] or e['next_gate']!=x['expected_next_gate']:raise ValueError('E3R custody drift')
 if len(c['readiness_review'])!=6 or any(v['status']!='PASS' for v in c['readiness_review']):raise ValueError('readiness failure')
 d=c['decision']
 if d['network_package_or_custody_mutation_authorized'] or d['patch_build_compile_link_execute_measure_or_candidate_authorized'] or d['scientific_authority']!='NONE':raise ValueError('authority broadening')
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('digest drift')
 return {'next_gate':d['post_run_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
