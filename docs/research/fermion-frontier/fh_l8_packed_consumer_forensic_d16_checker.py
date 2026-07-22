#!/usr/bin/env python3
"""Fail-closed FH-L8 packed-q3 consumer and legacy full-action forensic gate.

This checker never imports a scientific implementation and has no Hamiltonian
action entrypoint.  It independently validates the committed packed q3 bytes,
Git chronology, retained receipts, and (only in explicit external-audit mode)
the custody of an already-existing legacy scratch tree.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import os
import re
import resource
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Mapping


HERE = Path(__file__).parent.absolute()
PREFIX = "docs/research/fermion-frontier"
CHECKER_NAME = "fh_l8_packed_consumer_forensic_d16_checker.py"
CONTRACT_NAME = "fh_l8_packed_consumer_forensic_d16_contract.json"
RESULT_NAME = "fh_l8_packed_consumer_forensic_d16_result.json"
CHECKER_PATH = f"{PREFIX}/{CHECKER_NAME}"
CONTRACT_PATH = f"{PREFIX}/{CONTRACT_NAME}"
RESULT_PATH = f"{PREFIX}/{RESULT_NAME}"
CONTRACT = HERE / CONTRACT_NAME
RESULT = HERE / RESULT_NAME

CONTRACT_ID = "FH-L8-INDEPENDENT-REFERENCE-D16-PACKED-Q3-CUSTODY-FORENSIC-V1"
PROTOCOL_STATUS = "PROTOCOL_FROZEN_BEFORE_D16_EXTERNAL_CUSTODY_FORENSIC_AUDIT"
STATUS = "NO_GO_D16_LEGACY_TARGET_CUSTODY_BROKEN_ASSOCIATED_SPOOL_DUPLICATED_TARGET_QUARANTINED"
NEXT_GATE = "FRESH_EXCLUSIVE_PACKED_Q3_CONSUMER_IMPLEMENTATION_AND_BOUNDED_4096_PREFLIGHT_AUTHORIZATION"

BASE_COMMIT = "e6cc31c6987cc33d7fbb8890cc172a7ba817cf56"
BASE_TREE = "dde3e732132c552ba903210c92eee9a43f14f422"
BASE_PARENTS = [
    "08dadb701eff0650a6437b582f73c45888bd0f30",
]

PACKED_C1 = "49ac8a25faf80c85fab9acaa7390fda7b4c0d7f2"
PACKED_C2 = "429f31d0b82284f07860b3eb460102816fae1e17"
PACKED_C3 = "784f01b8e3c589b7c6ab25773f93937d5a1344f8"
PACKED_CHECKPOINT_PATH = f"{PREFIX}/fh_l8_packed_q3_checkpoint_d11_bundle/checkpoint.bin"
PACKED_RESULT_PATH = f"{PREFIX}/fh_l8_packed_q3_checkpoint_d11_bundle/result.json"
PACKED_RECEIPT_PATH = f"{PREFIX}/fh_l8_packed_q3_checkpoint_d11_terminal_receipt.json"

PARALLEL_SOURCE_COMMIT = "190ed66cf80e91940757b9716adb35757005fe26"
PARALLEL_PREFLIGHT_COMMIT = "57697b23cd96a0412c07da813353f501f64cb157"
PARALLEL_FULL_COMMIT = "73d88bc0a9a783f82d8f308c3a4b9d26e92850c8"
PARALLEL_MERGE_COMMIT = "4c3e189f28a1b0c6d6063a318d405ce5338be2f7"
D12_COMMIT = "86df2475aaae2fba02a09fdab67a2ee9fe68d6ec"
D12_MERGE_COMMIT = "e515f06692052dcff6e67ce0a54d7612af030ce4"
D12_MERGE_TREE = "777a339bc3792630dda4162141b9cf1dc1e6d868"
D12_MERGE_PARENTS = [
    "70d1f069ff398e7f4bcc2aba999db51df0f07afd",
    D12_COMMIT,
]

DEFAULT_SOURCE_ROOT = Path("/Data/CascadeProjects/fh-l8-d11-source-checkpoint")
DEFAULT_RUN_ROOT = Path("/Data/CascadeProjects/fh-l8-d11-full-v1")

SHA40_RE = re.compile(r"[0-9a-f]{40}")
SHA64_RE = re.compile(r"[0-9a-f]{64}")
READ_CHUNK = 1_048_576
RECORD_BYTES = 32
SOURCE_RECORDS = 213_099
SOURCE_BYTES = SOURCE_RECORDS * RECORD_BYTES
SOURCE_SHARD_SIZE = 4_096
SOURCE_SHARDS = 53
PARTITIONS = 256
ZERO7 = b"\x00" * 7

EXPECTED_PACKED = {
    "record_bytes": 32,
    "record_count": 213099,
    "file_bytes": 6819168,
    "packed_sorted_binary_sha256": "db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231",
    "base_projection_sha256": "09758478e63d21014bdd704e157b1969498fdd4068b6ab4f78c2720324477017",
    "sorted_semantic_sha256": "56584a95835d7a0535d118bbcc50f3670ad71f54c6b0e61597f0004483bba619",
    "legacy_d5b_insertion_json_sha256": "7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e",
    "d6_sorted_support_orbit_sha256": "7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26",
    "positive_amplitudes": 106583,
    "negative_amplitudes": 106516,
    "zero_amplitudes": 0,
    "amplitude_sum": "-2385544",
    "maximum_absolute_amplitude_observed": 2181376,
    "maximum_absolute_amplitude_allowed": 43614208,
    "orbit_size_histogram": {"1": 1, "4": 125, "8": 212973},
    "stabilizer_size_histogram": {"1": 212973, "2": 125, "8": 1},
    "orbit_coverage_sum": 1704285,
    "first_representative_hex": "0x266fd99666699996666999966669999",
    "last_representative_hex": "0x6667999866669999c66699996664999b",
    "nonzero_insertion_ranks": 213098,
}
PACKED_SHARD_MANIFEST_SHA256 = (
    "c2b4586ed67c4e3b4fd029bc96c3004bfb313fd12e6330a5c24353bed9c60dfb"
)

EXPECTED_EXTERNAL = {
    "receipt_count": 53,
    "partition_count": 256,
    "record_bytes": 32,
    "certified_segment_count": 13568,
    "certified_records": 44685210,
    "certified_bytes": 1429926720,
    "spool_records": 67812180,
    "spool_bytes": 2169989760,
    "gap_count": 6912,
    "gap_records": 23126970,
    "gap_bytes": 740063040,
    "duplicate_gap_matches": 6912,
    "duplicate_shards": list(range(25, 52)),
    "duplicate_source_start": 102400,
    "duplicate_source_end_inclusive": 212991,
    "target_records": 10785545,
    "target_bytes": 345137440,
    "target_sha256": "9769bbcd39cb5d48a83f42e8a8fa838c7577f8ab4978876f0fc4fe582250587c",
    "source_checkpoint_sha256": "09758478e63d21014bdd704e157b1969498fdd4068b6ab4f78c2720324477017",
    "source_manifest_sha256": "b702bf2a9eedd5fd9a7ae876700c834d3589a4076a274ed7dce11c1f9a43c134",
}

EXPECTED_FORENSIC_DIGESTS = {
    "receipt_set_sha256": "ca321dafc4a0ded9916ce4f4734ca46ef030c8ffc465ea1563c22fdf07d21ef3",
    "partition_manifest_sha256": "0d977d772d4d94fae8089e4b2b3eaca3d243693b8c247dc3169a57318df2c3aa",
    "gap_inventory_sha256": "156a65043d0f8b8d32a65242fe74343092e789c41ed3f310a7bc8ee16c5f1b98",
    "manifest_sha256": "869008057db5eb93129aca801dce2dab458ec2cfc6f7fa2894bf04538cb4d79b",
}

EXPECTED_COSTS = {
    "q4_sources_reported": 10785545,
    "raw_candidate_upper_bound": 2426747625,
    "candidate_group_image_upper_bound": 19413981000,
    "source_group_image_upper_bound": 86284360,
    "total_group_image_upper_bound": 19500265360,
    "byte_table_lookup_upper_bound": 312004245760,
    "primary_spill_bytes_upper_bound": 77655924000,
}

PACKED_ARTIFACTS = [
    {
        "path": "fh_l8_packed_q3_checkpoint_d11_checker.py",
        "mode": "100644",
        "blob": "582e0f181692e80d1e608b27c3313b225b9adf4e",
        "bytes": 109796,
        "sha256": "d7b4f1853f99f80f1a1241d078049d254d414ec0a3f99906d7b0801fe764a74e",
    },
    {
        "path": "fh_l8_packed_q3_checkpoint_d11_runner.py",
        "mode": "100644",
        "blob": "abb2c5e87092d51671a9923b97ebeeda6d11a3ea",
        "bytes": 97061,
        "sha256": "4a6a138ae56b9e308ef22ebad667982e5cbf488dfed76a7914f5ab4d03bef0ba",
    },
    {
        "path": "fh_l8_packed_q3_checkpoint_d11_contract.json",
        "mode": "100644",
        "blob": "bdbeb3c1b588fb623ed563166fe3bec3621191ba",
        "bytes": 21439,
        "sha256": "a9171c10c3fb66408b97c45fd8f2b81d2b4a8f64855e197f0e178cccedd18b41",
    },
    {
        "path": "fh_l8_packed_q3_checkpoint_d11_bundle/checkpoint.bin",
        "mode": "100644",
        "blob": "c71a85fd8ad1787e007da4576dbbe29f1f189e82",
        "bytes": 6819168,
        "sha256": "db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231",
    },
    {
        "path": "fh_l8_packed_q3_checkpoint_d11_bundle/result.json",
        "mode": "100644",
        "blob": "998feae83f21e43401f9461af33c79e32d4f8b62",
        "bytes": 8608,
        "sha256": "f372a2eedabfc57d049d6a8c6d0609c1b7bcf25aae760353699916a6f1bc4bf5",
    },
    {
        "path": "fh_l8_packed_q3_checkpoint_d11_terminal_receipt.json",
        "mode": "100644",
        "blob": "c9841f461d6811a9da516253d3e1dc926e1a0133",
        "bytes": 2470,
        "sha256": "deafacbcbb77885353254306200137c7248321641b0eb197494d5cbd0d3a9ab2",
    },
]

PARALLEL_ARTIFACTS = [
    {
        "path": "fh_l8_checkpointed_quotient_h_d11_contract.json",
        "mode": "100644",
        "blob": "ccfcb8ff8c1342bb4b0960bc25ca1b482777bd9f",
        "bytes": 465,
        "sha256": "34d294d8dd9665209649c45d6bb93d953a5300485e4a7d6ea20b73602fc92702",
    },
    {
        "path": "fh_l8_checkpointed_quotient_h_d11_receipt.json",
        "mode": "100644",
        "blob": "65873bf0645e127e46999eeb467fcd66c9b07259",
        "bytes": 508,
        "sha256": "fe45f0a816da286fd92af1c2d0ea07269149105820f3a742cb583135cbda88fd",
    },
    {
        "path": "fh_l8_checkpointed_quotient_h_d11_runner.py",
        "mode": "100644",
        "blob": "60f72c0fae346d8589fbc3fae6b0301b4e9f3ec7",
        "bytes": 14028,
        "sha256": "0a9bede4677912676d2bf2542a1f1730c1d27eda3d41997fbcec2e756bc7de78",
    },
    {
        "path": "fh_l8_d11_merge4096_receipt.json",
        "mode": "100644",
        "blob": "d2c2a52cddee5900c49d8a492d305df226d6ffeb",
        "bytes": 310,
        "sha256": "bd46791abd9e95a93f0b67c2f417ef0c2bda5563df485de54395db0a56cdbe7b",
    },
    {
        "path": "fh_l8_d11_verify4096_receipt.json",
        "mode": "100644",
        "blob": "aac1c3fd45c9b074d28effa04c036b335e69f0f4",
        "bytes": 229,
        "sha256": "9546e0a55242608c576eaa5beb7a273162f074fc54be166b986c84cdf5c1c105",
    },
    {
        "path": "fh_l8_d11_full_spill_receipt.json",
        "mode": "100644",
        "blob": "e840788a740f6a196378c10174977c42a5b7207b",
        "bytes": 234,
        "sha256": "65bc5b4369023255330199ed67f06fcc18bfb63694c229e978de2cc02e1eda29",
    },
    {
        "path": "fh_l8_d11_full_action_result.json",
        "mode": "100644",
        "blob": "5aa09ce1ea6f9aa0209fb147f0a60d19e4faf8bf",
        "bytes": 477,
        "sha256": "2515d15d1b865e3b2bd93015eadeb394a0ee7afdc04264caf9892e3a6238d658",
    },
]

D12_ARTIFACTS = [
    {
        "path": "fh_l8_q4_to_q5_cost_d12_checker.py",
        "mode": "100644",
        "blob": "940331b87c049a027ff1bba3c12235509a703ae8",
        "bytes": 3668,
        "sha256": "0b88b502ded66825de4c7b55a05ba391dd63044f2b50b8ab6685a9304db02ac6",
    },
    {
        "path": "fh_l8_q4_to_q5_cost_d12_contract.json",
        "mode": "100644",
        "blob": "9f9b0224740ca942d8e5e50bdd181f28c9f7d660",
        "bytes": 664,
        "sha256": "4a7c1361633d5087cb6529b788c8192cbb6707168952d46cc8bead9880191273",
    },
    {
        "path": "fh_l8_q4_to_q5_cost_d12_result.json",
        "mode": "100644",
        "blob": "655797f60b400d2edceedcece194ddf8d0194afb",
        "bytes": 1184,
        "sha256": "1796a2cd74a7fe262b2e4805b033cfda0f53ee9070e26325edfe7b789d138675",
    },
]

POST_D12_UNITS = [
    {
        "unit": "D13",
        "feature": {
            "commit": "a465986259c55646c9472d7793dd7129338901f9",
            "tree": "ed0f49413eceb8e616efa127eb10e62e7aa3fc3f",
            "parents": [D12_MERGE_COMMIT],
        },
        "merge": {
            "commit": "c713f4eb25b41e0a97c9cf2b10e9df045a93afa9",
            "tree": "ed0f49413eceb8e616efa127eb10e62e7aa3fc3f",
            "parents": [D12_MERGE_COMMIT, "a465986259c55646c9472d7793dd7129338901f9"],
        },
        "artifacts": [
            {"path": "fh_l8_q5_redesign_d13_checker.py", "mode": "100644", "blob": "fd0e5cfd584c2ea696d9cb0231696b5b492fd011", "bytes": 3300, "sha256": "bfa0a6804d1bf3c2b5d2d374faf5223dda79220fcbc41bbef56510f79555f0f2"},
            {"path": "fh_l8_q5_redesign_d13_contract.json", "mode": "100644", "blob": "430dc6a425037ebaaa1079d6854fc12d7313975b", "bytes": 696, "sha256": "17b6f70eb68fd825246ea3796930035bca20c0587a21f41644a3e03fb0b2fd29"},
            {"path": "fh_l8_q5_redesign_d13_result.json", "mode": "100644", "blob": "4885e34592cfd71144a6606a3b82bc9f7a36951f", "bytes": 1316, "sha256": "6ca1be2e4c28bd523082d5cde792b735532afea4e6aa079199033251ac297305"},
        ],
        "classification": "D12_DEPENDENT_NUMERIC_ROUTE_QUARANTINED_DESIGN_OBSERVATIONS_NO_EXECUTION_AUTHORITY",
    },
    {
        "unit": "D14",
        "feature": {
            "commit": "0887f2b8fbb7bd32ae6c871d5d80db1c7faa0142",
            "tree": "35d5458a180409c9afee446406db968cf51baa39",
            "parents": ["c713f4eb25b41e0a97c9cf2b10e9df045a93afa9"],
        },
        "merge": {
            "commit": "834a9db8227228c794e20047083890a31defe746",
            "tree": "35d5458a180409c9afee446406db968cf51baa39",
            "parents": ["c713f4eb25b41e0a97c9cf2b10e9df045a93afa9", "0887f2b8fbb7bd32ae6c871d5d80db1c7faa0142"],
        },
        "artifacts": [
            {"path": "fh_l8_adjoint_contraction_d14_checker.py", "mode": "100644", "blob": "a1aa351b8c3404398f4edee128153d0f10e7ca2f", "bytes": 4965, "sha256": "748e255df16aa4aca0a1eb5e03b2271cce37bf8aa387c3f73098dec741bb1423"},
            {"path": "fh_l8_adjoint_contraction_d14_contract.json", "mode": "100644", "blob": "d893be13b590873b6b40c3392148c6ed87fa0a72", "bytes": 1683, "sha256": "d9ee6436b6fda29bfe8d7b7e6f9843bd6720837ad1bf9918c6645d9fe5dba78f"},
            {"path": "fh_l8_adjoint_contraction_d14_result.json", "mode": "100644", "blob": "b40bdf738e57645f69e0a7f675c62f464e6b75b9", "bytes": 1012, "sha256": "bcf79606da571b297b8538894f95b66523782f3e15a8b28b4112717fa81e6a38"},
        ],
        "classification": "ABSTRACT_ALGEBRA_RETAINED_POST_HOC_DESIGN_ONLY_CLEAN_LINEAGE_REATTACHMENT_REQUIRED",
    },
    {
        "unit": "D15",
        "feature": {
            "commit": "e829bff03b4ecf795e39bf72f71caf0b92a0ffa8",
            "tree": "aca5978452f02285064ed485562e212c52f3d588",
            "parents": ["834a9db8227228c794e20047083890a31defe746"],
        },
        "merge": {
            "commit": "e5aba01ba8b49bbaad983ee9371051e89a499ce4",
            "tree": "aca5978452f02285064ed485562e212c52f3d588",
            "parents": ["834a9db8227228c794e20047083890a31defe746", "e829bff03b4ecf795e39bf72f71caf0b92a0ffa8"],
        },
        "artifacts": [
            {"path": "fh_l8_word_adjoint_d15_checker.py", "mode": "100644", "blob": "07c2c7264a5c7d8ac4b1e9a6783ebeacc97c1c0c", "bytes": 5540, "sha256": "682e4ef0602c6827d51334a3dadca72fdebef485afa8f315eb9e88c9dfaaa023"},
            {"path": "fh_l8_word_adjoint_d15_contract.json", "mode": "100644", "blob": "5b2f22d1449d8ccf62427ebfa070d4c6aa472549", "bytes": 2092, "sha256": "12ac51e59f8bfc7f2fbb77e9a04086e68ff37ae4e62df567d51c10f32c36028b"},
            {"path": "fh_l8_word_adjoint_d15_result.json", "mode": "100644", "blob": "0ddc33a28563de29e093ff99a965c6f10fc04b37", "bytes": 1033, "sha256": "60ee47e38d5f74b006a3680094c7ca48a38ccb1ad62387f99ede1f712cd95c57"},
        ],
        "classification": "ABSTRACT_ALGEBRA_RETAINED_POST_HOC_DESIGN_ONLY_CLEAN_LINEAGE_REATTACHMENT_REQUIRED",
    },
]

POST_D12_AUTHORITY = {
    "D13_full_q5_materialization_no_go_authoritative": False,
    "D13_route_exclusivity_authoritative": False,
    "D14_D15_abstract_algebra_rejected": False,
    "D14_D15_execution_authority": False,
    "clean_numeric_lineage_reattachment_required": True,
}

CAP_ARTIFACTS = [
    {
        "path": "fh_l8_depth3_to_depth4_quotient_h_design_gate_contract.json",
        "mode": "100644",
        "blob": "1ccb6fe77a439ceb643aa3cd5fcb236cb0ec92aa",
        "bytes": 15890,
        "sha256": "9557b9523b5d5f29d76a3d02dc50b76553879961dae7d168dc90080529fc61ed",
    },
    {
        "path": "fh_l8_cgroup_envelope_d10_contract.json",
        "mode": "100644",
        "blob": "f668ff7b579cf99c281bc800adcfe00e9dbe14d6",
        "bytes": 429,
        "sha256": "9fadd4e58ad65a0ddd9cb12ee09fd0e96dd0e09b270abb06a8858b20eb038ce3",
    },
]

EXPECTED_AUTHORITY = {
    "packed_q3_source_admissible": True,
    "legacy_full_action_git_observation_retained": True,
    "legacy_full_action_spool_custody_valid": False,
    "legacy_full_action_target_scientifically_admitted": False,
    "legacy_full_action_result_quarantined": True,
    "legacy_q4_target_cardinality_authoritative": False,
    "legacy_q4_target_digest_authoritative": False,
    "d12_q4_to_q5_cost_scientifically_authoritative": False,
    "d13_full_q5_materialization_no_go_authoritative": False,
    "d13_route_exclusivity_authoritative": False,
    "d14_d15_abstract_algebra_retained_as_design_only": True,
    "d14_d15_execution_authorized": False,
    "d16_terminal_execution_receipt_available": False,
    "d16_publication_resource_attested": False,
    "fresh_bounded_4096_preflight_design_eligible": True,
    "fresh_bounded_4096_preflight_execution_authorized": False,
    "fresh_full_53_shard_execution_authorized": False,
    "q3_to_q4_executed_in_this_unit": False,
    "q4_to_q5_executed_in_this_unit": False,
    "degree6_remainder_bounded": False,
    "two_step_cumulative_error_bounded": False,
    "full_R100_error_bounded": False,
    "physical_reference_qualified": False,
    "hardware_result_available": False,
    "quantum_advantage_claimed": False,
    "ready_gate_eligible": False,
}

EXPECTED_LIMITATIONS = [
    "The packed C3 q3 checkpoint is admitted only as a source artifact; this unit executes no Hamiltonian action.",
    "The retained scratch spool contains receipt-unbound duplicate bytes, but no provenance proves that the retained target was produced from exactly that spool.",
    "The legacy target is quarantined because its production custody is broken; its q4 count and digest are not authoritative q3-to-q4 results.",
    "The D12 q4-to-q5 arithmetic is post-hoc and conditional on a quarantined q4 count; it provides no scientific no-go.",
    "D13 numeric route selection inherits D12's invalid input; D14-D15 abstract algebra may be retained only as post-hoc design and must be reattached to a clean numeric lineage.",
    "No runtime or memory feasibility is certified for a fresh bounded preflight or a full 53-shard execution.",
    "The D16 resource snapshot covers forensic reads only; result serialization and publication are excluded, so the result is not a terminal execution/resource receipt.",
    "No q5 target, degree-six remainder, cumulative error, full-R100 error, physical reference, hardware result, quantum advantage, or READY claim is authorized.",
]


class VerificationError(ValueError):
    """A frozen identity, schema, arithmetic, or custody condition failed."""


class ResourceIndeterminate(VerificationError):
    """The external audit could not establish its frozen resource envelope."""


class ExternalCustodyIndeterminate(ResourceIndeterminate):
    """Retained external bytes are missing, changed, or not snapshot-stable."""


def _duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise VerificationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> Any:
    raise VerificationError(f"non-finite JSON constant: {value}")


def _reject_float(value: str) -> Any:
    raise VerificationError(f"floating-point JSON number forbidden: {value}")


def _load_json_bytes(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError("JSON root must be an object")
    return value


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"


def _canonical_value(value: Any) -> bytes:
    """Canonical JSON value bytes, without a file-format trailing newline."""
    return _canonical_json(value)[:-1]


def _strict_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _strict_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _strict_equal(left, right) for left, right in zip(actual, expected, strict=True)
        )
    return actual == expected


def _require_strict_equal(actual: Any, expected: Any, label: str) -> None:
    if not _strict_equal(actual, expected):
        raise VerificationError(f"{label} type/value drift")


def _require_exact_keys(value: Mapping[str, Any], keys: Iterable[str], label: str) -> None:
    expected = set(keys)
    if set(value) != expected:
        raise VerificationError(f"{label} schema drift")


def _require_int(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise VerificationError(f"{label} must be an integer >= {minimum}")
    return value


def _require_sha(value: Any, label: str, length: int = 64) -> str:
    pattern = SHA64_RE if length == 64 else SHA40_RE
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise VerificationError(f"{label} is not a canonical SHA")
    return value


def _git_root() -> str:
    return subprocess.check_output(
        ["git", "-C", str(HERE), "rev-parse", "--show-toplevel"],
        stderr=subprocess.DEVNULL,
    ).decode("utf-8").strip()


def _git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", _git_root(), *args], stderr=subprocess.DEVNULL
    )


def _commit_record(commit: str) -> dict[str, Any]:
    if not isinstance(commit, str) or SHA40_RE.fullmatch(commit) is None:
        raise VerificationError("full commit id required")
    resolved = _git("rev-parse", f"{commit}^{{commit}}").decode("ascii").strip()
    if resolved != commit:
        raise VerificationError("commit id is not exact")
    fields = _git("rev-list", "--parents", "-n", "1", commit).decode("ascii").split()
    return {
        "commit": commit,
        "tree": _git("rev-parse", f"{commit}^{{tree}}").decode("ascii").strip(),
        "parents": fields[1:],
    }


def _verify_commit(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    if not _strict_equal(actual, expected) or not _strict_equal(
        _commit_record(str(actual.get("commit", ""))), expected
    ):
        raise VerificationError("commit topology drift")


def _diff_entries(commit: str) -> set[tuple[str, str]]:
    raw = _git("diff-tree", "--no-commit-id", "--name-status", "-r", "-z", commit)
    parts = raw.rstrip(b"\0").split(b"\0") if raw else []
    if len(parts) % 2:
        raise VerificationError("malformed Git diff")
    entries: set[tuple[str, str]] = set()
    for index in range(0, len(parts), 2):
        status_code = parts[index].decode("ascii")
        path = parts[index + 1].decode("utf-8", errors="strict")
        if status_code not in {"A", "M", "D", "T"} or (status_code, path) in entries:
            raise VerificationError("unsupported or duplicate Git diff entry")
        entries.add((status_code, path))
    return entries


def _path_exists(commit: str, path: str) -> bool:
    try:
        _git("cat-file", "-e", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        return False
    return True


def _blob_metadata(commit: str, path: str) -> tuple[str, str, int]:
    fields = _git("ls-tree", commit, path).decode("ascii").split()
    if len(fields) < 3 or fields[1] != "blob":
        raise VerificationError(f"missing/non-blob Git artifact: {path}")
    mode, blob = fields[0], fields[2]
    size = int(_git("cat-file", "-s", f"{commit}:{path}"))
    return mode, blob, size


def _blob_identity(commit: str, path: str) -> tuple[str, str, int, str]:
    mode, blob, size = _blob_metadata(commit, path)
    process = subprocess.Popen(
        ["git", "-C", _git_root(), "cat-file", "blob", f"{commit}:{path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert process.stdout is not None
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk = process.stdout.read(READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        digest.update(chunk)
    returncode = process.wait()
    if returncode or total != size:
        raise VerificationError(f"could not stream Git artifact: {path}")
    return mode, blob, size, digest.hexdigest()


def _verify_artifacts(commit: str, supplied: Any, expected: list[dict[str, Any]]) -> None:
    _require_strict_equal(supplied, expected, "artifact pin family")
    for pin in expected:
        _require_exact_keys(pin, {"path", "mode", "blob", "bytes", "sha256"}, "artifact pin")
        path = f"{PREFIX}/{pin['path']}"
        identity = _blob_identity(commit, path)
        wanted = (pin["mode"], pin["blob"], pin["bytes"], pin["sha256"])
        if identity != wanted:
            raise VerificationError(f"artifact identity drift: {pin['path']}")


def _read_stable_fd(fd: int, label: str, maximum: int, exact: int | None = None) -> bytes:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode):
        raise VerificationError(f"{label} is not a regular file")
    if before.st_size > maximum or (exact is not None and before.st_size != exact):
        raise VerificationError(f"{label} byte size drift")
    chunks: list[bytes] = []
    total = 0
    while total < before.st_size:
        chunk = os.read(fd, min(READ_CHUNK, before.st_size - total))
        if not chunk:
            raise VerificationError(f"short read: {label}")
        chunks.append(chunk)
        total += len(chunk)
    if os.read(fd, 1):
        raise VerificationError(f"growth during read: {label}")
    after = os.fstat(fd)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if identity_before != identity_after:
        raise ResourceIndeterminate(f"file changed during read: {label}")
    return b"".join(chunks)


def _read_regular_nofollow(path: Path, maximum: int, exact: int | None = None) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        return _read_stable_fd(fd, str(path), maximum, exact)
    finally:
        os.close(fd)


def _read_member(dir_fd: int, name: str, maximum: int, exact: int | None = None) -> bytes:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
    try:
        return _read_stable_fd(fd, name, maximum, exact)
    finally:
        os.close(fd)


def _open_directory_nofollow(path: Path) -> int:
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)


def _stat_identity(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _directory_inventory(
    directory_fd: int, expected_names: set[str]
) -> dict[str, tuple[int, int, int, int, int, int]]:
    names = set(os.listdir(directory_fd))
    if names != expected_names:
        raise ExternalCustodyIndeterminate("external directory member set drift")
    return {
        name: _stat_identity(os.stat(name, dir_fd=directory_fd, follow_symlinks=False))
        for name in sorted(names)
    }


def _read_relative_member(
    root_fd: int,
    relative: str,
    maximum: int,
    exact: int | None = None,
) -> bytes:
    parts = relative.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise VerificationError("unsafe relative artifact path")
    current_fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            next_fd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        return _read_member(current_fd, parts[-1], maximum, exact)
    finally:
        os.close(current_fd)


def _read_git_bound_repo_artifact(
    relative: str,
    commit: str,
    expected_bytes: int,
    expected_sha256: str,
    maximum: int,
) -> bytes:
    metadata = _blob_metadata(commit, f"{PREFIX}/{relative}")
    if metadata[2] != expected_bytes or metadata[2] > maximum:
        raise VerificationError(f"Git artifact byte preflight drift: {relative}")
    root_fd = _open_directory_nofollow(HERE)
    try:
        raw = _read_relative_member(root_fd, relative, maximum, expected_bytes)
    finally:
        os.close(root_fd)
    frozen = _git("show", f"{commit}:{PREFIX}/{relative}")
    if raw != frozen or _hash_bytes(raw) != expected_sha256:
        raise VerificationError(f"working/Git artifact drift: {relative}")
    return raw


def _hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_contract(contract: Mapping[str, Any]) -> None:
    _require_exact_keys(
        contract,
        {
            "schema_version",
            "contract_id",
            "status",
            "analysis_class",
            "chronology",
            "checker_artifact",
            "packed_source",
            "parallel_full_action",
            "downstream_d12",
            "downstream_d13_d15",
            "external_forensic",
            "clean_reexecution_protocol",
            "resource_limits",
            "decision_rule",
            "authority_ceiling",
            "forbidden_claims",
        },
        "contract",
    )
    if (
        type(contract["schema_version"]) is not int
        or contract["schema_version"] != 1
        or contract["contract_id"] != CONTRACT_ID
        or contract["status"] != PROTOCOL_STATUS
        or contract["analysis_class"]
        != "PREREGISTERED_CUSTODY_FORENSIC_AND_CONSUMER_DESIGN_NO_SCIENTIFIC_ACTION"
    ):
        raise VerificationError("contract identity/status drift")

    packed = contract["packed_source"]
    _require_exact_keys(
        packed,
        {
            "source_freeze",
            "contract_freeze",
            "outcome",
            "artifacts",
            "expected_checkpoint",
            "source_authority",
        },
        "packed source",
    )
    if packed["source_authority"] != "ONLY_ADMISSIBLE_Q3_SOURCE_FOR_A_FRESH_CONSUMER":
        raise VerificationError("packed source contract drift")
    _require_strict_equal(packed["artifacts"], PACKED_ARTIFACTS, "packed artifact pins")
    _require_strict_equal(
        packed["expected_checkpoint"], EXPECTED_PACKED, "packed checkpoint expectation"
    )

    parallel = contract["parallel_full_action"]
    _require_exact_keys(
        parallel,
        {
            "source_materialization_commit",
            "bounded_preflight_commit",
            "full_action_commit",
            "merge_commit",
            "artifacts",
            "committed_observations",
            "known_chronology_failures",
        },
        "parallel full action",
    )
    _require_strict_equal(
        parallel["artifacts"], PARALLEL_ARTIFACTS, "parallel artifact pins"
    )
    _require_strict_equal(parallel["committed_observations"], {
        "completed_shards": 53,
        "new_spill_records": 23126970,
        "reported_fourth_action_executed": True,
        "reported_target_records": 10785545,
        "reported_target_bytes": 345137440,
        "reported_target_sha256": EXPECTED_EXTERNAL["target_sha256"],
    }, "parallel committed observations")
    _require_strict_equal(parallel["known_chronology_failures"], [
        "full runner implementation and full result first appeared in the same commit",
        "the unchanged source contract explicitly denied depth4 execution authority",
        "packed C3 was not an ancestor of the parallel full-action commit",
        "no committed target payload or terminal execution/resource receipt exists",
    ], "parallel chronology classification")

    downstream = contract["downstream_d12"]
    _require_exact_keys(
        downstream,
        {
            "commit",
            "merge_commit",
            "artifacts",
            "reported_costs",
            "classification",
            "cap_provenance",
        },
        "downstream D12",
    )
    if (
        downstream["classification"]
        != "POST_HOC_CONDITIONAL_ARITHMETIC_ON_QUARANTINED_Q4_INPUT"
    ):
        raise VerificationError("downstream D12 classification drift")
    _require_strict_equal(downstream["artifacts"], D12_ARTIFACTS, "D12 artifacts")
    _require_strict_equal(downstream["reported_costs"], EXPECTED_COSTS, "D12 costs")
    _require_strict_equal(downstream["cap_provenance"], {
        "raw_group_and_spill_caps_are_D7_planning_caps": True,
        "D10_only_supplies_cgroup_and_bounded_4096_preflight_evidence": True,
        "source_file_bytes_greater_than_live_buffer_is_not_a_streaming_no_go": True,
    }, "D12 cap provenance")

    post_d12 = contract["downstream_d13_d15"]
    _require_exact_keys(post_d12, {"units", "authority"}, "downstream D13-D15")
    _require_strict_equal(post_d12["units"], POST_D12_UNITS, "downstream D13-D15 units")
    _require_strict_equal(
        post_d12["authority"], POST_D12_AUTHORITY, "downstream D13-D15 authority"
    )

    forensic = contract["external_forensic"]
    _require_exact_keys(
        forensic,
        {
            "source_root",
            "run_root",
            "expected",
            "expected_digests",
            "receipt_record_bytes",
            "require_all_receipt_chunk_hashes",
            "require_exact_partition_set",
            "require_gap_duplicate_match",
            "forbid_gap_overlap_or_trailing_bytes_for_admission",
        },
        "external forensic",
    )
    if (
        forensic["source_root"] != str(DEFAULT_SOURCE_ROOT)
        or forensic["run_root"] != str(DEFAULT_RUN_ROOT)
        or not _strict_equal(forensic["expected"], EXPECTED_EXTERNAL)
        or not _strict_equal(forensic["expected_digests"], EXPECTED_FORENSIC_DIGESTS)
        or forensic["receipt_record_bytes"] != 32
        or forensic["require_all_receipt_chunk_hashes"] is not True
        or forensic["require_exact_partition_set"] is not True
        or forensic["require_gap_duplicate_match"] is not True
        or forensic["forbid_gap_overlap_or_trailing_bytes_for_admission"] is not True
    ):
        raise VerificationError("external forensic policy drift")

    protocol = contract["clean_reexecution_protocol"]
    _require_exact_keys(
        protocol,
        {
            "source_admission",
            "run_isolation",
            "source_shards",
            "partitions",
            "spill_record",
            "per_shard_publication",
            "resume_validation",
            "merge",
            "target_publication",
            "state_machine",
        },
        "clean reexecution protocol",
    )
    _require_strict_equal(protocol, {
        "source_admission": {
            "packed_C3_required": PACKED_C3,
            "checkpoint_sha256_required": EXPECTED_PACKED["packed_sorted_binary_sha256"],
            "source_shard_manifest_sha256_required": PACKED_SHARD_MANIFEST_SHA256,
            "terminal_receipt_required": True,
            "full_32_byte_record_validation_before_action": True,
            "legacy_external_manifest_cannot_authorize_execution": True,
        },
        "run_isolation": {
            "fresh_exclusive_scratch_root": True,
            "exclusive_run_lock": True,
            "shared_append_spool_reuse_forbidden": True,
            "stale_output_is_fail_closed": True,
        },
        "source_shards": {
            "records": 213099,
            "shard_size": 4096,
            "shard_count": 53,
            "full_shards": 52,
            "last_shard_records": 107,
        },
        "partitions": {
            "count": 256,
            "selector": "SHA256(target_u128_be)[0]",
            "exact_set_required": True,
        },
        "spill_record": {
            "bytes": 32,
            "encoding": "u128be_target+i64be_scaled8_delta+u64be_zero",
            "common_denominator": 8,
        },
        "per_shard_publication": {
            "independent_staging_directory": True,
            "file_fsync_before_manifest": True,
            "manifest_binds_source_slice_and_each_partition_file": True,
            "atomic_no_replace_publish": True,
            "parent_directory_fsync": True,
            "previous_receipt_hash_chain": True,
        },
        "resume_validation": {
            "exact_53_manifest_set": True,
            "all_file_hashes_recomputed": True,
            "no_gap_no_overlap_exact_frontier": True,
            "orphan_bytes_require_fresh_run_or_explicit_truncate_recovery_receipt": True,
        },
        "merge": {
            "reads_only_manifest_enumerated_files": True,
            "bounded_external_sort": True,
            "maximum_fan_in": 32,
            "signed_i128_accumulator": True,
            "exact_division_by_8": True,
            "drop_zero_after_exact_merge": True,
            "partition_order": "000_to_255",
        },
        "target_publication": {
            "staging_rehash": True,
            "atomic_no_replace_publish": True,
            "terminal_execution_and_resource_receipt": True,
        },
        "state_machine": {
            "fields": [
                "q3_rows_acted",
                "action_started",
                "spill_complete",
                "merge_complete",
                "target_materialized",
            ],
            "any_q3_row_forbids_fourth_action_executed_false": True,
            "spill_complete_requires_action_started": True,
            "merge_complete_requires_spill_complete": True,
            "target_materialized_requires_merge_complete": True,
            "state_transitions_are_monotone": True,
        },
    }, "clean reexecution protocol")

    limits = contract["resource_limits"]
    _require_strict_equal(limits, {
        "outer_memory_max_bytes": 268435456,
        "outer_memory_high_bytes": 201326592,
        "outer_swap_max_bytes": 0,
        "max_process_peak_rss_bytes": 67108864,
        "max_cgroup_peak_bytes": 201326592,
        "max_initial_cgroup_peak_bytes": 67108864,
        "internal_deadline_seconds": 180,
        "read_chunk_bytes": 1048576,
        "max_source_checkpoint_bytes": 6819168,
        "max_external_receipt_bytes_each": 131072,
        "max_external_spool_bytes_total": 3000000000,
        "max_external_spool_bytes_each": 33554432,
        "max_external_target_bytes": 536870912,
        "max_manifest_bytes": 524288,
        "max_result_bytes": 262144,
        "max_created_final_artifacts": 1,
        "scientific_action_call_budget": 0,
    }, "resource limits")
    _require_strict_equal(contract["decision_rule"], {
        "packed_source_failure": "VERIFICATION_FAILED",
        "external_missing_changed_timeout_or_resource_failure": "INDETERMINATE_D16_EXTERNAL_CUSTODY_AUDIT",
        "exact_retained_spool_duplicate_pattern": STATUS,
        "legacy_target_disposition": "QUARANTINED_BROKEN_PRODUCTION_CUSTODY_NOT_SCIENTIFICALLY_ADMITTED",
        "downstream_D12_disposition": "SUPERSEDED_INVALID_INPUT_NO_SCIENTIFIC_AUTHORITY",
        "fresh_execution_authorized_on_any_outcome": False,
        "next_gate": NEXT_GATE,
    }, "decision rule")
    _require_strict_equal(contract["authority_ceiling"], EXPECTED_AUTHORITY, "authority ceiling")
    _require_strict_equal(contract["forbidden_claims"], EXPECTED_LIMITATIONS, "limitations")


def verify_protocol(contract: Mapping[str, Any], contract_commit: str) -> dict[str, Any]:
    validate_contract(contract)
    chronology = contract["chronology"]
    _require_exact_keys(
        chronology,
        {
            "evidence_baseline",
            "checker_freeze",
            "checker_path",
            "contract_path",
            "result_path",
            "checker_must_precede_contract",
            "forensic_result_must_be_absent_before_audit",
        },
        "chronology",
    )
    baseline = {"commit": BASE_COMMIT, "tree": BASE_TREE, "parents": BASE_PARENTS}
    _verify_commit(chronology["evidence_baseline"], baseline)
    freeze = chronology["checker_freeze"]
    _require_exact_keys(freeze, {"commit", "tree", "parents"}, "checker freeze")
    if freeze["parents"] != [BASE_COMMIT]:
        raise VerificationError("checker freeze must directly descend from baseline")
    _verify_commit(freeze, freeze)
    if _diff_entries(freeze["commit"]) != {("A", CHECKER_PATH)}:
        raise VerificationError("checker freeze must add only the checker")
    if (
        chronology["checker_path"] != CHECKER_PATH
        or chronology["contract_path"] != CONTRACT_PATH
        or chronology["result_path"] != RESULT_PATH
        or chronology["checker_must_precede_contract"] is not True
        or chronology["forensic_result_must_be_absent_before_audit"] is not True
    ):
        raise VerificationError("chronology path/policy drift")
    for path in (CONTRACT_PATH, RESULT_PATH):
        if _path_exists(freeze["commit"], path):
            raise VerificationError("contract/output existed at checker freeze")
    checker_pin = contract["checker_artifact"]
    _require_exact_keys(checker_pin, {"path", "mode", "blob", "bytes", "sha256"}, "checker artifact")
    if (
        checker_pin["path"] != CHECKER_NAME
        or type(checker_pin["bytes"]) is not int
        or not 0 < checker_pin["bytes"] <= 1_048_576
    ):
        raise VerificationError("checker artifact path drift")
    _verify_artifacts(freeze["commit"], [checker_pin], [dict(checker_pin)])

    record = _commit_record(contract_commit)
    if record["parents"] != [freeze["commit"]]:
        raise VerificationError("contract commit must directly descend from checker freeze")
    if _diff_entries(contract_commit) != {("A", CONTRACT_PATH)}:
        raise VerificationError("contract freeze must add only the contract")
    here_fd = _open_directory_nofollow(HERE)
    try:
        raw_contract = _read_member(here_fd, CONTRACT_NAME, 1_048_576)
        current_checker = _read_member(here_fd, CHECKER_NAME, 1_048_576)
    finally:
        os.close(here_fd)
    contract_metadata = _blob_metadata(contract_commit, CONTRACT_PATH)
    if contract_metadata[2] > 1_048_576:
        raise VerificationError("contract Git blob exceeds byte cap")
    if _git("show", f"{contract_commit}:{CONTRACT_PATH}") != raw_contract:
        raise VerificationError("working/frozen contract drift")
    contract_identity = _blob_identity(contract_commit, CONTRACT_PATH)
    if contract_identity[0] != "100644":
        raise VerificationError("contract mode drift")
    checker_metadata = _blob_metadata(contract_commit, CHECKER_PATH)
    if checker_metadata[2] > 1_048_576:
        raise VerificationError("checker Git blob exceeds byte cap")
    if _git("show", f"{contract_commit}:{CHECKER_PATH}") != current_checker:
        raise VerificationError("checker changed after source freeze")
    forbidden_paths = (
        f"{PREFIX}/fh_l8_packed_consumer_forensic_d16_runner.py",
        f"{PREFIX}/fh_l8_packed_consumer_forensic_d16_target.bin",
    )
    for commit in (BASE_COMMIT, freeze["commit"], contract_commit):
        if any(_path_exists(commit, path) for path in forbidden_paths):
            raise VerificationError("forensic unit contains a forbidden scientific action artifact")
    matches = _git(
        "grep",
        "-l",
        "-F",
        CONTRACT_ID,
        contract_commit,
        "--",
        f"{PREFIX}/*_contract.json",
    ).decode("utf-8").splitlines()
    expected_match = f"{contract_commit}:{CONTRACT_PATH}"
    if matches != [expected_match]:
        raise VerificationError("contract id is not globally unique")
    if _path_exists(contract_commit, RESULT_PATH):
        raise VerificationError("forensic result existed at contract freeze")
    return {
        "checker_freeze_commit": freeze["commit"],
        "checker_freeze_tree": freeze["tree"],
        "contract_freeze_commit": record["commit"],
        "contract_freeze_tree": record["tree"],
        "contract_artifact": {
            "mode": contract_identity[0],
            "blob": contract_identity[1],
            "bytes": contract_identity[2],
            "sha256": contract_identity[3],
        },
        "checker_preceded_contract": True,
        "forensic_result_absent_before_external_audit": True,
    }


def verify_source_git(contract: Mapping[str, Any]) -> dict[str, Any]:
    packed = contract["packed_source"]
    packed_c1 = {
        "commit": PACKED_C1,
        "tree": "75f8034aec9c95d02b4647c5908aea17c1835115",
        "parents": ["b620f02ff53ed84472d0f38c775bdeb584fdf736"],
    }
    packed_c2 = {
        "commit": PACKED_C2,
        "tree": "3d0ce731c6ae6c3697eb691823e95e527ae4918f",
        "parents": [PACKED_C1],
    }
    packed_c3 = {
        "commit": PACKED_C3,
        "tree": "801d335d7edf39de22a24f969c1a81396c065095",
        "parents": [PACKED_C2],
    }
    for supplied, expected in (
        (packed["source_freeze"], packed_c1),
        (packed["contract_freeze"], packed_c2),
        (packed["outcome"], packed_c3),
    ):
        _verify_commit(supplied, expected)
    if _diff_entries(PACKED_C1) != {
        ("A", f"{PREFIX}/fh_l8_packed_q3_checkpoint_d11_checker.py"),
        ("A", f"{PREFIX}/fh_l8_packed_q3_checkpoint_d11_runner.py"),
    }:
        raise VerificationError("packed C1 diff drift")
    if _diff_entries(PACKED_C2) != {
        ("A", f"{PREFIX}/fh_l8_packed_q3_checkpoint_d11_contract.json")
    }:
        raise VerificationError("packed C2 diff drift")
    if _diff_entries(PACKED_C3) != {
        ("A", PACKED_CHECKPOINT_PATH),
        ("A", PACKED_RESULT_PATH),
        ("A", PACKED_RECEIPT_PATH),
    }:
        raise VerificationError("packed C3 diff drift")
    _verify_artifacts(PACKED_C3, packed["artifacts"], PACKED_ARTIFACTS)

    parallel = contract["parallel_full_action"]
    expected_parallel = [
        {
            "commit": PARALLEL_SOURCE_COMMIT,
            "tree": "d721185fbf72750b340a748ed67e44a80b37b915",
            "parents": ["b620f02ff53ed84472d0f38c775bdeb584fdf736"],
        },
        {
            "commit": PARALLEL_PREFLIGHT_COMMIT,
            "tree": "b7c92a4a8b78cd04dfe1c02f0a2f39ffb52d768e",
            "parents": [PARALLEL_SOURCE_COMMIT],
        },
        {
            "commit": PARALLEL_FULL_COMMIT,
            "tree": "6440240e7be75368513ec5798f4876c5a2a6d8bd",
            "parents": [PARALLEL_PREFLIGHT_COMMIT],
        },
        {
            "commit": PARALLEL_MERGE_COMMIT,
            "tree": "2c1cb516d7d291ba79abd53deef0295460ab38b3",
            "parents": [
                "ca4938833c1d7b85c9452000a92ac27f82594726",
                PARALLEL_FULL_COMMIT,
            ],
        },
    ]
    supplied_parallel = [
        parallel["source_materialization_commit"],
        parallel["bounded_preflight_commit"],
        parallel["full_action_commit"],
        parallel["merge_commit"],
    ]
    for supplied, expected in zip(supplied_parallel, expected_parallel, strict=True):
        _verify_commit(supplied, expected)
    if _diff_entries(PARALLEL_FULL_COMMIT) != {
        ("M", f"{PREFIX}/FH_L8_CHECKPOINTED_QUOTIENT_H_D11_ZH.md"),
        ("M", f"{PREFIX}/fh_l8_checkpointed_quotient_h_d11_runner.py"),
        ("A", f"{PREFIX}/fh_l8_d11_full_action_result.json"),
        ("A", f"{PREFIX}/fh_l8_d11_full_spill_receipt.json"),
        ("M", f"{PREFIX}/test_fh_l8_checkpointed_quotient_h_d11_runner.py"),
    }:
        raise VerificationError("parallel full-action commit diff drift")
    _verify_artifacts(PARALLEL_FULL_COMMIT, parallel["artifacts"], PARALLEL_ARTIFACTS)
    ancestor = subprocess.run(
        ["git", "-C", _git_root(), "merge-base", "--is-ancestor", PACKED_C3, PARALLEL_FULL_COMMIT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if ancestor.returncode == 0:
        raise VerificationError("parallel full action unexpectedly descends from packed C3")
    if ancestor.returncode != 1:
        raise VerificationError("could not establish packed/parallel ancestry")

    legacy_contract = _load_json_bytes(
        _git("show", f"{PARALLEL_FULL_COMMIT}:{PREFIX}/fh_l8_checkpointed_quotient_h_d11_contract.json")
    )
    if legacy_contract.get("authority") != {
        "depth4_action_executed": False,
        "target_vector_materialized": False,
        "degree6_remainder_bounded": False,
        "ready_gate_eligible": False,
    }:
        raise VerificationError("legacy contract authority drift")
    full_result = _load_json_bytes(
        _git("show", f"{PARALLEL_FULL_COMMIT}:{PREFIX}/fh_l8_d11_full_action_result.json")
    )
    if (
        full_result.get("fourth_action_executed") is not True
        or full_result.get("target_records") != 10785545
        or full_result.get("target_payload_bytes") != 345137440
        or full_result.get("target_sha256") != EXPECTED_EXTERNAL["target_sha256"]
    ):
        raise VerificationError("legacy full result drift")
    for absent in (
        f"{PREFIX}/fh_l8_d11_full_action_terminal_receipt.json",
        f"{PREFIX}/fh_l8_d11_depth4_target.bin",
    ):
        if _path_exists(PARALLEL_FULL_COMMIT, absent):
            raise VerificationError("unexpected committed full-action custody artifact")

    downstream = contract["downstream_d12"]
    d12_record = {
        "commit": D12_COMMIT,
        "tree": "135a9ff103d74e7f705dd0152b8b3e4dcbab83d8",
        "parents": [PARALLEL_MERGE_COMMIT],
    }
    d12_merge = {
        "commit": D12_MERGE_COMMIT,
        "tree": D12_MERGE_TREE,
        "parents": D12_MERGE_PARENTS,
    }
    _verify_commit(downstream["commit"], d12_record)
    _verify_commit(downstream["merge_commit"], d12_merge)
    expected_d12_diff = {
        ("A", f"{PREFIX}/FH_L8_Q4_TO_Q5_COST_D12_ZH.md"),
        ("A", f"{PREFIX}/fh_l8_q4_to_q5_cost_d12_checker.py"),
        ("A", f"{PREFIX}/fh_l8_q4_to_q5_cost_d12_contract.json"),
        ("A", f"{PREFIX}/fh_l8_q4_to_q5_cost_d12_result.json"),
        ("A", f"{PREFIX}/test_fh_l8_q4_to_q5_cost_d12_checker.py"),
    }
    if _diff_entries(D12_COMMIT) != expected_d12_diff:
        raise VerificationError("D12 same-commit artifact chronology drift")
    _verify_artifacts(D12_COMMIT, downstream["artifacts"], D12_ARTIFACTS)
    _verify_artifacts(D12_MERGE_COMMIT, CAP_ARTIFACTS, CAP_ARTIFACTS)

    post_d12 = contract["downstream_d13_d15"]
    expected_post_diffs = {
        "D13": {
            ("A", f"{PREFIX}/FH_L8_Q5_REDESIGN_D13_ZH.md"),
            ("A", f"{PREFIX}/fh_l8_q5_redesign_d13_checker.py"),
            ("A", f"{PREFIX}/fh_l8_q5_redesign_d13_contract.json"),
            ("A", f"{PREFIX}/fh_l8_q5_redesign_d13_result.json"),
            ("A", f"{PREFIX}/test_fh_l8_q5_redesign_d13_checker.py"),
        },
        "D14": {
            ("A", f"{PREFIX}/FH_L8_ADJOINT_CONTRACTION_D14_ZH.md"),
            ("A", f"{PREFIX}/fh_l8_adjoint_contraction_d14_checker.py"),
            ("A", f"{PREFIX}/fh_l8_adjoint_contraction_d14_contract.json"),
            ("A", f"{PREFIX}/fh_l8_adjoint_contraction_d14_result.json"),
            ("A", f"{PREFIX}/test_fh_l8_adjoint_contraction_d14_checker.py"),
        },
        "D15": {
            ("A", f"{PREFIX}/FH_L8_WORD_ADJOINT_D15_ZH.md"),
            ("A", f"{PREFIX}/fh_l8_word_adjoint_d15_checker.py"),
            ("A", f"{PREFIX}/fh_l8_word_adjoint_d15_contract.json"),
            ("A", f"{PREFIX}/fh_l8_word_adjoint_d15_result.json"),
            ("A", f"{PREFIX}/test_fh_l8_word_adjoint_d15_checker.py"),
        },
    }
    for supplied, expected in zip(post_d12["units"], POST_D12_UNITS, strict=True):
        _verify_commit(supplied["feature"], expected["feature"])
        _verify_commit(supplied["merge"], expected["merge"])
        if _diff_entries(expected["feature"]["commit"]) != expected_post_diffs[
            expected["unit"]
        ]:
            raise VerificationError(f"{expected['unit']} same-commit artifact drift")
        _verify_artifacts(
            expected["feature"]["commit"], supplied["artifacts"], expected["artifacts"]
        )

    d13_result = _load_json_bytes(
        _git(
            "show",
            f"{POST_D12_UNITS[0]['feature']['commit']}:{PREFIX}/fh_l8_q5_redesign_d13_result.json",
        )
    )
    if not _strict_equal(d13_result.get("D12_costs"), {
        "candidate_group_image_upper_bound": EXPECTED_COSTS["candidate_group_image_upper_bound"],
        "primary_spill_bytes_upper_bound": EXPECTED_COSTS["primary_spill_bytes_upper_bound"],
        "q4_sources": EXPECTED_COSTS["q4_sources_reported"],
        "raw_candidate_upper_bound": EXPECTED_COSTS["raw_candidate_upper_bound"],
        "source_group_image_upper_bound": EXPECTED_COSTS["source_group_image_upper_bound"],
        "total_group_image_upper_bound": EXPECTED_COSTS["total_group_image_upper_bound"],
    }):
        raise VerificationError("D13 no-go no longer binds D12 quarantined costs")
    for index, filename in (
        (1, "fh_l8_adjoint_contraction_d14_result.json"),
        (2, "fh_l8_word_adjoint_d15_result.json"),
    ):
        value = _load_json_bytes(
            _git(
                "show",
                f"{POST_D12_UNITS[index]['feature']['commit']}:{PREFIX}/{filename}",
            )
        )
        exclusions = value.get("authority_exclusions", {})
        if not isinstance(exclusions, dict) or any(item is not False for item in exclusions.values()):
            raise VerificationError(f"{POST_D12_UNITS[index]['unit']} authority drift")
    return {
        "packed_C1_C2_C3_topology_verified": True,
        "packed_artifacts_exactly_pinned": True,
        "parallel_full_action_commit": PARALLEL_FULL_COMMIT,
        "parallel_full_runner_and_result_same_commit": True,
        "parallel_contract_denied_depth4_execution": True,
        "packed_C3_is_ancestor_of_parallel_full_action": False,
        "parallel_target_payload_committed": False,
        "parallel_terminal_execution_resource_receipt_committed": False,
        "D12_checker_contract_result_same_commit": True,
        "D12_cap_provenance_separated": True,
        "D13_numeric_route_quarantined_invalid_D12_input": True,
        "D14_D15_abstract_algebra_retained_design_only": True,
        "D14_D15_execution_authority": False,
    }


def _json_item(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def audit_packed_checkpoint(contract: Mapping[str, Any]) -> dict[str, Any]:
    here_fd = _open_directory_nofollow(HERE)
    bundle_fd = os.open(
        "fh_l8_packed_q3_checkpoint_d11_bundle",
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        dir_fd=here_fd,
    )
    fd = os.open("checkpoint.bin", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=bundle_fd)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size != SOURCE_BYTES:
            raise VerificationError("packed checkpoint type/size drift")
        ranks = bytearray(SOURCE_RECORDS)
        rank_offsets = array.array("I", [0]) * SOURCE_RECORDS
        full_digest = hashlib.sha256()
        projection_digest = hashlib.sha256()
        semantic_digest = hashlib.sha256(b"[")
        support_digest = hashlib.sha256(b"[")
        shard_records: list[dict[str, Any]] = []
        shard_digest = hashlib.sha256()
        packed_bytes = bytearray()
        previous = -1
        first: int | None = None
        last: int | None = None
        positive = 0
        negative = 0
        zero = 0
        amplitude_sum = 0
        max_abs = 0
        orbit_histogram: dict[str, int] = {"1": 0, "4": 0, "8": 0}
        stabilizer_histogram: dict[str, int] = {"1": 0, "2": 0, "8": 0}
        coverage = 0
        nonzero_ranks = 0
        even_mask = int("55" * 16, 16)
        record_index = 0
        carry = b""
        while True:
            chunk = os.read(fd, READ_CHUNK)
            if not chunk:
                break
            full_digest.update(chunk)
            packed_bytes.extend(chunk)
            data = carry + chunk
            usable = len(data) - (len(data) % RECORD_BYTES)
            for offset in range(0, usable, RECORD_BYTES):
                raw = data[offset : offset + RECORD_BYTES]
                representative = int.from_bytes(raw[0:16], "big", signed=False)
                amplitude = int.from_bytes(raw[16:24], "big", signed=True)
                orbit = raw[24]
                flags = raw[25]
                reserved = int.from_bytes(raw[26:28], "big", signed=False)
                rank = int.from_bytes(raw[28:32], "big", signed=False)
                if representative <= previous:
                    raise VerificationError("packed representatives are not strictly ascending")
                if amplitude == 0:
                    zero += 1
                if abs(amplitude) > EXPECTED_PACKED["maximum_absolute_amplitude_allowed"]:
                    raise VerificationError("packed amplitude exceeds frozen bound")
                if orbit not in (1, 4, 8):
                    raise VerificationError("packed orbit size drift")
                if flags != 0 or reserved != 0:
                    raise VerificationError("packed flags/reserved drift")
                if rank >= SOURCE_RECORDS or ranks[rank]:
                    raise VerificationError("packed rank is not a permutation")
                if (
                    (representative & even_mask).bit_count() != 32
                    or ((representative >> 1) & even_mask).bit_count() != 32
                ):
                    raise VerificationError("packed representative escaped particle sector")
                ranks[rank] = 1
                rank_offsets[rank] = record_index
                nonzero_ranks += rank != 0
                previous = representative
                first = representative if first is None else first
                last = representative
                positive += amplitude > 0
                negative += amplitude < 0
                amplitude_sum += amplitude
                max_abs = max(max_abs, abs(amplitude))
                orbit_histogram[str(orbit)] += 1
                stabilizer_histogram[str(8 // orbit)] += 1
                coverage += orbit
                projection_digest.update(raw[:25])
                projection_digest.update(ZERO7)
                if record_index:
                    semantic_digest.update(b",")
                    support_digest.update(b",")
                semantic_digest.update(
                    _json_item([hex(representative), str(amplitude), orbit, rank])
                )
                support_digest.update(_json_item([hex(representative), str(orbit)]))
                shard_digest.update(raw)
                local = record_index % SOURCE_SHARD_SIZE
                if local == SOURCE_SHARD_SIZE - 1 or record_index == SOURCE_RECORDS - 1:
                    shard_index = record_index // SOURCE_SHARD_SIZE
                    records = local + 1
                    byte_offset = shard_index * SOURCE_SHARD_SIZE * RECORD_BYTES
                    shard_records.append(
                        {
                            "index": shard_index,
                            "source_start": shard_index * SOURCE_SHARD_SIZE,
                            "records": records,
                            "byte_offset": byte_offset,
                            "bytes": records * RECORD_BYTES,
                            "sha256": shard_digest.hexdigest(),
                        }
                    )
                    shard_digest = hashlib.sha256()
                record_index += 1
            carry = data[usable:]
        if carry or record_index != SOURCE_RECORDS or not all(ranks):
            raise VerificationError("packed record/rank coverage drift")
        semantic_digest.update(b"]")
        support_digest.update(b"]")

        if len(packed_bytes) != SOURCE_BYTES:
            raise VerificationError("packed in-memory custody copy length drift")
        legacy_digest = hashlib.sha256(b"[")
        for rank, index in enumerate(rank_offsets):
            raw = packed_bytes[index * RECORD_BYTES : (index + 1) * RECORD_BYTES]
            if rank:
                legacy_digest.update(b",")
            legacy_digest.update(
                _json_item(
                    [
                        hex(int.from_bytes(raw[0:16], "big", signed=False)),
                        str(int.from_bytes(raw[16:24], "big", signed=True)),
                        raw[24],
                    ]
                )
            )
        legacy_digest.update(b"]")
        after = os.fstat(fd)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if tuple(getattr(before, key) for key in stable_fields) != tuple(
            getattr(after, key) for key in stable_fields
        ):
            raise ResourceIndeterminate("packed checkpoint changed during audit")
    finally:
        os.close(fd)
        os.close(bundle_fd)
        os.close(here_fd)

    shard_manifest_sha = _hash_bytes(_canonical_value(shard_records))
    if shard_manifest_sha != PACKED_SHARD_MANIFEST_SHA256:
        raise VerificationError("packed source shard-manifest digest drift")
    evidence = {
        "record_bytes": RECORD_BYTES,
        "record_count": record_index,
        "file_bytes": SOURCE_BYTES,
        "packed_sorted_binary_sha256": full_digest.hexdigest(),
        "base_projection_sha256": projection_digest.hexdigest(),
        "sorted_semantic_sha256": semantic_digest.hexdigest(),
        "legacy_d5b_insertion_json_sha256": legacy_digest.hexdigest(),
        "d6_sorted_support_orbit_sha256": support_digest.hexdigest(),
        "positive_amplitudes": positive,
        "negative_amplitudes": negative,
        "zero_amplitudes": zero,
        "amplitude_sum": str(amplitude_sum),
        "maximum_absolute_amplitude_observed": max_abs,
        "maximum_absolute_amplitude_allowed": EXPECTED_PACKED[
            "maximum_absolute_amplitude_allowed"
        ],
        "orbit_size_histogram": orbit_histogram,
        "stabilizer_size_histogram": stabilizer_histogram,
        "orbit_coverage_sum": coverage,
        "first_representative_hex": hex(first if first is not None else 0),
        "last_representative_hex": hex(last if last is not None else 0),
        "nonzero_insertion_ranks": nonzero_ranks,
    }
    _require_strict_equal(evidence, EXPECTED_PACKED, "independent packed checkpoint audit")
    expected_contract = contract["packed_source"]["expected_checkpoint"]
    _require_strict_equal(evidence, expected_contract, "packed audit/contract")

    result_raw = _read_git_bound_repo_artifact(
        "fh_l8_packed_q3_checkpoint_d11_bundle/result.json",
        PACKED_C3,
        PACKED_ARTIFACTS[4]["bytes"],
        PACKED_ARTIFACTS[4]["sha256"],
        131072,
    )
    receipt_raw = _read_git_bound_repo_artifact(
        "fh_l8_packed_q3_checkpoint_d11_terminal_receipt.json",
        PACKED_C3,
        PACKED_ARTIFACTS[5]["bytes"],
        PACKED_ARTIFACTS[5]["sha256"],
        32768,
    )
    result = _load_json_bytes(result_raw)
    receipt = _load_json_bytes(receipt_raw)
    if (
        result.get("status")
        != "VERIFIED_D11_PACKED_DEPTH3_QUOTIENT_CHECKPOINT_MATERIALIZED_NO_Q4_AUTHORITY"
        or result.get("verified") is not True
        or result.get("checkpoint", {}).get("packed_sorted_binary_sha256")
        != evidence["packed_sorted_binary_sha256"]
        or result.get("checkpoint", {}).get("record_count") != SOURCE_RECORDS
        or result.get("authority", {}).get("depth3_to_depth4_execution_authorized")
        is not False
        or result.get("authority", {}).get(
            "depth3_to_depth4_quotient_hamiltonian_action_executed"
        )
        is not False
    ):
        raise VerificationError("packed result authority binding drift")
    terminal = receipt.get("runner_terminal_evidence", {})
    if (
        receipt.get("runner_exit_code") != 0
        or receipt.get("runner_stderr_bytes") != 0
        or receipt.get("contract_freeze_commit") != PACKED_C2
        or receipt.get("protocol_source_freeze_commit") != PACKED_C1
        or terminal.get("checkpoint_sha256")
        != EXPECTED_PACKED["packed_sorted_binary_sha256"]
        or terminal.get("result_sha256") != PACKED_ARTIFACTS[4]["sha256"]
    ):
        raise VerificationError("packed terminal receipt binding drift")
    return {
        "checkpoint": evidence,
        "source_shard_manifest": shard_records,
        "source_shard_manifest_sha256": shard_manifest_sha,
        "source_shards": len(shard_records),
        "packed_result_and_terminal_receipt_bound": True,
        "scientific_action_calls": 0,
    }


def _read_cgroup_impl() -> dict[str, Any]:
    def pseudo(path: Path, maximum: int) -> bytes:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            chunks: list[bytes] = []
            total = 0
            while True:
                raw = os.read(fd, min(4096, maximum + 1 - total))
                if not raw:
                    break
                chunks.append(raw)
                total += len(raw)
                if total > maximum:
                    raise ResourceIndeterminate(f"pseudo-file exceeds cap: {path}")
            return b"".join(chunks)
        finally:
            os.close(fd)

    lines = pseudo(Path("/proc/self/cgroup"), 65536).decode("ascii").splitlines()
    unified = [line.split("::", 1)[1] for line in lines if line.startswith("0::")]
    if len(unified) != 1:
        raise ResourceIndeterminate("unified cgroup v2 path unavailable")
    relative = unified[0].lstrip("/")
    directory = Path("/sys/fs/cgroup") / relative

    def finite(name: str) -> int:
        raw = pseudo(directory / name, 4096).decode("ascii").strip()
        if not raw.isdigit():
            raise ResourceIndeterminate(f"cgroup {name} is not finite")
        return int(raw)

    events: dict[str, int] = {}
    for line in pseudo(directory / "memory.events", 4096).decode("ascii").splitlines():
        fields = line.split()
        if len(fields) != 2 or not fields[1].isdigit():
            raise ResourceIndeterminate("malformed memory.events")
        events[fields[0]] = int(fields[1])
    names = {"low", "high", "max", "oom", "oom_kill", "oom_group_kill"}
    if not names <= set(events):
        raise ResourceIndeterminate("incomplete memory.events")
    process_ids = {
        int(line)
        for line in pseudo(directory / "cgroup.procs", 1_048_576)
        .decode("ascii")
        .splitlines()
        if line.isdigit()
    }
    memory_current = finite("memory.current")
    memory_peak = finite("memory.peak")
    swap_current = finite("memory.swap.current")
    return {
        "path": "/" + relative,
        "memory_max_bytes": finite("memory.max"),
        "memory_high_bytes": finite("memory.high"),
        "memory_swap_max_bytes": finite("memory.swap.max"),
        "memory_peak_bytes": memory_peak,
        "memory_current_bytes": memory_current,
        "memory_swap_current_bytes": swap_current,
        "memory_events": {name: events[name] for name in sorted(names)},
        "self_pid_listed": os.getpid() in process_ids,
    }


def _read_cgroup() -> dict[str, Any]:
    try:
        return _read_cgroup_impl()
    except ResourceIndeterminate:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ResourceIndeterminate(f"cgroup evidence unavailable: {exc}") from exc


def _check_cgroup(cgroup: Mapping[str, Any], limits: Mapping[str, Any], initial: bool) -> None:
    if (
        cgroup["memory_max_bytes"] != limits["outer_memory_max_bytes"]
        or cgroup["memory_high_bytes"] != limits["outer_memory_high_bytes"]
        or cgroup["memory_swap_max_bytes"] != limits["outer_swap_max_bytes"]
        or cgroup["memory_swap_current_bytes"] != 0
        or cgroup["self_pid_listed"] is not True
        or not cgroup["path"].endswith(".scope")
        or (initial and any(cgroup["memory_events"].values()))
        or cgroup["memory_peak_bytes"]
        > (
            limits["max_initial_cgroup_peak_bytes"]
            if initial
            else limits["max_cgroup_peak_bytes"]
        )
    ):
        raise ResourceIndeterminate("cgroup envelope drift")


def _deadline_check(deadline_ns: int) -> None:
    if time.monotonic_ns() > deadline_ns:
        raise ResourceIndeterminate("external forensic audit exceeded internal deadline")


def _stream_range(
    fd: int,
    offset: int,
    length: int,
    deadline_ns: int,
    aggregate_hashes: Iterable[Any] = (),
) -> str:
    digest = hashlib.sha256()
    remaining = length
    cursor = offset
    while remaining:
        _deadline_check(deadline_ns)
        raw = os.pread(fd, min(READ_CHUNK, remaining), cursor)
        if not raw:
            raise ResourceIndeterminate("short external spool read")
        digest.update(raw)
        for aggregate in aggregate_hashes:
            aggregate.update(raw)
        cursor += len(raw)
        remaining -= len(raw)
        if hasattr(os, "posix_fadvise") and hasattr(os, "POSIX_FADV_DONTNEED"):
            os.posix_fadvise(fd, cursor - len(raw), len(raw), os.POSIX_FADV_DONTNEED)
    return digest.hexdigest()


def _validate_source_manifest(value: Mapping[str, Any]) -> None:
    _require_exact_keys(
        value,
        {"contract_id", "record_bytes", "record_count", "payload_sha256", "shards", "complete"},
        "legacy source manifest",
    )
    if (
        value["contract_id"] != "FH-L8-INDEPENDENT-REFERENCE-D11"
        or type(value["record_bytes"]) is not int
        or type(value["record_count"]) is not int
        or value["record_bytes"] != RECORD_BYTES
        or value["record_count"] != SOURCE_RECORDS
        or value["payload_sha256"] != EXPECTED_EXTERNAL["source_checkpoint_sha256"]
        or value["complete"] is not True
        or not isinstance(value["shards"], list)
        or len(value["shards"]) != SOURCE_SHARDS
    ):
        raise VerificationError("legacy source manifest identity drift")
    for index, shard in enumerate(value["shards"]):
        _require_exact_keys(shard, {"index", "records", "sha256"}, "legacy source shard")
        expected_records = SOURCE_SHARD_SIZE if index < 52 else 107
        if (
            type(shard["index"]) is not int
            or type(shard["records"]) is not int
            or shard["index"] != index
            or shard["records"] != expected_records
            or not isinstance(shard["sha256"], str)
            or SHA64_RE.fullmatch(shard["sha256"]) is None
        ):
            raise VerificationError("legacy source shard manifest drift")


def _load_external_receipts(
    checks_fd: int, maximum_bytes: int
) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]], str]:
    expected_names = {f"shard-{index:03d}.json" for index in range(SOURCE_SHARDS)}
    initial_inventory = _directory_inventory(checks_fd, expected_names)
    receipt_manifest: list[dict[str, Any]] = []
    by_partition: dict[int, list[dict[str, Any]]] = {index: [] for index in range(PARTITIONS)}
    for shard_index in range(SOURCE_SHARDS):
        name = f"shard-{shard_index:03d}.json"
        raw = _read_member(checks_fd, name, maximum_bytes)
        value = _load_json_bytes(raw)
        _require_exact_keys(
            value,
            {
                "shard",
                "source_start",
                "source_records",
                "reduced_columns",
                "projected_zero",
                "chunks",
                "complete",
            },
            "external shard receipt",
        )
        expected_records = SOURCE_SHARD_SIZE if shard_index < 52 else 107
        if (
            type(value["shard"]) is not int
            or type(value["source_start"]) is not int
            or type(value["source_records"]) is not int
            or value["shard"] != shard_index
            or value["source_start"] != shard_index * SOURCE_SHARD_SIZE
            or value["source_records"] != expected_records
            or type(value["reduced_columns"]) is not int
            or value["reduced_columns"] < 0
            or type(value["projected_zero"]) is not int
            or value["projected_zero"] < 0
            or value["complete"] is not True
            or not isinstance(value["chunks"], list)
            or len(value["chunks"]) != PARTITIONS
        ):
            raise VerificationError("external shard receipt identity drift")
        seen: set[int] = set()
        chunk_records = 0
        for chunk in value["chunks"]:
            _require_exact_keys(
                chunk,
                {"partition", "offset", "bytes", "records", "sha256"},
                "external receipt chunk",
            )
            partition = _require_int(chunk["partition"], "partition")
            offset = _require_int(chunk["offset"], "chunk offset")
            byte_count = _require_int(chunk["bytes"], "chunk bytes", 1)
            records = _require_int(chunk["records"], "chunk records", 1)
            digest = _require_sha(chunk["sha256"], "chunk sha256")
            if (
                partition >= PARTITIONS
                or partition in seen
                or offset % RECORD_BYTES
                or byte_count != records * RECORD_BYTES
            ):
                raise VerificationError("external receipt chunk layout drift")
            seen.add(partition)
            chunk_records += records
            by_partition[partition].append(
                {
                    "partition": partition,
                    "shard": shard_index,
                    "offset": offset,
                    "bytes": byte_count,
                    "records": records,
                    "sha256": digest,
                }
            )
        if seen != set(range(PARTITIONS)) or chunk_records != value["reduced_columns"]:
            raise VerificationError("external receipt partition coverage drift")
        receipt_manifest.append(
            {
                "name": name,
                "bytes": len(raw),
                "sha256": _hash_bytes(raw),
                "shard": shard_index,
                "source_start": value["source_start"],
                "source_records": value["source_records"],
                "reduced_columns": value["reduced_columns"],
                "projected_zero": value["projected_zero"],
            }
        )
    if _directory_inventory(checks_fd, expected_names) != initial_inventory:
        raise ExternalCustodyIndeterminate("external receipt directory changed during audit")
    return receipt_manifest, by_partition, _hash_bytes(_canonical_json(receipt_manifest))


def _audit_external_custody_impl(
    contract: Mapping[str, Any],
    source_root: Path,
    run_root: Path,
    deadline_ns: int,
) -> dict[str, Any]:
    forensic = contract["external_forensic"]
    limits = contract["resource_limits"]
    if source_root != Path(forensic["source_root"]) or run_root != Path(forensic["run_root"]):
        raise VerificationError("external audit root override is not contract-bound")

    source_fd = _open_directory_nofollow(source_root)
    try:
        source_root_identity = _stat_identity(os.fstat(source_fd))
        source_names = {"depth3-source.bin", "depth3-source.manifest.json"}
        source_inventory = _directory_inventory(source_fd, source_names)
        source_manifest_raw = _read_member(
            source_fd, "depth3-source.manifest.json", 131072
        )
        source_manifest = _load_json_bytes(source_manifest_raw)
        _validate_source_manifest(source_manifest)
        if _hash_bytes(source_manifest_raw) != EXPECTED_EXTERNAL["source_manifest_sha256"]:
            raise VerificationError("external source manifest raw digest drift")
        payload_fd = os.open(
            "depth3-source.bin", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=source_fd
        )
        try:
            source_before = os.fstat(payload_fd)
            if (
                not stat.S_ISREG(source_before.st_mode)
                or source_before.st_size != SOURCE_BYTES
                or _stat_identity(source_before) != source_inventory["depth3-source.bin"]
            ):
                raise VerificationError("external source checkpoint type/size drift")
            source_digest = hashlib.sha256()
            source_cursor = 0
            for shard in source_manifest["shards"]:
                shard_bytes = shard["records"] * RECORD_BYTES
                shard_sha = _stream_range(
                    payload_fd,
                    source_cursor,
                    shard_bytes,
                    deadline_ns,
                    (source_digest,),
                )
                if shard_sha != shard["sha256"]:
                    raise VerificationError("legacy source shard payload digest drift")
                source_cursor += shard_bytes
            if source_cursor != SOURCE_BYTES:
                raise VerificationError("legacy source shard byte coverage drift")
            source_sha = source_digest.hexdigest()
            source_after = os.fstat(payload_fd)
            if (
                source_before.st_dev,
                source_before.st_ino,
                source_before.st_size,
                source_before.st_mtime_ns,
                source_before.st_ctime_ns,
            ) != (
                source_after.st_dev,
                source_after.st_ino,
                source_after.st_size,
                source_after.st_mtime_ns,
                source_after.st_ctime_ns,
            ):
                raise ResourceIndeterminate("external source changed during audit")
        finally:
            os.close(payload_fd)
        if _directory_inventory(source_fd, source_names) != source_inventory:
            raise ExternalCustodyIndeterminate("external source directory changed during audit")
        source_probe = _open_directory_nofollow(source_root)
        try:
            if _stat_identity(os.fstat(source_probe)) != source_root_identity:
                raise ExternalCustodyIndeterminate("external source root path was replaced")
        finally:
            os.close(source_probe)
    finally:
        os.close(source_fd)
    if source_sha != EXPECTED_EXTERNAL["source_checkpoint_sha256"]:
        raise VerificationError("external source checkpoint digest drift")

    run_fd = _open_directory_nofollow(run_root)
    try:
        run_root_identity = _stat_identity(os.fstat(run_fd))
        run_names = {"full-checkpoints", "full-spool", "depth4-target.bin"}
        run_inventory = _directory_inventory(run_fd, run_names)
        checks_fd = os.open(
            "full-checkpoints",
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=run_fd,
        )
        spool_fd = os.open(
            "full-spool",
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=run_fd,
        )
        try:
            if (
                _stat_identity(os.fstat(checks_fd)) != run_inventory["full-checkpoints"]
                or _stat_identity(os.fstat(spool_fd)) != run_inventory["full-spool"]
            ):
                raise ExternalCustodyIndeterminate("external child directory identity drift")
            receipt_manifest, by_partition, receipt_set_sha = _load_external_receipts(
                checks_fd, limits["max_external_receipt_bytes_each"]
            )
            expected_spool_names = {f"p{index:03d}.bin" for index in range(PARTITIONS)}
            spool_inventory = _directory_inventory(spool_fd, expected_spool_names)
            preflight_spool_bytes = 0
            for name, identity in spool_inventory.items():
                mode = identity[2]
                size = identity[3]
                if (
                    not stat.S_ISREG(mode)
                    or size <= 0
                    or size % RECORD_BYTES
                    or size > limits["max_external_spool_bytes_each"]
                ):
                    raise VerificationError(f"external spool preflight drift: {name}")
                preflight_spool_bytes += size
            if (
                preflight_spool_bytes != EXPECTED_EXTERNAL["spool_bytes"]
                or preflight_spool_bytes > limits["max_external_spool_bytes_total"]
            ):
                raise VerificationError("external aggregate spool byte preflight drift")

            partition_manifest: list[dict[str, Any]] = []
            duplicate_histogram: dict[int, int] = {}
            total_certified_segments = 0
            total_certified_bytes = 0
            total_gap_count = 0
            total_gap_bytes = 0
            total_spool_bytes = 0
            total_duplicate_matches = 0
            all_chunk_hashes_verified = True
            overlap_count = 0
            trailing_bytes = 0
            global_spool_file_manifest = hashlib.sha256(b"[")
            global_gap_inventory = hashlib.sha256(b"[")
            gap_inventory_index = 0

            for partition in range(PARTITIONS):
                _deadline_check(deadline_ns)
                name = f"p{partition:03d}.bin"
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=spool_fd)
                try:
                    before = os.fstat(fd)
                    if (
                        not stat.S_ISREG(before.st_mode)
                        or before.st_size % RECORD_BYTES
                        or _stat_identity(before) != spool_inventory[name]
                    ):
                        raise VerificationError("external spool file type/size drift")
                    intervals = sorted(by_partition[partition], key=lambda item: item["offset"])
                    signature_map: dict[tuple[int, str], list[int]] = {}
                    for item in intervals:
                        signature_map.setdefault((item["bytes"], item["sha256"]), []).append(
                            item["shard"]
                        )
                    metadata_sha = _hash_bytes(_canonical_json(intervals))
                    file_digest = hashlib.sha256()
                    gap_digest = hashlib.sha256(b"[")
                    cursor = 0
                    partition_certified_bytes = 0
                    partition_gap_bytes = 0
                    partition_gap_count = 0
                    partition_duplicate_matches = 0
                    for item in intervals:
                        offset = item["offset"]
                        end = offset + item["bytes"]
                        if offset < cursor:
                            overlap_count += 1
                            raise VerificationError("external receipt intervals overlap")
                        if offset > cursor:
                            gap_length = offset - cursor
                            gap_sha = _stream_range(
                                fd, cursor, gap_length, deadline_ns, (file_digest,)
                            )
                            matches = signature_map.get((gap_length, gap_sha), [])
                            if len(matches) != 1:
                                raise VerificationError("external gap is not a unique duplicate chunk")
                            matched_shard = matches[0]
                            duplicate_histogram[matched_shard] = (
                                duplicate_histogram.get(matched_shard, 0) + 1
                            )
                            gap_row = {
                                "partition": partition,
                                "offset": cursor,
                                "bytes": gap_length,
                                "sha256": gap_sha,
                                "matches_shard": matched_shard,
                            }
                            if partition_gap_count:
                                gap_digest.update(b",")
                            gap_digest.update(_json_item(gap_row))
                            if gap_inventory_index:
                                global_gap_inventory.update(b",")
                            global_gap_inventory.update(_json_item(gap_row))
                            gap_inventory_index += 1
                            partition_gap_count += 1
                            partition_gap_bytes += gap_length
                            partition_duplicate_matches += 1
                        chunk_sha = _stream_range(
                            fd, offset, item["bytes"], deadline_ns, (file_digest,)
                        )
                        if chunk_sha != item["sha256"]:
                            all_chunk_hashes_verified = False
                            raise VerificationError("receipt-bound chunk digest drift")
                        partition_certified_bytes += item["bytes"]
                        cursor = end
                    if cursor < before.st_size:
                        trailing = before.st_size - cursor
                        trailing_bytes += trailing
                        gap_sha = _stream_range(
                            fd, cursor, trailing, deadline_ns, (file_digest,)
                        )
                        raise VerificationError(
                            f"unclassified trailing spool bytes: {partition}:{gap_sha}"
                        )
                    if cursor > before.st_size:
                        raise VerificationError("receipt interval exceeds spool file")
                    gap_digest.update(b"]")
                    after = os.fstat(fd)
                    identity_before = (
                        before.st_dev,
                        before.st_ino,
                        before.st_mode,
                        before.st_size,
                        before.st_mtime_ns,
                        before.st_ctime_ns,
                    )
                    identity_after = (
                        after.st_dev,
                        after.st_ino,
                        after.st_mode,
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    )
                    if identity_before != identity_after:
                        raise ResourceIndeterminate("external spool changed during audit")
                finally:
                    os.close(fd)
                row = {
                    "partition": partition,
                    "name": name,
                    "file_bytes": before.st_size,
                    "file_records": before.st_size // RECORD_BYTES,
                    "file_sha256": file_digest.hexdigest(),
                    "certified_segments": len(intervals),
                    "certified_bytes": partition_certified_bytes,
                    "gap_count": partition_gap_count,
                    "gap_bytes": partition_gap_bytes,
                    "duplicate_gap_matches": partition_duplicate_matches,
                    "certified_metadata_sha256": metadata_sha,
                    "gap_inventory_sha256": gap_digest.hexdigest(),
                }
                if partition:
                    global_spool_file_manifest.update(b",")
                global_spool_file_manifest.update(_json_item(row))
                partition_manifest.append(row)
                total_certified_segments += len(intervals)
                total_certified_bytes += partition_certified_bytes
                total_gap_count += partition_gap_count
                total_gap_bytes += partition_gap_bytes
                total_spool_bytes += before.st_size
                total_duplicate_matches += partition_duplicate_matches
            global_spool_file_manifest.update(b"]")
            global_gap_inventory.update(b"]")
            if _directory_inventory(spool_fd, expected_spool_names) != spool_inventory:
                raise ExternalCustodyIndeterminate("external spool directory changed during audit")
        finally:
            os.close(checks_fd)
            os.close(spool_fd)

        target_fd = os.open(
            "depth4-target.bin", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=run_fd
        )
        try:
            target_before = os.fstat(target_fd)
            if (
                not stat.S_ISREG(target_before.st_mode)
                or target_before.st_size != EXPECTED_EXTERNAL["target_bytes"]
                or target_before.st_size > limits["max_external_target_bytes"]
                or _stat_identity(target_before) != run_inventory["depth4-target.bin"]
            ):
                raise VerificationError("legacy target type/size drift")
            target_sha = _stream_range(
                target_fd, 0, target_before.st_size, deadline_ns
            )
            target_after = os.fstat(target_fd)
            if (
                target_before.st_dev,
                target_before.st_ino,
                target_before.st_size,
                target_before.st_mtime_ns,
                target_before.st_ctime_ns,
            ) != (
                target_after.st_dev,
                target_after.st_ino,
                target_after.st_size,
                target_after.st_mtime_ns,
                target_after.st_ctime_ns,
            ):
                raise ResourceIndeterminate("legacy target changed during audit")
        finally:
            os.close(target_fd)
        if _directory_inventory(run_fd, run_names) != run_inventory:
            raise ExternalCustodyIndeterminate("external run directory changed during audit")
        run_probe = _open_directory_nofollow(run_root)
        try:
            if _stat_identity(os.fstat(run_probe)) != run_root_identity:
                raise ExternalCustodyIndeterminate("external run root path was replaced")
        finally:
            os.close(run_probe)
    finally:
        os.close(run_fd)

    duplicate_shards = sorted(duplicate_histogram)
    aggregates = {
        "receipt_count": len(receipt_manifest),
        "partition_count": len(partition_manifest),
        "record_bytes": RECORD_BYTES,
        "certified_segment_count": total_certified_segments,
        "certified_records": total_certified_bytes // RECORD_BYTES,
        "certified_bytes": total_certified_bytes,
        "spool_records": total_spool_bytes // RECORD_BYTES,
        "spool_bytes": total_spool_bytes,
        "gap_count": total_gap_count,
        "gap_records": total_gap_bytes // RECORD_BYTES,
        "gap_bytes": total_gap_bytes,
        "duplicate_gap_matches": total_duplicate_matches,
        "duplicate_shards": duplicate_shards,
        "duplicate_source_start": min(duplicate_shards) * SOURCE_SHARD_SIZE,
        "duplicate_source_end_inclusive":
            max(duplicate_shards) * SOURCE_SHARD_SIZE + SOURCE_SHARD_SIZE - 1,
        "target_records": target_before.st_size // RECORD_BYTES,
        "target_bytes": target_before.st_size,
        "target_sha256": target_sha,
        "source_checkpoint_sha256": source_sha,
        "source_manifest_sha256": _hash_bytes(source_manifest_raw),
    }
    if aggregates != EXPECTED_EXTERNAL:
        raise VerificationError("external forensic aggregate drift")
    if duplicate_histogram != {index: PARTITIONS for index in range(25, 52)}:
        raise VerificationError("duplicate shard/partition histogram drift")
    if not all_chunk_hashes_verified or overlap_count or trailing_bytes:
        raise VerificationError("external custody validation flags drift")

    manifest = {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "source_root": str(source_root),
        "run_root": str(run_root),
        "source_checkpoint": {
            "bytes": SOURCE_BYTES,
            "sha256": source_sha,
            "manifest_bytes": len(source_manifest_raw),
            "manifest_sha256": _hash_bytes(source_manifest_raw),
        },
        "receipt_set": {
            "receipts": receipt_manifest,
            "receipt_set_sha256": receipt_set_sha,
        },
        "spool": {
            "partitions": partition_manifest,
            "partition_manifest_sha256": global_spool_file_manifest.hexdigest(),
            "gap_inventory_sha256": global_gap_inventory.hexdigest(),
            "duplicate_shard_partition_histogram": {
                str(key): value for key, value in sorted(duplicate_histogram.items())
            },
        },
        "target": {
            "bytes": target_before.st_size,
            "records": target_before.st_size // RECORD_BYTES,
            "sha256": target_sha,
        },
        "aggregates": aggregates,
        "all_receipt_chunk_hashes_verified": True,
        "all_gaps_are_unique_exact_duplicates_of_receipt_chunks": True,
        "intended_input_multiset": "shards_0_through_52_once",
        "observed_retained_spool_multiset": "shards_0_through_52_plus_duplicate_shards_25_through_51",
        "target_to_spool_provenance_proven": False,
        "scientific_action_calls": 0,
    }
    raw_manifest = _canonical_json(manifest)
    if len(raw_manifest) > limits["max_manifest_bytes"]:
        raise ResourceIndeterminate("forensic manifest exceeds byte cap")
    observed_digests = {
        "receipt_set_sha256": receipt_set_sha,
        "partition_manifest_sha256": global_spool_file_manifest.hexdigest(),
        "gap_inventory_sha256": global_gap_inventory.hexdigest(),
        "manifest_sha256": _hash_bytes(_canonical_value(manifest)),
    }
    _require_strict_equal(
        observed_digests, EXPECTED_FORENSIC_DIGESTS, "external forensic digests"
    )
    return manifest


def audit_external_custody(
    contract: Mapping[str, Any],
    source_root: Path,
    run_root: Path,
    deadline_ns: int,
) -> dict[str, Any]:
    forensic = contract["external_forensic"]
    if source_root != Path(forensic["source_root"]) or run_root != Path(
        forensic["run_root"]
    ):
        raise VerificationError("external audit root override is not contract-bound")
    try:
        return _audit_external_custody_impl(
            contract, source_root, run_root, deadline_ns
        )
    except (ExternalCustodyIndeterminate, ResourceIndeterminate):
        raise
    except (OSError, VerificationError, KeyError, TypeError, ValueError) as exc:
        raise ExternalCustodyIndeterminate(
            f"retained external custody could not be reproduced: {exc}"
        ) from exc


def verify_conditional_cost_evidence(contract: Mapping[str, Any]) -> dict[str, Any]:
    full_spill = _load_json_bytes(
        _read_git_bound_repo_artifact(
            "fh_l8_d11_full_spill_receipt.json",
            PARALLEL_FULL_COMMIT,
            PARALLEL_ARTIFACTS[5]["bytes"],
            PARALLEL_ARTIFACTS[5]["sha256"],
            32768,
        )
    )
    full_result = _load_json_bytes(
        _read_git_bound_repo_artifact(
            "fh_l8_d11_full_action_result.json",
            PARALLEL_FULL_COMMIT,
            PARALLEL_ARTIFACTS[6]["bytes"],
            PARALLEL_ARTIFACTS[6]["sha256"],
            32768,
        )
    )
    d12_contract = _load_json_bytes(
        _read_git_bound_repo_artifact(
            "fh_l8_q4_to_q5_cost_d12_contract.json",
            D12_COMMIT,
            D12_ARTIFACTS[1]["bytes"],
            D12_ARTIFACTS[1]["sha256"],
            32768,
        )
    )
    d12_result = _load_json_bytes(
        _read_git_bound_repo_artifact(
            "fh_l8_q4_to_q5_cost_d12_result.json",
            D12_COMMIT,
            D12_ARTIFACTS[2]["bytes"],
            D12_ARTIFACTS[2]["sha256"],
            32768,
        )
    )
    if (
        full_spill.get("completed_shards") != 53
        or full_spill.get("new_spill_records") != EXPECTED_EXTERNAL["gap_records"]
        or full_result.get("target_records") != EXPECTED_COSTS["q4_sources_reported"]
        or full_result.get("target_sha256") != EXPECTED_EXTERNAL["target_sha256"]
    ):
        raise VerificationError("legacy full-action scalar observations drift")
    q4 = full_result["target_records"]
    raw = q4 * 225
    candidate_images = raw * 8
    source_images = q4 * 8
    total_images = candidate_images + source_images
    costs = {
        "q4_sources_reported": q4,
        "raw_candidate_upper_bound": raw,
        "candidate_group_image_upper_bound": candidate_images,
        "source_group_image_upper_bound": source_images,
        "total_group_image_upper_bound": total_images,
        "byte_table_lookup_upper_bound": total_images * 16,
        "primary_spill_bytes_upper_bound": raw * 32,
    }
    if costs != EXPECTED_COSTS or costs != contract["downstream_d12"]["reported_costs"]:
        raise VerificationError("conditional cost arithmetic drift")
    d12_reported = dict(d12_result.get("costs", {}))
    if d12_reported != {
        "q4_sources": q4,
        "raw_candidate_upper_bound": raw,
        "candidate_group_image_upper_bound": candidate_images,
        "source_group_image_upper_bound": source_images,
        "total_group_image_upper_bound": total_images,
        "primary_spill_bytes_upper_bound": raw * 32,
    }:
        raise VerificationError("D12 retained cost result drift")
    declared_caps = d12_contract.get("current_d10_caps")
    if declared_caps != {
        "max_raw_candidate_actions": 47947275,
        "max_total_group_images": 385282992,
        "max_cumulative_spill_write_bytes": 8589934592,
        "max_live_algorithm_buffer_bytes": 134217728,
    }:
        raise VerificationError("D12 declared cap block drift")
    d7 = _load_json_bytes(
        _read_git_bound_repo_artifact(
            "fh_l8_depth3_to_depth4_quotient_h_design_gate_contract.json",
            D12_MERGE_COMMIT,
            CAP_ARTIFACTS[0]["bytes"],
            CAP_ARTIFACTS[0]["sha256"],
            1_048_576,
        )
    )
    d10 = _load_json_bytes(
        _read_git_bound_repo_artifact(
            "fh_l8_cgroup_envelope_d10_contract.json",
            D12_MERGE_COMMIT,
            CAP_ARTIFACTS[1]["bytes"],
            CAP_ARTIFACTS[1]["sha256"],
            32768,
        )
    )
    d7_caps = d7.get("future_runner_planning_caps", {})
    if (
        declared_caps["max_raw_candidate_actions"] != d7_caps.get("max_raw_candidate_actions")
        or declared_caps["max_total_group_images"] != d7_caps.get("max_total_group_images")
        or declared_caps["max_cumulative_spill_write_bytes"]
        != d7_caps.get("max_cumulative_spill_write_bytes")
        or declared_caps["max_live_algorithm_buffer_bytes"]
        != d7_caps.get("max_live_algorithm_buffer_bytes")
    ):
        raise VerificationError("D12 caps do not match D7 planning provenance")
    if "current_d10_caps" in d10 or "max_raw_candidate_actions" in d10:
        raise VerificationError("D10 unexpectedly supplies D7 planning caps")
    return {
        "reported_costs_recomputed_exactly": costs,
        "costs_are_conditional_on_quarantined_q4_count": True,
        "D12_checker_contract_result_first_appeared_together": True,
        "declared_current_d10_caps_are_actually_D7_planning_caps": True,
        "D10_scope_is_cgroup_and_bounded_4096_preflight_only": True,
        "source_file_bytes_vs_live_buffer_is_not_a_streaming_no_go": True,
        "D12_scientific_authority": False,
        "D12_disposition": "SUPERSEDED_INVALID_INPUT_NO_SCIENTIFIC_AUTHORITY",
    }


def _resource_record(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    limits: Mapping[str, Any],
    started_ns: int,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        before["path"] != after["path"]
        or before["self_pid_listed"] is not True
        or after["self_pid_listed"] is not True
        or after["memory_peak_bytes"] < before["memory_peak_bytes"]
    ):
        raise ResourceIndeterminate("cgroup membership changed during forensic audit")
    event_names = {"low", "high", "max", "oom", "oom_kill", "oom_group_kill"}
    delta = {
        name: after["memory_events"][name] - before["memory_events"][name]
        for name in sorted(event_names)
    }
    if any(value != 0 for value in delta.values()):
        raise ResourceIndeterminate("cgroup memory event occurred during forensic audit")
    rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    if (
        rss_bytes > limits["max_process_peak_rss_bytes"]
        or after["memory_peak_bytes"] > limits["max_cgroup_peak_bytes"]
        or after["memory_swap_current_bytes"] != 0
    ):
        raise ResourceIndeterminate("forensic audit exceeded resource cap")
    external_read_bytes = (
        SOURCE_BYTES
        + manifest["aggregates"]["spool_bytes"]
        + manifest["target"]["bytes"]
        + sum(item["bytes"] for item in manifest["receipt_set"]["receipts"])
        + manifest["source_checkpoint"]["manifest_bytes"]
    )
    elapsed_ns = time.monotonic_ns() - started_ns
    if elapsed_ns > limits["internal_deadline_seconds"] * 1_000_000_000:
        raise ResourceIndeterminate("forensic audit exceeded internal deadline")
    return {
        "cgroup_v2_enforced": True,
        "cgroup_path": after["path"],
        "self_pid_listed": after["self_pid_listed"],
        "fresh_scope_initial_events_zero": not any(before["memory_events"].values()),
        "memory_max_bytes": after["memory_max_bytes"],
        "memory_high_bytes": after["memory_high_bytes"],
        "memory_swap_max_bytes": after["memory_swap_max_bytes"],
        "initial_memory_peak_bytes": before["memory_peak_bytes"],
        "memory_peak_at_snapshot_bytes": after["memory_peak_bytes"],
        "memory_current_at_snapshot_bytes": after["memory_current_bytes"],
        "swap_current_at_snapshot_bytes": after["memory_swap_current_bytes"],
        "memory_events_before": before["memory_events"],
        "memory_events_at_snapshot": after["memory_events"],
        "memory_events_delta": delta,
        "process_max_rss_bytes": rss_bytes,
        "elapsed_monotonic_ns": elapsed_ns,
        "external_bytes_read": external_read_bytes,
        "read_chunk_bytes": limits["read_chunk_bytes"],
        "scientific_action_calls": 0,
        "scope_ends_before_result_serialization_and_publication": True,
        "within_frozen_caps": True,
    }


def build_result(
    protocol: Mapping[str, Any],
    source_git: Mapping[str, Any],
    packed: Mapping[str, Any],
    manifest: Mapping[str, Any],
    conditional_cost: Mapping[str, Any],
    resources: Mapping[str, Any],
) -> dict[str, Any]:
    aggregates = manifest["aggregates"]
    if aggregates != EXPECTED_EXTERNAL or aggregates["gap_records"] <= 0:
        raise VerificationError("forensic decision input drift")
    # The second clause above is deliberately a positivity/type gate; exact byte/record
    # identities are checked by equality with EXPECTED_EXTERNAL.
    result = {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "status": STATUS,
        "verified": True,
        "protocol": dict(protocol),
        "source_git_audit": dict(source_git),
        "packed_source_audit": {
            "checkpoint": packed["checkpoint"],
            "source_shard_manifest_sha256": packed["source_shard_manifest_sha256"],
            "source_shards": packed["source_shards"],
            "packed_result_and_terminal_receipt_bound": packed[
                "packed_result_and_terminal_receipt_bound"
            ],
            "scientific_action_calls": 0,
        },
        "forensic_manifest": dict(manifest),
        "forensic_manifest_sha256": _hash_bytes(_canonical_value(manifest)),
        "legacy_full_action_disposition": {
            "reported_target_sha256": aggregates["target_sha256"],
            "reported_target_records": aggregates["target_records"],
            "intended_shards": "0..52_once",
            "observed_retained_spool": "0..52_plus_duplicate_25..51",
            "target_to_spool_provenance_proven": False,
            "duplicate_gap_count": aggregates["gap_count"],
            "duplicate_records": aggregates["gap_records"],
            "duplicate_bytes": aggregates["gap_bytes"],
            "all_duplicate_gaps_exactly_match_receipt_chunks": True,
            "scientific_validity": "REJECTED_BROKEN_PRODUCTION_CUSTODY_ASSOCIATED_SPOOL_CONTAMINATED",
            "target_quarantined": True,
        },
        "downstream_D12_disposition": dict(conditional_cost),
        "clean_reexecution_protocol_frozen": True,
        "forensic_read_resource_observations": dict(resources),
        "publication_scope": {
            "single_result_artifact": True,
            "staged_payload_fsync_and_rehash_before_no_replace_link": True,
            "result_is_terminal_execution_or_resource_receipt": False,
            "publication_resource_usage_attested": False,
        },
        "authority": EXPECTED_AUTHORITY,
        "limitations": EXPECTED_LIMITATIONS,
        "next_gate": NEXT_GATE,
    }
    raw = _canonical_json(result)
    if len(raw) > 262144:
        raise ResourceIndeterminate("D16 result exceeds byte cap")
    return result


def _publish_forensic_result_impl(result_raw: bytes, maximum: int) -> None:
    if len(result_raw) > maximum:
        raise ResourceIndeterminate("forensic result payload exceeds frozen cap")
    directory_fd = _open_directory_nofollow(HERE)
    token = f"{os.getpid()}-{time.monotonic_ns()}"
    staging = f".{RESULT_NAME}.{token}.staging"
    staged_identity: tuple[int, int] | None = None
    published = False
    try:
        try:
            os.stat(RESULT_NAME, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ResourceIndeterminate("stale/concurrent D16 forensic result exists")
        fd = os.open(
            staging,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        try:
            view = memoryview(result_raw)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise ResourceIndeterminate("short D16 forensic result write")
                view = view[written:]
            os.fsync(fd)
            info = os.fstat(fd)
            staged_identity = (info.st_dev, info.st_ino)
            if info.st_size != len(result_raw):
                raise ResourceIndeterminate("staged D16 forensic result size drift")
        finally:
            os.close(fd)
        if _read_member(directory_fd, staging, maximum, len(result_raw)) != result_raw:
            raise ResourceIndeterminate("staged D16 forensic result rehash drift")
        os.fsync(directory_fd)
        try:
            os.link(
                staging,
                RESULT_NAME,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise ResourceIndeterminate(
                "concurrent D16 forensic result publication"
            ) from exc
        published = True
        os.fsync(directory_fd)
        final_info = os.stat(RESULT_NAME, dir_fd=directory_fd, follow_symlinks=False)
        if (
            staged_identity is None
            or (final_info.st_dev, final_info.st_ino) != staged_identity
            or _read_member(directory_fd, RESULT_NAME, maximum, len(result_raw))
            != result_raw
        ):
            raise ResourceIndeterminate("published D16 forensic result identity drift")
        os.unlink(staging, dir_fd=directory_fd)
        os.fsync(directory_fd)
    except Exception:
        if published:
            try:
                info = os.stat(RESULT_NAME, dir_fd=directory_fd, follow_symlinks=False)
                if staged_identity is not None and (info.st_dev, info.st_ino) == staged_identity:
                    os.unlink(RESULT_NAME, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        try:
            os.unlink(staging, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        os.fsync(directory_fd)
        raise
    finally:
        os.close(directory_fd)


def _publish_forensic_result(result_raw: bytes, maximum: int) -> None:
    try:
        _publish_forensic_result_impl(result_raw, maximum)
    except ResourceIndeterminate:
        raise
    except OSError as exc:
        raise ResourceIndeterminate(f"D16 result publication failed: {exc}") from exc


def execute_audit(
    contract: Mapping[str, Any],
    contract_commit: str,
    source_root: Path,
    run_root: Path,
) -> dict[str, Any]:
    started_ns = time.monotonic_ns()
    limits = contract["resource_limits"]
    before = _read_cgroup()
    _check_cgroup(before, limits, initial=True)
    deadline_ns = started_ns + limits["internal_deadline_seconds"] * 1_000_000_000
    protocol = verify_protocol(contract, contract_commit)
    source_git = verify_source_git(contract)
    packed = audit_packed_checkpoint(contract)
    conditional = verify_conditional_cost_evidence(contract)
    manifest = audit_external_custody(
        contract, source_root, run_root, deadline_ns
    )
    after = _read_cgroup()
    _check_cgroup(after, limits, initial=False)
    resources = _resource_record(before, after, limits, started_ns, manifest)
    result = build_result(protocol, source_git, packed, manifest, conditional, resources)
    result_raw = _canonical_json(result)
    _publish_forensic_result(result_raw, limits["max_result_bytes"])
    return result


def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    _require_exact_keys(
        manifest,
        {
            "schema_version",
            "contract_id",
            "source_root",
            "run_root",
            "source_checkpoint",
            "receipt_set",
            "spool",
            "target",
            "aggregates",
            "all_receipt_chunk_hashes_verified",
            "all_gaps_are_unique_exact_duplicates_of_receipt_chunks",
            "intended_input_multiset",
            "observed_retained_spool_multiset",
            "target_to_spool_provenance_proven",
            "scientific_action_calls",
        },
        "forensic manifest",
    )
    if (
        manifest["schema_version"] != 1
        or type(manifest["schema_version"]) is not int
        or manifest["contract_id"] != CONTRACT_ID
        or manifest["source_root"] != str(DEFAULT_SOURCE_ROOT)
        or manifest["run_root"] != str(DEFAULT_RUN_ROOT)
        or manifest["all_receipt_chunk_hashes_verified"] is not True
        or manifest["all_gaps_are_unique_exact_duplicates_of_receipt_chunks"] is not True
        or manifest["intended_input_multiset"] != "shards_0_through_52_once"
        or manifest["observed_retained_spool_multiset"]
        != "shards_0_through_52_plus_duplicate_shards_25_through_51"
        or manifest["target_to_spool_provenance_proven"] is not False
        or manifest["scientific_action_calls"] != 0
        or type(manifest["scientific_action_calls"]) is not int
    ):
        raise VerificationError("forensic manifest identity drift")
    source = manifest["source_checkpoint"]
    _require_strict_equal(source, {
        "bytes": SOURCE_BYTES,
        "sha256": EXPECTED_EXTERNAL["source_checkpoint_sha256"],
        "manifest_bytes": 5701,
        "manifest_sha256": EXPECTED_EXTERNAL["source_manifest_sha256"],
    }, "forensic source manifest")
    receipts = manifest["receipt_set"]
    _require_exact_keys(receipts, {"receipts", "receipt_set_sha256"}, "receipt set")
    if not isinstance(receipts["receipts"], list) or len(receipts["receipts"]) != SOURCE_SHARDS:
        raise VerificationError("forensic receipt count drift")
    for index, item in enumerate(receipts["receipts"]):
        _require_exact_keys(
            item,
            {
                "name",
                "bytes",
                "sha256",
                "shard",
                "source_start",
                "source_records",
                "reduced_columns",
                "projected_zero",
            },
            "forensic receipt identity",
        )
        if (
            item["name"] != f"shard-{index:03d}.json"
            or any(
                type(item[key]) is not int
                for key in (
                    "bytes",
                    "shard",
                    "source_start",
                    "source_records",
                    "reduced_columns",
                    "projected_zero",
                )
            )
            or item["shard"] != index
            or item["source_start"] != index * SOURCE_SHARD_SIZE
            or item["source_records"] != (SOURCE_SHARD_SIZE if index < 52 else 107)
            or not 0 < item["bytes"] <= 131072
            or not isinstance(item["sha256"], str)
            or SHA64_RE.fullmatch(item["sha256"]) is None
            or item["reduced_columns"] < 0
            or item["projected_zero"] < 0
        ):
            raise VerificationError("forensic receipt identity drift")
    if (
        receipts["receipt_set_sha256"]
        != _hash_bytes(_canonical_json(receipts["receipts"]))
        or receipts["receipt_set_sha256"]
        != EXPECTED_FORENSIC_DIGESTS["receipt_set_sha256"]
    ):
        raise VerificationError("forensic receipt-set digest drift")

    spool = manifest["spool"]
    _require_exact_keys(
        spool,
        {
            "partitions",
            "partition_manifest_sha256",
            "gap_inventory_sha256",
            "duplicate_shard_partition_histogram",
        },
        "forensic spool",
    )
    if not isinstance(spool["partitions"], list) or len(spool["partitions"]) != PARTITIONS:
        raise VerificationError("forensic partition count drift")
    partition_digest = hashlib.sha256(b"[")
    totals = {
        "file_bytes": 0,
        "file_records": 0,
        "certified_segments": 0,
        "certified_bytes": 0,
        "gap_count": 0,
        "gap_bytes": 0,
        "duplicate_gap_matches": 0,
    }
    for index, item in enumerate(spool["partitions"]):
        _require_exact_keys(
            item,
            {
                "partition",
                "name",
                "file_bytes",
                "file_records",
                "file_sha256",
                "certified_segments",
                "certified_bytes",
                "gap_count",
                "gap_bytes",
                "duplicate_gap_matches",
                "certified_metadata_sha256",
                "gap_inventory_sha256",
            },
            "forensic partition",
        )
        if (
            item["partition"] != index
            or item["name"] != f"p{index:03d}.bin"
            or any(
                type(item[key]) is not int
                for key in (
                    "partition",
                    "file_bytes",
                    "file_records",
                    "certified_segments",
                    "certified_bytes",
                    "gap_count",
                    "gap_bytes",
                    "duplicate_gap_matches",
                )
            )
            or item["file_bytes"] <= 0
            or item["file_bytes"] % RECORD_BYTES
            or item["file_records"] != item["file_bytes"] // RECORD_BYTES
            or item["certified_segments"] != SOURCE_SHARDS
            or item["certified_bytes"] <= 0
            or item["certified_bytes"] % RECORD_BYTES
            or item["gap_count"] != 27
            or item["gap_bytes"] <= 0
            or item["gap_bytes"] % RECORD_BYTES
            or item["certified_bytes"] + item["gap_bytes"] != item["file_bytes"]
            or item["duplicate_gap_matches"] != item["gap_count"]
            or any(
                SHA64_RE.fullmatch(str(item[key])) is None
                for key in (
                    "file_sha256",
                    "certified_metadata_sha256",
                    "gap_inventory_sha256",
                )
            )
        ):
            raise VerificationError("forensic partition identity drift")
        if index:
            partition_digest.update(b",")
        partition_digest.update(_json_item(item))
        for key in totals:
            totals[key] += item[key]
    partition_digest.update(b"]")
    if (
        spool["partition_manifest_sha256"] != partition_digest.hexdigest()
        or spool["partition_manifest_sha256"]
        != EXPECTED_FORENSIC_DIGESTS["partition_manifest_sha256"]
    ):
        raise VerificationError("forensic partition manifest digest drift")
    if (
        _require_sha(spool["gap_inventory_sha256"], "gap inventory sha256")
        != EXPECTED_FORENSIC_DIGESTS["gap_inventory_sha256"]
    ):
        raise VerificationError("forensic gap inventory digest drift")
    _require_strict_equal(spool["duplicate_shard_partition_histogram"], {
        str(index): PARTITIONS for index in range(25, 52)
    }, "duplicate shard histogram")
    aggregates = manifest["aggregates"]
    _require_strict_equal(aggregates, EXPECTED_EXTERNAL, "forensic aggregate")
    if (
        totals["file_bytes"] != aggregates["spool_bytes"]
        or totals["file_records"] != aggregates["spool_records"]
        or totals["certified_segments"] != aggregates["certified_segment_count"]
        or totals["certified_bytes"] != aggregates["certified_bytes"]
        or totals["gap_count"] != aggregates["gap_count"]
        or totals["gap_bytes"] != aggregates["gap_bytes"]
        or totals["duplicate_gap_matches"] != aggregates["duplicate_gap_matches"]
    ):
        raise VerificationError("forensic partition aggregate disagreement")
    _require_strict_equal(manifest["target"], {
        "bytes": EXPECTED_EXTERNAL["target_bytes"],
        "records": EXPECTED_EXTERNAL["target_records"],
        "sha256": EXPECTED_EXTERNAL["target_sha256"],
    }, "forensic target identity")
    manifest_sha = _hash_bytes(_canonical_value(manifest))
    if manifest_sha != EXPECTED_FORENSIC_DIGESTS["manifest_sha256"]:
        raise VerificationError("forensic full-manifest digest drift")
    return {
        "manifest_sha256": manifest_sha,
        "duplicate_records": aggregates["gap_records"],
        "duplicate_bytes": aggregates["gap_bytes"],
        "duplicate_shards": aggregates["duplicate_shards"],
        "legacy_target_quarantined": True,
    }


def validate_result(
    result: Mapping[str, Any],
    raw_result: bytes,
    manifest: Mapping[str, Any],
    protocol: Mapping[str, Any],
    source_git: Mapping[str, Any],
    packed: Mapping[str, Any],
    conditional: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    _require_exact_keys(
        result,
        {
            "schema_version",
            "contract_id",
            "status",
            "verified",
            "protocol",
            "source_git_audit",
            "packed_source_audit",
            "forensic_manifest",
            "forensic_manifest_sha256",
            "legacy_full_action_disposition",
            "downstream_D12_disposition",
            "clean_reexecution_protocol_frozen",
            "forensic_read_resource_observations",
            "publication_scope",
            "authority",
            "limitations",
            "next_gate",
        },
        "D16 result",
    )
    if raw_result != _canonical_json(result):
        raise VerificationError("D16 output is not canonical JSON")
    if (
        type(result["schema_version"]) is not int
        or result["schema_version"] != 1
        or result["contract_id"] != CONTRACT_ID
        or result["status"] != STATUS
        or result["verified"] is not True
        or not _strict_equal(result["protocol"], protocol)
        or not _strict_equal(result["source_git_audit"], source_git)
        or not _strict_equal(result["downstream_D12_disposition"], conditional)
        or result["clean_reexecution_protocol_frozen"] is not True
        or not _strict_equal(result["authority"], EXPECTED_AUTHORITY)
        or not _strict_equal(result["authority"], contract["authority_ceiling"])
        or not _strict_equal(result["limitations"], EXPECTED_LIMITATIONS)
        or result["next_gate"] != NEXT_GATE
    ):
        raise VerificationError("D16 result identity/authority drift")
    expected_packed = {
        "checkpoint": packed["checkpoint"],
        "source_shard_manifest_sha256": packed["source_shard_manifest_sha256"],
        "source_shards": SOURCE_SHARDS,
        "packed_result_and_terminal_receipt_bound": True,
        "scientific_action_calls": 0,
    }
    _require_strict_equal(result["packed_source_audit"], expected_packed, "D16 packed source")
    manifest_summary = validate_manifest(manifest)
    if result["forensic_manifest_sha256"] != manifest_summary["manifest_sha256"]:
        raise VerificationError("D16 embedded forensic manifest binding drift")
    _require_strict_equal(result["legacy_full_action_disposition"], {
        "reported_target_sha256": EXPECTED_EXTERNAL["target_sha256"],
        "reported_target_records": EXPECTED_EXTERNAL["target_records"],
        "intended_shards": "0..52_once",
        "observed_retained_spool": "0..52_plus_duplicate_25..51",
        "target_to_spool_provenance_proven": False,
        "duplicate_gap_count": EXPECTED_EXTERNAL["gap_count"],
        "duplicate_records": EXPECTED_EXTERNAL["gap_records"],
        "duplicate_bytes": EXPECTED_EXTERNAL["gap_bytes"],
        "all_duplicate_gaps_exactly_match_receipt_chunks": True,
        "scientific_validity": "REJECTED_BROKEN_PRODUCTION_CUSTODY_ASSOCIATED_SPOOL_CONTAMINATED",
        "target_quarantined": True,
    }, "legacy full-action disposition")
    _require_strict_equal(result["publication_scope"], {
        "single_result_artifact": True,
        "staged_payload_fsync_and_rehash_before_no_replace_link": True,
        "result_is_terminal_execution_or_resource_receipt": False,
        "publication_resource_usage_attested": False,
    }, "D16 publication scope")

    resources = result["forensic_read_resource_observations"]
    _require_exact_keys(
        resources,
        {
            "cgroup_v2_enforced",
            "cgroup_path",
            "self_pid_listed",
            "fresh_scope_initial_events_zero",
            "memory_max_bytes",
            "memory_high_bytes",
            "memory_swap_max_bytes",
            "initial_memory_peak_bytes",
            "memory_peak_at_snapshot_bytes",
            "memory_current_at_snapshot_bytes",
            "swap_current_at_snapshot_bytes",
            "memory_events_before",
            "memory_events_at_snapshot",
            "memory_events_delta",
            "process_max_rss_bytes",
            "elapsed_monotonic_ns",
            "external_bytes_read",
            "read_chunk_bytes",
            "scientific_action_calls",
            "scope_ends_before_result_serialization_and_publication",
            "within_frozen_caps",
        },
        "D16 resource observations",
    )
    limits = contract["resource_limits"]
    integer_fields = {
        "memory_max_bytes",
        "memory_high_bytes",
        "memory_swap_max_bytes",
        "initial_memory_peak_bytes",
        "memory_peak_at_snapshot_bytes",
        "memory_current_at_snapshot_bytes",
        "swap_current_at_snapshot_bytes",
        "process_max_rss_bytes",
        "elapsed_monotonic_ns",
        "external_bytes_read",
        "read_chunk_bytes",
        "scientific_action_calls",
    }
    if any(type(resources[key]) is not int or resources[key] < 0 for key in integer_fields):
        raise VerificationError("D16 resource integer type drift")
    names = {"low", "high", "max", "oom", "oom_kill", "oom_group_kill"}
    for key in ("memory_events_before", "memory_events_at_snapshot", "memory_events_delta"):
        if set(resources[key]) != names or any(
            type(value) is not int or value < 0 for value in resources[key].values()
        ):
            raise VerificationError("D16 memory.events schema drift")
    if any(
        resources["memory_events_at_snapshot"][name]
        - resources["memory_events_before"][name]
        != resources["memory_events_delta"][name]
        for name in names
    ):
        raise VerificationError("D16 memory.events delta drift")
    expected_read_bytes = (
        SOURCE_BYTES
        + EXPECTED_EXTERNAL["spool_bytes"]
        + EXPECTED_EXTERNAL["target_bytes"]
        + sum(item["bytes"] for item in manifest["receipt_set"]["receipts"])
        + manifest["source_checkpoint"]["manifest_bytes"]
    )
    if (
        resources["cgroup_v2_enforced"] is not True
        or resources["self_pid_listed"] is not True
        or resources["fresh_scope_initial_events_zero"] is not True
        or not isinstance(resources["cgroup_path"], str)
        or not resources["cgroup_path"].startswith("/")
        or not resources["cgroup_path"].endswith(".scope")
        or resources["memory_max_bytes"] != limits["outer_memory_max_bytes"]
        or resources["memory_high_bytes"] != limits["outer_memory_high_bytes"]
        or resources["memory_swap_max_bytes"] != 0
        or resources["initial_memory_peak_bytes"] > limits["max_initial_cgroup_peak_bytes"]
        or resources["memory_peak_at_snapshot_bytes"]
        < resources["initial_memory_peak_bytes"]
        or resources["memory_peak_at_snapshot_bytes"] > limits["max_cgroup_peak_bytes"]
        or resources["memory_current_at_snapshot_bytes"]
        > resources["memory_peak_at_snapshot_bytes"]
        or resources["swap_current_at_snapshot_bytes"] != 0
        or resources["process_max_rss_bytes"] > limits["max_process_peak_rss_bytes"]
        or resources["elapsed_monotonic_ns"]
        > limits["internal_deadline_seconds"] * 1_000_000_000
        or resources["external_bytes_read"] != expected_read_bytes
        or resources["read_chunk_bytes"] != READ_CHUNK
        or resources["scientific_action_calls"] != 0
        or resources["scope_ends_before_result_serialization_and_publication"] is not True
        or resources["within_frozen_caps"] is not True
        or any(resources["memory_events_before"].values())
        or any(resources["memory_events_delta"].values())
    ):
        raise ResourceIndeterminate("D16 resource receipt exceeded frozen caps")
    return {
        "status": STATUS,
        "verified": True,
        "packed_source_admissible": True,
        "legacy_target_quarantined": True,
        "duplicate_records": EXPECTED_EXTERNAL["gap_records"],
        "manifest_sha256": manifest_summary["manifest_sha256"],
        "next_gate": NEXT_GATE,
    }


def verify_outcome(
    contract: Mapping[str, Any], contract_commit: str, outcome_commit: str
) -> dict[str, Any]:
    protocol = verify_protocol(contract, contract_commit)
    source_git = verify_source_git(contract)
    packed = audit_packed_checkpoint(contract)
    conditional = verify_conditional_cost_evidence(contract)
    outcome = _commit_record(outcome_commit)
    if outcome["parents"] != [contract_commit]:
        raise VerificationError("outcome must directly descend from contract freeze")
    diff = _diff_entries(outcome_commit)
    if ("A", RESULT_PATH) not in diff:
        raise ResourceIndeterminate("outcome lacks D16 forensic result")
    if diff != {("A", RESULT_PATH)}:
        raise VerificationError("outcome must add only the D16 forensic result")
    result_metadata = _blob_metadata(outcome_commit, RESULT_PATH)
    if (
        result_metadata[0] != "100644"
        or result_metadata[2] > contract["resource_limits"]["max_result_bytes"]
    ):
        raise VerificationError("D16 outcome result mode/size preflight drift")
    raw_result = _git("show", f"{outcome_commit}:{RESULT_PATH}")
    current_result = _read_git_bound_repo_artifact(
        RESULT_NAME,
        outcome_commit,
        len(raw_result),
        _hash_bytes(raw_result),
        contract["resource_limits"]["max_result_bytes"],
    )
    if raw_result != current_result:
        raise VerificationError("outcome/current D16 artifact drift")
    result_identity = _blob_identity(outcome_commit, RESULT_PATH)
    result = _load_json_bytes(raw_result)
    manifest = result.get("forensic_manifest")
    if not isinstance(manifest, dict):
        raise VerificationError("D16 embedded forensic manifest missing")
    evidence = validate_result(
        result,
        raw_result,
        manifest,
        protocol,
        source_git,
        packed,
        conditional,
        contract,
    )
    evidence["outcome_commit"] = outcome_commit
    evidence["outcome_tree"] = outcome["tree"]
    evidence["result_artifact"] = {
        "mode": result_identity[0],
        "blob": result_identity[1],
        "bytes": result_identity[2],
        "sha256": result_identity[3],
    }
    return evidence


def external_reverify(
    contract: Mapping[str, Any],
    contract_commit: str,
    outcome_commit: str,
    source_root: Path,
    run_root: Path,
) -> dict[str, Any]:
    static = verify_outcome(contract, contract_commit, outcome_commit)
    limits = contract["resource_limits"]
    started_ns = time.monotonic_ns()
    before = _read_cgroup()
    _check_cgroup(before, limits, initial=True)
    observed = audit_external_custody(
        contract,
        source_root,
        run_root,
        started_ns + limits["internal_deadline_seconds"] * 1_000_000_000,
    )
    raw_result = _read_git_bound_repo_artifact(
        RESULT_NAME,
        outcome_commit,
        _blob_identity(outcome_commit, RESULT_PATH)[2],
        _blob_identity(outcome_commit, RESULT_PATH)[3],
        limits["max_result_bytes"],
    )
    committed_result = _load_json_bytes(raw_result)
    committed = committed_result.get("forensic_manifest")
    if not _strict_equal(observed, committed):
        raise VerificationError("fresh external audit differs from committed forensic manifest")
    after = _read_cgroup()
    _check_cgroup(after, limits, initial=False)
    resource_check = _resource_record(before, after, limits, started_ns, observed)
    return {
        "status": STATUS,
        "verified": True,
        "mode": "external",
        "static": static,
        "external_manifest_bytes_equal": True,
        "external_manifest_sha256": _hash_bytes(_canonical_value(observed)),
        "resource_observations": resource_check,
        "scientific_action_calls": 0,
    }


def main(argv: list[str] | None = None) -> int:
    class StrictParser(argparse.ArgumentParser):
        def error(self, message: str) -> None:
            raise VerificationError(message)

    parser = StrictParser(allow_abbrev=False)
    parser.add_argument(
        "--mode", required=True, choices=("protocol", "audit", "static", "external")
    )
    parser.add_argument("--contract-commit", required=True)
    parser.add_argument("--outcome-commit")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--run-root", type=Path)
    try:
        args = parser.parse_args(argv)
        here_fd = _open_directory_nofollow(HERE)
        try:
            raw_contract = _read_member(here_fd, CONTRACT_NAME, 1_048_576)
        finally:
            os.close(here_fd)
        contract = _load_json_bytes(raw_contract)
        if args.mode in {"protocol", "static"} and (
            args.source_root is not None or args.run_root is not None
        ):
            raise VerificationError(f"{args.mode} mode forbids external root arguments")
        source_root = args.source_root or DEFAULT_SOURCE_ROOT
        run_root = args.run_root or DEFAULT_RUN_ROOT
        if args.mode == "protocol":
            if args.outcome_commit is not None:
                raise VerificationError("protocol mode forbids outcome commit")
            protocol = verify_protocol(contract, args.contract_commit)
            source_git = verify_source_git(contract)
            packed = audit_packed_checkpoint(contract)
            conditional = verify_conditional_cost_evidence(contract)
            evidence = {
                "contract_id": CONTRACT_ID,
                "status": PROTOCOL_STATUS,
                "verified": True,
                "mode": "protocol",
                "protocol": protocol,
                "source_git_audit": source_git,
                "packed_checkpoint_sha256": packed["checkpoint"][
                    "packed_sorted_binary_sha256"
                ],
                "conditional_D12_scientific_authority": conditional[
                    "D12_scientific_authority"
                ],
                "scientific_action_calls": 0,
                "next_gate": "OFFICIAL_EXTERNAL_CUSTODY_AUDIT",
            }
        elif args.mode == "audit":
            if args.outcome_commit is not None:
                raise VerificationError("audit mode forbids outcome commit")
            evidence = execute_audit(
                contract, args.contract_commit, source_root, run_root
            )
        elif args.mode == "static":
            if args.outcome_commit is None:
                raise VerificationError("static mode requires outcome commit")
            evidence = verify_outcome(contract, args.contract_commit, args.outcome_commit)
            evidence["mode"] = "static"
        else:
            if args.outcome_commit is None:
                raise VerificationError("external mode requires outcome commit")
            evidence = external_reverify(
                contract,
                args.contract_commit,
                args.outcome_commit,
                source_root,
                run_root,
            )
    except ResourceIndeterminate as exc:
        print(
            json.dumps(
                {
                    "status": "INDETERMINATE_D16_EXTERNAL_CUSTODY_AUDIT",
                    "verified": False,
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return 2
    except (
        VerificationError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(
            json.dumps(
                {"status": "VERIFICATION_FAILED", "verified": False, "error": str(exc)},
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
