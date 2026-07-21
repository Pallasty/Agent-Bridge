#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];C=HERE/'majorana_certificate_p11_g14_source_evidence_analysis_authorization_contract.json';R=HERE/'majorana_certificate_p11_g14_source_evidence_analysis_authorization_record.json';P='394f58d82f95a80de568b8ee16cc9ada52da5ba8';E='docs/research/fermion-frontier/majorana_certificate_p11e4_version_bound_source_evidence_analysis_record.json'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b)
 if b!=canon(r) or git('rev-parse','HEAD').decode().strip()!=P:raise ValueError('lifecycle drift')
 raw=git('show',f'{P}:{E}');e=json.loads(raw);x=c['E4_custody']
 if sha(raw)!=x['record_raw_sha256'] or e['disposition']!=x['expected_disposition'] or e['next_gate']!=x['expected_next_gate']:raise ValueError('E4 custody drift')
 if len(c['readiness_review'])!=6 or any(v['status']!='PASS' for v in c['readiness_review']):raise ValueError('readiness failure')
 d=c['decision'];o=c['operation_limits']
 if d['source_tree_or_custody_mutation_authorized'] or d['network_package_build_execution_or_measurement_authorized'] or d['kernel_bound_candidate_equivalence_or_science_authorized'] or d['scientific_authority']!='NONE':raise ValueError('authority broadening')
 if (o['maximum_excerpt_count'],o['maximum_excerpt_bytes'],o['context_lines_each_side'])!=(30,8192,20):raise ValueError('bounds drift')
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('digest drift')
 return {'next_gate':d['post_run_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
