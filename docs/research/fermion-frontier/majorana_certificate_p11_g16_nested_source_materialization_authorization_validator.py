#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
C=HERE/'majorana_certificate_p11_g16_nested_source_materialization_authorization_contract.json';R=HERE/'majorana_certificate_p11_g16_nested_source_materialization_authorization_record.json'
P='214a8442141c4f3d0cc49fb1b8ed8bf35814c8e7';BASE='docs/research/fermion-frontier/'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b)
 if b.rstrip(b'\n')!=canon(r) or git('rev-parse','HEAD').decode().strip()!=P or c['required_direct_parent_commit']!=P:raise ValueError('lifecycle drift')
 x=c['E4R_custody'];raw=git('show',f"{P}:{BASE}{x['record_relative_path']}");e=json.loads(raw);contract=git('show',f"{P}:{BASE}{x['contract_relative_path']}");ec=json.loads(contract)
 if sha(raw)!=x['record_raw_sha256'] or sha(contract)!=x['contract_raw_sha256'] or e['disposition']!=x['expected_disposition'] or e['next_gate']!=x['expected_next_gate'] or e['parent_commit']!='84bfdff5b227439542f9933848ef7fb76ca674c7' or e['scientific_authority']!='NONE':raise ValueError('E4R custody drift')
 if any(v for k,v in ec['current_authority'].items() if k!='scientific_authority') or ec['current_authority']['scientific_authority']!='NONE':raise ValueError('E4R authority drift')
 identity=ec['future_operation_identity'];root=Path(identity['immutable_E3R_root']);manifest=(root/identity['tree_manifest_relative_path']).read_bytes();state=(root/identity['E3R_state_relative_path']).read_bytes()
 if sha(manifest)!=identity['tree_manifest_raw_sha256'] or sha(state)!=identity['E3R_state_raw_sha256']:raise ValueError('E3R external custody drift')
 row=identity['nested_archive_row'];matches=[v for v in json.loads(manifest) if v.get('relative_path')==row['relative_path']]
 if matches!=[row] or row!={'mode':436,'relative_path':'gcc-15.2.0.tar.xz','sha256':'438fd996826b0c82485a29da03a72d71d6e3541a83ec702df4271f6fe025d24e','size_bytes':101056276,'type':'file'}:raise ValueError('nested archive identity drift')
 derived=Path(identity['new_empty_derived_root'])
 if derived.exists() or derived.is_symlink() or derived.parent.resolve()!=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana').resolve():raise ValueError('derived root precondition drift')
 if len(c['readiness_review'])!=7 or any(v['status']!='PASS' for v in c['readiness_review']):raise ValueError('readiness failure')
 d=c['decision'];must_true=['read_only_E3R_nested_archive_access_authorized','new_E4R_derived_root_and_receipt_creation_authorized','byte_level_archive_parse_copy_and_hash_authorized'];must_false=['source_text_semantic_read_or_excerpt_authorized','E4_analysis_retry_authorized','E2R_or_E3R_mutation_authorized','network_package_build_execution_or_measurement_authorized','kernel_bound_candidate_equivalence_or_science_authorized']
 if not all(d[k] for k in must_true) or any(d[k] for k in must_false) or d['scientific_authority']!='NONE':raise ValueError('authorization scope drift')
 limits=c['operation_limits']
 if limits['maximum_authorized_runs']!=1 or limits['materialized_nesting_layers']!=1 or limits['recursive_archive_extraction'] or limits['source_analysis_or_excerpt_count']!=0 or limits['maximum_member_count']>200000 or limits['maximum_total_regular_file_bytes']>4294967296 or limits['maximum_expansion_ratio']>64:raise ValueError('operation limits drift')
 if r['parent_commit']!=P or r['disposition']!=d['disposition'] or r['next_gate']!=d['post_run_gate'] or r['readiness_check_count']!=7 or r['readiness_pass_count']!=7 or r['scientific_authority']!='NONE':raise ValueError('record drift')
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('digest drift')
 return {'next_gate':d['post_run_gate'],'readiness_pass_count':7,'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
