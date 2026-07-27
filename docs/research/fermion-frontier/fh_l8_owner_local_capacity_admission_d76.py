#!/usr/bin/env python3
"""Admit only owner-local D23 capacity after independent checks."""
from __future__ import annotations
import hashlib, json, stat
from pathlib import Path
from typing import Any, Mapping

HERE=Path(__file__).resolve().parent
CONTRACT=HERE/"fh_l8_owner_local_capacity_admission_d76_contract.json"
RESULT=HERE/"fh_l8_owner_local_capacity_admission_d76_result.json"
class D76Error(RuntimeError): pass
def load(path: Path)->Mapping[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,Mapping): raise D76Error("object required")
    return value
def validate(contract: Mapping[str,Any])->dict[str,Any]:
    if contract.get("contract_id")!="FH-L8-OWNER-LOCAL-CAPACITY-ADMISSION-D76-V1": raise D76Error("id drift")
    for name, expected in contract["source_pins"].items():
        if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=expected: raise D76Error(f"pin drift: {name}")
    d75=load(HERE/"fh_l8_owner_local_attestation_d75_contract.json")
    d64=load(HERE/"fh_l8_d23_capacity_attestation_d64.json")
    reservation=Path(d64["reservation"]["path"])
    if not reservation.is_file() or reservation.stat().st_size < 3110572064: raise D76Error("reservation capacity drift")
    if stat.S_IMODE(reservation.stat().st_mode)!=0o600: raise D76Error("reservation mode drift")
    if d75["owner_attestation"].get("owner_confirmation") is not True or d75["owner_attestation"]["controlled_scope"]!=str(reservation): raise D76Error("owner confirmation drift")
    if len(contract["independent_checks"])!=4: raise D76Error("check coverage drift")
    authority=contract["authority"]
    expected={"owner_local_capacity_admitted":True,"external_resource_reservation_admitted":False,"production_io_executed":False,"scientific_execution":False,"full53_execution_authorized":False}
    if authority!=expected: raise D76Error("authority drift")
    return {"status":"VERIFIED_D76_OWNER_LOCAL_D23_CAPACITY_ADMITTED","owner_local_capacity_admitted":True,"external_resource_reservation_admitted":False,"full53_execution_authorized":False,"remaining_required_gates":["D58","D59","D60"],"decision":contract["decision"]}
def verify()->dict[str,Any]:
    expected=validate(load(CONTRACT))
    if load(RESULT)!=expected: raise D76Error("result drift")
    return expected
if __name__=="__main__": print(json.dumps(verify(),sort_keys=True))
