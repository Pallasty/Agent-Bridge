#!/usr/bin/env python3
"""Validate the G1 authenticated freeze-authority adapter preregistration.

This public validator checks one immutable design contract and its public G1.3
predecessor artifacts. It does not load private packets or key material,
verify signatures, capture secure custody, maintain a replay ledger, mint a
capability receipt, or represent a positive authority state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from engram_g1_corpus_design import (
    InputError,
    read_json,
    read_stable_bounded_file,
    reject_raw_fields,
    require_exact_fields,
    require_exact_value,
    require_list,
    require_object,
    sha256_bytes,
)


CONTRACT_SCHEMA = (
    "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_"
    "preregistration_contract.v0"
)
RECEIPT_SCHEMA = (
    "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_"
    "preregistration_receipt.v0"
)
CONTRACT_ID = (
    "engram_g1_authenticated_freeze_authority_adapter_preregistration_20260718"
)
CONTRACT_SHA256 = "a9d267056fac1662b478d929b011ef971b309db60182f0f1c7563624571945c0"
VALIDATOR_SHA256 = sha256_bytes(Path(__file__).resolve().read_bytes())

PREDECESSOR_COMMIT = "7062869196d1a3ff8bb72572a39700e65130cde4"
PREDECESSOR_CONTRACT_SHA256 = (
    "5657ac8f4b6fd4f154de7285fd4a62125bf4ea15cba787d25da40701a3ac1504"
)
PREDECESSOR_VALIDATOR_SHA256 = (
    "0b7cb3295bc3690bbfeee033de2ddf27a39eb71d0cec68f96e9b27b1a67ef089"
)
PREDECESSOR_CHECKER_SHA256 = (
    "e56a6f50a2c0372d0d59390e8792bc4269c4f63e282d49cf1a1bfe1fdd463e39"
)

REGISTERED_CONTRACT_PATH = (
    Path(__file__).resolve().parent
    / "fixtures/engram_g1_authenticated_freeze_authority_adapter_"
    "preregistration_contract_v0.json"
)


def load_registered_contract() -> dict[str, Any]:
    value, raw = read_json(REGISTERED_CONTRACT_PATH)
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError("registered adapter preregistration contract drifted")
    return value


def require_registered_value(actual: Any, expected: Any, path: str) -> None:
    """Recursively enforce every registered field, value, order, and type."""

    if isinstance(expected, dict):
        actual_object = require_object(actual, path)
        require_exact_fields(actual_object, set(expected), path)
        for field, expected_value in expected.items():
            require_registered_value(
                actual_object[field], expected_value, f"{path}.{field}"
            )
        return
    if isinstance(expected, list):
        actual_list = require_list(actual, path)
        if len(actual_list) != len(expected):
            raise InputError(
                f"{path} length must remain preregistered as {len(expected)}"
            )
        for index, expected_value in enumerate(expected):
            require_registered_value(
                actual_list[index], expected_value, f"{path}[{index}]"
            )
        return
    if type(actual) is not type(expected):
        raise InputError(
            f"{path} type must remain preregistered as {type(expected).__name__}"
        )
    require_exact_value(actual, expected, path)


def validate_contract_semantics(value: dict[str, Any]) -> dict[str, Any]:
    """Validate exact semantics without the public entry point's byte pin.

    The checker uses this pure seam to prove that each adversarial mutation is
    rejected by its specific semantic path. Public validation always calls
    :func:`validate_contract`, which additionally requires the registered raw
    bytes and exact predecessor artifacts.
    """

    reject_raw_fields(value)
    require_registered_value(value, load_registered_contract(), "contract")
    return value


def validate_public_predecessor_artifacts(repo_root: Path) -> None:
    expected = {
        repo_root
        / "scripts/eval/fixtures/engram_g1_corpus_freeze_review_contract_v1.json": PREDECESSOR_CONTRACT_SHA256,
        repo_root
        / "scripts/eval/engram_g1_corpus_freeze_review.py": PREDECESSOR_VALIDATOR_SHA256,
        repo_root
        / "scripts/check-engram-g1-corpus-freeze-review.sh": PREDECESSOR_CHECKER_SHA256,
    }
    for path, digest in expected.items():
        try:
            actual = sha256_bytes(read_stable_bounded_file(path))
        except OSError as exc:
            raise InputError(
                f"failed to read public predecessor artifact: {exc}"
            ) from exc
        if actual != digest:
            raise InputError(f"public predecessor artifact drifted: {path.name}")


def validate_contract(value: dict[str, Any], raw: bytes) -> dict[str, Any]:
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError("adapter preregistration contract bytes do not match v0")
    contract = validate_contract_semantics(value)
    validate_public_predecessor_artifacts(Path(__file__).resolve().parents[2])
    return contract


def build_receipt(contract: dict[str, Any]) -> dict[str, Any]:
    trust = contract["future_trust_model"]
    replay = contract["future_replay_lifecycle"]
    capability = contract["future_capability_receipt"]
    audit = contract["human_audit_policy"]
    boundaries = contract["boundaries"]
    return {
        "schema": RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": CONTRACT_SHA256,
        "validator_sha256": VALIDATOR_SHA256,
        "predecessor_commit": PREDECESSOR_COMMIT,
        "predecessor_contract_sha256": PREDECESSOR_CONTRACT_SHA256,
        "predecessor_validator_sha256": PREDECESSOR_VALIDATOR_SHA256,
        "predecessor_checker_sha256": PREDECESSOR_CHECKER_SHA256,
        "contract_verdict": "AUTHENTICATED_FREEZE_AUTHORITY_ADAPTER_PREREGISTERED_DESIGN_ONLY_FAIL_CLOSED",
        "public_design_contract_only": True,
        "required_signature_algorithm": trust["signature_algorithm"],
        "required_signed_encoding": trust["canonical_signed_encoding"],
        "required_signer_count": trust["required_signature_count"],
        "trust_ledger_rollback_protection_required": trust[
            "trust_ledger_revision_monotonic_and_rollback_protected"
        ],
        "required_threat_count": len(contract["threat_model"]["required_threats"]),
        "manual_audit_event_count": len(audit["manual_safety_audit_required_for"]),
        "routine_reversible_validation_requires_human_approval": audit[
            "routine_reversible_validation_requires_human_approval"
        ],
        "unchanged_authenticated_validation_requires_per_run_human_approval": audit[
            "unchanged_authenticated_validation_requires_per_run_human_approval"
        ],
        "reversible_failure_requires_automatic_rollback": audit[
            "reversible_failure_requires_automatic_rollback"
        ],
        "rollback_failure_requires_durable_lesson": audit[
            "rollback_failure_requires_durable_lesson"
        ],
        "trusted_time_profile": replay["trusted_time_profile"],
        "durable_time_high_water_mark_required": replay[
            "durable_time_high_water_mark_required"
        ],
        "bearer_capability_receipt_forbidden": capability["bearer_receipt_forbidden"],
        "adapter_implemented": False,
        "cryptographic_verification_implemented": False,
        "secure_custody_capture_implemented": False,
        "replay_ledger_implemented": False,
        "capability_receipt_minting_implemented": False,
        "current_state": contract["state_machine"]["current_state"],
        "positive_authority_state_representable": contract["state_machine"][
            "positive_authority_state_representable"
        ],
        **boundaries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    contract_parser = subparsers.add_parser("validate-contract")
    contract_parser.add_argument("--contract", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        value, raw = read_json(args.contract)
        contract = validate_contract(value, raw)
        print(json.dumps(build_receipt(contract), sort_keys=True, indent=2))
        return 0
    except InputError as exc:
        print(
            f"engram G1 authenticated freeze authority adapter preregistration rejected: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
