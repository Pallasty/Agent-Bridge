#!/usr/bin/env python3
"""Static verifier for the FH-L8 D14 adjoint-contraction design boundary."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT_NAME = "fh_l8_adjoint_contraction_d14_contract.json"
RESULT_NAME = "fh_l8_adjoint_contraction_d14_result.json"
STATUS = "VERIFIED_D14_ADJOINT_CONTRACTION_CONTRACT_DESIGN_NO_EXECUTION"


class VerificationError(ValueError):
    pass


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recompute(contract):
    if contract.get("contract_id") != "FH-L8-INDEPENDENT-REFERENCE-D14":
        raise VerificationError("identity drift")
    if sha256(Path(__file__)) != contract.get("checker_self_sha256"):
        raise VerificationError("checker self pin drift")
    for pin in contract["source_pins"]:
        if sha256(HERE / pin["path"]) != pin["sha256"]:
            raise VerificationError("source pin drift")

    d13 = load_json(HERE / "fh_l8_q5_redesign_d13_result.json")
    if d13.get("status") != "VERIFIED_D13_OBSERVABLE_ADJOINT_CONTRACTION_DESIGN_REQUIRED":
        raise VerificationError("D13 status drift")
    if d13.get("q5_executed") is not False or d13.get("ready_gate_eligible") is not False:
        raise VerificationError("D13 authority drift")

    quotient = contract["signed_quotient_coordinates"]
    required_quotient = {
        "stored_value": "canonical_representative_full_basis_per_state_amplitude",
        "orbit_reconstruction": "a[g*r]=fermionic_phase(g,r)*a[r]",
        "inner_product_metric": "diag(orbit_size)",
        "inner_product": "sum_rep orbit_size(rep)*conjugate(u_rep)*v_rep",
    }
    if quotient != required_quotient:
        raise VerificationError("signed quotient metric drift")

    identity = contract["hermitian_moment_identity"]
    required_identity = {
        "hamiltonian": "H=H_dagger",
        "observable": "O=O_dagger",
        "integers": "a,b>=0",
        "identity": "<psi|O H^(a+b)|psi> = <H^a O psi|H^b psi>",
        "derivation": "(H^a O psi)^dagger=<psi|O H^a; then H^a H^b=H^(a+b)",
        "requires_observable_commutation": False,
        "certifies_generic_product_formula_words": False,
    }
    if identity != required_identity:
        raise VerificationError("moment identity boundary drift")

    eigen = contract["neel_observable_eigenvalues"]
    if eigen != {"staggered_magnetization": 64, "double_occupancy": 0}:
        raise VerificationError("Neel observable eigenvalue drift")

    boundary = contract["product_formula_word_boundary"]
    required_boundary = {
        "general_term": "<psi|W_L^dagger O W_R|psi>",
        "automatic_reduction_to_moment_identity": False,
        "required_next_proof": "word_adjoint_decomposition_and_quotient_inner_product_proof",
        "no_commutation_inference": True,
    }
    if boundary != required_boundary:
        raise VerificationError("product-formula word boundary drift")

    authority = contract["authority_exclusions"]
    if any(authority.values()):
        raise VerificationError("forbidden authority granted")

    return {
        "contract_id": contract["contract_id"],
        "status": STATUS,
        "verified": True,
        "q5_executed": False,
        "moment_identity_certified": True,
        "signed_quotient_inner_product_certified": True,
        "neel_eigenvalue_preconditions_certified": True,
        "generic_d2_word_reduction_certified": False,
        "observable_commutation_claimed": False,
        "next_gate": "WORD_ADJOINT_DECOMPOSITION_AND_QUOTIENT_INNER_PRODUCT_PROOF",
        "authority_exclusions": authority,
        "limitations": [
            "This design covers only Hermitian single-Hamiltonian moments with nonnegative split exponents.",
            "It does not reduce a general D2 two-sided product-formula word without a separate word-adjoint proof.",
            "It performs no contraction and grants no D6, cumulative, R100, physical-reference, or READY authority.",
        ],
    }


def verify(contract, result):
    evidence = recompute(contract)
    if evidence != result:
        raise VerificationError("result does not equal recomputed evidence")
    return evidence


def main(argv=None):
    try:
        contract = load_json(HERE / CONTRACT_NAME)
        evidence = recompute(contract)
        if "--evidence" not in list(sys.argv[1:] if argv is None else argv):
            evidence = verify(contract, load_json(HERE / RESULT_NAME))
    except (OSError, json.JSONDecodeError, VerificationError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "VERIFICATION_FAILED", "verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
