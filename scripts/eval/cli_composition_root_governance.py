#!/usr/bin/env python3
"""Validate the continuous governance receipt for bridge/src/main.rs changes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MAIN_RS = "crates/bridge/src/main.rs"
RECEIPT_PREFIX = "docs/design/evidence/cli-composition-root-governance/"
SCHEMA = "agent_bridge.cli_composition_root_governance_receipt.v0"
CATEGORIES = {
    "cli_schema_or_routing",
    "startup_or_dependency_injection",
    "authority_or_effect_adapter",
    "pure_logic",
}
ROOT_DISPOSITIONS = {"root_visible", "extracted", "exception"}
CONTRACTS = {
    "clap_help_and_defaults",
    "json_and_text_output",
    "dry_run_preview_confirmation",
    "validation_and_error_ordering",
    "authority_and_effect_ordering",
    "focused_tests_and_check",
}
STATUSES = {"passed", "not_applicable"}


class GovernanceError(ValueError):
    pass


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise GovernanceError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(revision: str, path: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise GovernanceError(
            proc.stderr.decode("utf-8", errors="replace").strip()
            or f"cannot read {path} at {revision}"
        )
    return proc.stdout


def nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GovernanceError(f"{label} must be a non-empty string")
    return value.strip()


def nonempty_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise GovernanceError(f"{label} must be a non-empty array")
    result = []
    for index, item in enumerate(value):
        result.append(nonempty_string(item, f"{label}[{index}]"))
    return result


def validate_receipt(
    receipt: Any,
    *,
    base: str,
    before_sha256: str,
    after_sha256: str,
) -> None:
    if not isinstance(receipt, dict):
        raise GovernanceError("receipt must be a JSON object")
    if receipt.get("schema") != SCHEMA:
        raise GovernanceError(f"schema must equal {SCHEMA}")
    nonempty_string(receipt.get("change_id"), "change_id")
    if receipt.get("source_base") != base:
        raise GovernanceError("source_base must equal the resolved governance base commit")
    if receipt.get("main_rs_before_sha256") != before_sha256:
        raise GovernanceError("main_rs_before_sha256 does not bind the base file")
    if receipt.get("main_rs_after_sha256") != after_sha256:
        raise GovernanceError("main_rs_after_sha256 does not bind the proposed file")

    changes = receipt.get("changes")
    if not isinstance(changes, list) or not changes:
        raise GovernanceError("changes must be a non-empty array")
    authority_change = False
    for index, change in enumerate(changes):
        label = f"changes[{index}]"
        if not isinstance(change, dict):
            raise GovernanceError(f"{label} must be an object")
        nonempty_string(change.get("region"), f"{label}.region")
        nonempty_string(change.get("summary"), f"{label}.summary")
        nonempty_strings(change.get("evidence"), f"{label}.evidence")
        category = change.get("category")
        if category not in CATEGORIES:
            raise GovernanceError(f"{label}.category is not recognized")
        disposition = change.get("disposition")
        if disposition not in ROOT_DISPOSITIONS:
            raise GovernanceError(f"{label}.disposition is not recognized")
        if category == "authority_or_effect_adapter":
            authority_change = True
        if category == "pure_logic" and disposition == "root_visible":
            raise GovernanceError(
                f"{label}: pure logic cannot remain root_visible; extract it or record an exception"
            )
        if disposition == "root_visible":
            nonempty_string(change.get("root_reason"), f"{label}.root_reason")
        if disposition == "exception":
            nonempty_string(change.get("exception_reason"), f"{label}.exception_reason")

    contracts = receipt.get("contracts")
    if not isinstance(contracts, dict):
        raise GovernanceError("contracts must be an object")
    if set(contracts) != CONTRACTS:
        missing = sorted(CONTRACTS - set(contracts))
        extra = sorted(set(contracts) - CONTRACTS)
        raise GovernanceError(f"contracts keys mismatch; missing={missing}, extra={extra}")
    for name in sorted(CONTRACTS):
        contract = contracts[name]
        if not isinstance(contract, dict):
            raise GovernanceError(f"contracts.{name} must be an object")
        if contract.get("status") not in STATUSES:
            raise GovernanceError(f"contracts.{name}.status must be passed or not_applicable")
        nonempty_strings(contract.get("evidence"), f"contracts.{name}.evidence")
    if authority_change and contracts["authority_and_effect_ordering"]["status"] != "passed":
        raise GovernanceError(
            "authority/effect changes require a passed authority_and_effect_ordering contract"
        )

    nonempty_strings(receipt.get("rollback"), "rollback")


def changed_paths(base: str, head: str) -> list[str]:
    output = git("diff", "--name-only", base, head)
    return [line for line in output.splitlines() if line]


def validate_repository(base_ref: str, head_ref: str) -> None:
    base = git("rev-parse", f"{base_ref}^{{commit}}")
    head = git("rev-parse", f"{head_ref}^{{commit}}")
    paths = changed_paths(base, head)
    if MAIN_RS not in paths:
        print(f"PASS: {MAIN_RS} unchanged between {base[:12]} and {head[:12]}")
        return

    receipt_paths = [
        path
        for path in paths
        if path.startswith(RECEIPT_PREFIX) and path.endswith(".json")
        and not path.endswith(".example.json")
    ]
    if len(receipt_paths) != 1:
        raise GovernanceError(
            f"a main.rs change requires exactly one changed governance receipt; found {len(receipt_paths)}"
        )

    try:
        receipt = json.loads(git_blob(head, receipt_paths[0]).decode("utf-8"))
    except (GovernanceError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"cannot read governance receipt {receipt_paths[0]}: {exc}") from exc

    validate_receipt(
        receipt,
        base=base,
        before_sha256=sha256(git_blob(base, MAIN_RS)),
        after_sha256=sha256(git_blob(head, MAIN_RS)),
    )
    print(f"PASS: {receipt_paths[0]} governs {MAIN_RS} from {base[:12]} to {head[:12]}")


def valid_synthetic_receipt() -> dict[str, Any]:
    evidence = ["synthetic self-test evidence"]
    return {
        "schema": SCHEMA,
        "change_id": "s14b-self-test",
        "source_base": "a" * 40,
        "main_rs_before_sha256": "b" * 64,
        "main_rs_after_sha256": "c" * 64,
        "changes": [
            {
                "region": "synthetic",
                "category": "cli_schema_or_routing",
                "summary": "synthetic routing change",
                "disposition": "root_visible",
                "root_reason": "cross-domain routing remains visible at the composition root",
                "evidence": evidence,
            }
        ],
        "contracts": {
            name: {"status": "not_applicable", "evidence": evidence}
            for name in sorted(CONTRACTS)
        },
        "rollback": ["revert the synthetic change"],
    }


def expect_failure(receipt: dict[str, Any], fragment: str) -> None:
    try:
        validate_receipt(
            receipt,
            base="a" * 40,
            before_sha256="b" * 64,
            after_sha256="c" * 64,
        )
    except GovernanceError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {str(exc)!r}") from exc
        return
    raise AssertionError(f"expected governance failure containing {fragment!r}")


def self_test() -> None:
    valid = valid_synthetic_receipt()
    validate_receipt(
        valid,
        base="a" * 40,
        before_sha256="b" * 64,
        after_sha256="c" * 64,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "receipt.json"
        path.write_text(json.dumps(valid), encoding="utf-8")
        json.loads(path.read_text(encoding="utf-8"))

    wrong_hash = json.loads(json.dumps(valid))
    wrong_hash["main_rs_after_sha256"] = "0" * 64
    expect_failure(wrong_hash, "does not bind the proposed file")

    unclassified = json.loads(json.dumps(valid))
    unclassified["changes"][0]["category"] = "miscellaneous"
    expect_failure(unclassified, "category is not recognized")

    root_without_reason = json.loads(json.dumps(valid))
    del root_without_reason["changes"][0]["root_reason"]
    expect_failure(root_without_reason, "root_reason")

    pure_in_root = json.loads(json.dumps(valid))
    pure_in_root["changes"][0]["category"] = "pure_logic"
    expect_failure(pure_in_root, "pure logic cannot remain root_visible")

    missing_contract = json.loads(json.dumps(valid))
    del missing_contract["contracts"]["validation_and_error_ordering"]
    expect_failure(missing_contract, "contracts keys mismatch")

    authority_without_evidence = json.loads(json.dumps(valid))
    authority_without_evidence["changes"][0]["category"] = "authority_or_effect_adapter"
    expect_failure(authority_without_evidence, "require a passed authority")

    exception_without_reason = json.loads(json.dumps(valid))
    exception_without_reason["changes"][0]["category"] = "pure_logic"
    exception_without_reason["changes"][0]["disposition"] = "exception"
    expect_failure(exception_without_reason, "exception_reason")

    pure_extracted = json.loads(json.dumps(valid))
    pure_extracted["changes"][0]["category"] = "pure_logic"
    pure_extracted["changes"][0]["disposition"] = "extracted"
    pure_extracted["changes"][0].pop("root_reason")
    validate_receipt(
        pure_extracted,
        base="a" * 40,
        before_sha256="b" * 64,
        after_sha256="c" * 64,
    )

    authority_passed = json.loads(json.dumps(valid))
    authority_passed["changes"][0]["category"] = "authority_or_effect_adapter"
    authority_passed["contracts"]["authority_and_effect_ordering"]["status"] = "passed"
    validate_receipt(
        authority_passed,
        base="a" * 40,
        before_sha256="b" * 64,
        after_sha256="c" * 64,
    )

    print("PASS: 3 positive and 7 negative governance receipt cases")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--base", required=True)
    validate.add_argument("--head", default="HEAD")
    subparsers.add_parser("self-test")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "validate":
            validate_repository(args.base, args.head)
        else:
            self_test()
    except (GovernanceError, AssertionError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
