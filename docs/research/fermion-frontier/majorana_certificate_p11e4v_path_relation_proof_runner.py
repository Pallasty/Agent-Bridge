#!/usr/bin/env python3
import hashlib,json,os,stat,sys,tarfile
from collections import Counter
from pathlib import Path

H=Path(__file__).resolve().parent
C=H/'majorana_certificate_p11e4v_path_relation_proof_contract.json'
A=H/'majorana_certificate_p11_g24_path_relation_proof_authorization.json'
E=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e3r-source-inspection')
P=Path('/Data/CascadeProjects/.ab-evidence/fermion-majorana')

def canon(x): return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def hfd(fd):
    h=hashlib.sha256();os.lseek(fd,0,0)
    while b:=os.read(fd,1048576): h.update(b)
    os.lseek(fd,0,0);return h.hexdigest()
def put(fd,name,value):
    out=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
    try: os.write(out,canon(value));os.fsync(out)
    finally: os.close(out)
def valid_relative(value):
    if '\x00' in value or value.startswith('/'): return None
    parts=value.split('/')
    if '..' in parts or any(x=='' for x in parts[1:-1]): return None
    if value.startswith('./'): value=value[2:]
    return value
def relation(pax_path,member_name):
    if pax_path==member_name: return 'exact_byte_equal'
    p=valid_relative(pax_path);m=valid_relative(member_name)
    if p is None or m is None: return 'unsafe_or_unproven_relation'
    if ((pax_path.startswith('./')) != (member_name.startswith('./'))) and p==m: return 'single_leading_dot_slash_equal'
    if p==m: return 'posix_lexically_normalized_equal'
    return 'unsafe_or_unproven_relation'
def eligible(pax_path,member_name): return pax_path is not None and pax_path!=member_name and pax_path.lstrip('./')!=member_name.lstrip('./')
def main():
    c=json.loads(C.read_bytes());a=json.loads(A.read_bytes());i=c['future_input'];op=c['future_operation'];root=Path(i['new_empty_receipt_root'])
    if root.exists(): raise ValueError('receipt_root_exists')
    if a['decision']['disposition']!='AUTHORIZE_ONE_P11_E4V_PATH_RELATION_PROOF_RUN' or a['limits']['maximum_runs']!=1 or a['limits']['payload_bytes']!=0: raise ValueError('authorization')
    pfd=os.open(P,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);os.mkdir(root.name,0o700,dir_fd=pfd);rfd=os.open(root.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=pfd);os.mkdir('receipts',0o700,dir_fd=rfd);qfd=os.open('receipts',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=rfd);put(qfd,'attempt.json',{'outcome':'ATTEMPT_BEFORE_ARCHIVE_OPEN','payload_bytes':0,'source_text_read':False})
    fd=None
    try:
        fd=os.open(E/i['archive_relative_path'],os.O_RDONLY|os.O_NOFOLLOW);before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or hfd(fd)!=i['archive_sha256']: raise ValueError('archive_identity')
        counts=Counter();headers=0;eligible_count=0
        with os.fdopen(os.dup(fd),'rb') as f:
            with tarfile.open(fileobj=f,mode='r:xz') as t:
                while m:=t.next():
                    headers+=1;v=(m.pax_headers or {}).get('path')
                    if eligible(v,m.name): counts[relation(v,m.name)]+=1;eligible_count+=1
        after=os.fstat(fd)
        if headers>op['maximum_headers'] or eligible_count!=op['expected_eligible_member_count'] or eligible_count>op['maximum_eligible_members'] or before.st_ino!=after.st_ino or hfd(fd)!=i['archive_sha256']: raise ValueError('boundary_or_drift')
        out={'outcome':'PATH_RELATION_PROOF_COMPLETE','archive_sha256':i['archive_sha256'],'authorization_raw_sha256':sha(A.read_bytes()),'contract_raw_sha256':sha(C.read_bytes()),'headers_total':headers,'eligible_members':eligible_count,'relation_counts':{k:counts[k] for k in op['allowed_aggregate_relation_classes']},'payload_bytes':0,'source_text_read':False,'scientific_authority':'NONE','next_gate':a['decision']['post_run_gate']}
        put(qfd,'success.json',out);print(canon({'status':'PASS','eligible_members':eligible_count,'success_sha256':sha(canon(out))}).decode())
    finally:
        if fd is not None: os.close(fd)
        os.close(qfd);os.close(rfd);os.close(pfd)
if __name__=='__main__':
    try: main()
    except Exception as e: print(f'FAIL: {e}',file=sys.stderr);raise SystemExit(1)
