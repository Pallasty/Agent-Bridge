#!/usr/bin/env python3
"""One G18-authorized header-only inspection; never calls extractfile."""
import hashlib,json,os,stat,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;C=HERE/'majorana_certificate_p11e4s_archive_metadata_failure_receipt_contract.json'
E=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e3r-source-inspection');PARENT=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana');AUTH='03096a3d747e77ddc81e7ffc9b31536f9a487aef'
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def hfd(fd):
 h=hashlib.sha256();os.lseek(fd,0,0)
 while True:
  b=os.read(fd,1048576)
  if not b:break
  h.update(b)
 os.lseek(fd,0,0);return h.hexdigest()
def write_excl(fd,name,data):
 out=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
 try:
  n=0
  while n<len(data):n+=os.write(out,data[n:])
  os.fsync(out)
 finally:os.close(out)
def main():
 c=json.loads(C.read_bytes());i=c['future_input_identity'];ri=c['future_receipt_identity'];root=Path(ri['new_empty_receipt_root'])
 if root.exists() or root.is_symlink() or root.parent.resolve()!=PARENT.resolve():raise ValueError('receipt root precondition')
 mb=(E/i['tree_manifest_relative_path']).read_bytes()
 if sha(mb)!=i['tree_manifest_raw_sha256']:raise ValueError('manifest drift')
 row=i['archive_row'];match=[x for x in json.loads(mb) if x.get('relative_path')==row['relative_path']]
 if match!=[row]:raise ValueError('archive row drift')
 pfd=os.open(PARENT,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);os.mkdir(root.name,0o700,dir_fd=pfd);rfd=os.open(root.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=pfd);os.mkdir('receipts',0o700,dir_fd=rfd);qfd=os.open('receipts',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=rfd)
 attempt={'schema_version':1,'authorization_commit':AUTH,'outcome':'ATTEMPT_PERSISTED_BEFORE_ARCHIVE_OPEN','source_payload_bytes_read':0,'source_text_semantically_read':False,'archive_opened':False}
 write_excl(qfd,'attempt.json',canon(attempt))
 archive=E/'trees'/i['source_tree_identity']/row['relative_path'];fd=None
 try:
  fd=os.open(archive,os.O_RDONLY|os.O_NOFOLLOW);before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=row['size_bytes'] or hfd(fd)!=row['sha256']:raise ValueError('archive identity')
  counts={'headers_total':0,'pax_global':0,'pax_extended':0,'pax_member_with_headers':0,'xattr_or_acl_or_capability_keys':0,'gnu_sparse_typeflag':0,'tarinfo_sparse_map':0,'pax_sparse_keys':0};keys={};ident=[]
  with os.fdopen(os.dup(fd),'rb',closefd=True) as f:
   with tarfile.open(fileobj=f,mode='r:xz') as t:
    while True:
     m=t.next()
     if m is None:break
     counts['headers_total']+=1
     if counts['headers_total']>c['future_metadata_operation']['maximum_member_headers']:raise ValueError('header cap')
     typ=m.type.decode('latin1') if isinstance(m.type,bytes) else str(m.type)
     if typ=='g':counts['pax_global']+=1
     if typ=='x':counts['pax_extended']+=1
     ph=m.pax_headers or {}
     if ph:counts['pax_member_with_headers']+=1
     for k,v in ph.items():
      if k not in keys and len(keys)>=c['future_metadata_operation']['maximum_recorded_distinct_metadata_keys']:raise ValueError('key cap')
      keys[k]={'value_size_bytes':len(v.encode()),'value_sha256':sha(v.encode())}
      if k.startswith(('SCHILY.xattr.','SCHILY.acl','LIBARCHIVE.xattr','security.capability')):counts['xattr_or_acl_or_capability_keys']+=1
      if k.startswith('GNU.sparse.') or k.startswith('SCHILY.realsize'):counts['pax_sparse_keys']+=1
     if typ=='S':counts['gnu_sparse_typeflag']+=1
     if getattr(m,'sparse',None):counts['tarinfo_sparse_map']+=1
     ident.append({'header_offset':m.offset,'typeflag':typ,'name_sha256':sha(m.name.encode()),'linkname_sha256':sha(m.linkname.encode()) if m.linkname else None,'size_bytes':m.size,'mode':m.mode,'uid':m.uid,'gid':m.gid,'mtime':m.mtime})
  after=os.fstat(fd)
  if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or hfd(fd)!=row['sha256']:raise ValueError('archive changed')
  result={'schema_version':1,'outcome':'ARCHIVE_HEADER_METADATA_INSPECTION_COMPLETE','authorization_commit':AUTH,'archive_sha256':row['sha256'],'archive_size_bytes':row['size_bytes'],'archive_opened':True,'source_payload_bytes_read':0,'source_text_semantically_read':False,'member_paths_or_link_targets_recorded_verbatim':False,'counts':counts,'metadata_keys':keys,'header_identifier_records':ident,'scientific_authority':'NONE','next_gate':'P11-G19-POST-ARCHIVE-METADATA-INSPECTION-GOVERNANCE-V1'}
  write_excl(qfd,'success.json',canon(result));print(canon({'status':'PASS','success_sha256':sha(canon(result)),'headers_total':counts['headers_total']}).decode());return 0
 except Exception as exc:
  fail={'schema_version':1,'outcome':'ARCHIVE_HEADER_METADATA_INSPECTION_FAILED','authorization_commit':AUTH,'archive_opened':fd is not None,'source_payload_bytes_read':0,'source_text_semantically_read':False,'failure_type':type(exc).__name__,'failure_sha256':sha(str(exc).encode()),'scientific_authority':'NONE','next_gate':'P11-G19-POST-ARCHIVE-METADATA-INSPECTION-GOVERNANCE-V1'}
  write_excl(qfd,'failure.json',canon(fail));raise
 finally:
  if fd is not None:os.close(fd)
  os.close(qfd);os.close(rfd);os.close(pfd)
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
