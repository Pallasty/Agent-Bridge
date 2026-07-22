#!/usr/bin/env python3
"""Produce the frozen FH-L8 D11 packed depth-3 quotient checkpoint.

This runner has one scientific capability: replay the pinned full-basis Krylov
source from depth 0 through depth 3.  Its action guard rejects a fourth action
before the pinned Hamiltonian implementation can be entered.  It never imports
the D11 checker and never performs a quotient-H depth-3 to depth-4 transition.
"""

from __future__ import annotations

import ctypes
import errno
import gc
import hashlib
import json
import os
import re
import resource
import signal
import stat
import struct
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any, Callable, Mapping


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
PREFIX = "docs/research/fermion-frontier"
RUNNER_NAME = "fh_l8_packed_q3_checkpoint_d11_runner.py"
CHECKER_NAME = "fh_l8_packed_q3_checkpoint_d11_checker.py"
CONTRACT_NAME = "fh_l8_packed_q3_checkpoint_d11_contract.json"
BUNDLE_NAME = "fh_l8_packed_q3_checkpoint_d11_bundle"
STAGING_NAME = f".{BUNDLE_NAME}.staging"
STAGING_PREFIX = f".{BUNDLE_NAME}."
CHECKPOINT_NAME = "checkpoint.bin"
RESULT_NAME = "result.json"
TERMINAL_RECEIPT_NAME = "fh_l8_packed_q3_checkpoint_d11_terminal_receipt.json"
TERMINAL_RECEIPT_STAGING_NAME = f".{TERMINAL_RECEIPT_NAME}.staging"
RUNNER_PATH = f"{PREFIX}/{RUNNER_NAME}"
CHECKER_PATH = f"{PREFIX}/{CHECKER_NAME}"
CONTRACT_PATH = f"{PREFIX}/{CONTRACT_NAME}"
BUNDLE_PATH = f"{PREFIX}/{BUNDLE_NAME}"
CHECKPOINT_RELATIVE_PATH = f"{BUNDLE_NAME}/{CHECKPOINT_NAME}"
RESULT_RELATIVE_PATH = f"{BUNDLE_NAME}/{RESULT_NAME}"
CHECKPOINT_PATH = f"{PREFIX}/{CHECKPOINT_RELATIVE_PATH}"
RESULT_PATH = f"{PREFIX}/{RESULT_RELATIVE_PATH}"
TERMINAL_RECEIPT_PATH = f"{PREFIX}/{TERMINAL_RECEIPT_NAME}"
CONTRACT = HERE / CONTRACT_NAME

CONTRACT_ID = "FH-L8-D11-PACKED-D3-QUOTIENT-CHECKPOINT-MATERIALIZATION-V1"
STATUS = "VERIFIED_D11_PACKED_DEPTH3_QUOTIENT_CHECKPOINT_MATERIALIZED_NO_Q4_AUTHORITY"
NO_GO_STATUS = "NO_GO_D11_PACKED_Q3_CHECKPOINT_SEMANTICS"
INDETERMINATE_STATUS = "INDETERMINATE_D11_PACKED_Q3_CHECKPOINT_RESOURCE_ENVELOPE"
FORMAT_ID = "FH-L8-D11-PACKED-Q3-RECORD-V1"

BASE_COMMIT = "b620f02ff53ed84472d0f38c775bdeb584fdf736"
BASE_TREE = "64dd609322f7c8741f7b6536ad9a78ed9af24e95"
D7_INTEGRATION_COMMIT = "9e415753383335578d649d88803ce193b16398f5"
D7_INTEGRATION_TREE = "c92dcfab269a56894573921abf5517e5f4ea0844"
SHA40_RE = re.compile(r"[0-9a-f]{40}")
SHA64_RE = re.compile(r"[0-9a-f]{64}")

MEMORY_MAX_BYTES = 1_073_741_824
MEMORY_HIGH_BYTES = 805_306_368
SWAP_MAX_BYTES = 0
PROCESS_RSS_MAX_BYTES = 536_870_912
CGROUP_PEAK_MAX_BYTES = 805_306_368
INITIAL_CGROUP_PEAK_MAX_BYTES = 134_217_728
INTERNAL_DEADLINE_SECONDS = 300
OUTER_DEADLINE_SECONDS = 330
MAX_MATERIALIZED_STATES = 2_000_000
MAX_SOURCE_BYTES = 1_048_576
MAX_RESULT_BYTES = 131_072
MAX_TERMINAL_RECEIPT_BYTES = 32_768
MAX_RUNNER_STDOUT_CAPTURE_BYTES = 32_768
MAX_RUNNER_STDERR_CAPTURE_BYTES = 32_768
MAX_IO_CHUNK_BYTES = 1_048_576
MINIMUM_OUTPUT_FREE_BYTES = 33_554_432
OPEN_FILE_DESCRIPTOR_LIMIT = 32
FILE_SIZE_LIMIT_BYTES = 8_388_608
RECORD_BYTES = 32
RECORD_COUNT = 213_099
CHECKPOINT_BYTES = RECORD_BYTES * RECORD_COUNT
MAX_ABS_AMPLITUDE = 43_614_208
MASK128 = (1 << 128) - 1

# u128 representative, i64 amplitude, u8 orbit size, u8 flags,
# u16 reserved, u32 zero-based D5B insertion rank.
RECORD = struct.Struct(">16sqBBHI")
assert RECORD.size == RECORD_BYTES

EXPECTED_COUNTS = (1, 225, 24_421, 1_704_285)
EXPECTED_FULL_DIGESTS = (
    "4851eca743653e8f5e4b1aaa7796811bc24f1bca5e23432e5bc96bfd9882bec9",
    "9cbbe6d7e508bd37eef5ec54bfa5b580b80d0b3dc3998146c900d03220a847b3",
    "c92f2de07caa1a289d7aa27cd0fa64e707e084cf96e06219161ea55ff3f3c88b",
    "6f8f53101b8a3ec0b3dfcee624a014426d93a8aa0dfc1300780b0ad99b765e97",
)
EXPECTED_INSERTION_DIGEST = (
    "7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e"
)
EXPECTED_SUPPORT_DIGEST = (
    "7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26"
)
EXPECTED_ORBIT_HISTOGRAM = {"1": 1, "4": 125, "8": 212_973}
EXPECTED_STABILIZER_HISTOGRAM = {"1": 212_973, "2": 125, "8": 1}
GROUP_ORDER = ("I", "R90", "R180", "R270", "MX", "MY", "MD", "MA")
D5A_GROUP_ORDER = (
    "id",
    "r90_spinflip",
    "r180",
    "r270_spinflip",
    "fv_spinflip",
    "fh_spinflip",
    "diag",
    "adiag",
)

SOURCE_PINS = {
    "fh_l8_symmetry_orbit_quotient_d5_checker.py": (
        48_414,
        "681bc63fedce8b71cfb536c66d321467bc8f01cb5947bee59b4291e2ac51a022",
    ),
    "fh_l8_symmetry_orbit_quotient_d5_contract.json": (
        4_999,
        "1ebd1d38c0c40ca9617f86e09c86d528196260dd6b6b6692c34dacfe7a28d392",
    ),
    "fh_l8_symmetry_orbit_quotient_d5_result.json": (
        9_319,
        "a04a4d0be6265dcaf9d39c7937fc133d19c7a2050e1434c7cb24be88b795baed",
    ),
    "fh_l8_byte_table_orbit_d6_checker.py": (
        6_150,
        "6877a5ed376a85a77000fe5d46dc39975294b3a266dda188c26a9aba92b647ad",
    ),
    "fh_l8_byte_table_orbit_d6_contract.json": (
        1_146,
        "ce2b6f29b86965e392cbf26fe2d6d9aba2f795d4ccc51804101f893c72f65374",
    ),
    "fh_l8_byte_table_orbit_d6_result.json": (
        1_079,
        "5645aba12743e71853e1f0ace734116fec96203f1a150097a66a8969de3d7418",
    ),
    "fh_l8_signed_d4_orbit_d5_checker.py": (
        8_716,
        "1edf1275a4fa2e3407c5903876bf6000e0dabe0113a5e403c67ad4f7e0ff7bf7",
    ),
    "fh_l8_signed_d4_orbit_d5_contract.json": (
        2_000,
        "0b3e1b53086e3c66af7d42aa3276c3624c14267dc89a77b84a1071cf05770441",
    ),
    "fh_l8_signed_d4_orbit_d5_result.json": (
        2_048,
        "79d5251a0f433b8d79f5f7a5ed9916aea13146c0ff6f869f841ff53699eaa47b",
    ),
}

SOURCE_ARTIFACT_BLOBS = {
    "fh_l8_symmetry_orbit_quotient_d5_checker.py": "129b8f7c12b19deaee518c5dfdbcf9047a91c418",
    "fh_l8_symmetry_orbit_quotient_d5_contract.json": "0969f7214db04f771a6533f7bb8ca702f71849fe",
    "fh_l8_symmetry_orbit_quotient_d5_result.json": "f8b461b0d22e04413f01c49d072941be6d91c43b",
    "fh_l8_byte_table_orbit_d6_checker.py": "4a3083ae2c511b79d7a560f9a842c67ea10b77fd",
    "fh_l8_byte_table_orbit_d6_contract.json": "fc5aa621be228a20d5c3a71db1139f4731dc181e",
    "fh_l8_byte_table_orbit_d6_result.json": "7ff34d654a9a34e4e2a8de86371d13e9ced2c942",
    "fh_l8_signed_d4_orbit_d5_checker.py": "0cbf87befd79ad4bc5d48f923c9effa5b13f96da",
    "fh_l8_signed_d4_orbit_d5_contract.json": "33818f489ae04ec7ac381929349b43ee1955f103",
    "fh_l8_signed_d4_orbit_d5_result.json": "a89c0bcd279f42fc570ad0057f2799f4c8b27991",
}

D7_ARTIFACTS = [
    {
        "path": "fh_l8_depth3_to_depth4_quotient_h_design_gate_checker.py",
        "mode": "100644",
        "blob": "7ce1e4325d698f90cbe4f9e06792dfdb76189b8a",
        "bytes": 38_614,
        "sha256": "b43fcf1613fd2f3abd378c66261d2d01ca325446820bea735b5af4605dd379ae",
    },
    {
        "path": "fh_l8_depth3_to_depth4_quotient_h_design_gate_contract.json",
        "mode": "100644",
        "blob": "1ccb6fe77a439ceb643aa3cd5fcb236cb0ec92aa",
        "bytes": 15_890,
        "sha256": "9557b9523b5d5f29d76a3d02dc50b76553879961dae7d168dc90080529fc61ed",
    },
    {
        "path": "FH_L8_DEPTH3_TO_DEPTH4_QUOTIENT_H_DESIGN_GATE_ZH.md",
        "mode": "100644",
        "blob": "39f198c8434452d78be27ee3dec8af592e0ec3a3",
        "bytes": 6_295,
        "sha256": "350d970c8d4d903f8ae21c69699f12aec211461cd173db913876f02946832610",
    },
]

UPSTREAM_D8_ARTIFACTS = [
    {"path": "fh_l8_packed_depth3_checkpoint_d8_checker.py", "mode": "100644", "blob": "72436ddecb37ab0344223b0343e113d030cbb5cd", "bytes": 4881, "sha256": "c8cbc65a325d47ef92b65498d8f8513565d295a375e503f196f288d5a2529467"},
    {"path": "fh_l8_packed_depth3_checkpoint_d8_contract.json", "mode": "100644", "blob": "3cab52cd4d5c2785a856a318d4fbca5de17b8e17", "bytes": 1837, "sha256": "fc140ef5af58d2978d8b24e15d63a81b2c30d09ae35526f1513f05f8e17c8a80"},
    {"path": "fh_l8_packed_depth3_checkpoint_d8_result.json", "mode": "100644", "blob": "a80d9dec0bdb1be4a2ebb7a837bb8aaa4ed74890", "bytes": 869, "sha256": "a987cd1a683d4e4eaf64be9f7d159645c33c1be11f334e998ba49688bcce40e3"},
]

