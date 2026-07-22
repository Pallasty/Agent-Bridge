#!/usr/bin/env python3
"""Fail-closed selector for the next independent FH-L8 reference route."""
from __future__ import annotations
import hashlib, json, sys
from fractions import Fraction
from pathlib import Path
HERE = Path(__file__).resolve().parent
POSITIVE_STATUS = "VERIFIED_INDEPENDENT_REFERENCE_ROUTE_SELECTED"
class ValidationError(ValueError): pass
def _load(path):
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise ValidationError(f"{path.name} must contain an object")
    return value
def _fraction(value):
    if not isinstance(value,str) or "/" not in value: raise ValidationError("exact quantities must be fraction strings")
    try: return Fraction(value)
    except (ValueError,ZeroDivisionError) as exc: raise ValidationError("invalid exact fraction") from exc
def verify(contract,result):
    if contract.get("schema_version")!=1 or result.get("schema_version")!=1: raise ValidationError("unsupported schema")
    if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-S0" or result.get("contract_id")!=contract["contract_id"]: raise ValidationError("identity mismatch")
    w=contract.get("workload",{})
    if (w.get("strang_steps"),w.get("step_duration"))!=(100,"1/100"): raise ValidationError("wrong R100 workload")
    if (w.get("ordinary_light_cone_layers"),w.get("physical_lattice_diameter"))!=(803,14): raise ValidationError("geometry ledger drift")
    allocation=_fraction(contract.get("allocation")); arithmetic={}
    expected={"staggered_magnetization":(Fraction(1703,24),Fraction(136961,48)),"double_occupancy":(Fraction(423,16),Fraction(70477,24))}
    for name,(d3,r4) in expected.items():
        rec=contract.get("observables",{}).get(name,{})
        if _fraction(rec.get("D3_L1"))!=d3 or _fraction(rec.get("E4_plus_P4_L1"))!=r4: raise ValidationError(f"{name} coefficient drift")
        if _fraction(rec.get("k0_D3_Neel_expectation"))!=0: raise ValidationError(f"{name} k0 D3 expectation is not zero")
        one=Fraction(1,100)**3*d3+Fraction(1,100)**4*r4; floor=100*one
        if _fraction(rec.get("uniform_supremum_floor"))!=floor or _fraction(rec.get("uniform_floor_to_allocation_ratio"))!=floor/allocation: raise ValidationError(f"{name} floor arithmetic drift")
        if floor<=allocation: raise ValidationError(f"{name} uniform architecture is not closed")
        arithmetic[name]={"one_step_operator_bound":f"{one.numerator}/{one.denominator}","uniform_floor":f"{floor.numerator}/{floor.denominator}"}
    pins=contract.get("source_pins")
    if not isinstance(pins,list) or len(pins)!=1: raise ValidationError("exactly one source pin is required")
    pin=pins[0]; source=HERE/pin.get("path","")
    if source.parent!=HERE or not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=pin.get("sha256"): raise ValidationError("source pin drift")
    if {x.get("arxiv") for x in contract.get("literature_basis",[])}!={"1912.08854","1901.00564","2306.10603v2"}: raise ValidationError("literature basis drift")
    selected="PER_STEP_STATE_SPECIFIC_EXACT_DEFECT_LEDGER"
    if contract.get("required_selected_route")!=selected or result.get("selected_route")!=selected: raise ValidationError("selected route drift")
    decisions=result.get("route_decisions",{}); required={"UNIFORM_SUPREMUM_PAULI_L1":"CLOSED_FOR_FIXED_ARCHITECTURE","ORDINARY_SUPPORT_LIGHT_CONE":"CLOSED_FOR_FIXED_ORDINARY_CONE",selected:"SELECTED"}
    if {k:decisions.get(k,{}).get("decision") for k in required}!=required: raise ValidationError("route decision drift")
    if result.get("next_unit")!=contract.get("next_unit",{}).get("id"): raise ValidationError("next unit drift")
    if result.get("status")!=POSITIVE_STATUS or result.get("verified") is not True: raise ValidationError("not the fixed positive selection")
    if result.get("ready_gate_eligible") is not False or result.get("physical_reference_qualified") is not False: raise ValidationError("authority escalation")
    return {"status":POSITIVE_STATUS,"verified":True,"ready_gate_eligible":False,"selected_route":selected,"next_unit":result["next_unit"],"arithmetic":arithmetic}
def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv); cp=Path(args[0]) if args else HERE/"fh_l8_independent_reference_route_contract.json"; rp=Path(args[1]) if len(args)>1 else HERE/"fh_l8_independent_reference_route_result.json"
    try: receipt=verify(_load(cp),_load(rp))
    except (OSError,json.JSONDecodeError,ValidationError,TypeError,KeyError) as exc:
        print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(exc)},sort_keys=True)); return 1
    print(json.dumps(receipt,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
