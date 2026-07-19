#!/usr/bin/env python3
"""Static integrity checker for the owner-authorized G2E source-only lane."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0.json"
SOURCE_PATHS = [
    "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit",
    "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/component/src/lib.rs",
    "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/host/src/lib.rs",
]
CHANGED_PATHS = set(SOURCE_PATHS + [
    "docs/design/ENGRAM_G1_4_WASI_G2E_PUBLIC_SYNTHETIC_SOURCE_2026_07_19.md",
    "docs/design/ENGRAM_G1_4_WASI_G2E_PUBLIC_SYNTHETIC_SOURCE_RESULT_2026_07_19.md",
    "scripts/check-engram-g14-wasi-g2e-public-synthetic-source.sh",
    "scripts/eval/README.md",
    "scripts/eval/check_engram_g14_wasi_g2e_public_source.py",
    "scripts/eval/engram_g14_wasi_g2e_public_source.py",
    "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0.json",
])


def fail(message: str) -> None:
    raise AssertionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(relative: str) -> str:
    return (ROOT / relative).read_text()


def require(value: bool, message: str) -> None:
    if not value:
        fail(message)


def check_contract() -> dict:
    contract = json.loads(CONTRACT_PATH.read_text())
    require(contract["gate"] == "G2E_PUBLIC_SYNTHETIC_SOURCE_AUTHORING", "wrong gate")
    require(contract["mode"] == "PUBLIC_SYNTHETIC_SOURCE_ONLY_NO_DEPENDENCY_NO_BUILD_NO_RUN", "wrong mode")
    require(contract["predecessor"]["integration_commit"] == "32c9edcd982bfd4989562c12d83206913c6452e1", "wrong G2D predecessor")
    withdrawn = contract["supersedes_withdrawn_candidate"]
    require(withdrawn["commit"] == "b4cbfeda5d1e6446e7796cf37c12ce7683a83ce9", "withdrawn candidate not bound")
    require(withdrawn["withdrawal_post"] == 4768 and withdrawn["evidence_status"] == "withdrawn_not_used_for_G2E_acceptance", "withdrawal boundary weakened")
    require(contract["source_paths_in_order"] == SOURCE_PATHS, "source path surface changed")
    require(contract["B1"]["complete"] is True and contract["B1"]["completion_authorizes_build"] is False, "B1 boundary widened")
    require(contract["decision"]["only_permitted_successor"] == "G2F_PUBLIC_SYNTHETIC_BUILD_AUTHORIZATION_DECISION", "wrong successor")
    require(all(value is False for value in contract["scope"].values()), "scope widened")
    required_false = ["compiled_bindings_or_import_manifest_proven", "built_linker_timer_isolation_proven", "component_built_or_run"]
    require(all(contract["source_level_claims"][key] is False for key in required_false), "static claim promoted to build proof")
    keys = ["world_wit", "component_lib_rs", "host_lib_rs"]
    for key, relative in zip(keys, SOURCE_PATHS):
        require(contract["source_sha256"][key] == sha(ROOT / relative), f"hash mismatch: {relative}")
    return contract


def check_source() -> None:
    wit = text(SOURCE_PATHS[0])
    expected_wit = [
        "package agent-bridge:g14-clock-probe@0.1.0;",
        "import wasi:clocks/wall-clock@0.2.12;",
        "import wasi:clocks/monotonic-clock@0.2.12;",
        "import wasi:io/poll@0.2.12;",
        "export typed-report: func() -> typed-report;",
    ]
    require(all(marker in wit for marker in expected_wit), "WIT is not the exact three-interface world")
    require(wit.index(expected_wit[1]) < wit.index(expected_wit[2]) < wit.index(expected_wit[3]), "WIT import order changed")
    require(wit.count("import wasi:") == 3, "WIT import surface expanded")
    for forbidden in ("filesystem", "sockets", "random", "http", "cli", "streams", "preview1"):
        require(forbidden not in wit, f"forbidden WIT family: {forbidden}")

    component = text(SOURCE_PATHS[1])
    for marker in ("public synthetic component source", "source-only", "#![forbid(unsafe_code)]", "WALL_EPOCH_SECONDS", "QUANTUM_NANOSECONDS", "pub fn typed_report"):
        require(marker.lower() in component.lower(), f"component missing {marker}")
    for forbidden in ("bindgen", "wasmtime", "tokio", "std::time", "Command", "include_bytes", "compile"):
        require(forbidden not in component, f"component contains forbidden {forbidden}")

    host = text(SOURCE_PATHS[2])
    required_host = ("LogicalClockHost", "wall_clock_now", "monotonic_clock_now", "subscribe_duration", "subscribe_instant", "pub fn poll", "checked_add", "No host wait")
    require(all(marker in host for marker in required_host), "host lacks direct clock/poll semantics")
    forbidden_host = ("wasmtime_wasi", "wasmtime-wasi", "tokio", "WasiCtx", "add_to_linker", "std::time", "SystemTime", "Instant", "sleep", "thread::", "Command", "Tcp", "Udp", "File", "rand", "wasi_snapshot_preview1", "wasi:filesystem", "wasi:http", "wasi:sockets", "wasi:random", "wasi:cli", "wasi:io/streams", "QEMU")
    for forbidden in forbidden_host:
        require(forbidden not in host, f"host contains forbidden {forbidden}")


def check_docs() -> None:
    doc = text("docs/design/ENGRAM_G1_4_WASI_G2E_PUBLIC_SYNTHETIC_SOURCE_2026_07_19.md")
    result = text("docs/design/ENGRAM_G1_4_WASI_G2E_PUBLIC_SYNTHETIC_SOURCE_RESULT_2026_07_19.md")
    for marker in ("#4759", "G2D", "G2E", "G2F", "source-only", "no build", "static"):
        require(marker in doc.lower() or marker in doc, f"design doc missing {marker}")
    require("NOT compiled, linked, or run" in result, "result overclaims build evidence")


def changed_paths_against(base: str) -> set[str]:
    output = subprocess.check_output(["git", "diff", "--name-only", base, "HEAD"], cwd=ROOT, text=True)
    return {line for line in output.splitlines() if line}


def check_surface() -> None:
    base = "32c9edcd982bfd4989562c12d83206913c6452e1"
    clean = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True) == ""
    if clean and subprocess.run(["git", "cat-file", "-e", f"{base}^{{commit}}"], cwd=ROOT).returncode == 0:
        require(changed_paths_against(base) == CHANGED_PATHS, "committed changed-path surface differs")


def mutation_tests() -> None:
    checks = [
        ("hash", lambda c: c["source_sha256"].__setitem__("world_wit", "0" * 64)),
        ("wit-family", None),
        ("host-poll", None),
        ("host-tokio", None),
        ("build-proof", lambda c: c["source_level_claims"].__setitem__("component_built_or_run", True)),
        ("build-authority", lambda c: c["B1"].__setitem__("completion_authorizes_build", True)),
        ("path-expansion", lambda c: c["source_paths_in_order"].append("Cargo.toml")),
        ("cargo-scope", lambda c: c["scope"].__setitem__("Cargo_toml_or_lockfile_changed", True)),
    ]
    original_contract = CONTRACT_PATH.read_text()
    original_wit = (ROOT / SOURCE_PATHS[0]).read_text()
    original_host = (ROOT / SOURCE_PATHS[2]).read_text()
    try:
        for name, mutate in checks:
            if name == "wit-family":
                (ROOT / SOURCE_PATHS[0]).write_text(original_wit + "\n  import wasi:random/random@0.2.12;\n")
            elif name == "host-poll":
                (ROOT / SOURCE_PATHS[2]).write_text(original_host.replace("pub fn poll", "fn poll", 1))
            elif name == "host-tokio":
                (ROOT / SOURCE_PATHS[2]).write_text(original_host + "\n// tokio\n")
            else:
                candidate = json.loads(original_contract)
                mutate(candidate)
                CONTRACT_PATH.write_text(json.dumps(candidate, indent=2) + "\n")
            try:
                check_contract(); check_source()
            except AssertionError:
                pass
            else:
                fail(f"mutation accepted: {name}")
            CONTRACT_PATH.write_text(original_contract)
            (ROOT / SOURCE_PATHS[0]).write_text(original_wit)
            (ROOT / SOURCE_PATHS[2]).write_text(original_host)
    finally:
        CONTRACT_PATH.write_text(original_contract)
        (ROOT / SOURCE_PATHS[0]).write_text(original_wit)
        (ROOT / SOURCE_PATHS[2]).write_text(original_host)


def main() -> int:
    check_contract()
    check_source()
    check_docs()
    check_surface()
    mutation_tests()
    print("PASS G2E public synthetic source: static-only, no build/run authority")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f"FAIL G2E public synthetic source: {error}", file=sys.stderr)
        raise SystemExit(1)
