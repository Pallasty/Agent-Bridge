#!/usr/bin/env python3
import hashlib,json,os,stat
from pathlib import Path
from typing import Any,Mapping
HERE=Path(__file__).resolve().parent; C=HERE/"fh_l8_d23_capacity_attestation_d64.json"
class D64Error(RuntimeError):pass
def load(p:Path)->Mapping[str,Any]: return json.loads(p.read_text())
def verify():
 c=load(C)
 for n,h in c["source_pins"].items():
  if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h:raise D64Error(f"pin:{n}")
 r=c["reservation"]; p=Path(r["path"]); d=p.parent
 if not p.is_file() or p.stat().st_size<r["required_bytes"]:raise D64Error("reservation size")
 if stat.S_IMODE(d.stat().st_mode)!=0o700 or stat.S_IMODE(p.stat().st_mode)!=0o600:raise D64Error("reservation mode")
 if p.stat().st_uid!=r["owner_uid"] or p.stat().st_gid!=r["owner_gid"]:raise D64Error("reservation owner")
 if c["authority"]["capacity_attestation_admitted"] is not False or c["authority"]["external_resource_reservation_admitted"] is not False:raise D64Error("authority")
 return {"status":"VERIFIED_D64_OWNER_LOCAL_CAPACITY_OBSERVATION","logical_bytes":p.stat().st_size,"allocated_blocks":p.stat().st_blocks,"capacity_attestation_admitted":False,"external_resource_reservation_admitted":False,"full53_execution_authorized":False,"next_gate":c["next_gate"]}
if __name__=="__main__":print(json.dumps(verify(),sort_keys=True))
