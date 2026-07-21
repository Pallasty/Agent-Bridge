#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
C=HERE/'majorana_certificate_p11_g15_post_source_evidence_analysis_governance_contract.json';R=HERE/'majorana_certificate_p11_g15_post_source_evidence_analysis_governance_record.json'
P='aa1d21de79b0abee53acf0032526103dfab38b71';RESULT='docs/research/fermion-frontier/majorana_certificate_p11e4_source_evidence_analysis_result.json';RUNNER='docs/research/fermion-frontier/majorana_certificate_p11e4_source_evidence_analysis_runner.py'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b)
 if b.rstrip(b'\n')!=canon(r) or git('rev-parse','HEAD').decode().strip()!=P:raise ValueError('lifecycle drift')
 raw=git('show',f'{P}:{RESULT}');e=json.loads(raw);x=c['E4_custody']
 if sha(raw)!=x['result_raw_sha256'] or sha(git('show',f'{P}:{RUNNER}'))!=x['runner_raw_sha256']:raise ValueError('E4 custody drift')
 if e['disposition']!=x['expected_disposition'] or e['source_text_read'] is not False or e['excerpt_count']!=0 or e['next_gate']!=x['expected_next_gate']:raise ValueError('E4 boundary drift')
 if len(c['findings'])!=5 or any(v['status']!='PASS' for v in c['findings']):raise ValueError('finding failure')
 d=c['decision']
 forbidden=['E4_retry_authorized','nested_archive_materialization_authorized','source_text_read_authorized','source_or_custody_mutation_authorized','network_package_build_execution_or_measurement_authorized','kernel_bound_candidate_equivalence_or_science_authorized']
 if any(d[k] for k in forbidden) or d['scientific_authority']!='NONE':raise ValueError('authority reopened')
 req=c['future_design_requirements']
 if not all(req.values()) or d['only_allowed_next_gate']!='P11-E4R-NESTED-SOURCE-MATERIALIZATION-CONTRACT-DESIGN-V1':raise ValueError('remediation boundary drift')
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('digest drift')
 return {'finding_count':5,'next_gate':d['only_allowed_next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
