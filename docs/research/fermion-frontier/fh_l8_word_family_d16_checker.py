#!/usr/bin/env python3
"""Static D16 audit: observable word families and contraction resources."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
STATUS="VERIFIED_D16_WORD_FAMILY_AND_RESOURCE_CONTRACTION_DESIGN_NO_EXECUTION"
class VerificationError(ValueError):pass
def _json(path):return json.loads(path.read_text(encoding="utf-8"))
def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def recompute(contract):
 if contract.get("contract_id")!="FH-L8-INDEPENDENT-REFERENCE-D16":raise VerificationError("identity drift")
 if _sha(Path(__file__))!=contract.get("checker_self_sha256"):raise VerificationError("checker self pin drift")
 for pin in contract["source_pins"]:
  if _sha(HERE/pin["path"])!=pin["sha256"]:raise VerificationError("source pin drift")
 d15=_json(HERE/"fh_l8_word_adjoint_d15_result.json")
 d11=_json(HERE/"fh_l8_d11_full_action_result.json")
 d12=_json(HERE/"fh_l8_q4_to_q5_cost_d12_result.json")
 if d15.get("status")!="VERIFIED_D15_WORD_ADJOINT_QUOTIENT_INNER_PRODUCT_PROOF_NO_EXECUTION":raise VerificationError("D15 status drift")
 if d11.get("target_records")!=10785545 or d11.get("target_payload_bytes")!=345137440:raise VerificationError("D11 q4 custody drift")
 if d12.get("status")!="NO_GO_D12_Q4_TO_Q5_CURRENT_D10_ENVELOPE":raise VerificationError("D12 no-go drift")
 audit=contract["atomic_gate_symmetry_audit"]
 expected_audit={"R90":{"H1":"H4","H2":"H3","H3":"H2","H4":"H1"},"single_atomic_hopping_factors_G_equivariant":False,"current_atomic_product_formula_word_eligible":False,"reason":"D15_requires_every_factor_G_equivariant"}
 if audit!=expected_audit:raise VerificationError("atomic symmetry audit drift")
 family=contract["observable_word_families"]
 expected_family={"observables":["staggered_magnetization","double_occupancy"],"atomic_product_formula_words":{"eligible":False,"accepted_word_count":0},"full_H_moments":{"eligible_for_design_only":True,"maximum_total_H_depth":4,"moment_split_count_per_observable":15,"total_observable_word_specs":30,"requires_exact_pinned_q0_to_q4_vectors":True,"requires_separate_execution_protocol":True}}
 if family!=expected_family:raise VerificationError("word-family drift")
 resources=contract["resource_accounting"]
 expected_resources={"q4_representatives":10785545,"packed_q4_payload_bytes":345137440,"two_q4_vector_payload_bytes":690274880,"observable_support_expansion":"none_for_pinned_diagonal_observables","current_envelope_feasibility_certified":False,"q5_required":False,"q5_authorized":False}
 if resources!=expected_resources:raise VerificationError("resource accounting drift")
 authority=contract["authority_exclusions"]
 if any(authority.values()):raise VerificationError("forbidden authority granted")
 return {"contract_id":contract["contract_id"],"status":STATUS,"verified":True,"atomic_product_formula_word_family_accepted":False,"full_H_moment_word_family_design_eligible":True,"contraction_execution_authorized":False,"q5_executed":False,"next_gate":"PINNED_Q0_TO_Q4_VECTOR_CUSTODY_AND_DUAL_VECTOR_CONTRACTION_PROTOCOL","authority_exclusions":authority,"limitations":["Atomic product-formula hopping words fail the D15 every-factor equivariance requirement under the pinned D4 action.","Full-H moments are a design-only family; no dual-vector contraction protocol or resource feasibility is certified.","No q5, D6 remainder, cumulative, R100, physical-reference, or READY authority."]}
def verify(contract,result):
 evidence=recompute(contract)
 if evidence!=result:raise VerificationError("result does not equal recomputed evidence")
 return evidence
def main(argv=None):
 try:
  c=_json(HERE/"fh_l8_word_family_d16_contract.json");e=recompute(c)
  if "--evidence" not in list(sys.argv[1:] if argv is None else argv):e=verify(c,_json(HERE/"fh_l8_word_family_d16_result.json"))
 except (OSError,json.JSONDecodeError,VerificationError,KeyError,TypeError) as exc:print(json.dumps({"status":"VERIFICATION_FAILED","verified":False,"error":str(exc)},sort_keys=True));return 1
 print(json.dumps(e,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
