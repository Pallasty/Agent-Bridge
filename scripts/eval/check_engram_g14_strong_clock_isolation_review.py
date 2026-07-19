#!/usr/bin/env python3
"""Semantic checker for the public-static G1.4 clock-isolation review."""

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
BASE_COMMIT = "92fe2facf6f27c85ec0a34a8c46e045b1aaf67e1"
CONTRACT_PATH = (
    REPO_ROOT / "scripts/eval/fixtures/engram_g14_strong_clock_isolation_review_v0.json"
)
PRODUCER_PATH = REPO_ROOT / "scripts/eval/engram_g14_strong_clock_isolation_review.py"
DESIGN_PATH = (
    REPO_ROOT
    / "docs/design/ENGRAM_G1_4_STRONG_CLOCK_ISOLATION_PRIMITIVE_REVIEW_2026_07_18.md"
)
RESULT_PATH = (
    REPO_ROOT
    / "docs/design/ENGRAM_G1_4_STRONG_CLOCK_ISOLATION_PRIMITIVE_REVIEW_RESULT_2026_07_18.md"
)

EXPECTED_DOC_HASHES = {
    "design": "c51e80e151b4185026079db70d191d119fb4a460dfa026fd436629d88dc3433c",
    "result": "cb7fc17dea9c3b19633fb8407ce6830421f7cb142f4916fa97d72f5e8b07f758",
}

EXPECTED_PATHS = {
    "docs/design/ENGRAM_G1_4_STRONG_CLOCK_ISOLATION_PRIMITIVE_REVIEW_2026_07_18.md",
    "docs/design/ENGRAM_G1_4_STRONG_CLOCK_ISOLATION_PRIMITIVE_REVIEW_RESULT_2026_07_18.md",
    "scripts/check-engram-g14-strong-clock-isolation-review.sh",
    "scripts/eval/README.md",
    "scripts/eval/check_engram_g14_strong_clock_isolation_review.py",
    "scripts/eval/engram_g14_strong_clock_isolation_review.py",
    "scripts/eval/fixtures/engram_g14_strong_clock_isolation_review_v0.json",
}

