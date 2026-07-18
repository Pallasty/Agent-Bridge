#!/usr/bin/env python3
"""Validate the synthetic G1 authenticated-envelope shadow contract.

This public structural validator reads only checked-in public artifacts. It
does not execute the Rust verifier, load private packets or keys, authenticate
real identities, capture custody, consult time, maintain trust/replay state,
mint a capability, or represent freeze/G1.4/runtime authority.
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
    "agent_bridge.engram_g1_authenticated_freeze_authority_envelope_shadow_"
    "contract.v0"
)
RECEIPT_SCHEMA = (
    "agent_bridge.engram_g1_authenticated_freeze_authority_envelope_shadow_"
    "contract_receipt.v0"
)
CONTRACT_ID = "engram_g1_authenticated_freeze_authority_envelope_shadow_20260718"
CONTRACT_SHA256 = "066c77027635ef6f0ab388e9bee9cf094a597c7cc1a23cd867aa83d78d8bf6d7"
MODULE_SHA256 = "5f3285482c27a73b768ca3c0726031184cb022516d9d48c4abe4258c4ed117ef"
VALIDATOR_SHA256 = sha256_bytes(Path(__file__).resolve().read_bytes())

PREDECESSOR_COMMIT = "632918db75f65030d3ac15bc991b51a9c938cba6"
PREDECESSOR_CONTRACT_SHA256 = (
    "a9d267056fac1662b478d929b011ef971b309db60182f0f1c7563624571945c0"
)
PREDECESSOR_VALIDATOR_SHA256 = (
    "632f93b9c9bfcedeca81916ed34be6b4ce8b7b03b916c060b2d1999d06597fde"
)
PREDECESSOR_CHECKER_SHA256 = (
    "ea8ac0126306de517175a3dffa2a3722439b93b10a3d9d112ca1732f553e6f29"
)

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
REGISTERED_CONTRACT_PATH = (
    EVAL_DIR / "fixtures/engram_g1_authenticated_freeze_authority_envelope_shadow_"
    "contract_v0.json"
)
MODULE_PATH = REPO_ROOT / "crates/store/src/engram_g1_authenticated_envelope_shadow.rs"


def load_registered_contract() -> dict[str, Any]:
    value, raw = read_json(REGISTERED_CONTRACT_PATH)
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError("registered envelope-shadow contract drifted")
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
            raise InputError(f"{path} length must remain registered as {len(expected)}")
        for index, expected_value in enumerate(expected):
            require_registered_value(
                actual_list[index], expected_value, f"{path}[{index}]"
            )
        return
    if type(actual) is not type(expected):
        raise InputError(
            f"{path} type must remain registered as {type(expected).__name__}"
        )
    require_exact_value(actual, expected, path)


def validate_contract_semantics(value: dict[str, Any]) -> dict[str, Any]:
    """Validate exact semantics below the public raw-byte pin."""

    reject_raw_fields(value)
    require_registered_value(value, load_registered_contract(), "contract")
    return value


def validate_public_artifacts(contract: dict[str, Any]) -> None:
    expected = {
        MODULE_PATH: MODULE_SHA256,
        EVAL_DIR / "fixtures/engram_g1_authenticated_freeze_authority_adapter_"
        "preregistration_contract_v0.json": PREDECESSOR_CONTRACT_SHA256,
        EVAL_DIR
        / "engram_g1_authenticated_freeze_authority_adapter_preregistration.py": PREDECESSOR_VALIDATOR_SHA256,
        REPO_ROOT / "scripts/check-engram-g1-authenticated-freeze-authority-adapter-"
        "preregistration.sh": PREDECESSOR_CHECKER_SHA256,
    }
    for path, expected_sha256 in expected.items():
        try:
            actual_sha256 = sha256_bytes(read_stable_bounded_file(path))
        except OSError as exc:
            raise InputError(
                f"failed to read public implementation artifact: {exc}"
            ) from exc
        if actual_sha256 != expected_sha256:
            raise InputError(f"public implementation artifact drifted: {path.name}")
    if contract["implementation_surface"]["module_source_sha256"] != MODULE_SHA256:
        raise InputError("contract module source binding drifted")


def validate_contract(value: dict[str, Any], raw: bytes) -> dict[str, Any]:
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError("envelope-shadow contract bytes do not match v0")
    contract = validate_contract_semantics(value)
    validate_public_artifacts(contract)
    return contract


def build_receipt(contract: dict[str, Any]) -> dict[str, Any]:
    implementation = contract["implementation_surface"]
    checks = contract["implemented_shadow_checks"]
    result = contract["synthetic_result_contract"]
    state = contract["state_machine"]
    next_gate = contract["next_gate"]
    boundaries = contract["boundaries"]
    return {
        "schema": RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_schema": CONTRACT_SCHEMA,
        "contract_sha256": CONTRACT_SHA256,
        "validator_sha256": VALIDATOR_SHA256,
        "module_source_sha256": MODULE_SHA256,
        "predecessor_commit": PREDECESSOR_COMMIT,
        "predecessor_contract_sha256": PREDECESSOR_CONTRACT_SHA256,
        "predecessor_validator_sha256": PREDECESSOR_VALIDATOR_SHA256,
        "predecessor_checker_sha256": PREDECESSOR_CHECKER_SHA256,
        "contract_verdict": (
            "SYNTHETIC_AUTHENTICATED_ENVELOPE_SHADOW_CONTRACT_" "VALIDATED_NO_AUTHORITY"
        ),
        "cargo_feature": implementation["cargo_feature"],
        "feature_enabled_by_default": implementation["feature_enabled_by_default"],
        "module_exported_publicly": implementation["module_exported_publicly"],
        "runtime_entrypoint_present": implementation["runtime_entrypoint_present"],
        "synthetic_test_vectors_only": implementation["synthetic_test_vectors_only"],
        "canonicalization_profile": checks["canonicalization_profile"],
        "restricted_exact_subset_not_full_jcs": checks[
            "canonicalization_is_a_restricted_exact_subset_not_full_jcs"
        ],
        "required_signature_count": checks["required_signature_count"],
        "required_threat_count": len(contract["threat_model"]["required_cases"]),
        "synthetic_success_verdict": result["success_verdict"],
        "current_state": state["current_state"],
        "real_adapter_state": state["real_adapter_state"],
        "positive_freeze_authority_state_representable": state[
            "positive_freeze_authority_state_representable"
        ],
        "permitted_next_action": next_gate["permitted_next_action"],
        "real_trust_root_provisioning_permitted": next_gate[
            "may_provision_real_trust_roots"
        ],
        "real_private_corpus_loading_permitted": next_gate[
            "may_load_real_private_corpus"
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
            f"engram G1 authenticated envelope shadow rejected: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
