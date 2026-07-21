#!/usr/bin/env python3
"""Read-only Git validator for P11-G8 authorization."""
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent; REPO=HERE.parents[2]
CONTRACT=HERE/"majorana_certificate_p11_g8_remedial_operational_authorization_contract.json"; RECORD=HERE/"majorana_certificate_p11_g8_remedial_operational_authorization_record.json"
PARENT="6d8a0d32574bc0c4823feff4da5e21826e76cecd"; E2R="docs/research/fermion-frontier/majorana_certificate_p11e2r_remedial_acquisition_operational_record.json"
def canon(x:Any)->bytes:return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(",",":")).encode()
def load(p:Path,strict=False):
 b=p.read_bytes();v=json.loads(b)
 if strict and b!=canon(v):raise ValueError("noncanonical record")
 return v
def git(*a:str)->bytes:return subprocess.run(["git",*a],cwd=REPO,check=True,capture_output=True).stdout
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def verify():
 c=load(CONTRACT);r=load(RECORD,True)
 if git("rev-parse","HEAD").decode().strip()!=PARENT or r["parent_commit"]!=PARENT:raise ValueError("parent drift")
 e=git("show",f"{PARENT}:{E2R}");cust=c["P11_E2R_custody"]
 if sha(e)!=cust["record_raw_sha256"]:raise ValueError("E2R custody drift")
 ev=json.loads(e)
 if ev["disposition"]!=cust["expected_disposition"] or ev["next_gate"]!=cust["expected_next_gate"]:raise ValueError("E2R semantics drift")
 if len(c["readiness_review"])!=6 or any(x["status"]!="PASS" for x in c["readiness_review"]):raise ValueError("readiness failure")
 d=c["decision"]
 if any(d[k] for k in ("archive_unpack_or_source_reading_authorized","candidate_implementation_or_execution_authorized","kernel_accounting_bound_design_authorized")) or d["scientific_authority"]!="NONE":raise ValueError("downstream authority reopened")
 if r["contract_raw_sha256"]!=sha(CONTRACT.read_bytes()) or r["contract_canonical_sha256"]!=sha(canon(c)):raise ValueError("contract digest drift")
 return {"next_gate":d["post_run_gate"],"readiness_pass_count":6,"status":"PASS"}
if __name__=="__main__":
 try:print(canon(verify()).decode())
 except Exception as e:print(f"FAIL: {e}",file=sys.stderr);raise SystemExit(1)
