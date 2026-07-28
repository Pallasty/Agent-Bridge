#!/usr/bin/env python3
"""Validate the non-authoritative D78 owner-host fingerprint."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any, Mapping

HERE=Path(__file__).resolve().parent
RECORD=HERE/"fh_l8_owner_host_fingerprint_d78.json"
class D78Error(RuntimeError): pass
def load(path: Path)->Mapping[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,Mapping): raise D78Error("object required")
    return value
def verify()->dict[str,Any]:
    value=load(RECORD)
    if value.get("observation_id")!="FH-L8-OWNER-HOST-FINGERPRINT-D78-V1": raise D78Error("id drift")
    for name, expected in value["source_pins"].items():
        if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=expected: raise D78Error("source pin drift")
    host=value["host"]
    if host["filesystem_type"]!="f2fs" or host["memory_max"]!="max" or host["memory_high"]!="max" or host["memory_swap_max"]!="max": raise D78Error("host observation drift")
    authority=value["authority"]
    expected={"host_identity_observed":True,"environment_frozen":False,"page_cache_bound_admitted":False,"runtime_rule_precommitted":False,"production_io_executed":False,"scientific_execution":False,"full53_execution_authorized":False}
    if authority!=expected: raise D78Error("authority drift")
    return {"status":"VERIFIED_D78_OWNER_HOST_FINGERPRINT","host_identity_observed":True,"environment_frozen":False,"page_cache_bound_admitted":False,"runtime_rule_precommitted":False,"full53_execution_authorized":False,"decision":value["decision"]}
if __name__=="__main__": print(json.dumps(verify(),sort_keys=True))
