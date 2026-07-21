#!/usr/bin/env python3
"""Pure static G2L authorization preregistration checker."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_REL = "scripts/eval/fixtures/engram_g14_wasi_g2l_wit_component_linker_authorization_preregistration_v0.json"
HEX64 = re.compile(rb"[0-9a-f]{64}")
ZERO64 = b"0" * 64


def need(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(HEX64.sub(ZERO64, path.read_bytes())).hexdigest()


def main() -> None:
    fixture = json.loads((ROOT / FIXTURE_REL).read_text(encoding="utf-8"))
    need(fixture["gate"] == "G2L_WIT_COMPONENT_LINKER_AUTHORIZATION_PREREGISTRATION_STATIC_ONLY", "gate drift")
    predecessor = fixture["predecessor"]
    need(predecessor["result"] == "G2G_FINAL_PASS", "G2G result drift")
    need(predecessor["master_commit"] == "f0ea35edc066afe7adb71f7d7d9916cb630de938", "G2G commit drift")
    need(predecessor["master_tree"] == "f63107ee0ad97ee4daad589a7323e31c72722ffe", "G2G tree drift")
    need(predecessor["claim"] == "input-bound offline/locked host compile only", "G2G claim widened")
    need(set(predecessor["does_not_prove"]) == {"byte_reproducibility", "wit", "component", "linker", "execution", "runtime", "deployment"}, "G2G exclusions drift")
    refs = predecessor["receipt_evidence_references"]
    need(len(refs) == 2 and all(ref.endswith("@" + predecessor["master_commit"]) for ref in refs), "G2G receipt references")

    future = fixture["future_input_tuple"]
    need(future["wit_source"] == {"absolute_path": "UNSET_REQUIRES_SUCCESSOR", "sha256": "UNSET_REQUIRES_SUCCESSOR", "abi_sha256": "UNSET_REQUIRES_SUCCESSOR"}, "WIT/ABI tuple")
    need(set(future["tooling"]["required_identity_fields"]) == {"name", "absolute_path", "sha256", "version"}, "tool identity tuple")
    need(set(future["dependencies"]["required_identity_fields"]) == {"package", "source", "sha256"}, "dependency tuple")
    need(future["cache_and_network_policy"]["network_allowed"] is False and future["cache_and_network_policy"]["cache_population_allowed"] is False, "cache/network boundary")
    need(all(value == "UNSET_REQUIRES_SUCCESSOR" for value in future["outputs"].values()), "output/cleanup tuple")

    required_preconditions = {"owner_approval", "independent_pre_execution_review", "fresh_clean_worktrees", "offline", "locked", "no_private_input", "no_network", "no_rustup", "no_output_execution", "postcondition_receipts", "rollback_receipts"}
    need(set(fixture["mandatory_preconditions"]) == required_preconditions, "precondition set drift")
    need(all(value is True for value in fixture["mandatory_preconditions"].values()), "mandatory precondition weakened")
    closed = {"authorization_granted", "dependency_resolution_allowed", "wit_generation_allowed", "linker_build_allowed", "component_build_allowed", "output_execution_allowed", "runtime_or_deploy_allowed"}
    need(set(fixture["current_authority"]) == closed, "authority field drift")
    need(all(value is False for value in fixture["current_authority"].values()), "authority opened")
    need(fixture["pass_effect"] == {"opens_permissions": False, "execution_authority": False}, "PASS widened authority")
    need(fixture["only_allowed_successor"] == "SEPARATE_G2L_EXECUTION_AUTHORIZATION", "successor drift")

    bindings = fixture["static_bindings"]
    need(bindings.pop("algorithm") == "sha256_after_replacing_lowercase_64_hex_with_64_zeroes", "binding algorithm")
    need(set(bindings) == {
        "docs/design/ENGRAM_G1_4_WASI_G2L_WIT_COMPONENT_LINKER_AUTHORIZATION_PREREGISTRATION_2026_07_21.md",
        FIXTURE_REL,
        "scripts/eval/check_engram_g14_wasi_g2l_wit_component_linker_authorization_preregistration.py",
        "scripts/check-engram-g14-wasi-g2l-wit-component-linker-authorization-preregistration.sh",
    }, "binding file set")
    for relative, expected in bindings.items():
        need(re.fullmatch(r"[0-9a-f]{64}", expected) is not None, f"invalid binding: {relative}")
        need(canonical_sha256(ROOT / relative) == expected, f"static binding drift: {relative}")

    checker_text = Path(__file__).read_text(encoding="utf-8")
    wrapper_text = (ROOT / "scripts/check-engram-g14-wasi-g2l-wit-component-linker-authorization-preregistration.sh").read_text(encoding="utf-8")
    forbidden_apis = ("sub" + "process", "os." + "system", "os." + "popen", "pty." + "spawn", "exec" + "ve(", "spa" + "wn(")
    need(not any(token in checker_text for token in forbidden_apis), "checker process-launch surface")
    need(wrapper_text == "#!/bin/sh\nset -eu\nexec python3 scripts/eval/check_engram_g14_wasi_g2l_wit_component_linker_authorization_preregistration.py\n", "wrapper must only execute checker")
    forbidden_wrapper = ("cargo", "rustc", "rustup", "wasm-tools", "wasm32", "wit-bindgen", "component build", "component link")
    need(not any(token in wrapper_text.lower() for token in forbidden_wrapper), "forbidden wrapper command surface")
    print("PASS G2L static preregistration: all authorization closed; no execution authority")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        print(f"FAIL G2L: {error}", file=sys.stderr)
        raise SystemExit(1)
