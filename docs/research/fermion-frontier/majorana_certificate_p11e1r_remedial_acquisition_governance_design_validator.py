#!/usr/bin/env python3
"""Read-only Git validator for the nonexecuting P11-E1R design."""
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path
from typing import Any
HERE=Path(__file__).resolve().parent
CONTRACT=HERE/"majorana_certificate_p11e1r_remedial_acquisition_governance_design_contract.json"
RECORD=HERE/"majorana_certificate_p11e1r_remedial_acquisition_governance_design_record.json"
PARENT="536350075da41ffc1af1ecb053334233c00da48b"
G6="docs/research/fermion-frontier/majorana_certificate_p11_g6_post_source_custody_governance_record.json"
def canon(x:Any)->bytes:return json.dumps(x,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(",",":")).encode()
def sha(x:bytes)->str:return hashlib.sha256(x).hexdigest()
def load(p:Path, strict=False):
 r=p.read_bytes(); v=json.loads(r)
 if strict and r!=canon(v):raise ValueError("noncanonical record")
 return v
def git(*a:str)->bytes:return subprocess.run(["git",*a],cwd=HERE.parents[2],check=True,capture_output=True).stdout
def verify():
 c,r=load(CONTRACT),load(RECORD,True)
 if git("rev-parse","HEAD").decode().strip()!=PARENT or c["required_direct_parent_commit"]!=PARENT or r["parent_commit"]!=PARENT:raise ValueError("parent drift")
 g6=git("show",f"{PARENT}:{G6}")
 if sha(g6)!=c["P11_G6_custody"]["record_raw_sha256"] or json.loads(g6)["next_gate"]!="P11-E1R-REMEDIAL-ACQUISITION-GOVERNANCE-DESIGN-V1":raise ValueError("G6 custody drift")
 if any(c["authority"][key] for key in ("network_or_archive_acquisition_authorized","external_evidence_mutation_authorized","source_unpack_or_reading_authorized","candidate_implementation_or_execution_authorized","kernel_accounting_bound_design_authorized")) or c["authority"]["scientific_authority"]!="NONE":raise ValueError("authority reopened")
 if len(c["remedial_preconditions_for_any_future_operational_gate"])!=5 or r["precondition_count"]!=5:raise ValueError("precondition drift")
 if r["contract_raw_sha256"]!=sha(CONTRACT.read_bytes()) or r["contract_canonical_sha256"]!=sha(canon(c)):raise ValueError("contract digest drift")
 return {"next_gate":r["next_gate"],"status":"PASS"}
if __name__=="__main__":
 try:print(canon(verify()).decode())
 except (OSError,ValueError,subprocess.CalledProcessError) as e:print(f"FAIL: {e}",file=sys.stderr);raise SystemExit(1)
