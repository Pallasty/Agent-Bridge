#!/usr/bin/env python3
import hashlib,json,os,re,stat,sys,tarfile,unicodedata
from pathlib import Path,PurePosixPath
HERE=Path(__file__).resolve().parent;B=HERE/'majorana_certificate_p11g20r_pax_validation_execution_binding_contract.json';AUTH='1670567218599d6038be6396a2b942f3cb1f09b1'
E=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e3r-source-inspection');PARENT=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana')
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def hfd(fd):
 h=hashlib.sha256();os.lseek(fd,0,0)
 while True:
  b=os.read(fd,1048576)
  if not b:break
  h.update(b)
 os.lseek(fd,0,0);return h.hexdigest()
def put(fd,n,v):
 o=os.open(n,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
 try:
  b=canon(v);os.write(o,b);os.fsync(o)
 finally:os.close(o)
def valid_path(v):
 if len(v.encode())>4096 or '\0' in v or unicodedata.normalize('NFC',v)!=v:return False
 p=PurePosixPath(v)
 return not p.is_absolute() and p.parts and all(x not in ('','.','..') and not any(ord(c)<32 for c in x) for x in p.parts) and p.parts[0]=='gcc-15.2.0'
def main():
 b=json.loads(B.read_bytes());x=b['future_execution_binding'];root=Path(x['new_empty_receipt_root'])
 if root.exists() or root.parent.resolve()!=PARENT.resolve():raise ValueError('receipt root')
 pfd=os.open(PARENT,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);os.mkdir(root.name,0o700,dir_fd=pfd);rfd=os.open(root.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=pfd);os.mkdir('receipts',0o700,dir_fd=rfd);qfd=os.open('receipts',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=rfd)
 put(qfd,'attempt.json',{'authorization_commit':AUTH,'outcome':'ATTEMPT_PERSISTED_BEFORE_ARCHIVE_OPEN','payload_bytes':0})
 fd=None
 try:
  archive=E/x['exact_archive_relative_path'];fd=os.open(archive,os.O_RDONLY|os.O_NOFOLLOW);before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode) or hfd(fd)!=x['archive_sha256']:raise ValueError('archive identity')
  total=bad=0;time_re=re.compile(r'^-?(0|[1-9][0-9]*)(\.[0-9]+)?$')
  with os.fdopen(os.dup(fd),'rb') as f:
   with tarfile.open(fileobj=f,mode='r:xz') as t:
    while (m:=t.next()) is not None:
     total+=1;p=m.pax_headers or {}
     if set(p)!=set(x['exact_keys']) or not valid_path(p.get('path','')) or p.get('path')!=m.name or any(not time_re.fullmatch(p[k]) or len(p[k].encode())>64 for k in ('atime','ctime','mtime')):bad+=1
  after=os.fstat(fd)
  if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or hfd(fd)!=x['archive_sha256']:raise ValueError('archive drift')
  out={'authorization_commit':AUTH,'outcome':'RESTRICTED_PAX_VALIDATION_COMPLETE','headers_total':total,'invalid_headers':bad,'payload_bytes':0,'source_text_read':False,'scientific_authority':'NONE','next_gate':'P11-G21-POST-RESTRICTED-PAX-VALIDATION-GOVERNANCE-V1'}
  put(qfd,'success.json',out);print(canon({'status':'PASS','headers_total':total,'invalid_headers':bad,'success_sha256':sha(canon(out))}).decode());return 0
 except Exception as e:
  put(qfd,'failure.json',{'authorization_commit':AUTH,'outcome':'RESTRICTED_PAX_VALIDATION_FAILED','payload_bytes':0,'failure_sha256':sha(str(e).encode())});raise
 finally:
  if fd is not None:os.close(fd)
  os.close(qfd);os.close(rfd);os.close(pfd)
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
