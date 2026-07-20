#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];C=HERE/'majorana_certificate_p11_g17_post_nested_source_materialization_governance_contract.json';R=HERE/'majorana_certificate_p11_g17_post_nested_source_materialization_governance_record.json';P='c16223ef260d8175b7386a182aae722b1b21e9d9';BASE='docs/research/fermion-frontier/'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b)
 if b.rstrip(b'\n')!=canon(r) or git('rev-parse','HEAD').decode().strip()!=P or c['required_direct_parent_commit']!=P:raise ValueError('lifecycle drift')
 x=c['E4R_custody'];raw=git('show',f"{P}:{BASE}{x['result_relative_path']}");run=git('show',f"{P}:{BASE}{x['runner_relative_path']}");e=json.loads(raw)
 if sha(raw)!=x['result_raw_sha256'] or sha(run)!=x['runner_raw_sha256'] or e['disposition']!=x['expected_disposition'] or e['next_gate']!=x['expected_next_gate']:raise ValueError('E4R custody drift')
 if any(e[k] for k in ['derived_root_created','staging_directory_created','tree_manifest_created','source_text_semantically_read']):raise ValueError('zero-materialization drift')
 root=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e4r-nested-source-materialization')
 if root.exists() or len(c['findings'])!=5 or any(v['status']!='PASS' for v in c['findings']):raise ValueError('finding drift')
 d=c['decision'];closed=['E4R_retry_authorized','archive_open_or_metadata_reinspection_authorized','derived_root_or_receipt_root_creation_authorized','source_text_read_or_excerpt_authorized','E2R_or_E3R_mutation_authorized','network_package_build_execution_or_measurement_authorized','kernel_bound_candidate_equivalence_or_science_authorized']
 if any(d[k] for k in closed) or d['scientific_authority']!='NONE' or not all(c['future_design_requirements'].values()):raise ValueError('authority reopened')
 if r['parent_commit']!=P or r['disposition']!=d['disposition'] or r['next_gate']!=d['only_allowed_next_gate'] or r['finding_count']!=5 or r['finding_pass_count']!=5 or r['scientific_authority']!='NONE':raise ValueError('record drift')
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('digest drift')
 return {'next_gate':d['only_allowed_next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
