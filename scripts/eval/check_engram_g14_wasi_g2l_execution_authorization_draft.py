#!/usr/bin/env python3
"""Pure static checker for the fail-closed G2L execution authorization draft."""
from __future__ import annotations

import hashlib
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_REL = "scripts/eval/fixtures/engram_g14_wasi_g2l_execution_authorization_draft_v0.json"
CHECKER_REL = "scripts/eval/check_engram_g14_wasi_g2l_execution_authorization_draft.py"
WRAPPER_REL = "scripts/check-engram-g14-wasi-g2l-execution-authorization-draft.sh"
DOC_REL = "docs/design/ENGRAM_G1_4_WASI_G2L_EXECUTION_AUTHORIZATION_DRAFT_2026_07_21.md"
UNSET = "UNSET_REQUIRES_OWNER_SIGNATURE"
HEX64 = re.compile(rb"[0-9a-f]{64}")
ZERO64 = b"0" * 64


def need(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(HEX64.sub(ZERO64, path.read_bytes())).hexdigest()


BASELINE = {"commit": "652c9e1a9ba148cd24a4fbc1987c9ab2a5d49c9e", "tree": "3b88a5a691db846c5a1bcb245779c149fa6017fc"}
WIT = {"path": "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit", "sha256": "d47b294dc4c7ee3f48d7af8a6233022a75e79533a2f554ec1299639ba3e142be", "package": "agent-bridge:g14-clock-probe@0.1.0", "world": "probe", "export": "typed-report: func() -> typed-report", "record": {"name": "typed-report", "fields_in_order": ["wall-epoch-seconds: u64", "logical-nanoseconds: u64", "quantum-nanoseconds: u64"]}, "abi_sha256": UNSET, "generated_bindings": "NOT_OBSERVED"}
RUST_TOOLS = {"rustc": {"absolute_path": "/Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/rustc", "version": "rustc 1.92.0 (ded5c06cf 2025-12-08)", "sha256": "12cab30aa9890d54445e29149a1e82d18fbe457de12801bd11bbe7e5e7fe33a0"}, "cargo": {"absolute_path": "/Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/cargo", "version": "cargo 1.92.0 (344c4567c 2025-10-21)", "sha256": "03e381389f5b7b8e695a744362f3866478f99034b2cf2df6afd4d42cfdab6f67"}}


def validate(fixture: dict[str, object]) -> None:
    need(fixture["schema"] == "agent_bridge.engram_g14_wasi_g2l_execution_authorization_draft.v0", "schema drift")
    need(fixture["status"] == "DRAFT_PROPOSED_NOT_AUTHORIZED", "status is not draft")
    need(fixture["baseline"] == BASELINE, "baseline drift")
    frozen = fixture["frozen_tuple"]
    need(frozen["source"] == BASELINE, "source tuple drift")
    need(frozen["wit"] == WIT, "canonical WIT contract drift")
    need(frozen["component"] == {"model_version": UNSET, "profile": UNSET, "adapter_absolute_path": UNSET, "adapter_sha256": UNSET}, "component or adapter populated")
    deps = frozen["dependencies"]
    need(deps == {"g2a_candidate_only": {"name": "wasmtime", "version": "46.0.1", "authorizes_dependency": False}, "complete_package_tuple": UNSET, "lockfile_absolute_path": UNSET, "lockfile_sha256": UNSET}, "dependency boundary drift")
    tools = frozen["toolchain"]
    need(tools["observed_direct"] == RUST_TOOLS, "direct Rust identity drift")
    need(tools["not_observed"] == ["wasm-tools", "wit-bindgen", "cargo-component", "wasm-ld"], "unobserved tool drift")
    need(tools["complete_name_path_version_sha256_tuple"] == UNSET and tools["path_lookup_allowed"] is False and tools["mutable_selector_allowed"] is False, "toolchain authorization drift")
    for key in ("commands", "locations", "outputs", "cache", "limits_and_environment", "receipt_schemas"):
        need(UNSET in str(frozen[key]), f"{key} placeholder removed")


def main() -> None:
    fixture = json.loads((ROOT / FIXTURE_REL).read_text(encoding="utf-8"))
    validate(fixture)

    owner = fixture["owner_approval"]
    need(owner["owner_approval_received"] is False, "owner approval claimed")
    need(all(value == UNSET for key, value in owner.items() if key != "owner_approval_received"), "owner signature field populated")
    review = fixture["independent_pre_execution_review"]
    need(review == {"required": True, "reviewer_identity": UNSET, "review_receipt_sha256": UNSET, "approved_exact_tuple": False, "completed": False}, "review boundary drift")

    controls = fixture["execution_controls"]
    need(all(value is True for value in controls.values()), "execution control weakened")
    receipts = fixture["receipt_requirements"]
    need(all(receipts[key] is True for key in receipts if key != "negative_evidence"), "receipt requirement weakened")
    need(set(receipts["negative_evidence"]) == {"zero_network_attempts", "zero_private_inputs", "zero_rustup", "zero_dependency_resolution", "zero_output_execution", "zero_runtime_admission", "zero_deploy_actions"}, "negative evidence drift")

    authority = fixture["authority"]
    required_closed = {"owner_approval_received", "execution_authorized", "dependency_resolution_allowed", "wit_generation_allowed", "linker_build_allowed", "component_build_allowed", "output_execution_allowed", "runtime_allowed", "deploy_allowed"}
    need(set(authority) == required_closed, "authority fields drift")
    need(all(value is False for value in authority.values()), "authority opened")
    need(fixture["pass_effect"] == {"opens_permissions": False, "execution_authority": False}, "PASS opens authority")
    need(fixture["only_allowed_successor"] == "FORMAL_OWNER_SIGNED_G2L_EXECUTION_AUTHORIZATION", "successor drift")

    mutations = [
        ("baseline", "commit", "0" * 40),
        ("frozen_tuple", "wit", "abi_sha256", "0" * 64),
        ("frozen_tuple", "wit", "export", "run: func()"),
        ("frozen_tuple", "dependencies", "g2a_candidate_only", "authorizes_dependency", True),
        ("frozen_tuple", "toolchain", "not_observed", []),
        ("authority", "execution_authorized", True),
        ("independent_pre_execution_review", "completed", True),
    ]
    for mutation in mutations:
        changed = copy.deepcopy(fixture)
        target = changed
        for key in mutation[:-2]:
            target = target[key]
        target[mutation[-2]] = mutation[-1]
        try:
            validate(changed)
            if mutation[0] == "authority":
                need(all(value is False for value in changed["authority"].values()), "authority opened")
            elif mutation[0] == "independent_pre_execution_review":
                need(changed["independent_pre_execution_review"] == review, "review boundary drift")
        except AssertionError:
            continue
        raise AssertionError(f"mutation accepted: {mutation[:-1]}")

    bindings = dict(fixture["static_bindings"])
    need(bindings.pop("algorithm") == "sha256_after_replacing_lowercase_64_hex_with_64_zeroes", "binding algorithm drift")
    need(set(bindings) == {DOC_REL, FIXTURE_REL, CHECKER_REL, WRAPPER_REL}, "binding file set drift")
    mismatches = []
    for relative, expected in bindings.items():
        need(re.fullmatch(r"[0-9a-f]{64}", expected) is not None, f"invalid binding: {relative}")
        actual = canonical_sha256(ROOT / relative)
        if actual != expected:
            mismatches.append(f"{relative} expected={expected} actual={actual}")
    need(not mismatches, "static binding drift: " + "; ".join(mismatches))

    checker_text = Path(__file__).read_text(encoding="utf-8")
    wrapper_text = (ROOT / WRAPPER_REL).read_text(encoding="utf-8")
    forbidden_apis = ("sub" + "process", "os." + "system", "os." + "popen", "pty." + "spawn", "exec" + "ve(", "spa" + "wn(")
    need(not any(token in checker_text for token in forbidden_apis), "checker process-launch surface")
    expected_wrapper = "#!/bin/sh\nset -eu\nexec python3 scripts/eval/check_engram_g14_wasi_g2l_execution_authorization_draft.py\n"
    need(wrapper_text == expected_wrapper, "wrapper must only exec checker")
    print(f"PASS G2L execution authorization DRAFT: proposed only; all execution authority closed; {len(mutations)} mutations rejected")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        print(f"FAIL G2L execution authorization DRAFT: {error}", file=sys.stderr)
        raise SystemExit(1)