EXPECTED_ACCEPTANCE_INTEGRITY = {
    "checker_self_authenticating": False,
    "standalone_checker_result_is_acceptance_authority": False,
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

EXPECTED_PREDECESSOR_HASHES = {
    "docs/design/ENGRAM_G1_4_NATIVE_SANDBOX_ADAPTER_KAT_2026_07_18.md": "572aa46366fc641801a6a5b20a62a636b9ebf69595f95122bf8fdf644395923d",
    "docs/design/ENGRAM_G1_4_NATIVE_SANDBOX_ADAPTER_KAT_RESULT_2026_07_18.md": "b86fa8de658d40ba974d1ffe60327d9a68fae464a472ba078047a4d70d71548a",
    "scripts/eval/fixtures/engram_g14_native_sandbox_adapter_probe_v0.c": "0824beab20f922548f0033910e1ad3eb55695c0bb802488d0e9e531279199d12",
    "scripts/eval/engram_g14_native_sandbox_adapter_kat.py": "1f79379ef480c3f0c21b901b292990460cd330ee2a627082ed2a94b8094e7c1f",
    "scripts/eval/check_engram_g14_native_sandbox_adapter_kat.py": "d20e681f9824d0cd561f9e3d311cfc129aed1a7fe0f24b9eb6a2785fe79ab41e",
}

EXPECTED_SOURCE_ROWS = [
    (
        "linux_vdso_man_pages_6_18",
        "https://man7.org/linux/man-pages/man7/vdso.7.html",
        "vDSO clock functions execute without a syscall and are not visible to seccomp filters",
    ),
    (
        "linux_time_namespaces_man_pages_6_18",
        "https://man7.org/linux/man-pages/man7/time_namespaces.7.html",
        "time namespaces virtualize monotonic and boottime but do not virtualize realtime",
    ),
    (
        "linux_pr_set_tsc_man_pages_6_18",
        "https://man7.org/linux/man-pages/man2/PR_SET_TSC.2const.html",
        "PR_SET_TSC can fault timestamp-counter reads on x86 only",
    ),
    (
        "linux_seccomp_unotify_man_pages_6_18",
        "https://man7.org/linux/man-pages/man2/seccomp_unotify.2.html",
        "seccomp user notification mediates system calls and is explicitly not itself a complete security policy",
    ),
    (
        "wasi_capabilities",
        "https://github.com/WebAssembly/WASI/blob/main/docs/Capabilities.md",
        "WASI interfaces can be supplied as link-time capabilities including clocks",
    ),
    (
        "wasmtime_wasi_46_0_1_context_builder",
        "https://docs.rs/wasmtime-wasi/46.0.1/wasmtime_wasi/struct.WasiCtxBuilder.html",
        "Wasmtime permits custom wall and monotonic clocks but defaults to host clocks",
    ),
    (
        "apple_virtualization_framework",
        "https://developer.apple.com/documentation/virtualization",
        "Virtualization framework creates macOS or Linux VMs but publishes no custom deterministic clock contract",
    ),
    (
        "qemu_tcg_icount",
        "https://www.qemu.org/docs/master/devel/tcg-icount.html",
        "TCG instruction counting can derive a deterministic virtual clock and is incompatible with multi-threaded TCG",
    ),
    (
        "qemu_record_replay",
        "https://www.qemu.org/docs/master/system/replay.html",
        "record replay captures nondeterministic events including hardware clocks and requires icount",
    ),
    (
        "qemu_rtc_invocation",
        "https://qemu.readthedocs.io/en/v7.2.19/system/invocation.html",
        "fixed RTC base with clock vm is recommended with icount for determinism",
    ),
]

EXPECTED_MATRIX_ROWS = [
    (
        "nono_seatbelt_host_native",
        "host_native_policy",
        False,
        True,
        False,
        False,
        "REJECT_AS_CLOCK_BOUNDARY",
        "accepted Darwin KAT left libc and commpage clock paths readable",
    ),
    (
        "landlock_seccomp_host_native",
        "host_native_policy",
        False,
        True,
        False,
        False,
        "REJECT_AS_CLOCK_BOUNDARY",
        "Landlock has no clock control and vDSO clock paths bypass seccomp",
    ),
    (
        "linux_time_namespace_seccomp_pr_set_tsc",
        "host_native_composite",
        False,
        True,
        False,
        False,
        "REJECT_AS_COMPLETE_BOUNDARY",
        "realtime is not namespaced and timestamp-counter trapping is x86 only",
    ),
    (
        "dynamic_loader_clock_interposition",
        "user_space_interposition",
        False,
        False,
        False,
        False,
        "REJECT_SECURITY_CLAIM",
        "static binaries direct syscalls vDSO commpage and hardware counters bypass interposition",
    ),
    (
        "ptrace_or_seccomp_user_notification",
        "supervised_syscall_interposition",
        False,
        True,
        False,
        False,
        "REJECT_AS_COMPLETE_BOUNDARY",
        "only syscall entries are mediated while memory and hardware clock paths remain",
    ),
    (
        "apple_virtualization_framework_default_vm",
        "hardware_accelerated_vm",
        False,
        True,
        False,
        False,
        "REJECT_WITHOUT_CLOCK_CONTRACT",
        "a VM boundary alone does not prove a fixed or host-independent guest clock",
    ),
    (
        "wasi_component_custom_clocks",
        "capability_runtime",
        True,
        False,
        True,
        True,
        "PRIMARY_SYNTHETIC_FEASIBILITY_CANDIDATE",
        "requires a component-compatible candidate ABI and explicit replacement of default host clocks",
    ),
    (
        "qemu_tcg_icount_fixed_rtc",
        "full_system_emulation",
        True,
        True,
        True,
        True,
        "NATIVE_COMPATIBILITY_FALLBACK_CANDIDATE",
        "requires pinned TCG single-vCPU machine image device set and replay policy with high cost",
    ),
    (
        "supervisor_owned_authoritative_time",
        "authority_overlay",
        False,
        True,
        False,
        True,
        "MANDATORY_OVERLAY_NOT_STANDALONE_ISOLATION",
        "protects authority but does not stop candidate clock-dependent behavior",
    ),
]

EXPECTED_DECISION = {
    "host_native_nono_landlock_seatbelt_path": "REJECTED_FOR_G1_4_CLOCK_ISOLATION",
    "primary_candidate": "wasi_component_custom_clocks",
    "native_compatibility_fallback": "qemu_tcg_icount_fixed_rtc",
    "mandatory_overlay": "supervisor_owned_authoritative_time",
    "apple_virtualization_framework_default_vm": "INSUFFICIENT_WITHOUT_A_CUSTOM_CLOCK_CONTRACT",
    "current_wall_clock_deny_canary": "REMAINS_FROZEN_AND_UNSATISFIED",
    "proposed_future_semantic_change": "replace_api_denial_with_no_host_clock_plus_supervisor_defined_deterministic_time",
    "semantic_change_requires_human_security_audit": True,
    "implementation_authorized": False,
    "synthetic_feasibility_run_authorized": False,
    "g1_4_execution_open": False,
    "verdict": "DESIGN_ROUTE_SELECTED_NO_AUTHORITY",
}

EXPECTED_GATE_ROWS = [
    (
        "G2_WASI_PREREGISTRATION",
        "NOT_STARTED",
        (
            "pin Wasmtime and WASI component ABI with dependency and advisory review",
            "define a public component probe with no ambient host imports",
            "replace default wall and monotonic clocks with deterministic supervisor clocks",
            "omit network and host entropy and expose only registered filesystem capabilities",
            "prove identical outputs and clock transcripts across fresh replays",
            "retain supervisor-owned authenticated time outside the component",
        ),
    ),
    (
        "G2_QEMU_TCG_PREREGISTRATION",
        "NOT_STARTED",
        (
            "pin QEMU source binary machine CPU firmware kernel initramfs and disk digests",
            "use TCG not HVF or KVM with one vCPU and no multi-threaded TCG",
            "use fixed RTC base clock vm and registered icount configuration",
            "remove network entropy shared-folder audio input and unregistered devices",
            "start from a read-only image with a fresh bounded scratch overlay",
            "prove RTC vDSO hardware-counter and replay behavior with public canaries",
        ),
    ),
    (
        "G3_HUMAN_SECURITY_AUDIT",
        "REQUIRED_BEFORE_ADOPTION",
        (
            "review any promotion from wall-clock denial to deterministic virtual time",
            "review first Wasmtime or QEMU dependency promoted beyond public-synthetic feasibility",
            "review first native policy widening or custom clock implementation",
            "review first candidate private capability or real protocol run",
        ),
    ),
]


class CheckError(RuntimeError):
    """Closed checker failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def require_exact(value: Any, expected: Any, label: str) -> None:
    require(value == expected, f"{label}: expected {expected!r}, got {value!r}")


def require_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    require_exact(set(value), expected, f"{label} keys")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path}: expected object")
    return value


def matrix_tuple(row: dict[str, Any]) -> tuple[Any, ...]:
    require_keys(
        row,
        {
            "id",
            "class",
            "host_wall_clock_isolated",
            "arbitrary_native_binary_compatible",
            "deterministic_candidate_time",
            "cross_platform",
            "decision",
            "blocking_reason",
        },
        "candidate matrix row",
    )
    return (
        row["id"],
        row["class"],
        row["host_wall_clock_isolated"],
        row["arbitrary_native_binary_compatible"],
        row["deterministic_candidate_time"],
        row["cross_platform"],
        row["decision"],
        row["blocking_reason"],
    )


def validate_contract(contract: dict[str, Any]) -> None:
    require_keys(
        contract,
        {
            "schema",
            "mode",
            "date",
            "status",
            "predecessor",
            "scope",
            "acceptance_integrity",
            "security_objective",
            "evidence_pins",
            "candidate_matrix_in_order",
            "decision",
            "future_gates_in_order",
            "human_audit_policy",
            "nonclaims",
        },
        "contract",
    )
    require_exact(
        contract["schema"],
        "agent_bridge.engram_g14_strong_clock_isolation_review.v0",
        "schema",
    )
    require_exact(contract["mode"], "PUBLIC_STATIC_DESIGN_SECURITY_REVIEW", "mode")
    require_exact(contract["date"], "2026-07-18", "date")
    require_exact(contract["status"], "COMPLETE_NO_AUTHORITY", "status")

    require_exact(
        contract["predecessor"],
        {
            "accepted_feature_commit": "7cd6fe023cd88ae2a816f8b10bc6ce05084f240d",
            "integrated_master_commit": BASE_COMMIT,
            "terminal_verdict": "REJECTED_FAIL_CLOSED_WALL_CLOCK_UNCONFINED_NO_AUTHORITY",
            "only_permitted_successor": "separate_design_and_security_review_for_stronger_clock_isolation_primitive",
        },
        "predecessor",
    )
    require_exact(
        contract["scope"],
        {
            "public_sources_only": True,
            "static_review_only": True,
            "native_policy_compiled_or_applied": False,
            "native_probe_or_candidate_launched": False,
            "candidate_private_or_capability_material_accessed": False,
            "runtime_store_mcp_or_deploy_changed": False,
            "production_admissible": False,
            "g1_4_execution_open": False,
            "authority_class": "NONE_DESIGN_REVIEW_ONLY",
        },
        "scope",
    )
    require_exact(
        contract["acceptance_integrity"],
        EXPECTED_ACCEPTANCE_INTEGRITY,
        "acceptance integrity",
    )
    require_exact(
        contract["security_objective"],
        {
            "host_wall_clock_must_be_unobservable": True,
            "candidate_visible_time_must_be_absent_or_supervisor_defined_deterministic": True,
            "candidate_time_must_never_be_authoritative": True,
            "supervisor_exclusively_owns_authenticated_time": True,
            "external_time_channels_must_be_closed": [
                "network",
                "shared_host_services",
                "host_filesystem_timestamps",
                "unregistered_inherited_descriptors",
                "external_entropy_devices",
            ],
            "equal_clock_policy_across_arms": True,
            "identical_public_replay_required": True,
        },
        "security objective",
    )

    pins = contract["evidence_pins"]
    require_keys(
        pins,
        {
            "nono_version",
            "nono_crates_io_checksum",
            "grok_build_reference_commit",
            "predecessor_file_sha256",
            "primary_sources_in_order",
        },
        "evidence pins",
    )
    require_exact(pins["nono_version"], "0.53.0", "nono version")
    require_exact(
        pins["nono_crates_io_checksum"],
        "ae7eb523cc2036e9ad6527411c3da5dc2172dc454cc3447a03b910420a39bfee",
        "nono checksum",
    )
    require_exact(
        pins["grok_build_reference_commit"],
        "8adf9013a0929e5c7f1d4e849492d2387837a28d",
        "grok-build reference",
    )
    require_exact(
        pins["predecessor_file_sha256"],
        EXPECTED_PREDECESSOR_HASHES,
        "predecessor hashes",
    )
    source_rows = []
    for row in pins["primary_sources_in_order"]:
        require_keys(row, {"id", "url", "locked_claim"}, "primary source row")
        source_rows.append((row["id"], row["url"], row["locked_claim"]))
    require_exact(source_rows, EXPECTED_SOURCE_ROWS, "primary source rows")

    matrix = contract["candidate_matrix_in_order"]
    require(isinstance(matrix, list), "candidate matrix must be a list")
    require_exact([matrix_tuple(row) for row in matrix], EXPECTED_MATRIX_ROWS, "matrix")
    require_exact(contract["decision"], EXPECTED_DECISION, "decision")

    gate_rows = contract["future_gates_in_order"]
    require(isinstance(gate_rows, list), "future gates must be a list")
    observed_gate_rows = []
    for row in gate_rows:
        require_keys(row, {"id", "status", "requirements"}, "future gate row")
        require(
            isinstance(row["requirements"], list), "gate requirements must be a list"
        )
        require(
            all(isinstance(item, str) and item for item in row["requirements"]),
            "gate requirements must be non-empty strings",
        )
        observed_gate_rows.append(
            (row["id"], row["status"], tuple(row["requirements"]))
        )
    require_exact(observed_gate_rows, EXPECTED_GATE_ROWS, "future gate rows")

    audit = contract["human_audit_policy"]
    require_keys(
        audit,
        {"not_required_for", "required_before", "rollback_failure_rule"},
        "human audit policy",
    )
    require_exact(
        audit["not_required_for"],
        [
            "static public design validation",
            "unchanged reversible public checker rerun",
            "separately preregistered reversible public-synthetic feasibility run",
            "fail_closed_rejection",
            "successful automatic cleanup",
        ],
        "audit exemptions",
    )
    require_exact(
        audit["required_before"],
        [
            "promoting a stronger clock primitive beyond public-synthetic feasibility",
            "changing the frozen wall_clock_read canary semantics for candidate private or runtime admission",
            "promoting Wasmtime QEMU nono or native policy dependencies into runtime or a real candidate path",
            "first candidate private capability or real G1_4 run",
            "policy widening unblinding rerun or suspected exposure",
        ],
        "audit gates",
    )
    require_exact(
        audit["rollback_failure_rule"],
        "persist_and_verify_a_minimal_durable_lesson_before_any_fresh_attempt",
        "rollback failure rule",
    )
    require_exact(
        contract["nonclaims"],
        {
            "wasi_selected_or_implemented": False,
            "qemu_selected_or_implemented": False,
            "clock_isolation_verified": False,
            "native_adapter_implemented": False,
            "full_fourteen_canary_run_executed": False,
            "candidate_or_private_material_authorized": False,
            "production_or_deployment_authorized": False,
            "g1_4_execution_open": False,
        },
        "nonclaims",
    )


def validate_repository_pins(contract: dict[str, Any]) -> None:
    for relative, expected in EXPECTED_PREDECESSOR_HASHES.items():
        require_exact(sha256_file(REPO_ROOT / relative), expected, f"sha256 {relative}")
    cargo_toml = (REPO_ROOT / "crates/agent/Cargo.toml").read_text(encoding="utf-8")
    require(
        'nono = { version = "=0.53.0", default-features = false }' in cargo_toml,
        "Cargo.toml nono exact pin changed",
    )
    cargo_lock = (REPO_ROOT / "Cargo.lock").read_text(encoding="utf-8")
    lock_stanza = (
        'name = "nono"\n'
        'version = "0.53.0"\n'
        'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
        'checksum = "ae7eb523cc2036e9ad6527411c3da5dc2172dc454cc3447a03b910420a39bfee"'
    )
    require(lock_stanza in cargo_lock, "Cargo.lock nono pin/checksum changed")
    require_exact(
        contract["evidence_pins"]["predecessor_file_sha256"],
        EXPECTED_PREDECESSOR_HASHES,
        "contract predecessor hashes",
    )


def load_producer() -> Any:
    spec = importlib.util.spec_from_file_location(
        "engram_g14_clock_review", PRODUCER_PATH
    )
    require(spec is not None and spec.loader is not None, "producer import spec failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_receipt(contract: dict[str, Any]) -> None:
    producer = load_producer()
    receipt = producer.render_receipt(copy.deepcopy(contract))
    expected = {
        "schema": "agent_bridge.engram_g14_strong_clock_isolation_review_receipt.v0",
        "mode": "PUBLIC_STATIC_DESIGN_SECURITY_REVIEW",
        "verdict": "DESIGN_ROUTE_SELECTED_NO_AUTHORITY",
        "authority_class": "NONE_DESIGN_REVIEW_ONLY",
        "contract_sha256": hashlib.sha256(canonical_json(contract)).hexdigest(),
        "reviewed_candidate_count": 9,
        "rejected_candidate_count": 6,
        "conditional_feasibility_candidate_count": 2,
        "primary_candidate": "wasi_component_custom_clocks",
        "native_compatibility_fallback": "qemu_tcg_icount_fixed_rtc",
        "mandatory_overlay": "supervisor_owned_authoritative_time",
        "current_wall_clock_deny_canary": "REMAINS_FROZEN_AND_UNSATISFIED",
        "human_security_audit_required_before_adoption": True,
        "checker_self_authenticating": False,
        "standalone_checker_result_is_acceptance_authority": False,
        "out_of_band_acceptance_pin_required": True,
        "no_authority_before_verified_pin": True,
        "implementation_authorized": False,
        "synthetic_feasibility_run_authorized": False,
        "production_admissible": False,
        "g1_4_execution_open": False,
    }
    require_exact(receipt, expected, "producer receipt")
    require(len(canonical_json(receipt)) <= 2048, "receipt exceeds public bound")
    try:
        producer.main(["--contract", "/tmp/forbidden"])
    except producer.ReviewError:
        pass
    else:
        raise CheckError("producer accepted an argument")


def expect_invalid(
    contract: dict[str, Any],
    label: str,
    mutation: Callable[[dict[str, Any]], None],
) -> None:
    candidate = copy.deepcopy(contract)
    mutation(candidate)
    try:
        validate_contract(candidate)
    except CheckError:
        return
    raise CheckError(f"mutation unexpectedly accepted: {label}")


def validate_mutations(contract: dict[str, Any]) -> None:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        (
            "scope-authority",
            lambda x: x["scope"].__setitem__("production_admissible", True),
        ),
        (
            "native-launch",
            lambda x: x["scope"].__setitem__(
                "native_probe_or_candidate_launched", True
            ),
        ),
        (
            "objective-weakening",
            lambda x: x["security_objective"].__setitem__(
                "host_wall_clock_must_be_unobservable", False
            ),
        ),
        (
            "checker-self-authentication-claim",
            lambda x: x["acceptance_integrity"].__setitem__(
                "checker_self_authenticating", True
            ),
        ),
        (
            "out-of-band-pin-bypass",
            lambda x: x["acceptance_integrity"].__setitem__(
                "independent_out_of_band_commit_and_file_hash_pin_required", False
            ),
        ),
        (
            "source-claim",
            lambda x: x["evidence_pins"]["primary_sources_in_order"][0].__setitem__(
                "locked_claim", "changed"
            ),
        ),
        (
            "source-order",
            lambda x: x["evidence_pins"]["primary_sources_in_order"].reverse(),
        ),
        (
            "nono-checksum",
            lambda x: x["evidence_pins"].__setitem__(
                "nono_crates_io_checksum", "0" * 64
            ),
        ),
        (
            "predecessor-hash",
            lambda x: x["evidence_pins"]["predecessor_file_sha256"].__setitem__(
                next(iter(EXPECTED_PREDECESSOR_HASHES)), "0" * 64
            ),
        ),
        (
            "matrix-id",
            lambda x: x["candidate_matrix_in_order"][0].__setitem__("id", "changed"),
        ),
        (
            "matrix-order",
            lambda x: x["candidate_matrix_in_order"].reverse(),
        ),
        (
            "host-native-promotion",
            lambda x: x["candidate_matrix_in_order"][0].__setitem__(
                "decision", "PRIMARY_SYNTHETIC_FEASIBILITY_CANDIDATE"
            ),
        ),
        (
            "wasi-clock-false",
            lambda x: x["candidate_matrix_in_order"][6].__setitem__(
                "host_wall_clock_isolated", False
            ),
        ),
        (
            "vm-default-promotion",
            lambda x: x["candidate_matrix_in_order"][5].__setitem__(
                "host_wall_clock_isolated", True
            ),
        ),
        (
            "primary-substitution",
            lambda x: x["decision"].__setitem__(
                "primary_candidate", "qemu_tcg_icount_fixed_rtc"
            ),
        ),
        (
            "semantic-audit-bypass",
            lambda x: x["decision"].__setitem__(
                "semantic_change_requires_human_security_audit", False
            ),
        ),
        (
            "implementation-authority",
            lambda x: x["decision"].__setitem__("implementation_authorized", True),
        ),
        (
            "synthetic-run-authority",
            lambda x: x["decision"].__setitem__(
                "synthetic_feasibility_run_authorized", True
            ),
        ),
        ("gate-removal", lambda x: x["future_gates_in_order"].pop()),
        (
            "audit-gate-removal",
            lambda x: x["human_audit_policy"]["required_before"].pop(),
        ),
        (
            "nonclaim-flip",
            lambda x: x["nonclaims"].__setitem__("clock_isolation_verified", True),
        ),
        (
            "g1-open",
            lambda x: x["nonclaims"].__setitem__("g1_4_execution_open", True),
        ),
    ]
    for label, mutation in mutations:
        expect_invalid(contract, label, mutation)
    require_exact(len(mutations), 22, "mutation count")


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    if completed.returncode != 0:
        raise CheckError(
            f"git {' '.join(args)} failed rc={completed.returncode}: {completed.stderr.strip()}"
        )
    return completed.stdout


def precommit_paths() -> set[str]:
    paths: set[str] = set()
    for line in git_output(
        "status", "--porcelain=v1", "--untracked-files=all"
    ).splitlines():
        require(len(line) >= 4, f"malformed git status row: {line!r}")
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.add(path)
    return paths


def postcommit_paths() -> set[str]:
    require_exact(
        git_output("status", "--porcelain=v1", "--untracked-files=all"),
        "",
        "postcommit worktree status",
    )
    head = git_output("rev-parse", "HEAD").strip()
    require(head != BASE_COMMIT, "postcommit HEAD still equals base")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_COMMIT, head],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    return set(git_output("diff", "--name-only", f"{BASE_COMMIT}..{head}").splitlines())


def validate_surface(phase: str) -> None:
    require(phase in {"precommit", "postcommit"}, "invalid phase")
    observed = precommit_paths() if phase == "precommit" else postcommit_paths()
    require_exact(observed, EXPECTED_PATHS, f"{phase} changed path set")


def validate_docs() -> None:
    require_exact(
        sha256_file(DESIGN_PATH), EXPECTED_DOC_HASHES["design"], "design doc sha256"
    )
    require_exact(
        sha256_file(RESULT_PATH), EXPECTED_DOC_HASHES["result"], "result doc sha256"
    )
    design = DESIGN_PATH.read_text(encoding="utf-8")
    result = RESULT_PATH.read_text(encoding="utf-8")
    for token in [
        "Host-native interception is rejected",
        "WASI component with custom clocks",
        "QEMU TCG with icount and a fixed RTC",
        "Supervisor-owned authoritative time",
        "Human security audit boundary",
        "No authority",
    ]:
        require(token in design, f"design doc missing token: {token}")
    for _, url, _ in EXPECTED_SOURCE_ROWS:
        require(url in design, f"design doc missing primary source URL: {url}")
    for token in [
        "DESIGN_ROUTE_SELECTED_NO_AUTHORITY",
        "wasi_component_custom_clocks",
        "qemu_tcg_icount_fixed_rtc",
        "REMAINS_FROZEN_AND_UNSATISFIED",
        "No deployment or reconnect",
    ]:
        require(token in result, f"result doc missing token: {token}")


def validate_syntax_and_cache() -> None:
    for path in [Path(__file__), PRODUCER_PATH]:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    residues = [
        path
        for path in (REPO_ROOT / "scripts/eval").rglob("*")
        if path.name == "__pycache__" or path.suffix == ".pyc"
    ]
    require_exact(residues, [], "Python cache residues")


def main(argv: list[str]) -> int:
    require_exact(len(argv), 2, "CLI argument count")
    require_exact(argv[0], "--phase", "CLI flag")
    phase = argv[1]
    require(
        phase in {"precommit", "postcommit"}, "phase must be precommit or postcommit"
    )
    validate_syntax_and_cache()
    contract = load_json(CONTRACT_PATH)
    validate_contract(contract)
    validate_repository_pins(contract)
    validate_receipt(contract)
    validate_mutations(contract)
    validate_docs()
    validate_surface(phase)
    validate_syntax_and_cache()
    print(
        "engram G1.4 strong clock-isolation review: validated design route; no authority"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (CheckError, OSError, ValueError, KeyError, TypeError) as exc:
        print(
            f"engram G1.4 strong clock-isolation review: invalid: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
