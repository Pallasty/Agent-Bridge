#!/usr/bin/env python3
import hashlib,json,subprocess,sys
from pathlib import Path

H=Path(__file__).resolve().parent;ROOT=H.parents[2]
P11_A='71967df1b328cc40ad28c555f0c6ff9152f87774';TIP='056fd4d13fb0d29b296dd3f21445490090d4dde3';BASE='docs/research/fermion-frontier/'
EDGES=[
 ('0d875167aa289de0e2eb84f1beb5195335950e50','214a8442'),('c16223ef','0d875167'),('ddd29e19','c16223ef'),('496de839','ddd29e19'),('03096a3d','496de839'),('768be532','03096a3d'),('4014db37','768be532'),('fd0f111c','4014db37'),('5667fc19','fd0f111c'),('ee085a02','5667fc19'),('16705672','ee085a02'),('0ae6f115','16705672'),('be6cef15','0ae6f115'),('ebe4abdb','be6cef15'),('df5c3058','ebe4abdb'),('bf19ad9d','df5c3058'),('6dc3d453','bf19ad9d'),('e42b3905','6dc3d453'),('373957f3','e42b3905'),('aaa2d5bf','373957f3'),('056fd4d1','aaa2d5bf')]
E4U=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e4u-pax-value-shape-classification/receipts/success.json')
E4V=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e4v-path-relation-proof/receipts/success.json')
def git(*args): return subprocess.run(['git',*args],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
def raw(commit,path): return subprocess.run(['git','show',f'{commit}:{BASE}{path}'],cwd=ROOT,check=True,capture_output=True).stdout
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def verify():
    git('merge-base','--is-ancestor',P11_A,TIP);git('merge-base','--is-ancestor',TIP,'HEAD')
    for child,parent in EDGES:
        if git('rev-parse',f'{child}^')!=git('rev-parse',parent): raise ValueError(f'parent:{child}')
    if digest(E4U)!='e61e46c0d72c1feab4736c0b76255ea8d6f0a918028f5e42d29b72e957570a5d' or digest(E4V)!='5b7e863d7f8fbe33f09aaea2eec2f39e8cdf37bc580d8084727eac8442fcc42a': raise ValueError('receipt')
    e4u=json.loads(raw('bf19ad9d','majorana_certificate_p11e4u_pax_value_shape_result.json'))
    g25=json.loads(raw(TIP,'majorana_certificate_p11_g25_post_path_relation_proof_governance_contract.json'))
    result_raw=raw('aaa2d5bf','majorana_certificate_p11e4v_path_relation_proof_result.json');e4v=json.loads(result_raw)
    if e4u['shape_counts']['path']!={'equal_name':621,'missing':149190,'other_relation':54}: raise ValueError('e4u')
    if hashlib.sha256(result_raw).hexdigest()!=g25['E4V_result_custody']['result_raw_sha256'] or e4v['relation_counts']!={'exact_byte_equal':0,'single_leading_dot_slash_equal':0,'posix_lexically_normalized_equal':0,'unsafe_or_unproven_relation':54}: raise ValueError('e4v')
    d=g25['decision']
    if d['disposition']!='CLOSE_P11_PAX_PATH_MAPPING_AS_UNPROVEN' or any(d[k] for k in ('retry_or_policy_relaxation_authorized','materialization_authorized','source_payload_or_semantic_read_authorized','new_follow_on_contract_authorized')) or d['next_route']!='TERMINATE_P11_PAX_PATH_MAPPING_ROUTE': raise ValueError('g25')
    return {'status':'PASS','pax_route':d['next_route']}
if __name__=='__main__':
    try: print(json.dumps(verify(),sort_keys=True,separators=(',',':')))
    except Exception as e: print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
