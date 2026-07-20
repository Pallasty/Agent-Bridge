#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
P=Path(__file__).resolve().parents[2]/'scripts/eval/fixtures/engram_g14_wasi_g2i_recovery_preflight_v0.json'
def need(v,m):
 if not v: raise AssertionError(m)
def main():
 c=json.loads(P.read_text()); need(c['gate']=='G2I_TOOLCHAIN_RECOVERY_AUTHORIZATION_PREFLIGHT','gate')
 need(c['predecessor']['g2h_fail_closed_post']==4798 and c['predecessor']['claim_post']==4803,'chain')
 need(all(v is False for v in c['current_actions'].values()),'current action occurred')
 need(len(c['future_recovery_required'])==9 and 'selector_bypass' in c['future_recovery_required'],'recovery prerequisites')
 need(len(c['abort_conditions'])==5 and 'rustup_selector_reentry' in c['abort_conditions'],'abort conditions')
 need(all(v is False for v in c['authority'].values()),'authority expanded')
 print('PASS G2I recovery preflight: static only; no automatic recovery')
if __name__=='__main__':
 try: main()
 except (AssertionError,KeyError,OSError,json.JSONDecodeError) as e: print(f'FAIL G2I: {e}',file=sys.stderr); raise SystemExit(1)
