#!/usr/bin/env python3
"""Validate the fail-closed toolchain tuple review draft."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/eval/fixtures/engram_g14_wasi_toolchain_tuple_review_v0.json"
WIT = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit"
DOC = ROOT / "docs/design/ENGRAM_G1_4_WASI_TOOLCHAIN_TUPLE_REVIEW_DRAFT_2026_07_21.md"
CHECKER = ROOT / "scripts/eval/check_engram_g14_wasi_toolchain_tuple_review.py"
WRAPPER = ROOT / "scripts/check-engram-g14-wasi-toolchain-tuple-review.sh"


class CheckError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def exact(observed: Any, expected: Any, label: str) -> None:
    require(observed == expected, f"{label}: expected {expected!r}, observed {observed!r}")


def validate(value: dict[str, Any]) -> None:
    exact(value["schema"], "agent_bridge.engram_g14_wasi_toolchain_tuple_review.v0", "schema")
    exact(value["gate"], "OWNER_SIGNED_TOOLCHAIN_TUPLE_REVIEW", "gate")
    exact(value["status"], "DRAFT_PROPOSED_AWAITING_OWNER_SIGNATURE", "status")
    exact(value["mode"], "STATIC_DRAFT_NO_INSTALL_NO_DOWNLOAD_NO_BUILD_NO_RUN", "mode")
    exact(value["canonical_wit"]["sha256"], hashlib.sha256(WIT.read_bytes()).hexdigest(), "WIT hash")
    exact(value["canonical_wit"]["export"], "typed-report: func() -> typed-report", "WIT export")
    exact(value["recommendation"]["rust_release"], "1.94.0", "recommendation")
    exact(value["recommendation"]["selection_is_authorized"], False, "selection authority")
    candidate = value["candidate_tuple"]
    for name in ("wasm_tools", "wit_bindgen", "cargo_component", "wasm_ld"):
        exact(candidate[name], {"version": None, "sha256": None, "absolute_path": None}, f"missing {name}")
    exact(candidate["wasmtime"]["sha256"], None, "Wasmtime hash")
    exact(candidate["adapter"], {"identity": None, "sha256": None}, "adapter")
    exact(candidate["cache_roots"], None, "cache roots")
    exact(candidate["commands"], None, "commands")
    exact(candidate["expected_outputs"], None, "outputs")
    exact(value["signature"], {"owner": None, "signed_at": None, "tuple_sha256": None, "valid": False}, "signature")
    require(all(observed is False for observed in value["authority"].values()), "authority opened")
    exact(value["next_gate"]["automatic_transition"], False, "automatic transition")


def mutation_checks(value: dict[str, Any]) -> None:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("signature", lambda x: x["signature"].__setitem__("valid", True)),
        ("selection", lambda x: x["recommendation"].__setitem__("selection_is_authorized", True)),
        ("tool presence", lambda x: x["candidate_tuple"]["wasm_tools"].__setitem__("version", "1.0.0")),
        ("adapter", lambda x: x["candidate_tuple"]["adapter"].__setitem__("identity", "ambient")),
        ("commands", lambda x: x["candidate_tuple"].__setitem__("commands", ["cargo build"])),
        ("outputs", lambda x: x["candidate_tuple"].__setitem__("expected_outputs", {"binary": "x"})),
        ("authority", lambda x: x["authority"].__setitem__("build", True)),
        ("WIT export", lambda x: x["canonical_wit"].__setitem__("export", "probe.run: func()")),
        ("auto transition", lambda x: x["next_gate"].__setitem__("automatic_transition", True)),
    ]
    for label, mutate in mutations:
        trial = copy.deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except CheckError:
            continue
        raise CheckError(f"mutation accepted: {label}")
    exact(len(mutations), 9, "mutation count")


def main() -> int:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    validate(value)
    mutation_checks(value)
    require("awaiting owner signature" in DOC.read_text(encoding="utf-8"), "draft boundary")
    require(CHECKER.stat().st_mode & 0o111, "checker executable")
    require(WRAPPER.stat().st_mode & 0o111, "wrapper executable")
    print("engram toolchain tuple review: draft valid; owner signature absent; 9 mutations rejected; no authority")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CheckError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"engram toolchain tuple review: invalid: {exc}")
        raise SystemExit(2) from None
