#!/usr/bin/env python3
"""Validate the read-only G2A canonical-WIT/tooling preflight receipt."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2a_canonical_preflight_v0.json"
WIT = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit"
CHECKER = ROOT / "scripts/eval/check_engram_g14_wasi_g2a_canonical_preflight.py"
DOC = ROOT / "docs/design/ENGRAM_G1_4_WASI_G2A_CANONICAL_PREFLIGHT_2026_07_21.md"
WRAPPER = ROOT / "scripts/check-engram-g14-wasi-g2a-canonical-preflight.sh"


class CheckError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def exact(observed: Any, expected: Any, label: str) -> None:
    require(observed == expected, f"{label}: expected {expected!r}, observed {observed!r}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(value: dict[str, Any]) -> None:
    exact(value["schema"], "agent_bridge.engram_g14_wasi_g2a_canonical_preflight.v0", "schema")
    exact(value["gate"], "G2A_CANONICAL_WIT_TOOLING_PREFLIGHT", "gate")
    exact(value["mode"], "READ_ONLY_STATIC_OBSERVATION_NO_INSTALL_NO_DOWNLOAD_NO_BUILD_NO_RUN", "mode")
    exact(value["status"], "FAIL_CLOSED_TOOLING_TUPLE_NOT_READY", "status")
    exact(value["canonical_wit"]["path"], str(WIT.relative_to(ROOT)), "WIT path")
    exact(value["canonical_wit"]["sha256"], sha256(WIT), "WIT hash")
    exact(value["canonical_wit"]["package"], "agent-bridge:g14-clock-probe@0.1.0", "package")
    exact(value["canonical_wit"]["world"], "probe", "world")
    exact(value["canonical_wit"]["imports_in_order"], [
        "wasi:clocks/wall-clock@0.2.12",
        "wasi:clocks/monotonic-clock@0.2.12",
        "wasi:io/poll@0.2.12",
    ], "imports")
    exact(value["canonical_wit"]["export"], "typed-report: func() -> typed-report", "export")
    exact(value["canonical_wit"]["record_fields_in_order"], [
        "wall-epoch-seconds: u64", "logical-nanoseconds: u64", "quantum-nanoseconds: u64",
    ], "record fields")
    tools = value["tool_observations"]
    for name in ("rustc", "cargo"):
        require(tools[name]["observed_only"] is True, f"{name} observation boundary")
        require(len(tools[name]["sha256"]) == 64, f"{name} hash")
    exact(tools["missing_tools"], ["wasm-tools", "wit-bindgen", "cargo-component", "wasm-ld", "wasmtime"], "missing tools")
    exact(tools["missing_tools_are_authorized_to_install"], False, "install authority")
    drift = tools["historical_g2l_rust_tool_drift"]
    exact((drift["recorded_rust_release"], drift["current_observed_release"], drift["requires_new_signed_tuple"]), ("1.92.0", "1.94.0", True), "tool drift")
    authority = value["authority"]
    require(all(observed is False for observed in authority.values()), "authority opened")
    exact(value["next_gate"], {"id": "OWNER_SIGNED_TOOLCHAIN_TUPLE_REVIEW", "automatic_transition": False, "requires_explicit_owner_signature": True}, "next gate")
    negative = value["negative_evidence"]
    require(all(observed is False for observed in negative.values()), "negative evidence overclaim")


def mutation_checks(value: dict[str, Any]) -> None:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("WIT hash", lambda x: x["canonical_wit"].__setitem__("sha256", "0" * 64)),
        ("export", lambda x: x["canonical_wit"].__setitem__("export", "probe.run: func()")),
        ("record order", lambda x: x["canonical_wit"]["record_fields_in_order"].reverse()),
        ("tool install", lambda x: x["tool_observations"].__setitem__("missing_tools_are_authorized_to_install", True)),
        ("tool drift hidden", lambda x: x["tool_observations"]["historical_g2l_rust_tool_drift"].__setitem__("requires_new_signed_tuple", False)),
        ("authority", lambda x: x["authority"].__setitem__("build_authority", True)),
        ("automatic transition", lambda x: x["next_gate"].__setitem__("automatic_transition", True)),
        ("run evidence", lambda x: x["negative_evidence"].__setitem__("component_run", True)),
    ]
    for label, mutate in mutations:
        trial = copy.deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except CheckError:
            continue
        raise CheckError(f"mutation accepted: {label}")
    exact(len(mutations), 8, "mutation count")


def main() -> int:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    validate(value)
    mutation_checks(value)
    require("typed-report" in DOC.read_text(encoding="utf-8"), "canonical doc")
    require(CHECKER.stat().st_mode & 0o111, "checker executable")
    require(WRAPPER.stat().st_mode & 0o111, "wrapper executable")
    print("engram G2A canonical preflight: canonical WIT bound; tool tuple not ready; 8 mutations rejected; no authority")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CheckError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"engram G2A canonical preflight: invalid: {exc}")
        raise SystemExit(2) from None
