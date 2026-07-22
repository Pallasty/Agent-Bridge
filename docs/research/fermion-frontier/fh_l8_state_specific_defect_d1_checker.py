#!/usr/bin/env python3
"""Exact D4 plus rigorous degree-five remainder for the FH-L8 k0 defect."""
from __future__ import annotations
import hashlib, importlib.util, itertools, json, math, sys
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STATUS = "VERIFIED_FH_L8_K0_K1_STATE_SPECIFIC_DEFECT_WITHIN_ALLOCATION"
OBSERVABLES = ("staggered_magnetization", "double_occupancy")
_CACHE: tuple[str, dict[str, Any]] | None = None

class VerificationError(ValueError): pass

def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise VerificationError(f"{path.name} must contain an object")
    return value

def _fraction(value: Any) -> Fraction:
    if not isinstance(value, str) or "/" not in value: raise VerificationError("exact value must be a fraction string")
    try: return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc: raise VerificationError("invalid fraction") from exc

def _fmt(value: Fraction) -> str: return f"{value.numerator}/{value.denominator}"

def _sha(value: Any) -> str:
    raw=json.dumps(value,allow_nan=False,ensure_ascii=True,separators=(",",":"),sort_keys=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest()

def _load_upstream(contract: dict[str, Any]):
    pins=contract.get("source_pins")
    if not isinstance(pins,list) or len(pins)!=2: raise VerificationError("two upstream source pins required")
    loaded={}
    limit=contract["resource_limits"]["max_source_bytes"]
    for pin in pins:
        path=HERE/pin.get("path","")
        if path.parent!=HERE or not path.is_file(): raise VerificationError("unsafe or missing source pin")
        raw=path.read_bytes()
        if len(raw)>limit or hashlib.sha256(raw).hexdigest()!=pin.get("sha256"): raise VerificationError(f"source pin drift: {path.name}")
        loaded[path.name]=raw
    source=loaded["hubbard_strang_observable_taylor_step_checker.py"]
    spec=importlib.util.spec_from_loader("pinned_d1_upstream",loader=None)
    module=importlib.util.module_from_spec(spec); module.__file__=str(HERE/"hubbard_strang_observable_taylor_step_checker.py")
    exec(compile(source,module.__file__,"exec"),module.__dict__)
    return module

def _formal_product(module, backend, groups, observable, degree, counter):
    polynomial=[dict(observable)]+[{} for _ in range(degree)]
    for group_name,coefficient in module.STAGES:
        updated=[{} for _ in range(degree+1)]
        for base_degree,expansion in enumerate(polynomial):
            nested=dict(expansion)
            for power in range(degree-base_degree+1):
                if power: nested=module._commutator(backend,groups[group_name],nested,counter)
                scalar=module._i_scalar(backend,power,coefficient**power/Fraction(math.factorial(power)))
                module._add_scaled(backend,updated[base_degree+power],nested,scalar)
        polynomial=updated
    return polynomial

def _diagonal(module, backend, expansion, basis):
    value=(Fraction(0),Fraction(0))
    for key,coefficient in expansion.items():
        target,phase=backend._basis_pauli_action(key,basis)
        if target==basis: value=backend._g_add(value,backend._g_mul(coefficient,phase))
    if value[1]!=0: raise VerificationError("Hermitian diagonal expectation is not real")
    return value[0]

def _degree_five_product_bound(module, backend, groups, observable, counter, limits):
    cache={():dict(observable)}; total=Fraction(0); records=[]; maximum=0
    for sequence in itertools.combinations_with_replacement(range(len(module.STAGES)),5):
        prefix=(); final=None
        for stage_index in sequence:
            next_prefix=prefix+(stage_index,)
            if next_prefix not in cache:
                if len(cache)>=limits["max_degree_five_prefixes"]: raise VerificationError("degree-five prefix cap exceeded")
                cache[next_prefix]=module._commutator(backend,groups[module.STAGES[stage_index][0]],cache[prefix],counter)
            final=cache[next_prefix]; prefix=next_prefix
        assert final is not None
        counts=[sequence.count(i) for i in range(len(module.STAGES))]; weight=Fraction(1)
        for i,count in enumerate(counts): weight*=module.STAGES[i][1]**count/Fraction(math.factorial(count))
        norm=module._l1(final); total+=weight*norm; maximum=max(maximum,len(final))
        records.append({"sequence":list(sequence),"weight":_fmt(weight),"term_count":len(final),"L1":_fmt(norm)})
        if len(records)>limits["max_weak_compositions"]: raise VerificationError("composition cap exceeded")
    return total,{"path_count":len(records),"path_records_sha256":_sha(records),"cached_prefix_count":len(cache),"maximum_path_term_count":maximum}

def recompute(contract: dict[str, Any]) -> dict[str, Any]:
    global _CACHE
    contract_digest=_sha(contract)
    if _CACHE is not None and _CACHE[0]==contract_digest: return json.loads(json.dumps(_CACHE[1]))
    if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D1": raise VerificationError("wrong contract")
    if contract.get("parent_contract_id")!="FH-L8-INDEPENDENT-REFERENCE-S0": raise VerificationError("wrong parent")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=contract.get("checker_self_sha256"): raise VerificationError("checker self pin drift")
    workload=contract.get("workload",{})
    if (workload.get("linear_size"),workload.get("strang_steps"),workload.get("step_duration"))!=(8,100,"1/100"): raise VerificationError("workload drift")
    limits=contract.get("resource_limits",{}); module=_load_upstream(contract); backend=module._load_backend()
    old=dict(module.RESOURCE_LIMITS)
    module.RESOURCE_LIMITS["max_pair_products"]=limits["max_pair_products_per_observable"]
    module.RESOURCE_LIMITS["max_expansion_terms"]=limits["max_expansion_terms"]
    try:
        groups=backend.canonical_group_expansions(8); hamiltonian=backend._merge_expansions([groups[x] for x in module.GROUPS]); basis=module._neel_basis(8); records={}
        for name in OBSERVABLES:
            counter=module.ComputationCounter(); observable,identity=module._observable_expansion(backend,8,name)
            product=_formal_product(module,backend,groups,observable,4,counter)
            nested4=module._repeated_ad(backend,hamiltonian,observable,4,counter); ideal4={}
            module._add_scaled(backend,ideal4,nested4,module._i_scalar(backend,4,Fraction(1,24)))
            defect4=module._subtract(backend,product[4],ideal4); diagonal=_diagonal(module,backend,defect4,basis)
            nested5=module._commutator(backend,hamiltonian,nested4,counter); e5=module._l1(nested5)/120
            p5,ledger=_degree_five_product_bound(module,backend,groups,observable,counter,limits)
            delta=Fraction(1,100); total=delta**4*abs(diagonal)+delta**5*(e5+p5); allocation=_fraction(contract["per_observable_single_step_allocation"])
            expected=contract["expected_exact_values"][name]
            checks={"D4_Neel_expectation":diagonal,"D4_L1":module._l1(defect4),"E5_L1":e5,"P5_L1":p5,"total_bound":total,"bound_to_allocation_ratio":total/allocation}
            for key,value in checks.items():
                if _fraction(expected[key])!=value: raise VerificationError(f"{name} {key} drift")
            if total>=allocation: raise VerificationError(f"{name} does not fit allocation")
            records[name]={"observable_identity":identity,"D4":{"product_term_count":len(product[4]),"ideal_term_count":len(ideal4),"defect_term_count":len(defect4),"defect_expansion_sha256":backend._expansion_sha256(defect4),"Neel_expectation":_fmt(diagonal),"L1":_fmt(module._l1(defect4))},"degree_five_remainder":{"ideal_term_count":len(nested5),"ideal_expansion_sha256":backend._expansion_sha256(nested5),"E5_L1":_fmt(e5),"P5_L1":_fmt(p5),**ledger},"single_step":{"leading_absolute_contribution":_fmt(delta**4*abs(diagonal)),"remainder_bound":_fmt(delta**5*(e5+p5)),"total_bound":_fmt(total),"allocation":_fmt(allocation),"bound_to_allocation_ratio":_fmt(total/allocation),"within_allocation":True},"resource_usage":{"pair_products":counter.pair_products,"peak_expansion_terms":counter.peak_terms}}
    finally: module.RESOURCE_LIMITS.clear(); module.RESOURCE_LIMITS.update(old)
    evidence={"status":STATUS,"verified":True,"ready_gate_eligible":False,"physical_reference_qualified":False,"full_R100_error_bounded":False,"contract_id":contract["contract_id"],"observables":records,"limitations":["Only the k0 to k1 expectation defect is bounded.","The degree-five remainder uses operator-norm Pauli-L1 and does not assert later-step cancellation.","The two single-step bounds cannot be multiplied by 100 without evolved-observable certificates."]}
    _CACHE=(contract_digest,json.loads(json.dumps(evidence))); return evidence

def verify(contract: dict[str,Any],result: dict[str,Any]) -> dict[str,Any]:
    evidence=recompute(contract)
    if result!=evidence: raise VerificationError("result does not equal recomputed evidence")
    return evidence

def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv); contract=_load_json(HERE/"fh_l8_state_specific_defect_d1_contract.json")
    try:
        evidence=recompute(contract)
        if "--evidence" not in args: evidence=verify(contract,_load_json(HERE/"fh_l8_state_specific_defect_d1_result.json"))
    except (OSError,json.JSONDecodeError,VerificationError,ValueError,TypeError,KeyError) as exc:
        print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(exc)},sort_keys=True)); return 1
    print(json.dumps(evidence,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
