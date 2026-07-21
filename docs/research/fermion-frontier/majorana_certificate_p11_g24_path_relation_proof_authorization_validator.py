#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path

H=Path(__file__).resolve().parent
A=H/'majorana_certificate_p11_g24_path_relation_proof_authorization.json'
R=H/'majorana_certificate_p11_g24_path_relation_proof_authorization_record.json'
P='e42b39050d417c02427c9483388d537ba9c96ed9'
BASE='docs/research/fermion-frontier/'
def sha(b): return hashlib.sha256(b).hexdigest()
def verify():
    a=json.loads(A.read_bytes());r=json.loads(R.read_bytes())
    head=subprocess.run(['git','rev-parse','HEAD'],cwd=H.parents[2],check=True,capture_output=True,text=True).stdout.strip()
    raw=subprocess.run(['git','show',f"{P}:{BASE}{a['E4V_contract_relative_path']}"],cwd=H.parents[2],check=True,capture_output=True).stdout
    if head!=P or a['required_direct_parent_commit']!=P or sha(raw)!=a['E4V_contract_raw_sha256']: raise ValueError('custody')
    c=json.loads(raw);d=a['decision'];l=a['limits']
    if c['contract_role']!='nonexecuting_zero_payload_path_relation_proof' or c['future_operation_requires_independent_authorization'] is not True: raise ValueError('contract')
    if d['disposition']!='AUTHORIZE_ONE_P11_E4V_PATH_RELATION_PROOF_RUN' or not d['archive_header_iteration_authorized'] or not d['receipt_root_creation_authorized'] or any(d[k] for k in ('payload_read_extraction_materialization_authorized','source_text_semantic_read_authorized','policy_relaxation_authorized')) or d['scientific_authority']!='NONE': raise ValueError('authority')
    if l!={'maximum_runs':1,'payload_bytes':0,'eligible_members':54,'maximum_headers':200000,'no_verbatim_path_or_member_name':True,'no_per_member_identifier_or_value_hash':True,'aggregate_relation_classes_only':True,'archive_must_match_E4V_contract':True}: raise ValueError('limits')
    if r!={'disposition':d['disposition'],'next_gate':d['post_run_gate'],'parent_commit':P,'readiness_pass_count':7,'schema_version':1,'scientific_authority':'NONE'}: raise ValueError('record')
    return {'status':'PASS','next_gate':d['post_run_gate']}
if __name__=='__main__':
    try: print(json.dumps(verify(),sort_keys=True,separators=(',',':')))
    except Exception as e: print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
