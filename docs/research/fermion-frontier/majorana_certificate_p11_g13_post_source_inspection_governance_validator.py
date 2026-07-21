#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];C=HERE/'majorana_certificate_p11_g13_post_source_inspection_governance_contract.json';R=HERE/'majorana_certificate_p11_g13_post_source_inspection_governance_record.json';P='960cdd32f276a55a718d909d2c066125b26fc80f';REPORT='docs/research/fermion-frontier/majorana_certificate_p11e3r_source_inspection_report.json'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b)
 if b!=canon(r) or git('rev-parse','HEAD').decode().strip()!=P:raise ValueError('lifecycle drift')
 raw=git('show',f'{P}:{REPORT}');e=json.loads(raw);x=c['E3R_custody']
 if sha(raw)!=x['report_raw_sha256'] or e['outcome']!=x['expected_outcome'] or not e['materialization_completed'] or not e['pre_post_link_policy_passed'] or e['scientific_claim_established']:raise ValueError('E3R custody drift')
 if len(c['findings'])!=5 or any(v['status']!='PASS' for v in c['findings']):raise ValueError('finding failure')
 d=c['decision']
 if d['source_tree_mutation_or_additional_read_authorized'] or d['build_execution_measurement_or_candidate_authorized'] or d['kernel_accounting_bound_derivation_authorized'] or d['scientific_authority']!='NONE':raise ValueError('authority reopened')
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('digest drift')
 return {'next_gate':d['only_allowed_next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
