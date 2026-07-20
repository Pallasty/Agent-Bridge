#!/usr/bin/env python3
"""P11-E3R wrapper adding confined-link graph validation to the E3 runner."""
from __future__ import annotations
import importlib.util,os,stat,sys,tarfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
def load_module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);assert spec and spec.loader
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
BASE=load_module('p11e3_base',HERE/'majorana_certificate_p11e3_source_inspection_runner.py')
POLICY=load_module('p11e3r_policy',HERE/'majorana_certificate_p11e3r_confined_link_materialization_validator.py')
BASE.ROOT=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e3r-source-inspection')

def archive_graph(path:Path):
 entries=set();links={}
 if not tarfile.is_tarfile(path):return entries,links
 with tarfile.open(path,'r:*') as stream:
  for member in stream:
   name=member.name.rstrip('/')
   if not BASE.safe_rel(name):raise ValueError(f'unsafe archive path: {path.name}:{name}')
   if member.islnk() or not (member.isfile() or member.isdir() or member.issym()):raise ValueError(f'forbidden archive type: {path.name}:{name}')
   if member.mode&(stat.S_ISUID|stat.S_ISGID):raise ValueError(f'privileged archive member: {path.name}:{name}')
   if member.issym():
    POLICY.confined_target(name,member.linkname);links[name]=member.linkname
   else:entries.add(name)
 POLICY.verify_graph(entries,links)
 return entries,links

def preflight_graphs():
 graphs={}
 for package,version in BASE.PACKAGES.items():
  package_graph=[]
  for path in sorted((BASE.CUSTODY/'accepted'/f'{package}={version}').iterdir()):
   if path.name.endswith(('.tar.gz','.tar.xz','.debian.tar.xz')):
    entries,links=archive_graph(path);package_graph.append({'archive':path.name,'entry_count':len(entries),'links':links})
  graphs[package]=package_graph
 return graphs

def scan_tree(root:Path):
 rows=[];entries=set();links={};resolved_root=root.resolve()
 for path in sorted(root.rglob('*'),key=lambda p:str(p.relative_to(root))):
  rel=str(path.relative_to(root));st=path.lstat()
  if path.is_symlink():
   target=os.readlink(path);POLICY.confined_target('pkg/'+rel,target);links['pkg/'+rel]=target
   resolved=path.resolve(strict=True)
   if resolved_root not in (resolved,*resolved.parents):raise ValueError(f'post-extraction link escape: {rel}')
   rows.append({'relative_path':rel,'mode':stat.S_IMODE(st.st_mode),'type':'symlink','target':target});continue
  if stat.S_ISREG(st.st_mode):
   if st.st_nlink!=1:raise ValueError(f'hardlinked file: {rel}')
   row={'relative_path':rel,'mode':stat.S_IMODE(st.st_mode),'type':'file','size_bytes':st.st_size,'sha256':BASE.digest(path)['sha256']};entries.add('pkg/'+rel)
  elif stat.S_ISDIR(st.st_mode):row={'relative_path':rel,'mode':stat.S_IMODE(st.st_mode),'type':'directory','size_bytes':st.st_size};entries.add('pkg/'+rel)
  else:raise ValueError(f'forbidden materialized type: {rel}')
  if st.st_mode&(stat.S_ISUID|stat.S_ISGID):raise ValueError(f'privileged materialized entry: {rel}')
  rows.append(row)
 POLICY.verify_graph(entries,links)
 return rows

def main():
 graphs=preflight_graphs()
 BASE.precheck_tar=lambda path:None
 BASE.scan_tree=scan_tree
 code=BASE.main()
 if (BASE.ROOT/'receipts/state.json').exists():
  state=BASE.json.loads((BASE.ROOT/'receipts/state.json').read_bytes());state['pre_extraction_link_graphs']=graphs;(BASE.ROOT/'receipts/state.json').write_bytes(BASE.canon(state))
 return code
if __name__=='__main__':raise SystemExit(main())