UPSTREAM_D9_ARTIFACTS = [
    {"path": "fh_l8_depth4_preflight_d9.py", "mode": "100644", "blob": "3d812781070b58c4f3a745468daa2c1292ad5f1a", "bytes": 4107, "sha256": "90b1590301ffcdc2f5c181a8e4a5ed14bddb032a2b8284f2fd410301e1974d3e"},
    {"path": "fh_l8_depth4_preflight_d9_contract.json", "mode": "100644", "blob": "47cf6217484510caf76c099235039fc336ef18cd", "bytes": 422, "sha256": "070a9eb93bec73cd2ffb4f979b77d4afb544ab64e6c348fef1c4902c79b939e0"},
    {"path": "fh_l8_depth4_preflight_d9_receipt.json", "mode": "100644", "blob": "65a6fb7e56a6337cb88e66e83121a3e83d3db2c2", "bytes": 654, "sha256": "b310b09fb68eec400910099aecfe82da63d45b8bb8dd0fd15c9f736fb132c0f4"},
]

UPSTREAM_D10_ARTIFACTS = [
    {"path": "test_fh_l8_cgroup_envelope_d10.py", "mode": "100644", "blob": "b8d1b4f58cc7e1f51a7d89a2a8e368bbe03740c1", "bytes": 1018, "sha256": "5c34a9524291165633d7695b668dc5c48293193a83b72852f16a072c301f6ea7"},
    {"path": "fh_l8_cgroup_envelope_d10_contract.json", "mode": "100644", "blob": "f668ff7b579cf99c281bc800adcfe00e9dbe14d6", "bytes": 429, "sha256": "9fadd4e58ad65a0ddd9cb12ee09fd0e96dd0e09b270abb06a8858b20eb038ce3"},
    {"path": "fh_l8_cgroup_envelope_d10_receipt.json", "mode": "100644", "blob": "835fb18bd87c3c867f5747e4c250d8542388496e", "bytes": 630, "sha256": "6f61a66b579969d8319f25e75bdc92e7cd55d013f274483a258e75155d6e9788"},
]

