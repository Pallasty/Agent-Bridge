#!/usr/bin/env python3
"""Validate G2C's public-static B0 evidence completion without granting authority."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
BASE_COMMIT = "135904ab64d369e5953ff5948a8c4231bf1eccf1"
BASE_TREE = "b0f63ed0bcc5faf2243cd181f3bcca658bc5abdf"
GATE = "G2C_PRE_SOURCE_EVIDENCE_COMPLETION_REVIEW"
NEXT_GATE = "G2D_PUBLIC_SOURCE_AUTHORIZATION_DECISION"
CONTRACT_PATH = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2c_pre_source_evidence_v0.json"
RELEASE_PATH = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2c_release_archive_receipt_v0.json"
RUSTSEC_PATH = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2c_rustsec_scan_receipt_v0.json"
COMPAT_PATH = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2c_static_compatibility_v0.json"
LOCK_PATH = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2a_minimal_Cargo.lock"
SCANNER_PATH = ROOT / "scripts/eval/engram_g14_wasi_g2c_rustsec_scan.py"
PRODUCER_PATH = ROOT / "scripts/eval/engram_g14_wasi_g2c_pre_source_evidence.py"
CHECKER_PATH = ROOT / "scripts/eval/check_engram_g14_wasi_g2c_pre_source_evidence.py"
WRAPPER_PATH = ROOT / "scripts/check-engram-g14-wasi-g2c-pre-source-evidence.sh"
DESIGN_PATH = ROOT / "docs/design/ENGRAM_G1_4_WASI_G2C_PRE_SOURCE_EVIDENCE_2026_07_19.md"
RESULT_PATH = ROOT / "docs/design/ENGRAM_G1_4_WASI_G2C_PRE_SOURCE_EVIDENCE_RESULT_2026_07_19.md"
README_PATH = ROOT / "scripts/eval/README.md"

EXPECTED_PATHS = {
    "docs/design/ENGRAM_G1_4_WASI_G2C_PRE_SOURCE_EVIDENCE_2026_07_19.md",
    "docs/design/ENGRAM_G1_4_WASI_G2C_PRE_SOURCE_EVIDENCE_RESULT_2026_07_19.md",
    "scripts/check-engram-g14-wasi-g2c-pre-source-evidence.sh",
    "scripts/eval/README.md",
    "scripts/eval/check_engram_g14_wasi_g2c_pre_source_evidence.py",
    "scripts/eval/engram_g14_wasi_g2c_pre_source_evidence.py",
    "scripts/eval/engram_g14_wasi_g2c_rustsec_scan.py",
    "scripts/eval/fixtures/engram_g14_wasi_g2c_pre_source_evidence_v0.json",
    "scripts/eval/fixtures/engram_g14_wasi_g2c_release_archive_receipt_v0.json",
    "scripts/eval/fixtures/engram_g14_wasi_g2c_rustsec_scan_receipt_v0.json",
    "scripts/eval/fixtures/engram_g14_wasi_g2c_static_compatibility_v0.json",
}

REQUIREMENTS = [
    "verified_release_archive_and_crate_payload_digests",
    "minimal_exact_crate_feature_graph",
    "complete_Cargo_lock_and_all_transitive_checksums",
    "target_triples_and_rust_toolchain_digest",
    "pinned_current_advisory_database_and_official_or_accepted_equivalent_audit_receipt",
    "exact_WIT_package_world_shape_and_binding_generator_static_compatibility",
    "direct_clock_and_poll_host_design_forbids_all_builtin_timer_paths",
]


class CheckError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def exact(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise CheckError(f"{label}: expected {expected!r}, observed {observed!r}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_text(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    require(completed.returncode == 0, f"git {' '.join(args)} failed")
    return completed.stdout


def validate_release(value: dict[str, Any], archive: Path | None) -> None:
    exact(value["schema"], "agent_bridge.engram_g14_wasi_g2c_release_archive_receipt.v0", "release schema")
    exact(value["repository"], "bytecodealliance/wasmtime", "release repository")
    exact(value["tag"], "v46.0.1", "release tag")
    exact(value["git_commit"], "823d1b8f251494a06288194d0df746191f535ff7", "release commit")
    exact(value["asset_name"], "wasmtime-v46.0.1-src.tar.gz", "release asset")
    exact(value["expected_size"], 152108252, "release expected size")
    exact(value["observed_size"], 152108252, "release observed size")
    exact(value["official_sha256"], "7c61526bc1b4099d8ac80a03d32e738387e7d76877321e473b8e6d5c82320532", "release official hash")
    exact(value["observed_sha256"], value["official_sha256"], "release observed hash")
    exact(value["complete_payload_verified"], True, "release complete payload")
    exact(value["archive_executed_or_extracted"], False, "release nonexecution")
    exact(value["source_or_build_authority"], False, "release authority")
    crates = value["inherited_crate_payloads"]
    exact([(row["name"], row["version"], row["sha256"]) for row in crates], [
        ("wasmtime", "46.0.1", "c4213d2f019a5e44aa8a61d8826dd33a505bff79f749b14a8bafd67321cb9351"),
        ("wasmtime-wasi", "46.0.1", "e9f65ef30a2c5478873cdb619085a7a649d3ce41cc3eaf298a7ce3dee96a8e11"),
        ("wasmtime-wasi-io", "46.0.1", "cee57d5fef4976b1ab542615f4cef2c43278eb549d8078939668ea0f13d5c696"),
    ], "crate payload pins")
    require(all(row["locally_verified_in_G2A"] is True for row in crates), "crate verification inheritance")
    if archive is not None:
        exact(archive.stat().st_size, value["observed_size"], "supplied release archive size")
        exact(sha256(archive), value["observed_sha256"], "supplied release archive hash")


def validate_rustsec(value: dict[str, Any]) -> None:
    exact(value["schema"], "agent_bridge.engram_g14_wasi_g2c_rustsec_scan_receipt.v0", "RustSec schema")
    scanner = value["scanner"]
    exact(scanner["unknown_syntax"], "FAIL_CLOSED_PARSE_ERROR", "RustSec unknown syntax")
    exact(scanner["cargo_audit_executed"], False, "cargo-audit nonclaim")
    exact(scanner["official_cargo_audit_receipt_claimed"], False, "official audit nonclaim")
    database = value["database"]
    exact(database["origin_url"], "https://github.com/RustSec/advisory-db.git", "RustSec origin")
    exact(database["commit"], "b5fc89b8be99e96f79194d8a6f11e9b4143b99f0", "RustSec commit")
    exact(database["tree"], "c943a47fee3f2b9767f664fd26c2cb6f0447b23d", "RustSec tree")
    exact(database["crate_advisory_file_count"], 1146, "RustSec advisory count")
    exact(database["worktree_clean"], True, "RustSec database worktree")
    lock = value["lockfile"]
    exact(lock["sha256"], "ad53efcd1ac44e8fa10e5943c873bc02cdceeae12d34784fbf60a6c81793db6d", "RustSec lock hash")
    exact((lock["package_instances"], lock["registry_package_instances"]), (115, 114), "RustSec package counts")
    result = value["result"]
    exact((result["matched_advisory_files_unique"], result["evaluated_package_advisory_pairs"]), (59, 60), "RustSec evaluation counts")
    exact(result["parse_error_count"], 0, "RustSec parse errors")
    exact(result["status_counts"], {"informational_finding": 0, "patched_or_unaffected": 60, "vulnerability": 0, "withdrawn": 0}, "RustSec statuses")
    exact(result["accepted_equivalent_static_scan_pass"], True, "RustSec accepted equivalent pass")
    exact(result["dependency_promotion_authority"], False, "RustSec authority")
    exact(value["parse_errors"], [], "RustSec parse error rows")
    exact(len(value["advisories"]), 60, "RustSec advisory rows")
    require(all(row["status"] == "patched_or_unaffected" for row in value["advisories"]), "RustSec hidden finding")


def validate_compat(value: dict[str, Any]) -> None:
    exact(value["schema"], "agent_bridge.engram_g14_wasi_g2c_static_compatibility.v0", "compat schema")
    exact(value["mode"], "PUBLIC_STATIC_NO_SOURCE_NO_BUILD_NO_RUN", "compat mode")
    exact(value["upstream"]["commit"], "823d1b8f251494a06288194d0df746191f535ff7", "compat upstream")
    bindgen = value["binding_generator"]
    exact(bindgen["api"], "wasmtime::component::bindgen!", "bindgen API")
    exact(bindgen["raw_sha256"], "24322565687cf99d6272b01fc887edc5b6cd58a8a012076029fd4c9e81e02cc7", "bindgen raw hash")
    exact(bindgen["static_public_api_compatible"], True, "bindgen static compatibility")
    exact(bindgen["bindings_compiled"], False, "bindgen compile nonclaim")
    exact([(row["package"], row["git_blob"]) for row in value["wit_packages"]], [
        ("wasi:clocks@0.2.12", "06b7d8b2579e4d1aae4b0a8a90b61adc001236f7"),
        ("wasi:io@0.2.12", "543cbfc62cfa3712628dc0adad54318a3f82cd48"),
    ], "WIT package pins")
    exact([row["raw_sha256"] for row in value["wit_packages"]], [
        "6ed8aa65bb8cbe224a0b2cbac9fc1b3bd25bdb17eda5ae0d23c983ed31c447cc",
        "96e206d00076fa0480df32c5bcf255a3fa4862805ac2f6b8537a781cce54f433",
    ], "WIT raw hashes")
    world = value["exact_world_design"]
    exact(world["imports_in_order"], ["wasi:clocks/wall-clock@0.2.12", "wasi:clocks/monotonic-clock@0.2.12", "wasi:io/poll@0.2.12"], "exact imports")
    for key in ("custom_wit_authored", "component_or_host_source_authored", "compiled_import_graph_observed"):
        exact(world[key], False, f"world nonclaim {key}")
    graph = value["minimal_graph"]
    exact(graph["lockfile_sha256"], "ad53efcd1ac44e8fa10e5943c873bc02cdceeae12d34784fbf60a6c81793db6d", "compat lock")
    exact(graph["excluded_packages"], ["wasmtime-wasi", "wasmtime-wasi-io", "tokio", "cap-time-ext", "system-interface"], "compat exclusions")
    exact(graph["resolver_only_no_compile"], True, "compat no compile")
    timer = value["direct_timer_host_design"]
    for key in ("single_logical_clock_authority", "exact_world_linker_only", "design_complete"):
        exact(timer[key], True, f"timer design {key}")
    for key in ("source_level_bypass_proven", "built_linker_bypass_proven"):
        exact(timer[key], False, f"timer nonclaim {key}")
    exact(timer["forbidden_paths"], ["wasmtime_wasi_broad_linker", "wasmtime_wasi_io_broad_linker", "tokio_time_sleep_or_instant", "ambient_host_clock_fallback", "native_or_qemu_fallback"], "timer forbidden paths")
    boundary = value["claim_boundary"]
    exact(boundary["B0_static_WIT_bindgen_compatibility_complete"], True, "B0 WIT close")
    exact(boundary["B0_direct_timer_design_complete"], True, "B0 timer close")
    exact(boundary["source_build_run_or_dependency_promotion_authority"], False, "compat authority")


def validate_contract(value: dict[str, Any]) -> None:
    exact(value["schema"], "agent_bridge.engram_g14_wasi_g2c_pre_source_evidence.v0", "schema")
    exact(value["gate"], GATE, "gate")
    exact(value["mode"], "PUBLIC_STATIC_NO_SOURCE_NO_BUILD_NO_RUN", "mode")
    exact(value["status"], "B0_PRE_SOURCE_EVIDENCE_COMPLETE_AWAITING_OWNER_SOURCE_AUTHORIZATION_NO_AUTHORITY", "status")
    predecessor = value["predecessor"]
    exact(predecessor["integration_commit"], "60e5c0f1bbfc15349b8e0c18d32fde594eeafac4", "predecessor integration")
    exact(predecessor["integration_tree"], "007079895d681860df88a2be943f1571ad1167cf", "predecessor tree")
    exact((predecessor["independent_manifest_post"], predecessor["closure_post"]), (4745, 4747), "predecessor posts")
    scope = value["scope"]
    exact(scope["authority_class"], "NONE_PUBLIC_STATIC_EVIDENCE_ONLY", "authority class")
    require(all(observed is False for key, observed in scope.items() if key != "authority_class"), "scope lock")
    rows = value["B0_requirements_in_order"]
    exact([row["id"] for row in rows], REQUIREMENTS, "B0 requirement order")
    require(all(row["state"].startswith("CLOSED_") for row in rows), "B0 requirement closure")
    receipts = value["evidence_receipts"]
    exact(receipts["release_archive"]["sha256"], sha256(RELEASE_PATH), "release receipt hash")
    exact(receipts["rustsec"]["sha256"], sha256(RUSTSEC_PATH), "RustSec receipt hash")
    exact(receipts["static_compatibility"]["sha256"], sha256(COMPAT_PATH), "compat receipt hash")
    exact(receipts["rustsec"]["cargo_audit_executed"], False, "contract cargo-audit nonclaim")
    barriers = value["barriers"]
    exact(barriers["B0_PRE_SOURCE"]["complete"], True, "B0 complete")
    exact(barriers["B0_PRE_SOURCE"]["current_state"], "PRE_SOURCE_EVIDENCE_COMPLETE_AWAITING_OWNER_SOURCE_AUTHORIZATION", "B0 state")
    exact(barriers["B0_PRE_SOURCE"]["completion_authorizes_source"], False, "B0 authority")
    exact(barriers["B1_POST_SOURCE_PRE_BUILD"]["complete"], False, "B1 incomplete")
    exact(barriers["B2_POST_BUILD_PRE_RUN"]["complete"], False, "B2 incomplete")
    transitions = value["transition_rules"]
    require(all(observed is True for key, observed in transitions.items() if key != "unknown_or_missing_evidence"), "transition locks")
    exact(transitions["unknown_or_missing_evidence"], "FAIL_CLOSED_NO_TRANSITION", "missing evidence")
    decision = value["decision"]
    exact(decision["verdict"], "G2C_B0_COMPLETE_AWAITING_OWNER_SOURCE_AUTHORIZATION_NO_SOURCE_NO_BUILD_NO_RUN", "verdict")
    require(all(observed is False for key, observed in decision.items() if key.endswith("_authorized")), "decision authority")
    exact(decision["only_permitted_successor"], NEXT_GATE, "successor")
    next_gate = value["next_gate"]
    exact(next_gate["id"], NEXT_GATE, "next gate")
    exact(next_gate["automatic_transition"], False, "automatic transition")
    require(all(observed is False for key, observed in next_gate.items() if key.startswith("may_")), "next gate authority")
    integrity = value["acceptance_integrity"]
    exact(integrity["checker_self_authenticating"], False, "checker self-authentication")
    require(all(observed is True for key, observed in integrity.items() if key != "checker_self_authenticating"), "integrity locks")


def mutation_checks(contract: dict[str, Any], release: dict[str, Any], rustsec: dict[str, Any], compat: dict[str, Any]) -> None:
    contract_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("source authored", lambda x: x["scope"].__setitem__("component_or_custom_host_source_authored", True)),
        ("WIT authored", lambda x: x["scope"].__setitem__("custom_WIT_authored", True)),
        ("dependency compiled", lambda x: x["scope"].__setitem__("dependency_installed_promoted_or_compiled", True)),
        ("binary executed", lambda x: x["scope"].__setitem__("downloaded_binary_executed", True)),
        ("B0 incomplete", lambda x: x["barriers"]["B0_PRE_SOURCE"].__setitem__("complete", False)),
        ("B0 grants source", lambda x: x["barriers"]["B0_PRE_SOURCE"].__setitem__("completion_authorizes_source", True)),
        ("B1 complete", lambda x: x["barriers"]["B1_POST_SOURCE_PRE_BUILD"].__setitem__("complete", True)),
        ("source authority", lambda x: x["decision"].__setitem__("source_build_run_or_dependency_promotion_authorized", True)),
        ("automatic transition", lambda x: x["next_gate"].__setitem__("automatic_transition", True)),
        ("next source early", lambda x: x["next_gate"].__setitem__("may_author_source_before_owner_decision", True)),
        ("receipt drift", lambda x: x["evidence_receipts"]["rustsec"].__setitem__("sha256", "0" * 64)),
        ("requirement hidden", lambda x: x["B0_requirements_in_order"].pop()),
        ("self auth", lambda x: x["acceptance_integrity"].__setitem__("checker_self_authenticating", True)),
    ]
    for label, mutate in contract_mutations:
        trial = copy.deepcopy(contract)
        mutate(trial)
        try:
            validate_contract(trial)
        except CheckError:
            continue
        raise CheckError(f"contract mutation accepted: {label}")
    receipt_trials: list[tuple[str, dict[str, Any], Callable[[dict[str, Any]], None], Callable[[dict[str, Any]], None]]] = [
        ("release hash", release, lambda x: x.__setitem__("observed_sha256", "0" * 64), lambda x: validate_release(x, None)),
        ("release executed", release, lambda x: x.__setitem__("archive_executed_or_extracted", True), lambda x: validate_release(x, None)),
        ("RustSec hidden vulnerability", rustsec, lambda x: x["advisories"][0].__setitem__("status", "vulnerability"), validate_rustsec),
        ("RustSec cargo-audit overclaim", rustsec, lambda x: x["scanner"].__setitem__("cargo_audit_executed", True), validate_rustsec),
        ("RustSec dirty database", rustsec, lambda x: x["database"].__setitem__("worktree_clean", False), validate_rustsec),
        ("WIT compiled overclaim", compat, lambda x: x["binding_generator"].__setitem__("bindings_compiled", True), validate_compat),
        ("timer source overclaim", compat, lambda x: x["direct_timer_host_design"].__setitem__("source_level_bypass_proven", True), validate_compat),
        ("fallback omitted", compat, lambda x: x["direct_timer_host_design"]["forbidden_paths"].pop(), validate_compat),
    ]
    for label, original, mutate, validate in receipt_trials:
        trial = copy.deepcopy(original)
        mutate(trial)
        try:
            validate(trial)
        except CheckError:
            continue
        raise CheckError(f"receipt mutation accepted: {label}")
    exact(len(contract_mutations) + len(receipt_trials), 21, "mutation count")


def validate_reproducibility(contract: dict[str, Any], rustsec_db: Path | None) -> None:
    spec = importlib.util.spec_from_file_location("g2c_producer", PRODUCER_PATH)
    require(spec is not None and spec.loader is not None, "producer import")
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    expected = producer.render(copy.deepcopy(contract))
    exact((expected["B0_requirement_count"], expected["B0_closed_requirement_count"]), (7, 7), "producer closure")
    exact(expected["source_build_run_or_dependency_promotion_authorized"], False, "producer authority")
    outputs: list[bytes] = []
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1"}
    for _ in range(2):
        completed = subprocess.run([sys.executable, str(PRODUCER_PATH)], cwd=ROOT, env=env, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        require(completed.returncode == 0 and completed.stderr == b"", "producer command")
        outputs.append(completed.stdout)
    exact(outputs[0], outputs[1], "producer determinism")
    exact(json.loads(outputs[0]), expected, "producer output")
    if rustsec_db is not None:
        spec = importlib.util.spec_from_file_location("g2c_rustsec", SCANNER_PATH)
        require(spec is not None and spec.loader is not None, "RustSec scanner import")
        scanner = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = scanner
        spec.loader.exec_module(scanner)
        observed = scanner.build_receipt(LOCK_PATH, rustsec_db.resolve())
        expected_receipt = json.loads(RUSTSEC_PATH.read_text(encoding="utf-8"))
        exact(observed, expected_receipt, "RustSec receipt reproduction")


def validate_scanner_positive_controls() -> None:
    spec = importlib.util.spec_from_file_location("g2c_rustsec_positive", SCANNER_PATH)
    require(spec is not None and spec.loader is not None, "RustSec positive-control import")
    scanner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = scanner
    spec.loader.exec_module(scanner)
    with tempfile.TemporaryDirectory(prefix="ab-g2c-rustsec-positive-") as directory:
        path = Path(directory) / "db/crates/wasmtime/RUSTSEC-TEST-0001.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            '```toml\n[advisory]\nid = "RUSTSEC-TEST-0001"\npackage = "wasmtime"\n\n[versions]\npatched = [">= 99.0.0"]\n```\n',
            encoding="utf-8",
        )
        row = scanner.advisory_row(path, "46.0.1")
        exact(row["status"], "vulnerability", "RustSec known-vulnerability positive control")
        try:
            scanner.requirement_matches(scanner.Version.parse("46.0.1"), "~46.0")
        except ValueError:
            pass
        else:
            raise CheckError("RustSec unknown-grammar positive control did not fail closed")


def validate_docs() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")
    result = RESULT_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    for token in (GATE, NEXT_GATE, "B0_PRE_SOURCE", "No authority", "owner source authorization"):
        require(token in design, f"design token {token}")
    for token in ("B0 complete", "No source", "No build", "No run", NEXT_GATE):
        require(token in result, f"result token {token}")
    require("G2C WASI pre-source evidence" in readme and NEXT_GATE in readme, "README section")
    for path in (WRAPPER_PATH, PRODUCER_PATH, SCANNER_PATH, CHECKER_PATH):
        require(path.stat().st_mode & 0o111 != 0, f"executable {path.name}")


def validate_surface(phase: str) -> None:
    status = git_text("status", "--porcelain=v1", "--untracked-files=all")
    if phase == "precommit":
        observed = {row[3:].split(" -> ")[-1] for row in status.splitlines() if len(row) >= 4}
    else:
        exact(status, "", "clean postcommit worktree")
        head = git_text("rev-parse", "HEAD").strip()
        require(head != BASE_COMMIT, "postcommit still at base")
        require(subprocess.run(["git", "merge-base", "--is-ancestor", BASE_COMMIT, head], cwd=ROOT).returncode == 0, "base ancestry")
        observed = set(git_text("diff", "--name-only", f"{BASE_COMMIT}..{head}").splitlines())
    exact(observed, EXPECTED_PATHS, f"{phase} path surface")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("precommit", "postcommit"), required=True)
    parser.add_argument("--release-archive", type=Path)
    parser.add_argument("--rustsec-db", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    exact(git_text("show", "-s", "--format=%T", BASE_COMMIT).strip(), BASE_TREE, "base tree")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    rustsec = json.loads(RUSTSEC_PATH.read_text(encoding="utf-8"))
    compat = json.loads(COMPAT_PATH.read_text(encoding="utf-8"))
    validate_release(release, args.release_archive)
    validate_rustsec(rustsec)
    validate_compat(compat)
    validate_contract(contract)
    mutation_checks(contract, release, rustsec, compat)
    validate_scanner_positive_controls()
    validate_reproducibility(contract, args.rustsec_db)
    validate_docs()
    residues = [path for path in (ROOT / "scripts/eval").rglob("*") if path.name == "__pycache__" or path.suffix == ".pyc"]
    exact(residues, [], "Python cache residue")
    validate_surface(args.phase)
    print("engram G2C WASI pre-source evidence: B0 complete; 21 semantic mutations rejected; awaiting owner source authorization; no source, build, run, dependency promotion, or authority")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CheckError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"engram G2C pre-source evidence: invalid: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
