#!/usr/bin/env python3
"""Offline verifier for the fail-closed P11-E3 result."""
import hashlib,json,sys
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent;ROOT=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e3-source-inspection');MANIFEST=HERE/'majorana_certificate_p11e3_source_inspection_manifest.json';REPORT=HERE/'majorana_certificate_p11e3_source_inspection_report.json'
def canon(x:Any)->bytes:return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def load(p:Path):
 b=p.read_bytes();v=json.loads(b)
 if b!=canon(v):raise ValueError('noncanonical JSON')
 return v
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
 m,r,s=load(MANIFEST),load(REPORT),load(ROOT/'receipts/state.json')
 if s['outcome']!='CLOSED_MATERIALIZATION_OR_READ_FAILURE' or s['packages'] or s['commands']:raise ValueError('state drift')
 if s['error']!='unsafe archive member: linux_7.0.0.orig.tar.gz:linux-7.0/Documentation/Changes':raise ValueError('failure identity drift')
 if sha(ROOT/'receipts/state.json')!=m['state_sha256'] or m['materialized_tree_count']!=0:raise ValueError('manifest drift')
 if any((ROOT/'trees').iterdir()) or r['source_text_read'] or r['bounded_read_completed']:raise ValueError('closed boundary violated')
 return {'outcome':s['outcome'],'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
