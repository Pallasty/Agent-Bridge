#!/usr/bin/env python3
"""Independent offline verifier for E2R final-path custody."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent
ROOT=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e2r-source-custody')
MANIFEST=HERE/'majorana_certificate_p11e2r_remedial_source_archive_custody_manifest.json';REPORT=HERE/'majorana_certificate_p11e2r_remedial_source_archive_custody_report.json'
EXPECTED={'gcc-15':'15.2.0-16ubuntu1','binutils':'2.46-3ubuntu2','linux':'7.0.0-28.28','linux-signed':'7.0.0-28.28'}
def canon(x:Any)->bytes:return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def load(p:Path):
 b=p.read_bytes();v=json.loads(b)
 if b!=canon(v):raise ValueError(f'noncanonical {p.name}')
 return v
def digest(p:Path):
 h=hashlib.sha256();n=0
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):n+=len(c);h.update(c)
 return n,h.hexdigest()
def verify():
 m,r,s=load(MANIFEST),load(REPORT),load(ROOT/'receipts/state.json')
 out='REMEDIAL_SOURCE_ARCHIVE_CUSTODY_ESTABLISHED_EXACT_FOUR_FRESH_PACKAGE_SET'
 if s['outcome']!='SOURCE_ARCHIVE_CUSTODY_ESTABLISHED_EXACT_FOUR_PACKAGE_SET' or not s['complete_set_custody_established'] or r['outcome']!=out or not r['source_archive_custody_established']:raise ValueError('outcome drift')
 if {p['source_package']:p['source_version'] for p in s['packages']}!=EXPECTED:raise ValueError('identity drift')
 observed=[]
 for p in s['packages']:
  accepted=ROOT/p['accepted_relative_path']
  for row in p['files']:
   final=accepted/row['filename']; size,sha=digest(final)
   if (size,sha)!=(row['size_bytes'],row['sha256']) or not str(row['relative_path']).startswith('accepted/'):raise ValueError('final receipt mismatch')
   observed.append({'relative_path':str(final.relative_to(ROOT)),'sha256':sha,'size_bytes':size})
 if m['accepted_files']!=observed or digest(ROOT/'receipts/state.json')[1]!=m['state_sha256']:raise ValueError('manifest mismatch')
 for p in (ROOT/'receipts/logs').glob('*'):
  b=p.read_bytes()
  if b'/etc/apt' in b or b'Warning' in b or b'warning' in b:raise ValueError('APT warning found')
 return {'accepted_file_count':len(observed),'outcome':out,'status':'PASS'}
if __name__=='__main__':
 try:print(canon(verify()).decode())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
