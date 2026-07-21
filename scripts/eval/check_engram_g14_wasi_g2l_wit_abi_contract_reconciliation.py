#!/usr/bin/env python3
"""Pure static G2L WIT/ABI contract reconciliation blocker checker."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_REL = "scripts/eval/fixtures/engram_g14_wasi_g2l_wit_abi_contract_reconciliation_v0.json"
CHECKER_REL = "scripts/eval/check_engram_g14_wasi_g2l_wit_abi_contract_reconciliation.py"
WRAPPER_REL = "scripts/check-engram-g14-wasi-g2l-wit-abi-contract-reconciliation.sh"
DOC_REL = "docs/design/ENGRAM_G1_4_WASI_G2L_WIT_ABI_CONTRACT_RECONCILIATION_2026_07_21.md"
HEX64 = re.compile(rb"[0-9a-f]{64}")
ZERO64 = b"0" * 64


def need(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(HEX64.sub(ZERO64, path.read_bytes())).hexdigest()


def main() -> None:
    fixture = json.loads((ROOT / FIXTURE_REL).read_text(encoding="utf-8"))
    need(fixture["schema"] == "agent_bridge.engram_g14_wasi_g2l_wit_abi_contract_reconciliation.v0", "schema drift")
    need(fixture["gate"] == "G2L_WIT_ABI_CONTRACT_RECONCILIATION_STATIC_BLOCKER", "gate drift")
    need(fixture["status"] == "CONTRACT_RECONCILIATION_REQUIRED", "status drift")
    need(fixture["execution_draft_baseline"] == {"commit": "4db84d614fdff3430a664d1bec8627780ce99168", "tree": "d535e7b9bea5268713374ab4569c70a92c5f066b"}, "baseline drift")

    observed = fixture["observed_wit"]
    need(observed["sole_path"] == "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit", "WIT path drift")
    need(observed["sha256"] == "d47b294dc4c7ee3f48d7af8a6233022a75e79533a2f554ec1299639ba3e142be", "WIT SHA drift")
    need(observed["package"] == "agent-bridge:g14-clock-probe@0.1.0", "package drift")
    need(observed["world"] == "probe", "world drift")
    need(observed["export"] == "typed-report: func() -> typed-report", "export drift")
    need(observed["imports"] == ["wasi:clocks/wall-clock@0.2.12", "wasi:clocks/monotonic-clock@0.2.12", "wasi:io/poll@0.2.12"], "imports drift")
    need(set(fixture["not_observed"]) == {"abi_sha256", "generated_bindings", "adapter", "component"}, "unobserved set drift")

    older = fixture["older_preregistration_expectation"]
    need(older == {"export": "agent-bridge:g14-clock-probe/probe.run@0.1.0", "result": "deterministic-clock-report-v0", "matches_observed_wit": False, "automatic_modification_allowed": False}, "mismatch record drift")
    tooling = fixture["observed_tooling"]
    need(tooling["g2a_candidate_only"] == {"wasmtime": "46.0.1", "authorizes_parsing_or_dependency_resolution": False}, "G2A observation widened")
    need(tooling["direct_observable"] == {"rustc": "1.92.0", "cargo": "1.92.0"}, "direct tooling observation drift")
    need(tooling["not_found"] == ["wasm-tools", "wit-bindgen", "cargo-component", "wasm-ld"], "NOT_FOUND observation drift")

    authority = fixture["current_authority"]
    need(set(authority) == {"wit_generation_allowed", "component_build_allowed", "linker_build_allowed", "execution_allowed", "runtime_allowed", "deploy_allowed", "dependency_resolution_allowed", "wit_parsing_allowed"}, "authority fields drift")
    need(all(value is False for value in authority.values()), "authority opened")
    need(fixture["only_allowed_successor"] == {"action": "OWNER_SELECT_CANONICAL_WIT_CONTRACT_AND_SEPARATELY_APPROVE_REVISION", "may_modify_old_preregistration": False, "may_execute_tools": False}, "successor boundary drift")
    need(fixture["pass_effect"] == {"opens_permissions": False, "execution_authority": False}, "PASS widened authority")

    bindings = dict(fixture["static_bindings"])
    need(bindings.pop("algorithm") == "sha256_after_replacing_lowercase_64_hex_with_64_zeroes", "binding algorithm drift")
    need(set(bindings) == {DOC_REL, FIXTURE_REL, CHECKER_REL, WRAPPER_REL}, "binding file set drift")
    mismatches = []
    for relative, expected in bindings.items():
        need(re.fullmatch(r"[0-9a-f]{64}", expected) is not None, f"invalid binding: {relative}")
        actual = canonical_sha256(ROOT / relative)
        if actual != expected:
            mismatches.append(f"{relative}: expected {expected}, canonical {actual}")
    need(not mismatches, "static binding drift:\n" + "\n".join(mismatches))

    checker_text = (ROOT / CHECKER_REL).read_text(encoding="utf-8")
    wrapper_text = (ROOT / WRAPPER_REL).read_text(encoding="utf-8")
    forbidden_apis = ("sub" + "process", "os." + "system", "os." + "popen", "pty." + "spawn", "exec" + "ve(", "spa" + "wn(")
    need(not any(token in checker_text for token in forbidden_apis), "checker process-launch surface")
    expected_wrapper = "#!/bin/sh\nset -eu\nexec python3 scripts/eval/check_engram_g14_wasi_g2l_wit_abi_contract_reconciliation.py\n"
    need(wrapper_text == expected_wrapper, "wrapper must only execute checker")
    print("PASS G2L WIT/ABI contract reconciliation: CONTRACT_RECONCILIATION_REQUIRED; all authority closed")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        print(f"FAIL G2L WIT/ABI reconciliation: {error}", file=sys.stderr)
        raise SystemExit(1)
