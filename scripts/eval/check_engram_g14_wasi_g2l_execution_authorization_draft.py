#!/usr/bin/env python3
"""Pure static checker for the fail-closed G2L execution authorization draft."""
from __future__ import annotations

import hashlib
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


def require_placeholders(value: object, path: str = "frozen_tuple") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            require_placeholders(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            require_placeholders(child, f"{path}[{index}]")
    elif isinstance(value, str) and ("UNSET" in value or path.startswith("frozen_tuple")):
        allowed_literals = {UNSET, "b086e221d5a6d83a218ae70118b0dcac53570d73", "ceb87fe2664d0c05d813bccd22edb51325a9c70b"}
        need(value in allowed_literals, f"real or invalid value at {path}")


def main() -> None:
    fixture = json.loads((ROOT / FIXTURE_REL).read_text(encoding="utf-8"))
    need(fixture["schema"] == "agent_bridge.engram_g14_wasi_g2l_execution_authorization_draft.v0", "schema drift")
    need(fixture["status"] == "DRAFT_PROPOSED_NOT_AUTHORIZED", "status is not draft")
    baseline = {"commit": "b086e221d5a6d83a218ae70118b0dcac53570d73", "tree": "ceb87fe2664d0c05d813bccd22edb51325a9c70b"}
    need(fixture["baseline"] == baseline, "baseline drift")
    need(fixture["frozen_tuple"]["source"] == baseline, "source tuple drift")
    require_placeholders(fixture["frozen_tuple"])

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
    print("PASS G2L execution authorization DRAFT: proposed only; all execution authority closed")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        print(f"FAIL G2L execution authorization DRAFT: {error}", file=sys.stderr)
        raise SystemExit(1)
