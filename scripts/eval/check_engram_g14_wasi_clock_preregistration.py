#!/usr/bin/env python3
"""Fail-closed semantic checker for the public-static G2 WASI clock contract."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_COMMIT = "c4b3ffe89d1a9fc8adb55a6df8495e3c6bfbd7bc"
PREDECESSOR_COMMIT = "3ba3a2a6e166f9272acdf48e5bc6d19779a6b3ac"
PREDECESSOR_TREE = "b56b317d6af4e9eaaa95f98188b2d97a4c1fabb0"
CONTRACT_PATH = (
    REPO_ROOT
    / "scripts/eval/fixtures/engram_g14_wasi_clock_preregistration_v0.json"
)
CANONICAL_WIT_PATH = (
    REPO_ROOT
    / "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit"
)
CANONICAL_WIT_SHA256 = (
    "d47b294dc4c7ee3f48d7af8a6233022a75e79533a2f554ec1299639ba3e142be"
)
PRODUCER_PATH = REPO_ROOT / "scripts/eval/engram_g14_wasi_clock_preregistration.py"
DESIGN_PATH = (
    REPO_ROOT / "docs/design/ENGRAM_G1_4_WASI_CLOCK_PREREGISTRATION_2026_07_19.md"
)
RESULT_PATH = (
    REPO_ROOT
    / "docs/design/ENGRAM_G1_4_WASI_CLOCK_PREREGISTRATION_RESULT_2026_07_19.md"
)
WRAPPER_PATH = REPO_ROOT / "scripts/check-engram-g14-wasi-clock-preregistration.sh"

EXPECTED_PATHS = {
    "docs/design/ENGRAM_G1_4_WASI_CLOCK_PREREGISTRATION_2026_07_19.md",
    "scripts/eval/check_engram_g14_wasi_clock_preregistration.py",
    "scripts/eval/fixtures/engram_g14_wasi_clock_preregistration_v0.json",
}

EXPECTED_DOC_HASHES = {
    "design": "44fd63ce4f03b98e82dd08b0989b360da7cfccc95f169eaa0353d45cf15dd47c",
    "result": "850a457667a0164c97d79ced53392478e26078229c0d9eced28142a686caaf10",
}

EXPECTED_PREDECESSOR_HASHES = {
    "docs/design/ENGRAM_G1_4_STRONG_CLOCK_ISOLATION_PRIMITIVE_REVIEW_2026_07_18.md": "c51e80e151b4185026079db70d191d119fb4a460dfa026fd436629d88dc3433c",
    "docs/design/ENGRAM_G1_4_STRONG_CLOCK_ISOLATION_PRIMITIVE_REVIEW_RESULT_2026_07_18.md": "cb7fc17dea9c3b19633fb8407ce6830421f7cb142f4916fa97d72f5e8b07f758",
    "scripts/check-engram-g14-strong-clock-isolation-review.sh": "ea6c2154ec54d0080c8e3a51af42494789c0e7bdaf35c0158c3bb9d00588958d",
    "scripts/eval/README.md": "1725fb6cd321bc4f74d4328cc318a1dfab2112f56ec8cff00c04d08b7ae1859d",
    "scripts/eval/check_engram_g14_strong_clock_isolation_review.py": "184b1fe43269c4707babb9ca7674e14f1e908c7afc243213f35b6d358a69efb2",
    "scripts/eval/engram_g14_strong_clock_isolation_review.py": "66a5f294e96acfe89f7dc9f51c4e582b6893721863caefe0720ad25a07668add",
    "scripts/eval/fixtures/engram_g14_strong_clock_isolation_review_v0.json": "c85816a2b581fb5f63873e48032c74de13fd3632115d6cb041bf95fc37b4840c",
}

EXPECTED_PREDECESSOR = {
    "accepted_review_feature_commit": PREDECESSOR_COMMIT,
    "accepted_review_feature_tree": PREDECESSOR_TREE,
    "integrated_master_commit": "d59ea47c66387720ebb016e0c61b6e9c84faeaae",
    "accepted_review_verdict": "DESIGN_ROUTE_SELECTED_NO_AUTHORITY",
    "only_permitted_successor": "G2_WASI_PREREGISTRATION",
}

EXPECTED_SCOPE = {
    "public_sources_only": True,
    "static_preregistration_only": True,
    "review_targets_pinned": True,
    "runtime_dependency_selected_or_installed": False,
    "component_source_authored": False,
    "bindings_generated": False,
    "component_abi_sha256_observed": False,
    "component_built_or_executed": False,
    "custom_clock_or_poll_host_implemented": False,
    "host_policy_applied": False,
    "candidate_private_or_capability_material_accessed": False,
    "runtime_store_mcp_or_deploy_changed": False,
    "frozen_wall_clock_deny_canary_changed": False,
    "g1_4_execution_open": False,
    "authority_class": "NONE_STATIC_PREREGISTRATION_ONLY",
}

EXPECTED_ACCEPTANCE_INTEGRITY = {
    "checker_self_authenticating": False,
    "standalone_checker_result_is_acceptance_authority": False,
    "independent_read_only_review_required": True,
    "independent_out_of_band_commit_and_file_hash_pin_required": True,
    "accepted_pin_channel": "agent_bridge_forum_independent_review_manifest",
    "pin_verification_is_external_to_this_contract": True,
    "required_pin_contents_in_order": [
        "reviewer_session_id",
        "review_verdict_pass",
        "reviewed_feature_commit_sha",
        "reviewed_tree_sha",
        "semantic_checker_sha256",
        "sha256_for_each_exact_feature_path",
    ],
    "exact_feature_paths_in_order": sorted(EXPECTED_PATHS),
    "no_authority_before_verified_pin": True,
}

EXPECTED_SECURITY_OBJECTIVE = {
    "host_wall_clock_must_be_unobservable": True,
    "host_monotonic_clock_must_be_unobservable": True,
    "timer_readiness_must_not_use_host_elapsed_time": True,
    "candidate_visible_time_must_be_supervisor_defined_and_deterministic": True,
    "candidate_time_must_never_be_protocol_authority": True,
    "outer_supervisor_exclusively_owns_authenticated_time": True,
    "equal_clock_policy_across_experiment_arms": True,
    "fresh_instance_replay_count": 3,
    "frozen_wall_clock_deny_canary": "REMAINS_FROZEN_AND_UNSATISFIED",
}

EXPECTED_CRATE_ROWS = [
    {
        "name": "wasmtime",
        "version": "46.0.1",
        "sha256": "c4213d2f019a5e44aa8a61d8826dd33a505bff79f749b14a8bafd67321cb9351",
        "yanked": False,
    },
    {
        "name": "wasmtime-wasi",
        "version": "46.0.1",
        "sha256": "e9f65ef30a2c5478873cdb619085a7a649d3ce41cc3eaf298a7ce3dee96a8e11",
        "yanked": False,
    },
    {
        "name": "wasmtime-wasi-io",
        "version": "46.0.1",
        "sha256": "cee57d5fef4976b1ab542615f4cef2c43278eb549d8078939668ea0f13d5c696",
        "yanked": False,
    },
]

EXPECTED_SOURCE_ROWS = [
    {
        "id": "wasmtime_wasi_ctx_46_0_1",
        "url": "https://raw.githubusercontent.com/bytecodealliance/wasmtime/v46.0.1/crates/wasi/src/ctx.rs",
        "sha256": "2d26a093c6026a7026b0713e97128f4aa2d004bd06797947617bbc581bc2193c",
        "locked_claim": "WasiCtxBuilder defaults to ambient host clocks and broader WASI state",
    },
    {
        "id": "wasmtime_wasi_clock_traits_46_0_1",
        "url": "https://raw.githubusercontent.com/bytecodealliance/wasmtime/v46.0.1/crates/wasi/src/clocks.rs",
        "sha256": "4d440ae5eabf6e3ce63342c88b5fdc417f421a5e63c54edfe57808b807f5bb9a",
        "locked_claim": "HostWallClock and HostMonotonicClock replace now and resolution only",
    },
    {
        "id": "wasmtime_wasi_p2_linker_46_0_1",
        "url": "https://raw.githubusercontent.com/bytecodealliance/wasmtime/v46.0.1/crates/wasi/src/p2/mod.rs",
        "sha256": "1149c1e55d6d58b147b44595c38fd979be2e6d1a51e8429e91ab5eb4db4885f7",
        "locked_claim": "top-level add_to_linker helpers install broad WASI interfaces while individual bindings can be linked directly",
    },
    {
        "id": "wasmtime_wasi_p2_clock_host_46_0_1",
        "url": "https://raw.githubusercontent.com/bytecodealliance/wasmtime/v46.0.1/crates/wasi/src/p2/host/clocks.rs",
        "sha256": "d1ba7a7b0a823d173d86e39cb7de6b91c87560a33d73696c77e51a9ddb9bb77b",
        "locked_claim": "built-in monotonic subscriptions use Tokio Instant and sleep_until independently of the custom monotonic now provider",
    },
    {
        "id": "wasmtime_vendored_wasi_clocks_wit_0_2_12",
        "url": "https://raw.githubusercontent.com/bytecodealliance/wasmtime/v46.0.1/crates/wasi/src/p2/wit/deps/clocks.wit",
        "sha256": "6ed8aa65bb8cbe224a0b2cbac9fc1b3bd25bdb17eda5ae0d23c983ed31c447cc",
        "locked_claim": "the pinned clocks package exposes wall now resolution plus monotonic now resolution subscribe-instant and subscribe-duration",
    },
    {
        "id": "wasmtime_vendored_wasi_io_wit_0_2_12",
        "url": "https://raw.githubusercontent.com/bytecodealliance/wasmtime/v46.0.1/crates/wasi/src/p2/wit/deps/io.wit",
        "sha256": "96e206d00076fa0480df32c5bcf255a3fa4862805ac2f6b8537a781cce54f433",
        "locked_claim": "the pinned poll interface returns ready input indices for a non-empty list of pollables",
    },
]

EXPECTED_ADVISORY_REVIEW = {
    "status": "NOT_EXECUTED_NO_DEPENDENCY_PROMOTION",
    "wasmtime_security_source": "https://github.com/bytecodealliance/wasmtime/security/advisories",
    "rustsec_database_source": "https://github.com/RustSec/advisory-db",
    "future_review_requires_database_commit_and_utc_timestamp": True,
    "future_review_requires_full_lockfile_and_raw_audit_receipt_hash": True,
    "no_current_safety_claim": True,
}

EXPECTED_COMPONENT_ABI = {
    "component_model": "WASIP2_COMPONENT",
    "canonical_wit_path": "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit",
    "canonical_wit_sha256": "d47b294dc4c7ee3f48d7af8a6233022a75e79533a2f554ec1299639ba3e142be",
    "package": "agent-bridge:g14-clock-probe@0.1.0",
    "probe_world": "agent-bridge:g14-clock-probe/probe@0.1.0",
    "allowed_imports_in_exact_order": [
        "wasi:clocks/wall-clock@0.2.12",
        "wasi:clocks/monotonic-clock@0.2.12",
        "wasi:io/poll@0.2.12",
    ],
    "sole_export": "typed-report: func() -> typed-report",
    "sole_export_result": {
        "type": "typed-report",
        "record_fields_in_order": [
            "wall-epoch-seconds: u64",
            "logical-nanoseconds: u64",
            "quantum-nanoseconds: u64",
        ],
    },
    "component_import_graph_must_exactly_equal_allowlist": True,
    "component_import_export_manifest_sha256_required_before_run": True,
    "unknown_or_transitive_runtime_imports_fail_closed": True,
    "forbidden_import_prefixes_in_order": [
        "wasi:cli/",
        "wasi:filesystem/",
        "wasi:http/",
        "wasi:random/",
        "wasi:sockets/",
        "wasi:clocks/timezone@",
    ],
    "core_wasm_wasi_p1_allowed": False,
    "stdio_or_preopens_allowed": False,
    "native_or_host_process_fallback_allowed": False,
}

EXPECTED_LINKER_HOST = {
    "generated_bindings_for_exact_probe_world_required": True,
    "broad_wasi_context_or_view_allowed": False,
    "wasmtime_wasi_ctx_builder_allowed": False,
    "top_level_wasmtime_wasi_p2_add_to_linker_helpers_allowed": False,
    "proxy_world_add_to_linker_helpers_allowed": False,
    "built_in_wasmtime_wasi_monotonic_subscription_host_allowed": False,
    "direct_wall_clock_host_trait_implementation_required": True,
    "direct_monotonic_clock_host_trait_implementation_required": True,
    "direct_io_poll_host_trait_implementation_required": True,
    "single_shared_logical_clock_state_required": True,
    "tokio_instant_sleep_or_interval_allowed": False,
    "ambient_host_clock_fallback_allowed": False,
}

EXPECTED_CLOCK = {
    "wall_epoch_seconds": 946684800,
    "wall_epoch_nanoseconds": 0,
    "logical_initial_nanoseconds": 0,
    "quantum_nanoseconds": 1000000,
    "wall_and_monotonic_resolution_nanoseconds": 1000000,
    "resolution_calls_advance_logical_time": False,
    "wall_now_rule": "return_epoch_plus_current_logical_then_checked_advance_one_quantum",
    "monotonic_now_rule": "return_current_logical_then_checked_advance_one_quantum",
    "subscribe_duration_rule": "deadline_is_checked_current_logical_plus_duration_without_advancing",
    "subscribe_instant_rule": "deadline_is_requested_instant_without_advancing",
    "poll_ready_rule": "if_any_deadline_lte_current_return_all_ready_input_indices_in_input_order_without_advancing",
    "poll_wait_rule": "otherwise_set_logical_to_minimum_deadline_then_return_all_ready_input_indices_in_input_order",
    "poll_input_must_be_nonempty": True,
    "only_registered_timer_pollables_allowed": True,
    "pollable_ids_are_monotonic_creation_order_u64": True,
    "checked_u64_arithmetic_required": True,
    "overflow_unknown_or_mixed_pollable_result": "FAIL_CLOSED_TRAP_NO_RECEIPT",
    "host_wall_clock_reads_allowed": False,
    "host_monotonic_clock_reads_allowed": False,
    "host_sleep_or_timer_reads_allowed": False,
    "host_entropy_reads_allowed": False,
    "candidate_time_has_protocol_authority": False,
    "outer_supervisor_protocol_time_only": True,
}

EXPECTED_PROBE = {
    "source_status": "FUTURE_PUBLIC_SYNTHETIC_SOURCE_NOT_AUTHORED",
    "public_input": "agent-bridge-g14-wasi-clock-probe-v0",
    "call_sequence_in_order": [
        "wall-clock.resolution",
        "wall-clock.now",
        "monotonic-clock.resolution",
        "monotonic-clock.now",
        "monotonic-clock.subscribe-duration(3000000)",
        "monotonic-clock.subscribe-instant(2000000)",
        "io-poll.poll([pollable-0,pollable-1])",
        "io-poll.poll([pollable-0])",
        "wall-clock.now",
        "monotonic-clock.now",
        "monotonic-clock.subscribe-duration(0)",
        "io-poll.poll([pollable-2])",
    ],
    "expected_observations_in_order": [
        "resolution=1000000;logical=0",
        "datetime=946684800:0;logical_after=1000000",
        "resolution=1000000;logical=1000000",
        "instant=1000000;logical_after=2000000",
        "pollable=0;deadline=5000000;logical=2000000",
        "pollable=1;deadline=2000000;logical=2000000",
        "ready_indices=[1];logical=2000000",
        "ready_indices=[0];logical=5000000",
        "datetime=946684800:5000000;logical_after=6000000",
        "instant=6000000;logical_after=7000000",
        "pollable=2;deadline=7000000;logical=7000000",
        "ready_indices=[0];logical=7000000",
    ],
    "final_logical_nanoseconds": 7000000,
}

EXPECTED_TRANSCRIPT = {
    "event_schema": "agent_bridge.engram_g14_clock_event.v0",
    "event_fields_in_order": [
        "sequence",
        "operation",
        "arguments",
        "result",
        "logical_before_nanoseconds",
        "logical_after_nanoseconds",
    ],
    "event_encoding": "UTF8_CANONICAL_JSON_SORTED_KEYS_NO_WHITESPACE_NO_FLOATS",
    "hash_chain_initial": "SHA256(UTF8(agent-bridge:g14-clock-transcript:init:v0))",
    "hash_chain_step": "SHA256(UTF8(agent-bridge:g14-clock-transcript:event:v0)+NUL+previous_hash_32_bytes+event_length_u64_be+event_bytes)",
    "typed_report_required": True,
    "stdout_stderr_as_report_channel_allowed": False,
    "fresh_instance_count": 3,
    "required_byte_equal_artifacts_in_order": [
        "component_sha256",
        "import_export_manifest_bytes",
        "typed_report_bytes",
        "event_transcript_bytes",
        "transcript_root_sha256",
    ],
    "any_difference_result": "FAIL_CLOSED_NO_FEASIBILITY_RECEIPT",
}

EXPECTED_BOUNDS = {
    "maximum_component_bytes": 262144,
    "maximum_linear_memory_bytes": 16777216,
    "maximum_table_elements": 1024,
    "maximum_instances": 8,
    "maximum_clock_events": 64,
    "maximum_live_pollables": 16,
    "maximum_typed_report_bytes": 16384,
    "maximum_fuel": 2000000,
    "outer_supervisor_timeout_milliseconds": 5000,
    "supervisor_timeout_is_component_visible": False,
    "timeout_or_resource_exhaustion_result": "FAIL_CLOSED_NO_RECEIPT",
}

EXPECTED_FUTURE_INTERLOCK = {
    "only_permitted_successor": "G2A_PUBLIC_WASI_ARTIFACT_AND_COMPONENT_COMPATIBILITY_EVIDENCE_REVIEW",
    "successor_is_public_static_and_no_run": True,
    "before_any_component_source_build_or_run_require_in_order": [
        "verified_release_archive_and_crate_payload_digests",
        "minimal_exact_crate_feature_graph",
        "complete_Cargo_lock_and_all_transitive_checksums",
        "target_triples_and_rust_toolchain_digest",
        "pinned_RustSec_database_commit_timestamp_and_raw_audit_receipt_hash",
        "exact_WIT_world_and_binding_generator_compatibility",
        "proof_that_direct_clock_and_poll_traits_bypass_all_builtin_host_timer_paths",
        "fixed_public_component_source_binary_and_import_manifest_digests",
        "custom_clock_and_poll_host_source_digest",
    ],
    "missing_or_drifted_requirement": "FAIL_CLOSED_NO_SOURCE_NO_BUILD_NO_RUN",
    "silent_native_or_qemu_fallback_allowed": False,
}

EXPECTED_HUMAN_AUDIT = {
    "human_approval_required_for_this_static_gate": False,
    "human_approval_required_for_separately_authorized_reversible_public_synthetic_work": False,
    "independent_read_only_review_still_required": True,
    "human_security_audit_required_before_in_order": [
        "promoting_any_Wasmtime_or_WASI_dependency_into_Agent_Bridge_runtime",
        "changing_wall_clock_read_deny_semantics_beyond_public_synthetic_harness",
        "candidate_private_or_capability_material_access",
        "runtime_or_deployment_enablement",
        "first_real_G1_4_execution",
    ],
}

EXPECTED_ROLLBACK_INTERLOCK = {
    "rollback_or_cleanup_failure_requires_durable_lesson_before_retry": True,
    "lesson_must_be_create_new_not_overwrite": True,
    "lesson_must_be_fsynced_reopened_and_hash_verified": True,
    "lesson_failure_leaves_absorbing_interlock": True,
}

EXPECTED_DECISION = {
    "verdict": "WASI_CUSTOM_CLOCK_ROUTE_PREREGISTERED_NO_BUILD_NO_RUN_NO_AUTHORITY",
    "preferred_route": "wasi_component_custom_clocks",
    "built_in_wasmtime_timer_host_acceptable": False,
    "runtime_or_dependency_adopted": False,
    "component_or_host_implemented": False,
    "dependency_or_wit_generation_authorized": False,
    "component_or_linker_authorized": False,
    "build_or_run_authorized": False,
    "candidate_or_private_authorized": False,
    "runtime_or_deployment_authorized": False,
    "g1_4_execution_open": False,
    "only_permitted_successor": "G2A_PUBLIC_WASI_ARTIFACT_AND_COMPONENT_COMPATIBILITY_EVIDENCE_REVIEW",
}

EXPECTED_NONCLAIMS = {
    "host_clock_isolation_verified": False,
    "timer_poll_isolation_verified": False,
    "runtime_supply_chain_review_complete": False,
    "dependency_advisory_review_complete": False,
    "component_abi_compiled": False,
    "bindings_generated": False,
    "component_abi_sha256_observed": False,
    "component_import_graph_observed": False,
    "custom_clock_or_poll_host_implemented": False,
    "public_synthetic_run_executed": False,
    "candidate_compatibility_proven": False,
    "candidate_private_or_capability_authorized": False,
    "runtime_deployment_or_g1_4_authority": False,
}


class CheckError(RuntimeError):
    """Closed semantic-check failure."""


def require(condition: bool, label: str) -> None:
    if not condition:
        raise CheckError(label)


def exact(value: Any, expected: Any, label: str) -> None:
    if value != expected:
        raise CheckError(f"{label}: expected {expected!r}, got {value!r}")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def git_bytes(*args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise CheckError(f"git {' '.join(args)} rc={completed.returncode}: {detail}")
    return completed.stdout


def git_text(*args: str) -> str:
    return git_bytes(*args).decode("utf-8")


def validate_contract(contract: dict[str, Any]) -> None:
    exact(
        set(contract),
        {
            "schema",
            "gate",
            "date",
            "mode",
            "status",
            "predecessor",
            "scope",
            "acceptance_integrity",
            "security_objective",
            "public_review_target_pins",
            "component_abi_template",
            "linker_and_host_contract",
            "deterministic_clock_state_machine",
            "fixed_public_probe",
            "transcript_and_replay_contract",
            "resource_bounds",
            "future_artifact_review_interlock",
            "human_audit_boundary",
            "rollback_lesson_interlock",
            "decision",
            "nonclaims",
        },
        "top-level fields",
    )
    exact(
        contract["schema"],
        "agent_bridge.engram_g14_wasi_clock_preregistration.v0",
        "schema",
    )
    exact(contract["gate"], "G2_WASI_PREREGISTRATION", "gate")
    exact(contract["date"], "2026-07-19", "date")
    exact(contract["mode"], "PUBLIC_STATIC_PREREGISTRATION_ONLY", "mode")
    exact(
        contract["status"],
        "CANONICAL_WIT_CONTRACT_SELECTED_STATIC_ONLY",
        "status",
    )
    exact(contract["predecessor"], EXPECTED_PREDECESSOR, "predecessor")
    exact(contract["scope"], EXPECTED_SCOPE, "scope")
    exact(
        contract["acceptance_integrity"],
        EXPECTED_ACCEPTANCE_INTEGRITY,
        "acceptance integrity",
    )
    exact(
        contract["security_objective"],
        EXPECTED_SECURITY_OBJECTIVE,
        "security objective",
    )

    pins = contract["public_review_target_pins"]
    exact(
        set(pins),
        {
            "classification",
            "wasmtime_release",
            "crates_io_rows_in_order",
            "vendored_wit_packages_in_order",
            "source_rows_in_order",
            "advisory_review",
        },
        "review pin fields",
    )
    exact(
        pins["classification"],
        "REVIEW_TARGETS_ONLY_NOT_CARGO_ADOPTION",
        "review target classification",
    )
    exact(
        pins["wasmtime_release"],
        {
            "version": "46.0.1",
            "git_tag": "v46.0.1",
            "git_commit": "823d1b8f251494a06288194d0df746191f535ff7",
            "minimum_rust_version": "1.94.0",
        },
        "Wasmtime release",
    )
    exact(pins["crates_io_rows_in_order"], EXPECTED_CRATE_ROWS, "crate rows")
    exact(
        pins["vendored_wit_packages_in_order"],
        ["wasi:clocks@0.2.12", "wasi:io@0.2.12"],
        "vendored WIT packages",
    )
    exact(pins["source_rows_in_order"], EXPECTED_SOURCE_ROWS, "source rows")
    exact(pins["advisory_review"], EXPECTED_ADVISORY_REVIEW, "advisory review")

    exact(contract["component_abi_template"], EXPECTED_COMPONENT_ABI, "component ABI")
    exact(
        contract["linker_and_host_contract"],
        EXPECTED_LINKER_HOST,
        "linker and host contract",
    )
    exact(
        contract["deterministic_clock_state_machine"],
        EXPECTED_CLOCK,
        "clock state machine",
    )
    exact(contract["fixed_public_probe"], EXPECTED_PROBE, "fixed public probe")
    exact(
        contract["transcript_and_replay_contract"],
        EXPECTED_TRANSCRIPT,
        "transcript and replay",
    )
    exact(contract["resource_bounds"], EXPECTED_BOUNDS, "resource bounds")
    exact(
        contract["future_artifact_review_interlock"],
        EXPECTED_FUTURE_INTERLOCK,
        "future artifact review interlock",
    )
    exact(
        contract["human_audit_boundary"],
        EXPECTED_HUMAN_AUDIT,
        "human audit boundary",
    )
    exact(
        contract["rollback_lesson_interlock"],
        EXPECTED_ROLLBACK_INTERLOCK,
        "rollback lesson interlock",
    )
    exact(contract["decision"], EXPECTED_DECISION, "decision")
    exact(contract["nonclaims"], EXPECTED_NONCLAIMS, "nonclaims")


Mutation = tuple[str, Callable[[dict[str, Any]], None]]


def run_semantic_mutations(contract: dict[str, Any]) -> None:
    mutations: list[Mutation] = [
        ("schema drift", lambda value: value.__setitem__("schema", "v1")),
        (
            "canonical status drift",
            lambda value: value.__setitem__("status", "STATIC_CONTRACT_COMPLETE"),
        ),
        ("unknown top-level field", lambda value: value.__setitem__("authority", True)),
        (
            "predecessor drift",
            lambda value: value["predecessor"].__setitem__(
                "accepted_review_feature_commit", "0" * 40
            ),
        ),
        (
            "dependency adoption",
            lambda value: value["scope"].__setitem__(
                "runtime_dependency_selected_or_installed", True
            ),
        ),
        (
            "component execution",
            lambda value: value["scope"].__setitem__("component_built_or_executed", True),
        ),
        (
            "candidate access",
            lambda value: value["scope"].__setitem__(
                "candidate_private_or_capability_material_accessed", True
            ),
        ),
        (
            "canary change",
            lambda value: value["scope"].__setitem__(
                "frozen_wall_clock_deny_canary_changed", True
            ),
        ),
        (
            "self authentication",
            lambda value: value["acceptance_integrity"].__setitem__(
                "checker_self_authenticating", True
            ),
        ),
        (
            "external pin removal",
            lambda value: value["acceptance_integrity"].__setitem__(
                "no_authority_before_verified_pin", False
            ),
        ),
        (
            "host timer objective weakened",
            lambda value: value["security_objective"].__setitem__(
                "timer_readiness_must_not_use_host_elapsed_time", False
            ),
        ),
        (
            "single replay",
            lambda value: value["security_objective"].__setitem__(
                "fresh_instance_replay_count", 1
            ),
        ),
        (
            "review target becomes adoption",
            lambda value: value["public_review_target_pins"].__setitem__(
                "classification", "ADOPTED_DEPENDENCY"
            ),
        ),
        (
            "release drift",
            lambda value: value["public_review_target_pins"]["wasmtime_release"].__setitem__(
                "version", "46.0.2"
            ),
        ),
        (
            "crate checksum drift",
            lambda value: value["public_review_target_pins"]["crates_io_rows_in_order"][0].__setitem__(
                "sha256", "0" * 64
            ),
        ),
        (
            "source checksum drift",
            lambda value: value["public_review_target_pins"]["source_rows_in_order"][3].__setitem__(
                "sha256", "0" * 64
            ),
        ),
        (
            "false advisory safety claim",
            lambda value: value["public_review_target_pins"]["advisory_review"].__setitem__(
                "no_current_safety_claim", False
            ),
        ),
        (
            "poll import removed",
            lambda value: value["component_abi_template"]["allowed_imports_in_exact_order"].pop(),
        ),
        (
            "canonical WIT checksum drift",
            lambda value: value["component_abi_template"].__setitem__(
                "canonical_wit_sha256", "0" * 64
            ),
        ),
        (
            "typed export drift",
            lambda value: value["component_abi_template"].__setitem__(
                "sole_export", "run: func()"
            ),
        ),
        (
            "typed export result drift",
            lambda value: value["component_abi_template"]["sole_export_result"][
                "record_fields_in_order"
            ].pop(),
        ),
        (
            "random import added",
            lambda value: value["component_abi_template"]["allowed_imports_in_exact_order"].append(
                "wasi:random/random@0.2.12"
            ),
        ),
        (
            "unknown imports allowed",
            lambda value: value["component_abi_template"].__setitem__(
                "unknown_or_transitive_runtime_imports_fail_closed", False
            ),
        ),
        (
            "stdio enabled",
            lambda value: value["component_abi_template"].__setitem__(
                "stdio_or_preopens_allowed", True
            ),
        ),
        (
            "broad context enabled",
            lambda value: value["linker_and_host_contract"].__setitem__(
                "broad_wasi_context_or_view_allowed", True
            ),
        ),
        (
            "WasiCtxBuilder enabled",
            lambda value: value["linker_and_host_contract"].__setitem__(
                "wasmtime_wasi_ctx_builder_allowed", True
            ),
        ),
        (
            "broad linker enabled",
            lambda value: value["linker_and_host_contract"].__setitem__(
                "top_level_wasmtime_wasi_p2_add_to_linker_helpers_allowed", True
            ),
        ),
        (
            "built-in timer host enabled",
            lambda value: value["linker_and_host_contract"].__setitem__(
                "built_in_wasmtime_wasi_monotonic_subscription_host_allowed", True
            ),
        ),
        (
            "direct poll host removed",
            lambda value: value["linker_and_host_contract"].__setitem__(
                "direct_io_poll_host_trait_implementation_required", False
            ),
        ),
        (
            "Tokio time enabled",
            lambda value: value["linker_and_host_contract"].__setitem__(
                "tokio_instant_sleep_or_interval_allowed", True
            ),
        ),
        (
            "ambient clock fallback",
            lambda value: value["linker_and_host_contract"].__setitem__(
                "ambient_host_clock_fallback_allowed", True
            ),
        ),
        (
            "epoch drift",
            lambda value: value["deterministic_clock_state_machine"].__setitem__(
                "wall_epoch_seconds", 0
            ),
        ),
        (
            "quantum drift",
            lambda value: value["deterministic_clock_state_machine"].__setitem__(
                "quantum_nanoseconds", 1
            ),
        ),
        (
            "resolution advances",
            lambda value: value["deterministic_clock_state_machine"].__setitem__(
                "resolution_calls_advance_logical_time", True
            ),
        ),
        (
            "poll returns creation order",
            lambda value: value["deterministic_clock_state_machine"].__setitem__(
                "poll_ready_rule", "return_creation_order"
            ),
        ),
        (
            "host clock read enabled",
            lambda value: value["deterministic_clock_state_machine"].__setitem__(
                "host_monotonic_clock_reads_allowed", True
            ),
        ),
        (
            "candidate time authority",
            lambda value: value["deterministic_clock_state_machine"].__setitem__(
                "candidate_time_has_protocol_authority", True
            ),
        ),
        (
            "probe sequence drift",
            lambda value: value["fixed_public_probe"]["call_sequence_in_order"].pop(),
        ),
        (
            "probe expectation drift",
            lambda value: value["fixed_public_probe"]["expected_observations_in_order"].__setitem__(
                6, "ready_indices=[0]"
            ),
        ),
        (
            "stdout report enabled",
            lambda value: value["transcript_and_replay_contract"].__setitem__(
                "stdout_stderr_as_report_channel_allowed", True
            ),
        ),
        (
            "hash chain drift",
            lambda value: value["transcript_and_replay_contract"].__setitem__(
                "hash_chain_step", "SHA256(event_bytes)"
            ),
        ),
        (
            "replay count drift",
            lambda value: value["transcript_and_replay_contract"].__setitem__(
                "fresh_instance_count", 2
            ),
        ),
        (
            "fuel widened",
            lambda value: value["resource_bounds"].__setitem__(
                "maximum_fuel", 20_000_000
            ),
        ),
        (
            "timeout made visible",
            lambda value: value["resource_bounds"].__setitem__(
                "supervisor_timeout_is_component_visible", True
            ),
        ),
        (
            "successor can run",
            lambda value: value["future_artifact_review_interlock"].__setitem__(
                "successor_is_public_static_and_no_run", False
            ),
        ),
        (
            "evidence interlock weakened",
            lambda value: value["future_artifact_review_interlock"].__setitem__(
                "missing_or_drifted_requirement", "WARN_ONLY"
            ),
        ),
        (
            "silent QEMU fallback",
            lambda value: value["future_artifact_review_interlock"].__setitem__(
                "silent_native_or_qemu_fallback_allowed", True
            ),
        ),
        (
            "reversible work needs human approval",
            lambda value: value["human_audit_boundary"].__setitem__(
                "human_approval_required_for_separately_authorized_reversible_public_synthetic_work",
                True,
            ),
        ),
        (
            "runtime promotion audit removed",
            lambda value: value["human_audit_boundary"]["human_security_audit_required_before_in_order"].pop(0),
        ),
        (
            "rollback lesson removed",
            lambda value: value["rollback_lesson_interlock"].__setitem__(
                "rollback_or_cleanup_failure_requires_durable_lesson_before_retry", False
            ),
        ),
        (
            "lesson verification weakened",
            lambda value: value["rollback_lesson_interlock"].__setitem__(
                "lesson_must_be_fsynced_reopened_and_hash_verified", False
            ),
        ),
        (
            "built-in timer accepted",
            lambda value: value["decision"].__setitem__(
                "built_in_wasmtime_timer_host_acceptable", True
            ),
        ),
        (
            "run authorized",
            lambda value: value["decision"].__setitem__("build_or_run_authorized", True),
        ),
        (
            "WIT generation authorized",
            lambda value: value["decision"].__setitem__(
                "dependency_or_wit_generation_authorized", True
            ),
        ),
        (
            "G1.4 opened",
            lambda value: value["decision"].__setitem__("g1_4_execution_open", True),
        ),
        (
            "verification overclaimed",
            lambda value: value["nonclaims"].__setitem__(
                "timer_poll_isolation_verified", True
            ),
        ),
    ]

    for label, mutate in mutations:
        trial = copy.deepcopy(contract)
        mutate(trial)
        try:
            validate_contract(trial)
        except CheckError:
            continue
        raise CheckError(f"semantic mutation unexpectedly accepted: {label}")
    exact(len(mutations), 56, "semantic mutation count")


def load_producer_module() -> Any:
    spec = importlib.util.spec_from_file_location("engram_g14_wasi_prereg", PRODUCER_PATH)
    require(spec is not None and spec.loader is not None, "producer import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_receipt(contract: dict[str, Any]) -> None:
    producer = load_producer_module()
    first = producer.render_receipt(copy.deepcopy(contract))
    second = producer.render_receipt(copy.deepcopy(contract))
    exact(first, second, "deterministic in-process receipt")
    exact(
        first["contract_sha256"],
        sha256_bytes(canonical_json(contract)),
        "receipt contract hash",
    )
    exact(first["authority_class"], "NONE_STATIC_PREREGISTRATION_ONLY", "authority")
    exact(first["allowed_import_count"], 3, "receipt import count")
    exact(first["review_target_crate_count"], 3, "receipt crate count")
    exact(first["review_target_source_pin_count"], 6, "receipt source count")
    exact(first["fresh_future_instance_count"], 3, "receipt replay count")
    for field in (
        "built_in_wasmtime_timer_host_acceptable",
        "runtime_or_dependency_adopted",
        "component_built_or_executed",
        "build_or_run_authorized",
        "candidate_or_private_authorized",
        "runtime_or_deployment_authorized",
        "g1_4_execution_open",
        "checker_self_authenticating",
    ):
        exact(first[field], False, f"receipt {field}")
    exact(first["out_of_band_acceptance_pin_required"], True, "receipt pin required")
    exact(first["no_authority_before_verified_pin"], True, "receipt pin interlock")
    exact(
        first["only_permitted_successor"],
        "G2A_PUBLIC_WASI_ARTIFACT_AND_COMPONENT_COMPATIBILITY_EVIDENCE_REVIEW",
        "receipt successor",
    )

    command = [sys.executable, str(PRODUCER_PATH)]
    environment = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    outputs: list[bytes] = []
    for _ in range(2):
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(completed.returncode == 0, "producer command failed")
        exact(completed.stderr, b"", "producer stderr")
        require(completed.stdout.endswith(b"\n"), "producer newline")
        require(completed.stdout.count(b"\n") == 1, "producer single-line receipt")
        require(len(completed.stdout) <= 4097, "producer receipt bound")
        outputs.append(completed.stdout)
    exact(outputs[0], outputs[1], "deterministic command receipt")
    exact(json.loads(outputs[0]), first, "command and in-process receipt")


def validate_predecessor() -> None:
    exact(
        git_text("show", "-s", "--format=%T", PREDECESSOR_COMMIT).strip(),
        PREDECESSOR_TREE,
        "predecessor tree",
    )
    for feature_path, expected_hash in EXPECTED_PREDECESSOR_HASHES.items():
        observed = sha256_bytes(git_bytes("show", f"{PREDECESSOR_COMMIT}:{feature_path}"))
        exact(observed, expected_hash, f"predecessor hash {feature_path}")


def validate_docs_and_modes() -> None:
    exact(sha256_bytes(DESIGN_PATH.read_bytes()), EXPECTED_DOC_HASHES["design"], "design hash")
    exact(sha256_bytes(RESULT_PATH.read_bytes()), EXPECTED_DOC_HASHES["result"], "result hash")
    exact(
        sha256_bytes(CANONICAL_WIT_PATH.read_bytes()),
        CANONICAL_WIT_SHA256,
        "canonical WIT source binding",
    )
    require(WRAPPER_PATH.stat().st_mode & 0o111 != 0, "wrapper is not executable")
    require(PRODUCER_PATH.stat().st_mode & 0o111 != 0, "producer is not executable")


def validate_surface(phase: str) -> None:
    exact(phase in {"precommit", "postcommit"}, True, "phase")
    status = git_text("status", "--porcelain=v1", "--untracked-files=all")
    if phase == "precommit":
        observed = {
            row[3:].split(" -> ")[-1]
            for row in status.splitlines()
            if len(row) >= 4
        }
    else:
        exact(status, "", "clean postcommit worktree")
        head = git_text("rev-parse", "HEAD").strip()
        require(head != BASE_COMMIT, "postcommit HEAD equals base")
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", BASE_COMMIT, head],
            cwd=REPO_ROOT,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            check=False,
        )
        require(ancestor.returncode == 0, "base is not an ancestor of HEAD")
        observed = set(
            git_text("diff", "--name-only", f"{BASE_COMMIT}..{head}").splitlines()
        )
    exact(observed, EXPECTED_PATHS, f"{phase} path surface")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "--phase" or argv[1] not in {
        "precommit",
        "postcommit",
    }:
        raise CheckError("usage: checker --phase precommit|postcommit")
    phase = argv[1]
    contract = json.loads(CONTRACT_PATH.read_bytes())
    require(isinstance(contract, dict), "contract must be an object")
    validate_contract(contract)
    run_semantic_mutations(contract)
    validate_receipt(contract)
    validate_predecessor()
    validate_docs_and_modes()
    residues = [
        candidate
        for candidate in (REPO_ROOT / "scripts/eval").rglob("*")
        if candidate.name == "__pycache__" or candidate.suffix == ".pyc"
    ]
    exact(residues, [], "Python cache residue")
    validate_surface(phase)
    print(
        "engram G2 WASI clock preregistration: semantic contract valid; "
        "56 mutations rejected; canonical WIT bound; no build, run, or authority"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (CheckError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"engram G2 WASI clock preregistration: invalid: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
