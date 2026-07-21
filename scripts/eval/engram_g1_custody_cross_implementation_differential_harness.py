#!/usr/bin/env python3
"""Run the narrow public-synthetic G1 custody differential observation gate.

This is an evidence orchestrator, not a custody implementation. It invokes the
existing Rust test-only surface and the Python isolated lab's disposable
fixtures; it never represents equivalence, real custody, authority, or G1.4.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


CONTRACT_SCHEMA = (
    "agent_bridge.engram_g1_custody_cross_implementation_"
    "differential_harness_contract.v0"
)
RECEIPT_SCHEMA = (
    "agent_bridge.engram_g1_custody_cross_implementation_"
    "differential_harness_receipt.v0"
)
CONTRACT_ID = "engram_g1_custody_cross_implementation_differential_harness_20260718"
CONTRACT_SHA256 = "15ab49b5b4da4935e1ff0cb96f1ce52ae307affcbe98d2d63127ec36931b7acc"
PREDECESSOR_COMMIT = "382f94e597c9ccad748a271665973e01d7c78f9c"
PREDECESSOR_CONTRACT_SHA256 = (
    "d0ea62745ff239c988e5725240e0a0e44796cbce5c1b5e5a4dc499c7afa84fbc"
)
PREDECESSOR_VALIDATOR_SHA256 = (
    "1ec29777abe0d6ed5624f654aad5c685196f1a30b451241470714319c5c78c38"
)
RUST_MODULE_SHA256 = "ef516c9e8784eac869de38aa11c217de1602f7a9d47719216b620b6401356b82"
PYTHON_IMPLEMENTATION_SHA256 = (
    "50e35469af07a81b6eef85fba5c83c92076efe1931b2ee932d8e2d05907ebc94"
)
EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
CONTRACT_PATH = (
    EVAL_DIR
    / "fixtures/engram_g1_custody_cross_implementation_differential_harness_contract_v0.json"
)
PREDECESSOR_PATH = (
    EVAL_DIR
    / "fixtures/engram_g1_custody_cross_implementation_reconciliation_contract_v0.json"
)
PREDECESSOR_VALIDATOR_PATH = (
    EVAL_DIR / "engram_g1_custody_cross_implementation_reconciliation.py"
)
RUST_MODULE_PATH = REPO_ROOT / "crates/store/src/engram_g1_secure_custody_shadow.rs"
PYTHON_IMPLEMENTATION_PATH = (
    EVAL_DIR / "engram_g1_authenticated_freeze_authority_adapter_isolated_lab.py"
)


class GateError(RuntimeError):
    pass


PROBE_SPEC = (
    ("P01_RAW_PATH_SPELLING", "open", "DYNAMIC", "DYNAMIC", "RUST_STRICTER"),
    (
        "P02_ABSOLUTE_ANCESTOR_SWAP",
        "revalidate",
        "STATIC_WITNESS",
        "STATIC_WITNESS",
        "RUST_STRICTER",
    ),
    ("P03_PRIVATE_PARENT_SWAP", "revalidate", "DYNAMIC", "DYNAMIC", "RUST_STRICTER"),
    (
        "P04_PRIVATE_DIRECTORY_METADATA_DRIFT",
        "revalidate",
        "STATIC_WITNESS",
        "DYNAMIC",
        "RUST_STRICTER",
    ),
    (
        "P05_HARDLINK_BEFORE_OPEN",
        "open",
        "DYNAMIC",
        "DYNAMIC",
        "SHARED_INTENT_DIFFERENT_MECHANISM",
    ),
    (
        "P06_HARDLINK_OPEN_RACE",
        "open",
        "STATIC_WITNESS",
        "STATIC_WITNESS",
        "RUST_STRICTER",
    ),
    (
        "P07_FIFO_OR_DEVICE_SUBSTITUTION",
        "open",
        "DYNAMIC",
        "STATIC_WITNESS",
        "RUST_STRICTER",
    ),
    (
        "P08_FILE_REBIND_AFTER_READ",
        "revalidate",
        "DYNAMIC",
        "DYNAMIC",
        "SHARED_INTENT_DIFFERENT_MECHANISM",
    ),
    (
        "P09_IN_PLACE_BYTE_MUTATION",
        "revalidate",
        "DYNAMIC",
        "DYNAMIC",
        "SHARED_INTENT_DIFFERENT_MECHANISM",
    ),
    (
        "P10_LOCAL_NON_APFS_FILESYSTEM",
        "mount_policy",
        "DYNAMIC",
        "DYNAMIC",
        "RUST_STRICTER",
    ),
    (
        "P11_MOUNT_FINGERPRINT_DRIFT",
        "revalidate",
        "STATIC_WITNESS",
        "DYNAMIC",
        "RUST_STRICTER",
    ),
    (
        "P12_EXTENDED_METADATA_DRIFT",
        "revalidate",
        "STATIC_WITNESS",
        "STATIC_WITNESS",
        "RUST_STRICTER",
    ),
    (
        "P13_PUBLIC_ARTIFACT_NAME_REBIND",
        "precommit",
        "STATIC_WITNESS",
        "STATIC_WITNESS",
        "PYTHON_BROADER_SCOPE",
    ),
    (
        "P14_SQLITE_PATH_REOPEN_SWAP",
        "ledger_open",
        "STATIC_WITNESS",
        "STATIC_WITNESS",
        "NONCOMPARABLE",
    ),
    (
        "P15_AFTER_PRECOMMIT_BEFORE_COMMIT_MUTATION",
        "linearization",
        "STATIC_WITNESS",
        "STATIC_WITNESS",
        "SHARED_GAP",
    ),
    (
        "P16_POSTCOMMIT_FILESYSTEM_MUTATION",
        "linearization",
        "STATIC_WITNESS",
        "STATIC_WITNESS",
        "SHARED_GAP",
    ),
    (
        "P17_DARWIN_ACL_PRESENT",
        "shared_gap",
        "UNRESOLVED_SHARED_GAP",
        "UNRESOLVED_SHARED_GAP",
        "SHARED_GAP",
    ),
    (
        "P18_APFS_COPY_ALIAS",
        "shared_gap",
        "UNRESOLVED_SHARED_GAP",
        "UNRESOLVED_SHARED_GAP",
        "SHARED_GAP",
    ),
)
RUST_DYNAMIC_TESTS = {
    "P01_RAW_PATH_SPELLING": "engram_g1_secure_custody_shadow::tests::engram_g1_secure_custody_shadow_rejects_component_escape_forms",
    "P03_PRIVATE_PARENT_SWAP": "engram_g1_secure_custody_shadow::tests::engram_g1_secure_custody_shadow_rejects_parent_name_swap_after_read",
    "P05_HARDLINK_BEFORE_OPEN": "engram_g1_secure_custody_shadow::tests::engram_g1_secure_custody_shadow_rejects_hardlink_before_open",
    "P07_FIFO_OR_DEVICE_SUBSTITUTION": "engram_g1_secure_custody_shadow::tests::engram_g1_secure_custody_shadow_rejects_fifo_and_oversized_file",
    "P08_FILE_REBIND_AFTER_READ": "engram_g1_secure_custody_shadow::tests::engram_g1_secure_custody_shadow_rejects_final_name_swap_after_read",
    "P09_IN_PLACE_BYTE_MUTATION": "engram_g1_secure_custody_shadow::tests::engram_g1_secure_custody_shadow_rejects_in_place_mutation_after_read",
    "P10_LOCAL_NON_APFS_FILESYSTEM": "engram_g1_secure_custody_shadow::tests::engram_g1_secure_custody_shadow_mount_policy_is_local_apfs_only",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise GateError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def fields(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    require(type(value) is dict, f"{label} must be an object")
    require(set(value) == expected, f"{label} fields drifted")
    return value


def validate_contract_semantics(value: Any) -> list[dict[str, str]]:
    contract = fields(
        value,
        {
            "schema",
            "contract_id",
            "date",
            "verdict",
            "checker_sha256",
            "predecessor",
            "execution",
            "probe_plan",
            "boundaries",
        },
        "contract",
    )
    require(contract["schema"] == CONTRACT_SCHEMA, "contract schema drifted")
    require(contract["contract_id"] == CONTRACT_ID, "contract id drifted")
    require(contract["date"] == "2026-07-18", "contract date drifted")
    require(
        type(contract["checker_sha256"]) is str
        and re.fullmatch(r"[0-9a-f]{64}", contract["checker_sha256"]) is not None,
        "contract checker pin drifted",
    )
    require(
        contract["verdict"]
        == "SYNTHETIC_CROSS_IMPLEMENTATION_DIFFERENTIAL_OBSERVATION_CONTRACT_NO_AUTHORITY",
        "contract verdict drifted",
    )
    predecessor = fields(
        contract["predecessor"],
        {"commit", "contract_sha256", "validator_sha256", "checker_sha256"},
        "contract predecessor",
    )
    require(predecessor["commit"] == PREDECESSOR_COMMIT, "predecessor commit drifted")
    require(
        predecessor["contract_sha256"] == PREDECESSOR_CONTRACT_SHA256,
        "predecessor contract pin drifted",
    )
    require(
        predecessor["validator_sha256"] == PREDECESSOR_VALIDATOR_SHA256,
        "predecessor validator pin drifted",
    )
    execution = fields(
        contract["execution"],
        {
            "public_synthetic_only",
            "uses_existing_test_only_rust_permit",
            "uses_disposable_python_isolated_lab",
            "modifies_frozen_rust_source",
            "modifies_frozen_python_source",
            "implementation_equivalence_claimed",
            "production_custody_claimed",
            "authority_claimed",
        },
        "contract execution",
    )
    for name in (
        "public_synthetic_only",
        "uses_existing_test_only_rust_permit",
        "uses_disposable_python_isolated_lab",
    ):
        require(execution[name] is True, f"execution {name} widened")
    for name in (
        "modifies_frozen_rust_source",
        "modifies_frozen_python_source",
        "implementation_equivalence_claimed",
        "production_custody_claimed",
        "authority_claimed",
    ):
        require(execution[name] is False, f"execution {name} widened")
    plan = contract["probe_plan"]
    require(
        type(plan) is list and len(plan) == len(PROBE_SPEC), "probe plan length drifted"
    )
    for item, spec in zip(plan, PROBE_SPEC):
        probe = fields(
            item, {"id", "phase", "rust_mode", "python_mode", "classification"}, "probe"
        )
        observed = tuple(
            probe[name]
            for name in ("id", "phase", "rust_mode", "python_mode", "classification")
        )
        require(observed == spec, f"probe plan drifted: {probe['id']}")
    boundaries = fields(
        contract["boundaries"],
        {
            "real_private_input_permitted",
            "real_key_or_trust_root_permitted",
            "runtime_or_mcp_registration_permitted",
            "production_promotion_permitted",
            "g1_4_open_permitted",
            "runtime_authority",
        },
        "contract boundaries",
    )
    for name, state in boundaries.items():
        require(state is False, f"boundary widened: {name}")
    return plan


def load_contract(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    raw = path.read_bytes()
    require(digest(path) == CONTRACT_SHA256, "differential contract bytes drifted")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateError("differential contract is not closed JSON") from exc
    return value, validate_contract_semantics(value)


def validate_predecessor() -> None:
    require(
        digest(PREDECESSOR_PATH) == PREDECESSOR_CONTRACT_SHA256,
        "predecessor contract drifted",
    )
    require(
        digest(PREDECESSOR_VALIDATOR_PATH) == PREDECESSOR_VALIDATOR_SHA256,
        "predecessor validator drifted",
    )
    require(
        digest(RUST_MODULE_PATH) == RUST_MODULE_SHA256, "frozen Rust source drifted"
    )
    require(
        digest(PYTHON_IMPLEMENTATION_PATH) == PYTHON_IMPLEMENTATION_SHA256,
        "frozen Python source drifted",
    )
    sys.path.insert(0, str(EVAL_DIR))
    predecessor = importlib.import_module(
        "engram_g1_custody_cross_implementation_reconciliation"
    )
    value, raw = predecessor.read_json(PREDECESSOR_PATH)
    predecessor.validate_contract(value, raw)


def static_witnesses() -> None:
    rust = RUST_MODULE_PATH.read_text(encoding="utf-8")
    python = PYTHON_IMPLEMENTATION_PATH.read_text(encoding="utf-8")
    for token in (
        "absolute_root_components",
        "DIRECTORY_NAME_REBIND",
        "stable_without_atime",
        "O_NONBLOCK",
        "DARWIN_O_UNIQUE",
        "fstatat",
    ):
        require(token in rust, f"Rust static witness missing: {token}")
    for token in (
        "Path(self.config.private_input_dir_relative).parts",
        "sqlite3.connect(",
        "path.as_uri()",
        "precommit_fault_hook",
        "validate_mount_identity",
    ):
        require(token in python, f"Python static witness missing: {token}")


def run_rust_dynamic_tests() -> None:
    for probe_id, test_name in RUST_DYNAMIC_TESTS.items():
        result = subprocess.run(
            [
                "cargo",
                "test",
                "--locked",
                "-p",
                "ab-store",
                "--features",
                "engram-g1-secure-custody-shadow-synthetic",
                test_name,
                "--",
                "--exact",
                "--test-threads=1",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        require(
            result.returncode == 0
            and "running 1 test" in result.stdout
            and "test result: ok. 1 passed" in result.stdout,
            f"frozen Rust dynamic test failed: {probe_id}",
        )


def expect_error(action: Callable[[], Any], code: str, module: Any) -> None:
    try:
        action()
    except module.IsolatedLabError as exc:
        require(exc.code == code, f"expected {code}, got {exc.code}")
        return
    raise GateError(f"Python accepted attack expected to deny: {code}")


def require_no_authority(receipt: dict[str, Any]) -> None:
    require(
        receipt["production_admissible"] is False, "Python receipt widened production"
    )
    require(receipt["g1_4_open"] is False, "Python receipt opened G1.4")


def require_disposed_python_fixture(harness: Any) -> None:
    require(
        not harness.private_dir.exists() and not harness.ledger_dir.exists(),
        "disposable Python fixture cleanup failed",
    )


@contextmanager
def disposable_harness(checker: Any) -> Any:
    harness = checker.Harness(REPO_ROOT)
    try:
        with harness:
            yield harness
    finally:
        require_disposed_python_fixture(harness)


def run_python_probes() -> dict[str, str]:
    sys.path.insert(0, str(EVAL_DIR))
    module = importlib.import_module(
        "engram_g1_authenticated_freeze_authority_adapter_isolated_lab"
    )
    checker = importlib.import_module(
        "check_engram_g1_authenticated_freeze_authority_adapter_isolated_lab"
    )
    checker.module = module
    outcomes: dict[str, str] = {}
    normalized = Path(str(REPO_ROOT) + "//.")
    fd, _ = module._open_absolute_directory(normalized)
    os.close(fd)
    require(
        str(normalized) != str(REPO_ROOT) + "//.", "path spelling was not normalized"
    )
    outcomes["P01_RAW_PATH_SPELLING"] = "ACCEPTED_NORMALIZED_REPEATED_SEPARATOR_AND_DOT"

    with disposable_harness(checker) as harness:
        original = harness.private_dir
        moved = original.with_name(original.name + "-moved")

        def parent_swap(_custody: Any) -> None:
            original.rename(moved)
            original.mkdir(mode=0o700)
            os.chmod(original, 0o700)

        try:
            receipt, _ = harness.claim(hook=parent_swap)
            require_no_authority(receipt)
            outcomes["P03_PRIVATE_PARENT_SWAP"] = (
                "ACCEPTED_RETAINED_PARENT_FD_WITHOUT_NAME_CHAIN_RECHECK"
            )
        finally:
            if original.exists():
                shutil.rmtree(original)
            if moved.exists():
                moved.rename(original)
    with disposable_harness(checker) as harness:
        with module.RetainedCustodySession(harness.config) as custody:
            os.chmod(harness.private_dir, 0o750)
            try:
                receipt, _ = module.SyntheticAuthorityAdapter().claim(
                    custody,
                    harness.ledger,
                    harness.anchor,
                    harness.default_time_sample,
                    harness.consumer_public_key,
                )
                require_no_authority(receipt)
                outcomes["P04_PRIVATE_DIRECTORY_METADATA_DRIFT"] = (
                    "ACCEPTED_DIRECTORY_MODE_DRIFT_AT_CLAIM_TIME"
                )
            finally:
                os.chmod(harness.private_dir, 0o700)
    with disposable_harness(checker) as harness:
        os.link(
            harness.private_dir / "manifest.json",
            harness.private_dir / "manifest.alias",
        )
        expect_error(
            lambda: module.RetainedCustodySession(harness.config),
            "E_PRIVATE_FILE",
            module,
        )
        outcomes["P05_HARDLINK_BEFORE_OPEN"] = "REJECTED_E_PRIVATE_FILE"
    with disposable_harness(checker) as harness:
        path = harness.private_dir / "envelope.json"

        def file_rebind(_custody: Any) -> None:
            path.rename(harness.private_dir / "envelope.opened")
            checker.write_json(path, {"replacement": True})

        expect_error(lambda: harness.claim(hook=file_rebind), "E_CUSTODY_DRIFT", module)
        outcomes["P08_FILE_REBIND_AFTER_READ"] = "REJECTED_E_CUSTODY_DRIFT"
    with disposable_harness(checker) as harness:
        path = harness.private_dir / "manifest.json"

        def byte_mutation(_custody: Any) -> None:
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
            try:
                os.write(fd, b" ")
                os.fsync(fd)
            finally:
                os.close(fd)

        expect_error(
            lambda: harness.claim(hook=byte_mutation), "E_CUSTODY_DRIFT", module
        )
        outcomes["P09_IN_PLACE_BYTE_MUTATION"] = "REJECTED_E_CUSTODY_DRIFT"
    local_non_apfs = module.MountIdentity(1, 2, 3, "exfat", "0" * 64, True)
    module.validate_mount_identity(local_non_apfs, local_non_apfs)
    outcomes["P10_LOCAL_NON_APFS_FILESYSTEM"] = "ACCEPTED_LOCAL_NON_DENYLIST_FILESYSTEM"
    expected = module.MountIdentity(1, 2, 3, "apfs", "0" * 64, True)
    drifted = module.MountIdentity(1, 9, 3, "apfs", "0" * 64, True)
    expect_error(
        lambda: module.validate_mount_identity(drifted, expected),
        "E_MOUNT_DRIFT",
        module,
    )
    outcomes["P11_MOUNT_FINGERPRINT_DRIFT"] = "REJECTED_E_MOUNT_DRIFT"
    return outcomes


RUST_OUTCOMES = {
    "P01_RAW_PATH_SPELLING": "REJECTED_ROOT_PATH",
    "P02_ABSOLUTE_ANCESTOR_SWAP": "STATIC_WITNESS_RETAINS_AND_RERESOLVES_ABSOLUTE_ANCESTORS",
    "P03_PRIVATE_PARENT_SWAP": "REJECTED_DIRECTORY_NAME_REBIND",
    "P04_PRIVATE_DIRECTORY_METADATA_DRIFT": "STATIC_WITNESS_REJECTS_FULL_PRIVATE_DIRECTORY_DRIFT",
    "P05_HARDLINK_BEFORE_OPEN": "REJECTED_FILE_OPEN_OR_FILE_POLICY",
    "P06_HARDLINK_OPEN_RACE": "STATIC_WITNESS_DARWIN_O_UNIQUE",
    "P07_FIFO_OR_DEVICE_SUBSTITUTION": "REJECTED_FILE_POLICY_WITH_NONBLOCKING_OPEN",
    "P08_FILE_REBIND_AFTER_READ": "REJECTED_FILE_NAME_REBIND",
    "P09_IN_PLACE_BYTE_MUTATION": "REJECTED_FILE_DRIFT",
    "P10_LOCAL_NON_APFS_FILESYSTEM": "REJECTED_MOUNT_POLICY",
    "P11_MOUNT_FINGERPRINT_DRIFT": "STATIC_WITNESS_REJECTS_FULL_MOUNT_FINGERPRINT_DRIFT",
    "P12_EXTENDED_METADATA_DRIFT": "STATIC_WITNESS_RUST_ONLY_FIELDS_BOUND",
    "P13_PUBLIC_ARTIFACT_NAME_REBIND": "NONCOMPARABLE_NO_PUBLIC_ARTIFACT_SET",
    "P14_SQLITE_PATH_REOPEN_SWAP": "NONCOMPARABLE_NO_SQLITE_LEDGER",
    "P15_AFTER_PRECOMMIT_BEFORE_COMMIT_MUTATION": "NO_LEDGER_COMMIT_BOUNDARY",
    "P16_POSTCOMMIT_FILESYSTEM_MUTATION": "NO_LEDGER_COMMIT_BOUNDARY",
    "P17_DARWIN_ACL_PRESENT": "UNRESOLVED_SHARED_GAP",
    "P18_APFS_COPY_ALIAS": "UNRESOLVED_SHARED_GAP",
}
PYTHON_STATIC_OUTCOMES = {
    "P02_ABSOLUTE_ANCESTOR_SWAP": "STATIC_WITNESS_FINAL_ROOT_ONLY_RETENTION",
    "P06_HARDLINK_OPEN_RACE": "STATIC_WITNESS_NO_O_UNIQUE",
    "P07_FIFO_OR_DEVICE_SUBSTITUTION": "STATIC_WITNESS_NO_O_NONBLOCK_BOUNDED_RACE_HARNESS",
    "P12_EXTENDED_METADATA_DRIFT": "STATIC_WITNESS_REDUCED_STAT_TUPLE",
    "P13_PUBLIC_ARTIFACT_NAME_REBIND": "STATIC_WITNESS_NO_PUBLIC_NAME_CHAIN_REVALIDATION",
    "P14_SQLITE_PATH_REOPEN_SWAP": "STATIC_WITNESS_PATHNAME_REOPEN_UNRESOLVED",
    "P15_AFTER_PRECOMMIT_BEFORE_COMMIT_MUTATION": "STATIC_WITNESS_NO_POST_F2_INTERCEPTION_SEAM",
    "P16_POSTCOMMIT_FILESYSTEM_MUTATION": "STATIC_WITNESS_NO_POSTCOMMIT_CUSTODY_REVALIDATION",
    "P17_DARWIN_ACL_PRESENT": "UNRESOLVED_SHARED_GAP",
    "P18_APFS_COPY_ALIAS": "UNRESOLVED_SHARED_GAP",
}


def build_receipt(
    contract: dict[str, Any], plan: list[dict[str, str]]
) -> dict[str, Any]:
    validate_predecessor()
    static_witnesses()
    run_rust_dynamic_tests()
    observed = run_python_probes()
    results = []
    for item in plan:
        probe_id = item["id"]
        python_outcome = observed.get(probe_id, PYTHON_STATIC_OUTCOMES.get(probe_id))
        require(python_outcome is not None, f"missing Python outcome: {probe_id}")
        results.append(
            {
                "id": probe_id,
                "phase": item["phase"],
                "rust_execution": item["rust_mode"],
                "python_execution": item["python_mode"],
                "rust_outcome": RUST_OUTCOMES[probe_id],
                "python_outcome": python_outcome,
                "classification": item["classification"],
                "authority_if_pass": False,
            }
        )
    return {
        "schema": RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": CONTRACT_SHA256,
        "contract_verdict": contract["verdict"],
        "predecessor_commit": PREDECESSOR_COMMIT,
        "predecessor_contract_sha256": PREDECESSOR_CONTRACT_SHA256,
        "rust_module_sha256": RUST_MODULE_SHA256,
        "python_implementation_sha256": PYTHON_IMPLEMENTATION_SHA256,
        "verdict": "PASS_SYNTHETIC_DIFFERENTIAL_OBSERVATIONS_NO_AUTHORITY",
        "probe_count": len(results),
        "dynamic_rust_probe_count": sum(
            item["rust_execution"] == "DYNAMIC" for item in results
        ),
        "rust_dynamic_test_count": len(RUST_DYNAMIC_TESTS),
        "dynamic_python_probe_count": sum(
            item["python_execution"] == "DYNAMIC" for item in results
        ),
        "unresolved_shared_gap_count": sum(
            item["classification"] == "SHARED_GAP" for item in results
        ),
        "implementation_equivalence_claimed": False,
        "production_custody_claimed": False,
        "authority_claimed": False,
        "g1_4_open": False,
        "runtime_authority": False,
        "probe_results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    args = parser.parse_args()
    try:
        contract, plan = load_contract(args.contract)
        print(json.dumps(build_receipt(contract, plan), sort_keys=True, indent=2))
        return 0
    except (GateError, OSError, subprocess.SubprocessError) as exc:
        print(
            f"engram G1 custody differential harness rejected: {exc}", file=sys.stderr
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
