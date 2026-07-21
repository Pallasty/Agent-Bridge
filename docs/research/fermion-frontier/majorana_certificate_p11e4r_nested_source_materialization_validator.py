#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
C=HERE/'majorana_certificate_p11e4r_nested_source_materialization_contract.json';R=HERE/'majorana_certificate_p11e4r_nested_source_materialization_record.json'
P='84bfdff5b227439542f9933848ef7fb76ca674c7';BASE='docs/research/fermion-frontier/'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b)
 if b.rstrip(b'\n')!=canon(r) or git('rev-parse','HEAD').decode().strip()!=P:raise ValueError('lifecycle drift')
 x=c['P11_G15_custody'];raw=git('show',f"{P}:{BASE}{x['record_relative_path']}");g=json.loads(raw);gc=git('show',f"{P}:{BASE}{x['contract_relative_path']}")
 if c['required_direct_parent_commit']!=P or sha(raw)!=x['record_raw_sha256'] or sha(gc)!=x['contract_raw_sha256'] or g['disposition']!=x['expected_disposition'] or g['next_gate']!=x['expected_next_gate'] or g['parent_commit']!='aa1d21de79b0abee53acf0032526103dfab38b71' or g['finding_count']!=x['expected_finding_count'] or g['finding_pass_count']!=x['expected_finding_count'] or g['scientific_authority']!='NONE':raise ValueError('G15 custody drift')
 e=c['E4_failure_custody'];eraw=git('show',f"{P}:{BASE}{e['result_relative_path']}");failure=json.loads(eraw)
 if sha(eraw)!=e['result_raw_sha256'] or failure['disposition']!=e['expected_disposition'] or failure['source_text_read'] is not e['expected_source_text_read'] or failure['excerpt_count']!=e['expected_excerpt_count']:raise ValueError('E4 failure custody drift')
 q=c['E3R_repository_custody'];report_raw=git('show',f"{P}:{BASE}{q['report_relative_path']}");manifest_raw=git('show',f"{P}:{BASE}{q['manifest_relative_path']}")
 if sha(report_raw)!=q['report_raw_sha256'] or sha(manifest_raw)!=q['manifest_raw_sha256'] or json.loads(report_raw)['outcome']!=q['expected_outcome']:raise ValueError('E3R repository custody drift')
 a=c['current_authority']
 if any(v for k,v in a.items() if k!='scientific_authority') or a['scientific_authority']!='NONE':raise ValueError('authority reopened')
 i=c['future_operation_identity'];root=Path(i['immutable_E3R_root']);manifest=root/i['tree_manifest_relative_path'];mb=manifest.read_bytes()
 if sha(mb)!=i['tree_manifest_raw_sha256']:raise ValueError('E3R manifest drift')
 if sha((root/i['E3R_state_relative_path']).read_bytes())!=i['E3R_state_raw_sha256']:raise ValueError('E3R state drift')
 rows=json.loads(mb);matches=[row for row in rows if row.get('relative_path')==i['nested_archive_row']['relative_path']]
 if matches!=[i['nested_archive_row']]:raise ValueError('nested archive manifest row drift')
 expected={'mode':436,'relative_path':'gcc-15.2.0.tar.xz','sha256':'438fd996826b0c82485a29da03a72d71d6e3541a83ec702df4271f6fe025d24e','size_bytes':101056276,'type':'file'}
 if i['nested_archive_row']!=expected:raise ValueError('nested archive identity drift')
 derived=Path(i['new_empty_derived_root']);
 if derived==root or root in derived.parents or derived in root.parents or not i['failed_or_partial_root_reuse_forbidden']:raise ValueError('derived-root isolation drift')
 p=c['future_preflight_policy'];m=c['future_materialization_policy'];s=c['future_result_scope'];limits=c['resource_limits']
 if not all(p.values()) or not all(m.values()) or not all(s.values()) or not all(c['future_receipt_requirements'].values()):raise ValueError('safety policy drift')
 if limits['maximum_nesting_layers_materialized']!=1 or limits['recursive_archive_discovery_or_extraction'] is not False or limits['maximum_member_count']>200000 or limits['maximum_total_regular_file_bytes']>4294967296 or limits['maximum_expansion_ratio']>64:raise ValueError('resource policy drift')
 if not c['future_operation_requires_independent_authorization'] or c['only_allowed_next_gate']!='P11-G16-NESTED-SOURCE-MATERIALIZATION-AUTHORIZATION-V1':raise ValueError('authorization boundary drift')
 expected_paths=['docs/research/fermion-frontier/ARTIFACTS.md','docs/research/fermion-frontier/PROGRESS.md','docs/research/fermion-frontier/majorana_certificate_p11e4r_nested_source_materialization_contract.json','docs/research/fermion-frontier/majorana_certificate_p11e4r_nested_source_materialization_record.json','docs/research/fermion-frontier/majorana_certificate_p11e4r_nested_source_materialization_validator.py','docs/research/fermion-frontier/test_majorana_certificate_p11e4r_nested_source_materialization.py']
 if c['lifecycle']['exact_changed_paths']!=expected_paths:raise ValueError('changed-path policy drift')
 if r['parent_commit']!=P or r['disposition']!='NESTED_SOURCE_MATERIALIZATION_CONTRACT_ESTABLISHED_AWAITING_G16_AUTHORIZATION' or r['next_gate']!=c['only_allowed_next_gate'] or r['scientific_authority']!='NONE':raise ValueError('record boundary drift')
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('digest drift')
 return {'archive_sha256':i['nested_archive_row']['sha256'],'next_gate':c['only_allowed_next_gate'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