UPSTREAM_PROGRESSION = {
    "d8_protocol_only": {
        "contract_id": "FH-L8-INDEPENDENT-REFERENCE-D8",
        "result_status": "VERIFIED_D8_PACKED_DEPTH3_QUOTIENT_CHECKPOINT_PROTOCOL_NO_MATERIALIZATION",
        "outcome": {"commit": "bae8f05598d1c94da1d0c66dd67e30cc32e4f3ff", "tree": "ac944d406bbe2173efcc23034b5454bee3e40bf3", "parents": ["9e415753383335578d649d88803ce193b16398f5"]},
        "integration": {"commit": "14e9a75dd9c455a4a5a87c80cc80c09dd6342341", "tree": "ac944d406bbe2173efcc23034b5454bee3e40bf3", "parents": ["9e415753383335578d649d88803ce193b16398f5", "bae8f05598d1c94da1d0c66dd67e30cc32e4f3ff"]},
        "artifacts": UPSTREAM_D8_ARTIFACTS,
    },
    "d9_bounded_preflight": {
        "contract_id": "FH-L8-INDEPENDENT-REFERENCE-D9",
        "receipt_status": "VERIFIED_D9_PREFLIGHT_CGROUP_ENVELOPE_FAILURE_NO_FULL_RUN_AUTHORIZATION",
        "origin": {"commit": "ef9c43ecd8dc6954d303dfdfc457d31d09d39fe8", "tree": "14973ecbd25824078e3502d21d532f07e32d34e3", "parents": ["14e9a75dd9c455a4a5a87c80cc80c09dd6342341"]},
        "initial_integration": {"commit": "053155a6c53fb23612ed21b589aacc811dd6ecd8", "tree": "14973ecbd25824078e3502d21d532f07e32d34e3", "parents": ["14e9a75dd9c455a4a5a87c80cc80c09dd6342341", "ef9c43ecd8dc6954d303dfdfc457d31d09d39fe8"]},
        "outcome": {"commit": "8693ab2b5c4d2153756c87304f5797976d723ff9", "tree": "40d47a8b43c972adadd0328f7c5c0634deac6cdd", "parents": ["ef9c43ecd8dc6954d303dfdfc457d31d09d39fe8"]},
        "clean_branch_tip": {"commit": "827e50d5d67dfeae94672ae4ee96252d21908be2", "tree": "ce4c5678e6d122ef2b79f0237effc60318ceeddd", "parents": ["8693ab2b5c4d2153756c87304f5797976d723ff9"]},
        "integration": {"commit": "dc600faca4b9a438fe9a3f154c87258f6269ee43", "tree": "ce4c5678e6d122ef2b79f0237effc60318ceeddd", "parents": ["053155a6c53fb23612ed21b589aacc811dd6ecd8", "827e50d5d67dfeae94672ae4ee96252d21908be2"]},
        "artifacts": UPSTREAM_D9_ARTIFACTS,
    },
    "d10_cgroup_envelope": {
        "contract_id": "FH-L8-INDEPENDENT-REFERENCE-D10",
        "receipt_status": "VERIFIED_D9_BOUNDED_QUOTIENT_H_PREFLIGHT_NO_FULL_ACTION",
        "outcome": {"commit": "994e528025aeea3883a58eccb5053694181677b2", "tree": "58020e45817e481b3b69f5eab38f7512b84294fe", "parents": ["827e50d5d67dfeae94672ae4ee96252d21908be2"]},
        "integration": {"commit": "782cdcd26196de3e59dd59fc1ac3fc52e73abbbd", "tree": "58020e45817e481b3b69f5eab38f7512b84294fe", "parents": ["dc600faca4b9a438fe9a3f154c87258f6269ee43", "994e528025aeea3883a58eccb5053694181677b2"]},
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

SOURCE_OUTCOMES = {
    "d5b_full_quotient_lane": {
        "commit": "2f9556a986c50a42ff3096ded45b75e39c5a61a9",
        "tree": "c1164c1acffb570448038b461cc619ca5164d2f9",
        "parents": ["6daf30daeeb375962b9986af5df91517d8a4a8ec"],
    },
    "d6_byte_table_support_lane": {
        "commit": "e45b5b9f68520289d3396c0af071019856afe56e",
        "tree": "80724d12483ec39e0926ca4bfa341c6483eb27f9",
        "parents": ["64438c47be710835626dea0ceb2521b6634951dc"],
    },
    "d5a_direct_support_reference": {
        "commit": "72fe3b79a79501d5d523dc959a6a98b36a470bd4",
        "tree": "fa4ce50442da0e4c8e617d7d3497fea4cf34c49b",
        "parents": ["ae3935774d80f37b10f8317d0e17d339f03436cc"],
    },
}

AUTHORITY = {
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

LIMITATIONS = [
    "The checkpoint contains the pinned depth-3 quotient source only; no depth-3 to depth-4 action is authorized or executed.",
    "The D11 record format is a separate self-verifying materialization format and does not claim byte compatibility with D8's unmaterialized layout.",
    "The binary digest is over ascending fixed-width records and is distinct from the D5B insertion-order quotient digest.",
    "The exhaustive byte-table test certifies support permutation entries, not fermionic phases or quotient amplitudes.",
    "Observed checkpoint-generation time and memory do not certify q3-to-q4 runtime or memory feasibility.",
    "No target vector, remainder, cumulative, R100, physical-reference, hardware, quantum-advantage, or READY claim is certified.",
    "D10 already verified only a bounded 4,096-source preflight under 1 GiB and zero swap; the eligible successor is a separately frozen checkpointed full q3-to-q4 runner protocol, and this result grants no execution authority.",
]


class RunnerError(RuntimeError):
    """A protocol, source, scientific, output, or resource gate failed."""


class ActionBoundaryError(RunnerError):
    """An attempted Hamiltonian action exceeded the frozen q0-to-q3 boundary."""


class ResourceIndeterminate(RunnerError):
    """The run did not produce evidence because its resource envelope failed."""


class DeadlineExceeded(ResourceIndeterminate):
    """The frozen internal deadline elapsed."""


class ScientificReplayError(RunnerError):
    """Pinned scientific replay or digest evidence failed."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), *args], stderr=subprocess.DEVNULL
    )


def _read_regular_nofollow(path: Path, maximum: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        identity = os.fstat(fd)
        if not stat.S_ISREG(identity.st_mode) or identity.st_size > maximum:
            raise RunnerError(f"invalid regular input: {path.name}")
        chunks: list[bytes] = []
        remaining = identity.st_size
        while remaining:
            chunk = os.read(fd, min(1_048_576, remaining))
            if not chunk:
                raise RunnerError(f"short read: {path.name}")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise RunnerError(f"input grew while reading: {path.name}")
        after = os.fstat(fd)
        if (
            identity.st_dev,
            identity.st_ino,
            identity.st_size,
            identity.st_mtime_ns,
        ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise RunnerError(f"input changed while reading: {path.name}")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _load_json(raw: bytes, name: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise RunnerError(f"duplicate JSON key in {name}: {key}")
            value[key] = item
        return value

    try:
        value = json.loads(raw, object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        raise RunnerError(f"invalid JSON: {name}") from exc
    if not isinstance(value, dict):
        raise RunnerError(f"JSON root is not an object: {name}")
    return value


def _load_pinned_sources() -> tuple[dict[str, bytes], dict[str, Any]]:
    loaded: dict[str, bytes] = {}
    for name, (expected_bytes, expected_sha) in SOURCE_PINS.items():
        raw = _read_regular_nofollow(HERE / name, MAX_SOURCE_BYTES)
        if len(raw) != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_sha:
            raise RunnerError(f"pinned source drift: {name}")
        loaded[name] = raw
    parsed = {
        name: _load_json(raw, name)
        for name, raw in loaded.items()
        if name.endswith(".json")
    }
    d5b_result = parsed["fh_l8_symmetry_orbit_quotient_d5_result.json"]
    d6_result = parsed["fh_l8_byte_table_orbit_d6_result.json"]
    d5a_result = parsed["fh_l8_signed_d4_orbit_d5_result.json"]
    if (
        d5b_result.get("status")
        != "VERIFIED_D5_SYMMETRY_ORBIT_QUOTIENT_ADMISSIBLE_FOR_D6_DESIGN"
        or d5b_result.get("verified") is not True
        or d6_result.get("status") != "VERIFIED_D6_BYTE_TABLE_SIGNED_D4_DEPTH3_ORBITS"
        or d6_result.get("verified") is not True
        or d5a_result.get("status")
        != "VERIFIED_D5_SIGNED_D4_CUSTODY_AND_DEPTH3_ORBIT_PREFIX_BOUNDARY"
        or d5a_result.get("verified") is not True
    ):
        raise RunnerError("pinned source authority drift")
    return loaded, parsed


def _module_from_bytes(name: str, path: Path, raw: bytes) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def _source_artifact_records(names: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {
            "path": name,
            "mode": "100644",
            "blob": SOURCE_ARTIFACT_BLOBS[name],
            "bytes": SOURCE_PINS[name][0],
            "sha256": SOURCE_PINS[name][1],
        }
        for name in names
    ]


def _validate_source_evidence(source: Any) -> None:
    if not isinstance(source, Mapping) or set(source) != {
        "d7_design_gate",
        "upstream_progression",
        "d5b_full_quotient_lane",
        "d6_byte_table_support_lane",
        "d5a_direct_support_reference",
        "relationship",
    }:
        raise RunnerError("source evidence schema drift")
    baseline = {
        "commit": D7_INTEGRATION_COMMIT,
        "tree": D7_INTEGRATION_TREE,
        "parents": [
            "72e1e56af49b91267738d0b0108640f358fde59a",
            "6a9b97a0ee0c7d37878f3f267cfc07d002c86ada",
        ],
    }
    d7 = source["d7_design_gate"]
    if not isinstance(d7, Mapping) or set(d7) != {
        "contract_id",
        "status",
        "integration",
        "contract_freeze_commit",
        "artifacts",
    }:
        raise RunnerError("D7 source schema drift")
    if (
        d7["contract_id"] != "FH-L8-QUOTIENT-H-D3-TO-D4-DESIGN-GATE-V1"
        or d7["status"]
        != "VERIFIED_D7_QUOTIENT_H_DESIGN_GATE_FROZEN_NO_EXECUTION_AUTHORITY"
        or d7["contract_freeze_commit"]
        != "4544d4c0e02103c76e465abea43a08b91367a286"
        or d7["artifacts"] != D7_ARTIFACTS
    ):
        raise RunnerError("D7 source identity drift")
    _verify_commit(d7["integration"], baseline)
    _verify_committed_artifacts(D7_INTEGRATION_COMMIT, D7_ARTIFACTS)

    upstream = source["upstream_progression"]
    if upstream != UPSTREAM_PROGRESSION:
        raise RunnerError("D8-D10 upstream progression drift")
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
        _verify_committed_artifacts(stage["outcome"]["commit"], expected_artifacts)
    d8_contract = _load_json(
        _read_regular_nofollow(HERE / "fh_l8_packed_depth3_checkpoint_d8_contract.json", MAX_SOURCE_BYTES),
        "fh_l8_packed_depth3_checkpoint_d8_contract.json",
    )
    d8_result = _load_json(
        _read_regular_nofollow(HERE / "fh_l8_packed_depth3_checkpoint_d8_result.json", MAX_SOURCE_BYTES),
        "fh_l8_packed_depth3_checkpoint_d8_result.json",
    )
    d9_contract = _load_json(
        _read_regular_nofollow(HERE / "fh_l8_depth4_preflight_d9_contract.json", MAX_SOURCE_BYTES),
        "fh_l8_depth4_preflight_d9_contract.json",
    )
    d9_receipt = _load_json(
        _read_regular_nofollow(HERE / "fh_l8_depth4_preflight_d9_receipt.json", MAX_SOURCE_BYTES),
        "fh_l8_depth4_preflight_d9_receipt.json",
    )
    d10_contract = _load_json(
        _read_regular_nofollow(HERE / "fh_l8_cgroup_envelope_d10_contract.json", MAX_SOURCE_BYTES),
        "fh_l8_cgroup_envelope_d10_contract.json",
    )
    d10_receipt = _load_json(
        _read_regular_nofollow(HERE / "fh_l8_cgroup_envelope_d10_receipt.json", MAX_SOURCE_BYTES),
        "fh_l8_cgroup_envelope_d10_receipt.json",
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
        != {"memory_max": "1073741824", "memory_swap_max": "0", "memory_high": "805306368", "preflight_sources": 4096}
        or d10_receipt.get("status")
        != upstream["d10_cgroup_envelope"]["receipt_status"]
        or d10_receipt.get("memory_envelope_pass") is not True
        or d10_receipt.get("memory_max") != "1073741824"
        or d10_receipt.get("memory_swap_max") != "0"
        or d10_receipt.get("full_run_authorized") is not False
        or d10_receipt.get("fourth_action_executed") is not False
    ):
        raise RunnerError("D8-D10 upstream semantic boundary drift")

    lane_specs = {
        "d5b_full_quotient_lane": (
            "FH-L8-D5-EVIDENCE-SYMMETRY-ORBIT-QUOTIENT-V1",
            "full_depth3_signed_quotient_semantics_and_source_amplitudes",
            (
                "fh_l8_symmetry_orbit_quotient_d5_checker.py",
                "fh_l8_symmetry_orbit_quotient_d5_contract.json",
                "fh_l8_symmetry_orbit_quotient_d5_result.json",
            ),
        ),
        "d6_byte_table_support_lane": (
            "FH-L8-D6-EVIDENCE-BYTE-TABLE-SUPPORT-ORBIT-V1",
            "byte_table_support_only_no_phase_or_amplitude",
            (
                "fh_l8_byte_table_orbit_d6_checker.py",
                "fh_l8_byte_table_orbit_d6_contract.json",
                "fh_l8_byte_table_orbit_d6_result.json",
            ),
        ),
        "d5a_direct_support_reference": (
            "FH-L8-D5A-EVIDENCE-DIRECT-SIGNED-D4-SUPPORT-V1",
            "direct_mode_permutation_reference_only",
            (
                "fh_l8_signed_d4_orbit_d5_checker.py",
                "fh_l8_signed_d4_orbit_d5_contract.json",
                "fh_l8_signed_d4_orbit_d5_result.json",
            ),
        ),
    }
    for lane_name, (route_alias, scope, names) in lane_specs.items():
        lane = source[lane_name]
        expected_artifacts = _source_artifact_records(names)
        if (
            not isinstance(lane, Mapping)
            or set(lane) != {"route_alias", "scope", "outcome", "artifacts"}
            or lane["route_alias"] != route_alias
            or lane["scope"] != scope
            or lane["artifacts"] != expected_artifacts
        ):
            raise RunnerError(f"source lane drift: {lane_name}")
        outcome = SOURCE_OUTCOMES[lane_name]
        _verify_commit(lane["outcome"], outcome)
        _verify_committed_artifacts(outcome["commit"], expected_artifacts)
    if source["relationship"] != {
        "D7_authorizes_checkpoint_protocol_only": True,
        "D5B_supplies_signed_CAR_quotient_coordinates_and_amplitudes": True,
        "D6_supplies_support_byte_tables_only": True,
        "D5A_supplies_direct_support_permutations_only": True,
        "D6_or_D5A_supplies_phase_or_amplitude": False,
        "bare_legacy_contract_id_lookup_forbidden": True,
        "evidence_is_additive": False,
    }:
        raise RunnerError("source relationship drift")


def _validate_contract(contract: Mapping[str, Any]) -> None:
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
        raise RunnerError("contract schema drift")
    if (
        type(contract.get("schema_version")) is not int
        or contract.get("schema_version") != 1
        or contract.get("contract_id") != CONTRACT_ID
        or contract.get("status") != "PROTOCOL_FROZEN_BEFORE_PACKED_Q3_REPLAY"
        or contract.get("analysis_class")
        != "PREREGISTERED_DEPTH0_TO_DEPTH3_REPLAY_AND_CHECKPOINT_ONLY"
    ):
        raise RunnerError("contract identity/status drift")
    _validate_source_evidence(contract.get("source_evidence"))
    expected_depth_records = [
        {
            "depth": depth,
            "full_state_count": EXPECTED_COUNTS[depth],
            "full_vector_sha256": EXPECTED_FULL_DIGESTS[depth],
        }
        for depth in range(4)
    ]
    expected_workload = {
        "linear_size": 8,
        "boundary": "square_open_boundary_no_wrap",
        "particle_sector": "N_up=32,N_down=32",
        "replayed_source_depths": [0, 1, 2],
        "materialized_depth": 3,
        "expected_full_state_count": EXPECTED_COUNTS[3],
        "expected_representative_count": RECORD_COUNT,
        "expected_full_vector_sha256": EXPECTED_FULL_DIGESTS[3],
        "expected_D5B_insertion_order_quotient_sha256": EXPECTED_INSERTION_DIGEST,
        "expected_D6_sorted_support_orbit_sha256": EXPECTED_SUPPORT_DIGEST,
        "expected_depth_records": expected_depth_records,
        "expected_orbit_size_histogram": EXPECTED_ORBIT_HISTOGRAM,
        "hamiltonian_action_call_budget": 3,
        "allowed_acted_source_depths": [0, 1, 2],
        "depth3_to_depth4_action_authorized": False,
    }
    if contract.get("workload") != expected_workload:
        raise RunnerError("contract workload drift")
    expected_encoding = {
        "format_id": FORMAT_ID,
        "format": "headerless_fixed_width_records",
        "record_order": "strictly_ascending_unsigned_representative",
        "representative": "unsigned_u128_big_endian_16_bytes",
        "amplitude": "signed_i64_twos_complement_big_endian_8_bytes",
        "orbit_size": "unsigned_u8_allowed_1_4_8",
        "flags": "unsigned_u8_must_be_zero",
        "reserved": "unsigned_u16_big_endian_must_be_zero",
        "d5b_insertion_rank": "unsigned_u32_big_endian_permutation_0_to_213098",
        "field_offsets": {
            "representative": 0,
            "amplitude": 16,
            "orbit_size": 24,
            "flags": 25,
            "reserved": 26,
            "d5b_insertion_rank": 28,
        },
        "record_bytes": RECORD_BYTES,
        "record_count": RECORD_COUNT,
        "total_bytes": CHECKPOINT_BYTES,
        "file_header_bytes": 0,
        "file_trailer_bytes": 0,
        "zero_amplitudes_allowed": False,
        "maximum_absolute_amplitude": MAX_ABS_AMPLITUDE,
    }
    if contract.get("checkpoint_encoding") != expected_encoding:
        raise RunnerError("contract checkpoint encoding drift")
    expected_byte_table = {
        "group_elements": 8,
        "source_byte_chunks": 16,
        "byte_values_per_chunk": 256,
        "expected_definition_entries": 32_768,
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
    }
    if contract.get("byte_table_qualification") != expected_byte_table:
        raise RunnerError("contract byte-table qualification drift")
    expected_limits = {
        "outer_memory_max_bytes": MEMORY_MAX_BYTES,
        "outer_memory_high_bytes": MEMORY_HIGH_BYTES,
        "outer_swap_max_bytes": SWAP_MAX_BYTES,
        "internal_deadline_seconds": INTERNAL_DEADLINE_SECONDS,
        "outer_deadline_seconds": OUTER_DEADLINE_SECONDS,
        "max_process_peak_rss_bytes": PROCESS_RSS_MAX_BYTES,
        "max_cgroup_peak_bytes": CGROUP_PEAK_MAX_BYTES,
        "max_initial_cgroup_peak_bytes": INITIAL_CGROUP_PEAK_MAX_BYTES,
        "max_source_bytes_per_artifact": MAX_SOURCE_BYTES,
        "max_materialized_full_states": MAX_MATERIALIZED_STATES,
        "max_orbit_relation_group_images": 16_000_000,
        "max_checkpoint_records": RECORD_COUNT,
        "max_checkpoint_bytes": CHECKPOINT_BYTES,
        "max_result_bytes": MAX_RESULT_BYTES,
        "max_terminal_receipt_bytes": MAX_TERMINAL_RECEIPT_BYTES,
        "max_runner_stdout_capture_bytes": MAX_RUNNER_STDOUT_CAPTURE_BYTES,
        "max_runner_stderr_capture_bytes": MAX_RUNNER_STDERR_CAPTURE_BYTES,
        "max_packing_sort_buffer_bytes": 33_554_432,
        "max_io_chunk_bytes": 1_048_576,
        "max_live_scratch_bytes": 16_777_216,
        "max_application_payload_writes_bytes": 16_777_216,
        "max_created_regular_files": 4,
        "max_created_directories": 1,
        "max_open_file_descriptors": 32,
        "minimum_output_free_bytes": 33_554_432,
    }
    if contract.get("resource_limits") != expected_limits:
        raise RunnerError("contract resource limit drift")
    if contract.get("verification_modes") != {
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
        raise RunnerError("contract verification-mode schema drift")
    if contract.get("decision_rule") != {
        "source_protocol_schema_encoding_or_committed_artifact_failure": "VERIFICATION_FAILED",
        "official_replay_scientific_mismatch": "NO_GO_D11_PACKED_Q3_CHECKPOINT_SEMANTICS",
        "resource_timeout_oom_cap_or_missing_terminal_receipt": "INDETERMINATE_D11_PACKED_Q3_CHECKPOINT_RESOURCE_ENVELOPE",
        "all_checkpoint_gates_true": STATUS,
        "execution_authority_on_any_outcome": False,
        "next_gate": "CHECKPOINTED_FULL_QUOTIENT_H_RUNNER_IMPLEMENTATION_AND_AUTHORIZATION",
    }:
        raise RunnerError("contract decision rule drift")
    if contract.get("authority_ceiling") != {
        "packed_q3_checkpoint_generation_authorized": True,
        "depth0_to_depth3_replay_authorized": True,
        "byte_table_definition_validation_authorized": True,
        "upstream_bounded_4096_source_preflight_verified_under_envelope": True,
        "checkpointed_full_q3_to_q4_runner_protocol_design_eligible": True,
        "checkpointed_full_q3_to_q4_runner_execution_authorized": False,
        "depth3_to_depth4_execution_authorized": False,
        "fourth_krylov_hamiltonian_action_authorized": False,
    }:
        raise RunnerError("contract authority ceiling drift")
    if contract.get("forbidden_claims") != LIMITATIONS:
        raise RunnerError("contract forbidden-claim boundary drift")


def _commit_record(commit: str) -> dict[str, Any]:
    if not isinstance(commit, str) or SHA40_RE.fullmatch(commit) is None:
        raise RunnerError("full commit id required")
    exact = _git("rev-parse", f"{commit}^{{commit}}").decode("ascii").strip()
    if exact != commit:
        raise RunnerError("commit id is not exact")
    return {
        "commit": commit,
        "tree": _git("rev-parse", f"{commit}^{{tree}}").decode("ascii").strip(),
        "parents": _git("rev-list", "--parents", "-n", "1", commit)
        .decode("ascii")
        .split()[1:],
    }


def _verify_commit(record: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    if record != expected or _commit_record(str(record.get("commit", ""))) != expected:
        raise RunnerError("commit record or topology drift")


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
        raise RunnerError("malformed NUL-delimited Git diff")
    entries: set[tuple[str, str]] = set()
    for index in range(0, len(parts), 2):
        status = parts[index].decode("ascii")
        path = parts[index + 1].decode("utf-8", errors="strict")
        if status not in {"A", "M", "D", "T"} or (status, path) in entries:
            raise RunnerError("unsupported/duplicate Git diff entry")
        entries.add((status, path))
    return entries


def _verify_committed_artifacts(commit: str, artifacts: list[dict[str, Any]]) -> None:
    for artifact in artifacts:
        name = artifact["path"]
        if Path(name).name != name:
            raise RunnerError("source artifact path escapes frontier directory")
        path = f"{PREFIX}/{name}"
        raw = _git("show", f"{commit}:{path}")
        fields = _git("ls-tree", commit, path).decode("ascii").split()
        if (
            len(fields) < 3
            or fields[0] != artifact["mode"]
            or fields[1] != "blob"
            or fields[2] != artifact["blob"]
            or len(raw) != artifact["bytes"]
            or hashlib.sha256(raw).hexdigest() != artifact["sha256"]
            or _read_regular_nofollow(HERE / name, MAX_SOURCE_BYTES) != raw
        ):
            raise RunnerError(f"committed source artifact drift: {name}")


def _verify_protocol_artifacts(commit: str, artifacts: Any) -> None:
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise RunnerError("protocol artifact family drift")
    expected_names = {CHECKER_NAME, RUNNER_NAME}
    observed_names: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, Mapping) or set(artifact) != {
            "path",
            "mode",
            "blob",
            "bytes",
            "sha256",
        }:
            raise RunnerError("protocol artifact schema drift")
        name = artifact["path"]
        if name not in expected_names or name in observed_names:
            raise RunnerError("protocol artifact path drift")
        if (
            artifact["mode"] != "100644"
            or not isinstance(artifact["blob"], str)
            or SHA40_RE.fullmatch(artifact["blob"]) is None
            or type(artifact["bytes"]) is not int
            or not 0 < artifact["bytes"] <= MAX_SOURCE_BYTES
            or not isinstance(artifact["sha256"], str)
            or SHA64_RE.fullmatch(artifact["sha256"]) is None
        ):
            raise RunnerError("protocol artifact identity schema drift")
        path = f"{PREFIX}/{name}"
        raw = _git("show", f"{commit}:{path}")
        fields = _git("ls-tree", commit, path).decode("ascii").split()
        if (
            len(fields) < 3
            or fields[0] != artifact["mode"]
            or fields[1] != "blob"
            or fields[2] != artifact["blob"]
            or len(raw) != artifact["bytes"]
            or hashlib.sha256(raw).hexdigest() != artifact["sha256"]
            or _read_regular_nofollow(HERE / name, MAX_SOURCE_BYTES) != raw
        ):
            raise RunnerError(f"protocol artifact identity drift: {name}")
        observed_names.add(name)
    if observed_names != expected_names:
        raise RunnerError("protocol artifact family drift")


def _verify_protocol(
    contract: Mapping[str, Any], contract_raw: bytes, contract_commit: str
) -> dict[str, Any]:
    chronology = contract.get("chronology")
    if not isinstance(chronology, Mapping) or set(chronology) != {
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
        raise RunnerError("chronology schema drift")
    baseline = {
        "commit": BASE_COMMIT,
        "tree": BASE_TREE,
        "parents": [
            "14b884b2c6a808a8955a13f172051fbb692b8b57",
        ],
    }
    _verify_commit(chronology["evidence_baseline"], baseline)
    freeze = chronology["protocol_source_freeze"]
    if (
        not isinstance(freeze, Mapping)
        or set(freeze) != {"commit", "tree", "parents"}
        or freeze["parents"] != [BASE_COMMIT]
    ):
        raise RunnerError("protocol source freeze topology drift")
    _verify_commit(freeze, freeze)
    if _diff_entries(freeze["commit"]) != {
        ("A", CHECKER_PATH),
        ("A", RUNNER_PATH),
    }:
        raise RunnerError("protocol source freeze must add only checker and runner")
    _verify_protocol_artifacts(freeze["commit"], contract.get("protocol_artifacts"))
    for path in (
        CONTRACT_PATH,
        CHECKPOINT_PATH,
        RESULT_PATH,
        TERMINAL_RECEIPT_PATH,
    ):
        if _path_exists(freeze["commit"], path):
            raise RunnerError("contract/output existed in protocol source freeze")
    if (
        chronology["contract_path"] != CONTRACT_PATH
        or chronology["bundle_path"] != BUNDLE_PATH
        or chronology["checkpoint_path"] != CHECKPOINT_PATH
        or chronology["result_path"] != RESULT_PATH
        or chronology["terminal_receipt_path"] != TERMINAL_RECEIPT_PATH
        or chronology["source_must_precede_contract"] is not True
        or chronology["outputs_must_be_absent_before_official_replay"] is not True
    ):
        raise RunnerError("chronology policy drift")
    contract_record = _commit_record(contract_commit)
    if contract_record["parents"] != [freeze["commit"]]:
        raise RunnerError("contract commit must directly descend from source freeze")
    if _git("rev-parse", "HEAD").decode("ascii").strip() != contract_commit:
        raise RunnerError("official replay must execute from the exact contract commit")
    if _diff_entries(contract_commit) != {("A", CONTRACT_PATH)}:
        raise RunnerError("contract freeze must add only the contract")
    fields = _git("ls-tree", contract_commit, CONTRACT_PATH).decode("ascii").split()
    if len(fields) < 3 or fields[0] != "100644" or fields[1] != "blob":
        raise RunnerError("contract Git mode/type drift")
    if _git("show", f"{contract_commit}:{CONTRACT_PATH}") != contract_raw:
        raise RunnerError("working contract differs from frozen contract")
    for path, name in ((CHECKER_PATH, CHECKER_NAME), (RUNNER_PATH, RUNNER_NAME)):
        if _git("show", f"{contract_commit}:{path}") != _read_regular_nofollow(
            HERE / name, MAX_SOURCE_BYTES
        ):
            raise RunnerError("protocol source changed after freeze")
    for path in (CHECKPOINT_PATH, RESULT_PATH, TERMINAL_RECEIPT_PATH):
        if _path_exists(contract_commit, path):
            raise RunnerError("official output existed in contract freeze")
    matches = []
    for path in _git("ls-tree", "-r", "--name-only", contract_commit, PREFIX).decode(
        "utf-8"
    ).splitlines():
        if path.endswith(".json") and CONTRACT_ID.encode("ascii") in _git(
            "show", f"{contract_commit}:{path}"
        ):
            matches.append(path)
    if matches != [CONTRACT_PATH]:
        raise RunnerError("contract id is not globally unique")
    return {
        "protocol_source_freeze_commit": freeze["commit"],
        "protocol_source_freeze_tree": freeze["tree"],
        "contract_freeze_commit": contract_record["commit"],
        "contract_freeze_tree": contract_record["tree"],
        "outputs_absent_before_official_replay": True,
        "terminal_receipt_path": TERMINAL_RECEIPT_PATH,
        "terminal_receipt_required_for_outcome": True,
    }


def _cgroup_directory() -> Path:
    membership = Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
    unified = [line.split(":", 2)[2] for line in membership if line.startswith("0::")]
    if len(unified) != 1:
        raise ResourceIndeterminate("fresh cgroup v2 membership required")
    root = Path("/sys/fs/cgroup").resolve()
    directory = (root / unified[0].lstrip("/")).resolve()
    if directory != root and root not in directory.parents:
        raise ResourceIndeterminate("cgroup path escaped unified hierarchy")
    return directory


class _LinuxStatFs(ctypes.Structure):
    _fields_ = [
        ("f_type", ctypes.c_long),
        ("f_bsize", ctypes.c_long),
        ("f_blocks", ctypes.c_ulong),
        ("f_bfree", ctypes.c_ulong),
        ("f_bavail", ctypes.c_ulong),
        ("f_files", ctypes.c_ulong),
        ("f_ffree", ctypes.c_ulong),
        ("f_fsid", ctypes.c_int * 2),
        ("f_namelen", ctypes.c_long),
        ("f_frsize", ctypes.c_long),
        ("f_flags", ctypes.c_long),
        ("f_spare", ctypes.c_long * 4),
    ]


def _output_filesystem_type(path: Path) -> str:
    libc = ctypes.CDLL(None, use_errno=True)
    statfs = getattr(libc, "statfs", None)
    if statfs is None:
        raise ResourceIndeterminate("Linux statfs is required")
    statfs.argtypes = [ctypes.c_char_p, ctypes.POINTER(_LinuxStatFs)]
    statfs.restype = ctypes.c_int
    record = _LinuxStatFs()
    if statfs(os.fsencode(path), ctypes.byref(record)) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(path))
    mask = (1 << (ctypes.sizeof(ctypes.c_long) * 8)) - 1
    magic = record.f_type & mask
    names = {
        0x01021994: "tmpfs",
        0x858458F6: "ramfs",
        0x794C7630: "overlayfs",
        0xEF53: "ext-family",
        0x58465342: "xfs",
        0x9123683E: "btrfs",
        0x6969: "nfs",
        0x65735546: "fuse",
        0x2FC12FC1: "zfs",
        0xF2F52010: "f2fs",
    }
    filesystem_type = names.get(magic, f"linux-statfs-0x{magic:x}")
    if filesystem_type in {"tmpfs", "ramfs"}:
        raise ResourceIndeterminate(
            f"ephemeral output filesystem forbidden: {filesystem_type}"
        )
    return filesystem_type


def _set_soft_resource_limit(kind: int, target: int, label: str) -> tuple[int, int]:
    previous = resource.getrlimit(kind)
    hard = previous[1]
    if hard != resource.RLIM_INFINITY and hard < target:
        raise ResourceIndeterminate(
            f"hard {label} resource limit is below the frozen value"
        )
    resource.setrlimit(kind, (target, hard))
    if resource.getrlimit(kind)[0] != target:
        raise ResourceIndeterminate(f"failed to set frozen {label} resource limit")
    return previous


def _read_cgroup_number(path: Path) -> int:
    text = path.read_text(encoding="ascii").strip()
    if text == "max" or not text.isdecimal():
        raise ResourceIndeterminate(f"finite cgroup number required: {path.name}")
    return int(text)


def _read_memory_events(directory: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in (directory / "memory.events").read_text(encoding="ascii").splitlines():
        fields = line.split()
        if len(fields) != 2 or not fields[1].isdecimal():
            raise ResourceIndeterminate("invalid memory.events")
        values[fields[0]] = int(fields[1])
    selected = ("low", "high", "max", "oom", "oom_kill", "oom_group_kill")
    for required in selected:
        if required not in values:
            raise ResourceIndeterminate(f"memory.events lacks {required}")
    return {name: values[name] for name in selected}


class ResourceEnvelope:
    def __init__(self) -> None:
        self.directory = _cgroup_directory()
        if self.directory == Path("/sys/fs/cgroup").resolve():
            raise ResourceIndeterminate("a fresh non-root cgroup v2 is required")
        self.memory_max = _read_cgroup_number(self.directory / "memory.max")
        self.memory_high = _read_cgroup_number(self.directory / "memory.high")
        self.swap_max = _read_cgroup_number(self.directory / "memory.swap.max")
        self.initial_peak = _read_cgroup_number(self.directory / "memory.peak")
        self.initial_events = _read_memory_events(self.directory)
        self.sampled_max_current = _read_cgroup_number(self.directory / "memory.current")
        if (
            self.memory_max != MEMORY_MAX_BYTES
            or self.memory_high != MEMORY_HIGH_BYTES
            or self.swap_max != SWAP_MAX_BYTES
        ):
            raise ResourceIndeterminate(
                "1 GiB / 768 MiB high / zero-swap cgroup envelope required"
            )
        if self.initial_peak > INITIAL_CGROUP_PEAK_MAX_BYTES:
            raise ResourceIndeterminate("cgroup peak already exceeds frozen cap")
        if any(
            self.initial_events[name] != 0
            for name in ("max", "oom", "oom_kill", "oom_group_kill")
        ):
            raise ResourceIndeterminate("fresh cgroup has prior memory-limit/OOM events")
        if _read_cgroup_number(self.directory / "memory.swap.current") != 0:
            raise ResourceIndeterminate("nonzero cgroup swap current")

    def check(self) -> None:
        memory_max = _read_cgroup_number(self.directory / "memory.max")
        memory_high = _read_cgroup_number(self.directory / "memory.high")
        swap_max = _read_cgroup_number(self.directory / "memory.swap.max")
        current = _read_cgroup_number(self.directory / "memory.current")
        peak = _read_cgroup_number(self.directory / "memory.peak")
        swap = _read_cgroup_number(self.directory / "memory.swap.current")
        events = _read_memory_events(self.directory)
        self.sampled_max_current = max(self.sampled_max_current, current)
        rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        if (
            memory_max != self.memory_max
            or memory_high != self.memory_high
            or swap_max != self.swap_max
        ):
            raise ResourceIndeterminate(
                "cgroup memory max/high/swap limit changed during replay"
            )
        if peak > CGROUP_PEAK_MAX_BYTES:
            raise ResourceIndeterminate("cgroup memory peak cap exceeded")
        if rss_bytes > PROCESS_RSS_MAX_BYTES:
            raise ResourceIndeterminate("process peak RSS cap exceeded")
        if swap != 0:
            raise ResourceIndeterminate("swap usage observed")
        if any(
            events[name] != self.initial_events[name]
            for name in ("max", "oom", "oom_kill", "oom_group_kill")
        ):
            raise ResourceIndeterminate("cgroup memory-limit/OOM event observed")

    def record(
        self,
        started_ns: int,
        phase_elapsed_ns: Mapping[str, int],
        output_filesystem_type: str,
        output_st_dev: int,
        output_free_bytes_before: int,
    ) -> dict[str, Any]:
        self.check()
        events = _read_memory_events(self.directory)
        event_delta = {
            name: events[name] - self.initial_events[name] for name in self.initial_events
        }
        elapsed_ns = time.monotonic_ns() - started_ns
        usage = resource.getrusage(resource.RUSAGE_SELF)
        peak = _read_cgroup_number(self.directory / "memory.peak")
        current = _read_cgroup_number(self.directory / "memory.current")
        swap = _read_cgroup_number(self.directory / "memory.swap.current")
        if any(event_delta[name] != 0 for name in ("max", "oom", "oom_kill", "oom_group_kill")):
            raise ResourceIndeterminate("cgroup memory-limit/OOM event observed")
        if elapsed_ns <= 0 or elapsed_ns > INTERNAL_DEADLINE_SECONDS * 1_000_000_000:
            raise DeadlineExceeded("internal deadline exceeded")
        return {
            "cgroup_v2_enforced": True,
            "cgroup_path": str(self.directory),
            "observation_scope": "after_checkpoint_staged_and_rehashed_before_result_serialization_and_bundle_publication",
            "memory_max_bytes": self.memory_max,
            "memory_high_bytes": self.memory_high,
            "memory_swap_max_bytes": self.swap_max,
            "memory_peak_at_snapshot_bytes": peak,
            "initial_memory_peak_bytes": self.initial_peak,
            "sampled_max_memory_current_at_snapshot_bytes": self.sampled_max_current,
            "memory_current_at_snapshot_bytes": current,
            "swap_current_at_snapshot_bytes": swap,
            "memory_events_before": dict(self.initial_events),
            "memory_events_at_snapshot": events,
            "memory_events_delta_to_snapshot": event_delta,
            "process_max_rss_kib_at_snapshot": usage.ru_maxrss,
            "process_max_rss_bytes_at_snapshot": usage.ru_maxrss * 1024,
            "elapsed_to_snapshot_ns": elapsed_ns,
            "user_cpu_to_snapshot_ns": int(usage.ru_utime * 1_000_000_000),
            "system_cpu_to_snapshot_ns": int(usage.ru_stime * 1_000_000_000),
            "phase_elapsed_ns": dict(phase_elapsed_ns),
            "internal_deadline_seconds": INTERNAL_DEADLINE_SECONDS,
            "required_outer_deadline_seconds": OUTER_DEADLINE_SECONDS,
            "worker_count": 1,
            "io_chunk_bytes": 1_048_576,
            "application_payload_bytes_written": 0,
            "created_regular_files": 2,
            "created_directories": 1,
            "output_filesystem_type": output_filesystem_type,
            "output_st_dev": output_st_dev,
            "output_free_bytes_before": output_free_bytes_before,
            "open_file_descriptor_limit": OPEN_FILE_DESCRIPTOR_LIMIT,
            "file_size_limit_bytes": FILE_SIZE_LIMIT_BYTES,
            "checkpoint_file_fsync_completed": True,
            "staging_directory_fsync_completed": True,
            "staged_checkpoint_rehash_completed": True,
            "within_frozen_caps": True,
        }

    def terminal_receipt(self, started_ns: int) -> dict[str, Any]:
        self.check()
        events = _read_memory_events(self.directory)
        peak = _read_cgroup_number(self.directory / "memory.peak")
        current = _read_cgroup_number(self.directory / "memory.current")
        swap = _read_cgroup_number(self.directory / "memory.swap.current")
        usage = resource.getrusage(resource.RUSAGE_SELF)
        elapsed_ns = time.monotonic_ns() - started_ns
        if (
            peak > CGROUP_PEAK_MAX_BYTES
            or swap != 0
            or usage.ru_maxrss * 1024 > PROCESS_RSS_MAX_BYTES
            or any(
                events[name] != self.initial_events[name]
                for name in ("max", "oom", "oom_kill", "oom_group_kill")
            )
        ):
            raise ResourceIndeterminate("terminal resource receipt exceeded frozen caps")
        if elapsed_ns <= 0 or elapsed_ns > INTERNAL_DEADLINE_SECONDS * 1_000_000_000:
            raise DeadlineExceeded("internal deadline exceeded at publication receipt")
        return {
            "observation_scope": "after_single_bundle_publish_parent_fsync_and_post_publish_rehash",
            "memory_max_bytes": self.memory_max,
            "memory_high_bytes": self.memory_high,
            "memory_swap_max_bytes": self.swap_max,
            "memory_peak_bytes": peak,
            "memory_current_bytes": current,
            "swap_current_bytes": swap,
            "memory_events_at_receipt": events,
            "memory_events_delta_from_start": {
                name: events[name] - self.initial_events[name]
                for name in self.initial_events
            },
            "process_max_rss_kib": usage.ru_maxrss,
            "process_max_rss_bytes": usage.ru_maxrss * 1024,
            "elapsed_monotonic_ns": elapsed_ns,
            "user_cpu_ns": int(usage.ru_utime * 1_000_000_000),
            "system_cpu_ns": int(usage.ru_stime * 1_000_000_000),
            "required_outer_deadline_seconds": OUTER_DEADLINE_SECONDS,
            "single_bundle_renameat2_noreplace_completed": True,
            "parent_directory_fsync_completed": True,
            "checkpoint_post_publish_rehash_completed": True,
            "result_post_publish_rehash_completed": True,
            "within_frozen_caps": True,
        }


class ActionGuard:
    """Expose exactly q0->q1, q1->q2, and q2->q3 full actions."""

    def __init__(
        self,
        action: Callable[[Any, Any, Mapping[str, Any], Mapping[int, int], int], dict[int, int]],
        backend: Any,
        bonds: Mapping[str, Any],
    ) -> None:
        self._action = action
        self._backend = backend
        self._bonds = bonds
        self.underlying_source_depths: list[int] = []
        self.rejected_source_depths: list[int] = []

    def apply(self, source_depth: int, vector: Mapping[int, int]) -> dict[int, int]:
        expected = len(self.underlying_source_depths)
        if source_depth != expected or source_depth not in (0, 1, 2):
            self.rejected_source_depths.append(source_depth)
            raise ActionBoundaryError(
                "Hamiltonian action rejected before the pinned implementation"
            )
        self.underlying_source_depths.append(source_depth)
        try:
            return self._action(
                self._backend,
                self._bonds,
                vector,
                MAX_MATERIALIZED_STATES,
            )
        except (DeadlineExceeded, ResourceIndeterminate, MemoryError):
            raise
        except Exception as exc:
            if "ResourceNoGo" in {cls.__name__ for cls in type(exc).__mro__}:
                raise ResourceIndeterminate(
                    f"depth-{source_depth} Hamiltonian action hit its resource gate"
                ) from exc
            raise ScientificReplayError(
                f"depth-{source_depth} Hamiltonian action failed"
            ) from exc

    def prove_fourth_rejected(self) -> bool:
        before = list(self.underlying_source_depths)
        try:
            self.apply(3, {})
        except ActionBoundaryError:
            pass
        else:
            raise RunnerError("fourth action was not rejected")
        if self.underlying_source_depths != before or self.rejected_source_depths != [3]:
            raise RunnerError("fourth-action guard accounting drift")
        return True


def _check_particle_sector(representative: int) -> None:
    up = (representative & int("55" * 16, 16)).bit_count()
    down = ((representative >> 1) & int("55" * 16, 16)).bit_count()
    if up != 32 or down != 32:
        raise ScientificReplayError(
            "packed representative left the N_up=N_down=32 sector"
        )


def _byte_table_proof(
    d5a: types.ModuleType,
    d6: types.ModuleType,
    d5b: types.ModuleType,
    symmetries: list[dict[str, Any]],
) -> tuple[list[list[list[int]]], dict[str, Any]]:
    d5a_permutations = d5a._build_perms()
    if tuple(name for name, _ in d5a_permutations) != D5A_GROUP_ORDER:
        raise ScientificReplayError("D5A group order drift")
    if tuple(item["name"] for item in symmetries) != GROUP_ORDER:
        raise ScientificReplayError("D5B group order drift")
    tables = d6._tables(d5a_permutations)
    if len(tables) != 8 or any(len(chunks) != 16 for chunks in tables):
        raise ScientificReplayError("D6 byte-table shape drift")
    digest = hashlib.sha256()
    direct_checks = 0
    zero_checks = 0
    disjoint_or_checks = 0
    for group_index, symmetry in enumerate(symmetries):
        permutation = tuple(symmetry["mode_permutation"])
        if len(permutation) != 128 or set(permutation) != set(range(128)):
            raise ScientificReplayError("D5B mode permutation is not bijective")
        d5a_permutation = tuple(d5a_permutations[group_index][1])
        if d5a_permutation != permutation:
            raise ScientificReplayError("D5A/D5B mode permutation disagreement")
        for chunk in range(16):
            table = tables[group_index][chunk]
            if len(table) != 256:
                raise ScientificReplayError("D6 byte-table cell family drift")
            for value in range(256):
                source = value << (8 * chunk)
                expected, _ = d5b._generic_mode_action(source, permutation)
                observed = table[value]
                disjoint_or = 0
                for bit in range(8):
                    if (value >> bit) & 1:
                        image = 1 << permutation[8 * chunk + bit]
                        if disjoint_or & image:
                            raise ScientificReplayError("D5B byte images overlap")
                        disjoint_or |= image
                if observed != expected or observed != disjoint_or:
                    raise ScientificReplayError(
                        "D6 byte-table entry differs from D5B direct action"
                    )
                if value == 0:
                    if observed != 0:
                        raise ScientificReplayError("D6 byte-table zero entry drift")
                    zero_checks += 1
                digest.update(observed.to_bytes(16, "big", signed=False))
                direct_checks += 1
                disjoint_or_checks += 1
    one_hot_checks = 0
    pairwise_checks = 0
    bijective_checks = 0
    for group_index, (_, permutation_list) in enumerate(d5a_permutations):
        targets: list[int] = []
        union = 0
        for mode in range(128):
            observed = tables[group_index][mode // 8][1 << (mode % 8)]
            if observed.bit_count() != 1 or observed != 1 << permutation_list[mode]:
                raise ScientificReplayError("byte-table one-hot mode image drift")
            if union & observed:
                raise ScientificReplayError("byte-table mode images overlap")
            union |= observed
            targets.append(observed.bit_length() - 1)
            one_hot_checks += 1
        if union != MASK128:
            raise ScientificReplayError("byte-table mode images are not exhaustive")
        pairwise_checks += 1
        if sorted(targets) != list(range(128)):
            raise ScientificReplayError("byte-table group action is not bijective")
        bijective_checks += 1
    if (
        direct_checks != 32_768
        or zero_checks != 128
        or one_hot_checks != 1_024
        or disjoint_or_checks != 32_768
        or pairwise_checks != 8
        or bijective_checks != 8
    ):
        raise ScientificReplayError("byte-table definition coverage drift")
    return tables, {
        "group_elements": 8,
        "group_order": list(GROUP_ORDER),
        "source_byte_chunks": 16,
        "byte_values_per_chunk": 256,
        "definition_entries": 32_768,
        "direct_reference_checks": direct_checks,
        "zero_entry_checks": zero_checks,
        "one_hot_mode_image_checks": one_hot_checks,
        "disjoint_or_checks": disjoint_or_checks,
        "pairwise_disjoint_group_checks": pairwise_checks,
        "bijective_group_checks": bijective_checks,
        "table_bytes_hashed": direct_checks * 16,
        "table_sha256": digest.hexdigest(),
        "all_entries_equal_direct_reference": True,
        "phase_checks": 0,
        "phase_or_amplitude_authority": False,
    }


def _fast_support_image(value: int, chunks: list[list[int]]) -> int:
    target = 0
    for chunk in range(16):
        target |= chunks[chunk][(value >> (8 * chunk)) & 0xFF]
    return target


def _legacy_digest_update(
    digest: "hashlib._Hash", index: int, representative: int, amplitude: int, orbit_size: int
) -> None:
    if index:
        digest.update(b",")
    digest.update(
        json.dumps(
            [hex(representative), str(amplitude), orbit_size], separators=(",", ":")
        ).encode("ascii")
    )


def _support_digest_update(
    digest: "hashlib._Hash", index: int, representative: int, orbit_size: int
) -> None:
    if index:
        digest.update(b",")
    digest.update(
        json.dumps(
            [hex(representative), str(orbit_size)], separators=(",", ":")
        ).encode("ascii")
    )


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    written = 0
    while written < len(view):
        count = os.write(fd, view[written : written + MAX_IO_CHUNK_BYTES])
        if count <= 0:
            raise ResourceIndeterminate("short output write")
        written += count


def _hash_fd(fd: int) -> str:
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while True:
        chunk = os.read(fd, 1_048_576)
        if not chunk:
            break
        digest.update(chunk)
    os.lseek(fd, 0, os.SEEK_SET)
    return digest.hexdigest()


def _rename_noreplace(directory_fd: int, source: str, target: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise ResourceIndeterminate("renameat2(RENAME_NOREPLACE) is required")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        directory_fd,
        os.fsencode(source),
        directory_fd,
        os.fsencode(target),
        1,
    )
    if result != 0:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise ResourceIndeterminate(f"refusing to overwrite output: {target}")
        raise OSError(code, os.strerror(code), target)


def _assert_output_absent(directory_fd: int, name: str) -> None:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise ResourceIndeterminate(f"stale or concurrent output exists: {name}")


def _safe_unlink_owned(directory_fd: int, name: str, identity: tuple[int, int] | None) -> None:
    if identity is None:
        return
    try:
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if (current.st_dev, current.st_ino) != identity:
        raise RunnerError(f"refusing to remove replaced output: {name}")
    os.unlink(name, dir_fd=directory_fd)


def _open_exclusive_file(directory_fd: int, name: str) -> tuple[int, tuple[int, int]]:
    fd = os.open(
        name,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory_fd,
    )
    try:
        identity = os.fstat(fd)
        if not stat.S_ISREG(identity.st_mode):
            raise RunnerError(f"new output is not regular: {name}")
        return fd, (identity.st_dev, identity.st_ino)
    except BaseException:
        os.close(fd)
        try:
            os.unlink(name, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        raise


def _create_staging_bundle(parent_fd: int) -> tuple[str, int, tuple[int, int]]:
    name = STAGING_NAME
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
    except FileExistsError as exc:
        raise ResourceIndeterminate("concurrent D11 staging claim exists") from exc
    try:
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    except BaseException:
        os.rmdir(name, dir_fd=parent_fd)
        raise
    try:
        identity = os.fstat(fd)
        if not stat.S_ISDIR(identity.st_mode):
            raise RunnerError("staging bundle is not a directory")
        return name, fd, (identity.st_dev, identity.st_ino)
    except BaseException:
        os.close(fd)
        os.rmdir(name, dir_fd=parent_fd)
        raise


def _open_owned_bundle(
    parent_fd: int, name: str, expected_identity: tuple[int, int]
) -> int:
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    identity = os.fstat(fd)
    if (
        not stat.S_ISDIR(identity.st_mode)
        or (identity.st_dev, identity.st_ino) != expected_identity
    ):
        os.close(fd)
        raise RunnerError(f"bundle identity drift: {name}")
    return fd


def _remove_owned_bundle(
    parent_fd: int,
    name: str,
    directory_identity: tuple[int, int] | None,
    file_identities: Mapping[str, tuple[int, int] | None],
) -> None:
    if directory_identity is None:
        return
    try:
        directory_fd = _open_owned_bundle(parent_fd, name, directory_identity)
    except FileNotFoundError:
        return
    try:
        entries = set(os.listdir(directory_fd))
        if not entries.issubset(file_identities):
            raise RunnerError(f"refusing to remove bundle with unexpected entries: {name}")
        for entry in entries:
            identity = file_identities[entry]
            if identity is None:
                raise RunnerError(f"refusing to remove unowned bundle entry: {entry}")
            _safe_unlink_owned(directory_fd, entry, identity)
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if (current.st_dev, current.st_ino) != directory_identity:
        raise RunnerError(f"refusing to remove replaced bundle: {name}")
    os.rmdir(name, dir_fd=parent_fd)


def _post_publish_hash(directory_fd: int, name: str, expected_size: int, expected_sha: str) -> tuple[int, int]:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    try:
        identity = os.fstat(fd)
        if not stat.S_ISREG(identity.st_mode) or identity.st_size != expected_size:
            raise ResourceIndeterminate(f"published output identity drift: {name}")
        if _hash_fd(fd) != expected_sha:
            raise ResourceIndeterminate(f"published output hash drift: {name}")
        return identity.st_dev, identity.st_ino
    finally:
        os.close(fd)


def _deadline_handler(_signum: int, _frame: Any) -> None:
    raise DeadlineExceeded("internal deadline exceeded")


def _build_scientific_payload(
    contract: Mapping[str, Any],
    envelope: ResourceEnvelope,
    started_ns: int,
) -> tuple[bytes, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, int]]:
    phase_elapsed_ns: dict[str, int] = {}
    phase_started_ns = time.monotonic_ns()
    loaded, parsed = _load_pinned_sources()
    d5b = _module_from_bytes(
        "pinned_fh_l8_d5b_science_for_d11",
        HERE / "fh_l8_symmetry_orbit_quotient_d5_checker.py",
        loaded["fh_l8_symmetry_orbit_quotient_d5_checker.py"],
    )
    d6 = _module_from_bytes(
        "pinned_fh_l8_d6_table_for_d11",
        HERE / "fh_l8_byte_table_orbit_d6_checker.py",
        loaded["fh_l8_byte_table_orbit_d6_checker.py"],
    )
    d5a = _module_from_bytes(
        "pinned_fh_l8_d5a_support_for_d11",
        HERE / "fh_l8_signed_d4_orbit_d5_checker.py",
        loaded["fh_l8_signed_d4_orbit_d5_checker.py"],
    )
    d5b_contract = parsed["fh_l8_symmetry_orbit_quotient_d5_contract.json"]
    d5b_result = parsed["fh_l8_symmetry_orbit_quotient_d5_result.json"]
    d6_result = parsed["fh_l8_byte_table_orbit_d6_result.json"]
    depth3_expected = d5b_result["krylov_prefix"]["depth_records"][3]
    if (
        depth3_expected["full_state_count"] != EXPECTED_COUNTS[3]
        or depth3_expected["orbit_representative_count"] != RECORD_COUNT
        or depth3_expected["full_vector_sha256"] != EXPECTED_FULL_DIGESTS[3]
        or depth3_expected["deterministic_insertion_order_quotient_sha256"]
        != EXPECTED_INSERTION_DIGEST
        or depth3_expected["orbit_size_histogram"] != EXPECTED_ORBIT_HISTOGRAM
        or d6_result.get("depth3_orbit", {}).get("digest") != EXPECTED_SUPPORT_DIGEST
    ):
        raise RunnerError("pinned q3 committed evidence drift")

    d4, d4_contract, _ = d5b._verify_parent_sources(d5b_contract)
    d3 = d4._load_d3(d4_contract)
    d3_contract = d5b._load_json(HERE / "fh_l8_degree6_streaming_d3_contract.json")
    d2 = d3._load_d2(d3_contract)
    d2_contract = d5b._load_json(HERE / "fh_l8_two_step_scalar_defect_d2_contract.json")
    upstream = d2._load_upstream(d2_contract)
    backend = upstream._load_backend()
    bonds = {name: backend._hopping_bonds(8, name) for name in ("H1", "H2", "H3", "H4")}
    neel = upstream._neel_basis(8)
    if hex(neel) != d5b_contract["workload"]["neel_basis_hex"]:
        raise ScientificReplayError("Neel source drift")
    d5b._ACTIVE_DEADLINE = started_ns / 1_000_000_000 + INTERNAL_DEADLINE_SECONDS
    symmetries, _ = d5b._build_symmetries(d5b_contract)
    tables, table_record = _byte_table_proof(d5a, d6, d5b, symmetries)
    envelope.check()
    phase_elapsed_ns["source_and_table_validation"] = (
        time.monotonic_ns() - phase_started_ns
    )

    phase_started_ns = time.monotonic_ns()
    guard = ActionGuard(d4._sector_action, backend, bonds)
    vector: dict[int, int] = {neel: 1}
    depth_records: list[dict[str, Any]] = []
    for depth in range(4):
        if len(vector) != EXPECTED_COUNTS[depth]:
            raise ScientificReplayError(f"depth-{depth} state count drift")
        digest = d5b._vector_digest_streaming(vector)
        if digest != EXPECTED_FULL_DIGESTS[depth]:
            raise ScientificReplayError(f"depth-{depth} full-vector digest drift")
        depth_records.append(
            {"depth": depth, "full_state_count": len(vector), "full_vector_sha256": digest}
        )
        envelope.check()
        if depth < 3:
            vector = guard.apply(depth, vector)
    if guard.underlying_source_depths != [0, 1, 2] or not guard.prove_fourth_rejected():
        raise RunnerError("Hamiltonian action boundary drift")
    if len(vector) != EXPECTED_COUNTS[3]:
        raise ScientificReplayError("q3 state count drift after action guard")
    phase_elapsed_ns["depth0_to_depth3_replay"] = (
        time.monotonic_ns() - phase_started_ns
    )

    phase_started_ns = time.monotonic_ns()
    try:
        audit, quotient = d5b._audit_vector(
            vector, symmetries, materialize_quotient=True
        )
    except (DeadlineExceeded, ResourceIndeterminate, MemoryError):
        raise
    except Exception as exc:
        if "ResourceNoGo" in {cls.__name__ for cls in type(exc).__mro__}:
            raise ResourceIndeterminate("D5B q3 audit hit its resource gate") from exc
        raise ScientificReplayError("D5B q3 quotient audit failed") from exc
    if quotient is None:
        raise ScientificReplayError("D5B q3 quotient was not materialized")
    expected_audit = {
        "full_state_count": EXPECTED_COUNTS[3],
        "orbit_representative_count": RECORD_COUNT,
        "compression_ratio": "1704285/213099",
        "orbit_size_histogram": EXPECTED_ORBIT_HISTOGRAM,
        "stabilizer_size_histogram": EXPECTED_STABILIZER_HISTOGRAM,
        "coverage_sum": EXPECTED_COUNTS[3],
        "amplitude_relation_checks": 13_634_280,
        "projected_zero_nonzero_states": 0,
        "deterministic_insertion_order_quotient_sha256": EXPECTED_INSERTION_DIGEST,
    }
    if audit != expected_audit or len(quotient) != RECORD_COUNT:
        raise ScientificReplayError("D5B q3 quotient audit drift")
    del vector
    gc.collect()
    envelope.check()

    legacy_digest = hashlib.sha256(b"[")
    positive = 0
    negative = 0
    amplitude_sum = 0
    maximum_abs = 0
    orbit_histogram: dict[str, int] = {}
    stabilizer_histogram: dict[str, int] = {}
    orbit_coverage_sum = 0
    particle_sector_checks = 0
    signed_canonicality_checks = 0
    d6_nomination_checks = 0
    signed_group_images = 0
    support_group_images = 0
    for rank, representative in enumerate(quotient):
        amplitude = quotient[representative]
        if not isinstance(amplitude, int) or isinstance(amplitude, bool):
            raise ScientificReplayError("q3 amplitude is not an integer")
        if amplitude == 0 or abs(amplitude) > MAX_ABS_AMPLITUDE:
            raise ScientificReplayError("q3 amplitude violates packed bound")
        _check_particle_sector(representative)
        particle_sector_checks += 1
        signed = d5b._canonical_info(representative, symmetries)
        signed_group_images += 8
        if (
            signed["representative"] != representative
            or signed["projected_zero"] is not False
            or signed["orbit_size"] not in (1, 4, 8)
        ):
            raise ScientificReplayError(
                "q3 representative is not signed-canonical/admissible"
            )
        signed_canonicality_checks += 1
        support_images = {
            _fast_support_image(representative, group_tables) for group_tables in tables
        }
        support_group_images += 8
        orbit_size = signed["orbit_size"]
        if min(support_images) != representative or len(support_images) != orbit_size:
            raise ScientificReplayError(
                "D6 support nomination/orbit differs from D5B"
            )
        d6_nomination_checks += 1
        _legacy_digest_update(legacy_digest, rank, representative, amplitude, orbit_size)
        quotient[representative] = (amplitude, orbit_size, rank)
        orbit_histogram[str(orbit_size)] = orbit_histogram.get(str(orbit_size), 0) + 1
        stabilizer = str(8 // orbit_size)
        stabilizer_histogram[stabilizer] = stabilizer_histogram.get(stabilizer, 0) + 1
        orbit_coverage_sum += orbit_size
        positive += amplitude > 0
        negative += amplitude < 0
        amplitude_sum += amplitude
        maximum_abs = max(maximum_abs, abs(amplitude))
        if not (rank & 0xFFF):
            envelope.check()
    legacy_digest.update(b"]")
    if legacy_digest.hexdigest() != EXPECTED_INSERTION_DIGEST:
        raise ScientificReplayError("independent D5B insertion digest drift")
    if (
        orbit_histogram != EXPECTED_ORBIT_HISTOGRAM
        or stabilizer_histogram != EXPECTED_STABILIZER_HISTOGRAM
        or orbit_coverage_sum != EXPECTED_COUNTS[3]
        or particle_sector_checks != RECORD_COUNT
        or signed_canonicality_checks != RECORD_COUNT
        or d6_nomination_checks != RECORD_COUNT
        or signed_group_images != RECORD_COUNT * 8
        or support_group_images != RECORD_COUNT * 8
        or audit["amplitude_relation_checks"] + signed_group_images > 16_000_000
    ):
        raise ScientificReplayError("q3 quotient qualification coverage drift")
    phase_elapsed_ns["q3_orbit_audit"] = time.monotonic_ns() - phase_started_ns

    phase_started_ns = time.monotonic_ns()
    sorted_representatives = sorted(quotient)
    if len(sorted_representatives) != RECORD_COUNT:
        raise ScientificReplayError("sorted q3 representative count drift")
    checkpoint = bytearray()
    packed_digest = hashlib.sha256()
    semantic_digest = hashlib.sha256(b"[")
    support_digest = hashlib.sha256(b"[")
    previous = -1
    seen_rank = bytearray((RECORD_COUNT + 7) // 8)
    for index, representative in enumerate(sorted_representatives):
        amplitude, orbit_size, rank = quotient[representative]
        if representative <= previous or not 0 <= rank < RECORD_COUNT:
            raise ScientificReplayError("packed sort/rank boundary drift")
        byte_index, bit_index = divmod(rank, 8)
        bit = 1 << bit_index
        if seen_rank[byte_index] & bit:
            raise ScientificReplayError("duplicate D5B insertion rank")
        seen_rank[byte_index] |= bit
        record = RECORD.pack(
            representative.to_bytes(16, "big", signed=False),
            amplitude,
            orbit_size,
            0,
            0,
            rank,
        )
        checkpoint.extend(record)
        packed_digest.update(record)
        if index:
            semantic_digest.update(b",")
        semantic_digest.update(
            json.dumps(
                [hex(representative), str(amplitude), orbit_size, rank],
                separators=(",", ":"),
            ).encode("ascii")
        )
        _support_digest_update(support_digest, index, representative, orbit_size)
        previous = representative
    semantic_digest.update(b"]")
    support_digest.update(b"]")
    if any(value != 0xFF for value in seen_rank[:-1]):
        raise ScientificReplayError("insertion rank permutation has gaps")
    final_rank_bits = RECORD_COUNT & 7
    expected_final = 0xFF if final_rank_bits == 0 else (1 << final_rank_bits) - 1
    if not seen_rank or seen_rank[-1] != expected_final:
        raise ScientificReplayError("insertion rank tail mask drift")
    if support_digest.hexdigest() != EXPECTED_SUPPORT_DIGEST:
        raise ScientificReplayError("packed support-orbit digest drift")
    if len(checkpoint) != CHECKPOINT_BYTES:
        raise ScientificReplayError("packed checkpoint byte count drift")
    checkpoint_record = {
        "path": CHECKPOINT_RELATIVE_PATH,
        "format_id": FORMAT_ID,
        "encoding": "u128be_rep+i64be_amplitude+u8_orbit+u8_zero_flags+u16_zero_reserved+u32be_d5b_rank",
        "record_bytes": RECORD_BYTES,
        "record_count": RECORD_COUNT,
        "file_bytes": CHECKPOINT_BYTES,
        "packed_sorted_binary_sha256": packed_digest.hexdigest(),
        "sorted_semantic_sha256": semantic_digest.hexdigest(),
        "legacy_d5b_insertion_json_sha256": EXPECTED_INSERTION_DIGEST,
        "d6_sorted_support_orbit_sha256": EXPECTED_SUPPORT_DIGEST,
        "strictly_ascending_representatives": True,
        "unique_representatives": True,
        "insertion_ranks_complete_permutation": True,
        "flags_nonzero": 0,
        "reserved_nonzero": 0,
        "particle_sector_checks": particle_sector_checks,
        "d5b_signed_canonicality_checks": signed_canonicality_checks,
        "d6_support_nomination_checks": d6_nomination_checks,
        "zero_amplitudes": 0,
        "positive_amplitudes": positive,
        "negative_amplitudes": negative,
        "amplitude_sum": str(amplitude_sum),
        "maximum_absolute_amplitude_observed": maximum_abs,
        "orbit_size_histogram": orbit_histogram,
        "stabilizer_size_histogram": stabilizer_histogram,
        "orbit_coverage_sum": orbit_coverage_sum,
        "first_representative_hex": hex(sorted_representatives[0]),
        "last_representative_hex": hex(sorted_representatives[-1]),
    }
    depth_replay = {
        "depth_records": depth_records,
        "q3_audit": audit,
        "hamiltonian_action_call_budget": 3,
        "hamiltonian_actions_executed": 3,
        "acted_source_depths": [0, 1, 2],
        "maximum_acted_source_depth": 2,
        "depth3_source_rows_visited": 0,
        "q4_records_emitted": 0,
        "fourth_call_rejected_before_backend": True,
        "underlying_action_calls_after_rejection": 3,
        "forbidden_quotient_helpers_invoked": 0,
    }
    del sorted_representatives, quotient
    gc.collect()
    envelope.check()
    phase_elapsed_ns["packing_and_staging"] = time.monotonic_ns() - phase_started_ns
    return bytes(checkpoint), depth_replay, checkpoint_record, table_record, phase_elapsed_ns


def _source_evidence_record() -> dict[str, Any]:
    return {
        "d7_design_gate_verified": True,
        "d8_protocol_only_verified": True,
        "d8_checkpoint_materialized": False,
        "d9_bounded_preflight_record_verified": True,
        "d9_bounded_preflight_executed": True,
        "d9_memory_envelope_pass": False,
        "d10_one_gib_zero_swap_preflight_verified": True,
        "d10_memory_envelope_pass": True,
        "d10_full_run_authorized": False,
        "d5b_route_alias": "FH-L8-D5-EVIDENCE-SYMMETRY-ORBIT-QUOTIENT-V1",
        "d6_route_alias": "FH-L8-D6-EVIDENCE-BYTE-TABLE-SUPPORT-ORBIT-V1",
        "d5a_route_alias": "FH-L8-D5A-EVIDENCE-DIRECT-SIGNED-D4-SUPPORT-V1",
        "depth3_full_states": EXPECTED_COUNTS[3],
        "depth3_representatives": RECORD_COUNT,
        "legacy_d5b_insertion_json_sha256": EXPECTED_INSERTION_DIGEST,
        "d6_sorted_support_orbit_sha256": EXPECTED_SUPPORT_DIGEST,
        "evidence_is_additive": False,
    }


def run(contract_commit: str) -> dict[str, Any]:
    parent_fd = os.open(HERE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    staging_name: str | None = None
    staging_fd: int | None = None
    result_fd: int | None = None
    bundle_identity: tuple[int, int] | None = None
    checkpoint_identity: tuple[int, int] | None = None
    result_identity: tuple[int, int] | None = None
    previous_nofile = resource.getrlimit(resource.RLIMIT_NOFILE)
    previous_fsize = resource.getrlimit(resource.RLIMIT_FSIZE)
    nofile_changed = False
    fsize_changed = False
    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.setitimer(signal.ITIMER_REAL, 0)
    try:
        _assert_output_absent(parent_fd, BUNDLE_NAME)
        _assert_output_absent(parent_fd, TERMINAL_RECEIPT_NAME)
        _assert_output_absent(parent_fd, TERMINAL_RECEIPT_STAGING_NAME)
        leftovers = sorted(
            name for name in os.listdir(parent_fd) if name.startswith(STAGING_PREFIX)
        )
        if leftovers:
            raise ResourceIndeterminate("stale or concurrent D11 staging claim exists")
        worktree_status = _git("status", "--porcelain=v1").strip()
        if worktree_status:
            raise RunnerError("official replay requires a clean worktree")
        staging_name, staging_fd, bundle_identity = _create_staging_bundle(parent_fd)
        _set_soft_resource_limit(
            resource.RLIMIT_NOFILE, OPEN_FILE_DESCRIPTOR_LIMIT, "open-file-descriptor"
        )
        nofile_changed = True
        _set_soft_resource_limit(
            resource.RLIMIT_FSIZE, FILE_SIZE_LIMIT_BYTES, "file-size"
        )
        fsize_changed = True
        filesystem = os.fstatvfs(parent_fd)
        output_free_bytes_before = filesystem.f_bavail * filesystem.f_frsize
        output_filesystem_type = _output_filesystem_type(HERE)
        output_st_dev = os.fstat(parent_fd).st_dev
        if output_free_bytes_before < MINIMUM_OUTPUT_FREE_BYTES:
            raise ResourceIndeterminate("insufficient output free space")
        if output_st_dev <= 0:
            raise RunnerError("invalid output filesystem device identity")
        if len(os.listdir("/proc/self/fd")) > OPEN_FILE_DESCRIPTOR_LIMIT:
            raise ResourceIndeterminate(
                "open-file-descriptor cap exceeded before replay"
            )
        contract_raw = _read_regular_nofollow(CONTRACT, MAX_SOURCE_BYTES)
        contract = _load_json(contract_raw, CONTRACT_NAME)
        _validate_contract(contract)
        protocol = _verify_protocol(contract, contract_raw, contract_commit)
        envelope = ResourceEnvelope()
        started_ns = time.monotonic_ns()
        signal.signal(signal.SIGALRM, _deadline_handler)
        signal.setitimer(signal.ITIMER_REAL, INTERNAL_DEADLINE_SECONDS)

        (
            checkpoint_raw,
            depth_replay,
            checkpoint_record,
            table_record,
            phase_elapsed_ns,
        ) = _build_scientific_payload(contract, envelope, started_ns)

        staging_started_ns = time.monotonic_ns()
        checkpoint_fd, checkpoint_identity = _open_exclusive_file(
            staging_fd, CHECKPOINT_NAME
        )
        try:
            _write_all(checkpoint_fd, checkpoint_raw)
            os.fsync(checkpoint_fd)
            identity = os.fstat(checkpoint_fd)
            if (
                (identity.st_dev, identity.st_ino) != checkpoint_identity
                or identity.st_size != CHECKPOINT_BYTES
                or _hash_fd(checkpoint_fd)
                != checkpoint_record["packed_sorted_binary_sha256"]
            ):
                raise ResourceIndeterminate("checkpoint temporary file drift")
        finally:
            os.close(checkpoint_fd)
        del checkpoint_raw
        gc.collect()
        envelope.check()
        _post_publish_hash(
            staging_fd,
            CHECKPOINT_NAME,
            CHECKPOINT_BYTES,
            checkpoint_record["packed_sorted_binary_sha256"],
        )
        result_fd, result_identity = _open_exclusive_file(staging_fd, RESULT_NAME)
        os.fsync(staging_fd)
        phase_elapsed_ns["packing_and_staging"] += (
            time.monotonic_ns() - staging_started_ns
        )

        resource_record = envelope.record(
            started_ns,
            phase_elapsed_ns,
            output_filesystem_type,
            output_st_dev,
            output_free_bytes_before,
        )
        result = {
            "schema_version": 1,
            "contract_id": CONTRACT_ID,
            "status": STATUS,
            "verified": True,
            "protocol": protocol,
            "source_evidence": _source_evidence_record(),
            "byte_table_full_domain_validation": table_record,
            "depth_replay": depth_replay,
            "checkpoint": checkpoint_record,
            "resource_observations": resource_record,
            "authority": dict(AUTHORITY),
            "limitations": list(LIMITATIONS),
            "next_gate": "CHECKPOINTED_FULL_QUOTIENT_H_RUNNER_IMPLEMENTATION_AND_AUTHORIZATION",
        }
        result_raw = b""
        for _ in range(16):
            result_raw = _canonical_json(result) + b"\n"
            payload_bytes = CHECKPOINT_BYTES + len(result_raw)
            if resource_record["application_payload_bytes_written"] == payload_bytes:
                break
            resource_record["application_payload_bytes_written"] = payload_bytes
        else:
            raise RunnerError("result payload-size fixed point did not converge")
        if resource_record["application_payload_bytes_written"] != CHECKPOINT_BYTES + len(
            result_raw
        ):
            raise RunnerError("result payload-size fixed point drift")
        if len(result_raw) > MAX_RESULT_BYTES:
            raise ResourceIndeterminate("result exceeds frozen byte cap")
        result_sha = hashlib.sha256(result_raw).hexdigest()
        try:
            _write_all(result_fd, result_raw)
            os.fsync(result_fd)
            identity = os.fstat(result_fd)
            if (
                (identity.st_dev, identity.st_ino) != result_identity
                or identity.st_size != len(result_raw)
                or _hash_fd(result_fd) != result_sha
            ):
                raise ResourceIndeterminate("result temporary file drift")
        finally:
            os.close(result_fd)
            result_fd = None
        os.fsync(staging_fd)
        envelope.check()
        if len(os.listdir("/proc/self/fd")) > OPEN_FILE_DESCRIPTOR_LIMIT:
            raise ResourceIndeterminate(
                "open-file-descriptor cap exceeded before publication"
            )
        staged_directory_fd = staging_fd
        staging_fd = None
        os.close(staged_directory_fd)

        _rename_noreplace(parent_fd, staging_name, BUNDLE_NAME)
        os.fsync(parent_fd)
        final_fd = _open_owned_bundle(parent_fd, BUNDLE_NAME, bundle_identity)
        try:
            if set(os.listdir(final_fd)) != {CHECKPOINT_NAME, RESULT_NAME}:
                raise ResourceIndeterminate("published bundle content drift")
            published_checkpoint_identity = _post_publish_hash(
                final_fd,
                CHECKPOINT_NAME,
                CHECKPOINT_BYTES,
                checkpoint_record["packed_sorted_binary_sha256"],
            )
            published_result_identity = _post_publish_hash(
                final_fd, RESULT_NAME, len(result_raw), result_sha
            )
            if (
                published_checkpoint_identity != checkpoint_identity
                or published_result_identity != result_identity
            ):
                raise ResourceIndeterminate("published bundle file identity drift")
        finally:
            os.close(final_fd)
        terminal_resource_receipt = envelope.terminal_receipt(started_ns)
        elapsed_at_receipt_ns = terminal_resource_receipt["elapsed_monotonic_ns"]
        staging_name = None
        signal.setitimer(signal.ITIMER_REAL, 0)
        return {
            "schema_version": 1,
            "contract_id": CONTRACT_ID,
            "contract_freeze_commit": contract_commit,
            "protocol_source_freeze_commit": protocol[
                "protocol_source_freeze_commit"
            ],
            "status": STATUS,
            "verified": True,
            "bundle_path": BUNDLE_NAME,
            "single_bundle_renameat2_noreplace_completed": True,
            "parent_directory_fsync_completed": True,
            "checkpoint_post_publish_rehash_completed": True,
            "result_post_publish_rehash_completed": True,
            "terminal_resource_receipt": terminal_resource_receipt,
            "checkpoint_sha256": checkpoint_record["packed_sorted_binary_sha256"],
            "checkpoint_bytes": CHECKPOINT_BYTES,
            "result_sha256": result_sha,
            "result_bytes": len(result_raw),
            "elapsed_at_publication_receipt_ns": elapsed_at_receipt_ns,
            "depth3_to_depth4_execution_authorized": False,
            "depth3_to_depth4_action_executed": False,
            "next_gate": result["next_gate"],
        }
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if result_fd is not None:
            staged_result_fd = result_fd
            result_fd = None
            os.close(staged_result_fd)
        if staging_fd is not None:
            staged_directory_fd = staging_fd
            staging_fd = None
            os.close(staged_directory_fd)
        cleanup_errors: list[BaseException] = []
        identities = {
            CHECKPOINT_NAME: checkpoint_identity,
            RESULT_NAME: result_identity,
        }
        for candidate in (BUNDLE_NAME, staging_name):
            if candidate is None:
                continue
            try:
                _remove_owned_bundle(parent_fd, candidate, bundle_identity, identities)
            except BaseException as exc:
                cleanup_errors.append(exc)
        try:
            os.fsync(parent_fd)
        except BaseException as exc:
            cleanup_errors.append(exc)
        if cleanup_errors:
            cleanup_error = cleanup_errors[0]
            raise ResourceIndeterminate(
                f"output cleanup failed: {cleanup_error}"
            ) from cleanup_error
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        signal.setitimer(signal.ITIMER_REAL, *old_timer)
        if staging_fd is not None:
            os.close(staging_fd)
        if result_fd is not None:
            os.close(result_fd)
        if fsize_changed:
            resource.setrlimit(resource.RLIMIT_FSIZE, previous_fsize)
        if nofile_changed:
            resource.setrlimit(resource.RLIMIT_NOFILE, previous_nofile)
        os.close(parent_fd)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] != "--contract-commit":
        print(
            json.dumps(
                {
                    "status": "VERIFICATION_FAILED",
                    "verified": False,
                    "error": "usage: runner.py --contract-commit <full-commit>",
                },
                sort_keys=True,
            )
        )
        return 1
    try:
        evidence = run(args[1])
    except BaseException as exc:
        exception_class_names = {cls.__name__ for cls in type(exc).__mro__}
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
            isinstance(exc, (ResourceIndeterminate, MemoryError, KeyboardInterrupt))
            or "ResourceNoGo" in exception_class_names
            or isinstance(exc, OSError)
            and exc.errno in resource_errnos
        ):
            failure_status = INDETERMINATE_STATUS
        elif (
            isinstance(exc, ScientificReplayError)
            or "SemanticNoGo" in exception_class_names
        ):
            failure_status = NO_GO_STATUS
        else:
            failure_status = "VERIFICATION_FAILED"
        print(
            json.dumps(
                {
                    "status": failure_status,
                    "verified": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc) or type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
