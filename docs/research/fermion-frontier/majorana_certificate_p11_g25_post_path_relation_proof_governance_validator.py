#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent
C=H/'majorana_certificate_p11_g25_post_path_relation_proof_governance_contract.json'
R=H/'majorana_certificate_p11_g25_post_path_relation_proof_governance_record.json'
P='aaa2d5bf9826076058d56e4916ba3053a2dd4cfe';BASE='docs/research/fermion-frontier/'
def verify():
 c=json.loads(C.read_bytes());r=json.loads(R.read_bytes());head=subprocess.run(['git','rev-parse','HEAD'],cwd=H.parents[2],check=True,capture_output=True,text=True).stdout.strip();cust=c['E4V_result_custody'];raw=subprocess.run(['git','show',f"{P}:{BASE}{cust['result_relative_path']}"],cwd=H.parents[2],check=True,capture_output=True).stdout;e=json.loads(raw)
 if head!=P or hashlib.sha256(raw).hexdigest()!=cust['result_raw_sha256'] or e['disposition']!=cust['expected_disposition'] or e['success_receipt_raw_sha256']!=cust['expected_success_receipt_raw_sha256']:raise ValueError('custody')
 if e['headers_total']!=149865 or e['eligible_members']!=54 or e['relation_counts']!={'exact_byte_equal':0,'single_leading_dot_slash_equal':0,'posix_lexically_normalized_equal':0,'unsafe_or_unproven_relation':54} or e['payload_bytes']!=0 or e['source_text_read'] or e['scientific_authority']!='NONE':raise ValueError('result')
 if len(c['findings'])!=6 or any(x['status']!='PASS' for x in c['findings']):raise ValueError('findings')
 d=c['decision']
 if d['disposition']!='CLOSE_P11_PAX_PATH_MAPPING_AS_UNPROVEN' or any(d[k] for k in ('retry_or_policy_relaxation_authorized','materialization_authorized','source_payload_or_semantic_read_authorized','new_follow_on_contract_authorized')) or d['scientific_authority']!='NONE' or d['next_route']!='TERMINATE_P11_PAX_PATH_MAPPING_ROUTE':raise ValueError('boundary')
 if r!={'disposition':d['disposition'],'finding_count':6,'finding_pass_count':6,'next_route':d['next_route'],'parent_commit':P,'schema_version':1,'scientific_authority':'NONE'}:raise ValueError('record')
 return {'status':'PASS','next_route':d['next_route']}
if __name__=='__main__':
 try:print(json.dumps(verify(),sort_keys=True,separators=(',',':')))
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
