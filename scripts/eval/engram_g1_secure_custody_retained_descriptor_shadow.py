#!/usr/bin/env python3
"""Validate the synthetic G1 retained-descriptor custody shadow contract.

This public structural validator reads only checked-in public artifacts. It
does not traverse a private path, read corpus bytes, execute the Rust shadow,
authenticate an envelope, provision trust, consult time, claim replay state,
mint a capability, or represent secure-custody/freeze/G1.4/runtime authority.
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
    "agent_bridge.engram_g1_secure_custody_retained_descriptor_shadow_contract.v0"
)
RECEIPT_SCHEMA = (
    "agent_bridge.engram_g1_secure_custody_retained_descriptor_shadow_"
    "contract_receipt.v0"
)
CONTRACT_ID = "engram_g1_secure_custody_retained_descriptor_shadow_20260718"
CONTRACT_SHA256 = "782fafff5b456d2ddd5fbe95d833525a1e62e4d5416ddf481d9ba3e36e582a84"
MODULE_SHA256 = "ef516c9e8784eac869de38aa11c217de1602f7a9d47719216b620b6401356b82"
VALIDATOR_SHA256 = sha256_bytes(Path(__file__).resolve().read_bytes())

PREDECESSOR_COMMIT = "2cca958844bc4ddf06954737775d40560119b8d1"
PREDECESSOR_CONTRACT_SHA256 = (
    "066c77027635ef6f0ab388e9bee9cf094a597c7cc1a23cd867aa83d78d8bf6d7"
)
PREDECESSOR_VALIDATOR_SHA256 = (
    "57e0b30fb459c1ac3ec2d9a0eff9ee6673fbd704f2b94702d5a5ebc35df76fe0"
)
PREDECESSOR_MODULE_SHA256 = (
    "5f3285482c27a73b768ca3c0726031184cb022516d9d48c4abe4258c4ed117ef"
)
PREDECESSOR_CHECKER_SHA256 = (
    "8f602104ad6e6b35af4fe4e681f02c8303f3cc98256d119a0216e58cde24e6d4"
)

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
REGISTERED_CONTRACT_PATH = (
    EVAL_DIR
    / "fixtures/engram_g1_secure_custody_retained_descriptor_shadow_contract_v0.json"
)
MODULE_PATH = REPO_ROOT / "crates/store/src/engram_g1_secure_custody_shadow.rs"


def load_registered_contract() -> dict[str, Any]:
    value, raw = read_json(REGISTERED_CONTRACT_PATH)
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError("registered retained-descriptor shadow contract drifted")
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
        EVAL_DIR
        / "fixtures/engram_g1_authenticated_freeze_authority_envelope_shadow_contract_v0.json": PREDECESSOR_CONTRACT_SHA256,
        EVAL_DIR
        / "engram_g1_authenticated_freeze_authority_envelope_shadow.py": PREDECESSOR_VALIDATOR_SHA256,
        REPO_ROOT
        / "crates/store/src/engram_g1_authenticated_envelope_shadow.rs": PREDECESSOR_MODULE_SHA256,
        REPO_ROOT
        / "scripts/check-engram-g1-authenticated-freeze-authority-envelope-shadow.sh": PREDECESSOR_CHECKER_SHA256,
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
        raise InputError("retained-descriptor shadow contract bytes do not match v0")
    contract = validate_contract_semantics(value)
    validate_public_artifacts(contract)
    return contract


def build_receipt(contract: dict[str, Any]) -> dict[str, Any]:
    implementation = contract["implementation_surface"]
    checks = contract["implemented_shadow_checks"]
    tests = contract["deterministic_attack_tests"]
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
        "predecessor_module_sha256": PREDECESSOR_MODULE_SHA256,
        "predecessor_checker_sha256": PREDECESSOR_CHECKER_SHA256,
        "contract_verdict": (
            "SYNTHETIC_RETAINED_DESCRIPTOR_CUSTODY_SHADOW_CONTRACT_"
            "VALIDATED_NO_AUTHORITY"
        ),
        "cargo_feature": implementation["cargo_feature"],
        "feature_enabled_by_default": implementation["feature_enabled_by_default"],
        "module_exported_publicly": implementation["module_exported_publicly"],
        "runtime_entrypoint_present": implementation["runtime_entrypoint_present"],
        "supported_os": implementation["supported_os"],
        "supported_filesystem": implementation["supported_filesystem"],
        "test_only_permit": implementation["only_entry_permit_constructor_is_test_cfg"],
        "synthetic_disposable_tree_only": implementation[
            "synthetic_disposable_tree_only"
        ],
        "open_directory_flags": checks["open_directory_flags"],
        "open_file_flags": checks["open_file_flags"],
        "maximum_synthetic_file_bytes": checks["maximum_synthetic_file_bytes"],
        "required_attack_test_count": tests["required_test_count"],
        "required_threat_count": len(contract["threat_model"]["required_cases"]),
        "synthetic_success_verdict": result["success_verdict"],
        "current_state": state["current_state"],
        "real_adapter_state": state["real_adapter_state"],
        "positive_secure_custody_state_representable": state[
            "positive_secure_custody_state_representable"
        ],
        "permitted_next_action": next_gate["permitted_next_action"],
        "real_private_corpus_loading_permitted": next_gate[
            "may_load_real_private_corpus"
        ],
        "real_trust_root_provisioning_permitted": next_gate[
            "may_provision_real_trust_roots"
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
            f"engram G1 retained-descriptor custody shadow rejected: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
