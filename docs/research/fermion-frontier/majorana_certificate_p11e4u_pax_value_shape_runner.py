#!/usr/bin/env python3
import hashlib,json,os,re,stat,sys,tarfile,unicodedata
from collections import Counter
from pathlib import Path
H=Path(__file__).resolve().parent;C=H/'majorana_certificate_p11e4u_pax_value_shape_classification_contract.json';E=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e3r-source-inspection');P=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana')
def canon(x):return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def hfd(fd):
 h=hashlib.sha256();os.lseek(fd,0,0)
 while b:=os.read(fd,1048576):h.update(b)
 os.lseek(fd,0,0);return h.hexdigest()
def put(fd,n,x):
 o=os.open(n,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
 try:os.write(o,canon(x));os.fsync(o)
 finally:os.close(o)
def main():
 c=json.loads(C.read_bytes());i=c['future_input'];root=Path(i['new_empty_receipt_root'])
 if root.exists():raise ValueError('root exists')
 pfd=os.open(P,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);os.mkdir(root.name,0o700,dir_fd=pfd);rfd=os.open(root.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=pfd);os.mkdir('receipts',0o700,dir_fd=rfd);qfd=os.open('receipts',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=rfd);put(qfd,'attempt.json',{'outcome':'ATTEMPT_BEFORE_OPEN','payload_bytes':0})
 fd=None
 try:
  fd=os.open(E/i['archive_relative_path'],os.O_RDONLY|os.O_NOFOLLOW);before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode) or hfd(fd)!=i['archive_sha256']:raise ValueError('identity')
  agg={k:Counter() for k in i['expected_keys']};total=0;dec=re.compile(r'^-?(0|[1-9][0-9]*)(\.[0-9]+)?$')
  with os.fdopen(os.dup(fd),'rb') as f:
   with tarfile.open(fileobj=f,mode='r:xz') as t:
    while m:=t.next():
     total+=1
     for k in i['expected_keys']:
      v=(m.pax_headers or {}).get(k);base='missing' if v is None else 'utf8_nfc' if unicodedata.normalize('NFC',v)==v else 'non_nfc'
      if k=='path' and v is not None:
       rel='equal_name' if v==m.name else 'leading_dot_equivalent' if v.lstrip('./')==m.name.lstrip('./') else 'other_relation';agg[k][base+'|'+rel]+=1
      elif k!='path' and v is not None:
       shape='decimal' if dec.fullmatch(v) else 'other';agg[k][base+'|'+shape+'|len='+str(len(v.encode()))]+=1
      else:agg[k][base]+=1
  after=os.fstat(fd)
  if before.st_ino!=after.st_ino or hfd(fd)!=i['archive_sha256']:raise ValueError('drift')
  out={'outcome':'PAX_VALUE_SHAPE_CLASSIFICATION_COMPLETE','headers_total':total,'payload_bytes':0,'source_text_read':False,'shape_counts':{k:dict(v) for k,v in agg.items()},'scientific_authority':'NONE','next_gate':'P11-G23-POST-PAX-VALUE-SHAPE-CLASSIFICATION-GOVERNANCE-V1'};put(qfd,'success.json',out);print(canon({'status':'PASS','headers_total':total,'success_sha256':sha(canon(out))}).decode())
 finally:
  if fd is not None:os.close(fd)
  os.close(qfd);os.close(rfd);os.close(pfd)
if __name__=='__main__':
 try:main()
 except Exception as e:print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
