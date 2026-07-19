#!/usr/bin/env python3
"""Validate G2B's fail-closed three-barrier artifact-ordering repair."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_COMMIT = "bf46c1ef6463e32954f60362ae912037fda5d275"
BASE_TREE = "2c6821a8e948b81fe5ef72dd3f2ebbf849825637"
CONTRACT_PATH = REPO_ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2b_ordering_repair_v0.json"
PRODUCER_PATH = REPO_ROOT / "scripts/eval/engram_g14_wasi_g2b_ordering_repair.py"
CHECKER_PATH = REPO_ROOT / "scripts/eval/check_engram_g14_wasi_g2b_ordering_repair.py"
WRAPPER_PATH = REPO_ROOT / "scripts/check-engram-g14-wasi-g2b-ordering-repair.sh"
DESIGN_PATH = REPO_ROOT / "docs/design/ENGRAM_G1_4_WASI_G2B_ARTIFACT_ORDERING_REPAIR_2026_07_19.md"
RESULT_PATH = REPO_ROOT / "docs/design/ENGRAM_G1_4_WASI_G2B_ARTIFACT_ORDERING_REPAIR_RESULT_2026_07_19.md"
README_PATH = REPO_ROOT / "scripts/eval/README.md"

EXPECTED_PATHS = {
    "docs/design/ENGRAM_G1_4_WASI_G2B_ARTIFACT_ORDERING_REPAIR_2026_07_19.md",
    "docs/design/ENGRAM_G1_4_WASI_G2B_ARTIFACT_ORDERING_REPAIR_RESULT_2026_07_19.md",
    "scripts/check-engram-g14-wasi-g2b-ordering-repair.sh",
    "scripts/eval/README.md",
    "scripts/eval/check_engram_g14_wasi_g2b_ordering_repair.py",
    "scripts/eval/engram_g14_wasi_g2b_ordering_repair.py",
    "scripts/eval/fixtures/engram_g14_wasi_g2b_ordering_repair_v0.json",
}

STATES = [
    "PRE_SOURCE_EVIDENCE_INCOMPLETE",
    "PRE_SOURCE_EVIDENCE_COMPLETE_AWAITING_OWNER_SOURCE_AUTHORIZATION",
    "SOURCE_AUTHORIZED_NOT_YET_ATTESTED",
    "POST_SOURCE_PRE_BUILD_EVIDENCE_COMPLETE_AWAITING_OWNER_BUILD_AUTHORIZATION",
    "BUILD_AUTHORIZED_NOT_YET_ATTESTED",
    "POST_BUILD_PRE_RUN_EVIDENCE_COMPLETE_AWAITING_OWNER_RUN_AUTHORIZATION",
    "RUN_AUTHORIZED_BY_SEPARATE_GATE",
]
BARRIERS = ["B0_PRE_SOURCE", "B1_POST_SOURCE_PRE_BUILD", "B2_POST_BUILD_PRE_RUN"]
NEXT_GATE = "G2C_PRE_SOURCE_EVIDENCE_COMPLETION_REVIEW"


class CheckError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def exact(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise CheckError(f"{label}: expected {expected!r}, observed {observed!r}")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def git_text(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    require(completed.returncode == 0, f"git {' '.join(args)} failed")
    return completed.stdout


def validate_contract(value: dict[str, Any]) -> None:
    exact(value["schema"], "agent_bridge.engram_g14_wasi_g2b_ordering_repair.v0", "schema")
    exact(value["gate"], "G2B_PUBLIC_WASI_ARTIFACT_ORDERING_REPAIR_PREREGISTRATION", "gate")
    exact(value["mode"], "PUBLIC_STATIC_NO_SOURCE_NO_BUILD_NO_RUN", "mode")
    exact(value["status"], "ORDERING_REPAIR_PREREGISTERED_PRE_SOURCE_BARRIER_INCOMPLETE_NO_AUTHORITY", "status")

    predecessor = value["predecessor"]
    exact(predecessor["feature_commit"], BASE_COMMIT, "predecessor commit")
    exact(predecessor["feature_tree"], BASE_TREE, "predecessor tree")
    exact(predecessor["independent_manifest_post"], 4736, "predecessor manifest")
    exact(predecessor["closure_post"], 4738, "predecessor closure")
    exact(predecessor["only_permitted_successor"], value["gate"], "predecessor successor")

    scope = value["scope"]
    exact(scope["authority_class"], "NONE_STATIC_ORDERING_REPAIR_ONLY", "authority class")
    for key, observed in scope.items():
        if key != "authority_class":
            exact(observed, False, f"scope lock {key}")

    defect = value["defect_repaired"]
    exact(len(defect["causal_contradictions_in_order"]), 3, "causal contradiction count")
    exact(defect["single_impossible_barrier_replaced"], True, "barrier replacement")
    exact(defect["placeholder_or_predicted_digest_allowed"], False, "placeholder lock")
    exact(defect["missing_evidence_result"], "FAIL_CLOSED_NO_TRANSITION", "missing evidence result")
    exact(defect["barrier_green_implies_action_authority"], False, "green authority lock")

    exact(value["states_in_order"], STATES, "state order")
    exact(value["current_state"], STATES[0], "current state")
    barriers = value["barriers_in_order"]
    exact([row["id"] for row in barriers], BARRIERS, "barrier order")
    exact([row["currently_complete"] for row in barriers], [False, False, False], "barrier completion")
    exact([row["completion_authorizes_next_action"] for row in barriers], [False, False, False], "barrier authority")
    exact([row["next_action_requires"] for row in barriers], [
        "SEPARATE_OWNER_SOURCE_AUTHORIZATION_GATE",
        "SEPARATE_OWNER_BUILD_AUTHORIZATION_GATE",
        "SEPARATE_OWNER_RUN_AUTHORIZATION_GATE",
    ], "barrier authorization gates")
    exact(barriers[0]["inherited_g2a_states_in_order"], ["PARTIAL", "CLOSED_STATIC", "CLOSED_STATIC", "CLOSED_STATIC", "PARTIAL", "PARTIAL", "CONDITIONAL"], "B0 inherited states")
    require(len(barriers[0]["requirements_in_order"]) == 7, "B0 requirement count")
    require(len(barriers[1]["requirements_in_order"]) == 5, "B1 requirement count")
    require(len(barriers[2]["requirements_in_order"]) == 6, "B2 requirement count")

    mapping = value["original_requirement_mapping_in_order"]
    exact(len(mapping), 9, "original requirement mapping count")
    require(all(row["barrier"].startswith(("B0", "B1")) for row in mapping), "mapping barrier prefixes")
    exact(mapping[7]["barrier"], "B1_SOURCE_DIGEST_THEN_B2_BINARY_AND_MANIFEST", "split source/binary mapping")

    transitions = value["transition_rules"]
    for key in (
        "ordered_only_no_skips",
        "each_transition_requires_all_current_barrier_evidence",
        "each_risk_increasing_action_requires_separate_owner_authorization",
        "source_authorization_does_not_authorize_build",
        "build_authorization_does_not_authorize_run",
        "run_authorization_does_not_authorize_candidate_private_input",
        "upstream_pin_drift_invalidates_current_and_downstream_barriers",
        "source_change_invalidates_B1_and_B2",
        "build_input_change_invalidates_B2",
        "expired_advisory_snapshot_invalidates_B0_and_downstream",
    ):
        exact(transitions[key], True, f"transition rule {key}")
    exact(transitions["unknown_or_missing_evidence"], "FAIL_CLOSED_NO_TRANSITION", "unknown evidence rule")

    next_gate = value["next_gate"]
    exact(next_gate["id"], NEXT_GATE, "next gate")
    exact(next_gate["mode"], "PUBLIC_STATIC_NO_SOURCE_NO_BUILD_NO_RUN", "next gate mode")
    exact(next_gate["is_only_permitted_successor"], True, "unique successor")
    for key, observed in next_gate.items():
        if key.startswith("may_"):
            exact(observed, False, f"next gate authority {key}")

    integrity = value["acceptance_integrity"]
    exact(integrity["checker_self_authenticating"], False, "checker self authentication")
    require(all(value is True for key, value in integrity.items() if key != "checker_self_authenticating"), "acceptance integrity")


def mutation_checks(contract: dict[str, Any]) -> None:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("source authored", lambda x: x["scope"].__setitem__("component_or_host_source_authored", True)),
        ("dependency compiled", lambda x: x["scope"].__setitem__("dependency_installed_promoted_or_compiled", True)),
        ("run", lambda x: x["scope"].__setitem__("component_built_or_run", True)),
        ("fallback", lambda x: x["scope"].__setitem__("native_or_qemu_fallback_allowed", True)),
        ("placeholder", lambda x: x["defect_repaired"].__setitem__("placeholder_or_predicted_digest_allowed", True)),
        ("green authority", lambda x: x["defect_repaired"].__setitem__("barrier_green_implies_action_authority", True)),
        ("state skip", lambda x: x.__setitem__("current_state", STATES[3])),
        ("barrier reorder", lambda x: x["barriers_in_order"].reverse()),
        ("B0 complete", lambda x: x["barriers_in_order"][0].__setitem__("currently_complete", True)),
        ("B1 authority", lambda x: x["barriers_in_order"][1].__setitem__("completion_authorizes_next_action", True)),
        ("source gate removed", lambda x: x["barriers_in_order"][0].__setitem__("next_action_requires", "AUTO")),
        ("mapping collapse", lambda x: x["original_requirement_mapping_in_order"][7].__setitem__("barrier", "B0_PRE_SOURCE")),
        ("skip allowed", lambda x: x["transition_rules"].__setitem__("ordered_only_no_skips", False)),
        ("source authorizes build", lambda x: x["transition_rules"].__setitem__("source_authorization_does_not_authorize_build", False)),
        ("drift ignored", lambda x: x["transition_rules"].__setitem__("upstream_pin_drift_invalidates_current_and_downstream_barriers", False)),
        ("next source allowed", lambda x: x["next_gate"].__setitem__("may_author_component_or_host_source", True)),
        ("successor drift", lambda x: x["next_gate"].__setitem__("id", "G2D")),
        ("self auth", lambda x: x["acceptance_integrity"].__setitem__("checker_self_authenticating", True)),
    ]
    for label, mutate in mutations:
        trial = copy.deepcopy(contract)
        mutate(trial)
        try:
            validate_contract(trial)
        except CheckError:
            continue
        raise CheckError(f"semantic mutation unexpectedly accepted: {label}")
    exact(len(mutations), 18, "mutation count")


def validate_receipt(contract: dict[str, Any]) -> None:
    spec = importlib.util.spec_from_file_location("g2b_producer", PRODUCER_PATH)
    require(spec is not None and spec.loader is not None, "producer import")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = module.render(copy.deepcopy(contract))
    exact(expected["complete_barrier_count"], 0, "receipt complete barriers")
    exact(expected["source_build_run_authority"], False, "receipt authority")
    exact(expected["next_gate"], NEXT_GATE, "receipt successor")
    environment = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1"}
    outputs = []
    for _ in range(2):
        completed = subprocess.run([sys.executable, str(PRODUCER_PATH)], cwd=REPO_ROOT, env=environment, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        require(completed.returncode == 0 and completed.stderr == b"", "producer command")
        outputs.append(completed.stdout)
    exact(outputs[0], outputs[1], "receipt determinism")
    exact(json.loads(outputs[0]), expected, "receipt output")


def validate_docs() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")
    result = RESULT_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    for token in (NEXT_GATE, *BARRIERS, "No authority", "owner authorization"):
        require(token in design, f"design token {token}")
    for token in (NEXT_GATE, "No authority", "PRE_SOURCE_EVIDENCE_INCOMPLETE"):
        require(token in result, f"result token {token}")
    require("G2B WASI artifact ordering repair" in readme and NEXT_GATE in readme, "README section")
    for path in (WRAPPER_PATH, PRODUCER_PATH, CHECKER_PATH):
        require(path.stat().st_mode & 0o111 != 0, f"executable {path.name}")


def validate_surface(phase: str) -> None:
    status = git_text("status", "--porcelain=v1", "--untracked-files=all")
    if phase == "precommit":
        observed = {row[3:].split(" -> ")[-1] for row in status.splitlines() if len(row) >= 4}
    else:
        exact(status, "", "clean postcommit worktree")
        head = git_text("rev-parse", "HEAD").strip()
        require(head != BASE_COMMIT, "postcommit still at base")
        require(subprocess.run(["git", "merge-base", "--is-ancestor", BASE_COMMIT, head], cwd=REPO_ROOT).returncode == 0, "base ancestry")
        observed = set(git_text("diff", "--name-only", f"{BASE_COMMIT}..{head}").splitlines())
    exact(observed, EXPECTED_PATHS, f"{phase} path surface")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "--phase" or argv[1] not in {"precommit", "postcommit"}:
        raise CheckError("usage: checker --phase precommit|postcommit")
    exact(git_text("show", "-s", "--format=%T", BASE_COMMIT).strip(), BASE_TREE, "base tree")
    contract = json.loads(CONTRACT_PATH.read_bytes())
    validate_contract(contract)
    mutation_checks(contract)
    validate_receipt(contract)
    validate_docs()
    residues = [path for path in (REPO_ROOT / "scripts/eval").rglob("*") if path.name == "__pycache__" or path.suffix == ".pyc"]
    exact(residues, [], "Python cache residue")
    validate_surface(argv[1])
    print("engram G2B WASI ordering repair: three barriers valid; 18 semantic mutations rejected; pre-source incomplete; no source, build, run, or authority")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (CheckError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"engram G2B ordering repair: invalid: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
