#!/usr/bin/env python3
"""Static verifier for the FH-L8 D15 word-adjoint quotient proof boundary."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT_NAME = "fh_l8_word_adjoint_d15_contract.json"
RESULT_NAME = "fh_l8_word_adjoint_d15_result.json"
STATUS = "VERIFIED_D15_WORD_ADJOINT_QUOTIENT_INNER_PRODUCT_PROOF_NO_EXECUTION"


class VerificationError(ValueError):
    pass


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recompute(contract):
    if contract.get("contract_id") != "FH-L8-INDEPENDENT-REFERENCE-D15":
        raise VerificationError("identity drift")
    if _sha(Path(__file__)) != contract.get("checker_self_sha256"):
        raise VerificationError("checker self pin drift")
    for pin in contract["source_pins"]:
        if _sha(HERE / pin["path"]) != pin["sha256"]:
            raise VerificationError("source pin drift")

    d14 = _json(HERE / "fh_l8_adjoint_contraction_d14_result.json")
    if d14.get("status") != "VERIFIED_D14_ADJOINT_CONTRACTION_CONTRACT_DESIGN_NO_EXECUTION":
        raise VerificationError("D14 status drift")
    if d14.get("next_gate") != "WORD_ADJOINT_DECOMPOSITION_AND_QUOTIENT_INNER_PRODUCT_PROOF":
        raise VerificationError("D14 next gate drift")

    decomposition = contract["word_adjoint_decomposition"]
    expected_decomposition = {
        "general_term": "<psi|W_L^dagger O W_R|psi>",
        "left_ket": "ell=W_L|psi>",
        "right_ket": "r=W_R|psi>",
        "exact_full_space_identity": "<psi|W_L^dagger O W_R|psi>=<ell|O|r>",
        "left_word_order": "W_L=L_m...L_1",
        "adjoint_order": "W_L^dagger=L_1^dagger...L_m^dagger",
        "word_reversal_must_be_explicit": True,
    }
    if decomposition != expected_decomposition:
        raise VerificationError("word-adjoint decomposition drift")

    quotient = contract["quotient_contraction"]
    expected_quotient = {
        "metric": "G=diag(orbit_size)",
        "coordinate_identity": "<ell|O|r>=ell_Q^dagger G O_Q r_Q",
        "hermitian_alternative": "ell_Q^dagger G O_Q r_Q=(O_Q ell_Q)^dagger G r_Q",
        "metric_hermiticity": "O_Q^dagger G=G O_Q",
        "common_quotient_required": True,
    }
    if quotient != expected_quotient:
        raise VerificationError("quotient contraction drift")

    acceptance = contract["acceptance_requirements"]
    expected_acceptance = {
        "initial_character": "chi=trivial_Neel_character",
        "left_word_every_factor_sector_preserving": True,
        "right_word_every_factor_sector_preserving": True,
        "left_word_every_factor_G_equivariant": True,
        "right_word_every_factor_G_equivariant": True,
        "observable_G_equivariant": True,
        "observable_metric_hermitian": True,
        "same_canonical_signed_quotient": True,
        "exact_untruncated_word_actions_required_for_identity": True,
    }
    if acceptance != expected_acceptance:
        raise VerificationError("acceptance requirements drift")

    rejections = contract["mandatory_rejections"]
    expected_rejections = {
        "mismatched_symmetry_character": True,
        "non_equivariant_word_factor": True,
        "missing_adjoint_reversal_witness": True,
        "different_or_unpinned_quotient_coordinates": True,
        "non_metric_hermitian_observable_for_left_transfer": True,
        "truncated_word_promoted_to_exact_identity": True,
    }
    if rejections != expected_rejections:
        raise VerificationError("rejection boundary drift")

    authority = contract["authority_exclusions"]
    if any(authority.values()):
        raise VerificationError("forbidden authority granted")

    return {
        "contract_id": contract["contract_id"],
        "status": STATUS,
        "verified": True,
        "exact_word_decomposition_certified": True,
        "signed_quotient_contraction_identity_certified": True,
        "left_transfer_requires_metric_hermiticity": True,
        "generic_unpinned_or_truncated_word_accepted": False,
        "contraction_executed": False,
        "next_gate": "OBSERVABLE_SPECIFIC_WORD_FAMILY_AND_RESOURCE_CONTRACTION_DESIGN",
        "authority_exclusions": authority,
        "limitations": [
            "D15 proves an algebraic representation only; it supplies neither word-family enumeration nor a resource bound.",
            "A truncated word requires a separately proved approximation ledger and cannot be promoted to this exact identity.",
            "No q5, D6 remainder, cumulative, R100, physical-reference, or READY authority is granted.",
        ],
    }


def verify(contract, result):
    evidence = recompute(contract)
    if evidence != result:
        raise VerificationError("result does not equal recomputed evidence")
    return evidence


def main(argv=None):
    try:
        contract = _json(HERE / CONTRACT_NAME)
        evidence = recompute(contract)
        if "--evidence" not in list(sys.argv[1:] if argv is None else argv):
            evidence = verify(contract, _json(HERE / RESULT_NAME))
    except (OSError, json.JSONDecodeError, VerificationError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "VERIFICATION_FAILED", "verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
