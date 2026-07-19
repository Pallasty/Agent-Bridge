#!/usr/bin/env python3
"""Validate G2D's narrow owner-authorized G2E source boundary."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
BASE_COMMIT = "dd7b31d61c4d286e9d2076409db19051e0126907"
BASE_TREE = "5e806654b3a5c8ba41710e61a52e6198bfd07bc3"
CONTRACT_PATH = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2d_source_authorization_v0.json"
PRODUCER_PATH = ROOT / "scripts/eval/engram_g14_wasi_g2d_source_authorization.py"
CHECKER_PATH = ROOT / "scripts/eval/check_engram_g14_wasi_g2d_source_authorization.py"
WRAPPER_PATH = ROOT / "scripts/check-engram-g14-wasi-g2d-source-authorization.sh"
DESIGN_PATH = ROOT / "docs/design/ENGRAM_G1_4_WASI_G2D_SOURCE_AUTHORIZATION_2026_07_19.md"
RESULT_PATH = ROOT / "docs/design/ENGRAM_G1_4_WASI_G2D_SOURCE_AUTHORIZATION_RESULT_2026_07_19.md"
README_PATH = ROOT / "scripts/eval/README.md"
EXPECTED_PATHS = {
    "docs/design/ENGRAM_G1_4_WASI_G2D_SOURCE_AUTHORIZATION_2026_07_19.md",
    "docs/design/ENGRAM_G1_4_WASI_G2D_SOURCE_AUTHORIZATION_RESULT_2026_07_19.md",
    "scripts/check-engram-g14-wasi-g2d-source-authorization.sh",
    "scripts/eval/README.md",
    "scripts/eval/check_engram_g14_wasi_g2d_source_authorization.py",
    "scripts/eval/engram_g14_wasi_g2d_source_authorization.py",
    "scripts/eval/fixtures/engram_g14_wasi_g2d_source_authorization_v0.json",
}
ALLOWED_SOURCE_PATHS = [
    "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit",
    "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/component/src/lib.rs",
    "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/host/src/lib.rs",
]


class CheckError(RuntimeError):
    pass


def require(value: bool, label: str) -> None:
    if not value:
        raise CheckError(label)


def exact(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise CheckError(f"{label}: expected {expected!r}, observed {observed!r}")


def git_text(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, capture_output=True, text=True)
    require(completed.returncode == 0, f"git {' '.join(args)} failed")
    return completed.stdout


def validate_contract(value: dict[str, Any]) -> None:
    exact(value["schema"], "agent_bridge.engram_g14_wasi_g2d_source_authorization.v0", "schema")
    exact(value["gate"], "G2D_PUBLIC_SOURCE_AUTHORIZATION_DECISION", "gate")
    exact(value["mode"], "PUBLIC_DECISION_NO_SOURCE_NO_BUILD_NO_RUN", "mode")
    exact(value["status"], "SOURCE_AUTHORIZED_FOR_G2E_PUBLIC_SYNTHETIC_SOURCE_ONLY", "status")
    predecessor = value["predecessor"]
    exact(predecessor["integration_commit"], BASE_COMMIT, "predecessor commit")
    exact(predecessor["integration_tree"], BASE_TREE, "predecessor tree")
    exact((predecessor["closure_post"], predecessor["owner_authorization_post"]), (4758, 4759), "forum authority")
    require(all(observed is False for observed in value["current_gate_scope"].values()), "G2D execution scope")
    successor = value["authorized_successor"]
    exact(successor["id"], "G2E_PUBLIC_SYNTHETIC_SOURCE_AUTHORING", "successor")
    exact(successor["source_authoring_authorized"], True, "source authority")
    exact(successor["public_synthetic_only"], True, "public synthetic lock")
    exact(successor["allowed_source_paths_in_order"], ALLOWED_SOURCE_PATHS, "source path allowlist")
    exact(successor["allowed_non_source_artifact_classes"], ["bounded_static_checker", "deterministic_receipt_producer", "design_and_result_docs", "README_entry"], "non-source allowlist")
    exact(successor["forbidden_actions"], ["Cargo_toml_or_lockfile_change", "dependency_install_promotion_or_compile", "component_build_or_run", "downloaded_binary_execution", "candidate_private_or_capability_access", "runtime_store_MCP_policy_deploy_canary_or_G1_4_change", "native_or_QEMU_fallback"], "forbidden actions")
    world = value["frozen_world"]
    exact(world["name"], "agent-bridge:g14-clock-probe/probe@0.1.0", "world name")
    exact(world["imports_in_order"], ["wasi:clocks/wall-clock@0.2.12", "wasi:clocks/monotonic-clock@0.2.12", "wasi:io/poll@0.2.12"], "world imports")
    exact(world["forbidden_import_families"], ["wasi:cli", "wasi:filesystem", "wasi:random", "wasi:http", "wasi:sockets", "wasi:io/streams", "wasi_snapshot_preview1"], "forbidden imports")
    exact(value["B1_source_evidence_requirements"], ["fixed_SHA256_for_each_allowed_source_path", "exact_WIT_world_and_three_import_allowlist", "direct_logical_wall_monotonic_subscription_and_poll_source_markers", "forbidden_symbol_scan_for_broad_WASI_Tokio_ambient_and_fallback_paths", "no_manifest_lockfile_or_runtime_path_change", "public_synthetic_provenance_only"], "B1 requirements")
    rules = value["transition_rules"]
    for key in ("G2D_authorizes_only_G2E_source_authoring", "G2E_success_authorizes_build", "build_authorization_authorizes_run"):
        exact(rules[key], key == "G2D_authorizes_only_G2E_source_authoring", f"transition {key}")
    exact(rules["source_change_invalidates_B1_and_B2"], True, "source invalidation")
    exact(rules["unknown_or_missing_static_evidence"], "FAIL_CLOSED_NO_TRANSITION", "missing evidence")
    exact(rules["forbidden_action_or_path"], "FAIL_CLOSED_STOP_AND_PRESERVE_BRANCH", "forbidden action")
    next_gate = value["next_gate"]
    exact(next_gate, {"id": "G2E_PUBLIC_SYNTHETIC_SOURCE_AUTHORING", "build_or_run_authorized": False, "automatic_build_transition": False, "subsequent_build_gate": "G2F_PUBLIC_SYNTHETIC_BUILD_AUTHORIZATION_DECISION"}, "next gate")
    integrity = value["acceptance_integrity"]
    exact(integrity["checker_self_authenticating"], False, "self-auth")
    require(all(observed is True for key, observed in integrity.items() if key != "checker_self_authenticating"), "integrity")


def mutations(contract: dict[str, Any]) -> None:
    cases: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("current source", lambda x: x["current_gate_scope"].__setitem__("component_or_custom_host_source_authored", True)),
        ("current build", lambda x: x["current_gate_scope"].__setitem__("component_built_or_run", True)),
        ("Cargo allowed", lambda x: x["authorized_successor"]["forbidden_actions"].remove("Cargo_toml_or_lockfile_change")),
        ("source path expansion", lambda x: x["authorized_successor"]["allowed_source_paths_in_order"].append("crates/bridge/src/lib.rs")),
        ("source path order", lambda x: x["authorized_successor"]["allowed_source_paths_in_order"].reverse()),
        ("source authority removed", lambda x: x["authorized_successor"].__setitem__("source_authoring_authorized", False)),
        ("private allowed", lambda x: x["authorized_successor"]["forbidden_actions"].remove("candidate_private_or_capability_access")),
        ("extra import", lambda x: x["frozen_world"]["imports_in_order"].append("wasi:filesystem/types@0.2.12")),
        ("Tokio family removed", lambda x: x["frozen_world"]["forbidden_import_families"].pop()),
        ("build automatic", lambda x: x["next_gate"].__setitem__("automatic_build_transition", True)),
        ("G2E build authority", lambda x: x["transition_rules"].__setitem__("G2E_success_authorizes_build", True)),
        ("run authority", lambda x: x["transition_rules"].__setitem__("build_authorization_authorizes_run", True)),
        ("fail-open", lambda x: x["transition_rules"].__setitem__("unknown_or_missing_static_evidence", "CONTINUE")),
        ("self auth", lambda x: x["acceptance_integrity"].__setitem__("checker_self_authenticating", True)),
    ]
    for label, mutate in cases:
        trial = copy.deepcopy(contract)
        mutate(trial)
        try:
            validate_contract(trial)
        except CheckError:
            continue
        raise CheckError(f"semantic mutation accepted: {label}")
    exact(len(cases), 14, "mutation count")


def validate_receipt(contract: dict[str, Any]) -> None:
    spec = importlib.util.spec_from_file_location("g2d_producer", PRODUCER_PATH)
    require(spec is not None and spec.loader is not None, "producer import")
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    expected = producer.render(copy.deepcopy(contract))
    exact((expected["owner_authorization_post"], expected["G2E_source_path_count"], expected["source_authoring_authorized"], expected["build_or_run_authorized"]), (4759, 3, True, False), "receipt boundary")
    outputs = []
    for _ in range(2):
        done = subprocess.run([sys.executable, str(PRODUCER_PATH)], cwd=ROOT, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True)
        require(done.returncode == 0 and done.stderr == b"", "producer command")
        outputs.append(done.stdout)
    exact(outputs[0], outputs[1], "producer determinism")
    exact(json.loads(outputs[0]), expected, "producer receipt")


def validate_docs() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")
    result = RESULT_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    for token in ("G2D_PUBLIC_SOURCE_AUTHORIZATION_DECISION", "G2E_PUBLIC_SYNTHETIC_SOURCE_AUTHORING", "No `Cargo.toml`", "No `Cargo.toml`", "G2F_PUBLIC_SYNTHETIC_BUILD_AUTHORIZATION_DECISION"):
        require(token in design, f"design token {token}")
    for token in ("G2D_SOURCE_AUTHORIZED", "No source", "No build", "No run", "G2E_PUBLIC_SYNTHETIC_SOURCE_AUTHORING"):
        require(token in result, f"result token {token}")
    require("G2D WASI source authorization" in readme and "G2E_PUBLIC_SYNTHETIC_SOURCE_AUTHORING" in readme, "README")
    for path in (WRAPPER_PATH, PRODUCER_PATH, CHECKER_PATH):
        require(path.stat().st_mode & 0o111 != 0, f"executable {path.name}")


def validate_surface(phase: str) -> None:
    status = git_text("status", "--porcelain=v1", "--untracked-files=all")
    if phase == "precommit":
        observed = {row[3:].split(" -> ")[-1] for row in status.splitlines() if len(row) >= 4}
    else:
        exact(status, "", "clean postcommit worktree")
        head = git_text("rev-parse", "HEAD").strip()
        require(head != BASE_COMMIT, "postcommit at base")
        require(subprocess.run(["git", "merge-base", "--is-ancestor", BASE_COMMIT, head], cwd=ROOT).returncode == 0, "base ancestry")
        observed = set(git_text("diff", "--name-only", f"{BASE_COMMIT}..{head}").splitlines())
    exact(observed, EXPECTED_PATHS, f"{phase} surface")


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--phase" or sys.argv[2] not in {"precommit", "postcommit"}:
        raise CheckError("usage: checker --phase precommit|postcommit")
    exact(git_text("show", "-s", "--format=%T", BASE_COMMIT).strip(), BASE_TREE, "base tree")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    validate_contract(contract)
    mutations(contract)
    validate_receipt(contract)
    validate_docs()
    residues = [p for p in (ROOT / "scripts/eval").rglob("*") if p.name == "__pycache__" or p.suffix == ".pyc"]
    exact(residues, [], "Python residue")
    validate_surface(sys.argv[2])
    print("engram G2D WASI source authorization: 14 semantic mutations rejected; G2E public synthetic source only; no build, run, dependency, runtime, or authority expansion")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CheckError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"engram G2D source authorization: invalid: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
