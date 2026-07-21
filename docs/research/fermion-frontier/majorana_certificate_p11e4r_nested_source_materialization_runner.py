#!/usr/bin/env python3
"""The single G16-authorized byte-level E4R GCC inner-archive materialization."""
from __future__ import annotations
import hashlib,json,os,shutil,stat,sys,tarfile,unicodedata,uuid
from pathlib import Path, PurePosixPath

HERE=Path(__file__).resolve().parent
CONTRACT=HERE/'majorana_certificate_p11e4r_nested_source_materialization_contract.json'
EVIDENCE=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e3r-source-inspection')
PARENT=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana')
AUTH='0d875167aa289de0e2eb84f1beb5195335950e50'

def canon(x): return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(data): return hashlib.sha256(data).hexdigest()
def hash_fd(fd):
 h=hashlib.sha256();os.lseek(fd,0,os.SEEK_SET)
 while True:
  b=os.read(fd,1024*1024)
  if not b: break
  h.update(b)
 os.lseek(fd,0,os.SEEK_SET);return h.hexdigest()
def norm_member(name):
 if not isinstance(name,str) or not name or '\x00' in name or unicodedata.normalize('NFC',name)!=name: raise ValueError('invalid member name')
 p=PurePosixPath(name.rstrip('/'))
 if p.is_absolute() or not p.parts or any(x in ('','.', '..') or any(ord(c)<32 for c in x) for x in p.parts): raise ValueError('unsafe member path')
 return p.parts
def norm_target(parent,target):
 if not isinstance(target,str) or not target or '\x00' in target or unicodedata.normalize('NFC',target)!=target: raise ValueError('invalid link target')
 p=PurePosixPath(target)
 if p.is_absolute() or any(any(ord(c)<32 for c in x) for x in p.parts): raise ValueError('unsafe link target')
 out=list(parent)
 for x in p.parts:
  if x in ('','.'): continue
  if x=='..':
   if not out: raise ValueError('link target escape')
   out.pop()
  else: out.append(x)
 return tuple(out)
def fd_for(rootfd,parts,create=True):
 fd=os.dup(rootfd)
 try:
  for part in parts:
   try: os.mkdir(part,0o700,dir_fd=fd)
   except FileExistsError: pass
   st=os.stat(part,dir_fd=fd,follow_symlinks=False)
   if not stat.S_ISDIR(st.st_mode): raise ValueError('non-directory parent')
   nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
  return fd
 except: os.close(fd);raise
def scan(root):
 rows=[];links={}
 for p in sorted(root.rglob('*'),key=lambda x:str(x.relative_to(root))):
  rel=str(p.relative_to(root));st=p.lstat()
  if p.is_symlink():
   target=os.readlink(p);links[rel]=target;rows.append({'relative_path':rel,'mode':stat.S_IMODE(st.st_mode),'type':'symlink','target':target})
  elif p.is_dir(): rows.append({'relative_path':rel,'mode':stat.S_IMODE(st.st_mode),'size_bytes':st.st_size,'type':'directory'})
  elif p.is_file():
   h=hashlib.sha256()
   with p.open('rb') as f:
    for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
   rows.append({'relative_path':rel,'mode':stat.S_IMODE(st.st_mode),'sha256':h.hexdigest(),'size_bytes':st.st_size,'type':'file'})
  else: raise ValueError('forbidden post-materialization type')
 return rows,links
