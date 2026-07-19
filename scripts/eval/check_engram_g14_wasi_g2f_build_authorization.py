#!/usr/bin/env python3
"""Fail-closed static checker for the G2F build-authorization decision."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2f_build_authorization_v0.json"
EXPECTED = {
 "docs/design/ENGRAM_G1_4_WASI_G2F_PUBLIC_SYNTHETIC_BUILD_AUTHORIZATION_2026_07_19.md",
 "docs/design/ENGRAM_G1_4_WASI_G2F_PUBLIC_SYNTHETIC_BUILD_AUTHORIZATION_RESULT_2026_07_19.md",
 "scripts/check-engram-g14-wasi-g2f-build-authorization.sh",
 "scripts/eval/README.md",
 "scripts/eval/check_engram_g14_wasi_g2f_build_authorization.py",
 "scripts/eval/engram_g14_wasi_g2f_build_authorization.py",
 "scripts/eval/fixtures/engram_g14_wasi_g2f_build_authorization_v0.json",
}

def require(ok: bool, message: str) -> None:
    if not ok: raise AssertionError(message)

def check(contract: dict) -> None:
    require(contract["gate"] == "G2F_PUBLIC_SYNTHETIC_BUILD_AUTHORIZATION_DECISION", "wrong gate")
    require(contract["mode"] == "PUBLIC_DECISION_NO_MANIFEST_NO_BUILD_NO_RUN", "wrong mode")
    p = contract["predecessor"]
    require((p["integration_commit"], p["integration_tree"], p["owner_authorization_post"]) == ("bae7bb7edb845ab477acf031582d6a8f61446597", "adfd0fb2421687d7b60301ea3c79d76f95050469", 4774), "bad predecessor or authority")
    require(all(value is False for value in contract["current_gate_scope"].values()), "G2F performed a forbidden action")
    s = contract["authorized_successor"]
    require(s["id"] == "G2G_PUBLIC_SYNTHETIC_HOST_BUILD" and s["build_authorized"] is True and s["run_authorized"] is False, "wrong build/run authority")
    require(s["network_authorized"] is False and s["dependency_authorized"] is False, "network or dependency widened")
    require(s["required_manifest"]["dependency_count"] == 0 and s["required_manifest"]["isolated_workspace"] is True, "fixture isolation weakened")
    require(s["required_source"]["sha256"] == "52f5f2adeed96e4d70b3ddb03d7793bac6f142b7eb8e125eb591eec4f1207343", "G2E source binding changed")
    require(s["allowed_paths_in_order"] == ["scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0/Cargo.toml", "scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0/Cargo.lock", "scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0/src/lib.rs"], "G2G path surface widened")
    t = contract["transition_rules"]
    require(t["G2G_success_authorizes_execution"] is False and t["G2G_success_authorizes_WIT_component_or_linker_dependency"] is False, "successor authority widened")

def check_docs() -> None:
    doc = (ROOT / "docs/design/ENGRAM_G1_4_WASI_G2F_PUBLIC_SYNTHETIC_BUILD_AUTHORIZATION_2026_07_19.md").read_text()
    result = (ROOT / "docs/design/ENGRAM_G1_4_WASI_G2F_PUBLIC_SYNTHETIC_BUILD_AUTHORIZATION_RESULT_2026_07_19.md").read_text()
    for marker in ("#4774", "G2G", "--offline", "--locked", "no WIT binding generation", "not authorize execution"):
        require(marker.lower() in doc.lower(), f"doc missing {marker}")
    require("**not** created" in result and "not produced an artifact" in result, "result overclaims action")

def check_surface() -> None:
    base = "bae7bb7edb845ab477acf031582d6a8f61446597"
    clean = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True) == ""
    if clean:
        paths = set(subprocess.check_output(["git", "diff", "--name-only", base, "HEAD"], cwd=ROOT, text=True).split())
        require(paths == EXPECTED, "changed path surface differs")

def mutations(original: dict) -> None:
    cases = [
      ("run", lambda c: c["authorized_successor"].__setitem__("run_authorized", True)),
      ("network", lambda c: c["authorized_successor"].__setitem__("network_authorized", True)),
      ("dependency", lambda c: c["authorized_successor"]["required_manifest"].__setitem__("dependency_count", 1)),
      ("path", lambda c: c["authorized_successor"]["allowed_paths_in_order"].append("Cargo.toml")),
      ("source", lambda c: c["authorized_successor"]["required_source"].__setitem__("sha256", "0" * 64)),
      ("gate-scope", lambda c: c["current_gate_scope"].__setitem__("fixture_or_component_built_or_run", True)),
      ("future-linker", lambda c: c["transition_rules"].__setitem__("G2G_success_authorizes_WIT_component_or_linker_dependency", True)),
    ]
    for name, mutate in cases:
        candidate = json.loads(json.dumps(original)); mutate(candidate)
        try: check(candidate)
        except AssertionError: continue
        raise AssertionError(f"mutation accepted: {name}")

def main() -> int:
    contract = json.loads(CONTRACT_PATH.read_text())
    check(contract); check_docs(); check_surface(); mutations(contract)
    print("PASS G2F build authorization: G2G host compile only; no run/dependency/linker authority")
    return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except (AssertionError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f"FAIL G2F build authorization: {error}", file=sys.stderr); raise SystemExit(1)
