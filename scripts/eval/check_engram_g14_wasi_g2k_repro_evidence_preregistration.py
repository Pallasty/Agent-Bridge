#!/usr/bin/env python3
"""Static G2K preregistration checker; deliberately never invokes Cargo."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2k_repro_evidence_preregistration_v0.json"
SOURCE = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/host/src/lib.rs"
G2F_AUTH = ROOT / "docs/design/ENGRAM_G1_4_WASI_G2F_PUBLIC_SYNTHETIC_BUILD_AUTHORIZATION_2026_07_19.md"
G2F_AMENDMENT = ROOT / "docs/design/ENGRAM_G1_4_WASI_G2F_ARTIFACT_EVIDENCE_AMENDMENT_2026_07_19.md"
FIXTURE_DIR = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0"


def need(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    plan = json.loads(FIXTURE.read_text())
    need(plan["gate"] == "G2K_G2G_REPRODUCIBILITY_EVIDENCE_PREREGISTRATION", "gate")
    need(plan["predecessor"]["r2_integration_commit"] == "8b4fc3c1", "R2 predecessor")
    need(hashlib.sha256(G2F_AUTH.read_bytes()).hexdigest() == plan["predecessor"]["g2f_authorization_document_sha256"], "G2F authorization binding")
    need(hashlib.sha256(G2F_AMENDMENT.read_bytes()).hexdigest() == plan["predecessor"]["g2f_artifact_evidence_amendment_sha256"], "G2F amendment binding")
    need(hashlib.sha256(SOURCE.read_bytes()).hexdigest() == plan["input_tuple"]["g2e_source_sha256"], "G2E source binding")
    toolchain = plan["input_tuple"]["toolchain"]
    expected_toolchain = {
        "rustc": {"absolute_path": "/Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/rustc", "sha256": "12cab30aa9890d54445e29149a1e82d18fbe457de12801bd11bbe7e5e7fe33a0", "version": "rustc 1.92.0 (ded5c06cf 2025-12-08)"},
        "cargo": {"absolute_path": "/Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/cargo", "sha256": "03e381389f5b7b8e695a744362f3866478f99034b2cf2df6afd4d42cfdab6f67", "version": "cargo 1.92.0 (344c4567c 2025-10-21)"},
    }
    need(toolchain == expected_toolchain, "toolchain binding")
    expected_fixture = {
        "fixture_manifest_sha256": "187cd13adf218f8bc3bc7f2fb83fe35e658af2b32346b55e1d7cd13746424253",
        "fixture_lockfile_sha256": "2be6ded55daea7c71b2f5c7be3446d3dc933a164da0c04cd764686bdce8cf89c",
        "fixture_wrapper_sha256": "9a34d87e2d9795c63e49abea5495e4860c649a0d718cf9f38b26b46749a48f0d",
    }
    need({key: plan["input_tuple"][key] for key in expected_fixture} == expected_fixture, "fixture receipt binding")
    need(hashlib.sha256((FIXTURE_DIR / "Cargo.toml").read_bytes()).hexdigest() == expected_fixture["fixture_manifest_sha256"], "fixture manifest drift")
    need(hashlib.sha256((FIXTURE_DIR / "Cargo.lock").read_bytes()).hexdigest() == expected_fixture["fixture_lockfile_sha256"], "fixture lock drift")
    need(hashlib.sha256((FIXTURE_DIR / "src/lib.rs").read_bytes()).hexdigest() == expected_fixture["fixture_wrapper_sha256"], "fixture wrapper drift")
    manifest = (FIXTURE_DIR / "Cargo.toml").read_text()
    wrapper = (FIXTURE_DIR / "src/lib.rs").read_text()
    need("[dependencies]" not in manifest and "rust-version = \"1.85\"" in manifest, "fixture dependency boundary")
    need('#[path = "../../engram_g14_wasi_g2e_public_source_v0/host/src/lib.rs"]' in wrapper and "pub use logical_clock_host::*;" in wrapper, "fixture source binding")
    expected_retry = {"independent_receipt_count": 2, "distinct_clean_worktrees": True, "clean_worktree_required": True, "fresh_target_per_receipt": True, "offline": True, "locked": True, "output_execution": False, "pre_post_toolchain_identity": True, "command_template": "CARGO_NET_OFFLINE=true /Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/cargo build --offline --locked --manifest-path scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0/Cargo.toml --target-dir <fresh-target-directory>"}
    need(plan["future_retry"] == expected_retry, "retry boundary")
    contract = plan["future_receipt_contract"]
    required_fields = ["absolute_worktree_path", "git_head", "git_tree", "absolute_manifest_path", "absolute_target_path", "expanded_command", "exit_code", "compile_succeeded", "g2e_source_sha256_pre", "g2e_source_sha256_post", "fixture_identity_pre", "fixture_identity_post", "toolchain_identity_pre", "toolchain_identity_post", "raw_artifact_sha256", "raw_artifact_sha_scope", "target_cleanup_confirmed", "negative_evidence", "fail_closed_reason"]
    fixture_identity_fields = ["manifest_sha256", "lockfile_sha256", "wrapper_sha256"]
    toolchain_fields = ["rustc_absolute_path", "rustc_sha256", "rustc_version", "cargo_absolute_path", "cargo_sha256", "cargo_version"]
    command_requirements = ["CARGO_NET_OFFLINE=true", "--offline", "--locked", "absolute_manifest_path", "absolute_target_path", "direct_cargo_absolute_path"]
    negative_fields = ["network_indication", "rustup_selector_reentry", "lockfile_mutation", "dependency_appearance", "output_execution"]
    pair_acceptance = {"different_absolute_worktree_paths": True, "different_absolute_target_paths": True, "equal_input_tuple_bindings": True, "each_receipt_g2e_identity_matches_frozen": True, "each_receipt_fixture_identity_matches_frozen": True, "each_receipt_toolchain_identity_matches_frozen": True, "both_exit_code_zero": True, "both_compile_succeeded": True, "both_target_cleanup_confirmed": True, "both_negative_evidence_clear": True, "raw_artifact_sha_equality_required": False, "normalized_artifact_digest": "UNDEFINED_NOT_AUTHORIZED"}
    need(contract == {"required_fields": required_fields, "fixture_identity_required_fields": fixture_identity_fields, "toolchain_identity_required_fields": toolchain_fields, "command_requirements": command_requirements, "negative_evidence_required_fields": negative_fields, "pair_acceptance": pair_acceptance}, "future receipt contract")
    artifact = plan["artifact_policy"]
    need(artifact == {"raw_artifact_sha_scope": "local_observation_only", "cross_worktree_raw_sha_comparison": False, "normalized_artifact_digest": "UNDEFINED_NOT_AUTHORIZED"}, "artifact policy")
    expected_forbidden = {"cargo_invoked", "network_accessed", "dependency_resolution", "g2g_retry", "wit_or_component", "execution", "runtime_or_deploy"}
    need(set(plan["current_actions"]) == expected_forbidden and all(v is False for v in plan["current_actions"].values()), "current action widened")
    print("PASS G2K preregistration: input-bound independent receipts; no raw rlib cross-worktree invariant")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f"FAIL G2K: {error}", file=sys.stderr)
        raise SystemExit(1)
