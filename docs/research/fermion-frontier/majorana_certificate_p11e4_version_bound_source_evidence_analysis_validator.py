#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];C=HERE/'majorana_certificate_p11e4_version_bound_source_evidence_analysis_contract.json';R=HERE/'majorana_certificate_p11e4_version_bound_source_evidence_analysis_record.json';P='9b0240dc8123cad04e211f6dbc2a9cdca60a42c7';G='docs/research/fermion-frontier/majorana_certificate_p11_g13_post_source_inspection_governance_record.json'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.run(['git',*a],cwd=REPO,check=True,capture_output=True).stdout
def verify():
 c=json.loads(C.read_bytes());b=R.read_bytes();r=json.loads(b)
 if b!=canon(r) or git('rev-parse','HEAD').decode().strip()!=P:raise ValueError('lifecycle drift')
 raw=git('show',f'{P}:{G}');g=json.loads(raw);x=c['P11_G13_custody']
 if sha(raw)!=x['record_raw_sha256'] or g['disposition']!=x['expected_disposition'] or g['next_gate']!=x['expected_next_gate']:raise ValueError('G13 custody drift')
 if c['current_authority']['additional_source_reading_authorized'] or c['current_authority']['kernel_bound_or_candidate_derivation_authorized']:raise ValueError('authority reopened')
 e=c['future_evidence_admission']
 if e['context_window_lines_each_side']!=20 or e['maximum_excerpt_bytes']!=8192 or e['maximum_admitted_excerpts_total']!=30:raise ValueError('evidence bound drift')
 if len(c['analysis_tracks'])!=4 or not c['interpretation_rules']['observed_text_must_be_separate_from_interpretation']:raise ValueError('analysis scope drift')
 if r['contract_raw_sha256']!=sha(C.read_bytes()) or r['contract_canonical_sha256']!=sha(canon(c)):raise ValueError('digest drift')
 return {'next_gate':c['only_allowed_next_gate'],'track_count':4,'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
