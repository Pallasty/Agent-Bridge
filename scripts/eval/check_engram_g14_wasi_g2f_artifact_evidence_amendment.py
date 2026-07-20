#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'scripts/eval/fixtures/engram_g14_wasi_g2f_artifact_evidence_amendment_v0.json'
def need(v,m):
    if not v: raise AssertionError(m)
def main():
    c=json.loads(P.read_text()); a=c['authority']; r=c['raw_rlib_sha']
    need(c['gate']=='G2F_ARTIFACT_EVIDENCE_AMENDMENT','gate')
    need(c['predecessor']['owner_confirmation_post']==4783 and c['predecessor']['g2g_independent_failure_post']==4780 and c['predecessor']['g2g_fail_closed_post']==4781,'authority chain')
    need(r['required'] is True and r['cross_worktree_reproducibility_required'] is False and r['meaning']=='per_build_observation_only','raw digest semantics')
    need(len(c['required_acceptance_binding'])==9 and 'independent_compile_success' in c['required_acceptance_binding'],'binding')
    need(a=={'build_authorized':True,'run_authorized':False,'network_authorized':False,'dependency_authorized':False,'component_or_linker_authorized':False,'runtime_or_g1_4_authorized':False},'authority widened')
    print('PASS G2F amendment: raw artifact hash is observation only; authority unchanged')
if __name__=='__main__':
    try: main()
    except (AssertionError,KeyError,OSError,json.JSONDecodeError) as e: print(f'FAIL G2F amendment: {e}',file=sys.stderr); raise SystemExit(1)
