#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];C=HERE/'majorana_certificate_p11_g18_archive_metadata_inspection_authorization_contract.json';R=HERE/'majorana_certificate_p11_g18_archive_metadata_inspection_authorization_record.json';P='496de839a3a4f833ff3472f93162b9b0ebcce0ac';BASE='docs/research/fermion-frontier/'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b)
 if b.rstrip(b'\n')!=canon(r) or git('rev-parse','HEAD').decode().strip()!=P or c['required_direct_parent_commit']!=P:raise ValueError('lifecycle drift')
 x=c['E4S_custody'];raw=git('show',f"{P}:{BASE}{x['record_relative_path']}");e=json.loads(raw);ec=git('show',f"{P}:{BASE}{x['contract_relative_path']}")
 if sha(raw)!=x['record_raw_sha256'] or sha(ec)!=x['contract_raw_sha256'] or e['disposition']!=x['expected_disposition'] or e['next_gate']!=x['expected_next_gate'] or e['scientific_authority']!='NONE':raise ValueError('E4S custody drift')
 receipt=Path(json.loads(ec)['future_receipt_identity']['new_empty_receipt_root'])
 if receipt.exists() or receipt.is_symlink():raise ValueError('receipt root drift')
 if len(c['readiness_review'])!=6 or any(v['status']!='PASS' for v in c['readiness_review']):raise ValueError('readiness drift')
 d=c['decision'];yes=['read_only_E3R_archive_header_access_authorized','new_E4S_receipt_root_creation_authorized','append_only_attempt_and_terminal_receipt_creation_authorized'];no=['source_payload_read_extraction_or_materialization_authorized','E4_or_E4R_retry_authorized','E2R_or_E3R_mutation_authorized','network_package_build_execution_or_measurement_authorized','kernel_bound_candidate_equivalence_or_science_authorized']
 if not all(d[k] for k in yes) or any(d[k] for k in no) or d['scientific_authority']!='NONE':raise ValueError('authority drift')
 l=c['operation_limits']
 if l['maximum_authorized_runs']!=1 or l['member_payload_bytes_read']!=0 or l['member_paths_or_link_targets_recorded_verbatim'] or not l['receipt_attempt_before_archive_open'] or not l['exactly_one_terminal_receipt']:raise ValueError('limit drift')
 if r['parent_commit']!=P or r['disposition']!=d['disposition'] or r['next_gate']!=d['post_run_gate'] or r['readiness_check_count']!=6 or r['readiness_pass_count']!=6 or r['scientific_authority']!='NONE' or r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('record drift')
 return {'next_gate':d['post_run_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
