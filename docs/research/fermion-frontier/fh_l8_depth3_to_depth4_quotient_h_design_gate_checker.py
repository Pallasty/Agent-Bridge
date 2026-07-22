#!/usr/bin/env python3
"""Static design gate for the FH-L8 depth-3 to depth-4 quotient-H action.

This checker is intentionally unable to execute the scientific workload.  It
only verifies Git/raw-byte custody, JSON scope, and integer resource arithmetic.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
CHECKER_PATH = "docs/research/fermion-frontier/fh_l8_depth3_to_depth4_quotient_h_design_gate_checker.py"
CONTRACT_PATH = "docs/research/fermion-frontier/fh_l8_depth3_to_depth4_quotient_h_design_gate_contract.json"
CONTRACT = HERE / Path(CONTRACT_PATH).name
CONTRACT_ID = "FH-L8-QUOTIENT-H-D3-TO-D4-DESIGN-GATE-V1"
STATUS = "VERIFIED_D7_QUOTIENT_H_DESIGN_GATE_FROZEN_NO_EXECUTION_AUTHORITY"
RESOURCE_NO_GO = "NO_GO_D7_QUOTIENT_H_STATIC_RESOURCE_CEILING"
BASE_COMMIT = "72e1e56af49b91267738d0b0108640f358fde59a"
BASE_TREE = "bd49157c6aa367b802cc724d27763a6c4903f590"
FULL_ALIAS = "FH-L8-D5-EVIDENCE-SYMMETRY-ORBIT-QUOTIENT-V1"
SUPPORT_ALIAS = "FH-L8-D6-EVIDENCE-BYTE-TABLE-SUPPORT-ORBIT-V1"
SHA_RE = re.compile(r"[0-9a-f]{40}")

FORBIDDEN_DESIGN_PATHS = [
    "docs/research/fermion-frontier/fh_l8_depth3_to_depth4_quotient_h_design_gate_result.json",
    "docs/research/fermion-frontier/fh_l8_depth3_to_depth4_quotient_h_runner.py",
    "docs/research/fermion-frontier/fh_l8_depth3_to_depth4_quotient_h_implementation.py",
]

R2_ARTIFACTS = [
    {
        "path": "fh_l8_d5_d6_descendant_reconciliation_checker.py",
        "mode": "100644",
        "blob": "5603bb299f97637a89bebb8055383fc65eb4d660",
        "bytes": 15391,
        "sha256": "4133a98f19f55db95b213fc6df8f4f0127b090152d1c1acd51e98794508a4fed",
    },
    {
        "path": "fh_l8_d5_d6_descendant_reconciliation.json",
        "mode": "100644",
        "blob": "cc66769b97d9f8a8211ac1892e73c67ecc4ceed4",
        "bytes": 5537,
        "sha256": "4f169897212704091b120d1380782cc2a61c17de0d01611259e97a7cb99e852e",
    },
    {
        "path": "FH_L8_D5_D6_DESCENDANT_RECONCILIATION_ZH.md",
        "mode": "100644",
        "blob": "e8367b32914cd15f3dbd44fd927d63894cec688a",
        "bytes": 2578,
        "sha256": "8d1f4afbb44e1d7f2885cbb4dcd13860261b0b447d1395fa6fd666d675ec482a",
    },
]

FULL_ARTIFACTS = [
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

SUPPORT_ARTIFACTS = [
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

EXPECTED_ARITHMETIC = {
    "source_representatives": 213099,
    "row_term_upper_bound_per_source": 225,
    "hopping_terms_per_source": 224,
    "diagonal_terms_per_source": 1,
    "symmetry_group_order": 8,
    "raw_candidate_action_upper_bound": 47947275,
    "candidate_canonicalization_upper_bound": 47947275,
    "candidate_group_image_upper_bound": 383578200,
    "source_canonicality_group_image_upper_bound": 1704792,
    "total_group_image_upper_bound": 385282992,
    "byte_table_lookups_per_group_image": 16,
    "candidate_byte_table_lookup_upper_bound": 6137251200,
    "source_byte_table_lookup_upper_bound": 27276672,
    "total_byte_table_lookup_upper_bound": 6164527872,
    "inherited_d5b_raw_candidate_cap": 300000000,
}

EXPECTED_SCHEDULE = {
    "source_shard_size": 4096,
    "source_shard_count": 53,
    "full_source_shards": 52,
    "last_source_shard_size": 107,
    "source_microbatch_size": 512,
    "max_raw_candidate_actions_per_full_shard": 921600,
    "max_candidate_group_images_per_full_shard": 7372800,
    "max_source_group_images_per_full_shard": 32768,
    "max_total_group_images_per_full_shard": 7405568,
    "target_hash_partitions": 256,
    "fixed_width_spill_record_bytes": 32,
    "max_primary_spool_bytes": 1534312800,
    "max_sort_chunk_records": 262144,
    "max_sort_chunk_bytes": 8388608,
    "max_double_sort_buffer_bytes": 16777216,
    "max_merge_fan_in": 32,
    "merge_fd_reserve": 4,
    "max_open_file_descriptors": 64,
    "max_io_chunk_bytes": 8388608,
}

EXPECTED_NUMERIC_BOUNDS = {
    "common_denominator": 8,
    "row_absolute_l1_upper_bound": 352,
    "source_amplitude_absolute_upper_bound": 43614208,
    "target_amplitude_absolute_upper_bound": 15352201216,
    "scaled_target_amplitude_absolute_upper_bound": 122817609728,
    "single_raw_scaled_delta_absolute_upper_bound": 357287591936,
    "all_raw_records_partial_sum_absolute_upper_bound": 17130966424643174400,
    "raw_scaled_delta_fits_signed_i64": True,
    "global_merge_accumulator_requires_signed_i128": True,
}

EXPECTED_AUTHORITY = {
    "design_protocol_frozen": True,
    "static_integer_arithmetic_verified": True,
    "next_packed_source_checkpoint_protocol_design_eligible": True,
    "implementation_present": False,
    "source_vector_materialized_in_this_unit": False,
    "bounded_preflight_executed": False,
    "runtime_feasibility_certified": False,
    "memory_feasibility_certified": False,
    "target_cardinality_known": False,
    "depth3_to_depth4_execution_authorized": False,
    "depth3_to_depth4_quotient_hamiltonian_action_executed": False,
    "fourth_krylov_hamiltonian_action_executed": False,
    "target_vector_materialized": False,
    "degree6_remainder_bounded": False,
    "two_step_cumulative_error_bounded": False,
    "full_R100_error_bounded": False,
    "physical_reference_qualified": False,
    "hardware_result_available": False,
    "quantum_advantage_claimed": False,
    "ready_gate_eligible": False,
}


class VerificationError(ValueError):
    """The frozen design or its custody chain drifted."""


def _root() -> str:
    return _git("rev-parse", "--show-toplevel").decode("utf-8").strip()


def _git(*args: str) -> bytes:
    root = subprocess.check_output(
        ["git", "-C", str(HERE), "rev-parse", "--show-toplevel"],
        stderr=subprocess.DEVNULL,
    ).decode("utf-8").strip()
    return subprocess.check_output(
        ["git", "-C", root, *args], stderr=subprocess.DEVNULL
    )


def _load_json_bytes(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise VerificationError("JSON root must be an object")
    return value


def _commit_record(commit: str) -> dict[str, Any]:
    if not isinstance(commit, str) or SHA_RE.fullmatch(commit) is None:
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
    if record != expected:
        raise VerificationError("commit record drift")
    if _commit_record(str(record["commit"])) != expected:
        raise VerificationError("Git commit topology drift")


def _path_exists(commit: str, path: str) -> bool:
    try:
        _git("cat-file", "-e", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        return False
    return True


def _verify_artifacts(
    commit: str,
    artifacts: Any,
    expected: list[dict[str, Any]],
) -> dict[str, bytes]:
    if artifacts != expected:
        raise VerificationError("artifact pin family drift")
    loaded: dict[str, bytes] = {}
    for artifact in expected:
        relative = f"docs/research/fermion-frontier/{artifact['path']}"
        raw = _git("show", f"{commit}:{relative}")
        entry = _git("ls-tree", commit, relative).decode("ascii").split()
        if len(entry) < 3 or entry[0] != artifact["mode"] or entry[2] != artifact["blob"]:
            raise VerificationError(f"Git artifact identity drift: {artifact['path']}")
        if len(raw) > 1048576:
            raise VerificationError(f"source artifact exceeds static checker cap: {artifact['path']}")
        if len(raw) != artifact["bytes"] or hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
            raise VerificationError(f"raw artifact identity drift: {artifact['path']}")
        if (HERE / artifact["path"]).read_bytes() != raw:
            raise VerificationError(f"working artifact drift: {artifact['path']}")
        loaded[artifact["path"]] = raw
    return loaded


def _verify_chronology(contract: Mapping[str, Any], contract_commit: str) -> dict[str, Any]:
    chronology = contract["chronology"]
    if set(chronology) != {
        "evidence_baseline",
        "checker_freeze",
        "checker_artifact",
        "contract_path",
        "forbidden_design_paths",
        "checker_must_precede_contract",
    }:
        raise VerificationError("chronology schema drift")
    baseline = {
        "commit": BASE_COMMIT,
        "tree": BASE_TREE,
        "parents": ["cbd5668e42c6a73237a31a07112466dfc8a80739"],
    }
    _verify_commit(chronology["evidence_baseline"], baseline)
    freeze = chronology["checker_freeze"]
    if set(freeze) != {"commit", "tree", "parents"}:
        raise VerificationError("checker freeze schema drift")
    if freeze["parents"] != [BASE_COMMIT]:
        raise VerificationError("checker freeze must directly descend from R2")
    _verify_commit(freeze, freeze)
    checker_diff = _git(
        "diff-tree", "--no-commit-id", "--name-status", "-r", freeze["commit"]
    ).decode("utf-8").splitlines()
    if checker_diff != [f"A\t{CHECKER_PATH}"]:
        raise VerificationError("checker freeze must add only the checker")
    checker_pin = chronology["checker_artifact"]
    if set(checker_pin) != {"path", "mode", "blob", "bytes", "sha256"}:
        raise VerificationError("checker artifact schema drift")
    if checker_pin["path"] != Path(CHECKER_PATH).name:
        raise VerificationError("checker artifact path drift")
    _verify_artifacts(freeze["commit"], [checker_pin], [dict(checker_pin)])
    if checker_pin["sha256"] != contract["checker_self_sha256"]:
        raise VerificationError("checker self pin disagreement")
    if _path_exists(freeze["commit"], CONTRACT_PATH):
        raise VerificationError("contract existed before checker freeze")
    for path in FORBIDDEN_DESIGN_PATHS:
        if _path_exists(freeze["commit"], path):
            raise VerificationError("execution artifact existed in checker freeze")
    if chronology["contract_path"] != CONTRACT_PATH:
        raise VerificationError("contract path drift")
    if chronology["forbidden_design_paths"] != FORBIDDEN_DESIGN_PATHS:
        raise VerificationError("forbidden path policy drift")
    if chronology["checker_must_precede_contract"] is not True:
        raise VerificationError("checker-before-contract gate disabled")

    contract_record = _commit_record(contract_commit)
    if contract_record["parents"] != [freeze["commit"]]:
        raise VerificationError("contract commit must directly descend from checker freeze")
    contract_diff = _git(
        "diff-tree", "--no-commit-id", "--name-status", "-r", contract_commit
    ).decode("utf-8").splitlines()
    if contract_diff != [f"A\t{CONTRACT_PATH}"]:
        raise VerificationError("contract freeze must add only the contract")
    if _git("show", f"{contract_commit}:{CONTRACT_PATH}") != CONTRACT.read_bytes():
        raise VerificationError("working contract differs from frozen contract commit")
    if _git("show", f"{contract_commit}:{CHECKER_PATH}") != (HERE / Path(CHECKER_PATH).name).read_bytes():
        raise VerificationError("checker changed after its freeze")
    for path in FORBIDDEN_DESIGN_PATHS:
        if _path_exists(contract_commit, path):
            raise VerificationError("execution artifact exists in contract freeze")
    subprocess.check_call(
        ["git", "-C", _root(), "merge-base", "--is-ancestor", contract_commit, "HEAD"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    matches = []
    for path in _git(
        "ls-tree", "-r", "--name-only", contract_commit, "docs/research/fermion-frontier"
    ).decode("utf-8").splitlines():
        if path.endswith(".json") and CONTRACT_ID.encode("ascii") in _git("show", f"{contract_commit}:{path}"):
            matches.append(path)
    if matches != [CONTRACT_PATH]:
        raise VerificationError("contract id is not globally unique in frozen JSON artifacts")
    return {
        "checker_freeze_commit": freeze["commit"],
        "checker_freeze_tree": freeze["tree"],
        "contract_freeze_commit": contract_record["commit"],
        "contract_freeze_tree": contract_record["tree"],
        "checker_preceded_contract": True,
        "execution_artifacts_absent": True,
    }


def _verify_sources(contract: Mapping[str, Any]) -> dict[str, Any]:
    source = contract["source_evidence"]
    if set(source) != {
        "reconciliation",
        "full_quotient_semantics_lane",
        "support_orbit_lane",
        "relationship",
    }:
        raise VerificationError("source evidence schema drift")
    reconciliation = source["reconciliation"]
    expected_r2_commit = {
        "commit": BASE_COMMIT,
        "tree": BASE_TREE,
        "parents": ["cbd5668e42c6a73237a31a07112466dfc8a80739"],
    }
    if set(reconciliation) != {"reconciliation_id", "status", "commit_record", "artifacts"}:
        raise VerificationError("R2 source schema drift")
    if (
        reconciliation["reconciliation_id"] != "FH-L8-D5-D6-DESCENDANT-R2"
        or reconciliation["status"] != "VERIFIED_D5_D6_DESCENDANT_SCOPE_RECONCILIATION"
    ):
        raise VerificationError("R2 source identity drift")
    _verify_commit(reconciliation["commit_record"], expected_r2_commit)
    r2_loaded = _verify_artifacts(BASE_COMMIT, reconciliation["artifacts"], R2_ARTIFACTS)

    full = source["full_quotient_semantics_lane"]
    if set(full) != {
        "route_alias",
        "legacy_contract_id",
        "scope",
        "preregistration_evidence",
        "protocol_freeze",
        "outcome",
        "artifacts",
    }:
        raise VerificationError("full quotient lane schema drift")
    if (
        full["route_alias"] != FULL_ALIAS
        or full["legacy_contract_id"] != "FH-L8-INDEPENDENT-REFERENCE-D5"
        or full["scope"] != "full_depth3_symmetry_quotient_and_depth0_to_depth3_transition_semantics"
        or full["preregistration_evidence"] is not True
    ):
        raise VerificationError("full quotient lane identity/scope drift")
    _verify_commit(
        full["protocol_freeze"],
        {
            "commit": "6daf30daeeb375962b9986af5df91517d8a4a8ec",
            "tree": "9c7096bca41a1da8c440f37d93a08a4f51e5cef0",
            "parents": ["ae3935774d80f37b10f8317d0e17d339f03436cc"],
        },
    )
    _verify_commit(
        full["outcome"],
        {
            "commit": "2f9556a986c50a42ff3096ded45b75e39c5a61a9",
            "tree": "c1164c1acffb570448038b461cc619ca5164d2f9",
            "parents": ["6daf30daeeb375962b9986af5df91517d8a4a8ec"],
        },
    )
    full_loaded = _verify_artifacts(full["outcome"]["commit"], full["artifacts"], FULL_ARTIFACTS)

    support = source["support_orbit_lane"]
    if set(support) != {
        "route_alias",
        "legacy_contract_id",
        "resolved_parent_evidence_lane_alias",
        "scope",
        "preregistration_evidence",
        "outcome",
        "integration",
        "artifacts",
    }:
        raise VerificationError("support orbit lane schema drift")
    if (
        support["route_alias"] != SUPPORT_ALIAS
        or support["legacy_contract_id"] != "FH-L8-INDEPENDENT-REFERENCE-D6"
        or support["resolved_parent_evidence_lane_alias"] != "FH-L8-D5-EVIDENCE-SIGNED-D4-PREFIX-V1"
        or support["scope"] != "full_depth3_signed_support_orbit_enumeration_only"
        or support["preregistration_evidence"] is not False
    ):
        raise VerificationError("support orbit lane identity/scope drift")
    _verify_commit(
        support["outcome"],
        {
            "commit": "e45b5b9f68520289d3396c0af071019856afe56e",
            "tree": "80724d12483ec39e0926ca4bfa341c6483eb27f9",
            "parents": ["64438c47be710835626dea0ceb2521b6634951dc"],
        },
    )
    _verify_commit(
        support["integration"],
        {
            "commit": "77475550b96dee1a862e9f11046de8b097d9d063",
            "tree": "559aac3cf352da8152531242374b13688fd83648",
            "parents": [
                "ec5777e284585377896e7e50503a54dcd95a9b82",
                "e45b5b9f68520289d3396c0af071019856afe56e",
            ],
        },
    )
    support_loaded = _verify_artifacts(
        support["outcome"]["commit"], support["artifacts"], SUPPORT_ARTIFACTS
    )
    if source["relationship"] != {
        "shared_D4_inputs": True,
        "evidence_is_additive": False,
        "bare_legacy_contract_id_lookup_forbidden": True,
        "full_lane_supplies_signed_quotient_amplitude_semantics": True,
        "support_lane_supplies_complementary_byte_table_support_canonicalization": True,
        "support_lane_does_not_supply_quotient_hamiltonian_amplitudes": True,
    }:
        raise VerificationError("source relationship drift")

    r2 = _load_json_bytes(r2_loaded["fh_l8_d5_d6_descendant_reconciliation.json"])
    full_result = _load_json_bytes(full_loaded["fh_l8_symmetry_orbit_quotient_d5_result.json"])
    support_result = _load_json_bytes(support_loaded["fh_l8_byte_table_orbit_d6_result.json"])
    selection = r2.get("selection", {})
    if (
        selection.get("required_full_quotient_semantics_route_alias") != FULL_ALIAS
        or selection.get("complementary_support_orbit_route_alias") != SUPPORT_ALIAS
        or selection.get("evidence_is_additive") is not False
        or selection.get("future_contract_id_policy")
        != "new_globally_unique_route_specific_id_required"
    ):
        raise VerificationError("R2 route selection drift")
    depth3 = full_result["krylov_prefix"]["depth_records"][3]
    if (
        depth3.get("full_state_count") != 1704285
        or depth3.get("orbit_representative_count") != 213099
        or depth3.get("deterministic_insertion_order_quotient_sha256")
        != "7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e"
    ):
        raise VerificationError("D5B full quotient input drift")
    if support_result.get("depth3_orbit") != {
        "digest": "7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26",
        "orbits": 213099,
        "states": 1704285,
    }:
        raise VerificationError("D6 support orbit input drift")
    if support_result.get("fourth_layer_feasibility") != "NOT_EXECUTED_OR_CERTIFIED":
        raise VerificationError("D6 authority boundary drift")
    return {
        "r2_reconciliation_verified": True,
        "full_quotient_semantics_alias": FULL_ALIAS,
        "support_orbit_alias": SUPPORT_ALIAS,
        "shared_depth3_counts": {"full_states": 1704285, "representatives": 213099},
        "evidence_is_additive": False,
    }


def _verify_workload_and_arithmetic(contract: Mapping[str, Any]) -> dict[str, int]:
    if contract["workload"] != {
        "linear_size": 8,
        "boundary": "square_open_boundary_no_wrap",
        "particle_sector": "N_up=32,N_down=32",
        "source_depth": 3,
        "target_depth": 4,
        "operation": "fourth_krylov_hamiltonian_action_in_symmetry_quotient_coordinates",
        "source_full_state_count": 1704285,
        "source_representative_count": 213099,
        "source_full_vector_digest": "6f8f53101b8a3ec0b3dfcee624a014426d93a8aa0dfc1300780b0ad99b765e97",
        "source_quotient_digest": "7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e",
        "source_orbit_size_histogram": {"1": 1, "4": 125, "8": 212973},
        "support_orbit_digest": "7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26",
        "source_vector_artifact_present": False,
        "source_replay_required_before_future_run": True,
        "action_executed_in_this_unit": False,
    }:
        raise VerificationError("workload scope drift")
    arithmetic = contract["design_arithmetic"]
    if arithmetic != EXPECTED_ARITHMETIC:
        raise VerificationError("design arithmetic drift")
    if arithmetic["hopping_terms_per_source"] + arithmetic["diagonal_terms_per_source"] != arithmetic[
        "row_term_upper_bound_per_source"
    ]:
        raise VerificationError("Hamiltonian row decomposition arithmetic drift")
    raw = arithmetic["source_representatives"] * arithmetic["row_term_upper_bound_per_source"]
    candidate_images = raw * arithmetic["symmetry_group_order"]
    source_images = arithmetic["source_representatives"] * arithmetic["symmetry_group_order"]
    candidate_lookups = candidate_images * arithmetic["byte_table_lookups_per_group_image"]
    source_lookups = source_images * arithmetic["byte_table_lookups_per_group_image"]
    if (
        raw != arithmetic["raw_candidate_action_upper_bound"]
        or raw != arithmetic["candidate_canonicalization_upper_bound"]
        or candidate_images != arithmetic["candidate_group_image_upper_bound"]
        or source_images != arithmetic["source_canonicality_group_image_upper_bound"]
        or candidate_images + source_images != arithmetic["total_group_image_upper_bound"]
        or candidate_lookups != arithmetic["candidate_byte_table_lookup_upper_bound"]
        or source_lookups != arithmetic["source_byte_table_lookup_upper_bound"]
        or candidate_lookups + source_lookups
        != arithmetic["total_byte_table_lookup_upper_bound"]
        or raw > arithmetic["inherited_d5b_raw_candidate_cap"]
    ):
        raise VerificationError("integer resource derivation failed")
    return dict(arithmetic)


def evaluate_resource_gate(
    arithmetic: Mapping[str, int], caps: Mapping[str, int]
) -> dict[str, Any]:
    gates = {
        "raw_candidate_actions_within_cap": arithmetic["raw_candidate_action_upper_bound"]
        <= caps["max_raw_candidate_actions"],
        "candidate_canonicalizations_within_cap": arithmetic[
            "candidate_canonicalization_upper_bound"
        ]
        <= caps["max_candidate_canonicalizations"],
        "candidate_group_images_within_cap": arithmetic["candidate_group_image_upper_bound"]
        <= caps["max_candidate_group_images"],
        "source_group_images_within_cap": arithmetic["source_canonicality_group_image_upper_bound"]
        <= caps["max_source_canonicality_group_images"],
        "total_group_images_within_cap": arithmetic["total_group_image_upper_bound"]
        <= caps["max_total_group_images"],
    }
    return {
        "status": STATUS if all(gates.values()) else RESOURCE_NO_GO,
        "gates": gates,
        "execution_authorized": False,
    }


def _verify_algorithm_and_resources(
    contract: Mapping[str, Any], arithmetic: Mapping[str, int]
) -> dict[str, Any]:
    if contract["algorithm_contract"] != {
        "source_order": "ascending_128bit_representative",
        "row_term_order": "224_sorted_hopping_terms_then_one_diagonal_term",
        "source_preparation": "separate_hash_bound_packed_D5B_depth3_quotient_checkpoint_required",
        "candidate_materialization": "one_candidate_at_a_time_never_full_candidate_set",
        "support_canonicalization": "D6_byte_tables_may_nominate_support_representative_only",
        "signed_quotient_semantics": "D5B_CAR_phase_orbit_size_and_projected_zero_rules_are_mandatory",
        "cross_lane_check": "byte_table_support_representative_must_equal_D5B_signed_representative",
        "coefficient_arithmetic": "scaled8_signed_i64_records_checked_signed_i128_merge_then_exact_divide_by_8",
        "contribution_formula": "scaled8=q3_amp*H_coeff*CAR_phase*source_orbit_size*(8/target_orbit_size)",
        "partitioning": "first_SHA256_digest_byte_of_u128_big_endian_target_selects_one_of_256_partitions",
        "merge": "bounded_32_way_target_order_checked_i128_sum_divisibility_drop_zero_then_digest",
        "checkpoint": "fsync_manifest_after_each_source_shard_with_exact_counters_and_hashes",
        "resume": "only_from_hash_bound_complete_shard_boundary",
        "memory_probe": "read_cgroup_v2_memory.current_before_microbatch_spill_and_merge",
        "page_cache_policy": "bounded_IO_and_fadvise_DONTNEED_or_equivalent_after_durable_spill",
        "scratch_filesystem": "non_tmpfs_non_ramfs_required",
        "workers": 1,
        "abort_policy": "fail_closed_before_next_allocation_on_any_cap_or_digest_drift",
    }:
        raise VerificationError("algorithm contract drift")
    limits = contract["design_checker_limits"]
    if limits != {
        "max_source_bytes_per_artifact": 1048576,
        "maximum_seconds": 15,
        "allowed_operations": ["git_metadata", "raw_sha256", "json_parse", "integer_arithmetic"],
        "scientific_state_iteration_allowed": False,
        "scientific_action_execution_allowed": False,
    }:
        raise VerificationError("design checker limits drift")
    planning = contract["future_runner_planning_caps"]
    if set(planning) != {
        "outer_memory_max_bytes",
        "outer_swap_max_bytes",
        "memory_high_water_abort_bytes",
        "max_process_peak_rss_bytes",
        "max_live_algorithm_buffer_bytes",
        "internal_deadline_seconds",
        "outer_deadline_seconds",
        "max_raw_candidate_actions",
        "max_candidate_canonicalizations",
        "max_candidate_group_images",
        "max_source_canonicality_group_images",
        "max_total_group_images",
        "schedule",
        "packed_source_checkpoint",
        "max_live_scratch_bytes",
        "max_cumulative_spill_write_bytes",
        "max_created_files",
        "preflight",
        "performance_evidence",
    }:
        raise VerificationError("future runner planning schema drift")
    exact_maxima = {
        "outer_memory_max_bytes": 1073741824,
        "outer_swap_max_bytes": 0,
        "memory_high_water_abort_bytes": 805306368,
        "max_process_peak_rss_bytes": 536870912,
        "max_live_algorithm_buffer_bytes": 134217728,
        "internal_deadline_seconds": 1800,
        "outer_deadline_seconds": 1830,
        "max_raw_candidate_actions": EXPECTED_ARITHMETIC["raw_candidate_action_upper_bound"],
        "max_candidate_canonicalizations": EXPECTED_ARITHMETIC[
            "candidate_canonicalization_upper_bound"
        ],
        "max_candidate_group_images": EXPECTED_ARITHMETIC["candidate_group_image_upper_bound"],
        "max_source_canonicality_group_images": EXPECTED_ARITHMETIC[
            "source_canonicality_group_image_upper_bound"
        ],
        "max_total_group_images": EXPECTED_ARITHMETIC["total_group_image_upper_bound"],
    }
    for name, maximum in exact_maxima.items():
        value = planning[name]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise VerificationError(f"invalid planning cap: {name}")
        if value > maximum:
            raise VerificationError(f"planning cap uplift: {name}")
    if planning["outer_swap_max_bytes"] != 0:
        raise VerificationError("swap must remain disabled")
    if planning["schedule"] != EXPECTED_SCHEDULE:
        raise VerificationError("streaming schedule drift")
    schedule = planning["schedule"]
    if (
        schedule["full_source_shards"] * schedule["source_shard_size"]
        + schedule["last_source_shard_size"]
        != arithmetic["source_representatives"]
        or schedule["source_shard_count"] != schedule["full_source_shards"] + 1
        or schedule["source_shard_size"] * arithmetic["row_term_upper_bound_per_source"]
        != schedule["max_raw_candidate_actions_per_full_shard"]
        or schedule["max_raw_candidate_actions_per_full_shard"]
        * arithmetic["symmetry_group_order"]
        != schedule["max_candidate_group_images_per_full_shard"]
        or schedule["source_shard_size"] * arithmetic["symmetry_group_order"]
        != schedule["max_source_group_images_per_full_shard"]
        or schedule["max_candidate_group_images_per_full_shard"]
        + schedule["max_source_group_images_per_full_shard"]
        != schedule["max_total_group_images_per_full_shard"]
        or arithmetic["raw_candidate_action_upper_bound"]
        * schedule["fixed_width_spill_record_bytes"]
        != schedule["max_primary_spool_bytes"]
        or schedule["max_sort_chunk_records"] * schedule["fixed_width_spill_record_bytes"]
        != schedule["max_sort_chunk_bytes"]
        or 2 * schedule["max_sort_chunk_bytes"] != schedule["max_double_sort_buffer_bytes"]
        or schedule["max_merge_fan_in"] + schedule["merge_fd_reserve"]
        > schedule["max_open_file_descriptors"]
    ):
        raise VerificationError("streaming schedule arithmetic drift")
    if (
        planning["max_live_algorithm_buffer_bytes"] > planning["max_process_peak_rss_bytes"]
        or planning["max_process_peak_rss_bytes"] > planning["memory_high_water_abort_bytes"]
        or planning["memory_high_water_abort_bytes"] >= planning["outer_memory_max_bytes"]
    ):
        raise VerificationError("memory planning does not preserve OOM headroom")
    if planning["packed_source_checkpoint"] != {
        "required_before_action": True,
        "record_bytes": 32,
        "record_count": 213099,
        "maximum_bytes": 6819168,
        "certified_in_this_unit": False,
    }:
        raise VerificationError("packed source checkpoint boundary drift")
    if (
        planning["max_live_scratch_bytes"] != 4294967296
        or planning["max_cumulative_spill_write_bytes"] != 8589934592
        or planning["max_created_files"] != 1024
    ):
        raise VerificationError("scratch planning cap drift")
    if planning["preflight"] != {
        "required_before_any_full_run": True,
        "max_source_representatives": 4096,
        "new_authorization_required": True,
        "scientific_authority": False,
        "full_run_authority": False,
    }:
        raise VerificationError("preflight boundary drift")
    if planning["performance_evidence"] != {
        "runtime_projection_available": False,
        "measured_peak_RSS_available": False,
        "target_cardinality_available": False,
        "D6_240_second_cap_reusable": False,
        "D6_unretained_14_856_seconds_certifying": False,
        "deadlines_are_provisional_stop_rules_not_predictions": True,
    }:
        raise VerificationError("performance evidence uplift")
    return evaluate_resource_gate(arithmetic, planning)


def recompute(contract: Mapping[str, Any], contract_commit: str) -> dict[str, Any]:
    if set(contract) != {
        "schema_version",
        "contract_id",
        "status",
        "analysis_class",
        "checker_self_sha256",
        "chronology",
        "source_evidence",
        "workload",
        "coordinate_convention",
        "design_arithmetic",
        "numeric_bounds",
        "kpis",
        "algorithm_contract",
        "design_checker_limits",
        "future_runner_planning_caps",
        "decision_rule",
        "authority",
        "forbidden_claims",
    }:
        raise VerificationError("contract schema drift")
    if (
        contract["schema_version"] != 1
        or contract["contract_id"] != CONTRACT_ID
        or contract["status"] != "FROZEN_DESIGN_ONLY_NO_DEPTH3_TO_DEPTH4_EXECUTION_AUTHORITY"
        or contract["analysis_class"]
        != "STATIC_GIT_HASH_JSON_AND_INTEGER_ARITHMETIC_DESIGN_GATE"
    ):
        raise VerificationError("contract identity/status drift")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != contract["checker_self_sha256"]:
        raise VerificationError("checker self pin drift")
    chronology = _verify_chronology(contract, contract_commit)
    sources = _verify_sources(contract)
    arithmetic = _verify_workload_and_arithmetic(contract)
    if contract["coordinate_convention"] != {
        "stored_source_value": "canonical_representative_full_basis_per_state_amplitude",
        "orbit_reconstruction": "a[g*r]=fermionic_phase(g,r)*a[r]",
        "orbit_average_coefficients_used": False,
        "target_update": "q4[t]+=q3[s]*H[x,s]*phase(x_to_t)*source_orbit_size/target_orbit_size",
        "streaming_integer_scale": 8,
        "D6_support_table_supplies_phase": False,
        "D5B_signed_CAR_semantics_mandatory": True,
    }:
        raise VerificationError("quotient coordinate convention drift")
    if contract["numeric_bounds"] != EXPECTED_NUMERIC_BOUNDS:
        raise VerificationError("fraction-free numeric bound drift")
    numeric = contract["numeric_bounds"]
    if (
        numeric["source_amplitude_absolute_upper_bound"]
        != numeric["row_absolute_l1_upper_bound"] ** 3
        or numeric["target_amplitude_absolute_upper_bound"]
        != numeric["row_absolute_l1_upper_bound"] ** 4
        or numeric["scaled_target_amplitude_absolute_upper_bound"]
        != numeric["common_denominator"] * numeric["target_amplitude_absolute_upper_bound"]
        or numeric["all_raw_records_partial_sum_absolute_upper_bound"]
        != numeric["single_raw_scaled_delta_absolute_upper_bound"]
        * arithmetic["raw_candidate_action_upper_bound"]
    ):
        raise VerificationError("fraction-free numeric arithmetic drift")
    resource_decision = _verify_algorithm_and_resources(contract, arithmetic)
    if contract["kpis"] != {
        "semantic_input": "D5B_signed_quotient_semantics_and_D6_support_canonicalization_remain_distinct",
        "equivalence_input": "shared_depth3_counts_only_no_digest_or_quotient_H_equivalence_claim",
        "resource_primary": "raw_candidate_actions_and_group_images_are_independent_counters",
        "guardrails": [
            "no_scientific_action_in_design_checker",
            "no_runtime_or_target_cardinality_inference",
            "no_execution_authority",
        ],
    }:
        raise VerificationError("KPI separation drift")
    if contract["decision_rule"] != {
        "source_chronology_schema_or_arithmetic_failure": "VERIFICATION_FAILED",
        "any_static_resource_cap_below_bound": RESOURCE_NO_GO,
        "all_design_gates_true": STATUS,
        "execution_authority_on_any_outcome": False,
        "next_gate": "SEPARATE_PACKED_DEPTH3_QUOTIENT_CHECKPOINT_PROTOCOL_REQUIRED",
    }:
        raise VerificationError("decision rule drift")
    if contract["authority"] != EXPECTED_AUTHORITY:
        raise VerificationError("authority uplift or drift")
    if contract["forbidden_claims"] != [
        "No depth-3 to depth-4 quotient Hamiltonian action is authorized or executed.",
        "No packed depth-3 source checkpoint, fourth Krylov Hamiltonian action, target vector, target cardinality, runtime, or memory feasibility is certified.",
        "The D6 240-second cap and unretained 14.856-second console observation are not extrapolated.",
        "D5B and D6 share D4 inputs and provide complementary non-additive scopes; digest or quotient-H equivalence is not claimed.",
        "No degree-six remainder, cumulative, R100, physical-reference, hardware, quantum-advantage, or READY claim is certified.",
    ]:
        raise VerificationError("forbidden claim boundary drift")
    return {
        "contract_id": CONTRACT_ID,
        "status": resource_decision["status"],
        "verified": True,
        "chronology": chronology,
        "source_evidence": sources,
        "design_arithmetic": arithmetic,
        "numeric_bounds": dict(EXPECTED_NUMERIC_BOUNDS),
        "resource_decision": resource_decision,
        "max_process_peak_rss_bytes": contract["future_runner_planning_caps"][
            "max_process_peak_rss_bytes"
        ],
        "memory_high_water_abort_bytes": contract["future_runner_planning_caps"][
            "memory_high_water_abort_bytes"
        ],
        "outer_memory_max_bytes": contract["future_runner_planning_caps"]["outer_memory_max_bytes"],
        "authority": dict(EXPECTED_AUTHORITY),
        "next_gate": contract["decision_rule"]["next_gate"],
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] != "--contract-commit":
        print(
            json.dumps(
                {
                    "status": "VERIFICATION_FAILED",
                    "verified": False,
                    "error": "usage: checker.py --contract-commit <full-commit>",
                },
                sort_keys=True,
            )
        )
        return 1
    try:
        evidence = recompute(_load_json_bytes(CONTRACT.read_bytes()), args[1])
    except (
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        VerificationError,
        ValueError,
        TypeError,
        KeyError,
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