def main():
 c=json.loads(CONTRACT.read_bytes());i=c['future_operation_identity'];limits=c['resource_limits'];final=Path(i['new_empty_derived_root'])
 if final.exists() or final.is_symlink() or PARENT.resolve()!=PARENT or final.parent!=PARENT: raise ValueError('derived root precondition failed')
 manifest=(EVIDENCE/i['tree_manifest_relative_path']).read_bytes();state=(EVIDENCE/i['E3R_state_relative_path']).read_bytes()
 if sha(manifest)!=i['tree_manifest_raw_sha256'] or sha(state)!=i['E3R_state_raw_sha256']:raise ValueError('external receipt drift')
 rows=json.loads(manifest);row=i['nested_archive_row'];matches=[x for x in rows if x.get('relative_path')==row['relative_path']]
 if matches!=[row]:raise ValueError('archive manifest row drift')
 archive=EVIDENCE/'trees'/i['source_tree_identity']/row['relative_path'];fd=os.open(archive,os.O_RDONLY|os.O_NOFOLLOW)
 staging=None
 try:
  before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=row['size_bytes'] or hash_fd(fd)!=row['sha256']:raise ValueError('archive identity failure')
  with os.fdopen(os.dup(fd),'rb',closefd=True) as f:
   with tarfile.open(fileobj=f,mode='r:xz') as t: members=t.getmembers()
  if not members or len(members)>limits['maximum_member_count']:raise ValueError('member-count limit')
  entries={};links={};link_text={};total=0;top=None;casefold=set()
  for m in members:
   if m.pax_headers or getattr(m,'sparse',None):raise ValueError('PAX or sparse member')
   parts=norm_member(m.name);top=parts[0] if top is None else top
   if parts[0]!=top:raise ValueError('multiple top-level roots')
   rel=parts[1:]
   if not rel:
    if not m.isdir():raise ValueError('top root is not a directory')
    continue
   key='/'.join(rel);fold=key.casefold()
   if key in entries or fold in casefold:raise ValueError('path collision')
   casefold.add(fold)
   if m.isreg():
    if m.size>limits['maximum_single_regular_file_bytes']:raise ValueError('single-file limit')
    total+=m.size;kind='file'
   elif m.isdir():kind='directory'
   elif m.issym():kind='symlink';links[key]=norm_target(rel[:-1],m.linkname);link_text[key]=m.linkname
   else:raise ValueError('forbidden archive member type')
   if m.mode&(stat.S_ISUID|stat.S_ISGID) or len(key.encode())>limits['maximum_normalized_path_bytes'] or len(rel)>limits['maximum_path_components']:raise ValueError('member policy failure')
   entries[key]=(m,kind,rel)
  if top!=i['expected_single_top_level_directory'] or total>limits['maximum_total_regular_file_bytes'] or total>before.st_size*limits['maximum_expansion_ratio']:raise ValueError('resource or root policy failure')
  for key,(_,kind,rel) in entries.items():
   for n in range(1,len(rel)):
    parent='/'.join(rel[:n])
    if parent in entries and entries[parent][1]!='directory':raise ValueError('non-directory parent graph')
   if kind=='symlink':
    target='/'.join(links[key])
    seen=set();hops=0
    while target in links:
     if target in seen or hops>=limits['maximum_symlink_chain_hops']:raise ValueError('link cycle')
     seen.add(target);target='/'.join(norm_target(tuple(target.split('/')[:-1]),links[target]));hops+=1
    if target not in entries or entries[target][1] not in ('file','directory'):raise ValueError('dangling link')
  parentfd=os.open(PARENT,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);name='.'+final.name+'.staging-'+uuid.uuid4().hex
  os.mkdir(name,0o700,dir_fd=parentfd);staging=PARENT/name;rootfd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parentfd)
  try:
   os.mkdir(top,0o700,dir_fd=rootfd);treefd=os.open(top,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=rootfd)
   with os.fdopen(os.dup(fd),'rb',closefd=True) as f:
    with tarfile.open(fileobj=f,mode='r:xz') as t:
     byname={m.name.rstrip('/'):m for m in t.getmembers()}
     for key,(m,kind,rel) in sorted(entries.items(),key=lambda x:(len(x[1][2]),x[0])):
      if kind!='directory':continue
      dfd=fd_for(treefd,rel);os.fchmod(dfd,(m.mode&0o755)&~0o002);os.close(dfd)
     for key,(m,kind,rel) in entries.items():
      if kind!='file':continue
      pfd=fd_for(treefd,rel[:-1]);out=os.open(rel[-1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,(m.mode&0o755)&~0o002,dir_fd=pfd)
      src=t.extractfile(byname[m.name.rstrip('/')]);written=0
      try:
       while True:
        b=src.read(1024*1024)
        if not b:break
        offset=0
        while offset<len(b):offset+=os.write(out,b[offset:])
        written+=len(b)
      finally:
       src.close();os.close(out);os.close(pfd)
      if written!=m.size:raise ValueError('written-size mismatch')
     for key,(m,kind,rel) in entries.items():
      if kind=='symlink':
       pfd=fd_for(treefd,rel[:-1]);os.symlink(m.linkname,rel[-1],dir_fd=pfd);os.close(pfd)
   os.close(treefd)
   tree=staging/top;post,postlinks=scan(tree)
   if postlinks!=link_text:raise ValueError('post link graph mismatch')
   after=os.fstat(fd)
   if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or hash_fd(fd)!=row['sha256']:raise ValueError('archive changed during operation')
   tree_manifest=canon(post);(staging/'receipts').mkdir();(staging/'receipts'/'gcc-tree.json').write_bytes(tree_manifest)
   state_out={'schema_version':1,'outcome':'NESTED_GCC_SOURCE_MATERIALIZATION_COMPLETE','authorization_commit':AUTH,'archive_sha256':row['sha256'],'archive_size_bytes':row['size_bytes'],'member_count':len(entries),'regular_file_bytes':total,'tree_manifest_raw_sha256':sha(tree_manifest),'tree_entry_count':len(post),'source_text_read':False,'excerpt_count':0,'scientific_authority':'NONE','next_gate':'P11-G17-POST-NESTED-SOURCE-MATERIALIZATION-GOVERNANCE-V1'}
   (staging/'receipts'/'state.json').write_bytes(canon(state_out));os.close(rootfd);rootfd=None
   os.rename(staging,final);staging=None;os.close(parentfd);parentfd=None
   print(canon({'status':'PASS','state_sha256':sha(canon(state_out)),'tree_manifest_sha256':sha(tree_manifest)}).decode());return 0
  finally:
   if 'treefd' in locals() and treefd is not None:
    try:os.close(treefd)
    except OSError:pass
   if 'rootfd' in locals() and rootfd is not None:os.close(rootfd)
   if 'parentfd' in locals() and parentfd is not None:os.close(parentfd)
 finally:
  os.close(fd)
  if staging and staging.exists():shutil.rmtree(staging)
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
