#!/usr/bin/env python3
"""Validate the fail-closed public-static G2A artifact compatibility review."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_COMMIT = "7873f24dddb6ed96e9ae9cb0358f6c5ff030a00d"
PREDECESSOR_COMMIT = "1f3f1d6a5f8873351b3483cea8cd4f8e3a1e86eb"
PREDECESSOR_TREE = "0bcc1bd507f65049fdee29f726e76340fd700dd5"
PREDECESSOR_FIXTURE = "scripts/eval/fixtures/engram_g14_wasi_clock_preregistration_v0.json"
PREDECESSOR_FIXTURE_SHA256 = "6c5a2f2d685b4aba8bf8392d6fb36b27d7fbccea87e5189c7cd95b15dacc3f9c"

CONTRACT_PATH = REPO_ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2a_artifact_compatibility_v0.json"
MANIFEST_PATH = REPO_ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2a_minimal_manifest_v0.toml"
LOCK_PATH = REPO_ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2a_minimal_Cargo.lock"
RUSTSEC_RECEIPT_PATH = REPO_ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2a_rustsec_bounded_receipt_v0.json"
PRODUCER_PATH = REPO_ROOT / "scripts/eval/engram_g14_wasi_g2a_artifact_compatibility.py"
CHECKER_PATH = REPO_ROOT / "scripts/eval/check_engram_g14_wasi_g2a_artifact_compatibility.py"
WRAPPER_PATH = REPO_ROOT / "scripts/check-engram-g14-wasi-g2a-artifact-compatibility.sh"
DESIGN_PATH = REPO_ROOT / "docs/design/ENGRAM_G1_4_WASI_G2A_ARTIFACT_COMPATIBILITY_REVIEW_2026_07_19.md"
RESULT_PATH = REPO_ROOT / "docs/design/ENGRAM_G1_4_WASI_G2A_ARTIFACT_COMPATIBILITY_RESULT_2026_07_19.md"
README_PATH = REPO_ROOT / "scripts/eval/README.md"

EXPECTED_PATHS = {
    "docs/design/ENGRAM_G1_4_WASI_G2A_ARTIFACT_COMPATIBILITY_REVIEW_2026_07_19.md",
    "docs/design/ENGRAM_G1_4_WASI_G2A_ARTIFACT_COMPATIBILITY_RESULT_2026_07_19.md",
    "scripts/check-engram-g14-wasi-g2a-artifact-compatibility.sh",
    "scripts/eval/README.md",
    "scripts/eval/check_engram_g14_wasi_g2a_artifact_compatibility.py",
    "scripts/eval/engram_g14_wasi_g2a_artifact_compatibility.py",
    "scripts/eval/fixtures/engram_g14_wasi_g2a_artifact_compatibility_v0.json",
    "scripts/eval/fixtures/engram_g14_wasi_g2a_minimal_Cargo.lock",
    "scripts/eval/fixtures/engram_g14_wasi_g2a_minimal_manifest_v0.toml",
    "scripts/eval/fixtures/engram_g14_wasi_g2a_rustsec_bounded_receipt_v0.json",
}

REQUIREMENTS = [
    "verified_release_archive_and_crate_payload_digests",
    "minimal_exact_crate_feature_graph",
    "complete_Cargo_lock_and_all_transitive_checksums",
    "target_triples_and_rust_toolchain_digest",
    "pinned_RustSec_database_commit_timestamp_and_raw_audit_receipt_hash",
    "exact_WIT_world_and_binding_generator_compatibility",
    "proof_that_direct_clock_and_poll_traits_bypass_all_builtin_host_timer_paths",
    "fixed_public_component_source_binary_and_import_manifest_digests",
    "custom_clock_and_poll_host_source_digest",
]
STATES = ["PARTIAL", "CLOSED_STATIC", "CLOSED_STATIC", "CLOSED_STATIC", "PARTIAL", "PARTIAL", "CONDITIONAL", "MISSING", "MISSING"]
VERDICT = "G2A_FAIL_CLOSED_UNSATISFIABLE_ARTIFACT_ORDER_NO_SOURCE_NO_BUILD_NO_RUN"
SUCCESSOR = "G2B_PUBLIC_WASI_ARTIFACT_ORDERING_REPAIR_PREREGISTRATION"
MANIFEST_SHA256 = "ec21411297f03e4c46d1c6520b86f2dca6309abc03069cf885ea9300a030dc54"
LOCK_SHA256 = "ad53efcd1ac44e8fa10e5943c873bc02cdceeae12d34784fbf60a6c81793db6d"
RUSTSEC_RECEIPT_SHA256 = "176434aad971db6ea455a4834c0e6a08dcf4c45c87a4b9e6bbb373d12b8fdb36"


class CheckError(RuntimeError):
    """Fail-closed semantic validation error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def exact(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise CheckError(f"{label}: expected {expected!r}, observed {observed!r}")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def git_bytes(*args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(completed.returncode == 0, f"git {' '.join(args)} failed")
    return completed.stdout


def git_text(*args: str) -> str:
    return git_bytes(*args).decode("utf-8")


def validate_contract(value: dict[str, Any]) -> None:
    exact(value["schema"], "agent_bridge.engram_g14_wasi_g2a_artifact_compatibility.v0", "schema")
    exact(value["gate"], "G2A_PUBLIC_WASI_ARTIFACT_AND_COMPONENT_COMPATIBILITY_EVIDENCE_REVIEW", "gate")
    exact(value["mode"], "PUBLIC_STATIC_NO_SOURCE_NO_BUILD_NO_RUN", "mode")
    exact(value["status"], "FAIL_CLOSED_UNSATISFIABLE_ARTIFACT_ORDER_NO_AUTHORITY", "status")

    predecessor = value["predecessor"]
    exact(predecessor["feature_commit"], PREDECESSOR_COMMIT, "predecessor feature")
    exact(predecessor["integration_commit"], "30da86c37caff6c2a3ca18cf2dcd564bdf750063", "predecessor integration")
    exact(predecessor["requirements_in_order"], REQUIREMENTS, "predecessor requirement order")
    exact(predecessor["missing_or_drifted_requirement"], "FAIL_CLOSED_NO_SOURCE_NO_BUILD_NO_RUN", "predecessor fail state")

    scope = value["scope"]
    exact(scope["authority_class"], "NONE", "authority class")
    for key, observed in scope.items():
        if key != "authority_class":
            exact(observed, False, f"scope lock {key}")

    release = value["official_release_evidence"]
    exact(release["tag"], "v46.0.1", "release tag")
    exact(release["git_commit"], "823d1b8f251494a06288194d0df746191f535ff7", "release commit")
    exact(release["github_release_id"], 344307162, "release id")
    exact(release["immutable"], True, "release immutable")
    exact(release["asset_count"], 38, "release asset count")
    exact(release["matching_custom_clock_component_asset_count"], 0, "matching release component")
    exact(release["official_prebuilt_component_closes_gap"], False, "prebuilt gap")
    archive = release["source_archive"]
    exact(archive["size"], 152108252, "source archive size")
    exact(archive["official_sha256"], "7c61526bc1b4099d8ac80a03d32e738387e7d76877321e473b8e6d5c82320532", "source archive digest")
    exact(archive["official_digest_observed"], True, "official digest observed")
    exact(archive["local_complete_payload_sha256_verified"], False, "local source archive nonclaim")

    crates = value["crate_payload_evidence"]
    exact([(row["name"], row["version"], row["sha256"]) for row in crates], [
        ("wasmtime", "46.0.1", "c4213d2f019a5e44aa8a61d8826dd33a505bff79f749b14a8bafd67321cb9351"),
        ("wasmtime-wasi", "46.0.1", "e9f65ef30a2c5478873cdb619085a7a649d3ce41cc3eaf298a7ce3dee96a8e11"),
        ("wasmtime-wasi-io", "46.0.1", "cee57d5fef4976b1ab542615f4cef2c43278eb549d8078939668ea0f13d5c696"),
    ], "crate rows")
    require(all(row["local_payload_verified"] is True for row in crates), "crate payload verification")

    deps = value["dependency_resolution_evidence"]
    exact(deps["resolver_only_no_compile"], True, "resolver no compile")
    exact(deps["manifest_path"], "scripts/eval/fixtures/engram_g14_wasi_g2a_minimal_manifest_v0.toml", "manifest path")
    exact(deps["manifest_sha256"], MANIFEST_SHA256, "manifest pin")
    exact(deps["lockfile_sha256"], LOCK_SHA256, "lock pin")
    exact(deps["package_stanza_count"], 115, "package count")
    exact(deps["registry_dependency_count"], 114, "registry count")
    exact(deps["forbidden_resolved_packages"], ["wasmtime-wasi", "wasmtime-wasi-io", "tokio", "cap-time-ext", "system-interface"], "forbidden package list")
    exact(deps["forbidden_resolved_package_count"], 0, "forbidden package count")
    exact(deps["agent_bridge_cargo_metadata_changed"], False, "Agent-Bridge cargo mutation")

    toolchain = value["toolchain_evidence"]
    exact(toolchain["rust_release"], "1.94.0", "Rust release")
    exact(toolchain["rustc_commit"], "4a4ef493e3a1488c6e321570238084b38948f6db", "rustc commit")
    exact(toolchain["channel_manifest_sha256"], "aaa177def36e01d539bee6bde95295230b9ce378f81057845db8d0ebe97898ee", "channel hash")
    exact((toolchain["host_target"], toolchain["guest_target"]), ("aarch64-apple-darwin", "wasm32-wasip2"), "targets")
    exact(toolchain["guest_target_installed"], False, "guest target noninstall")
    exact(toolchain["payloads_installed_by_this_review"], False, "toolchain noninstall")
    require(all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in toolchain["payload_sha256"].values()), "toolchain payload hashes")

    rustsec = value["rustsec_evidence"]
    exact(rustsec["advisory_db_commit"], "b5fc89b8be99e96f79194d8a6f11e9b4143b99f0", "RustSec commit")
    exact(rustsec["advisory_db_committer_timestamp"], "2026-07-17T15:52:38Z", "RustSec timestamp")
    exact(rustsec["receipt_path"], "scripts/eval/fixtures/engram_g14_wasi_g2a_rustsec_bounded_receipt_v0.json", "RustSec receipt path")
    exact(rustsec["raw_bounded_receipt_sha256"], RUSTSEC_RECEIPT_SHA256, "bounded receipt hash")
    exact(rustsec["scanner"], "bounded_ruby_rustsec_frontmatter_v0", "bounded scanner")
    exact((rustsec["advisory_count"], rustsec["audited_dependency_count"], rustsec["matched_advisory_file_count"], rustsec["vulnerability_count"], rustsec["warning_count"], rustsec["parse_error_count"]), (1146, 115, 59, 0, 0, 0), "bounded scan counts")
    exact(rustsec["cargo_audit_executed"], False, "cargo-audit nonclaim")
    exact(rustsec["official_cargo_audit_receipt_claimed"], False, "official audit receipt nonclaim")
    exact(rustsec["dependency_advisory_review_complete_for_pinned_db"], False, "advisory review incomplete")
    exact(rustsec["package_yank_review_complete"], False, "yank review")

    wit = value["wit_and_timer_path_evidence"]
    exact(wit["world"], "agent-bridge:g14-clock-probe/probe@0.1.0", "WIT world")
    exact(wit["exact_imports_in_order"], ["wasi:clocks/wall-clock@0.2.12", "wasi:clocks/monotonic-clock@0.2.12", "wasi:io/poll@0.2.12"], "WIT imports")
    exact(wit["exact_world_bindgen_public_api_source_verified"], True, "bindgen source support")
    exact(wit["broad_wasmtime_wasi_host_uses_tokio_timer_paths"], True, "Tokio timer finding")
    exact(wit["minimal_graph_excludes_broad_wasi_host"], True, "minimal graph finding")
    for key in ("bindings_compiled", "component_import_graph_observed", "actual_custom_host_direct_trait_bypass_verified"):
        exact(wit[key], False, f"WIT nonclaim {key}")

    causal = value["causal_order_audit"]
    for key in ("component_source_digest_requires_component_source", "component_binary_and_observed_import_manifest_require_build_or_accepted_prebuilt", "custom_host_source_digest_requires_custom_host_source"):
        exact(causal[key], True, f"causal fact {key}")
    for key in ("accepted_matching_prebuilt_exists", "ordered_gate_satisfiable_before_source", "missing_evidence_may_be_replaced_with_placeholder_digest"):
        exact(causal[key], False, f"causal lock {key}")

    rows = value["ordered_requirement_review"]
    exact([row["requirement"] for row in rows], REQUIREMENTS, "review requirement order")
    exact([row["state"] for row in rows], STATES, "review states")
    require(all(isinstance(row["reason"], str) and row["reason"] for row in rows), "review reasons")

    repair = value["ordering_repair_contract"]
    exact(repair["successor_is_public_static_and_no_run"], True, "repair mode")
    exact(repair["barriers_in_order"], [
        "PRE_SOURCE_STATIC_SUPPLY_CHAIN_EXACT_WORLD_AND_TIMER_PATH_DESIGN_EVIDENCE",
        "POST_AUTHORIZED_SOURCE_PRE_BUILD_COMPONENT_AND_HOST_SOURCE_DIGESTS",
        "POST_AUTHORIZED_BUILD_PRE_RUN_COMPONENT_BINARY_AND_OBSERVED_IMPORT_EXPORT_MANIFEST_DIGESTS",
    ], "repair barriers")
    exact(repair["g2b_authorizes_later_barrier_actions"], False, "repair authority")
    exact(repair["missing_or_drifted_barrier"], "FAIL_CLOSED_NO_NEXT_ACTION", "repair fail state")
    exact(repair["silent_native_or_qemu_fallback_allowed"], False, "fallback lock")

    decision = value["decision"]
    exact(decision["verdict"], VERDICT, "verdict")
    exact(decision["only_permitted_successor"], SUCCESSOR, "successor")
    for key, observed in decision.items():
        if key not in {"verdict", "only_permitted_successor"}:
            exact(observed, False, f"decision lock {key}")
    require(all(observed is False for observed in value["nonclaims"].values()), "nonclaims must remain false")
    integrity = value["acceptance_integrity"]
    exact(integrity["checker_self_authenticating"], False, "checker self-authentication")
    require(all(integrity[key] is True for key in integrity if key != "checker_self_authenticating"), "acceptance integrity")


def validate_lock(raw: bytes) -> None:
    exact(sha256_bytes(raw), LOCK_SHA256, "raw evidence lock hash")
    text = raw.decode("utf-8")
    require(text.startswith("# This file is automatically @generated by Cargo.\n# It is not intended for manual editing.\nversion = 4\n"), "lock header")
    stanzas = re.findall(r"(?ms)^\[\[package\]\]\n(.*?)(?=^\[\[package\]\]|\Z)", text)
    exact(len(stanzas), 115, "lock package stanza count")
    names: list[str] = []
    registry_count = 0
    for stanza in stanzas:
        name_match = re.search(r'^name = "([^"]+)"$', stanza, re.MULTILINE)
        require(name_match is not None, "lock package name")
        name = name_match.group(1)
        names.append(name)
        if 'source = "registry+https://github.com/rust-lang/crates.io-index"' in stanza:
            registry_count += 1
            require(re.search(r'^checksum = "[0-9a-f]{64}"$', stanza, re.MULTILINE) is not None, f"registry checksum {name}")
    exact(registry_count, 114, "lock registry package count")
    exact(names.count("engram-g14-wasi-g2a-host"), 1, "resolver root")
    for forbidden in ("wasmtime-wasi", "wasmtime-wasi-io", "tokio", "cap-time-ext", "system-interface"):
        exact(forbidden in names, False, f"forbidden lock package {forbidden}")
    wasmtime = next(stanza for stanza in stanzas if 'name = "wasmtime"\n' in stanza)
    require('version = "46.0.1"' in wasmtime, "wasmtime lock version")
    require('checksum = "c4213d2f019a5e44aa8a61d8826dd33a505bff79f749b14a8bafd67321cb9351"' in wasmtime, "wasmtime lock checksum")


def run_semantic_mutations(contract: dict[str, Any]) -> None:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("authority", lambda x: x["scope"].__setitem__("authority_class", "EXECUTE")),
        ("component source", lambda x: x["scope"].__setitem__("component_source_present", True)),
        ("build", lambda x: x["scope"].__setitem__("component_built_or_run", True)),
        ("dependency", lambda x: x["scope"].__setitem__("runtime_or_dependency_adopted", True)),
        ("archive overclaim", lambda x: x["official_release_evidence"]["source_archive"].__setitem__("local_complete_payload_sha256_verified", True)),
        ("prebuilt invented", lambda x: x["official_release_evidence"].__setitem__("matching_custom_clock_component_asset_count", 1)),
        ("forbidden dependency", lambda x: x["dependency_resolution_evidence"].__setitem__("forbidden_resolved_package_count", 1)),
        ("guest installed", lambda x: x["toolchain_evidence"].__setitem__("guest_target_installed", True)),
        ("audit finding hidden", lambda x: x["rustsec_evidence"].__setitem__("vulnerability_count", 1)),
        ("yank overclaim", lambda x: x["rustsec_evidence"].__setitem__("package_yank_review_complete", True)),
        ("binding compiled", lambda x: x["wit_and_timer_path_evidence"].__setitem__("bindings_compiled", True)),
        ("bypass overclaim", lambda x: x["wit_and_timer_path_evidence"].__setitem__("actual_custom_host_direct_trait_bypass_verified", True)),
        ("causality flipped", lambda x: x["causal_order_audit"].__setitem__("ordered_gate_satisfiable_before_source", True)),
        ("placeholder", lambda x: x["causal_order_audit"].__setitem__("missing_evidence_may_be_replaced_with_placeholder_digest", True)),
        ("missing promoted", lambda x: x["ordered_requirement_review"][7].__setitem__("state", "CLOSED_STATIC")),
        ("order changed", lambda x: x["ordered_requirement_review"].reverse()),
        ("repair authority", lambda x: x["ordering_repair_contract"].__setitem__("g2b_authorizes_later_barrier_actions", True)),
        ("fallback", lambda x: x["ordering_repair_contract"].__setitem__("silent_native_or_qemu_fallback_allowed", True)),
        ("gate passed", lambda x: x["decision"].__setitem__("g2a_passed", True)),
        ("source authorized", lambda x: x["decision"].__setitem__("source_build_or_run_authorized", True)),
        ("successor drift", lambda x: x["decision"].__setitem__("only_permitted_successor", "G2C")),
        ("nonclaim flipped", lambda x: x["nonclaims"].__setitem__("component_abi_compiled", True)),
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
    exact(len(mutations), 23, "mutation count")


def load_producer_module() -> Any:
    spec = importlib.util.spec_from_file_location("engram_g14_wasi_g2a", PRODUCER_PATH)
    require(spec is not None and spec.loader is not None, "producer import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_receipt(contract: dict[str, Any]) -> None:
    producer = load_producer_module()
    first = producer.render_receipt(copy.deepcopy(contract))
    second = producer.render_receipt(copy.deepcopy(contract))
    exact(first, second, "deterministic receipt")
    exact(first["contract_sha256"], sha256_bytes(canonical_json(contract)), "receipt contract hash")
    exact((first["requirement_count"], first["closed_count"], first["partial_count"], first["conditional_count"], first["missing_count"]), (9, 3, 3, 1, 2), "receipt counts")
    exact(first["ordered_gate_satisfiable_before_source"], False, "receipt causal result")
    exact(first["verdict"], VERDICT, "receipt verdict")
    exact(first["only_permitted_successor"], SUCCESSOR, "receipt successor")
    exact(first["authority_class"], "NONE", "receipt authority")
    command = [sys.executable, str(PRODUCER_PATH)]
    environment = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1"}
    outputs: list[bytes] = []
    for _ in range(2):
        completed = subprocess.run(command, cwd=REPO_ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        require(completed.returncode == 0, "producer command")
        exact(completed.stderr, b"", "producer stderr")
        require(completed.stdout.endswith(b"\n") and completed.stdout.count(b"\n") == 1, "producer framing")
        outputs.append(completed.stdout)
    exact(outputs[0], outputs[1], "command receipt determinism")
    exact(json.loads(outputs[0]), first, "command receipt")


def validate_predecessor() -> None:
    exact(git_text("show", "-s", "--format=%T", PREDECESSOR_COMMIT).strip(), PREDECESSOR_TREE, "predecessor tree")
    observed = sha256_bytes(git_bytes("show", f"{PREDECESSOR_COMMIT}:{PREDECESSOR_FIXTURE}"))
    exact(observed, PREDECESSOR_FIXTURE_SHA256, "predecessor fixture hash")


def validate_docs() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")
    result = RESULT_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    for token in (VERDICT, SUCCESSOR, "152,108,252", "cargo-audit", "causal"):
        require(token in design, f"design token {token}")
    for token in (VERDICT, SUCCESSOR, "No authority"):
        require(token in result, f"result token {token}")
    require("G2A artifact compatibility" in readme and SUCCESSOR in readme, "README G2A section")
    require(WRAPPER_PATH.stat().st_mode & 0o111 != 0, "wrapper executable")
    require(PRODUCER_PATH.stat().st_mode & 0o111 != 0, "producer executable")
    require(CHECKER_PATH.stat().st_mode & 0o111 != 0, "checker executable")


def validate_auxiliary_evidence() -> None:
    exact(sha256_bytes(MANIFEST_PATH.read_bytes()), MANIFEST_SHA256, "minimal manifest hash")
    manifest = MANIFEST_PATH.read_text(encoding="utf-8")
    require('wasmtime = { version = "=46.0.1", default-features = false, features = ["component-model", "cranelift", "runtime", "std"] }' in manifest, "minimal manifest dependency")
    exact(sha256_bytes(RUSTSEC_RECEIPT_PATH.read_bytes()), RUSTSEC_RECEIPT_SHA256, "RustSec receipt hash")
    receipt = json.loads(RUSTSEC_RECEIPT_PATH.read_bytes())
    exact(receipt["advisory_database"]["commit"], "b5fc89b8be99e96f79194d8a6f11e9b4143b99f0", "receipt database commit")
    exact(receipt["lockfile"]["sha256"], LOCK_SHA256, "receipt lock binding")
    exact((receipt["scanner"]["matched_advisory_files"], receipt["scanner"]["parse_errors"], receipt["scanner"]["vulnerability_findings"]), (59, 0, 0), "receipt bounded scan")
    exact(receipt["claim_boundary"]["cargo_audit_executed"], False, "receipt cargo-audit nonclaim")
    exact(receipt["claim_boundary"]["implementation_or_execution_authority"], False, "receipt authority")


def validate_surface(phase: str) -> None:
    status = git_text("status", "--porcelain=v1", "--untracked-files=all")
    if phase == "precommit":
        observed = {row[3:].split(" -> ")[-1] for row in status.splitlines() if len(row) >= 4}
    else:
        exact(status, "", "clean postcommit worktree")
        head = git_text("rev-parse", "HEAD").strip()
        require(head != BASE_COMMIT, "postcommit HEAD equals base")
        completed = subprocess.run(["git", "merge-base", "--is-ancestor", BASE_COMMIT, head], cwd=REPO_ROOT, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, check=False)
        require(completed.returncode == 0, "base ancestry")
        observed = set(git_text("diff", "--name-only", f"{BASE_COMMIT}..{head}").splitlines())
    exact(observed, EXPECTED_PATHS, f"{phase} path surface")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "--phase" or argv[1] not in {"precommit", "postcommit"}:
        raise CheckError("usage: checker --phase precommit|postcommit")
    contract = json.loads(CONTRACT_PATH.read_bytes())
    require(isinstance(contract, dict), "contract object")
    validate_contract(contract)
    validate_lock(LOCK_PATH.read_bytes())
    validate_auxiliary_evidence()
    mutated_lock = LOCK_PATH.read_bytes().replace(b'wasmtime\"\nversion = \"46.0.1', b'wasmtime\"\nversion = \"46.0.2', 1)
    try:
        validate_lock(mutated_lock)
    except CheckError:
        pass
    else:
        raise CheckError("raw lock mutation unexpectedly accepted")
    run_semantic_mutations(contract)
    validate_receipt(contract)
    validate_predecessor()
    validate_docs()
    residues = [path for path in (REPO_ROOT / "scripts/eval").rglob("*") if path.name == "__pycache__" or path.suffix == ".pyc"]
    exact(residues, [], "Python cache residue")
    validate_surface(argv[1])
    print("engram G2A WASI artifact compatibility: fail-closed contract valid; 23 semantic mutations and raw lock drift rejected; no source, build, run, or authority")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (CheckError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"engram G2A WASI artifact compatibility: invalid: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
