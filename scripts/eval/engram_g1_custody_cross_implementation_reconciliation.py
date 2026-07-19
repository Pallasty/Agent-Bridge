#!/usr/bin/env python3
"""Validate the Engram G1 custody cross-implementation preregistration.

This public structural validator reads only checked-in public source and
contract artifacts. It does not run either custody implementation, traverse a
private path, open a ledger, provision trust, consult time, claim replay state,
mint a capability, or represent implementation equivalence, real custody,
freeze authority, G1.4, or runtime authority.
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
    "agent_bridge.engram_g1_custody_cross_implementation_reconciliation_" "contract.v0"
)
RECEIPT_SCHEMA = (
    "agent_bridge.engram_g1_custody_cross_implementation_reconciliation_" "receipt.v0"
)
CONTRACT_ID = "engram_g1_custody_cross_implementation_reconciliation_20260718"
CONTRACT_SHA256 = "d0ea62745ff239c988e5725240e0a0e44796cbce5c1b5e5a4dc499c7afa84fbc"
VALIDATOR_SHA256 = sha256_bytes(Path(__file__).resolve().read_bytes())

RUST_COMMIT = "db27075ff3eb473b5ca779b57bd86094290dc1c6"
PYTHON_COMMIT = "bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54"
INTEGRATED_MASTER = "33c2c4df78ef302fd0538986b95fa40a3711ba86"
LOCAL_MERGE_COMMIT = "9e441542f5bf424b4b07ac105ccc1d25c1676d81"

RUST_MODULE_SHA256 = "ef516c9e8784eac869de38aa11c217de1602f7a9d47719216b620b6401356b82"
RUST_CONTRACT_SHA256 = (
    "782fafff5b456d2ddd5fbe95d833525a1e62e4d5416ddf481d9ba3e36e582a84"
)
RUST_VALIDATOR_SHA256 = (
    "25badec3b0ca55f2a07f8038177a33306a56345fe670bff5c4784b586a3b3e5a"
)
RUST_CHECKER_SHA256 = "331736d1244584c25cff50e1c77d93c38668bf9a93543c7ce14602326b699138"
PYTHON_IMPLEMENTATION_SHA256 = (
    "50e35469af07a81b6eef85fba5c83c92076efe1931b2ee932d8e2d05907ebc94"
)
PYTHON_CONTRACT_SHA256 = (
    "f9b913c50eaf477c58a11bbf9526070c43137fe91098388d8260f84eb51a3b14"
)
PYTHON_CHECKER_SHA256 = (
    "e9aec0676148591e44181b36bf6f0a3ad62f130e1c92ed88bdd3cf7519b4c69e"
)
PYTHON_SHELL_SHA256 = "6f81855d87d348e1e096adad9df2b271385edea3eed52695532155bac06e4895"

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
REGISTERED_CONTRACT_PATH = (
    EVAL_DIR / "fixtures/engram_g1_custody_cross_implementation_reconciliation_"
    "contract_v0.json"
)


def load_registered_contract() -> dict[str, Any]:
    value, raw = read_json(REGISTERED_CONTRACT_PATH)
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError("registered custody reconciliation contract drifted")
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
        REPO_ROOT
        / "crates/store/src/engram_g1_secure_custody_shadow.rs": RUST_MODULE_SHA256,
        EVAL_DIR / "fixtures/engram_g1_secure_custody_retained_descriptor_shadow_"
        "contract_v0.json": RUST_CONTRACT_SHA256,
        EVAL_DIR
        / "engram_g1_secure_custody_retained_descriptor_shadow.py": RUST_VALIDATOR_SHA256,
        REPO_ROOT
        / "scripts/check-engram-g1-secure-custody-retained-descriptor-shadow.sh": RUST_CHECKER_SHA256,
        EVAL_DIR
        / "engram_g1_authenticated_freeze_authority_adapter_isolated_lab.py": PYTHON_IMPLEMENTATION_SHA256,
        EVAL_DIR / "fixtures/engram_g1_authenticated_freeze_authority_adapter_"
        "isolated_lab_contract_v0.json": PYTHON_CONTRACT_SHA256,
        EVAL_DIR / "check_engram_g1_authenticated_freeze_authority_adapter_"
        "isolated_lab.py": PYTHON_CHECKER_SHA256,
        REPO_ROOT / "scripts/check-engram-g1-authenticated-freeze-authority-adapter-"
        "isolated-lab.sh": PYTHON_SHELL_SHA256,
    }
    for path, expected_sha256 in expected.items():
        try:
            actual_sha256 = sha256_bytes(read_stable_bounded_file(path))
        except OSError as exc:
            raise InputError(
                f"failed to read public comparison artifact: {exc}"
            ) from exc
        if actual_sha256 != expected_sha256:
            raise InputError(f"public comparison artifact drifted: {path.name}")

    rust = contract["source_profiles"]["rust_retained_descriptor_shadow"]
    python = contract["source_profiles"]["python_authenticated_adapter_isolated_lab"]
    if (
        rust["module_sha256"] != RUST_MODULE_SHA256
        or rust["contract_sha256"] != RUST_CONTRACT_SHA256
        or rust["validator_sha256"] != RUST_VALIDATOR_SHA256
        or rust["checker_sha256"] != RUST_CHECKER_SHA256
    ):
        raise InputError("Rust source-profile binding drifted")
    if (
        python["implementation_sha256"] != PYTHON_IMPLEMENTATION_SHA256
        or python["contract_sha256"] != PYTHON_CONTRACT_SHA256
        or python["checker_sha256"] != PYTHON_CHECKER_SHA256
        or python["shell_entrypoint_sha256"] != PYTHON_SHELL_SHA256
    ):
        raise InputError("Python source-profile binding drifted")


def validate_contract(value: dict[str, Any], raw: bytes) -> dict[str, Any]:
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError("custody reconciliation contract bytes do not match v0")
    contract = validate_contract_semantics(value)
    validate_public_artifacts(contract)
    return contract


def build_receipt(contract: dict[str, Any]) -> dict[str, Any]:
    purpose = contract["purpose"]
    vocabulary = contract["classification_vocabulary"]
    matrix = contract["comparison_matrix"]
    probes = contract["required_future_differential_probes"]
    linearization = contract["linearization_model"]
    adjudication = contract["adjudication_rules"]
    state = contract["state_machine"]
    next_gate = contract["next_gate"]
    boundaries = contract["boundaries"]
    return {
        "schema": RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_schema": CONTRACT_SCHEMA,
        "contract_sha256": CONTRACT_SHA256,
        "validator_sha256": VALIDATOR_SHA256,
        "contract_verdict": contract["verdict"],
        "rust_custody_commit": RUST_COMMIT,
        "python_isolated_lab_commit": PYTHON_COMMIT,
        "integrated_master": INTEGRATED_MASTER,
        "local_merge_commit": LOCAL_MERGE_COMMIT,
        "rust_module_sha256": RUST_MODULE_SHA256,
        "python_implementation_sha256": PYTHON_IMPLEMENTATION_SHA256,
        "source_pinned": purpose["source_pinned"],
        "design_only": purpose["design_only"],
        "differential_harness_implemented": purpose["differential_harness_implemented"],
        "implementation_equivalence_claimed": purpose[
            "implementation_equivalence_claimed"
        ],
        "comparison_row_count": len(matrix),
        "required_probe_count": len(probes),
        "classification_count": len(vocabulary["allowed"]),
        "exact_equivalence_row_count": len(vocabulary["exact_equivalence_rows"]),
        "automatic_union_permitted": vocabulary["automatic_union_permitted"],
        "shared_atomic_linearization_point_proven": linearization[
            "shared_atomic_linearization_point_proven"
        ],
        "descriptor_native_sqlite_open_proven": linearization[
            "descriptor_native_sqlite_open_proven"
        ],
        "postcommit_custody_revalidation_present": linearization[
            "postcommit_custody_revalidation_present"
        ],
        "may_select_strongest_control_by_union": adjudication[
            "may_select_strongest_control_by_union"
        ],
        "current_state": state["current_state"],
        "positive_equivalence_state_representable": state[
            "positive_equivalence_state_representable"
        ],
        "production_custody_state_representable": state[
            "production_custody_state_representable"
        ],
        "permitted_next_action": next_gate["permitted_next_action"],
        "design_review_required_before_implementation": next_gate[
            "design_review_required_before_implementation"
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
        print(f"engram G1 custody reconciliation rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
