#!/usr/bin/env python3
"""Custody and static verification for the FH-L8 D11 packed q3 checkpoint."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import errno
import os
import re
import selectors
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
PREFIX = "docs/research/fermion-frontier"
CHECKER_NAME = "fh_l8_packed_q3_checkpoint_d11_checker.py"
RUNNER_NAME = "fh_l8_packed_q3_checkpoint_d11_runner.py"
CONTRACT_NAME = "fh_l8_packed_q3_checkpoint_d11_contract.json"
BUNDLE_NAME = "fh_l8_packed_q3_checkpoint_d11_bundle"
CHECKPOINT_NAME = "checkpoint.bin"
RESULT_NAME = "result.json"
TERMINAL_RECEIPT_NAME = "fh_l8_packed_q3_checkpoint_d11_terminal_receipt.json"
TERMINAL_RECEIPT_STAGING_NAME = f".{TERMINAL_RECEIPT_NAME}.staging"
CHECKER_PATH = f"{PREFIX}/{CHECKER_NAME}"
RUNNER_PATH = f"{PREFIX}/{RUNNER_NAME}"
CONTRACT_PATH = f"{PREFIX}/{CONTRACT_NAME}"
BUNDLE_PATH = f"{PREFIX}/{BUNDLE_NAME}"
CHECKPOINT_PATH = f"{PREFIX}/{BUNDLE_NAME}/{CHECKPOINT_NAME}"
RESULT_PATH = f"{PREFIX}/{BUNDLE_NAME}/{RESULT_NAME}"
TERMINAL_RECEIPT_PATH = f"{PREFIX}/{TERMINAL_RECEIPT_NAME}"
CONTRACT = HERE / CONTRACT_NAME
CHECKPOINT = HERE / BUNDLE_NAME / CHECKPOINT_NAME
RESULT = HERE / BUNDLE_NAME / RESULT_NAME
TERMINAL_RECEIPT = HERE / TERMINAL_RECEIPT_NAME

CONTRACT_ID = "FH-L8-D11-PACKED-D3-QUOTIENT-CHECKPOINT-MATERIALIZATION-V1"
STATUS = "VERIFIED_D11_PACKED_DEPTH3_QUOTIENT_CHECKPOINT_MATERIALIZED_NO_Q4_AUTHORITY"
BASE_COMMIT = "b620f02ff53ed84472d0f38c775bdeb584fdf736"
BASE_TREE = "64dd609322f7c8741f7b6536ad9a78ed9af24e95"
D7_INTEGRATION_COMMIT = "9e415753383335578d649d88803ce193b16398f5"
D7_INTEGRATION_TREE = "c92dcfab269a56894573921abf5517e5f4ea0844"
D7_CONTRACT_COMMIT = "4544d4c0e02103c76e465abea43a08b91367a286"
SHA40_RE = re.compile(r"[0-9a-f]{40}")
SHA64_RE = re.compile(r"[0-9a-f]{64}")
_SOURCE_CACHE: dict[str, Any] | None = None
_SCIENCE_CACHE: dict[str, Any] | None = None
_SOURCE_CACHE_KEY: str | None = None

D7_ARTIFACTS = [
    {
        "path": "fh_l8_depth3_to_depth4_quotient_h_design_gate_checker.py",
        "mode": "100644",
        "blob": "7ce1e4325d698f90cbe4f9e06792dfdb76189b8a",
        "bytes": 38614,
        "sha256": "b43fcf1613fd2f3abd378c66261d2d01ca325446820bea735b5af4605dd379ae",
    },
    {
        "path": "fh_l8_depth3_to_depth4_quotient_h_design_gate_contract.json",
        "mode": "100644",
        "blob": "1ccb6fe77a439ceb643aa3cd5fcb236cb0ec92aa",
        "bytes": 15890,
        "sha256": "9557b9523b5d5f29d76a3d02dc50b76553879961dae7d168dc90080529fc61ed",
    },
    {
        "path": "FH_L8_DEPTH3_TO_DEPTH4_QUOTIENT_H_DESIGN_GATE_ZH.md",
        "mode": "100644",
        "blob": "39f198c8434452d78be27ee3dec8af592e0ec3a3",
        "bytes": 6295,
        "sha256": "350d970c8d4d903f8ae21c69699f12aec211461cd173db913876f02946832610",
    },
]

D5B_ARTIFACTS = [
    {
        "path": "fh_l8_symmetry_orbit_quotient_d5_checker.py",
        "mode": "100644",
        "blob": "129b8f7c12b19deaee518c5dfdbcf9047a91c418",
        "bytes": 48414,
        "sha256": "681bc63fedce8b71cfb536c66d321467bc8f01cb5947bee59b4291e2ac51a022",
    },
    {
        "path": "fh_l8_symmetry_orbit_quotient_d5_contract.json",
        "mode": "100644",
        "blob": "0969f7214db04f771a6533f7bb8ca702f71849fe",
        "bytes": 4999,
        "sha256": "1ebd1d38c0c40ca9617f86e09c86d528196260dd6b6b6692c34dacfe7a28d392",
    },
    {
        "path": "fh_l8_symmetry_orbit_quotient_d5_result.json",
        "mode": "100644",
        "blob": "f8b461b0d22e04413f01c49d072941be6d91c43b",
        "bytes": 9319,
        "sha256": "a04a4d0be6265dcaf9d39c7937fc133d19c7a2050e1434c7cb24be88b795baed",
    },
]

D6_ARTIFACTS = [
    {
        "path": "fh_l8_byte_table_orbit_d6_checker.py",
        "mode": "100644",
        "blob": "4a3083ae2c511b79d7a560f9a842c67ea10b77fd",
        "bytes": 6150,
        "sha256": "6877a5ed376a85a77000fe5d46dc39975294b3a266dda188c26a9aba92b647ad",
    },
    {
        "path": "fh_l8_byte_table_orbit_d6_contract.json",
        "mode": "100644",
        "blob": "fc5aa621be228a20d5c3a71db1139f4731dc181e",
        "bytes": 1146,
        "sha256": "ce2b6f29b86965e392cbf26fe2d6d9aba2f795d4ccc51804101f893c72f65374",
    },
    {
        "path": "fh_l8_byte_table_orbit_d6_result.json",
        "mode": "100644",
        "blob": "7ff34d654a9a34e4e2a8de86371d13e9ced2c942",
        "bytes": 1079,
        "sha256": "5645aba12743e71853e1f0ace734116fec96203f1a150097a66a8969de3d7418",
    },
]

D5A_ARTIFACTS = [
    {
        "path": "fh_l8_signed_d4_orbit_d5_checker.py",
        "mode": "100644",
        "blob": "0cbf87befd79ad4bc5d48f923c9effa5b13f96da",
        "bytes": 8716,
        "sha256": "1edf1275a4fa2e3407c5903876bf6000e0dabe0113a5e403c67ad4f7e0ff7bf7",
    },
    {
        "path": "fh_l8_signed_d4_orbit_d5_contract.json",
        "mode": "100644",
        "blob": "33818f489ae04ec7ac381929349b43ee1955f103",
        "bytes": 2000,
        "sha256": "0b3e1b53086e3c66af7d42aa3276c3624c14267dc89a77b84a1071cf05770441",
    },
    {
        "path": "fh_l8_signed_d4_orbit_d5_result.json",
        "mode": "100644",
        "blob": "a89c0bcd279f42fc570ad0057f2799f4c8b27991",
        "bytes": 2048,
        "sha256": "79d5251a0f433b8d79f5f7a5ed9916aea13146c0ff6f869f841ff53699eaa47b",
    },
]

UPSTREAM_D8_ARTIFACTS = [
    {
        "path": "fh_l8_packed_depth3_checkpoint_d8_checker.py",
        "mode": "100644",
        "blob": "72436ddecb37ab0344223b0343e113d030cbb5cd",
        "bytes": 4881,
        "sha256": "c8cbc65a325d47ef92b65498d8f8513565d295a375e503f196f288d5a2529467",
    },
    {
        "path": "fh_l8_packed_depth3_checkpoint_d8_contract.json",
        "mode": "100644",
        "blob": "3cab52cd4d5c2785a856a318d4fbca5de17b8e17",
        "bytes": 1837,
        "sha256": "fc140ef5af58d2978d8b24e15d63a81b2c30d09ae35526f1513f05f8e17c8a80",
    },
    {
        "path": "fh_l8_packed_depth3_checkpoint_d8_result.json",
        "mode": "100644",
        "blob": "a80d9dec0bdb1be4a2ebb7a837bb8aaa4ed74890",
        "bytes": 869,
        "sha256": "a987cd1a683d4e4eaf64be9f7d159645c33c1be11f334e998ba49688bcce40e3",
    },
]

UPSTREAM_D9_ARTIFACTS = [
    {
        "path": "fh_l8_depth4_preflight_d9.py",
        "mode": "100644",
        "blob": "3d812781070b58c4f3a745468daa2c1292ad5f1a",
        "bytes": 4107,
        "sha256": "90b1590301ffcdc2f5c181a8e4a5ed14bddb032a2b8284f2fd410301e1974d3e",
    },
    {
        "path": "fh_l8_depth4_preflight_d9_contract.json",
        "mode": "100644",
        "blob": "47cf6217484510caf76c099235039fc336ef18cd",
        "bytes": 422,
        "sha256": "070a9eb93bec73cd2ffb4f979b77d4afb544ab64e6c348fef1c4902c79b939e0",
    },
    {
        "path": "fh_l8_depth4_preflight_d9_receipt.json",
        "mode": "100644",
        "blob": "65a6fb7e56a6337cb88e66e83121a3e83d3db2c2",
        "bytes": 654,
        "sha256": "b310b09fb68eec400910099aecfe82da63d45b8bb8dd0fd15c9f736fb132c0f4",
    },
]

UPSTREAM_D10_ARTIFACTS = [
    {
        "path": "test_fh_l8_cgroup_envelope_d10.py",
        "mode": "100644",
        "blob": "b8d1b4f58cc7e1f51a7d89a2a8e368bbe03740c1",
        "bytes": 1018,
        "sha256": "5c34a9524291165633d7695b668dc5c48293193a83b72852f16a072c301f6ea7",
    },
    {
        "path": "fh_l8_cgroup_envelope_d10_contract.json",
        "mode": "100644",
        "blob": "f668ff7b579cf99c281bc800adcfe00e9dbe14d6",
        "bytes": 429,
        "sha256": "9fadd4e58ad65a0ddd9cb12ee09fd0e96dd0e09b270abb06a8858b20eb038ce3",
    },
    {
        "path": "fh_l8_cgroup_envelope_d10_receipt.json",
        "mode": "100644",
        "blob": "835fb18bd87c3c867f5747e4c250d8542388496e",
        "bytes": 630,
        "sha256": "6f61a66b579969d8319f25e75bdc92e7cd55d013f274483a258e75155d6e9788",
    },
]

UPSTREAM_PROGRESSION = {
    "d8_protocol_only": {
        "contract_id": "FH-L8-INDEPENDENT-REFERENCE-D8",
        "result_status": "VERIFIED_D8_PACKED_DEPTH3_QUOTIENT_CHECKPOINT_PROTOCOL_NO_MATERIALIZATION",
        "outcome": {
            "commit": "bae8f05598d1c94da1d0c66dd67e30cc32e4f3ff",
            "tree": "ac944d406bbe2173efcc23034b5454bee3e40bf3",
            "parents": ["9e415753383335578d649d88803ce193b16398f5"],
        },
        "integration": {
            "commit": "14e9a75dd9c455a4a5a87c80cc80c09dd6342341",
            "tree": "ac944d406bbe2173efcc23034b5454bee3e40bf3",
            "parents": [
                "9e415753383335578d649d88803ce193b16398f5",
                "bae8f05598d1c94da1d0c66dd67e30cc32e4f3ff",
            ],
        },
        "artifacts": UPSTREAM_D8_ARTIFACTS,
    },
    "d9_bounded_preflight": {
        "contract_id": "FH-L8-INDEPENDENT-REFERENCE-D9",
        "receipt_status": "VERIFIED_D9_PREFLIGHT_CGROUP_ENVELOPE_FAILURE_NO_FULL_RUN_AUTHORIZATION",
        "origin": {
            "commit": "ef9c43ecd8dc6954d303dfdfc457d31d09d39fe8",
            "tree": "14973ecbd25824078e3502d21d532f07e32d34e3",
            "parents": ["14e9a75dd9c455a4a5a87c80cc80c09dd6342341"],
        },
        "initial_integration": {
            "commit": "053155a6c53fb23612ed21b589aacc811dd6ecd8",
            "tree": "14973ecbd25824078e3502d21d532f07e32d34e3",
            "parents": [
                "14e9a75dd9c455a4a5a87c80cc80c09dd6342341",
                "ef9c43ecd8dc6954d303dfdfc457d31d09d39fe8",
            ],
        },
        "outcome": {
            "commit": "8693ab2b5c4d2153756c87304f5797976d723ff9",
            "tree": "40d47a8b43c972adadd0328f7c5c0634deac6cdd",
            "parents": ["ef9c43ecd8dc6954d303dfdfc457d31d09d39fe8"],
        },
        "clean_branch_tip": {
            "commit": "827e50d5d67dfeae94672ae4ee96252d21908be2",
            "tree": "ce4c5678e6d122ef2b79f0237effc60318ceeddd",
            "parents": ["8693ab2b5c4d2153756c87304f5797976d723ff9"],
        },
        "integration": {
            "commit": "dc600faca4b9a438fe9a3f154c87258f6269ee43",
            "tree": "ce4c5678e6d122ef2b79f0237effc60318ceeddd",
            "parents": [
                "053155a6c53fb23612ed21b589aacc811dd6ecd8",
                "827e50d5d67dfeae94672ae4ee96252d21908be2",
            ],
        },
        "artifacts": UPSTREAM_D9_ARTIFACTS,
    },
    "d10_cgroup_envelope": {
        "contract_id": "FH-L8-INDEPENDENT-REFERENCE-D10",
        "receipt_status": "VERIFIED_D9_BOUNDED_QUOTIENT_H_PREFLIGHT_NO_FULL_ACTION",
        "outcome": {
            "commit": "994e528025aeea3883a58eccb5053694181677b2",
            "tree": "58020e45817e481b3b69f5eab38f7512b84294fe",
            "parents": ["827e50d5d67dfeae94672ae4ee96252d21908be2"],
        },
        "integration": {
            "commit": "782cdcd26196de3e59dd59fc1ac3fc52e73abbbd",
            "tree": "58020e45817e481b3b69f5eab38f7512b84294fe",
            "parents": [
                "dc600faca4b9a438fe9a3f154c87258f6269ee43",
                "994e528025aeea3883a58eccb5053694181677b2",
            ],
        },
        "artifacts": UPSTREAM_D10_ARTIFACTS,
    },
    "relationship": {
        "D8_checkpoint_materialized": False,
        "D8_layout_reused_byte_for_byte": False,
        "D11_adds_big_endian_amplitude_and_D5B_insertion_rank": True,
        "D9_bounded_source_representatives": 4096,
        "D9_bounded_preflight_executed": True,
        "D9_memory_envelope_pass": False,
        "D10_repeats_the_bounded_preflight_under_one_GiB_zero_swap": True,
        "D10_memory_envelope_pass": True,
        "D10_full_run_authorized": False,
        "D11_materializes_q3_source_only": True,
        "D11_inherits_no_q3_to_q4_execution_authority": True,
    },
}

EXPECTED_AUTHORITY = {
    "packed_q3_checkpoint_materialized": True,
    "packed_q3_checkpoint_certified": True,
    "byte_table_definition_exhaustively_verified": True,
    "checkpoint_generation_completed_under_envelope": True,
    "upstream_bounded_4096_source_preflight_verified_under_envelope": True,
    "upstream_bounded_4096_source_preflight_executed": True,
    "this_unit_depth3_to_depth4_preflight_executed": False,
    "next_checkpointed_full_q3_to_q4_runner_protocol_design_eligible": True,
    "checkpointed_full_q3_to_q4_runner_execution_authorized": False,
    "depth3_to_depth4_execution_authorized": False,
    "depth3_to_depth4_quotient_hamiltonian_action_executed": False,
    "fourth_krylov_hamiltonian_action_executed": False,
    "target_vector_materialized": False,
    "target_cardinality_known": False,
    "runtime_feasibility_for_q3_to_q4_certified": False,
    "memory_feasibility_for_q3_to_q4_certified": False,
    "degree6_remainder_bounded": False,
    "two_step_cumulative_error_bounded": False,
    "full_R100_error_bounded": False,
    "physical_reference_qualified": False,
    "hardware_result_available": False,
    "quantum_advantage_claimed": False,
    "ready_gate_eligible": False,
}

EXPECTED_LIMITATIONS = [
    "The checkpoint contains the pinned depth-3 quotient source only; no depth-3 to depth-4 action is authorized or executed.",
    "The D11 record format is a separate self-verifying materialization format and does not claim byte compatibility with D8's unmaterialized layout.",
    "The binary digest is over ascending fixed-width records and is distinct from the D5B insertion-order quotient digest.",
    "The exhaustive byte-table test certifies support permutation entries, not fermionic phases or quotient amplitudes.",
    "Observed checkpoint-generation time and memory do not certify q3-to-q4 runtime or memory feasibility.",
    "No target vector, remainder, cumulative, R100, physical-reference, hardware, quantum-advantage, or READY claim is certified.",
    "D10 already verified only a bounded 4,096-source preflight under 1 GiB and zero swap; the eligible successor is a separately frozen checkpointed full q3-to-q4 runner protocol, and this result grants no execution authority.",
]


class VerificationError(ValueError):
    """A frozen source, chronology, checkpoint, or authority invariant failed."""


class ScientificNoGo(VerificationError):
    """The independent heavy replay disagreed with the frozen scientific payload."""


class ResourceIndeterminate(VerificationError):
    """The heavy replay did not complete inside the frozen host envelope."""


def _root() -> str:
    return subprocess.check_output(
        ["git", "-C", str(HERE), "rev-parse", "--show-toplevel"],
        stderr=subprocess.DEVNULL,
    ).decode("ascii").strip()


def _git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", _root(), *args], stderr=subprocess.DEVNULL
    )


def _load_json_bytes(raw: bytes) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise VerificationError(f"duplicate JSON key: {key}")
            output[key] = value
        return output

    value = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise VerificationError("JSON root must be an object")
    return value


def _read_stable_fd(
    fd: int, label: str, maximum_bytes: int, exact_bytes: int | None = None
) -> bytes:
    before = os.fstat(fd)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_size < 0
        or before.st_size > maximum_bytes
        or exact_bytes is not None
        and before.st_size != exact_bytes
    ):
        raise VerificationError(f"invalid regular input: {label}")
    chunks: list[bytes] = []
    remaining = before.st_size
    while remaining:
        chunk = os.read(fd, min(1_048_576, remaining))
        if not chunk:
            raise VerificationError(f"short read: {label}")
        chunks.append(chunk)
        remaining -= len(chunk)
    if os.read(fd, 1):
        raise VerificationError(f"input grew while reading: {label}")
    after = os.fstat(fd)
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise VerificationError(f"input changed while reading: {label}")
    return b"".join(chunks)


def _read_regular_nofollow(
    path: Path, maximum_bytes: int, exact_bytes: int | None = None
) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        return _read_stable_fd(fd, path.name, maximum_bytes, exact_bytes)
    finally:
        os.close(fd)


def _read_bundle_member_nofollow(
    name: str, maximum_bytes: int, exact_bytes: int | None = None
) -> bytes:
    parent_fd = os.open(HERE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        bundle_fd = os.open(
            BUNDLE_NAME,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        try:
            member_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=bundle_fd)
            try:
                return _read_stable_fd(
                    member_fd,
                    f"{BUNDLE_NAME}/{name}",
                    maximum_bytes,
                    exact_bytes,
                )
            finally:
                os.close(member_fd)
        finally:
            os.close(bundle_fd)
    finally:
        os.close(parent_fd)


def _commit_record(commit: str) -> dict[str, Any]:
    if not isinstance(commit, str) or SHA40_RE.fullmatch(commit) is None:
        raise VerificationError("full commit id required")
    if _git("rev-parse", f"{commit}^{{commit}}").decode("ascii").strip() != commit:
        raise VerificationError("commit id is not exact")
    return {
        "commit": commit,
        "tree": _git("rev-parse", f"{commit}^{{tree}}").decode("ascii").strip(),
        "parents": _git("rev-list", "--parents", "-n", "1", commit)
        .decode("ascii")
        .split()[1:],
    }


def _verify_commit(record: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    if record != expected or _commit_record(str(record.get("commit", ""))) != expected:
        raise VerificationError("commit record or topology drift")


def _path_exists(commit: str, path: str) -> bool:
    try:
        _git("cat-file", "-e", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        return False
    return True


def _diff_entries(commit: str) -> set[tuple[str, str]]:
    raw = _git("diff-tree", "--no-commit-id", "--name-status", "-r", "-z", commit)
    parts = raw.rstrip(b"\0").split(b"\0") if raw else []
    if len(parts) % 2:
        raise VerificationError("malformed NUL-delimited Git diff")
    entries: set[tuple[str, str]] = set()
    for index in range(0, len(parts), 2):
        status = parts[index].decode("ascii")
        path = parts[index + 1].decode("utf-8", errors="strict")
        if status not in {"A", "M", "D", "T"} or (status, path) in entries:
            raise VerificationError("unsupported/duplicate Git diff entry")
        entries.add((status, path))
    return entries


def _require_mode(commit: str, path: str, expected: str = "100644") -> None:
    fields = _git("ls-tree", commit, path).decode("ascii").split()
    if len(fields) < 3 or fields[0] != expected or fields[1] != "blob":
        raise VerificationError(f"Git mode/type drift: {path}")


def _verify_artifacts(
    commit: str,
    artifacts: Any,
    expected: list[dict[str, Any]],
) -> dict[str, bytes]:
    if artifacts != expected:
        raise VerificationError("artifact pin family drift")
    loaded: dict[str, bytes] = {}
    for artifact in expected:
        path = f"{PREFIX}/{artifact['path']}"
        raw = _git("show", f"{commit}:{path}")
        entry = _git("ls-tree", commit, path).decode("ascii").split()
        if (
            len(entry) < 3
            or entry[0] != artifact["mode"]
            or entry[1] != "blob"
            or entry[2] != artifact["blob"]
            or len(raw) != artifact["bytes"]
            or hashlib.sha256(raw).hexdigest() != artifact["sha256"]
        ):
            raise VerificationError(f"artifact identity drift: {artifact['path']}")
        if _read_regular_nofollow(HERE / artifact["path"], 1_048_576) != raw:
            raise VerificationError(f"working artifact drift: {artifact['path']}")
        loaded[artifact["path"]] = raw
    return loaded


def validate_contract(contract: Mapping[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "contract_id",
        "status",
        "analysis_class",
        "chronology",
        "protocol_artifacts",
        "source_evidence",
        "workload",
        "checkpoint_encoding",
        "byte_table_qualification",
        "resource_limits",
        "verification_modes",
        "decision_rule",
        "authority_ceiling",
        "forbidden_claims",
    }
    if set(contract) != expected_keys:
        raise VerificationError("contract schema drift")
    if (
        type(contract["schema_version"]) is not int
        or contract["schema_version"] != 1
        or contract["contract_id"] != CONTRACT_ID
        or contract["status"] != "PROTOCOL_FROZEN_BEFORE_PACKED_Q3_REPLAY"
        or contract["analysis_class"]
        != "PREREGISTERED_DEPTH0_TO_DEPTH3_REPLAY_AND_CHECKPOINT_ONLY"
    ):
        raise VerificationError("contract identity/status drift")
    if contract["workload"] != {
        "linear_size": 8,
        "boundary": "square_open_boundary_no_wrap",
        "particle_sector": "N_up=32,N_down=32",
        "replayed_source_depths": [0, 1, 2],
        "materialized_depth": 3,
        "expected_full_state_count": 1704285,
        "expected_representative_count": 213099,
        "expected_full_vector_sha256": "6f8f53101b8a3ec0b3dfcee624a014426d93a8aa0dfc1300780b0ad99b765e97",
        "expected_D5B_insertion_order_quotient_sha256": "7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e",
        "expected_D6_sorted_support_orbit_sha256": "7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26",
        "expected_depth_records": [
            {"depth": 0, "full_state_count": 1, "full_vector_sha256": "4851eca743653e8f5e4b1aaa7796811bc24f1bca5e23432e5bc96bfd9882bec9"},
            {"depth": 1, "full_state_count": 225, "full_vector_sha256": "9cbbe6d7e508bd37eef5ec54bfa5b580b80d0b3dc3998146c900d03220a847b3"},
            {"depth": 2, "full_state_count": 24421, "full_vector_sha256": "c92f2de07caa1a289d7aa27cd0fa64e707e084cf96e06219161ea55ff3f3c88b"},
            {"depth": 3, "full_state_count": 1704285, "full_vector_sha256": "6f8f53101b8a3ec0b3dfcee624a014426d93a8aa0dfc1300780b0ad99b765e97"},
        ],
        "expected_orbit_size_histogram": {"1": 1, "4": 125, "8": 212973},
        "hamiltonian_action_call_budget": 3,
        "allowed_acted_source_depths": [0, 1, 2],
        "depth3_to_depth4_action_authorized": False,
    }:
        raise VerificationError("workload drift")
    if contract["checkpoint_encoding"] != {
        "format_id": "FH-L8-D11-PACKED-Q3-RECORD-V1",
        "format": "headerless_fixed_width_records",
        "record_order": "strictly_ascending_unsigned_representative",
        "representative": "unsigned_u128_big_endian_16_bytes",
        "amplitude": "signed_i64_twos_complement_big_endian_8_bytes",
        "orbit_size": "unsigned_u8_allowed_1_4_8",
        "flags": "unsigned_u8_must_be_zero",
        "reserved": "unsigned_u16_big_endian_must_be_zero",
        "d5b_insertion_rank": "unsigned_u32_big_endian_permutation_0_to_213098",
        "field_offsets": {"representative": 0, "amplitude": 16, "orbit_size": 24, "flags": 25, "reserved": 26, "d5b_insertion_rank": 28},
        "record_bytes": 32,
        "record_count": 213099,
        "total_bytes": 6819168,
        "file_header_bytes": 0,
        "file_trailer_bytes": 0,
        "zero_amplitudes_allowed": False,
        "maximum_absolute_amplitude": 43614208,
    }:
        raise VerificationError("checkpoint encoding drift")
    if contract["byte_table_qualification"] != {
        "group_elements": 8,
        "source_byte_chunks": 16,
        "byte_values_per_chunk": 256,
        "expected_definition_entries": 32768,
        "entry_encoding": "unsigned_u128_big_endian_16_bytes",
        "direct_reference": "D5B_generic_mode_action_support_target",
        "required_checks": [
            "all_entries_equal_direct_reference",
            "zero_entry_maps_to_zero",
            "each_mode_image_is_one_hot",
            "each_byte_value_is_disjoint_or_of_one_hot_images",
            "mode_images_are_pairwise_disjoint",
            "each_group_mode_permutation_is_bijective",
        ],
        "phase_or_amplitude_authority": False,
    }:
        raise VerificationError("byte-table qualification drift")
    limits = contract["resource_limits"]
    if limits != {
        "outer_memory_max_bytes": 1073741824,
        "outer_memory_high_bytes": 805306368,
        "outer_swap_max_bytes": 0,
        "internal_deadline_seconds": 300,
        "outer_deadline_seconds": 330,
        "max_process_peak_rss_bytes": 536870912,
        "max_cgroup_peak_bytes": 805306368,
        "max_initial_cgroup_peak_bytes": 134217728,
        "max_source_bytes_per_artifact": 1048576,
        "max_materialized_full_states": 2000000,
        "max_orbit_relation_group_images": 16000000,
        "max_checkpoint_records": 213099,
        "max_checkpoint_bytes": 6819168,
        "max_result_bytes": 131072,
        "max_terminal_receipt_bytes": 32768,
        "max_runner_stdout_capture_bytes": 32768,
        "max_runner_stderr_capture_bytes": 32768,
        "max_packing_sort_buffer_bytes": 33554432,
        "max_io_chunk_bytes": 1048576,
        "max_live_scratch_bytes": 16777216,
        "max_application_payload_writes_bytes": 16777216,
        "max_created_regular_files": 4,
        "max_created_directories": 1,
        "max_open_file_descriptors": 32,
        "minimum_output_free_bytes": 33554432,
    }:
        raise VerificationError("resource-limit drift")
    if contract["verification_modes"] != {
        "static_protocol": {
            "outcome_commit_required": False,
            "full_q3_rebuilt": False,
            "hamiltonian_action_calls": 0,
        },
        "official_execute": {
            "launcher": "checker_systemd_scope_capture",
            "runner_exit_code_required": 0,
            "terminal_execution_receipt_required": True,
            "full_q3_rebuilt": True,
            "hamiltonian_action_calls": 3,
        },
        "static_outcome": {
            "outcome_commit_required": True,
            "full_q3_rebuilt": False,
            "hamiltonian_action_calls": 0,
        },
        "heavy_outcome": {
            "outcome_commit_required": True,
            "full_q3_rebuilt": True,
            "hamiltonian_action_calls": 3,
            "maximum_acted_source_depth": 2,
            "fourth_action_executed": False,
        },
        "runner_and_checker_use_independent_control_flow_and_serialization": True,
        "independent_hamiltonian_implementation_claimed": False,
    }:
        raise VerificationError("verification-mode schema drift")
    if contract["decision_rule"] != {
        "source_protocol_schema_encoding_or_committed_artifact_failure": "VERIFICATION_FAILED",
        "official_replay_scientific_mismatch": "NO_GO_D11_PACKED_Q3_CHECKPOINT_SEMANTICS",
        "resource_timeout_oom_cap_or_missing_terminal_receipt": "INDETERMINATE_D11_PACKED_Q3_CHECKPOINT_RESOURCE_ENVELOPE",
        "all_checkpoint_gates_true": STATUS,
        "execution_authority_on_any_outcome": False,
        "next_gate": "CHECKPOINTED_FULL_QUOTIENT_H_RUNNER_IMPLEMENTATION_AND_AUTHORIZATION",
    }:
        raise VerificationError("decision-rule drift")
    if contract["authority_ceiling"] != {
        "packed_q3_checkpoint_generation_authorized": True,
        "depth0_to_depth3_replay_authorized": True,
        "byte_table_definition_validation_authorized": True,
        "upstream_bounded_4096_source_preflight_verified_under_envelope": True,
        "checkpointed_full_q3_to_q4_runner_protocol_design_eligible": True,
        "checkpointed_full_q3_to_q4_runner_execution_authorized": False,
        "depth3_to_depth4_execution_authorized": False,
        "fourth_krylov_hamiltonian_action_authorized": False,
    }:
        raise VerificationError("authority ceiling drift")
    if contract["forbidden_claims"] != EXPECTED_LIMITATIONS:
        raise VerificationError("forbidden claim boundary drift")


def verify_protocol(contract: Mapping[str, Any], contract_commit: str) -> dict[str, Any]:
    validate_contract(contract)
    chronology = contract["chronology"]
    if set(chronology) != {
        "evidence_baseline",
        "protocol_source_freeze",
        "contract_path",
        "bundle_path",
        "checkpoint_path",
        "result_path",
        "terminal_receipt_path",
        "source_must_precede_contract",
        "outputs_must_be_absent_before_official_replay",
    }:
        raise VerificationError("chronology schema drift")
    baseline = {
        "commit": BASE_COMMIT,
        "tree": BASE_TREE,
        "parents": [
            "14b884b2c6a808a8955a13f172051fbb692b8b57",
        ],
    }
    _verify_commit(chronology["evidence_baseline"], baseline)
    freeze = chronology["protocol_source_freeze"]
    if set(freeze) != {"commit", "tree", "parents"} or freeze["parents"] != [BASE_COMMIT]:
        raise VerificationError("protocol source freeze topology drift")
    _verify_commit(freeze, freeze)
    source_diff = _diff_entries(freeze["commit"])
    if source_diff != {("A", CHECKER_PATH), ("A", RUNNER_PATH)}:
        raise VerificationError("protocol source freeze must add only checker and runner")
    if (
        not isinstance(contract["protocol_artifacts"], list)
        or len(contract["protocol_artifacts"]) != 2
        or any(
            set(item) != {"path", "mode", "blob", "bytes", "sha256"}
            or item["mode"] != "100644"
            or type(item["bytes"]) is not int
            or not 0 < item["bytes"] <= contract["resource_limits"]["max_source_bytes_per_artifact"]
            or SHA40_RE.fullmatch(str(item["blob"])) is None
            or SHA64_RE.fullmatch(str(item["sha256"])) is None
            for item in contract["protocol_artifacts"]
        )
    ):
        raise VerificationError("protocol artifact schema/mode drift")
    if {item.get("path") for item in contract["protocol_artifacts"]} != {CHECKER_NAME, RUNNER_NAME}:
        raise VerificationError("protocol artifact family drift")
    _verify_artifacts(
        freeze["commit"], contract["protocol_artifacts"], contract["protocol_artifacts"]
    )
    _require_mode(freeze["commit"], CHECKER_PATH)
    _require_mode(freeze["commit"], RUNNER_PATH)
    for path in (
        CONTRACT_PATH,
        CHECKPOINT_PATH,
        RESULT_PATH,
        TERMINAL_RECEIPT_PATH,
    ):
        if _path_exists(freeze["commit"], path):
            raise VerificationError("contract/output existed in protocol source freeze")
    if (
        chronology["contract_path"] != CONTRACT_PATH
        or chronology["bundle_path"] != BUNDLE_PATH
        or chronology["checkpoint_path"] != CHECKPOINT_PATH
        or chronology["result_path"] != RESULT_PATH
        or chronology["terminal_receipt_path"] != TERMINAL_RECEIPT_PATH
        or chronology["source_must_precede_contract"] is not True
        or chronology["outputs_must_be_absent_before_official_replay"] is not True
    ):
        raise VerificationError("chronology policy drift")
    contract_record = _commit_record(contract_commit)
    if contract_record["parents"] != [freeze["commit"]]:
        raise VerificationError("contract commit must directly descend from source freeze")
    contract_diff = _diff_entries(contract_commit)
    if contract_diff != {("A", CONTRACT_PATH)}:
        raise VerificationError("contract freeze must add only the contract")
    _require_mode(contract_commit, CONTRACT_PATH)
    if _git("show", f"{contract_commit}:{CONTRACT_PATH}") != _read_regular_nofollow(
        CONTRACT, 1_048_576
    ):
        raise VerificationError("working contract differs from frozen contract")
    for path, name in ((CHECKER_PATH, CHECKER_NAME), (RUNNER_PATH, RUNNER_NAME)):
        if _git("show", f"{contract_commit}:{path}") != _read_regular_nofollow(
            HERE / name, 1_048_576
        ):
            raise VerificationError("protocol source changed after freeze")
    for path in (CHECKPOINT_PATH, RESULT_PATH, TERMINAL_RECEIPT_PATH):
        if _path_exists(contract_commit, path):
            raise VerificationError("official output existed in contract freeze")
    matches = []
    for path in _git("ls-tree", "-r", "--name-only", contract_commit, PREFIX).decode("utf-8").splitlines():
        if path.endswith(".json") and CONTRACT_ID.encode("ascii") in _git("show", f"{contract_commit}:{path}"):
            matches.append(path)
    if matches != [CONTRACT_PATH]:
        raise VerificationError("contract id is not globally unique")
    return {
        "protocol_source_freeze_commit": freeze["commit"],
        "protocol_source_freeze_tree": freeze["tree"],
        "contract_freeze_commit": contract_record["commit"],
        "contract_freeze_tree": contract_record["tree"],
        "outputs_absent_before_official_replay": True,
        "terminal_receipt_path": TERMINAL_RECEIPT_PATH,
        "terminal_receipt_required_for_outcome": True,
    }


def _module_from_bytes(name: str, filename: str, raw: bytes) -> Any:
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(HERE / filename)
    exec(compile(raw, module.__file__, "exec"), module.__dict__)
    return module


def verify_sources(contract: Mapping[str, Any]) -> dict[str, Any]:
    global _SOURCE_CACHE, _SCIENCE_CACHE, _SOURCE_CACHE_KEY
    source = contract["source_evidence"]
    source_cache_key = hashlib.sha256(
        json.dumps(
            source,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    if _SOURCE_CACHE_KEY != source_cache_key:
        _SOURCE_CACHE = None
        _SCIENCE_CACHE = None
    if set(source) != {
        "d7_design_gate",
        "upstream_progression",
        "d5b_full_quotient_lane",
        "d6_byte_table_support_lane",
        "d5a_direct_support_reference",
        "relationship",
    }:
        raise VerificationError("source evidence schema drift")
    d7 = source["d7_design_gate"]
    expected_baseline = {
        "commit": D7_INTEGRATION_COMMIT,
        "tree": D7_INTEGRATION_TREE,
        "parents": [
            "72e1e56af49b91267738d0b0108640f358fde59a",
            "6a9b97a0ee0c7d37878f3f267cfc07d002c86ada",
        ],
    }
    if set(d7) != {"contract_id", "status", "integration", "contract_freeze_commit", "artifacts"}:
        raise VerificationError("D7 source schema drift")
    if (
        d7["contract_id"] != "FH-L8-QUOTIENT-H-D3-TO-D4-DESIGN-GATE-V1"
        or d7["status"] != "VERIFIED_D7_QUOTIENT_H_DESIGN_GATE_FROZEN_NO_EXECUTION_AUTHORITY"
        or d7["contract_freeze_commit"] != D7_CONTRACT_COMMIT
    ):
        raise VerificationError("D7 source identity drift")
    _verify_commit(d7["integration"], expected_baseline)
    upstream = source["upstream_progression"]
    if upstream != UPSTREAM_PROGRESSION:
        raise VerificationError("D8-D10 upstream progression drift")
    upstream_loaded: dict[str, dict[str, bytes]] = {}
    for stage_name, expected_artifacts in (
        ("d8_protocol_only", UPSTREAM_D8_ARTIFACTS),
        ("d9_bounded_preflight", UPSTREAM_D9_ARTIFACTS),
        ("d10_cgroup_envelope", UPSTREAM_D10_ARTIFACTS),
    ):
        stage = upstream[stage_name]
        for record_name in (
            "origin",
            "initial_integration",
            "outcome",
            "clean_branch_tip",
            "integration",
        ):
            if record_name in stage:
                _verify_commit(
                    stage[record_name],
                    UPSTREAM_PROGRESSION[stage_name][record_name],
                )
        upstream_loaded[stage_name] = _verify_artifacts(
            stage["outcome"]["commit"], stage["artifacts"], expected_artifacts
        )
    d8_contract = _load_json_bytes(
        upstream_loaded["d8_protocol_only"][
            "fh_l8_packed_depth3_checkpoint_d8_contract.json"
        ]
    )
    d8_result = _load_json_bytes(
        upstream_loaded["d8_protocol_only"][
            "fh_l8_packed_depth3_checkpoint_d8_result.json"
        ]
    )
    d9_contract = _load_json_bytes(
        upstream_loaded["d9_bounded_preflight"][
            "fh_l8_depth4_preflight_d9_contract.json"
        ]
    )
    d9_receipt = _load_json_bytes(
        upstream_loaded["d9_bounded_preflight"][
            "fh_l8_depth4_preflight_d9_receipt.json"
        ]
    )
    d10_contract = _load_json_bytes(
        upstream_loaded["d10_cgroup_envelope"][
            "fh_l8_cgroup_envelope_d10_contract.json"
        ]
    )
    d10_receipt = _load_json_bytes(
        upstream_loaded["d10_cgroup_envelope"][
            "fh_l8_cgroup_envelope_d10_receipt.json"
        ]
    )
    if (
        d8_contract.get("contract_id") != upstream["d8_protocol_only"]["contract_id"]
        or d8_contract.get("record_layout", {}).get("fields", [None, None])[1]
        != {"name": "amplitude_i64_le", "offset": 16, "bytes": 8}
        or d8_result.get("status") != upstream["d8_protocol_only"]["result_status"]
        or d8_result.get("checkpoint_materialized") is not False
        or d9_contract.get("contract_id")
        != upstream["d9_bounded_preflight"]["contract_id"]
        or d9_contract.get("limits", {}).get("source_representatives") != 4096
        or d9_receipt.get("status")
        != upstream["d9_bounded_preflight"]["receipt_status"]
        or d9_receipt.get("memory_envelope_pass") is not False
        or d9_receipt.get("full_run_authorized") is not False
        or d10_contract.get("contract_id")
        != upstream["d10_cgroup_envelope"]["contract_id"]
        or d10_contract.get("method") != "systemd_run_user_transient_scope"
        or d10_contract.get("required")
        != {
            "memory_max": "1073741824",
            "memory_swap_max": "0",
            "memory_high": "805306368",
            "preflight_sources": 4096,
        }
        or d10_receipt.get("status")
        != upstream["d10_cgroup_envelope"]["receipt_status"]
        or d10_receipt.get("memory_envelope_pass") is not True
        or d10_receipt.get("memory_max") != "1073741824"
        or d10_receipt.get("memory_swap_max") != "0"
        or d10_receipt.get("full_run_authorized") is not False
        or d10_receipt.get("fourth_action_executed") is not False
    ):
        raise VerificationError("D8-D10 upstream semantic boundary drift")

    full = source["d5b_full_quotient_lane"]
    support = source["d6_byte_table_support_lane"]
    direct = source["d5a_direct_support_reference"]
    if set(full) != {"route_alias", "scope", "outcome", "artifacts"}:
        raise VerificationError("D5B source schema drift")
    if set(support) != {"route_alias", "scope", "outcome", "artifacts"}:
        raise VerificationError("D6 source schema drift")
    if set(direct) != {"route_alias", "scope", "outcome", "artifacts"}:
        raise VerificationError("D5A source schema drift")
    if (
        full["route_alias"] != "FH-L8-D5-EVIDENCE-SYMMETRY-ORBIT-QUOTIENT-V1"
        or full["scope"] != "full_depth3_signed_quotient_semantics_and_source_amplitudes"
        or support["route_alias"] != "FH-L8-D6-EVIDENCE-BYTE-TABLE-SUPPORT-ORBIT-V1"
        or support["scope"] != "byte_table_support_only_no_phase_or_amplitude"
        or direct["route_alias"] != "FH-L8-D5A-EVIDENCE-DIRECT-SIGNED-D4-SUPPORT-V1"
        or direct["scope"] != "direct_mode_permutation_reference_only"
    ):
        raise VerificationError("source route/scope drift")
    expected_d5b = {
        "commit": "2f9556a986c50a42ff3096ded45b75e39c5a61a9",
        "tree": "c1164c1acffb570448038b461cc619ca5164d2f9",
        "parents": ["6daf30daeeb375962b9986af5df91517d8a4a8ec"],
    }
    expected_d6 = {
        "commit": "e45b5b9f68520289d3396c0af071019856afe56e",
        "tree": "80724d12483ec39e0926ca4bfa341c6483eb27f9",
        "parents": ["64438c47be710835626dea0ceb2521b6634951dc"],
    }
    expected_d5a = {
        "commit": "72fe3b79a79501d5d523dc959a6a98b36a470bd4",
        "tree": "fa4ce50442da0e4c8e617d7d3497fea4cf34c49b",
        "parents": ["ae3935774d80f37b10f8317d0e17d339f03436cc"],
    }
    _verify_commit(full["outcome"], expected_d5b)
    _verify_commit(support["outcome"], expected_d6)
    _verify_commit(direct["outcome"], expected_d5a)
    if source["relationship"] != {
        "D7_authorizes_checkpoint_protocol_only": True,
        "D5B_supplies_signed_CAR_quotient_coordinates_and_amplitudes": True,
        "D6_supplies_support_byte_tables_only": True,
        "D5A_supplies_direct_support_permutations_only": True,
        "D6_or_D5A_supplies_phase_or_amplitude": False,
        "bare_legacy_contract_id_lookup_forbidden": True,
        "evidence_is_additive": False,
    }:
        raise VerificationError("source relationship drift")

    if _SOURCE_CACHE is None or _SCIENCE_CACHE is None:
        d7_loaded = _verify_artifacts(
            D7_INTEGRATION_COMMIT, d7["artifacts"], D7_ARTIFACTS
        )
        d5b_loaded = _verify_artifacts(expected_d5b["commit"], full["artifacts"], D5B_ARTIFACTS)
        d6_loaded = _verify_artifacts(expected_d6["commit"], support["artifacts"], D6_ARTIFACTS)
        d5a_loaded = _verify_artifacts(expected_d5a["commit"], direct["artifacts"], D5A_ARTIFACTS)
        d7_contract = _load_json_bytes(
            d7_loaded["fh_l8_depth3_to_depth4_quotient_h_design_gate_contract.json"]
        )
        d7_module = _module_from_bytes(
            "fh_l8_d7_source_for_d11",
            "fh_l8_depth3_to_depth4_quotient_h_design_gate_checker.py",
            d7_loaded["fh_l8_depth3_to_depth4_quotient_h_design_gate_checker.py"],
        )
        evidence = d7_module.recompute(d7_contract, D7_CONTRACT_COMMIT)
        if evidence.get("status") != d7_module.STATUS or evidence.get("verified") is not True:
            raise VerificationError("D7 design gate replay drift")

        d5b_result = _load_json_bytes(d5b_loaded["fh_l8_symmetry_orbit_quotient_d5_result.json"])
        depth3 = d5b_result["krylov_prefix"]["depth_records"][3]
        if (
            depth3.get("full_state_count") != 1704285
            or depth3.get("orbit_representative_count") != 213099
            or depth3.get("full_vector_sha256")
            != "6f8f53101b8a3ec0b3dfcee624a014426d93a8aa0dfc1300780b0ad99b765e97"
            or depth3.get("deterministic_insertion_order_quotient_sha256")
            != "7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e"
            or depth3.get("orbit_size_histogram") != {"1": 1, "4": 125, "8": 212973}
        ):
            raise VerificationError("D5B depth-3 source drift")
        d6_result = _load_json_bytes(d6_loaded["fh_l8_byte_table_orbit_d6_result.json"])
        if (
            d6_result.get("status") != "VERIFIED_D6_BYTE_TABLE_SIGNED_D4_DEPTH3_ORBITS"
            or d6_result.get("depth3_orbit")
            != {"states": 1704285, "orbits": 213099, "digest": "7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26"}
        ):
            raise VerificationError("D6 support source drift")
        d5a_result = _load_json_bytes(d5a_loaded["fh_l8_signed_d4_orbit_d5_result.json"])
        if d5a_result.get("status") != "VERIFIED_D5_SIGNED_D4_CUSTODY_AND_DEPTH3_ORBIT_PREFIX_BOUNDARY":
            raise VerificationError("D5A direct support source drift")

        d5b_module = _module_from_bytes(
            "fh_l8_d5b_science_for_d11",
            "fh_l8_symmetry_orbit_quotient_d5_checker.py",
            d5b_loaded["fh_l8_symmetry_orbit_quotient_d5_checker.py"],
        )
        d6_module = _module_from_bytes(
            "fh_l8_d6_support_for_d11",
            "fh_l8_byte_table_orbit_d6_checker.py",
            d6_loaded["fh_l8_byte_table_orbit_d6_checker.py"],
        )
        d5a_module = _module_from_bytes(
            "fh_l8_d5a_direct_for_d11",
            "fh_l8_signed_d4_orbit_d5_checker.py",
            d5a_loaded["fh_l8_signed_d4_orbit_d5_checker.py"],
        )
        d5b_contract = _load_json_bytes(d5b_loaded["fh_l8_symmetry_orbit_quotient_d5_contract.json"])
        symmetries, _ = d5b_module._build_symmetries(d5b_contract)
        d5a_permutations = d5a_module._build_perms()
        tables = d6_module._tables(d5a_permutations)
        _SCIENCE_CACHE = {
            "d5b_module": d5b_module,
            "d5b_contract": d5b_contract,
            "symmetries": symmetries,
            "d6_module": d6_module,
            "d6_tables": tables,
            "d5a_permutations": d5a_permutations,
        }
        _SOURCE_CACHE = {
            "d7_design_gate_verified": True,
            "d8_protocol_only_verified": True,
            "d8_checkpoint_materialized": False,
            "d9_bounded_preflight_record_verified": True,
            "d9_bounded_preflight_executed": True,
            "d9_memory_envelope_pass": False,
            "d10_one_gib_zero_swap_preflight_verified": True,
            "d10_memory_envelope_pass": True,
            "d10_full_run_authorized": False,
            "d5b_route_alias": full["route_alias"],
            "d6_route_alias": support["route_alias"],
            "d5a_route_alias": direct["route_alias"],
            "depth3_full_states": 1704285,
            "depth3_representatives": 213099,
            "legacy_d5b_insertion_json_sha256": "7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e",
            "d6_sorted_support_orbit_sha256": "7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26",
            "evidence_is_additive": False,
        }
        _SOURCE_CACHE_KEY = source_cache_key
    # Recheck raw working/Git bytes on every call; the module cache is keyed by
    # contract evidence, but mutable working files must never inherit trust.
    _verify_artifacts(D7_INTEGRATION_COMMIT, d7["artifacts"], D7_ARTIFACTS)
    _verify_artifacts(expected_d5b["commit"], full["artifacts"], D5B_ARTIFACTS)
    _verify_artifacts(expected_d6["commit"], support["artifacts"], D6_ARTIFACTS)
    _verify_artifacts(expected_d5a["commit"], direct["artifacts"], D5A_ARTIFACTS)
    return dict(_SOURCE_CACHE)


def verify_byte_tables(contract: Mapping[str, Any]) -> dict[str, Any]:
    verify_sources(contract)
    assert _SCIENCE_CACHE is not None
    symmetries = _SCIENCE_CACHE["symmetries"]
    d5a_permutations = _SCIENCE_CACHE["d5a_permutations"]
    tables = _SCIENCE_CACHE["d6_tables"]
    digest = hashlib.sha256()
    checks = 0
    zero_checks = 0
    one_hot_checks = 0
    disjoint_or_checks = 0
    for group_index, (symmetry, (legacy_name, legacy_permutation), group_tables) in enumerate(
        zip(symmetries, d5a_permutations, tables)
    ):
        permutation = tuple(symmetry["mode_permutation"])
        if tuple(legacy_permutation) != permutation:
            raise VerificationError(f"D5A/D5B mode-permutation drift at group {group_index}")
        images = []
        for mode in range(128):
            image = group_tables[mode // 8][1 << (mode % 8)]
            if image.bit_count() != 1 or image != 1 << permutation[mode]:
                raise VerificationError("byte-table one-hot image drift")
            images.append(image)
            one_hot_checks += 1
        if len(set(images)) != 128 or sorted(value.bit_length() - 1 for value in images) != list(range(128)):
            raise VerificationError("byte-table group permutation is not bijective")
        for chunk in range(16):
            for value in range(256):
                expected = 0
                for bit in range(8):
                    if (value >> bit) & 1:
                        image = 1 << permutation[8 * chunk + bit]
                        if expected & image:
                            raise VerificationError("byte-table one-hot images overlap")
                        expected |= image
                observed = group_tables[chunk][value]
                if observed != expected:
                    raise VerificationError("D6 table differs from D5B direct support action")
                if value == 0:
                    if observed != 0:
                        raise VerificationError("byte-table zero entry drift")
                    zero_checks += 1
                digest.update(observed.to_bytes(16, "big", signed=False))
                checks += 1
                disjoint_or_checks += 1
    if checks != 32768:
        raise VerificationError("byte-table definition coverage drift")
    return {
        "group_elements": 8,
        "group_order": ["I", "R90", "R180", "R270", "MX", "MY", "MD", "MA"],
        "source_byte_chunks": 16,
        "byte_values_per_chunk": 256,
        "definition_entries": 32768,
        "direct_reference_checks": checks,
        "zero_entry_checks": zero_checks,
        "one_hot_mode_image_checks": one_hot_checks,
        "disjoint_or_checks": disjoint_or_checks,
        "pairwise_disjoint_group_checks": 8,
        "bijective_group_checks": 8,
        "table_bytes_hashed": 524288,
        "table_sha256": digest.hexdigest(),
        "all_entries_equal_direct_reference": True,
        "phase_checks": 0,
        "phase_or_amplitude_authority": False,
    }


def parse_checkpoint(raw: bytes, contract: Mapping[str, Any]) -> dict[str, Any]:
    verify_sources(contract)
    assert _SCIENCE_CACHE is not None
    d5b = _SCIENCE_CACHE["d5b_module"]
    symmetries = _SCIENCE_CACHE["symmetries"]
    d6 = _SCIENCE_CACHE["d6_module"]
    tables = _SCIENCE_CACHE["d6_tables"]
    encoding = contract["checkpoint_encoding"]
    if len(raw) != encoding["total_bytes"] or len(raw) > contract["resource_limits"]["max_checkpoint_bytes"]:
        raise VerificationError("checkpoint byte length drift")
    record_bytes = encoding["record_bytes"]
    if len(raw) % record_bytes:
        raise VerificationError("partial checkpoint record")
    count = len(raw) // record_bytes
    if count != encoding["record_count"] or count > contract["resource_limits"]["max_checkpoint_records"]:
        raise VerificationError("checkpoint record count drift")
    previous = -1
    min_rep = None
    max_rep = None
    max_abs = 0
    positive = 0
    negative = 0
    amplitude_sum = 0
    orbit_histogram: dict[str, int] = {}
    coverage_sum = 0
    insertion_records: list[tuple[int, int, int] | None] = [None] * count
    seen_ranks = bytearray(count)
    legacy_digest = hashlib.sha256()
    support_digest = hashlib.sha256()
    semantic_digest = hashlib.sha256()
    support_digest.update(b"[")
    semantic_digest.update(b"[")
    even_mask = int("55" * 16, 16)
    canonicality_checks = 0
    d6_nomination_checks = 0
    for offset in range(0, len(raw), record_bytes):
        representative = int.from_bytes(raw[offset : offset + 16], "big", signed=False)
        amplitude = int.from_bytes(raw[offset + 16 : offset + 24], "big", signed=True)
        orbit_size = raw[offset + 24]
        flags = raw[offset + 25]
        reserved = int.from_bytes(raw[offset + 26 : offset + 28], "big", signed=False)
        insertion_rank = int.from_bytes(raw[offset + 28 : offset + 32], "big", signed=False)
        if representative <= previous:
            raise VerificationError("checkpoint representatives are not strictly ascending")
        if amplitude == 0:
            raise VerificationError("checkpoint contains a zero amplitude")
        if abs(amplitude) > encoding["maximum_absolute_amplitude"]:
            raise VerificationError("checkpoint amplitude exceeds frozen bound")
        if orbit_size not in (1, 4, 8):
            raise VerificationError("checkpoint orbit size is not admissible")
        if flags != 0 or reserved != 0:
            raise VerificationError("checkpoint flags/reserved bytes are nonzero")
        if insertion_rank >= count or seen_ranks[insertion_rank]:
            raise VerificationError("checkpoint insertion ranks are not a permutation")
        seen_ranks[insertion_rank] = 1
        insertion_records[insertion_rank] = (representative, amplitude, orbit_size)
        if (representative & even_mask).bit_count() != 32 or ((representative >> 1) & even_mask).bit_count() != 32:
            raise VerificationError("checkpoint representative escaped N_up=32,N_down=32")
        info = d5b._canonical_info(representative, symmetries)
        if (
            info["representative"] != representative
            or info["projected_zero"] is not False
            or info["orbit_size"] != orbit_size
        ):
            raise VerificationError("D5B signed representative/orbit admissibility drift")
        canonicality_checks += 1
        table_images = [d6._fast(representative, group_table) for group_table in tables]
        if min(table_images) != representative or len(set(table_images)) != orbit_size:
            raise VerificationError("D6 support-table nomination/orbit drift")
        d6_nomination_checks += 1
        previous = representative
        min_rep = representative if min_rep is None else min_rep
        max_rep = representative
        max_abs = max(max_abs, abs(amplitude))
        positive += amplitude > 0
        negative += amplitude < 0
        amplitude_sum += amplitude
        orbit_histogram[str(orbit_size)] = orbit_histogram.get(str(orbit_size), 0) + 1
        coverage_sum += orbit_size
        index = offset // record_bytes
        if index:
            support_digest.update(b",")
            semantic_digest.update(b",")
        support_digest.update(
            json.dumps([hex(representative), str(orbit_size)], separators=(",", ":")).encode("ascii")
        )
        semantic_digest.update(
            json.dumps(
                [hex(representative), str(amplitude), orbit_size, insertion_rank],
                separators=(",", ":"),
            ).encode("ascii")
        )
    if not all(seen_ranks) or any(record is None for record in insertion_records):
        raise VerificationError("checkpoint insertion-rank coverage drift")
    support_digest.update(b"]")
    semantic_digest.update(b"]")
    legacy_digest.update(b"[")
    for rank, record in enumerate(insertion_records):
        assert record is not None
        if rank:
            legacy_digest.update(b",")
        representative, amplitude, orbit_size = record
        legacy_digest.update(
            json.dumps(
                [hex(representative), str(amplitude), orbit_size], separators=(",", ":")
            ).encode("ascii")
        )
    legacy_digest.update(b"]")
    if legacy_digest.hexdigest() != contract["workload"]["expected_D5B_insertion_order_quotient_sha256"]:
        raise VerificationError("legacy D5B insertion-order digest drift")
    if support_digest.hexdigest() != contract["workload"]["expected_D6_sorted_support_orbit_sha256"]:
        raise VerificationError("D6 sorted support-orbit digest drift")
    if orbit_histogram != contract["workload"]["expected_orbit_size_histogram"] or coverage_sum != 1704285:
        raise VerificationError("checkpoint orbit histogram/coverage drift")
    return {
        "path": f"{BUNDLE_NAME}/{CHECKPOINT_NAME}",
        "format_id": encoding["format_id"],
        "encoding": "u128be_rep+i64be_amplitude+u8_orbit+u8_zero_flags+u16_zero_reserved+u32be_d5b_rank",
        "record_bytes": record_bytes,
        "record_count": count,
        "file_bytes": len(raw),
        "packed_sorted_binary_sha256": hashlib.sha256(raw).hexdigest(),
        "sorted_semantic_sha256": semantic_digest.hexdigest(),
        "legacy_d5b_insertion_json_sha256": legacy_digest.hexdigest(),
        "d6_sorted_support_orbit_sha256": support_digest.hexdigest(),
        "strictly_ascending_representatives": True,
        "unique_representatives": True,
        "insertion_ranks_complete_permutation": True,
        "flags_nonzero": 0,
        "reserved_nonzero": 0,
        "particle_sector_checks": count,
        "d5b_signed_canonicality_checks": canonicality_checks,
        "d6_support_nomination_checks": d6_nomination_checks,
        "zero_amplitudes": 0,
        "positive_amplitudes": positive,
        "negative_amplitudes": negative,
        "amplitude_sum": str(amplitude_sum),
        "maximum_absolute_amplitude_observed": max_abs,
        "orbit_size_histogram": orbit_histogram,
        "stabilizer_size_histogram": {"1": 212973, "2": 125, "8": 1},
        "orbit_coverage_sum": coverage_sum,
        "first_representative_hex": hex(min_rep if min_rep is not None else 0),
        "last_representative_hex": hex(max_rep if max_rep is not None else 0),
    }


def _current_cgroup_limits() -> dict[str, Any]:
    lines = Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
    unified = [line.split("::", 1)[1] for line in lines if line.startswith("0::")]
    if len(unified) != 1:
        raise VerificationError("unified cgroup-v2 path unavailable")
    relative = unified[0].lstrip("/")
    directory = Path("/sys/fs/cgroup") / relative
    def bounded(name: str) -> int:
        value = (directory / name).read_text(encoding="ascii").strip()
        if not value.isdigit():
            raise VerificationError(f"cgroup {name} is not a finite canonical integer")
        return int(value)
    events: dict[str, int] = {}
    for line in (directory / "memory.events").read_text(encoding="ascii").splitlines():
        fields = line.split()
        if len(fields) != 2 or not fields[1].isdigit():
            raise VerificationError("malformed cgroup memory.events")
        events[fields[0]] = int(fields[1])
    required_events = {"low", "high", "max", "oom", "oom_kill", "oom_group_kill"}
    if not required_events <= set(events):
        raise VerificationError("incomplete cgroup memory.events")
    return {
        "path": "/" + relative,
        "memory_max_bytes": bounded("memory.max"),
        "memory_high_bytes": bounded("memory.high"),
        "memory_swap_max_bytes": bounded("memory.swap.max"),
        "memory_peak_bytes": bounded("memory.peak"),
        "memory_current_bytes": bounded("memory.current"),
        "memory_swap_current_bytes": bounded("memory.swap.current"),
        "memory_events": {name: events[name] for name in sorted(required_events)},
    }


def heavy_replay(
    contract: Mapping[str, Any], raw_checkpoint: bytes, checkpoint_record: Mapping[str, Any]
) -> dict[str, Any]:
    """Independently replay only q0->q3 and compare the complete packed payload."""
    import gc
    import resource
    import time

    verify_sources(contract)
    assert _SCIENCE_CACHE is not None
    limits = contract["resource_limits"]
    cgroup = _current_cgroup_limits()
    if (
        cgroup["path"] == "/"
        or cgroup["memory_max_bytes"] != limits["outer_memory_max_bytes"]
        or cgroup["memory_high_bytes"] != limits["outer_memory_high_bytes"]
        or cgroup["memory_swap_max_bytes"] != limits["outer_swap_max_bytes"]
        or cgroup["memory_swap_current_bytes"] != 0
        or cgroup["memory_peak_bytes"] > limits["max_initial_cgroup_peak_bytes"]
        or any(
            cgroup["memory_events"][name] != 0
            for name in ("max", "oom", "oom_kill", "oom_group_kill")
        )
    ):
        raise ResourceIndeterminate("heavy replay lacks exact 1-GiB/zero-swap envelope")
    started = time.monotonic()
    d5b = _SCIENCE_CACHE["d5b_module"]
    d5b_contract = _SCIENCE_CACHE["d5b_contract"]
    symmetries = _SCIENCE_CACHE["symmetries"]
    d6 = _SCIENCE_CACHE["d6_module"]
    tables = _SCIENCE_CACHE["d6_tables"]
    d5b._ACTIVE_DEADLINE = started + limits["internal_deadline_seconds"]
    d4, d4_contract, _ = d5b._verify_parent_sources(d5b_contract)
    d3 = d4._load_d3(d4_contract)
    d3_contract = _load_json_bytes(
        _read_regular_nofollow(
            HERE / "fh_l8_degree6_streaming_d3_contract.json", 1_048_576
        )
    )
    d2 = d3._load_d2(d3_contract)
    d2_contract = _load_json_bytes(
        _read_regular_nofollow(
            HERE / "fh_l8_two_step_scalar_defect_d2_contract.json", 1_048_576
        )
    )
    upstream = d2._load_upstream(d2_contract)
    backend = upstream._load_backend()
    bonds = {name: backend._hopping_bonds(8, name) for name in ("H1", "H2", "H3", "H4")}
    neel = upstream._neel_basis(8)
    vector: dict[int, int] = {neel: 1}
    action_calls = 0
    acted_depths: list[int] = []
    action_locked = False

    def act(source_depth: int, source: Mapping[int, int]) -> dict[int, int]:
        nonlocal action_calls
        if action_locked or source_depth not in (0, 1, 2) or action_calls >= 3:
            raise ScientificNoGo("fourth/depth-3 Hamiltonian action rejected before backend")
        if source_depth != action_calls:
            raise ScientificNoGo("Hamiltonian action depth sequence drift")
        action_calls += 1
        acted_depths.append(source_depth)
        return d4._sector_action(backend, bonds, source, limits["max_materialized_full_states"])

    depth_records = []
    for expected in contract["workload"]["expected_depth_records"]:
        depth = expected["depth"]
        observed = {
            "depth": depth,
            "full_state_count": len(vector),
            "full_vector_sha256": d5b._vector_digest_streaming(vector),
        }
        if observed != expected:
            raise ScientificNoGo(f"heavy depth-{depth} replay drift")
        depth_records.append(observed)
        if depth < 3:
            vector = act(depth, vector)
    action_locked = True
    calls_before_rejection = action_calls
    try:
        act(3, vector)
    except VerificationError:
        pass
    else:
        raise ScientificNoGo("heavy fourth-action guard did not reject")
    if action_calls != calls_before_rejection or action_calls != 3 or acted_depths != [0, 1, 2]:
        raise ScientificNoGo("heavy Hamiltonian call budget drift")

    q3_audit, quotient = d5b._audit_vector(vector, symmetries, materialize_quotient=True)
    if quotient is None:
        raise ScientificNoGo("heavy q3 quotient was not materialized")
    q3_audit = dict(q3_audit)
    expected_q3_audit = {
        "full_state_count": 1704285,
        "orbit_representative_count": 213099,
        "compression_ratio": "1704285/213099",
        "orbit_size_histogram": {"1": 1, "4": 125, "8": 212973},
        "stabilizer_size_histogram": {"1": 212973, "2": 125, "8": 1},
        "coverage_sum": 1704285,
        "amplitude_relation_checks": 13634280,
        "projected_zero_nonzero_states": 0,
        "deterministic_insertion_order_quotient_sha256": "7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e",
    }
    if q3_audit != expected_q3_audit:
        raise ScientificNoGo("heavy q3 signed-orbit audit drift")
    del vector
    gc.collect()
    records: list[tuple[int, int, int, int]] = []
    for rank, (representative, amplitude) in enumerate(quotient.items()):
        images = {d6._fast(representative, table) for table in tables}
        if min(images) != representative or len(images) not in (1, 4, 8):
            raise ScientificNoGo("heavy D6 support nomination drift")
        records.append((representative, amplitude, len(images), rank))
    del quotient
    gc.collect()
    records.sort(key=lambda item: item[0])
    expected_raw = bytearray()
    semantic_digest = hashlib.sha256()
    semantic_digest.update(b"[")
    support_digest = hashlib.sha256()
    support_digest.update(b"[")
    for index, (representative, amplitude, orbit_size, rank) in enumerate(records):
        if index:
            semantic_digest.update(b",")
            support_digest.update(b",")
        expected_raw.extend(representative.to_bytes(16, "big"))
        expected_raw.extend(amplitude.to_bytes(8, "big", signed=True))
        expected_raw.extend(bytes((orbit_size, 0, 0, 0)))
        expected_raw.extend(rank.to_bytes(4, "big"))
        semantic_digest.update(
            json.dumps([hex(representative), str(amplitude), orbit_size, rank], separators=(",", ":")).encode("ascii")
        )
        support_digest.update(
            json.dumps([hex(representative), str(orbit_size)], separators=(",", ":")).encode("ascii")
        )
    semantic_digest.update(b"]")
    support_digest.update(b"]")
    if bytes(expected_raw) != raw_checkpoint:
        raise ScientificNoGo("heavy replay binary differs from frozen checkpoint")
    if semantic_digest.hexdigest() != checkpoint_record["sorted_semantic_sha256"]:
        raise ScientificNoGo("heavy semantic digest differs from checkpoint")
    if support_digest.hexdigest() != checkpoint_record["d6_sorted_support_orbit_sha256"]:
        raise ScientificNoGo("heavy support digest differs from checkpoint")
    elapsed_ns = int((time.monotonic() - started) * 1_000_000_000)
    if elapsed_ns > limits["internal_deadline_seconds"] * 1_000_000_000:
        raise ResourceIndeterminate("heavy replay exceeded internal deadline")
    cgroup_after = _current_cgroup_limits()
    rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if (
        cgroup_after["path"] != cgroup["path"]
        or cgroup_after["memory_max_bytes"] != limits["outer_memory_max_bytes"]
        or cgroup_after["memory_high_bytes"] != limits["outer_memory_high_bytes"]
        or cgroup_after["memory_swap_max_bytes"] != limits["outer_swap_max_bytes"]
        or cgroup_after["memory_peak_bytes"] > limits["max_cgroup_peak_bytes"]
        or cgroup_after["memory_swap_current_bytes"] != 0
        or rss_kib * 1024 > limits["max_process_peak_rss_bytes"]
        or any(
            cgroup_after["memory_events"][name] != cgroup["memory_events"][name]
            for name in ("max", "oom", "oom_kill", "oom_group_kill")
        )
    ):
        raise ResourceIndeterminate("heavy replay resource envelope failed")
    return {
        "mode": "heavy",
        "depth_records": depth_records,
        "q3_audit": q3_audit,
        "hamiltonian_action_calls": action_calls,
        "acted_source_depths": acted_depths,
        "fourth_call_rejected_before_backend": True,
        "checkpoint_bytes_equal": True,
        "checkpoint_sha256": hashlib.sha256(raw_checkpoint).hexdigest(),
        "elapsed_monotonic_ns": elapsed_ns,
        "cgroup_before": cgroup,
        "cgroup_after": cgroup_after,
        "process_max_rss_kib": rss_kib,
        "q3_to_q4_executed": False,
    }


def _validate_result(
    contract: Mapping[str, Any],
    result: Mapping[str, Any],
    checkpoint_record: Mapping[str, Any],
    protocol: Mapping[str, Any],
    raw_result_bytes: int,
) -> dict[str, Any]:
    if set(result) != {
        "schema_version",
        "contract_id",
        "status",
        "verified",
        "protocol",
        "source_evidence",
        "byte_table_full_domain_validation",
        "depth_replay",
        "checkpoint",
        "resource_observations",
        "authority",
        "limitations",
        "next_gate",
    }:
        raise VerificationError("result schema drift")
    if (
        type(result["schema_version"]) is not int
        or result["schema_version"] != 1
        or result["contract_id"] != CONTRACT_ID
        or result["status"] != STATUS
        or result["verified"] is not True
        or result["protocol"] != protocol
    ):
        raise VerificationError("result identity/protocol drift")
    if result["source_evidence"] != verify_sources(contract):
        raise VerificationError("result source evidence drift")
    table = result["byte_table_full_domain_validation"]
    if table != verify_byte_tables(contract):
        raise VerificationError("byte-table full-domain result drift")
    q3_audit = {
        "full_state_count": 1704285,
        "orbit_representative_count": 213099,
        "compression_ratio": "1704285/213099",
        "orbit_size_histogram": {"1": 1, "4": 125, "8": 212973},
        "stabilizer_size_histogram": {"1": 212973, "2": 125, "8": 1},
        "coverage_sum": 1704285,
        "amplitude_relation_checks": 13634280,
        "projected_zero_nonzero_states": 0,
        "deterministic_insertion_order_quotient_sha256": "7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e",
    }
    depth_replay = result["depth_replay"]
    if depth_replay != {
        "depth_records": contract["workload"]["expected_depth_records"],
        "q3_audit": q3_audit,
        "hamiltonian_action_call_budget": 3,
        "hamiltonian_actions_executed": 3,
        "acted_source_depths": [0, 1, 2],
        "maximum_acted_source_depth": 2,
        "depth3_source_rows_visited": 0,
        "q4_records_emitted": 0,
        "fourth_call_rejected_before_backend": True,
        "underlying_action_calls_after_rejection": 3,
        "forbidden_quotient_helpers_invoked": 0,
    }:
        raise VerificationError("depth replay/call-budget record drift")
    if result["checkpoint"] != checkpoint_record:
        raise VerificationError("checkpoint/result record drift")

    resources = result["resource_observations"]
    if set(resources) != {
        "cgroup_v2_enforced",
        "cgroup_path",
        "observation_scope",
        "memory_max_bytes",
        "memory_high_bytes",
        "memory_swap_max_bytes",
        "memory_peak_at_snapshot_bytes",
        "initial_memory_peak_bytes",
        "sampled_max_memory_current_at_snapshot_bytes",
        "memory_current_at_snapshot_bytes",
        "swap_current_at_snapshot_bytes",
        "memory_events_before",
        "memory_events_at_snapshot",
        "memory_events_delta_to_snapshot",
        "process_max_rss_kib_at_snapshot",
        "process_max_rss_bytes_at_snapshot",
        "elapsed_to_snapshot_ns",
        "user_cpu_to_snapshot_ns",
        "system_cpu_to_snapshot_ns",
        "phase_elapsed_ns",
        "internal_deadline_seconds",
        "required_outer_deadline_seconds",
        "worker_count",
        "io_chunk_bytes",
        "application_payload_bytes_written",
        "created_regular_files",
        "created_directories",
        "output_filesystem_type",
        "output_st_dev",
        "output_free_bytes_before",
        "open_file_descriptor_limit",
        "file_size_limit_bytes",
        "checkpoint_file_fsync_completed",
        "staging_directory_fsync_completed",
        "staged_checkpoint_rehash_completed",
        "within_frozen_caps",
    }:
        raise VerificationError("resource execution schema drift")
    limits = contract["resource_limits"]
    event_names = {"low", "high", "max", "oom", "oom_kill", "oom_group_kill"}
    before = resources["memory_events_before"]
    after = resources["memory_events_at_snapshot"]
    delta = resources["memory_events_delta_to_snapshot"]
    if any(
        set(record) != event_names
        or any(type(value) is not int or value < 0 for value in record.values())
        for record in (before, after, delta)
    ):
        raise VerificationError("memory.events schema drift")
    if any(after[name] - before[name] != delta[name] for name in event_names):
        raise VerificationError("memory.events delta drift")
    phases = resources["phase_elapsed_ns"]
    if (
        not isinstance(phases, dict)
        or set(phases)
        != {
            "source_and_table_validation",
            "depth0_to_depth3_replay",
            "q3_orbit_audit",
            "packing_and_staging",
        }
        or any(type(value) is not int or value < 0 for value in phases.values())
    ):
        raise VerificationError("phase timing schema drift")
    numeric = (
        all(
            type(resources[key]) is int
            for key in {
                "memory_max_bytes",
                "memory_high_bytes",
                "memory_swap_max_bytes",
                "memory_peak_at_snapshot_bytes",
                "initial_memory_peak_bytes",
                "sampled_max_memory_current_at_snapshot_bytes",
                "memory_current_at_snapshot_bytes",
                "swap_current_at_snapshot_bytes",
                "process_max_rss_kib_at_snapshot",
                "process_max_rss_bytes_at_snapshot",
                "elapsed_to_snapshot_ns",
                "user_cpu_to_snapshot_ns",
                "system_cpu_to_snapshot_ns",
                "internal_deadline_seconds",
                "required_outer_deadline_seconds",
                "worker_count",
                "io_chunk_bytes",
                "application_payload_bytes_written",
                "created_regular_files",
                "created_directories",
                "output_st_dev",
                "output_free_bytes_before",
                "open_file_descriptor_limit",
                "file_size_limit_bytes",
            }
        )
        and 0 <= resources["initial_memory_peak_bytes"] <= resources["memory_peak_at_snapshot_bytes"]
        and resources["initial_memory_peak_bytes"] <= limits["max_initial_cgroup_peak_bytes"]
        and 0 <= resources["sampled_max_memory_current_at_snapshot_bytes"] <= resources["memory_peak_at_snapshot_bytes"]
        and 0 <= resources["memory_current_at_snapshot_bytes"] <= resources["memory_peak_at_snapshot_bytes"]
        and resources["memory_max_bytes"] == limits["outer_memory_max_bytes"]
        and resources["memory_high_bytes"] == limits["outer_memory_high_bytes"]
        and resources["memory_swap_max_bytes"] == limits["outer_swap_max_bytes"]
        and 0 <= resources["memory_peak_at_snapshot_bytes"] <= limits["max_cgroup_peak_bytes"]
        and 0 <= resources["memory_current_at_snapshot_bytes"] <= limits["outer_memory_max_bytes"]
        and resources["swap_current_at_snapshot_bytes"] == 0
        and delta["oom"] == 0
        and delta["oom_kill"] == 0
        and delta["oom_group_kill"] == 0
        and delta["max"] == 0
        and all(before[name] == 0 for name in ("max", "oom", "oom_kill", "oom_group_kill"))
        and 0
        < resources["process_max_rss_kib_at_snapshot"] * 1024
        == resources["process_max_rss_bytes_at_snapshot"]
        <= limits["max_process_peak_rss_bytes"]
        and 0
        < resources["elapsed_to_snapshot_ns"]
        <= limits["internal_deadline_seconds"] * 1_000_000_000
        and 0 <= resources["user_cpu_to_snapshot_ns"]
        and 0 <= resources["system_cpu_to_snapshot_ns"]
        and sum(phases.values()) <= resources["elapsed_to_snapshot_ns"]
        and resources["internal_deadline_seconds"] == limits["internal_deadline_seconds"]
        and resources["required_outer_deadline_seconds"] == limits["outer_deadline_seconds"]
        and resources["worker_count"] == 1
        and resources["io_chunk_bytes"] == limits["max_io_chunk_bytes"]
        and resources["application_payload_bytes_written"]
        == checkpoint_record["file_bytes"] + raw_result_bytes
        and resources["application_payload_bytes_written"] <= limits["max_application_payload_writes_bytes"]
        and resources["created_regular_files"] == 2
        and resources["created_directories"] == 1
        and resources["output_st_dev"] > 0
        and resources["output_free_bytes_before"] >= limits["minimum_output_free_bytes"]
        and resources["open_file_descriptor_limit"] == limits["max_open_file_descriptors"]
        and resources["file_size_limit_bytes"] == 8388608
    )
    if (
        resources["cgroup_v2_enforced"] is not True
        or not isinstance(resources["cgroup_path"], str)
        or not resources["cgroup_path"].startswith("/")
        or resources["cgroup_path"] == "/"
        or resources["observation_scope"]
        != "after_checkpoint_staged_and_rehashed_before_result_serialization_and_bundle_publication"
        or not isinstance(resources["output_filesystem_type"], str)
        or resources["output_filesystem_type"] in {"tmpfs", "ramfs"}
        or resources["output_filesystem_type"] == ""
        or resources["checkpoint_file_fsync_completed"] is not True
        or resources["staging_directory_fsync_completed"] is not True
        or resources["staged_checkpoint_rehash_completed"] is not True
        or not numeric
        or resources["within_frozen_caps"] is not True
    ):
        raise VerificationError("resource execution cap failure")
    expected_next = "CHECKPOINTED_FULL_QUOTIENT_H_RUNNER_IMPLEMENTATION_AND_AUTHORIZATION"
    if (
        result["authority"] != EXPECTED_AUTHORITY
        or result["limitations"] != EXPECTED_LIMITATIONS
        or result["next_gate"] != expected_next
    ):
        raise VerificationError("result authority uplift")
    return {
        "contract_id": CONTRACT_ID,
        "status": STATUS,
        "verified": True,
        "mode": "static",
        "checkpoint_sha256": checkpoint_record["packed_sorted_binary_sha256"],
        "checkpoint_records": checkpoint_record["record_count"],
        "checkpoint_bytes": checkpoint_record["file_bytes"],
        "legacy_d5b_insertion_json_sha256": checkpoint_record[
            "legacy_d5b_insertion_json_sha256"
        ],
        "d6_sorted_support_orbit_sha256": checkpoint_record[
            "d6_sorted_support_orbit_sha256"
        ],
        "table_sha256": table["table_sha256"],
        "authority": dict(EXPECTED_AUTHORITY),
    }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _validate_runner_terminal(
    terminal_evidence: Mapping[str, Any],
    contract: Mapping[str, Any],
    contract_commit: str,
    protocol: Mapping[str, Any],
    result: Mapping[str, Any],
    checkpoint_record: Mapping[str, Any],
    raw_result: bytes,
) -> dict[str, Any]:
    expected_keys = {
        "schema_version",
        "contract_id",
        "contract_freeze_commit",
        "protocol_source_freeze_commit",
        "status",
        "verified",
        "bundle_path",
        "single_bundle_renameat2_noreplace_completed",
        "parent_directory_fsync_completed",
        "checkpoint_post_publish_rehash_completed",
        "result_post_publish_rehash_completed",
        "terminal_resource_receipt",
        "checkpoint_sha256",
        "checkpoint_bytes",
        "result_sha256",
        "result_bytes",
        "elapsed_at_publication_receipt_ns",
        "depth3_to_depth4_execution_authorized",
        "depth3_to_depth4_action_executed",
        "next_gate",
    }
    if not isinstance(terminal_evidence, Mapping) or set(terminal_evidence) != expected_keys:
        raise VerificationError("runner terminal evidence schema drift")
    if any(
        type(terminal_evidence[name]) is not int
        for name in (
            "schema_version",
            "checkpoint_bytes",
            "result_bytes",
            "elapsed_at_publication_receipt_ns",
        )
    ):
        raise VerificationError("runner terminal integer type drift")
    expected_result_sha = hashlib.sha256(raw_result).hexdigest()
    if (
        terminal_evidence["schema_version"] != 1
        or terminal_evidence["contract_id"] != CONTRACT_ID
        or terminal_evidence["contract_freeze_commit"] != contract_commit
        or terminal_evidence["protocol_source_freeze_commit"]
        != protocol["protocol_source_freeze_commit"]
        or terminal_evidence["status"] != STATUS
        or terminal_evidence["verified"] is not True
        or terminal_evidence["bundle_path"] != BUNDLE_NAME
        or terminal_evidence["checkpoint_sha256"]
        != checkpoint_record["packed_sorted_binary_sha256"]
        or terminal_evidence["checkpoint_bytes"] != checkpoint_record["file_bytes"]
        or terminal_evidence["result_sha256"] != expected_result_sha
        or terminal_evidence["result_bytes"] != len(raw_result)
        or terminal_evidence["depth3_to_depth4_execution_authorized"] is not False
        or terminal_evidence["depth3_to_depth4_action_executed"] is not False
        or terminal_evidence["next_gate"] != result["next_gate"]
        or any(
            terminal_evidence[name] is not True
            for name in (
                "single_bundle_renameat2_noreplace_completed",
                "parent_directory_fsync_completed",
                "checkpoint_post_publish_rehash_completed",
                "result_post_publish_rehash_completed",
            )
        )
    ):
        raise VerificationError("runner terminal evidence binding drift")

    receipt = terminal_evidence["terminal_resource_receipt"]
    receipt_keys = {
        "observation_scope",
        "memory_max_bytes",
        "memory_high_bytes",
        "memory_swap_max_bytes",
        "memory_peak_bytes",
        "memory_current_bytes",
        "swap_current_bytes",
        "memory_events_at_receipt",
        "memory_events_delta_from_start",
        "process_max_rss_kib",
        "process_max_rss_bytes",
        "elapsed_monotonic_ns",
        "user_cpu_ns",
        "system_cpu_ns",
        "required_outer_deadline_seconds",
        "single_bundle_renameat2_noreplace_completed",
        "parent_directory_fsync_completed",
        "checkpoint_post_publish_rehash_completed",
        "result_post_publish_rehash_completed",
        "within_frozen_caps",
    }
    if not isinstance(receipt, Mapping) or set(receipt) != receipt_keys:
        raise VerificationError("terminal resource receipt schema drift")
    event_names = {"low", "high", "max", "oom", "oom_kill", "oom_group_kill"}
    events = receipt["memory_events_at_receipt"]
    event_delta = receipt["memory_events_delta_from_start"]
    if any(
        not isinstance(record, Mapping)
        or set(record) != event_names
        or any(type(value) is not int or value < 0 for value in record.values())
        for record in (events, event_delta)
    ):
        raise VerificationError("terminal memory.events schema drift")
    if any(events[name] < event_delta[name] for name in event_names):
        raise VerificationError("terminal memory.events delta exceeds total")
    limits = contract["resource_limits"]
    snapshot = result["resource_observations"]
    integer_fields = {
        "memory_max_bytes",
        "memory_high_bytes",
        "memory_swap_max_bytes",
        "memory_peak_bytes",
        "memory_current_bytes",
        "swap_current_bytes",
        "process_max_rss_kib",
        "process_max_rss_bytes",
        "elapsed_monotonic_ns",
        "user_cpu_ns",
        "system_cpu_ns",
        "required_outer_deadline_seconds",
    }
    caps_ok = (
        all(type(receipt[name]) is int for name in integer_fields)
        and receipt["observation_scope"]
        == "after_single_bundle_publish_parent_fsync_and_post_publish_rehash"
        and receipt["memory_max_bytes"] == limits["outer_memory_max_bytes"]
        and receipt["memory_high_bytes"] == limits["outer_memory_high_bytes"]
        and receipt["memory_swap_max_bytes"] == limits["outer_swap_max_bytes"]
        and snapshot["memory_peak_at_snapshot_bytes"]
        <= receipt["memory_peak_bytes"]
        <= limits["max_cgroup_peak_bytes"]
        and 0 <= receipt["memory_current_bytes"] <= limits["outer_memory_max_bytes"]
        and receipt["swap_current_bytes"] == 0
        and 0
        < receipt["process_max_rss_kib"] * 1024
        == receipt["process_max_rss_bytes"]
        <= limits["max_process_peak_rss_bytes"]
        and snapshot["process_max_rss_bytes_at_snapshot"]
        <= receipt["process_max_rss_bytes"]
        and snapshot["elapsed_to_snapshot_ns"]
        <= receipt["elapsed_monotonic_ns"]
        <= limits["internal_deadline_seconds"] * 1_000_000_000
        and terminal_evidence["elapsed_at_publication_receipt_ns"]
        == receipt["elapsed_monotonic_ns"]
        and snapshot["user_cpu_to_snapshot_ns"] <= receipt["user_cpu_ns"]
        and snapshot["system_cpu_to_snapshot_ns"] <= receipt["system_cpu_ns"]
        and receipt["required_outer_deadline_seconds"]
        == limits["outer_deadline_seconds"]
        and all(
            event_delta[name]
            >= snapshot["memory_events_delta_to_snapshot"][name]
            for name in event_names
        )
        and all(
            events[name] - snapshot["memory_events_before"][name]
            == event_delta[name]
            for name in event_names
        )
        and all(
            events[name] == 0 and event_delta[name] == 0
            for name in ("max", "oom", "oom_kill", "oom_group_kill")
        )
        and all(
            receipt[name] is True
            for name in (
                "single_bundle_renameat2_noreplace_completed",
                "parent_directory_fsync_completed",
                "checkpoint_post_publish_rehash_completed",
                "result_post_publish_rehash_completed",
                "within_frozen_caps",
            )
        )
    )
    if not caps_ok:
        raise ResourceIndeterminate("terminal resource receipt exceeded frozen caps")
    return {
        "verified": True,
        "checkpoint_sha256": terminal_evidence["checkpoint_sha256"],
        "result_sha256": terminal_evidence["result_sha256"],
        "elapsed_monotonic_ns": receipt["elapsed_monotonic_ns"],
        "memory_peak_bytes": receipt["memory_peak_bytes"],
        "process_max_rss_bytes": receipt["process_max_rss_bytes"],
        "required_outer_deadline_seconds": receipt[
            "required_outer_deadline_seconds"
        ],
    }


def _validate_execution_receipt(
    raw_receipt: bytes,
    contract: Mapping[str, Any],
    contract_commit: str,
    protocol: Mapping[str, Any],
    result: Mapping[str, Any],
    checkpoint_record: Mapping[str, Any],
    raw_result: bytes,
) -> dict[str, Any]:
    if len(raw_receipt) > contract["resource_limits"]["max_terminal_receipt_bytes"]:
        raise ResourceIndeterminate("terminal execution receipt exceeds byte cap")
    receipt = _load_json_bytes(raw_receipt)
    if raw_receipt != _canonical_json(receipt) + b"\n":
        raise VerificationError("terminal execution receipt is not canonical JSON")
    if set(receipt) != {
        "schema_version",
        "contract_id",
        "contract_freeze_commit",
        "protocol_source_freeze_commit",
        "launcher_id",
        "runner_exit_code",
        "runner_stdout_bytes",
        "runner_stdout_sha256",
        "runner_stderr_bytes",
        "runner_stderr_sha256",
        "runner_terminal_evidence",
    }:
        raise VerificationError("terminal execution receipt schema drift")
    if any(
        type(receipt[name]) is not int
        for name in (
            "schema_version",
            "runner_exit_code",
            "runner_stdout_bytes",
            "runner_stderr_bytes",
        )
    ):
        raise VerificationError("terminal execution receipt integer type drift")
    terminal = receipt["runner_terminal_evidence"]
    if not isinstance(terminal, Mapping):
        raise VerificationError("runner terminal evidence is not an object")
    reconstructed_stdout = (
        json.dumps(terminal, allow_nan=False, indent=2, sort_keys=True).encode("ascii")
        + b"\n"
    )
    if (
        receipt["schema_version"] != 1
        or receipt["contract_id"] != CONTRACT_ID
        or receipt["contract_freeze_commit"] != contract_commit
        or receipt["protocol_source_freeze_commit"]
        != protocol["protocol_source_freeze_commit"]
        or receipt["launcher_id"]
        != "FH-L8-D11-CHECKER-SYSTEMD-SCOPE-CAPTURE-V1"
        or receipt["runner_exit_code"] != 0
        or receipt["runner_stdout_bytes"] != len(reconstructed_stdout)
        or receipt["runner_stdout_sha256"]
        != hashlib.sha256(reconstructed_stdout).hexdigest()
        or receipt["runner_stderr_bytes"] != 0
        or receipt["runner_stderr_sha256"] != hashlib.sha256(b"").hexdigest()
    ):
        raise VerificationError("terminal execution receipt binding drift")
    return _validate_runner_terminal(
        terminal,
        contract,
        contract_commit,
        protocol,
        result,
        checkpoint_record,
        raw_result,
    )


def _write_execution_receipt(payload: bytes) -> None:
    if len(payload) > 32768:
        raise ResourceIndeterminate("terminal execution receipt exceeds byte cap")
    directory_fd = os.open(HERE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    fd: int | None = None
    identity: tuple[int, int] | None = None
    published = False
    try:
        for name in (TERMINAL_RECEIPT_NAME, TERMINAL_RECEIPT_STAGING_NAME):
            try:
                os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise ResourceIndeterminate(
                f"stale or concurrent terminal receipt artifact exists: {name}"
            )
        fd = os.open(
            TERMINAL_RECEIPT_STAGING_NAME,
            flags,
            0o600,
            dir_fd=directory_fd,
        )
        stat_result = os.fstat(fd)
        if not stat.S_ISREG(stat_result.st_mode):
            raise OSError(errno.EIO, "terminal receipt staging is not regular")
        identity = (stat_result.st_dev, stat_result.st_ino)
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise OSError(errno.EIO, "short terminal receipt write")
            offset += written
        os.fsync(fd)
        if os.fstat(fd).st_size != len(payload):
            raise OSError(errno.EIO, "terminal receipt size drift")
        os.close(fd)
        fd = None
        os.link(
            TERMINAL_RECEIPT_STAGING_NAME,
            TERMINAL_RECEIPT_NAME,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        published = True
        current = os.stat(
            TERMINAL_RECEIPT_NAME, dir_fd=directory_fd, follow_symlinks=False
        )
        if identity is None or (current.st_dev, current.st_ino) != identity:
            raise OSError(errno.EIO, "terminal receipt publication identity drift")
        os.fsync(directory_fd)
        os.unlink(TERMINAL_RECEIPT_STAGING_NAME, dir_fd=directory_fd)
        os.fsync(directory_fd)
    except BaseException as exc:
        if fd is not None:
            os.close(fd)
            fd = None
        for name, may_remove in (
            (TERMINAL_RECEIPT_NAME, published),
            (TERMINAL_RECEIPT_STAGING_NAME, identity is not None),
        ):
            if not may_remove:
                continue
            try:
                current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if identity is not None and (current.st_dev, current.st_ino) == identity:
                    os.unlink(name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        try:
            os.fsync(directory_fd)
        except OSError:
            pass
        if isinstance(exc, ResourceIndeterminate):
            raise
        raise ResourceIndeterminate(
            f"terminal execution receipt persistence failed: {type(exc).__name__}"
        ) from exc
    finally:
        os.close(directory_fd)


def _terminate_scope_process(process: subprocess.Popen[bytes], unit: str) -> None:
    scope = f"{unit}.scope"
    try:
        subprocess.run(
            [
                "/usr/bin/systemctl",
                "--user",
                "kill",
                "--kill-whom=all",
                "--signal=SIGKILL",
                scope,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
    if process.poll() is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:
            raise ResourceIndeterminate(
                "launcher process survived repeated SIGKILL cleanup"
            ) from exc
    def scope_state() -> tuple[str, str]:
        completed = subprocess.run(
            [
                "/usr/bin/systemctl",
                "--user",
                "show",
                "--property=ActiveState",
                "--property=ControlGroup",
                scope,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
        if completed.returncode != 0 or len(completed.stdout) > 4096:
            raise ResourceIndeterminate("failed scope state query was inconclusive")
        fields: dict[str, str] = {}
        for line in completed.stdout.decode("ascii").splitlines():
            key, separator, value = line.partition("=")
            if separator != "=" or key in fields:
                raise ResourceIndeterminate("failed scope state query was malformed")
            fields[key] = value
        if set(fields) != {"ActiveState", "ControlGroup"}:
            raise ResourceIndeterminate("failed scope state query was incomplete")
        return fields["ActiveState"], fields["ControlGroup"]

    try:
        active_state, control_group = scope_state()
        if active_state not in {"inactive", "failed"}:
            subprocess.run(
                ["/usr/bin/systemctl", "--user", "stop", scope],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
            active_state, control_group = scope_state()
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ResourceIndeterminate(
            "could not confirm failed scope termination"
        ) from exc
    if active_state not in {"inactive", "failed"}:
        raise ResourceIndeterminate("failed scope remained active after SIGKILL")
    if control_group:
        cgroup_procs = Path("/sys/fs/cgroup") / control_group.lstrip("/") / "cgroup.procs"
        try:
            if cgroup_procs.exists() and cgroup_procs.read_text(encoding="ascii").strip():
                raise ResourceIndeterminate(
                    "failed scope cgroup still contains processes"
                )
        except OSError as exc:
            raise ResourceIndeterminate(
                "failed scope cgroup process check was inconclusive"
            ) from exc


def _run_bounded_scope(
    command: list[str],
    unit: str,
    stdout_cap: int,
    stderr_cap: int,
) -> tuple[int, bytes, bytes]:
    selector = selectors.DefaultSelector()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    caps = {"stdout": stdout_cap, "stderr": stderr_cap}
    try:
        process = subprocess.Popen(
            command,
            cwd=_root(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
    except OSError as exc:
        selector.close()
        raise ResourceIndeterminate("official scope launcher could not start") from exc
    deadline = time.monotonic() + 345
    try:
        if process.stdout is None or process.stderr is None:
            raise ResourceIndeterminate("launcher pipes were not created")
        for name, stream in (
            ("stdout", process.stdout),
            ("stderr", process.stderr),
        ):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ResourceIndeterminate(
                    "official launcher exceeded 345-second failsafe"
                )
            for key, _mask in selector.select(timeout=min(1.0, remaining)):
                try:
                    chunk = os.read(key.fileobj.fileno(), 4096)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                name = key.data
                if len(buffers[name]) + len(chunk) > caps[name]:
                    raise ResourceIndeterminate(
                        f"runner {name} exceeds frozen capture cap"
                    )
                buffers[name].extend(chunk)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ResourceIndeterminate(
                "official launcher exceeded 345-second failsafe"
            )
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise ResourceIndeterminate(
                "official launcher exceeded 345-second failsafe"
            ) from exc
    except BaseException:
        _terminate_scope_process(process, unit)
        raise
    finally:
        selector.close()
        for stream in (process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
    return returncode, bytes(buffers["stdout"]), bytes(buffers["stderr"])


def execute_official(contract: Mapping[str, Any], contract_commit: str) -> dict[str, Any]:
    protocol = verify_protocol(contract, contract_commit)
    verify_sources(contract)
    verify_byte_tables(contract)
    preflight_fd = os.open(HERE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name in (TERMINAL_RECEIPT_NAME, TERMINAL_RECEIPT_STAGING_NAME):
            try:
                os.stat(name, dir_fd=preflight_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise ResourceIndeterminate(
                f"stale or concurrent terminal receipt artifact exists: {name}"
            )
    finally:
        os.close(preflight_fd)
    unit = f"fh-l8-d11-{os.getpid()}-{time.monotonic_ns()}"
    command = [
        "/usr/bin/systemd-run",
        "--user",
        "--scope",
        "--collect",
        "--quiet",
        f"--unit={unit}",
        "-p",
        "MemoryMax=1073741824",
        "-p",
        "MemoryHigh=805306368",
        "-p",
        "MemorySwapMax=0",
        "--",
        "/usr/bin/timeout",
        "--signal=TERM",
        "--kill-after=5s",
        "330s",
        "/usr/bin/python3",
        str(HERE / RUNNER_NAME),
        "--contract-commit",
        contract_commit,
    ]
    returncode, runner_stdout, runner_stderr = _run_bounded_scope(
        command,
        unit,
        contract["resource_limits"]["max_runner_stdout_capture_bytes"],
        contract["resource_limits"]["max_runner_stderr_capture_bytes"],
    )
    if returncode != 0:
        if returncode in (124, 137, -9, -15):
            raise ResourceIndeterminate(
                f"runner terminated under resource/deadline envelope: {returncode}"
            )
        try:
            failure = _load_json_bytes(runner_stdout)
        except Exception as exc:
            raise ResourceIndeterminate(
                "nonzero runner exit lacked a valid terminal failure record"
            ) from exc
        if failure.get("status") == "NO_GO_D11_PACKED_Q3_CHECKPOINT_SEMANTICS":
            raise ScientificNoGo(str(failure.get("error", "runner scientific no-go")))
        if failure.get("status") == "INDETERMINATE_D11_PACKED_Q3_CHECKPOINT_RESOURCE_ENVELOPE":
            raise ResourceIndeterminate(str(failure.get("error", "runner indeterminate")))
        if failure.get("status") == "VERIFICATION_FAILED":
            raise VerificationError(str(failure.get("error", "runner verification failed")))
        raise ResourceIndeterminate(
            f"nonzero runner exit had an unrecognized status: {returncode}"
        )
    if runner_stderr != b"":
        raise ResourceIndeterminate(
            "successful official runner emitted uncaptured-environment stderr"
        )
    if runner_stdout == b"":
        raise ResourceIndeterminate("successful runner produced no terminal receipt")
    try:
        terminal = _load_json_bytes(runner_stdout)
    except Exception as exc:
        raise ResourceIndeterminate(
            "successful runner lacked a valid terminal receipt"
        ) from exc
    raw_checkpoint = _read_bundle_member_nofollow(
        CHECKPOINT_NAME,
        contract["checkpoint_encoding"]["total_bytes"],
        contract["checkpoint_encoding"]["total_bytes"],
    )
    raw_result = _read_bundle_member_nofollow(
        RESULT_NAME, contract["resource_limits"]["max_result_bytes"]
    )
    if len(raw_result) > contract["resource_limits"]["max_result_bytes"]:
        raise VerificationError("result exceeds byte cap")
    checkpoint_record = parse_checkpoint(raw_checkpoint, contract)
    result = _load_json_bytes(raw_result)
    _validate_result(
        contract, result, checkpoint_record, protocol, len(raw_result)
    )
    terminal_summary = _validate_runner_terminal(
        terminal,
        contract,
        contract_commit,
        protocol,
        result,
        checkpoint_record,
        raw_result,
    )
    receipt = {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "contract_freeze_commit": contract_commit,
        "protocol_source_freeze_commit": protocol["protocol_source_freeze_commit"],
        "launcher_id": "FH-L8-D11-CHECKER-SYSTEMD-SCOPE-CAPTURE-V1",
        "runner_exit_code": returncode,
        "runner_stdout_bytes": len(runner_stdout),
        "runner_stdout_sha256": hashlib.sha256(runner_stdout).hexdigest(),
        "runner_stderr_bytes": len(runner_stderr),
        "runner_stderr_sha256": hashlib.sha256(runner_stderr).hexdigest(),
        "runner_terminal_evidence": terminal,
    }
    raw_receipt = _canonical_json(receipt) + b"\n"
    _write_execution_receipt(raw_receipt)
    _validate_execution_receipt(
        _read_regular_nofollow(
            TERMINAL_RECEIPT,
            contract["resource_limits"]["max_terminal_receipt_bytes"],
        ),
        contract,
        contract_commit,
        protocol,
        result,
        checkpoint_record,
        raw_result,
    )
    return {
        "contract_id": CONTRACT_ID,
        "status": STATUS,
        "verified": True,
        "mode": "execute",
        "runner_exit_code": returncode,
        "terminal_execution_receipt_path": TERMINAL_RECEIPT_PATH,
        "terminal_execution_receipt_sha256": hashlib.sha256(raw_receipt).hexdigest(),
        "terminal": terminal_summary,
        "next_gate": result["next_gate"],
    }


def verify_outcome(
    contract: Mapping[str, Any], contract_commit: str, outcome_commit: str
) -> dict[str, Any]:
    protocol = verify_protocol(contract, contract_commit)
    verify_sources(contract)
    outcome = _commit_record(outcome_commit)
    if outcome["parents"] != [contract_commit]:
        raise VerificationError("outcome must directly descend from contract freeze")
    outcome_diff = _diff_entries(outcome_commit)
    if ("A", TERMINAL_RECEIPT_PATH) not in outcome_diff:
        raise ResourceIndeterminate("outcome lacks the terminal execution receipt")
    if outcome_diff != {
        ("A", CHECKPOINT_PATH),
        ("A", RESULT_PATH),
        ("A", TERMINAL_RECEIPT_PATH),
    }:
        raise VerificationError(
            "outcome commit must add only checkpoint, result, and terminal receipt"
        )
    _require_mode(outcome_commit, CHECKPOINT_PATH)
    _require_mode(outcome_commit, RESULT_PATH)
    _require_mode(outcome_commit, TERMINAL_RECEIPT_PATH)
    checkpoint_git_bytes = int(
        _git("cat-file", "-s", f"{outcome_commit}:{CHECKPOINT_PATH}")
    )
    result_git_bytes = int(_git("cat-file", "-s", f"{outcome_commit}:{RESULT_PATH}"))
    receipt_git_bytes = int(
        _git("cat-file", "-s", f"{outcome_commit}:{TERMINAL_RECEIPT_PATH}")
    )
    if (
        checkpoint_git_bytes != contract["checkpoint_encoding"]["total_bytes"]
        or result_git_bytes > contract["resource_limits"]["max_result_bytes"]
        or receipt_git_bytes
        > contract["resource_limits"]["max_terminal_receipt_bytes"]
    ):
        raise VerificationError("outcome Git artifact byte cap drift")
    local_artifacts = (
        (CHECKER_PATH, HERE / CHECKER_NAME, 1_048_576, None),
        (RUNNER_PATH, HERE / RUNNER_NAME, 1_048_576, None),
        (CONTRACT_PATH, CONTRACT, 1_048_576, None),
        (
            TERMINAL_RECEIPT_PATH,
            TERMINAL_RECEIPT,
            contract["resource_limits"]["max_terminal_receipt_bytes"],
            None,
        ),
    )
    for path, local, maximum, exact in local_artifacts:
        if _git("show", f"{outcome_commit}:{path}") != _read_regular_nofollow(
            local, maximum, exact
        ):
            raise VerificationError("outcome/current artifact drift")
    local_checkpoint = _read_bundle_member_nofollow(
        CHECKPOINT_NAME,
        contract["checkpoint_encoding"]["total_bytes"],
        contract["checkpoint_encoding"]["total_bytes"],
    )
    local_result = _read_bundle_member_nofollow(
        RESULT_NAME, contract["resource_limits"]["max_result_bytes"]
    )
    raw_checkpoint = _git("show", f"{outcome_commit}:{CHECKPOINT_PATH}")
    raw_result = _git("show", f"{outcome_commit}:{RESULT_PATH}")
    if (
        raw_checkpoint != local_checkpoint
        or raw_result != local_result
    ):
        raise VerificationError("outcome/current bundle artifact drift")
    raw_receipt = _git("show", f"{outcome_commit}:{TERMINAL_RECEIPT_PATH}")
    checkpoint_record = parse_checkpoint(raw_checkpoint, contract)
    result = _load_json_bytes(raw_result)
    evidence = _validate_result(
        contract, result, checkpoint_record, protocol, len(raw_result)
    )
    evidence["terminal_execution_receipt"] = _validate_execution_receipt(
        raw_receipt,
        contract,
        contract_commit,
        protocol,
        result,
        checkpoint_record,
        raw_result,
    )
    return evidence


def main(argv: list[str] | None = None) -> int:
    import argparse

    class StrictParser(argparse.ArgumentParser):
        def error(self, message: str) -> None:
            raise VerificationError(message)

    parser = StrictParser(allow_abbrev=False)
    parser.add_argument(
        "--mode", required=True, choices=("static", "heavy", "execute")
    )
    parser.add_argument("--contract-commit", required=True)
    parser.add_argument("--outcome-commit")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
        contract = _load_json_bytes(_read_regular_nofollow(CONTRACT, 1_048_576))
        if args.outcome_commit is None:
            if args.mode == "execute":
                evidence = execute_official(contract, args.contract_commit)
            elif args.mode != "static":
                raise VerificationError("heavy mode requires --outcome-commit")
            else:
                protocol = verify_protocol(contract, args.contract_commit)
                evidence = {
                    "contract_id": CONTRACT_ID,
                    "status": "VERIFIED_D11_PROTOCOL_STATIC_NO_OUTPUT",
                    "verified": True,
                    "mode": "static",
                    "protocol": protocol,
                    "source_evidence": verify_sources(contract),
                    "byte_table_full_domain_validation": verify_byte_tables(contract),
                    "outputs_absent_at_contract_freeze": True,
                    "checkpoint_replay_authorized_by_frozen_contract": True,
                    "depth3_to_depth4_execution_authorized": False,
                }
        else:
            if args.mode == "execute":
                raise VerificationError("execute mode forbids --outcome-commit")
            evidence = verify_outcome(contract, args.contract_commit, args.outcome_commit)
            if args.mode == "heavy":
                raw_checkpoint = _git("show", f"{args.outcome_commit}:{CHECKPOINT_PATH}")
                checkpoint_record = parse_checkpoint(raw_checkpoint, contract)
                evidence = {
                    "static": evidence,
                    "heavy": heavy_replay(contract, raw_checkpoint, checkpoint_record),
                }
    except Exception as exc:
        resource_errnos = {
            errno.EDQUOT,
            errno.EFBIG,
            errno.EMFILE,
            errno.ENFILE,
            errno.ENOMEM,
            errno.ENOSPC,
            errno.ETIMEDOUT,
        }
        if (
            isinstance(exc, (ResourceIndeterminate, MemoryError))
            or type(exc).__name__ in {"ResourceNoGo", "DeadlineExceeded"}
            or isinstance(exc, OSError)
            and exc.errno in resource_errnos
        ):
            failure_status = "INDETERMINATE_D11_PACKED_Q3_CHECKPOINT_RESOURCE_ENVELOPE"
        elif isinstance(exc, ScientificNoGo) or type(exc).__name__ == "SemanticNoGo":
            failure_status = "NO_GO_D11_PACKED_Q3_CHECKPOINT_SEMANTICS"
        else:
            failure_status = "VERIFICATION_FAILED"
        print(
            json.dumps(
                {"status": failure_status, "verified": False, "error": str(exc)},
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
