#!/usr/bin/env python3
"""One-shot P11-E3 safe materialization and bounded-read runner."""
from __future__ import annotations
import hashlib,json,os,stat,subprocess,sys,tarfile
from pathlib import Path
from typing import Any
ROOT=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e3-source-inspection')
CUSTODY=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e2r-source-custody')
HERE=Path(__file__).resolve().parent
MANIFEST=HERE/'majorana_certificate_p11e2r_remedial_source_archive_custody_manifest.json'
PACKAGES={'gcc-15':'15.2.0-16ubuntu1','binutils':'2.46-3ubuntu2','linux':'7.0.0-28.28','linux-signed':'7.0.0-28.28'}
QUERIES={'gcc-15':['link_command_spec','startfile','endfile'],'binutils':['PHDRS','NOLOAD','p_align'],'linux':['load_elf_binary','vm_brk_flags','memory.peak'],'linux-signed':['linux-source','Source: linux']}
def canon(x:Any)->bytes:return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def digest(p:Path):
 h=hashlib.sha256();n=0
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):n+=len(c);h.update(c)
 return {'size_bytes':n,'sha256':h.hexdigest()}
def safe_rel(name:str)->bool:
 p=Path(name);return bool(name) and not p.is_absolute() and '..' not in p.parts and '\x00' not in name and all(ord(c)>=32 for c in name)
def precheck_tar(p:Path)->None:
 if not tarfile.is_tarfile(p):return
 with tarfile.open(p,'r:*') as t:
  seen=set()
  for m in t:
   folded=m.name.casefold()
   if not safe_rel(m.name) or folded in seen or not (m.isfile() or m.isdir()):raise ValueError(f'unsafe archive member: {p.name}:{m.name}')
   if m.mode & (stat.S_ISUID|stat.S_ISGID):raise ValueError(f'privileged archive member: {p.name}:{m.name}')
   seen.add(folded)
def scan_tree(root:Path):
 rows=[]
 for p in sorted(root.rglob('*'),key=lambda x:str(x.relative_to(root))):
  st=p.lstat();rel=str(p.relative_to(root))
  if p.is_symlink() or st.st_nlink!=1 or not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)):raise ValueError(f'unsafe materialized entry: {rel}')
  row={'relative_path':rel,'mode':stat.S_IMODE(st.st_mode),'type':'directory' if p.is_dir() else 'file','size_bytes':st.st_size}
  if p.is_file():row['sha256']=digest(p)['sha256']
  rows.append(row)
 return rows
def bounded_hits(package:str,root:Path):
 hits=[]
 for p in sorted(root.rglob('*')):
  if len(hits)>=20:break
  if not p.is_file() or p.stat().st_size>2_000_000:continue
  try:lines=p.read_text(encoding='utf-8').splitlines()
  except UnicodeDecodeError:continue
  for number,line in enumerate(lines,1):
   for query in QUERIES[package]:
    if query in line:
     raw=line.encode('utf-8');hits.append({'query':query,'relative_path':str(p.relative_to(root)),'line_number':number,'line_size_bytes':len(raw),'line_sha256':hashlib.sha256(raw).hexdigest()})
     if len(hits)>=20:break
   if len(hits)>=20:break
 return hits
def main()->int:
 state={'schema_version':1,'commands':[],'packages':[],'outcome':'CLOSED_MATERIALIZATION_OR_READ_FAILURE'}
 try:
  if ROOT.exists() or ROOT.is_symlink():raise ValueError('derived root must be new')
  ROOT.mkdir(parents=True,mode=0o700);(ROOT/'trees').mkdir();(ROOT/'receipts').mkdir();(ROOT/'logs').mkdir()
  manifest=json.loads(MANIFEST.read_bytes())
  for row in manifest['accepted_files']:
   p=CUSTODY/row['relative_path'];got=digest(p)
   if got!={'size_bytes':row['size_bytes'],'sha256':row['sha256']}:raise ValueError(f'custody hash mismatch: {row["relative_path"]}')
   if p.name.endswith(('.tar.gz','.tar.xz','.debian.tar.xz')):precheck_tar(p)
  env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
  for package,version in PACKAGES.items():
   base=CUSTODY/'accepted'/f'{package}={version}';dsc=next(base.glob('*.dsc'));target=ROOT/'trees'/f'{package}={version}'
   argv=['/usr/bin/dpkg-source','-x','--no-check',str(dsc),str(target)]
   result=subprocess.run(argv,cwd=ROOT,env=env,capture_output=True,check=False)
   (ROOT/'logs'/f'{package}.stdout').write_bytes(result.stdout);(ROOT/'logs'/f'{package}.stderr').write_bytes(result.stderr)
   command={'argv':argv,'returncode':result.returncode,'stdout':digest(ROOT/'logs'/f'{package}.stdout'),'stderr':digest(ROOT/'logs'/f'{package}.stderr')};state['commands'].append(command)
   if result.returncode!=0:raise ValueError(f'dpkg-source failed: {package}')
   tree=scan_tree(target);hits=bounded_hits(package,target);receipt={'source_package':package,'source_version':version,'tree_entry_count':len(tree),'tree_manifest_sha256':hashlib.sha256(canon(tree)).hexdigest(),'bounded_hits':hits}
   (ROOT/'receipts'/f'{package}.tree.json').write_bytes(canon(tree));(ROOT/'receipts'/f'{package}.json').write_bytes(canon(receipt));state['packages'].append(receipt)
  state['outcome']='SOURCE_MATERIALIZATION_AND_BOUNDED_READ_COMPLETED'
 except Exception as e:state['error']=str(e)
 (ROOT/'receipts/state.json').write_bytes(canon(state));print(canon({'outcome':state['outcome'],'completed_packages':len(state['packages']),'error':state.get('error')}).decode());return 0
if __name__=='__main__':raise SystemExit(main())
